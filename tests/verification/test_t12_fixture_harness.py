import os
import signal
import socket
import subprocess
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.verification import t12_fixture_harness as harness
from scripts.verification.t12_fixture_harness import (
    FixtureClock,
    HarnessConfig,
    InvalidConfiguration,
    PrerequisiteUnavailable,
    fixture_run,
)


class FixtureHarnessTests(unittest.TestCase):
    def setUp(self):
        temporary_root = TemporaryDirectory()
        self.addCleanup(temporary_root.cleanup)
        self.root = Path(temporary_root.name)
        self.sentinel = self.root / "unrelated-sentinel"
        self.sentinel.write_bytes(b"unrelated")
        self.config = HarnessConfig(root=self.root, seed=42)

    def assert_sentinel_only(self):
        self.assertEqual(tuple(self.root.iterdir()), (self.sentinel,))
        self.assertEqual(self.sentinel.read_bytes(), b"unrelated")

    def test_valid_runs_have_repeatable_seed_data_and_independent_state(self):
        with fixture_run(self.config) as first, fixture_run(self.config) as second:
            self.assertNotEqual(first.namespace, second.namespace)
            self.assertTrue(first.namespace.is_dir())
            self.assertTrue(second.namespace.is_dir())
            self.assertEqual(first.fixture, second.fixture)
            self.assertEqual((first.fixture.version, first.fixture.seed), (1, 42))
            self.assertIsNot(first.identity, second.identity)
            first.clock.advance(1)
            self.assertNotEqual(first.clock.now(), second.clock.now())
        self.assert_sentinel_only()
        with fixture_run(replace(self.config, seed=43)) as third:
            self.assertNotEqual(first.fixture.boards, third.fixture.boards)
            self.assertNotEqual(first.fixture.actors, third.fixture.actors)
        self.assert_sentinel_only()

    def test_fixture_clock_controls_expiry_and_rejects_invalid_moves(self):
        clock = FixtureClock()
        self.assertEqual(clock.now(), datetime(2026, 1, 1, tzinfo=timezone.utc))
        expiry = datetime(2026, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
        clock.advance(1)
        self.assertLess(clock.now(), expiry)
        clock.advance(1)
        self.assertEqual(clock.now(), expiry)
        for invalid in (-1, True, 1.25, 86_401):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "^seconds$"):
                clock.advance(invalid)
            self.assertEqual(clock.now(), expiry)
        clock.advance(1)
        self.assertGreater(clock.now(), expiry)

    def test_fixture_preserves_scoped_collisions_and_distinct_observer(self):
        with patch.object(socket, "socket", side_effect=AssertionError("socket")) as connect:
            with fixture_run(self.config) as run:
                primary, secondary, foreign = run.fixture.boards
                self.assertEqual(primary.guild_id, secondary.guild_id)
                self.assertNotEqual(primary.guild_id, foreign.guild_id)
                for field in ("board_id", "asset_id", "receipt_id", "lineage_id"):
                    self.assertEqual(getattr(primary, field), getattr(foreign, field))
                    self.assertNotEqual(getattr(primary, field), getattr(secondary, field))
                viewer, moderator, revoked, control = run.fixture.actors
                self.assertEqual(
                    tuple(actor.fixture_role for actor in run.fixture.actors),
                    ("viewer", "moderator", "revoked", "foreign-control"),
                )
                self.assertEqual(moderator.user_id, control.user_id)
                self.assertNotEqual(moderator.guild_id, control.guild_id)
                observer = run.fixture.observer
                self.assertEqual(observer.guild_id, primary.guild_id)
                self.assertNotIn(observer.user_id, {actor.user_id for actor in run.fixture.actors})
                for actor in (viewer, moderator, revoked, control, observer):
                    self.assertEqual(run.identity.membership(actor.guild_id, actor.user_id), actor)
                self.assertIsNone(run.identity.membership(foreign.guild_id, viewer.user_id))
            connect.assert_not_called()
        self.assert_sentinel_only()

    def assert_preflight_rejected(self, config, error, diagnostic, expected_entries=None):
        module = "scripts.verification.t12_fixture_harness"
        with (
            patch.object(os, "mkdir", side_effect=AssertionError("namespace")) as create,
            patch.object(subprocess, "Popen", side_effect=AssertionError("worker")) as worker,
            patch(f"{module}.FakeDiscordIdentity", side_effect=AssertionError("identity")) as identity,
            patch.object(socket, "socket", side_effect=AssertionError("socket")) as connect,
        ):
            with self.assertRaisesRegex(error, f"^{diagnostic}$"):
                with fixture_run(config):
                    self.fail("rejected preflight entered the run")
            create.assert_not_called()
            worker.assert_not_called()
            identity.assert_not_called()
            connect.assert_not_called()
        self.assertEqual(set(self.root.iterdir()), expected_entries or {self.sentinel})
        self.assertEqual(self.sentinel.read_bytes(), b"unrelated")

    def test_invalid_preflight_fails_before_resource_setup(self):
        symlink = self.root / "unrelated-alias"
        symlink.symlink_to(self.root, target_is_directory=True)
        public = self.root / "unrelated-public"
        public.mkdir()
        public.chmod(0o755)
        for root in (symlink, public):
            self.assert_preflight_rejected(
                replace(self.config, root=root), InvalidConfiguration, "root",
                expected_entries={self.sentinel, symlink, public},
            )
        self.assertTrue(symlink.is_symlink())
        self.assertTrue(public.is_dir())
        symlink.unlink()
        public.rmdir()
        for field, value in (
            ("target", "invalid-input"),
            ("seed", True),
            ("seed", -1),
            ("cleanup_timeout_seconds", 0),
            ("cleanup_timeout_seconds", 11),
            ("cleanup_timeout_seconds", float("inf")),
            ("root", Path(".")),
            ("root", self.root / "missing"),
            ("root", self.sentinel),
        ):
            with self.subTest(field=field, value=value):
                self.assert_preflight_rejected(
                    replace(self.config, **{field: value}), InvalidConfiguration, field
                )

    def test_integration_preflight_fails_before_resource_setup(self):
        self.assert_preflight_rejected(
            replace(self.config, target="integration"),
            PrerequisiteUnavailable,
            "sql_engine,migrations,api,policy,storage,bot",
        )

    def test_namespace_open_failure_rolls_back_creation(self):
        open_directory = os.open
        failure = OSError("namespace open failed")

        def fail_namespace_open(path, flags, *, dir_fd=None):
            if dir_fd is not None:
                self.assertTrue((self.root / path).is_dir())
                raise failure
            return open_directory(path, flags)

        with patch.object(os, "open", side_effect=fail_namespace_open):
            with self.assertRaises(OSError) as raised, fixture_run(self.config):
                self.fail("failed acquisition entered the run")
        self.assertIs(raised.exception, failure)
        self.assert_sentinel_only()

    def test_namespace_open_failure_preserves_untracked_contents(self):
        open_directory = os.open

        def fail_namespace_open(path, flags, *, dir_fd=None):
            if dir_fd is not None:
                (self.root / path / "untracked").write_bytes(b"untracked")
                raise OSError("namespace open failed")
            return open_directory(path, flags)

        with patch.object(os, "open", side_effect=fail_namespace_open):
            with (
                self.assertRaisesRegex(
                    RuntimeError, "^could not roll back fixture namespace acquisition$"
                ),
                fixture_run(self.config),
            ):
                self.fail("failed acquisition entered the run")
        namespaces = set(self.root.iterdir()) - {self.sentinel}
        self.assertEqual(len(namespaces), 1)
        namespace = namespaces.pop()
        self.assertEqual((namespace / "untracked").read_bytes(), b"untracked")
        self.assertEqual(self.sentinel.read_bytes(), b"unrelated")

    @unittest.skipUnless(os.name == "posix", "requires waitpid on an owned POSIX child")
    def test_interruption_reaps_only_owned_worker_and_preserves_sentinel(self):
        # The separately owned process uses its stdin as a lifetime handle.
        with subprocess.Popen(
            [sys.executable, "-I", "-S", "-c", "import sys; sys.stdin.buffer.read()"],
            stdin=subprocess.PIPE,
            env={},
        ) as unrelated:
            try:
                with self.assertRaises(KeyboardInterrupt), fixture_run(self.config) as run:
                    pid = run.start_worker()
                    self.assertNotEqual(pid, unrelated.pid)
                    self.assertEqual(os.waitpid(pid, os.WNOHANG), (0, 0))
                    self.assertTrue(run.namespace.is_dir())
                    with self.assertRaisesRegex(RuntimeError, "^worker$"):
                        run.start_worker()
                    signal.raise_signal(signal.SIGINT)
                with self.assertRaises(ChildProcessError):
                    os.waitpid(pid, os.WNOHANG)
                self.assertIsNone(unrelated.poll())
                self.assert_sentinel_only()
                with self.assertRaisesRegex(RuntimeError, "^worker$"):
                    run.start_worker()
            finally:
                unrelated.stdin.close()
                unrelated.wait(timeout=5)

    def test_root_replacement_keeps_allocation_worker_and_cleanup_in_pinned_root(self):
        fixture_root = self.root / "fixture-root"
        original_root = self.root / "original-root"
        fixture_root.mkdir(mode=0o700)
        config = replace(self.config, root=fixture_root)
        make_fixture = harness._make_fixture

        def replace_root(seed):
            fixture_root.rename(original_root)
            fixture_root.mkdir(mode=0o700)
            return make_fixture(seed)

        with patch.object(harness, "_make_fixture", side_effect=replace_root):
            with fixture_run(config) as run:
                original_namespace = original_root / run.namespace.name
                self.assertTrue(original_namespace.is_dir())
                run.namespace.mkdir(mode=0o700)
                replacement_sentinel = fixture_root / "replacement-sentinel"
                replacement_sentinel.write_bytes(b"replacement")
                pid = run.start_worker()
                self.assertTrue(Path(f"/proc/{pid}/cwd").samefile(original_namespace))
        self.assertFalse(original_namespace.exists())
        self.assertTrue(run.namespace.is_dir())
        self.assertEqual(replacement_sentinel.read_bytes(), b"replacement")
        self.assertEqual(self.sentinel.read_bytes(), b"unrelated")

    def test_namespace_replacement_preserves_both_directories_and_reaps_worker(self):
        original_namespace = self.root / "original-namespace"
        with (
            self.assertRaisesRegex(RuntimeError, "^fixture namespace identity changed$"),
            fixture_run(self.config) as run,
        ):
            run.namespace.rename(original_namespace)
            run.namespace.mkdir(mode=0o700)
            pid = run.start_worker()
            self.assertTrue(Path(f"/proc/{pid}/cwd").samefile(original_namespace))
        with self.assertRaises(ChildProcessError):
            os.waitpid(pid, os.WNOHANG)
        self.assertEqual(tuple(original_namespace.iterdir()), ())
        self.assertEqual(tuple(run.namespace.iterdir()), ())
        self.assertEqual(self.sentinel.read_bytes(), b"unrelated")

    def test_untracked_contents_surface_cleanup_failure_and_are_preserved(self):
        with self.assertRaises(OSError), fixture_run(self.config) as run:
            unexpected = run.namespace / "untracked"
            unexpected.write_bytes(b"untracked")
        self.assertEqual(unexpected.read_bytes(), b"untracked")
        self.assertEqual(self.sentinel.read_bytes(), b"unrelated")


if __name__ == "__main__":
    unittest.main()
