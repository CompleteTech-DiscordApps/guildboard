"""Deterministic finite cases for the separately versioned release experiment."""

from dataclasses import replace
from pathlib import Path
import runpy
import unittest

M = runpy.run_path(str(Path(__file__).resolve().parents[2] /
                      "scripts/research/t2_release_model.py"))
Authority, Effects, Public = M["Authority"], M["Effects"], M["Public"]
prepare, release, invalidate = M["prepare"], M["release"], M["invalidate"]
commit_once, released_count = M["commit_once"], M["released_count"]


class ReleaseResearchTests(unittest.TestCase):
    def test_allowed_release_and_writable_positive_controls(self):
        for kind in M["KINDS"]:
            with self.subTest(kind=kind):
                s = prepare(kind)
                self.assertEqual(s.emitted, ())
                expected = s.queue
                before = s.effects
                while s.queue:
                    s = release(s)
                self.assertEqual(tuple(x.packet for x in s.emitted), expected)
                self.assertEqual(s.effects, before)
        self.assertEqual(prepare("prepared_ack").effects, Effects(1, 1, 1, 1))

    def test_every_invalidation_at_every_release_cut(self):
        for kind in M["KINDS"]:
            prepared = prepare(kind)
            for loss in M["LOSSES"]:
                for cut in range(len(prepared.queue) + 1):
                    with self.subTest(kind=kind, loss=loss, cut=cut):
                        s = prepared
                        for _ in range(cut):
                            s = release(s)
                        visible = s.emitted
                        s = invalidate(s, loss)
                        denied = release(s)
                        self.assertEqual(denied.effects, prepared.effects)
                        self.assertEqual(denied.committed, prepared.committed)
                        self.assertEqual(denied.emitted[:cut], visible)
                        self.assertEqual(released_count(denied), cut)
                        self.assertFalse(denied.queue)
                        if s.queue:
                            self.assertEqual(denied.emitted[-1],
                                             Public(M["read_error"](s.authority)))
                            self.assertIsNone(denied.emitted[-1].packet)
                        self.assertIs(release(denied), denied)

    def test_release_denial_is_independent_of_receipt_or_digest_result(self):
        for loss in M["LOSSES"]:
            public = []
            for kind in M["KINDS"]:
                s = invalidate(prepare(kind), loss)
                public.append(release(s).emitted)
            self.assertTrue(all(item == public[0] for item in public))

    def test_initial_denial_reveals_no_receipt_or_digest_result(self):
        for changes, expected in (({"scoped": False}, "NOT_FOUND"),
                                  ({"session_live": False}, "UNAUTHENTICATED"),
                                  ({"member": False}, "FORBIDDEN"),
                                  ({"can_read": False}, "FORBIDDEN"),
                                  ({"time_known": False}, "DEPENDENCY_UNAVAILABLE"),
                                  ({"policy_known": False}, "DEPENDENCY_UNAVAILABLE")):
            for kind in M["KINDS"]:
                with self.subTest(changes=changes, kind=kind):
                    s = prepare(kind, replace(Authority(), **changes))
                    self.assertEqual(s.emitted, (Public(expected),))
                    self.assertEqual(s.queue, ())
                    # Pre-existing effects persist; a denied new ACK commits none.
                    self.assertEqual(s.effects, Effects(1, 1, 1, 1) if kind in
                                     ("retained_receipt", "digest_conflict") else Effects())

    def test_expiry_boundaries_and_missing_trust_fail_closed(self):
        for field in ("session_until", "evidence_until"):
            a = Authority(session_until=9, evidence_until=9)
            a = replace(a, **{field: 3}, now=2)
            self.assertIsNone(M["read_error"](a))
            self.assertIsNotNone(M["read_error"](replace(a, now=3)))
        for field in ("time_known", "policy_known"):
            self.assertEqual(M["read_error"](replace(Authority(), **{field: False})),
                             "DEPENDENCY_UNAVAILABLE")

    def test_commit_before_revoke_survives_suppressed_ack_and_retry(self):
        s = prepare("prepared_ack")
        denied = release(invalidate(s, "session_revoke"))
        self.assertTrue(denied.committed)
        self.assertEqual(denied.effects, Effects(1, 1, 1, 1))
        # Explicitly restored trusted read authority, still without write rights.
        recovered = replace(denied, authority=Authority(can_write=False, generation=1))
        status, retried = commit_once(recovered, 0)
        self.assertEqual(status, "retained_receipt")
        self.assertEqual(retried.effects, denied.effects)
        self.assertEqual(retried.emitted, denied.emitted)

    def test_revoke_before_write_denies_without_effects(self):
        initial = M["State"]()
        for s in (invalidate(initial, "session_revoke"),
                  replace(initial, authority=Authority(generation=1)),
                  replace(initial, authority=Authority(can_write=False))):
            status, after = commit_once(s, 0)
            self.assertNotEqual(status, "committed")
            self.assertIs(after, s)
            self.assertEqual(after.effects, Effects())

    def test_write_permission_loss_allows_retained_read_without_duplication(self):
        for kind in ("retained_receipt", "digest_conflict"):
            s = prepare(kind, Authority(can_write=False, generation=1))
            after = release(s)
            self.assertEqual(released_count(after), 1)
            self.assertEqual(after.effects, Effects(1, 1, 1, 1))

    def test_stale_initial_only_control_exposes_protected_packets(self):
        for kind in M["KINDS"]:
            for loss in M["LOSSES"]:
                s = invalidate(prepare(kind), loss)
                self.assertEqual(released_count(release(s)), 0)
                self.assertEqual(released_count(M["stale_initial_only_control"](s)), 1)

    def test_finite_report_counts_and_determinism(self):
        d = M["experiment"]()
        self.assertEqual(d["enumerated_schedules"], 70)
        self.assertEqual(d["denied_release_points"], 42)
        self.assertEqual(d["fully_released_before_loss"], 28)
        self.assertEqual(d["previously_released_packets_preserved"], 63)
        self.assertEqual(d["candidate_protected_packets_after_loss"], 0)
        self.assertEqual(d["stale_initial_only_protected_packets_after_loss"], 42)
        self.assertEqual(d["release_changed_committed_effects"], 0)
        self.assertEqual(d, M["experiment"]())


if __name__ == "__main__":
    unittest.main()
