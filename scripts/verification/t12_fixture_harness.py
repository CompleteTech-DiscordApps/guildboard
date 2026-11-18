"""Offline fixture support for GB-T12.01.01.T1."""

import os
import signal
import stat
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class InvalidConfiguration(ValueError):
    """The diagnostic contains only the invalid field name."""


class PrerequisiteUnavailable(RuntimeError):
    """A real integration target requires capabilities outside this harness."""


@contextmanager
def _defer_sigint():
    """Defer SIGINT on the synchronous caller thread, without changing handlers."""
    # Read before changing the mask so even a failed block restores caller state.
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, set())
    try:
        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
        yield
    finally:
        try:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
        except BaseException:
            # Restoration can raise before applying the mask or after dispatching
            # a pending Python handler. One idempotent retry preserves either
            # outcome's original exception when restoration succeeds.
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
            raise


class FixtureClock:
    """Explicitly advanced UTC server time for a single fixture run."""

    def __init__(self):
        self._now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: int) -> None:
        if type(seconds) is not int or not 0 <= seconds <= 86_400:
            raise ValueError("seconds")
        self._now += timedelta(seconds=seconds)


@dataclass(frozen=True)
class Board:
    guild_id: str
    board_id: str
    asset_id: str
    receipt_id: str
    lineage_id: str


@dataclass(frozen=True)
class Actor:
    guild_id: str
    user_id: str
    fixture_role: str


@dataclass(frozen=True)
class Fixture:
    version: int
    seed: int
    boards: tuple[Board, ...]
    actors: tuple[Actor, ...]
    observer: Actor


class FakeDiscordIdentity:
    """Look up predetermined membership records in memory."""

    def __init__(self, fixture: Fixture):
        self._memberships = {
            (actor.guild_id, actor.user_id): actor
            for actor in (*fixture.actors, fixture.observer)
        }

    def membership(self, guild_id: str, user_id: str) -> Actor | None:
        return self._memberships.get((guild_id, user_id))


@dataclass(frozen=True)
class HarnessConfig:
    root: Path
    seed: int = 1
    target: str = "fixture"
    cleanup_timeout_seconds: int = 5


def _preflight(config: HarnessConfig) -> None:
    if type(config.target) is not str or config.target not in ("fixture", "integration"):
        raise InvalidConfiguration("target")
    if type(config.seed) is not int or not 0 <= config.seed <= 2_147_483_647:
        raise InvalidConfiguration("seed")
    timeout = config.cleanup_timeout_seconds
    if type(timeout) is not int or not 1 <= timeout <= 10:
        raise InvalidConfiguration("cleanup_timeout_seconds")
    if not isinstance(config.root, Path) or not config.root.is_absolute():
        raise InvalidConfiguration("root")


@contextmanager
def _private_root(path: Path):
    try:
        root_fd = os.open(path, _DIRECTORY_FLAGS)
    except (OSError, ValueError):
        raise InvalidConfiguration("root") from None
    try:
        root = os.fstat(root_fd)
        if root.st_uid != os.geteuid() or stat.S_IMODE(root.st_mode) != 0o700:
            raise InvalidConfiguration("root")
        yield root_fd
    finally:
        os.close(root_fd)


def _make_fixture(seed: int) -> Fixture:
    subject = f"guild-{seed}-subject"
    foreign = f"guild-{seed}-foreign"
    common_board = (f"board-{seed}", f"asset-{seed}", f"receipt-{seed}", f"lineage-{seed}")
    return Fixture(
        version=1,
        seed=seed,
        boards=(
            Board(subject, *common_board),
            Board(subject, *(f"{selector}-secondary" for selector in common_board)),
            Board(foreign, *common_board),
        ),
        actors=(
            Actor(subject, f"user-{seed}-viewer", "viewer"),
            Actor(subject, f"user-{seed}-moderator", "moderator"),
            Actor(subject, f"user-{seed}-revoked", "revoked"),
            Actor(foreign, f"user-{seed}-moderator", "foreign-control"),
        ),
        observer=Actor(subject, f"user-{seed}-observer", "observer"),
    )


class _FixtureRun:
    def __init__(self, config: HarnessConfig, fixture: Fixture, root_fd: int):
        self.fixture = fixture
        self.clock = FixtureClock()
        self.identity = FakeDiscordIdentity(fixture)
        self._cleanup_timeout = config.cleanup_timeout_seconds
        self._worker = None
        self._worker_acquisition_pending = False
        # Recovery state exists before the caller can acquire any worker.
        self._cleanup_completed = False
        self._cleanup_failure = None
        self._active = True
        self._root_fd = root_fd
        self._namespace_name = f"t12-fixture-{uuid4().hex}"
        self._namespace = config.root / self._namespace_name
        os.mkdir(self._namespace_name, mode=0o700, dir_fd=root_fd)
        try:
            created = self._namespace_entry()
        except OSError as error:
            raise RuntimeError("could not verify created fixture namespace") from error
        if not stat.S_ISDIR(created.st_mode) or created.st_uid != os.geteuid():
            raise RuntimeError("could not verify created fixture namespace")

        try:
            self._namespace_fd = os.open(self._namespace_name, _DIRECTORY_FLAGS, dir_fd=root_fd)
        except OSError:
            try:
                self._remove_namespace(created)
            except (OSError, RuntimeError) as error:
                raise RuntimeError("could not roll back fixture namespace acquisition") from error
            raise

    def _namespace_entry(self) -> os.stat_result:
        return os.stat(self._namespace_name, dir_fd=self._root_fd, follow_symlinks=False)

    def _remove_namespace(self, expected: os.stat_result) -> None:
        try:
            entry = self._namespace_entry()
        except FileNotFoundError:
            raise RuntimeError("fixture namespace identity changed") from None
        if not os.path.samestat(expected, entry):
            raise RuntimeError("fixture namespace identity changed")
        os.rmdir(self._namespace_name, dir_fd=self._root_fd)

    @property
    def namespace(self) -> Path:
        return self._namespace

    def start_worker(self) -> int:
        """Start the single owned lifecycle probe and return its PID."""
        if not self._active or self._worker is not None or self._worker_acquisition_pending:
            raise RuntimeError("worker")
        with _defer_sigint():
            # An exception without a returned handle does not prove zero children.
            self._worker_acquisition_pending = True
            self._worker = subprocess.Popen(
                [sys.executable, "-I", "-S", "-c", "import sys; sys.stdin.buffer.read()"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=f"/proc/self/fd/{self._namespace_fd}",
                pass_fds=(self._namespace_fd,),
                env={},
            )
            self._worker_acquisition_pending = False
        return self._worker.pid

    def _close(self) -> None:
        self._active = False
        with _defer_sigint():
            try:
                try:
                    if self._worker is not None:
                        # The process has no descendants and is the only handle we signal.
                        try:
                            self._worker.kill()
                            self._worker.wait(timeout=self._cleanup_timeout)
                        except Exception as error:
                            raise RuntimeError("fixture worker cleanup outcome unknown") from error
                        finally:
                            self._worker.stdin.close()
                    if self._worker_acquisition_pending:
                        raise RuntimeError("fixture worker acquisition outcome unknown")
                    # A failed reap or unexpected contents retain the namespace.
                    self._remove_namespace(os.fstat(self._namespace_fd))
                finally:
                    os.close(self._namespace_fd)
            except Exception as error:
                # A pending interrupt at mask restoration must preserve an
                # uncertain resource outcome, including a failed descriptor close.
                self._cleanup_failure = error
                raise
            finally:
                self._cleanup_completed = True


@contextmanager
def fixture_run(config: HarnessConfig):
    """Open an owned fixture namespace after checking the setup."""
    _preflight(config)
    with _private_root(config.root) as root_fd:
        if config.target == "integration":
            raise PrerequisiteUnavailable("sql_engine,migrations,api,policy,storage,bot")
        run = _FixtureRun(config, _make_fixture(config.seed), root_fd)
        # This guard is active before a worker can exist, including throughout
        # normal-exit dispatch and _close's preamble before masking SIGINT.
        try:
            try:
                yield run
            except BaseException as error:
                try:
                    run._close()
                except BaseException as cleanup_error:
                    if isinstance(error, (KeyboardInterrupt, SystemExit)):
                        raise error from cleanup_error
                    raise
                raise
            else:
                run._close()
        except (KeyboardInterrupt, SystemExit) as error:
            try:
                if not run._cleanup_completed:
                    # Exactly one recovery attempt; entry interruption has not
                    # closed the descriptor needed to identify the namespace.
                    run._close()
                if run._cleanup_failure is not None:
                    raise run._cleanup_failure
            except BaseException as cleanup_error:
                error.add_note("fixture cleanup failed; resources may remain")
                raise error from cleanup_error
            raise
