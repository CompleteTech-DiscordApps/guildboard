"""Real local proxy negative controls, opt-in Docker prerequisite; no image pulls."""
import os
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


class ActualNginxControls(unittest.TestCase):
    def run_probe(self, control):
        binary = os.environ.get("T10_NGINX_BINARY")
        return PROBE.run_local(binary, control) if binary else PROBE.run(control)

    def assert_cleanup(self, result):
        cleanup = result["cleanup"]
        self.assertTrue(all(cleanup.values()) if isinstance(cleanup, dict) else all(item["absence_verified"] for item in cleanup))

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
