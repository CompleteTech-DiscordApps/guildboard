"""Adversarial checks for the research asset-copy experiment only."""

import hashlib
from pathlib import Path
import runpy
import tempfile
import unittest


MODEL = runpy.run_path(str(Path(__file__).resolve().parents[2]
                          / "scripts/research/t5-asset-manifest-probe.py"))
verify = MODEL["verify"]


class AssetResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="guildboard-t5-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "asset-a").write_bytes(b"safe")
        self.digest = hashlib.sha256(b"safe").hexdigest()

    def test_complete_copy_is_verified(self):
        self.assertEqual(len(verify(self.root, {"asset-a": self.digest})), 64)

    def test_missing_reference_does_not_pass(self):
        with self.assertRaises(FileNotFoundError):
            verify(self.root, {"asset-missing": self.digest})

    def test_corrupt_reference_does_not_pass(self):
        (self.root / "asset-a").write_bytes(b"evil")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            verify(self.root, {"asset-a": self.digest})

    def test_byte_budget_has_exact_boundary(self):
        verify(self.root, {"asset-a": self.digest}, byte_budget=4)
        with self.assertRaisesRegex(ValueError, "byte"):
            verify(self.root, {"asset-a": self.digest}, byte_budget=3)

    def test_count_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "count"):
            verify(self.root, {"asset-"+str(n): self.digest for n in range(9)})

    def test_invalid_budgets_cannot_enable_unbounded_read(self):
        for budget in (-2, -1, 1025, True, 3.5):
            with self.subTest(budget=budget), self.assertRaisesRegex(ValueError, "budget"):
                verify(self.root, {"asset-a": self.digest}, byte_budget=budget)

    def test_paths_and_malformed_hashes_are_rejected(self):
        for name in ("../asset-a", "/asset-a", "C:\\asset-a", "a/b", ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                verify(self.root, {name: self.digest})
        with self.assertRaisesRegex(ValueError, "digest"):
            verify(self.root, {"asset-a": "broken"})

    def test_directory_cannot_substitute_for_asset(self):
        (self.root / "asset-dir").mkdir()
        with self.assertRaisesRegex(ValueError, "not a file"):
            verify(self.root, {"asset-dir": self.digest})

    def test_experiment_contains_both_fault_controls(self):
        report = MODEL["experiment"]()
        self.assertTrue(report["missing_asset_rejected"])
        self.assertTrue(report["corrupt_asset_rejected"])
        self.assertTrue(report["copied_asset_hashes_equal"])
        self.assertEqual(report, MODEL["experiment"]())


if __name__ == "__main__":
    unittest.main()
