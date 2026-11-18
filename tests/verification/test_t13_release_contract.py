"""Declarative GB-T13.S1 examples with an in-memory publication model."""

from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import date
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "docs/specifications/fixtures/GB-T13-S1-scenarios.json"
IDENTITY = {"version", "revision", "artifactSha256", "manifestSha256", "notesSha256"}
MANIFEST = (IDENTITY - {"manifestSha256"}) | {
    "schemaVersion", "gate", "notesRef", "provenanceRef", "evidence",
}
APPROVAL = {"schemaVersion", "gate", "identity", "decision", "decisionRef", "provenanceRef"}
MVP_PUBLICATION = {"identity", "releaseRef"}
NATIVE_DECISION = {"identity", "gate", "decision", "authority", "decisionRef", "evidenceRefs", "mvpPublication"}
NATIVE_AUTHORITY = "synthetic/native-maintainer"
SCHEMA_VERSION = "1.0.0"
MAX_VERSION = 128
INDEX_PATH = "SHA256SUMS"
ENVELOPE_PATHS = {INDEX_PATH, "manifest.json", "publication-receipt.json"}
GATES = {"GB-T13.G1", "GB-T13.G2", "GB-T13.G3"}
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


def valid_version(value):
    return isinstance(value, str) and len(value) <= MAX_VERSION and bool(SEMVER.fullmatch(value))


def precedence(version):
    core, _, pre = version.split("+", 1)[0].partition("-")
    identifiers = tuple((0, int(part)) if part.isdigit() else (1, part)
                        for part in pre.split(".")) if pre else ()
    return tuple(map(int, core.split("."))), not pre, identifiers


def release_gate(version):
    core, final, _ = precedence(version)
    major = core[0]
    if major == 0:
        return "GB-T13.G1"
    return "GB-T13.G3" if final else None


def safe_ref(value):
    release_prefix = f"{REPOSITORY}/releases/tag/v"
    if value.startswith(release_prefix):
        return bool(valid_version(value.removeprefix(release_prefix)))
    if value.startswith(REPOSITORY + "/"):
        return bool(re.fullmatch(
            re.escape(REPOSITORY) + r"/(?:(?:issues|pull|actions/runs)/[1-9][0-9]*|commit/[0-9a-f]{40})",
            value,
        ))
    return safe_path(value)


def safe_path(value):
    return isinstance(value, str) and len(value) <= 256 and all(
        re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", part) for part in value.split("/")
    )


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
    if not isinstance(candidate, dict):
        return False
    optional = {"mvpPublication"} if candidate.get("gate") == "GB-T13.G3" else set()
    if (candidate.keys() - optional != MANIFEST
            or not strings(candidate, MANIFEST - {"evidence"})):
        return False
    if not (
        candidate["schemaVersion"] == SCHEMA_VERSION
        and candidate["gate"] in GATES
        and valid_version(candidate["version"])
        and re.fullmatch(r"[0-9a-f]{40}", candidate["revision"])
        and DIGEST.fullmatch(candidate["artifactSha256"])
        and DIGEST.fullmatch(candidate["notesSha256"])
        and safe_path(candidate["notesRef"])
        and safe_path(candidate["provenanceRef"])
    ):
        return False
    evidence = candidate["evidence"]
    return (
        isinstance(evidence, list) and len(evidence) <= 128
        and all(valid_record(record) for record in evidence)
        and len({record["id"] for record in evidence}) == len(evidence)
        and ("mvpPublication" not in candidate or valid_mvp_reference(candidate["mvpPublication"]))
    )

def valid_mvp_reference(reference):
    if not isinstance(reference, dict) or reference.keys() != MVP_PUBLICATION:
        return False
    identity = reference["identity"]
    if (not isinstance(identity, dict) or identity.keys() != IDENTITY
            or not strings(identity, IDENTITY)):
        return False
    version = identity["version"]
    return (
        valid_version(version) and release_gate(version) == "GB-T13.G1"
        and re.fullmatch(r"[0-9a-f]{40}", identity["revision"])
        and all(DIGEST.fullmatch(identity[key]) for key in IDENTITY if key.endswith("Sha256"))
        and reference["releaseRef"] == f"{REPOSITORY}/releases/tag/v{version}"
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
    notes_path: str
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
    committed_authorizations: dict = field(default_factory=dict)
    designated_mvp: dict | None = None
    reservation_proof_digests: tuple = ()


def json_object(data, limit):
    if len(data) <= limit:
        try:
            return json.loads(data.decode("utf-8"), object_pairs_hook=strict_object)
        except (UnicodeError, ValueError, RecursionError):
            return None
    return None


def valid_build_file(record, files, provenance_path):
    return (isinstance(record, dict) and record.keys() == {"path", "sha256"}
            and safe_path(record["path"]) and record["path"] != provenance_path
            and record["path"] in files and record["sha256"] == digest(files[record["path"]]))


def valid_provenance(manifest, files):
    path = manifest["provenanceRef"]
    provenance = json_object(files.get(path, b""), 64 * 1024)
    if (not isinstance(provenance, dict)
            or provenance.keys() != {"schemaVersion", "sourceRevision", "inputs", "recipe", "checksumIndex"}
            or provenance["schemaVersion"] != SCHEMA_VERSION
            or provenance["sourceRevision"] != manifest["revision"]
            or provenance["checksumIndex"] != INDEX_PATH):
        return False
    inputs = provenance["inputs"]
    return (isinstance(inputs, list) and 1 <= len(inputs) <= 64
            and all(valid_build_file(record, files, path) for record in inputs)
            and len({record["path"] for record in inputs}) == len(inputs)
            and valid_build_file(provenance["recipe"], files, path))


def notes_header(manifest):
    return (f'Version: {manifest["version"]}\nRevision: {manifest["revision"]}\n'
            f'Artifact SHA-256: {manifest["artifactSha256"]}\n\n')


def verified_bundle(bundle):
    manifest = json_object(bundle.manifest, 512 * 1024)
    if (not valid_manifest(manifest) or not bundle.files
            or any(not safe_path(path) for path in bundle.files)
            or ENVELOPE_PATHS.intersection(bundle.files) or bundle.notes_path in bundle.files
            or bundle.notes_path in ENVELOPE_PATHS or bundle.notes_path != manifest["notesRef"]):
        return None
    paths = {*bundle.files, *ENVELOPE_PATHS, bundle.notes_path}
    parents = {str(parent) for path in paths for parent in PurePosixPath(path).parents}
    if (paths.intersection(parents)
            or bundle.index != checksum_index(bundle.files)
            or manifest["artifactSha256"] != digest(bundle.index)
            or len(bundle.notes) > 256 * 1024 or manifest["notesSha256"] != digest(bundle.notes)
            or not valid_provenance(manifest, bundle.files)):
        return None
    try:
        if not bundle.notes.decode("utf-8").startswith(notes_header(manifest)):
            return None
    except UnicodeError:
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
    receipt = deepcopy({field: approval[field] for field in APPROVAL - {"decision"}})
    tag = f'v{approval["identity"]["version"]}'
    receipt["tagRef"] = f"refs/tags/{tag}"
    receipt["releaseRef"] = f"{REPOSITORY}/releases/tag/{tag}"
    return receipt


def valid_native_decision(decision, manifest, identity):
    return (
        isinstance(decision, dict) and decision.keys() == NATIVE_DECISION
        and strings(decision, {"gate", "decision", "authority", "decisionRef"})
        and decision["authority"] == NATIVE_AUTHORITY and decision["decision"] == "accepted"
        and decision["identity"] == identity and decision["gate"] == manifest["gate"]
        and safe_ref(decision["decisionRef"])
        and decision["evidenceRefs"] == [row["ref"] for row in manifest["evidence"]]
        and decision["mvpPublication"] == manifest.get("mvpPublication")
    )


def immutable_json(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")


def matches_authorization_proof(record, approval, manifest, identity):
    if not isinstance(record, bytes):
        return False
    proof = json_object(record, 512 * 1024)
    return (
        isinstance(proof, dict) and proof.keys() == {"approval", "nativeDecision"}
        and proof["approval"] == approval
        and valid_native_decision(proof["nativeDecision"], manifest, identity)
    )


def verified_receipt(state, identity):
    version = identity["version"]
    published = state.versions.get(version)
    if published is None:
        return None

    verified = verified_bundle(published.bundle)
    if verified is None:
        return None
    manifest, observed_identity = verified
    approval = published.approval
    proof = state.committed_authorizations.get(version)
    reserved_proof_digest = dict(state.reservation_proof_digests).get(version)
    if (published.identity != identity or observed_identity != identity
            or manifest["gate"] != release_gate(identity["version"])
            or not valid_approval(approval, manifest, identity)
            or not matches_authorization_proof(proof, approval, manifest, identity)
            or digest(proof) != reserved_proof_digest):
        return None

    receipt = receipt_for(approval)
    if (published.receipt != receipt or published.tag_revision != identity["revision"]
            or published.release_tag != receipt["tagRef"]):
        return None
    return receipt


def valid_current(state):
    if state is None:
        return False
    if state.current is None:
        return not (state.versions or state.committed_authorizations or state.reservation_proof_digests)
    if not isinstance(state.current, dict) or state.current.keys() != IDENTITY:
        return False
    version = state.current["version"]
    return (valid_version(version) and verified_receipt(state, state.current) is not None
            and state.committed_authorizations.keys() == state.versions.keys()
            and dict(state.reservation_proof_digests).keys() == state.versions.keys()
            and len(state.reservation_proof_digests) == len(state.versions)
            and all(valid_version(other) and precedence(other) < precedence(version)
                    for other in state.versions if other != version))


def advances(version, state):
    return state.current is None or precedence(version) > precedence(state.current["version"])


def reconcile(state, identity, expected_prior):
    """Resolve a possibly committed publication against the authoritative state."""
    if not valid_current(state):
        return "PUBLICATION_UNKNOWN", None
    if identity["version"] in state.versions:
        receipt = verified_receipt(state, identity)
        return ("ALREADY_PUBLISHED", receipt) if receipt else ("PUBLICATION_UNKNOWN", None)
    if state.current != expected_prior:
        return "PREVIOUS_PUBLICATION_CHANGED", None
    if not advances(identity["version"], state):
        return "VERSION_NOT_FORWARD", None
    return "RETRY_CONDITIONALLY", None


def verified_mvp_publication(state, manifest):
    reference = manifest.get("mvpPublication")
    if not valid_mvp_reference(reference) or reference != state.designated_mvp:
        return False
    receipt = verified_receipt(state, reference["identity"])
    return receipt is not None and receipt["releaseRef"] == reference["releaseRef"]


def attempt(bundle, identity, approval, state, expected_prior, *,
            authoritative_approvals, authoritative_native_decisions, interruption=None,
            authorization_at_commit=None):
    """Model a representative evidence row per publication path and atomic commit."""
    verified = verified_bundle(bundle)
    if verified is None or verified[1] != identity:
        return "INVALID_METADATA", state, None
    if not valid_current(state):
        return "PUBLICATION_UNKNOWN", state, None

    manifest, identity = verified
    version = identity["version"]
    if version in state.versions:
        if state.versions[version].identity != identity:
            return "VERSION_CONFLICT", state, None
        outcome, receipt = reconcile(state, identity, expected_prior)
        return outcome, state, receipt

    gate = manifest["gate"]
    required = {
        "GB-T13.G1": ("discord-startup", "GB-T12.MVP1", "real-discord"),
        "GB-T13.G3": ("production-smoke", "GB-T13.G2", "real-godaddy"),
    }
    candidate_digest = identity["manifestSha256"]
    native_decision = authoritative_native_decisions.get(candidate_digest)
    if (gate != release_gate(version)
            or not valid_approval(approval, manifest, identity)
            or approval not in authoritative_approvals
            or not valid_native_decision(native_decision, manifest, identity)
            or (gate == "GB-T13.G3" and not verified_mvp_publication(state, manifest))
            or (gate == "GB-T13.G3" and release_gate(state.current["version"]) == "GB-T13.G1"
                and version != "1.0.0")
            or not any(
                (record["id"], record["issue"], record["level"]) == required[gate]
                and record["revision"] == identity["revision"] and record["result"] == "pass"
                for record in manifest["evidence"]
            )):
        return "PREREQUISITE_UNAVAILABLE", state, None
    if state.current != expected_prior:
        return "PREVIOUS_PUBLICATION_CHANGED", state, None
    if not advances(version, state):
        return "VERSION_NOT_FORWARD", state, None
    if interruption == "before":
        return "PUBLICATION_INTERRUPTED", state, None

    # Freeze the verified authority inputs before simulating a concurrent change.
    verified_approval = json.loads(immutable_json(approval))
    native_snapshot = immutable_json(native_decision)
    prior_snapshot = deepcopy(expected_prior)
    if authorization_at_commit is not None:
        current_approvals, current_native_decisions = authorization_at_commit()
        current_decision = current_native_decisions.get(candidate_digest)
        if (immutable_json(current_decision) != native_snapshot
                or verified_approval not in current_approvals):
            return "PREREQUISITE_UNAVAILABLE", state, None
        if verified_bundle(bundle) != (manifest, identity):
            return "INVALID_METADATA", state, None
        if not valid_current(state) or version in state.versions:
            return "PUBLICATION_UNKNOWN", state, None
        if state.current != prior_snapshot:
            return "PREVIOUS_PUBLICATION_CHANGED", state, None
        if gate == "GB-T13.G3" and not verified_mvp_publication(state, manifest):
            return "PREREQUISITE_UNAVAILABLE", state, None

    receipt = receipt_for(verified_approval)
    publication = Publication(identity, bundle, verified_approval, receipt, identity["revision"],
                              receipt["tagRef"])
    proof = immutable_json({"approval": verified_approval, "nativeDecision": json.loads(native_snapshot)})
    committed = deepcopy(State(
        identity, {**state.versions, version: publication},
        {**state.committed_authorizations, version: proof},
        state.designated_mvp,
        (*state.reservation_proof_digests, (version, digest(proof))),
    ))
    if interruption == "after":
        return "PUBLICATION_UNKNOWN", committed, None
    readback = verified_receipt(committed, identity)
    if readback is None:
        return "PUBLICATION_UNKNOWN", committed, None
    return "PUBLISHED", committed, readback


class ReleaseContractScenarios(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"),
                                  object_pairs_hook=strict_object)
        self.approvals = []
        self.native_decisions = {}
        self.prior_bundle, self.prior_identity, self.prior_approval = self.stage(
            version=self.fixture["priorVersion"],
        )
        outcome, self.prior, _ = self.publish(
            self.prior_bundle, self.prior_identity, self.prior_approval,
            State(None, {}),
        )
        self.assertEqual(outcome, "PUBLISHED")
        self.prior = replace(self.prior, designated_mvp=self.mvp_reference(
            self.prior_identity, self.prior_approval,
        ))

    @staticmethod
    def mvp_reference(identity, approval):
        return {"identity": deepcopy(identity), "releaseRef": receipt_for(approval)["releaseRef"]}

    def stage(self, *, version=None, scenario=None, notes=None):
        scenario = scenario or {}
        manifest = deepcopy(self.fixture["manifest"])
        files = {path: content.encode("utf-8") for path, content in self.fixture["files"].items()}
        if version is not None:
            manifest["version"] = version
        manifest.update(scenario.get("candidatePatch", {}))
        if "recordPatch" in scenario:
            manifest["evidence"][0].update(scenario["recordPatch"])
        if manifest["gate"] == "GB-T13.G3" and scenario.get("includeMvp", True):
            manifest["mvpPublication"] = scenario.get("mvpReference", {
                "identity": {**self.prior_identity, **scenario.get("mvpIdentityPatch", {})},
                "releaseRef": receipt_for(self.prior_approval)["releaseRef"],
            })
        provenance = {
            "schemaVersion": SCHEMA_VERSION, "sourceRevision": manifest["revision"],
            "inputs": [{"path": "repro/input.lock", "sha256": digest(files["repro/input.lock"])}],
            "recipe": {"path": "repro/build.txt", "sha256": digest(files["repro/build.txt"])},
            "checksumIndex": INDEX_PATH,
        }
        provenance.update(scenario.get("provenancePatch", {}))
        files[self.fixture["manifest"]["provenanceRef"]] = json.dumps(provenance).encode("utf-8")
        files.update({path: content.encode("utf-8") for path, content in scenario.get("filePatch", {}).items()})
        index = checksum_index(files)
        manifest.setdefault("artifactSha256", digest(index))
        notes_identity = {**manifest, **scenario.get("notesIdentityPatch", {})}
        notes = (notes_header(notes_identity) + (notes or self.fixture["notes"])).encode("utf-8")
        manifest.setdefault("notesSha256", digest(notes))
        manifest_bytes = json.dumps(manifest, sort_keys=True).encode("utf-8")
        bundle = Bundle(files, index, manifest_bytes, self.fixture["manifest"]["notesRef"], notes)
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
        gate = manifest["gate"]
        self.native_decisions[identity["manifestSha256"]] = {
            "identity": deepcopy(identity), "gate": gate, "decision": "accepted",
            "authority": NATIVE_AUTHORITY,
            "decisionRef": f'synthetic/native/{identity["manifestSha256"]}.json',
            "evidenceRefs": self.fixture["nativeEvidenceRefs"].get(gate, []),
            "mvpPublication": self.prior.designated_mvp if gate == "GB-T13.G3" else None,
        }
        return bundle, identity, approval

    def publish(self, bundle, identity, approval, state, *, expected_matches=True,
                native_ready=True, **kwargs):
        return attempt(
            bundle, identity, approval, state, state.current if expected_matches else None,
            authoritative_approvals=self.approvals,
            authoritative_native_decisions=self.native_decisions if native_ready else {}, **kwargs,
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

    def test_reserved_versions_reject_alterations_and_allow_exact_retries(self):
        bundle, current, approval, state = self.commit_candidate()
        for retry in ((bundle, current, approval),
                      (self.prior_bundle, self.prior_identity, self.prior_approval)):
            version = retry[1]["version"]
            changes = ({"notes": "Different notes\n"},
                       {"scenario": {"recordPatch": {"environment": "different evidence"}}})
            attempts = [(retry, "ALREADY_PUBLISHED", receipt_for(retry[2]))]
            for change in changes:
                changed = self.stage(version=version, **change)
                self.assertEqual(changed[1]["artifactSha256"], current["artifactSha256"])
                attempts.append((changed, "VERSION_CONFLICT", None))
            for staged, outcome, receipt in attempts:
                for expected_matches in (True, False):
                    with self.subTest(version=version, outcome=outcome, cas=expected_matches):
                        before = deepcopy(state)
                        result = self.publish(*staged, state, expected_matches=expected_matches)
                        self.assertEqual(result, (outcome, before, receipt))
                        self.assertIs(result[1], state)

    def test_changed_candidate_fails_original_approval_and_readback(self):
        bundle, identity, approval, state = self.commit_candidate()
        version = identity["version"]
        publication = state.versions[version]
        changes = ({"notes": "Different notes\n"},
                   {"scenario": {"recordPatch": {"environment": "different evidence"}}},
                   {"scenario": {"filePatch": {"dist/client.js": "changed bytes"}}})
        for change in changes:
            with self.subTest(change=change):
                revised_bundle, revised_identity, _ = self.stage(**change)
                self.assertEqual(revised_identity["revision"], identity["revision"])
                self.assertEqual(revised_bundle.index == bundle.index, change != changes[-1])
                self.assertEqual(self.publish(revised_bundle, revised_identity, approval, self.prior),
                                 ("PREREQUISITE_UNAVAILABLE", self.prior, None))
                history = {**state.versions, version: replace(publication, bundle=revised_bundle)}
                self.assertEqual(reconcile(replace(state, versions=history), identity,
                                           self.prior_identity),
                                 ("PUBLICATION_UNKNOWN", None))

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
                    reconcile(corrupted, identity, self.prior_identity),
                    ("PUBLICATION_UNKNOWN", None),
                )

    def test_checksum_index_and_exact_metadata(self):
        bundle, identity, approval = self.stage()
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
        for path in ("dist", "manifest.json/extra"):
            staged = self.stage(scenario={"filePatch": {path: "path collision"}})
            self.assertEqual(self.publish(*staged, self.prior),
                             ("INVALID_METADATA", self.prior, None))

    def test_precommit_retry_and_postcommit_reconciliation(self):
        bundle, identity, approval = self.stage()
        early = self.publish(bundle, identity, approval, self.prior, interruption="before")
        self.assertEqual(early, ("PUBLICATION_INTERRUPTED", self.prior, None))
        self.assertEqual(reconcile(early[1], identity, self.prior_identity),
                         ("RETRY_CONDITIONALLY", None))
        outcome, committed, receipt = self.publish(
            bundle, identity, approval, early[1], interruption="after",
        )
        self.assertEqual((outcome, receipt), ("PUBLICATION_UNKNOWN", None))
        self.assertEqual(reconcile(None, identity, self.prior_identity),
                         ("PUBLICATION_UNKNOWN", None))
        self.assertEqual(reconcile(committed, identity, self.prior_identity),
                         ("ALREADY_PUBLISHED", receipt_for(approval)))

        newer_bundle, newer_identity, newer_approval = self.stage(version="0.1.0-mvp.12")
        outcome, newer, _ = self.publish(newer_bundle, newer_identity, newer_approval, committed)
        self.assertEqual(outcome, "PUBLISHED")
        self.assertEqual(reconcile(newer, identity, self.prior_identity),
                         ("ALREADY_PUBLISHED", receipt_for(approval)))
        self.assertEqual(newer.current, newer_identity)

        _, competing, _ = self.publish(newer_bundle, newer_identity, newer_approval, self.prior)
        self.assertEqual(reconcile(competing, identity, self.prior_identity),
                         ("PREVIOUS_PUBLICATION_CHANGED", None))

    def test_inconsistent_current_blocks_mutation_and_reconciliation(self):
        bundle, identity, approval, published = self.commit_candidate()
        for state in (None, replace(self.prior, current=None), replace(self.prior, current={}),
                      replace(self.prior, current=identity),
                      replace(published, current=self.prior_identity)):
            with self.subTest(state=state):
                self.assertEqual(attempt(
                    bundle, identity, approval, state, None,
                    authoritative_approvals=self.approvals,
                    authoritative_native_decisions=self.native_decisions,
                ), ("PUBLICATION_UNKNOWN", state, None))
                self.assertEqual(reconcile(state, identity, None),
                                 ("PUBLICATION_UNKNOWN", None))

    def test_reapproved_mismatches_in_authoritative_publication(self):
        _, _, _, state = self.commit_candidate()
        for patch in (
            {"candidatePatch": {"notesRef": "synthetic/other.md"}},
            {"notesIdentityPatch": {"revision": self.fixture["otherRevision"]}},
            {"notesIdentityPatch": {"artifactSha256": "b" * 64}},
            {"candidatePatch": {"provenanceRef": "synthetic/other.json"}},
            {"provenancePatch": {"sourceRevision": self.fixture["otherRevision"]}},
            {"filePatch": {"repro/build.txt": "different recipe"}},
        ):
            with self.subTest(patch=patch):
                bundle, identity, approval = self.stage(scenario=patch)
                receipt = receipt_for(approval)
                version = identity["version"]
                observed = replace(state.versions[version], bundle=bundle, identity=identity,
                                   approval=approval, receipt=receipt)
                history = {**state.versions, version: observed}
                self.assertEqual(reconcile(replace(state, current=identity, versions=history), identity, None),
                                 ("PUBLICATION_UNKNOWN", None))

    def test_live_approval_fence_preserves_historical_commit_proof(self):
        bundle, identity, approval = self.stage()
        digest_key = identity["manifestSha256"]
        replacement = {
            digest_key: {**self.native_decisions[digest_key],
                         "decisionRef": "synthetic/native/replacement.json"},
        }
        for commit_state in (([approval], {}), ([], self.native_decisions), ([approval], replacement)):
            with self.subTest(commit_state=commit_state):
                self.assertEqual(self.publish(
                    bundle, identity, approval, self.prior,
                    authorization_at_commit=lambda: commit_state,
                ), ("PREREQUISITE_UNAVAILABLE", self.prior, None))
        _, committed, _ = self.publish(bundle, identity, approval, self.prior, interruption="after")
        self.approvals.clear()
        self.native_decisions.clear()
        self.assertEqual(reconcile(committed, identity, self.prior_identity),
                         ("ALREADY_PUBLISHED", receipt_for(approval)))
        later = self.stage(version="0.1.0-mvp.12")
        result, current, _ = self.publish(*later, committed)
        self.assertEqual(result, "PUBLISHED")
        self.assertEqual(reconcile(current, identity, self.prior_identity),
                         ("ALREADY_PUBLISHED", receipt_for(approval)))
        published = current.versions[identity["version"]]
        original_proof = current.committed_authorizations[identity["version"]]
        proof = json.loads(original_proof)
        self.assertEqual(proof["nativeDecision"]["decisionRef"],
                         f"synthetic/native/{digest_key}.json")
        proof["nativeDecision"]["decisionRef"] = "synthetic/native/replacement.json"
        corrupt_proof = {**current.committed_authorizations, identity["version"]: json.dumps(proof).encode()}
        self.assertEqual(reconcile(replace(current, committed_authorizations=corrupt_proof),
                                   identity, self.prior_identity),
                         ("PUBLICATION_UNKNOWN", None))
        published.approval["decisionRef"] = "synthetic/changed-decision.json"
        published.receipt["decisionRef"] = published.approval["decisionRef"]
        self.assertEqual(current.committed_authorizations[identity["version"]], original_proof)
        self.assertEqual(reconcile(current, identity, self.prior_identity),
                         ("PUBLICATION_UNKNOWN", None))

    def test_commit_rejects_replaced_approval_and_mutated_stage(self):
        for change, expected in (("approval", "PREREQUISITE_UNAVAILABLE"),
                                 ("payload", "INVALID_METADATA")):
            with self.subTest(change=change):
                bundle, identity, approval = self.stage()

                def change_commit_inputs():
                    if change == "approval":
                        approval["decisionRef"] = "synthetic/decision/replacement.json"
                        return [deepcopy(approval)], self.native_decisions
                    bundle.files["dist/client.js"] = b"changed after verification"
                    return self.approvals, self.native_decisions

                self.assertEqual(self.publish(
                    bundle, identity, approval, self.prior,
                    authorization_at_commit=change_commit_inputs,
                ), (expected, self.prior, None))
                self.assertNotIn(identity["version"], self.prior.versions)

    def test_public_receipts_are_detached_from_committed_state(self):
        bundle, identity, approval = self.stage()
        outcome, committed, receipt = self.publish(bundle, identity, approval, self.prior)
        self.assertEqual(outcome, "PUBLISHED")
        receipt["identity"]["revision"] = self.fixture["otherRevision"]
        outcome, retry = reconcile(committed, identity, self.prior_identity)
        self.assertEqual((outcome, retry), ("ALREADY_PUBLISHED", receipt_for(approval)))
        retry["identity"]["revision"] = self.fixture["otherRevision"]
        self.assertEqual(reconcile(committed, identity, self.prior_identity),
                         ("ALREADY_PUBLISHED", receipt_for(approval)))

    def test_native_registry_rejects_unverified_evidence_reference(self):
        bundle, identity, approval = self.stage(scenario={
            "recordPatch": {"ref": "synthetic/no-such-authoritative-record.json"},
        })
        self.assertEqual(self.publish(bundle, identity, approval, self.prior),
                         ("PREREQUISITE_UNAVAILABLE", self.prior, None))

    def test_stable_requires_verified_historical_mvp_receipt(self):
        scenario = next(row for row in self.fixture["scenarios"] if row["id"] == "stable-publication")
        _, unrelated_identity, unrelated_approval, before_stable = self.commit_candidate()
        unrelated_mvp = self.mvp_reference(unrelated_identity, unrelated_approval)
        stable = self.stage(scenario=scenario)
        wrong_stable = self.stage(scenario={**scenario, "mvpReference": unrelated_mvp})
        self.assertEqual(self.publish(*wrong_stable, before_stable),
                         ("PREREQUISITE_UNAVAILABLE", before_stable, None))
        outcome, current, _ = self.publish(*stable, before_stable)
        self.assertEqual(outcome, "PUBLISHED")
        later_scenario = {**scenario, "candidatePatch": {"gate": "GB-T13.G3", "version": "1.0.1"}}
        later = self.stage(scenario=later_scenario)
        self.assertEqual(self.publish(*later, current)[0], "PUBLISHED")

        mvp_version = self.prior_identity["version"]
        mvp = current.versions[mvp_version]
        corrupted = replace(current, versions={**current.versions, mvp_version: replace(mvp, receipt={})})
        self.assertEqual(self.publish(*later, corrupted),
                         ("PREREQUISITE_UNAVAILABLE", corrupted, None))
        for change in ({"includeMvp": False}, {"mvpIdentityPatch": {"manifestSha256": "a" * 64}},
                       {"mvpReference": unrelated_mvp}):
            with self.subTest(change=change):
                wrong = self.stage(scenario={**later_scenario, **change})
                self.assertEqual(self.publish(*wrong, current),
                                 ("PREREQUISITE_UNAVAILABLE", current, None))

        def withdraw_mvp_evidence():
            current.versions[mvp_version] = replace(mvp, receipt={})
            return self.approvals, self.native_decisions

        self.assertEqual(self.publish(*later, current, authorization_at_commit=withdraw_mvp_evidence),
                         ("PREREQUISITE_UNAVAILABLE", current, None))
        self.assertEqual(current.current, stable[1])
        self.assertNotIn(later[1]["version"], current.versions)

    def test_canonical_release_reference_and_version_bound(self):
        record = self.fixture["manifest"]["evidence"][0]
        link = f'{REPOSITORY}/releases/tag/v{self.prior_identity["version"]}'
        for suffix in ("", "+build.2", "?raw=1", "#notes", "%2Fextra", "/extra"):
            with self.subTest(suffix=suffix):
                self.assertEqual(bool(valid_record({**record, "ref": link + suffix})),
                                 suffix in ("", "+build.2"))
        longest = "0.1.0-" + "x" * (MAX_VERSION - len("0.1.0-"))
        self.assertTrue(safe_ref(f"{REPOSITORY}/releases/tag/v{longest}"))
        self.assertFalse(safe_ref(f"{REPOSITORY}/releases/tag/v{longest}x"))

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
