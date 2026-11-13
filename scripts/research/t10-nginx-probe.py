"""Run an owned, cached-image-only Nginx network experiment. Python stdlib only."""
import argparse
import hashlib
import importlib.util
import http.server
import socket
import tempfile
import threading
import json
import os
import signal
import re
from pathlib import Path
import platform
import subprocess
import time
import uuid
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
NGINX = "sha256:62ff2089abf5a9ed33bd232895bef5e22f7bb4b200675cec49a5ebc48e3d4ac8"
PYTHON = "sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70"


def docker(*args, input_text=None):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=30, input=input_text)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
    return result


class DockerCleanupError(RuntimeError):
    def __init__(self, failures, report):
        self.failures = failures
        self.report = report
        super().__init__("Owned Docker cleanup failed: " + "; ".join(failures))


def inspect_container(reference):
    """Only an explicit missing-container response establishes absence."""
    try:
        output = docker("container", "inspect", reference).stdout
    except subprocess.CalledProcessError as error:
        missing = r"(?:Error:|Error response from daemon:) No such (?:object|container): " + re.escape(reference)
        if error.returncode == 1 and re.fullmatch(missing, (error.stderr or "").strip()):
            return None
        raise
    data = json.loads(output)
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise RuntimeError("Invalid container inspection: " + reference)
    return data[0]


def create_owned_container(intended, name, *args):
    # A collision is not ours even if the caller reuses a token. Never delete it.
    if inspect_container(name) is not None:
        raise RuntimeError("Container name already exists: " + name)
    # The daemon may create the resource before the CLI times out or disconnects.
    intended.append(name)
    docker("create", "--name", name, *args)


def cleanup_owned_containers(intended, token, report):
    cleanup, failures = [], []
    for name in reversed(intended):
        try:
            info = inspect_container(name)
            if info is None:
                cleanup.append({"kind": "container", "name": name, "absence_verified": True})
                continue
            labels = info.get("Config", {}).get("Labels", {})
            identifier = info.get("Id")
            if (not isinstance(labels, dict) or labels.get("guildboard.t10.probe") != token
                    or info.get("Name") != "/" + name
                    or not isinstance(identifier, str) or re.fullmatch(r"[0-9a-f]{64}", identifier) is None):
                raise RuntimeError("Ownership/identity mismatch; refusing cleanup: " + name)
            removal_error = None
            try:
                # Bind removal to the inspected immutable ID, not a reusable name.
                docker("container", "rm", "--force", identifier)
            except (subprocess.SubprocessError, OSError) as error:
                removal_error = error
            if inspect_container(identifier) is not None:
                raise RuntimeError("Cleanup absence not verified: " + name) from removal_error
            cleanup.append({"kind": "container", "name": name, "id": identifier, "absence_verified": True})
        except Exception as error:
            # Failure to inspect/remove one resource must not strand the others.
            failures.append(name + ": " + type(error).__name__ + ": " + str(error))
    report["cleanup"] = cleanup
    if failures:
        report["cleanup_failures"] = failures
        raise DockerCleanupError(failures, report)


def run(control=None):
    token = "gb-t10-" + uuid.uuid4().hex[:12]
    backend, proxy = token + "-backend", token + "-proxy"
    label = "guildboard.t10.probe=" + token
    intended = []
    report = {"observed_at": datetime.now(timezone.utc).isoformat(), "host": platform.platform(),
              "host_python": platform.python_version(), "images": {"nginx": NGINX, "python": PYTHON},
              "resource_scope": {"network": "network=none backend; nginx shares its owned network namespace", "published_ports": [], "mounts": [],
                                 "per_container": "0.5 CPU / 128MiB / 64 PIDs / nonroot / read-only / cap-drop ALL"}}
    for image in (NGINX, PYTHON):
        docker("image", "inspect", image)  # No pulls or installs; fail if absent.
    try:
        common = ["--pull=never", "--label", label, "--cpus", "0.5", "--memory", "128m", "--pids-limit", "64", "--user", "65534:65534", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m,mode=1777"]
        create_owned_container(intended, backend, "--network", "none", *common, "--entrypoint", "python", PYTHON, "-c", "import time; time.sleep(3600)")
        docker("start", backend)
        docker("exec", "-i", backend, "python", "-c", "import sys; from pathlib import Path; Path('/tmp/probe.py').write_text(sys.stdin.read())", input_text=(ROOT / "scripts/research/t10-proxy-fixture.py").read_text())
        docker("exec", "-d", backend, "python", "/tmp/probe.py", "serve")
        create_owned_container(intended, proxy, "--network", "container:" + backend, *common, "--entrypoint", "sleep", NGINX, "3600")
        docker("start", proxy)
        config = (ROOT / "docs/research/t10-nginx-probe.conf").read_text()
        if control == "strip-upgrade":
            config = config.replace("proxy_set_header Upgrade $http_upgrade;", "proxy_set_header Upgrade '';" )
        elif control == "publish-private-assets":
            config = config.replace("location /private-assets/ { return 404; }", "location /private-assets/ { return 200 'exposed'; }")
        elif control == "long-read-timeout":
            setting = "proxy_read_timeout 2s;"
            if config.count(setting) != 1:
                raise ValueError("long-read-timeout control requires exactly one " + setting)
            config = config.replace(setting, "proxy_read_timeout 60s;")
        elif control is not None:
            raise ValueError("unknown negative control")
        docker("exec", "-i", proxy, "sh", "-c", "cat > /tmp/nginx.conf", input_text=config)
        check = docker("exec", proxy, "nginx", "-c", "/tmp/nginx.conf", "-t")
        report["nginx_config_check"] = (check.stdout + check.stderr).strip()
        docker("exec", "-d", proxy, "nginx", "-c", "/tmp/nginx.conf", "-g", "daemon off;")
        # Bounded readiness; successful traffic is required before the acceptance probe.
        readiness = "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8080/ready', timeout=1).status == 200"
        for attempt in range(20):
            try:
                docker("exec", backend, "python", "-c", readiness)
                break
            except subprocess.CalledProcessError:
                if attempt == 19:
                    raise
                time.sleep(0.1)
        version = docker("exec", proxy, "nginx", "-v")
        report["nginx_version"] = (version.stdout + version.stderr).strip()
        report["container_python"] = docker("exec", backend, "python", "--version").stdout.strip()
        try:
            report["result"] = json.loads(docker("exec", backend, "python", "/tmp/probe.py", "probe").stdout)
        except subprocess.CalledProcessError as error:
            expected = {"strip-upgrade": "websocket-status", "publish-private-assets": "private-assets-not-public",
                        "long-read-timeout": "idle-close-deadline"}
            try:
                failure = json.loads(error.stdout)["failure"]
            except (ValueError, KeyError, TypeError):
                raise error
            if (not isinstance(failure, dict) or control not in expected or failure.get("check") != expected[control]
                    or (control == "strip-upgrade" and failure.get("detail") != "HTTP/1.1 426 Upgrade Required")):
                raise
            report["negative_control"] = {"variant": control, "detected": True, "failure": failure}
        if control and "negative_control" not in report:
            raise AssertionError("unsafe negative control escaped the probe")
        report["fixture_hashes"] = {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
                                    for path in (ROOT / "docs/research/t10-nginx-probe.conf", ROOT / "scripts/research/t10-proxy-fixture.py")}
    except Exception as error:
        error.report = report
        report["failure"] = {"type": type(error).__name__, "detail": str(error),
                             "passed_checks": getattr(error, "passed_checks", [])}
        raise
    finally:
        cleanup_owned_containers(intended, token, report)
    return report


def stop_local_proxy(proxy):
    """Stop only the session created for this owned Nginx master and its workers."""
    try:
        try:
            os.killpg(proxy.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proxy.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    finally:
        # Failed/interrupted waits and an exited master cannot skip worker cleanup.
        try:
            os.killpg(proxy.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proxy.wait(timeout=5)


def run_local(nginx_binary, control=None):
    """Owned loopback processes only; no Docker, privilege or system service changes."""
    binary = str(Path(nginx_binary).resolve(strict=True))
    spec = importlib.util.spec_from_file_location("t10_local_fixture", ROOT / "scripts/research/t10-proxy-fixture.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    server = thread = proxy = None
    report = {}
    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), fixture.Handler)
        server.idle_stop = threading.Event()
        # The shutdown probe closes the listening socket before checking the 502.
        def serve():
            try:
                server.serve_forever()
            finally:
                server.server_close()
        thread = threading.Thread(target=serve)
        thread.start()
        with tempfile.TemporaryDirectory(prefix="gb-t10-nginx-") as temporary:
            root = Path(temporary)
            (root / "logs").mkdir()
            with socket.socket() as reserve:
                reserve.bind(("127.0.0.1", 0))
                proxy_port = reserve.getsockname()[1]
            fixture.PROXY_PORT = proxy_port
            config = (ROOT / "docs/research/t10-nginx-probe.conf").read_text()
            config = config.replace("listen 8080;", f"listen 127.0.0.1:{proxy_port};")
            config = config.replace("127.0.0.1:8000", f"127.0.0.1:{server.server_port}")
            config = config.replace("/tmp/", temporary + "/")
            if control == "strip-upgrade":
                config = config.replace("proxy_set_header Upgrade $http_upgrade;", "proxy_set_header Upgrade '';" )
            elif control == "publish-private-assets":
                config = config.replace("location /private-assets/ { return 404; }", "location /private-assets/ { return 200 'exposed'; }")
            elif control == "long-read-timeout":
                assert config.count("proxy_read_timeout 2s;") == 1
                config = config.replace("proxy_read_timeout 2s;", "proxy_read_timeout 60s;")
            elif control is not None:
                raise ValueError("unknown negative control")
            path = root / "nginx.conf"
            path.write_text(config)
            report = {"observed_at": datetime.now(timezone.utc).isoformat(),
                      "tested_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                      "host": platform.platform(), "host_python": platform.python_version(),
                      "scope": "local loopback Nginx processes; no TLS/Discord/GoDaddy acceptance",
                      "nginx_binary_sha256": hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
                      "nginx_version": subprocess.run([binary, "-V"], capture_output=True, text=True, check=True).stderr.strip(),
                      "control": control,
                      "fixture_hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                         (ROOT / "scripts/research/t10-nginx-probe.py", ROOT / "scripts/research/t10-proxy-fixture.py", ROOT / "docs/research/t10-nginx-probe.conf")}}
            checked = subprocess.run([binary, "-p", temporary + "/", "-c", str(path), "-t"], capture_output=True, text=True, check=True)
            report["nginx_config_check"] = checked.stderr.strip()
            with (root / "stderr.log").open("w+") as errors:
                proxy = subprocess.Popen([binary, "-p", temporary + "/", "-c", str(path), "-g", "daemon off;"], stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
                for attempt in range(50):
                    try:
                        if fixture.request("/ready")[0] == 200:
                            break
                    except OSError:
                        pass
                    if proxy.poll() is not None:
                        raise RuntimeError("owned nginx exited before readiness")
                    time.sleep(0.05)
                else:
                    raise RuntimeError("owned nginx readiness deadline")
                try:
                    report["result"] = fixture.probe()
                except fixture.ProbeFailure as error:
                    expected = {"strip-upgrade": "websocket-status", "publish-private-assets": "private-assets-not-public",
                                "long-read-timeout": "idle-close-deadline"}
                    if (control not in expected or error.check != expected[control]
                            or (control == "strip-upgrade" and error.detail != "HTTP/1.1 426 Upgrade Required")):
                        raise
                    report["negative_control"] = {"variant": control, "detected": True, "failure": str(error)}
                if control and "negative_control" not in report:
                    raise AssertionError("unsafe negative control escaped the probe")
                errors.seek(0)
                report["nginx_log"] = errors.read()
    except Exception as error:
        error.report = report
        report["failure"] = {"type": type(error).__name__, "detail": str(error),
                             "passed_checks": getattr(error, "passed_checks", [])}
        raise
    finally:
        failures = []
        if proxy is not None:
            try:
                stop_local_proxy(proxy)
            except Exception as error:
                failures.append("nginx: " + repr(error))
        if server is not None:
            server.idle_stop.set()
            for action in (
                lambda: server.shutdown() if thread is not None and thread.is_alive() else None,
                lambda: thread.join(timeout=5) if thread is not None and thread.ident is not None else None,
                server.server_close,
            ):
                try:
                    action()
                except Exception as error:
                    failures.append("backend: " + repr(error))
        report["cleanup"] = {"owned_nginx_exited": proxy is None or proxy.poll() is not None,
                             "owned_backend_thread_exited": thread is None or not thread.is_alive()}
        if failures:
            report["cleanup_failures"] = failures
            error = RuntimeError("Owned local cleanup failed: " + "; ".join(failures))
            error.report = report
            raise error
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--nginx-binary", type=Path, help="Use an explicit local binary with owned loopback processes")
    parser.add_argument("--negative-control", choices=["strip-upgrade", "publish-private-assets", "long-read-timeout"])
    args = parser.parse_args()
    try:
        report = run_local(args.nginx_binary, args.negative_control) if args.nginx_binary else run(args.negative_control)
    except Exception as error:
        report = getattr(error, "report", {"failure": {"type": type(error).__name__, "detail": str(error)}})
        output = json.dumps(report, indent=2) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8", newline="\n")
        print(output, end="")
        raise SystemExit(1)
    output = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8", newline="\n")
    print(output, end="")
