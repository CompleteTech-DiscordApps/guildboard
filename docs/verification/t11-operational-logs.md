# T11 operational logs and classified errors

[GB-T11.01.01.T1](https://github.com/CompleteTech-DiscordApps/guildboard/issues/360)
implements the API record boundary from the [T11 telemetry v1 contract](../specifications/GB-T11-S1-sre-operations-contract.md#telemetry-v1).
The [T9 audit and incident evidence contract](../specifications/GB-T9-S1-security-privacy-contract.md#audit-integrity-and-incident-evidence)
governs moderation audit, protected incident evidence and their custody.

## API boundary

The boundary returns a frozen record with schema version, UTC, component, event
class and outcome. UTC uses a valid calendar instant with seconds and optional
millisecond precision, for example `2026-11-17T12:00:00Z`. The classified error
constructor uses the same schema and accepts only failure outcomes. Both check
an exact set of enumerable own data fields and return `invalid_record` on
unsafe input. The caller must classify failures at their source with the
declared outcomes. Raw exceptions, stack traces, client correlation values,
headers, free text and request contents are ineligible.

The caller supplies the safe envelope using server-observed UTC and closed
event codes. For correlated records, server code must establish current board
and session authority and retain the same private reference objects for the
journey, board and session. The journey time must come from the same server
monotonic clock as the boundary and represent the first submission. Those
references are server-only capabilities for telemetry association. They do
not confer product authorization. Never construct or select them from
untrusted data outside the governing authority and retry identity checks.

Call `issueCorrelation` on first submission and pass the same scope to record
constructors for later request, operation and board observations in that
journey. The first well-formed scope binds the private journey reference to
its board, session and first submission time, including when issuance fails.
Exact retries can recover from a transient issuance failure within the
original lifetime. Successful issuance keeps the canonical 128-bit random
token in a bounded private process-local table. Exact retries reuse the token
and its fixed deadline. The lifetime starts at the first submission and
expiry is exclusive. An unreferenced host timer reclaims the live mapping
even while the boundary is idle. Monotonic deadline checks on issuance and
lookup also reclaim expired entries when timer dispatch is delayed. A failed
timer cancellation leaves the expired mapping reclaimed and the callback inert. Weak
identity tracking prevents expired journeys from receiving a new token and
lets garbage collection reclaim the identity with its journey. The table
exports only the associated opaque token as part of a valid record. A
different process or boundary has no mapping. The caller must treat a
failed issuance or lookup as observation loss with unknown journey coverage.
It must preserve the original submission and its product outcome
independently of telemetry.

## Collection and access status

The API boundary and internal injected reporter operate in memory. They establish
no approved collector or reporter configuration. Actual collection requires SRE and privacy approval of
mapping bounds, retention trigger and duration, access roster and access
logging, exporter and sampling strategy. The deployment must enforce least
privilege, keep operational logs and moderation audit in separate sinks with
separate access roles, and validate the same closed shape at the proxy and
reporter. The helper below exercises bounded backpressure, component/outcome
accounting and flush mechanics only. Actual exporter behavior, access logging,
retention enforcement and real platform verification remain pending. The
configuration supplied by the local tests is synthetic.

## Internal injected reporter

The [maintainer design claim](https://github.com/CompleteTech-DiscordApps/guildboard/issues/360#issuecomment-6970252668)
selects `apps/api/src/operational-log-reporter.ts`. It owns its
`createOperationalLogBoundary` instance, so a caller cannot hand it an arbitrary
`OperationalLogV1` with a syntactically valid correlation and claim provenance.
Use the same server-owned boundary configuration and private scope rules above.
The module is internal, absent from the package entrypoint, and has no service
startup, default sink, file/network output, retry or sampling integration.

| Operation | Result and lifecycle |
| --- | --- |
| `issueCorrelation(scope)` | Existing boundary issuance; unavailable or closed returns `coverage_unknown`. |
| `report(input, scope?)` | Builds a frozen allowlisted record and returns `queued`, `invalid_record`, `coverage_unknown`, `saturated` or `closed`. |
| `reportError(input, scope?)` | Same path, using the existing classified-error constructor; success and raw exceptions are rejected. |
| `snapshot()` | Immutable occupancy, capacity, bounded counters and component/outcome rows; contains no scope objects or correlation values. |
| `flush(budgetMs, signal?)` | Waits for drain within the positive integer budget. A normal drain leaves admission open; deadline or cancellation seals it permanently. |
| `close(budgetMs, signal?)` | Seals admission synchronously and returns a shared bounded flush completion. Repeated close calls return that same promise. |

Configuration, sink, budgets and abort signals are trusted server-owned ports.
Capacity is an integer from 1 through 4096 and includes the single active sink
call. `counterLimit` is a positive safe integer. Flush budgets are at most
2,147,483,647 milliseconds, the host timer limit. These are explicit synthetic
mechanics limits, **not an approved operational profile**. No product latency,
queue capacity or retention policy is selected here.

Only immutable records constructed by the owned boundary enter the queue.
Delivery is ordered, with at most one sink call awaiting actual settlement.
Overflow rejects the new observation. Synchronous throws, rejected promises
and thenable failures are counted without reading or forwarding the error.
Counters distinguish rejected invalid/closed submissions, saturation, lost
observations and resolved sink calls (`delivered`). Valid record classifications
allocate at most 90 component/outcome rows from the existing closed enums;
invalid input and unavailable scope contribute only to totals. Counters clamp
at `counterLimit`; `countsCapped` records attempted overflow. They count local
attempts, including failed correlation issuance, not distinct product journeys.

Every loss makes coverage permanently `unknown` for that reporter. Otherwise
`no_loss_observed` means only that this instance has observed no loss; it does
not prove complete journey coverage. Sink resolution is not protected storage
or end-to-end delivery evidence. The `drained` flush result only means retained
deliveries have settled, and can accompany unknown coverage after sink failure.
Original authorization, commit-unknown and other product outcome classifications
remain untouched; counters cannot authorize actions, ACK writes or cause rollback.
Moderation audit remains a separate T9 boundary and sink.

Concurrent flush/close calls share the first pending flush's budget and signal;
there is only one timer/listener waiter. Deadline or cancellation returns
`deadline_elapsed` or `interrupted`, discards queued observations as loss and
aborts the active sink. A noncooperative sink retains its one occupied slot
until it actually settles. No replacement or retry starts, and even late success
cannot change its unknown delivery outcome to observed success. Closing does
not reset existing correlation mappings; those remain subject to their original
bounded expiry. Sinks must cooperate with abort and avoid blocking the event loop;
synchronous blocking or a stalled process can delay all timer dispatch.

A future approved shutdown adapter can await `close(budgetMs, signal)` inside
the existing coordinator's `flushTelemetry` callback and handle its finite
result. Coordinator callback completion alone does not imply successful log
delivery. The focused suite exercises this composition with synthetic callbacks;
no actual host integration or collection is enabled.

## Local evidence

Linux x86_64 with Node.js v24.22.3. On base
`7efd107d72c298a796ba57bd997a1920c8ad6c68` plus the expiry remediation,
`node --test tests/engineering/t11-operational-logs.test.mjs` passed 12
tests. The suite compiles the API workspace into a temporary directory and
exercises record and classified error acceptance, unsafe payload rejection
with accessor and proxy traps left untouched, server-issued scope binding,
mapping capacity, idle and synchronous expiry, first-identity enforcement,
exact retries, clock and scheduler failure, and no stdout or stderr writes.
`npm run lint` passed. This is offline API-boundary evidence. Hosted and
real-platform acceptance require their own evidence.

For the reporter slice over base `5213b52753dbb25ace3d94bab70a1eed3f959684`,
use Linux and Node 24 with locked dependencies:

```sh
npm ci --offline --ignore-scripts
node --test tests/engineering/t11-operational-log-reporter.test.mjs
node --test tests/engineering/t11-operational-logs.test.mjs tests/engineering/t11-graceful-shutdown.test.mjs
npm run lint
npm run typecheck
npm run format:check
npm run boundaries
npm run test:engineering
npm run build
git diff --check
```

The 11 reporter tests cover finite configuration, occupancy including the active
record, ordered slow delivery, overflow, counter saturation/cardinality, original
correlation provenance, immutable output, unsafe/accessor/proxy input with no
trap or sink effects, throws/rejections, hung sinks, cancellation, shared bounded
flush/close, late settlement, synthetic shutdown composition and no stdout/stderr
output. The PR records exact-head results. Architecture-control integration and
independent functional/security review remain separate gates. This partial #360
slice does not complete retention, access, protected collector, producer, proxy,
exporter or real-platform acceptance requirements.
