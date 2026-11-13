# GB-T12.R1: quality engineering strategy research v1

Proposed research for [#388](https://github.com/CompleteTech-DiscordApps/guildboard/issues/388),
not an accepted test/release contract or implemented application. Observed
2026-10-26 UTC during the 2026-10-25 America/New_York session. Base
`c108b552a660e12a3b3998e1e1ad944fbd7a894d`, package `0.0.0`.

Recommendation: use bounded reproducible schedule/property experiments to develop
oracles, then exercise the actual accepted server/storage implementation with
controlled failpoints and truly overlapping clients. Combine isolated browser
checks with a separate real Discord/client/assistive-technology matrix, and
measure bounded load/recovery on the mandatory GoDaddy Linux VPS. Every number
below is a proposed investigation/acceptance budget needing consumer review,
not a measured capacity, adopted protocol, product SLA or release approval.

## Scope, ownership and provisional inputs

Live #388 had no assignee, comments or competing focused open T12 PR before the
[scoped claim](https://github.com/CompleteTech-DiscordApps/guildboard/issues/388#issuecomment-6405789528).
Native #389 is still blocked by #388; research publication does not remove that
blocker. No Project fields, dependency relationships or shared ledgers change.
Read CONTRIBUTING, GOVERNANCE, SECURITY, architecture proposal, tests guidance,
and T12 scope. These explicitly distinguish preparation from real acceptance.

Read-only coordination inputs, frozen for this research:

| Artifact | Evaluated revision and limits |
| --- | --- |
| [#481 system contract](https://github.com/CompleteTech-DiscordApps/guildboard/pull/481) | `a25082ca0bca1e39610b900e4dd01db056bab4ad`: provisional current identity/read before retained receipt/digest, then lineage/new-write checks. Historical receipt does not reapply restored content. No accepted architecture. |
| [#490 T5](https://github.com/CompleteTech-DiscordApps/guildboard/pull/490) | `5e8a9fe999e0ef6db5509ad4075e324da6c2be79`: narrow SQL fixture reports MySQL **8.4.11**, MariaDB **11.4.13-MariaDB-ubu2404-log**. Neither is a production selection; serial probes do not prove concurrent lock ordering, physical power-loss safety or GoDaddy restore. |
| [#491 T1](https://github.com/CompleteTech-DiscordApps/guildboard/pull/491) | `8a56a58b0a57cd9e467b90f8a2bb043e63a67547`: pinned SDK **2.5.0** artifact/helper evidence; registered app, controlled guild, authenticated clients and actual proxy/identity inputs absent. Membership/channel access alone is not exact launch/current-presence proof. No T12 SDK installation/execution. |
| [#493 T7](https://github.com/CompleteTech-DiscordApps/guildboard/pull/493) | `833181d40bfe047cf69a02026358c46e0fb910b9`: semantic fixture/browser exploration is provisional. Browser emulation and DOM semantics are distinct from physical input, speech, human usability and WCAG conformance. No T7 files executed or adopted here. |

Any changed head requires consumers to reconcile these assumptions before using
the research. T1/T2/T4/T5/T7/T9/T10 and #389 owners must review eventual identity,
authority, reducer, storage, accessibility, abuse and hosting contracts together.
This harness chooses no production conflict semantics or database schema.

## Primary evidence, versions and alternatives

[Source observations](t12-source-observations.json) record ten bounded official
document GETs, date, version scope and response hashes. The initial capture exited
1 because three Discord pages returned HTTP 403. The final capture retains those
failures and fetches official MDX at Discord's observed source revision
`6128d99116af8357db1e4966ebd7f099817a0e04`; all ten sources then have HTTP 200
evidence. Separate browser-source reads inspected the live Discord pages.
Hashes identify observations; they neither archive content nor prove behavior.

| ID / official source | Observation and implication |
| --- | --- |
| F1 [FoundationDB SIGMOD 2021 paper](https://www.foundationdb.org/files/fdb-paper.pdf) | Describes reproducible simulation/fault testing with real database code. Our miniature abstract model does not have that integration; use its replay discipline without borrowing its correctness claims. |
| P1 [Playwright parallelism](https://playwright.dev/docs/test-parallel) | Tests can run in independent worker processes; suite parallelism alone does not coordinate competing operations in one room or exercise server transaction races. Rolling stable docs; no Playwright binary evaluated in T12. |
| P2 [Playwright accessibility testing](https://playwright.dev/docs/accessibility-testing) | Automated checks find a subset of issues; manual assessment and user testing remain necessary. A browser/accessibility scan is one evidence layer. |
| K1 [k6 open/closed load models](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/) | Closed-loop slowdown reduces offered arrivals; open arrivals expose this omission. Prefer scheduled arrivals with bounded outstanding work and explicit dropped-work reporting. Rolling docs displayed **v2.3.x**, no k6 binary installed or evaluated. |
| W1 [WCAG 2.2 Recommendation, 2024-12-12](https://www.w3.org/TR/2024/REC-WCAG22-20241212/) | Proposed normative accessibility target is all applicable A/AA criteria. Specific task sampling below does not establish full-page conformance. W3C informative examples/guidance and our additional design goals are separate. |
| D1 [Discord local development](https://docs.discord.com/developers/activities/development-guides/local-development) | URL override can bypass the proxy; actual mapped proxy testing remains necessary. A tunnel is a development option, not GoDaddy acceptance. |
| D2 [Discord mobile](https://docs.discord.com/developers/activities/development-guides/mobile) | Web/iOS/Android support configuration and mobile safe-area variables require actual client validation, not guessed dimensions. |
| D3 [Discord production readiness](https://docs.discord.com/developers/activities/development-guides/production-readiness) | Include non-HTML asset cache busting and API rate-limit handling in release tests. No fixed rate-limit quota inferred. |
| N1 [Nginx WebSocket proxying](https://nginx.org/en/docs/http/websocket.html) | Upgrade headers and proxy timeout/heartbeat behavior matter. Documented default inactivity close is 60s; actual VPS/Discord path configuration and behavior remain unmeasured. |
| G1 [GoDaddy VPS backups](https://www.godaddy.com/help/back-up-my-vps-hosting-27819) | Provider backup functionality does not demonstrate a coordinated SQL/assets cut or application restore. Verify plan-specific behavior and independent restore evidence. |

| Choice | Evaluated alternatives | Proposed direction and unresolved risk |
| --- | --- | --- |
| Race testing | Happy-path E2E alone; uncontrolled stress; exhaustive bounded schedules plus seeded actions; actual server failpoints | Combine the last two. Small schedule coverage is exact only inside its stated model; stress finds timing/environment failures; neither covers every real schedule. |
| Properties | Fixed examples only; generated traces with shrinkable/replayable failures | Preserve minimal examples and deterministic seeds now. Add property-generator/tool version pinning and trace minimization against the accepted reducer later; no additional dependency adopted. |
| Client tests | SDK mock/URL override only; standalone browsers; actual mapped Discord clients | First layers are cheap regressions. Actual Discord clients and proxy remain compatibility gates, including OAuth errors/cancellation and stale server policy. |
| Load | One user repeatedly waits for response; open offered-rate load; unrestricted stress | Bounded open arrivals plus persistent independent sockets. Report generator limits and rejection reasons; stop on safety/tenant-integrity triggers. Stress is exploratory. |
| Accessibility | Automated scan only; semantic fixture; manual AT/keyboard tasks and user review | Combine all three and review full supported functionality, including accessible alternatives for canvas objects and non-drag movement. No script or reviewer substitutes for real speech/input evidence. |
| Hosting | Local loopback/container only; provider snapshot only; exact GoDaddy test deployment and independent restore | Require the last option for external claims. Local fixtures develop tests; do not replace mandatory GoDaddy hosting or claim restore from a successful backup command. |

## Executed bounded experiment and its oracle

`scripts/research/t12-schedule-experiment.py` uses only Python's standard library.
Python **3.14.3**, Windows x64 was executed; no SDK, database, browser, container,
daemon, WSL, registered app or remote host was launched by this lane.

Two actors each have prepare/commit/ACK steps plus one revoke step. Enumerate
all **140** orders preserving actor order. Check **980** abstract recovery cuts,
plus **32 x 48 = 1,536** seeded actions including reorder/duplicate delivery,
logical revoke, restore and recovery. Seeds are bounded to 0..31 and traces to
48 steps. An injected logical clock accepts tick 4 and denies new writes at
expiry tick 5; these ticks are arbitrary, not a production TTL or wall clock.

The toy command is a conditional single-object replacement, chosen to expose
stale-base conflicts without inventing a general editor merge rule. Its identity
includes tenant/board/lineage/actor/operation. Its digest is a research encoding.
The oracle checks contiguous revisions, receipt/event pairing, accepted content
projection, zero denied side effects, current committed application authority,
tenant/board isolation and no acknowledged event loss. Current read authorization
precedes receipt lookup; retained same-digest receipt precedes active lineage and
new-write base checks. Explicit scenarios cover lost ACK after commit, duplicate
retry after another edit, different-digest conflict, restore retaining historical
receipts without replaying content, unknown old-lineage denial and read denial.

All **five unsafe controls fail** their oracle: prepare-only authority, foreign
scope acceptance, split receipt/event commit, stale-base check before retained
receipt and ACK before commit. This confirms sensitivity to those modeled
defects. Accepted-event counts across schedules are 0:52, 1:68, 2:20; conflicts
and post-revoke denials are expected. Final reports are byte-reproducible.

**Limits:** commit and authority fencing are indivisible in-memory assumptions.
Recovery deep-copies fields designated durable; it does not crash a process or
write/flush a disk. Enumeration is serial execution of abstract interleavings,
not real distributed concurrency. Trusted read/write inputs are global stubs,
not verified Discord identity, per-principal authorization or external role
freshness. There are no real sockets, clocks, SQL locks, outbox consumers,
assets, general undo/compound semantics, client replicas or measured convergence.
Seeded coverage is finite and not exhaustive. Retaining receipts here proves no
production retention/compaction policy. These limits must travel with results.

## Next experiment against accepted runtime code

After the native specification gates, connect the same invariant checks to actual
server/storage code, not a second toy implementation. Use isolated tenant/guild,
board and actor fixtures with a fake identity adapter, deterministic server clock,
real pinned engine and bounded connection pools. Keep real Discord identity
checks in their separate matrix. For each race, launch **independent clients and
connections**, wait on named server barriers, release both, and retain operation
history with request identity/digest, preconditions, invocation/response, commit
revision and fault point. Timeouts produce inconclusive/failed tests, never pass.

| Race/fault | Required observable result and limitation |
| --- | --- |
| Same-object/disjoint-object and compound operations | Compare accepted projection against the reviewed reducer and allowed serial histories, preserve accepted edits; do not compare only screenshots. Define undo conflict rules in T4 first. |
| Write versus revoke/expiry | Pause after preliminary authority read, commit revoke, resume write; assert new effect denied at committed fence with no revision/receipt/event/outbox/audit mutation. Reverse order permits an earlier accepted effect. Discord detection delay is separately measured, not instantaneous. |
| Duplicate operation versus commit/restore | Same scoped identity/digest yields one durable effect and historical result after current read; changed digest conflicts; unknown retired lineage cannot mutate. Do not discard receipts to make retries disappear. |
| COMMIT before ACK / ACK delivery interrupted | Failpoint before commit leaves no accepted effect; after commit/before ACK returns retained receipt on retry. Assert authoritative durable records, not just client UI state. |
| Split commit/storage error/deadlock/timeout | Force real failures in isolated test services; rollback all coupled writes or return explicit unknown outcome and reconcile same identity. Reject partial receipt/event/content/outbox state. |
| Reconnect/late join, duplicated or delayed event | Check accepted-state convergence and ordered revisions; preserve unsent drafts; never promote draft to accepted before durable ACK. Reauthorize replay/broadcast recipients after revoke or restore. |
| Snapshot/tail/assets and backup restore | Exercise boundary writes, missing/corrupt manifests and interrupted publication; restore to isolated destination and compare accepted operation/receipt/asset set. Measure RPO/RTO independently of process restart. |
| Abuse/tenant boundaries | Cross-guild/board/object/asset/receipt, forged actor/admin, expired/replayed session, viewer writes, oversized/malformed commands, floods and invalid uploads are separate negative fixtures. Assert no leaked identifiers and no side effects; retain redacted results. |

No runtime implementation is present to run these probes here. Crash/restore and
resource tests require explicit owned-environment authority and must never affect
shared workloads; no WSL/VM/daemon restart is part of this procedure.

## Synthetic load and proposed budgets

[Machine-readable inputs](t12-validation-matrix.json) and
[derived arithmetic](t12-matrix-evidence.json) send **zero traffic**. Proposed
representative corpus: 1,000 objects, <=2MiB initial serialized board, 70% modify /
15% create / 10% delete / 5% compound; 20% of writes contend on one object. Content
and operation sizes need T4/T5 acceptance, not adoption from this fixture.

| Profile | Guilds / boards / connected clients | Offered ops/s and time | Payload ingress / peer fanout bytes/s |
| --- | --- | --- | --- |
| Small | 1 / 1 / 10 (2 editors, 8 viewers) | 4 for 300s; 1,200 offered | 4,096 / 36,864 |
| Baseline candidate | 3 / 6 / 120 (24 editors, 96 viewers) | 96 for 900s; 86,400 offered | 98,304 / 1,867,776 |
| Stress exploratory | 10 / 20 / 1,000 (160 editors, 840 viewers) | 800 for 60s; 48,000 offered | 1,638,400 / 80,281,600 |

Fanout assumes one event to every other participant on its board. These are
payload arithmetic lower bounds under that broadcast assumption; envelope,
TLS/proxy, compression, resends, presence, assets and stored-log growth differ.
**80MB/s stress fanout is not a GoDaddy capacity claim or release requirement.**
Do not run a profile until the host/generator budget is reviewed. Large initial
scenes/assets, hot boards, read-only audiences and reconnect storms need separate
measured cases; this small synthetic corpus cannot represent unknown usage.

Baseline candidates: durable ACK p95/p99 **250/750ms**; accepted peer projection
**500/1,000ms**; authenticated usable cold board **5,000/7,500ms**; convergence
after a 30s disconnect with <=500 missed events **3,000/5,000ms**; foreground
frame duration **32/50ms**. Measure desktop/mobile separately. Conditions and
metric boundaries are in the JSON. These numbers are engineering hypotheses,
not values asserted by Discord, W3C, GoDaddy or this local experiment.

Use 60s warmup then >=900s measured steady baseline, >=10,000 new commands and
three independent runs. Report per-run distributions and sample counts, nearest
rank percentile definition, cold/warm cache, success/conflict/reject/timeout/lost
samples separately. Do not exclude timeouts or dropped offered work from the
arrival denominator. Same-client monotonic clocks measure ACK latency; cross-peer
latency needs clock calibration/error bounds or a shared instrumented observer.
Report offered versus started versus completed work and generator scheduling lag;
bounded concurrency saturation is failure to deliver the profile, not throughput.

Candidate resource investigation limits: <=70% steady CPU, >=20% available RAM and
free data disk, <=10% unexplained RSS growth after load drains, event-loop p99
<=50ms, unexplained application errors <=0.1%. Expected denials/conflicts and
Discord 429 responses remain visible and separately classified. Zero unauthorized
effects, tenant leaks and acknowledged loss are invariant gates, not percentile
exceptions. No RPO/RTO or external role-detection SLA is selected; T5/T2/T10 must
review recovery size and freshness evidence before numerical contracts.

Stop on integrity violation, <10% available RAM, <15% free data disk, sustained
>1s generator scheduling lag, host safety budget breach, shared-workload impact
or missing scoped destructive-test authority. Stress must remain bounded and
must not generate real Discord API floods; load the owned backend test path with
controlled adapters while actual Discord tests respect API responses/rate limits.

## Discord, accessibility and GoDaddy acceptance matrix

The JSON contains **ten external rows, all not-run**: Windows/macOS stable Discord
desktop; Discord web on Chrome and Firefox (Firefox support decision pending);
physical iOS/Android Discord; preview channels exploratory; actual GoDaddy network,
load and recovery. Pin exact app commit, SDK/browser/Discord build, OS/device/AT
versions, plan/resources/region, date, scenario, fault/seed, raw trace/hash and
reviewer. Refresh moving client builds at release; no support promise is inferred.

Test actual launch/ready/authorization/cancellation, server-bound guild/board,
mapped HTTPS/WSS, controlled unmapped-request failure, caching upgrades, permission
revocation, reconnect, safe areas/rotation/software keyboard, background/foreground
and PIP where supported. URL override/proxy and cold/warm cache are distinct rows
within each run. Screen size emulation does not prove a device or platform setting.

Candidate accessibility budget: **zero task blockers** across supported keyboard/
AT flows, plus review every applicable WCAG 2.2 A/AA criterion. Tasks include
launch/auth, finding/describing/selecting objects, semantic create/edit/move/delete,
non-drag navigation, dialogs, focus return, policy feedback and reconnect drafts.
Pair Windows NVDA, macOS/iOS VoiceOver and Android TalkBack with the actual client;
record speech, focus and input observations with human assessment. Automated
critical/serious findings need resolution or documented expert disposition.

W1 checks include keyboard/no trap, names/roles/states, status messages, visible
unobscured focus, contrast (normal text 4.5:1; large text and applicable nontext
3:1), 200% text resize, outer UI reflow at 320 CSS px, text spacing, dragging
alternatives and 24x24 CSS px targets or reviewed criterion exceptions. Two-
dimensional canvas exceptions require review and do not exempt surrounding UI.
44x44 outer controls, reduced motion, forced-colors review and coalesced live
feedback are additional proposed design goals. This is not a full conformance
checklist or conformance claim. Freehand/images/geometry alternatives and editor
parity remain T7/T4 decisions; a semantic fixture cannot prove them.

For actual GoDaddy Linux VPS: record chosen distribution/kernel, CPU/RAM/disk/
quotas, TLS/Nginx/runtime/SQL builds and durability settings. Check public HTTPS
chain/renewal, WSS upgrade and idle intervals **below and above 60s**, heartbeat
loss, reconnect and graceful application restart in an isolated test deployment.
Exercise actual Discord proxy as well as direct external connections; default
Nginx guidance is not the provider/Discord timeout. Verify SQL/private assets are
unreachable externally and authorized asset paths remain tenant scoped. Restore
SQL, required logs/receipts and persistent assets to an isolated destination;
compare hashes/revisions and report measured recovery time/loss and missing data.
Provider snapshots alone are insufficient. No host/plan was provisioned, accessed
or measured; only `.env.example` exists among repo-local env filenames inspected.

## Reproduction, results and handoff

Run from repo root, Python 3.14.3 as evaluated (dependency-free; other versions
not claimed). The first three commands are entirely offline. PowerShell output
redirection shown produces UTF-8 in the evaluated shell; preserve JSON semantics
and line endings when comparing evidence across operating systems.

```powershell
python tests/research/t12-test-experiments.py -v
python scripts/research/t12-schedule-experiment.py > docs/research/t12-schedule-evidence.json
python scripts/research/t12-validate-matrix.py > docs/research/t12-matrix-evidence.json
python scripts/research/t12-capture-sources.py > docs/research/t12-source-observations.json
python scripts/github-bootstrap/validate.py
git diff --check
```

Local result: **14 tests pass**; 140 schedules/980 recovery boundaries, 1,536
seeded actions, five unsafe controls caught, expiry boundary verified; repeated
fresh process experiment output is byte-identical. Matrix validates 3 bounded
profiles, correct offered-load arithmetic, ten pending external rows and rejects
oversized/noninteger/duplicate load, invalid mix/percentiles, missing evidence and
invented platform/a11y pass results. Source capture final exit 0 with ten fetched
official sources and three retained HTTP 403 attempts. Roadmap validator passes
471 items / 457 native relationships / 600 dependencies / zero errors; unrelated
generated audit rewrite is restored. These scripts run explicitly and are not
silently added to the existing hosted workflow.

| #388 clause | Observable artifact/result | Still open |
| --- | --- | --- |
| Deterministic concurrency strategies | Executed bounded schedule/property oracle and unsafe controls; actual runtime experiment plan above | Real overlapping server/SQL/socket/fault execution and accepted reducer/authority contracts |
| Discord-client/VPS strategies | Ten pending machine-readable environment/evidence rows, alternatives and primary-source rationale | Registered app/guild/clients/AT and owned GoDaddy environment; every real row not-run |
| Load/accessibility budgets | Validated synthetic calculations and proposed measurable metrics/tasks | Representative telemetry, reviewed support matrix/numbers, actual performance/AT/conformance measurement |
| Versions/date/uncertainty | Dated response hashes, exact provisional input heads, executed Python version and explicit limits | Actual QE/security/consumer/CODEOWNER review, current-head Copilot review, hosted CI, merge/post-merge checks |

Pipeline owns review requests, review comments and merge decisions; this writing
lane requests no reviewer and makes no approval. Native CODEOWNER protections and
#389's research blocker remain intact. No purchase, provisioning, deployment,
production acceptance, runtime-contract adoption or issue-closing directive.


## 2026-11-12 scope reconciliation and local revalidation

T11 SRE owns operational objectives, production metric/log privacy and bounded
cardinality, alert thresholds, retention, backup policy and incident/runbook
responsibility. T12 owns the test strategy, candidate acceptance budgets, test
oracles and evidence matrix; T10 owns deployment/proxy configuration and platform
measurements. The load/resource candidates above are inputs for joint T11/T12
review, not adopted alerts or an SLO. T5 supplies durable recovery/receipt
semantics and T2 the authorization boundary. No T11 deliverable, staffing
assignment, dependency or operational guarantee is created by this research.

The retained-receipt model continues to follow the provisional #481 contract:
current read first, existing identity plus digest next, and current lineage/write
checks only for a new effect. After restore, a retained matching receipt reports
historical acceptance without changing the restored projection; a changed digest
conflicts; an unknown retired-lineage operation is denied. Added regression cases
exercise these outcomes, current read denial, and an intervening write revocation
while asserting no durable side effects. These are abstract model checks, not SQL
or a running collaboration service. Consumers must reconcile the final reviewed
T4/T5/system-contract heads before adoption; this text does not accept a contract.


Revalidation on 2026-11-12, code/test head
`6c9286f` (full SHA in the campaign receipt), Linux 7.2.15-1-omarchy x86_64 / Python 3.14.8:
`python3 tests/research/t12-test-experiments.py -v` passed **17 tests**.
Fresh `t12-schedule-experiment.py` and `t12-validate-matrix.py` JSON equals the
existing saved evidence semantically: 140 schedules, 980 recovery boundaries,
1,536 seeded actions, five unsafe controls, three load profiles and ten not-run
external rows. The historical JSON is preserved. Planning validation passed
471 items / 457 native relationships / 600 dependencies / zero errors.
Raw stdout/stderr is retained in campaign `2026-11-12/logs/platform/` under
`t12-tests-6c9286f.log`, `t12-schedule.json`, `t12-matrix.json` and
`t12-planning.log`; the handoff receipt records exact paths and full heads.
No source freshness, actual Discord, assistive technology, SQL or GoDaddy result
is added by this offline revalidation.


The coordinated T4 candidate [#484](https://github.com/CompleteTech-DiscordApps/guildboard/pull/484)
at `3379307f5b0e64c9b135307a160558347d7299f0` now documents retained receipts
across restore in `docs/research/collaboration-semantics.md`. This agrees with
T12's historical-receipt model at the described boundary. T4 remains provisional
pending fresh independent review and external approval; agreement between models
is not implementation or acceptance evidence.


Fresh GitHub review comments `4559078585` and `4559078629` against
`13572b1cb81d97d1699540984949154e026f2062` identified that counting ten rows did
not preserve VPS coverage, and evidence length alone accepted empty/duplicate
names or omission of `trace-hash-date`. Both findings were reproduced against
the original validator: the two new regression methods produced eight expected
assertion failures. Code revision `d423949776fab96efa0fa98399213dacfc25657a` requires the exact ten environment
IDs with their expected client/VPS groups, distinct nonblank evidence names and
the mandatory dated trace/hash field. All **19** focused tests then passed;
fresh matrix output still equals the saved synthetic arithmetic. Planning
validation and diff whitespace checks passed. Raw results are
`t12-regressions-before.log`, `t12-tests-d423949.log` and
`t12-planning-d423949.log` in the campaign log directory. These code changes
require fresh full-head independent review; discussion threads are left open.
