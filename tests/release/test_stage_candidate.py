"""Local integration and synthetic authority checks for private staging."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.release import stage_candidate as release


class StageCandidateTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.checkout = self.root / "source"
        self.checkout.mkdir()
        self.output = self.root / "private"
        self.output.mkdir(mode=0o700)
        self.git("init", "-q")
        self.inputs = {
            "package.json": b'{"version":"0.0.0"}\n',
            "package-lock.json": b'{"lockfileVersion":3}\n',
            "tsconfig.base.json": b'{"compilerOptions":{}}\n',
            "apps/api/package.json": b'{"name":"@guildboard/api","version":"0.0.0"}\n',
            "apps/api/src/index.ts": b"export const marker = true;\n",
        }
        self.build_outputs = {"apps/api/dist/index.js": b"export const marker = true;\n"}
        self.write_source({**self.inputs, release.BUILD_SCRIPT: b"// fixture build entry point\n"})
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Fixture")
        self.revision = self.git("rev-parse", "HEAD").strip()
        self.build = {
            "format": 1, "rootVersion": "0.0.0", "versions": {"@guildboard/api": "0.0.0"},
            "inputs": {path: release.digest(data) for path, data in self.inputs.items()},
            "outputs": {path: release.digest(data) for path, data in self.build_outputs.items()},
        }
        self.write_source({**self.build_outputs, release.BUILD: release.canonical(self.build)})
        self.today = date(2026, 11, 17)

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.checkout), *args], check=True, capture_output=True, text=True,
        ).stdout

    def write_source(self, files):
        for name, data in files.items():
            target = self.checkout / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

    def metadata(self, *, stable=False):
        gate = release.G3 if stable else release.G1
        level = "real-godaddy" if stable else "real-discord"
        issue = "GB-T13.G2" if stable else "GB-T12.MVP1"
        metadata = {
            "schemaVersion": release.SCHEMA, "version": "1.0.0" if stable else "0.3.1-rc.1+local",
            "gate": gate, "evidence": [{
                "id": "example-scenario", "issue": issue, "revision": self.revision,
                "date": self.today.isoformat(), "environment": "synthetic fixture",
                "level": level, "result": "pass", "ref": "evidence/example.json",
            }],
        }
        if stable:
            metadata["mvpPublication"] = {
                "identity": {
                    "version": "0.2.0", "revision": self.revision,
                    "artifactSha256": "2" * 64, "manifestSha256": "3" * 64, "notesSha256": "4" * 64,
                },
                "releaseRef": f"{release.REPO}/releases/tag/v0.2.0",
            }
        return metadata

    def assemble(self, metadata=None, body=b"# Local draft\n\nKnown limitations.\n"):
        if metadata is None:
            metadata = self.metadata()
        return release.assemble(self.checkout, release.canonical(metadata), body)

    def authority(self, bundle):
        manifest, identity = release.verify_bundle(bundle)
        return {
            "schemaVersion": release.SCHEMA, "validFrom": self.today.isoformat(),
            "validUntil": (self.today + timedelta(days=1)).isoformat(),
            "approval": {
                "schemaVersion": release.SCHEMA, "gate": manifest["gate"], "identity": identity,
                "provenanceRef": manifest["provenanceRef"], "decision": "approved",
                "decisionRef": "evidence/maintainer.json",
            },
            "prerequisites": {
                "gate": manifest["gate"], "identity": identity, "decision": "accepted",
                "decisionRef": "evidence/native.json", "evidence": manifest["evidence"],
                "mvpPublication": manifest.get("mvpPublication"),
            },
        }

    def dry(self, version, authority=None, pin=None):
        if authority is None:
            return release.dry_run(self.output, version, None, None, self.today)
        raw = release.canonical(authority)
        path = self.root / "authority.json"
        path.write_bytes(raw)
        return release.dry_run(self.output, version, path, pin or release.digest(raw), self.today)

    def test_stage_is_reproducible_and_retries_exact_bytes(self):
        first, second = self.assemble(), self.assemble()
        self.assertEqual(first, second)
        identity = release.stage(self.output, first)
        alternate = self.root / "alternate"
        alternate.mkdir(mode=0o700)
        self.assertEqual(release.stage(alternate, second), identity)
        original = self.output / identity["version"]
        duplicate = alternate / identity["version"]
        self.assertEqual(
            {str(path.relative_to(original)): path.read_bytes() for path in original.rglob("*") if path.is_file()},
            {str(path.relative_to(duplicate)): path.read_bytes() for path in duplicate.rglob("*") if path.is_file()},
        )
        self.assertEqual(release.stage(self.output, first), identity)
        self.assertEqual(identity["artifactSha256"], release.digest(first[release.INDEX]))
        self.assertEqual(identity["manifestSha256"], release.digest(first[release.MANIFEST]))
        manifest = json.loads(first[release.MANIFEST])
        self.assertTrue(first[release.NOTES].startswith(release.notes_header(manifest)))
        self.assertEqual(identity["notesSha256"], release.digest(first[release.NOTES]))
        with self.assertRaisesRegex(release.Invalid, "version-conflict"):
            release.stage(self.output, self.assemble(body=b"Changed approved notes."))
        self.assertEqual((original / release.NOTES).read_bytes(), first[release.NOTES])
        self.assertFalse((original / release.RECEIPT).exists())

    def test_cli_stage_and_dry_run_return_machine_reports(self):
        self.today = datetime.now(UTC).date()
        script = Path(release.__file__).absolute()
        spec = self.root / "metadata.json"
        spec.write_bytes(release.canonical(self.metadata()))
        body = self.root / "notes.md"
        body.write_bytes(b"# Draft engineering notes")
        stage = subprocess.run(
            [sys.executable, str(script), "stage", "--source", str(self.checkout), "--output", str(self.output),
             "--metadata", str(spec), "--notes-body", str(body)],
            capture_output=True, check=True,
        )
        report = json.loads(stage.stdout)
        self.assertEqual(report["outcome"], "STAGED")
        dry = subprocess.run(
            [sys.executable, str(script), "dry-run", "--output", str(self.output),
             "--version", report["identity"]["version"]],
            capture_output=True, check=False,
        )
        self.assertEqual(dry.returncode, 3)
        denied = json.loads(dry.stdout)
        self.assertEqual(denied["identity"], report["identity"])
        self.assertEqual(denied["outcome"], "PREREQUISITE_UNAVAILABLE")
        with release.directory(self.output) as root:
            bundle = release.read_bundle(root, report["identity"]["version"])
        authority = release.canonical(self.authority(bundle))
        snapshot = self.root / "authority.json"
        snapshot.write_bytes(authority)
        accepted = subprocess.run(
            [sys.executable, str(script), "dry-run", "--output", str(self.output),
             "--version", report["identity"]["version"], "--authority", str(snapshot),
             "--authority-sha256", release.digest(authority)],
            capture_output=True, check=True,
        )
        self.assertEqual(json.loads(accepted.stdout)["outcome"], "DRY_RUN_ACCEPTED")

    def test_concurrent_versions_preserve_the_first_complete_candidate(self):
        first = self.assemble()
        altered = self.assemble(body=b"Alternative draft.")
        version = self.metadata()["version"]

        def attempt(bundle):
            try:
                return release.stage(self.output, bundle)
            except release.Invalid as error:
                return str(error)

        with ThreadPoolExecutor(max_workers=3) as workers:
            results = list(workers.map(attempt, [first, altered, first]))
        self.assertIn("version-conflict", results)
        with release.directory(self.output) as root:
            winner = release.read_bundle(root, version)
        self.assertIn(winner, (first, altered))
        identity = release.verify_bundle(winner)[1]
        self.assertTrue(all(result == "version-conflict" or result == identity for result in results))
        self.assertEqual({path.name for path in self.output.iterdir()}, {version})

    def test_matching_independent_records_allow_g1_and_g3_without_mutations(self):
        git_refs = self.git("show-ref")
        for stable in (False, True):
            with self.subTest(stable=stable):
                bundle = self.assemble(self.metadata(stable=stable))
                identity = release.stage(self.output, bundle)
                authority = self.authority(bundle)
                report = self.dry(identity["version"], authority)
                self.assertEqual(report["outcome"], "DRY_RUN_ACCEPTED")
                self.assertEqual(report["identity"], identity)
                self.assertEqual(report["authoritySha256"], release.digest(release.canonical(authority)))
                self.assertFalse((self.output / identity["version"] / release.RECEIPT).exists())
        self.assertEqual(git_refs, self.git("show-ref"))

    def test_missing_denied_expired_substituted_or_stale_authority_fails_closed(self):
        bundle = self.assemble()
        identity = release.stage(self.output, bundle)
        version = identity["version"]
        self.assertEqual(self.dry(version)["category"], "authority")
        self.assertEqual(self.dry(version, self.authority(bundle), "0" * 64)["category"], "authority-digest")
        for field, changes, category in [
            ("approval", {"decision": "denied"}, "approval"),
            ("approval", {"identity": {**identity, "notesSha256": "0" * 64}}, "approval"),
            ("prerequisites", {"decision": "blocked"}, "prerequisites"),
            ("prerequisites", {"evidence": []}, "prerequisites"),
            ("prerequisites", {"mvpPublication": self.metadata(stable=True)["mvpPublication"]}, "prerequisites"),
        ]:
            with self.subTest(changes=changes):
                snapshot = self.authority(bundle)
                snapshot[field].update(changes)
                report = self.dry(version, snapshot)
                self.assertEqual(report["outcome"], "PREREQUISITE_UNAVAILABLE")
                self.assertEqual(report["category"], category)
        for bounds in [
            {"validUntil": self.today.isoformat()},
            {"validFrom": (self.today + timedelta(days=1)).isoformat()},
        ]:
            report = self.dry(version, {**self.authority(bundle), **bounds})
            self.assertEqual(report["category"], "authority-window")
        for changes in [
            {"revision": "a" * 40}, {"level": "synthetic"}, {"result": "fail"}, {"issue": "GB-T13.G2"},
            {"date": (self.today + timedelta(days=1)).isoformat()},
        ]:
            metadata = self.metadata()
            metadata["version"] = f"0.3.2-{next(iter(changes))}"
            metadata["evidence"][0].update(changes)
            altered = self.assemble(metadata)
            release.stage(self.output, altered)
            self.assertEqual(self.dry(metadata["version"], self.authority(altered))["category"], "evidence")

    def test_stable_mvp_designation_matches_independent_snapshot(self):
        metadata = self.metadata(stable=True)
        bundle = self.assemble(metadata)
        version = release.stage(self.output, bundle)["version"]
        snapshot = self.authority(bundle)
        snapshot["prerequisites"]["mvpPublication"]["identity"]["artifactSha256"] = "a" * 64
        self.assertEqual(self.dry(version, snapshot)["category"], "prerequisites")

        other = self.root / "missing-mvp"
        other.mkdir(mode=0o700)
        del metadata["mvpPublication"]
        missing = self.assemble(metadata)
        version = release.stage(other, missing)["version"]
        pin = release.canonical(self.authority(missing))
        path = self.root / "authority.json"
        path.write_bytes(pin)
        report = release.dry_run(other, version, path, release.digest(pin), self.today)
        self.assertEqual(report["category"], "mvp-publication")

    def test_build_missing_tampered_or_unlisted_files_are_rejected(self):
        for relative, data, category in [
            (release.BUILD, None, "build-manifest"),
            ("apps/api/dist/index.js", b"wrong", "build-digests"),
            ("apps/api/src/index.ts", b"other source", "source-inputs"),
            ("apps/api/dist/unlisted", b"extra", "build-outputs"),
            ("apps/api/src/unlisted", b"extra", "build-inputs"),
        ]:
            with self.subTest(path=relative):
                path = self.checkout / relative
                previous = path.read_bytes() if path.exists() else None
                if data is None:
                    path.unlink()
                else:
                    path.write_bytes(data)
                with self.assertRaisesRegex(release.Invalid, category):
                    self.assemble()
                if previous is None:
                    path.unlink()
                else:
                    path.write_bytes(previous)

    def test_record_types_unsafe_refs_and_duplicate_keys_are_rejected(self):
        duplicate = b'{"schemaVersion":"1.0.0","schemaVersion":"1.0.0"}'
        with self.assertRaisesRegex(release.Invalid, "metadata"):
            release.assemble(self.checkout, duplicate, b"# Draft")
        for field, value in [
            ("gate", []), ("version", "../v0.1.0"), ("version", "0.1.0-01"),
            ("version", "0.1.0-" + "a" * 128), ("evidence", {}),
        ]:
            with self.subTest(field=field, value=value):
                spec = {**self.metadata(), field: value}
                with self.assertRaises(release.Invalid):
                    self.assemble(spec)
        for field, value in [
            ("ref", "../evidence"),
            ("ref", f"{release.REPO}/issues/44?token=example"),
            ("level", []), ("date", "2026-02-30"), ("environment", "line\nsecret"),
        ]:
            spec = self.metadata()
            spec["evidence"][0][field] = value
            with self.assertRaisesRegex(release.Invalid, "evidence"):
                self.assemble(spec)
        spec = self.metadata()
        spec["evidence"].append(deepcopy(spec["evidence"][0]))
        with self.assertRaisesRegex(release.Invalid, "evidence"):
            self.assemble(spec)

    def test_readback_rejects_notes_payload_and_provenance_rebinding(self):
        bundle = self.assemble()
        for changed, category in [
            ({**bundle, release.NOTES: bundle[release.NOTES] + b"append"}, "notes"),
            ({**bundle, "added.txt": b"unindexed"}, "checksum"),
            ({**bundle, "apps/api/dist/index.js": b"other"}, "checksum"),
            ({**bundle, "apps": b"ancestor"}, "path"),
        ]:
            with self.assertRaisesRegex(release.Invalid, category):
                release.verify_bundle(changed)
        manifest = json.loads(bundle[release.MANIFEST])
        provenance = json.loads(bundle[release.PROVENANCE])
        provenance["inputs"][0]["sha256"] = "0" * 64
        altered = dict(bundle)
        altered[release.PROVENANCE] = release.canonical(provenance)
        altered[release.INDEX] = release.checksum({
            path: data for path, data in altered.items() if path not in release.ENVELOPES
        })
        manifest["artifactSha256"] = release.digest(altered[release.INDEX])
        altered[release.NOTES] = release.notes_header(manifest) + b"Different body."
        manifest["notesSha256"] = release.digest(altered[release.NOTES])
        altered[release.MANIFEST] = release.canonical(manifest)
        with self.assertRaisesRegex(release.Invalid, "provenance"):
            release.verify_bundle(altered)

    def test_no_symlinks_fifos_or_shared_output_root(self):
        bundle = self.assemble()
        version = self.metadata()["version"]
        link = self.root / "link"
        link.symlink_to(self.output, target_is_directory=True)
        with self.assertRaises(OSError):
            release.stage(link, bundle)
        self.output.chmod(0o755)
        with self.assertRaisesRegex(release.Invalid, "private-root"):
            release.stage(self.output, bundle)
        self.output.chmod(0o700)
        (self.output / version).symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(release.Invalid, "version-conflict"):
            release.stage(self.output, bundle)
        self.assertTrue((self.output / version).is_symlink())

        detached = self.root / "fifo"
        os.mkfifo(detached)
        report = release.stage(self.root, bundle)
        self.assertEqual(
            release.dry_run(self.root, report["version"], detached, "0" * 64, self.today)["category"],
            "authority",
        )

    def test_interruption_leaves_previous_candidate_and_retry_promotes_complete_bytes(self):
        old = self.assemble()
        old_identity = release.stage(self.output, old)
        spec = self.metadata()
        spec["version"] = "0.3.2"
        bundle = self.assemble(spec)
        with patch.object(release.os, "rename", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                release.stage(self.output, bundle)
        self.assertEqual({path.name for path in self.output.iterdir()}, {old_identity["version"]})

        # Abrupt process termination cannot run the temporary directory cleanup.
        raw = self.root / "metadata.json"
        raw.write_bytes(release.canonical(spec))
        code = """
import os
from pathlib import Path
import sys
from scripts.release import stage_candidate as release

bundle = release.assemble(Path(sys.argv[1]), Path(sys.argv[2]).read_bytes(), b"# Interrupted")
release.os.rename = lambda *args, **kwargs: os._exit(72)
release.stage(Path(sys.argv[3]), bundle)
"""
        result = subprocess.run(
            [sys.executable, "-c", code, str(self.checkout), str(raw), str(self.output)],
            cwd=Path(release.__file__).resolve().parents[2], check=False,
        )
        self.assertEqual(result.returncode, 72)
        self.assertFalse((self.output / spec["version"]).exists())
        self.assertTrue(any(path.name.startswith(".stage-") for path in self.output.iterdir()))
        self.assertEqual(release.stage(self.output, old), old_identity)
        new_identity = release.stage(self.output, bundle)
        self.assertEqual(new_identity, release.verify_bundle(bundle)[1])
        self.assertEqual(release.stage(self.output, bundle), new_identity)


if __name__ == "__main__":
    unittest.main()
