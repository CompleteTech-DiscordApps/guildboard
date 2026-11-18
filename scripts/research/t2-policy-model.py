"""Hypothetical policy comparison, NOT Guildboard authorization/runtime code.

Inputs are trusted abstract facts, not a wire schema. No Discord, SQL, token,
role-API, clock synchronization or distributed atomicity is implemented.
Policy choices here are candidates requiring T2/T6 review, not accepted defaults.
"""

from dataclasses import dataclass, replace
from itertools import product
import json
import sys


@dataclass(frozen=True)
class Facts:
    guild_matches: bool = True
    board_matches: bool = True
    session_live: bool = True
    member: bool = True
    board_visible: bool = True
    observed_tick: int = 0
    evidence_ttl: int = 10  # Arbitrary model ticks, not a proposed production TTL.
    now: int = 1
    roles: frozenset[str] = frozenset({"writer"})
    restricted: bool = False
    view_only: bool = False
    lockdown: bool = False
    mode_allows_edit: bool = True  # External hypothetical mode predicate.
    moderator_edits: bool = False
    grant_until: int = 0
    object_permitted: bool = True
    action: str = "edit"
    self_target: bool = False
    expected_generation: int = 0
    current_generation: int = 0
    receipt_present: bool = False  # Trusted server-lookup result, never client input.
    digest_matches: bool = True
    active_lineage: bool = True
    client_admin_claim: bool = False  # Deliberately irrelevant to authority.


@dataclass(frozen=True)
class Effects:
    revision: int = 0
    receipts: int = 0
    events: int = 0
    outbox: int = 0


def candidate(f: Facts) -> str:
    if not (f.guild_matches and f.board_matches):
        return "hidden_resource"
    if not f.session_live:
        return "unauthenticated"
    if not (0 <= f.now - f.observed_tick < f.evidence_ttl):
        return "evidence_stale"
    if not (f.member and f.board_visible):
        return "read_denied"
    # Match #481's proposed read -> receipt/digest -> lineage -> NEW-write order.
    if f.action == "edit" and f.receipt_present:
        return "historical_receipt" if f.digest_matches else "digest_conflict"
    if f.action == "edit" and not f.active_lineage:
        return "lineage_changed"
    if f.expected_generation != f.current_generation:
        return "policy_stale"
    if f.action == "map_roles":
        return "control_allowed" if "admin" in f.roles and not f.self_target else "control_denied"
    if f.action == "grant":
        return ("control_allowed" if f.roles & {"moderator", "admin"}
                and not f.self_target else "control_denied")
    if f.action != "edit":
        return "unknown_action"
    if f.restricted or f.view_only or f.lockdown or not f.mode_allows_edit:
        return "hard_edit_denial"
    if not f.object_permitted:
        return "object_denied"
    has_write = ("writer" in f.roles or f.now < f.grant_until
                 or ("moderator" in f.roles and f.moderator_edits))
    return "new_write" if has_write else "no_write_capability"


def apply_edit(f: Facts, before: Effects) -> tuple[str, Effects]:
    outcome = candidate(f)
    if outcome != "new_write":
        return outcome, before
    # Abstract atomicity assumed. No locks, durable transaction or audit system.
    return outcome, Effects(before.revision+1, before.receipts+1,
                            before.events+1, before.outbox+1)


def publish_refresh(current_generation: int, request_generation: int) -> bool:
    """Can a delayed response publish after a known invalidation? Model only."""
    return request_generation == current_generation


def experiment() -> dict:
    matrix = 0
    candidate_hard_denial_bypasses = 0
    allow_first_hard_denial_bypasses = 0
    names = ("viewer", "writer", "moderator", "admin")
    for role_bits in product((False, True), repeat=4):
        roles = frozenset(name for name, enabled in zip(names, role_bits) if enabled)
        for fresh, grant, restricted, locked, mode, mod_edits, view_only in product((False, True), repeat=7):
            f = Facts(roles=roles, now=1 if fresh else 10, grant_until=20 if grant else 0,
                      restricted=restricted, lockdown=locked, mode_allows_edit=mode,
                      moderator_edits=mod_edits, view_only=view_only)
            hard_deny = not fresh or restricted or locked or not mode or view_only
            # Intentionally unsafe negative control: grants/roles win first.
            allow_first = bool(roles & {"writer", "moderator", "admin"}) or grant
            allow_first_hard_denial_bypasses += int(hard_deny and allow_first)
            candidate_hard_denial_bypasses += int(hard_deny and candidate(f) == "new_write")
            matrix += 1
    initial = Effects()
    delayed = Facts(now=2)  # Source says member; Discord changed at tick 1, unobserved.
    expired = replace(delayed, now=10)
    observed = replace(delayed, member=False, current_generation=1)
    pending = replace(Facts(), expected_generation=0, current_generation=1)
    traces = {
        "external_change_unobserved_within_ttl": {
            "actual_external_member": False, "cached_member": True,
            "outcome": candidate(delayed),
            "meaning": "Residual acceptance window; no instantaneous external freshness guarantee.",
        },
        "same_cache_at_expiry": {"outcome": candidate(expired)},
        "observed_external_removal": {"outcome": candidate(observed)},
        "application_revoke_after_prepare_before_commit": {
            "outcome": apply_edit(pending, initial)[0],
            "effects_unchanged": apply_edit(pending, initial)[1] == initial,
        },
        "delayed_refresh_after_known_invalidation": {
            "unsafe_unconditional_publish": True,
            "generation_fenced_publish": publish_refresh(1, 0),
        },
    }
    return {
        "evidence_kind": "hypothetical-policy-model-only", "model_version": 1,
        "arbitrary_ttl_ticks": 10, "matrix_cases": matrix,
        "hard_denial_bypasses": {"candidate": candidate_hard_denial_bypasses,
                                 "unsafe_allow_first": allow_first_hard_denial_bypasses},
        "traces": traces,
        "limitations": [
            "Trusted booleans/roles and atomic commit are assumptions, not verified inputs.",
            "No Discord API, SQL, client transport, production policy or elapsed-time guarantee.",
            "TTL bounds cache age, not age of Discord truth or upstream consistency delay.",
            "Control outcomes are decisions only; no grant/mapping persistence implemented.",
        ],
    }


if __name__ == "__main__":
    sys.stdout.buffer.write((json.dumps(experiment(), indent=2, sort_keys=True)+"\n").encode())
