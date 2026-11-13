"""Real local proxy negative controls, opt-in Docker prerequisite; no image pulls."""
import os
import io
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
        self.assertIn("client deadline expired before proxy EOF", result["negative_control"]["failure"])
        self.assert_cleanup(result)

    def test_upgrade_removal_is_detected(self):
        result = self.run_probe("strip-upgrade")
        self.assertTrue(result["negative_control"]["detected"])
        self.assert_cleanup(result)

    def test_public_private_route_is_detected(self):
        result = self.run_probe("publish-private-assets")
        self.assertTrue(result["negative_control"]["detected"])
        self.assert_cleanup(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
