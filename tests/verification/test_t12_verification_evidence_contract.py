"""Offline conformance controls for the proposed T12 contract.

These validators are test oracles, not a product decoder or a release gate.
The authored observations simulate independent instrumentation.
"""

import copy
import hashlib
import json
import re
import unittest
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from pathlib import Path

import test_t13_release_contract as t13


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "docs/specifications/fixtures"
TOKEN = r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}"
CANDIDATE = "1" * 40
DATE = "2026-11-17T00:00:00Z"
EXTERNAL = {
    "discord-win", "discord-mac", "discord-web-chromium", "discord-web-firefox",
    "discord-ios", "discord-android", "discord-previews", "vps-network",
    "vps-load", "vps-recovery",
}
CLASS_BY_ROW = {
    "offline": "fixture",
    "local": "local_integration",
    "hosted": "hosted_ci",
    "review": "independent_review",
    "merged": "post_merge",
    **{row: "real_discord" if row.startswith("discord-") else "real_godaddy"
       for row in EXTERNAL},
}
STATES = {"completed", "invalid_configuration", "prerequisite_unavailable", "interrupted"}
CLEANUP = {"verified", "untouched", "pending", "failed"}
RESULTS = {"pass", "fail", "blocked"}
METADATA = ("candidateSha nativeIssue scenarioIds executedAt method environment scope "
            "artifactVersions verifierRef artifactRef findingDispositions limitations")
SECURITY_INPUTS = {
    "threat-model", "authorization-negative", "dependency-license-lockfile",
    "secret-static-triage", "upload-import", "independent-security-review",
}


def require(condition, code="INVALID_RECORD"):
    if not condition:
        raise ValueError(code)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                      parse_constant=invalid_constant)


def invalid_constant(_):
    raise ValueError("INVALID_RECORD")


def decode_json(data, limit):
    require(type(data) is bytes and 0 < len(data) <= limit)
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique_object,
                          parse_constant=invalid_constant, parse_float=invalid_constant)
    except (UnicodeError, RecursionError, ValueError) as error:
        raise ValueError("INVALID_RECORD") from error


def unique_object(pairs):
    record = dict(pairs)
    require(len(pairs) == len(record))
    return record


def closed(record, keys):
    require(type(record) is dict and record.keys() == set(keys.split()))


def token(value):
    require(type(value) is str and re.fullmatch(TOKEN, value))


def unique_array(values, key=None, minimum=0, maximum=32):
    require(type(values) is list and minimum <= len(values) <= maximum)
    keys = [value if key is None else value[key] for value in values]
    require(len(set(keys)) == len(keys))


def count(value):
    require(type(value) is int and 0 <= value <= 2_147_483_647)


def assess_fixture(claim, observation, scenario):
    closed(claim, "id scenario state cleanup expected result")
    closed(observation, "run signalSource values")
    require(claim["id"] == observation["run"] and claim["scenario"] == scenario["id"])
    require(claim["state"] in STATES and claim["cleanup"] in CLEANUP)
    require(claim["result"] in RESULTS)
    require(observation["signalSource"].startswith("synthetic-"))
    require(type(claim["expected"]) is list)
    closed(observation["values"], " ".join(scenario["signals"]))
    actual = [observation["values"][signal] for signal in scenario["signals"]]
    for value in actual + claim["expected"]:
        count(value)
    require(len(claim["expected"]) == len(actual))
    if claim["expected"] != actual:
        return "fail"
    if scenario["id"] == "E07" and observation["values"]["integratedLossStop"]:
        return "fail"
    if scenario["id"] == "E08":
        if observation["values"]["verifiedFailures"]:
            return "fail"
        if any(actual):
            return "blocked"
    if claim["state"] != "completed" or claim["cleanup"] not in {"verified", "untouched"}:
        return "blocked"
    return "pass"


def encode(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_depth(value, depth=1):
    require(depth <= 6)
    if type(value) is dict:
        for key, child in value.items():
            token(key)
            check_depth(child, depth + 1)
    elif type(value) is list:
        require(len(value) <= 32)
        for child in value:
            check_depth(child, depth + 1)
    elif type(value) is int:
        require(-2_147_483_648 <= value <= 2_147_483_647)
    else:
        require(type(value) is str and len(value) <= 240 and value.isascii())


def validate_version(record):
    count(record.get("version"))
    require(record["version"] > 0)
    require(record["version"] == 1, "UNSUPPORTED_RECORD_VERSION")


def hex_value(value, width):
    require(type(value) is str and re.fullmatch(f"[0-9a-f]{{{width}}}", value))


def validate_receipt(data):
    record = decode_json(data, 16_384)
    check_depth(record)
    require(type(record) is dict)
    validate_version(record)
    closed(record, "version requirementId gateRow environmentId runId executionState cleanup artifactSha256 evidence")
    for key in ("requirementId", "gateRow", "environmentId", "runId", "executionState", "cleanup"):
        token(record[key])
    require(record["gateRow"] in CLASS_BY_ROW)
    require(record["executionState"] in STATES and record["cleanup"] in CLEANUP)
    hex_value(record["artifactSha256"], 64)
    evidence = record["evidence"]
    require(type(evidence) is dict)
    validate_version(evidence)
    closed(evidence, "version candidateSha nativeIssue scenarioIds method executedAt environment "
                     "artifactVersions verifierRef scope evidenceClass result limitations "
                     "artifactRef findingDispositions")
    for key in ("evidenceClass", "result"):
        token(evidence[key])
    require(evidence["evidenceClass"] in CLASS_BY_ROW.values() and evidence["result"] in RESULTS)
    validate_metadata({key: evidence[key] for key in METADATA.split()})
    require(record["environmentId"] == evidence["environment"])
    return record


def validate_metadata(evidence):
    closed(evidence, METADATA)
    for key in ("method", "environment", "verifierRef", "scope", "artifactRef"):
        token(evidence[key])
    hex_value(evidence["candidateSha"], 40)
    count(evidence["nativeIssue"])
    require(evidence["nativeIssue"] > 0 and type(evidence["scenarioIds"]) is list)
    for identifier in evidence["scenarioIds"]:
        token(identifier)
        require(identifier in {f"E{index:02}" for index in range(1, 9)})
    unique_array(evidence["scenarioIds"], minimum=1)
    instant(evidence["executedAt"])
    require(type(evidence["limitations"]) is str)
    require(re.fullmatch(r"[ -~]{1,240}", evidence["limitations"]))
    for field, keys, identity, minimum in (
        ("artifactVersions", "artifactRef version", "artifactRef", 1),
        ("findingDispositions", "findingRef dispositionRef", "findingRef", 0),
    ):
        require(type(evidence[field]) is list)
        for item in evidence[field]:
            closed(item, keys)
            for value in item.values():
                token(value)
        unique_array(evidence[field], identity, minimum)


def instant(value):
    require(type(value) is str)
    require(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value))
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("INVALID_RECORD") from error


class Outcome(Enum):
    VERIFIED_PASS = "pass"
    VERIFIED_FAIL = "fail"
    INELIGIBLE = "ineligible"


@dataclass(frozen=True)
class Qualification:
    key: tuple
    candidate: str
    scope: str
    checked_at: str
    outcome: Outcome
    receipt_sha256: str


@dataclass(frozen=True)
class AuthorityRegistry:
    # Independently supplied policy selects an issuer for each purpose and grant.
    issuers: dict
    grants: dict


def current_grant(registry, ref, purpose, subject, current, since=None):
    if type(registry) is not AuthorityRegistry:
        return False
    issuer = registry.issuers.get((purpose, ref))
    grant = registry.grants.get(ref)
    if issuer is None or grant is None:
        return False
    closed(grant, "subject authorityRef issuedAt expiresAt decision")
    token(grant["authorityRef"])
    token(grant["decision"])
    require(grant["decision"] in {"approved", "withdrawn"})
    return (grant["authorityRef"] == issuer and encode(grant["subject"]) == encode(subject)
            and grant["decision"] == "approved"
            and instant(grant["issuedAt"]) <= (since or current) <= current < instant(grant["expiresAt"]))


def qualifies(data, key, registry, artifact, observation, inventory, trusted_time, authorities):
    record = validate_receipt(data)
    require(type(key) is tuple and len(key) == 2)
    requirement, row = key
    token(requirement)
    token(row)
    require(row in CLASS_BY_ROW)
    require(all(item is not None for item in (
        registry, artifact, observation, inventory, trusted_time, authorities)), "DEPENDENCY_UNAVAILABLE")
    require(type(registry) is dict and key in registry and type(authorities) is AuthorityRegistry)
    approval = registry[key]
    closed(approval, "metadata runId artifactSha256 resultObserver cleanupObserver authorityRef resourceful "
                     "configurationRef supportedConfiguration prerequisiteRefs freshUntil projection")
    validate_metadata(approval["metadata"])
    hex_value(approval["artifactSha256"], 64)
    for field in ("runId", "resultObserver", "cleanupObserver", "authorityRef", "configurationRef"):
        token(approval[field])
    require(approval["resultObserver"] != approval["cleanupObserver"])
    require(approval["metadata"]["verifierRef"] not in
            {approval["resultObserver"], approval["cleanupObserver"]})
    require(type(approval["resourceful"]) is bool and type(approval["supportedConfiguration"]) is bool)
    require(type(approval["prerequisiteRefs"]) is list)
    for ref in approval["prerequisiteRefs"]:
        token(ref)
    unique_array(approval["prerequisiteRefs"], minimum=1)
    require(type(approval["projection"]) is list and len(approval["projection"]) == 2)
    token(approval["projection"][0])
    require(type(approval["projection"][1]) is str and t13.safe_ref(approval["projection"][1]))
    closed(observation, "requirementId gateRow runId observerRef candidateSha environmentId configurationRef artifactSha256 executionState result")
    closed(inventory, "requirementId gateRow runId observerRef candidateSha environmentId configurationRef artifactSha256 cleanup ownedCreated "
                      "ownedRemaining foreignSentinel")
    for observed in (observation, inventory):
        hex_value(observed["candidateSha"], 40)
        hex_value(observed["artifactSha256"], 64)
        for field in ("requirementId", "gateRow", "runId", "observerRef", "environmentId", "configurationRef"):
            token(observed[field])
    for observed, field, allowed in (
        (observation, "executionState", STATES), (observation, "result", RESULTS),
        (inventory, "cleanup", CLEANUP),
    ):
        token(observed[field])
        require(observed[field] in allowed)
    for value in (inventory["ownedCreated"], inventory["ownedRemaining"], inventory["foreignSentinel"]):
        count(value)
    require(type(artifact) is bytes)
    evidence = record["evidence"]
    current = instant(trusted_time)
    executed = instant(evidence["executedAt"])
    binding = {"requirementId": record["requirementId"], "gateRow": record["gateRow"],
               "runId": record["runId"], "candidateSha": evidence["candidateSha"],
               "environmentId": record["environmentId"], "configurationRef": approval["configurationRef"],
               "artifactSha256": record["artifactSha256"]}
    cleanup = "verified" if approval["resourceful"] else "untouched"
    refs = [approval["authorityRef"], *approval["prerequisiteRefs"]]
    require(all(ref in authorities.grants for ref in refs), "DEPENDENCY_UNAVAILABLE")
    subject = [*key, digest(encode(approval))]
    outcome = Outcome.INELIGIBLE
    if (
        (record["requirementId"], record["gateRow"]) == key
        and evidence["evidenceClass"] == CLASS_BY_ROW[row]
        and encode({key: evidence[key] for key in METADATA.split()}) == encode(approval["metadata"])
        and approval["supportedConfiguration"]
        and current < instant(approval["freshUntil"])
        and current_grant(authorities, approval["authorityRef"], "qualification", subject, current, executed)
        and all(current_grant(authorities, ref, "prerequisite", [ref, *subject], current, executed)
                for ref in approval["prerequisiteRefs"])
        and record["runId"] == approval["runId"]
        and record["artifactSha256"] == approval["artifactSha256"] == digest(artifact)
        and all(observation[key] == inventory[key] == value for key, value in binding.items())
        and observation["observerRef"] == approval["resultObserver"]
        and inventory["observerRef"] == approval["cleanupObserver"]
        and record["executionState"] == observation["executionState"] == "completed"
        and record["cleanup"] == inventory["cleanup"]
        and evidence["result"] == observation["result"]
    ):
        if evidence["result"] == "fail":
            outcome = Outcome.VERIFIED_FAIL
        elif (evidence["result"] == "pass" and inventory["cleanup"] == cleanup
              and inventory["ownedRemaining"] == 0 and inventory["foreignSentinel"] == 1
              and (approval["resourceful"] or inventory["ownedCreated"] == 0)):
            outcome = Outcome.VERIFIED_PASS
    return Qualification(key, evidence["candidateSha"], evidence["scope"], trusted_time, outcome, digest(data))


def disposition_resolved(finding, candidate, scope, current, records, artifacts, authorities):
    finding_ref, severity, receipt_sha, ref = finding
    record = records.get(ref)
    if record is None:
        return False
    closed(record, "findingRef candidateSha scope severity receiptSha256 approverRef authorityRef "
                   "evidenceRef evidenceSha256 exceptionRef exceptionPermissionRef")
    binding = {"findingRef": finding_ref, "candidateSha": candidate, "scope": scope,
               "severity": severity, "receiptSha256": receipt_sha, "dispositionRef": ref,
               "approverRef": record["approverRef"]}
    for field in ("approverRef", "authorityRef", "evidenceRef"):
        token(record[field])
    raw = artifacts.get(record["evidenceRef"])
    if not (type(raw) is bytes and digest(raw) == record["evidenceSha256"]
            and all(record[name] == binding[name] for name in binding if name != "dispositionRef")
            and record["approverRef"] == authorities.issuers.get(("disposition", record["authorityRef"]))
            and current_grant(authorities, record["authorityRef"], "disposition",
                              [ref, digest(encode(record))], current)):
        return False
    observed = decode_json(raw, 4096)
    if record["exceptionRef"] == "":
        closed(observed, "binding state remediationRef remediationSha256")
        token(observed["remediationRef"])
        remediation = artifacts.get(observed["remediationRef"])
        if (observed["binding"] != binding or observed["state"] != "closed"
                or record["exceptionPermissionRef"] != "" or type(remediation) is not bytes
                or digest(remediation) != observed["remediationSha256"]):
            return False
        verified = decode_json(remediation, 4096)
        closed(verified, "binding result checkRef authorityRef")
        token(verified["checkRef"])
        token(verified["authorityRef"])
        return (
            verified["binding"] == binding and verified["result"] == "verified-remediated"
            and authorities.issuers.get(("remediation-review", verified["authorityRef"])) != record["approverRef"]
            and current_grant(authorities, verified["authorityRef"], "remediation-review",
                              [observed["remediationRef"], digest(remediation)], current)
        )

    for name in ("exceptionRef", "exceptionPermissionRef"):
        token(record[name])
    exception_bytes = artifacts.get(record["exceptionRef"])
    if type(exception_bytes) is not bytes:
        return False
    exception = decode_json(exception_bytes, 4096)
    check_depth(exception)
    require(type(exception) is dict)
    validate_version(exception)
    closed(exception, "version scope severity approverRef rationale controls expiresAt closureCriteria")
    for field in ("scope", "severity", "approverRef", "closureCriteria"):
        token(exception[field])
    require(type(exception["rationale"]) is str and re.fullmatch(r"[ -~]{1,240}", exception["rationale"]))
    require(type(exception["controls"]) is list)
    for control in exception["controls"]:
        token(control)
    unique_array(exception["controls"], minimum=1)
    closed(observed, "binding state controls closureCriteria exceptionSha256")
    permission_ref = record["exceptionPermissionRef"]
    return (
        all(exception[name] == binding[name] for name in ("scope", "severity", "approverRef"))
        and current < instant(exception["expiresAt"])
        and observed["binding"] == binding
        and observed["state"] == "exception-verified"
        and observed["controls"] == exception["controls"]
        and observed["closureCriteria"] == exception["closureCriteria"]
        and observed["exceptionSha256"] == digest(exception_bytes)
        and authorities.issuers.get(("exception-policy", permission_ref)) != record["approverRef"]
        and current_grant(authorities, permission_ref, "exception-policy",
                          [binding, digest(exception_bytes)], current)
    )


def passing(*args):
    return qualifies(*args).outcome is Outcome.VERIFIED_PASS


@dataclass(frozen=True)
class EvidenceSources:
    registry: dict
    receipt_refs: dict
    receipts: dict
    artifacts: dict
    observations: dict
    inventories: dict
    time: str
    authorities: AuthorityRegistry


def qualified_receipt(key, sources):
    ref = sources.receipt_refs.get(key)
    approval = sources.registry.get(key)
    raw = sources.receipts.get(ref)
    if raw is None or approval is None:
        return None, None
    require(type(approval) is dict and type(approval.get("metadata")) is dict)
    artifact_ref = approval["metadata"].get("artifactRef")
    token(artifact_ref)
    item = qualifies(raw, key, sources.registry, sources.artifacts.get(artifact_ref),
                     sources.observations.get(key), sources.inventories.get(key), sources.time, sources.authorities)
    return (item, validate_receipt(raw)) if approval["projection"][1] == ref else (None, None)


def findings_resolved(keys, receipts, candidate, scope, sources, findings, dispositions):
    if type(findings) is not dict:
        return False
    closed(findings, "authorityRef candidateSha scope receiptSha256s findings")
    current = instant(sources.time)
    require(type(findings["findings"]) is list)
    token(findings["authorityRef"])
    refs = {}
    for receipt_sha, record in receipts:
        for item in record["evidence"]["findingDispositions"]:
            identity = (receipt_sha, item["findingRef"])
            refs[identity] = item["dispositionRef"]
    expected = {}
    for item in findings["findings"]:
        closed(item, "findingRef severity receiptSha256 dispositionRef")
        for name in ("findingRef", "severity", "dispositionRef"):
            token(item[name])
        hex_value(item["receiptSha256"], 64)
        require(item["severity"] in {"critical", "high", "medium", "low", "informational"})
        identity = (item["receiptSha256"], item["findingRef"])
        require(identity not in expected)
        expected[identity] = item["dispositionRef"]
    return (
        findings["candidateSha"] == candidate and findings["scope"] == scope
        and findings["receiptSha256s"] == [receipt_sha for receipt_sha, _ in receipts]
        and refs == expected
        and current_grant(sources.authorities, findings["authorityRef"], "finding-inventory",
                          [sorted(keys), digest(encode(findings))], current)
        and all(disposition_resolved((item["findingRef"], item["severity"], item["receiptSha256"],
                                      item["dispositionRef"]), candidate, scope, current,
                                     dispositions, sources.artifacts, sources.authorities)
                for item in findings["findings"] if item["severity"] in {"critical", "high"})
    )


SECURITY_KEYS = {(name, "review" if name == "independent-security-review" else "hosted")
                 for name in SECURITY_INPUTS}


def matrix_outcome(required_keys, sources, candidate, scope, findings, dispositions):
    """Re-resolve every selected row from the current independent sources."""
    keys = required_keys | SECURITY_KEYS
    eligible, receipts = {}, []
    for key in sorted(keys):
        try:
            item, record = qualified_receipt(key, sources)
        except ValueError:
            continue
        if item is not None and item.candidate == candidate and item.scope == scope:
            eligible[key] = item.outcome
            receipts.append((item.receipt_sha256, record))
    if Outcome.VERIFIED_FAIL in eligible.values():
        return "fail"
    if not required_keys or any(eligible.get(key) is not Outcome.VERIFIED_PASS for key in keys):
        return "blocked"
    try:
        return "pass" if findings_resolved(keys, receipts, candidate, scope, sources, findings, dispositions) else "blocked"
    except ValueError:
        return "blocked"


T13_LEVELS = {
    "fixture": "synthetic", "local_integration": "integration", "hosted_ci": "integration",
    "independent_review": "independent-review", "real_discord": "real-discord",
    "real_godaddy": "real-godaddy",
}

T13_GATE_RECORDS = {
    "GB-T13.G1": {("discord-startup", "GB-T12.MVP1", "real-discord")},
    "GB-T13.G2": {("production-smoke", "GB-T13.G2", "real-godaddy"),
                 ("production-recovery", "GB-T13.G2", "real-godaddy")},
    "GB-T13.G3": {("production-smoke", "GB-T13.G2", "real-godaddy")},
}


def t13_projection(key, candidate, scope, sources, issue_map):
    try:
        qualification, record = qualified_receipt(key, sources)
    except ValueError:
        return None
    if (qualification is None or qualification.outcome is not Outcome.VERIFIED_PASS
            or qualification.candidate != candidate or qualification.scope != scope):
        return None
    evidence = record["evidence"]
    level = T13_LEVELS.get(evidence["evidenceClass"])
    issue = issue_map.get(evidence["nativeIssue"])
    if level is None or issue is None:
        return None
    identifier, ref = sources.registry[key]["projection"]
    entry = {"id": identifier, "issue": issue, "revision": evidence["candidateSha"],
             "date": evidence["executedAt"][:10], "environment": evidence["environment"],
             "level": level, "result": "pass", "ref": ref}
    return entry if t13.valid_record(entry) else None


def t13_handoff(bundle, sources, gate_registry, issue_map, findings, dispositions,
                approvals, native_decisions, historical):
    if type(sources) is not EvidenceSources or type(bundle) is not t13.Bundle:
        return "pending"
    if (verified := t13.verified_bundle(bundle)) is None:
        return "pending"
    manifest, identity = verified
    gate, candidate = manifest["gate"], identity["revision"]
    selected = gate_registry.get(gate)
    if selected is None:
        return "pending"
    try:
        closed(selected, "authorityRef candidateSha scope matrixKeys projectionKeys prerequisiteRefs")
        current = instant(sources.time)
        for name in ("matrixKeys", "projectionKeys"):
            keys = selected[name]
            require(type(keys) is list and all(type(key) in {tuple, list} and len(key) == 2 for key in keys))
            for requirement, row in keys:
                token(requirement)
                token(row)
                require(row in CLASS_BY_ROW)
            unique_array([tuple(key) for key in keys], minimum=1, maximum=128)
        require(type(selected["prerequisiteRefs"]) is list)
        for ref in selected["prerequisiteRefs"]:
            token(ref)
        unique_array(selected["prerequisiteRefs"], minimum=1)
        token(selected["scope"])
        token(selected["authorityRef"])
    except ValueError:
        return "pending"
    required = {tuple(key) for key in selected["matrixKeys"]}
    projected = [tuple(key) for key in selected["projectionKeys"]]
    scope = selected["scope"]
    matrix_subject = [gate, digest(encode(selected))]
    if (selected["candidateSha"] != candidate or not projected
            or not set(projected) <= required
            or not current_grant(sources.authorities, selected["authorityRef"], "gate-matrix", matrix_subject, current)
            or not all(current_grant(sources.authorities, ref, "gate-prerequisite", [ref, *matrix_subject], current)
                       for ref in selected["prerequisiteRefs"])
            or matrix_outcome(required, sources, candidate, scope, findings, dispositions) != "pass"):
        return "pending"
    evidence = [t13_projection(key, candidate, scope, sources, issue_map) for key in projected]
    if (any(row is None for row in evidence) or manifest["evidence"] != evidence
            or not T13_GATE_RECORDS[gate] <= {(row["id"], row["issue"], row["level"])
                                             for key, row in zip(projected, evidence) if key[0] == row["id"]}
            or len({row["ref"] for row in evidence}) != len(evidence)
            or (gate != "GB-T13.G2" and t13.release_gate(identity["version"]) != gate)):
        return "pending"
    bundle_ref = identity["manifestSha256"]
    approval = approvals.get(bundle_ref)
    decision = native_decisions.get(bundle_ref)
    if (not t13.valid_approval(approval, manifest, identity)
            or not t13.valid_native_decision(decision, manifest, identity)
            or not current_grant(sources.authorities, "t13-approval", "release-approval",
                                 [bundle_ref, digest(encode(approval))], current)
            or not current_grant(sources.authorities, "t13-native", "native-decision",
                                 [bundle_ref, digest(encode(decision)), manifest["provenanceRef"]], current)):
        return "pending"
    if gate == "GB-T13.G3" and (type(historical) is not t13.State
            or not t13.valid_current(historical)
            or not t13.verified_mvp_publication(historical, manifest)
            or (t13.release_gate(historical.current["version"]) == "GB-T13.G1"
                and identity["version"] != "1.0.0")
            or not current_grant(sources.authorities, "t13-mvp", "accepted-mvp",
                                 historical.designated_mvp, current)):
        return "pending"
    return "verified"


class VerificationEvidenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = read_json(FIXTURES / "GB-T12-S1-scenarios.json")
        cls.scenarios = {row["id"]: row for row in cls.fixture["scenarios"]}
        cls.claims = {row["id"]: row for row in cls.fixture["claims"]}
        cls.observations = {row["run"]: row for row in cls.fixture["observations"]}
        cls.reviewed = {
            "candidateSha": CANDIDATE, "nativeIssue": 393, "scenarioIds": ["E01"],
            "limitations": "Synthetic only.",
            "executedAt": DATE,
            "method": "offline-unit", "environment": "synthetic-v1", "scope": "test-only",
            "artifactVersions": [{"artifactRef": "corpus", "version": "v1"}],
            "verifierRef": "synthetic-verifier", "artifactRef": "synthetic-valid",
            "findingDispositions": [],
        }

    def receipt(self):
        artifact = encode(self.observations["valid"])
        record = {
            "version": 1, "requirementId": "harness", "gateRow": "offline", "environmentId": "synthetic-v1",
            "runId": "valid", "executionState": "completed", "cleanup": "verified",
            "artifactSha256": digest(artifact),
            "evidence": {
                **copy.deepcopy(self.reviewed), "version": 1,
                "evidenceClass": "fixture", "result": "pass", "limitations": "Synthetic only.",
            },
        }
        return record, artifact

    def test_scope_and_contract_references(self):
        closed(self.fixture, "version status scenarios claims operationControls observations handoffMatrix")
        self.assertEqual((self.fixture["version"], self.fixture["status"]), (1, "synthetic-only"))
        self.assertEqual(list(self.scenarios), [f"E{index:02}" for index in range(1, 9)])
        self.assertEqual(len(self.scenarios), len(self.fixture["scenarios"]))
        self.assertEqual(len(self.claims), len(self.fixture["claims"]))
        self.assertEqual(len(self.observations), len(self.fixture["observations"]))
        self.assertEqual(self.claims.keys(), self.observations.keys())
        self.assertEqual({claim["scenario"] for claim in self.claims.values()}, self.scenarios.keys())
        for scenario in self.scenarios.values():
            closed(scenario, "id verification t0 t9 signals")
            unique_array(scenario["signals"], minimum=1)
        for domain in ("T0", "T9"):
            upstream = read_json(FIXTURES / f"GB-{domain}-S1-scenarios.json")
            upstream_ids = {item["id"] for item in upstream["scenarios"]}
            traced = set()
            for scenario in self.scenarios.values():
                unique_array(scenario[domain.lower()])
                traced.update(scenario[domain.lower()])
            self.assertEqual(traced, upstream_ids)
        expected = {
            "E01": (393, set(), set()),
            "E02": (393, {"F12", "F13"}, set()),
            "E03": (393, set(), {"resource_profile"}),
            "E04": (403, {"F01", "F02", "F03", "F14"},
                    {"membership", "tenant_scope", "auth_transaction", "policy_matrix",
                     "bounded_content", "audit_integrity", "receipt_lookup", "malformed_command", "ingress"}),
            "E05": (407, {f"F{index:02}" for index in range(4, 10)} | {"F16", "F17"},
                    {"commit_order", "commit_dependencies", "durable_retry"}),
            "E06": (400, {f"F{index:02}" for index in range(23, 37)} | {"F15"},
                    {"release_order", "asset_export_release", "receipt_release_denial"}),
            "E07": (410, {"F10", "F11"} | {f"F{index:02}" for index in range(18, 23)},
                    {"receipt_history", "delete_restore"}),
            "E08": (417, set(), {"release_gate", "host_boundary", "internal_records"}),
        }
        self.assertEqual({key: (row["verification"], set(row["t0"]), set(row["t9"]))
                          for key, row in self.scenarios.items()}, expected)
        backlog = read_json(ROOT / "planning/guildboard-backlog.json")["items"]
        by_id = {item["id"]: item["github"]["number"] for item in backlog}
        native = {item["github"]["number"]: {by_id[key] for key in item["dependencies"]} for item in backlog}
        verification = {item["github"]["number"] for item in backlog
                        if item["id"].startswith("GB-T12.") and item["id"].endswith(".V1")}
        self.assertEqual(verification, {393, 396, 400, 403, 407, 410, 414, 417})
        self.assertEqual(native[418], verification | {389, 455})
        self.assertEqual(native[470], verification | {418, 455})
        self.assertEqual(native[457], {353, 378, 414, 417})
        self.assertEqual(native[471], {446, 456})
        self.assertEqual(native[473], {446, 472})

    def test_independent_synthetic_controls(self):
        for run, claim in self.claims.items():
            with self.subTest(run=run):
                scenario = self.scenarios[claim["scenario"]]
                observed = self.observations[run]
                self.assertEqual(assess_fixture(claim, observed, scenario), claim["result"])

    def test_e05_deduplicates_only_matching_scoped_identity_and_digest(self):
        for run, commands in self.fixture["operationControls"].items():
            committed = {}
            for command in commands:
                closed(command, "guild board author operationId payload")
                identity = tuple(command[name] for name in ("guild", "board", "author", "operationId"))
                payload_digest = digest(command["payload"].encode())
                self.assertEqual(committed.setdefault(identity, payload_digest), payload_digest)
            self.assertEqual(len(set(committed.values())), 1)
            observed = self.observations[run]["values"]
            self.assertEqual((observed["durableEffects"], observed["acceptedReceipts"]),
                             (len(committed), len(committed)))

    def test_side_effect_and_interruption_mutations_are_detected(self):
        for run, signal in [
            ("invalid", "binds"), ("unavailable", "adapterCalls"),
            ("interrupted", "ownedRemaining"), ("interrupted", "foreignSentinel"),
            ("denied", "durableEffects"), ("denied", "egressEvents"),
            ("denied", "foreignIdentifiers"), ("duplicate", "acceptedReceipts"),
            ("distinct-id-same-digest", "durableEffects"),
            ("ack-fenced", "protectedBytes"), ("handoff-before-revoke", "bytesAfterRevocation"),
            ("handoff-before-revoke", "handoffSequence"), ("restart", "missingAcknowledgedEffects"),
            ("restart", "lostAckDeliveries"),
            ("document-restore", "beyondCutReceipts"), ("document-restore", "oldLineageEffects"),
            ("disaster-recovery", "rpoExceeded"), ("disaster-recovery", "integratedLossStop"), ("matrix-valid", "unresolvedFindings"),
        ]:
            with self.subTest(run=run, signal=signal):
                claim = self.claims[run]
                observed = copy.deepcopy(self.observations[run])
                observed["values"][signal] += 1
                self.assertEqual(assess_fixture(claim, observed, self.scenarios[claim["scenario"]]),
                                 "fail")

    def qualification_inputs(self, requirement="harness", row="offline", scope="test-only",
                             result="pass", issue=393, finding_refs=None):
        record, artifact = self.receipt()
        record["requirementId"], record["gateRow"] = requirement, row
        record["evidence"].update(scope=scope, evidenceClass=CLASS_BY_ROW[row], result=result,
                                  nativeIssue=issue, artifactRef=f"{requirement}-{row}")
        if finding_refs is not None:
            record["evidence"]["findingDispositions"] = finding_refs
        binding = {"requirementId": requirement, "gateRow": row,
                   "runId": record["runId"], "candidateSha": CANDIDATE,
                   "environmentId": record["environmentId"], "configurationRef": "approved-configuration",
                   "artifactSha256": digest(artifact)}
        current = "2026-11-17T00:01:00Z"
        key = (requirement, row)
        approval = {
            "metadata": {name: record["evidence"][name] for name in METADATA.split()},
            "runId": record["runId"], "artifactSha256": digest(artifact),
            "resultObserver": "result-oracle", "cleanupObserver": "cleanup-oracle",
            "resourceful": True, "authorityRef": f"approval-{requirement}-{row}",
            "configurationRef": binding["configurationRef"], "supportedConfiguration": True,
            "prerequisiteRefs": [f"prerequisite-{requirement}-{row}"],
            "freshUntil": "2026-11-17T00:10:00Z",
            "projection": [requirement, f"synthetic/{requirement}-{row}.json"],
        }
        authorities = AuthorityRegistry({}, {})
        self.approve_row(authorities, key, approval)
        observation = {**binding, "observerRef": "result-oracle", "result": result,
                       "executionState": "completed"}
        inventory = {**binding, "observerRef": "cleanup-oracle", "cleanup": "verified",
                     "ownedCreated": 1, "ownedRemaining": 0, "foreignSentinel": 1}
        return record, key, {key: approval}, artifact, observation, inventory, current, authorities

    @staticmethod
    def grant(authorities, purpose, ref, subject, issuer="approved-owner-policy"):
        authorities.issuers[purpose, ref] = issuer
        authorities.grants[ref] = {"subject": subject, "authorityRef": issuer, "issuedAt": DATE,
                                   "expiresAt": "2026-11-17T01:00:00Z", "decision": "approved"}

    def approve_row(self, authorities, key, approval):
        subject = [*key, digest(encode(approval))]
        self.grant(authorities, "qualification", approval["authorityRef"], subject)
        for ref in approval["prerequisiteRefs"]:
            self.grant(authorities, "prerequisite", ref, [ref, *subject])

    def sources(self, keys, **overrides):
        sources = EvidenceSources({}, {}, {}, {}, {}, {}, "2026-11-17T00:01:00Z",
                                  AuthorityRegistry({}, {}))
        for key in keys | SECURITY_KEYS:
            record, _, registry, artifact, observed, inventory, _, authorities = self.qualification_inputs(
                *key, scope="release", **{"finding_refs": [], **overrides.get(key[0], {})})
            approval = registry[key]
            ref = approval["projection"][1]
            sources.registry[key] = approval
            sources.receipt_refs[key] = ref
            sources.receipts[ref] = encode(record)
            sources.artifacts[record["evidence"]["artifactRef"]] = artifact
            sources.observations[key] = observed
            sources.inventories[key] = inventory
            sources.authorities.issuers.update(authorities.issuers)
            sources.authorities.grants.update(authorities.grants)
        return sources

    def finding_inventory(self, keys, sources, findings=()):
        matrix_keys = sorted(keys | SECURITY_KEYS)
        inventory = {"authorityRef": "complete-findings", "candidateSha": CANDIDATE, "scope": "release",
                     "receiptSha256s": [qualified_receipt(key, sources)[0].receipt_sha256 for key in matrix_keys],
                     "findings": list(findings)}
        self.grant(sources.authorities, "finding-inventory", inventory["authorityRef"],
                   [matrix_keys, digest(encode(inventory))], "independent-security-inventory")
        return inventory

    def test_exact_environment_and_provenance_are_required(self):
        record, *inputs = self.qualification_inputs()
        self.assertTrue(passing(encode(record), *inputs))
        for field, value in [
            ("candidateSha", "2" * 40), ("nativeIssue", 400), ("scope", "different-scope"),
            ("executedAt", "2025-11-17T00:00:00Z"), ("verifierRef", "replacement"),
            ("scenarioIds", ["E02"]), ("result", "blocked"), ("artifactRef", "different-trace"),
        ]:
            with self.subTest(field=field):
                mutated = copy.deepcopy(record)
                mutated["evidence"][field] = value
                self.assertFalse(passing(encode(mutated), *inputs))
        changed_environment = copy.deepcopy(record)
        changed_environment["environmentId"] = changed_environment["evidence"]["environment"] = "other-build"
        self.assertFalse(passing(encode(changed_environment), *inputs))
        self.assertFalse(passing(encode({**record, "runId": "other-run"}), *inputs))
        self.assertFalse(passing(encode({**record, "gateRow": "discord-win"}), *inputs))
        _, row, registry, artifact, observation, inventory, current, authorities = self.qualification_inputs()
        self.assertFalse(passing(encode(record), row, registry, artifact + b" ", observation, inventory, current, authorities))
        with self.assertRaisesRegex(ValueError, "DEPENDENCY_UNAVAILABLE"):
            passing(encode(record), row, registry, None, observation, inventory, current, authorities)
        sparse_registry = copy.deepcopy(registry)
        sparse_registry[row]["metadata"] = {"environment": record["environmentId"]}
        with self.assertRaisesRegex(ValueError, "INVALID_RECORD"):
            passing(encode(record), row, sparse_registry, artifact, observation, inventory, current, authorities)

    def test_target_cleanup_and_observations_are_independently_bound(self):
        record, row, registry, artifact, observation, inventory, current, authorities = self.qualification_inputs()
        for field, values in [
            ("executionState", STATES - {"completed"}),
            ("cleanup", CLEANUP - {"verified"}),
        ]:
            for value in values:
                with self.subTest(field=field, value=value):
                    changed = {**record, field: value}
                    self.assertFalse(passing(encode(changed), row, registry, artifact, observation, inventory, current, authorities))
        untouched = {**record, "cleanup": "untouched"}
        self.assertFalse(passing(encode(untouched), row, registry, artifact, observation,
                                   {**inventory, "cleanup": "untouched"}, current, authorities))
        for field, value in [("runId", "other-run"), ("observerRef", "result-oracle"),
                             ("artifactSha256", "2" * 64), ("ownedRemaining", 1), ("foreignSentinel", 0)]:
            self.assertFalse(passing(encode(record), row, registry, artifact, observation,
                                       {**inventory, field: value}, current, authorities))
        for field, value in [("runId", "other-run"), ("observerRef", "cleanup-oracle"), ("result", "fail"),
                             ("executionState", "interrupted")]:
            self.assertFalse(passing(encode(record), row, registry, artifact,
                                       {**observation, field: value}, inventory, current, authorities))
        self.assertFalse(passing(encode(record), row, registry, artifact, observation, inventory,
                                   authorities.grants[registry[row]["authorityRef"]]["expiresAt"], authorities))
        registry[row]["resourceful"] = False
        self.approve_row(authorities, row, registry[row])
        self.assertFalse(passing(encode(untouched), row, registry, artifact, observation,
                                   {**inventory, "cleanup": "untouched"}, current, authorities))
        self.assertTrue(passing(encode(untouched), row, registry, artifact, observation,
                                  {**inventory, "cleanup": "untouched", "ownedCreated": 0}, current, authorities))
        authorities.grants[registry[row]["authorityRef"]]["decision"] = "withdrawn"
        self.assertFalse(passing(encode(untouched), row, registry, artifact, observation,
                                   {**inventory, "cleanup": "untouched", "ownedCreated": 0}, current, authorities))

    def test_release_gate_distinguishes_verified_failure_and_substitution(self):
        network, smoke = ("network", "vps-network"), ("smoke", "vps-network")
        keys = {network, smoke}
        sources = self.sources(keys)
        findings = self.finding_inventory(keys, sources)

        def outcome(current=sources):
            return matrix_outcome(keys, current, CANDIDATE, "release", findings, {})

        self.assertEqual(outcome(), "pass")
        self.assertEqual(outcome(replace(sources, receipt_refs={
            **sources.receipt_refs, smoke: sources.receipt_refs[network],
        })), "blocked")
        self.assertEqual(outcome(self.sources(keys, smoke={"result": "fail"})), "fail")
        for key in keys | SECURITY_KEYS:
            for field in ("receipts", "artifacts", "observations", "inventories"):
                changed = copy.deepcopy(sources)
                source = getattr(changed, field)
                lookup = {"receipts": sources.receipt_refs[key],
                          "artifacts": sources.registry[key]["metadata"]["artifactRef"]}
                source.pop(lookup.get(field, key))
                self.assertEqual(outcome(changed), "blocked")

    def test_release_disposition_requires_inventory_and_exact_evidence(self):
        key = ("harness", "offline")
        keys, scope = {key}, "release"
        finding_ref = {"findingRef": "f1", "dispositionRef": "d1"}
        sources = self.sources(keys, harness={"finding_refs": [finding_ref]})
        receipt_sha = qualified_receipt(key, sources)[0].receipt_sha256
        finding = {**finding_ref, "severity": "high", "receiptSha256": receipt_sha}
        findings = self.finding_inventory(keys, sources, [finding])
        exception = {"version": 1, "scope": scope, "severity": "high", "approverRef": "approver",
                     "rationale": "Reviewed temporary coverage.", "controls": ["mitigation"],
                     "expiresAt": "2026-11-17T01:00:00Z", "closureCriteria": "remediation-check"}
        binding = {**finding, "candidateSha": CANDIDATE, "scope": scope, "approverRef": "approver"}

        def outcome(closed=False, mutation=None, inventory=findings):
            current = copy.deepcopy(sources)
            remediation = encode({"binding": binding, "result": "verified-remediated",
                                  "checkRef": "independent-remediation-check", "authorityRef": "remediation-review"})
            self.grant(current.authorities, "remediation-review", "remediation-review",
                       ["remediation", digest(remediation)], "independent-reviewer")
            observed = {"binding": binding, "state": "closed", "remediationRef": "remediation",
                        "remediationSha256": digest(remediation)} if closed else {
                "binding": binding, "state": "exception-verified", "controls": exception["controls"],
                "closureCriteria": exception["closureCriteria"], "exceptionSha256": digest(encode(exception)),
            }
            disposition = {key: value for key, value in binding.items() if key != "dispositionRef"}
            disposition.update(authorityRef="approval", evidenceRef="observed",
                               evidenceSha256=digest(encode(observed)), exceptionRef="" if closed else "exception",
                               exceptionPermissionRef="" if closed else "exception-permission")
            self.grant(current.authorities, "disposition", "approval", ["d1", digest(encode(disposition))], "approver")
            self.grant(current.authorities, "exception-policy", "exception-permission",
                       [binding, digest(encode(exception))], "repository-policy")
            current.artifacts.update(observed=encode(observed), exception=encode(exception), remediation=remediation)
            if mutation:
                mutation(current, disposition)
            return matrix_outcome(keys, current, CANDIDATE, scope, inventory, {"d1": disposition})

        self.assertEqual(outcome(), "pass")
        self.assertEqual(outcome(closed=True), "pass")
        self.assertEqual(outcome(inventory=None), "blocked")
        self.assertEqual(outcome(inventory={**findings, "findings": []}), "blocked")
        empty = self.finding_inventory(keys, sources, [])
        self.assertEqual(outcome(inventory=empty), "blocked")
        findings = self.finding_inventory(keys, sources, [finding])
        for change in (
            lambda _, record: record.update(findingRef="f2"),
            lambda _, record: record.update(receiptSha256="a" * 64),
            lambda current, _: current.authorities.grants["approval"].update(decision="withdrawn"),
            lambda current, _: current.authorities.grants["approval"].update(authorityRef="wrong-issuer"),
            lambda current, _: current.authorities.grants["approval"].update(expiresAt=current.time),
            lambda current, _: current.authorities.grants.pop("exception-permission"),
            lambda current, _: current.authorities.grants["exception-permission"].update(decision="withdrawn"),
            lambda current, _: current.artifacts.pop("observed"),
            lambda current, _: current.artifacts.update(observed=b"substituted"),
            lambda current, _: current.artifacts.pop("exception"),
            lambda current, _: current.artifacts.update(exception=encode({**exception, "expiresAt": current.time})),
        ):
            self.assertEqual(outcome(mutation=change), "blocked")
        for change in (lambda current, _: current.artifacts.pop("remediation"),
                       lambda current, _: current.artifacts.update(remediation=b"substituted"),
                       lambda current, _: current.authorities.grants["remediation-review"].update(decision="withdrawn")):
            self.assertEqual(outcome(closed=True, mutation=change), "blocked")

    def test_wrong_types_in_registry_and_independent_observations_are_controlled(self):
        record, key, registry, artifact, observation, inventory, current, authorities = self.qualification_inputs()
        for field, original in registry[key]["metadata"].items():
            for replacement in (None, {}, True):
                with self.subTest(field=field, replacement=replacement):
                    registry[key]["metadata"][field] = replacement
                    with self.assertRaisesRegex(ValueError, "^INVALID_RECORD$"):
                        qualifies(encode(record), key, registry, artifact, observation, inventory,
                                  current, authorities)
            registry[key]["metadata"][field] = original
        for observation_field in ("observerRef", "executionState", "result", "artifactSha256"):
            with self.assertRaisesRegex(ValueError, "^INVALID_RECORD$"):
                qualifies(encode(record), key, registry, artifact, {**observation, observation_field: []},
                          inventory, current, authorities)

    def test_t13_projection_reresolves_current_sources(self):
        key = ("t12-probe", "vps-network")
        sources = self.sources({key})
        issue_map = self.issue_map()
        ref = sources.receipt_refs[key]

        def project(current=sources):
            return t13_projection(key, CANDIDATE, "release", current, issue_map)

        entry = project()
        self.assertEqual(entry, {
            "id": "t12-probe", "issue": issue_map[393], "revision": CANDIDATE,
            "date": "2026-11-17", "environment": "synthetic-v1", "level": "real-godaddy",
            "result": "pass", "ref": ref,
        })
        self.assertIsNone(t13_projection(key, CANDIDATE, "release", sources, {393: "393"}))
        approval = sources.registry[key]
        authority, prerequisite = approval["authorityRef"], approval["prerequisiteRefs"][0]
        for mutate in (
            lambda current: current.authorities.grants[authority].update(decision="withdrawn"),
            lambda current: current.authorities.grants[authority].update(authorityRef="different-issuer"),
            lambda current: current.authorities.issuers.pop(("qualification", authority)),
            lambda current: current.authorities.grants.pop(prerequisite),
            lambda current: current.authorities.grants[prerequisite].update(decision="withdrawn"),
            lambda current: current.authorities.grants[prerequisite].update(expiresAt=current.time),
            lambda current: current.artifacts.update({approval["metadata"]["artifactRef"]: b"substituted"}),
            lambda current: current.observations[key].update(result="fail"),
            lambda current: current.observations[key].update(configurationRef="other-configuration"),
            lambda current: current.inventories[key].update(ownedRemaining=1),
            lambda current: current.registry[key].update(supportedConfiguration=False),
        ):
            changed = copy.deepcopy(sources)
            mutate(changed)
            if changed.registry[key] != approval:
                self.approve_row(changed.authorities, key, changed.registry[key])
            self.assertIsNone(project(changed))
        self.assertIsNone(project(replace(sources, time=approval["freshUntil"])))
        record = validate_receipt(sources.receipts[ref])
        for update in ({"method": "replacement"}, {"evidenceClass": "local_integration"}):
            substituted = {**record, "evidence": {**record["evidence"], **update}}
            self.assertIsNone(project(replace(sources, receipts={ref: encode(substituted)})))
        self.assertIsNone(project(replace(sources, receipts={ref: encode({**record, "gateRow": "vps-load"})})))
        merged = ("post-merge", "merged")
        self.assertIsNone(t13_projection(merged, CANDIDATE, "release", self.sources({merged}), issue_map))

    @staticmethod
    def issue_map():
        backlog = read_json(ROOT / "planning/guildboard-backlog.json")["items"]
        return {item["github"]["number"]: item["id"] for item in backlog}

    def test_t13_handoff_requires_qualified_matrix_gate_evidence_and_authority(self):
        issue_map = self.issue_map()
        model = t13.ReleaseContractScenarios()
        model.setUp()
        smoke = ("production-smoke", "vps-network")
        matrix = self.fixture["handoffMatrix"]
        keys = {tuple(entry["key"]) for entry in matrix}
        sources = self.sources(keys, **{entry["key"][0]: {"issue": entry["issue"]} for entry in matrix})
        findings = self.finding_inventory(keys, sources)
        gate = "GB-T13.G3"
        policy = {gate: {"authorityRef": "applicable-matrix", "candidateSha": CANDIDATE, "scope": "release",
                         "matrixKeys": sorted(keys), "projectionKeys": [smoke],
                         "prerequisiteRefs": ["native-prerequisites"]}}
        subject = [gate, digest(encode(policy[gate]))]
        self.grant(sources.authorities, "gate-matrix", "applicable-matrix", subject)
        self.grant(sources.authorities, "gate-prerequisite", "native-prerequisites",
                   ["native-prerequisites", *subject])
        self.grant(sources.authorities, "accepted-mvp", "t13-mvp", model.prior.designated_mvp)
        original, _, approval = model.stage(scenario={"candidatePatch": {
            "revision": CANDIDATE, "gate": gate, "version": "1.0.0",
        }})

        def stage(entries):
            manifest = {**json.loads(original.manifest), "evidence": entries}
            bundle = replace(original, manifest=encode(manifest))
            _, identity = t13.verified_bundle(bundle)
            approval_record = {**approval, "identity": identity}
            decision = {"identity": identity, "gate": gate, "decision": "accepted",
                        "authority": t13.NATIVE_AUTHORITY, "decisionRef": "native/stable.json",
                        "evidenceRefs": [entry["ref"] for entry in entries],
                        "mvpPublication": manifest["mvpPublication"]}
            ref = identity["manifestSha256"]
            self.grant(sources.authorities, "release-approval", "t13-approval", [ref, digest(encode(approval_record))])
            self.grant(sources.authorities, "native-decision", "t13-native",
                       [ref, digest(encode(decision)), manifest["provenanceRef"]])
            return bundle, {ref: approval_record}, {ref: decision}

        entry = t13_projection(smoke, CANDIDATE, "release", sources, issue_map)
        bundle, approvals, decisions = stage([entry])
        orig_approval = sources.authorities.grants["t13-approval"].copy()
        orig_native = sources.authorities.grants["t13-native"].copy()

        def handoff(candidate=bundle, current=sources, registry=policy, approved=approvals,
                    native=decisions, historical=model.prior):
            return t13_handoff(candidate, current, registry, issue_map, findings, {}, approved, native, historical)

        self.assertEqual(handoff(), "verified")
        self.assertEqual(handoff(approved={}), "pending")
        self.assertEqual(handoff(native={}), "pending")
        self.assertEqual(handoff(historical=None), "pending")
        self.assertEqual(handoff(registry={}), "pending")
        self.assertEqual(handoff(current=[entry]), "pending")
        for ref in ("t13-approval", "t13-native", "t13-mvp", "applicable-matrix", "native-prerequisites",
                    "complete-findings"):
            current = copy.deepcopy(sources)
            current.authorities.grants[ref]["decision"] = "withdrawn"
            self.assertEqual(handoff(current=current), "pending")
        alternatives = copy.deepcopy(policy)
        integration = ("integrated", "hosted")
        alternatives[gate]["projectionKeys"] = [integration]
        alternate = t13_projection(integration, CANDIDATE, "release", sources, issue_map)
        altered, approved, native = stage([alternate])
        other_sources = copy.deepcopy(sources)
        alternate_subject = [gate, digest(encode(alternatives[gate]))]
        self.grant(other_sources.authorities, "gate-matrix", "applicable-matrix", alternate_subject)
        self.grant(other_sources.authorities, "gate-prerequisite", "native-prerequisites",
                   ["native-prerequisites", *alternate_subject])
        self.assertEqual(handoff(candidate=altered, approved=approved, native=native, current=other_sources,
                                 registry=alternatives), "pending")
        for new_entries in ([], [{**entry, "id": "network"}], [{**entry, "level": "integration"}]):
            malformed, approved, native = stage(new_entries)
            self.assertEqual(handoff(candidate=malformed, approved=approved, native=native), "pending")
        sources.authorities.grants.update({"t13-approval": orig_approval, "t13-native": orig_native})
        current = copy.deepcopy(sources)
        current.receipts.pop(current.receipt_refs["integrated", "hosted"])
        self.assertEqual(handoff(current=current), "pending")
        current = copy.deepcopy(sources)
        current.artifacts.pop(current.registry[smoke]["metadata"]["artifactRef"])
        self.assertEqual(handoff(current=current), "pending")
        changed = {ref: {**decision, "decisionRef": "native/replacement.json"} for ref, decision in decisions.items()}
        self.assertEqual(handoff(native=changed), "pending")
        for changed in (None, replace(bundle, notes=b"substitution"), replace(bundle, files={}),
                        replace(bundle, manifest=b"{}"), replace(bundle, index=b"substitution")):
            self.assertEqual(handoff(candidate=changed), "pending")

        prior = model.prior
        version = prior.designated_mvp["identity"]["version"]
        published = prior.versions[version]
        for changed in (
            replace(prior, designated_mvp=None),
            replace(prior, designated_mvp={**prior.designated_mvp, "releaseRef": "other"}),
            replace(prior, committed_authorizations={}),
            *(replace(prior, versions={version: item}) for item in (
                replace(published, receipt={}),
                replace(published, tag_revision="2" * 40),
                replace(published, bundle=replace(published.bundle, notes=b"substituted")),
            )),
        ):
            self.assertEqual(handoff(historical=changed), "pending")

    def test_strict_envelope_rejects_malformed_records(self):
        record, _ = self.receipt()
        bad_evidence = (
            {"nativeIssue": True}, {"nativeIssue": 1.0}, {"scenarioIds": [[], []]},
            {"scenarioIds": ["E01", "E01"]}, {"limitations": "a" * 241},
            {"executedAt": "2026-02-30T00:00:00Z"}, {"artifactVersions": []},
            {"artifactRef": "../escape"}, {"findingDispositions": [{}]},
        )
        malformed = [
            b'{"version":1,"version":1}', b"\xff", b" " * 16_385,
            b'{"version":NaN}', b'{"version":Infinity}', b'{"version":-Infinity}',
            b'{"version":1e10}', b'{"version":true}', b'{"version":0}', b'{"version":"2"}',
            b'{"version":2,"duplicate":{"a":1,"a":2}}', b'[' * 8 + b'0' + b']' * 8,
            b'{"version":2,"scalar":1.2}', b'{"version":2,"scalar":true}',
            b'{"version":2,"scalar":2147483648}', b'{"version":2147483648}',
            br'{"version":2,"scalar":"\ud800"}', encode({"version": 2, "items": [0] * 33}),
            encode({**record, "gateRow": "unknown"}), encode({**record, "environmentId": "other"}),
            *(encode({**record, "evidence": {**record["evidence"], "scenarioIds": [value]}})
              for value in ("E99", "a/b", 1)),
            encode({**record, "unexpected": "value"}),
            encode({**record, "executionState": []}),
            *(encode({**record, "evidence": {**record["evidence"], **update}})
              for update in bad_evidence),
        ]
        for raw in malformed:
            with self.subTest(raw=raw[:120]), self.assertRaisesRegex(ValueError, "INVALID_RECORD"):
                validate_receipt(raw)
        for raw in (encode({**record, "version": 2}), b'{"version":2,"futureField":7}',
                    encode({**record, "evidence": {"version": 2, "futureField": "token"}})):
            with self.assertRaisesRegex(ValueError, "^UNSUPPORTED_RECORD_VERSION$"):
                validate_receipt(raw)

    def test_external_registry_and_budgets_remain_proposed(self):
        matrix = read_json(ROOT / "docs/research/t12-validation-matrix.json")
        rows = matrix["external_rows"]
        self.assertEqual({row["id"] for row in rows}, EXTERNAL)
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row["status"] == "not-run" and "trace-hash-date" in row["required_evidence"]
                            for row in rows))
        self.assertEqual(matrix["accessibility_candidate"]["status"], "not-run")
        self.assertEqual([(row["id"], row["p95_ms"], row["p99_ms"])
                          for row in matrix["budget_candidates"]],
                         [("commit-ack", 250, 750), ("peer-visible", 500, 1000),
                          ("cold-launch", 5000, 7500), ("reconnect", 3000, 5000),
                          ("render", 32, 50)])


if __name__ == "__main__":
    unittest.main()
