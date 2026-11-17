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


def require(condition, code="INVALID_RECORD"):
    if not condition:
        raise ValueError(code)


def read_json(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique_object)


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
    require(type(record.get("version")) is int)
    require(record["version"] == 1, "UNSUPPORTED_RECORD_VERSION")


def validate_receipt(data):
    require(type(data) is bytes and len(data) <= 16_384)
    try:
        record = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, RecursionError, ValueError) as error:
        raise ValueError("INVALID_RECORD") from error
    check_depth(record)
    require(type(record) is dict)
    validate_version(record)
    closed(record, "version gateRow environmentId runId executionState cleanup artifactSha256 evidence")
    for key in ("gateRow", "environmentId", "runId", "executionState", "cleanup"):
        token(record[key])
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
    unique_array(evidence["scenarioIds"], minimum=1)
    require(type(evidence["executedAt"]) is str)
    require(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
                         evidence["executedAt"]))
    try:
        datetime.fromisoformat(evidence["executedAt"])
    except ValueError as error:
        raise ValueError("INVALID_RECORD") from error
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


def qualifies(record, row, expected_metadata, artifact, observed_result):
    evidence = record["evidence"]
    require(artifact is not None and expected_metadata is not None
            and observed_result is not None, "DEPENDENCY_UNAVAILABLE")
    return (
        row in CLASS_BY_ROW
        and record["gateRow"] == row
        and evidence["evidenceClass"] == CLASS_BY_ROW[row]
        and all(evidence[key] == value for key, value in expected_metadata.items())
        and record["environmentId"] == expected_metadata["environment"]
        and record["artifactSha256"] == digest(artifact)
        and record["executionState"] == "completed"
        and record["cleanup"] in {"verified", "untouched"}
        and evidence["result"] == observed_result == "pass"
    )


class VerificationEvidenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = read_json(FIXTURES / "GB-T12-S1-scenarios.json")
        cls.scenarios = {row["id"]: row for row in cls.fixture["scenarios"]}
        cls.claims = {row["id"]: row for row in cls.fixture["claims"]}
        cls.observations = {row["run"]: row for row in cls.fixture["observations"]}
        cls.reviewed = {
            "candidateSha": CANDIDATE, "nativeIssue": 393, "scenarioIds": ["E01"],
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
        backlog = read_json(ROOT / "planning/guildboard-backlog.json")["items"]
        verification = {item["github"]["number"] for item in backlog
                        if item["id"].startswith("GB-T12.") and item["id"].endswith(".V1")}
        self.assertLessEqual({scenario["verification"] for scenario in self.scenarios.values()},
                             verification)

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
            ("ack-fenced", "protectedChunks"), ("restore", "missingAcceptedEffects"),
            ("restore", "oldLineageEffects"), ("matrix-valid", "openFindings"),
        ]:
            with self.subTest(run=run, signal=signal):
                claim = self.claims[run]
                observed = copy.deepcopy(self.observations[run])
                observed["values"][signal] += 1
                self.assertEqual(assess_fixture(claim, observed, self.scenarios[claim["scenario"]]),
                                 "fail")

    def test_exact_environment_and_provenance_are_required(self):
        record, artifact = self.receipt()
        validated = validate_receipt(encode(record))
        self.assertTrue(qualifies(validated, "offline", self.reviewed, artifact, "pass"))
        for row in CLASS_BY_ROW.keys() - {"offline"}:
            with self.subTest(row=row):
                substituted = {**validated, "gateRow": row}
                self.assertFalse(qualifies(substituted, row, self.reviewed, artifact, "pass"))
        for field, value in [
            ("candidateSha", "2" * 40), ("environment", "other-build"),
            ("nativeIssue", 400), ("scope", "different-scope"),
            ("executedAt", "2025-11-17T00:00:00Z"),
            ("scenarioIds", ["E02"]), ("result", "blocked"),
        ]:
            with self.subTest(field=field):
                mutated = copy.deepcopy(record)
                mutated["evidence"][field] = value
                self.assertFalse(qualifies(validate_receipt(encode(mutated)), "offline",
                                           self.reviewed, artifact, "pass"))
        self.assertFalse(qualifies(validated, "offline", self.reviewed, artifact + b" ", "pass"))
        self.assertFalse(qualifies(validated, "offline", self.reviewed, artifact, "fail"))
        with self.assertRaisesRegex(ValueError, "DEPENDENCY_UNAVAILABLE"):
            qualifies(validated, "offline", self.reviewed, None, "pass")

    def test_failed_target_or_dirty_cleanup_cannot_pass(self):
        record, artifact = self.receipt()
        for field, values in [
            ("executionState", STATES - {"completed"}),
            ("cleanup", {"failed", "pending"}),
        ]:
            for value in values:
                with self.subTest(field=field, value=value):
                    changed = validate_receipt(encode({**record, field: value}))
                    self.assertFalse(qualifies(changed, "offline", self.reviewed, artifact, "pass"))

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
