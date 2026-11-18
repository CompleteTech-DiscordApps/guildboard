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


def restore_verdict(selected, preflight, verification, loss, objectives):
    if preflight == "unsafe":
        return "denied"
    if preflight == "unavailable" or selected is None:
        return "blocked"
    if verification != "complete" or loss in {"at_or_before_cut", "outside_bound", "contradictory"}:
        return "failed"
    if "breached" in objectives:
        return "breached"
    return "undetermined" if loss == "unknown" or "unknown" in objectives else "within_candidate"


def acknowledgment_loss(trial, cut, acknowledgments, recovered):
    if cut is None:
        return "unknown", []
    expected = acknowledgments["identities"]
    present = recovered["identities"]
    covered_through = recovered["covered_through"]
    missing = sorted(item for item in expected - present if item[-1] <= covered_through)
    lost = [list(item) for item in missing]
    evidence = expected | present
    if len(evidence) != len({item[:-1] for item in evidence}) or len(evidence) != len({item[-1] for item in evidence}):
        return "contradictory", lost
    if any(item[-1] <= cut for item in missing):
        return "at_or_before_cut", lost
    if trial["loss_bound"] is not None and any(
        item[-1] - cut > trial["loss_bound"] for item in missing
    ):
        return "outside_bound", lost
    if (trial["loss_bound"] is None
            or acknowledgments["covered_through"] < trial["prefault_high_water"]
            or covered_through < trial["prefault_high_water"]):
        return "unknown", lost
    return ("within_bound" if missing else "none"), lost


def consistent_canary_times(candidates, acknowledged, restored, eligible=None):
    commits_by_position = {}
    positions_by_operation = {}
    operations_by_position = {}
    contradiction = False
    for entry in acknowledged | restored:
        positions_by_operation.setdefault(entry[:-1], set()).add(entry[-1])
        operations_by_position.setdefault((*entry[:3], entry[-1]), set()).add(entry[:-1])
    for operation, position, timestamp in candidates:
        known_positions = positions_by_operation.get(operation, {position})
        known_operations = operations_by_position.get((*operation[:3], position), {operation})
        if known_positions != {position} or known_operations != {operation}:
            contradiction = True
            continue
        if (*operation, position) not in restored:
            continue
        commits_by_position.setdefault(position, set()).add((operation, timestamp))
    times = [timestamp for position, matches in commits_by_position.items() if len(matches) == 1
             for operation, timestamp in matches if eligible is None or (operation, position, timestamp) in eligible]
    return times, contradiction


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

    def synthetic_identity(self, value):
        self.assertIs(type(value), str)
        self.assertIsNotNone(re.fullmatch(r"[a-z][a-z0-9_]{0,47}", value))

    def operation_evidence(self, evidence, scope):
        self.assertEqual(set(evidence), {"board_scope", "coverage", "identities"})
        self.assertIs(type(evidence["board_scope"]), list)
        self.assertEqual(len(evidence["board_scope"]), 2)
        for identity in evidence["board_scope"]:
            self.synthetic_identity(identity)
        self.assertIs(type(evidence["coverage"]), dict)
        self.assertLessEqual(len(evidence["coverage"]), 4)
        for lineage, through in evidence["coverage"].items():
            self.synthetic_identity(lineage)
            self.bounded_integer(through, 100)
        self.assertIs(type(evidence["identities"]), list)
        self.assertLessEqual(len(evidence["identities"]), 16)
        identities = set()
        for item in evidence["identities"]:
            self.assertIs(type(item), list)
            self.assertEqual(len(item), 6)
            for identity in item[:-1]:
                self.synthetic_identity(identity)
            self.bounded_integer(item[-1], 100)
            self.assertNotIn(tuple(item), identities)
            identities.add(tuple(item))
        if tuple(evidence["board_scope"]) != scope[:2]:
            return {"covered_through": -1, "identities": set()}
        return {
            "covered_through": evidence["coverage"].get(scope[2], -1),
            "identities": {item for item in identities if item[:3] == scope},
        }

    def test_backup_and_restore_have_independent_verdicts(self):
        fields = {"generations", "trial", "preflight", "verification", "acknowledgments",
                  "recovered", "fault_second", "canaries", "rto_seconds"}
        for case in self.cases("recovery", fields):
            with self.subTest(case=case["case"]):
                trial = case["trial"]
                self.assertEqual(set(trial), {"guild", "board", "lineage", "prefault_high_water", "loss_bound"})
                scope = (trial["guild"], trial["board"], trial["lineage"])
                for identity in scope:
                    self.synthetic_identity(identity)
                self.bounded_integer(trial["prefault_high_water"], 100)
                self.bounded_integer(trial["loss_bound"], 100, nullable=True)
                generations = case["generations"]
                self.assertIs(type(generations), list)
                self.assertTrue(1 <= len(generations) <= 8)
                generation_ids = set()
                selected = None
                last_sequence = -1
                for generation in generations:
                    self.assertEqual(set(generation), {"id", "sequence", "guild", "board", "lineage", "cut", "status"})
                    self.synthetic_identity(generation["id"])
                    self.assertNotIn(generation["id"], generation_ids)
                    generation_ids.add(generation["id"])
                    self.bounded_integer(generation["sequence"], 100)
                    self.assertGreater(generation["sequence"], last_sequence)
                    last_sequence = generation["sequence"]
                    generation_scope = tuple(generation[name] for name in ("guild", "board", "lineage"))
                    for identity in generation_scope:
                        self.synthetic_identity(identity)
                    self.bounded_integer(generation["cut"], 100)
                    self.assertIn(generation["status"], {"verified", "interrupted"})
                    if (generation["status"] == "verified"
                            and generation_scope == scope
                            and generation["cut"] <= trial["prefault_high_water"]):
                        selected = generation
                attempt = generations[-1]
                cut = selected["cut"] if selected else None
                acknowledgments = self.operation_evidence(case["acknowledgments"], scope)
                recovered = self.operation_evidence(case["recovered"], scope)
                for item in acknowledgments["identities"] | recovered["identities"]:
                    self.assertLessEqual(item[-1], trial["prefault_high_water"])
                loss, missing = acknowledgment_loss(trial, cut, acknowledgments, recovered)
                self.assertIn(case["preflight"], {"isolated", "unsafe", "unavailable"})
                self.assertIn(case["verification"], {
                    "complete", "unstarted", "interrupted", "integrity_failed", "marker_gap",
                })
                self.bounded_integer(case["fault_second"], 86400, nullable=True)
                self.bounded_integer(case["rto_seconds"], 86400, nullable=True)
                self.assertIs(type(case["canaries"]), list)
                self.assertLessEqual(len(case["canaries"]), 8)
                canary_commits = []
                temporally_eligible = set()
                for canary in case["canaries"]:
                    self.assertEqual(set(canary), {"commit_second", "restore_second", "evidence", "operation", "position"})
                    self.bounded_integer(canary["commit_second"], 86400, nullable=True)
                    self.bounded_integer(canary["restore_second"], 86400, nullable=True)
                    self.assertIn(canary["evidence"], {
                        "verified_consistent", "inconsistent", "unverified", "unrestored",
                    })
                    self.assertIs(type(canary["operation"]), list)
                    operation = tuple(canary["operation"])
                    self.assertEqual(len(operation), 5)
                    for identity in operation:
                        self.synthetic_identity(identity)
                    self.bounded_integer(canary["position"], 100)
                    if (cut is not None and operation[:3] == scope
                            and canary["position"] <= cut
                            and canary["evidence"] == "verified_consistent"
                            and canary["commit_second"] is not None):
                        evidence = (operation, canary["position"], canary["commit_second"])
                        canary_commits.append(evidence)
                        if (canary["restore_second"] is not None and case["fault_second"] is not None
                                and canary["commit_second"] < case["fault_second"] <= canary["restore_second"]):
                            temporally_eligible.add(evidence)
                valid_commits, conflicting_canary = consistent_canary_times(
                    canary_commits, acknowledgments["identities"], recovered["identities"], temporally_eligible,
                )
                if conflicting_canary:
                    loss = "contradictory"
                rpo_seconds = case["fault_second"] - max(valid_commits) if valid_commits else None
                outcomes = (objective(rpo_seconds, 900), objective(case["rto_seconds"], 14400))
                self.assertEqual(
                    {"backup": attempt["status"], "attempt": attempt["id"],
                     "selected": selected["id"] if selected else None, "cut": cut,
                     "loss": loss, "missing": missing,
                     "escalate": (case["preflight"] == "unsafe"
                                  or case["verification"] in {"integrity_failed", "marker_gap"}
                                  or loss in {"at_or_before_cut", "outside_bound", "contradictory"}),
                     "rpo_seconds": rpo_seconds,
                     "rto_seconds": case["rto_seconds"], "rpo": outcomes[0], "rto": outcomes[1],
                     "drill": restore_verdict(selected, case["preflight"], case["verification"], loss, outcomes)},
                    case["expected"],
                )

    def test_foreign_inventory_cannot_supply_target_acknowledgment_evidence(self):
        scope = ("guild_a", "board_a", "lineage_a")
        trial = {"guild": scope[0], "board": scope[1], "lineage": scope[2],
                 "prefault_high_water": 10, "loss_bound": 0}
        original = (*scope, "actor_a", "operation_a")
        conflict = (*scope, "actor_a", "operation_b")
        recovered = self.operation_evidence({
            "board_scope": list(scope[:2]), "coverage": {"lineage_a": 10},
            "identities": [[*original, 8]],
        }, scope)
        for foreign_board_scope in (["guild_b", "board_a"], ["guild_a", "board_b"]):
            with self.subTest(board_scope=foreign_board_scope):
                foreign = self.operation_evidence({
                    "board_scope": foreign_board_scope, "coverage": {"lineage_a": 10},
                    "identities": [[*original, 8], [*conflict, 8]],
                }, scope)
                self.assertEqual(foreign["identities"], set())
                self.assertEqual(acknowledgment_loss(trial, 10, foreign, recovered), ("unknown", []))
                self.assertEqual(acknowledgment_loss(trial, 10, recovered, foreign), ("unknown", []))
                self.assertEqual(consistent_canary_times([(original, 8, 5)],
                                                          foreign["identities"], recovered["identities"]),
                                 ([5], False))

    def test_conflicting_operation_positions_cannot_prove_recovery_or_rpo(self):
        trial = {"guild": "guild_a", "board": "board_a", "lineage": "lineage_a",
                 "prefault_high_water": 10, "loss_bound": 0}
        scope = ("guild_a", "board_a", "lineage_a")
        original = (*scope, "actor_a", "operation_a")
        other = (*scope, "actor_a", "operation_b")
        for operation, position in ((other, 8), (original, 9)):
            with self.subTest(operation=operation, position=position):
                identities = {(*original, 8), (*operation, position)}
                inventory = {"covered_through": 10, "identities": identities}
                self.assertEqual(acknowledgment_loss(trial, 10, inventory, inventory), ("contradictory", []))
                self.assertEqual(consistent_canary_times([(original, 8, 5), (operation, position, 9)],
                                                          identities, identities), ([], True))
        evidence = {(*original, 8)}
        self.assertEqual(consistent_canary_times([(original, 8, 5)], evidence, evidence), ([5], False))
        self.assertEqual(consistent_canary_times([(original, 8, 5)], evidence, set()), ([], False))
        for contradicts in ((other, 8, 9), (original, 9, 9)):
            self.assertEqual(consistent_canary_times([contradicts], evidence, evidence), ([], True))

    def test_canary_timestamp_consistency_precedes_temporal_eligibility(self):
        original = ("guild_a", "board_a", "lineage_a", "actor_a", "operation_a")
        next_operation = (*original[:4], "operation_b")
        source = {(*original, 8)}
        pre_fault = (original, 8, 5)
        earlier = (original, 8, 4)
        self.assertEqual(consistent_canary_times([pre_fault, earlier], source, source, {pre_fault, earlier}),
                         ([], False))
        self.assertEqual(consistent_canary_times([pre_fault, (original, 8, 11)], source, source, {pre_fault}),
                         ([], False))
        self.assertEqual(consistent_canary_times([pre_fault, (next_operation, 9, 11)], source, source, {pre_fault}),
                         ([5], False))

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
        fields = {"active", "evidence", "approved_source", "signal", "approved", "sufficient", "observed_second",
                  "last_breach_second", "evaluated_second", "freshness_seconds", "integrity_recovery"}
        cohorts = {"board_open": {"all", "cold", "warm", "unknown"},
                   "edit": {"all", "solo", "collaborative", "unknown"},
                   "probe": {"all"}, "none": {"none"}}
        applicable = {
            "journey_objective": {"board_open", "edit", "probe"},
            "fast_probe": {"probe"}, "fast_journey": {"board_open", "edit"},
            "coverage": {"board_open", "edit", "probe"},
            "capacity": {"board_open", "edit", "none"},
        }
        integrity_fields = {"responder_acknowledged", "isolated_rehearsal_verified", "loss_disposition_recorded"}
        rules = set()
        for case in self.cases("alert_recovery", fields):
            with self.subTest(case=case["case"]):
                scope_fields = {"deployment", "rule", "profile", "journey", "cohort"}
                for scope in (case["active"], case["evidence"]):
                    self.assertEqual(set(scope) - {"source"}, scope_fields)
                    for value in scope.values():
                        self.synthetic_identity(value)
                    self.assertIn(scope["rule"], signals)
                    self.assertIn(scope["journey"], cohorts)
                    self.assertIn(scope["cohort"], cohorts[scope["journey"]])
                self.assertEqual(set(case["active"]), scope_fields)
                self.assertEqual(set(case["evidence"]), scope_fields | {"source"})
                self.synthetic_identity(case["approved_source"])
                rule = case["active"]["rule"]
                integrity = case["integrity_recovery"]
                if rule == "backup_integrity":
                    self.assertEqual(set(integrity), integrity_fields)
                    self.assertTrue(all(type(value) is bool for value in integrity.values()))
                else:
                    self.assertIsNone(integrity)
                self.assertIn(case["signal"], set(signals.values()) | {None})
                for field in ("approved", "sufficient"):
                    self.assertIs(type(case[field]), bool)
                for field in ("last_breach_second", "evaluated_second", "freshness_seconds"):
                    self.bounded_integer(case[field], 86400)
                observed = case["observed_second"]
                self.bounded_integer(observed, 86400, nullable=True)
                clear = (
                    case["approved"] and case["sufficient"] and case["signal"] == signals[rule]
                    and case["active"]["journey"] in applicable.get(rule, {"none"})
                    and all(case["active"][key] == case["evidence"][key] for key in scope_fields)
                    and case["evidence"]["source"] == case["approved_source"]
                    and (integrity is None or all(integrity.values()))
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
