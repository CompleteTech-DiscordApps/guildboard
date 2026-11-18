# Operational metric records v1

The [T11 telemetry contract](../specifications/GB-T11-S1-sre-operations-contract.md#telemetry-v1)
defines the API record boundary for [#363](https://github.com/CompleteTech-DiscordApps/guildboard/issues/363).
The [T9 privacy inventory](../specifications/GB-T9-S1-security-privacy-contract.md#privacy-inventory)
governs access, retention and incident holds.

Call `parseOperationalMetricV1(record, approvedBuckets)` with decoded,
ingress-bounded plain data. It returns a frozen record with copied dimensions
and histogram arrays, or `undefined` on rejection. Consumers can count
rejections independently with fixed classifications. Capture both interval
endpoints as UTC calendar timestamps with seconds and optional three-digit
milliseconds. The end must follow the start. The signal and its declared
label tuple identify the series.

## Registry

`OPERATIONAL_METRICS_V1` publishes the unit, kind, exact dimensions, allowed
values, maximum finite bucket count and series bound for each signal.

| Signal | Kind and unit | Required dimensions | Series |
| --- | --- | --- | ---: |
| `board_open_outcome` | Counter, items | Journey outcome × open cohort | 21 |
| `edit_outcome` | Counter, items | Edit outcome × edit cohort | 24 |
| `reconnect_outcome` | Counter, items | Journey outcome | 7 |
| `probe_outcome` | Counter, items | Probe outcome | 4 |
| `operation_latency` | Histogram, milliseconds | Operation outcome | 6 |
| `board_open_latency` | Histogram, milliseconds | Journey outcome × open cohort | 21 |
| `edit_latency` | Histogram, milliseconds | Edit outcome × edit cohort | 24 |
| `reconnect_latency` | Histogram, milliseconds | Journey outcome | 7 |
| `probe_latency` | Histogram, milliseconds | Probe outcome | 4 |
| `active_sockets`, `active_boards` | Gauge, items | Component `collaboration` | 1 each |
| `admission_depth`, `admission_capacity` | Gauge, items | Component `api` or `collaboration` | 2 each |
| `output_depth`, `output_capacity` | Gauge, items | Component `collaboration` | 1 each |
| `cpu_used`, `cpu_allocatable` | Gauge, millicores | Component `host` | 1 each |
| `resident_memory`, `allocatable_memory` | Gauge, bytes | Component `host` | 1 each |
| `persistent_disk_used`, `persistent_disk_usable` | Gauge, bytes | Component `host` | 1 each |
| `database_health` | Gauge, boolean encoded as 0 or 1 | Component `persistence` | 1 |
| `verified_recovery_point_age` | Gauge, milliseconds | Component `recovery` | 1 |
| `backup_job_outcome` | Counter, items | Backup outcome | 6 |

- Journey outcomes are `success`, `invalid_input`, `authorization_denied`,
  `dependency_unavailable`, `saturated`, `deadline_elapsed` and
  `coverage_unknown`. Edit outcomes add `commit_unknown`.
- Probe outcomes are `success`, `dependency_unavailable`,
  `deadline_elapsed` and `coverage_unknown`.
- Operation outcomes are `success`, `dependency_unavailable`, `saturated`,
  `deadline_elapsed`, `commit_unknown` and `coverage_unknown`.
- Backup outcomes are `success`, `dependency_unavailable`,
  `deadline_elapsed`, `coverage_unknown`, `interrupted` and `integrity_failed`.
- Open cohorts are `cold`, `warm` and `unknown`. Edit cohorts are `solo`,
  `collaborative` and `unknown`.

Counters and gauges carry a nonnegative safe integer `value`. Histograms
carry `buckets`, `counts` and `total`. The caller supplies the independently
approved bucket layout by histogram signal from trusted configuration. Hold
that layout fixed for the lifetime of a collection and export configuration.
Each layout has 1 to 32 strictly increasing nonnegative safe integer upper
bounds in milliseconds. The record must reproduce the approved layout in
order. Counts are cumulative through their inclusive bound. The total
includes observations above the last finite bound. Empty observations use
zero counts and a zero total. If an exporter materializes a series for each
finite cumulative count and one more for the total, its per-signal bound is
the label product × (finite bucket count + 1). Publish
the actual approved layouts before enabling a sink.

## Local verification

Run from the repository root with Node 24 and the locked dependencies.

```sh
npm ci --offline --ignore-scripts
node --test tests/engineering/t11-operational-metrics.test.mjs
python3 -B tests/verification/test_t11_sre_operations_contract.py -v
```

The tests enumerate the registry against independent per-signal series
counts, reject dynamic identifiers and malformed records, check histogram
consistency, and exercise import and parsing with restricted local process
permissions and synthetic ambient-call guards. Evidence covers record
validation and offline specification scenarios. Live collectors and
measured alert configuration for #363, approval of bucket layouts and
operational thresholds, protected sink setup, and Discord and GoDaddy
acceptance for #364 require separate evidence.
