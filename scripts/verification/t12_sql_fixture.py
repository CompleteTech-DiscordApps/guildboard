"""Opt-in, bounded SQL fixture; callers supply an owned disposable local engine.

Only trusted test SQL belongs here. This is not an application connection pool.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import math
import os
from pathlib import Path
import re
import secrets
import select
import signal
import stat
import subprocess
import time

from database import verify_initial_schema as schema


@dataclass(frozen=True)
class SqlFixtureConfig:
    client: Path
    socket: Path
    admin_user: str
    disposable: bool = False
    timeout_seconds: float = 30
    operation_timeout_seconds: float = 3
    cleanup_timeout_seconds: float = 5


class SqlFixtureError(RuntimeError):
    """Names-only classification; uncertain resources require owner reconciliation."""
    def __init__(self, phase, outcome, uncertain=()):
        super().__init__(f"{phase}:{outcome}")
        self.phase, self.outcome, self.uncertain = phase, outcome, tuple(uncertain)


def _validate(config):
    for field, maximum in (("timeout_seconds", 60), ("operation_timeout_seconds", 10),
                           ("cleanup_timeout_seconds", 10)):
        value = getattr(config, field)
        if type(value) not in (int, float) or not 0 < value <= maximum or not math.isfinite(value):
            raise ValueError(field)
    if config.disposable is not True:
        raise ValueError("disposable")
    if type(config.admin_user) is not str or not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", config.admin_user):
        raise ValueError("admin_user")
    for field in ("client", "socket"):
        path = getattr(config, field)
        try:
            if not isinstance(path, Path) or not path.is_absolute() or path.resolve(strict=True) != path:
                raise ValueError(field)
            info = path.stat()
            if field == "client":
                if (path.name not in {"mysql", "mariadb"} or not stat.S_ISREG(info.st_mode)
                    or info.st_uid not in {0, os.geteuid()} or info.st_mode & 0o022
                    or not os.access(path, os.X_OK)):
                    raise ValueError(field)
            else:
                parent = path.parent.stat()
                if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid()
                    or parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) != 0o700):
                    raise ValueError(field)
        except (OSError, RuntimeError):
            raise ValueError(field) from None
    try:
        if schema.sha(schema.SOURCE.read_bytes()) != schema.SOURCE_DIGEST:
            raise ValueError("migration")
    except OSError:
        raise ValueError("migration") from None


class _Session:
    """One client process with bounded I/O, query count, output and reap time."""
    def __init__(self, config, user, database, deadline):
        self.config, self.user = config, user
        self.database, self.deadline = database, deadline
        self.operation_timeout = config.operation_timeout_seconds
        self.buffer, self.queries, self.closed, self.tainted = b"", 0, False, False
        self.client = None

    def start(self):
        # The fixture registers this session before it can acquire a child.
        config, user, database = self.config, self.user, self.database
        argv = [str(config.client), "--no-defaults"]
        if config.client.name == "mysql":
            argv.append("--no-login-paths")
        argv += ["--protocol=socket", f"--socket={config.socket}", f"--user={user}",
                 "--batch", "--skip-column-names", "--unbuffered", "--skip-reconnect",
                 "--binary-mode", "--connect-timeout=1"]
        if database is not None:
            argv.append(f"--database={database}")
        if self.client is not None or self.closed or time.monotonic() >= self.deadline:
            raise SqlFixtureError("session", "unavailable")
        try:
            self.client = subprocess.Popen(argv, env={}, stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        except OSError:
            raise SqlFixtureError("session", "unavailable") from None
        os.set_blocking(self.client.stdin.fileno(), False)
        os.set_blocking(self.client.stdout.fileno(), False)

    def query(self, sql):
        if self.client is None or self.closed or self.tainted or type(sql) is not str or self.queries >= 1024:
            raise SqlFixtureError("query", "unavailable")
        try:
            encoded = sql.encode("ascii")
        except UnicodeError:
            raise ValueError("sql") from None
        if len(encoded) > 65536:
            raise ValueError("sql")
        self.queries += 1
        self.tainted = True
        marker = ("gb_end_" + secrets.token_hex(16)).encode("ascii")
        request = encoded + b";\nSELECT '" + marker + b"';\n"
        deadline = min(self.deadline, time.monotonic() + self.operation_timeout)
        lines, size = [], 0
        try:
            while request:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([], [self.client.stdin], [], remaining)[1]:
                    raise SqlFixtureError("query", "unknown")
                request = request[os.write(self.client.stdin.fileno(), request):]
            while True:
                line, sep, rest = self.buffer.partition(b"\n")
                if sep:
                    self.buffer = rest
                    if line == marker:
                        self.tainted = False
                        return lines
                    lines.append(line)
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([self.client.stdout], [], [], remaining)[0]:
                    raise SqlFixtureError("query", "unknown")
                chunk = os.read(self.client.stdout.fileno(), 4096)
                size += len(chunk)
                if not chunk or size > 65536:
                    raise SqlFixtureError("query", "unknown")
                self.buffer += chunk
        except (OSError, ValueError):
            raise SqlFixtureError("query", "unknown") from None

    def close(self):
        self.closed = True
        if self.client is None:
            return
        try:
            if self.client.poll() is None:
                self.client.kill()
            self.client.wait(timeout=0.5)
        except (OSError, subprocess.TimeoutExpired):
            raise SqlFixtureError("client_cleanup", "unknown") from None
        finally:
            self.client.stdin.close()
            self.client.stdout.close()


def _preflight(session):
    rows = session.query("SELECT VERSION(), @@global.skip_networking, @@session.autocommit")
    allowed = {f"{version}\t1\t1".encode("ascii") for version in schema.CATALOG}
    if len(rows) != 1 or rows[0] not in allowed:
        raise SqlFixtureError("preflight", "blocked")


class SqlFixture:
    def __init__(self, config):
        self.config = config
        # Database-level grants treat '_' and '%' as patterns on some engines.
        self.database = "gb12" + secrets.token_hex(16)
        self.observer_user = "gb12o_" + secrets.token_hex(10)
        self.generation = secrets.token_hex(16).upper()
        self.deadline = time.monotonic() + config.timeout_seconds
        self._owned, self._uncertain, self._sessions = [], [], []
        self._active, self._connections = True, 0

    @contextmanager
    def _connect(self, user, database, deadline):
        if self._active and (len(self._sessions) >= 4 or self._connections >= 32):
            raise SqlFixtureError("connections", "unavailable")
        self._connections += 1
        session = None
        # Register the child before a pending catchable SIGINT can be delivered.
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
        try:
            try:
                session = _Session(self.config, user, database, deadline)
                self._sessions.append(session)
                session.start()
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, previous)
            _preflight(session)
            yield session
        finally:
            if session is not None:
                session.close()
                if session in self._sessions:
                    self._sessions.remove(session)

    @contextmanager
    def writer(self):
        if not self._active:
            raise SqlFixtureError("fixture", "closed")
        with self._connect(self.config.admin_user, self.database, self.deadline) as session:
            yield session

    @contextmanager
    def observer(self):
        if not self._active:
            raise SqlFixtureError("fixture", "closed")
        with self._connect(self.observer_user, self.database, self.deadline) as session:
            yield session

    def _create(self, session, kind, sql):
        # Mark uncertainty before sending: cancellation can occur after COMMIT
        # but before acknowledgement or inventory registration in this process.
        self._uncertain.append(kind)
        session.query(sql)
        self._owned.append(kind)
        self._uncertain.remove(kind)

    def _setup(self):
        phase = "preflight"
        try:
            with self._connect(self.config.admin_user, None, self.deadline) as admin:
                phase = "create"
                self._create(admin, "database", f"CREATE DATABASE `{self.database}`")
                self._create(admin, "observer", f"CREATE USER '{self.observer_user}'@'localhost'")
                admin.query(f"GRANT SELECT ON `{self.database}`.* TO '{self.observer_user}'@'localhost'")
            phase = "migration"
            with self.writer() as writer:
                schema.migration(writer, self.generation, True)
            phase = "observer"
            with self.observer() as observer:
                if observer.query("SELECT phase FROM schema_installation WHERE singleton=1") != [b"activated"]:
                    raise SqlFixtureError("observer", "blocked")
        except Exception:
            raise SqlFixtureError(phase, "blocked" if phase == "preflight" else "unknown",
                                  self._uncertain) from None

    @property
    def inventory(self):
        names = {"database": self.database, "observer": self.observer_user}
        resources = tuple((kind, names[kind], "owned" if kind in self._owned else "unknown")
                          for kind in dict.fromkeys([*self._owned, *self._uncertain]))
        clients = tuple(("client", str(session.client.pid), "unknown") for session in self._sessions
                        if getattr(session, "client", None) is not None)
        return resources + clients

    def retry_client_cleanup(self):
        """Retry only tracked child teardown once; never retry SQL deletion."""
        failed = False
        for session in tuple(self._sessions):
            try:
                session.close()
                self._sessions.remove(session)
            except BaseException:
                failed = True
        if failed:
            error = SqlFixtureError("cleanup", "unknown")
            error.inventory = self.inventory
            error.retry_client_cleanup = self.retry_client_cleanup
            raise error from None
        return self.inventory

    def _cleanup(self):
        self._active = False
        failed = False
        try:
            self.retry_client_cleanup()
        except BaseException:
            failed = True
        deadline = time.monotonic() + self.config.cleanup_timeout_seconds
        for kind in reversed(tuple(self._owned)):
            try:
                with self._connect(self.config.admin_user, None, deadline) as admin:
                    if kind == "observer":
                        admin.query(f"DROP USER '{self.observer_user}'@'localhost'")
                        rows = admin.query(f"SELECT 1 FROM mysql.user WHERE User=BINARY '{self.observer_user}' AND Host='localhost'")
                    else:
                        admin.query(f"DROP DATABASE `{self.database}`")
                        rows = admin.query(f"SELECT 1 FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=BINARY '{self.database}'")
                    if rows:
                        raise SqlFixtureError("cleanup", "unknown")
                self._owned.remove(kind)
            except BaseException:
                failed = True
        if failed:
            raise SqlFixtureError("cleanup", "unknown", (*self._uncertain, *self._owned)) from None


@contextmanager
def sql_fixture_run(config):
    """Create/migrate an owned database and close it, including on cancellation.

    Unknown CREATE outcomes are preserved for authorized reconciliation. The
    error inventory retains synthetic names and ownership state for local
    reconciliation. It contains no passwords or engine diagnostics.
    """
    _validate(config)
    run = SqlFixture(config)
    try:
        try:
            run._setup()
            yield run
        finally:
            run._cleanup()
    except BaseException as error:
        error.inventory = run.inventory
        error.retry_client_cleanup = run.retry_client_cleanup
        raise
