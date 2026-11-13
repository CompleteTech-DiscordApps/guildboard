"""Synthetic backend/client for the isolated real-Nginx probe; no application code."""
import base64
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
            key = self.headers.get("Sec-WebSocket-Key", "")
            if self.headers.get("Upgrade", "").lower() != "websocket" or not key:
                self.send_error(426)
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
                headers[name.lower()] = value.strip()
            assert b"101" in status, status
            assert headers["sec-websocket-accept"] == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=", headers
            return stream.read(7)


def idle_close():
    started = time.monotonic()
    try:
        payload = websocket("/idle", timeout=IDLE_CLOSE_DEADLINE)
    except TimeoutError as error:
        raise AssertionError("idle-close-within-bounded-window: client deadline expired before proxy EOF") from error
    elapsed = time.monotonic() - started
    assert payload == b"", "idle-upstream-closed"
    assert 1.5 <= elapsed < IDLE_CLOSE_DEADLINE, "idle-close-within-bounded-window"
    return elapsed


def probe():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
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
        print(json.dumps(probe(), indent=2))
