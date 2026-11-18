#!/usr/bin/env python3
"""Validate exact-commit, redacted supply-chain evidence without network access."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone

import check_licenses

REPOSITORY = "CompleteTech-DiscordApps/guildboard"
LOCKS = dict(zip(("root", "canvas"), check_licenses.DEFAULT_LOCKFILES, strict=True))
WORKSPACES = ("apps/activity", "apps/api", "apps/bot", "packages/auth", "packages/canvas",
              "packages/collaboration", "packages/config", "packages/contracts")
MANIFESTS = {
    "root": ("package.json", *(f"{path}/package.json" for path in WORKSPACES)),
    "canvas": ("research-fixtures/canvas/package.json",),
}
LICENSE_INPUT = check_licenses.DEFAULT_EXCEPTIONS
SOURCE_FILES = frozenset((*LOCKS.values(), *MANIFESTS["root"], *MANIFESTS["canvas"], LICENSE_INPUT))
RECEIPTS = {
    "provenance-root": ("provenance", "root"),
    "provenance-canvas": ("provenance", "canvas"),
    "dependency-root": ("dependency", "root"),
    "dependency-canvas": ("dependency", "canvas"),
    "secret-source": ("secret", "source"),
    "static-source": ("static", "source"),
}
DIGEST = re.compile(r"[a-f0-9]{64}")
COMMIT = re.compile(r"[a-f0-9]{40}")
PACKAGE = re.compile(r"(?:@[a-z0-9._-]+/)?[a-z0-9][a-z0-9._-]*")
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:[-+][a-zA-Z0-9.+-]+)?")
TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
SEVERITIES = {"low", "moderate", "high", "critical"}
FIELDS_FROM_MANIFEST = ("name", "version", "workspaces", "dependencies", "devDependencies",
                        "optionalDependencies", "peerDependencies", "peerDependenciesMeta", "engines",
                        "bin", "os", "cpu", "license")
OBJECT_LIMIT = 2 * 1024 * 1024
RECEIPT_LIMIT = 256 * 1024
EVIDENCE_DIRECTORY = ".t9-assurance"


class Invalid(ValueError):
    """Evidence could not establish assurance."""


def require(condition):
    if not condition:
        raise Invalid()


def matches(pattern, value):
    return type(value) is str and pattern.fullmatch(value) is not None


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def reject_constant(_value):
    raise Invalid()


def read_json(data):
    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def fields(value, keys):
    require(type(value) is dict and value.keys() == set(keys.split()))


def header(value, revision):
    require(type(value["version"]) is int and value["version"] == 1
            and value["repository"] == REPOSITORY and value["revision"] == revision)


def instant(value):
    require(matches(TIME, value))
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def git(*args):
    # A missing object must fail offline, including in a partial clone.
    environ = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environ.update(GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1")
    deadline = time.monotonic() + 15
    with subprocess.Popen(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          env=environ) as process, selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        result = bytearray()
        try:
            while len(result) <= OBJECT_LIMIT:
                require(selector.select(max(0, deadline - time.monotonic())))
                block = os.read(process.stdout.fileno(), min(65536, OBJECT_LIMIT + 1 - len(result)))
                if not block:
                    require(process.wait(timeout=max(0, deadline - time.monotonic())) == 0)
                    return bytes(result)
                result.extend(block)
        finally:
            if process.poll() is None:
                process.kill()
    raise Invalid()


def source_snapshot(revision):
    # Inventory names and modes without reading unrelated source or installed files.
    listing = git("ls-tree", "-r", "-z", revision)
    objects = {}
    package_inputs = {b"package.json", b"package-lock.json", b"npm-shrinkwrap.json",
                      b"yarn.lock", b"pnpm-lock.yaml", b"bun.lock", b"bun.lockb"}
    for record in listing.rstrip(b"\0").split(b"\0"):
        info, _, name = record.partition(b"\t")
        if name.rsplit(b"/", 1)[-1] not in package_inputs and name != LICENSE_INPUT.encode():
            continue
        path = name.decode("ascii")
        require(path in SOURCE_FILES)
        mode, kind, oid = info.split()
        require(mode == b"100644" and kind == b"blob" and matches(COMMIT, oid.decode("ascii")))
        objects[path] = oid.decode("ascii")
    require(objects.keys() == SOURCE_FILES)
    snapshot = {}
    for path, oid in objects.items():
        require(int(git("cat-file", "-s", oid)) <= OBJECT_LIMIT)
        snapshot[path] = git("cat-file", "blob", oid)
    return snapshot


def same_json(left, right):
    # Python equality alone equates booleans, integers and floats.
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def check_manifest(manifest, entry):
    require(type(manifest) is dict and type(entry) is dict)
    require(matches(PACKAGE, manifest.get("name")) and matches(VERSION, manifest.get("version")))
    for key in FIELDS_FROM_MANIFEST:
        require((key in manifest) == (key in entry) and same_json(manifest.get(key), entry.get(key)))
    for key in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        deps = manifest.get(key, {})
        require(type(deps) is dict and all(matches(PACKAGE, name) and type(spec) is str and
                0 < len(spec) <= 256 for name, spec in deps.items()))


def check_lock(snapshot, scope):
    lock = read_json(snapshot[LOCKS[scope]])
    fields(lock, "name version lockfileVersion requires packages")
    require(type(lock["lockfileVersion"]) is int and lock["lockfileVersion"] == 3 and lock["requires"] is True)
    packages = lock["packages"]
    require(type(packages) is dict and 1 <= len(packages) <= 4096 and "" in packages)
    require(type(packages[""]) is dict and lock["name"] == packages[""].get("name")
            and lock["version"] == packages[""].get("version"))
    manifests = MANIFESTS[scope]
    targets = {}
    for path in manifests:
        name = "" if path == manifests[0] else path.removesuffix("/package.json")
        require(name in packages)
        manifest = read_json(snapshot[path])
        check_manifest(manifest, packages[name])
        require(not {"resolved", "integrity", "link"} & packages[name].keys())
        if name:
            link = f'node_modules/{manifest["name"]}'
            require(link not in targets)
            targets[link] = name
    expected_workspaces = ["apps/*", "packages/*"] if scope == "root" else None
    require(packages[""].get("workspaces") == expected_workspaces)
    require(all(key in packages for key in targets))

    known_root_advisory = False
    for path, entry in packages.items():
        require(type(entry) is dict)
        if path == "" or path in targets.values():
            continue
        if path in targets:
            fields(entry, "resolved link")
            require(entry["link"] is True and entry["resolved"] == targets[path])
            continue
        install_name = check_licenses.install_name(path)
        if install_name is None:
            relative_path = path.split("/node_modules/", 1)
            require(len(relative_path) == 2 and relative_path[0] in targets.values())
            install_name = check_licenses.install_name("node_modules/" + relative_path[1])
        name = entry.get("name", install_name)
        version = entry.get("version")
        require("link" not in entry and "inBundle" not in entry
                and matches(PACKAGE, install_name) and matches(PACKAGE, name) and matches(VERSION, version))
        expected = f'https://registry.npmjs.org/{name}/-/{name.rsplit("/", 1)[-1]}-{version}.tgz'
        require(entry.get("resolved") == expected and check_licenses.valid_integrity(entry.get("integrity")))
        known_root_advisory |= scope == "root" and name == "picomatch" and version == "4.0.7"
    return known_root_advisory


def check_license_policy(snapshot):
    # Only copies of already checked committed inputs go to the existing checker.
    # Its detailed names, paths and reason text stay out of this command's output.
    policy = read_json(snapshot[LICENSE_INPUT])
    require(type(policy) is dict and type(policy.get("schema_version")) is int)
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        files = []
        for path in (LICENSE_INPUT, *LOCKS.values()):
            destination = base / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(snapshot[path])
            files.append(str(destination))
        exceptions = check_licenses.load_exceptions(files[0])
        index = check_licenses.OverrideIndex(check_licenses.load_overrides(files[0]))
        used = set()
        root = check_licenses.scan_lockfile(files[1], {}, set(), check_licenses.OverrideIndex([]))
        canvas = check_licenses.scan_lockfile(files[2], exceptions, used, index)
        return (not root.failures and not canvas.failures
                and set(exceptions) == used and not index.stale_details())


def evidence_bytes(directory, name):
    with_fd = os.open(name + ".json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(with_fd, "rb") as source:
        info = os.fstat(source.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= RECEIPT_LIMIT)
        data = source.read(RECEIPT_LIMIT + 1)
    require(len(data) <= RECEIPT_LIMIT)
    return data


def verified_json(directory, name, expected):
    data = evidence_bytes(directory, name)
    require(matches(DIGEST, expected) and sha256(data) == expected)
    return read_json(data)


def validate_authority(authority, revision, now):
    fields(authority, "version repository revision reviewer issued_at expires_at receipts approvals_sha256")
    header(authority, revision)
    require(matches(DIGEST, authority["reviewer"]) and matches(DIGEST, authority["approvals_sha256"]))
    issued = instant(authority["issued_at"])
    expiry = instant(authority["expires_at"])
    require(issued <= now < expiry <= issued + timedelta(days=7))
    fields(authority["receipts"], " ".join(RECEIPTS))
    for record in authority["receipts"].values():
        fields(record, "producer tool_sha256 profile_sha256 receipt_sha256")
        require(all(matches(DIGEST, value) for value in record.values())
                and record["producer"] != authority["reviewer"])
    return issued


def check_receipt(receipt, name, authority_record, snapshot, revision, issued, now):
    common = "version repository revision kind scope producer tool_sha256 profile_sha256 completed_at run_id artifact_sha256 result"
    kind, scope = RECEIPTS[name]
    if scope in LOCKS:
        common += " lock_sha256 manifest_set_sha256"
    fields(receipt, common if kind == "provenance" else common + " findings")
    header(receipt, revision)
    require(receipt["kind"] == kind and receipt["scope"] == scope)
    require(all(receipt[key] == authority_record[key] for key in ("producer", "tool_sha256", "profile_sha256")))
    require(matches(DIGEST, receipt["run_id"]) and matches(DIGEST, receipt["artifact_sha256"]))
    completed = instant(receipt["completed_at"])
    require(now - timedelta(days=7) <= completed <= issued)
    if scope in LOCKS:
        manifest_hashes = [sha256(snapshot[path]) for path in MANIFESTS[scope]]
        require(receipt["lock_sha256"] == sha256(snapshot[LOCKS[scope]])
                and receipt["manifest_set_sha256"] == sha256("".join(manifest_hashes).encode("ascii")))
    if kind == "provenance":
        require(receipt["result"] == "reproduced-and-integrity-verified")
        return {}, completed

    findings = receipt["findings"]
    require(type(findings) is list and len(findings) <= 512)
    require(receipt["result"] == ("findings" if findings else "clear"))
    indexed = {}
    for finding in findings:
        fields(finding, "id severity")
        key = finding["id"]
        require(matches(DIGEST, key) and key not in indexed
                and type(finding["severity"]) is str and finding["severity"] in SEVERITIES)
        indexed[key] = finding["severity"]
    return indexed, completed


def check_approvals(record, authority, findings, revision, issued, now):
    fields(record, "version repository revision reviewer exceptions")
    header(record, revision)
    require(record["reviewer"] == authority["reviewer"])
    entries = record["exceptions"]
    require(type(entries) is list and len(entries) <= 512)
    covered = set()
    for entry in entries:
        fields(entry, "receipt_sha256 finding_id severity approved_at expires_at decision reason "
                      "controls closure_criteria_sha256")
        controls = entry["controls"]
        require(type(controls) is list and 1 <= len(controls) <= 8
                and all(matches(DIGEST, item) for item in controls) and len(set(controls)) == len(controls)
                and matches(DIGEST, entry["closure_criteria_sha256"]))
        require(matches(DIGEST, entry["receipt_sha256"]) and matches(DIGEST, entry["finding_id"]))
        key = (entry["receipt_sha256"], entry["finding_id"])
        require(key in findings and key not in covered and entry["severity"] == findings[key][0]
                and entry["decision"] == "temporary-exception"
                and entry["reason"] in ("mitigation-verified", "false-positive-verified"))
        approved, expiry = instant(entry["approved_at"]), instant(entry["expires_at"])
        require(findings[key][1] <= approved <= issued and now < expiry <= approved + timedelta(days=30))
        covered.add(key)
    return covered


def check_evidence(directory, trusted_digest, snapshot, revision, now):
    authority = verified_json(directory, "authority", trusted_digest)
    issued = validate_authority(authority, revision, now)
    approvals = verified_json(directory, "approvals", authority["approvals_sha256"])
    findings = {}
    runs = set()
    for name in RECEIPTS:
        expected = authority["receipts"][name]
        receipt = verified_json(directory, name, expected["receipt_sha256"])
        observed, completed = check_receipt(receipt, name, expected, snapshot, revision, issued, now)
        require(receipt["run_id"] not in runs)
        runs.add(receipt["run_id"])
        findings.update({(expected["receipt_sha256"], key): (severity, completed)
                         for key, severity in observed.items()})
    return findings.keys() == check_approvals(approvals, authority, findings, revision, issued, now)


INPUT_ERRORS = (ValueError, OverflowError, OSError, RecursionError, subprocess.SubprocessError,
                check_licenses.InputError)


class RedactedParser(argparse.ArgumentParser):
    def error(self, _message):
        print("result: UNVERIFIED (INVALID_ARGUMENTS)")
        raise SystemExit(2)


def utc_now():
    return datetime.now(timezone.utc)


def main(argv=None, *, clock=utc_now):
    parser = RedactedParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--trusted-authority-sha256", help="digest from an independent authorized channel")
    args = parser.parse_args(argv)
    print("historical reports: HISTORICAL_ONLY")
    try:
        require(Path(__file__).resolve().parents[2] == Path.cwd().resolve()
                and git("rev-parse", "--show-prefix") == b"\n")
        revision = git("rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip()
        require(matches(COMMIT, revision))
        snapshot = source_snapshot(revision)
        known_advisory = check_lock(snapshot, "root")
        check_lock(snapshot, "canvas")
        license_pass = check_license_policy(snapshot)
    except INPUT_ERRORS:
        print("result: UNVERIFIED (SOURCE_OR_LICENSE_INPUT)")
        return 2

    print(f"revision: {revision}")
    print("lockfile and manifest structure: PASS")
    print("offline license policy:", "PASS" if license_pass else "FAIL")
    if known_advisory:
        print("root advisory tracked by #458: OPEN")

    try:
        require(matches(DIGEST, args.trusted_authority_sha256))
        directory = os.open(EVIDENCE_DIRECTORY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            evidence_pass = check_evidence(directory, args.trusted_authority_sha256, snapshot, revision,
                                           clock())
        finally:
            os.close(directory)
    except INPUT_ERRORS:
        print("result: UNVERIFIED (EVIDENCE_OR_AUTHORITY)")
        return 2

    if license_pass and evidence_pass and not known_advisory:
        print("result: PASS (SUPPLY_CHAIN_SCOPE)")
        return 0
    print("result: FAIL (UNRESOLVED_FINDINGS_OR_LICENSE)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
