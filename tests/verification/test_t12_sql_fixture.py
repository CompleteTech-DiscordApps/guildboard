"""Synthetic SQL ports only: no daemon/client is present or contacted."""
from contextlib import ExitStack
from dataclasses import replace
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from scripts.verification import t12_sql_fixture as fixture


class SyntheticEngine:
    def __init__(self):
        self.databases = {"unrelated_sentinel": b"sentinel"}
        self.users = {"unrelated_observer": "unrelated_sentinel"}
        self.sessions, self.commands = [], []
        self.version = next(iter(fixture.schema.CATALOG))
        self.networking, self.failure = "1", None

    def session(self, config, user, database, deadline):
        engine = self

        class Port:
            closed = False

            def __init__(self):
                self.database, self.user, self.deadline = database, user, deadline
                engine.sessions.append(self)

            def close(self):
                self.closed = True

            def query(self, sql):
                if self.closed or time.monotonic() >= deadline:
                    raise fixture.SqlFixtureError("query", "unknown")
                engine.commands.append((user, database, sql))
                failure = engine.failure
                if failure and failure[0] in sql and not failure[1]:
                    raise failure[2]
                if sql.startswith("SELECT VERSION()"):
                    result = [f"{engine.version}\t{engine.networking}\t1".encode()]
                elif sql.startswith("CREATE DATABASE"):
                    name = sql.split("`")[1]
                    if name in engine.databases:
                        raise fixture.SqlFixtureError("query", "unknown")
                    engine.databases[name] = None
                    result = []
                elif sql.startswith("CREATE USER"):
                    name = sql.split("'")[1]
                    if name in engine.users:
                        raise fixture.SqlFixtureError("query", "unknown")
                    engine.users[name] = None
                    result = []
                elif sql.startswith("GRANT SELECT"):
                    engine.users[sql.split("'")[1]] = sql.split("`")[1]
                    result = []
                elif sql.startswith("DROP DATABASE"):
                    del engine.databases[sql.split("`")[1]]
                    result = []
                elif sql.startswith("DROP USER"):
                    del engine.users[sql.split("'")[1]]
                    result = []
                elif "FROM mysql.user" in sql:
                    result = [b"1"] if sql.split("'")[1] in engine.users else []
                elif "FROM information_schema.SCHEMATA" in sql:
                    result = [b"1"] if sql.split("'")[1] in engine.databases else []
                elif sql == "SELECT phase FROM schema_installation WHERE singleton=1":
                    result = [engine.databases[database]]
                elif sql == "SELECT synthetic_value":
                    result = [engine.databases[database]]
                elif sql == "UPDATE synthetic_value":
                    if user in engine.users:
                        raise fixture.SqlFixtureError("query", "unknown")
                    engine.databases[database] = b"changed"
                    result = []
                else:
                    raise AssertionError("unexpected synthetic SQL")
                if failure and failure[0] in sql and failure[1]:
                    raise failure[2]
                return result

        return Port()

    def migrate(self, session, generation, apply):
        if not re.fullmatch("[0-9A-F]{32}", generation) or apply is not True:
            raise AssertionError("migration arguments")
        self.databases[session.database] = b"activated"


class SqlFixtureTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.client = self.root / "mysql"
        self.client.write_text("synthetic port; never executable in tests\n")
        self.client.chmod(0o700)
        self.socket = self.root / "synthetic.sock"
        self.socket.touch()
        original_stat = Path.stat

        def metadata(path, *args, **kwargs):
            info = original_stat(path, *args, **kwargs)
            if path == self.socket:
                fields = list(info)
                fields[0] = stat.S_IFSOCK | 0o600
                return os.stat_result(fields)
            return info

        patch.object(Path, "stat", new=metadata).start()
        self.sentinel = self.root / "unrelated-sentinel"
        self.sentinel.write_bytes(b"unchanged")
        self.config = fixture.SqlFixtureConfig(self.client, self.socket, "fixture_admin", True)
        self.engine = SyntheticEngine()
        self.addCleanup(patch.stopall)
        patch.object(fixture, "_Session", side_effect=lambda *args: self.engine.session(*args)).start()
        self.migration = patch.object(fixture.schema, "migration", side_effect=lambda *args: self.engine.migrate(*args)).start()

    def assert_clean(self):
        self.assertEqual(self.engine.databases, {"unrelated_sentinel": b"sentinel"})
        self.assertEqual(self.engine.users, {"unrelated_observer": "unrelated_sentinel"})
        self.assertTrue(all(session.closed for session in self.engine.sessions))
        self.assertEqual(self.sentinel.read_bytes(), b"unchanged")

    def test_invalid_configuration_has_zero_process_or_sql_effects(self):
        for field, value in (("disposable", False), ("admin_user", "root;secret"),
                             ("client", Path("mysql")), ("client", self.socket),
                             ("socket", self.client), ("timeout_seconds", True),
                             ("timeout_seconds", float("nan")), ("operation_timeout_seconds", 0),
                             ("cleanup_timeout_seconds", 11)):
            with self.subTest(field=field), patch.object(subprocess, "Popen") as spawn:
                with self.assertRaisesRegex(ValueError, f"^{field}$"):
                    with fixture.sql_fixture_run(replace(self.config, **{field: value})):
                        self.fail("invalid setup entered")
                spawn.assert_not_called()
        alias = self.root / "alias"
        alias.symlink_to(self.client)
        with self.assertRaisesRegex(ValueError, "^client$"):
            with fixture.sql_fixture_run(replace(self.config, client=alias)):
                self.fail("symlink entered")
        for path, mode, field in ((self.root, 0o755, "socket"), (self.client, 0o777, "client")):
            original = path.stat().st_mode & 0o777
            path.chmod(mode)
            try:
                with self.assertRaisesRegex(ValueError, f"^{field}$"):
                    with fixture.sql_fixture_run(self.config):
                        self.fail("unsafe path entered")
            finally:
                path.chmod(original)
        self.assertEqual(self.engine.commands, [])
        self.assert_clean()

    def test_engine_and_networking_preflight_have_zero_creates(self):
        supported = self.engine.version
        for version, networking in (("unknown", "1"), (supported, "0")):
            self.engine.version, self.engine.networking = version, networking
            with self.assertRaisesRegex(fixture.SqlFixtureError, "^preflight:blocked$"):
                with fixture.sql_fixture_run(self.config):
                    self.fail("unsupported engine entered")
        self.assertTrue(all(sql.startswith("SELECT VERSION()") for _, _, sql in self.engine.commands))
        self.assert_clean()

    def test_isolation_migration_and_separate_select_only_observer(self):
        with fixture.sql_fixture_run(self.config) as first, fixture.sql_fixture_run(self.config) as second:
            self.assertNotEqual(first.database, second.database)
            self.assertNotEqual(first.observer_user, second.observer_user)
            with first.writer() as writer, first.observer() as observer, second.observer() as other:
                self.assertIsNot(writer, observer)
                self.assertNotEqual(writer.user, observer.user)
                writer.query("UPDATE synthetic_value")
                self.assertEqual(observer.query("SELECT synthetic_value"), [b"changed"])
                self.assertEqual(other.query("SELECT synthetic_value"), [b"activated"])
                with self.assertRaises(fixture.SqlFixtureError):
                    observer.query("UPDATE synthetic_value")
            self.assertEqual(len(first.inventory), 2)
        self.assertEqual(self.migration.call_count, 2)
        for call in self.migration.call_args_list:
            self.assertEqual(call.args[2], True)
            self.assertRegex(call.args[1], "^[0-9A-F]{32}$")
        with self.assertRaisesRegex(fixture.SqlFixtureError, "^fixture:closed$"):
            with first.observer():
                self.fail("closed fixture entered")
        self.assert_clean()

    def test_migration_failure_cleans_owned_resources_and_redacts_diagnostics(self):
        self.migration.side_effect = fixture.schema.Fenced("raw secret diagnostic")
        with self.assertRaisesRegex(fixture.SqlFixtureError, "^migration:unknown$") as result:
            with fixture.sql_fixture_run(self.config):
                self.fail("failed migration entered")
        self.assertEqual(result.exception.inventory, ())
        self.assert_clean()

    def test_grant_or_observer_failure_never_enters_fixture(self):
        for command in ("GRANT SELECT", "SELECT phase"):
            self.engine.failure = command, False, fixture.SqlFixtureError("query", "unknown")
            with self.subTest(command=command), self.assertRaises(fixture.SqlFixtureError):
                with fixture.sql_fixture_run(self.config):
                    self.fail("incomplete observer entered")
            self.assert_clean()

    def test_unknown_create_is_preserved_and_inventory_retains_names(self):
        for command, kind in (("CREATE DATABASE", "database"), ("CREATE USER", "observer")):
            with self.subTest(command=command):
                self.engine.failure = command, True, fixture.SqlFixtureError("query", "unknown")
                with self.assertRaisesRegex(fixture.SqlFixtureError, "^create:unknown$") as result:
                    with fixture.sql_fixture_run(self.config):
                        self.fail("uncertain create entered")
                inventory = result.exception.inventory
                self.assertEqual(len(inventory), 1)
                self.assertEqual((inventory[0][0], inventory[0][2]), (kind, "unknown"))
                self.assertFalse(any(sql.startswith("DROP") and inventory[0][1] in sql
                                     for _, _, sql in self.engine.commands))
                self.assertEqual(self.sentinel.read_bytes(), b"unchanged")
                self.engine = SyntheticEngine()

    def test_colliding_existing_database_is_never_dropped(self):
        name = "gb12_" + "a" * 32
        self.engine.databases[name] = b"existing sentinel"
        with patch.object(fixture.secrets, "token_hex", return_value="a" * 32):
            with self.assertRaisesRegex(fixture.SqlFixtureError, "^create:unknown$"):
                with fixture.sql_fixture_run(self.config):
                    self.fail("collision entered")
        self.assertEqual(self.engine.databases[name], b"existing sentinel")
        self.assertFalse(any(sql.startswith("DROP") for _, _, sql in self.engine.commands))

    def test_cancellation_after_registration_cleans_and_preserves_sentinel(self):
        with self.assertRaises(KeyboardInterrupt):
            with fixture.sql_fixture_run(self.config):
                raise KeyboardInterrupt
        self.assert_clean()

    def test_cancellation_during_create_preserves_unknown_resource(self):
        self.engine.failure = "CREATE USER", True, KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt) as result:
            with fixture.sql_fixture_run(self.config):
                self.fail("cancelled acquisition entered")
        self.assertEqual(len(result.exception.inventory), 1)
        kind, name, state = result.exception.inventory[0]
        self.assertEqual((kind, state), ("observer", "unknown"))
        self.assertIn(name, self.engine.users)
        self.assertEqual(self.engine.databases, {"unrelated_sentinel": b"sentinel"})

    def test_sigint_during_client_acquisition_is_deferred_until_registered(self):
        original = self.engine.session

        def interrupted(*args):
            session = original(*args)
            signal.raise_signal(signal.SIGINT)
            return session

        with patch.object(fixture, "_Session", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                with fixture.sql_fixture_run(self.config):
                    self.fail("interrupted setup entered")
        self.assert_clean()

    def test_connection_and_shared_cleanup_deadlines_are_finite(self):
        with fixture.sql_fixture_run(self.config) as run:
            with ExitStack() as stack:
                for _ in range(4):
                    stack.enter_context(run.writer())
                with self.assertRaisesRegex(fixture.SqlFixtureError, "^connections:unavailable$"):
                    stack.enter_context(run.writer())
            for _ in range(25):
                with run.writer():
                    pass
            with self.assertRaisesRegex(fixture.SqlFixtureError, "^connections:unavailable$"):
                with run.writer():
                    self.fail("connection count exhausted")
        self.assert_clean()
        deadlines = []

        def unavailable(*args):
            deadlines.append(args[-1])
            raise fixture.SqlFixtureError("session", "unavailable")

        with self.assertRaisesRegex(fixture.SqlFixtureError, "^cleanup:unknown$"):
            with fixture.sql_fixture_run(self.config):
                fixture._Session.side_effect = unavailable
        self.assertEqual(len(deadlines), 2)
        self.assertEqual(deadlines[0], deadlines[1])

    def test_cleanup_failure_is_unknown_and_other_resource_is_still_cleaned(self):
        self.engine.failure = "DROP USER", True, fixture.SqlFixtureError("query", "unknown")
        with self.assertRaisesRegex(fixture.SqlFixtureError, "^cleanup:unknown$") as result:
            with fixture.sql_fixture_run(self.config):
                pass
        self.assertEqual(len(result.exception.inventory), 1)
        self.assertEqual(result.exception.inventory[0][0], "observer")
        self.assertEqual(self.engine.databases, {"unrelated_sentinel": b"sentinel"})
        self.assertEqual(self.sentinel.read_bytes(), b"unchanged")

    def test_cleanup_verifies_absence_and_does_not_retry_drops(self):
        original = self.engine.session

        def port(*args):
            session = original(*args)
            query = session.query

            def retained(sql):
                return [b"1"] if "FROM mysql.user" in sql else query(sql)
            session.query = retained
            return session

        with patch.object(fixture, "_Session", side_effect=port):
            with self.assertRaisesRegex(fixture.SqlFixtureError, "^cleanup:unknown$"):
                with fixture.sql_fixture_run(self.config):
                    pass
        self.engine.failure = "DROP", False, fixture.SqlFixtureError("query", "unknown")
        with self.assertRaisesRegex(fixture.SqlFixtureError, "^cleanup:unknown$"):
            with fixture.sql_fixture_run(self.config):
                pass
        drops = [sql for _, _, sql in self.engine.commands if sql.startswith("DROP")]
        self.assertEqual(len(drops), 4)


class BoundedClientTests(unittest.TestCase):
    def session(self, program, timeout=0.15):
        original = subprocess.Popen
        config = fixture.SqlFixtureConfig(Path("/synthetic/mysql"), Path("/synthetic/socket"),
                                          "fixture_admin", True, operation_timeout_seconds=timeout)
        captured = []

        def spawn(argv, **kwargs):
            captured.append((argv, kwargs))
            return original([sys.executable, "-I", "-S", "-c", program], **kwargs)

        with patch.object(subprocess, "Popen", side_effect=spawn):
            session = fixture._Session(config, config.admin_user, None, time.monotonic() + 2)
        self.addCleanup(session.close)
        return session, captured[0]

    def test_synthetic_child_receives_no_ambient_config_and_is_reaped(self):
        program = "import sys\nfor line in sys.stdin:\n if line.startswith(\"SELECT 'gb_end_\"):\n  print(line.split(\"'\")[1], flush=True)"
        with patch.dict(os.environ, {"MYSQL_PWD": "must not reach child", "HOME": "/private"}):
            session, (argv, kwargs) = self.session(program)
        self.assertEqual(session.query("SELECT 1"), [])
        self.assertEqual(kwargs["env"], {})
        self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
        self.assertEqual(argv[1:3], ["--no-defaults", "--no-login-paths"])
        for flag in ("--protocol=socket", "--skip-reconnect", "--connect-timeout=1"):
            self.assertIn(flag, argv)
        session.close()
        self.assertIsNotNone(session.client.returncode)

    def test_timeout_output_bound_and_cancel_taint_connection(self):
        programs = ("import sys; sys.stdin.buffer.read()",
                    "import sys; sys.stdin.readline(); sys.stdout.write('x'*70000); sys.stdout.flush()")
        for program in programs:
            with self.subTest(program=program):
                session, _ = self.session(program)
                started = time.monotonic()
                with self.assertRaisesRegex(fixture.SqlFixtureError, "^query:unknown$"):
                    session.query("SELECT 1")
                self.assertLess(time.monotonic() - started, 1)
                with self.assertRaisesRegex(fixture.SqlFixtureError, "^query:unavailable$"):
                    session.query("DROP DATABASE anything")
                session.close()
                self.assertIsNotNone(session.client.returncode)
        session, _ = self.session(programs[0])
        with patch.object(fixture.select, "select", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                session.query("SELECT 1")
        self.assertTrue(session.tainted)

    def test_reap_timeout_is_classified_and_can_be_retried(self):
        session, _ = self.session("import sys; sys.stdin.buffer.read()")
        with patch.object(session.client, "wait", side_effect=subprocess.TimeoutExpired("synthetic", 0.5)) as wait:
            with self.assertRaisesRegex(fixture.SqlFixtureError, "^client_cleanup:unknown$"):
                session.close()
            wait.assert_called_once_with(timeout=0.5)
        session.close()
        self.assertIsNotNone(session.client.returncode)

    def test_query_size_count_and_expired_session_are_bounded(self):
        session, _ = self.session("import sys; sys.stdin.buffer.read()")
        with self.assertRaisesRegex(ValueError, "^sql$"):
            session.query("x" * 65537)
        session.queries = 1024
        with self.assertRaisesRegex(fixture.SqlFixtureError, "^query:unavailable$"):
            session.query("SELECT 1")
        with patch.object(subprocess, "Popen") as spawn:
            with self.assertRaisesRegex(fixture.SqlFixtureError, "^session:unavailable$"):
                fixture._Session(fixture.SqlFixtureConfig(Path("/synthetic/mysql"), Path("/synthetic/socket"),
                                                         "fixture_admin", True), "fixture_admin", None, 0)
            spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
