"""Offline acceptance examples for the GB-T11.S1 v1 candidate."""

import json
from pathlib import Path
import re
import unittest


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "docs/specifications/fixtures/GB-T11-S1-scenarios.json"
)


def unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"duplicate field: {name}")
        result[name] = value
    return result


def edit_verdict(peer, ack_ms, peer_ms):
    if peer == "unknown":
        return "unknown"
    timely_ack = ack_ms is not None and ack_ms <= 1000
    timely_peer = peer_ms is not None and peer_ms <= 1000
    return "good" if timely_ack and (peer == "none" or timely_peer) else "bad"


def probe_verdict(scheduled, success):
    if success > scheduled:
        return "invalid_configuration"
    if scheduled == 0:
        return "undefined"
    return "within_candidate" if 1000 * success >= 995 * scheduled else "breached"


def restore_verdict(backup, preflight, verification, rpo_seconds, rto_seconds):
    if preflight == "unsafe":
        return "denied"
    if preflight == "unavailable" or backup != "verified":
        return "blocked"
    if verification != "complete":
        return "failed"
    if rpo_seconds is None or rto_seconds is None:
        return "undetermined"
    if rpo_seconds > 900 or rto_seconds > 14400:
        return "breached"
    return "within_candidate"


class OperationsContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with FIXTURE.open(encoding="utf-8") as source:
            cls.fixture = json.load(source, object_pairs_hook=unique_object)

    def cases(self, section, fields):
        cases = self.fixture[section]
        self.assertIs(type(cases), list)
        self.assertTrue(1 <= len(cases) <= 32)
        names = set()
        for case in cases:
            self.assertIs(type(case), dict)
            self.assertEqual(set(case), {"case", "expected"} | set(fields))
            self.assertIs(type(case["case"]), str)
            self.assertIsNotNone(re.fullmatch(r"[a-z][a-z0-9_]{0,47}", case["case"]))
            self.assertNotIn(case["case"], names)
            names.add(case["case"])
            yield case

    def bounded_integer(self, value, maximum, nullable=False):
        if nullable and value is None:
            return
        self.assertIs(type(value), int)
        self.assertTrue(0 <= value <= maximum)

    def test_envelope(self):
        self.assertEqual(set(self.fixture), {"schema_version", "log", "alert", "edit", "probe", "reconcile", "recovery"})
        self.assertIs(type(self.fixture["schema_version"]), int)
        self.assertEqual(self.fixture["schema_version"], 1)

    def test_log_field_allowlist(self):
        required = {"schema_version", "utc", "component", "event", "outcome"}
        for case in self.cases("log", {"fields"}):
            with self.subTest(case=case["case"]):
                fields = case["fields"]
                self.assertIs(type(fields), list)
                self.assertTrue(1 <= len(fields) <= 8)
                for field in fields:
                    self.assertIs(type(field), str)
                    self.assertIsNotNone(re.fullmatch(r"[a-z][a-z_]{0,31}", field))
                unique = set(fields)
                allowed = len(unique) == len(fields) and required <= unique <= required | {"correlation"}
                self.assertEqual("allowed" if allowed else "rejected", case["expected"])

    def test_candidate_alert_thresholds(self):
        for case in self.cases("alert", {"eligible", "bad", "complete"}):
            with self.subTest(case=case["case"]):
                for field in ("eligible", "bad", "complete"):
                    self.assertIs(type(case[field]), list)
                    self.assertEqual(len(case[field]), 2)
                for count in case["eligible"] + case["bad"]:
                    self.bounded_integer(count, 300000)
                for complete in case["complete"]:
                    self.assertIs(type(complete), bool)
                windows = list(zip(case["eligible"], case["bad"], case["complete"]))
                if any(bad > eligible for eligible, bad, _ in windows):
                    verdict = "invalid_configuration"
                elif not any(case["complete"]):
                    verdict = "coverage"
                elif all(complete and eligible >= 20 and 20 * bad > eligible
                         for eligible, bad, complete in windows):
                    verdict = "journey"
                else:
                    verdict = "quiet"
                self.assertEqual(verdict, case["expected"])

    def test_first_attempt_deadline_and_fixed_peer(self):
        for case in self.cases("edit", {"peer", "ack_ms", "peer_ms"}):
            with self.subTest(case=case["case"]):
                self.assertIn(case["peer"], {"selected", "none", "unknown"})
                self.bounded_integer(case["ack_ms"], 60000, nullable=True)
                self.bounded_integer(case["peer_ms"], 60000, nullable=True)
                if case["peer"] != "selected":
                    self.assertIsNone(case["peer_ms"])
                self.assertEqual(
                    edit_verdict(case["peer"], case["ack_ms"], case["peer_ms"]), case["expected"]
                )

    def test_probe_denominator_includes_missing(self):
        for case in self.cases("probe", {"scheduled", "success"}):
            with self.subTest(case=case["case"]):
                self.bounded_integer(case["scheduled"], 43200)
                self.bounded_integer(case["success"], 43200)
                self.assertEqual(probe_verdict(case["scheduled"], case["success"]), case["expected"])

    def test_unknown_commit_requires_authorized_matching_receipt(self):
        for case in self.cases("reconcile", {"authorized", "receipt"}):
            with self.subTest(case=case["case"]):
                self.assertIs(type(case["authorized"]), bool)
                self.assertIn(case["receipt"], {"matching", "conflict", "unavailable"})
                settled = case["authorized"] and case["receipt"] == "matching"
                self.assertEqual("settled" if settled else "unknown", case["expected"])

    def test_backup_and_restore_have_independent_verdicts(self):
        fields = {"backup", "preflight", "verification", "rpo_seconds", "rto_seconds"}
        for case in self.cases("recovery", fields):
            with self.subTest(case=case["case"]):
                self.assertIn(case["backup"], {"verified", "interrupted"})
                self.assertIn(case["preflight"], {"isolated", "unsafe", "unavailable"})
                self.assertIn(case["verification"], {"complete", "unstarted", "interrupted", "integrity_failed", "marker_gap"})
                for field in ("rpo_seconds", "rto_seconds"):
                    self.bounded_integer(case[field], 86400, nullable=True)
                    if case["verification"] != "complete":
                        self.assertIsNone(case[field])
                self.assertEqual(
                    restore_verdict(**{field: case[field] for field in fields}), case["expected"]
                )


if __name__ == "__main__":
    unittest.main()
