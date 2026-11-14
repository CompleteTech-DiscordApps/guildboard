from copy import deepcopy
from dataclasses import replace
from itertools import permutations
import unittest
from model import Board, Change, Command, Context, Replica


def command(op="op-A", element="A", value=1, expected=0, **kwargs):
    return Command(op, (Change(element, expected, value),), **kwargs)


class Experiment(unittest.TestCase):
    def test_whole_document_last_write_wins_loses_independent_edit(self):
        initial = {"A": 0, "B": 0}
        left, right = initial | {"A": 1}, initial | {"B": 2}
        for first, last in ((left, right), (right, left)):
            state = deepcopy(first)
            state = deepcopy(last)  # Deliberately rejected naive comparator.
            self.assertNotEqual(state, {"A": 1, "B": 2})

    def test_distinct_elements_all_orders(self):
        for strategy, count in (("board", 1), ("element", 3)):
            for schedule in permutations([command(k, k, i) for i, k in enumerate("ABC", 1)]):
                board = Board(strategy)
                outcomes = [board.submit(Context(), c)[0] for c in schedule]
                self.assertEqual(outcomes.count("ACCEPTED"), count)
                self.assertEqual(board.revision, count)
                if strategy == "element":
                    self.assertEqual(board.elements, {k: (1, i) for i, k in enumerate("ABC", 1)})

    def test_same_element_conflict_all_orders(self):
        for schedule in permutations([command("first", value=1), command("second", value=2)]):
            b = Board()
            self.assertEqual([b.submit(Context(), c)[0] for c in schedule], ["ACCEPTED", "CONFLICT"])
            self.assertEqual(b.elements["A"], (1, schedule[0].changes[0].value))

    def test_atomic_compound_rolls_back_first_valid_change(self):
        b = Board()
        before = b.observable()
        c = Command("compound", (Change("A", 0, 1), Change("B", 7, 2)))
        self.assertEqual(b.submit(Context(), c)[0], "CONFLICT")
        self.assertEqual(before, b.observable())

    def test_compound_success_one_revision(self):
        b = Board()
        self.assertEqual(b.submit(Context(), Command("c", (Change("A", 0, 1), Change("B", 0, 2)))), ("ACCEPTED", 1))
        self.assertEqual(len(b.events), 1)
        self.assertEqual(b.elements["B"], (1, 2))

    def test_idempotency_unknown_commit_retry(self):
        for crash, prior_revision in (("before_commit", 0), ("after_commit", 1)):
            b, c = Board(), command()
            self.assertEqual(b.submit(Context(), c, crash), ("UNKNOWN", None))
            self.assertEqual(b.revision, prior_revision)
            self.assertEqual(b.submit(Context(), c), ("ACCEPTED", 1))
            self.assertEqual(b.submit(Context(), c), ("ACCEPTED", 1))
            self.assertEqual(len(b.events), 1)
            self.assertEqual(b.submit(Context(), replace(c, changes=(Change("A", 0, 2),)))[0], "IDEMPOTENCY_CONFLICT")

    def test_scoped_actor_identity(self):
        b = Board()
        b.submit(Context(), command())
        self.assertEqual(b.submit(Context(actor="actor-B"), command(element="B")), ("ACCEPTED", 2))

    def test_auth_denials_no_side_effects(self):
        for ctx, cmd, code in [
            (Context(session_valid=False), command(), "UNAUTHENTICATED"),
            (Context(guild="foreign"), command(), "NOT_FOUND"),
            (Context(), command(board="foreign"), "NOT_FOUND"),
            (Context(), command(guild="foreign"), "NOT_FOUND"),
            (Context(readable=False), command(), "NOT_FOUND"),
            (Context(writable=False), command(), "FORBIDDEN"),
        ]:
            b = Board(); before = b.observable()
            self.assertEqual(b.submit(ctx, cmd)[0], code)
            self.assertEqual(before, b.observable())

    def test_serialized_revoke_schedules_and_receipt(self):
        b, c = Board(), command()
        b.revoke()
        self.assertEqual(b.submit(Context(), c)[0], "POLICY_STALE")
        self.assertEqual(b.revision, 0)
        b = Board()
        self.assertEqual(b.submit(Context(), c), ("ACCEPTED", 1))
        b.revoke()
        self.assertEqual(b.submit(Context(writable=False), c), ("ACCEPTED", 1))
        self.assertEqual(b.submit(Context(readable=False), c)[0], "NOT_FOUND")
        self.assertEqual(b.revision, 1)

    def test_restore_retains_historical_unknown_outcome_without_reapplying(self):
        b = Board()
        b.submit(Context(), command("first", element="B"))
        c = command("lost-ack", base=1)
        self.assertEqual(b.submit(Context(), c, "after_commit"), ("UNKNOWN", None))
        b.restore()
        before = b.observable()
        # The old base exceeds the restored revision, but an existing receipt
        # settles history without replaying content or requiring write access.
        self.assertEqual(b.submit(Context(writable=False), c), ("ACCEPTED", 2))
        self.assertEqual(b.observable(), before)
        self.assertEqual(b.elements["A"], (0, 0))
        self.assertEqual(b.events, [])
        self.assertEqual(b.submit(Context(), replace(c, changes=(Change("A", 0, 2),)))[0],
                         "IDEMPOTENCY_CONFLICT")
        self.assertEqual(b.observable(), before)

    def test_restore_fences_uncommitted_and_foreign_receipt_retries(self):
        b, c = Board(), command()
        b.submit(Context(), c, "after_commit")
        b.restore()
        before = b.observable()
        for ctx, cmd, code in [
            (Context(), command("never-committed"), "LINEAGE_CHANGED"),
            (Context(actor="actor-B"), c, "LINEAGE_CHANGED"),
            (Context(session_valid=False), c, "UNAUTHENTICATED"),
            (Context(readable=False), c, "NOT_FOUND"),
            (Context(guild="foreign"), c, "NOT_FOUND"),
            (Context(), replace(c, board="foreign"), "NOT_FOUND"),
        ]:
            with self.subTest(code=code, ctx=ctx):
                self.assertEqual(b.submit(ctx, cmd)[0], code)
                self.assertEqual(b.observable(), before)
        # The same operation ID in the new lineage is independent history.
        self.assertEqual(b.submit(Context(), replace(c, lineage=b.lineage)), ("ACCEPTED", 1))
        self.assertEqual(len(b.receipts), 2)

    def test_delete_tombstone_stale_undo_no_resurrection(self):
        b = Board(); b.submit(Context(), command(value=None))
        before = b.observable()
        for expected in (0, 1):
            self.assertEqual(b.submit(Context(), command("undo", expected=expected))[0], "CONFLICT")
        self.assertEqual(before, b.observable())

    def test_duplicate_invalid_and_oversized_compounds(self):
        for changes in [(), (Change("A", 0, 1),) * 2,
                        tuple(Change(str(i), 0, 1) for i in range(101)),
                        (Change("A", 0, True),), (Change("A", 0, 1000001),)]:
            b = Board(); before = b.observable()
            self.assertEqual(b.submit(Context(), Command("bad", changes))[0], "INVALID")
            self.assertEqual(before, b.observable())

    def test_replay_all_720_duplicate_and_reorder_schedules(self):
        b = Board()
        for key in "ABC": b.submit(Context(), command(key, key))
        for schedule in permutations(b.events * 2):
            replica = Replica()
            for event in schedule: replica.deliver(event)
            self.assertEqual(replica.elements, b.elements)
            self.assertEqual(replica.revision, 3)
            self.assertEqual(replica.pending, {})

    def test_gap_and_bounded_overflow_require_recovery(self):
        r = Replica()
        for rev in (2, 3, 4):
            self.assertEqual(r.deliver({"lineage": r.lineage, "revision": rev, "changes": {}}), "GAP")
        self.assertEqual(r.revision, 0)
        before = deepcopy(r.__dict__)
        self.assertEqual(r.deliver({"lineage": r.lineage, "revision": 5, "changes": {}}), "SNAPSHOT_REQUIRED")
        self.assertEqual(len(r.pending), 3)
        self.assertEqual(r.__dict__, before)
        self.assertEqual(r.deliver({"lineage": r.lineage, "revision": 2, "changes": {}}), "GAP")
        self.assertEqual(r.__dict__, before)
        self.assertEqual(r.deliver({"lineage": "old", "revision": 1, "changes": {}}), "SNAPSHOT_REQUIRED")
        self.assertEqual(r.__dict__, before)

    def test_full_buffer_applies_gap_closing_revision_and_drains_all_orders(self):
        events = {rev: {"lineage": "lineage-A", "revision": rev,
                        "changes": {"A": (rev, rev)}} for rev in range(1, 5)}
        regression = (2, 3, 4, 1)
        schedules = [regression] + [order for order in permutations(range(1, 5))
                                    if order != regression]
        for order in schedules:
            with self.subTest(order=order):
                r = Replica()
                for rev in order:
                    self.assertIn(r.deliver(events[rev]), ("APPLIED", "GAP"))
                    self.assertLessEqual(len(r.pending), 3)
                self.assertEqual(r.revision, 4)
                self.assertEqual(r.elements, {"A": (4, 4), "B": (0, 0), "C": (0, 0)})
                self.assertEqual(r.pending, {})
                for rev in order:
                    self.assertEqual(r.deliver(events[rev]), "DUPLICATE")

    def test_conflicting_pending_event_detected(self):
        r = Replica(); e = {"lineage": r.lineage, "revision": 2, "changes": {}}
        r.deliver(e); changed = deepcopy(e); changed["changes"] = {"A": (1, 9)}
        self.assertEqual(r.deliver(changed), "INCONSISTENT_EVENT")


if __name__ == "__main__": unittest.main()
