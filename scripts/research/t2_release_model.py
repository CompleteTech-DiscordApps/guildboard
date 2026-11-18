"""Finite offline read-release experiment, release-model v1 (not policy-model v1).

Trusted inputs, serialized scheduling and integer clock are assumptions. No network,
transport, SQL, production policy, external input or credential handling exists.
Do not import this research experiment into application code.
"""

from dataclasses import dataclass, replace
import json


MODEL_VERSION = "t2-release-v1"
KINDS = ("prepared_ack", "retained_receipt", "digest_conflict", "queued_chunk")
LOSSES = ("session_revoke", "session_expiry", "membership_invalidation",
          "read_policy_loss", "evidence_expiry", "time_unavailable",
          "policy_unavailable")


@dataclass(frozen=True)
class Authority:
    scoped: bool = True
    session_live: bool = True
    member: bool = True
    can_read: bool = True
    can_write: bool = True
    policy_known: bool = True
    time_known: bool = True
    now: int = 1
    session_until: int = 4  # Arbitrary ticks, never seconds or a recommended TTL.
    evidence_until: int = 3
    generation: int = 0


def read_error(a: Authority) -> str | None:
    if not a.scoped:
        return "NOT_FOUND"
    if not a.time_known:
        return "DEPENDENCY_UNAVAILABLE"
    if not a.session_live or a.now >= a.session_until:
        return "UNAUTHENTICATED"
    if not a.policy_known or a.now >= a.evidence_until:
        return "DEPENDENCY_UNAVAILABLE"
    if not a.member or not a.can_read:
        return "FORBIDDEN"
    return None


@dataclass(frozen=True)
class Effects:
    revision: int = 0
    receipts: int = 0
    events: int = 0
    outbox: int = 0


@dataclass(frozen=True)
class Packet:
    kind: str
    body: str  # Synthetic protected bytes, including receipt/digest-dependent data.


@dataclass(frozen=True)
class Public:
    status: str
    packet: Packet | None = None


@dataclass(frozen=True)
class State:
    authority: Authority = Authority()
    effects: Effects = Effects()
    committed: bool = False  # One fixed synthetic scoped operation identity.
    queue: tuple[Packet, ...] = ()
    emitted: tuple[Public, ...] = ()


def commit_once(s: State, expected_generation: int) -> tuple[str, State]:
    """Assumed atomic write fence; no actual transaction or crash recovery."""
    error = read_error(s.authority)
    if error:
        return error, s
    if s.committed:
        return "retained_receipt", s
    if not s.authority.can_write or expected_generation != s.authority.generation:
        return "WRITE_DENIED", s
    e = s.effects
    return "committed", replace(s, committed=True, effects=Effects(
        e.revision + 1, e.receipts + 1, e.events + 1, e.outbox + 1))


def prepare(kind: str, authority: Authority = Authority()) -> State:
    """Lookup/preparation is separate from release; no protected result emitted."""
    if kind not in KINDS:
        raise ValueError("unknown synthetic case")
    # Historical lookup cases start with one earlier accepted effect tuple.
    retained = kind in ("retained_receipt", "digest_conflict")
    s = State(authority, Effects(1, 1, 1, 1) if retained else Effects(), retained)
    error = read_error(authority)
    if error:
        return replace(s, emitted=(Public(error),))
    if kind == "prepared_ack":
        status, s = commit_once(s, authority.generation)
        if status != "committed":
            return replace(s, emitted=(Public(status),))
    # Three queued chunks expose checking only the first release as insufficient.
    count = 3 if kind == "queued_chunk" else 1
    return replace(s, queue=tuple(Packet(kind, f"synthetic:{kind}:{i}")
                                 for i in range(count)))


def invalidate(s: State, loss: str) -> State:
    changes = {
        "session_revoke": {"session_live": False},
        "session_expiry": {"now": s.authority.session_until},
        "membership_invalidation": {"member": False},
        "read_policy_loss": {"can_read": False},
        "evidence_expiry": {"now": s.authority.evidence_until},
        "time_unavailable": {"time_known": False},
        "policy_unavailable": {"policy_known": False},
    }
    a = replace(s.authority, **changes[loss])
    return replace(s, authority=replace(a, generation=a.generation + 1))


def release(s: State) -> State:
    """One indivisible current-check + emit step under the assumed shared fence.

    Denial cancels remaining application-queued protected packets. Already emitted
    bytes remain visible. Delivery denial cannot undo an accepted commit.
    """
    if not s.queue:
        return s
    error = read_error(s.authority)
    if error:
        return replace(s, queue=(), emitted=s.emitted + (Public(error),))
    return replace(s, queue=s.queue[1:], emitted=s.emitted + (Public("released", s.queue[0]),))


def stale_initial_only_control(s: State) -> State:
    """Intentionally unsafe offline comparator, using only prior preparation."""
    if not s.queue:
        return s
    return replace(s, queue=s.queue[1:], emitted=s.emitted + (Public("released", s.queue[0]),))


def released_count(s: State) -> int:
    return sum(item.packet is not None for item in s.emitted)


def experiment() -> dict:
    cases = denied = leaks = unsafe_leaks = effect_changes = 0
    already_released = fully_released = 0
    for kind in KINDS:
        prepared = prepare(kind)
        for loss in LOSSES:
            # Every cut: invalidate before first, between chunks, or after last.
            for cut in range(len(prepared.queue) + 1):
                s = prepared
                for _ in range(cut):
                    s = release(s)
                s = invalidate(s, loss)
                before = s
                candidate = release(s)
                unsafe = stale_initial_only_control(s)
                cases += 1
                already_released += released_count(before)
                if before.queue:
                    denied += 1
                    leaks += released_count(candidate) - released_count(before)
                    unsafe_leaks += released_count(unsafe) - released_count(before)
                else:
                    fully_released += 1
                effect_changes += int(candidate.effects != prepared.effects
                                      or candidate.committed != prepared.committed)
    return {
        "evidence_kind": "finite-offline-release-model-only",
        "model_version": MODEL_VERSION,
        "prepared_families": len(KINDS), "invalidation_types": len(LOSSES),
        "enumerated_schedules": cases, "denied_release_points": denied,
        "fully_released_before_loss": fully_released,
        "previously_released_packets_preserved": already_released,
        "candidate_protected_packets_after_loss": leaks,
        "stale_initial_only_protected_packets_after_loss": unsafe_leaks,
        "release_changed_committed_effects": effect_changes,
        "assumptions": [
            "Trusted scoped facts and synthetic complete retained-receipt lookup.",
            "Atomic shared ordering of authority changes, writes and each release.",
            "Trusted monotonic integer time, checked at the atomic release point.",
            "Three finite application-queued chunks; emitted bytes cannot be recalled.",
        ],
        "limitations": [
            "Enumerated schedules only, not a proof or arbitrary interleavings.",
            "No SQL, HTTP/WSS/bot, storage, Discord, OAuth or GoDaddy execution.",
            "No numeric freshness recommendation or upstream detection guarantee.",
            "No runtime queue bounds, crashes, multi-worker ordering or timing evidence.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(experiment(), indent=2, sort_keys=True))
