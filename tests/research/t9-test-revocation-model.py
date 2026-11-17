"""Test the finite threat-research experiment, never production authorization."""

from dataclasses import replace
from pathlib import Path
import runpy
import unittest


MODEL = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / "scripts/research/t9-revocation-model.py")
)
State, step = MODEL["State"], MODEL["step"]
run_trace, experiment = MODEL["run_trace"], MODEL["experiment"]


class RevocationResearchTests(unittest.TestCase):
    def test_no_prepared_authority_never_commits(self):
        for fenced in (False, True):
            self.assertEqual(step(State(), "commit", fenced=fenced).accepted, 0)

    def test_current_authority_commits_once(self):
        rows = run_trace(("prepare", "commit", "commit"), fenced=True)
        self.assertEqual([r["after"]["accepted"] for r in rows], [0, 1, 1])

    def test_negative_control_exhibits_revocation_bug(self):
        rows = run_trace(("prepare", "revoke", "commit"), fenced=False)
        self.assertFalse(rows[-1]["before"]["can_write"])
        self.assertEqual(rows[-1]["after"]["accepted"], 1)

    def test_fence_rejects_revoked_preparation(self):
        rows = run_trace(("prepare", "revoke", "commit"), fenced=True)
        self.assertEqual(rows[-1]["after"]["accepted"], 0)

    def test_regrant_does_not_resurrect_old_preparation(self):
        rows = run_trace(("prepare", "revoke", "grant", "commit"), fenced=True)
        self.assertTrue(rows[-1]["before"]["can_write"])
        self.assertEqual(rows[-1]["after"]["accepted"], 0)

    def test_fresh_preparation_after_regrant_can_commit(self):
        rows = run_trace(("revoke", "grant", "prepare", "commit"), fenced=True)
        self.assertEqual(rows[-1]["after"]["accepted"], 1)

    def test_denied_commit_changes_no_authority_or_content_counter(self):
        before = State(generation=2, prepared_generation=0, accepted=9)
        after = step(before, "commit", fenced=True)
        self.assertEqual(after, replace(before, prepared_generation=None))
        self.assertEqual(before.accepted, 9)

    def test_enumeration_has_positive_and_negative_controls(self):
        report = experiment()
        self.assertEqual(report["histories_per_design"], sum(4**n for n in range(1, 6)))
        self.assertEqual(report["histories_per_design"], 1364)
        self.assertGreater(report["stale_or_revoked_commits"]["prepare_only"], 0)
        self.assertEqual(report["stale_or_revoked_commits"]["commit_fence"], 0)
        self.assertEqual(report, experiment())


if __name__ == "__main__":
    unittest.main()
