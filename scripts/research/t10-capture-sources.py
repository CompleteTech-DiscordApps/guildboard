"""Record public primary-response metadata, not a platform verification result."""
import argparse
import contextlib
import signal
from datetime import datetime, timezone
import http.client
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
import urllib.request
import urllib.error

SOURCES = [
    ("godaddy-vps", "https://www.godaddy.com/hosting/vps-hosting"),
    ("godaddy-ssh", "https://www.godaddy.com/en-uk/help/connect-to-my-server-with-ssh-secure-shell-4943"),
    ("godaddy-admin", "https://www.godaddy.com/en/help/enable-root-or-admin-access-to-my-vps-hosting-24737?inapp=true"),
    ("godaddy-unsupported-os", "https://www.godaddy.com/en-ph/help/unsupported-operating-systems-for-vps-hosting-41852"),
    ("godaddy-ports", "https://www.godaddy.com/en-ph/help/common-server-ports-19608"),
    ("godaddy-recovery", "https://www.godaddy.com/en/help/use-the-recovery-console-for-vps-hosting-32064"),
    ("nginx-websocket", "https://nginx.org/en/docs/http/websocket.html"),
    ("nginx-proxy", "https://nginx.org/en/docs/http/ngx_http_proxy_module.html"),
    ("discord-networking", "https://docs.discord.com/developers/activities/development-guides/networking"),
    ("discord-mappings", "https://docs.discord.com/developers/activities/development-guides/local-development"),
    ("docker-firewall", "https://docs.docker.com/engine/network/packet-filtering-firewalls/"),
    ("docker-ubuntu", "https://docs.docker.com/engine/install/ubuntu/"),
    ("node-releases", "https://nodejs.org/en/about/previous-releases"),
    ("mysql-backup", "https://dev.mysql.com/doc/refman/8.4/en/backup-policy.html"),
]


MAX_BYTES = 4_000_000
ATTEMPT_SECONDS = 20
COLLECTION_SECONDS = 90


class ExperimentCancelled(RuntimeError):
    def __init__(self, signum):
        self.signum = signum
        self.signal_name = signal.Signals(signum).name
        self.exit_code = 128 + signum
        super().__init__("cancelled by " + self.signal_name)


_cancellation_state = None


@contextlib.contextmanager
def cancellation_signals():
    """Deliver the first catchable signal outside owned worker cleanup."""
    global _cancellation_state
    previous, previous_state = {}, _cancellation_state
    state = {"signal": None, "delivered": False, "cleanup_depth": 0}
    _cancellation_state = state
    def cancel(signum, _frame):
        if state["signal"] is None:
            state["signal"] = signum
        if not state["delivered"] and not state["cleanup_depth"]:
            state["delivered"] = True
            raise ExperimentCancelled(state["signal"])
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, cancel)
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        _cancellation_state = previous_state


@contextlib.contextmanager
def owned_cleanup():
    state = _cancellation_state
    if state is not None:
        state["cleanup_depth"] += 1
    try:
        yield
    finally:
        if state is not None:
            state["cleanup_depth"] -= 1
            if not state["cleanup_depth"] and state["signal"] is not None and not state["delivered"]:
                state["delivered"] = True
                raise ExperimentCancelled(state["signal"])


class FetchFailure(OSError):
    def __init__(self, error):
        super().__init__(error["detail"])
        self.error_type = error["type"]
        self.http_status = error.get("http_status")


def fetch(url, timeout):
    """A disposable process bounds DNS, redirects and trickling response bodies."""
    if timeout <= 0:
        raise TimeoutError("collection elapsed-time deadline exceeded")
    process = None
    try:
        # Record the handle before a pending signal can unwind this try.
        with owned_cleanup():
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                       "--fetch-worker", url], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(timeout=timeout)
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, process.args, stdout, stderr)
    except subprocess.TimeoutExpired as error:
        raise TimeoutError("response elapsed-time deadline exceeded") from error
    finally:
        # Protect kill/reap/pipe close even when the first signal arrives here.
        with owned_cleanup():
            if process is not None:
                try:
                    if process.poll() is None:
                        process.kill()
                finally:
                    try:
                        process.wait()
                    finally:
                        process.stdout.close()
                        process.stderr.close()
    envelope = json.loads(stdout)
    if "error" in envelope:
        raise FetchFailure(envelope["error"])
    return envelope["result"]


def fetch_worker(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Guildboard-T10-Research/1.0"}), timeout=20) as response:
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


def capture():
    observations = []
    row = None
    deadline = time.monotonic() + COLLECTION_SECONDS
    try:
        for name, url in SOURCES:
            row = {"id": name, "url": url, "observed_at": datetime.now(timezone.utc).isoformat()}
            try:
                result = fetch(url, min(ATTEMPT_SECONDS, deadline - time.monotonic()))
                row.update(result)
                row["status"] = row.pop("http_status")
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                row["error"] = str(error)
            observations.append(row)
    except ExperimentCancelled as error:
        if row is not None and (not observations or observations[-1] is not row):
            row.update(error=str(error), cancelled=True)
            observations.append(row)
        error.report = {"kind": "public-response-observation-not-account-or-content-attestation", "sources": observations}
        raise
    return {"kind": "public-response-observation-not-account-or-content-attestation", "sources": observations}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = {"kind": "public-response-observation-not-account-or-content-attestation", "sources": []}
    with cancellation_signals():
        try:
            result = capture()
            try:
                args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
            except (OSError, ValueError) as error:
                print(json.dumps(result, indent=2))
                print("Cannot write source report: " + str(error), file=sys.stderr)
                return 1
            print(json.dumps({"observed": len(result["sources"]), "http_200": sum(row.get("status") == 200 for row in result["sources"]), "failures": [row["id"] for row in result["sources"] if "error" in row]}))
            return 0
        except ExperimentCancelled as error:
            result = getattr(error, "report", result)
            result["failure"] = {"type": type(error).__name__, "detail": str(error), "signal": error.signal_name}
            print(json.dumps(result, indent=2))
            try:
                args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
            except (OSError, ValueError) as output_error:
                print("Cannot write source report: " + str(output_error), file=sys.stderr)
            return error.exit_code


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fetch-worker":
        fetch_worker(sys.argv[2])
        sys.exit(0)
    raise SystemExit(main())
