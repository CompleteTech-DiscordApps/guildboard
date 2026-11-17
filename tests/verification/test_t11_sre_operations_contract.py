"""Offline acceptance examples for the GB-T11.S1 v1 candidate."""

from datetime import datetime
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


def objective(seconds, limit):
    if seconds is None:
        return "unknown"
    return "breached" if seconds > limit else "within_candidate"


def restore_verdict(backup, preflight, verification, objectives):
    if preflight == "unsafe":
        return "denied"
    if preflight == "unavailable" or backup != "verified":
        return "blocked"
    if verification != "complete":
        return "failed"
    if "breached" in objectives:
        return "breached"
    return "undetermined" if "unknown" in objectives else "within_candidate"


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
        self.assertEqual(set(self.fixture), {"schema_version", "log", "alert", "edit", "probe", "reconcile", "recovery",
                                            "eligibility", "alert_recovery", "configuration", "privacy"})
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

    def test_edit_eligibility_and_dependency_accounting(self):
        fields = {"authorization", "dependency_available", "observation"}
        for case in self.cases("eligibility", fields):
            with self.subTest(case=case["case"]):
                authority = case["authorization"]
                self.assertIn(authority, {"allowed", "denied", "unknown"})
                self.assertIs(type(case["dependency_available"]), bool)
                self.assertIn(case["observation"], {"good", "unknown", "unavailable"})
                if authority == "denied":
                    outcome = "excluded_denied"
                elif authority == "unknown":
                    outcome = "unknown_eligibility"
                elif not case["dependency_available"]:
                    outcome = "bad"
                else:
                    outcome = case["observation"]
                eligible = int(outcome in {"good", "bad", "unknown"})
                self.assertEqual(
                    {"outcome": outcome, "eligible": eligible,
                     "unknown_eligibility": int(outcome == "unknown_eligibility")},
                    case["expected"],
                )

    def test_unknown_commit_requires_authorized_lookup_and_serialized_release(self):
        fields = {"lookup_read", "release_read", "write", "receipt", "lineage", "cut_validated"}
        for case in self.cases("reconcile", fields):
            with self.subTest(case=case["case"]):
                for field in ("lookup_read", "release_read", "write"):
                    self.assertIn(case[field], {"allowed", "denied", "unknown"})
                self.assertIn(case["receipt"], {
                    "matching", "conflict", "unavailable", "no_match", "nonrecoverable",
                })
                self.assertIn(case["lineage"], {"active", "retired"})
                self.assertIs(type(case["cut_validated"]), bool)
                for field in ("looked_up", "current_saved"):
                    self.assertIs(type(case["expected"][field]), bool)
                for field in ("retransmissions", "mutations", "revisions", "broadcasts"):
                    self.assertIs(type(case["expected"][field]), int)
                looked_up = case["lookup_read"] == "allowed"
                released = "none"
                if looked_up and case["release_read"] == "allowed":
                    released = {"matching": "receipt", "conflict": "conflict"}.get(case["receipt"], "none")
                outcome = {"active": "settled", "retired": "historical_only"}[case["lineage"]]
                self.assertEqual(
                    {"outcome": outcome if released == "receipt" else "unknown",
                     "looked_up": looked_up, "released": released,
                     "current_saved": (released == "receipt" and case["lineage"] == "active"
                                       and case["cut_validated"]),
                     "retransmissions": 0, "mutations": 0, "revisions": 0, "broadcasts": 0},
                    case["expected"],
                )

    def test_backup_and_restore_have_independent_verdicts(self):
        fields = {"backup", "preflight", "verification", "fault_second", "canaries", "rto_seconds"}
        for case in self.cases("recovery", fields):
            with self.subTest(case=case["case"]):
                self.assertIn(case["backup"], {"verified", "interrupted"})
                self.assertIn(case["preflight"], {"isolated", "unsafe", "unavailable"})
                self.assertIn(case["verification"], {
                    "complete", "unstarted", "interrupted", "integrity_failed", "marker_gap",
                })
                self.bounded_integer(case["fault_second"], 86400, nullable=True)
                self.bounded_integer(case["rto_seconds"], 86400, nullable=True)
                self.assertIs(type(case["canaries"]), list)
                self.assertLessEqual(len(case["canaries"]), 8)
                valid_commits = []
                for canary in case["canaries"]:
                    self.assertEqual(set(canary), {"commit_second", "restore_second", "evidence"})
                    self.bounded_integer(canary["commit_second"], 86400, nullable=True)
                    self.bounded_integer(canary["restore_second"], 86400, nullable=True)
                    self.assertIn(canary["evidence"], {
                        "verified_consistent", "inconsistent", "unverified", "unrestored",
                    })
                    if (canary["evidence"] == "verified_consistent"
                            and canary["restore_second"] is not None
                            and canary["commit_second"] is not None
                            and case["fault_second"] is not None
                            and canary["commit_second"] < case["fault_second"]):
                        valid_commits.append(canary["commit_second"])
                rpo_seconds = case["fault_second"] - max(valid_commits) if valid_commits else None
                outcomes = (objective(rpo_seconds, 900), objective(case["rto_seconds"], 14400))
                self.assertEqual(
                    {"backup": case["backup"], "rpo_seconds": rpo_seconds,
                     "rto_seconds": case["rto_seconds"], "rpo": outcomes[0], "rto": outcomes[1],
                     "drill": restore_verdict(case["backup"], case["preflight"],
                                              case["verification"], outcomes)},
                    case["expected"],
                )

    def test_alert_recovery_requires_fresh_rule_specific_evidence(self):
        signals = {
            "journey_objective": "complete_rolling_window",
            "fast_probe": "successful_probe_run",
            "fast_journey": "complete_healthy_journey_windows",
            "coverage": "observed_coverage_windows",
            "capacity": "healthy_latency_and_resource_windows",
            "queue": "recovered_queue_without_rejections",
            "backup": "timely_verified_backup",
            "backup_integrity": "verified_backup_rehearsal_and_disposition",
            "restart": "verified_restart",
            "disaster": "verified_disaster_rehearsal",
        }
        fields = {"rule", "signal", "approved", "sufficient", "observed_second",
                  "last_breach_second", "evaluated_second", "freshness_seconds"}
        rules = set()
        for case in self.cases("alert_recovery", fields):
            with self.subTest(case=case["case"]):
                rule = case["rule"]
                self.assertIn(rule, signals)
                self.assertIn(case["signal"], set(signals.values()) | {None})
                for field in ("approved", "sufficient"):
                    self.assertIs(type(case[field]), bool)
                for field in ("last_breach_second", "evaluated_second", "freshness_seconds"):
                    self.bounded_integer(case[field], 86400)
                observed = case["observed_second"]
                self.bounded_integer(observed, 86400, nullable=True)
                clear = (
                    case["approved"] and case["sufficient"] and case["signal"] == signals[rule]
                    and observed is not None
                    and case["last_breach_second"] < observed <= case["evaluated_second"]
                    and case["evaluated_second"] - observed <= case["freshness_seconds"]
                )
                if clear:
                    rules.add(rule)
                self.assertEqual("clear" if clear else "open", case["expected"])
        self.assertEqual(rules, set(signals))

    def test_configuration_loss_cannot_override_independent_guard(self):
        fields = {"configured", "enabled", "approved", "window_count", "unsafe_target"}
        for case in self.cases("configuration", fields):
            with self.subTest(case=case["case"]):
                for field in ("configured", "enabled", "approved", "unsafe_target"):
                    self.assertIs(type(case[field]), bool)
                count = case["window_count"]
                diagnostic = None
                if not case["configured"]:
                    diagnostic = "candidate_evaluator"
                elif not case["enabled"]:
                    diagnostic = "enabled"
                elif not case["approved"]:
                    diagnostic = "approval"
                elif type(count) is not int or not 1 <= count <= 32:
                    diagnostic = "window_count"
                self.assertEqual(
                    {"evaluator": "enabled" if diagnostic is None else "coverage_lost",
                     "page_or_clear_allowed": diagnostic is None, "diagnostic": diagnostic,
                     "guard": "deny" if case["unsafe_target"] else "allow"},
                    case["expected"],
                )

    def test_privacy_checks_values_and_finite_dimensions(self):
        fields = {"sink", "field", "value", "origin", "evidence_read"}
        dimensions = {
            "board_open_outcome": {
                "outcome": {"success", "dependency_unavailable"},
                "cohort": {"cold", "warm", "unknown"},
            },
        }
        for case in self.cases("privacy", fields):
            with self.subTest(case=case["case"]):
                sink, field, value, origin = (case[k] for k in ("sink", "field", "value", "origin"))
                self.assertIn(origin, {"server", "client", "synthetic", "production"})
                self.assertIn(sink, {"log", "metric", "restricted"})
                self.assertIs(type(case["evidence_read"]), bool)
                if sink == "metric":
                    self.assertIs(type(value), dict)
                    expected_domains = dimensions.get(field)
                    allowed = (
                        expected_domains is not None and set(value) == set(expected_domains)
                        and all(type(label) is str and label in expected_domains[name]
                                for name, label in value.items())
                    )
                else:
                    self.assertIs(type(value), str)
                    allowed = False
                    if sink == "restricted":
                        allowed = (case["evidence_read"] and field == "canary" and origin == "synthetic"
                                   and re.fullmatch(r"synthetic-[0-9]{4}", value) is not None)
                    elif field == "correlation":
                        allowed = origin == "server" and re.fullmatch(r"[a-f0-9]{32}", value) is not None
                    elif field == "component":
                        allowed = value in {"activity", "api", "bot", "collaboration", "persistence",
                                            "edge", "host", "recovery", "probe"}
                    elif field == "utc" and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value):
                        try:
                            datetime.fromisoformat(value)
                        except ValueError:
                            pass
                        else:
                            allowed = True
                self.assertEqual("allowed" if allowed else "rejected", case["expected"])


if __name__ == "__main__":
    unittest.main()
