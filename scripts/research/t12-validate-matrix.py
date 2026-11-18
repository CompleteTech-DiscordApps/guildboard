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

REQUIRED_MATRIX_FIELDS = {'accessibility_candidate',
 'budget_candidates',
 'contention_candidate',
 'external_rows',
 'fault_corpus_candidate',
 'issue',
 'load_basis',
 'load_profiles',
 'resource_candidates',
 'status',
 'stop_conditions',
 'version',
 'workload_mix_percent'}
REQUIRED_BUDGET_DEFINITIONS = {'cold-launch': {'conditions': 'cold/warm cache separate; <=2MiB initial board serialized data and '
                               '<=1000 objects synthetic initial corpus',
                 'metric': 'user launch to authenticated usable accepted board'},
 'commit-ack': {'conditions': 'baseline, target same-region RTT <=100ms; rejected/conflicting commands '
                              'reported separately; lost/timeout samples remain in denominator',
                'metric': 'same-client monotonic send-to-durable-ACK, all eligible new commands, after '
                          'warmup'},
 'peer-visible': {'conditions': 'baseline; report clock error separately; do not subtract proxy/network '
                                'time',
                  'metric': 'source send to accepted peer projection, instrumented shared clock '
                            'uncertainty'},
 'reconnect': {'conditions': 'after 30s offline, <=500 missed operations, drafts preserved; no false '
                             'ACK',
               'metric': 'transport restored to converged accepted board'},
 'render': {'conditions': 'real desktop/mobile measured separately; background/PIP separate; no '
                          'screen-reader performance inference',
            'metric': 'main-thread frame duration while editing/panning synthetic baseline board'}}
REQUIRED_ACCESSIBILITY_TEXT = {'additional_design_goal': '44x44 CSS pixel outer controls, reduced motion and polite/coalesced live '
                           'feedback; these are proposed design goals, not WCAG AA numeric '
                           'requirements. Canvas two-dimensional reflow exceptions require documented '
                           'review; surrounding UI remains testable.',
 'critical_task_budget': 'zero blockers for supported keyboard and AT tasks; no critical/serious '
                         'automated findings left unexplained; automated scans alone cannot pass',
 'normative_target': 'All applicable WCAG 2.2 A and AA criteria, W3C Recommendation 2024-12-12; actual '
                     'applicability/conformance review pending'}
REQUIRED_ACCESSIBILITY_LISTS = {'checks': {'dragging-alternative',
            'focus-visible-not-obscured',
            'forced-colors-manual-review',
            'keyboard-no-trap',
            'name-role-value-and-status-speech',
            'nontext-contrast-3',
            'outer-controls-reflow-320-css-px',
            'reduced-motion-design-goal',
            'target-size-24-css-px-or-reviewed-exception',
            'text-contrast-4.5-normal-3-large',
            'text-resize-200-percent',
            'text-spacing'},
 'tasks': {'create-edit-move-delete-through-semantic-alternative',
           'launch-auth-enter-board',
           'locate-select-describe-object',
           'navigate-pan-zoom-without-drag',
           'open-close-dialog-and-restore-focus',
           'preserve-draft-on-revoke-and-reconnect',
           'read-policy-denial-and-pending-accepted-rejected-feedback'}}
REQUIRED_FAULTS = {'30 second disconnect and <=500 event tail',
 '5 percent duplicate delivery with same logical ID',
 'commit-before-ACK disconnect',
 'one board policy fence while other guild remains active',
 'snapshot boundary and retained old-lineage receipt retry'}
REQUIRED_RESOURCE_FIELDS = {'available_memory_percent_min',
 'event_loop_delay_p99_ms_max',
 'free_data_disk_percent_min',
 'minimum_measured_commands',
 'note',
 'post_drain_unexplained_rss_growth_percent_max',
 'repeat_runs_min',
 'steady_cpu_percent_max',
 'steady_duration_seconds_min',
 'unexplained_application_error_fraction_max'}

def integer(value, lower, upper, label):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError("invalid bounded integer: " + label)
    return value


def mapping(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError("missing/unknown fields: " + label)
    return value


def text(value, label):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError("missing/invalid text: " + label)


def string_list(value, required, label):
    if not isinstance(value, list):
        raise ValueError("invalid list: " + label)
    for item in value:
        text(item, label)
    if len(set(value)) != len(value) or not set(required).issubset(value):
        raise ValueError("missing/duplicate entries: " + label)


def identified_rows(rows, ids, fields, label):
    if not isinstance(rows, list) or len(rows) != len(ids):
        raise ValueError("missing/duplicate coverage: " + label)
    found = set()
    for row in rows:
        mapping(row, fields, label)
        text(row["id"], label + " ID")
        if row["id"] in found:
            raise ValueError("duplicate ID: " + label)
        found.add(row["id"])
    if found != set(ids):
        raise ValueError("unexpected/missing coverage: " + label)


def validate_contract_shape(matrix):
    """Reject missing sections and malformed values before evaluating arithmetic."""
    mapping(matrix, REQUIRED_MATRIX_FIELDS, "matrix")
    if matrix["issue"] != "GB-T12.R1":
        raise ValueError("unexpected research issue")
    for field in ("load_basis", "contention_candidate"):
        text(matrix[field], field)
    mapping(matrix["workload_mix_percent"], ("modify", "create", "delete", "compound"), "workload mix")
    string_list(matrix["fault_corpus_candidate"], REQUIRED_FAULTS, "fault corpus")
    identified_rows(matrix["load_profiles"], ("small", "baseline", "stress"),
                    ("id", "guilds", "boards_per_guild", "editors_per_board", "viewers_per_board",
                     "operations_per_editor_second", "operation_payload_bytes", "duration_seconds", "gate_candidate"),
                    "load profiles")
    identified_rows(matrix["budget_candidates"], REQUIRED_BUDGET_DEFINITIONS,
                    ("id", "metric", "conditions", "p95_ms", "p99_ms"), "latency budgets")
    for budget in matrix["budget_candidates"]:
        for field, expected in REQUIRED_BUDGET_DEFINITIONS[budget["id"]].items():
            if budget[field] != expected:
                raise ValueError("latency budget definition changed: " + budget["id"] + "/" + field)
    resources = mapping(matrix["resource_candidates"], REQUIRED_RESOURCE_FIELDS, "resource candidates")
    text(resources["note"], "resource note")
    for field, value in resources.items():
        if field == "note":
            continue
        if field == "unexplained_application_error_fraction_max":
            if type(value) not in (int, float) or not 0 <= value <= 1:
                raise ValueError("invalid resource fraction")
        elif "percent" in field:
            integer(value, 1, 100, field)
        else:
            if type(value) is not int or value < 1:
                raise ValueError("invalid positive resource integer: " + field)
    identified_rows(matrix["external_rows"], EXTERNAL_GROUPS,
                    ("id", "environment", "group", "status", "required_evidence"), "external matrix")
    accessibility = mapping(matrix["accessibility_candidate"],
                            set(REQUIRED_ACCESSIBILITY_TEXT) | {"tasks", "checks", "status"}, "accessibility")
    for field, expected in REQUIRED_ACCESSIBILITY_TEXT.items():
        if accessibility[field] != expected:
            raise ValueError("missing/changed accessibility definition: " + field)
    for field, required in REQUIRED_ACCESSIBILITY_LISTS.items():
        string_list(accessibility[field], required, "accessibility " + field)


def validate(matrix):
    validate_contract_shape(matrix)
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
