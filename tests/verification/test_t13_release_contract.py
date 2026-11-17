"""Declarative GB-T13.S1 examples with an in-memory publication model."""

from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "docs/specifications/fixtures/GB-T13-S1-scenarios.json"
IDENTITY = {"version", "revision", "artifactSha256", "manifestSha256", "notesSha256"}
MANIFEST = (IDENTITY - {"manifestSha256"}) | {
    "schemaVersion", "gate", "notesRef", "provenanceRef", "evidence",
}
APPROVAL = {"schemaVersion", "gate", "identity", "decision", "decisionRef", "provenanceRef"}
SCHEMA_VERSION = "1.0.0"
REPOSITORY = "https://github.com/CompleteTech-DiscordApps/guildboard"
DIGEST = re.compile(r"[0-9a-f]{64}")
RECORD = {"id", "issue", "revision", "date", "environment", "level", "result", "ref"}
LEVELS = {
    "static", "synthetic", "integration", "independent-review",
    "real-discord", "real-godaddy",
}
NUMBER = r"(?:0|[1-9][0-9]*)"
PRERELEASE_ID = rf"(?:{NUMBER}|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
SEMVER = re.compile(
    rf"{NUMBER}\.{NUMBER}\.{NUMBER}"
    rf"(?:-{PRERELEASE_ID}(?:\.{PRERELEASE_ID})*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def strings(record, fields):
    return all(isinstance(record[key], str) and 0 < len(record[key]) <= 256 for key in fields)


def safe_ref(value):
    if value.startswith("https://github.com/CompleteTech-DiscordApps/guildboard/"):
        return bool(re.fullmatch(
            r"https://github\.com/CompleteTech-DiscordApps/guildboard/"
            r"(?:(?:issues|pull|actions/runs)/[1-9][0-9]*|commit/[0-9a-f]{40})",
            value,
        ))
    return safe_path(value)


def safe_path(value):
    return all(re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", part)
               for part in value.split("/"))


def valid_record(record):
    if not isinstance(record, dict) or record.keys() != RECORD or not strings(record, RECORD):
        return False
    try:
        calendar_date = date.fromisoformat(record["date"])
    except ValueError:
        return False
    return (
        calendar_date.isoformat() == record["date"]
        and re.fullmatch(r"[a-z][a-z0-9-]*", record["id"])
        and re.fullmatch(r"GB-T[0-9]+(?:\.[A-Z0-9]+)*", record["issue"])
        and re.fullmatch(r"[0-9a-f]{40}", record["revision"])
        and record["level"] in LEVELS
        and record["result"] in {"pass", "fail", "blocked"}
        and safe_ref(record["ref"])
    )


def valid_manifest(candidate):
    if (not isinstance(candidate, dict) or candidate.keys() != MANIFEST
            or not strings(candidate, MANIFEST - {"evidence"})):
        return False
    if not (
        candidate["schemaVersion"] == SCHEMA_VERSION
        and candidate["gate"] == "GB-T13.G1"
        and SEMVER.fullmatch(candidate["version"])
        and re.fullmatch(r"[0-9a-f]{40}", candidate["revision"])
        and DIGEST.fullmatch(candidate["artifactSha256"])
        and DIGEST.fullmatch(candidate["notesSha256"])
        and safe_ref(candidate["notesRef"])
        and safe_ref(candidate["provenanceRef"])
    ):
        return False
    evidence = candidate["evidence"]
    return (
        isinstance(evidence, list) and len(evidence) <= 128
        and all(valid_record(record) for record in evidence)
        and len({record["id"] for record in evidence}) == len(evidence)
    )


def digest(data):
    return sha256(data).hexdigest()


def checksum_index(files):
    return "".join(f"{digest(content)}  {path}\n"
                   for path, content in sorted(files.items())).encode("ascii")


@dataclass(frozen=True)
class Bundle:
    files: dict
    index: bytes
    manifest: bytes
    notes: bytes


@dataclass(frozen=True)
class Publication:
    identity: dict
    bundle: Bundle
    approval: dict
    receipt: dict
    tag_revision: str
    release_tag: str


@dataclass(frozen=True)
class State:
    current: dict | None
    versions: dict


def verified_bundle(bundle):
    if (len(bundle.manifest) > 512 * 1024 or not bundle.files
            or any(len(path) > 256 or not safe_path(path) for path in bundle.files)):
        return None
    try:
        manifest = json.loads(bundle.manifest.decode("utf-8"), object_pairs_hook=strict_object)
    except (UnicodeError, ValueError, RecursionError):
        return None
    if not valid_manifest(manifest) or bundle.index != checksum_index(bundle.files):
        return None
    if (manifest["artifactSha256"] != digest(bundle.index)
            or manifest["notesSha256"] != digest(bundle.notes)):
        return None
    identity = {field: manifest[field] for field in IDENTITY - {"manifestSha256"}}
    identity["manifestSha256"] = digest(bundle.manifest)
    return manifest, identity


def valid_approval(approval, manifest, identity):
    return (
        isinstance(approval, dict) and approval.keys() == APPROVAL
        and strings(approval, APPROVAL - {"identity"})
        and approval["schemaVersion"] == SCHEMA_VERSION
        and approval["gate"] == manifest["gate"]
        and approval["identity"] == identity
        and approval["decision"] == "approved"
        and safe_ref(approval["decisionRef"])
        and approval["provenanceRef"] == manifest["provenanceRef"]
    )


def receipt_for(approval):
    receipt = {field: approval[field] for field in APPROVAL - {"decision"}}
    tag = f'v{approval["identity"]["version"]}'
    receipt["tagRef"] = f"refs/tags/{tag}"
    receipt["releaseRef"] = f"{REPOSITORY}/releases/tag/{tag}"
    return receipt


def verified_receipt(state, identity, authoritative_approvals):
    version = identity["version"]
    published = state.versions.get(version)
    if published is None or state.current is None:
        return None

    # The pointer must resolve to its own version record, including on historical retries.
    current = state.versions.get(state.current["version"])
    if current is None or current.identity != state.current:
        return None

    verified = verified_bundle(published.bundle)
    if verified is None:
        return None
    manifest, observed_identity = verified
    approval = published.approval
    if (published.identity != identity or observed_identity != identity
            or not valid_approval(approval, manifest, identity)
            or approval not in authoritative_approvals):
        return None

    receipt = receipt_for(approval)
    if (published.receipt != receipt or published.tag_revision != identity["revision"]
            or published.release_tag != receipt["tagRef"]):
        return None
    return receipt


def reconcile(state, identity, expected_prior, authoritative_approvals):
    """Read back an uncertain commit without altering the authoritative state."""
    if state is None:
        return "PUBLICATION_UNKNOWN", None
    receipt = verified_receipt(state, identity, authoritative_approvals)
    if receipt is not None:
        return "ALREADY_PUBLISHED", receipt
    if identity["version"] in state.versions:
        return "PUBLICATION_UNKNOWN", None
    if state.current is not None and verified_receipt(
        state, state.current, authoritative_approvals
    ) is None:
        return "PUBLICATION_UNKNOWN", None
    if state.current == expected_prior:
        return "RETRY_CONDITIONALLY", None
    return "PREVIOUS_PUBLICATION_CHANGED", None


def attempt(bundle, identity, approval, state, expected_prior, *,
            authoritative_approvals, native_ready=True, interruption=None):
    """Model one G1 evidence row and one atomic version reservation and publication."""
    verified = verified_bundle(bundle)
    if verified is None or verified[1] != identity:
        return "INVALID_METADATA", state, None

    manifest, identity = verified
    version = identity["version"]
    if version in state.versions:
        if state.versions[version].identity != identity:
            return "VERSION_CONFLICT", state, None
        outcome, receipt = reconcile(state, identity, expected_prior, authoritative_approvals)
        return outcome, state, receipt

    if (not valid_approval(approval, manifest, identity)
            or approval not in authoritative_approvals or not native_ready
            or not any(
                record["id"] == "discord-startup"
                and record["issue"] == "GB-T12.MVP1"
                and record["level"] == "real-discord"
                and record["revision"] == identity["revision"]
                and record["result"] == "pass"
                for record in manifest["evidence"]
            )):
        return "PREREQUISITE_UNAVAILABLE", state, None
    if state.current != expected_prior:
        return "PREVIOUS_PUBLICATION_CHANGED", state, None
    if interruption == "before":
        return "PUBLICATION_INTERRUPTED", state, None

    receipt = receipt_for(approval)
    publication = Publication(identity, bundle, approval, receipt, identity["revision"],
                              receipt["tagRef"])
    committed = deepcopy(State(identity, {**state.versions, version: publication}))
    if interruption == "after":
        return "PUBLICATION_UNKNOWN", committed, None
    readback = verified_receipt(committed, identity, authoritative_approvals)
    if readback is None:
        return "PUBLICATION_UNKNOWN", committed, None
    return "PUBLISHED", committed, readback


class ReleaseContractScenarios(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"),
                                  object_pairs_hook=strict_object)
        self.approvals = []
        self.prior_bundle, self.prior_identity, self.prior_approval = self.stage(
            version=self.fixture["priorVersion"],
        )
        outcome, self.prior, _ = self.publish(
            self.prior_bundle, self.prior_identity, self.prior_approval,
            State(None, {}),
        )
        self.assertEqual(outcome, "PUBLISHED")

    def stage(self, *, version=None, scenario=None, notes=None):
        scenario = scenario or {}
        manifest = deepcopy(self.fixture["manifest"])
        files = {path: content.encode("utf-8") for path, content in self.fixture["files"].items()}
        notes = (notes if notes is not None else self.fixture["notes"]).encode("utf-8")
        index = checksum_index(files)
        manifest.update(artifactSha256=digest(index), notesSha256=digest(notes))
        if version is not None:
            manifest["version"] = version
        manifest.update(scenario.get("candidatePatch", {}))
        if "recordPatch" in scenario:
            manifest["evidence"][0].update(scenario["recordPatch"])
        manifest_bytes = json.dumps(manifest, sort_keys=True).encode("utf-8")
        bundle = Bundle(files, index, manifest_bytes, notes)
        identity = {field: manifest[field] for field in IDENTITY - {"manifestSha256"}}
        identity["manifestSha256"] = digest(manifest_bytes)
        approval = {
            **self.fixture["approval"],
            "gate": manifest["gate"],
            "identity": identity,
            "decisionRef": f'synthetic/decisions/{identity["manifestSha256"]}.json',
            "provenanceRef": manifest["provenanceRef"],
        }
        self.approvals.append(deepcopy(approval))
        return bundle, identity, approval

    def publish(self, bundle, identity, approval, state, *, expected_matches=True, **kwargs):
        return attempt(
            bundle, identity, approval, state, state.current if expected_matches else None,
            authoritative_approvals=self.approvals, **kwargs,
        )

    def commit_candidate(self):
        bundle, identity, approval = self.stage()
        outcome, state, receipt = self.publish(bundle, identity, approval, self.prior)
        self.assertEqual(outcome, "PUBLISHED")
        self.assertEqual(receipt, receipt_for(approval))
        return bundle, identity, approval, state

    def test_fixture_scenarios(self):
        for scenario in self.fixture["scenarios"]:
            with self.subTest(scenario=scenario["id"]):
                bundle, identity, approval = self.stage(scenario=scenario)
                outcome, state, receipt = self.publish(
                    bundle, identity, approval, self.prior,
                    expected_matches=scenario.get("expectedPriorMatches", True),
                    native_ready=scenario.get("nativeReady", True),
                    interruption=scenario.get("interruption"),
                )
                expected = identity if scenario["current"] == "candidate" else self.prior_identity
                self.assertEqual(outcome, scenario["expected"])
                self.assertEqual(state.current, expected)
                self.assertEqual(receipt, receipt_for(approval) if outcome == "PUBLISHED" else None)
                if expected == self.prior_identity:
                    self.assertIs(state, self.prior)

    def test_current_and_historical_version_conflicts_independent_of_prior(self):
        _, candidate, _, published = self.commit_candidate()
        for version in (candidate["version"], self.prior_identity["version"]):
            changes = (
                {"notes": "Different notes\n"},
                {"scenario": {"recordPatch": {"environment": "different synthetic evidence"}}},
            )
            for change in changes:
                bundle, identity, approval = self.stage(version=version, **change)
                self.assertEqual(identity["artifactSha256"], candidate["artifactSha256"])
                for expected_matches in (True, False):
                    with self.subTest(version=version, change=change,
                                      expected_matches=expected_matches):
                        snapshot = deepcopy(published)
                        result = self.publish(bundle, identity, approval, published,
                                              expected_matches=expected_matches)
                        self.assertEqual(result, ("VERSION_CONFLICT", snapshot, None))
                        self.assertIs(result[1], published)

    def test_current_and_historical_exact_retry_preserve_pointer_and_receipts(self):
        bundle, identity, approval, state = self.commit_candidate()
        for retry in ((bundle, identity, approval),
                      (self.prior_bundle, self.prior_identity, self.prior_approval)):
            for expected_matches in (True, False):
                with self.subTest(version=retry[1]["version"], expected_matches=expected_matches):
                    before = deepcopy(state)
                    result = self.publish(*retry, state, expected_matches=expected_matches)
                    self.assertEqual(result, ("ALREADY_PUBLISHED", before, receipt_for(retry[2])))
                    self.assertIs(result[1], state)
                    self.assertEqual(state.current, identity)

    def test_readback_rejects_altered_manifest_or_notes_with_same_binary(self):
        _, identity, _, state = self.commit_candidate()
        version = identity["version"]
        publication = state.versions[version]
        manifest_only = self.stage(scenario={
            "recordPatch": {"environment": "different synthetic evidence"}
        })[0]
        changed_notes = self.stage(notes="Different notes\n")[0]
        for bundle in (manifest_only, changed_notes):
            with self.subTest(identity=verified_bundle(bundle)[1]):
                self.assertEqual(bundle.files, publication.bundle.files)
                self.assertEqual(bundle.index, publication.bundle.index)
                altered = replace(
                    state, versions={**state.versions, version: replace(publication, bundle=bundle)},
                )
                self.assertEqual(
                    reconcile(altered, identity, self.prior_identity, self.approvals),
                    ("PUBLICATION_UNKNOWN", None),
                )

    def test_approval_binds_exact_candidate(self):
        _, _, approval = self.stage()
        original_bundle, original_identity, _ = self.stage()
        bundle = self.stage(notes="Different notes\n")[0]
        changed_binary = {**original_bundle.files, "dist/client.js": b"new synthetic bytes"}
        changed_index = checksum_index(changed_binary)
        binary_manifest = json.loads(original_bundle.manifest)
        binary_manifest["artifactSha256"] = digest(changed_index)
        binary_bundle = replace(original_bundle, files=changed_binary, index=changed_index,
                                manifest=json.dumps(binary_manifest).encode("utf-8"))
        manifest_bundle = self.stage(scenario={
            "recordPatch": {"environment": "different synthetic evidence"}
        })[0]
        for changed in (bundle, binary_bundle, manifest_bundle):
            with self.subTest(identity=verified_bundle(changed)[1]):
                manifest, identity = verified_bundle(changed)
                self.assertEqual(identity["revision"], original_identity["revision"])
                self.assertFalse(valid_approval(approval, manifest, identity))
                self.assertEqual(self.publish(changed, identity, approval, self.prior),
                                 ("PREREQUISITE_UNAVAILABLE", self.prior, None))

    def test_approval_gate_decision_and_provenance_are_checked(self):
        bundle, identity, approval = self.stage()
        for patch in (
            {"gate": "GB-T13.G3"}, {"decision": "denied"},
            {"provenanceRef": "synthetic/other-build.json"}, {"decisionRef": "../private"},
        ):
            with self.subTest(patch=patch):
                changed = {**approval, **patch}
                self.approvals.append(changed)
                self.assertEqual(self.publish(bundle, identity, changed, self.prior),
                                 ("PREREQUISITE_UNAVAILABLE", self.prior, None))
        self.approvals.remove(approval)
        self.assertEqual(self.publish(bundle, identity, approval, self.prior),
                         ("PREREQUISITE_UNAVAILABLE", self.prior, None))

    def test_readback_checks_receipt_references_and_resolved_targets(self):
        _, identity, _, state = self.commit_candidate()
        version = identity["version"]
        published = state.versions[version]
        changed = [
            replace(published, receipt={**published.receipt, field: "synthetic/wrong"})
            for field in ("gate", "decisionRef", "provenanceRef", "releaseRef", "tagRef")
        ]
        changed.extend((
            replace(published, tag_revision=self.fixture["otherRevision"]),
            replace(published, release_tag="refs/tags/wrong"),
            replace(published, receipt={**published.receipt, "identity": self.prior_identity}),
        ))
        for observation in changed:
            with self.subTest(observation=observation):
                corrupted = replace(state, versions={**state.versions, version: observation})
                self.assertEqual(
                    reconcile(corrupted, identity, self.prior_identity, self.approvals),
                    ("PUBLICATION_UNKNOWN", None),
                )

    def test_checksum_index_and_exact_metadata(self):
        bundle, identity, approval = self.stage()
        self.assertEqual(list(bundle.files), sorted(bundle.files, reverse=True))
        self.assertEqual(bundle.index.splitlines()[0].split(b"  ")[1], b"dist/client.js")
        for files in (
            {**bundle.files, "dist/client.js": b"tampered"},
            {**bundle.files, "dist/extra": b"unlisted"},
            {"dist/client.js": bundle.files["dist/client.js"]},
        ):
            with self.subTest(files=files):
                self.assertEqual(self.publish(replace(bundle, files=files), identity, approval,
                                              self.prior),
                                 ("INVALID_METADATA", self.prior, None))
        self.assertEqual(self.publish(bundle, self.prior_identity, approval, self.prior),
                         ("INVALID_METADATA", self.prior, None))

    def test_precommit_retry_and_postcommit_reconciliation(self):
        bundle, identity, approval = self.stage()
        early = self.publish(bundle, identity, approval, self.prior, interruption="before")
        self.assertEqual(early, ("PUBLICATION_INTERRUPTED", self.prior, None))
        self.assertEqual(reconcile(early[1], identity, self.prior_identity, self.approvals),
                         ("RETRY_CONDITIONALLY", None))
        outcome, committed, receipt = self.publish(
            bundle, identity, approval, early[1], interruption="after",
        )
        self.assertEqual((outcome, receipt), ("PUBLICATION_UNKNOWN", None))
        self.assertEqual(reconcile(None, identity, self.prior_identity, self.approvals),
                         ("PUBLICATION_UNKNOWN", None))
        self.assertEqual(reconcile(committed, identity, self.prior_identity, self.approvals),
                         ("ALREADY_PUBLISHED", receipt_for(approval)))

        newer_bundle, newer_identity, newer_approval = self.stage(version="0.1.0-mvp.2")
        outcome, newer, _ = self.publish(newer_bundle, newer_identity, newer_approval, committed)
        self.assertEqual(outcome, "PUBLISHED")
        self.assertEqual(reconcile(newer, identity, self.prior_identity, self.approvals),
                         ("ALREADY_PUBLISHED", receipt_for(approval)))
        self.assertEqual(newer.current, newer_identity)

        _, competing, _ = self.publish(newer_bundle, newer_identity, newer_approval, self.prior)
        self.assertEqual(reconcile(competing, identity, self.prior_identity, self.approvals),
                         ("PREVIOUS_PUBLICATION_CHANGED", None))

    def test_duplicate_evidence_ids_and_input_keys(self):
        manifest = deepcopy(self.fixture["manifest"])
        manifest.update(artifactSha256="a" * 64, notesSha256="b" * 64)
        self.assertTrue(valid_manifest(manifest))
        manifest["evidence"].append(deepcopy(manifest["evidence"][0]))
        self.assertFalse(valid_manifest(manifest))
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            json.loads('{"version": "1.0.0", "version": "2.0.0"}',
                       object_pairs_hook=strict_object)


if __name__ == "__main__":
    unittest.main()
