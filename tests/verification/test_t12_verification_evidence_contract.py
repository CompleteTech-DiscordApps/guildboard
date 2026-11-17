"""Offline conformance controls for the proposed T12 contract.

These validators are test oracles, not a product decoder or a release gate.
The authored observations simulate independent instrumentation.
"""

import copy
import hashlib
import json
import re
import unittest
from datetime import datetime
from pathlib import Path


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
        for child in value.values():
            check_depth(child, depth + 1)
    elif type(value) is list:
        require(len(value) <= 32)
        for child in value:
            check_depth(child, depth + 1)
    else:
        require(type(value) in (str, int))


def validate_version(record):
    count(record.get("version"))
    require(record["version"] > 0)
    require(record["version"] == 1, "UNSUPPORTED_RECORD_VERSION")


def validate_receipt(data):
    record = decode_json(data, 16_384)
    check_depth(record)
    require(type(record) is dict)
    validate_version(record)
    closed(record, "version gateRow environmentId runId executionState cleanup artifactSha256 evidence")
    for key in ("gateRow", "environmentId", "runId", "executionState", "cleanup"):
        token(record[key])
    require(record["gateRow"] in CLASS_BY_ROW)
    require(record["executionState"] in STATES and record["cleanup"] in CLEANUP)
    require(type(record["artifactSha256"]) is str)
    require(re.fullmatch(r"[0-9a-f]{64}", record["artifactSha256"]))
    evidence = record["evidence"]
    require(type(evidence) is dict)
    validate_version(evidence)
    closed(evidence, "version candidateSha nativeIssue scenarioIds method executedAt environment "
                     "artifactVersions verifierRef scope evidenceClass result limitations "
                     "artifactRef findingDispositions")
    for key in ("method", "environment", "verifierRef", "scope", "artifactRef",
                "evidenceClass", "result"):
        token(evidence[key])
    require(type(evidence["candidateSha"]) is str)
    require(re.fullmatch(r"[0-9a-f]{40}", evidence["candidateSha"]))
    count(evidence["nativeIssue"])
    require(evidence["nativeIssue"] > 0 and type(evidence["scenarioIds"]) is list)
    for identifier in evidence["scenarioIds"]:
        token(identifier)
        require(identifier in {f"E{index:02}" for index in range(1, 9)})
    unique_array(evidence["scenarioIds"], minimum=1)
    instant(evidence["executedAt"])
    require(record["environmentId"] == evidence["environment"])
    require(evidence["evidenceClass"] in CLASS_BY_ROW.values() and evidence["result"] in RESULTS)
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
    return record


def instant(value):
    require(type(value) is str)
    require(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value))
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("INVALID_RECORD") from error


def qualifies(data, row, registry, artifact, observation, inventory, trusted_time):
    record = validate_receipt(data)
    require(type(row) is str and row in CLASS_BY_ROW)
    require(all(item is not None for item in (registry, artifact, observation, inventory, trusted_time)),
            "DEPENDENCY_UNAVAILABLE")
    require(type(registry) is dict and row in registry)
    approval = registry[row]
    closed(approval, "metadata runId artifactSha256 resultObserver cleanupObserver approvedAt expiresAt "
                     "resourceful prerequisites")
    closed(approval["metadata"], METADATA)
    closed(approval["prerequisites"], "authorized available")
    for field in ("runId", "resultObserver", "cleanupObserver"):
        token(approval[field])
    require(approval["resultObserver"] != approval["cleanupObserver"])
    require(approval["metadata"]["verifierRef"] not in
            {approval["resultObserver"], approval["cleanupObserver"]})
    require(type(approval["resourceful"]) is bool)
    require(all(type(value) is bool for value in approval["prerequisites"].values()))
    require(approval["prerequisites"]["available"], "DEPENDENCY_UNAVAILABLE")
    closed(observation, "runId observerRef candidateSha environmentId artifactSha256 result")
    closed(inventory, "runId observerRef candidateSha environmentId artifactSha256 cleanup ownedCreated "
                      "ownedRemaining foreignSentinel")
    for value in (inventory["ownedCreated"], inventory["ownedRemaining"], inventory["foreignSentinel"]):
        count(value)
    require(type(artifact) is bytes)
    evidence = record["evidence"]
    current = instant(trusted_time)
    approved = instant(approval["approvedAt"])
    expires = instant(approval["expiresAt"])
    executed = instant(evidence["executedAt"])
    binding = {"runId": record["runId"], "candidateSha": evidence["candidateSha"],
               "environmentId": record["environmentId"], "artifactSha256": record["artifactSha256"]}
    cleanup = "verified" if approval["resourceful"] else "untouched"
    return (
        record["gateRow"] == row
        and evidence["evidenceClass"] == CLASS_BY_ROW[row]
        and encode({key: evidence[key] for key in METADATA.split()}) == encode(approval["metadata"])
        and approval["prerequisites"]["authorized"] and approved <= executed <= current < expires
        and record["runId"] == approval["runId"]
        and record["artifactSha256"] == approval["artifactSha256"] == digest(artifact)
        and all(observation[key] == inventory[key] == value for key, value in binding.items())
        and observation["observerRef"] == approval["resultObserver"]
        and inventory["observerRef"] == approval["cleanupObserver"]
        and record["executionState"] == "completed"
        and record["cleanup"] == inventory["cleanup"] == cleanup
        and inventory["ownedRemaining"] == 0 and inventory["foreignSentinel"] == 1
        and (inventory["ownedCreated"] == 0 if cleanup == "untouched" else True)
        and evidence["result"] == observation["result"] == "pass"
    )


def matrix_outcome(required_rows, observed_rows, security_inputs, findings, candidate, scope, trusted_time):
    """Assess registered exact-scope outcomes and independently resolved T9 records."""
    if any(observed_rows.get(row) == "fail" for row in required_rows):
        return "fail"
    if any(observed_rows.get(row) != "pass" for row in required_rows):
        return "blocked"
    current = instant(trusted_time)
    for name in SECURITY_INPUTS:
        evidence = security_inputs.get(name)
        if evidence is None:
            return "blocked"
        closed(evidence, "candidateSha scope artifactRef verifierRef authorized result")
        token(evidence["artifactRef"])
        token(evidence["verifierRef"])
        if not (evidence["candidateSha"] == candidate and evidence["scope"] == scope
                and evidence["authorized"] is True and evidence["result"] == "pass"):
            return "blocked"
    for finding_ref, severity, disposition in findings:
        if severity not in {"critical", "high"}:
            continue
        if disposition is None:
            return "blocked"
        closed(disposition, "findingRef candidateSha scope severity approverRef authorized "
                            "controlsVerified closureCriteriaVerified expiresAt")
        token(disposition["approverRef"])
        if not (disposition["findingRef"] == finding_ref and disposition["candidateSha"] == candidate
                and disposition["scope"] == scope and disposition["severity"] == severity
                and disposition["authorized"] is True and disposition["controlsVerified"] is True
                and disposition["closureCriteriaVerified"] is True
                and current < instant(disposition["expiresAt"])):
            return "blocked"
    return "pass"


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
            "version": 1, "gateRow": "offline", "environmentId": "synthetic-v1",
            "runId": "valid", "executionState": "completed", "cleanup": "verified",
            "artifactSha256": digest(artifact),
            "evidence": {
                **copy.deepcopy(self.reviewed), "version": 1,
                "evidenceClass": "fixture", "result": "pass", "limitations": "Synthetic only.",
            },
        }
        return record, artifact

    def test_scope_and_contract_references(self):
        closed(self.fixture, "version status scenarios claims observations")
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

    def test_side_effect_and_interruption_mutations_are_detected(self):
        for run, signal in [
            ("invalid", "binds"), ("unavailable", "adapterCalls"),
            ("interrupted", "ownedRemaining"), ("interrupted", "foreignSentinel"),
            ("denied", "durableEffects"), ("denied", "egressEvents"),
            ("denied", "foreignIdentifiers"), ("duplicate", "acceptedReceipts"),
            ("ack-fenced", "protectedBytes"), ("handoff-before-revoke", "bytesAfterRevocation"),
            ("handoff-before-revoke", "handoffSequence"), ("restart", "missingAcknowledgedEffects"),
            ("document-restore", "beyondCutReceipts"), ("document-restore", "oldLineageEffects"),
            ("disaster-recovery", "rpoExceeded"), ("matrix-valid", "unresolvedFindings"),
        ]:
            with self.subTest(run=run, signal=signal):
                claim = self.claims[run]
                observed = copy.deepcopy(self.observations[run])
                observed["values"][signal] += 1
                self.assertEqual(assess_fixture(claim, observed, self.scenarios[claim["scenario"]]),
                                 "fail")

    def qualification_inputs(self):
        record, artifact = self.receipt()
        binding = {"runId": record["runId"], "candidateSha": CANDIDATE,
                   "environmentId": record["environmentId"], "artifactSha256": digest(artifact)}
        current = "2026-11-17T00:01:00Z"
        approval = {
            "metadata": copy.deepcopy(self.reviewed), "runId": record["runId"],
            "artifactSha256": digest(artifact), "resultObserver": "result-oracle",
            "cleanupObserver": "cleanup-oracle", "approvedAt": DATE,
            "expiresAt": "2026-11-17T01:00:00Z", "resourceful": True,
            "prerequisites": {"authorized": True, "available": True},
        }
        observation = {**binding, "observerRef": "result-oracle", "result": "pass"}
        inventory = {**binding, "observerRef": "cleanup-oracle", "cleanup": "verified",
                     "ownedCreated": 1, "ownedRemaining": 0, "foreignSentinel": 1}
        return record, "offline", {"offline": approval}, artifact, observation, inventory, current

    def test_exact_environment_and_provenance_are_required(self):
        record, *inputs = self.qualification_inputs()
        self.assertTrue(qualifies(encode(record), *inputs))
        for field, value in [
            ("candidateSha", "2" * 40), ("nativeIssue", 400), ("scope", "different-scope"),
            ("executedAt", "2025-11-17T00:00:00Z"), ("verifierRef", "replacement"),
            ("scenarioIds", ["E02"]), ("result", "blocked"), ("artifactRef", "different-trace"),
        ]:
            with self.subTest(field=field):
                mutated = copy.deepcopy(record)
                mutated["evidence"][field] = value
                self.assertFalse(qualifies(encode(mutated), *inputs))
        changed_environment = copy.deepcopy(record)
        changed_environment["environmentId"] = changed_environment["evidence"]["environment"] = "other-build"
        self.assertFalse(qualifies(encode(changed_environment), *inputs))
        self.assertFalse(qualifies(encode({**record, "runId": "other-run"}), *inputs))
        self.assertFalse(qualifies(encode({**record, "gateRow": "discord-win"}), *inputs))
        _, row, registry, artifact, observation, inventory, current = self.qualification_inputs()
        self.assertFalse(qualifies(encode(record), row, registry, artifact + b" ", observation, inventory, current))
        with self.assertRaisesRegex(ValueError, "DEPENDENCY_UNAVAILABLE"):
            qualifies(encode(record), row, registry, None, observation, inventory, current)
        sparse_registry = copy.deepcopy(registry)
        sparse_registry[row]["metadata"] = {"environment": record["environmentId"]}
        with self.assertRaisesRegex(ValueError, "INVALID_RECORD"):
            qualifies(encode(record), row, sparse_registry, artifact, observation, inventory, current)

    def test_target_cleanup_and_observations_are_independently_bound(self):
        record, row, registry, artifact, observation, inventory, current = self.qualification_inputs()
        for field, values in [
            ("executionState", STATES - {"completed"}),
            ("cleanup", CLEANUP - {"verified"}),
        ]:
            for value in values:
                with self.subTest(field=field, value=value):
                    changed = {**record, field: value}
                    self.assertFalse(qualifies(encode(changed), row, registry, artifact, observation, inventory, current))
        untouched = {**record, "cleanup": "untouched"}
        self.assertFalse(qualifies(encode(untouched), row, registry, artifact, observation,
                                   {**inventory, "cleanup": "untouched"}, current))
        for field, value in [("runId", "other-run"), ("observerRef", "result-oracle"),
                             ("artifactSha256", "2" * 64), ("ownedRemaining", 1), ("foreignSentinel", 0)]:
            self.assertFalse(qualifies(encode(record), row, registry, artifact, observation,
                                       {**inventory, field: value}, current))
        for field, value in [("runId", "other-run"), ("observerRef", "cleanup-oracle"), ("result", "fail")]:
            self.assertFalse(qualifies(encode(record), row, registry, artifact,
                                       {**observation, field: value}, inventory, current))
        self.assertFalse(qualifies(encode(record), row, registry, artifact, observation, inventory,
                                   registry[row]["expiresAt"]))
        registry[row]["resourceful"] = False
        self.assertFalse(qualifies(encode(untouched), row, registry, artifact, observation,
                                   {**inventory, "cleanup": "untouched"}, current))
        self.assertTrue(qualifies(encode(untouched), row, registry, artifact, observation,
                                  {**inventory, "cleanup": "untouched", "ownedCreated": 0}, current))
        registry[row]["prerequisites"]["authorized"] = False
        self.assertFalse(qualifies(encode(untouched), row, registry, artifact, observation,
                                   {**inventory, "cleanup": "untouched", "ownedCreated": 0}, current))

    def test_release_gate_distinguishes_unqualified_rows_and_verified_failure(self):
        rows = {"discord-win", "vps-network", "vps-recovery", "review"}
        observed = dict.fromkeys(rows, "pass")
        scope = "release"
        security = {
            name: {"candidateSha": CANDIDATE, "scope": scope, "artifactRef": name,
                   "verifierRef": "authorized-reviewer", "authorized": True, "result": "pass"}
            for name in SECURITY_INPUTS
        }
        disposition = {
            "findingRef": "finding", "candidateSha": CANDIDATE, "scope": scope, "severity": "high",
            "approverRef": "authorized-approver", "authorized": True, "controlsVerified": True,
            "closureCriteriaVerified": True, "expiresAt": "2026-11-17T01:00:00Z",
        }

        def outcome(observations=observed, inputs=security, findings=()):
            return matrix_outcome(rows, observations, inputs, findings, CANDIDATE, scope, DATE)

        self.assertEqual(outcome(findings=[("finding", "high", disposition)]), "pass")
        for row in rows:
            for result, expected in (("pending", "blocked"), ("ineligible", "blocked"), ("fail", "fail")):
                self.assertEqual(outcome({**observed, row: result}), expected)
        for item in SECURITY_INPUTS:
            self.assertEqual(outcome(inputs={**security, item: None}), "blocked")
            stale = {**security[item], "candidateSha": "2" * 40}
            self.assertEqual(outcome(inputs={**security, item: stale}), "blocked")
        for changed in (None, {**disposition, "authorized": False}, {**disposition, "expiresAt": DATE},
                        {**disposition, "scope": "other-scope"}, {**disposition, "controlsVerified": False},
                        {**disposition, "findingRef": "other-finding"}, {**disposition, "severity": "critical"},
                        {**disposition, "closureCriteriaVerified": False}):
            self.assertEqual(outcome(findings=[("finding", "high", changed)]), "blocked")

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
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_RECORD_VERSION"):
            validate_receipt(encode({**record, "version": 2}))

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
