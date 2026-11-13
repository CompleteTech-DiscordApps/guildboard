"""Abuse and negative-control tests of hypothetical research policy only."""

from dataclasses import replace
from pathlib import Path
import runpy
import unittest


M = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/research/t2-policy-model.py"))
Facts, Effects = M["Facts"], M["Effects"]
candidate, apply_edit = M["candidate"], M["apply_edit"]


class PolicyResearchTests(unittest.TestCase):
    def deny_without_effects(self, facts, outcome=None):
        before = Effects(7, 7, 7, 7)
        result, after = apply_edit(facts, before)
        self.assertNotEqual(result, "new_write")
        self.assertIs(after, before)
        if outcome:
            self.assertEqual(result, outcome)

    def test_verified_writer_positive_control(self):
        self.assertEqual(apply_edit(Facts(), Effects()), ("new_write", Effects(1, 1, 1, 1)))

    def test_foreign_guild_or_board_ignores_client_admin(self):
        for change in ({"guild_matches": False}, {"board_matches": False}):
            self.deny_without_effects(replace(Facts(client_admin_claim=True), **change), "hidden_resource")

    def test_viewer_baseline_is_not_an_explicit_write_deny(self):
        self.deny_without_effects(Facts(roles=frozenset({"viewer"})))
        self.assertEqual(candidate(Facts(roles=frozenset({"viewer", "writer"}))), "new_write")
        self.assertEqual(candidate(Facts(roles=frozenset({"viewer"}), grant_until=2)), "new_write")

    def test_restriction_and_view_only_override_grants(self):
        for flag in ("restricted", "view_only"):
            self.deny_without_effects(replace(Facts(grant_until=20), **{flag: True}), "hard_edit_denial")

    def test_lockdown_and_mode_override_all_ordinary_edit_paths(self):
        base = Facts(roles=frozenset({"writer", "moderator", "admin"}), moderator_edits=True, grant_until=20)
        self.deny_without_effects(replace(base, lockdown=True), "hard_edit_denial")
        self.deny_without_effects(replace(base, mode_allows_edit=False), "hard_edit_denial")

    def test_moderator_editing_is_explicit_and_admin_is_not_writer(self):
        self.deny_without_effects(Facts(roles=frozenset({"moderator"})))
        self.assertEqual(candidate(Facts(roles=frozenset({"moderator"}), moderator_edits=True)), "new_write")
        self.deny_without_effects(Facts(roles=frozenset({"admin"})))

    def test_grant_expiry_boundary_uses_server_tick(self):
        viewer = Facts(roles=frozenset({"viewer"}), grant_until=5)
        self.assertEqual(candidate(replace(viewer, now=4)), "new_write")
        self.deny_without_effects(replace(viewer, now=5))

    def test_evidence_expiry_and_future_timestamp_fail_closed(self):
        self.deny_without_effects(Facts(now=10), "evidence_stale")
        self.deny_without_effects(Facts(observed_tick=2, now=1), "evidence_stale")

    def test_member_visibility_session_and_object_denials_have_no_effects(self):
        for flag in ("member", "board_visible", "session_live", "object_permitted"):
            self.deny_without_effects(replace(Facts(), **{flag: False}))

    def test_moderator_cannot_map_roles_or_self_grant(self):
        mod = Facts(roles=frozenset({"moderator"}))
        self.assertEqual(candidate(replace(mod, action="grant")), "control_allowed")
        self.deny_without_effects(replace(mod, action="grant", self_target=True), "control_denied")
        self.deny_without_effects(replace(mod, action="map_roles"), "control_denied")

    def test_unknown_action_and_self_mapping_deny(self):
        self.deny_without_effects(Facts(action="undefined"), "unknown_action")
        admin_mapping = Facts(roles=frozenset({"admin"}), action="map_roles")
        self.assertEqual(candidate(admin_mapping), "control_allowed")
        self.deny_without_effects(replace(admin_mapping, self_target=True), "control_denied")

    def test_local_revocation_fences_prepared_write(self):
        self.deny_without_effects(Facts(expected_generation=0, current_generation=1), "policy_stale")

    def test_retired_receipt_does_not_need_write_permission_or_new_generation(self):
        f = Facts(roles=frozenset({"viewer"}), receipt_present=True, active_lineage=False,
                  expected_generation=0, current_generation=1, lockdown=True)
        self.deny_without_effects(f, "historical_receipt")
        self.deny_without_effects(replace(f, digest_matches=False), "digest_conflict")
        self.deny_without_effects(replace(f, board_visible=False), "read_denied")
        self.deny_without_effects(replace(f, receipt_present=False), "lineage_changed")

    def test_known_invalidation_prevents_old_refresh_publish(self):
        self.assertFalse(M["publish_refresh"](1, 0))
        self.assertTrue(M["publish_refresh"](1, 1))

    def test_exhaustive_matrix_and_external_detection_negative_control(self):
        d = M["experiment"]()
        self.assertEqual(d["matrix_cases"], 2048)
        self.assertEqual(d["hard_denial_bypasses"]["candidate"], 0)
        self.assertGreater(d["hard_denial_bypasses"]["unsafe_allow_first"], 0)
        self.assertEqual(d["traces"]["external_change_unobserved_within_ttl"]["outcome"], "new_write")
        self.assertEqual(d["traces"]["same_cache_at_expiry"]["outcome"], "evidence_stale")
        self.assertEqual(d, M["experiment"]())


if __name__ == "__main__":
    unittest.main()
