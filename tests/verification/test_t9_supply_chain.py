"""The T9 verifier is exercised with inert synthetic package and evidence data."""

from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/verification"))
import check_t9_supply_chain as gate

NOW = datetime(2026, 11, 17, 21, tzinfo=timezone.utc)
REVISION = "a" * 40
SRI = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


def encoded(record):
    return json.dumps(record, sort_keys=True).encode("utf-8")


def digest(value):
    return gate.sha256(value.encode("ascii"))


def header(revision=REVISION):
    return {"version": 1, "repository": gate.REPOSITORY, "revision": revision}


def snapshot(package="example", version="1.0.0"):
    data = {}
    for scope, paths in gate.MANIFESTS.items():
        root = {"name": f"sample-{scope}", "version": "1.0.0"}
        if scope == "root":
            root["workspaces"] = ["apps/*", "packages/*"]
            root["devDependencies"] = {package: version}
        data[paths[0]] = root
        packages = {"": root.copy()}
        for path in paths[1:]:
            target = path.removesuffix("/package.json")
            manifest = {"name": "@example/" + target.rsplit("/", 1)[-1], "version": "1.0.0"}
            data[path] = manifest
            packages[target] = manifest.copy()
            packages[f'node_modules/{manifest["name"]}'] = {"link": True, "resolved": target}
        if scope == "root":
            packages["node_modules/" + package] = {
                "version": version, "resolved": f"https://registry.npmjs.org/{package}/-/{package}-{version}.tgz",
                "integrity": SRI, "license": "MIT",
            }
        data[gate.LOCKS[scope]] = dict(name=root["name"], version=root["version"],
                                      lockfileVersion=3, requires=True, packages=packages)
    data[gate.LICENSE_INPUT] = {"schema_version": 1, "exceptions": [], "verified_license_overrides": []}
    return {path: encoded(file) for path, file in data.items()}


class SupplyChainTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = snapshot()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.receipts = {}
        self.authority = dict(header(), reviewer=digest("reviewer"), receipts={},
                              issued_at="2026-11-17T20:00:00Z", expires_at="2026-11-18T20:00:00Z")
        self.approvals = dict(header(), reviewer=self.authority["reviewer"], exceptions=[])
        for name, (kind, scope) in gate.RECEIPTS.items():
            result = "reproduced-and-integrity-verified" if kind == "provenance" else "clear"
            receipt = dict(header(), kind=kind, scope=scope, producer=digest(kind),
                           tool_sha256=digest(f"{kind}:tool"), profile_sha256=digest(f"{kind}:profile"),
                           completed_at="2026-11-17T19:00:00Z", run_id=digest(name + ":run"),
                           artifact_sha256=digest(name + ":artifact"), result=result)
            if scope in gate.LOCKS:
                receipt["lock_sha256"] = gate.sha256(self.snapshot[gate.LOCKS[scope]])
                receipt["manifest_set_sha256"] = digest("".join(
                    gate.sha256(self.snapshot[path]) for path in gate.MANIFESTS[scope]))
            if kind != "provenance":
                receipt["findings"] = []
            self.receipts[name] = receipt

    def put(self, name, data):
        (self.directory / f"{name}.json").write_bytes(data)
        return gate.sha256(data)

    def write_dossier(self, *, receipt_overrides=None):
        overrides = receipt_overrides or {}
        for name, receipt in self.receipts.items():
            data = overrides.get(name, encoded(receipt))
            self.authority["receipts"][name] = {
                "receipt_sha256": self.put(name, data),
                **{key: receipt[key] for key in ("producer", "tool_sha256", "profile_sha256")},
            }
        self.authority["approvals_sha256"] = self.put("approvals", encoded(self.approvals))
        return self.put("authority", encoded(self.authority))

    def validate(self, pin):
        with_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            return gate.check_evidence(with_fd, pin, self.snapshot, REVISION, NOW)
        finally:
            os.close(with_fd)

    def test_clear_exact_receipts(self):
        self.assertTrue(self.validate(self.write_dossier()))

    def test_receipt_requires_separate_pin_and_matching_digest(self):
        pin = self.write_dossier()
        with self.assertRaises(gate.Invalid):
            self.validate(digest("wrong"))
        self.put("secret-source", encoded(dict(self.receipts["secret-source"], run_id=digest("other"))))
        with self.assertRaises(gate.Invalid):
            self.validate(pin)
        (self.directory / "secret-source.json").unlink()
        with self.assertRaises(OSError):
            self.validate(pin)

    def test_approval_covers_only_the_exact_finding_before_expiry(self):
        receipt = self.receipts["dependency-root"]
        finding = {"id": digest("finding"), "severity": "high"}
        receipt.update(result="findings", findings=[finding])
        self.assertFalse(self.validate(self.write_dossier()))
        exception = {"receipt_sha256": gate.sha256(encoded(receipt)), "finding_id": finding["id"],
                     "severity": "high", "approved_at": "2026-11-17T20:00:00Z",
                     "expires_at": "2026-11-18T20:00:00Z", "decision": "temporary-exception",
                     "reason": "mitigation-verified", "controls": [digest("mitigation-proof")],
                     "closure_criteria_sha256": digest("closure-criteria")}
        self.approvals["exceptions"] = [exception]
        self.assertTrue(self.validate(self.write_dossier()))
        exception["expires_at"] = "2026-11-17T21:00:00Z"
        with self.assertRaises(gate.Invalid):
            self.validate(self.write_dossier())
        exception["expires_at"] = "2026-11-18T20:00:00Z"
        receipt["run_id"] = digest("new run")
        with self.assertRaises(gate.Invalid):
            self.validate(self.write_dossier())

    def test_rejects_self_approval_and_stale_or_expired_authority(self):
        for field, value in (
            ("reviewer", self.receipts["static-source"]["producer"]),
            ("expires_at", "2026-11-17T21:00:00Z"),
            ("expires_at", "2026-12-01T00:00:00Z"),
            ("issued_at", "2026-11-17T22:00:00Z"),
        ):
            with self.subTest(field=field, value=value):
                saved = self.authority[field]
                self.authority[field] = value
                with self.assertRaises(gate.Invalid):
                    self.validate(self.write_dossier())
                self.authority[field] = saved

    def test_strict_receipt_fields_and_separate_scopes(self):
        receipt = self.receipts["secret-source"]
        for field, value in (
            ("version", True), ("version", 1.0), ("revision", "b" * 40), ("repository", "other"),
            ("kind", "static"), ("scope", "deployment"), ("artifact_sha256", "raw artifact"),
            ("profile_sha256", "unknown profile"), ("findings", {}),
            ("result", "historical"), ("completed_at", "2026-11-10T20:59:59Z"),
            ("completed_at", "2026-11-17T22:00:00Z"), ("raw_payload", "untrusted"),
            ("run_id", self.receipts["static-source"]["run_id"]),
        ):
            with self.subTest(field=field, value=value):
                modified = dict(receipt, **{field: value})
                with self.assertRaises(gate.Invalid):
                    self.validate(self.write_dossier(receipt_overrides={"secret-source": encoded(modified)}))
        with self.assertRaises(gate.Invalid):
            self.validate(self.write_dossier(receipt_overrides={
                "secret-source": encoded(receipt)[:-1] + b', "version": 1}'}))

    def test_lock_receipts_bind_exact_lock_and_manifests(self):
        for name in ("provenance-root", "dependency-canvas"):
            for field in ("lock_sha256", "manifest_set_sha256"):
                with self.subTest(name=name, field=field):
                    override = encoded(dict(self.receipts[name], **{field: digest("a different input")}))
                    with self.assertRaises(gate.Invalid):
                        self.validate(self.write_dossier(receipt_overrides={name: override}))

    def test_redacted_receipt_input_disallows_symlinks_and_oversize(self):
        pin = self.write_dossier()
        source = self.directory / "secret-source.json"
        source.unlink()
        source.symlink_to(self.directory / "static-source.json")
        with self.assertRaises(OSError):
            self.validate(pin)
        source.unlink()
        source.write_bytes(b" " * (gate.RECEIPT_LIMIT + 1))
        with self.assertRaises(gate.Invalid):
            self.validate(pin)

    def test_lock_and_license_pass_only_with_expected_source_and_integrity(self):
        self.assertFalse(gate.check_lock(self.snapshot, "root"))
        self.assertFalse(gate.check_lock(self.snapshot, "canvas"))
        self.assertTrue(gate.check_license_policy(self.snapshot))
        lock_path = gate.LOCKS["root"]
        for override in ({"resolved": "https://other.invalid/object.tgz"}, {"integrity": SRI[:-2]},
                         {"version": 1}, {"link": False}):
            with self.subTest(override=override):
                lock = json.loads(self.snapshot[lock_path])
                lock["packages"]["node_modules/example"].update(override)
                with self.assertRaises(gate.Invalid):
                    gate.check_lock(dict(self.snapshot, **{lock_path: encoded(lock)}), "root")
        lock = json.loads(self.snapshot[lock_path])
        lock["packages"][""]["devDependencies"]["example"] = "1.0.1"
        with self.assertRaises(gate.Invalid):
            gate.check_lock(dict(self.snapshot, **{lock_path: encoded(lock)}), "root")
        lock = json.loads(self.snapshot[lock_path])
        lock["packages"]["node_modules/example"]["license"] = "UNKNOWN"
        self.assertFalse(gate.check_license_policy(dict(self.snapshot, **{lock_path: encoded(lock)})))

    def test_canvas_license_exception_cannot_cover_same_root_package(self):
        policy_path = gate.LICENSE_INPUT
        policy = json.loads(self.snapshot[policy_path])
        policy["exceptions"] = [
            {"name": "example", "version": "1.0.0", "license": "MPL-2.0", "reason": "synthetic"},
        ]
        self.snapshot[policy_path] = encoded(policy)
        canvas = json.loads(self.snapshot[gate.LOCKS["canvas"]])
        entry = {"version": "1.0.0", "integrity": SRI, "license": "MPL-2.0"}
        canvas["packages"]["node_modules/example"] = entry
        self.snapshot[gate.LOCKS["canvas"]] = encoded(canvas)
        self.assertTrue(gate.check_license_policy(self.snapshot))

        root = json.loads(self.snapshot[gate.LOCKS["root"]])
        root["packages"]["node_modules/example"].update(entry)
        self.snapshot[gate.LOCKS["root"]] = encoded(root)
        self.assertFalse(gate.check_license_policy(self.snapshot))

    def test_known_root_pin_blocks_even_if_receipts_report_clear(self):
        output = StringIO()
        fixture = snapshot("picomatch", "4.0.7")
        with (redirect_stdout(output), patch.object(Path, "cwd", return_value=ROOT),
              patch.object(gate, "git", side_effect=[b"\n", REVISION.encode()]),
              patch.object(gate, "source_snapshot", return_value=fixture),
              patch.object(gate, "check_evidence", return_value=True),
              patch.object(gate, "EVIDENCE_DIRECTORY", str(self.directory))):
            result = gate.main(["--trusted-authority-sha256", digest("synthetic")], clock=lambda: NOW)
        self.assertEqual(result, 1)
        self.assertIn("root advisory tracked by #458: OPEN", output.getvalue())
        self.assertIn("FAIL (UNRESOLVED_FINDINGS_OR_LICENSE)", output.getvalue())

    def test_unsafe_cli_arguments_do_not_echo(self):
        output = StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as context:
            gate.main(["--unrecognized", "not-for-output"])
        self.assertEqual(context.exception.code, 2)
        self.assertEqual(output.getvalue(), "result: UNVERIFIED (INVALID_ARGUMENTS)\n")

    def test_cli_reads_exact_git_commit_and_reports_real_status_classes(self):
        source = self.directory / "repo"
        source.mkdir()
        script_dir = source / "scripts/verification"
        script_dir.mkdir(parents=True)
        for path in (Path(gate.__file__), Path(gate.check_licenses.__file__)):
            (script_dir / path.name).write_bytes(path.read_bytes())
        for name, blob in self.snapshot.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
        for args in (["init", "--quiet"], ["add", "."],
                     ["-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                      "commit", "--quiet", "-m", "Synthetic package fixtures"]):
            subprocess.run(["git", *args], cwd=source, check=True, capture_output=True)
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
        for record in [self.authority, self.approvals, *self.receipts.values()]:
            record["revision"] = revision
        for record in self.receipts.values():
            record["completed_at"] = "2026-11-17T19:00:00Z"
        self.directory = source / gate.EVIDENCE_DIRECTORY
        self.directory.mkdir()
        pin = self.write_dossier()
        command = [sys.executable, "-B", "scripts/verification/check_t9_supply_chain.py"]
        result = subprocess.run(command, cwd=source, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("UNVERIFIED (EVIDENCE_OR_AUTHORITY)", result.stdout)
        self.assertIn("HISTORICAL_ONLY", result.stdout)
        self.assertIn(revision, result.stdout)
        self.assertEqual(result.stderr, "")
        # Altering uncommitted source does not change the reported input commit or evidence scope.
        (source / "package.json").write_bytes(b"uncommitted synthetic payload")
        runner = ("from datetime import datetime, timezone; "
                  "import check_t9_supply_chain as g; "
                  "clock = lambda: datetime(2026,11,17,21,tzinfo=timezone.utc); "
                  f"raise SystemExit(g.main(['--trusted-authority-sha256','{pin}'], clock=clock))")
        command = [sys.executable, "-B", "-c", "import sys; sys.path.insert(0, 'scripts/verification'); " + runner]
        result = subprocess.run(command, cwd=source, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS (SUPPLY_CHAIN_SCOPE)", result.stdout)
        self.assertNotIn("synthetic payload", result.stdout)


if __name__ == "__main__":
    unittest.main()
