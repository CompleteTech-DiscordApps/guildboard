"""Record public primary-response metadata, not a platform verification result."""
import argparse
from datetime import datetime, timezone
import http.client
import hashlib
import json
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


def capture():
    observations = []
    for name, url in SOURCES:
        row = {"id": name, "url": url, "observed_at": datetime.now(timezone.utc).isoformat()}
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Guildboard-T10-Research/1.0"})
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read(4_000_001)
                if len(data) > 4_000_000:
                    raise ValueError("public response exceeds budget")
                declared = response.headers.get("Content-Length")
                if declared is not None and len(data) != int(declared):
                    raise ValueError("incomplete response body")
                row.update(status=response.status, final_url=response.url, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        except (OSError, http.client.HTTPException, ValueError) as error:
            row["error"] = str(error)
        observations.append(row)
    return {"kind": "public-response-observation-not-account-or-content-attestation", "sources": observations}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = capture()
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"observed": len(result["sources"]), "http_200": sum(row.get("status") == 200 for row in result["sources"]), "failures": [row["id"] for row in result["sources"] if "error" in row]}))
