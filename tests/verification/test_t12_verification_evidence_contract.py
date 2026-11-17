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


def unique_array(values, key=None, minimum=0):
    require(type(values) is list and minimum <= len(values) <= 32)
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


def current_grant(grant, subject, current, since=None):
    if grant is None:
        return False
    closed(grant, "subject authorityRef issuedAt expiresAt decision")
    token(grant["authorityRef"])
    token(grant["decision"])
    require(grant["decision"] in {"approved", "withdrawn"})
    return (grant["subject"] == subject and grant["decision"] == "approved"
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
    require(type(registry) is dict and key in registry and type(authorities) is dict)
    approval = registry[key]
    closed(approval, "metadata runId artifactSha256 resultObserver cleanupObserver authorityRef resourceful")
    validate_metadata(approval["metadata"])
    hex_value(approval["artifactSha256"], 64)
    for field in ("runId", "resultObserver", "cleanupObserver", "authorityRef"):
        token(approval[field])
    require(approval["resultObserver"] != approval["cleanupObserver"])
    require(approval["metadata"]["verifierRef"] not in
            {approval["resultObserver"], approval["cleanupObserver"]})
    require(type(approval["resourceful"]) is bool)
    closed(observation, "requirementId gateRow runId observerRef candidateSha environmentId artifactSha256 executionState result")
    closed(inventory, "requirementId gateRow runId observerRef candidateSha environmentId artifactSha256 cleanup ownedCreated "
                      "ownedRemaining foreignSentinel")
    for observed in (observation, inventory):
        hex_value(observed["candidateSha"], 40)
        hex_value(observed["artifactSha256"], 64)
        for field in ("requirementId", "gateRow", "runId", "observerRef", "environmentId"):
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
               "environmentId": record["environmentId"], "artifactSha256": record["artifactSha256"]}
    cleanup = "verified" if approval["resourceful"] else "untouched"
    authority = authorities.get(approval["authorityRef"])
    require(authority is not None, "DEPENDENCY_UNAVAILABLE")
    subject = [*key, digest(encode(approval))]
    outcome = Outcome.INELIGIBLE
    if (
        (record["requirementId"], record["gateRow"]) == key
        and evidence["evidenceClass"] == CLASS_BY_ROW[row]
        and encode({key: evidence[key] for key in METADATA.split()}) == encode(approval["metadata"])
        and current_grant(authority, subject, current, executed)
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
    return Qualification(key, evidence["candidateSha"], evidence["scope"], trusted_time, outcome, digest(encode(record)))


def disposition_resolved(finding, candidate, scope, current, records, artifacts, authorities):
    finding_ref, severity, ref = finding
    record = records.get(ref)
    if record is None:
        return False
    closed(record, "findingRef candidateSha scope severity approverRef authorityRef evidenceRef "
                   "evidenceSha256 exceptionRef")
    for field in ("findingRef", "scope", "severity", "approverRef", "authorityRef", "evidenceRef"):
        token(record[field])
    hex_value(record["candidateSha"], 40)
    hex_value(record["evidenceSha256"], 64)
    raw = artifacts.get(record["evidenceRef"])
    if raw is None:
        return False
    if not (record["findingRef"] == finding_ref and record["candidateSha"] == candidate
            and record["scope"] == scope and record["severity"] == severity
            and digest(raw) == record["evidenceSha256"]
            and current_grant(authorities.get(record["authorityRef"]),
                              [ref, digest(encode(record))], current)):
        return False
    observed = decode_json(raw, 4096)
    closed(observed, "findingRef candidateSha scope approverRef state controls closureCriteria exceptionSha256")
    if not all(observed[name] == record[name]
               for name in ("findingRef", "candidateSha", "scope", "approverRef")):
        return False
    if record["exceptionRef"] == "":
        return observed["state"] == "closed"
    token(record["exceptionRef"])
    exception_bytes = artifacts.get(record["exceptionRef"])
    if exception_bytes is None:
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
    return (
        all(exception[name] == record[name] for name in ("scope", "severity", "approverRef"))
        and current < instant(exception["expiresAt"])
        and observed["state"] == "exception-verified"
        and observed["controls"] == exception["controls"]
        and observed["closureCriteria"] == exception["closureCriteria"]
        and observed["exceptionSha256"] == digest(exception_bytes)
    )


def passing(*args):
    return qualifies(*args).outcome is Outcome.VERIFIED_PASS


def matrix_outcome(required_keys, security_keys, qualified, candidate, scope, trusted_time,
                   findings=(), *, dispositions=None, artifacts=None, authorities=None):
    """Consume only qualified outcomes from the same assessment and scope."""
    eligible = {}
    for key in required_keys | security_keys:
        item = qualified.get(key)
        if (type(item) is Qualification and item.key == key and item.candidate == candidate
                and item.scope == scope and item.checked_at == trusted_time):
            eligible[key] = item.outcome
    if Outcome.VERIFIED_FAIL in eligible.values():
        return "fail"
    if any(eligible.get(key) is not Outcome.VERIFIED_PASS for key in required_keys | security_keys):
        return "blocked"
    current = instant(trusted_time)
    if any(finding[1] in {"critical", "high"} and not disposition_resolved(
        finding, candidate, scope, current, dispositions or {}, artifacts or {}, authorities or {})
           for finding in findings):
        return "blocked"
    return "pass"


T13_LEVELS = {
    "fixture": "synthetic", "local_integration": "integration", "hosted_ci": "integration",
    "independent_review": "independent-review", "real_discord": "real-discord",
    "real_godaddy": "real-godaddy",
}


def t13_projection(identifier, qualification, issue_map, ref, source_records):
    raw = source_records.get(ref)
    if (raw is None or type(qualification) is not Qualification
            or qualification.outcome is not Outcome.VERIFIED_PASS):
        return None
    record = validate_receipt(raw)
    if qualification.receipt_sha256 != digest(encode(record)):
        return None
    evidence = record["evidence"]
    level = T13_LEVELS.get(evidence["evidenceClass"])
    issue = issue_map.get(evidence["nativeIssue"])
    if level is None or issue is None:
        return None
    entry = {"id": identifier, "issue": issue, "revision": evidence["candidateSha"],
             "date": evidence["executedAt"][:10], "environment": evidence["environment"],
             "level": level, "result": "pass", "ref": ref}
    return entry if t13.valid_record(entry) else None


def t13_handoff(bundle, evidence, approvals, native_decisions, historical=None):
    if bundle is None or (verified := t13.verified_bundle(bundle)) is None:
        return "pending"
    manifest, identity = verified
    decision = native_decisions.get(identity["manifestSha256"])
    if (not evidence or manifest["evidence"] != evidence
            or not all(row["revision"] == identity["revision"] for row in evidence)
            or not any(t13.valid_approval(approval, manifest, identity) for approval in approvals)
            or not t13.valid_native_decision(decision, manifest, identity)):
        return "pending"
    if manifest["gate"] == "GB-T13.G3" and (
        historical is None or not t13.verified_mvp_publication(historical, manifest)
    ):
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
        closed(self.fixture, "version status scenarios claims operationControls observations")
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

    def qualification_inputs(self, requirement="harness", row="offline", scope="test-only", result="pass"):
        record, artifact = self.receipt()
        record["requirementId"], record["gateRow"] = requirement, row
        record["evidence"].update(scope=scope, evidenceClass=CLASS_BY_ROW[row], result=result)
        binding = {"requirementId": requirement, "gateRow": row,
                   "runId": record["runId"], "candidateSha": CANDIDATE,
                   "environmentId": record["environmentId"], "artifactSha256": digest(artifact)}
        current = "2026-11-17T00:01:00Z"
        key = (requirement, row)
        approval = {
            "metadata": {name: record["evidence"][name] for name in METADATA.split()},
            "runId": record["runId"], "artifactSha256": digest(artifact),
            "resultObserver": "result-oracle", "cleanupObserver": "cleanup-oracle",
            "resourceful": True, "authorityRef": "qualification-approval",
        }
        authorities = {approval["authorityRef"]: self.grant([*key, digest(encode(approval))])}
        observation = {**binding, "observerRef": "result-oracle", "result": result,
                       "executionState": "completed"}
        inventory = {**binding, "observerRef": "cleanup-oracle", "cleanup": "verified",
                     "ownedCreated": 1, "ownedRemaining": 0, "foreignSentinel": 1}
        return record, key, {key: approval}, artifact, observation, inventory, current, authorities

    @staticmethod
    def grant(subject):
        return {"subject": subject, "authorityRef": "approved-owner-policy", "issuedAt": DATE,
                "expiresAt": "2026-11-17T01:00:00Z", "decision": "approved"}

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
                                   authorities["qualification-approval"]["expiresAt"], authorities))
        registry[row]["resourceful"] = False
        authorities["qualification-approval"]["subject"] = [*row, digest(encode(registry[row]))]
        self.assertFalse(passing(encode(untouched), row, registry, artifact, observation,
                                   {**inventory, "cleanup": "untouched"}, current, authorities))
        self.assertTrue(passing(encode(untouched), row, registry, artifact, observation,
                                  {**inventory, "cleanup": "untouched", "ownedCreated": 0}, current, authorities))
        authorities["qualification-approval"]["decision"] = "withdrawn"
        self.assertFalse(passing(encode(untouched), row, registry, artifact, observation,
                                   {**inventory, "cleanup": "untouched", "ownedCreated": 0}, current, authorities))

    def test_release_gate_distinguishes_verified_failure_and_substitution(self):
        keys = {("network", "vps-network"), ("smoke", "vps-network")}
        security_keys = {(name, "review" if name == "independent-security-review" else "hosted")
                         for name in SECURITY_INPUTS}
        current = self.qualification_inputs()[-2]

        def observed(key, result="pass", mutate=None):
            record, *inputs = self.qualification_inputs(*key, scope="release", result=result)
            if mutate:
                mutate(inputs)
            return qualifies(encode(record), *inputs)

        outcomes = {key: observed(key) for key in keys | security_keys}

        def outcome(items=outcomes):
            return matrix_outcome(keys, security_keys, items, CANDIDATE, "release", current)

        self.assertEqual(outcome(), "pass")
        network, smoke = ("network", "vps-network"), ("smoke", "vps-network")
        self.assertEqual(outcome({**outcomes, smoke: outcomes[network]}), "blocked")
        network_record, *_ = self.qualification_inputs(*network, scope="release")
        _, *smoke_inputs = self.qualification_inputs(*smoke, scope="release")
        self.assertEqual(qualifies(encode(network_record), *smoke_inputs).outcome, Outcome.INELIGIBLE)
        self.assertEqual(outcome({**outcomes, smoke: observed(smoke, "fail")}), "fail")
        for state in ("pass", "fail", Outcome.VERIFIED_PASS, Outcome.VERIFIED_FAIL):
            self.assertEqual(outcome({**outcomes, smoke: state}), "blocked")

        def stale(inputs):
            inputs[-1]["qualification-approval"]["expiresAt"] = current

        def different_artifact(inputs):
            inputs[2] += b"other"

        for key in keys | security_keys:
            for mutation in (stale, different_artifact):
                self.assertEqual(outcome({**outcomes, key: observed(key, "fail", mutation)}), "blocked")
            self.assertEqual(outcome({**outcomes, key: None}), "blocked")

    def test_release_disposition_requires_bound_authority_and_exception_evidence(self):
        scope = "test-only"
        record, key, *inputs = self.qualification_inputs()
        qualification = qualifies(encode(record), key, *inputs)
        current = inputs[-2]
        finding = ("f1", "high", "d1")
        exception = {"version": 1, "scope": scope, "severity": "high", "approverRef": "approver",
                     "rationale": "Reviewed temporary coverage.", "controls": ["mitigation"],
                     "expiresAt": "2026-11-17T01:00:00Z", "closureCriteria": "remediation-check"}
        subject = {"findingRef": finding[0], "candidateSha": CANDIDATE, "scope": scope,
                   "approverRef": exception["approverRef"]}

        def outcome(exception_bytes=encode(exception), change=None, displaced=False, closed=False):
            observed = encode({**subject, "state": "closed" if closed else "exception-verified",
                               "controls": exception["controls"], "closureCriteria": exception["closureCriteria"],
                               "exceptionSha256": digest(encode(exception))})
            disposition = {**subject, "severity": finding[1], "authorityRef": "approval",
                           "evidenceRef": "observed", "evidenceSha256": digest(observed),
                           "exceptionRef": "" if closed else "exception"}
            authority = self.grant([finding[2], digest(encode(disposition))])
            artifacts = {"observed": observed, "exception": exception_bytes}
            if change:
                change(authority, artifacts)
            if displaced:
                disposition["findingRef"] = "f2"
            return matrix_outcome({key}, set(), {key: qualification}, CANDIDATE, scope, current,
                                  [finding], dispositions={"d1": disposition}, artifacts=artifacts,
                                  authorities={"approval": authority})

        self.assertEqual(outcome(), "pass")
        self.assertEqual(outcome(closed=True), "pass")
        self.assertEqual(outcome(displaced=True), "blocked")
        self.assertEqual(outcome(encode({**exception, "expiresAt": current})), "blocked")
        for change in (
            lambda grant, _: grant.update(decision="withdrawn"),
            lambda grant, _: grant.update(expiresAt=current),
            lambda _, artifacts: artifacts.pop("observed"),
            lambda _, artifacts: artifacts.update(observed=b"substituted"),
            lambda _, artifacts: artifacts.pop("exception"),
        ):
            self.assertEqual(outcome(change=change), "blocked")

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

    def test_t13_projection_and_exact_candidate_handoff(self):
        record, *inputs = self.qualification_inputs(row="vps-network")
        qualification = qualifies(encode(record), *inputs)
        backlog = read_json(ROOT / "planning/guildboard-backlog.json")["items"]
        issue_map = {item["github"]["number"]: item["id"] for item in backlog}
        ref = "synthetic/t12-trace.json"
        source = {ref: encode(record)}
        entry = t13_projection("t12-probe", qualification, issue_map, ref, source)
        self.assertEqual(entry, {
            "id": "t12-probe", "issue": issue_map[393], "revision": CANDIDATE,
            "date": "2026-11-17", "environment": "synthetic-v1", "level": "real-godaddy",
            "result": "pass", "ref": ref,
        })
        self.assertIsNone(t13_projection("t12-probe", qualification, {393: "393"}, ref, source))
        for changes in ({"method": "replacement"}, {"evidenceClass": "local_integration"}):
            substituted = {**record, "evidence": {**record["evidence"], **changes}}
            self.assertIsNone(t13_projection("t12-probe", qualification, issue_map, ref,
                                             {ref: encode(substituted)}))
        post_merge, *post_inputs = self.qualification_inputs(row="merged")
        self.assertIsNone(t13_projection("t12-probe", qualifies(encode(post_merge), *post_inputs),
                                         issue_map, ref, {ref: encode(post_merge)}))

        model = t13.ReleaseContractScenarios()
        model.setUp()
        original_bundle, _, approval = model.stage(scenario={"candidatePatch": {
            "revision": CANDIDATE, "gate": "GB-T13.G3", "version": "1.0.0",
        }})
        manifest = json.loads(original_bundle.manifest)
        manifest["evidence"] = [entry]
        bundle = replace(original_bundle, manifest=encode(manifest))
        _, identity = t13.verified_bundle(bundle)
        approval = {**approval, "identity": identity}
        decision = {"identity": identity, "gate": manifest["gate"], "decision": "accepted",
                    "authority": t13.NATIVE_AUTHORITY, "decisionRef": "native/stable.json",
                    "evidenceRefs": [ref], "mvpPublication": manifest["mvpPublication"]}
        decisions = {identity["manifestSha256"]: decision}
        self.assertNotEqual(record["artifactSha256"], identity["artifactSha256"])
        self.assertEqual(t13_handoff(bundle, [entry], [approval], decisions, model.prior), "verified")
        self.assertEqual(t13_handoff(bundle, [entry], [], decisions, model.prior), "pending")
        self.assertEqual(t13_handoff(bundle, [entry], [approval], {}, model.prior), "pending")
        self.assertEqual(t13_handoff(bundle, [entry], [approval], decisions), "pending")
        for changed in (None, replace(bundle, notes=b"substitution"),
                        replace(bundle, files={}), replace(bundle, manifest=b"{}"),
                        replace(bundle, index=b"substitution")):
            self.assertEqual(t13_handoff(changed, [entry], [approval], decisions, model.prior),
                             "pending")

        prior = model.prior
        version = prior.designated_mvp["identity"]["version"]
        published = prior.versions[version]
        for changed in (
            replace(prior, designated_mvp=None),
            replace(prior, designated_mvp={**prior.designated_mvp, "releaseRef": "other"}),
            replace(prior, designated_mvp={**prior.designated_mvp, "identity": identity}),
            replace(prior, committed_authorizations={}),
            *(replace(prior, versions={version: item}) for item in (
                replace(published, receipt={}),
                replace(published, tag_revision="2" * 40),
                replace(published, bundle=replace(published.bundle, notes=b"substituted")),
            )),
        ):
            self.assertEqual(t13_handoff(bundle, [entry], [approval], decisions, changed), "pending")

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
