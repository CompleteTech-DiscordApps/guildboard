"""Reproduce T10 report publication against two explicit read-only worktrees."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time

BEFORE = "aae49862fc2c0c4cba63f4742cb8d02b4481cf2e"
SOURCES = ("scripts/research/t10-nginx-probe.py", "scripts/research/t10-proxy-fixture.py",
           "scripts/research/t10-capture-sources.py", "tests/research/t10-test-nginx-probe.py",
           "docs/research/t10-nginx-probe.conf")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(repository, *args):
    return subprocess.check_output(["git", "-C", str(repository), *args])


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def case(repository, fixed, optimized=False, number=None, requested=False, drain=True, closed=False):
    with tempfile.TemporaryDirectory(prefix="t10-publication-capture-") as scratch:
        root = Path(scratch)
        temporary = root / "temporary"
        temporary.mkdir()
        owned = root / "owned-startup-failure"
        owned.write_text("#!" + sys.executable + "\nimport sys\n"
                         "if '-V' in sys.argv or '-t' in sys.argv: sys.exit(0)\n"
                         "print('x'*70000,file=sys.stderr)\nsys.exit(7)\n")
        owned.chmod(0o700)
        destination = root / "requested.json"
        command = [sys.executable, *(["-O"] if optimized else []),
                   str(repository / SOURCES[0]), "--nginx-binary", str(owned)]
        if requested:
            command += ["--output", str(destination)]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   pipesize=4096, env={**os.environ, "TMPDIR": str(temporary),
                                                      "PYTHONDONTWRITEBYTECODE": "1"})
        prefix, started = b"", time.monotonic()
        try:
            if closed:
                process.stdout.close()
                process.stdout = None
            elif number is not None or not drain:
                check(bool(select.select([process.stdout], [], [], 8)[0]), "report never reached stdout")
                prefix = os.read(process.stdout.fileno(), 512)
                check(bool(prefix), "empty report prefix")
            if number is not None:
                process.send_signal(number)
            if not drain:
                process.wait(timeout=6)
            stdout, stderr = process.communicate(timeout=8)
            stdout = prefix + (stdout or b"")
            try:
                json.loads(stdout)
                valid_stdout = True
            except (ValueError, UnicodeError):
                valid_stdout = False
            copies = ([destination] if destination.exists() else
                      list(temporary.glob("guildboard-t10-report-*.json")))
            complete = copies[0].read_bytes() if len(copies) == 1 else None
            if not fixed:
                check(process.returncode == 1 and not valid_stdout and b"ExperimentCancelled" in stderr,
                      "old publication failure did not reproduce")
            elif number is None and drain and not closed:
                check(process.returncode == 1 and valid_stdout, "ordinary failure control was not complete")
                if requested:
                    check(complete == stdout, "requested control copy differs")
            else:
                expected = 128 + number if number is not None else 1
                check(process.returncode == expected, "incorrect publication exit status")
                check(complete is not None, "missing complete recovery copy")
                report = json.loads(complete)
                check(report["failure"]["type"] == "RuntimeError" and all(report["cleanup"].values()),
                      "lost original failure or cleanup evidence")
                check(complete.startswith(stdout), "a second JSON object followed partial output")
                check(str(copies[0]).encode() in stderr, "recovery path not reported")
                check(b"Traceback" not in stderr, "uncaught publication exception")
            check(not any(p.is_dir() for p in temporary.iterdir()), "owned temporary process directory remains")
            def clean(value):
                return value.replace(str(repository), "<REPOSITORY>").replace(scratch, "<CASE>")
            return {"fixed": fixed, "optimized": optimized, "signal": signal.Signals(number).name if number else None,
                    "requested_output": requested, "receiver_drains": drain, "closed_stdout": closed,
                    "exit_code": process.returncode, "elapsed_seconds": time.monotonic() - started,
                    "stdout_valid_json": valid_stdout, "stdout_bytes": len(stdout),
                    "stdout_original_sha256": sha(stdout), "stderr_original_sha256": sha(stderr),
                    "stdout": clean(stdout.decode(errors="replace")), "stderr": clean(stderr.decode(errors="replace")),
                    "complete_copy": clean(complete.decode()) if complete is not None else None,
                    "complete_copy_original_sha256": sha(complete) if complete is not None else None,
                    "owned_temporary_directories_left": []}
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--before-repository", required=True, type=Path)
    parser.add_argument("--tested-revision", required=True)
    parser.add_argument("--nginx-binary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    repository, before = args.repository.resolve(), args.before_repository.resolve()
    check(git(before, "rev-parse", "HEAD").decode().strip() == BEFORE, "before worktree is not exact old revision")
    bindings = {}
    for path in SOURCES:
        expected = git(repository, "show", args.tested_revision + ":" + path)
        actual = (repository / path).read_bytes()
        check(expected == actual, "current source does not match tested revision: " + path)
        bindings[path] = sha(actual)
    old_bytes = git(before, "show", BEFORE + ":" + SOURCES[0])
    check(old_bytes == (before / SOURCES[0]).read_bytes(), "before executable differs from exact Git bytes")
    observations = [case(before, False, optimized, number)
                    for optimized in (False, True) for number in (signal.SIGTERM, signal.SIGINT)]
    observations += [case(repository, True, optimized, number)
                     for optimized in (False, True) for number in (signal.SIGTERM, signal.SIGINT)]
    observations += [case(repository, True, number=number, requested=True)
                     for number in (signal.SIGTERM, signal.SIGINT)]
    observations += [case(repository, True, number=signal.SIGTERM, drain=False),
                     case(repository, True, drain=False), case(repository, True, closed=True),
                     case(repository, True, requested=True)]
    specification = importlib.util.spec_from_file_location("publication_probe", repository / SOURCES[0])
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    network = [module.run_local(args.nginx_binary.resolve(), control)
               for control in (None, *module.HANDSHAKE_REJECTIONS, "publish-private-assets", "long-read-timeout")]
    check(len(network[0]["result"]["checks"]) == 12 and all(x["passed"] for x in network[0]["result"]["checks"]),
          "baseline did not pass all 12 checks")
    check(all(x["negative_control"]["detected"] for x in network[1:]), "unsafe control not detected")
    report = {"tested_revision": args.tested_revision,
              "checkout_revision": git(repository, "rev-parse", "HEAD").decode().strip(),
              "before_revision": BEFORE, "before_executable_sha256": sha(old_bytes),
              "source_sha256": bindings, "python": sys.version, "publication_observations": observations,
              "network": network,
              "scope": "Actual CLI with an owned synthetic startup-failure executable; separate real local Nginx baseline and six controls. No Docker, GoDaddy, public TLS/DNS or Discord acceptance."}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("Four old publication failures reproduced; ten fixed publication cases verified; Nginx 12 baseline and six controls verified")


if __name__ == "__main__":
    main()
