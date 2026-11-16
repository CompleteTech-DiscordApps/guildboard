"""Falsify acceptance of corrupt, substituted, or incomplete publisher artifacts."""
import base64
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import unittest

MODULE = Path(__file__).resolve().parents[2] / "scripts/research/probe_feasibility.py"
spec = importlib.util.spec_from_file_location("probe", MODULE)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeTests(unittest.TestCase):
    def fixture(self, overrides=None, duplicate=False, link=False):
        files = {
            "package/package.json": json.dumps({"name": "fixture", "version": "1.0.0", "license": "MIT"}).encode(),
            "package/index.d.ts": b"export declare function expectedHook(): void;",
        }
        files.update(overrides or {})
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:gz") as archive:
            for name, data in list(files.items()) + ([next(iter(files.items()))] if duplicate else []):
                member = tarfile.TarInfo(name)
                member.size = len(data)
                if link and name == "package/index.d.ts":
                    member.type = tarfile.SYMTYPE
                    member.linkname = "/etc/passwd"
                    member.size = 0
                archive.addfile(member, io.BytesIO(data) if member.isfile() else None)
        data = output.getvalue()
        expected = {
            "name": "fixture", "version": "1.0.0", "archive_license": None,
            "integrity": "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode(),
            "checks": [{"path": "package/index.d.ts", "sha256": probe.digest(files["package/index.d.ts"]),
                        "symbols": ["expectedHook"]}],
        }
        return data, expected

    def test_matching_static_artifact_is_not_runtime_certification(self):
        data, expected = self.fixture()
        report = probe.inspect_archive(data, expected)
        self.assertEqual(report["version"], "1.0.0")
        self.assertIn("not included", report["published_license"])

    def test_changed_bytes_fail_integrity(self):
        data, expected = self.fixture()
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            probe.inspect_archive(data + b"changed", expected)

    def test_substituted_identity_fails_even_with_matching_archive_integrity(self):
        data, expected = self.fixture({"package/package.json": b'{"name":"other","version":"1.0.0","license":"MIT"}'})
        with self.assertRaisesRegex(ValueError, "identity"):
            probe.inspect_archive(data, expected)

    def test_missing_and_substituted_declarations_fail(self):
        data, expected = self.fixture()
        changed = copy.deepcopy(expected)
        changed["checks"][0]["path"] = "package/missing.d.ts"
        with self.assertRaisesRegex(ValueError, "missing"):
            probe.inspect_archive(data, changed)
        changed = copy.deepcopy(expected)
        changed["checks"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            probe.inspect_archive(data, changed)
        changed = copy.deepcopy(expected)
        changed["checks"][0]["symbols"] = ["absentHook"]
        with self.assertRaisesRegex(ValueError, "symbol missing"):
            probe.inspect_archive(data, changed)

    def test_duplicates_and_links_are_rejected(self):
        for kwargs, reason in [({"duplicate": True}, "duplicate"), ({"link": True}, "regular file")]:
            with self.subTest(kwargs=kwargs):
                data, expected = self.fixture(**kwargs)
                with self.assertRaisesRegex(ValueError, reason):
                    probe.inspect_archive(data, expected)

    def test_declared_expansion_is_bounded(self):
        data, expected = self.fixture()
        original = probe.MAX_UNPACKED
        try:
            probe.MAX_UNPACKED = 1
            with self.assertRaisesRegex(ValueError, "expanded byte limit"):
                probe.inspect_archive(data, expected)
        finally:
            probe.MAX_UNPACKED = original

    def test_pax_metadata_cannot_bypass_expanded_byte_limit(self):
        data, expected = self.fixture()
        # PAX records are consumed inside tarfile before yielding a member. They
        # must count even when the sum of visible file sizes is below the limit.
        expanded = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as source:
            with tarfile.open(fileobj=expanded, mode="w:gz", format=tarfile.PAX_FORMAT) as target:
                for member in source:
                    member.pax_headers = {"comment": "x" * 8192}
                    target.addfile(member, source.extractfile(member))
        attack = expanded.getvalue()
        expected["integrity"] = "sha512-" + base64.b64encode(hashlib.sha512(attack).digest()).decode()
        original = probe.MAX_UNPACKED
        try:
            probe.MAX_UNPACKED = 16384
            with self.assertRaisesRegex(ValueError, "expanded byte limit"):
                probe.inspect_archive(attack, expected)
        finally:
            probe.MAX_UNPACKED = original


if __name__ == "__main__":
    unittest.main()
