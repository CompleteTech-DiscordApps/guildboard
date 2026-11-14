"""Record public primary-response metadata, not a platform verification result."""
import argparse
import contextlib
import importlib.util
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

_publication_spec = importlib.util.spec_from_file_location(
    "t10_report_publication", Path(__file__).with_name("t10-report-publication.py"))
_publication = importlib.util.module_from_spec(_publication_spec)
_publication_spec.loader.exec_module(_publication)
report_notice = _publication.report_notice
report_copy = _publication.report_copy
write_report_stdout = _publication.write_report_stdout
discard_stdout_buffer = _publication.discard_stdout_buffer
REPORT_STDOUT_SECONDS = _publication.REPORT_STDOUT_SECONDS



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
    state = {"signal": None, "delivered": False, "cleanup_depth": 0, "publication_depth": 0, "publication_started": False}
    _cancellation_state = state
    def cancel(signum, _frame):
        if state["signal"] is None:
            state["signal"] = signum
        # Do not asynchronously unwind owned-resource lifecycles or an emitter
        # before its staging guard is active. Their safe checkpoints deliver it.
        frame = _frame if _frame is not None else sys._getframe(1)
        protected = False
        while frame is not None:
            if frame.f_globals is globals() and (frame.f_code.co_name in ('fetch', 'capture', 'owned_cleanup')
                    or (frame.f_code.co_name in ("emit_report", "emit_source_report")
                        and not state["publication_started"])):
                protected = True
                break
            frame = frame.f_back
        if not protected and not state["delivered"] and not state["cleanup_depth"] and not state["publication_depth"]:
            state["delivered"] = True
            raise ExperimentCancelled(state["signal"])
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, cancel)
        yield state
    finally:
        state["delivered"] = True
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
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(process.args, timeout)
            try:
                stdout, stderr = process.communicate(timeout=min(remaining, 0.1))
                break
            except subprocess.TimeoutExpired:
                state = _cancellation_state
                if state is not None and state["signal"] is not None and not state["delivered"]:
                    state["delivered"] = True
                    raise ExperimentCancelled(state["signal"])
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
    report = {"kind": "public-response-observation-not-account-or-content-attestation", "sources": []}
    if _cancellation_state is not None:
        _cancellation_state["report"] = report
    observations = report["sources"]
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
        error.report = report
        raise
    return report


def emit_source_report(result, output_path):
    state = _cancellation_state
    snapshot, automatic, requested_ok = None, False, True
    try:
        if state is not None:
            state["publication_depth"] += 1
        try:
            complete = json.dumps(result, indent=2) + "\n"
            try:
                snapshot, automatic, requested_ok = report_copy(
                    complete, output_path, label="source", prefix="guildboard-t10-source-report-")
            except (OSError, ValueError) as error:
                requested_ok = False
                report_notice("Cannot stage source report recovery copy: " + str(error))
            if "failure" in result or not requested_ok:
                output = complete
            else:
                output = json.dumps({"observed": len(result["sources"]),
                                     "http_200": sum(row.get("status") == 200 for row in result["sources"]),
                                     "failures": [row["id"] for row in result["sources"] if "error" in row]}) + "\n"
            if state is not None and state["signal"] is not None and not state["delivered"]:
                # Preserve the frozen complete snapshot; final status records a
                # late signal without appending a replacement JSON to stdout.
                state["delivered"] = True
        finally:
            if state is not None:
                state["publication_depth"] -= 1
        if state is not None:
            state["publication_started"] = True
        write_report_stdout(output)
    except (ExperimentCancelled, OSError, ValueError) as error:
        discard_stdout_buffer()
        if snapshot is not None:
            report_notice("Source report recovery: " + json.dumps({"path": str(snapshot), "reason": str(error)}))
        else:
            report_notice("Source report unavailable after publication failure: " + str(error))
        return False
    finally:
        if state is not None:
            state["delivered"] = True
    if automatic and snapshot is not None:
        try:
            snapshot.unlink()
        except OSError as error:
            report_notice("Cannot remove completed source recovery copy: " + str(error))
            return False
    return requested_ok


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = {"kind": "public-response-observation-not-account-or-content-attestation", "sources": []}
    exit_code = 0
    with cancellation_signals() as state:
        try:
            try:
                result = capture()
                if state["signal"] is not None and not state["delivered"]:
                    state["delivered"] = True
                    raise ExperimentCancelled(state["signal"])
            except ExperimentCancelled as error:
                result = getattr(error, "report", state.get("report", result))
                result["failure"] = {"type": type(error).__name__, "detail": str(error), "signal": error.signal_name}
                exit_code = 1
            if not emit_source_report(result, args.output):
                exit_code = 1
        except ExperimentCancelled as error:
            result = getattr(error, "report", state.get("report", result))
            result["failure"] = {"type": type(error).__name__, "detail": str(error), "signal": error.signal_name}
            if not state["publication_started"]:
                emit_source_report(result, args.output)
            exit_code = 1
        finally:
            state["delivered"] = True
    return 128 + state["signal"] if state["signal"] is not None else exit_code


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fetch-worker":
        fetch_worker(sys.argv[2])
        sys.exit(0)
    raise SystemExit(main())
