"""Bounded public primary-document GET observations, no installation or credentials.

Output is metadata only. Hashes identify observed bytes; they are not an archive
or evidence of running the documented product. Failures are retained and exit 1.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import http.client
import hashlib
import json
import subprocess
import signal
import threading
import time
from pathlib import Path
import sys
import urllib.error
import urllib.request

SOURCES = (
    ("F1", "https://www.foundationdb.org/files/fdb-paper.pdf", "SIGMOD 2021 paper, not a runtime evaluation"),
    ("P1", "https://playwright.dev/docs/test-parallel", "rolling stable documentation, binary not evaluated"),
    ("P2", "https://playwright.dev/docs/accessibility-testing", "rolling stable documentation, binary not evaluated"),
    ("K1", "https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/", "rolling latest documentation, observed v2.3.x navigation; binary not evaluated"),
    ("W1", "https://www.w3.org/TR/2024/REC-WCAG22-20241212/", "WCAG 2.2 Recommendation 2024-12-12"),
    ("D1", "https://docs.discord.com/developers/activities/development-guides/local-development", "rolling official Discord documentation"),
    ("D2", "https://docs.discord.com/developers/activities/development-guides/mobile", "rolling official Discord documentation"),
    ("D3", "https://docs.discord.com/developers/activities/development-guides/production-readiness", "rolling official Discord documentation"),
    ("N1", "https://nginx.org/en/docs/http/websocket.html", "rolling official Nginx documentation, host version unverified"),
    ("G1", "https://www.godaddy.com/help/back-up-my-vps-hosting-27819", "rolling VPS Hosting provider help, plan and backup behavior unverified"),
)
MAX_BYTES = 2 * 1024 * 1024
DISCORD_SOURCE_REVISION = "6128d99116af8357db1e4966ebd7f099817a0e04"


ATTEMPT_SECONDS = 15
COLLECTION_SECONDS = 60
CLEANUP_SECONDS = 1
_fetch_context = threading.local()


class CaptureCancelled(OSError):
    """Catchable cancellation is a failed observation, never a content hash."""


class Cancellation:
    def __init__(self):
        self.event = threading.Event()
        self.signal = None

    def request(self, signum, frame):
        if self.signal is None:
            self.signal = signum
            self.event.set()


class FetchFailure(OSError):
    def __init__(self, error):
        super().__init__(error["detail"])
        self.error_type = error["type"]
        self.http_status = error.get("http_status")


def fetch(url, timeout):
    """A disposable process bounds DNS, redirects and trickling response bodies."""
    cancellation = getattr(_fetch_context, "cancellation", None)
    def check_cancelled():
        if cancellation is not None and cancellation.event.is_set():
            raise CaptureCancelled("collection cancelled")
    check_cancelled()
    if timeout <= 0:
        raise TimeoutError("collection elapsed-time deadline exceeded")
    deadline = time.monotonic() + timeout
    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                "--fetch-worker", url], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    try:
        while True:
            check_cancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("response elapsed-time deadline exceeded")
            try:
                stdout, stderr = process.communicate(timeout=min(0.05, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, process.args,
                                                output=stdout, stderr=stderr)
    finally:
        # Only the disposable direct child is owned. Never signal a shared group.
        if process.poll() is None:
            process.kill()
        try:
            process.communicate(timeout=CLEANUP_SECONDS)
        finally:
            process.stdout.close()
            process.stderr.close()
    envelope = json.loads(stdout)
    if "error" in envelope:
        raise FetchFailure(envelope["error"])
    return envelope["result"]


def fetch_worker(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            payload = response.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES:
                raise ValueError("response budget exceeded")
            declared = response.headers.get("Content-Length")
            if declared is not None and len(payload) != int(declared):
                raise ValueError("incomplete response body")
            result = {"http_status": response.status, "final_url": response.url,
                      "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        envelope = {"result": result}
    except (OSError, http.client.HTTPException, ValueError) as error:
        detail = {"type": type(error).__name__, "detail": str(error)}
        if isinstance(error, urllib.error.HTTPError):
            detail["http_status"] = error.code
        envelope = {"error": detail}
    print(json.dumps(envelope))


def capture(source, deadline=None):
    if deadline is None:
        deadline = time.monotonic() + COLLECTION_SECONDS
    source_id, url, version = source
    observation = {"id": source_id, "url": url, "document_version": version,
                   "observed_at_utc": datetime.now(timezone.utc).isoformat()}
    urls = [url]
    if source_id.startswith("D"):
        path = url.split("docs.discord.com/", 1)[1]
        urls.append("https://raw.githubusercontent.com/discord/discord-api-docs/" +
                    DISCORD_SOURCE_REVISION + "/" + path + ".mdx")
        observation["fallback_source_revision"] = DISCORD_SOURCE_REVISION
    attempts = []
    for target in urls:
        attempt = {"url": target, "observed_at_utc": datetime.now(timezone.utc).isoformat()}
        try:
            result = fetch(target, min(ATTEMPT_SECONDS, deadline - time.monotonic()))
            attempt.update(status="fetched", **result)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            attempt.update(status="fetch-failed", error_type=getattr(error, "error_type", type(error).__name__))
            if getattr(error, "http_status", None) is not None:
                attempt["http_status"] = error.http_status
        attempts.append(attempt)
        if attempt["status"] == "fetched":
            break
    observation["attempts"] = attempts
    observation["status"] = attempts[-1]["status"]
    return observation


def capture_all(cancellation=None):
    cancellation = cancellation if cancellation is not None else Cancellation()
    previous = {}
    # Python permits signal registration only from the main thread. Callers in
    # other threads can supply Cancellation and request it themselves.
    if threading.current_thread() is threading.main_thread():
        for number in (signal.SIGTERM, signal.SIGINT):
            previous[number] = signal.signal(number, cancellation.request)
    def collect(source):
        _fetch_context.cancellation = cancellation
        try:
            return capture(source, deadline)
        finally:
            del _fetch_context.cancellation
    try:
        deadline = time.monotonic() + COLLECTION_SECONDS
        with ThreadPoolExecutor(max_workers=4) as executor:
            return list(executor.map(collect, SOURCES))
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def main():
    cancellation = Cancellation()
    sources = capture_all(cancellation)
    output = {"kind": "public-document-observations-not-platform-testing",
              "sources": sources}
    if cancellation.signal is not None:
        output["cancelled_signal"] = cancellation.signal
    print(json.dumps(output, indent=2, sort_keys=True))
    return (128 + cancellation.signal if cancellation.signal is not None else
            int(any(source["status"] != "fetched" for source in sources)))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fetch-worker":
        fetch_worker(sys.argv[2])
        sys.exit(0)
    sys.exit(main())
