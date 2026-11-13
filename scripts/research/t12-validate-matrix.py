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
                or "trace-hash-date" not in evidence):
            raise ValueError("missing or invalid environment/evidence requirements")
    if matrix["accessibility_candidate"]["status"] != "not-run":
        raise ValueError("research fixture cannot certify accessibility")
    if len(matrix["stop_conditions"]) < 6:
        raise ValueError("missing bounded experiment stop conditions")
    return {"matrix_version": 1, "kind": "input-validation-and-arithmetic-only",
            "runtime_or_platform_acceptance": False, "load": derived,
            "external_not_run": len(rows), "accessibility": "not-run"}


if __name__ == "__main__":
    print(json.dumps(validate(json.loads(DEFAULT.read_text(encoding="utf-8"))),
                     indent=2, sort_keys=True))
