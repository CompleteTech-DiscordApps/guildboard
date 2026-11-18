import hashlib
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/verification"))
from t11_backup_inventory import InventoryMismatch, verify_inventory


# The synthetic cut references only asset 1 and requires log positions 8 and 9.
# This trusted fixture inventory is supplied independently of the bundle.
CUT_FILES = {
    "base.sql": b"INSERT INTO synthetic_cut VALUES (7, 1);\n",
    "replay-8.bin": b"synthetic replay position 8\n",
    "replay-9.bin": b"synthetic replay position 9\n",
    "asset-1.bin": b"synthetic asset referenced at cut 7\n",
}
EXPECTED = {
    name: (len(contents), hashlib.sha256(contents).hexdigest())
    for name, contents in CUT_FILES.items()
}


class BackupInventoryTests(unittest.TestCase):
    def setUp(self):
        parent = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.root = parent / "bundle"
        self.root.mkdir(mode=0o700)
        for name, contents in CUT_FILES.items():
            (self.root / name).write_bytes(contents)

    def test_exact_bundle(self):
        verify_inventory(self.root, EXPECTED)
        self.assertEqual(
            {path.name: path.read_bytes() for path in self.root.iterdir()}, CUT_FILES
        )

    def test_missing_replay_and_unclaimed_asset_fail_even_with_original_count(self):
        (self.root / "replay-8.bin").rename(self.root / "asset-2.bin")
        with self.assertRaisesRegex(InventoryMismatch, "inventory differs"):
            verify_inventory(self.root, EXPECTED)

    def test_interrupted_asset_write_fails(self):
        asset = self.root / "asset-1.bin"
        asset.write_bytes(CUT_FILES[asset.name][:3])
        with self.assertRaisesRegex(InventoryMismatch, "type or length"):
            verify_inventory(self.root, EXPECTED)
        self.assertEqual(asset.read_bytes(), CUT_FILES[asset.name][:3])

    def test_same_length_asset_corruption_fails(self):
        asset = self.root / "asset-1.bin"
        asset.write_bytes(b"x" * len(CUT_FILES[asset.name]))
        with self.assertRaisesRegex(InventoryMismatch, "digest differs"):
            verify_inventory(self.root, EXPECTED)

    def test_link_to_exact_bytes_outside_bundle_fails(self):
        asset = self.root / "asset-1.bin"
        outside = self.root.parent / asset.name
        asset.rename(outside)
        asset.symlink_to(outside)
        with self.assertRaisesRegex(InventoryMismatch, "artifact unavailable"):
            verify_inventory(self.root, EXPECTED)
        asset.unlink()
        asset.hardlink_to(outside)
        with self.assertRaisesRegex(InventoryMismatch, "type or length"):
            verify_inventory(self.root, EXPECTED)
        self.assertEqual(outside.read_bytes(), CUT_FILES[asset.name])

    def test_nonregular_member_fails(self):
        asset = self.root / "asset-1.bin"
        asset.unlink()
        asset.mkdir()
        with self.assertRaisesRegex(InventoryMismatch, "type or length"):
            verify_inventory(self.root, EXPECTED)

    def test_invalid_expectation_fails(self):
        for expected in ({}, {"../base.sql": EXPECTED["base.sql"]},
                         {"base.sql": (True, EXPECTED["base.sql"][1])},
                         {"base.sql": (1, "TBD")}):
            with self.subTest(expected=expected), self.assertRaises(InventoryMismatch):
                verify_inventory(self.root, expected)

    def test_nonprivate_and_symlink_root_fail(self):
        alias = self.root.parent / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(InventoryMismatch, "artifact unavailable"):
            verify_inventory(alias, EXPECTED)
        self.root.chmod(0o755)
        with self.assertRaisesRegex(InventoryMismatch, "directory must be private"):
            verify_inventory(self.root, EXPECTED)
