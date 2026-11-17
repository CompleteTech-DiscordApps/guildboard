"""Re-run the owned loopback signal tests and retain literal collector output.

Run from the repository root. No public-network requests are made.
"""
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
spec = importlib.util.spec_from_file_location("t12_tests", ROOT / "tests/research/t12-test-experiments.py")
tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tests)
original_popen = tests.subprocess.Popen
launched = 0


def tracked(*args, **kwargs):
    global launched
    process = original_popen(*args, **kwargs)
    name = ("sigterm", "sigint", "normal-cleanup-sigterm", "normal-cleanup-sigint")[launched]
    launched += 1
    communicate = process.communicate

    def recorded(*arguments, **options):
        stdout, stderr = communicate(*arguments, **options)
        (HERE / (name + "-output.json")).write_text(json.dumps({
            "returncode": process.returncode, "stdout": stdout, "stderr": stderr,
        }, indent=2) + "\n", encoding="utf-8")
        return stdout, stderr

    process.communicate = recorded
    return process


tests.subprocess.Popen = tracked
suite = unittest.TestSuite(tests.SourceCaptureRegression(name) for name in (
    "test_sigterm_reaps_owned_workers_and_retains_completed_results",
    "test_sigint_reaps_owned_workers_and_retains_completed_results",
    "test_first_signal_during_normal_cleanup_still_returns_nonzero",
))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
