"""Declarative GB-T13.S1 examples with an in-memory publication model."""

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "docs/specifications/fixtures/GB-T13-S1-scenarios.json"
IDENTITY = {"version", "revision", "artifactSha256"}
MANIFEST = IDENTITY | {"schemaVersion", "gate", "notesRef", "evidence"}
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
    if candidate.keys() != MANIFEST or not strings(candidate, MANIFEST - {"evidence"}):
        return False
    if not (
        candidate["schemaVersion"] == "1.0.0"
        and candidate["gate"] == "GB-T13.G1"
        and SEMVER.fullmatch(candidate["version"])
        and re.fullmatch(r"[0-9a-f]{40}", candidate["revision"])
        and re.fullmatch(r"[0-9a-f]{64}", candidate["artifactSha256"])
        and safe_ref(candidate["notesRef"])
    ):
        return False
    evidence = candidate["evidence"]
    return (
        isinstance(evidence, list) and len(evidence) <= 128
        and all(valid_record(record) for record in evidence)
        and len({record["id"] for record in evidence}) == len(evidence)
    )


def attempt(candidate, current, expected_prior, *, native_ready, interruption=None):
    """Model one G1 evidence row and an atomic commit of the candidate identity."""
    if not valid_manifest(candidate):
        return "INVALID_METADATA", current
    if not native_ready or not any(
        record["id"] == "discord-startup"
        and record["issue"] == "GB-T12.MVP1"
        and record["level"] == "real-discord"
        and record["revision"] == candidate["revision"]
        and record["result"] == "pass"
        for record in candidate["evidence"]
    ):
        return "PREREQUISITE_UNAVAILABLE", current
    if current != expected_prior:
        return "PREVIOUS_PUBLICATION_CHANGED", current
    if interruption == "before":
        return "PUBLICATION_INTERRUPTED", current

    current = {field: candidate[field] for field in IDENTITY}
    if interruption == "after":
        return "PUBLICATION_UNKNOWN", current
    return "PUBLISHED", current


class ReleaseContractScenarios(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"),
                                  object_pairs_hook=strict_object)

    def test_fixture_scenarios(self):
        prior = deepcopy(self.fixture["prior"])
        for scenario in self.fixture["scenarios"]:
            with self.subTest(scenario=scenario["id"]):
                candidate = deepcopy(self.fixture["candidate"])
                candidate.update(scenario.get("candidatePatch", {}))
                if "recordPatch" in scenario:
                    candidate["evidence"][0].update(scenario["recordPatch"])
                expected_prior = prior if scenario.get("expectedPriorMatches", True) else None
                outcome, visible = attempt(
                    candidate, prior, expected_prior,
                    native_ready=scenario.get("nativeReady", True),
                    interruption=scenario.get("interruption"),
                )
                expected = (
                    {field: candidate[field] for field in IDENTITY}
                    if scenario["current"] == "candidate" else self.fixture["prior"]
                )
                self.assertEqual(outcome, scenario["expected"])
                self.assertEqual(visible, expected)
                self.assertEqual(prior, self.fixture["prior"])

    def test_precommit_retry_and_postcommit_reconciliation(self):
        candidate = self.fixture["candidate"]
        prior = self.fixture["prior"]
        early, current = attempt(candidate, prior, prior, native_ready=True, interruption="before")
        self.assertEqual((early, current), ("PUBLICATION_INTERRUPTED", prior))
        late, current = attempt(candidate, current, prior, native_ready=True, interruption="after")
        self.assertEqual(late, "PUBLICATION_UNKNOWN")
        self.assertEqual(current, {field: candidate[field] for field in IDENTITY})
        # A blind retry cannot replace the complete candidate already visible.
        self.assertEqual(attempt(candidate, current, prior, native_ready=True),
                         ("PREVIOUS_PUBLICATION_CHANGED", current))

    def test_duplicate_evidence_ids_and_input_keys(self):
        candidate = self.fixture["candidate"]
        candidate["evidence"].append(deepcopy(candidate["evidence"][0]))
        self.assertFalse(valid_manifest(candidate))
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            json.loads('{"version": "1.0.0", "version": "2.0.0"}',
                       object_pairs_hook=strict_object)


if __name__ == "__main__":
    unittest.main()
