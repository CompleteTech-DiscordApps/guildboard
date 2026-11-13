"""Finite scalar-element research model, NOT a product service or wire codec.

Calls are serialized atomically by the experiment. No database, transport,
thread synchronization, real authorization or Excalidraw execution is modeled.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class Context:
    guild: str = "guild-A"
    actor: str = "actor-A"
    readable: bool = True
    writable: bool = True
    session_valid: bool = True


@dataclass(frozen=True)
class Change:
    element: str
    expected: int
    value: int | None


@dataclass(frozen=True)
class Command:
    operation: str
    changes: tuple[Change, ...]
    guild: str = "guild-A"
    board: str = "board-A"
    lineage: str = "lineage-A"
    policy: int = 1
    base: int = 0

    def digest(self):
        # Closed scalar domain: integer values, strings, null, no JSON floats.
        return hashlib.sha256(json.dumps(self.__dict__ | {
            "changes": [c.__dict__ for c in self.changes]
        }, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class Board:
    def __init__(self, strategy="element"):
        assert strategy in ("element", "board")
        self.strategy = strategy
        self.guild, self.board, self.lineage = "guild-A", "board-A", "lineage-A"
        self.policy, self.revision = 1, 0
        self.elements = {key: (0, 0) for key in "ABC"}  # version, scalar value/tombstone
        self.receipts, self.events = {}, []

    def observable(self):
        return deepcopy((self.elements, self.receipts, self.events, self.revision))

    def submit(self, ctx, cmd, crash=None):
        if not ctx.session_valid:
            return "UNAUTHENTICATED", None
        if ctx.guild != self.guild or cmd.guild != self.guild or cmd.board != self.board or not ctx.readable:
            return "NOT_FOUND", None
        if (not isinstance(cmd.operation, str) or not 1 <= len(cmd.operation) <= 64
                or not 1 <= len(cmd.changes) <= 100
                or type(cmd.base) is not int or cmd.base < 0
                or type(cmd.policy) is not int or cmd.policy < 1):
            return "INVALID", None
        if any(not isinstance(c, Change) or not isinstance(c.element, str)
               or len(c.element) > 64 or type(c.expected) is not int or c.expected < 0
               or (c.value is not None and (type(c.value) is not int or abs(c.value) > 1000000))
               for c in cmd.changes):
            return "INVALID", None
        if len({c.element for c in cmd.changes}) != len(cmd.changes):
            return "INVALID", None
        identity = (self.guild, self.board, cmd.lineage, ctx.actor, cmd.operation)
        digest = cmd.digest()
        if identity in self.receipts:
            old_digest, revision = self.receipts[identity]
            return ("ACCEPTED", revision) if old_digest == digest else ("IDEMPOTENCY_CONFLICT", None)
        if cmd.lineage != self.lineage:
            return "LINEAGE_CHANGED", None
        if cmd.base > self.revision:
            return "INVALID", None
        if not ctx.writable:
            return "FORBIDDEN", None
        if cmd.policy != self.policy:
            return "POLICY_STALE", None
        if self.strategy == "board" and cmd.base != self.revision:
            return "CONFLICT", None
        candidate = deepcopy(self.elements)
        for change in cmd.changes:
            old = candidate.get(change.element)
            if old is None or old[0] != change.expected or old[1] is None:
                return "CONFLICT", None
            candidate[change.element] = (old[0] + 1, change.value)
        if crash == "before_commit":
            return "UNKNOWN", None
        # A single modeled atomic transition, not evidence of a real SQL transaction.
        self.revision += 1
        self.elements = candidate
        self.receipts[identity] = digest, self.revision
        self.events.append({"lineage": self.lineage, "revision": self.revision,
                            "changes": {c.element: candidate[c.element] for c in cmd.changes}})
        return ("UNKNOWN", None) if crash == "after_commit" else ("ACCEPTED", self.revision)

    def revoke(self):
        self.policy += 1

    def restore(self):
        """Reset content while retaining scoped receipts for historical retries."""
        self.lineage = "lineage-B"
        self.revision = 0
        self.elements = {key: (0, 0) for key in "ABC"}
        self.events = []


class Replica:
    """Bounded replay toy; on overflow caller must fetch a validated snapshot."""
    def __init__(self):
        self.lineage, self.revision = "lineage-A", 0
        self.elements = {key: (0, 0) for key in "ABC"}
        self.pending = {}

    def deliver(self, event):
        if event["lineage"] != self.lineage:
            return "SNAPSHOT_REQUIRED"
        revision = event["revision"]
        if revision <= self.revision:
            return "DUPLICATE"
        if revision in self.pending and self.pending[revision] != event:
            return "INCONSISTENT_EVENT"
        if revision > self.revision + 1:
            if revision not in self.pending and len(self.pending) >= 3:
                return "SNAPSHOT_REQUIRED"
            self.pending[revision] = deepcopy(event)
            return "GAP"
        # A contiguous event consumes no reorder-buffer slot, even when full.
        self.revision = revision
        self.elements.update(deepcopy(event["changes"]))
        while self.revision + 1 in self.pending:
            self.revision += 1
            self.elements.update(self.pending.pop(self.revision)["changes"])
        return "APPLIED"
