"""Bounded, dependency-free research oracle; never imported by application code.

An atomic in-memory commit is an ASSUMPTION. Enumerated sequential schedules
explore abstract interleavings, not SQL locks, process crashes or real networks.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
import random


class InvariantViolation(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise InvariantViolation(message)


@dataclass(frozen=True)
class Command:
    actor: str
    operation: str
    tenant: str = "guild-a"
    board: str = "board-a"
    lineage: int = 1
    base: int = 0
    epoch: int = 0
    expires_at: int = 100
    value: str = "synthetic"

    @property
    def key(self):
        return (self.tenant, self.board, self.lineage, self.actor, self.operation)

    @property
    def digest(self):
        # Research encoding only. No product canonical-codec selection.
        raw = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()


class Model:
    def __init__(self, defect=None):
        self.defect = defect
        self.revision = 0
        self.epoch = 0
        self.lineage = 1
        self.can_read = True
        self.can_write = True
        self.now = 0
        self.events = []
        self.receipts = {}
        self.content = {}
        self.acked = set()

    def prepare(self, actor, operation):
        return Command(actor, operation, lineage=self.lineage,
                       base=self.revision, epoch=self.epoch, value=actor)

    def durable(self):
        return deepcopy((self.revision, self.epoch, self.lineage, self.now, self.can_read,
                         self.can_write, self.events, self.receipts, self.content))

    def revoke(self):
        self.can_write = False
        self.epoch += 1

    def restore(self):
        # Abstract publication of an empty new lineage; retained receipts/events.
        # Not a backup restore and not a claim about physical atomicity.
        self.lineage += 1
        self.epoch += 1
        self.content = {}

    def commit(self, command):
        before = self.durable()
        result = self._commit(command)
        if result[0] not in {"accepted", "receipt"}:
            require(self.durable() == before, "denial mutated durable state")
        self.check()
        return result

    def _commit(self, command):
        if not self.can_read:
            return ("read-denied", None)
        if ((command.tenant, command.board) != ("guild-a", "board-a")
                and self.defect != "foreign-scope"):
            return ("scope-denied", None)
        if self.defect == "base-before-receipt" and command.base != self.revision:
            return ("base-conflict", None)
        old = self.receipts.get(command.key)
        if old:
            return (("receipt", old[1]) if old[0] == command.digest
                    else ("digest-conflict", None))
        if command.lineage != self.lineage:
            return ("lineage-denied", None)
        if self.defect != "prepare-only-authority":
            if not self.can_write or command.epoch != self.epoch:
                return ("write-denied", None)
        if self.now >= command.expires_at:
            return ("expired", None)
        if command.base != self.revision:
            return ("base-conflict", None)
        self.revision += 1
        event = {"revision": self.revision, "key": command.key,
                 "digest": command.digest, "epoch": command.epoch,
                 "authority_epoch": self.epoch, "write_allowed": self.can_write,
                 "value": command.value}
        self.content["object"] = command.value
        if self.defect != "split-commit":
            self.events.append(event)
        self.receipts[command.key] = (command.digest, self.revision)
        return ("accepted", self.revision)

    def ack(self, result):
        if result and result[0] in {"accepted", "receipt"}:
            self.acked.add(result[1])
        self.check()

    def crash(self):
        # Reconstruct server model from designated durable fields. External
        # driver/client command/results survive to retry; no process is killed.
        # All durable fields survive by assumption, not a disk/flush experiment.
        recovered = Model(self.defect)
        (recovered.revision, recovered.epoch, recovered.lineage, recovered.now,
         recovered.can_read, recovered.can_write, recovered.events,
         recovered.receipts, recovered.content) = self.durable()
        recovered.acked = set(self.acked)
        recovered.check()
        return recovered

    def check(self):
        revisions = [event["revision"] for event in self.events]
        require(revisions == list(range(1, self.revision + 1)), "revision/event gap")
        require(self.acked.issubset(set(revisions)), "acknowledged loss")
        require(len(self.receipts) == len(self.events), "receipt/event split")
        for event in self.events:
            require(event["key"][:2] == ("guild-a", "board-a"), "foreign mutation")
            require(event["write_allowed"] and
                    event["epoch"] == event["authority_epoch"], "stale authority")
            require(self.receipts[event["key"]] == (event["digest"], event["revision"]),
                    "receipt mismatch")
        active = [event for event in self.events if event["key"][2] == self.lineage]
        expected = {"object": active[-1]["value"]} if active else {}
        require(self.content == expected, "accepted projection differs")


def schedules(chains):
    """Every order preserving each chain; input size is fixed by this module."""
    if not any(chains):
        yield ()
    for index, chain in enumerate(chains):
        if chain:
            rest = list(chains)
            rest[index] = chain[1:]
            for tail in schedules(tuple(rest)):
                yield (chain[0],) + tail


def schedule_trial(order, defect=None):
    model = Model(defect)
    prepared, results = {}, {}
    for action in order:
        if action == "revoke":
            model.revoke()
        else:
            actor, phase = action.split(".")
            if phase == "prepare":
                prepared[actor] = model.prepare(actor, "one")
            elif phase == "commit":
                results[actor] = model.commit(prepared[actor])
            elif phase == "ack":
                model.ack(results[actor])
        model = model.crash()  # recovery oracle after every abstract boundary
    return len(model.events)


def special_trials(defect=None):
    model = Model(defect)
    command = model.prepare("a", "one")
    model = model.crash()  # crash before commit: no ACK, no event
    first = model.commit(command)
    model = model.crash()  # commit succeeded, ACK was lost
    require(first == ("accepted", 1), "initial command not accepted")
    second = model.commit(model.prepare("b", "two"))
    model.ack(second)
    retry = model.commit(command)
    require(retry == ("receipt", 1), "lost-ACK retry lost historical receipt")
    model.ack(retry)
    require(model.commit(replace(command, value="different"))[0] == "digest-conflict",
            "same identity/different content not rejected")
    model.restore()
    require(model.commit(command) == ("receipt", 1), "restore forgot retained receipt")
    require(model.content == {}, "historical receipt reapplied restored content")
    require(model.commit(replace(command, operation="unknown"))[0] == "lineage-denied",
            "unknown old-lineage command accepted")
    model.can_read = False
    require(model.commit(command)[0] == "read-denied", "receipt disclosed without read")
    model.can_read = True
    foreign = replace(model.prepare("c", "three"), tenant="guild-foreign")
    require(model.commit(foreign)[0] == "scope-denied", "foreign command accepted")
    return {"accepted_events": len(model.events), "restored_content": model.content,
            "lost_ack_retry": retry[0], "current_read_required": True}


def clock_trial():
    model = Model()
    command = replace(model.prepare("a", "expires"), expires_at=5)
    model.now = 4
    require(model.commit(command) == ("accepted", 1), "pre-expiry edit denied")
    command2 = replace(model.prepare("b", "boundary"), expires_at=5)
    model.now = 5
    require(model.commit(command2)[0] == "expired", "expiry boundary edit accepted")
    return {"last_valid_tick": 4, "first_denied_tick": 5,
            "clock": "injected-logical-server-ticks-not-wall-time"}


def seeded_trial(seed, steps=48):
    require(type(seed) is int and 0 <= seed < 32, "seed outside bounded corpus")
    require(type(steps) is int and 1 <= steps <= 48, "step bound exceeded")
    rng, model, counts = random.Random(seed), Model(), Counter()
    pending = [model.prepare("a", "initial")]
    for step in range(steps):
        action = rng.choice(("new", "deliver", "duplicate", "revoke", "restore", "crash"))
        counts[action] += 1
        if action == "new":
            pending.append(model.prepare(rng.choice(("a", "b")), str(step)))
        elif action in {"deliver", "duplicate"}:
            command = rng.choice(pending)
            result = model.commit(command)
            if rng.choice((True, False)):
                model.ack(result)
        elif action == "revoke":
            model.revoke()
        elif action == "restore":
            model.restore()
        else:
            model = model.crash()
        model.check()
    return dict(sorted(counts.items()))


def experiment():
    chains = (("a.prepare", "a.commit", "a.ack"),
              ("b.prepare", "b.commit", "b.ack"), ("revoke",))
    corpus = tuple(schedules(chains))
    outcomes = Counter(schedule_trial(order) for order in corpus)
    controls = {}
    for defect in ("prepare-only-authority", "foreign-scope", "split-commit",
                   "base-before-receipt"):
        try:
            if defect == "prepare-only-authority":
                for order in corpus:
                    schedule_trial(order, defect)
            else:
                special_trials(defect)
        except InvariantViolation as error:
            controls[defect] = str(error)
        else:
            raise InvariantViolation("negative control escaped: " + defect)
    premature = Model()
    premature.acked.add(1)  # deliberately broken ACK-before-COMMIT control
    try:
        premature.check()
    except InvariantViolation as error:
        controls["ack-before-commit"] = str(error)
    else:
        raise InvariantViolation("premature ACK control escaped")
    return {"experiment_version": 1, "kind": "abstract-serial-schedule-exploration",
            "runtime_or_platform_acceptance": False,
            "atomic_commit_is_assumed": True, "schedules": len(corpus),
            "recovery_boundaries": sum(len(order) for order in corpus),
            "accepted_event_count_distribution": dict(sorted(outcomes.items())),
            "seeded_traces": [seeded_trial(seed) for seed in range(32)],
            "seeded_steps": 32 * 48, "special_trials": special_trials(),
            "clock_trial": clock_trial(),
            "unsafe_controls_detected": controls}


if __name__ == "__main__":
    print(json.dumps(experiment(), indent=2, sort_keys=True))
