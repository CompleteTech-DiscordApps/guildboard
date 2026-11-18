import errno
import os
import signal
import socket
import subprocess
import sys
import unittest
from contextlib import ExitStack
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

    def reap_owned_child(self, child):
        """Bound test fallback cleanup even if an assertion or injected fault fails."""
        try:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
        finally:
            child.stdin.close()

    def capture_children(self, children, after_spawn=lambda child: None):
        popen = subprocess.Popen

        def start(*args, **kwargs):
            child = popen(*args, **kwargs)
            children.append(child)
            self.addCleanup(self.reap_owned_child, child)
            after_spawn(child)
            return child

        return patch.object(subprocess, "Popen", side_effect=start)

    def assert_reaped(self, child):
        self.assertIsNotNone(child.returncode)
        with self.assertRaises(ChildProcessError):
            os.waitpid(child.pid, os.WNOHANG)

    def interrupt_next_mask_read(self, after_read, interruptions):
        sigmask = signal.pthread_sigmask
        armed = True

        def read(how, mask):
            nonlocal armed
            if armed and how == signal.SIG_BLOCK and not mask:
                armed = False
                if after_read:
                    sigmask(how, mask)
                try:
                    signal.raise_signal(signal.SIGINT)
                except KeyboardInterrupt as error:
                    interruptions.append(error)
                    raise
                self.fail("SIGINT did not interrupt the unmasked cleanup entry")
            return sigmask(how, mask)

        return patch.object(signal, "pthread_sigmask", side_effect=read)

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

    def test_successful_worker_is_reaped_before_namespace_removal(self):
        children = []
        with self.capture_children(children), fixture_run(self.config) as run:
            pid = run.start_worker()
            self.assertEqual(os.waitpid(pid, os.WNOHANG), (0, 0))
            remove = run._remove_namespace

            def observe_remove(expected):
                self.assert_reaped(children[0])
                self.assertTrue(children[0].stdin.closed)
                remove(expected)

            run._remove_namespace = observe_remove
        self.assert_sentinel_only()

    def test_sigint_after_spawn_before_registration_reaps_only_owned_child(self):
        children = []
        unrelated = subprocess.Popen(
            [sys.executable, "-I", "-S", "-c", "import sys; sys.stdin.buffer.read()"],
            stdin=subprocess.PIPE, env={},
        )
        self.addCleanup(self.reap_owned_child, unrelated)
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, set())
        handler = signal.getsignal(signal.SIGINT)

        def interrupt(child):
            self.assertIsNone(run._worker)
            self.assertEqual(os.waitpid(child.pid, os.WNOHANG), (0, 0))
            signal.raise_signal(signal.SIGINT)
            self.assertIn(signal.SIGINT, signal.sigpending())

        with self.capture_children(children, interrupt):
            with self.assertRaises(KeyboardInterrupt), fixture_run(self.config) as run:
                remove = run._remove_namespace

                def observe_remove(expected):
                    self.assert_reaped(children[0])
                    remove(expected)

                run._remove_namespace = observe_remove
                run.start_worker()
                self.fail("pending SIGINT was lost")
        self.assert_reaped(children[0])
        self.assertIsNone(unrelated.poll())
        self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK, set()), previous)
        self.assertIs(signal.getsignal(signal.SIGINT), handler)
        self.assert_sentinel_only()

    def test_caller_handler_and_preexisting_signal_mask_are_preserved(self):
        children, handled = [], []
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
        handler = signal.getsignal(signal.SIGINT)

        def observe_interrupt(signum, frame):
            handled.append(signum)
            self.assertIs(run._worker, children[-1])
            self.assertFalse(run._worker_acquisition_pending)

        try:
            signal.signal(signal.SIGINT, observe_interrupt)
            with self.capture_children(children, lambda child: signal.raise_signal(signal.SIGINT)):
                with fixture_run(self.config) as run:
                    run.start_worker()
                    self.assertEqual(handled, [signal.SIGINT])
                    self.assertEqual(
                        signal.pthread_sigmask(signal.SIG_BLOCK, set()),
                        previous | {signal.SIGUSR1},
                    )
            self.assertIs(signal.getsignal(signal.SIGINT), observe_interrupt)
            self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK, set()), previous | {signal.SIGUSR1})
            self.assert_reaped(children[0])
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
            signal.signal(signal.SIGINT, handler)
        self.assert_sentinel_only()

    def test_preblocked_sigint_stays_pending_until_caller_unblocks(self):
        children, handled = [], []
        handler = signal.getsignal(signal.SIGINT)
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
        try:
            signal.signal(signal.SIGINT, lambda signum, frame: handled.append(signum))
            with self.capture_children(children, lambda child: signal.raise_signal(signal.SIGINT)):
                with fixture_run(self.config) as run:
                    run.start_worker()
            self.assertEqual(handled, [])
            self.assertIn(signal.SIGINT, signal.sigpending())
            self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK, set()), previous | {signal.SIGINT})
            self.assert_reaped(children[0])
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
            self.assertEqual(handled, [signal.SIGINT])
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
            signal.signal(signal.SIGINT, handler)
        self.assert_sentinel_only()

    def test_startup_failure_retains_namespace_and_restores_mask(self):
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, set())
        with self.assertRaisesRegex(RuntimeError, "^fixture worker acquisition outcome unknown$") as raised:
            with fixture_run(self.config) as run:
                with patch.object(harness.sys, "executable", str(self.root / "missing-executable")):
                    run.start_worker()
        self.assertIsInstance(raised.exception.__context__, FileNotFoundError)
        self.assertTrue(run.namespace.is_dir())
        self.assertEqual(tuple(run.namespace.iterdir()), ())
        self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK, set()), previous)
        self.assertEqual(self.sentinel.read_bytes(), b"unrelated")

    def test_unexpected_acquisition_exception_quarantines_unknown_child(self):
        children = []
        failure = RuntimeError("injected acquisition failure")

        def fail_after_spawn(child):
            raise failure

        with self.capture_children(children, fail_after_spawn):
            with self.assertRaisesRegex(RuntimeError, "^fixture worker acquisition outcome unknown$") as raised:
                with fixture_run(self.config) as run:
                    with self.assertRaises(RuntimeError) as startup:
                        run.start_worker()
                    self.assertIs(startup.exception, failure)
                    with self.assertRaisesRegex(RuntimeError, "^worker$"):
                        run.start_worker()
        self.assertIsNone(raised.exception.__context__)
        self.assertTrue(run.namespace.is_dir())
        self.assertIsNone(children[0].poll())
        self.assertEqual(self.sentinel.read_bytes(), b"unrelated")
        self.reap_owned_child(children[0])

    def test_unknown_reap_preserves_namespace_and_original_interrupt(self):
        children = []
        interruption = KeyboardInterrupt("caller interruption")
        with self.capture_children(children), ExitStack() as stack:
            with self.assertRaises(KeyboardInterrupt) as raised:
                with fixture_run(self.config) as run:
                    run.start_worker()
                    stack.enter_context(patch.object(
                        children[0], "wait",
                        side_effect=subprocess.TimeoutExpired("owned-worker", 1),
                    ))
                    raise interruption
        self.assertIs(raised.exception, interruption)
        self.assertRegex(str(raised.exception.__cause__), "^fixture worker cleanup outcome unknown$")
        self.assertIn("fixture cleanup failed; resources may remain", raised.exception.__notes__)
        self.assertTrue(run.namespace.is_dir())
        self.assertTrue(children[0].stdin.closed)
        self.assertEqual(self.sentinel.read_bytes(), b"unrelated")
        self.reap_owned_child(children[0])

    def test_sigint_during_reap_is_delivered_after_cleanup(self):
        children = []
        with self.capture_children(children), ExitStack() as stack:
            with self.assertRaises(KeyboardInterrupt), fixture_run(self.config) as run:
                run.start_worker()
                wait = children[0].wait

                def interrupt_reap(*args, **kwargs):
                    signal.raise_signal(signal.SIGINT)
                    self.assertTrue(run.namespace.is_dir())
                    return wait(*args, **kwargs)

                stack.enter_context(patch.object(children[0], "wait", side_effect=interrupt_reap))
        self.assert_reaped(children[0])
        self.assert_sentinel_only()

    def cleanup_dispatch_boundaries(self):
        """Record Python line boundaries from normal dispatch to the first mask."""
        boundaries = []
        recording = True
        previous = sys.gettrace()

        def trace(frame, event, arg):
            nonlocal recording
            if event == "call" and frame.f_code is harness._defer_sigint.__wrapped__.__code__:
                recording = False
            if recording and event == "line" and frame.f_code.co_filename == harness.__file__:
                boundaries.append((frame.f_code, frame.f_lineno))
            return trace

        try:
            with fixture_run(self.config):
                sys.settrace(trace)
        finally:
            sys.settrace(previous)
        self.assertIn(harness._FixtureRun._close.__code__, {code for code, _ in boundaries})
        self.assertIn(harness.fixture_run.__wrapped__.__code__, {code for code, _ in boundaries})
        self.assert_sentinel_only()
        return boundaries

    def assert_cleanup_dispatch_interruptions(self, fail_reap):
        boundaries = self.cleanup_dispatch_boundaries()
        unrelated = subprocess.Popen(
            [sys.executable, "-I", "-S", "-c", "import sys; sys.stdin.buffer.read()"],
            stdin=subprocess.PIPE, env={},
        )
        self.addCleanup(self.reap_owned_child, unrelated)
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
        handler, previous_trace = signal.getsignal(signal.SIGINT), sys.gettrace()
        close = os.close
        try:
            for code, line in boundaries:
                with self.subTest(function=code.co_name, line=line, fail_reap=fail_reap):
                    children, interruptions, removals, closes = [], [], [], []
                    namespace_fd = None

                    def trace(frame, event, arg):
                        if (not interruptions and event == "line"
                                and frame.f_code is code and frame.f_lineno == line):
                            try:
                                signal.raise_signal(signal.SIGINT)
                            except KeyboardInterrupt as error:
                                interruptions.append(error)
                                raise
                            self.fail("SIGINT did not interrupt cleanup dispatch")
                        return trace

                    def observe_close(fd):
                        if fd == namespace_fd:
                            closes.append(fd)
                        return close(fd)

                    try:
                        with self.capture_children(children), ExitStack() as stack:
                            with self.assertRaises(KeyboardInterrupt) as raised:
                                with fixture_run(self.config) as run:
                                    run.start_worker()
                                    namespace_fd = run._namespace_fd
                                    namespace_identity = os.fstat(namespace_fd)
                                    remove = run._remove_namespace

                                    def observe_remove(expected):
                                        self.assert_reaped(children[0])
                                        self.assertTrue(children[0].stdin.closed)
                                        removals.append(run.namespace)
                                        remove(expected)

                                    run._remove_namespace = observe_remove
                                    stack.enter_context(patch.object(os, "close", side_effect=observe_close))
                                    if fail_reap:
                                        wait = stack.enter_context(patch.object(
                                            children[0], "wait",
                                            side_effect=subprocess.TimeoutExpired("owned-worker", 1),
                                        ))
                                    sys.settrace(trace)
                            sys.settrace(previous_trace)
                        self.assertEqual(len(interruptions), 1)
                        self.assertIs(raised.exception, interruptions[0])
                        self.assertEqual(closes, [namespace_fd])
                        with self.assertRaises(OSError):
                            os.fstat(namespace_fd)
                        if fail_reap:
                            self.assertEqual(str(raised.exception.__cause__), "fixture worker cleanup outcome unknown")
                            self.assertIsInstance(raised.exception.__cause__.__cause__, subprocess.TimeoutExpired)
                            self.assertIn("fixture cleanup failed; resources may remain", raised.exception.__notes__)
                            wait.assert_called_once_with(timeout=self.config.cleanup_timeout_seconds)
                            self.assertEqual(removals, [])
                            self.assertTrue(run.namespace.is_dir())
                            self.assertTrue(children[0].stdin.closed)
                        else:
                            self.assertIsNone(raised.exception.__cause__)
                            self.assertEqual(removals, [run.namespace])
                            self.assert_reaped(children[0])
                            self.assert_sentinel_only()
                        self.assertEqual(self.sentinel.read_bytes(), b"unrelated")
                        self.assertIsNone(unrelated.poll())
                        self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK, set()), previous_mask | {signal.SIGUSR1})
                        self.assertIs(signal.getsignal(signal.SIGINT), handler)
                    finally:
                        sys.settrace(previous_trace)
                        # The regression must safely fail on a leaking implementation.
                        for child in children:
                            self.reap_owned_child(child)
                        if namespace_fd is not None:
                            try:
                                opened = os.fstat(namespace_fd)
                            except OSError:
                                pass
                            else:
                                self.assertTrue(os.path.samestat(opened, namespace_identity))
                                close(namespace_fd)
                            if run.namespace.exists():
                                self.assertTrue(os.path.samestat(run.namespace.stat(), namespace_identity))
                                run.namespace.rmdir()
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)

    def test_sigint_at_cleanup_dispatch_and_preamble_recovers(self):
        self.assert_cleanup_dispatch_interruptions(fail_reap=False)

    def test_sigint_at_cleanup_dispatch_and_preamble_chains_failed_recovery(self):
        self.assert_cleanup_dispatch_interruptions(fail_reap=True)

    def test_sigint_at_cleanup_mask_read_recovers_before_propagating(self):
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
        handler = signal.getsignal(signal.SIGINT)
        try:
            for after_read in (False, True):
                with self.subTest(after_read=after_read):
                    children, interruptions = [], []
                    with self.capture_children(children), ExitStack() as stack:
                        with self.assertRaises(KeyboardInterrupt) as raised:
                            with fixture_run(self.config) as run:
                                run.start_worker()
                                remove = run._remove_namespace

                                def observe_remove(expected):
                                    self.assert_reaped(children[0])
                                    self.assertTrue(children[0].stdin.closed)
                                    remove(expected)

                                run._remove_namespace = observe_remove
                                stack.enter_context(self.interrupt_next_mask_read(
                                    after_read, interruptions,
                                ))
                    self.assertEqual(len(interruptions), 1)
                    self.assertIs(raised.exception, interruptions[0])
                    self.assertIsNone(raised.exception.__cause__)
                    self.assert_reaped(children[0])
                    self.assert_sentinel_only()
                    self.assertEqual(
                        signal.pthread_sigmask(signal.SIG_BLOCK, set()),
                        previous | {signal.SIGUSR1},
                    )
                    self.assertIs(signal.getsignal(signal.SIGINT), handler)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)

    def test_sigint_at_cleanup_mask_read_chains_failed_recovery(self):
        for after_read in (False, True):
            with self.subTest(after_read=after_read):
                children, interruptions = [], []
                previous = signal.pthread_sigmask(signal.SIG_BLOCK, set())
                handler = signal.getsignal(signal.SIGINT)
                with self.capture_children(children), ExitStack() as stack:
                    with self.assertRaises(KeyboardInterrupt) as raised:
                        with fixture_run(self.config) as run:
                            run.start_worker()
                            wait = stack.enter_context(patch.object(
                                children[0], "wait",
                                side_effect=subprocess.TimeoutExpired("owned-worker", 1),
                            ))
                            stack.enter_context(self.interrupt_next_mask_read(
                                after_read, interruptions,
                            ))
                self.assertEqual(len(interruptions), 1)
                self.assertIs(raised.exception, interruptions[0])
                self.assertEqual(
                    str(raised.exception.__cause__), "fixture worker cleanup outcome unknown",
                )
                self.assertIsInstance(raised.exception.__cause__.__cause__, subprocess.TimeoutExpired)
                self.assertIn("fixture cleanup failed; resources may remain", raised.exception.__notes__)
                wait.assert_called_once_with(timeout=self.config.cleanup_timeout_seconds)
                self.assertTrue(run.namespace.is_dir())
                self.assertTrue(children[0].stdin.closed)
                self.assertEqual(self.sentinel.read_bytes(), b"unrelated")
                self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK, set()), previous)
                self.assertIs(signal.getsignal(signal.SIGINT), handler)
                self.reap_owned_child(children[0])

    def test_pending_sigint_preserves_reap_failure_without_retry(self):
        children = []
        failure = subprocess.TimeoutExpired("owned-worker", 1)

        def fail_reap(*args, **kwargs):
            signal.raise_signal(signal.SIGINT)
            raise failure

        with self.capture_children(children), ExitStack() as stack:
            with self.assertRaises(KeyboardInterrupt) as raised:
                with fixture_run(self.config) as run:
                    run.start_worker()
                    wait = stack.enter_context(patch.object(children[0], "wait", side_effect=fail_reap))
        self.assertEqual(str(raised.exception.__cause__), "fixture worker cleanup outcome unknown")
        self.assertIs(raised.exception.__cause__.__cause__, failure)
        self.assertIn("fixture cleanup failed; resources may remain", raised.exception.__notes__)
        wait.assert_called_once_with(timeout=self.config.cleanup_timeout_seconds)
        self.assertTrue(run.namespace.is_dir())
        self.assertTrue(children[0].stdin.closed)
        self.assertEqual(self.sentinel.read_bytes(), b"unrelated")
        self.reap_owned_child(children[0])

    def test_direct_cancellation_during_acquisition_reports_unknown_outcome(self):
        for interruption in (KeyboardInterrupt(), SystemExit(7)):
            with self.subTest(interruption=type(interruption).__name__):
                children = []

                def cancel_after_spawn(child):
                    raise interruption

                with self.capture_children(children, cancel_after_spawn):
                    with self.assertRaises(type(interruption)) as raised:
                        with fixture_run(self.config) as run:
                            run.start_worker()
                self.assertIs(raised.exception, interruption)
                self.assertEqual(
                    str(raised.exception.__cause__), "fixture worker acquisition outcome unknown"
                )
                self.assertTrue(run.namespace.is_dir())
                self.assertIsNone(children[0].poll())
                self.assertEqual(self.sentinel.read_bytes(), b"unrelated")
                self.reap_owned_child(children[0])

    def test_failed_sigint_block_restores_mask_before_propagating(self):
        sigmask = signal.pthread_sigmask
        previous = sigmask(signal.SIG_BLOCK, set())
        failure = RuntimeError("injected block failure")
        calls = 0

        def fail_after_block(how, mask):
            nonlocal calls
            calls += 1
            result = sigmask(how, mask)
            if calls == 2:
                raise failure
            return result

        with patch.object(signal, "pthread_sigmask", side_effect=fail_after_block):
            with self.assertRaises(RuntimeError) as raised, fixture_run(self.config) as run:
                run.start_worker()
        self.assertIs(raised.exception, failure)
        self.assertIsNone(run._worker)
        self.assertEqual(sigmask(signal.SIG_BLOCK, set()), previous)
        self.assert_sentinel_only()

    def test_transient_mask_restore_failure_retries_without_losing_worker(self):
        children = []
        sigmask = signal.pthread_sigmask
        previous = sigmask(signal.SIG_BLOCK, set())
        failure = OSError("injected restore failure")
        failed = False

        def fail_first_restore(how, mask):
            nonlocal failed
            if how == signal.SIG_SETMASK and not failed:
                failed = True
                raise failure
            return sigmask(how, mask)

        with self.capture_children(children):
            with patch.object(signal, "pthread_sigmask", side_effect=fail_first_restore):
                with self.assertRaises(OSError) as raised, fixture_run(self.config) as run:
                    run.start_worker()
        self.assertIs(raised.exception, failure)
        self.assert_reaped(children[0])
        self.assertEqual(sigmask(signal.SIG_BLOCK, set()), previous)
        self.assert_sentinel_only()

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

    def close_retained_descriptor(self, fd, identity):
        """Fallback closes only the retained test-owned descriptor identity."""
        try:
            current = os.fstat(fd)
        except OSError as error:
            self.assertEqual(error.errno, errno.EBADF)
        else:
            self.assertTrue(os.path.samestat(current, identity), "descriptor identity changed")
            os.close(fd)

    def root_cleanup_boundaries(self):
        """Observe normal root cleanup through its first real close dispatch."""
        boundaries = []
        recording = False
        previous_trace, close = sys.gettrace(), os.close
        root_code = harness._private_root.__wrapped__.__code__
        root_fd = identity = None

        def trace(frame, event, arg):
            nonlocal recording
            if event == "call" and frame.f_code is root_code:
                recording = True
            if recording and event == "line" and frame.f_code.co_filename == harness.__file__:
                boundary = (frame.f_code, frame.f_lineno)
                if boundary not in boundaries:
                    boundaries.append(boundary)
            return trace

        def observe_close(fd):
            nonlocal recording
            if fd == root_fd:
                recording = False
            return close(fd)

        try:
            with ExitStack() as stack:
                with fixture_run(self.config) as run:
                    root_fd, identity = run._root_fd, os.fstat(run._root_fd)
                    stack.enter_context(patch.object(os, "close", side_effect=observe_close))
                    sys.settrace(trace)
        finally:
            sys.settrace(previous_trace)
            if root_fd is not None:
                self.close_retained_descriptor(root_fd, identity)
        self.assertTrue(boundaries)
        self.assert_sentinel_only()
        return boundaries

    def assert_root_sigint_cleanup(self, *, boundary=None, after_close=False, cancellation=None):
        children, attempted, fired, delivered = [], [], [], []
        root_fd = identity = None
        close, previous_trace = os.close, sys.gettrace()
        root_code = harness._private_root.__wrapped__.__code__
        root_cleanup = False
        interruption = KeyboardInterrupt("real SIGINT during root cleanup")
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
        previous_handler = signal.getsignal(signal.SIGINT)
        unrelated = subprocess.Popen(
            [sys.executable, "-I", "-S", "-c", "import sys; sys.stdin.buffer.read()"],
            stdin=subprocess.PIPE, env={},
        )
        self.addCleanup(self.reap_owned_child, unrelated)

        def handle_interrupt(signum, frame):
            delivered.append(signum)
            raise interruption

        def interrupt_once():
            self.assertEqual(fired, [])
            self.assert_reaped(children[0])
            self.assertTrue(children[0].stdin.closed)
            self.assert_sentinel_only()
            fired.append(signal.SIGINT)
            signal.raise_signal(signal.SIGINT)

        def trace(frame, event, arg):
            nonlocal root_cleanup
            if event == "call" and frame.f_code is root_code:
                root_cleanup = True
            if (root_cleanup and not fired and event == "line"
                    and (frame.f_code, frame.f_lineno) == boundary):
                interrupt_once()
            return trace

        def observe_close(fd):
            if fd != root_fd:
                return close(fd)
            attempted.append(fd)
            if boundary is None and not after_close:
                interrupt_once()
            result = close(fd)
            if boundary is None and after_close:
                interrupt_once()
            return result

        try:
            signal.signal(signal.SIGINT, handle_interrupt)
            expected = cancellation if cancellation is not None else interruption
            with self.capture_children(children), ExitStack() as stack:
                with self.assertRaises(BaseException) as raised:
                    with fixture_run(self.config) as run:
                        run.start_worker()
                        root_fd, identity = run._root_fd, os.fstat(run._root_fd)
                        stack.enter_context(patch.object(os, "close", side_effect=observe_close))
                        if boundary is not None:
                            sys.settrace(trace)
                        if cancellation is not None:
                            raise cancellation
                sys.settrace(previous_trace)
            self.assertIs(raised.exception, expected)
            self.assertEqual(fired, [signal.SIGINT])
            self.assertEqual(delivered, [signal.SIGINT])
            with self.assertRaises(OSError) as closed:
                os.fstat(root_fd)
            self.assertEqual(closed.exception.errno, errno.EBADF)
            self.assertEqual(attempted, [root_fd])
            self.assert_reaped(children[0])
            self.assertIsNone(unrelated.poll())
            self.assert_sentinel_only()
            self.assertEqual(
                signal.pthread_sigmask(signal.SIG_BLOCK, set()), previous_mask | {signal.SIGUSR1}
            )
            self.assertIs(signal.getsignal(signal.SIGINT), handle_interrupt)
        finally:
            sys.settrace(previous_trace)
            # Drain a test-generated pending signal safely if a regression failed
            # to restore the mask; an assertion above records that failure.
            signal.signal(signal.SIGINT, lambda signum, frame: None)
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
            signal.signal(signal.SIGINT, previous_handler)
            for child in children:
                self.reap_owned_child(child)
            self.reap_owned_child(unrelated)
            if root_fd is not None:
                self.close_retained_descriptor(root_fd, identity)

    def test_root_sigint_at_observed_cleanup_dispatch_boundaries(self):
        for code, line in self.root_cleanup_boundaries():
            with self.subTest(function=code.co_name, line=line):
                self.assert_root_sigint_cleanup(boundary=(code, line))

    def test_root_single_sigint_before_and_after_real_close(self):
        for after_close in (False, True):
            with self.subTest(after_close=after_close):
                self.assert_root_sigint_cleanup(after_close=after_close)

    def test_root_close_sigint_preserves_original_caller_cancellation(self):
        for after_close in (False, True):
            for cancellation in (KeyboardInterrupt("caller cancellation"), SystemExit(19)):
                with self.subTest(after_close=after_close, cancellation=type(cancellation).__name__):
                    self.assert_root_sigint_cleanup(after_close=after_close, cancellation=cancellation)

    def test_root_close_preserves_returning_handler_and_preblocked_sigint(self):
        for preblocked in (False, True):
            with self.subTest(preblocked=preblocked):
                delivered, attempted = [], []
                close = os.close
                previous_handler = signal.getsignal(signal.SIGINT)
                blocked = {signal.SIGUSR1} | ({signal.SIGINT} if preblocked else set())
                previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, blocked)
                root_fd = identity = None

                def handler(signum, frame):
                    delivered.append(signum)

                def observe_close(fd):
                    if fd == root_fd:
                        attempted.append(fd)
                        signal.raise_signal(signal.SIGINT)
                    return close(fd)

                try:
                    signal.signal(signal.SIGINT, handler)
                    with ExitStack() as stack:
                        with fixture_run(self.config) as run:
                            root_fd, identity = run._root_fd, os.fstat(run._root_fd)
                            stack.enter_context(patch.object(os, "close", side_effect=observe_close))
                    self.assertEqual(attempted, [root_fd])
                    with self.assertRaises(OSError) as closed:
                        os.fstat(root_fd)
                    self.assertEqual(closed.exception.errno, errno.EBADF)
                    self.assertEqual(delivered, [] if preblocked else [signal.SIGINT])
                    self.assertEqual(signal.SIGINT in signal.sigpending(), preblocked)
                    self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK, set()), previous_mask | blocked)
                    self.assertIs(signal.getsignal(signal.SIGINT), handler)
                    signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
                    self.assertEqual(delivered, [signal.SIGINT])
                    self.assert_sentinel_only()
                finally:
                    signal.signal(signal.SIGINT, lambda signum, frame: None)
                    signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
                    signal.signal(signal.SIGINT, previous_handler)
                    if root_fd is not None:
                        self.close_retained_descriptor(root_fd, identity)

    def assert_root_close_fault(self, *, reuse_descriptor, cancellation=None, pending_sigint=False):
        """Injected close failure: optionally close and reuse the owned FD first."""
        children, attempted, delivered = [], [], []
        close, open_descriptor = os.close, os.open
        root_fd = root_identity = replacement_fd = replacement_identity = None
        failure = OSError(errno.EIO, "injected root close failure")
        interruption = KeyboardInterrupt("real SIGINT with injected root close failure")
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
        previous_handler = signal.getsignal(signal.SIGINT)

        def handler(signum, frame):
            delivered.append(signum)
            raise interruption

        def fail_close(fd):
            nonlocal replacement_fd, replacement_identity
            if fd != root_fd:
                return close(fd)
            attempted.append(fd)
            self.assert_reaped(children[0])
            self.assert_sentinel_only()
            if len(attempted) > 1:
                # A retry really closes the replacement, so its survival is an
                # independent oracle rather than just a mocked call assertion.
                return close(fd)
            if reuse_descriptor:
                close(fd)
                replacement_fd = open_descriptor(self.sentinel, os.O_RDONLY)
                replacement_identity = os.fstat(replacement_fd)
                self.assertEqual(replacement_fd, root_fd, "test must exercise exact descriptor reuse")
                self.assertFalse(os.path.samestat(replacement_identity, root_identity))
            try:
                raise failure
            finally:
                if pending_sigint:
                    signal.raise_signal(signal.SIGINT)

        try:
            signal.signal(signal.SIGINT, handler)
            with self.capture_children(children), ExitStack() as stack:
                with self.assertRaises(BaseException) as raised:
                    with fixture_run(self.config) as run:
                        run.start_worker()
                        root_fd, root_identity = run._root_fd, os.fstat(run._root_fd)
                        stack.enter_context(patch.object(os, "close", side_effect=fail_close))
                        if cancellation is not None:
                            raise cancellation
            self.assertEqual(attempted, [root_fd], "uncertain close must never be retried")
            retained_identity = replacement_identity if reuse_descriptor else root_identity
            self.assertTrue(os.path.samestat(os.fstat(root_fd), retained_identity))
            if reuse_descriptor:
                self.assertEqual(os.read(root_fd, 32), b"unrelated")
            self.assert_reaped(children[0])
            self.assert_sentinel_only()
            self.assertEqual(delivered, [signal.SIGINT] if pending_sigint else [])
            self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK, set()), previous_mask | {signal.SIGUSR1})
            self.assertIs(signal.getsignal(signal.SIGINT), handler)
            if cancellation is not None:
                self.assertIs(raised.exception, cancellation)
            elif pending_sigint:
                self.assertIs(raised.exception, interruption)
            chain, pending = [], [raised.exception]
            while pending:
                error = pending.pop()
                if error is None or any(error is prior for prior in chain):
                    continue
                chain.append(error)
                pending.extend((error.__cause__, error.__context__))
            self.assertIn(failure, chain)
            diagnostics = " ".join(
                text for error in chain for text in (str(error), *getattr(error, "__notes__", ()))
            ).lower()
            self.assertRegex(diagnostics, r"root.*(?:unknown|uncertain)")
        finally:
            signal.signal(signal.SIGINT, lambda signum, frame: None)
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
            signal.signal(signal.SIGINT, previous_handler)
            for child in children:
                self.reap_owned_child(child)
            if root_fd is not None:
                self.close_retained_descriptor(
                    root_fd, replacement_identity if replacement_fd == root_fd else root_identity
                )
            if replacement_fd is not None and replacement_fd != root_fd:
                self.close_retained_descriptor(replacement_fd, replacement_identity)

    def test_root_injected_close_failure_reports_uncertainty_without_retry(self):
        for reuse_descriptor in (False, True):
            with self.subTest(reuse_descriptor=reuse_descriptor):
                self.assert_root_close_fault(reuse_descriptor=reuse_descriptor)

    def test_root_injected_close_failure_preserves_caller_cancellation(self):
        for reuse_descriptor in (False, True):
            for cancellation in (KeyboardInterrupt("caller cancellation"), SystemExit(23)):
                with self.subTest(reuse_descriptor=reuse_descriptor, cancellation=type(cancellation).__name__):
                    self.assert_root_close_fault(reuse_descriptor=reuse_descriptor, cancellation=cancellation)

    def test_root_pending_sigint_reports_injected_close_uncertainty(self):
        for reuse_descriptor in (False, True):
            with self.subTest(reuse_descriptor=reuse_descriptor):
                self.assert_root_close_fault(reuse_descriptor=reuse_descriptor, pending_sigint=True)


if __name__ == "__main__":
    unittest.main()
