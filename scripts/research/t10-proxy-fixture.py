"""Synthetic backend/client for the isolated real-Nginx probe; no application code."""
import base64
import binascii
import hashlib
import http.client
import http.server
import json
import socket
import sys
import threading
import time

# Keep the upstream silent and open beyond the client acceptance deadline.
PROXY_PORT = 8080
IDLE_CLOSE_DEADLINE = 4.5
IDLE_BACKEND_HOLD_SECONDS = 10


class ProbeFailure(AssertionError):
    def __init__(self, check, detail=""):
        self.check = check
        self.detail = detail
        super().__init__(check + (": " + detail if detail else ""))


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path == "/shutdown":
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path in ("/ws", "/idle"):
            if self.request_version != "HTTP/1.1" or not self.headers.get("Host", "").strip():
                self.send_error(400)
                return
            upgrades = self.headers.get_all("Upgrade", [])
            if len(upgrades) != 1 or upgrades[0].strip().lower() != "websocket":
                self.send_error(426)
                return
            tokens = {token.strip().lower() for token in ",".join(self.headers.get_all("Connection", [])).split(",")}
            if "upgrade" not in tokens:
                self.send_error(400)
                return
            versions = self.headers.get_all("Sec-WebSocket-Version", [])
            if len(versions) != 1 or versions[0].strip() != "13":
                self.send_response(426)
                self.send_header("Sec-WebSocket-Version", "13")
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                return
            keys = self.headers.get_all("Sec-WebSocket-Key", [])
            key = keys[0].strip() if len(keys) == 1 else ""
            try:
                decoded = base64.b64decode(key, validate=True)
            except (binascii.Error, ValueError):
                decoded = b""
            if len(decoded) != 16:
                self.send_error(400)
                return
            accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            if self.path == "/idle":
                self.server.idle_stop.wait(IDLE_BACKEND_HOLD_SECONDS)
            else:
                self.wfile.write(b"\x81\x05hello")
                self.wfile.flush()
            self.close_connection = True
            return
        data = json.dumps({"path": self.path, "host": self.headers.get("Host"),
                           "forwarded_for": self.headers.get("X-Forwarded-For"),
                           "proto": self.headers.get("X-Forwarded-Proto")}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def request(path, method="GET", body=None, headers=None):
    client = http.client.HTTPConnection("127.0.0.1", PROXY_PORT, timeout=5)
    try:
        client.request(method, path, body=body, headers=headers or {})
        response = client.getresponse()
        return response.status, response.read()
    finally:
        client.close()


def websocket(path, timeout=5):
    with socket.create_connection(("127.0.0.1", PROXY_PORT), timeout=timeout) as client:
        client.settimeout(timeout)
        client.sendall((f"GET {path} HTTP/1.1\r\nHost: research.invalid\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n").encode())
        with client.makefile("rb") as stream:
            status = stream.readline()
            headers = {}
            while True:
                line = stream.readline()
                if line == b"\r\n":
                    break
                if not line:
                    raise AssertionError("truncated handshake")
                name, value = line.decode().split(":", 1)
                key = name.lower()
                headers[key] = headers.get(key, "") + ("," if key in headers else "") + value.strip()
            parts = status.split()
            if not (len(parts) >= 2 and parts[0] == b"HTTP/1.1" and parts[1] == b"101"):
                raise ProbeFailure("websocket-status", status.decode(errors="replace").strip())
            if headers.get("upgrade", "").lower() != "websocket":
                raise ProbeFailure("websocket-upgrade", "missing/invalid Upgrade response")
            tokens = {token.strip().lower() for token in headers.get("connection", "").split(",")}
            if "upgrade" not in tokens:
                raise ProbeFailure("websocket-connection", "missing Connection upgrade token")
            if headers.get("sec-websocket-accept") != "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=":
                raise ProbeFailure("websocket-accept", "missing/invalid Sec-WebSocket-Accept")
            try:
                return stream.read(1 if path == "/idle" else 7)
            except TimeoutError as error:
                # Only a read AFTER validating the 101 and every upgrade header
                # proves that the idle tunnel remained open. Connect, request,
                # status/header, and /ws frame timeouts are unrelated failures.
                if path == "/idle":
                    raise ProbeFailure("idle-close-deadline", "client deadline expired before proxy EOF") from error
                raise


def idle_close():
    started = time.monotonic()
    payload = websocket("/idle", timeout=IDLE_CLOSE_DEADLINE)
    elapsed = time.monotonic() - started
    if payload != b"":
        raise ProbeFailure("idle-upstream-closed")
    if not 1.5 <= elapsed < IDLE_CLOSE_DEADLINE:
        raise ProbeFailure("idle-close-within-bounded-window")
    return elapsed


def _probe(checks):
    def check(name, condition):
        if not condition:
            raise ProbeFailure(name)
        checks.append({"name": name, "passed": True})
    status, raw = request("/health?x=1", headers={"X-Forwarded-For": "spoof", "X-Forwarded-Proto": "https", "Host": "attacker.invalid"})
    data = json.loads(raw)
    check("path-query-preserved", status == 200 and data["path"] == "/health?x=1")
    check("upstream-host-fixed", data["host"] == "research.invalid")
    check("forwarded-ip-overwritten", data["forwarded_for"] != "spoof" and "," not in data["forwarded_for"])
    check("forwarded-proto-overwritten", data["proto"] == "http")
    check("private-assets-not-public", request("/private-assets/fixture")[0] == 404)
    check("oversized-body-rejected", request("/health", "POST", b"x" * 2048)[0] == 413)
    check("missing-websocket-upgrade-rejected", request("/ws")[0] == 426)
    check("actual-101-and-frame", websocket("/ws") == b"\x81\x05hello")
    elapsed = idle_close()
    check("idle-upstream-closed", True)
    check("idle-close-within-bounded-window", True)
    check("fixture-shutdown-ack", request("/shutdown")[0] == 200)
    time.sleep(0.6)
    check("upstream-unavailable-fails", request("/health")[0] == 502)
    return {"checks": checks, "idle_close_seconds": round(elapsed, 4), "scope": "local HTTP/WS real nginx + synthetic stdlib backend; no TLS/Discord/VPS proof"}


def probe():
    checks = []
    try:
        return _probe(checks)
    except Exception as error:
        error.passed_checks = checks
        raise


if __name__ == "__main__":
    if sys.argv[1] == "serve":
        server = http.server.ThreadingHTTPServer(("0.0.0.0", 8000), Handler)
        server.idle_stop = threading.Event()
        try:
            server.serve_forever()
        finally:
            server.idle_stop.set()
            server.server_close()
        # Keep the owned container available for the client after backend failure.
        threading.Event().wait()
    elif sys.argv[1] == "probe":
        try:
            print(json.dumps(probe(), indent=2))
        except Exception as error:
            print(json.dumps({"failure": {"check": getattr(error, "check", "unexpected-probe-failure"),
                                          "detail": getattr(error, "detail", str(error)),
                                          "type": type(error).__name__,
                                          "passed_checks": getattr(error, "passed_checks", [])}}))
            sys.exit(1)
