#!/usr/bin/env python3
"""Validate and report the offline #416 coverage plan."""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = "docs/verification/t12-regression-matrix.json"
MVP = "planning/MVP-ACCEPTANCE.md"
TRACE = "planning/traceability.json"
BACKLOG = "planning/guildboard-backlog.json"
T9 = "docs/specifications/GB-T9-S1-security-privacy-contract.md"
T12 = "docs/specifications/GB-T12-S1-verification-evidence-contract.md"
T13 = "docs/specifications/GB-T13-S1-documentation-release-contract.md"
HANDOFF = "docs/specifications/fixtures/GB-T12-S1-scenarios.json"
PLATFORMS = "docs/research/t12-validation-matrix.json"
REQUIREMENTS = "docs/requirements/GB-T0-01-01-requirements.md"
G1, G2, G3 = ("GB-T13.G1", "GB-T13.G2", "GB-T13.G3")
GATES = {G1, G2, G3}
MVP_CASES = {
    "Discord Activity startup": "activity-startup",
    "Authenticated guild context": "authenticated-guild",
    "Moderator role verification": "moderator-role",
    "Working whiteboard editor": "whiteboard",
    "Simultaneous moderator editing": "simultaneous-moderators",
    "Read-only viewers": "read-only-viewer",
    "Backend-enforced permissions": "backend-permissions",
    "Live synchronization": "live-sync",
    "Saved boards and basic board APIs": "save-board",
    "Basic board locking": "board-lock",
    "Basic reconnection": "reconnect",
    "Fundamental security negatives": "security-negatives",
}
STABLE_CASES = {"modes", "moderation", "import-export", "recovery"}
SECURITY = {
    "threat-model": 321,
    "authorization-negative": 300,
    "dependency-license-lockfile": 318,
    "secret-static-triage": 318,
    "upload-import": 307,
    "independent-security-review": 321,
}
SMOKE = "Production smoke requires an approved deployed candidate at the GoDaddy target."


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = dict(pairs)
    require(len(result) == len(pairs), "duplicate JSON key")
    return result


def load(root, path):
    return json.loads((root / path).read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def mvp_requirements(root, native):
    rows = {}
    for label, _, verification in re.findall(
        r"^\| ([^|]+?) \| (\[GB-[^|]+?) \| (\[GB-[^|]+?) \|$",
        (root / MVP).read_text(encoding="utf-8"), re.MULTILINE
    ):
        ids = re.findall(r"\[(GB-[^\]]+)\]\([^\)]+/issues/(\d+)\)", verification)
        require(ids and all(native.get(key) == int(number) for key, number in ids),
                f"{MVP}: missing or mismatched issue for {label}")
        require(label not in rows, f"{MVP}: duplicate behavior {label}")
        rows[label] = [key for key, _ in ids]
    require(rows.keys() == MVP_CASES.keys(), f"{MVP}: mandatory behavior set changed")
    return rows


def trace_requirements(root, native, dependencies):
    result = []
    for index, row in enumerate(load(root, TRACE)):
        if row["release"] not in {"MVP", "v1.0"}:
            continue
        gate = G1 if row["release"] == "MVP" else G3
        require(row["release_gate"] == gate and row["tests"],
                f"{TRACE}#/{index}: missing gate or verification")
        require(all(key in native for key in row["tests"] + [row["documentation"]]),
                f"{TRACE}#/{index}: unknown verification or documentation issue")
        require(set(row["tests"]) <= dependencies[G3],
                f"{TRACE}#/{index}: verification outside G3 prerequisite closure")
        result.append({"source": f"{TRACE}#/{index}", "text": row["requirement"], "gate": gate,
                       "verification": row["tests"], "handoff": row["documentation"]})
    return result


def prerequisite_closure(key, items):
    pending = list(items[key]["dependencies"])
    result = set()
    while pending:
        current = pending.pop()
        if current not in result:
            result.add(current)
            pending.extend(items[current]["dependencies"])
    return result


def row_floors(root, discord):
    handoff = load(root, HANDOFF)["handoffMatrix"]
    floors = {tuple(row["key"]): (row["issue"], {G3}) for row in handoff}
    for key, issue, gates in (
        (("integrated", "hosted"), 455, {G1, G3}),
        (("production-network", "vps-network"), 353, {G2, G3}),
        (("production-smoke", "vps-network"), 457, {G2, G3}),
        (("production-recovery", "vps-recovery"), 457, {G2, G3}),
        (("credentials-recovery", "vps-recovery"), 378, {G2, G3}),
        (("platform-network", "vps-network"), 414, {G2, G3}),
        (("bounded-load", "vps-load"), 414, {G2, G3}),
        (("deployed-build-smoke", "vps-network"), 417, {G2, G3}),
        (("mvp-publication", "review"), 471, {G3}),
        (("availability", "vps-network"), 364, {G3}),
    ):
        floors[key] = issue, gates
    for client in discord:
        for name, issue, gates in (
            ("discord-startup", 455, {G1, G3}), ("production-discord", 353, {G2, G3}),
            ("deployed-client-smoke", 417, {G2, G3}), ("sdk-launch", 396, {G3})
        ):
            floors[name, client] = issue, gates
    for name, issue in SECURITY.items():
        environment = "review" if name == "independent-security-review" else "hosted"
        floors[name, environment] = issue, {G1, G3}
    return floors


def audit(root, matrix):
    require(type(matrix["version"]) is int and matrix["version"] == 1, "invalid matrix version")
    require(matrix.keys() == {"version", "mvp", "stable", "rows", "productionSmoke"},
            "unexpected matrix field")
    items = {row["id"]: row for row in load(root, BACKLOG)["items"]}
    native = {key: item["github"]["number"] for key, item in items.items()}
    dependencies = {gate: prerequisite_closure(gate, items) for gate in GATES}
    mvp = mvp_requirements(root, native)
    require(matrix["mvp"] == {MVP_CASES[label]: ids for label, ids in mvp.items()},
            "mandatory MVP behavior or direct verification differs from canonical table")
    trace = trace_requirements(root, native, dependencies)
    counts = {target: sum(row["gate"] == gate for row in trace)
              for target, gate in (("MVP", G1), ("v1.0", G3))}
    require(matrix["stable"] == {"traceRows": counts,
            "directPrerequisites": sorted(items[G3]["dependencies"]),
            "publicationIssue": "GB-T13.04.01.O1", "integratedCases": sorted(STABLE_CASES)},
            "mandatory stable requirement count or native prerequisite list changed")

    external = {row["id"]: row for row in load(root, PLATFORMS)["external_rows"]}
    discord = {key for key in external if key.startswith("discord-")}
    floors = row_floors(root, discord)
    environments = {"offline": "fixture", "local": "local_integration", "hosted": "hosted_ci",
                    "review": "independent_review",
                    **{key: "real_discord" if key in discord else "real_godaddy" for key in external}}
    native_ids = {number: key for key, number in native.items()}
    seen = set()
    for row in matrix["rows"]:
        require(row.keys() == {"id", "environment", "class", "issue", "gates", "cases",
                               "owner", "source", "status", "limitation"}, "unexpected row field")
        key = row["id"], row["environment"]
        require(key in floors and key not in seen, f"{key}: unknown environment, row or duplicate")
        seen.add(key)
        issue, gates = floors[key]
        require(row["class"] == environments[key[1]], f"{key}: wrong evidence class")
        require(type(row["issue"]) is int and row["issue"] == issue and row["issue"] in native_ids
                and sorted(row["gates"]) == sorted(gates), f"{key}: wrong native issue or release gate")
        require(row["source"] in {T9, T12, T13, REQUIREMENTS}, f"{key}: unknown source")
        require(isinstance(row["cases"], list) and row["cases"]
                and all(isinstance(case, str) and case.strip() for case in row["cases"])
                and len(set(row["cases"])) == len(row["cases"])
                and row["owner"] == items[native_ids[issue]]["fields"]["Owner Role"]
                and isinstance(row["limitation"], str) and row["limitation"].strip(), f"{key}: incomplete observation")
        require(row["status"] in {"pending", "blocked"}, f"{key}: unsupported status or pass claim")
        if key[1] in external:
            require(row["status"] == "blocked", f"{key}: owned environment prerequisites unavailable")
        if "smoke" in key[0]:
            require(row["status"] == "blocked" and row["limitation"] == SMOKE,
                    f"{key}: missing production smoke limitation")
        if key == ("integrated", "hosted"):
            require(set(matrix["mvp"]) == set(row["cases"]), "integrated row differs from mandatory MVP cases")

    require(seen == floors.keys(), f"missing required evidence rows: {sorted(floors.keys() - seen)}")
    require(matrix["productionSmoke"] == {"issue": 417, "state": "open", "status": "blocked",
                                          "limitation": SMOKE},
            "#417 production smoke limitation must remain explicit")
    rows = [
        {**row, "issueId": native_ids[row["issue"]],
         "casesByGate": {
             gate: sorted(set(row["cases"]) | STABLE_CASES)
             if row["id"] == "integrated" and gate == G3 else row["cases"]
             for gate in row["gates"]
         }}
        for row in matrix["rows"]
    ]
    verification = {key for ids in mvp.values() for key in ids}
    verification.update(key for row in trace for key in row["verification"])
    return {
        "verificationIssues": {
            key: {"url": items[key]["github"]["url"], "owner": items[key]["fields"]["Owner Role"],
                  "expectedTests": items[key]["expected_tests"]}
            for key in sorted(verification)
        },
        "platformEnvironments": external,
        "mvp": [
            {"case": MVP_CASES[label], "behavior": label, "verification": issues,
             "observationRows": [[row["id"], row["environment"]] for row in rows
                                 if G1 in row["gates"] and MVP_CASES[label] in row["casesByGate"][G1]]}
            for label, issues in mvp.items()
        ],
        "requirements": trace,
        "gates": {gate: {"status": "pending", "issue": native[gate],
                         "prerequisites": sorted(items[gate]["dependencies"])}
                  for gate in sorted(GATES)},
        "rows": rows,
        "productionSmoke": matrix["productionSmoke"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="emit the complete coverage report as JSON")
    options = parser.parse_args()
    try:
        report = audit(ROOT, load(ROOT, MATRIX))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"Invalid regression matrix: {error}", file=sys.stderr)
        return 1
    if options.report:
        print(json.dumps(report, indent=2))
    else:
        print(f"Validated {len(report['mvp'])} MVP behaviors, {len(report['requirements'])} planning "
              f"requirements and {len(report['rows'])} evidence rows. G1/G2/G3 are pending.")
        print(f"#417 remains open; smoke blocked. {SMOKE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
