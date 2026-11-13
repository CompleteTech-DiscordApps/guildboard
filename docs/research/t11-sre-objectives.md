# GB-T11.R1: proposed reliability objectives and baseline plan

Status: research recommendation awaiting actual review and acceptance. Related
issue: [#356](https://github.com/CompleteTech-DiscordApps/guildboard/issues/356);
parent [#355](https://github.com/CompleteTech-DiscordApps/guildboard/issues/355).
Prepared 2026-10-26 UTC (2026-10-25 America/New_York), against repository base
`c108b552a660e12a3b3998e1e1ad944fbd7a894d`.

Guildboard is an application scaffold. These are proposed internal objectives,
not measured product results, a customer SLA, an accepted runtime contract, or
authorization to provision anything. The local experiment below tests research
fixtures only. No Discord client, GoDaddy VPS, SQL service, monitoring stack or
backup service was contacted or deployed by the experiment.

## Scope and live boundary checks

At research start, live #356 had no execution blockers, claim or comments, and
the open PR search for T11 returned none. A scoped writer claim was posted as
[comment 6405796591](https://github.com/CompleteTech-DiscordApps/guildboard/issues/356#issuecomment-6405796591).
Native dependencies showed [#357](https://github.com/CompleteTech-DiscordApps/guildboard/issues/357)
blocked by #356. That specification and all downstream implementation/acceptance
remain gated. This document proposes measurement semantics for its consideration;
it does not adopt telemetry schemas, queue sizes, protocol fields, database
schema, topology or supervisor configuration.

T5 [draft PR #490](https://github.com/CompleteTech-DiscordApps/guildboard/pull/490),
head `5e8a9fe999e0ef6db5509ad4075e324da6c2be79`, contains provisional database
research reportedly exercised on MySQL 8.4.11 / MariaDB 11.4.13. Those results
were not rerun here and are not accepted database contracts. T1
[draft PR #491](https://github.com/CompleteTech-DiscordApps/guildboard/pull/491),
head `8a56a58b0a57cd9e467b90f8a2bb043e63a67547`, remains provisional; registered
application/client inputs needed for real Discord verification are missing.
The heads and draft/open states were read live; cross-lane result details are
coordination inputs, not independent evidence produced by T11.

## Expected use is a synthetic hypothesis

No product analytics, customer research, registered client or VPS measurements
establish expected demand yet. Use this bounded starting envelope for T12/T10
planning, and replace it after pilot measurements and owner approval:

| Dimension | Synthetic assumption and rationale |
| --- | --- |
| Tenancy | Catalog of 100 guilds; 10 simultaneously active boards, one per active guild for the first test. Include multiple boards in one guild and one hot board in later fairness tests. |
| Connections | 10 connections per active board = 100 sockets; 2 active writers per board = 20 writers, remaining clients receive updates. |
| Mutations | 5 small operations/writer/second = 100 offered operations/second. Fixture payload content is 2 KiB, not an accepted operation limit. |
| Broadcast cost | 100 operations/second × 9 peers × 2 KiB = 1.76 MiB/second outbound before envelopes, TLS, retries and assets. No fanout is executed by the local model. |
| Bursts | 10 seconds at 1,000 operations/second, then return to 100; separately reconnect all 100 sockets over 30 seconds with jitter. These are stress cases, not promised supported rates. |
| Board open/assets | 2,000 synthetic elements, 2 MiB serialized board plus eight 1 MiB assets (10 MiB total); test empty and maximum accepted boards once T3/T4/T5 define limits. |
| Storage | Future restore rehearsal: 10 GiB database plus 20 GiB assets, with a separate growth run. These sizes are test assumptions, not disk inventory. |
| Duration | Real baseline: 5-minute warmup, 15 minutes at 100 operations/second, 60-minute mixed session, then 8-hour soak at measured normal load. Local virtual baseline covers 60 seconds only. |

At a hypothetical sustained 100 × 2 KiB operations/second, operation content
alone grows 16.48 GiB/day before indexes, receipts, snapshots, binary logs and
assets; at 8 hours/day it is 5.49 GiB/day. Do not size retention from socket count.
T5 must quantify compaction and history needs before any storage purchase.

## Proposed objectives and how to measure them

The values below are engineering hypotheses chosen for an interactive drawing
pilot on the required single GoDaddy Linux VPS target, with maintenance and
dependency failures visible. They are **not inferred from the local file timings**.
The SRE workbook recommends iterating user-facing indicators and objectives
with stakeholders; it does not prescribe these Guildboard numbers. [S1]

| Objective | Proposed initial value | Measurement and acceptance boundary |
| --- | --- | --- |
| Availability: board-open journey | >=99.5% good eligible attempts, rolling 30 days | Separate indicator from edits. Eligible means authorized, supported client, within accepted input/workload bounds. Good means a usable current board and required assets within 5 seconds; timeouts/5xx/dependency failures count bad. Establish trusted sampling/aggregation in #357; missing data is unknown, never success. |
| Availability: edit journey | >=99.5% good eligible submissions, rolling 30 days | Good means the accepted operation is durably acknowledged and observed by a connected peer within 1 second. Count in-profile overload rejections and failed reconnect attempts bad; deduplicate retries by the eventual accepted T4/T5 identity rules. Never discard slow successes from the denominator. |
| Availability: external synthetic | >=99.5% successful scheduled 1-minute probes, rolling 30 days | Separate controlled-tenant board-open/write/read probe through actual HTTPS/WSS; planned maintenance counts. Probe missing/failed is bad for this indicator. 43,200 scheduled samples imply 216 allowed bad samples in exactly 30 days; this is not an outage-minute allowance for the request-based indicators. |
| Latency: durable acknowledgement | p95 <=100 ms; p99 <=250 ms at 100 operations/second | Measure authorized server ingress to durable receipt using one server monotonic clock; report failed attempts and throughput alongside histogram. No client animation/prediction is a durable acknowledgement. |
| Latency: peer visibility | p95 <=250 ms; p99 <=500 ms at baseline | Sender round trip via peer echo on the sender's monotonic clock, so no unsynchronized cross-client subtraction. Report network/Discord proxy path and rendering separately. |
| Latency: board open | p95 <=3 seconds; p99 <=5 seconds for the 10 MiB fixture | Client launch-to-usable-board; cold and warm caches separate, real desktop/mobile and network profiles recorded. Proxy, authentication, assets and rendering included. |
| Process recovery | Ready <=60 seconds after owned service process failure; zero loss of durably acknowledged operations | Recovery clock begins at fault injection; ends after auth, read, write and peer convergence succeed. Local prefix experiment does not meet this target. T5/T4 must prove retry idempotency and receipt durability. |
| Disaster recovery | RPO <=15 minutes; RTO <=4 hours for the 30 GiB fixture | RPO = incident time minus latest recovered consistent commit time, using a timestamped canary. Also report lost acknowledged operations. RTO begins at incident declaration and includes operator response, fresh VPS access, credentials/keys, download, restore, DNS/TLS and client verification. No achieved RPO/RTO exists yet. |
| Capacity | Sustain the baseline for 15 minutes and the agreed soak with no in-profile shedding and above latency objectives | Proposed headroom: average CPU <60%, process+DB memory <70% of allocatable RAM, disk <70%, no swap thrash, stable queue/memory trend. Record host CPU/RAM/disk, versions and contention; no VPS size is selected. |
| Overload containment | Bounded accepted backlog and bounded per-client output; return explicit retryable failure on saturation | A 10-second burst may reject work but cannot silently lose/acknowledge rejected work, cross tenant boundaries, or prevent healthy boards recovering within 30 seconds after baseline resumes. Accepted queue/deadline values await #357/T4 review. |

Always report the numerator, denominator, histogram count and observation window.
Zero eligible attempts yields undefined availability, not 100%. Known invalid,
unauthorized and oversized requests can be excluded from the user objective but
must have separate bounded rejection counters. A failed authorization dependency
for an otherwise valid user is not an abuse exclusion. A flood must not create
successful synthetic journeys or inflate denominators with invented attempts.
Real-client dependency outages count in the end-to-end indicator; a separate
server-only view aids diagnosis without hiding user impact.

Proposed error-budget policy: measure for a 30-day pilot before calling the
targets validated; freeze risky releases when the budget is exhausted, allow
reliability/security repairs under the eventual approved policy, and review
objectives monthly with product, SRE and T12. No one is assigned an on-call role
by this research document.

## Alternatives and recommendation

| Choice | Alternatives compared | Research recommendation and unresolved cost |
| --- | --- | --- |
| Availability goal | 99% (1% bad attempts), 99.5%, 99.9% (0.1% bad attempts) | Start at proposed 99.5% for pilot evaluation. 99% tolerates substantial interactive disruption; 99.9% needs stronger recovery/operational evidence than a single untested VPS provides. None is a vendor SLA. |
| User signal | HTTP 200 ratio; process uptime; end-to-end board/edit journeys | Use journeys plus independent synthetic probes. Uptime misses broken auth/SQL/proxy paths; HTTP success alone can hide lost edits. Correlate lower-level health for diagnosis. |
| Backpressure | Unbounded buffering; bounded admission with deadlines; drop accepted edits | Prefer bounded admission/deadlines, per-tenant fairness and explicit retry outcomes; volatile presence may be coalesced only under T4's accepted distinction. Never discard accepted durable edits to meet latency. [S3] |
| Backup strategy | Nightly logical dump only; base backup plus archived binary logs and matching assets; replicas alone | Evaluate base+logs+consistent assets for the proposed 15-minute RPO. Nightly-only could lose nearly 24 hours; replication can propagate corruption/deletion. Retain a separate encrypted copy outside the VPS failure domain. MySQL PITR requires a base plus incremental recovery. MariaDB physical backups require preparation and compatible tools. [S4, S5] |
| Recovery topology | One supervised process/VPS; additional replica/VPS; different hosting vendor | Measure one VPS first within mandatory GoDaddy hosting; document single-host failure exposure. Additional GoDaddy capacity requires separate topology/cost evidence and authorization. No alternate hosting adoption here. |
| Supervision | systemd or Compose | T10 owns this choice. Either must stop admission, drain within a measured deadline, preserve volumes and fence retry/duplicate acknowledgements. The systemd manual documents forced termination after the stop timeout; prove the drain fits whichever supervisor is accepted. [S7] |
| Monitoring tooling | Structured logs+external probe; Prometheus-compatible metrics+alerts; paid hosted stack | Prefer bounded metrics and an independent probe as requirements; compare resource cost and maintenance on the actual VPS before tool adoption. No package or paid service installed. Label cardinality must remain bounded. [S6] |

## Baseline experiment: observed local evidence

The [stdlib script](../../scripts/research/t11-baseline.py) is a deliberately
independent fixture. It starts no listener, imports no application code, uses no
database, and creates only owned temporary files plus the explicit JSON receipt.
It has no dependencies to install. Run on Python 3.11+ from the repository root:

```powershell
python tests/research/t11-baseline-test.py -v
python scripts/research/t11-baseline.py --output docs/research/t11-baseline-local.json
python scripts/github-bootstrap/validate.py
git diff --check
```

Use a fresh output filename: exclusive creation prevents replacing prior evidence.
The roadmap validator writes `planning/audit/local-validation.json`; preserve or
restore that generated unrelated file before staging this lane. Never stage all
files in a shared checkout.

Recorded receipt: [t11-baseline-2026-10-26.json](t11-baseline-2026-10-26.json),
2026-10-26T00:54:04Z, Python 3.14.3, Windows 11 AMD64. Script digest in the receipt
identifies the exact executed fixture independently of the later signed commit.

| Case | Observed outcome | Interpretation |
| --- | --- | --- |
| Virtual steady: 100/s, 60 s, assumed fixed 4 ms single worker, bound 128 | 6,000 offered, 6,000 completed, 0 rejected; virtual p99 4 ms | Arithmetic under assumed service time; no measured server latency. |
| Virtual burst: 1,000/s, 10 s, same worker/bound | 10,000 offered, 2,627 completed, 7,373 rejected; peak outstanding 128; accepted p99 512 ms | A bound prevents backlog growth but does not satisfy the proposed p99 target. Historical run used floating-point event times; the exact-arithmetic follow-up below removes false tie saturation. |
| Virtual slow dependency: 100/s, 10 s, assumed 20 ms service | 1,000 offered, 627 completed, 373 rejected; p99 2,560 ms | The same queue bound is too large for interactive latency when the dependency slows. Select limits/deadlines from real service-time distributions, not 128 from this fixture. |
| Local write+flush+fsync, one per record | 300 synthetic records, 625,390 bytes; p50 1.0356 ms, p95 4.7304 ms, p99 8.9523 ms; 0.486976 s total | One small local filesystem run with cache/storage effects and concurrent host workloads uncontrolled; 616.046 records/s is fixture wall throughput, never SQL/Guildboard capacity. |
| Copy+hash+sequence verification | Backup 8.5847 ms; restore 8.4812 ms; 300 exact records restored | Same-disk copies of 0.60 MiB synthetic files; no encryption, asset graph, remote transfer, key recovery or SQL restore. No RPO/RTO claim. |
| Corruption | Truncated copied fixture rejected | Whole-file digest plus deterministic ordered-record comparison detect this specific truncation. Does not prove authenticated backups or malicious-tamper resistance. |
| Owned child abrupt exit | Exit 23 after fsync and close; 32-record prefix verified; child start/exit/verify 93.7136 ms | Process exits without normal interpreter cleanup after a completed write; no in-flight transaction, power loss, OS crash or service restart is tested. |

Five focused unit tests passed: steady behavior, overload accounting/bounds,
invalid/unbounded configuration, reordered content rejection even with a matching
digest, and copy/corruption/owned-child behavior. Queue scenarios are simulated
time; file timings are actual wall time. Percentiles use nearest rank. No timings
are test pass thresholds because host contention can vary. No CPU, RAM, socket,
SQL, asset or real-platform objective is established by these tests.

The local roadmap validator passed with 471 items, 457 expected native
relationships, 600 expected dependencies and zero errors. This is structural
manifest validation, not live Project reconciliation or functional acceptance.
The unrelated generated audit file was restored. Whitespace validation passed.

## Exact queue arithmetic follow-up (2026-11-13 UTC)

Review reproduced a defect in the virtual scheduler: binary floating-point event
comparisons rejected 721 of 6,000 equal-rate requests at 100/s with 10 ms service
and one slot, and 1,530 of 10,000 at 1,000/s with 1 ms service. Both must reject
zero: a completion exactly at the next arrival releases its slot first. The
current fixture interprets numeric inputs by their decimal spelling and uses
exact rational arithmetic for arrival, completion and offered-count calculations.
Only reported latency/time values convert to floats. No epsilon relaxes admission.

Eight tests now pass. Regressions cover those two equal-rate cases, fractional
rates, decimal offered-count boundaries, and service times just below/above the
arrival interval. In the one-slot 100/s case, 9.999999999 ms service rejects zero,
while 10.000000001 ms rejects 50 of 100 requests, preserving genuine overload.
The original burst and slow-dependency counts above remain 7,373 and 373 rejected
under exact arithmetic. The original dated JSON remains historical evidence;
current commands, source SHA and raw results are in the campaign handoff. These
are virtual scheduling results, not measured Guildboard capacity or latency.

## Failure, restart and recovery evaluation plan

These are proposed acceptance experiments for consumers after their native
contracts are accepted, not additional implementation in this PR:

| Fault or abuse case | Required observation and measurable acceptance |
| --- | --- |
| SQL unavailable/slow or disk full | No durable success before commit; classify errors without content; bounded queue/connection usage; no accepted-receipt ambiguity. Retry safely after recovery and verify board/receipt hashes with T5. Admission latency must remain bounded by the accepted deadline. |
| Hot tenant, oversized payload, slow receiver, reconnect storm | Validate size before expensive processing, enforce tenant/client budgets and bounded outbound buffers, preserve healthy-board latency, release slow sockets safely. Reconnect with capped exponential backoff/jitter; never reuse revoked authority or bypass re-auth. T2 owns authorization policy; T4 owns transport/admission bounds, with T3 supplying editor payload constraints. |
| Graceful deploy/restart | Mark unready, stop new work, drain accepted work within proposed 15 seconds, flush telemetry, notify/disconnect clients; proposed supervisor grace >=20 seconds subject to T10 measurement. Record all pending/committed receipts and reconcile retries after restart. Prove no duplicate acknowledgements or revision gaps. |
| Abrupt owned application failure | Kill only a disposable owned test process; measure recovery to successful journey <=60 seconds, durable acknowledged loss =0. Reconcile writes committed before disconnect with retries; acceptance needs actual SQL/supervisor/socket evidence. |
| Nginx idle timeout or Discord proxy disruption | Test WSS upgrade/idle heartbeat, half-open detection, resume authorization and desktop/mobile behavior through registered URL mappings. Nginx documents a default 60-second upstream inactivity timeout; choose/test heartbeat and proxy timeouts together. Discord traffic traverses its Activity proxy; direct localhost tests cannot prove that path. [S8, S9] |
| Missing backup, corrupt archive, wrong/missing key or missing log segment | Fail verification, preserve last known-good backup, emit distinct actionable alert; never report an incomplete restore as success. No credentials or production services used by this research. |
| Full VPS loss and asset/database skew | Restore into a fresh isolated environment with no production write access; verify DB revision/receipt continuity, every referenced asset hash and access boundary, auth/revocation behavior, and timestamped canary. Measure achieved RPO/RTO including manual steps; record failure if any objective is missed. |

Proposed backup candidate: daily consistent base, archive database logs and new
durable assets at most every 5 minutes so verification/retry can fit a 15-minute
RPO; alert when verified recovery-point age exceeds 10 minutes. This cadence is
not sufficient by itself: source+copy consistency, off-host completion, gaps and
recoverable keys determine the actual point. Pair the T5 snapshot/commit boundary
with an asset manifest; prevent asset garbage collection until all retained
recovery points no longer reference the asset. T5 owns board history/replay rules.

Proposed retention for evaluation: seven daily bases plus four weekly bases and
all logs/assets needed to recover those points; choose immutable/encrypted
off-host storage only after threat/cost review. At the 30 GiB fixture, eleven
uncompressed full copies alone are 330 GiB before logs, asset growth and working
space. This is a sizing warning in the research, not a purchase requirement.
Backup credentials should read required source data and write the scoped backup
destination; restore/deletion rights separated. Restrict operator access and
keep recovery keys separate from the failed VPS. Run nightly integrity checks,
weekly isolated restore rehearsals and a full VPS-loss/key-recovery exercise
before release; maintain a verified pre-upgrade recovery point. Proposed
retention and legal/privacy deletion behavior require T9/T5 review in #357.

## Monitoring, privacy and incident handoff

Propose counters for journey outcomes, accepted/rejected work, retries, backup
outcomes; histograms for durable ack, peer visibility, board-open and SQL latency;
gauges for sockets, boards, queue age/depth, outbound bytes, CPU/RAM, free
disk/inodes and verified backup age. Correlate proxy, API, DB and assets without
board content. Keep metric dimensions finite (route template, bounded outcome,
service/environment); no guild/board/user IDs, tokens, raw URL/query, operation
ID or arbitrary error strings as labels. Prometheus warns against unbounded
dimensions. #357 must specify exact fields, cardinality budgets and access. [S6]

Proposed structured log allowlist: UTC time, service/version, severity, bounded
error class, duration and short-lived opaque trace correlation. Do not log
authorization headers, cookies, OAuth codes, session tokens, raw messages,
signed asset URLs, board text/drawings or SQL parameters. Default seven-day
operational log retention and 30-day aggregate metrics are hypotheses for T9
privacy review; access audited, credentials separately protected. Security audit
retention requires T2 audit semantics and T9 security/privacy review. Negative acceptance must seed recognizable
synthetic secret/content canaries and confirm no log/export contains them.

For the proposed 99.5% objective, burn rate = bad-attempt fraction / 0.005.
Starting alert hypotheses adapted from SRE guidance: page when both 1-hour and
5-minute burn exceed 14.4 (7.2% bad), or both 6-hour and 30-minute burn exceed 6
(3% bad); ticket when 3-day and 6-hour burn exceed 1 (0.5% bad). The book's
budget-consumption percentages use a 30-day window. Low-volume behavior needs
explicit testing: below 100 eligible samples in the long window, flag burn as
insufficient evidence and rely on synthetic failures/health alerts for paging.
This sample floor is proposed and must not hide actual failures. Page after
three consecutive 1-minute external journey failures; detect telemetry absence
as a separate alert. Avoid a single healthy process heartbeat masking failure.
[S2]

Additional candidate alerts: verified backup age >10 minutes, corruption or
missing chain immediately; disk <15% free or forecast exhaustion <24 hours;
memory >85% for 10 minutes, CPU >80% for 15 minutes, oldest accepted queue age
>250 ms for 5 minutes. Thresholds are proposed diagnostic triggers, not proven
capacity. CPU alone is a ticket unless accompanied by journey impact. Deduplicate
related alerts; route security signals privately; test alert delivery and recovery
notifications before accepting the monitoring implementation.

SRE incident lead, platform operator, data recovery owner, security contact and
communications owner must be named with backups, timezone coverage and escalation
before release. Until named, no 24/7 response promise exists and the 4-hour RTO
remains unvalidated. Proposed incident flow: declare and timestamp, restrict
unsafe writes, preserve receipts/logs without secrets, diagnose/fence failure,
recover using approved runbook, verify journeys and tenant boundaries, communicate
status via the maintainer-approved channel, then record cause/timeline and owned
followups. Credential incidents require private security routing, scoped
revocation and evidence preservation; never paste secrets into GitHub.

## Primary sources and evaluated versions

All links below were inspected on **2026-10-26 UTC**. Rolling documentation is
identified as such; access date is not a software release date. No latest-version
claim or dependency pin is implied.

| ID | Primary source | Version/date scope and use |
| --- | --- | --- |
| S1 | [Google SRE Workbook, Implementing SLOs](https://sre.google/workbook/implementing-slos/) | 2018 workbook, current online chapter; user-focused good/total indicators and iterative adoption. |
| S2 | [Google SRE Workbook, Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/) | 2018 workbook, current online chapter; multiwindow burn rates and low-traffic limitations. |
| S3 | [Google SRE Book, Handling Overload](https://sre.google/sre-book/handling-overload/) | 2016 book, current online chapter; bounded queues and overload handling. |
| S4 | [MySQL 8.4 PITR](https://dev.mysql.com/doc/refman/8.4/en/point-in-time-recovery.html) and [backup policy](https://dev.mysql.com/doc/refman/8.4/en/backup-policy.html) | 8.4 manual, not an 8.4.11 execution here; restore base plus incremental changes and recovery planning. |
| S5 | [MariaDB full backup and restore](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/full-backup-and-restore-with-mariadb-backup) | Rolling manual; compatible backup/prepare tools, prepared physical consistency, empty isolated restore destination. MariaDB 11.4.13 remains a T5 provisional evaluation input only. |
| S6 | [Prometheus metric and label naming](https://prometheus.io/docs/practices/naming/) | Rolling practices page, no Prometheus binary installed/evaluated; finite label dimensions. |
| S7 | [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html) | Online page identifies systemd 262; GoDaddy image/version unknown and untested. Stop timeout and restart semantics need matching target-version verification. |
| S8 | [Nginx WebSocket proxying](https://nginx.org/en/docs/http/websocket.html) | Rolling page discusses WebSocket support since 1.3.13 and HTTP-version behavior before 1.29.7. No Nginx binary tested/pinned; explicitly verify target HTTP/1.1 upgrade/headers/timeouts. |
| S9 | [Discord Activity networking](https://docs.discord.com/developers/activities/development-guides/networking) | Rolling guide, no registered app/SDK/client tested; Activity proxy and URL mappings affect the real measurement path. |
| S10 | [GoDaddy VPS hosting](https://www.godaddy.com/hosting/vps-hosting) | Current vendor offering; only confirms target family, not measured resources, network behavior or Guildboard availability. No plan selected or purchased. |

## Acceptance mapping, consumer handoff and uncertainty

| #356 clause | Reviewable evidence now | Still required |
| --- | --- | --- |
| Availability/latency/recovery/capacity objectives from expected use | Explicit synthetic workload, proposed objective table, denominators and clocks | Product/SRE acceptance of demand and targets; no invented usage/SLA. |
| Measured baseline plan and reproducible experiment | Executable bounded fixture, dated JSON with script hash, five original tests plus three exact-arithmetic regressions, real-platform matrix | T10/T12 actual SQL, HTTPS/WSS, Discord desktop/mobile, assets and soak measurements on accepted contracts. |
| Alternatives, primary URLs, versions/date and uncertainty | Decision comparison and S1-S10 source ledger | Actual current-head GitHub Copilot review plus required SRE/CODEOWNER/consumer review, accepted decision and merge. |
| Error/abuse and recovery evidence | Local invalid-config, overload accounting, content reorder and corruption rejection, owned child prefix check | Real tenant fairness, slow receivers, revocation, SQL/disk failure, graceful restart, encrypted off-host restore and key recovery. |

Handoff to #357: propose exact observability/redaction/retention contracts,
alert evaluation fixtures, backup manifests, recovery acceptance and named roles
using this research after acceptance. T4/T5 own durable operation processing and replay
semantics; T3 owns canonical editor/schema constraints; T1 owns Discord client and
identity constraints; T9 owns security/privacy and audit-integrity review;
T5 owns asset/import storage and limits; T8 integrates the API surface;
T7 owns accessible shell controls;
T10 owns GoDaddy sizing, supervisor and routing; T12 owns executable acceptance.
These are information handoffs, not new native blocker edits.

Uncertainty remains high: no real demand distribution, database/schema choice,
asset growth, VPS image/limits, mobile/proxy latency, security/privacy retention
decision, staffed incident coverage, backup destination/keys or recovery runbook
has been accepted. The 300-record file sample cannot support tail/capacity
extrapolation to a 30 GiB restore. External platform checks, consumer review and
post-merge acceptance remain open. #356/#355 remain open; #357 stays blocked until
its actual prerequisite gate is satisfied.
