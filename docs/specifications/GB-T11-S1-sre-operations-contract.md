# GB-T11.S1 SRE operations contract v1

Status: specification candidate for [#357](https://github.com/CompleteTech-DiscordApps/guildboard/issues/357).
The [research](../research/t11-sre-objectives.md) merged in #496 and #356 closed.
The target is Guildboard on a GoDaddy Linux VPS with Nginx HTTPS/WSS, private
database and persistent assets. The contract defines observable boundaries for
consumers. Implementation, owner approval and acceptance on the target are
pending. Numeric hypotheses below are internal trials with no SLA commitment.

The [accepted GB-T0.S1 system contract](GB-T0-S1-system-contract.md) governs
receipt and read-release ordering. Its original status header is archival.
The [T0 evidence and handoff](../workstreams/T0.md#evidence-and-handoff)
records the accepted boundary in
[#481](https://github.com/CompleteTech-DiscordApps/guildboard/pull/481#issuecomment-6919558260)
and its protected integration handoff in
[#521](https://github.com/CompleteTech-DiscordApps/guildboard/pull/521).

## Telemetry v1

| Record | Required fields and bounds |
| --- | --- |
| Metric | Schema version 1, UTC interval, fixed signal name and declared finite dimensions only, nonnegative count/gauge or cumulative histogram counts with a fixed bucket set and total. Latency uses milliseconds; storage, queue and memory use bytes or item counts as named; saturation uses explicit capacity denominators. |
| Operational log | Schema version 1, UTC timestamp, component (Activity, API, bot, collaboration, persistence, edge, host, recovery, probe), event class (journey, dependency, admission, durability, lifecycle, backup, restore), classified outcome and optional 128-bit opaque correlation token. No arbitrary metadata or free text. |
| Restricted evidence | Schema version 1, authorized evidence reference, test/incident window, build and environment/profile references, checks and classified outcomes. Recovery evidence may contain scoped synthetic canary and cut references. Access decisions are audited through the governing security and audit contracts. |

Outcomes are closed by record class: success, invalid input, authorization denied,
dependency unavailable, saturated, deadline elapsed, commit unknown, coverage
unknown, interrupted or integrity failed. Reject unknown fields/enum values and
invalid units/types before export. Validate values as well as field names:
timestamps must be valid UTC, categorical values must come from the declared
record enums, and a correlation value must be server-issued and in the
canonical 32-character lowercase hexadecimal encoding. A client value is
ineligible even when it fits the correlation syntax. Reject unsafe values
without echoing them to the sink. Report bounded counts by component and
failure class. Use the same allowlist at error reporters, reverse proxy and
exporters. Never interpolate raw exception messages, headers, paths, query
strings, bodies, asset filenames, board content, credentials, connection URLs,
Discord identifiers, tenant/board IDs, raw operation IDs or digests. Operational
logs and moderation audit use separate access roles and sinks. Access requires
least privilege, with approved limits on retention and access logging before
enabling collection. Retention duration, exporter, access roster and sampling
strategy require SRE and privacy approval. Safety counters and probe accounting
must survive sampling or report missing coverage.

Metric names use a fixed registry covering board-open/edit/reconnect and probe
outcomes, operation and journey latency, active sockets/boards, admission and
output depth/capacity, CPU used/allocatable CPU, resident memory/allocatable
memory, persistent disk used/usable bytes, database health, backup age and backup
job outcomes. Permitted dimensions are component, declared signal-specific
outcome, and fixed solo/collaborative/unknown or cold/warm/unknown cohorts where
applicable. No correlation token, per-guild label, raw identifier, profile URL or
dynamic dimension. The registry must publish units, finite dimension products,
series upper bounds and histogram buckets before shipment. Require exactly
the dimensions declared for the signal and reject out-of-domain values and
undeclared combinations before export. An invalid signal or label cannot
create a series. Synthetic canaries use only generated data in the approved
synthetic scope. A canary reference may appear only in authorized restricted
evidence, never as a metric dimension or operational log value.

Correlation uses a server-issued random token scoped to one journey and
authorized board/session context. Never treat it as authentication. Keep the
mapping private and ephemeral. Retries use the same internal logical identity
even where pre-admission fails. Cap mapping size and lifetime using reviewed
workload and deadline bounds. On missing mappings or exporter saturation,
count observation loss and mark affected journey coverage unknown. A lost
overload response cannot erase the first submission. Telemetry failure must
neither grant access nor determine acknowledgement, rollback or authorization.

## Indicators and alert evaluation

Record the first attempt's UTC reporting window and elapsed time on one trusted
monotonic clock per journey. Report good, bad, unknown, exclusions by finite
reason, eligible total, histogram counts, scheduled/missing observations and
window/profile on every evaluation. The eligible total includes good, bad and
known eligible unknown outcomes. If eligibility itself is unknown, count that
separately outside the eligible denominator. Explicit authorization denial
is a separate exclusion. Dependency failure counts bad when other eligibility
criteria, including authorization, are already established by trusted evidence.
If dependency failure prevents that determination, count unknown eligibility
and do not infer denial. Rate is undefined at zero eligible attempts. With unknown coverage,
report the conservative interval from good / eligible to (good + unknown) /
eligible, then disclose unknown-eligibility observations separately. A window
with missing coverage cannot pass acceptance. Finalize after the relevant
deadline. Record raw attempt overload and retries independently from logical
user journeys.

- Board open starts at supported client launch and ends with current usable
  board and required assets. Report cold/warm separately. Authorized supported
  in-profile attempts count. An otherwise eligible request blocked by a
  dependency failure counts bad. Explicit abuse, authorization denial and
  out-of-profile inputs have separate counters. Planned maintenance and Discord
  dependency failures count in the end-to-end observation.
- Edit counts once at first in-profile submission for admission. Authorization
  and accepted input/workload criteria govern eligibility independently of
  admission. Good requires the durable receipt received by the sender by the
  original deadline. A collaborative edit also requires correlated observation
  from the fixed measurement peer by that deadline. Pick the first eligible
  synchronized, authorized peer by server room-join order at first submission.
  Keep the peer fixed through disconnect or retry. Trusted peer echo is timed
  by the sender's monotonic clock. If no eligible peer exists, record solo.
  Missing evidence of peer eligibility is unknown coverage. Deadline expiry
  with complete observation and no confirmed peer observation is bad.
- Standalone reconnect starts at disconnect and ends at authorized resume with
  current state. No edit sample is allocated. Server diagnostic latency starts
  at authorized ingress and ends at durable receipt availability, independently
  of client delivery. Report latency histograms with outcome counts and
  throughput. A timeout during commit produces a commit-unknown outcome, whose
  reconciliation follows the [system contract](GB-T0-S1-system-contract.md).
  Preserve scope, original identity, digest and preconditions. Verify current
  session, membership and scoped read authority before any receipt or digest
  lookup. Check them again using trusted time at the serialized release fence,
  including for a digest-dependent result. Revocation, expiry or invalidation
  ordered first suppresses that result. A matching retained receipt can settle
  the historical commit even if write authority was revoked. Denial, changed
  digest or unavailable read leaves the original outcome unknown. After a
  disaster recovery gap, an authorized no-match or a nonrecoverable receipt
  likewise leaves the original outcome unknown. Receipt recovery never
  retransmits the operation or creates a new identity, logical mutation,
  revision or broadcast. A retired-lineage receipt settles historical commit
  only. Rejoin and validate the current lineage before reporting its save
  state. A user may deliberately discard stale intent or submit a distinct
  current-lineage intent through the ordinary write authorization and
  precondition checks.
- External probe uses a controlled synthetic tenant and real HTTPS/WSS with
  authorized open/write/read. Count each scheduled minute once. Failed and
  missing probes are bad, including scheduled maintenance. The probe indicator
  stays independent from request rates and supplies independent coverage.

| Candidate evaluation rule | Trigger and response | Observable recovery signal |
| --- | --- | --- |
| Journey objectives | Separately for board-open, edit and probe, 99.5% good over rolling 30 days. Good board-open by 5 seconds, good edit by 1 second. A closed window strictly below target opens an SRE investigation. At 43,200 scheduled probe minutes, 216 bad still meets the candidate, 217 breaches. | A fresh, complete rolling window for that journey meets the target at the approved minimum volume. |
| Fast journey and probe detection | Provisional exercise rules: alert after 3 consecutive failed/missing scheduled minutes or 2 consecutive closed 5-minute journey windows with ≥20 eligible observations each and >5% known bad each. Coverage gaps open a separate telemetry incident after 2 consecutive incomplete 5-minute windows. Insufficient traffic yields no rate page. Use the independent probe during low/no traffic. | Fast probe requires a fresh approved run of successful scheduled minutes. Fast journey requires fresh, consecutive, complete windows at approved minimum volumes within the configured bad-rate limit. The coverage incident requires fresh, complete coverage windows. |
| Latency/capacity | Pilot candidate p95/p99 durable receipt ≤100/250 ms, peer echo ≤250/500 ms, board-open ≤3/5 seconds at declared cohort/profile. Open capacity investigation after two consecutive complete 5-minute in-profile windows breaching either applicable percentile or research headroom (CPU ≥60%, resident memory or persistent disk ≥70%). Report observed counts and test with approved minimum sample sizes. Queue saturation uses the approved queue capacity and explicit rejection counter; no accepted durable work is dropped. | Fresh, consecutive, complete in-profile windows with sufficient samples meet the latency and resource recovery limits. For queue saturation, measured depth meets the approved recovery level and rejection counters show no saturation during the recovery windows. |
| Backup/recovery | Any failed or interrupted job, missing expected job by approved finish deadline, unverifiable chain or freshness beyond approved maximum opens an operations investigation. Integrity failure, unsafe restore destination or known loss of acknowledged data outside the stated trial boundary escalate immediately. Both job deadline and maximum freshness require T5/T10/SRE approval. | A newly verified job completed on schedule, has an intact chain and meets freshness. For integrity, isolation or acknowledged loss, also require responder acknowledgement and an isolated, independently verified rehearsal with a recorded loss disposition. |
| Restart and disaster drill | Candidate ≤60 seconds from process fault to authorized read/write and peer convergence, with zero acknowledged loss. Disaster hypothesis RPO ≤15 minutes and RTO ≤4 hours for the 30 GiB research workload. Breach either measured objective or fail any mandatory integrity/isolation check to fail the drill. | After remediation, a fresh independent drill of the failed type verifies authorization, integrity and isolation, measures every objective and meets each trial boundary. |

Candidate comparisons use complete, aligned windows and declared minimum volumes.
Deduplicate by rule and affected deployment, preserve earliest trigger time,
route with a bounded reason and runbook reference, and escalate unacknowledged
pages by the approved rota. Clear each active rule only after observing its
recovery signal for the same deployment, rule and approved workload profile. Evidence must come from the
approved source and be newer than the last breach, within the configured
freshness bound, complete, and sufficient for the approved recovery window
count, duration, and minimum samples. Stale, missing, partial or inapplicable
evidence keeps the alert open. Suppressing duplicate notifications cannot exclude observations from
SLIs. Require approved configuration for evaluation and recovery: enabled state,
sources, profile, thresholds, sample counts, window lengths, freshness,
consecutive windows and routing. Validate disabled, malformed, inconsistent
or missing configuration with names-only diagnostics. The affected evaluator
reports loss of coverage, emits no candidate verdict or page, and cannot
clear an active alert. Independent service protection, including authorization,
isolation and integrity guards, continues to enforce its own policy. SRE and QE
must reconcile the #356 workload and #388 QE candidate before approving a shared
profile. Alert routing, progression/cooldown and numeric policies require pilot
observations and owner approval.

## Independent backup and restore acceptance

A backup attempt passes when its authenticated encrypted artifacts are readable
by the designated recovery role, the consistent database cut has a complete
required replay range, all asset versions referenced at that cut are included or
recoverable, and integrity verification is complete. Record job schedule,
start/end, cut and first/last required replay position, manifest and integrity
status, off-host availability, and key recovery check. Keep backup/restore roles
separate from serving credentials. The copy must survive loss of the source
VPS. Missing prerequisite is blocked; interruption leaves the attempted
generation incomplete and recovery uses only prior verified generations until
revalidation. Job completion and backup age are independent of restore verdict.

Restore rehearsals use fresh isolated resources and synthetic canaries.
Prove target identity, actual write/read isolation, distinct scoped recovery
credentials and absence of production routing before opening artifacts or
applying mutations. Demonstrate an isolation marker inside the authorized
target and verify source/production-equivalent guard markers remain unchanged.
A name, claimed flag or mount label alone cannot prove isolation. Apply the
governing accepted [system contract](GB-T0-S1-system-contract.md) and the
security contract once accepted ([#534](https://github.com/CompleteTech-DiscordApps/guildboard/pull/534),
informational handoff). Do not probe production to prove a drill target's isolation.

Before exposure, reconcile authoritative deletion markers and their high-water
mark from an independent source. Verify contiguous coverage from the backup's
applied cut through a serialized exposure fence, or recheck and reconcile
under an equivalent fence. Reapply current revocations and verify deleted or
revoked content, assets, exports and references remain inaccessible. Missing,
stale or gapped evidence or a later unapplied marker keeps the target isolated.
These deletion markers are distinct from the synthetic target isolation marker.

Verify manifest authenticity, decryption/key recovery, replay continuity,
consistent cut and lineage, database hashes, referenced assets, and authorized
read/write and convergence with a negative cross-scope check. Quarantine partial
output and restart from an independently verified cut after an interrupted
restore. Corruption, missing keys/assets/logs, lineage mismatch, incomplete
verification and unexpected scope access all fail acceptance. Record a denied
preflight with zero destination writes.

Use one trusted UTC timeline for declaration, incident/fault and recovered
canary commit. Choose the latest consistent restored synthetic canary whose
original pre-fault durable commit and restored lineage/cut match trusted
evidence. RPO is incident/fault time minus that original commit time. Exclude
inconsistent, unverified, post-fault and unrestored canaries. Copy, replay and
restore execution timestamps cannot serve as original commit evidence. Count acknowledged operations lost, report the tested
loss boundary, and treat untrustworthy timing or absent canary as unknown.
RTO is elapsed time from declaration through access/key recovery, restore and
service verification over approved DNS/TLS and client paths, including operator
waits. Use monotonic elapsed timing when available and record clock provenance.
Report each measure and its individual outcome independently as within the
candidate, breached or unknown. Any known objective breach fails the drill,
including when the other measure is unknown. After mandatory checks pass,
unknown timing without a known breach leaves the trial undetermined. Both
objectives must be known and within their boundaries to pass.
A local model, snapshot age, copy timing or intact backup cannot certify RPO/RTO.

## Incident roles and handoffs

| Role | Responsibility |
| --- | --- |
| SRE on-call / incident commander | Own intake, deduplication, severity, declaration time, incident timeline, responder assignments, recovery decision and review. Declare service incidents for sustained user impact; escalate suspected data loss, disclosure or compromised credentials immediately. |
| T10 deployment responder | Own service/edge/Nginx/supervisor diagnosis and authorized rollback, drain, restore environment and platform evidence. Stop admission before shutdown, settle/drain accepted work or preserve commit-unknown reconciliation, reconnect clients and verify readiness. |
| T4/T5 collaboration and persistence responders | Own reconciliation and deduplication evidence, backup chain, consistency and restore integrity, loss assessment and board/asset verification. |
| T9 security responder | Own credential revocation, isolation, restricted evidence preservation and private disclosure routing via SECURITY.md. Security-sensitive raw diagnostics stay in separately authorized evidence storage. |
| Communications owner and QE | Communications owner issues approved audience updates and closes the communication loop. T12 QE validates scenarios, coverage and reproducible receipt evidence; SRE records actions and owners at handoff. |

The actual named rota, severity deadlines and notification channels require
maintainer approval and a handoff rehearsal with acknowledgement and alternate
owner. Closure requires verified recovery, known data-loss boundaries or an
explicit unresolved item, a restricted record and accountable follow-up.
T1/T8 own client/edge measurement integration, T7 client status, T2 moderation
audit semantics, T9 telemetry privacy, T4/T5 durability and asset cut, T10 real
supervisor/GoDaddy checks and T12 workload and acceptance evidence. SRE owns
candidate policy, Product owns objective commitments, and CODEOWNERS and
consuming engineering review precede implementation.

## Evidence

The [bounded v1 scenarios](fixtures/GB-T11-S1-scenarios.json) and focused
verification exercise offline contract logic, including invalid configuration,
dependency failure and interrupted work. Real collection overhead, protected
sink configuration, candidate threshold fitness, registered Discord
desktop/mobile journey coverage, GoDaddy capacity and restart, backup
retention/key policy and actual isolated restore remain unobserved. Evidence
must identify the exact build, profile, platform, time window, command/results
and reviewer. Production acceptance remains pending.
