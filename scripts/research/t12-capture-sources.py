"""Bounded public primary-document GET observations, no installation or credentials.

Output is metadata only. Hashes identify observed bytes; they are not an archive
or evidence of running the documented product. Failures are retained and exit 1.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import http.client
import hashlib
import json
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


def capture(source):
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
            with urllib.request.urlopen(target, timeout=15) as response:
                payload = response.read(MAX_BYTES + 1)
                if len(payload) > MAX_BYTES:
                    raise ValueError("response budget exceeded")
                declared = response.headers.get("Content-Length")
                if declared is not None and len(payload) != int(declared):
                    raise ValueError("incomplete response body")
                attempt.update(status="fetched", http_status=response.status,
                               final_url=response.url, bytes=len(payload),
                               sha256=hashlib.sha256(payload).hexdigest())
        except (OSError, http.client.HTTPException, ValueError) as error:
            attempt.update(status="fetch-failed", error_type=type(error).__name__)
            if isinstance(error, urllib.error.HTTPError):
                attempt["http_status"] = error.code
        attempts.append(attempt)
        if attempt["status"] == "fetched":
            break
    observation["attempts"] = attempts
    observation["status"] = attempts[-1]["status"]
    return observation


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as executor:
        sources = list(executor.map(capture, SOURCES))
    print(json.dumps({"kind": "public-document-observations-not-platform-testing",
                      "sources": sources}, indent=2, sort_keys=True))
    sys.exit(any(source["status"] != "fetched" for source in sources))
