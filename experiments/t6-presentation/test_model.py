import itertools
import unittest
from dataclasses import replace
from model import (Authority, Viewer, Packet, MODES, transition, can_write,
                   admitted, snapshot, follow, unfollow, navigate, receive)


class PresentationResearch(unittest.TestCase):
    def setUp(self):
        self.a, _ = transition(Authority(), 0, control_allowed=True, presenter='alice')
        self.p = Packet(self.a.scope, self.a.epoch, 'alice', 0, (10, 20, 2))
        self.v = follow(Viewer(self.a))

    def test_all_modes_and_trusted_write_inputs_are_independent_of_presenter(self):
        for mode, allowed, valid, scoped, presenter in itertools.product(
                MODES, (False, True), (False, True), (False, True), (None, 'alice')):
            a = replace(self.a, mode=mode, presenter=presenter)
            self.assertEqual(can_write(a, current_t2_write_allowed=allowed,
                                      session_valid=valid, scope_matches=scoped),
                             allowed and valid and scoped and mode != 'locked')

    def test_follow_never_changes_authority_or_personal_view(self):
        v = receive(self.v, self.p)
        self.assertEqual(v.authority, self.a)
        self.assertEqual(v.personal, (0, 0, 1))
        self.assertEqual(unfollow(v).displayed, (0, 0, 1))
        self.assertEqual(follow(v), v)

    def test_navigation_exits_follow_and_rejoin_restores_latest_personal_view(self):
        v = navigate(receive(self.v, self.p), (33, 44, 3))
        self.assertFalse(v.following)
        cached = receive(v, replace(self.p, sequence=1))
        self.assertEqual(cached.displayed, v.displayed)
        self.assertEqual(cached.sequence, 1)
        rejoined = follow(v)
        self.assertEqual(rejoined.displayed, self.p.view)
        self.assertEqual(rejoined.personal, (33, 44, 3))
        self.assertEqual(receive(rejoined, self.p), rejoined)
        v = receive(rejoined, replace(self.p, sequence=1))
        self.assertEqual(unfollow(v).displayed, (33, 44, 3))

    def test_unfollow_rejoin_restores_presenter_without_a_new_packet(self):
        latest = replace(self.p, sequence=10, view=(10, 10, 2))
        v = receive(self.v, latest)
        for _ in range(2):
            personal = unfollow(v)
            self.assertEqual(personal.displayed, personal.personal)
            v = follow(personal)
            self.assertTrue(v.following)
            self.assertEqual(v.displayed, latest.view)
            self.assertEqual(v.personal, (0, 0, 1))
            self.assertEqual(v.sequence, 10)
            self.assertEqual(follow(v), v)
            # A duplicate with a different viewport still cannot overwrite it.
            self.assertEqual(receive(v, replace(latest, view=(99, 99, 1))), v)

    def test_revocation_and_same_presenter_aba_counterexample(self):
        # Alice -> none -> Alice: user-ID-only acceptance wrongly accepts old seq99.
        revoked, _ = transition(self.a, 1, control_allowed=True)
        renewed, _ = transition(revoked, 2, control_allowed=True, presenter='alice')
        old = replace(self.p, sequence=99)
        self.assertEqual(old.sender, renewed.presenter)  # naive gate accepts
        self.assertFalse(admitted(renewed, old, session_valid=True, read_allowed=True))
        v = follow(snapshot(self.v, renewed))
        self.assertEqual(receive(v, old), v)
        new = replace(self.p, epoch=renewed.epoch)
        self.assertEqual(receive(v, new).displayed, new.view)

    def test_each_invalid_publication_is_side_effect_free(self):
        bad = [replace(self.p, scope=('guild-b', 'board-a')),
               replace(self.p, scope=('guild-a', 'board-b')),
               replace(self.p, epoch=True), replace(self.p, epoch=0),
               replace(self.p, sender='mallory'), replace(self.p, sequence=True),
               replace(self.p, sequence=-1), replace(self.p, sequence=2**53),
               *[replace(self.p, view=v) for v in
                 [(float('nan'), 0, 1), (0, float('inf'), 1), (0, 0, 0),
                  (0, 0, 11), (1_000_001, 0, 1), (True, 0, 1), (0, 1)]]]
        for packet in bad:
            self.assertFalse(admitted(self.a, packet, session_valid=True, read_allowed=True))
            self.assertEqual(receive(self.v, packet), self.v)
        for valid, read in [(False, True), (True, False), (False, False)]:
            self.assertFalse(admitted(self.a, self.p, session_valid=valid, read_allowed=read))

    def test_reordered_and_duplicate_packets_converge_without_rewind(self):
        packets = [replace(self.p, sequence=i, view=(i, i, 1)) for i in range(4)]
        for order in itertools.permutations(packets):
            v = self.v
            for packet in order + order:
                before = v.sequence
                v = receive(v, packet)
                self.assertGreaterEqual(v.sequence, before)
            self.assertEqual(v.displayed, (3, 3, 1))

    def test_concurrent_mode_and_presenter_cas_has_one_winner(self):
        changes = [dict(mode='locked'), dict(presenter='bob')]
        for order in itertools.permutations(changes):
            a = self.a
            results = []
            for change in order:
                a, result = transition(a, 1, control_allowed=True, **change)
                results.append(result)
            self.assertEqual(results, ['ok', 'stale-revision'])
            self.assertEqual(a.revision, 2)
            self.assertEqual(a.epoch, 2)

    def test_mode_transition_revokes_stream_and_reconnect_requires_rejoin(self):
        a, _ = transition(self.a, 1, control_allowed=True, mode='open')
        self.assertIsNone(a.presenter)
        v = snapshot(receive(self.v, self.p), a)
        self.assertFalse(v.following)
        self.assertEqual(v.displayed, v.personal)
        self.assertEqual(follow(v), v)
        self.assertEqual(snapshot(v, self.a), v)
        reconnect = snapshot(receive(self.v, self.p), self.a)
        self.assertFalse(reconnect.following)
        other = snapshot(self.v, replace(self.a, scope=('g2', 'b2')))
        self.assertEqual(other.personal, (0, 0, 1))
        self.assertEqual(receive(follow(other), self.p), follow(other))

    def test_invalid_control_has_no_effect(self):
        for kw, expected in [({'control_allowed': False}, 'forbidden'),
                              ({'control_allowed': True, 'mode': 'presentation'}, 'invalid'),
                              ({'control_allowed': True, 'presenter': ''}, 'invalid')]:
            self.assertEqual(transition(self.a, 1, **kw), (self.a, expected))
        self.assertEqual(transition(self.a, 0, control_allowed=True), (self.a, 'stale-revision'))
        self.assertEqual(transition(self.a, True, control_allowed=True), (self.a, 'stale-revision'))

    def test_huge_integer_viewports_are_rejected_without_overflow(self):
        for axis in range(3):
            for huge in (10**400, -(10**400)):
                view = [0, 0, 1]
                view[axis] = huge
                packet = replace(self.p, view=tuple(view))
                self.assertFalse(admitted(self.a, packet, session_valid=True, read_allowed=True))
                self.assertEqual(receive(self.v, packet), self.v)
                self.assertEqual(navigate(self.v, tuple(view)), self.v)

    def test_same_stream_reconnect_preserves_watermark(self):
        latest = replace(self.p, sequence=10, view=(10, 10, 1))
        v = receive(self.v, latest)
        reconnect = snapshot(v, self.a)
        self.assertFalse(reconnect.following)
        self.assertEqual(reconnect.displayed, reconnect.personal)
        rejoined = follow(reconnect)
        self.assertEqual(rejoined.displayed, latest.view)
        self.assertEqual(rejoined.personal, (0, 0, 1))
        self.assertEqual(rejoined.sequence, 10)
        # Previously snapshot reset sequence=-1 and accepted delayed seq1.
        old = replace(self.p, sequence=1, view=(1, 1, 1))
        self.assertEqual(receive(rejoined, old), rejoined)
        self.assertEqual(receive(rejoined, replace(old, sequence=10)), rejoined)
        self.assertEqual(receive(rejoined, replace(old, sequence=11)).sequence, 11)
        renewed, _ = transition(self.a, 1, control_allowed=True, presenter='alice')
        fresh = follow(snapshot(v, renewed))
        self.assertEqual(fresh.sequence, -1)
        self.assertEqual(fresh.displayed, fresh.personal)
        self.assertEqual(receive(fresh, latest), fresh)
        current = replace(self.p, epoch=renewed.epoch)
        fresh = receive(fresh, current)
        self.assertEqual(fresh.sequence, 0)
        self.assertEqual(fresh.displayed, current.view)

    def test_new_scope_starts_empty_and_return_restores_own_stream(self):
        personal = navigate(self.v, (33, 44, 3))
        latest = replace(self.p, sequence=10, view=(10, 10, 2))
        v = receive(follow(personal), latest)
        for scope in [('guild-b', 'board-a'), ('guild-a', 'board-b')]:
            with self.subTest(scope=scope):
                authority = replace(self.a, scope=scope)
                other = follow(snapshot(v, authority))
                self.assertEqual(other.sequence, -1)
                self.assertEqual(other.personal, (0, 0, 1))
                self.assertEqual(other.displayed, other.personal)
                self.assertEqual(receive(other, latest), other)
                returned = follow(snapshot(other, self.a))
                self.assertEqual(returned.sequence, 10)
                self.assertEqual(returned.displayed, latest.view)
                current = replace(self.p, scope=scope)
                other = receive(other, current)
                self.assertEqual(other.sequence, 0)
                self.assertEqual(other.displayed, current.view)

    def test_first_follow_and_rejoin_use_updates_received_while_unfollowed(self):
        latest = replace(self.p, sequence=11, view=(110, 110, 2))
        for initial in (Viewer(self.a), receive(self.v, self.p)):
            with self.subTest(initial=initial):
                personal = navigate(initial, (3, 4, 1))
                updated = receive(personal, latest)
                self.assertEqual(updated.displayed, personal.displayed)
                self.assertEqual(updated.personal, personal.personal)
                self.assertFalse(updated.following)
                self.assertEqual(follow(updated).displayed, latest.view)
                self.assertEqual(updated.sequence, 11)
                self.assertEqual(receive(updated, self.p), updated)
                for bad in (replace(latest, scope=('foreign', 'board')),
                            replace(latest, epoch=0), replace(latest, sender='mallory')):
                    self.assertEqual(receive(updated, bad), updated)

    def test_scope_roundtrip_preserves_replay_fence_without_cross_scope_display(self):
        latest = replace(self.p, sequence=10, view=(10, 10, 2))
        for scope in [('guild-a', 'board-b'), ('guild-b', 'board-a')]:
            v = receive(self.v, latest)
            other = snapshot(v, replace(self.a, scope=scope))
            self.assertEqual(other.displayed, (0, 0, 1))
            returned = snapshot(other, self.a)
            self.assertFalse(returned.following)
            self.assertEqual(returned.displayed, (0, 0, 1))
            self.assertEqual(returned.sequence, 10)
            rejoined = follow(returned)
            self.assertEqual(rejoined.displayed, latest.view)
            self.assertEqual(receive(rejoined, replace(self.p, sequence=1)), rejoined)
            self.assertEqual(receive(rejoined, replace(latest, sequence=11)).sequence, 11)

    def test_scope_history_bound_fails_closed_without_eviction(self):
        v = receive(self.v, replace(self.p, sequence=10))
        for i in range(1, 8):
            v = snapshot(v, replace(self.a, scope=('guild-a', f'board-{i}')))
        before = v
        with self.assertRaisesRegex(ValueError, 'scope history'):
            snapshot(v, replace(self.a, scope=('guild-a', 'overflow')))
        self.assertEqual(v, before)
        returned = follow(snapshot(v, self.a))
        self.assertEqual(returned.sequence, 10)
        self.assertEqual(receive(returned, self.p), returned)

    def test_returned_scope_rejects_stale_authority_and_resets_new_epoch(self):
        newer, _ = transition(self.a, self.a.revision, control_allowed=True, presenter='alice')
        v = receive(follow(Viewer(newer)), replace(self.p, epoch=newer.epoch, sequence=10))
        other = snapshot(v, replace(self.a, scope=('guild-b', 'board-a')))
        self.assertEqual(snapshot(other, self.a), other)
        newest, _ = transition(newer, newer.revision, control_allowed=True, presenter='alice')
        returned = snapshot(other, newest)
        self.assertEqual(returned.sequence, -1)
        self.assertIsNone(returned.presenter_view)
        self.assertEqual(returned.displayed, returned.personal)
        self.assertEqual(receive(returned, replace(self.p, epoch=newer.epoch)), returned)
        updated = receive(returned, replace(self.p, epoch=newest.epoch))
        self.assertEqual(follow(updated).displayed, self.p.view)

    def test_naive_follow_snapshot_overwrites_personal_counterexample(self):
        displayed = receive(self.v, self.p)
        naive_personal_on_second_follow = displayed.displayed
        self.assertNotEqual(naive_personal_on_second_follow, displayed.personal)
        self.assertEqual(unfollow(follow(displayed)).displayed, (0, 0, 1))


if __name__ == '__main__':
    unittest.main()
