"""Test oracle sensitivity, reproducibility and honest matrix evidence boundaries."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/research" / (name + ".py"))
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


schedule = module("t12-schedule-experiment")
matrix = module("t12-validate-matrix")


class SchedulingTests(unittest.TestCase):
    def test_all_small_schedules_and_recovery_cuts(self):
        result = schedule.experiment()
        self.assertEqual(result["schedules"], 140)
        self.assertEqual(result["recovery_boundaries"], 980)
        self.assertEqual(sum(result["accepted_event_count_distribution"].values()), 140)
        self.assertEqual(len(result["unsafe_controls_detected"]), 5)
        self.assertEqual(result["seeded_steps"], 1536)

    def test_stale_prepared_authority_control_is_caught(self):
        order = ("a.prepare", "revoke", "a.commit", "a.ack")
        self.assertEqual(schedule.schedule_trial(order), 0)
        with self.assertRaisesRegex(schedule.InvariantViolation, "stale authority"):
            schedule.schedule_trial(order, "prepare-only-authority")

    def test_duplicate_and_restore_keep_historical_receipts(self):
        result = schedule.special_trials()
        self.assertEqual(result["accepted_events"], 2)
        self.assertEqual(result["restored_content"], {})
        self.assertEqual(result["lost_ack_retry"], "receipt")

    def test_foreign_and_split_controls_are_caught(self):
        for defect in ("foreign-scope", "split-commit", "base-before-receipt"):
            with self.subTest(defect=defect), self.assertRaises(schedule.InvariantViolation):
                schedule.special_trials(defect)

    def test_read_deny_precedes_retained_receipt(self):
        model = schedule.Model()
        command = model.prepare("a", "one")
        model.commit(command)
        before = model.durable()
        model.can_read = False
        self.assertEqual(model.commit(command), ("read-denied", None))
        model.can_read = True
        self.assertEqual(model.durable(), before)

    def test_restore_retained_receipt_precedes_current_write_fence(self):
        model = schedule.Model()
        command = model.prepare("a", "one")
        model.commit(command)
        model.restore()
        model.revoke()
        before = model.durable()
        self.assertEqual(model.commit(command), ("receipt", 1))
        self.assertEqual(model.content, {})
        self.assertEqual(model.durable(), before)

    def test_restore_changed_digest_conflicts_without_reapplying_content(self):
        model = schedule.Model()
        command = model.prepare("a", "one")
        model.commit(command)
        model.restore()
        before = model.durable()
        self.assertEqual(model.commit(schedule.replace(command, value="different")), ("digest-conflict", None))
        self.assertEqual(model.durable(), before)

    def test_restore_unknown_old_lineage_and_unreadable_receipt_are_denied(self):
        model = schedule.Model()
        command = model.prepare("a", "one")
        model.commit(command)
        model.restore()
        before = model.durable()
        self.assertEqual(model.commit(schedule.replace(command, operation="unknown")), ("lineage-denied", None))
        self.assertEqual(model.durable(), before)
        model.can_read = False
        before = model.durable()
        self.assertEqual(model.commit(command), ("read-denied", None))
        self.assertEqual(model.durable(), before)

    def test_expiry_boundary_uses_injected_server_clock(self):
        self.assertEqual(schedule.clock_trial()["first_denied_tick"], 5)

    def test_foreign_board_and_tenant_denials_leave_no_effect(self):
        for field, value in (("board", "foreign"), ("tenant", "foreign")):
            model = schedule.Model()
            command = schedule.replace(model.prepare("a", "one"), **{field: value})
            before = model.durable()
            self.assertEqual(model.commit(command)[0], "scope-denied")
            self.assertEqual(model.durable(), before)

    def test_bounded_seed_inputs(self):
        for seed, steps in ((-1, 48), (32, 48), (True, 48), (0, 49), (0, 0)):
            with self.assertRaises(schedule.InvariantViolation):
                schedule.seeded_trial(seed, steps)

    def test_replay_output_is_byte_identical(self):
        command = [sys.executable, str(ROOT / "scripts/research/t12-schedule-experiment.py")]
        first = subprocess.run(command, check=True, capture_output=True, timeout=15)
        second = subprocess.run(command, check=True, capture_output=True, timeout=15)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first.stderr, b"")
        self.assertFalse(json.loads(first.stdout)["runtime_or_platform_acceptance"])


class MatrixTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(matrix.DEFAULT.read_text(encoding="utf-8"))

    def test_offered_load_arithmetic_and_pending_external_rows(self):
        result = matrix.validate(self.data)
        baseline = next(row for row in result["load"] if row["id"] == "baseline")
        self.assertEqual(baseline["connected_clients"], 120)
        self.assertEqual(baseline["offered_operations_per_second"], 96)
        self.assertEqual(baseline["offered_operations_total"], 86400)
        self.assertEqual(baseline["peer_fanout_payload_bytes_per_second"], 1867776)
        self.assertIsNone(baseline["measured_throughput"])
        self.assertEqual(result["external_not_run"], 10)

    def test_invalid_oversized_and_noninteger_loads_fail(self):
        for bad in (0, -1, 11, True, 1.1, "3"):
            data = deepcopy(self.data)
            data["load_profiles"][0]["guilds"] = bad
            with self.assertRaises(ValueError):
                matrix.validate(data)

    def test_duplicate_profile_and_impossible_percentiles_fail(self):
        data = deepcopy(self.data)
        data["load_profiles"][1]["id"] = data["load_profiles"][0]["id"]
        with self.assertRaises(ValueError):
            matrix.validate(data)
        self.data["budget_candidates"][0]["p95_ms"] = 9999
        with self.assertRaises(ValueError):
            matrix.validate(self.data)

    def test_workload_mix_does_not_hide_missing_arrivals(self):
        self.data["workload_mix_percent"]["modify"] = 69
        with self.assertRaisesRegex(ValueError, "sum to 100"):
            matrix.validate(self.data)

    def test_external_pass_or_incomplete_coverage_cannot_be_laundered(self):
        for mutation in ("pass", "coverage", "evidence", "accessibility"):
            data = deepcopy(self.data)
            if mutation == "pass":
                data["external_rows"][0]["status"] = "passed"
            elif mutation == "coverage":
                data["external_rows"].pop()
            elif mutation == "evidence":
                data["external_rows"][0]["required_evidence"] = []
            else:
                data["accessibility_candidate"]["status"] = "passed"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                matrix.validate(data)


if __name__ == "__main__":
    unittest.main()
