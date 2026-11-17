#!/usr/bin/env python3
"""Detect drift from the reviewed a08 architecture artifacts; not a product test."""
import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
import sys

BASELINE = {
 'docs/architecture.md': '6da35a1f4a0ef9dfdbbb784db67e006f1683cd8af68e47d53f343db2e1888cad',
 'docs/adr/0001-editor-activity-vps-direction.md': '1cea5ad95a16a54e156357c3e272d38ff4f756c3042b8eac5b59d2b057034398',
 'docs/adr/0002-server-authority-and-interactions.md': 'd74120927944cbae12d6ebdddde38b92b14e0a55008bf818da351b071a60c058',
 'docs/specifications/GB-T0-S1-system-contract.md': '6563ec365b8a36dafd00c79f829234ee53a629bfdf2a1c10a816d996ed9a805f',
 'docs/specifications/fixtures/GB-T0-01-02-interactions.json': 'c31d2a8ac09850617f84bd51125358c189308c82d27f05a3d33c50453e77d2de',
 'docs/specifications/fixtures/GB-T0-S1-scenarios.json': 'd28f682ad3bcd0d82dc6c00a9595e0d7e5d5c87763a61cffbadb882c5ed1a470',
 'docs/requirements/fixtures/GB-T0-01-01-use-cases.json': 'b1cf27dae882560ac1b040c261dd7e97f142f4c8917d07a26bc45005fc796440',
}
SIZE_LIMIT = 2_000_000

class VerificationError(Exception):
    pass

def verify(root, checkpoint=lambda: None):
    if not isinstance(root, Path) or not root.is_dir():
        raise VerificationError('invalid root or unavailable prerequisite')
    for name, expected in BASELINE.items():
        checkpoint()
        path = root / name
        # Linux CI and deployment provide both flags. Fail closed elsewhere: without
        # them opening a FIFO can block or the final component can follow a link.
        if not hasattr(os, 'O_NONBLOCK') or not hasattr(os, 'O_NOFOLLOW'):
            raise VerificationError('safe file open unsupported on this platform')
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise VerificationError('input is not a regular file: ' + name)
                # The bound applies to bytes actually read even if the file grows.
                with os.fdopen(fd, 'rb', closefd=False) as stream:
                    content = stream.read(SIZE_LIMIT + 1)
            finally:
                os.close(fd)
        except OSError as exc:
            raise VerificationError('unavailable prerequisite: ' + name) from exc
        if len(content) > SIZE_LIMIT:
            raise VerificationError('input exceeds size limit: ' + name)
        if hashlib.sha256(content).hexdigest() != expected:
            raise VerificationError('baseline mismatch: ' + name)
        if name.endswith('.json'):
            try:
                obj = json.loads(content)
                if not isinstance(obj, dict) or not isinstance(obj.get('scenarios' if 'use-cases' not in name else 'cases'), list):
                    raise VerificationError('invalid fixture shape: ' + name)
            except (ValueError, UnicodeError, RecursionError) as exc:
                raise VerificationError('invalid fixture: ' + name) from exc
    return 'PASS: seven accepted artifact digests match; runtime behavior not tested'

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args(argv)
    try:
        print(verify(Path(args.root)))
        return 0
    except (VerificationError, OSError, ValueError, RecursionError) as exc:
        print('FAIL: ' + str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('FAIL: verification interrupted', file=sys.stderr)
        return 130
if __name__ == '__main__':
    sys.exit(main())
