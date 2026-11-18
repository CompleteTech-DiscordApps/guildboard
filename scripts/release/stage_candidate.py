#!/usr/bin/env python3
"""Stage and verify a private GB-T13.S1 release candidate on Linux."""

import argparse
from contextlib import contextmanager
from datetime import UTC, date, datetime
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

SCHEMA = "1.0.0"
REPO = "https://github.com/CompleteTech-DiscordApps/guildboard"
G1 = "GB-T13.G1"
G3 = "GB-T13.G3"
INDEX = "SHA256SUMS"
MANIFEST = "manifest.json"
NOTES = "notes.md"
PROVENANCE = "build-provenance.json"
RECEIPT = "publication-receipt.json"
BUILD = "engineering-build/manifest.json"
RECIPE = "engineering-build/release-recipe.txt"
BUILD_SCRIPT = "scripts/engineering/build.mjs"
SETTINGS = {"package.json", "package-lock.json", "tsconfig.base.json"}
LIMIT = 512 * 1024
MAX_FILE = 16 * 1024 * 1024
MAX_BUNDLE = 64 * 1024 * 1024
MAX_FILES = 1024
NUMBER = r"(?:0|[1-9][0-9]*)"
PRERELEASE = rf"(?:{NUMBER}|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
SEMVER = re.compile(
    rf"{NUMBER}\.{NUMBER}\.{NUMBER}(?:-{PRERELEASE}(?:\.{PRERELEASE})*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
EVIDENCE_FIELDS = {"id", "issue", "revision", "date", "environment", "level", "result", "ref"}
LEVELS = {"static", "synthetic", "integration", "independent-review", "real-discord", "real-godaddy"}
IDENTITY = {"version", "revision", "artifactSha256", "manifestSha256", "notesSha256"}
METADATA = {"schemaVersion", "gate", "version", "evidence"}
ENVELOPES = {INDEX, MANIFEST, NOTES, RECEIPT}
DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW


class Invalid(ValueError):
    """Invalid or unavailable input, labeled with a fixed metadata category."""


def require(condition, category):
    if not condition:
        raise Invalid(category)


def match(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def version_ok(value):
    return isinstance(value, str) and len(value) <= 128 and match(value, SEMVER)


def path_ok(value):
    return (isinstance(value, str) and len(value) <= 256
            and all(match(part, r"[A-Za-z0-9_-][A-Za-z0-9_.-]*") for part in value.split("/")))


def ref_ok(value):
    if path_ok(value):
        return True
    if not isinstance(value, str) or len(value) > 256 or not value.startswith(f"{REPO}/"):
        return False
    relative = value[len(REPO) + 1:]
    tag = "releases/tag/v"
    if relative.startswith(tag):
        return version_ok(relative[len(tag):])
    return match(relative, r"(?:(?:issues|pull|actions/runs)/[1-9][0-9]*|commit/[0-9a-f]{40})")


def digest(value):
    return sha256(value).hexdigest()


def digest_ok(value):
    return match(value, r"[0-9a-f]{64}")


def revision_ok(value):
    return match(value, r"[0-9a-f]{40}")


def record(value, keys):
    return type(value) is dict and value.keys() == keys


def canonical(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode()


def unique_object(pairs):
    result = dict(pairs)
    require(len(result) == len(pairs), "duplicate-key")
    return result


def decode(raw, limit, category):
    require(len(raw) <= limit, category)
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
        require(type(value) is dict, category)
        return value
    except (ValueError, RecursionError):
        raise Invalid(category) from None


def parse_date(value, category):
    require(match(value, r"[0-9]{4}-[0-9]{2}-[0-9]{2}"), category)
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise Invalid(category) from None


def identity_ok(value):
    return (record(value, IDENTITY) and version_ok(value["version"]) and revision_ok(value["revision"])
            and all(digest_ok(value[key]) for key in IDENTITY if key.endswith("Sha256")))


def mvp_ok(value):
    return (record(value, {"identity", "releaseRef"}) and identity_ok(value["identity"])
            and value["identity"]["version"].startswith("0.")
            and value["releaseRef"] == f'{REPO}/releases/tag/v{value["identity"]["version"]}')


def validate_metadata(value, extra=frozenset()):
    gate = value.get("gate")
    keys = METADATA | extra
    if gate == G3 and "mvpPublication" in value:
        keys |= {"mvpPublication"}
        require(mvp_ok(value["mvpPublication"]), "mvp-publication")
    require(record(value, keys) and value["schemaVersion"] == SCHEMA
            and version_ok(value["version"]), "metadata")
    version = value["version"]
    require((gate == G1 and version.startswith("0.")) or (gate == G3 and version == "1.0.0"), "gate")
    rows = value["evidence"]
    require(type(rows) is list and len(rows) <= 128, "evidence")
    ids = set()
    for row in rows:
        require(record(row, EVIDENCE_FIELDS), "evidence")
        require(match(row["id"], r"[a-z][a-z0-9-]{0,255}") and row["id"] not in ids
                and match(row["issue"], r"GB-T[0-9]+(?:\.[A-Z0-9]+)*") and len(row["issue"]) <= 256
                and revision_ok(row["revision"]) and ref_ok(row["ref"]), "evidence")
        require(isinstance(row["environment"], str) and 0 < len(row["environment"]) <= 256
                and row["environment"].isprintable()
                and isinstance(row["level"], str) and row["level"] in LEVELS
                and isinstance(row["result"], str) and row["result"] in {"pass", "fail", "blocked"},
                "evidence")
        parse_date(row["date"], "evidence")
        ids.add(row["id"])


@contextmanager
def directories(start, parts):
    descriptor = os.dup(start)
    try:
        for part in parts:
            child = os.open(part, DIRECTORY, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def directory(path):
    # Preserve the supplied components so links are rejected before resolution.
    absolute = path.absolute()
    if ".." in absolute.parts:
        raise Invalid("path")
    descriptor = os.open(absolute.anchor, DIRECTORY)
    try:
        with directories(descriptor, absolute.parts[1:]) as opened:
            yield opened
    finally:
        os.close(descriptor)


def read_file(root, name, limit, category):
    parts = name.split("/")
    try:
        with directories(root, parts[:-1]) as parent:
            descriptor = os.open(parts[-1], FILE, dir_fd=parent)
            with os.fdopen(descriptor, "rb") as handle:
                info = os.fstat(handle.fileno())
                require(stat.S_ISREG(info.st_mode) and info.st_size <= limit, category)
                result = handle.read(limit + 1)
                require(len(result) <= limit, category)
                return result
    except OSError:
        raise Invalid(category) from None


def external_file(path, limit, category):
    try:
        with directory(path.parent) as parent:
            return read_file(parent, path.name, limit, category)
    except OSError:
        raise Invalid(category) from None


def scan(root, path="", *, skip=frozenset(), allow_empty_directories=False):
    """Return the complete tree of safe regular files under a held directory."""
    found = set()
    entries = 0

    def visit(current, prefix):
        nonlocal entries
        with os.scandir(current) as children:
            for entry in children:
                entries += 1
                require(entries <= 2 * MAX_FILES, "tree-size")
                name = f"{prefix}/{entry.name}" if prefix else entry.name
                require(path_ok(name), "path")
                if entry.is_dir(follow_symlinks=False):
                    if entry.name in skip:
                        continue
                    with directories(current, (entry.name,)) as child:
                        size = len(found)
                        visit(child, name)
                        require(allow_empty_directories or len(found) > size, "empty-directory")
                else:
                    require(entry.is_file(follow_symlinks=False), "file-type")
                    found.add(name)

    with directories(root, path.split("/") if path else ()) as start:
        visit(start, path)
    require(len(found) <= MAX_FILES, "tree-size")
    return found


def file_bytes(root, paths):
    contents = {}
    total = 0
    for path in sorted(paths):
        data = read_file(root, path, MAX_FILE, "payload")
        total += len(data)
        require(total <= MAX_BUNDLE, "bundle-size")
        contents[path] = data
    return contents


def git(source, *args):
    try:
        return subprocess.run(
            ["git", "--no-optional-locks", "-C", str(source.absolute()), *args],
            check=True, capture_output=True, timeout=15,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        raise Invalid("source-revision") from None


def valid_hashes(value):
    return (type(value) is dict and 0 < len(value) <= MAX_FILES
            and all(path_ok(path) and digest_ok(sha) for path, sha in value.items()))


def build_payload(source):
    with directory(source) as root:
        revision = git(source, "rev-parse", "--verify", "HEAD").decode("ascii").strip()
        require(revision_ok(revision), "source-revision")
        build_raw = read_file(root, BUILD, LIMIT, "build-manifest")
        build = decode(build_raw, LIMIT, "build-manifest")
        require(record(build, {"format", "rootVersion", "versions", "inputs", "outputs"})
                and type(build["format"]) is int and build["format"] == 1
                and match(build["rootVersion"], rf"{NUMBER}\.{NUMBER}\.{NUMBER}")
                and valid_hashes(build["inputs"]) and valid_hashes(build["outputs"]), "build-manifest")
        source_tree = git(source, "ls-tree", "-r", "-z", "--name-only", revision, "--", "apps", "packages")
        tracked = {entry.decode("utf-8") for entry in source_tree.split(b"\0") if entry}
        tracked = {path for path in tracked if not {"dist", "node_modules"}.intersection(path.split("/")[:-1])}
        projects = sorted({"/".join(path.split("/")[:2]) for path in tracked
                           if path.count("/") == 2 and path.endswith("/package.json")})
        require(projects and all(path_ok(path) for path in projects), "build-projects")
        inputs = SETTINGS.copy()
        outputs = set()
        versions = {}
        for project in projects:
            inputs.update(scan(root, project, skip={"dist", "node_modules"}, allow_empty_directories=True))
            project_outputs = scan(root, f"{project}/dist", allow_empty_directories=True)
            require(project_outputs, "build-outputs")
            outputs.update(project_outputs)
        require(inputs == (SETTINGS | tracked) and inputs == build["inputs"].keys(), "build-inputs")
        require(outputs == build["outputs"].keys(), "build-outputs")

        package_paths = {f"{project}/package.json" for project in projects}
        payload = file_bytes(root, outputs)
        for path in sorted(inputs | {BUILD_SCRIPT}):
            data = read_file(root, path, MAX_FILE, "build-inputs")
            require(data == git(source, "show", f"{revision}:{path}"), "source-inputs")
            if path in inputs:
                require(digest(data) == build["inputs"][path], "build-inputs")
            if path == "package.json":
                package = decode(data, LIMIT, "build-inputs")
                require(package.get("version") == build["rootVersion"], "build-versions")
            if path in package_paths:
                package = decode(data, LIMIT, "build-inputs")
                name = package.get("name")
                version = package.get("version")
                require(match(name, r"@guildboard/[a-z0-9-]+") and name not in versions
                        and match(version, rf"{NUMBER}\.{NUMBER}\.{NUMBER}"), "build-versions")
                versions[name] = version
            if path in SETTINGS or path == BUILD_SCRIPT:
                payload[path] = data
        require(versions == build["versions"], "build-versions")
        require(all(digest(payload[path]) == build["outputs"][path] for path in outputs), "build-digests")
        require(git(source, "rev-parse", "--verify", "HEAD").strip() == revision.encode(), "source-revision")
    payload[BUILD] = build_raw
    payload[RECIPE] = (
        f"Source revision {revision}\n"
        "From that checkout with Node 24 and npm, run:\n"
        "npm ci --ignore-scripts\n"
        "npm run build\n"
        f"The build entry point is {BUILD_SCRIPT}.\n"
        f"The completed output inventory is {BUILD}.\n"
    ).encode()
    return revision, payload


def checksum(payload):
    return "".join(f"{digest(payload[path])}  {path}\n" for path in sorted(payload)).encode()


def notes_header(manifest):
    return (
        f'Version: {manifest["version"]}\n'
        f'Revision: {manifest["revision"]}\n'
        f'Artifact SHA-256: {manifest["artifactSha256"]}\n\n'
    ).encode()


def utf8_notes(data):
    try:
        require(bool(data.decode("utf-8").strip()) and b"\0" not in data, "notes")
    except UnicodeError:
        raise Invalid("notes") from None


def build_record(path, payload):
    return {"path": path, "sha256": digest(payload[path])}


def assemble(source, metadata_raw, body):
    metadata = decode(metadata_raw, LIMIT, "metadata")
    validate_metadata(metadata)
    utf8_notes(body)
    # The input is the reviewed body. The generated envelope owns the header.
    require(not body.startswith(b"Version: "), "notes")
    revision, payload = build_payload(source)
    payload[PROVENANCE] = canonical({
        "schemaVersion": SCHEMA,
        "sourceRevision": revision,
        "inputs": [build_record(path, payload) for path in sorted(SETTINGS | {BUILD, BUILD_SCRIPT})],
        "recipe": build_record(RECIPE, payload),
        "checksumIndex": INDEX,
    })
    index = checksum(payload)
    manifest = {
        **metadata, "revision": revision, "artifactSha256": digest(index),
        "notesRef": NOTES, "provenanceRef": PROVENANCE,
    }
    notes = notes_header(manifest) + body
    manifest["notesSha256"] = digest(notes)
    bundle = {**payload, INDEX: index, NOTES: notes, MANIFEST: canonical(manifest)}
    return bundle


def verify_bundle(bundle):
    require(len(bundle) <= MAX_FILES and sum(map(len, bundle.values())) <= MAX_BUNDLE
            and all(len(data) <= MAX_FILE for data in bundle.values()), "bundle-size")
    require(ENVELOPES - {RECEIPT} <= bundle.keys() and RECEIPT not in bundle, "envelope")
    require(all(path_ok(path) for path in bundle), "path")
    for path in bundle:
        parts = path.split("/")
        require(all("/".join(parts[:length]) not in bundle for length in range(1, len(parts))), "path")
    manifest = decode(bundle[MANIFEST], LIMIT, "manifest")
    validate_metadata(manifest, {"revision", "artifactSha256", "notesSha256", "notesRef", "provenanceRef"})
    require(revision_ok(manifest["revision"]) and manifest["notesRef"] == NOTES
            and manifest["provenanceRef"] == PROVENANCE, "manifest")
    payload = {path: data for path, data in bundle.items() if path not in ENVELOPES}
    require(PROVENANCE in payload and bundle[INDEX] == checksum(payload)
            and manifest["artifactSha256"] == digest(bundle[INDEX]), "checksum")
    notes = bundle[NOTES]
    header = notes_header(manifest)
    require(len(notes) <= 256 * 1024 and notes.startswith(header)
            and manifest["notesSha256"] == digest(notes), "notes")
    utf8_notes(notes[len(header):])
    provenance = decode(payload[PROVENANCE], 64 * 1024, "provenance")
    require(record(provenance, {"schemaVersion", "sourceRevision", "inputs", "recipe", "checksumIndex"})
            and provenance["schemaVersion"] == SCHEMA and provenance["sourceRevision"] == manifest["revision"]
            and provenance["checksumIndex"] == INDEX, "provenance")
    inputs = provenance["inputs"]
    require(type(inputs) is list and 1 <= len(inputs) <= 64, "provenance")
    seen = set()
    for item in [*inputs, provenance["recipe"]]:
        require(record(item, {"path", "sha256"}) and path_ok(item["path"]), "provenance")
        path = item["path"]
        require(path in payload and path != PROVENANCE and path not in seen
                and item["sha256"] == digest(payload[path]), "provenance")
        seen.add(path)
    identity = {key: manifest[key] for key in IDENTITY - {"manifestSha256"}}
    identity["manifestSha256"] = digest(bundle[MANIFEST])
    return manifest, identity


def require_private(root):
    info = os.fstat(root)
    require(info.st_uid == os.geteuid() and not info.st_mode & 0o077, "private-root")


def read_bundle(root, version):
    with directories(root, (version,)) as private:
        require_private(private)
        return file_bytes(private, scan(private))


def sync_directory(path):
    with directory(path) as descriptor:
        os.fsync(descriptor)


def stage(output, bundle):
    _, identity = verify_bundle(bundle)
    version = identity["version"]
    with directory(output) as root:
        require_private(root)
        # Cooperating stagers serialize check and promotion. Linux releases the
        # lock even when the writing process is interrupted.
        fcntl.flock(root, fcntl.LOCK_EX)
        try:
            os.stat(version, dir_fd=root, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            try:
                identical = read_bundle(root, version) == bundle
            except (Invalid, OSError):
                identical = False
            require(identical, "version-conflict")
            # A prior rename may have succeeded before the staging root was synced.
            os.fsync(root)
            return identity
        # Address the held directory for staging as well as promotion.
        root_path = Path(f"/proc/self/fd/{root}")
        with tempfile.TemporaryDirectory(prefix=".stage-", dir=root_path) as name:
            temporary = Path(name)
            for member, data in sorted(bundle.items()):
                target = temporary / member
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            # Resolve the controlled temporary path before the no-link directory walk.
            for parent, _, _ in os.walk(temporary.resolve(), topdown=False):
                sync_directory(Path(parent))
            os.rename(temporary.name, version, src_dir_fd=root, dst_dir_fd=root)
            os.fsync(root)
    return identity


def verify_authority(manifest, identity, snapshot_raw, pin, today):
    require(digest_ok(pin) and digest(snapshot_raw) == pin, "authority-digest")
    snapshot = decode(snapshot_raw, LIMIT, "authority")
    require(record(snapshot, {"schemaVersion", "validFrom", "validUntil", "approval", "prerequisites"})
            and snapshot["schemaVersion"] == SCHEMA, "authority")
    require(parse_date(snapshot["validFrom"], "authority-window") <= today
            < parse_date(snapshot["validUntil"], "authority-window"), "authority-window")
    approval = snapshot["approval"]
    require(record(approval, {"schemaVersion", "gate", "identity", "decision", "decisionRef", "provenanceRef"})
            and approval["schemaVersion"] == SCHEMA and approval["gate"] == manifest["gate"]
            and approval["identity"] == identity and approval["decision"] == "approved"
            and ref_ok(approval["decisionRef"]) and approval["provenanceRef"] == manifest["provenanceRef"],
            "approval")
    prerequisites = snapshot["prerequisites"]
    require(record(prerequisites, {"gate", "identity", "decision", "decisionRef", "evidence", "mvpPublication"})
            and prerequisites["gate"] == manifest["gate"] and prerequisites["identity"] == identity
            and prerequisites["decision"] == "accepted" and ref_ok(prerequisites["decisionRef"])
            and prerequisites["evidence"] == manifest["evidence"]
            and prerequisites["mvpPublication"] == manifest.get("mvpPublication"), "prerequisites")
    require(manifest["gate"] != G3 or mvp_ok(prerequisites["mvpPublication"]), "mvp-publication")
    required_issue, required_level = (
        ("GB-T12.MVP1", "real-discord") if manifest["gate"] == G1 else ("GB-T13.G2", "real-godaddy")
    )
    rows = manifest["evidence"]
    require(all(row["result"] == "pass" and parse_date(row["date"], "evidence") <= today for row in rows)
            and any(row["issue"] == required_issue and row["level"] == required_level
                    and row["revision"] == manifest["revision"] for row in rows),
            "evidence")


def dry_run(output, version, snapshot, pin, today):
    require(version_ok(version), "version")
    with directory(output) as root:
        require_private(root)
        manifest, identity = verify_bundle(read_bundle(root, version))
    require(identity["version"] == version, "version")
    report = {
        "schemaVersion": SCHEMA, "operation": "dry-run", "identity": identity,
        "gate": manifest["gate"], "date": today.isoformat(),
    }
    try:
        require(snapshot is not None and pin is not None, "authority")
        raw = external_file(snapshot, LIMIT, "authority")
        verify_authority(manifest, identity, raw, pin, today)
    except Invalid as error:
        return {**report, "outcome": "PREREQUISITE_UNAVAILABLE", "category": str(error)}
    return {**report, "outcome": "DRY_RUN_ACCEPTED", "authoritySha256": pin}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    staging = commands.add_parser("stage")
    staging.add_argument("--source", required=True, type=Path)
    staging.add_argument("--metadata", required=True, type=Path)
    staging.add_argument("--notes-body", required=True, type=Path)
    staging.add_argument("--output", required=True, type=Path)
    gate = commands.add_parser("dry-run")
    gate.add_argument("--output", required=True, type=Path)
    gate.add_argument("--version", required=True)
    gate.add_argument("--authority", type=Path)
    gate.add_argument("--authority-sha256")
    args = parser.parse_args(argv)
    try:
        if args.operation == "stage":
            bundle = assemble(args.source, external_file(args.metadata, LIMIT, "metadata"),
                              external_file(args.notes_body, 256 * 1024, "notes"))
            report = {"schemaVersion": SCHEMA, "operation": "stage", "outcome": "STAGED",
                      "identity": stage(args.output, bundle)}
        else:
            report = dry_run(args.output, args.version, args.authority, args.authority_sha256,
                             datetime.now(UTC).date())
    except Invalid as error:
        category = str(error)
        outcome = "VERSION_CONFLICT" if category == "version-conflict" else "INVALID_METADATA"
        report = {"schemaVersion": SCHEMA, "operation": args.operation, "outcome": outcome,
                  "category": category}
    except (OSError, UnicodeError):
        report = {"schemaVersion": SCHEMA, "operation": args.operation, "outcome": "INPUT_UNAVAILABLE"}
    sys.stdout.buffer.write(canonical(report))
    return {"STAGED": 0, "DRY_RUN_ACCEPTED": 0, "PREREQUISITE_UNAVAILABLE": 3}.get(report["outcome"], 2)


if __name__ == "__main__":
    sys.exit(main())
