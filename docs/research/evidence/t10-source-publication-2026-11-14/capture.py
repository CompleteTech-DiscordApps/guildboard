"""Capture real loopback source-publication and return-handoff regressions."""
import argparse
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time

BEFORE = "c9b0e0f61ba290ec1da0d1d7d0e75990d2253d2b"
SOURCES = ("scripts/research/t10-nginx-probe.py", "scripts/research/t10-proxy-fixture.py",
           "scripts/research/t10-capture-sources.py", "scripts/research/t10-report-publication.py",
           "tests/research/t10-test-nginx-probe.py", "docs/research/t10-nginx-probe.conf")


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def git(repository, *args):
    return subprocess.check_output(["git", "-C", str(repository), *args])


def sha(data):
    return hashlib.sha256(data).hexdigest()


def capture_case(repository, fixed, optimized=False, unbuffered=False,
                 number=signal.SIGTERM, mode="draining", handoff=False, short=False):
    connected, stop = threading.Event(), threading.Event()
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            slow = self.path == "/slow"
            self.send_response(200)
            self.send_header("Content-Length", "1000000" if slow else "2")
            self.end_headers()
            try:
                if slow:
                    connected.set()
                    while not stop.wait(.02):
                        self.wfile.write(b"x")
                        self.wfile.flush()
                else:
                    self.wfile.write(b"ok")
            except OSError:
                pass
    process, worker = None, None
    with tempfile.TemporaryDirectory(prefix="t10-source-publication-capture-") as scratch, \
         http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.05))
        thread.start()
        root = Path(scratch)
        destination = root / "sources.json"
        temporary = root / "temporary"
        temporary.mkdir()
        url = "http://127.0.0.1:" + str(server.server_port)
        program = ("import importlib.util,sys,os; "
                   "s=importlib.util.spec_from_file_location('capture',sys.argv[1]); "
                   "m=importlib.util.module_from_spec(s);s.loader.exec_module(m); "
                   "m.SOURCES=[('healthy',sys.argv[2]+" + ("'/healthy'" if short else "'/'+'x'*10000") + ")]" +
                   ("+[('slow',sys.argv[2]+'/slow')]; " if number is not None and not handoff else "; "))
        if handoff:
            program += ("\ndef trace_return(frame,event,arg):\n"
                        " if frame.f_code is m.capture.__code__ and event=='return' and isinstance(arg,dict):\n"
                        "  sys.settrace(None)\n  os.kill(os.getpid()," + str(int(number)) + ")\n"
                        " return trace_return\nsys.settrace(trace_return)\n")
        program += "raise SystemExit(m.main(['--output',sys.argv[3]]))"
        command = [sys.executable, *(["-O"] if optimized else []), *(["-u"] if unbuffered else []),
                   "-c", program, str(repository / SOURCES[2]), url, str(destination)]
        rescued, prefix = False, b""
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, pipesize=4096,
                                       env={**os.environ, "TMPDIR": str(temporary), "PYTHONDONTWRITEBYTECODE": "1",
                                            "PYTHONUNBUFFERED": "1" if unbuffered else ""})
            if number is not None and not handoff:
                check(connected.wait(8), "slow worker did not fetch after healthy row")
                for child in Path(f"/proc/{process.pid}/task/{process.pid}/children").read_text().split():
                    try:
                        cmdline = Path(f"/proc/{child}/cmdline").read_bytes()
                    except FileNotFoundError:
                        continue
                    if b"--fetch-worker" in cmdline and url.encode() in cmdline:
                        worker = int(child)
                check(worker is not None, "owned slow worker not captured")
            if mode == "closed":
                process.stdout.close()
                process.stdout = None
            started = time.monotonic()
            if number is not None and not handoff:
                process.send_signal(number)
            before_rescue = None
            if mode == "undrained":
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    check(not fixed, "fixed collector blocked on undrained output")
                    rescued = True
                    process.kill()
                before_rescue = destination.read_bytes() if destination.exists() else None
            stdout, stderr = process.communicate(timeout=8)
            stdout = stdout or b""
            complete = destination.read_bytes() if destination.exists() else None
            report = json.loads(complete) if complete is not None else None
            reaped = worker is None or not Path(f"/proc/{worker}").exists()
            check(reaped, "owned fetch worker not reaped")
            if fixed:
                expected = 128 + number if number is not None else 0
                check(process.returncode == expected, "incorrect fixed exit status")
                check(report is not None and report["sources"][0]["bytes"] == 2, "healthy row not retained")
                check(b"Traceback" not in stderr, "uncaught source publication error")
                if number is not None:
                    check(report["failure"]["signal"] == signal.Signals(number).name, "first signal was not retained")
                    check(complete.startswith(stdout), "second JSON follows partial first JSON")
                    if not handoff:
                        check(report["sources"][1]["cancelled"], "cancelled source row lost")
                    else:
                        check(len(report["sources"]) == 1, "completed handoff row lost")
                elif mode == "draining":
                    check(json.loads(stdout) == {"observed": 1, "http_200": 1, "failures": []}, "ordinary summary changed")
                if mode == "undrained":
                    check(before_rescue is not None, "report was not written before draining")
            elif handoff:
                check(process.returncode == 128 + number and report is not None and report["sources"] == [],
                      "old return-handoff loss not reproduced")
            elif mode == "closed":
                check(process.returncode != 128 + number, "old closed-pipe status bug not reproduced")
            elif mode == "undrained":
                check(rescued and complete is None, "old backpressure loss not reproduced")
            else:
                check(process.returncode == 128 + number and report is not None, "old draining control failed")
            def clean(text):
                return text.replace(str(repository), "<REPOSITORY>").replace(scratch, "<CASE>")
            return {"fixed": fixed, "optimized": optimized, "unbuffered": unbuffered,
                    "signal": signal.Signals(number).name if number else None, "stdout_mode": mode,
                    "return_handoff_injection": handoff, "short_metadata": short,
                    "exit_code": process.returncode, "elapsed_seconds": time.monotonic() - started,
                    "owned_parent_rescue_required": rescued, "worker_pid_observed": worker is not None,
                    "worker_reaped": reaped if worker is not None else None,
                    "stdout_original_sha256": sha(stdout), "stderr_original_sha256": sha(stderr),
                    "report_original_sha256": sha(complete) if complete is not None else None,
                    "stdout": clean(stdout.decode(errors="replace")), "stderr": clean(stderr.decode(errors="replace")),
                    "requested_report": clean(complete.decode()) if complete is not None else None,
                    "complete_file_before_drain": (before_rescue is not None) if mode == "undrained" else None}
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            if worker is not None and Path(f"/proc/{worker}").exists():
                try:
                    cmdline = Path(f"/proc/{worker}/cmdline").read_bytes()
                    if b"--fetch-worker" in cmdline and url.encode() in cmdline:
                        os.kill(worker, signal.SIGKILL)
                except FileNotFoundError:
                    pass
            stop.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
            check(not thread.is_alive(), "owned loopback server did not stop")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--before-repository", required=True, type=Path)
    parser.add_argument("--tested-revision", required=True)
    parser.add_argument("--nginx-binary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    repository, before = args.repository.resolve(), args.before_repository.resolve()
    check(git(before, "rev-parse", "HEAD").decode().strip() == BEFORE, "wrong before revision")
    bindings, old_bindings = {}, {}
    for path in SOURCES:
        expected = git(repository, "show", args.tested_revision + ":" + path)
        check((repository / path).read_bytes() == expected, "tested source mismatch: " + path)
        bindings[path] = sha(expected)
        if path != "scripts/research/t10-report-publication.py":
            old = git(before, "show", BEFORE + ":" + path)
            check((before / path).read_bytes() == old, "before source mismatch: " + path)
            old_bindings[path] = sha(old)
    observations = []
    for optimized in (False, True):
        for number in (signal.SIGTERM, signal.SIGINT):
            for mode in ("draining", "closed", "undrained"):
                observations.append(capture_case(before, False, optimized, number=number, mode=mode))
            observations.append(capture_case(before, False, optimized, number=number, mode="closed", short=True))
            observations.append(capture_case(before, False, optimized, number=number, handoff=True))
            for mode in ("draining", "closed", "undrained"):
                observations.append(capture_case(repository, True, optimized, number=number, mode=mode))
            observations.append(capture_case(repository, True, optimized, number=number, mode="closed", short=True))
            observations.append(capture_case(repository, True, optimized, number=number, handoff=True))
    observations.append(capture_case(repository, True, number=None))
    specification = importlib.util.spec_from_file_location("source_publication_probe", repository / SOURCES[0])
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    with module.cancellation_signals():
        network = [module.run_local(args.nginx_binary.resolve(), control)
                   for control in (None, *module.HANDSHAKE_REJECTIONS, "publish-private-assets", "long-read-timeout")]
    check(len(network[0]["result"]["checks"]) == 12 and all(row["passed"] for row in network[0]["result"]["checks"]),
          "actual Nginx baseline failed")
    check(all(row["negative_control"]["detected"] for row in network[1:]), "unsafe control escaped detection")
    report = {"tested_revision": args.tested_revision,
              "checkout_revision": git(repository, "rev-parse", "HEAD").decode().strip(),
              "before_revision": BEFORE, "source_sha256": bindings, "before_source_sha256": old_bindings,
              "python": sys.version, "observations": observations, "network": network,
              "scope": "Actual healthy/slow loopback fetches and owned worker processes; deterministic trace-at-return handoff injection. Separate actual local Nginx. No GoDaddy, Discord, public TLS/DNS, actual Docker or SQL acceptance."}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("20 old cases and21 fixed cases verified; six current source bindings include shared helper; actual Nginx12 baseline/six controls verified")


if __name__ == "__main__":
    main()
