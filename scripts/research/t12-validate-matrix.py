"""Validate research inputs and calculate offered load; sends no network traffic."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "docs/research/t12-validation-matrix.json"
EXTERNAL_GROUPS = {
    "discord-win": "client-at", "discord-mac": "client-at",
    "discord-web-chromium": "client-at", "discord-web-firefox": "client-at",
    "discord-ios": "client-at", "discord-android": "client-at",
    "discord-previews": "client-at", "vps-network": "vps",
    "vps-load": "vps", "vps-recovery": "vps",
}


# Scenario requirements are fixed independently of the untrusted matrix input.
REQUIRED_EVIDENCE = {'discord-android': {'app-build-sdk',
                     'background-foreground-reconnect',
                     'discord-os-at-device-builds',
                     'safe-area-rotation-soft-keyboard',
                     'supported-platform-setting',
                     'touch-speech-focus',
                     'trace-hash-date'},
 'discord-ios': {'app-build-sdk',
                 'background-foreground-reconnect',
                 'discord-os-at-device-builds',
                 'safe-area-rotation-soft-keyboard',
                 'supported-platform-setting',
                 'touch-speech-focus',
                 'trace-hash-date'},
 'discord-mac': {'app-build-sdk',
                 'discord-os-at-builds',
                 'keyboard-speech-focus',
                 'launch-ready-auth',
                 'proxy-https-wss',
                 'revocation-reconnect',
                 'trace-hash-date'},
 'discord-previews': {'app-build-sdk',
                      'exact-client-build-channel',
                      'launch-proxy-smoke',
                      'separate-from-stable-gate',
                      'trace-hash-date'},
 'discord-web-chromium': {'actual-discord-iframe',
                          'app-build-sdk',
                          'browser-os-at-builds',
                          'keyboard-speech-focus',
                          'proxy-https-wss',
                          'trace-hash-date',
                          'zoom-reflow-contrast'},
 'discord-web-firefox': {'actual-discord-iframe',
                         'app-build-sdk',
                         'browser-os-at-builds',
                         'keyboard-speech-focus',
                         'proxy-https-wss',
                         'support-decision',
                         'trace-hash-date'},
 'discord-win': {'app-build-sdk',
                 'discord-os-at-builds',
                 'keyboard-speech-focus',
                 'launch-ready-auth',
                 'proxy-https-wss',
                 'revocation-reconnect',
                 'trace-hash-date'},
 'vps-load': {'app-db-protocol-builds',
              'arrival-lag-dropped-work',
              'host-cpu-ram-disk-quota',
              'latency-sample-count-clock-error',
              'resource-raw-series',
              'tenant-isolation-and-revoke-races',
              'trace-hash-date'},
 'vps-network': {'https-chain-renewal',
                 'nginx-runtime-tls-builds',
                 'private-db-assets-denied-externally',
                 'redacted-provider-plan-region-os',
                 'trace-hash-date',
                 'wss-upgrade-heartbeat-idle-reconnect'},
 'vps-recovery': {'app-db-backup-tools-builds',
                  'commit-ack-fault-history',
                  'measured-rpo-rto-and-restore-hashes',
                  'scoped-crash-authorization',
                  'snapshot-tail-assets-receipts-cut',
                  'trace-hash-date'}}
REQUIRED_STOP_CONDITIONS = {'acknowledged mutation missing after authorized crash/recovery',
 'any unauthorized side effect or tenant leak',
 'available memory below 10 percent',
 'free data disk below 15 percent',
 'shared workload interference or missing explicit destructive-test authority',
 'sustained generator schedule lag above 1 second or host safety budget exceeded'}

def integer(value, lower, upper, label):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError("invalid bounded integer: " + label)
    return value


def validate(matrix):
    if (type(matrix.get("version")) is not int or matrix["version"] != 1
            or matrix.get("status") != "proposed-research-not-release-contract"):
        raise ValueError("unexpected research matrix version/status")
    mix = matrix["workload_mix_percent"]
    for value in mix.values():
        integer(value, 0, 100, "workload mix percent")
    if sum(mix.values()) != 100:
        raise ValueError("workload mix must sum to 100 percent")
    derived = []
    seen = set()
    profiles = matrix["load_profiles"]
    if not 1 <= len(profiles) <= 3:
        raise ValueError("bounded research profile count exceeded")
    bounds = {"guilds": 10, "boards_per_guild": 2, "editors_per_board": 8,
              "viewers_per_board": 42, "operations_per_editor_second": 5,
              "operation_payload_bytes": 2048, "duration_seconds": 900}
    for profile in profiles:
        if not isinstance(profile["id"], str) or not profile["id"] or profile["id"] in seen:
            raise ValueError("missing/duplicate profile ID")
        seen.add(profile["id"])
        for field, upper in bounds.items():
            integer(profile[field], 1, upper, field)
        if type(profile["gate_candidate"]) is not bool:
            raise ValueError("gate candidate must be boolean")
        boards = profile["guilds"] * profile["boards_per_guild"]
        people = profile["editors_per_board"] + profile["viewers_per_board"]
        rate = boards * profile["editors_per_board"] * profile["operations_per_editor_second"]
        payload = rate * profile["operation_payload_bytes"]
        derived.append({"id": profile["id"], "boards": boards,
                        "connected_clients": boards * people,
                        "offered_operations_per_second": rate,
                        "offered_operations_total": rate * profile["duration_seconds"],
                        "ingress_payload_bytes_per_second": payload,
                        "peer_fanout_payload_bytes_per_second": payload * (people - 1),
                        "measured_throughput": None})
    for budget in matrix["budget_candidates"]:
        p95 = integer(budget["p95_ms"], 1, 10000, "p95_ms")
        p99 = integer(budget["p99_ms"], 1, 10000, "p99_ms")
        if p95 > p99 or not budget["metric"] or not budget["conditions"]:
            raise ValueError("invalid latency budget/conditions")
    rows = matrix["external_rows"]
    if (len(rows) != len(EXTERNAL_GROUPS)
            or {row["id"] for row in rows} != set(EXTERNAL_GROUPS)):
        raise ValueError("external matrix coverage changed without research review")
    for row in rows:
        if row["group"] != EXTERNAL_GROUPS[row["id"]] or row["status"] != "not-run":
            raise ValueError("research fixture cannot certify external acceptance or change environment groups")
        evidence = row["required_evidence"]
        if (not isinstance(row["environment"], str) or not row["environment"].strip()
                or not isinstance(evidence, list) or len(evidence) < 5
                or any(not isinstance(item, str) or not item.strip() or item != item.strip()
                       for item in evidence)
                or len(set(evidence)) != len(evidence)
                or not REQUIRED_EVIDENCE[row["id"]].issubset(evidence)):
            raise ValueError("missing or invalid environment/evidence requirements")
    if matrix["accessibility_candidate"]["status"] != "not-run":
        raise ValueError("research fixture cannot certify accessibility")
    stops = matrix["stop_conditions"]
    if (not isinstance(stops, list) or len(stops) < 6
            or any(not isinstance(stop, str) or not stop.strip() or stop != stop.strip()
                   for stop in stops)
            or len(set(stops)) != len(stops)
            or not REQUIRED_STOP_CONDITIONS.issubset(stops)):
        raise ValueError("missing or invalid bounded experiment stop conditions")
    return {"matrix_version": 1, "kind": "input-validation-and-arithmetic-only",
            "runtime_or_platform_acceptance": False, "load": derived,
            "external_not_run": len(rows), "accessibility": "not-run"}


if __name__ == "__main__":
    print(json.dumps(validate(json.loads(DEFAULT.read_text(encoding="utf-8"))),
                     indent=2, sort_keys=True))
