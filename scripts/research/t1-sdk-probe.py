"""Inspect a pinned SDK and run only its dependency-free URL utility locally.

No SDK handshake, Discord API, OAuth, browser proxy or credentials are used.
Broader package/license research remains #477; this probes T1-specific surfaces.
"""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import urllib.request


VERSION = "2.5.0"
INTEGRITY = "sha512-FNoe5PbSkoKEbqPubaBmq6tlEMOftMjR3gu55YrdrrKmBfKKM4i9P/Z+Zxl0RZdJcKviBwVcTyYMMPM/aGex/w=="
URL_MODULE_HASH = "0865df06e3742aa4cf7092f95c7a1519c09ddd45126f8af9bf6afaaa3aee7038"
PATHS = (
    "package/package.json",
    "package/output/commands/authorize.d.ts",
    "package/output/Discord.d.ts",
    "package/output/interface.d.ts",
    "package/output/commands/getChannelPermissions.d.ts",
    "package/output/utils/patchUrlMappings.d.ts",
    "package/output/schema/types.d.ts",
    "package/output/utils/url.mjs",
)


def inspect(archive: Path) -> tuple[dict, bytes]:
    with archive.open("rb") as stream:
        raw = stream.read(4*1024*1024 + 1)
    if len(raw) > 4*1024*1024:
        raise ValueError("archive exceeds research byte budget")
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(raw).digest()).decode()
    if integrity != INTEGRITY:
        raise ValueError("SDK archive does not match fixed 2.5.0 integrity pin")
    selected = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        members = tar.getmembers()
        if len(members) > 512 or sum(m.size for m in members) > 4*1024*1024:
            raise ValueError("expanded metadata exceeds research budget")
        for path in PATHS:
            matches = [m for m in members if m.name == path]
            if len(matches) != 1 or not matches[0].isfile() or matches[0].size > 1024*1024:
                raise ValueError("missing, duplicate or invalid selected SDK member")
            selected[path] = tar.extractfile(matches[0]).read(1024*1024 + 1)
    package = json.loads(selected[PATHS[0]])
    if package["name"] != "@discord/embedded-app-sdk" or package["version"] != VERSION:
        raise ValueError("unexpected package identity")
    authorize = selected[PATHS[1]].decode()
    declaration = re.search(r"export interface AuthorizeInput \{([^}]+)\}", authorize)
    if declaration is None:
        raise ValueError("authorize input declaration missing")
    fields = dict(re.findall(r"^\s+(\w+\??):\s*([^;]+);", declaration[1], re.MULTILINE))
    expected = {
        "client_id": "string", "scope": "OAuthScopes[]", "response_type?": "'code'",
        "code_challenge?": "string", "state?": "string", "prompt?": "'none'",
        "code_challenge_method?": "'S256'",
    }
    if fields != expected or "code: string;" not in authorize:
        raise ValueError("authorize declaration observations changed")
    interface = selected[PATHS[2]].decode()
    if not all("readonly " + key + ": string | null;" in interface
               for key in ("guildId", "channelId", "mobileAppVersion")):
        raise ValueError("nullable context declaration changed")
    scope_types = selected["package/output/schema/types.d.ts"].decode()
    if not all("'" + scope + "'" in scope_types
               for scope in ("identify", "guilds", "guilds.members.read")):
        raise ValueError("candidate membership scope declarations changed")
    url_module = selected[PATHS[-1]]
    if hashlib.sha256(url_module).hexdigest() != URL_MODULE_HASH:
        raise ValueError("URL module hash differs from reviewed pin")
    if re.search(rb"^\s*import\b", url_module, re.MULTILINE):
        raise ValueError("URL module unexpectedly imports dependencies")
    return {
        "package": package["name"], "version": VERSION, "archive_integrity": integrity,
        "archive_sha256": hashlib.sha256(raw).hexdigest(),
        "selected_sha256": {p: hashlib.sha256(b).hexdigest() for p, b in selected.items()},
        "authorize_input_declaration": fields,
        "authorize_response_declaration": {"code": "string"},
        "nullable_sdk_context": ["guildId", "channelId", "mobileAppVersion"],
        "candidate_scope_literals_present": ["identify", "guilds", "guilds.members.read"],
        "declaration_limit": "Static text observations, not TypeScript compile or OAuth behavior.",
    }, url_module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--archive", type=Path)
    source.add_argument("--download", action="store_true", help="fetch only the fixed public 2.5.0 tarball")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="guildboard-t1-sdk-") as temp:
        archive = args.archive
        if args.download:
            archive = Path(temp) / "sdk.tgz"
            url = "https://registry.npmjs.org/@discord/embedded-app-sdk/-/embedded-app-sdk-2.5.0.tgz"
            with urllib.request.urlopen(url, timeout=25) as response:
                archive.write_bytes(response.read(4*1024*1024 + 1))
        report, module = inspect(archive)
        report.update(evidence_kind="pinned-artifact-and-local-url-utility-only",
                      observed_at_utc=datetime.now(timezone.utc).isoformat())
        path = Path(temp) / "url.mjs"
        path.write_bytes(module)
        # Execute only the reviewed, integrity-pinned dependency-free URL helper.
        env = dict(os.environ, T1_SDK_URL_MODULE=str(path))
        test = Path(__file__).resolve().parents[2] / "tests/research/t1-sdk-url.test.mjs"
        result = subprocess.run(["node", "--test", "--test-reporter=tap", str(test)],
                                text=True, encoding="utf-8", capture_output=True,
                                env=env, timeout=30)
        names = re.findall(r"^# Subtest: (.+)$", result.stdout, re.MULTILINE)
        report["node_version"] = subprocess.check_output(["node", "--version"], text=True).strip()
        report["url_helper_tests"] = {"exit_code": result.returncode, "count": len(names),
                                      "names": names, "tap_output": result.stdout}
        report["result"] = "pass" if result.returncode == 0 and len(names) == 12 else "fail"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(report, indent=2, sort_keys=True) + "\n").encode())
    print("SDK 2.5.0 pin/declarations checked; URL utility tests: " + report["result"])
    return int(report["result"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
