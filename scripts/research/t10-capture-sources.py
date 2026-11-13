"""Record public primary-response metadata, not a platform verification result."""
import argparse
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


class FetchFailure(OSError):
    def __init__(self, error):
        super().__init__(error["detail"])
        self.error_type = error["type"]
        self.http_status = error.get("http_status")


def fetch(url, timeout):
    """A disposable process bounds DNS, redirects and trickling response bodies."""
    if timeout <= 0:
        raise TimeoutError("collection elapsed-time deadline exceeded")
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                 "--fetch-worker", url], capture_output=True,
                                text=True, check=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        # subprocess.run kills and reaps the child before raising.
        raise TimeoutError("response elapsed-time deadline exceeded") from error
    envelope = json.loads(result.stdout)
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
    deadline = time.monotonic() + COLLECTION_SECONDS
    for name, url in SOURCES:
        row = {"id": name, "url": url, "observed_at": datetime.now(timezone.utc).isoformat()}
        try:
            result = fetch(url, min(ATTEMPT_SECONDS, deadline - time.monotonic()))
            row.update(result)
            row["status"] = row.pop("http_status")
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            row["error"] = str(error)
        observations.append(row)
    return {"kind": "public-response-observation-not-account-or-content-attestation", "sources": observations}


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fetch-worker":
        fetch_worker(sys.argv[2])
        sys.exit(0)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = capture()
    try:
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    except (OSError, ValueError) as error:
        print(json.dumps(result, indent=2))
        print("Cannot write source report: " + str(error), file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"observed": len(result["sources"]), "http_200": sum(row.get("status") == 200 for row in result["sources"]), "failures": [row["id"] for row in result["sources"] if "error" in row]}))
