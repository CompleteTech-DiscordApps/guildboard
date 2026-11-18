"""Offline contract vectors for GB-T5.S1. No application or engine is invoked."""

from dataclasses import dataclass, fields, replace
from hashlib import sha256
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


TRUSTED_ALLOCATOR_ISSUER = "independent-allocator"


@dataclass(frozen=True)
class VerifiedLineageReservation:
    lineage: str
    guild: str = "guild-a"
    board: str = "board-a"
    generation: str = "generation-a"
    issuer: str = TRUSTED_ALLOCATOR_ISSUER
    authority_epoch: int = 1
    authorized: bool = True


# This synthetic allocator's grants are independent of the recovered lineage inventory.
ALLOCATOR_GRANTS = {
    ("guild-a", "board-a", 1): "lineage-b",
    ("guild-a", "board-a", 2): "lineage-c",
    ("guild-a", "board-a", 3): "lineage-d",
}
FIXTURE_RESERVATION = VerifiedLineageReservation("lineage-b")


@dataclass
class AllocatorAuthority:
    """The current fenced allocator, outside the recoverable board history."""

    generation: str = "generation-a"
    serving_lineage: str = "lineage-a"
    serving_revision: int = 7
    epoch: int = 1
    issuer: str | None = TRUSTED_ALLOCATOR_ISSUER
    current: bool = True
    consumed: frozenset = frozenset()
    guild: str = "guild-a"
    board: str = "board-a"

    def serves(self, guild, board, generation, lineage, revision):
        return (
            self.current and self.issuer == TRUSTED_ALLOCATOR_ISSUER
            and (guild, board, generation, lineage, revision)
            == (self.guild, self.board, self.generation, self.serving_lineage, self.serving_revision)
        )

    def reservation(self, guild, board, lineage):
        scope = (guild, board, lineage)
        if (not self.current or self.issuer != TRUSTED_ALLOCATOR_ISSUER
                or (guild, board) != (self.guild, self.board)
                or scope in self.consumed
                or lineage != ALLOCATOR_GRANTS.get((guild, board, self.epoch))):
            return None
        return VerifiedLineageReservation(lineage, guild, board, self.generation, self.issuer, self.epoch)

    def consume(self, guild, board, lineage, disaster):
        self.consumed |= {(guild, board, lineage)}
        self.epoch += 1
        self.serving_lineage = lineage
        self.serving_revision = 0
        if disaster:
            self.generation = f"generation-{lineage}"


@dataclass(frozen=True)
class History:
    active: str = "lineage-a"
    disaster_seen: bool = False
    complete_retired: frozenset = frozenset()
    known_lineages: frozenset = frozenset({"lineage-a"})
    guild: str = "guild-a"
    board: str = "board-a"
    storage_generation: str = "generation-a"

    def restart(self):
        return replace(self)

    def restore(self, new_lineage, reservation, *, allocator):
        return self.activate(new_lineage, reservation, self.complete_retired | {self.active}, allocator)

    def promote(self, new_lineage, reservation, proven_complete, *, allocator):
        previously_complete = self.complete_retired | {self.active}
        return self.activate(new_lineage, reservation, previously_complete & proven_complete,
                             allocator, disaster=True)

    def activate(self, new_lineage, reservation, complete_retired, allocator, disaster=False):
        if (allocator is None or type(reservation) is not VerifiedLineageReservation
                or reservation != allocator.reservation(self.guild, self.board, new_lineage)
                or new_lineage == self.active or new_lineage in self.known_lineages):
            return None
        allocator.consume(self.guild, self.board, new_lineage, disaster)
        return replace(self, active=new_lineage, disaster_seen=self.disaster_seen or disaster,
                       complete_retired=complete_retired, storage_generation=allocator.generation,
                       known_lineages=self.known_lineages | {self.active, new_lineage})


@dataclass(frozen=True)
class CommandScenario(Command):
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
    journal: str = "planned"
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
    source_generation: str = "generation-a"
    restored_sql_cut: str = "sql-cut-a"
    restored_object_set: str = "objects-a"
    restored_reference_set: str = "references-a"
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
    target_lineage: str = "lineage-b"
    same_scope: bool = True
    authorized: bool = True
    deleted: bool = False
    assets_verified: bool = True
    generation_current: bool = True
    audit_ready: bool = True
    commit: bool = True
    source_deletion_cut: int = 4
    source_projection_tampered: bool = False
    current_watermark: int = 6
    markers: tuple = (5, 6)
    exposure_fence: bool = True
    coverage_independent: bool = True


EFFECTS = ["state", "event", "receipt", "outbox", "quota", "audit"]


ORIGINAL_RECEIPTS = {("guild-a", "board-a", "lineage-a", "actor-a", "operation-a"): ("digest-a", 7)}


def identity(case):
    return case.guild, case.board, case.lineage, case.actor, case.operation


@dataclass(frozen=True)
class CommitWitness:
    generation: str
    operation: tuple
    intent_digest: str
    revision: int
    event_transaction: tuple
    receipt_transaction: tuple
    outbox_transaction: tuple


MODEL_STORE = object()


def model_witness(case, history, revision):
    operation = identity(case)
    transaction = (history.storage_generation, operation, revision)
    return CommitWitness(history.storage_generation, operation, case.digest, revision,
                         transaction, transaction, transaction)


def command_result(case, receipts=ORIGINAL_RECEIPTS, history=History(), witness=MODEL_STORE, *,
                   revision=8, release_denial="NOT_FOUND", verify_serving_cut=None):
    """Evaluate one decision without modifying the supplied receipt store."""
    if not case.valid:
        return "INVALID_MESSAGE", []
    if not case.read or (case.guild, case.board) != (history.guild, history.board):
        return "NOT_FOUND", []

    if verify_serving_cut is not None and not verify_serving_cut():
        return ("DEPENDENCY_UNAVAILABLE" if case.release else release_denial), []

    operation = identity(case)
    existing = dict(receipts).get(operation)
    active_lineage = history.active
    effects = []
    if existing is not None:
        digest, revision = existing
        if case.digest != digest:
            outcome = "IDEMPOTENCY_CONFLICT"
        else:
            receipt_kind = "CURRENT" if case.lineage == active_lineage else "HISTORICAL"
            outcome = f"ACK_{receipt_kind}_{revision}"
    elif case.lineage != active_lineage:
        incomplete = history.disaster_seen and case.lineage not in history.complete_retired
        outcome = "DEPENDENCY_UNAVAILABLE" if incomplete else "LINEAGE_CHANGED"
    elif not case.write:
        outcome = "FORBIDDEN"
    elif not case.policy_current:
        outcome = "POLICY_STALE"
    elif not case.capacity:
        outcome = "RATE_LIMITED"
    elif case.commit != "durable":
        effects = EFFECTS if case.commit == "unknown_committed" else []
        outcome = "DEPENDENCY_UNAVAILABLE"
    else:
        effects = EFFECTS
        expected = model_witness(case, history, revision)
        if witness is MODEL_STORE:
            witness = expected
        if type(witness) is not CommitWitness or witness != expected:
            outcome = "DEPENDENCY_UNAVAILABLE"
        else:
            outcome = "NO_RELEASE" if case.lost_ack else "ACK_NEW"

    return (outcome if case.release else release_denial), effects


def command_scenario_result(case):
    history = History()
    if case.recovery == "document":
        history = history.restore("lineage-b", FIXTURE_RESERVATION, allocator=AllocatorAuthority())
    elif case.recovery == "disaster":
        proven_complete = {"lineage-a"} if case.complete_history else set()
        history = history.promote("lineage-b", FIXTURE_RESERVATION, proven_complete, allocator=AllocatorAuthority())
    return command_result(case, history=history)


def snapshot_result(case):
    verified = (
        case.same_scope and case.same_lineage and case.consistent_cut
        and case.pinned and case.assets_verified and case.durable_bytes
        and case.digest_matches and case.complete_transfer
        and case.start <= case.end and case.tail == tuple(range(case.start + 1, case.end + 1))
    )
    return ("PROMOTED", ["snapshot"]) if verified else ("ISOLATED", [])


MIGRATION_STEPS = {
    "planned": ("prior", "expanded", "EXPANDED", "schema"),
    "expanded": ("expanded", "backfilled", "BACKFILLED", "data"),
    "backfilled": ("backfilled", "verified", "VERIFIED", None),
    "verified": ("verified", "activated", "ACTIVATED", "activation"),
    "activated": ("activated", "contracted", "CONTRACTED", "schema"),
}


def migration_result(case):
    if not all((case.digest_matches, case.journal_matches, case.compatible, case.verified)):
        return "FENCED", []
    if case.journal == "activated" and not (case.old_writer_fenced and case.recoverable):
        return "FENCED", []
    before, after, outcome, effect = MIGRATION_STEPS[case.journal]
    if case.catalog == before:
        return outcome, [effect, "journal"] if effect else ["journal"]
    if case.catalog == after:
        return "RESUMED", ["journal"]
    return "FENCED", []


DISASTER_DELETION_PROOF = ("generation-a", "sql-cut-a", "objects-a", "references-a", 4)


def disaster_attempt(case, history=History(), target_lineage="lineage-b", proven_complete=frozenset(),
                     reservation=FIXTURE_RESERVATION, *, allocator=None):
    restored_cut = (case.source_generation, case.restored_sql_cut, case.restored_object_set,
                    case.restored_reference_set, case.deletion_cut)
    verified = all((
        case.manifest_verified, case.deletion_independent, case.exposure_fence,
        restored_cut == DISASTER_DELETION_PROOF,
        case.hidden, case.revocations_applied, case.audit_independent,
        case.audit_integrity, case.generation_fenced, case.lineage_receipts_verified,
        case.deletion_cut <= case.current_watermark,
        case.applied_markers == tuple(range(case.deletion_cut + 1, case.current_watermark + 1)),
        case.checkpoint <= case.anchored_head,
        case.audit_tail == tuple(range(case.checkpoint + 1, case.anchored_head + 1)),
    ))
    promoted = history.promote(target_lineage, reservation, proven_complete, allocator=allocator) if verified else None
    if promoted is None:
        return "ISOLATED", [], history
    return "EXPOSED", ["exposure"], promoted


def disaster_result(case):
    outcome, effects, _ = disaster_attempt(case, allocator=AllocatorAuthority())
    return outcome, effects


# Synthetic checkpoint rows, with T9 subject attribution and reference targets.
SOURCE_CONTENT = {"shape-a": "subject-a", "shape-b": "subject-b"}
SOURCE_REFERENCES = {
    "asset-a": ("subject-a", "shape-b"),
    "asset-b": ("subject-b", "shape-b"),
    "history-a": ("subject-b", "shape-a"),
}
MARKER_SUBJECTS = {5: "subject-a", 6: "subject-c", 7: "subject-b"}


def checkpoint_digest(content, references):
    return sha256(json.dumps([content, references], sort_keys=True).encode()).digest()


# The authenticated checkpoint record binds this cut to these exact source rows.
CHECKPOINT_PROOF = (4, checkpoint_digest(SOURCE_CONTENT, SOURCE_REFERENCES))


def restore_projection(case):
    source_content = dict(SOURCE_CONTENT)
    if case.source_projection_tampered:
        source_content["shape-a"] = "subject-b"
    source_digest = checkpoint_digest(source_content, SOURCE_REFERENCES)
    if not all((case.same_scope, case.authorized, not case.deleted,
                case.assets_verified, case.generation_current, case.audit_ready,
                case.exposure_fence, case.coverage_independent,
                CHECKPOINT_PROOF == (case.source_deletion_cut, source_digest),
                case.source_deletion_cut <= case.current_watermark,
                case.markers == tuple(range(case.source_deletion_cut + 1,
                                            case.current_watermark + 1)),
                all(marker in MARKER_SUBJECTS for marker in case.markers))):
        return None
    fenced_subjects = {MARKER_SUBJECTS[marker] for marker in case.markers}
    content = {row for row, subject in source_content.items() if subject not in fenced_subjects}
    references = {row for row, (subject, target) in SOURCE_REFERENCES.items()
                  if subject not in fenced_subjects and target in content}
    return sorted(content), sorted(references)


@dataclass(frozen=True)
class RestoreArtifacts:
    final_cut: tuple
    event: tuple
    outbox: tuple
    audit: tuple
    content: tuple
    references: tuple
    event_transaction: tuple
    receipt_transaction: tuple
    outbox_transaction: tuple


@dataclass(frozen=True)
class RestoreState:
    history: History = History()
    revision: int = 7
    policy_generation: int = 1
    receipts: tuple = ()
    artifacts: tuple = ()


INITIAL_RESTORE_STATE = RestoreState(receipts=tuple(ORIGINAL_RECEIPTS.items()))
RESTORE_COMMAND = Command(operation="operation-restore", digest="digest-restore")


def restore_attempt(case, command=RESTORE_COMMAND, state=INITIAL_RESTORE_STATE,
                    reservation=FIXTURE_RESERVATION, witness=MODEL_STORE, *, allocator=None):
    history = state.history

    def verify_serving_cut():
        return allocator is not None and allocator.serves(
            history.guild, history.board, history.storage_generation, history.active, state.revision,
        )

    final_revision = state.revision + 1
    outcome, effects = command_result(
        command, receipts=state.receipts, history=history, witness=witness,
        revision=final_revision, verify_serving_cut=verify_serving_cut,
    )
    if not effects:
        return outcome, [], state

    projection = restore_projection(case)
    if projection is None or not case.commit:
        return ("REJECTED" if command.release else "NOT_FOUND"), [], state
    next_history = state.history.restore(case.target_lineage, reservation, allocator=allocator)
    if next_history is None:
        return ("DEPENDENCY_UNAVAILABLE" if command.release else "NOT_FOUND"), [], state
    content, references = projection
    transaction = model_witness(command, history, final_revision).event_transaction
    final_cut = (command.guild, command.board, command.lineage, final_revision)
    artifacts = RestoreArtifacts(
        final_cut=final_cut,
        event=(final_cut, command.operation, "restore", case.target_lineage, 0),
        outbox=final_cut,
        audit=(final_cut, "restore", case.target_lineage),
        content=tuple(content),
        references=tuple(references),
        event_transaction=transaction,
        receipt_transaction=transaction,
        outbox_transaction=transaction,
    )
    publication = RestoreState(
        history=next_history,
        revision=0,
        policy_generation=state.policy_generation + 1,
        receipts=(*state.receipts, (identity(command), (command.digest, final_revision))),
        artifacts=(*state.artifacts, artifacts),
    )
    effects = ["state", "lineage", "policy", "event", "receipt", "outbox", "audit",
               *content, *references]
    return ("RESTORED" if outcome == "ACK_NEW" else outcome), effects, publication


def restore_result(case):
    outcome, effects, _ = restore_attempt(case, allocator=AllocatorAuthority())
    return outcome, effects


MODELS = {
    "command": (CommandScenario, command_scenario_result),
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
        self.assertTrue(1 <= len(scenarios) <= 82)
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

    def test_egress_denial_conceals_receipt_and_commit_precondition_branches(self):
        for blocked, code in (({"write": False}, "FORBIDDEN"),
                              ({"policy_current": False}, "POLICY_STALE"),
                              ({"capacity": False}, "RATE_LIMITED")):
            attempt = Command(**blocked)
            self.assertEqual(command_result(attempt, {}), (code, []))
            conflicting = {identity(attempt): ("different", 7)}
            for receipts in ({}, ORIGINAL_RECEIPTS, conflicting):
                with self.subTest(code=code, receipts=receipts):
                    denied = replace(attempt, release=False)
                    self.assertEqual(command_result(denied, receipts), ("NOT_FOUND", []))

    def test_lost_restore_ack_returns_former_lineage_receipt_without_republishing(self):
        command = replace(RESTORE_COMMAND, lost_ack=True)
        allocator = AllocatorAuthority()
        outcome, effects, published = restore_attempt(Restore(), command, allocator=allocator)
        self.assertEqual(outcome, "NO_RELEASE")
        self.assertEqual(effects, ["state", "lineage", "policy", "event", "receipt",
                                   "outbox", "audit", "shape-b", "asset-b"])
        former_cut = ("guild-a", "board-a", "lineage-a", 8)
        transaction = ("generation-a", identity(command), 8)
        self.assertEqual(published.receipts, (
            *INITIAL_RESTORE_STATE.receipts, (identity(command), (command.digest, 8)),
        ))
        self.assertEqual(published.artifacts, (RestoreArtifacts(
            former_cut, (former_cut, command.operation, "restore", "lineage-b", 0),
            former_cut, (former_cut, "restore", "lineage-b"), ("shape-b",), ("asset-b",),
            transaction, transaction, transaction,
        ),))
        self.assertEqual((published.history.active, published.revision, published.policy_generation),
                         ("lineage-b", 0, 2))

        reopened = replace(published, history=published.history.restart())
        retry = replace(command, lost_ack=False, write=False, policy_current=False)
        self.assertEqual(restore_attempt(Restore(), retry, reopened, allocator=allocator),
                         ("ACK_HISTORICAL_8", [], reopened))
        self.assertEqual(restore_attempt(Restore(), replace(retry, release=False), reopened, allocator=allocator),
                         ("NOT_FOUND", [], reopened))
        self.assertEqual(restore_attempt(Restore(), replace(command, release=False, lost_ack=False),
                                         allocator=AllocatorAuthority()),
                         ("NOT_FOUND", effects, published))
        self.assertEqual(restore_attempt(Restore(commit=False), allocator=AllocatorAuthority()),
                         ("REJECTED", [], INITIAL_RESTORE_STATE))
        self.assertEqual(restore_attempt(Restore(commit=False), replace(command, release=False, lost_ack=False),
                                         allocator=AllocatorAuthority()),
                         ("NOT_FOUND", [], INITIAL_RESTORE_STATE))

    def test_uncertain_restore_reconciles_original_identity_after_restart(self):
        case = Restore()
        _, committed_effects, committed = restore_attempt(case, allocator=AllocatorAuthority())
        initial = INITIAL_RESTORE_STATE
        for commit, expected_effects, expected_state in (
            ("unknown_committed", committed_effects, committed),
            ("unknown_rolled_back", [], initial),
        ):
            with self.subTest(commit=commit):
                command = replace(RESTORE_COMMAND, commit=commit)
                allocator = AllocatorAuthority()
                self.assertEqual(restore_attempt(case, command, allocator=allocator),
                                 ("DEPENDENCY_UNAVAILABLE", expected_effects, expected_state))
                self.assertEqual(restore_attempt(case, replace(command, release=False), allocator=AllocatorAuthority()),
                                 ("NOT_FOUND", expected_effects, expected_state))
                reopened = replace(expected_state, history=expected_state.history.restart())
                retry = replace(command, commit="durable")
                expected = (("ACK_HISTORICAL_8", [], reopened) if expected_effects
                            else ("RESTORED", committed_effects, committed))
                self.assertEqual(restore_attempt(case, retry, reopened, allocator=allocator), expected)

    def test_restore_retains_scoped_artifacts_and_never_reuses_retired_lineages(self):
        first = RESTORE_COMMAND
        allocator = AllocatorAuthority()
        _, _, after_first = restore_attempt(Restore(), first, allocator=allocator)
        fresh = allocator.reservation("guild-a", "board-a", "lineage-c")
        second = replace(first, lineage="lineage-b", operation="restore-again")
        self.assertEqual(restore_attempt(Restore(target_lineage="lineage-a"), second, after_first,
                                        replace(fresh, lineage="lineage-a"), allocator=allocator),
                         ("DEPENDENCY_UNAVAILABLE", [], after_first))
        second_case = Restore(target_lineage="lineage-c")
        outcome, _, after_second = restore_attempt(second_case, second, after_first,
                                                   fresh, allocator=allocator)
        self.assertEqual(outcome, "RESTORED")
        self.assertEqual(after_second.history.active, "lineage-c")
        self.assertEqual(after_second.history.complete_retired, frozenset({"lineage-a", "lineage-b"}))
        reopened = replace(after_second, history=after_second.history.restart())
        former_cut = ("guild-a", "board-a", "lineage-b", 1)
        transaction = ("generation-a", identity(second), 1)
        second_artifacts = RestoreArtifacts(
            former_cut, (former_cut, second.operation, "restore", "lineage-c", 0),
            former_cut, (former_cut, "restore", "lineage-c"), ("shape-b",), ("asset-b",),
            transaction, transaction, transaction,
        )
        self.assertEqual(reopened.artifacts, (*after_first.artifacts, second_artifacts))
        self.assertEqual(restore_attempt(Restore(), first, reopened, allocator=allocator), ("ACK_HISTORICAL_8", [], reopened))
        self.assertEqual(restore_attempt(second_case, second, reopened, allocator=allocator), ("ACK_HISTORICAL_1", [], reopened))

    def test_disaster_applied_cut_requires_bound_recovered_projection(self):
        valid = Disaster()
        self.assertEqual(disaster_result(valid), ("EXPOSED", ["exposure"]))
        for claim in ({"deletion_cut": 6, "applied_markers": ()}, {"source_generation": "generation-b"},
                      {"restored_sql_cut": "sql-cut-b"}, {"restored_object_set": "objects-b"},
                      {"restored_reference_set": "references-b"}):
            with self.subTest(claim=claim):
                self.assertEqual(disaster_result(replace(valid, **claim)), ("ISOLATED", []))

    def test_disaster_promotion_stays_isolated_for_previously_used_lineages(self):
        allocator = AllocatorAuthority()
        history = History().restore("lineage-b", FIXTURE_RESERVATION, allocator=allocator).restart()
        fresh = allocator.reservation("guild-a", "board-a", "lineage-c")
        for used in ("lineage-a", "lineage-b"):
            with self.subTest(lineage=used):
                self.assertEqual(disaster_attempt(Disaster(), history, used,
                                                  reservation=replace(fresh, lineage=used), allocator=allocator),
                                 ("ISOLATED", [], history))
        outcome, effects, promoted = disaster_attempt(Disaster(), history, "lineage-c",
                                                       reservation=fresh, allocator=allocator)
        self.assertEqual((outcome, effects, promoted.active), ("EXPOSED", ["exposure"], "lineage-c"))
        self.assertEqual(promoted.known_lineages, frozenset({"lineage-a", "lineage-b", "lineage-c"}))

    def test_disaster_coverage_survives_restart_restore_and_later_disasters(self):
        allocator = AllocatorAuthority()
        history = History().promote("lineage-b", FIXTURE_RESERVATION, set(), allocator=allocator)
        missing = Command(operation="operation-lost")
        unrecognized = Command(lineage="lineage-lost")
        unknown = ("DEPENDENCY_UNAVAILABLE", [])
        self.assertEqual(command_result(Command(), history=history), ("ACK_HISTORICAL_7", []))
        self.assertEqual(command_result(missing, history=history), unknown)
        history = history.restart()
        self.assertEqual(history.active, "lineage-b")
        self.assertEqual(command_result(unrecognized, history=history), unknown)
        current = Command(lineage=history.active, operation="operation-in-b")
        receipts = {**ORIGINAL_RECEIPTS, identity(current): (current.digest, 1)}
        self.assertEqual(command_result(current, receipts, history), ("ACK_CURRENT_1", []))

        self.assertEqual(restore_projection(Restore()), (["shape-b"], ["asset-b"]))
        history = history.restore("lineage-c", allocator.reservation("guild-a", "board-a", "lineage-c"),
                                  allocator=allocator).restart()
        self.assertEqual(history.active, "lineage-c")
        self.assertEqual(command_result(current, receipts, history), ("ACK_HISTORICAL_1", []))
        self.assertEqual(command_result(missing, receipts, history), unknown)
        self.assertEqual(command_result(unrecognized, receipts, history), unknown)
        absent_b = replace(current, operation="absent-in-b")
        self.assertEqual(command_result(absent_b, receipts, history), ("LINEAGE_CHANGED", []))

        # The later recovered cut proves B complete but omits a suffix of C.
        history = history.promote("lineage-d", allocator.reservation("guild-a", "board-a", "lineage-d"),
                                  {"lineage-b"}, allocator=allocator).restart()
        self.assertEqual(command_result(absent_b, receipts, history), ("LINEAGE_CHANGED", []))
        self.assertEqual(command_result(missing, receipts, history), unknown)
        self.assertEqual(command_result(unrecognized, receipts, history), unknown)
        self.assertEqual(command_result(Command(lineage="lineage-c"), receipts, history), unknown)
        self.assertEqual(command_result(replace(missing, release=False), receipts, history),
                         ("NOT_FOUND", []))
        self.assertEqual(command_result(Command(lineage=history.active), receipts, history),
                         ("ACK_NEW", EFFECTS))

    def test_omitted_lineage_cannot_become_active_without_a_current_scoped_reservation(self):
        omitted = "lineage-omitted"
        former = History(active=omitted, known_lineages=frozenset({"lineage-a", omitted}))
        allocator = AllocatorAuthority()
        promoted = former.promote("lineage-b", FIXTURE_RESERVATION, set(), allocator=allocator)
        history = replace(promoted, known_lineages=promoted.known_lineages - {omitted}).restart()
        state = RestoreState(history=history, revision=0)
        old = Command(lineage=omitted, operation="unresolved-old-operation")
        command = replace(RESTORE_COMMAND, lineage=history.active)
        self.assertNotIn(omitted, history.known_lineages)
        self.assertIsNone(allocator.reservation("guild-a", "board-a", omitted))
        fresh = allocator.reservation("guild-a", "board-a", "lineage-c")
        denied = ("DEPENDENCY_UNAVAILABLE", [], state)
        isolated = ("ISOLATED", [], history)
        self.assertEqual(restore_attempt(Restore(target_lineage=omitted), command, state,
                                         replace(fresh, lineage=omitted), allocator=allocator), denied)
        self.assertEqual(disaster_attempt(Disaster(), history, omitted,
                                          reservation=replace(fresh, lineage=omitted), allocator=allocator), isolated)

        restore = Restore(target_lineage=fresh.lineage)
        for reservation in (
            None, replace(fresh, lineage="lineage-d"),
            replace(fresh, guild="foreign"), replace(fresh, board="foreign"),
            replace(fresh, generation=History().storage_generation),
            replace(fresh, authority_epoch=allocator.epoch - 1),
            replace(fresh, issuer="recovered-inventory"), replace(fresh, authorized=False),
        ):
            with self.subTest(reservation=reservation):
                self.assertEqual(restore_attempt(restore, command, state, reservation, allocator=allocator), denied)
                self.assertEqual(restore_attempt(restore, replace(command, release=False), state,
                                                 reservation, allocator=allocator), ("NOT_FOUND", [], state))
                self.assertEqual(disaster_attempt(Disaster(), history, fresh.lineage,
                                                  reservation=reservation, allocator=allocator), isolated)
        self.assertEqual(restore_attempt(restore, command, state, fresh, allocator=replace(allocator))[0], "RESTORED")
        self.assertEqual(disaster_attempt(Disaster(), history, fresh.lineage,
                                          reservation=fresh, allocator=allocator)[:2], ("EXPOSED", ["exposure"]))
        self.assertEqual(command_result(old, history=history), ("DEPENDENCY_UNAVAILABLE", []))
        self.assertEqual(command_result(replace(old, release=False), history=history), ("NOT_FOUND", []))

    def test_recovered_cut_cannot_replay_a_consumed_reservation(self):
        recovered = History()
        state = replace(INITIAL_RESTORE_STATE, history=recovered)
        allocator = AllocatorAuthority()
        outcome, _, previous = disaster_attempt(Disaster(), recovered, allocator=allocator)
        self.assertEqual((outcome, previous.active), ("EXPOSED", "lineage-b"))
        self.assertNotIn("lineage-b", recovered.known_lineages)
        self.assertIn(("guild-a", "board-a", "lineage-b"), allocator.consumed)

        fresh = allocator.reservation("guild-a", "board-a", "lineage-c")
        self.assertNotEqual(fresh.generation, recovered.storage_generation)
        for target, reservation, source in (
            ("lineage-b", FIXTURE_RESERVATION, allocator),
            ("lineage-b", FIXTURE_RESERVATION, replace(allocator, epoch=1, generation="generation-a")),
            ("lineage-c", fresh, None),
            ("lineage-c", fresh, replace(allocator, current=False)),
            ("lineage-c", fresh, replace(allocator, issuer="recovered-inventory")),
        ):
            with self.subTest(target=target, source=source):
                before = None if source is None else replace(source)
                self.assertEqual(restore_attempt(Restore(target_lineage=target), state=state,
                                                 reservation=reservation, allocator=source),
                                 ("DEPENDENCY_UNAVAILABLE", [], state))
                self.assertEqual(disaster_attempt(Disaster(), recovered, target,
                                                  reservation=reservation, allocator=source),
                                 ("ISOLATED", [], recovered))
                self.assertEqual(source, before)

        restore = Restore(target_lineage="lineage-c")
        serving_state = RestoreState(history=previous, revision=0)
        serving_command = replace(RESTORE_COMMAND, lineage="lineage-b")
        for stale_state, command in (
            (state, RESTORE_COMMAND),
            (replace(serving_state, history=replace(previous, storage_generation="generation-a")),
             serving_command),
            (replace(serving_state, history=replace(previous, active="lineage-a")), RESTORE_COMMAND),
            (replace(serving_state, revision=1), serving_command),
        ):
            with self.subTest(stale_state=stale_state):
                before = replace(allocator)
                self.assertEqual(restore_attempt(restore, command, stale_state, fresh, allocator=allocator),
                                 ("DEPENDENCY_UNAVAILABLE", [], stale_state))
                self.assertEqual(restore_attempt(restore, replace(command, release=False), stale_state, fresh,
                                                 allocator=allocator), ("NOT_FOUND", [], stale_state))
                self.assertEqual(allocator, before)
        for source in (allocator, None, replace(allocator, current=False)):
            with self.subTest(receipt_authority=source):
                self.assertEqual(restore_attempt(restore, Command(), state, fresh, allocator=source),
                                 ("DEPENDENCY_UNAVAILABLE", [], state))
                self.assertEqual(restore_attempt(restore, Command(release=False), state, fresh,
                                                 allocator=source), ("NOT_FOUND", [], state))

        # Fork the authority fixture to exercise two alternative cutovers.
        restore_allocator = replace(allocator)
        outcome, effects, restored = restore_attempt(restore, serving_command, serving_state,
                                                     fresh, allocator=restore_allocator)
        self.assertEqual(outcome, "RESTORED")
        self.assertIn("receipt", effects)
        self.assertEqual(restored.history.active, "lineage-c")
        self.assertEqual(restored.history.storage_generation, fresh.generation)
        self.assertEqual(restored.artifacts[0].receipt_transaction,
                         (fresh.generation, identity(serving_command), 1))
        self.assertEqual(restored.receipts, ((identity(serving_command), (serving_command.digest, 1)),))
        self.assertIn(("guild-a", "board-a", "lineage-c"), restore_allocator.consumed)

        outcome, effects, promoted = disaster_attempt(Disaster(), recovered, "lineage-c",
                                                       reservation=fresh, allocator=allocator)
        self.assertEqual((outcome, effects, promoted.active), ("EXPOSED", ["exposure"], "lineage-c"))
        self.assertEqual(promoted.storage_generation, allocator.generation)
        self.assertIn(("guild-a", "board-a", "lineage-c"), allocator.consumed)

    def test_restore_receipt_lookup_requires_authoritative_serving_inventory(self):
        allocator = AllocatorAuthority()
        _, _, before_disaster = restore_attempt(Restore(), allocator=allocator)
        self.assertEqual(before_disaster.receipts, (
            *INITIAL_RESTORE_STATE.receipts, (identity(RESTORE_COMMAND), (RESTORE_COMMAND.digest, 8)),
        ))
        outcome, _, promoted = disaster_attempt(Disaster(), History(), "lineage-c",
                                                reservation=allocator.reservation("guild-a", "board-a", "lineage-c"),
                                                allocator=allocator)
        self.assertEqual((outcome, promoted.active), ("EXPOSED", "lineage-c"))
        retained = Command(operation="retained-before-recovery")
        current = RestoreState(history=promoted, revision=0,
                               receipts=((identity(retained), (retained.digest, 6)),))
        self.assertNotIn(identity(RESTORE_COMMAND), dict(current.receipts))
        for attempt in (
            RESTORE_COMMAND, replace(RESTORE_COMMAND, digest="different"),
            Command(), Command(digest="different"),
        ):
            for state in (before_disaster, current):
                with self.subTest(attempt=attempt, state=state):
                    self.assertEqual(restore_attempt(Restore(), attempt, state, allocator=allocator),
                                     ("DEPENDENCY_UNAVAILABLE", [], state))
                    self.assertEqual(restore_attempt(Restore(), replace(attempt, release=False), state,
                                                     allocator=allocator), ("NOT_FOUND", [], state))
                    self.assertEqual(restore_attempt(Restore(), replace(attempt, read=False), state,
                                                     allocator=allocator), ("NOT_FOUND", [], state))

        empty_cut = replace(current, receipts=())
        for command in (Command(), Command(digest="different")):
            self.assertEqual(restore_attempt(Restore(), command, empty_cut, allocator=allocator),
                             ("DEPENDENCY_UNAVAILABLE", [], empty_cut))

        self.assertEqual(restore_attempt(Restore(), retained, current, allocator=allocator),
                         ("ACK_HISTORICAL_6", [], current))
        self.assertEqual(restore_attempt(Restore(), replace(retained, digest="different"), current,
                                         allocator=allocator), ("IDEMPOTENCY_CONFLICT", [], current))
        self.assertEqual(restore_attempt(Restore(), replace(retained, release=False), current,
                                         allocator=allocator), ("NOT_FOUND", [], current))

    def test_restore_receipt_lookup_requires_scoped_independent_issuer(self):
        allocator = AllocatorAuthority()
        _, _, state = restore_attempt(Restore(), allocator=allocator)
        attempts = (
            (RESTORE_COMMAND, "ACK_HISTORICAL_8"),
            (replace(RESTORE_COMMAND, digest="different"), "IDEMPOTENCY_CONFLICT"),
            (replace(RESTORE_COMMAND, operation="absent"), "LINEAGE_CHANGED"),
        )
        for command, expected in attempts:
            self.assertEqual(restore_attempt(Restore(), command, state, allocator=allocator),
                             (expected, [], state))
            self.assertEqual(restore_attempt(Restore(), replace(command, release=False), state,
                                             allocator=allocator), ("NOT_FOUND", [], state))

            # All supplied authorities report the same generation, lineage and revision.
            for source in (
                replace(allocator, issuer="recovered-inventory"),
                replace(allocator, issuer=None),
                replace(allocator, current=False),
                replace(allocator, guild="foreign"),
                replace(allocator, board="foreign"),
            ):
                with self.subTest(command=command, source=source):
                    before = replace(source)
                    self.assertEqual(restore_attempt(Restore(), command, state, allocator=source),
                                     ("DEPENDENCY_UNAVAILABLE", [], state))
                    for denied in (replace(command, read=False), replace(command, release=False)):
                        self.assertEqual(restore_attempt(Restore(), denied, state, allocator=source),
                                         ("NOT_FOUND", [], state))
                    self.assertEqual(source, before)

    def test_current_commit_witness_binds_scope_intent_and_atomic_records(self):
        allocator = AllocatorAuthority()
        history = History().promote("lineage-b", FIXTURE_RESERVATION, set(), allocator=allocator)
        allocator.serving_revision = 7
        state = RestoreState(history=history)
        command = replace(RESTORE_COMMAND, lineage=history.active)
        restore = Restore(target_lineage="lineage-c")
        reservation = allocator.reservation("guild-a", "board-a", "lineage-c")
        witness = model_witness(command, history, revision=8)
        committed_allocator = replace(allocator)
        outcome, effects, committed = restore_attempt(restore, command, state, reservation, witness,
                                                       allocator=committed_allocator)
        self.assertEqual(outcome, "RESTORED")
        self.assertTrue(effects)
        artifact, = committed.artifacts
        transaction = (history.storage_generation, identity(command), 8)
        self.assertEqual(artifact.final_cut, (command.guild, command.board, command.lineage, 8))
        self.assertEqual(committed.receipts, ((identity(command), (command.digest, 8)),))
        self.assertEqual((artifact.event_transaction, artifact.receipt_transaction, artifact.outbox_transaction),
                         (transaction, transaction, transaction))

        next_state = replace(state, revision=8)
        next_allocator = replace(allocator, serving_revision=8)
        next_witness = model_witness(command, history, revision=9)
        next_outcome, next_effects, next_commit = restore_attempt(
            restore, command, next_state, reservation, next_witness, allocator=replace(next_allocator),
        )
        self.assertEqual((next_outcome, next_effects), ("RESTORED", effects))
        self.assertEqual(next_commit.receipts, ((identity(command), (command.digest, 9)),))
        self.assertEqual(restore_attempt(restore, command, next_state, reservation, witness,
                                         allocator=replace(next_allocator)),
                         ("DEPENDENCY_UNAVAILABLE", effects, next_commit))
        self.assertEqual(restore_attempt(restore, replace(command, release=False), next_state,
                                         reservation, witness, allocator=replace(next_allocator)),
                         ("NOT_FOUND", effects, next_commit))

        for unproven in (
            None, replace(witness, generation=History().storage_generation),
            replace(witness, operation=("foreign", *witness.operation[1:])),
            replace(witness, intent_digest="other"),
            replace(witness, revision=9),
            replace(witness, event_transaction=next_witness.event_transaction),
            replace(witness, receipt_transaction=next_witness.receipt_transaction),
            replace(witness, outbox_transaction=next_witness.outbox_transaction),
        ):
            with self.subTest(witness=unproven):
                self.assertEqual(restore_attempt(restore, command, state, reservation, unproven,
                                                 allocator=replace(allocator)),
                                 ("DEPENDENCY_UNAVAILABLE", effects, committed))
                self.assertEqual(restore_attempt(restore, replace(command, release=False), state,
                                                 reservation, unproven, allocator=replace(allocator)),
                                 ("NOT_FOUND", effects, committed))
                self.assertEqual(restore_attempt(restore, command, committed, reservation, None,
                                                 allocator=committed_allocator),
                                 ("ACK_HISTORICAL_8", [], committed))

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
                    "catalog": {
                        "prior", "expanded", "backfilled", "verified", "activated",
                        "contracted", "unrecognized",
                    },
                    "journal": MIGRATION_STEPS.keys(),
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
