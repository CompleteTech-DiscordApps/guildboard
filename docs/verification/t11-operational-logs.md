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

The API boundary builds records in memory. It establishes no collector or
reporter configuration. Actual collection requires SRE and privacy approval of
mapping bounds, retention trigger and duration, access roster and access
logging, exporter and sampling strategy. The deployment must enforce least
privilege, keep operational logs and moderation audit in separate sinks with
separate access roles, and validate the same closed shape at the proxy and
reporter. Exporter backpressure, aggregation by bounded component and failure
class, loss accounting, access logging, retention enforcement and real
platform verification are pending. The configuration supplied by the local
tests is synthetic.

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
