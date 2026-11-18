# Operational metric records v1

The [T11 telemetry contract](../specifications/GB-T11-S1-sre-operations-contract.md#telemetry-v1)
defines the API record boundary for [#363](https://github.com/CompleteTech-DiscordApps/guildboard/issues/363).
The [T9 privacy inventory](../specifications/GB-T9-S1-security-privacy-contract.md#privacy-inventory)
governs access, retention and incident holds.

Create one parser per collection and export configuration with
`createOperationalMetricParserV1(approvedBuckets)`. The factory returns
`undefined` if any layout is invalid. A successful parser accepts one argument,
a decoded, ingress-bounded plain-data record, and returns a frozen record
with copied dimensions and histogram arrays, or `undefined` on rejection.
Consumers can count rejections independently with fixed classifications.
Capture both interval endpoints as UTC calendar timestamps with seconds and
optional three-digit milliseconds. The end must follow the start. The signal
and its declared label tuple identify the series.

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
approved bucket layouts by histogram signal from trusted configuration at
setup. The factory copies and freezes the layouts for the lifetime of the
parser. Histograms require a configured layout for their signal. Omit the
configuration or pass an empty object to accept counters and gauges only.
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
consistency and fixed layouts across records, and exercise import and parsing
with restricted local process permissions and synthetic ambient-call guards.
Evidence covers record validation and offline specification scenarios. Live collectors and
measured alert configuration for #363, approval of bucket layouts and
operational thresholds, protected sink setup, and Discord and GoDaddy
acceptance for #364 require separate evidence.

## Private offline interval recorder

The internal `apps/api/src/operational-metric-recorder.ts` helper adds bounded
accumulation for the [maintainer design claim](https://github.com/CompleteTech-DiscordApps/guildboard/issues/363#issuecomment-6970252911).
It has no package entrypoint export, producers, timers, host probes or sink.
`createOperationalMetricRecorderV1(startUtc, endUtc, approvedBuckets?, maxSeries?)`
returns `undefined` for invalid setup. Both endpoints must satisfy the existing
v1 parser. One recorder owns exactly that supplied interval; create a new one
for a new interval. No clock, interval rotation, finalization or schedule is
inferred. The caller remains responsible for trusted timing and interval use.

The helper reuses `OPERATIONAL_METRICS_V1` and
`createOperationalMetricParserV1`. The configured layouts are validated and
copied at construction; later caller changes cannot enable a histogram or
change its buckets. Omitted layouts disable their histograms. Synthetic
one-bucket layouts are used internally only to validate rejected disabled
histograms' labels, never to enable recording or populate a snapshot.
Explicit synthetic mechanics profiles in tests are not approval of production
bucket sizing, collection or thresholds.

| Method | Local behavior |
| --- | --- |
| `increment(signal, dimensions, amount = 1)` | Add a nonnegative safe integer to a counter. |
| `setGauge(signal, dimensions, value)` | Replace a gauge with a nonnegative safe integer; boolean gauges accept only 0 or 1. |
| `observe(signal, dimensions, sample, occurrences = 1)` | Add a nonnegative safe integer millisecond sample, optionally repeated a positive safe integer number of times. Each inclusive finite bound at or above the sample increases by `occurrences`; total increases even above the last bound. |
| `reportMissing(observations = 1)` | Record a positive safe integer number of caller-known missing observations. This never creates a successful metric. |
| `snapshot()` | Return a frozen array of detached, frozen existing `OperationalMetricV1` records for allocated series. |
| `status()` | Return frozen local accounting with fixed fields and rejection classes; this is not a metric wire record or an SLI verdict. |

Updates return `true` when applied and `false` on rejection. Signal kind,
exact dimensions and values are checked before retaining any new series.
Nonplain, accessor and proxy inputs are rejected without invoking caller code.
Overflow, invalid input and capacity rejection leave every retained metric
unchanged. Gauges replace values rather than adding them. Counter zero updates
are permitted. Histograms reject zero occurrences. Retained series are keyed
by the signal and parser-normalized label tuple, so dimension property order
cannot create duplicates.

The optional `maxSeries` is a nonnegative safe integer no larger than the sum
of the registry's published series bounds; its default is that sum. Zero
rejects all new series. Reaching the cap leaves existing series updateable.
All layouts have the parser's existing maximum of 32 finite buckets. The
recorder cannot extend registry cardinality or add labels, identifiers or
arbitrary metadata. Snapshot copies are bounded by the same retained series
and bucket limits; callers own the number of snapshots they retain.

Status reports `allocatedSeries`, `maxSeries`, `acceptedUpdates`,
`reportedMissing`, fixed `rejected` counts (`invalid`, `disabled`, `capacity`,
`overflow`), `lossDetected`, `accountingSaturated` and `coverage`. Accepted and
rejected counts measure method calls, not inferred journey counts or histogram
multiplicities; `reportedMissing` measures explicitly reported observations.
Accounting saturates at `Number.MAX_SAFE_INTEGER` with sticky
`accountingSaturated = true` if an addition would overflow. Any rejection or
reported missing observation sets sticky `lossDetected = true`. Successful
updates cannot clear it. Accounting contains no supplied labels or values.
`coverage` always remains `unknown`: an empty snapshot is not observed zero,
and a recorder cannot establish expected observations, eligibility,
deduplication, successful delivery or complete coverage. Callers must report
known gaps and independently establish all coverage required by the accepted
T11 contract. Losing the recorder itself also loses its local accounting;
there is no persistence, flush, export or crash-survival claim.

Run `npm run build`, then
`node --test tests/engineering/t11-operational-metric-recorder.test.mjs` and the
existing parser test above. The focused suite checks inclusive boundaries,
above-last totals, disabled histograms, full finite tuple enumeration, capacity,
invalid shapes/values, atomic overflow rejection, immutable interval snapshots,
configuration isolation and saturating loss accounting. Its restricted-process
case exercises offline mechanics with synthetic ambient-call guards. These
checks establish no real producer, collector, retention/access policy,
production bucket approval, measured alert budget, SLO, Discord or GoDaddy
behavior. Actual instrumentation, approved collection/retention/bucket/alert
policies and real delivery remain blocked. Fresh review, architecture-control
integration, native CI and post-merge acceptance remain separate gates; this
partial slice does not complete or close #363.
