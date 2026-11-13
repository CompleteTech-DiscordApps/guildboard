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
        with mock.patch.object(FIXTURE, "websocket", return_value=b"") as websocket:
            with mock.patch.object(FIXTURE.time, "monotonic", side_effect=[10, 12]):
                self.assertEqual(FIXTURE.idle_close(), 2)
        websocket.assert_called_once_with("/idle", timeout=FIXTURE.IDLE_CLOSE_DEADLINE)

    def test_late_close_is_not_accepted(self):
        with mock.patch.object(FIXTURE, "websocket", return_value=b""):
            with mock.patch.object(FIXTURE.time, "monotonic", side_effect=[10, 14.5]):
                with self.assertRaisesRegex(AssertionError, "idle-close-within-bounded-window"):
                    FIXTURE.idle_close()

    def test_early_close_is_not_accepted(self):
        with mock.patch.object(FIXTURE, "websocket", return_value=b""):
            with self.assertRaisesRegex(AssertionError, "idle-close-within-bounded-window"):
                FIXTURE.idle_close()

    def test_nonempty_idle_payload_is_not_accepted(self):
        with mock.patch.object(FIXTURE, "websocket", return_value=b"unexpected"):
            with self.assertRaisesRegex(AssertionError, "idle-upstream-closed"):
                FIXTURE.idle_close()


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
    def response(self, status="101 Switching Protocols", upgrade="websocket", connection="Upgrade"):
        headers = [f"HTTP/1.1 {status}", "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo="]
        if upgrade is not None:
            headers.append("Upgrade: " + upgrade)
        if connection is not None:
            headers.append("Connection: " + connection)
        raw = ("\r\n".join(headers) + "\r\n\r\n").encode() + b"\x81\x05hello"
        client = mock.MagicMock()
        client.__enter__.return_value = client
        client.makefile.return_value = io.BytesIO(raw)
        return client

    def test_required_upgrade_headers_and_exact_status(self):
        for kwargs in ({"upgrade": None}, {"upgrade": "h2c"}, {"connection": None},
                       {"connection": "notupgrade"}, {"status": "200 reason-101"},
                       {"status": "1010 Switching Protocols"}):
            with self.subTest(kwargs=kwargs), mock.patch.object(FIXTURE.socket, "create_connection", return_value=self.response(**kwargs)):
                with self.assertRaises(AssertionError):
                    FIXTURE.websocket("/ws")

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


class FailureAttributionRegression(unittest.TestCase):
    def test_cli_failure_emits_accumulated_report(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/research/t10-nginx-probe.py"),
                                 "--nginx-binary", sys.executable], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertIn("tested_sha", report)
        self.assertIn("failure", report)
        self.assertTrue(all(report["cleanup"].values()))

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
        return PROBE.run_local(binary, control) if binary else PROBE.run(control)

    def assert_cleanup(self, result):
        cleanup = result["cleanup"]
        self.assertTrue(all(cleanup.values()) if isinstance(cleanup, dict) else all(item["absence_verified"] for item in cleanup))

    @unittest.skipUnless(Path("/proc").is_dir(), "Linux process introspection required")
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
                with self.assertRaisesRegex(AssertionError, "injected unexpected probe failure"):
                    PROBE.run_local(binary)
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

    def test_exhausted_collection_budget_starts_no_worker(self):
        with mock.patch.object(self.capture_module.subprocess, "Popen") as popen:
            with mock.patch.object(self.capture_module, "COLLECTION_SECONDS", 0):
                rows = self.capture_module.capture()["sources"]
            self.assertTrue(all("deadline exceeded" in row["error"] for row in rows))
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
