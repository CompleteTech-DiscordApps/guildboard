"""Finite research counterexample, NOT Guildboard authorization/runtime code.

Compare checking authority only at prepare with an atomic commit-time fence.
There is one actor, one object and one abstract atomic commit. No networking,
Discord, SQL locks, tenant isolation or crash durability is represented.
"""

from dataclasses import asdict, dataclass, replace
from itertools import product
import json
import sys


ACTIONS = ("prepare", "revoke", "grant", "commit")


@dataclass(frozen=True)
class State:
    generation: int = 0
    can_write: bool = True
    prepared_generation: int | None = None
    accepted: int = 0


def step(state: State, action: str, *, fenced: bool) -> State:
    if action == "prepare":
        return replace(
            state, prepared_generation=state.generation if state.can_write else None
        )
    if action in ("revoke", "grant"):
        return replace(
            state, generation=state.generation + 1, can_write=action == "grant"
        )
    if action != "commit":
        raise ValueError("unknown abstract action")
    allowed = state.prepared_generation is not None
    if fenced:
        allowed = (
            allowed
            and state.can_write
            and state.prepared_generation == state.generation
        )
    # Consuming the prepared command prevents a repeated commit in this toy model.
    # It does not model runtime operation IDs, receipts or retry semantics.
    return replace(
        state, prepared_generation=None, accepted=state.accepted + int(allowed)
    )


def run_trace(actions: tuple[str, ...], *, fenced: bool) -> list[dict]:
    state = State()
    records = []
    for action in actions:
        before = state
        state = step(state, action, fenced=fenced)
        records.append(
            {"action": action, "before": asdict(before), "after": asdict(state)}
        )
    return records


def violations(records: list[dict]) -> int:
    return sum(
        row["after"]["accepted"] > row["before"]["accepted"]
        and (
            not row["before"]["can_write"]
            or row["before"]["prepared_generation"] != row["before"]["generation"]
        )
        for row in records
    )


def experiment() -> dict:
    totals = {"prepare_only": 0, "commit_fence": 0}
    histories = 0
    for length in range(1, 6):
        for actions in product(ACTIONS, repeat=length):
            histories += 1
            for name, fenced in (("prepare_only", False), ("commit_fence", True)):
                totals[name] += violations(run_trace(actions, fenced=fenced))
    counterexample = ("prepare", "revoke", "commit")
    return {
        "evidence_kind": "abstract-model-only",
        "model_version": 1,
        "maximum_trace_length": 5,
        "histories_per_design": histories,
        "stale_or_revoked_commits": totals,
        "counterexample": {
            "actions": list(counterexample),
            "prepare_only": run_trace(counterexample, fenced=False),
            "commit_fence": run_trace(counterexample, fenced=True),
        },
        "limitations": [
            "One actor and object; sequential atomic abstract events only.",
            "No Discord, browser, tenant, session, SQL, network or crash evidence.",
            "Atomic fencing is an assumption, not an implemented database result.",
        ],
    }


if __name__ == "__main__":
    # Canonical UTF-8/LF bytes make the report identical on Windows and Linux.
    sys.stdout.buffer.write(
        (json.dumps(experiment(), indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
