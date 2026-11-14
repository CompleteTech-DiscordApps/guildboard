"""Real local proxy negative controls, opt-in Docker prerequisite; no image pulls."""
import os
import sys
import io
import json
from types import SimpleNamespace
import subprocess
import signal
import importlib.util
from pathlib import Path
import unittest
from unittest import mock
import http.server
import socket
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
POSIX_LOCAL = os.name == "posix" and hasattr(os, "killpg") and hasattr(signal, "SIGKILL")
SPEC = importlib.util.spec_from_file_location("t10_probe", ROOT / "scripts/research/t10-nginx-probe.py")
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)

FIXTURE_SPEC = importlib.util.spec_from_file_location("t10_fixture", ROOT / "scripts/research/t10-proxy-fixture.py")
FIXTURE = importlib.util.module_from_spec(FIXTURE_SPEC)
FIXTURE_SPEC.loader.exec_module(FIXTURE)


class FixtureIdleRegression(unittest.TestCase):
    """Stdlib-only checks; these do not substitute for actual Nginx controls."""

    def test_backend_cannot_supply_false_positive_eof(self):
        self.assertGreater(FIXTURE.IDLE_BACKEND_HOLD_SECONDS, FIXTURE.IDLE_CLOSE_DEADLINE)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FIXTURE.Handler)
        server.idle_stop = threading.Event()
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        connect = socket.create_connection
        # Bypass the proxy: without its timeout, the probe must fail rather than
        # accept the backend's old three-second EOF as evidence of proxy closure.
        def direct_backend(_address, timeout):
            return connect(server.server_address, timeout=timeout)
        started = time.monotonic()
        try:
            with mock.patch.object(FIXTURE.socket, "create_connection", side_effect=direct_backend):
                with self.assertRaisesRegex(AssertionError, "client deadline expired before proxy EOF"):
                    FIXTURE.idle_close()
            elapsed = time.monotonic() - started
            self.assertGreaterEqual(elapsed, FIXTURE.IDLE_CLOSE_DEADLINE)
            self.assertLess(elapsed, FIXTURE.IDLE_BACKEND_HOLD_SECONDS)
        finally:
            server.idle_stop.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertFalse(thread.is_alive())

    def test_expected_proxy_close_is_accepted(self):
        with mock.patch.object(FIXTURE, "_websocket_exchange", return_value=(b"", 2)):
            self.assertEqual(FIXTURE.idle_close(), 2)

    def test_late_close_is_not_accepted(self):
        with mock.patch.object(FIXTURE, "_websocket_exchange", return_value=(b"", 4.5)):
            with self.assertRaisesRegex(AssertionError, "idle-close-within-bounded-window"):
                FIXTURE.idle_close()

    def test_early_close_is_not_accepted(self):
        with mock.patch.object(FIXTURE, "_websocket_exchange", return_value=(b"", 0)):
            with self.assertRaisesRegex(AssertionError, "idle-close-within-bounded-window"):
                FIXTURE.idle_close()

    def test_nonempty_idle_payload_is_not_accepted(self):
        with mock.patch.object(FIXTURE, "_websocket_exchange", return_value=(b"unexpected", 2)):
            with self.assertRaisesRegex(AssertionError, "idle-upstream-closed"):
                FIXTURE.idle_close()

    def exchange_with_delays(self, handshake_delay=0, idle_delay=0, drip=False):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        address = listener.getsockname()
        stop = threading.Event()
        def serve():
            try:
                with listener.accept()[0] as client:
                    client.settimeout(2)
                    request = b""
                    while b"\r\n\r\n" not in request:
                        request += client.recv(4096)
                    if stop.wait(handshake_delay):
                        return
                    response = (b"HTTP/1.1 101 Switching Protocols\r\n"
                                b"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                                b"Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n\r\n")
                    if drip:
                        for byte in response:
                            client.sendall(bytes([byte]))
                            if stop.wait(.03):
                                return
                    else:
                        client.sendall(response)
                    stop.wait(idle_delay)
            except (OSError, TimeoutError):
                pass  # The deadline test deliberately disconnects mid-handshake.
        thread = threading.Thread(target=serve)
        thread.start()
        connect = socket.create_connection
        try:
            with mock.patch.object(FIXTURE.socket, "create_connection", side_effect=lambda _, timeout: connect(address, timeout=timeout)):
                return FIXTURE.idle_close()
        finally:
            stop.set()
            listener.close()
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())

    def test_delayed_handshake_immediate_eof_is_not_idle_evidence(self):
        with self.assertRaisesRegex(FIXTURE.ProbeFailure, "idle-close-within-bounded-window"):
            self.exchange_with_delays(handshake_delay=2)

    def test_valid_post_upgrade_two_second_idle_is_accepted(self):
        elapsed = self.exchange_with_delays(handshake_delay=.1, idle_delay=2)
        self.assertGreaterEqual(elapsed, 1.5)
        self.assertLess(elapsed, FIXTURE.IDLE_CLOSE_DEADLINE)

    def test_slow_drip_handshake_has_one_total_deadline(self):
        started = time.monotonic()
        with mock.patch.object(FIXTURE, "IDLE_CLOSE_DEADLINE", .25):
            with self.assertRaises(TimeoutError):
                self.exchange_with_delays(drip=True)
        self.assertLess(time.monotonic() - started, 1.5)


class UpgradeRequestRegression(unittest.TestCase):
    def setUp(self):
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FIXTURE.Handler)
        self.server.idle_stop = threading.Event()
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.headers = [("Host", "research.invalid"), ("Upgrade", "websocket"), ("Connection", "Upgrade"),
                        ("Sec-WebSocket-Version", "13"), ("Sec-WebSocket-Key", "dGhlIHNhbXBsZSBub25jZQ==")]

    def tearDown(self):
        self.server.idle_stop.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive())

    def exchange(self, headers, method="GET", version="HTTP/1.1", path="/ws"):
        with socket.create_connection(self.server.server_address, timeout=2) as client:
            request = method + " " + path + " " + version + "\r\n" + "\r\n".join(name + ": " + value for name, value in headers) + "\r\n\r\n"
            client.sendall(request.encode("latin-1"))
            with client.makefile("rb") as stream:
                status = int(stream.readline().split()[1])
                response_headers = {}
                while True:
                    line = stream.readline()
                    if line == b"\r\n":
                        break
                    if not line:
                        self.fail("truncated fixture response")
                    name, value = line.decode().split(":", 1)
                    response_headers[name.lower()] = value.strip()
                payload = stream.read(7) if status == 101 else stream.read(int(response_headers.get("content-length", 0)))
                return status, response_headers, payload

    def test_case_and_connection_token_list_are_valid(self):
        headers = [(name.lower(), "keep-alive, UpGrAdE" if name == "Connection" else "WebSocket" if name == "Upgrade" else value) for name, value in self.headers]
        status, _, frame = self.exchange(headers)
        self.assertEqual(status, 101)
        self.assertEqual(frame, b"\x81\x05hello")

    def test_valid_authority_names_and_bracketed_ipv6_remain_accepted(self):
        for authority in ("research.invalid:8080", "[::1]:8080", "[::ffff:192.0.2.1]", "[v1.a:b]",
                          "[VAF.a-._~!$&'()*+,;=:]", "exa%6dple.invalid", "research.invalid:"):
            headers = [(key, authority if key == "Host" else value) for key, value in self.headers]
            with self.subTest(authority=authority):
                status, _, frame = self.exchange(headers)
                self.assertEqual(status, 101)
                self.assertEqual(frame, b"\x81\x05hello")

    def test_missing_or_malformed_request_headers_never_upgrade_or_send_frame(self):
        invalid = [(name, None) for name in ("Host", "Upgrade", "Connection", "Sec-WebSocket-Version", "Sec-WebSocket-Key")]
        invalid += [("Host", "[v1.a b]"), ("Host", "[v1.a%b]"), ("Host", "[v1.[x]"),
                    ("Host", "[v.abc]"), ("Host", "[vG.a]"), ("Host", "[v1.]"),
                    ("Host", "[1:2:3]"), ("Host", "[192.0.2.1]"), ("Host", "[::1%25eth0]"),
                    ("Host", "bad host"), ("Host", "user@host"), ("Host", "host/path"),
                    ("Host", "host?query"), ("Host", "[broken]"), ("Host", "host:word"), ("Host", "host%zz"),
                    ("Upgrade", "h2c"), ("Connection", "notupgrade"), ("Connection", "keep-alive"),
                    ("Sec-WebSocket-Version", "12"), ("Sec-WebSocket-Version", "13x"),
                    ("Sec-WebSocket-Key", "not-base64!"), ("Sec-WebSocket-Key", "eA=="),
                    ("Sec-WebSocket-Key", "eHh4eHh4eHh4eHh4eHh4eHg="), ("Sec-WebSocket-Key", "ÿ")]
        for name, value in invalid:
            headers = [(key, value if key == name else old) for key, old in self.headers if key != name or value is not None]
            with self.subTest(header=name, value=value):
                status, _, payload = self.exchange(headers)
                self.assertIn(status, (400, 426))
                self.assertNotIn(b"\x81\x05hello", payload)
        for name in ("Host", "Upgrade", "Sec-WebSocket-Key", "Sec-WebSocket-Version"):
            headers = self.headers + [next(item for item in self.headers if item[0] == name)]
            with self.subTest(duplicate=name):
                status, _, payload = self.exchange(headers)
                self.assertNotEqual(status, 101)
                self.assertNotIn(b"\x81\x05hello", payload)

    def test_wrong_method_or_http_version_cannot_upgrade(self):
        for kwargs in ({"method": "POST"}, {"version": "HTTP/1.0"}, {"path": "/unknown"}):
            with self.subTest(kwargs=kwargs):
                status, _, payload = self.exchange(self.headers, **kwargs)
                self.assertNotEqual(status, 101)
                self.assertNotIn(b"\x81\x05hello", payload)


@unittest.skipUnless(POSIX_LOCAL, "POSIX local Nginx runner required")
class LocalSetupCleanupRegression(unittest.TestCase):
    def test_setup_failures_close_backend_listener_and_thread(self):
        server_factory = http.server.ThreadingHTTPServer
        thread_factory = threading.Thread
        for failing in ("temporary-directory", "git-metadata", "nginx-version"):
            servers, threads = [], []
            def make_server(*args, **kwargs):
                server = server_factory(*args, **kwargs)
                servers.append(server)
                return server
            def make_thread(*args, **kwargs):
                thread = thread_factory(*args, **kwargs)
                threads.append(thread)
                return thread
            error = RuntimeError("injected setup failure")
            with self.subTest(failing=failing):
                try:
                    with mock.patch.object(PROBE.http.server, "ThreadingHTTPServer", side_effect=make_server), \
                         mock.patch.object(PROBE.threading, "Thread", side_effect=make_thread), \
                         mock.patch.object(PROBE.subprocess, "check_output", side_effect=error if failing == "git-metadata" else None, return_value="test-sha"), \
                         mock.patch.object(PROBE.subprocess, "run", side_effect=error), \
                         mock.patch.object(PROBE.tempfile, "TemporaryDirectory", side_effect=error if failing == "temporary-directory" else PROBE.tempfile.TemporaryDirectory):
                        with self.assertRaisesRegex(RuntimeError, "injected setup failure"):
                            PROBE.run_local(__file__)
                    self.assertTrue(servers)
                    self.assertEqual(servers[0].socket.fileno(), -1)
                    self.assertTrue(all(not thread.is_alive() for thread in threads))
                finally:
                    # Keep the regression itself bounded when exercising old code.
                    for server in servers:
                        server.idle_stop.set()
                        if any(thread.is_alive() for thread in threads):
                            server.shutdown()
                        server.server_close()
                    for thread in threads:
                        thread.join(timeout=2)


class HandshakeRegression(unittest.TestCase):
    def response(self, status="101 Switching Protocols", upgrade="websocket", connection="Upgrade", accept="s3pPLMBiTxaQ9kYGzzhZRbK+xOo=", extra_headers=()):
        headers = [f"HTTP/1.1 {status}"]
        if accept is not None:
            headers.append("Sec-WebSocket-Accept: " + accept)
        if upgrade is not None:
            headers.append("Upgrade: " + upgrade)
        if connection is not None:
            headers.append("Connection: " + connection)
        headers.extend(name + ": " + value for name, value in extra_headers)
        raw = ("\r\n".join(headers) + "\r\n\r\n").encode() + b"\x81\x05hello"
        client = mock.MagicMock()
        client.__enter__.return_value = client
        client.makefile.return_value = io.BytesIO(raw)
        return client

    def test_required_upgrade_headers_and_exact_status(self):
        for kwargs in ({"upgrade": None}, {"upgrade": "h2c"}, {"connection": None},
                       {"accept": None}, {"accept": "wrong-accept"},
                       {"connection": "notupgrade"}, {"status": "200 reason-101"},
                       {"status": "1010 Switching Protocols"}):
            with self.subTest(kwargs=kwargs), mock.patch.object(FIXTURE.socket, "create_connection", return_value=self.response(**kwargs)):
                with self.assertRaises(AssertionError):
                    FIXTURE.websocket("/ws")

    def test_connect_and_handshake_timeouts_cannot_certify_idle_control(self):
        for phase in ("connect", "send", "status", "headers"):
            client = self.response()
            connect = mock.Mock(return_value=client)
            if phase == "connect":
                connect.side_effect = TimeoutError("connect deadline")
            elif phase == "send":
                client.sendall.side_effect = TimeoutError("send deadline")
            else:
                stream = mock.MagicMock()
                stream.__enter__.return_value = stream
                stream.readline.side_effect = ([TimeoutError("status deadline")] if phase == "status"
                                              else [b"HTTP/1.1 101 Switching Protocols\r\n", TimeoutError("header deadline")])
                client.makefile.return_value = stream
            with self.subTest(phase=phase), mock.patch.object(FIXTURE.socket, "create_connection", connect):
                with self.assertRaises(TimeoutError):
                    FIXTURE.idle_close()

    def test_only_validated_idle_read_timeout_can_certify_control(self):
        class ReadTimeout(io.BytesIO):
            def read(self, *args):
                raise TimeoutError("frame/idle read deadline")
        for path in ("/ws", "/idle"):
            client = self.response()
            client.makefile.return_value = ReadTimeout(client.makefile.return_value.getvalue())
            with self.subTest(path=path), mock.patch.object(FIXTURE.socket, "create_connection", return_value=client):
                if path == "/idle":
                    with self.assertRaises(FIXTURE.ProbeFailure) as caught:
                        FIXTURE.idle_close()
                    self.assertEqual(caught.exception.check, "idle-close-deadline")
                else:
                    with self.assertRaises(TimeoutError):
                        FIXTURE.websocket(path)
        client = self.response(upgrade=None)
        client.makefile.return_value = ReadTimeout(client.makefile.return_value.getvalue())
        with mock.patch.object(FIXTURE.socket, "create_connection", return_value=client):
            with self.assertRaisesRegex(AssertionError, "missing/invalid Upgrade"):
                FIXTURE.idle_close()

    def test_unsolicited_negotiation_and_duplicate_singleton_responses_are_rejected(self):
        for name, value in (("Sec-WebSocket-Extensions", "permessage-deflate"),
                            ("Sec-WebSocket-Protocol", "unrequested"),
                            ("Sec-WebSocket-Accept", "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="),
                            ("Upgrade", "websocket")):
            with self.subTest(header=name), mock.patch.object(FIXTURE.socket, "create_connection", return_value=self.response(extra_headers=[(name, value)])):
                with self.assertRaises(FIXTURE.ProbeFailure):
                    FIXTURE.websocket("/ws")

    def test_repeated_connection_headers_combine_tokens(self):
        with mock.patch.object(FIXTURE.socket, "create_connection", return_value=self.response(connection="keep-alive", extra_headers=[("Connection", "UpGrAdE")])):
            self.assertEqual(FIXTURE.websocket("/ws"), b"\x81\x05hello")

    def test_connection_token_list_and_case_are_accepted(self):
        with mock.patch.object(FIXTURE.socket, "create_connection", return_value=self.response(upgrade="WebSocket", connection="keep-alive, UpGrAdE")):
            self.assertEqual(FIXTURE.websocket("/ws"), b"\x81\x05hello")


class FakeDocker:
    """Only an in-memory Docker command boundary, never platform evidence."""
    def __init__(self, create_timeout=None):
        self.containers = {}
        self.calls = []
        self.create_timeout = create_timeout
        self.inspect_errors = {}
        self.remove_mode = {}

    def add(self, name, token="token"):
        info = {"Id": format(len(self.containers) + 1, "064x"), "Name": "/" + name,
                "Config": {"Labels": {"guildboard.t10.probe": token}}}
        self.containers[name] = info
        return info

    def __call__(self, *args, **kwargs):
        self.calls.append(args)
        if args[:2] == ("image", "inspect"):
            return SimpleNamespace(stdout="[]", stderr="")
        if args[0] == "create":
            name = args[args.index("--name") + 1]
            label = args[args.index("--label") + 1].split("=", 1)[1]
            self.add(name, label)
            if self.create_timeout and name.endswith(self.create_timeout):
                raise subprocess.TimeoutExpired(args, 30)
        if args[:2] == ("container", "inspect"):
            reference = args[2]
            if reference in self.inspect_errors:
                raise self.inspect_errors[reference]
            info = self.containers.get(reference)
            if info is None:
                info = next((value for value in self.containers.values() if value["Id"] == reference), None)
            if info is None:
                raise subprocess.CalledProcessError(1, args, stderr="Error: No such container: " + reference)
            return SimpleNamespace(stdout=json.dumps([info]), stderr="")
        if args[:2] == ("container", "rm"):
            reference = args[-1]
            name = next(name for name, value in self.containers.items() if value["Id"] == reference)
            mode = self.remove_mode.get(name, self.remove_mode.get(name.rsplit("-", 1)[-1]))
            if mode in ("fail", "noop"):
                if mode == "fail":
                    raise subprocess.CalledProcessError(1, args, stderr="simulated removal failure")
            else:
                del self.containers[name]
                if mode == "timeout-after-delete":
                    raise subprocess.TimeoutExpired(args, 30)
        return SimpleNamespace(stdout="", stderr="")


class DockerCleanupRegression(unittest.TestCase):
    def test_image_preflight_failure_retains_metadata_and_bounded_diagnostics(self):
        for failing_image in (PROBE.NGINX, PROBE.PYTHON):
            fake = FakeDocker()
            marker = "OWNED_IMAGE_INSPECTION_DIAGNOSTIC"
            def command(*args, **kwargs):
                if args == ("image", "inspect", failing_image):
                    raise subprocess.CalledProcessError(1, args, output="owned inspection stdout",
                                                        stderr="x" * (PROBE.MAX_DIAGNOSTIC_BYTES + 100) + marker)
                return fake(*args, **kwargs)
            with self.subTest(image=failing_image), mock.patch.object(PROBE, "docker", side_effect=command):
                with self.assertRaises(subprocess.CalledProcessError) as caught:
                    PROBE.run()
            report = caught.exception.report
            self.assertEqual(report["images"], {"nginx": PROBE.NGINX, "python": PROBE.PYTHON})
            self.assertIn("host", report)
            self.assertIn(marker, report["failure"]["stderr"])
            self.assertTrue(report["failure"]["stderr_truncated"])
            self.assertLessEqual(len(report["failure"]["stderr"]), PROBE.MAX_DIAGNOSTIC_BYTES)
            self.assertEqual(report["failure"]["stdout"], "owned inspection stdout")
            self.assertEqual(report["cleanup"], [])
            self.assertFalse(any(call[0] == "create" for call in fake.calls))

    def test_create_timeout_after_daemon_creation_is_cleaned(self):
        for target in ("backend", "proxy"):
            fake = FakeDocker(create_timeout=target)
            with self.subTest(target=target), mock.patch.object(PROBE, "docker", side_effect=fake):
                with self.assertRaises(subprocess.TimeoutExpired):
                    PROBE.run()
            self.assertEqual(fake.containers, {})

    def test_runner_cleanup_failure_still_attempts_backend(self):
        fake = FakeDocker()
        fake.remove_mode["proxy"] = "fail"
        with mock.patch.object(PROBE, "docker", side_effect=fake):
            with self.assertRaises(RuntimeError):
                PROBE.run()
        self.assertFalse(any(name.endswith("backend") for name in fake.containers))
        self.assertTrue(any(name.endswith("proxy") for name in fake.containers))

    def test_failed_cleanup_continues_to_other_owned_container(self):
        for mode in ("fail", "noop", "unknown-inspect", "foreign-label", "invalid-identity"):
            fake = FakeDocker()
            fake.add("backend")
            proxy = fake.add("proxy")
            if mode in ("fail", "noop"):
                fake.remove_mode["proxy"] = mode
            elif mode == "unknown-inspect":
                fake.inspect_errors["proxy"] = subprocess.CalledProcessError(1, [], stderr="daemon unavailable")
            elif mode == "foreign-label":
                proxy["Config"]["Labels"]["guildboard.t10.probe"] = "other"
            else:
                proxy["Id"] = "not-an-immutable-container-id"
            report = {}
            with self.subTest(mode=mode), mock.patch.object(PROBE, "docker", side_effect=fake):
                with self.assertRaises(PROBE.DockerCleanupError) as caught:
                    PROBE.cleanup_owned_containers(["backend", "proxy"], "token", report)
            self.assertNotIn("backend", fake.containers)
            self.assertIn("proxy", fake.containers)
            self.assertEqual(len(caught.exception.failures), 1)
            self.assertIs(caught.exception.report, report)

    def test_collision_never_registers_or_removes_preexisting_container(self):
        fake = FakeDocker()
        fake.add("backend")
        intended = []
        with mock.patch.object(PROBE, "docker", side_effect=fake):
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                PROBE.create_owned_container(intended, "backend")
            PROBE.cleanup_owned_containers(intended, "token", {})
        self.assertEqual(intended, [])
        self.assertIn("backend", fake.containers)
        self.assertFalse(any(call[:2] == ("container", "rm") for call in fake.calls))

    def test_absence_is_strict_and_removal_timeout_is_verified(self):
        fake = FakeDocker()
        fake.add("backend")
        fake.remove_mode["backend"] = "timeout-after-delete"
        with mock.patch.object(PROBE, "docker", side_effect=fake):
            report = {}
            PROBE.cleanup_owned_containers(["backend", "absent"], "token", report)
            self.assertEqual(len(report["cleanup"]), 2)
            self.assertEqual(fake.containers, {})
            for message in ("daemon unavailable", "Error: No such container: unrelated", "No such file or directory"):
                fake.inspect_errors["absent"] = subprocess.CalledProcessError(1, [], stderr=message)
                with self.subTest(message=message), self.assertRaises(subprocess.CalledProcessError):
                    PROBE.inspect_container("absent")

    def test_malformed_inspection_never_authorizes_removal(self):
        for output in ("invalid JSON", "[]", "{}", "[{}, {}]", json.dumps([{"Config": None}])):
            call = mock.Mock(return_value=SimpleNamespace(stdout=output, stderr=""))
            with self.subTest(output=output), mock.patch.object(PROBE, "docker", call):
                with self.assertRaises(PROBE.DockerCleanupError):
                    PROBE.cleanup_owned_containers(["backend"], "token", {})
                self.assertFalse(any(args[:2] == ("container", "rm") for args, _ in call.call_args_list))

    def test_multiple_cleanup_failures_are_aggregated(self):
        fake = FakeDocker()
        fake.add("backend")
        fake.add("proxy")
        fake.remove_mode = {"backend": "fail", "proxy": "fail"}
        with mock.patch.object(PROBE, "docker", side_effect=fake):
            with self.assertRaises(PROBE.DockerCleanupError) as caught:
                PROBE.cleanup_owned_containers(["backend", "proxy"], "token", {})
        self.assertEqual(len(caught.exception.failures), 2)
        self.assertEqual(sum(call[:2] == ("container", "rm") for call in fake.calls), 2)


class CancellationRegression(unittest.TestCase):
    def test_first_signal_during_short_command_spawn_reaps_transient_child(self):
        original = subprocess.Popen
        for number in (signal.SIGTERM, signal.SIGINT):
            processes = []
            def popen(*args, **kwargs):
                process = original(*args, **kwargs)
                processes.append(process)
                os.kill(os.getpid(), number)
                return process
            try:
                with self.subTest(signal=number), PROBE.cancellation_signals(), mock.patch.object(subprocess, "Popen", side_effect=popen):
                    with self.assertRaises(PROBE.ExperimentCancelled) as caught:
                        PROBE.run_owned_command([sys.executable, "-c", "import time; time.sleep(.05)"], capture_output=True)
                self.assertEqual(caught.exception.signum, number)
                self.assertTrue(processes and all(process.poll() is not None for process in processes))
            finally:
                for process in processes:
                    if process.poll() is None: process.kill()
                    process.wait()
                    if process.stdout is not None: process.stdout.close()
                    if process.stderr is not None: process.stderr.close()

    @unittest.skipUnless(POSIX_LOCAL and Path("/proc").is_dir(), "POSIX/Linux process ownership required")
    def test_first_signal_after_nginx_spawn_before_assignment_reaps_owned_group(self):
        import contextlib
        binary = os.environ.get("T10_NGINX_BINARY")
        if not binary:
            self.skipTest("explicit local Nginx binary required")
        original = subprocess.Popen
        for number in (signal.SIGTERM, signal.SIGINT):
            output, processes, workers = io.StringIO(), [], []
            def popen(*args, **kwargs):
                process = original(*args, **kwargs)
                if kwargs.get("start_new_session"):
                    processes.append(process)
                    # Let actual Nginx spawn its worker before testing the assignment gap.
                    deadline = time.monotonic() + 2
                    while time.monotonic() < deadline:
                        children = Path(f"/proc/{process.pid}/task/{process.pid}/children")
                        if children.exists():
                            workers.extend(int(pid) for pid in children.read_text().split())
                        if workers:
                            break
                        time.sleep(.01)
                    os.kill(os.getpid(), number)
                return process
            try:
                with self.subTest(signal=number), mock.patch.object(subprocess, "Popen", side_effect=popen), contextlib.redirect_stdout(output):
                    code = PROBE.main(["--nginx-binary", binary])
                report = json.loads(output.getvalue())
                self.assertEqual(code, 128 + number)
                self.assertEqual(report["failure"]["signal"], signal.Signals(number).name)
                self.assertTrue(processes and workers, "must signal after actual owned master/worker creation")
                self.assertTrue(all(process.poll() is not None for process in processes))
                self.assertTrue(all(report["cleanup"].values()))
                deadline = time.monotonic() + 2
                def live(pid):
                    try:
                        return Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()[0] != "Z"
                    except FileNotFoundError:
                        return False
                while any(live(pid) for pid in workers) and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertFalse(any(live(pid) for pid in workers))
            finally:
                for process in processes:
                    PROBE.stop_local_proxy(process)

    @unittest.skipUnless(POSIX_LOCAL, "POSIX process ownership required")
    def test_first_signal_after_fetch_spawn_before_assignment_reaps_owned_child(self):
        import contextlib
        import tempfile
        spec = importlib.util.spec_from_file_location("capture_spawn", ROOT / "scripts/research/t10-capture-sources.py")
        capture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(capture)
        original = subprocess.Popen
        for number in (signal.SIGTERM, signal.SIGINT):
            output, processes = io.StringIO(), []
            def popen(*args, **kwargs):
                process = original([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
                processes.append(process)
                os.kill(os.getpid(), number)
                return process
            try:
                with self.subTest(signal=number), tempfile.TemporaryDirectory() as scratch, \
                     mock.patch.object(capture, "SOURCES", [("owned-child", "unused")]), \
                     mock.patch.object(subprocess, "Popen", side_effect=popen), contextlib.redirect_stdout(output):
                    code = capture.main(["--output", str(Path(scratch) / "capture.json")])
                report = json.loads(output.getvalue())
                self.assertEqual(code, 128 + number)
                self.assertEqual(report["failure"]["signal"], signal.Signals(number).name)
                self.assertTrue(report["sources"][0]["cancelled"])
                self.assertTrue(processes)
                self.assertTrue(all(process.poll() is not None and process.stdout.closed and process.stderr.closed for process in processes))
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    process.stdout.close()
                    process.stderr.close()

    @unittest.skipUnless(POSIX_LOCAL, "POSIX local resources required")
    def test_first_signal_after_local_acquisition_before_registration_closes_resources(self):
        import contextlib
        import tempfile
        binary = os.environ.get("T10_NGINX_BINARY")
        if not binary:
            self.skipTest("explicit local Nginx binary required")
        originals = (http.server.ThreadingHTTPServer, threading.Thread.start, tempfile.TemporaryDirectory, Path.open)
        for phase in ("server", "thread", "temporary-directory", "stderr-file"):
            for number in (signal.SIGTERM, signal.SIGINT):
                output, servers, threads, directories, files = io.StringIO(), [], [], [], []
                def server(*args, **kwargs):
                    resource = originals[0](*args, **kwargs); servers.append(resource)
                    if phase == "server": os.kill(os.getpid(), number)
                    return resource
                def start(resource):
                    result = originals[1](resource); threads.append(resource)
                    if phase == "thread": os.kill(os.getpid(), number)
                    return result
                def temporary(*args, **kwargs):
                    resource = originals[2](*args, **kwargs); directories.append(resource)
                    if phase == "temporary-directory": os.kill(os.getpid(), number)
                    return resource
                def opened(path, *args, **kwargs):
                    resource = originals[3](path, *args, **kwargs)
                    if path.name == "stderr.log" and args and args[0] == "w+b":
                        files.append(resource)
                        if phase == "stderr-file": os.kill(os.getpid(), number)
                    return resource
                try:
                    with self.subTest(phase=phase, signal=number), \
                         mock.patch.object(http.server, "ThreadingHTTPServer", side_effect=server), \
                         mock.patch.object(threading.Thread, "start", start), \
                         mock.patch.object(tempfile, "TemporaryDirectory", side_effect=temporary), \
                         mock.patch.object(Path, "open", opened), contextlib.redirect_stdout(output):
                        code = PROBE.main(["--nginx-binary", binary])
                    report = json.loads(output.getvalue())
                    self.assertEqual(code, 128 + number)
                    self.assertEqual(report["failure"]["signal"], signal.Signals(number).name)
                    self.assertTrue(all(report["cleanup"].values()))
                    self.assertTrue(all(resource.fileno() == -1 for resource in servers))
                    self.assertTrue(all(not resource.is_alive() for resource in threads))
                    self.assertTrue(all(not Path(resource.name).exists() for resource in directories))
                    self.assertTrue(all(resource.closed for resource in files))
                finally:
                    for resource in servers:
                        if any(thread.is_alive() for thread in threads): resource.shutdown()
                        resource.server_close()
                    for resource in threads: resource.join(timeout=2)
                    for resource in files: resource.close()
                    for resource in directories: resource.cleanup()

    def test_first_signal_during_normal_docker_cleanup_is_deferred(self):
        import contextlib
        for number in (signal.SIGTERM, signal.SIGINT):
            fake, output, sent = FakeDocker(), io.StringIO(), []
            foreign = fake.add("foreign", token="foreign")
            def command(*args, **kwargs):
                if args[:2] == ("container", "inspect") and args[2].endswith("proxy") and len(fake.containers) == 3 and not sent:
                    sent.append(number)
                    os.kill(os.getpid(), number)
                    os.kill(os.getpid(), signal.SIGINT if number == signal.SIGTERM else signal.SIGTERM)
                if args[0] == "exec" and args[-1] == "probe":
                    return SimpleNamespace(stdout=json.dumps({"checks": ["synthetic body success"]}), stderr="")
                return fake(*args, **kwargs)
            with self.subTest(signal=number), mock.patch.object(PROBE, "docker", side_effect=command), contextlib.redirect_stdout(output):
                code = PROBE.main([])
            report = json.loads(output.getvalue())
            self.assertEqual(code, 128 + number)
            self.assertEqual(report["failure"]["signal"], signal.Signals(number).name)
            self.assertEqual(report["cancellation"]["signal"], signal.Signals(number).name)
            self.assertEqual(fake.containers, {"foreign": foreign})
            self.assertEqual(len(report["cleanup"]), 2)
            self.assertTrue(all(item["absence_verified"] for item in report["cleanup"]))
            self.assertIn("result", report)

    @unittest.skipUnless(POSIX_LOCAL, "POSIX process ownership required")
    def test_first_signal_during_normal_local_cleanup_finishes_all_actions(self):
        import contextlib
        binary = os.environ.get("T10_NGINX_BINARY")
        if not binary:
            self.skipTest("explicit local Nginx binary required")
        original_spec = PROBE.importlib.util.spec_from_file_location
        original_stop, original_shutdown = PROBE.stop_local_proxy, http.server.ThreadingHTTPServer.shutdown
        def inject(name, path):
            spec = original_spec(name, path)
            load = spec.loader.exec_module
            def execute(module):
                load(module)
                module.probe = lambda: {"checks": ["synthetic body success; real owned cleanup"]}
            spec.loader.exec_module = execute
            return spec
        for phase in ("nginx", "backend"):
            for number in (signal.SIGTERM, signal.SIGINT):
                output, servers, processes = io.StringIO(), [], []
                def stop(proxy):
                    processes.append(proxy)
                    if phase == "nginx":
                        os.kill(os.getpid(), number)
                    return original_stop(proxy)
                def shutdown(server):
                    servers.append(server)
                    if phase == "backend":
                        os.kill(os.getpid(), number)
                    return original_shutdown(server)
                try:
                    with self.subTest(phase=phase, signal=number), \
                         mock.patch.object(PROBE.importlib.util, "spec_from_file_location", side_effect=inject), \
                         mock.patch.object(PROBE, "stop_local_proxy", side_effect=stop), \
                         mock.patch.object(http.server.ThreadingHTTPServer, "shutdown", shutdown), contextlib.redirect_stdout(output):
                        code = PROBE.main(["--nginx-binary", binary])
                    report = json.loads(output.getvalue())
                    self.assertEqual(code, 128 + number)
                    self.assertEqual(report["failure"]["signal"], signal.Signals(number).name)
                    self.assertTrue(all(report["cleanup"].values()))
                    self.assertTrue(all(process.poll() is not None for process in processes))
                    self.assertTrue(all(server.fileno() == -1 for server in servers))
                    self.assertIn("result", report)
                finally:
                    # Rescue only captured owned resources if old code skips an action.
                    for server in servers:
                        original_shutdown(server)
                        server.server_close()
                    for process in processes:
                        original_stop(process)

    def test_first_signal_during_normal_fetch_worker_cleanup_reaps_and_reports(self):
        import contextlib
        import tempfile
        spec = importlib.util.spec_from_file_location("t10_capture_cleanup", ROOT / "scripts/research/t10-capture-sources.py")
        capture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(capture)
        original_popen = subprocess.Popen
        for number in (signal.SIGTERM, signal.SIGINT):
            output, processes, sent = io.StringIO(), [], []
            def popen(*args, **kwargs):
                # Real disposable child, deterministic successful body; no public fetch.
                process = original_popen([sys.executable, "-c", "import json; print(json.dumps(dict(result=dict(http_status=200,bytes=2))))"], **kwargs)
                processes.append(process)
                original_wait = process.wait
                def wait(*args, **kwargs):
                    state = getattr(capture, "_cancellation_state", None)
                    if state and state["cleanup_depth"] and not sent:
                        sent.append(number)
                        os.kill(os.getpid(), number)
                    return original_wait(*args, **kwargs)
                process.wait = wait
                return process
            with self.subTest(signal=number), tempfile.TemporaryDirectory() as scratch, \
                 mock.patch.object(capture, "SOURCES", [("synthetic", "unused")]), \
                 mock.patch.object(capture.subprocess, "Popen", side_effect=popen), contextlib.redirect_stdout(output):
                code = capture.main(["--output", str(Path(scratch) / "report.json")])
            report = json.loads(output.getvalue())
            self.assertTrue(sent, "first signal must occur inside explicit owned cleanup")
            self.assertEqual(code, 128 + number)
            self.assertEqual(report["failure"]["signal"], signal.Signals(number).name)
            self.assertTrue(report["sources"][0]["cancelled"])
            self.assertTrue(all(process.poll() is not None and process.stdout.closed and process.stderr.closed for process in processes))

    def test_signal_handlers_restore_and_repeat_signals_do_not_interrupt_cleanup(self):
        spec = importlib.util.spec_from_file_location("t10_capture_cancel", ROOT / "scripts/research/t10-capture-sources.py")
        capture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(capture)
        for module in (PROBE, capture):
            previous = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}
            with self.subTest(module=module.__name__), module.cancellation_signals():
                with self.assertRaises(module.ExperimentCancelled):
                    signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
                signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
            self.assertEqual({number: signal.getsignal(number) for number in previous}, previous)

    def test_cancelled_uncertain_docker_create_reconciles_only_owned_resources(self):
        for target in ("backend", "proxy"):
            fake = FakeDocker()
            foreign = fake.add("foreign", token="foreign")
            def command(*args, **kwargs):
                result = fake(*args, **kwargs)
                if args[0] == "create" and args[args.index("--name") + 1].endswith(target):
                    signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
                if args[:2] == ("container", "rm"):
                    signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
                return result
            with self.subTest(target=target), PROBE.cancellation_signals(), mock.patch.object(PROBE, "docker", side_effect=command):
                with self.assertRaises(PROBE.ExperimentCancelled) as caught:
                    PROBE.run()
            self.assertEqual(fake.containers, {"foreign": foreign})
            self.assertEqual(caught.exception.report["failure"]["signal"], "SIGTERM")
            self.assertTrue(all(item["absence_verified"] for item in caught.exception.report["cleanup"]))

    @unittest.skipUnless(POSIX_LOCAL and Path("/proc").is_dir(), "POSIX/Linux process ownership required")
    def test_cli_signals_after_readiness_cleanup_and_emit_json(self):
        import tempfile
        import re
        binary = os.environ.get("T10_NGINX_BINARY")
        if not binary:
            self.skipTest("explicit local Nginx binary required")
        def process_start(pid):
            try:
                parts = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()
                return None if parts[0] == "Z" else parts[19]
            except FileNotFoundError:
                return None
        for number in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=number), tempfile.TemporaryDirectory(prefix="t10-cli-cancel-") as scratch:
                process = subprocess.Popen([sys.executable, str(ROOT / "scripts/research/t10-nginx-probe.py"),
                                            "--nginx-binary", binary, "--negative-control", "long-read-timeout"],
                                           env=dict(os.environ, TMPDIR=scratch), stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True)
                owned, group = {}, None
                try:
                    deadline, ready, temporary = time.monotonic() + 6, False, None
                    while time.monotonic() < deadline:
                        directories = list(Path(scratch).glob("gb-t10-nginx-*"))
                        if directories:
                            temporary = directories[0]
                            config = temporary / "nginx.conf"
                            if config.exists():
                                port = int(re.search(r"listen 127\.0\.0\.1:(\d+);", config.read_text()).group(1))
                                try:
                                    with socket.create_connection(("127.0.0.1", port), timeout=.1) as client:
                                        client.sendall(b"GET /ready HTTP/1.1\r\nHost: research.invalid\r\nConnection: close\r\n\r\n")
                                        ready = b" 200 " in client.recv(1024).split(b"\r\n", 1)[0]
                                except OSError:
                                    pass
                        if ready:
                            break
                        time.sleep(.02)
                    self.assertTrue(ready, "cancellation must happen after actual owned readiness")
                    children = Path(f"/proc/{process.pid}/task/{process.pid}/children").read_text().split()
                    for child in children:
                        pid = int(child)
                        if str(temporary).encode() in Path(f"/proc/{pid}/cmdline").read_bytes():
                            group = pid
                            owned[pid] = process_start(pid)
                            workers = Path(f"/proc/{pid}/task/{pid}/children").read_text().split()
                            owned.update({int(worker): process_start(int(worker)) for worker in workers})
                    self.assertIsNotNone(group)
                    process.send_signal(number)
                    stdout, stderr = process.communicate(timeout=6)
                    self.assertEqual(process.returncode, 128 + number, stderr)
                    report = json.loads(stdout)
                    self.assertEqual(report["failure"]["signal"], signal.Signals(number).name)
                    self.assertTrue(all(report["cleanup"].values()))
                    self.assertFalse(temporary.exists())
                    deadline = time.monotonic() + 2
                    while any(process_start(pid) == start for pid, start in owned.items() if start is not None) and time.monotonic() < deadline:
                        time.sleep(.02)
                    self.assertFalse(any(process_start(pid) == start for pid, start in owned.items() if start is not None))
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate(timeout=5)
                    # Bound the regression on old code; only captured ownership may authorize cleanup.
                    if group is not None and any(process_start(pid) == start for pid, start in owned.items() if start is not None):
                        for sig in (signal.SIGTERM, signal.SIGKILL):
                            try:
                                os.killpg(group, sig)
                            except ProcessLookupError:
                                pass

    @unittest.skipUnless(POSIX_LOCAL and Path("/proc").is_dir(), "POSIX/Linux child ownership required")
    def test_source_capture_signal_reaps_worker_and_retains_completed_rows(self):
        for number in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=number):
                self._source_capture_signal(number)

    def _source_capture_signal(self, number):
        import socketserver
        import tempfile
        stop, slow_connected = threading.Event(), threading.Event()
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                request = self.request.recv(4096)
                try:
                    if b"/slow " in request:
                        self.request.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 1000000\r\n\r\n")
                        slow_connected.set()
                        while not stop.wait(.02):
                            self.request.sendall(b"x")
                    else:
                        self.request.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
                except (BrokenPipeError, ConnectionResetError):
                    pass
        worker = None
        with tempfile.TemporaryDirectory(prefix="t10-capture-cancel-") as scratch, socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.05))
            thread.start()
            url = "http://127.0.0.1:" + str(server.server_address[1])
            output = str(Path(scratch) / "capture.json")
            program = ("import importlib.util,sys; s=importlib.util.spec_from_file_location('capture',sys.argv[1]); "
                       "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                       "m.SOURCES=[('healthy',sys.argv[2]+'/healthy'),('slow',sys.argv[2]+'/slow')]; "
                       "raise SystemExit(m.main(['--output',sys.argv[3]]))")
            process = subprocess.Popen([sys.executable, "-c", program, str(ROOT / "scripts/research/t10-capture-sources.py"), url, output], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertTrue(slow_connected.wait(timeout=6), "actual worker must be reading slow response")
                children = Path(f"/proc/{process.pid}/task/{process.pid}/children").read_text().split()
                for child in children:
                    command = Path(f"/proc/{child}/cmdline").read_bytes()
                    if b"--fetch-worker" in command and url.encode() in command:
                        worker = int(child)
                self.assertIsNotNone(worker)
                process.send_signal(number)
                stdout, stderr = process.communicate(timeout=6)
                self.assertEqual(process.returncode, 128 + number, stderr)
                report = json.loads(stdout)
                self.assertEqual(report["failure"]["signal"], signal.Signals(number).name)
                self.assertEqual(report["sources"][0]["bytes"], 2)
                self.assertTrue(report["sources"][1]["cancelled"])
                self.assertEqual(json.loads(Path(output).read_text()), report)
                self.assertFalse(Path(f"/proc/{worker}").exists(), "owned capture worker must be reaped")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
                if worker is not None:
                    try:
                        command = Path(f"/proc/{worker}/cmdline").read_bytes()
                        if b"--fetch-worker" in command and url.encode() in command:
                            os.kill(worker, signal.SIGKILL)
                    except FileNotFoundError:
                        pass
                stop.set()
                server.shutdown()
                thread.join(timeout=2)
        self.assertFalse(thread.is_alive())


@unittest.skipUnless(POSIX_LOCAL and sys.platform.startswith("linux"), "POSIX/Linux pipe publication regression")
class ReportPublicationRegression(unittest.TestCase):
    def publication_case(self, number=None, optimized=False, requested=False,
                         drain=True, success=False, full_stderr=False, closed_stdout=False):
        import tempfile
        import select
        with tempfile.TemporaryDirectory(prefix="t10-publication-") as scratch:
            directory = Path(scratch)
            temporary = directory / "temporary"
            temporary.mkdir()
            binary = directory / "owned-startup-failure"
            binary.write_text("#!" + sys.executable + "\nimport sys\n"
                              "if '-V' in sys.argv or '-t' in sys.argv: sys.exit(0)\n"
                              "print('x'*70000,file=sys.stderr)\nsys.exit(7)\n")
            binary.chmod(0o700)
            args = ["--nginx-binary", str(binary)]
            destination = directory / "requested.json"
            if requested:
                args += ["--output", str(destination)]
            if full_stderr:
                # Force a failed requested destination and an undrained stderr.
                args += ["--output", str(directory)]
            program = ("import importlib.util,sys,os; "
                       "s=importlib.util.spec_from_file_location('probe',sys.argv[1]); "
                       "m=importlib.util.module_from_spec(s);s.loader.exec_module(m); ")
            if success:
                program += "m.run_local=lambda *a,**k:{'result':'x'*70000}; "
            if full_stderr:
                program += "os.write(2,b'z'*4096); "
            program += "raise SystemExit(m.main(sys.argv[2:]))"
            command = [sys.executable] + (["-O"] if optimized else []) + ["-c", program, str(PROBE.__file__), *args]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       pipesize=4096, env={**os.environ, "TMPDIR": str(temporary), "PYTHONDONTWRITEBYTECODE": "1"})
            prefix = b""
            started = time.monotonic()
            try:
                if closed_stdout:
                    process.stdout.close()
                    process.stdout = None
                elif number is not None or not drain:
                    self.assertTrue(select.select([process.stdout], [], [], 8)[0], "report must reach actual pipe")
                    prefix = os.read(process.stdout.fileno(), 512)
                    self.assertTrue(prefix)
                if number is not None:
                    process.send_signal(number)
                if not drain:
                    process.wait(timeout=6)
                    self.assertLess(time.monotonic() - started, 6)
                stdout, stderr = process.communicate(timeout=8)
                stdout = prefix + (stdout or b"")
                if number is None and drain and not closed_stdout and not full_stderr:
                    self.assertEqual(process.returncode, 0 if success else 1, stderr)
                    self.assertEqual(json.loads(stdout).get("result") is not None, success)
                    if requested:
                        self.assertEqual(destination.read_bytes(), stdout)
                    self.assertEqual(list(temporary.iterdir()), [])
                    return
                self.assertEqual(process.returncode, 128 + number if number is not None else 1, stderr)
                self.assertNotIn(b"Traceback", stderr)
                if requested and not full_stderr:
                    copies = [destination]
                else:
                    copies = list(temporary.glob("guildboard-t10-report-*.json"))
                self.assertEqual(len(copies), 1, stderr)
                complete = copies[0].read_bytes()
                report = json.loads(complete)
                self.assertEqual(report.get("result") is not None, success)
                if not success:
                    self.assertEqual(report["failure"]["type"], "RuntimeError")
                    self.assertTrue(all(report["cleanup"].values()))
                self.assertTrue(complete.startswith(stdout), "no second JSON may follow a partial first object")
                if not full_stderr:
                    self.assertIn(str(copies[0]).encode(), stderr)
                self.assertFalse(any(path.is_dir() for path in temporary.iterdir()), "owned Nginx/backend temporary directories removed")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)

    def test_failure_publication_first_signal_preserves_snapshot_and_signal_status(self):
        for optimized in (False, True):
            for number in (signal.SIGTERM, signal.SIGINT):
                for requested in (False, True):
                    with self.subTest(optimized=optimized, signal=number, requested=requested):
                        self.publication_case(number, optimized, requested)

    def test_success_publication_first_signal_preserves_snapshot(self):
        for number in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=number):
                self.publication_case(number, success=True)

    def test_never_draining_stdout_has_bounded_signal_and_no_signal_exit(self):
        for number in (None, signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=number):
                self.publication_case(number, drain=False)

    def test_full_stderr_does_not_block_failure_or_signal(self):
        for number in (None, signal.SIGTERM):
            with self.subTest(signal=number):
                self.publication_case(number, drain=False, full_stderr=True)

    def test_closed_stdout_preserves_complete_snapshot(self):
        self.publication_case(closed_stdout=True)

    def test_no_signal_publishes_one_complete_report_and_removes_automatic_copy(self):
        for requested in (False, True):
            with self.subTest(requested=requested):
                self.publication_case(requested=requested)

    def test_signal_during_serialization_or_staging_is_recorded(self):
        import tempfile
        import contextlib
        for stage in ("serialization", "staging"):
            for number in (signal.SIGTERM, signal.SIGINT):
                output = io.StringIO()
                original = PROBE.json.dumps if stage == "serialization" else PROBE.report_copy
                triggered = False
                def inject(*args, **kwargs):
                    nonlocal triggered
                    if not triggered:
                        triggered = True
                        os.kill(os.getpid(), number)
                    return original(*args, **kwargs)
                target, name = (PROBE.json, "dumps") if stage == "serialization" else (PROBE, "report_copy")
                with self.subTest(stage=stage, signal=number), tempfile.TemporaryDirectory() as directory, \
                     mock.patch.object(PROBE, "run", return_value={"result": "complete"}), \
                     mock.patch.object(target, name, side_effect=inject), contextlib.redirect_stdout(output):
                    code = PROBE.main(["--output", str(Path(directory) / "report.json")])
                    self.assertEqual(code, 128 + number)
                    self.assertEqual(json.loads(output.getvalue()), {"result": "complete"})
                    self.assertEqual(json.loads((Path(directory) / "report.json").read_text()), {"result": "complete"})

    def test_fifo_or_symlink_to_fifo_output_fails_fast_without_mutating_it(self):
        import tempfile
        import contextlib
        import stat
        with tempfile.TemporaryDirectory() as directory:
            fifo = Path(directory) / "report.fifo"
            link = Path(directory) / "report.link"
            os.mkfifo(fifo)
            link.symlink_to(fifo)
            for destination in (fifo, link):
                stdout, stderr = io.StringIO(), io.StringIO()
                with self.subTest(destination=destination), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertFalse(PROBE.emit_report({"result": "retained"}, destination))
                self.assertEqual(json.loads(stdout.getvalue()), {"result": "retained"})
                self.assertTrue(stat.S_ISFIFO(fifo.stat().st_mode))
                self.assertIn("Cannot write probe report", stderr.getvalue())


class FailureAttributionRegression(unittest.TestCase):
    def test_windows_local_runner_fails_before_resources_with_json(self):
        import runpy
        import contextlib
        output = io.StringIO()
        with mock.patch.object(sys, "argv", ["probe", "--nginx-binary", "missing-binary"]), \
             mock.patch.object(PROBE.platform, "system", return_value="Windows"), \
             mock.patch.object(PROBE.http.server, "ThreadingHTTPServer") as server, \
             contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as caught:
                runpy.run_path(str(ROOT / "scripts/research/t10-nginx-probe.py"), run_name="__main__")
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("requires POSIX process groups", json.loads(output.getvalue())["failure"]["detail"])
        server.assert_not_called()

    def test_report_survives_output_write_failure(self):
        import tempfile
        import contextlib
        report = {"failure": {"detail": "retained failure"}, "cleanup": {"done": True}}
        output, errors = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertFalse(PROBE.emit_report(report, Path(directory)))
        self.assertEqual(json.loads(output.getvalue()), report)
        self.assertIn("Cannot write probe report", errors.getvalue())

    def test_docker_readiness_status_check_survives_optimization(self):
        fake = FakeDocker()
        with mock.patch.object(PROBE, "docker", side_effect=fake):
            with self.assertRaises(ValueError):
                PROBE.run()
        readiness = next(args[-1] for args in fake.calls if len(args) > 4 and args[-2] == "-c" and "urlopen" in args[-1])
        for status in (200, 503):
            prelude = "import urllib.request; from types import SimpleNamespace; urllib.request.urlopen = lambda *a, **k: SimpleNamespace(status=" + str(status) + "); "
            result = subprocess.run([sys.executable, "-O", "-c", prelude + readiness], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0 if status == 200 else 1)

    @unittest.skipUnless(POSIX_LOCAL, "POSIX local Nginx runner required")
    def test_cli_failure_emits_accumulated_report(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/research/t10-nginx-probe.py"),
                                 "--nginx-binary", sys.executable], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertIn("tested_sha", report)
        self.assertIn("failure", report)
        self.assertTrue(all(report["cleanup"].values()))

    def test_log_read_failure_cannot_replace_original_failure(self):
        report = {"failure": {"detail": "original experiment failure"}}
        errors = mock.Mock()
        errors.seek.side_effect = OSError("owned log read failure")
        PROBE.capture_nginx_log(errors, report)
        self.assertEqual(report["failure"], {"detail": "original experiment failure"})
        self.assertEqual(report["nginx_log_error"]["type"], "OSError")

    @unittest.skipUnless(POSIX_LOCAL, "POSIX owned executable required")
    def test_startup_failure_preserves_bounded_stderr_before_temp_cleanup(self):
        import tempfile
        marker = "UNIQUE_OWNED_NGINX_STARTUP_DIAGNOSTIC"
        with tempfile.TemporaryDirectory(prefix="t10-owned-diagnostic-") as directory:
            executable = Path(directory) / "owned-nginx-control"
            executable.write_text("#!" + sys.executable + "\nimport sys\n"
                                  "if '-V' in sys.argv or '-t' in sys.argv:\n"
                                  "    print('owned version/config control', file=sys.stderr)\n"
                                  "    sys.exit(0)\n"
                                  "print('x' * " + str(PROBE.MAX_DIAGNOSTIC_BYTES + 100) + ", file=sys.stderr)\n"
                                  "print('" + marker + "', file=sys.stderr)\n"
                                  "sys.exit(7)\n")
            executable.chmod(0o700)
            with self.assertRaisesRegex(RuntimeError, "owned nginx exited before readiness") as caught:
                PROBE.run_local(executable)
        report = caught.exception.report
        self.assertIn(marker, report["nginx_log"])
        self.assertTrue(report["nginx_log_truncated"])
        self.assertLessEqual(len(report["nginx_log"]), PROBE.MAX_DIAGNOSTIC_BYTES)
        self.assertTrue(all(report["cleanup"].values()))
        self.assertEqual(report["failure"]["type"], "RuntimeError")

    def test_failure_retains_successful_checks(self):
        with mock.patch.object(FIXTURE, "request", return_value=(200, b'{"path":"wrong"}')):
            with self.assertRaises(AssertionError) as caught:
                FIXTURE.probe()
        self.assertEqual(caught.exception.passed_checks, [])
        checks = [{"name": "first", "passed": True}]
        def fail_after_check(captured):
            captured.extend(checks)
            raise FIXTURE.ProbeFailure("second")
        with mock.patch.object(FIXTURE, "_probe", side_effect=fail_after_check):
            with self.assertRaises(FIXTURE.ProbeFailure) as caught:
                FIXTURE.probe()
        self.assertEqual(caught.exception.passed_checks, checks)

    @unittest.skipUnless(POSIX_LOCAL, "POSIX local Nginx runner required")
    def test_wait_failure_still_kills_group_and_reaps(self):
        process = mock.Mock(pid=12345)
        process.wait.side_effect = [RuntimeError("wait failure"), 0]
        with mock.patch.object(PROBE.os, "killpg") as kill:
            with self.assertRaisesRegex(RuntimeError, "wait failure"):
                PROBE.stop_local_proxy(process)
        self.assertEqual(kill.call_args_list, [mock.call(12345, signal.SIGTERM), mock.call(12345, signal.SIGKILL)])
        self.assertEqual(process.wait.call_count, 2)

    def test_docker_timeout_failure_detail_is_asserted(self):
        fake = FakeDocker()
        failure = {"check": "idle-close-deadline", "detail": "client deadline expired before proxy EOF", "passed_checks": []}
        def command(*args, **kwargs):
            if args[-2:] == ("/tmp/probe.py", "probe"):
                raise subprocess.CalledProcessError(1, args, output=json.dumps({"failure": failure}))
            return fake(*args, **kwargs)
        with mock.patch.object(PROBE, "docker", side_effect=command):
            result = PROBE.run("long-read-timeout")
        with mock.patch.object(ActualNginxControls, "run_probe", return_value=result):
            ActualNginxControls("test_long_read_timeout_is_detected").test_long_read_timeout_is_detected()

    def test_docker_baseline_retains_structured_failed_check(self):
        fake = FakeDocker()
        failure = {"check": "private-assets-not-public", "detail": "", "passed_checks": [{"name": "path-query-preserved", "passed": True}]}
        def command(*args, **kwargs):
            if args[-2:] == ("/tmp/probe.py", "probe"):
                raise subprocess.CalledProcessError(1, args, output=json.dumps({"failure": failure}))
            return fake(*args, **kwargs)
        with mock.patch.object(PROBE, "docker", side_effect=command):
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                PROBE.run()
        self.assertEqual(caught.exception.report["failure"], failure)
        self.assertEqual(len(caught.exception.report["cleanup"]), 2)

    def test_fixture_cli_retains_generic_failure_and_prior_checks(self):
        import runpy
        import contextlib
        import http.client
        first = mock.Mock()
        first.getresponse.return_value.status = 200
        first.getresponse.return_value.read.return_value = b'{"path":"/health?x=1","host":"research.invalid","forwarded_for":"127.0.0.1","proto":"http"}'
        second = mock.Mock()
        second.getresponse.return_value.status = 404
        second.getresponse.return_value.read.return_value = b""
        third = mock.Mock()
        third.request.side_effect = OSError("injected generic failure")
        output = io.StringIO()
        with mock.patch.object(sys, "argv", ["fixture", "probe"]), \
             mock.patch.object(http.client, "HTTPConnection", side_effect=[first, second, third]), \
             contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as caught:
                runpy.run_path(str(ROOT / "scripts/research/t10-proxy-fixture.py"), run_name="__main__")
        self.assertEqual(caught.exception.code, 1)
        failure = json.loads(output.getvalue())["failure"]
        self.assertEqual(failure["check"], "unexpected-probe-failure")
        self.assertEqual(failure["type"], "OSError")
        self.assertEqual(len(failure["passed_checks"]), 5)

    def test_unrelated_docker_stderr_cannot_pass_negative_control(self):
        fake = FakeDocker()
        def command(*args, **kwargs):
            if args[-2:] == ("/tmp/probe.py", "probe"):
                raise subprocess.CalledProcessError(1, args, output="", stderr="unrelated failure HTTP/1.1 426")
            return fake(*args, **kwargs)
        with mock.patch.object(PROBE, "docker", side_effect=command):
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                PROBE.run("strip-upgrade")
        self.assertIn("nginx_config_check", caught.exception.report)
        self.assertIn("failure", caught.exception.report)
        self.assertEqual(len(caught.exception.report["cleanup"]), 2)
        self.assertEqual(fake.containers, {})

    @unittest.skipUnless(POSIX_LOCAL, "POSIX local Nginx runner required")
    def test_unrelated_local_assertion_cannot_pass_negative_control(self):
        binary = os.environ.get("T10_NGINX_BINARY")
        if not binary:
            self.skipTest("explicit local Nginx binary required")
        original = PROBE.importlib.util.spec_from_file_location
        def inject(name, path):
            spec = original(name, path)
            load = spec.loader.exec_module
            def execute(module):
                load(module)
                module.probe = mock.Mock(side_effect=AssertionError("unrelated 426 failure"))
            spec.loader.exec_module = execute
            return spec
        with mock.patch.object(PROBE.importlib.util, "spec_from_file_location", side_effect=inject):
            with self.assertRaisesRegex(AssertionError, "unrelated 426 failure") as caught:
                PROBE.run_local(binary, "strip-upgrade")
        self.assertIn("nginx_version", caught.exception.report)
        self.assertTrue(all(caught.exception.report["cleanup"].values()))
        self.assertNotIn("negative_control", caught.exception.report)


class ActualNginxControls(unittest.TestCase):
    def run_probe(self, control):
        binary = os.environ.get("T10_NGINX_BINARY")
        if binary and not POSIX_LOCAL:
            self.skipTest("explicit local Nginx binary requires POSIX; omit T10_NGINX_BINARY for Docker mode")
        return PROBE.run_local(binary, control) if binary else PROBE.run(control)

    def assert_cleanup(self, result):
        cleanup = result["cleanup"]
        self.assertTrue(all(cleanup.values()) if isinstance(cleanup, dict) else all(item["absence_verified"] for item in cleanup))

    @unittest.skipUnless(POSIX_LOCAL and Path("/proc").is_dir(), "POSIX and Linux process introspection required")
    def test_unexpected_failure_closes_actual_nginx_workers_and_listener(self):
        binary = os.environ.get("T10_NGINX_BINARY")
        if not binary:
            self.skipTest("explicit local Nginx binary required")
        original_spec = PROBE.importlib.util.spec_from_file_location
        original_popen = PROBE.subprocess.Popen
        owned = {"workers": []}
        def capture_popen(args, *rest, **kwargs):
            process = original_popen(args, *rest, **kwargs)
            if "daemon off;" in args:
                owned["master"] = process.pid
                owned["stderr_fd"] = kwargs["stderr"].fileno()
            return process
        def inject_spec(name, path):
            spec = original_spec(name, path)
            original_exec = spec.loader.exec_module
            def load(module):
                original_exec(module)
                def fail_after_readiness():
                    owned["port"] = module.PROXY_PORT
                    children = Path(f"/proc/{owned['master']}/task/{owned['master']}/children")
                    owned["workers"] = [int(pid) for pid in children.read_text().split()]
                    os.write(owned["stderr_fd"], b"OWNED_UNEXPECTED_PROBE_DIAGNOSTIC\n")
                    raise AssertionError("injected unexpected probe failure")
                module.probe = fail_after_readiness
            spec.loader.exec_module = load
            return spec
        def running(pid):
            try:
                return Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()[0] != "Z"
            except FileNotFoundError:
                return False
        try:
            with mock.patch.object(PROBE.importlib.util, "spec_from_file_location", side_effect=inject_spec), \
                 mock.patch.object(PROBE.subprocess, "Popen", side_effect=capture_popen):
                with self.assertRaisesRegex(AssertionError, "injected unexpected probe failure") as caught:
                    PROBE.run_local(binary)
            self.assertIn("OWNED_UNEXPECTED_PROBE_DIAGNOSTIC", caught.exception.report["nginx_log"])
            deadline = time.monotonic() + 2
            while any(running(pid) for pid in owned["workers"]) and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(owned["workers"], "test must observe actual Nginx worker processes")
            self.assertFalse(any(running(pid) for pid in owned["workers"]))
            with self.assertRaises(OSError):
                with socket.create_connection(("127.0.0.1", owned["port"]), timeout=1):
                    pass
        finally:
            # Bound cleanup even when run against the original leaking runner.
            for pid in owned["workers"]:
                if running(pid):
                    os.kill(pid, signal.SIGTERM)

    @unittest.skipUnless(POSIX_LOCAL, "POSIX local Nginx runner required")
    def test_idle_connect_timeout_is_not_an_actual_control_success(self):
        binary = os.environ.get("T10_NGINX_BINARY")
        if not binary:
            self.skipTest("explicit local Nginx binary required")
        original = PROBE.importlib.util.spec_from_file_location
        def inject(name, path):
            spec = original(name, path)
            load = spec.loader.exec_module
            def execute(module):
                load(module)
                websocket = module._websocket_exchange
                def fail_idle_connect(path, *args, **kwargs):
                    if path == "/idle":
                        raise TimeoutError("injected idle connect timeout")
                    return websocket(path, *args, **kwargs)
                module._websocket_exchange = fail_idle_connect
            spec.loader.exec_module = execute
            return spec
        with mock.patch.object(PROBE.importlib.util, "spec_from_file_location", side_effect=inject):
            with self.assertRaisesRegex(TimeoutError, "injected idle connect timeout") as caught:
                PROBE.run_local(binary, "long-read-timeout")
        self.assertNotIn("negative_control", caught.exception.report)
        self.assertTrue(all(caught.exception.report["cleanup"].values()))
        self.assertIn("actual-101-and-frame", [row["name"] for row in caught.exception.report["failure"]["passed_checks"]])

    def test_long_read_timeout_is_detected(self):
        result = self.run_probe("long-read-timeout")
        self.assertTrue(result["negative_control"]["detected"])
        failure = result["negative_control"]["failure"]
        detail = failure["detail"] if isinstance(failure, dict) else failure
        self.assertIn("client deadline expired before proxy EOF", detail)
        self.assert_cleanup(result)

    def test_upgrade_removal_is_detected(self):
        result = self.run_probe("strip-upgrade")
        self.assertTrue(result["negative_control"]["detected"])
        self.assert_cleanup(result)

    def test_dropped_connection_key_and_version_are_detected(self):
        for control in ("strip-connection", "strip-key", "strip-version"):
            with self.subTest(control=control):
                result = self.run_probe(control)
                self.assertTrue(result["negative_control"]["detected"])
                failure = result["negative_control"]["failure"]
                detail = failure["detail"] if isinstance(failure, dict) else failure
                self.assertIn(PROBE.HANDSHAKE_REJECTIONS[control], detail)
                self.assert_cleanup(result)

    def test_public_private_route_is_detected(self):
        result = self.run_probe("publish-private-assets")
        self.assertTrue(result["negative_control"]["detected"])
        self.assert_cleanup(result)



class SourceCaptureRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get("CAPTURE_REGRESSION_SCRIPT", str(ROOT / "scripts/research/t10-capture-sources.py")))
        spec = importlib.util.spec_from_file_location("capture_regression", path)
        cls.capture_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.capture_module)

    def collect(self, responses):
        import socketserver
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.recv(4096)
                self.request.sendall(responses.pop(0))
        with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            url = "http://127.0.0.1:" + str(server.server_address[1])
            try:
                return self.invoke(url)
            finally:
                server.shutdown()
                thread.join(timeout=2)

    def test_truncated_length_is_failure_and_other_source_survives(self):
        result = self.collect([
            b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\nConnection: close\r\n\r\nshort",
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"])
        self.assert_failed_then_success(result)

    def test_broken_chunk_is_failure_and_other_source_survives(self):
        result = self.collect([
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n5\r\nx",
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"])
        self.assert_failed_then_success(result)

    def invoke(self, url):
        with mock.patch.object(self.capture_module, "SOURCES", [("first", url), ("second", url)]):
            return self.capture_module.capture()["sources"]

    def assert_failed_then_success(self, result):
        self.assertIn("error", result[0])
        self.assertNotIn("sha256", result[0])
        self.assertEqual(result[1]["bytes"], 2)

    def test_slow_drip_deadline_reaps_worker_and_preserves_healthy_result(self):
        import socketserver
        import time
        stop = threading.Event()
        connected = threading.Event()
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                request = self.request.recv(4096)
                try:
                    if b"/slow " in request:
                        self.request.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 100000\r\n\r\n")
                        connected.set()
                        while not stop.wait(0.02):
                            self.request.sendall(b"x")
                    else:
                        self.request.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
                except (BrokenPipeError, ConnectionResetError):
                    pass
        processes = []
        original_popen = subprocess.Popen
        def popen(*args, **kwargs):
            process = original_popen(*args, **kwargs)
            processes.append(process)
            return process
        with socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.05))
            thread.start()
            url = "http://127.0.0.1:" + str(server.server_address[1])
            started = time.monotonic()
            try:
                with mock.patch.object(self.capture_module, "ATTEMPT_SECONDS", 0.8), \
                     mock.patch.object(self.capture_module.subprocess, "Popen", side_effect=popen):
                    with mock.patch.object(self.capture_module, "SOURCES", [("slow", url + "/slow"), ("healthy", url + "/healthy")]):
                        result = self.capture_module.capture()["sources"]
                elapsed = time.monotonic() - started
                self.assertTrue(connected.is_set(), "test must exercise actual slow HTTP traffic")
                self.assertLess(elapsed, 3, "healthy output must not await the trickling body")
                self.assertIn("deadline exceeded", result[0]["error"])
                self.assertEqual(result[1]["bytes"], 2)
                self.assertTrue(processes)
                self.assertTrue(all(process.poll() is not None for process in processes), "all fetch children must be reaped")
            finally:
                stop.set()
                server.shutdown()
                thread.join(timeout=2)
        self.assertFalse(thread.is_alive())

    def test_source_cli_write_failure_preserves_collected_rows(self):
        import tempfile
        import contextlib
        import runpy
        output, errors = io.StringIO(), io.StringIO()
        response = mock.Mock(returncode=0)
        response.communicate.return_value = (json.dumps({"result": {"http_status": 200, "bytes": 2, "sha256": "test", "final_url": "http://fixture"}}), "")
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(sys, "argv", ["capture", "--output", directory]), \
             mock.patch.object(subprocess, "Popen", return_value=response), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            with self.assertRaises(SystemExit) as caught:
                runpy.run_path(str(ROOT / "scripts/research/t10-capture-sources.py"), run_name="__main__")
        self.assertEqual(caught.exception.code, 1)
        rows = json.loads(output.getvalue())["sources"]
        self.assertEqual(len(rows), len(self.capture_module.SOURCES))
        self.assertTrue(all(row["status"] == 200 for row in rows))
        self.assertIn("Cannot write source report", errors.getvalue())

    def test_exhausted_collection_budget_starts_no_worker(self):
        with mock.patch.object(self.capture_module.subprocess, "Popen") as popen:
            with mock.patch.object(self.capture_module, "COLLECTION_SECONDS", 0):
                rows = self.capture_module.capture()["sources"]
            self.assertTrue(all("deadline exceeded" in row["error"] for row in rows))
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
