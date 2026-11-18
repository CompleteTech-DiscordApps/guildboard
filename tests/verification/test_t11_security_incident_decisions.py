"""Synthetic observations for the T11 security incident and maintenance runbook."""

from dataclasses import dataclass, replace
import unittest


@dataclass(frozen=True)
class Containment:
    configuration_valid: bool = True
    approval_matches_scope: bool = True
    required_audit_available: bool = True
    atomic_audit_verified: bool = True
    effects_reconciled: bool = True
    urgent_revocation_approved: bool = False
    replacement_ready: bool = True
    superseded_authority_denied: bool = True
    denial_side_effects_absent: bool = True
    isolation_verified: bool = True
    recovery_approved: bool = True


def containment_decision(case):
    if not case.configuration_valid:
        return "invalid_configuration", "hold"
    if not (case.approval_matches_scope and case.required_audit_available and case.atomic_audit_verified):
        return "blocked", "hold"
    if not case.effects_reconciled:
        return "reconcile_before_retry", "hold"
    if not case.replacement_ready:
        action = "urgent_revocation_allowed" if case.urgent_revocation_approved else "hold_routine_rotation"
        return action, "hold"
    if not (case.superseded_authority_denied and case.denial_side_effects_absent
            and case.isolation_verified):
        return "verification_failed", "hold"
    return "verified", "recover" if case.recovery_approved else "hold"


@dataclass(frozen=True)
class Preservation:
    scope_and_destination_approved: bool = True
    custody_and_retention_approved: bool = True
    recipient_authorized: bool = True
    contains_credential_material: bool = False
    collection_verified: bool = True
    transfer_integrity_verified: bool = True


def evidence_handoff(case):
    return (
        "allow_restricted_handoff"
        if (case.scope_and_destination_approved and case.custody_and_retention_approved
            and case.recipient_authorized and not case.contains_credential_material
            and case.collection_verified and case.transfer_integrity_verified)
        else "withhold_handoff"
    )


def private_route(feature_available, fallback_verified, *, audience_approved, channel_approved, content_approved):
    if audience_approved and channel_approved and content_approved:
        if feature_available is True:
            return "github_private_report"
        if feature_available is False and fallback_verified:
            return "verified_maintainer_contact"
    return "retain_privately_and_escalate"


@dataclass(frozen=True)
class BackupCheck:
    finish_second: int | None = 90
    recovery_point_second: int | None = 86
    same_scope_independently_verified: bool = True
    chain_state: str = "intact"
    chain_identity: tuple[str, str, str] | None = ("job_a", "deployment_a", "profile_a")
    unsafe_restore: bool = False
    acknowledged_loss_outside_boundary: bool = False


def backup_decision(check, *, expected_identity, finish_deadline, now, maximum_point_age):
    if check.chain_state == "corrupt" or check.unsafe_restore or check.acknowledged_loss_outside_boundary:
        return "escalate"
    finished = check.finish_second
    point = check.recovery_point_second
    if (finished is not None and point is not None and check.same_scope_independently_verified
            and check.chain_state == "intact" and check.chain_identity == expected_identity
            and point <= finished <= min(finish_deadline, now) and now - point <= maximum_point_age):
        return "verified"
    return "investigate"


def maintenance_decisions(upgrade_verified, backup, corrective_criterion_verified):
    return (
        "ready_for_review" if upgrade_verified else "hold_update",
        backup_decision(backup, expected_identity=("job_a", "deployment_a", "profile_a"),
                        finish_deadline=95, now=100, maximum_point_age=15),
        "close_item" if corrective_criterion_verified else "keep_item_open",
    )


class SecurityIncidentDecisionTest(unittest.TestCase):
    def test_scoped_containment_requires_distinct_recovery_decision(self):
        contained = Containment(recovery_approved=False)
        self.assertEqual(containment_decision(contained), ("verified", "hold"))
        self.assertEqual(containment_decision(replace(contained, recovery_approved=True)),
                         ("verified", "recover"))

    def test_invalid_configuration_and_missing_authority_or_audit_hold(self):
        for field, expected in (
            ("configuration_valid", "invalid_configuration"),
            ("approval_matches_scope", "blocked"),
            ("required_audit_available", "blocked"),
            ("atomic_audit_verified", "blocked"),
        ):
            with self.subTest(field=field):
                case = replace(Containment(), **{field: False})
                self.assertEqual(containment_decision(case), (expected, "hold"))

    def test_approved_urgent_revocation_can_precede_replacement_but_recovery_waits(self):
        routine = Containment(replacement_ready=False)
        self.assertEqual(containment_decision(routine), ("hold_routine_rotation", "hold"))
        urgent = replace(routine, urgent_revocation_approved=True)
        self.assertEqual(containment_decision(urgent), ("urgent_revocation_allowed", "hold"))
        self.assertEqual(containment_decision(replace(urgent, approval_matches_scope=False)),
                         ("blocked", "hold"))
        self.assertEqual(containment_decision(replace(urgent, replacement_ready=True)),
                         ("verified", "recover"))

    def test_interruption_holds_even_after_apparent_isolation_and_revocation(self):
        interrupted = Containment(effects_reconciled=False)
        self.assertEqual(containment_decision(interrupted), ("reconcile_before_retry", "hold"))
        self.assertEqual(containment_decision(replace(interrupted, effects_reconciled=True)),
                         ("verified", "recover"))

    def test_stale_authority_or_side_effects_or_unproven_isolation_hold(self):
        for field in ("superseded_authority_denied", "denial_side_effects_absent", "isolation_verified"):
            with self.subTest(field=field):
                case = replace(Containment(), **{field: False})
                self.assertEqual(containment_decision(case), ("verification_failed", "hold"))

    def test_evidence_transfer_requires_scope_custody_hygiene_and_integrity(self):
        case = Preservation()
        self.assertEqual(evidence_handoff(case), "allow_restricted_handoff")
        for field, invalid in (
            ("scope_and_destination_approved", False),
            ("custody_and_retention_approved", False),
            ("recipient_authorized", False),
            ("contains_credential_material", True),
            ("collection_verified", False),
            ("transfer_integrity_verified", False),
        ):
            with self.subTest(field=field):
                self.assertEqual(evidence_handoff(replace(case, **{field: invalid})), "withhold_handoff")

    def test_private_route_requires_known_availability_and_approval(self):
        for feature, fallback, approved, expected in (
            (True, False, True, "github_private_report"),
            (True, True, True, "github_private_report"),
            (False, True, True, "verified_maintainer_contact"),
            (False, False, True, "retain_privately_and_escalate"),
            (None, True, True, "retain_privately_and_escalate"),
            (True, True, False, "retain_privately_and_escalate"),
            (False, True, False, "retain_privately_and_escalate"),
        ):
            with self.subTest(feature=feature, fallback=fallback, approved=approved):
                self.assertEqual(private_route(feature, fallback, audience_approved=approved,
                                               channel_approved=True, content_approved=True), expected)
        for feature in (True, False):
            for missing in ("audience_approved", "channel_approved", "content_approved"):
                with self.subTest(feature=feature, missing=missing):
                    approvals = dict.fromkeys(("audience_approved", "channel_approved", "content_approved"), True)
                    approvals[missing] = False
                    self.assertEqual(private_route(feature, True, **approvals), "retain_privately_and_escalate")

    def test_independent_post_release_checks_keep_open_items_visible(self):
        healthy = BackupCheck()
        self.assertEqual(maintenance_decisions(True, healthy, True),
                         ("ready_for_review", "verified", "close_item"))
        self.assertEqual(maintenance_decisions(False, healthy, False),
                         ("hold_update", "verified", "keep_item_open"))
        for inputs in (
            {"finish_second": None},
            {"finish_second": 96},
            {"recovery_point_second": None},
            {"recovery_point_second": 84},
            {"recovery_point_second": 91},
            {"same_scope_independently_verified": False},
            {"chain_state": "unknown"},
            {"chain_identity": None},
            {"chain_identity": ("job_b", "deployment_a", "profile_a")},
            {"chain_identity": ("job_a", "deployment_b", "profile_a")},
            {"chain_identity": ("job_a", "deployment_a", "profile_b")},
        ):
            with self.subTest(inputs=inputs):
                self.assertEqual(maintenance_decisions(True, replace(healthy, **inputs), False),
                                 ("ready_for_review", "investigate", "keep_item_open"))
        for inputs in ({"chain_state": "corrupt"}, {"unsafe_restore": True},
                       {"acknowledged_loss_outside_boundary": True}):
            with self.subTest(inputs=inputs):
                self.assertEqual(maintenance_decisions(False, replace(healthy, **inputs), False),
                                 ("hold_update", "escalate", "keep_item_open"))



if __name__ == "__main__":
    unittest.main()
