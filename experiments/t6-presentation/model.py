"""Research model v0; NOT application code, wire schema, or accepted T6 contract.

Identity/read/control/write decisions are trusted inputs supplied by a hypothetical
T2 boundary. No Discord authorization is implemented here. Calls are serial steps.
"""
from dataclasses import dataclass, replace
from math import isfinite

MODES = ('open', 'moderated', 'locked', 'request-to-draw')
MAX_SCOPE_HISTORY = 8  # finite research budget; never evict a replay fence


@dataclass(frozen=True)
class Authority:
    scope: tuple = ('guild-a', 'board-a')
    revision: int = 0
    epoch: int = 0
    mode: str = 'moderated'
    presenter: str | None = None


def transition(state, expected, *, control_allowed, mode=None, presenter=None):
    """Replace mode/presenter atomically; every successful change fences streams.

    Omitted presenter means revoke, including a mode-only change. This conservative
    choice is an experiment, not an accepted lifecycle policy.
    """
    if not control_allowed:
        return state, 'forbidden'
    if type(expected) is not int or expected != state.revision:
        return state, 'stale-revision'
    mode = state.mode if mode is None else mode
    if mode not in MODES or (presenter is not None and
                            (type(presenter) is not str or not 1 <= len(presenter) <= 64)):
        return state, 'invalid'
    return replace(state, revision=state.revision + 1, epoch=state.epoch + 1,
                   mode=mode, presenter=presenter), 'ok'


def can_write(state, *, current_t2_write_allowed, session_valid, scope_matches):
    # Presentation/follow does not occur in this expression. T2 owns the role and
    # temporary-grant matrix; no claim that all readers can write in open mode.
    return bool(session_valid and scope_matches and current_t2_write_allowed
                and state.mode != 'locked')


def valid_view(view):
    return (type(view) is tuple and len(view) == 3
            and all(type(n) in (int, float) for n in view)
            # Compare bounds before isfinite: huge Python integers cannot safely
            # convert to float, but bounded integers can. NaN fails comparisons.
            and abs(view[0]) <= 1_000_000 and abs(view[1]) <= 1_000_000
            and 0.1 <= view[2] <= 10
            and all(isfinite(n) for n in view))


@dataclass(frozen=True)
class Packet:
    scope: tuple
    epoch: int
    sender: str
    sequence: int
    view: tuple


def admitted(state, packet, *, session_valid, read_allowed):
    """Server-side publication gate at a serial authority boundary."""
    return (session_valid and read_allowed and packet.scope == state.scope
            and type(packet.epoch) is int and packet.epoch == state.epoch
            and state.presenter is not None and packet.sender == state.presenter
            and type(packet.sequence) is int and 0 <= packet.sequence <= 2**53 - 1
            and valid_view(packet.view))


@dataclass(frozen=True)
class StreamMemory:
    authority: Authority
    sequence: int
    presenter_view: tuple | None


@dataclass(frozen=True)
class Viewer:
    authority: Authority
    personal: tuple = (0, 0, 1)
    displayed: tuple = (0, 0, 1)
    following: bool = False
    sequence: int = -1
    presenter_view: tuple | None = None
    history: tuple[StreamMemory, ...] = ()


def snapshot(viewer, authority):
    """Trusted current snapshot; explicit Follow required after any switch.

    Retain bounded per-scope stream fences, never personal navigation. Exhaustion
    fails explicitly without evicting a fence; a fresh validated stream baseline
    is outside this model. Raise ValueError without changing viewer when the
    target scope is unseen and MAX_SCOPE_HISTORY distinct scopes are retained.
    History uses first-seen scope insertion order; refreshing a known scope
    replaces its entry in place. No untrusted packet can add a scope to history.
    """
    history = {entry.authority.scope: entry for entry in viewer.history}
    history[viewer.authority.scope] = StreamMemory(
        viewer.authority, viewer.sequence, viewer.presenter_view)
    previous = history.get(authority.scope)
    if previous is not None and authority.revision < previous.authority.revision:
        return viewer
    if previous is None and len(history) >= MAX_SCOPE_HISTORY:
        raise ValueError('scope history budget exhausted; validated fresh stream required')
    same_stream = previous is not None and authority.epoch == previous.authority.epoch
    sequence = previous.sequence if same_stream else -1
    presenter_view = previous.presenter_view if same_stream else None
    history[authority.scope] = StreamMemory(authority, sequence, presenter_view)
    personal = viewer.personal if authority.scope == viewer.authority.scope else (0, 0, 1)
    return Viewer(authority, personal=personal, displayed=personal,
                  sequence=sequence, presenter_view=presenter_view,
                  history=tuple(history.values()))


def follow(viewer):
    if viewer.authority.presenter is None:
        return viewer
    # Restore the last current-stream view without resetting replay protection or
    # overwriting personal navigation. No packet is needed for an explicit rejoin.
    view = viewer.presenter_view if viewer.presenter_view is not None else viewer.personal
    return replace(viewer, following=True, displayed=view)


def unfollow(viewer):
    return replace(viewer, following=False, displayed=viewer.personal)


def navigate(viewer, view):
    if not valid_view(view):
        return viewer
    return replace(viewer, personal=view, displayed=view, following=False)


def receive(viewer, packet):
    # Client receives only server-admitted packets, but stale delivery still exists.
    if (not admitted(viewer.authority, packet, session_valid=True, read_allowed=True)
            or packet.sequence <= viewer.sequence):
        return viewer
    return replace(viewer, displayed=packet.view if viewer.following else viewer.displayed,
                   sequence=packet.sequence,
                   presenter_view=packet.view)
