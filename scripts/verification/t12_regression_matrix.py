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
GATES = (G1, G2, G3)
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
PUBLICATION = "GB-T13.04.01.O1"
HANDOFF_ISSUES = ("GB-T12.D1", "GB-T12.G1")
PENDING = "No exact-candidate qualifying observation is recorded."
DISCORD_BLOCKED = "Candidate-scoped client support, approved Discord scope and qualifying receipt unavailable."
VPS_BLOCKED = "Approved GoDaddy scope and qualifying receipt unavailable."
REVIEW_PENDING = "Exact-candidate independent review and disposition unavailable."
PUBLICATION_BLOCKED = "Accepted historical #471 designation, published bytes and approval unavailable."
SMOKE = "Production smoke requires an approved deployed candidate at the GoDaddy target."
TRACE_SCOPES = {
    ("GB-T12.01.02", "Exercise actual UI launch/ready/auth/navigation with controlled SDK mocks "
     "and separately real supported Discord clients"): {"browser-e2e", "sdk-launch"},
    ("GB-T12.04.02", "run production smoke after deployment"): {"deployed-build-smoke", "deployed-client-smoke"},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = dict(pairs)
    require(len(result) == len(pairs), "duplicate JSON key")
    return result


def load(root, path):
    return json.loads((root / path).read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def indexed(rows, key, registry):
    result = {}
    for row in rows:
        identity = key(row)
        require(identity not in result, f"{registry}: duplicate registry identity {identity}")
        result[identity] = row
    return result


def mvp_requirements(root, native):
    rows = {}
    table = (line for line in (root / MVP).read_text(encoding="utf-8").splitlines() if line.startswith("|"))
    for line in table:
        label, *cells = (cell.strip() for cell in line.strip("|").split("|"))
        if label in {"Mandatory behavior", "---"}:
            continue
        require(label in MVP_CASES and len(cells) == 2, f"{MVP}: invalid behavior row {label}")
        ids = re.findall(r"\[(GB-[^\]]+)\]\([^\)]+/issues/(\d+)\)", cells[1])
        require(ids and all(native.get(key) == int(number) for key, number in ids),
                f"{MVP}: missing or mismatched issue for {label}")
        require(label not in rows, f"{MVP}: duplicate behavior {label}")
        require(len({key for key, _ in ids}) == len(ids), f"{MVP}: duplicate verification for {label}")
        rows[label] = [key for key, _ in ids]
    require(rows.keys() == MVP_CASES.keys(), f"{MVP}: mandatory behavior set changed")
    return rows


def trace_requirements(root, native, dependencies):
    result = []
    plan = load(root, TRACE)
    indexed(plan, lambda row: (row["feature"], row["requirement"]), TRACE)
    for index, row in enumerate(plan):
        if row["release"] not in {"MVP", "v1.0"}:
            continue
        gate = G1 if row["release"] == "MVP" else G3
        require(row["release_gate"] == gate and row["tests"],
                f"{TRACE}#/{index}: missing gate or verification")
        require(len(row["tests"]) == len(set(row["tests"])), f"{TRACE}#/{index}: duplicate verification")
        require(all(key in native for key in row["tests"] + [row["documentation"]]),
                f"{TRACE}#/{index}: unknown verification or documentation issue")
        require(set(row["tests"]) <= dependencies[G3],
                f"{TRACE}#/{index}: verification outside G3 prerequisite closure")
        result.append({"source": f"{TRACE}#/{index}", "text": row["requirement"], "gate": gate,
                       "workstream": row["workstream"], "feature": row["feature"],
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
    manifest = indexed(load(root, HANDOFF)["handoffMatrix"], lambda row: tuple(row["key"]), HANDOFF)
    floors = {}

    def add(name, environment, cases, *, issue=None, gates=(G3,), source=T12):
        key = name, environment
        if key in manifest:
            accepted_issue = manifest.pop(key)["issue"]
            require(issue is None or issue == accepted_issue, f"{key}: native handoff issue differs")
            issue = accepted_issue
        require(issue is not None, f"{key}: missing accepted handoff entry")
        floors[key] = issue, sorted(gates), source, frozenset(cases.split())

    mvp_cases = " ".join(MVP_CASES.values())
    add("integrated", "hosted", mvp_cases, gates=(G1, G3))
    add("harness", "offline", "owned-setup invalid-config interrupted-cleanup")
    add("browser-e2e", "local", "controlled-launch ready auth cancel navigation policy-feedback reconnect drafts accessible-controls")
    add("release-fence", "hosted", "release-fence")
    add("isolation", "hosted", "tenant-isolation content-scope")
    add("convergence", "hosted", "idempotency concurrent-convergence")
    add("recovery", "vps-recovery", "recovery-inventories deletion-fences")
    add("regression", "hosted", f"regression verified-build {mvp_cases} {' '.join(STABLE_CASES)} accessibility")
    production = (G2, G3)
    add("production-network", "vps-network", "https wss heartbeat private-data-plane tls-chain tls-renewal "
        "idle-below-threshold idle-above-threshold reconnect-restart firewall-isolation sql-asset-isolation "
        "large-message oversize-denial", issue=353, gates=production)
    add("production-smoke", "vps-network", "https-wss monitoring rollback smoke", gates=production)
    add("production-recovery", "vps-recovery", "isolated-restore rpo-rto continuity backup-recovery-objectives",
        gates=production)
    add("credentials-recovery", "vps-recovery", "credential-restore retired-credential-denied", issue=378,
        gates=production)
    add("platform-network", "vps-network", "platform-network https wss idle-below-threshold idle-above-threshold",
        gates=production)
    add("bounded-load", "vps-load", "bounded-load resource-budget safety-stop capacity-durable-ack-latency "
        "process-restart-under-load reconnect-latency", gates=production)
    add("deployed-build-smoke", "vps-network", "verified-build smoke https-wss", issue=417, gates=production)
    add("mvp-publication", "review", "authoritative-471-designation historical-g1-approval-and-receipt "
        "published-tag-and-release-bytes", issue=471, source=T13)
    add("availability", "vps-network", "complete-utc-month counts-incidents-gaps "
        "representative-end-to-end-read-and-write", issue=364, source=REQUIREMENTS)
    for client in sorted(discord):
        add("discord-startup", client, "activity-startup authenticated-guild", issue=455, gates=(G1, G3))
        add("production-discord", client, "activity-startup mapped-proxy upgrade reconnect large-message "
            "oversize-denial resync-without-acceptance", issue=353, gates=production)
        add("deployed-client-smoke", client, "verified-build deployed-client-journey activity-startup "
            "authenticated-guild mapped-proxy reconnect", issue=417, gates=production)
        add("sdk-launch", client, "actual-launch sdk-compatibility", issue=396)
        suffix = client.removeprefix("discord-web-").removeprefix("discord-")
        add(f"accessibility-{suffix}", client, "manual-at keyboard screen-reader accessible-task-coverage")
    for name, issue in SECURITY.items():
        environment = "review" if name == "independent-security-review" else "hosted"
        add(name, environment, name, issue=issue, gates=(G1, G3), source=T9)
    require(not manifest, f"unexpected accepted handoff keys: {sorted(manifest)}")
    return floors


def row_state(key, external, discord):
    name, environment = key
    if "smoke" in name:
        return "blocked", SMOKE
    if name == "mvp-publication":
        return "blocked", PUBLICATION_BLOCKED
    if environment in discord:
        return "blocked", DISCORD_BLOCKED
    if environment in external:
        return "blocked", VPS_BLOCKED
    if name == "independent-security-review":
        return "pending", REVIEW_PENDING
    return "pending", PENDING


def issue_reference(item):
    return {"id": item["id"], "url": item["github"]["url"], "owner": item["fields"]["Owner Role"]}


def observation_reference(row, cases):
    return {"row": [row["id"], row["environment"]], "method": row["method"],
            "issue": row["issueUrl"], "cases": cases, "source": row["source"],
            "environmentSource": row["environmentSource"], "status": row["status"]}


def case_observations(rows, gate, case):
    matching = {case, "accessible-task-coverage"} if case == "accessibility" else {case}
    return [observation_reference(row, sorted(matching.intersection(row["casesByGate"][gate])))
            for row in rows if matching.intersection(row["casesByGate"].get(gate, ()))]


def audit(root, matrix):
    require(type(matrix["version"]) is int and matrix["version"] == 1, "invalid matrix version")
    require(matrix.keys() == {"version", "mvp", "stable", "nativePrerequisites", "rows", "productionSmoke"},
            "unexpected matrix field")
    registry = load(root, BACKLOG)["items"]
    items = indexed(registry, lambda item: item["id"], BACKLOG)
    issues = indexed(registry, lambda item: item["github"]["number"], BACKLOG)
    indexed(registry, lambda item: item["github"]["id"], BACKLOG)
    native = {key: item["github"]["number"] for key, item in items.items()}
    native_ids = {number: item["id"] for number, item in issues.items()}
    require(all(len(items[gate]["dependencies"]) == len(set(items[gate]["dependencies"]))
                for gate in GATES), "duplicate native release prerequisite")
    dependencies = {gate: prerequisite_closure(gate, items) for gate in GATES}
    mvp = mvp_requirements(root, native)
    require(matrix["mvp"] == {MVP_CASES[label]: ids for label, ids in mvp.items()},
            "mandatory MVP behavior or direct verification differs from canonical table")
    require({key for ids in mvp.values() for key in ids} <= dependencies[G1],
            "mandatory MVP direct verification outside G1 prerequisite closure")
    trace = trace_requirements(root, native, dependencies)
    counts = {target: sum(row["gate"] == gate for row in trace)
              for target, gate in (("MVP", G1), ("v1.0", G3))}
    require(matrix["stable"] == {"traceRows": counts,
            "publicationIssue": PUBLICATION, "integratedCases": sorted(STABLE_CASES)},
            "mandatory stable requirement summary changed")

    require(matrix["nativePrerequisites"] == {gate: sorted(items[gate]["dependencies"]) for gate in sorted(GATES)},
            "native release prerequisite list changed")
    external = indexed(load(root, PLATFORMS)["external_rows"], lambda row: row["id"], PLATFORMS)
    require(all(row["status"] == "not-run" for row in external.values()),
            f"{PLATFORMS}: unsupported platform status or pass claim")
    discord = {key for key in external if key.startswith("discord-")}
    floors = row_floors(root, discord)
    require(external.keys() == {environment for _, environment in floors
                                if environment.startswith(("discord-", "vps-"))},
            f"{PLATFORMS}: unexpected external environment coverage")
    platform_source = {key: f"{PLATFORMS}#/external_rows/{index}" for index, key in enumerate(external)}
    environments = {"offline": "fixture", "local": "local_integration", "hosted": "hosted_ci",
                    "review": "independent_review",
                    **{key: "real_discord" if key in discord else "real_godaddy" for key in external}}
    seen = set()
    for row in matrix["rows"]:
        require(row.keys() == {"id", "environment", "class", "issue", "gates", "cases",
                               "owner", "source", "status", "limitation"}, "unexpected row field")
        key = row["id"], row["environment"]
        require(key in floors and key not in seen, f"{key}: unknown environment, row or duplicate")
        seen.add(key)
        issue, gates, source, cases = floors[key]
        require(row["class"] == environments[key[1]], f"{key}: wrong evidence class")
        require(type(row["issue"]) is int and row["issue"] == issue and row["issue"] in native_ids
                and sorted(row["gates"]) == sorted(gates), f"{key}: wrong native issue or release gate")
        require(row["source"] == source, f"{key}: wrong canonical observation source")
        require(isinstance(row["cases"], list) and len(row["cases"]) == len(cases)
                and frozenset(row["cases"]) == cases, f"{key}: wrong canonical observation cases")
        require(row["owner"] == items[native_ids[issue]]["fields"]["Owner Role"],
                f"{key}: wrong verification owner")
        status, limitation = row_state(key, external, discord)
        require(row["status"] in {"pending", "blocked"}, f"{key}: unsupported status or pass claim")
        if key[1] in external:
            require(row["status"] == "blocked", f"{key}: owned environment prerequisites unavailable")
        require(row["status"] == status and row["limitation"] == limitation,
                f"{key}: wrong planned status or limitation")

    require(seen == floors.keys(), f"missing required evidence rows: {sorted(floors.keys() - seen)}")
    require(matrix["productionSmoke"] == {"issue": 417, "state": "open", "status": "blocked",
                                          "limitation": SMOKE},
            "#417 production smoke limitation must remain explicit")
    rows = [
        {**row, "issueId": native_ids[row["issue"]], "issueUrl": issues[row["issue"]]["github"]["url"],
         "method": ("manual" if row["environment"] == "review" or row["id"].startswith("accessibility-")
                    else "owned-platform" if row["environment"] in external else "automated"),
         "environmentSource": platform_source.get(row["environment"], row["source"]),
         "casesByGate": {
             gate: sorted(set(row["cases"]) | STABLE_CASES)
             if row["id"] == "integrated" and gate == G3 else row["cases"]
             for gate in row["gates"]
         }}
        for row in matrix["rows"]
    ]
    verification = {key for ids in mvp.values() for key in ids}
    verification.update(key for row in trace for key in row["verification"])
    for requirement in trace:
        gate = requirement["gate"]
        links = [row for row in rows if row["issueId"] in requirement["verification"] and gate in row["gates"]]
        scope = TRACE_SCOPES.get((requirement["feature"], requirement["text"]), ())
        requirement["issueLevelObservationLinks"] = [observation_reference(row, row["casesByGate"][gate])
                                                     for row in links]
        requirement["scopeObservationLinks"] = [observation_reference(row, row["casesByGate"][gate])
                                                for row in links if row["id"] in scope]
        requirement["handoffIssue"] = {**issue_reference(items[requirement["handoff"]]),
                                       "artifacts": items[requirement["handoff"]]["documentation_artifacts"]}
        requirement["scopeEvidenceStatus"] = "pending"
    mvp_report = []
    for label, verification_ids in mvp.items():
        case = MVP_CASES[label]
        observations = case_observations(rows, G1, case)
        mvp_report.append({"case": case, "behavior": label, "verification": verification_ids, "source": MVP,
                           "observations": observations, "observationRows": [row["row"] for row in observations]})
    return {
        "verificationIssues": {
            key: {**issue_reference(items[key]), "expectedTests": items[key]["expected_tests"],
                  "documentation": items[key]["documentation_artifacts"]}
            for key in sorted(verification)
        },
        "platformEnvironments": external,
        "mvp": mvp_report,
        "stableFunctionality": {case: case_observations(rows, G3, case)
                                for case in sorted(STABLE_CASES | {"accessibility"})},
        "requirements": trace,
        "handoffs": {
            key: {**issue_reference(items[key]),
                  "prerequisites": [issue_reference(items[dependency]) for dependency in sorted(items[key]["dependencies"])]}
            for key in (*HANDOFF_ISSUES, PUBLICATION)
        },
        "gates": {gate: {"status": "pending", "issue": native[gate], "issueUrl": items[gate]["github"]["url"],
                         "prerequisites": sorted(items[gate]["dependencies"]),
                         "prerequisiteIssues": [issue_reference(items[key]) for key in sorted(items[gate]["dependencies"])]}
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
