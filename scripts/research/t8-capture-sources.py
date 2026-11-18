"""Capture public primary-source response metadata, never app credentials/content."""
import concurrent.futures
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

SOURCES = [
    ("D1", "https://docs.discord.com/developers/resources/application.md"),
    ("D2", "https://docs.discord.com/developers/topics/oauth2.md"),
    ("D3", "https://docs.discord.com/developers/interactions/application-commands.md"),
    ("D4", "https://docs.discord.com/developers/interactions/overview.md"),
    ("D5", "https://docs.discord.com/developers/interactions/receiving-and-responding.md"),
    ("D6", "https://docs.discord.com/developers/topics/permissions.md"),
    ("D7", "https://docs.discord.com/developers/resources/guild.md"),
    ("D8", "https://docs.discord.com/developers/events/gateway.md"),
    ("N1", "https://nodejs.org/download/release/v24.18.0/docs/api/crypto.html"),
    ("R1", "https://www.rfc-editor.org/rfc/rfc8032.txt"),
]


def capture(source):
    source_id, url = source
    request = urllib.request.Request(url, headers={"User-Agent": "Guildboard-T8-public-research/1"})
    with urllib.request.urlopen(request, timeout=45) as response:
        body = response.read(4_000_001)
        if len(body) > 4_000_000:
            raise ValueError("public source exceeds capture bound")
        return {"id": source_id, "url": url, "resolved_url": response.url,
                "observed_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "status": response.status, "content_type": response.headers.get("Content-Type"),
                "last_modified": response.headers.get("Last-Modified"),
                "etag": response.headers.get("ETag"), "response_bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest()}


if __name__ == "__main__":
    # Explicit invocation refreshes observations; hashes identify responses, not immutable docs releases.
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(capture, SOURCES))
    result = {"schema": "t8-primary-observations-v1", "python": sys.version.split()[0],
              "disclaimer": "Public HTTP response observations only; no platform acceptance.",
              "sources": rows}
    output = Path(sys.argv[1]) if len(sys.argv) == 2 else None
    data = (json.dumps(result, indent=2) + "\n").encode()
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
    else:
        sys.stdout.buffer.write(data)
