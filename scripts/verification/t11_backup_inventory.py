"""Verify artifact bytes against an independently supplied offline inventory."""

import hashlib
import os
from pathlib import Path
import re
import stat


class InventoryMismatch(ValueError):
    """The bundle could not be verified."""


def _file_version(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _verify_member(directory: int, name: str, length: int, digest: str) -> None:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    artifact = os.open(name, flags, dir_fd=directory)
    try:
        before = os.fstat(artifact)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != length:
            raise InventoryMismatch("invalid artifact type or length")
        observed = hashlib.sha256()
        remaining = length
        while remaining:
            block = os.read(artifact, min(remaining, 64 * 1024))
            if not block:
                raise InventoryMismatch("artifact ended before its declared length")
            observed.update(block)
            remaining -= len(block)
        if os.read(artifact, 1):
            raise InventoryMismatch("artifact exceeded its declared length")
        after = os.stat(name, dir_fd=directory, follow_symlinks=False)
        if _file_version(before) != _file_version(after):
            raise InventoryMismatch("artifact changed during verification")
        if observed.hexdigest() != digest:
            raise InventoryMismatch("artifact digest differs")
    finally:
        os.close(artifact)


def verify_inventory(root: Path, expected: dict[str, tuple[int, str]]) -> None:
    """Match a quiescent private directory to trusted flat names, lengths and SHA-256.

    The offline fixture supplies the exact expected inventory from outside the
    bundle. Caller owns the private directory and keeps its parents stable.
    """
    if not expected:
        raise InventoryMismatch("missing expected inventory")
    for name, (length, digest) in expected.items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", name):
            raise InventoryMismatch("invalid artifact name")
        if type(length) is not int or length < 0 or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise InventoryMismatch("invalid artifact expectation")
    try:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            root_info = os.fstat(directory)
            if root_info.st_uid != os.geteuid() or root_info.st_mode & 0o077:
                raise InventoryMismatch("bundle directory must be private and owned")
            if set(os.listdir(directory)) != expected.keys():
                raise InventoryMismatch("bundle inventory differs")
            for name, (length, digest) in expected.items():
                _verify_member(directory, name, length, digest)
            if _file_version(root_info) != _file_version(os.fstat(directory)):
                raise InventoryMismatch("bundle directory changed during verification")
        finally:
            os.close(directory)
    except OSError as error:
        raise InventoryMismatch("bundle artifact unavailable") from error
