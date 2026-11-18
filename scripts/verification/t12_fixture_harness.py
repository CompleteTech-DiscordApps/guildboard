"""Offline fixture support for GB-T12.01.01.T1."""

import os
import stat
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import mkdtemp


class InvalidConfiguration(ValueError):
    """The diagnostic contains only the invalid field name."""


class PrerequisiteUnavailable(RuntimeError):
    """A real integration target requires capabilities outside this harness."""


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
    try:
        root = config.root.lstat()
    except (OSError, ValueError):
        raise InvalidConfiguration("root") from None
    if (
        not stat.S_ISDIR(root.st_mode)
        or root.st_uid != os.geteuid()
        or stat.S_IMODE(root.st_mode) != 0o700
    ):
        raise InvalidConfiguration("root")
    if config.target == "integration":
        raise PrerequisiteUnavailable("sql_engine,migrations,api,policy,storage,bot")


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
    def __init__(self, config: HarnessConfig, fixture: Fixture):
        self.fixture = fixture
        self.clock = FixtureClock()
        self.identity = FakeDiscordIdentity(fixture)
        self._namespace = Path(mkdtemp(prefix="t12-fixture-", dir=config.root))
        self._cleanup_timeout = config.cleanup_timeout_seconds
        self._worker = None
        self._active = True

    @property
    def namespace(self) -> Path:
        return self._namespace

    def start_worker(self) -> int:
        """Start the single owned lifecycle probe and return its PID."""
        if not self._active or self._worker is not None:
            raise RuntimeError("worker")
        self._worker = subprocess.Popen(
            [sys.executable, "-I", "-S", "-c", "import sys; sys.stdin.buffer.read()"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=self.namespace,
            env={},
        )
        return self._worker.pid

    def _close(self) -> None:
        self._active = False
        if self._worker is not None:
            # The process has no descendants and is the only handle we signal.
            try:
                self._worker.kill()
                self._worker.wait(timeout=self._cleanup_timeout)
            finally:
                self._worker.stdin.close()
        # A failed reap or unexpected contents leave the namespace for inspection.
        self.namespace.rmdir()


@contextmanager
def fixture_run(config: HarnessConfig):
    """Open an owned fixture namespace after checking the setup."""
    _preflight(config)
    run = _FixtureRun(config, _make_fixture(config.seed))
    try:
        yield run
    finally:
        run._close()
