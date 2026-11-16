#!/usr/bin/env python3
"""Inspect pinned publisher artifacts without installing or executing their code.

This is static research evidence, not an editor, Discord, or VPS integration test.
"""
import argparse
import base64
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_UNPACKED = 128 * 1024 * 1024
MAX_SELECTED = 2 * 1024 * 1024
MAX_SOURCE = 64 * 1024


def read_bounded(stream, limit):
    data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("artifact exceeds byte limit")
    return data


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect_archive(data, spec):
    if len(data) > MAX_ARCHIVE:
        raise ValueError("archive exceeds byte limit")
    sri = "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()
    if sri != spec["integrity"]:
        raise ValueError("archive integrity mismatch")
    wanted = {"package/package.json", *[c["path"] for c in spec["checks"]]}
    if spec["archive_license"]:
        wanted.add(spec["archive_license"])
    # Bound actual expanded bytes, including PAX/GNU metadata that tarfile may
    # consume internally before yielding any member to our loop.
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as expanded:
        try:
            raw_tar = read_bounded(expanded, MAX_UNPACKED)
        except ValueError as error:
            raise ValueError("archive exceeds expanded byte limit") from error
    selected, seen, total = {}, set(), 0
    # Never extract paths or follow archive links to the filesystem.
    with tarfile.open(fileobj=io.BytesIO(raw_tar), mode="r|") as archive:
        for index, member in enumerate(archive):
            total += member.size
            if index >= 10000 or total > MAX_UNPACKED:
                raise ValueError("archive exceeds member or expanded byte limit")
            if member.name in seen:
                raise ValueError("duplicate archive member")
            seen.add(member.name)
            if member.name in wanted:
                if not member.isfile() or member.size > MAX_SELECTED:
                    raise ValueError("expected artifact is not a bounded regular file")
                selected[member.name] = read_bounded(archive.extractfile(member), MAX_SELECTED)
    if wanted - selected.keys():
        raise ValueError("expected archive artifact missing")
    metadata = json.loads(selected["package/package.json"])
    if (metadata.get("name"), metadata.get("version"), metadata.get("license")) != (
        spec["name"], spec["version"], "MIT"
    ):
        raise ValueError("package identity or declared license mismatch")
    for check in spec["checks"]:
        content = selected[check["path"]]
        if digest(content) != check["sha256"]:
            raise ValueError("declaration hash mismatch")
        for symbol in check["symbols"]:
            if not re.search(r"\b" + re.escape(symbol) + r"\b", content.decode("utf-8")):
                raise ValueError("declaration symbol missing")
    license_path = spec["archive_license"]
    if license_path and digest(selected[license_path]) != spec["source_license"]["sha256"]:
        raise ValueError("published license differs from pinned source license")
    return {
        "name": spec["name"], "version": spec["version"],
        "archive_sha256": digest(data), "compressed_bytes": len(data),
        "declared_license": metadata["license"], "checked_files": spec["checks"],
        "published_license": license_path or "not included at a checked path; retain source notice",
        "license_named_files": sorted(n for n in seen if re.search(r"(^|/)(license|licence|copying|notice)([./]|$)", n, re.I)),
        "font_asset_count": sum(n.endswith((".woff", ".woff2", ".ttf", ".otf")) for n in seen),
    }


def artifact(cache, filename, url, limit, offline):
    path = cache / filename
    if not path.exists():
        if offline:
            raise ValueError(f"offline cache missing: {filename}")
        with urllib.request.urlopen(url, timeout=30) as response:
            data = read_bounded(response, limit)
        path.write_bytes(data)
    with path.open("rb") as stream:
        return read_bounded(stream, limit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    pins_path = ROOT / "docs/research/feasibility-pins.json"
    pins_bytes = pins_path.read_bytes()
    pins = json.loads(pins_bytes)
    results = []
    for spec in pins["packages"]:
        data = artifact(args.cache, spec["key"] + ".tgz", spec["tarball"], MAX_ARCHIVE, args.offline)
        result = inspect_archive(data, spec)
        source = spec["source_license"]
        license_data = artifact(args.cache, spec["key"] + "-LICENSE", source["url"], MAX_SOURCE, args.offline)
        if digest(license_data) != source["sha256"]:
            raise ValueError("pinned source license hash mismatch")
        result["source_commit"] = spec["source_commit"]
        result["source_license"] = source
        results.append(result)
    report = {
        "schema_version": 1, "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "system": platform.system(),
        "pins_sha256": digest(pins_bytes), "result": "static-artifacts-match-pins",
        "limitations": ["No third-party code executed", "No transitive or font license clearance",
                         "No rendering, authorization, Discord client, proxy, or GoDaddy runtime test"],
        "packages": results,
    }
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    sys.stdout.write(rendered)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, tarfile.TarError, KeyError) as error:
        sys.exit(f"probe failed: {error}")
