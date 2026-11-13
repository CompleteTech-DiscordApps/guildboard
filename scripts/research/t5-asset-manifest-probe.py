"""Bounded filesystem research fixture, not production upload/backup code.

Demonstrates that a copied SQL backup is insufficient if referenced immutable
asset bytes are missing or corrupt. Does not provide SQL/filesystem atomicity,
directory fsync, authorization or GoDaddy backup verification.
"""

import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile


def verify(root: Path, manifest: dict[str, str], *, byte_budget: int = 1024) -> str:
    if type(byte_budget) is not int or not 0 <= byte_budget <= 1024:
        raise ValueError("invalid research byte budget")
    if len(manifest) > 8:
        raise ValueError("manifest count exceeds research budget")
    base = root.resolve(strict=True)
    remaining = byte_budget
    for opaque_id, expected in sorted(manifest.items()):
        if not re.fullmatch(r"[a-z0-9-]{1,64}", opaque_id):
            raise ValueError("invalid opaque research asset ID")
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("invalid expected digest")
        path = (base / opaque_id).resolve(strict=True)
        if path.parent != base or not path.is_file():
            raise ValueError("asset escapes fixture directory or is not a file")
        with path.open("rb") as stream:
            data = stream.read(remaining + 1)
        if len(data) > remaining:
            raise ValueError("asset bytes exceed research budget")
        remaining -= len(data)
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("asset digest mismatch")
    return hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def experiment() -> dict:
    with tempfile.TemporaryDirectory(prefix="guildboard-t5-assets-") as directory:
        base = Path(directory)
        source, restore = base / "source", base / "restore"
        source.mkdir()
        restore.mkdir()
        payload = b"synthetic immutable board asset\n"
        (source / "asset-a").write_bytes(payload)
        manifest = {"asset-a": hashlib.sha256(payload).hexdigest()}
        expected = verify(source, manifest)
        missing_rejected = corrupt_rejected = False
        try:
            verify(restore, manifest)
        except FileNotFoundError:
            missing_rejected = True
        shutil.copyfile(source / "asset-a", restore / "asset-a")
        restored_equal = verify(restore, manifest) == expected
        (restore / "asset-a").write_bytes(b"corrupt")
        try:
            verify(restore, manifest)
        except ValueError:
            corrupt_rejected = True
        if not (missing_rejected and corrupt_rejected and restored_equal):
            raise RuntimeError("asset verification negative/positive control failed")
        return {
            "evidence_kind": "real-local-filesystem-fixture-not-durable-backup-system",
            "manifest": manifest, "manifest_sha256": expected,
            "missing_asset_rejected": missing_rejected,
            "copied_asset_hashes_equal": restored_equal,
            "corrupt_asset_rejected": corrupt_rejected,
            "limits": "8 files, 1024 total bytes; synthetic local fixture only",
            "result": "pass",
        }


if __name__ == "__main__":
    sys.stdout.buffer.write(
        (json.dumps(experiment(), indent=2, sort_keys=True) + "\n").encode()
    )
