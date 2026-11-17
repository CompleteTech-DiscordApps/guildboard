"""Offline contract vectors for GB-T5.S1. No application or engine is invoked."""

from dataclasses import dataclass, fields
import json
from pathlib import Path
import unittest


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "docs/specifications/fixtures/GB-T5-S1-scenarios.json"
)


@dataclass(frozen=True)
class Command:
    guild: str = "guild-a"
    board: str = "board-a"
    actor: str = "actor-a"
    lineage: str = "lineage-a"
    operation: str = "operation-a"
    digest: str = "digest-a"
    valid: bool = True
    read: bool = True
    write: bool = True
    policy_current: bool = True
    release: bool = True
    capacity: bool = True
    commit: str = "durable"
    lost_ack: bool = False
    recovery: str = "restart"
    complete_history: bool = False


@dataclass(frozen=True)
class Snapshot:
    same_scope: bool = True
    same_lineage: bool = True
    consistent_cut: bool = True
    pinned: bool = True
    assets_verified: bool = True
    durable_bytes: bool = True
    digest_matches: bool = True
    complete_transfer: bool = True
    start: int = 4
    end: int = 6
    tail: tuple = (5, 6)


@dataclass(frozen=True)
class Migration:
    catalog: str = "prior"
    digest_matches: bool = True
    journal_matches: bool = True
    compatible: bool = True
    verified: bool = True
    old_writer_fenced: bool = True
    recoverable: bool = True


@dataclass(frozen=True)
class Disaster:
    manifest_verified: bool = True
    deletion_independent: bool = True
    exposure_fence: bool = True
    deletion_cut: int = 4
    current_watermark: int = 6
    applied_markers: tuple = (5, 6)
    hidden: bool = True
    revocations_applied: bool = True
    audit_independent: bool = True
    audit_integrity: bool = True
    checkpoint: int = 4
    anchored_head: int = 6
    audit_tail: tuple = (5, 6)
    generation_fenced: bool = True
    lineage_receipts_verified: bool = True


@dataclass(frozen=True)
class Restore:
    same_scope: bool = True
    authorized: bool = True
    deleted: bool = False
    assets_verified: bool = True
    generation_current: bool = True
    audit_ready: bool = True
    commit: bool = True


EFFECTS = ["state", "event", "receipt", "outbox", "quota", "audit"]


ORIGINAL_RECEIPTS = {("guild-a", "board-a", "lineage-a", "actor-a", "operation-a"): ("digest-a", 7)}


def identity(case):
    return case.guild, case.board, case.lineage, case.actor, case.operation


def command_result(case, receipts=ORIGINAL_RECEIPTS):
    """Evaluate one decision without modifying the supplied receipt store."""
    if not case.valid:
        return "INVALID_MESSAGE", []
    if not case.read or (case.guild, case.board) != ("guild-a", "board-a"):
        return "NOT_FOUND", []

    existing = receipts.get(identity(case))
    active_lineage = "lineage-a" if case.recovery == "restart" else "lineage-b"
    effects = []
    if existing is not None:
        digest, revision = existing
        if case.digest != digest:
            outcome = "IDEMPOTENCY_CONFLICT"
        else:
            receipt_kind = "CURRENT" if case.lineage == active_lineage else "HISTORICAL"
            outcome = f"ACK_{receipt_kind}_{revision}"
    elif case.lineage != active_lineage:
        incomplete = case.recovery == "disaster" and not case.complete_history
        outcome = "DEPENDENCY_UNAVAILABLE" if incomplete else "LINEAGE_CHANGED"
    elif not case.write:
        return "FORBIDDEN", []
    elif not case.policy_current:
        return "POLICY_STALE", []
    elif not case.capacity:
        return "RATE_LIMITED", []
    elif case.commit != "durable":
        effects = EFFECTS if case.commit == "unknown_committed" else []
        outcome = "DEPENDENCY_UNAVAILABLE"
    else:
        effects = EFFECTS
        outcome = "NO_RELEASE" if case.lost_ack else "ACK_NEW"

    return (outcome if case.release else "NOT_FOUND"), effects


def snapshot_result(case):
    verified = (
        case.same_scope and case.same_lineage and case.consistent_cut
        and case.pinned and case.assets_verified and case.durable_bytes
        and case.digest_matches and case.complete_transfer
        and case.start <= case.end and case.tail == tuple(range(case.start + 1, case.end + 1))
    )
    return ("PROMOTED", ["snapshot"]) if verified else ("ISOLATED", [])


def migration_result(case):
    if not all((case.digest_matches, case.journal_matches, case.compatible,
                case.verified, case.old_writer_fenced, case.recoverable)):
        return "FENCED", []
    if case.catalog == "expanded":
        return "RESUMED", ["journal"]
    if case.catalog == "prior":
        return "EXPANDED", ["schema", "journal"]
    return "FENCED", []


def disaster_result(case):
    verified = all((
        case.manifest_verified, case.deletion_independent, case.exposure_fence,
        case.hidden, case.revocations_applied, case.audit_independent,
        case.audit_integrity, case.generation_fenced, case.lineage_receipts_verified,
        case.deletion_cut <= case.current_watermark,
        case.applied_markers == tuple(range(case.deletion_cut + 1, case.current_watermark + 1)),
        case.checkpoint <= case.anchored_head,
        case.audit_tail == tuple(range(case.checkpoint + 1, case.anchored_head + 1)),
    ))
    return ("EXPOSED", ["exposure"]) if verified else ("ISOLATED", [])


def restore_result(case):
    verified = all((case.same_scope, case.authorized, not case.deleted,
                    case.assets_verified, case.generation_current,
                    case.audit_ready, case.commit))
    if not verified:
        return "REJECTED", []
    return "RESTORED", ["state", "lineage", "policy", "audit"]


MODELS = {
    "command": (Command, command_result),
    "snapshot": (Snapshot, snapshot_result),
    "migration": (Migration, migration_result),
    "disaster": (Disaster, disaster_result),
    "restore": (Restore, restore_result),
}


class ContractScenarios(unittest.TestCase):
    def test_scenarios(self):
        data = FIXTURE.read_bytes()
        self.assertLessEqual(len(data), 24 * 1024)
        fixture = json.loads(data, object_pairs_hook=self.unique_object)
        self.assertEqual(set(fixture), {"version", "scenarios"})
        self.assertIs(type(fixture["version"]), int)
        self.assertEqual(fixture["version"], 1)
        scenarios = fixture["scenarios"]
        self.assertIs(type(scenarios), list)
        self.assertTrue(1 <= len(scenarios) <= 80)
        seen = set()
        covered = set()
        for case in scenarios:
            with self.subTest(case=case.get("id")):
                self.assertEqual(set(case), {"id", "kind", "inputs", "outcome", "effects"})
                self.assertRegex(case["id"], r"^[A-Z][0-9]{2}$")
                self.assertNotIn(case["id"], seen)
                seen.add(case["id"])
                covered.add(case["kind"])
                model, evaluate = MODELS[case["kind"]]
                expected = (case["outcome"], case["effects"])
                self.assertEqual(evaluate(self.load_inputs(model, case["inputs"])), expected)
        self.assertEqual(covered, set(MODELS))

    def test_unknown_commit_and_lost_ack_reconcile_after_restart(self):
        for outcome, lost_ack, committed in (
            ("unknown_committed", False, True),
            ("unknown_rolled_back", False, False),
            ("durable", True, True),
        ):
            with self.subTest(outcome=outcome):
                attempt = Command(operation="operation-new", commit=outcome, lost_ack=lost_ack)
                _, first_effects = command_result(attempt)
                self.assertEqual("receipt" in first_effects, committed)
                # Model the receipt store reopened from durable state.
                reopened = dict(ORIGINAL_RECEIPTS)
                if committed:
                    reopened[identity(attempt)] = (attempt.digest, 8)
                retry = Command(operation=attempt.operation)
                expected = ("ACK_CURRENT_8", []) if committed else ("ACK_NEW", EFFECTS)
                self.assertEqual(command_result(retry, reopened), expected)

    def load_inputs(self, model, inputs):
        self.assertIs(type(inputs), dict)
        defaults = {field.name: field.default for field in fields(model)}
        self.assertLessEqual(inputs.keys(), defaults.keys())
        values = {}
        for key, value in inputs.items():
            default = defaults[key]
            if type(default) is tuple:
                self.assertIs(type(value), list)
                self.assertLessEqual(len(value), 16)
                for revision in value:
                    self.assertIs(type(revision), int)
                    self.assertTrue(0 <= revision <= 16)
                values[key] = tuple(value)
                continue
            self.assertIs(type(value), type(default))
            if type(default) is int:
                self.assertTrue(0 <= value <= 16)
            if type(default) is str:
                self.assertRegex(value, r"^[a-z][a-z0-9_-]{0,31}$")
                enum = {
                    "commit": {"durable", "rollback", "unknown_committed", "unknown_rolled_back"},
                    "recovery": {"restart", "document", "disaster"},
                    "catalog": {"prior", "expanded", "unrecognized"},
                }.get(key)
                if enum is not None:
                    self.assertIn(value, enum)
            values[key] = value
        return model(**values)

    @staticmethod
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate fixture key: {key}")
            result[key] = value
        return result
