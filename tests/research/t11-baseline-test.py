"""Research invariants and negative cases; these do not test Guildboard."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("t11_baseline", ROOT / "scripts/research/t11-baseline.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


class BaselineTests(unittest.TestCase):
    def test_underload_has_no_loss_and_service_time_latency(self):
        result = baseline.queue_model(100, 60, 4, 128)
        self.assertEqual(result["offered"], 6000)
        self.assertEqual(result["rejected"], 0)
        self.assertEqual(result["accepted_virtual_latency_ms"]["p99"], 4)

    def test_overload_preserves_accounting_and_bound(self):
        result = baseline.queue_model(1000, 10, 4, 128)
        self.assertGreater(result["rejected"], 0)
        self.assertLessEqual(result["peak_outstanding"], 128)
        self.assertEqual(result["offered"], result["rejected"] + result["accepted_and_eventually_completed"])

    def test_equal_rate_completion_precedes_next_arrival(self):
        for rate, seconds, service in ((100, 60, 10), (1000, 10, 1), (2.5, 4, 400),
                                       (3, 60, 1000 / 3)):
            with self.subTest(rate=rate):
                result = baseline.queue_model(rate, seconds, service, 1)
                self.assertEqual(result["rejected"], 0)
                self.assertEqual(result["accepted_and_eventually_completed"], int(rate * seconds))
                self.assertEqual(result["peak_outstanding"], 1)
                self.assertEqual(result["accepted_virtual_latency_ms"]["p99"], round(service, 6))
                self.assertEqual(result["last_completion_virtual_seconds"], seconds)

    def test_near_capacity_distinguishes_real_overlap_without_tolerance(self):
        under = baseline.queue_model(100, 1, 9.999999999, 1)
        over = baseline.queue_model(100, 1, 10.000000001, 1)
        self.assertEqual(under["rejected"], 0)
        # A one-slot queue cannot accept the next arrival even for a tiny real
        # overlap. Every other request is therefore rejected, not rounded away.
        self.assertEqual(over["accepted_and_eventually_completed"], 50)
        self.assertEqual(over["rejected"], 50)
        self.assertEqual(over["peak_outstanding"], 1)

    def test_decimal_arrival_count_is_not_truncated_by_binary_rounding(self):
        result = baseline.queue_model(0.7, 90, 1, 1)
        self.assertEqual(result["offered"], 63)
        self.assertEqual(result["accepted_and_eventually_completed"], 63)

    def test_invalid_and_unbounded_configs_fail(self):
        for args in [(0, 1, 4, 128), (100, 1, -1, 128), (100, 1, 4, 0),
                     (100, 1, 4, True), (True, 1, 4, 128), (100, "1", 4, 128),
                     (float("nan"), 1, 4, 128), (1000, 1000, 4, 128)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                baseline.queue_model(*args)

    def test_wrong_sequence_fails_even_with_matching_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong-sequence"
            path.write_bytes(baseline.record(1) + baseline.record(0))
            with self.assertRaisesRegex(ValueError, "sequence"):
                baseline.verify(path, baseline.digest(path), 2)

    def test_local_copy_corruption_and_owned_child_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            result = baseline.file_experiment(Path(directory))
        self.assertEqual(result["restored_records"], 300)
        self.assertTrue(result["truncated_copy_rejected"])
        self.assertEqual(result["abrupt_owned_child_exit_code"], 23)
        self.assertEqual(result["abrupt_child_prefix_verified_records"], 32)


if __name__ == "__main__":
    unittest.main()
