# GB-T12.S1 verification evidence contract v1

Specification candidate for [#389](https://github.com/CompleteTech-DiscordApps/guildboard/issues/389).
The native [#388 research](../research/t12-quality-engineering-research.md) is
closed following #498. Use the accepted [T0 disposition](../workstreams/T0.md#deliverable-disposition)
and [system scenarios](fixtures/GB-T0-S1-scenarios.json), the merged
[T9 control and evidence contract](GB-T9-S1-security-privacy-contract.md), and
the applicable domain contracts for expected behavior. Quality Engineering,
Security Engineering for trust boundaries, and consuming engineering must
review the exact change before downstream implementation depends on this
contract. Native approval and release decisions follow repository governance. The
[interaction architecture ADR](../adr/0002-server-authority-and-interactions.md)
retains server authority across request, commit and read release. T12 research
compares scheduler and client harness options. SDK mocks cannot observe actual
Discord proxy authority, browser-only outcomes cannot prove SQL durability, and
provider snapshots alone cannot establish application recovery. This contract
keeps those checks at the corresponding independently observable boundaries.

## Test pyramid and fixture ownership

| Level | Test subject and oracle | Execution and credit |
| --- | --- | --- |
| Static and unit | Strict decoders, pure validation, reducer, policy tables, arithmetic and evidence schema. Check valid, malformed, boundary and stale inputs against contract-owned expectations. | Deterministic and offline. Evidence class `fixture` for simulated subjects. |
| Service/SQL integration | Pinned accepted SQL engine, migrated schema, actual API/bot/command, storage and transport code. Observe transaction and egress state independently. Use a fake Discord identity adapter and controlled server time. | `local_integration` or `hosted_ci`. Report engines, drivers, migrations, fake adapters, and exact entry points. |
| Browser E2E | Real built Activity UI with a controlled SDK, browser, proxy and backend. Record launch/ready/auth/cancel/navigation, policy feedback, reconnect/drafts and accessible controls. | Same integration classes. These observations cover the declared browser harness and simulated SDK surface. |
| Owned platform runs | Actual Discord clients and mapped paths, human AT runs, and authorized GoDaddy Linux VPS network/load and isolated restore. | `real_discord` and `real_godaddy`, with separate row receipts even for a joined network journey. |
| Independent and post-merge | Qualified reviewers examine the exact delta, evidence, findings and integration. Requalify accepted artifacts and applicable checks on the actual merge revision. | `independent_review` and `post_merge` have distinct provenance and supplement executable checks. |

Use the cheapest reproducible level that observes the boundary. High-risk
controls require several levels. A mocked assertion about a database or egress
event does not satisfy a row requiring a real SQL, transport or platform probe.
Measure user-visible effects and durable state at their own boundaries.

QE owns the fixture manifest and deterministic seed, accepted expected outcome,
clock, schedule and test-data provenance. Domain owners provide versioned
encoders, actual transport and SQL entry points, and reviewed failpoints.
Allocate an exclusive run namespace before creating any resource. Record its
owner, approved target, lease expiry and inventory, including worker handles,
connection pools, migrations/schema, temporary asset paths, queues, files and
bot/session fixtures. Use at least two synthetic guilds, two boards in the
subject guild and a foreign board with colliding selectors; define viewer,
moderator, revoked user and independent control actor. Seed separate assets,
receipts and lineage. Use logically independent clients/connections and a
separate observing connection. Record fixture/version/seed and named barrier
ordering. Exhaust bounded schedules or state the number and seeds exercised.
Use trusted simulated server time for expiry branches and monotonic deadlines
for harness waits. A barrier timeout yields blocked or failed evidence.

Validate configuration, owns-target authorization, prerequisites and finite
timeouts before creating resources, binding listeners or issuing adapter
requests. Use names-only validation errors. When catchable cancellation occurs,
stop new work, drain/reap owned workers within the deadline, close connections,
remove only inventory-owned resources and independently check that the
unrelated sentinel remains. On host loss or uncatchable cancellation, leave
the row blocked, quarantine the namespace, reconcile it through the authorized
owner and rerun from a fresh namespace. Cleanup failure blocks acceptance even
when assertions completed. Denials must preserve the before/after state vector
under the scoped boundary: revisions, rows/content/assets, receipts,
outbox/events, protected read projection and unauthorized audit transitions.
A separately approved redacted denial audit may exist. Successful controls
establish that the instrument would detect real writes, reads and effects.

## Scenarios and observable effects

The [synthetic corpus](fixtures/GB-T12-S1-scenarios.json) registers conformance
cases and independent observer data for this document. Its records represent
offline acceptance logic and carry fixture-class evidence only. Runtime
verification must use the real supported entry points against owned test data
and take a separate observation of persistence, protected egress and peer
projection. No runtime service, SQL, browser, production or vendor test is
included in this specification.

| Scenario family | Observations demanded of consuming verification |
| --- | --- |
| E01/E02/E03 | Valid owned setup reaches the harness; an invalid setting or unavailable prerequisite causes zero creates, binds or outbound calls; interruption reaps owned work and preserves the unrelated sentinel. Keep unavailable/aborted status distinct from pass. |
| E04 | Compare authorized and denied viewer, expired/replayed session, stale role, forged claim and foreign guild/board/asset/receipt decisions; no durable or peer side effects on denial. Exercise accepted inert/bounded input controls and generic response equivalence for missing and foreign selectors. |
| E05 | For independently ordered commit and revocation, cover both sides of the fence; confirm rollback and retained acceptance when delivery fails. Duplicate digest yields one durable effect, changed digest conflicts only after current read authorization. Same-object/disjoint/compound operations and reconnect/late join converge to accepted revision and canonical projection. |
| E06 | Verify both orderings of read authorization and protected handoff to transport, including already prepared ACKs, current and historical receipt/digest results, events, replay, metadata, and each queued snapshot, asset and export chunk. Exercise expiry, revocation, membership invalidation and unavailable trusted time/freshness under backpressure. Measure emissions at handoff and acceptable disclosure independently; an accepted write stays durable when ACK release is denied. |
| E07 | Cover precommit interruption, committed/lost ACK, interrupted snapshot publication, current read denial after restore, retained historical receipt retry, changed digest and unknown old lineage. Verify the isolated restored cut against independent SQL, receipt/outbox and persistent asset inventories. Compare canonical hashes and revisions, fence old writers and record achieved RPO/RTO with missing data and measurement boundaries. |
| E08 | Required platform, integration, review and merge rows match class, exact candidate and observed environment; stale or substituted evidence, missing authority, and unresolved required failures keep the gate blocked. |

## Environment and load matrix

Carry all ten row IDs, required evidence fields and six safety stops from the
[pinned research matrix](../research/t12-validation-matrix.json). Adopt it here
as a coverage registry. The numeric values and supported-client choices remain
proposals until their decision owners accept them. Every external row is
currently unrun. Pin app commit/build/SDK and separately capture exact client
build/channel, browser/OS/device/AT, support decision, date, approved test
scope, reviewer, fixture and redacted trace digests. Recheck changing client
builds at release.

- `discord-win`, `discord-mac`, `discord-web-chromium`,
  `discord-web-firefox`, `discord-ios`, `discord-android` and
  `discord-previews` are separately authorized actual Discord environments
  with isolated app/guild and least-privilege accounts. Firefox support remains
  a decision; previews are exploratory. Record actual iframe, launch/auth or
  cancellation, mapped HTTPS/WSS and controlled unmapped failure, proxy
  upgrade, reconnect and role change. Separate cold/warm cache and URL-override
  conditions. Use physical mobile devices for rotation/safe areas, touch,
  soft keyboard and background/foreground behavior where supported.
- Manual accessibility evidence accompanies the appropriate real client row.
  Pair NVDA, VoiceOver and TalkBack with the corresponding pinned platform and
  record observed focus, speech, inputs and outcomes for the seven research
  tasks and the listed checks. Match all applicable WCAG 2.2 A/AA criteria to
  reviewed observations or criterion-specific applicability rationale. Require
  zero supported critical-task blockers and dispositions for serious/critical
  automated findings. Automated scans and device emulation are supplemental.
- `vps-network` requires the actual authorized GoDaddy Linux VPS, a separate
  external viewpoint and the actual Discord proxy journey. Record redacted
  plan, region, distro/kernel, TLS/Nginx/app/SQL versions and deployment
  topology. Observe HTTPS chain/renewal, WSS upgrade, heartbeat, idle intervals
  below and above 60s, reconnect/restart and private SQL/asset exposure.
- `vps-load` requires a reviewed owned-host budget and bounded independent
  generators on that pinned host. Load goes to owned backend paths and stays
  within explicit scope. Record applied safety stops and respect real Discord
  rate limits in that separate platform run.
- `vps-recovery` requires separate authority for faults and an isolated owned
  destination. Record source/destination versions, cut, data/assets/receipts
  hashes, consistency checks and achieved recovery. Report restore and
  graceful-restart observations independently. Missing authorization,
  unresolved resource isolation or shared-workload impact blocks execution.

Keep the proposed small, baseline and exploratory stress profiles at 4, 96 and
800 operations/s for 300, 900 and 60 seconds, respectively. Retain the research
workload mix, hotspot, payload/excluded-overhead assumptions and fault corpus.
Proposed p95/p99 milliseconds are durable ACK 250/750, peer visibility
500/1,000, cold launch 5,000/7,500, reconnect 3,000/5,000, foreground frame
32/50. Apply the research conditions per metric. Keep 60s warmup, three
independent baseline repetitions, at least 900s steady time and 10,000
measured new commands. Report per-run nearest-rank quantiles, sample counts,
clock/calibration error, offered/started/completed denominator and separate
timeout/loss/conflict/reject/throttle counts and generator scheduling lag.
Retain proposed 70% CPU maximum, 20% available memory/free data disk minimum,
10% unexplained post-drain RSS growth maximum, 50ms event-loop p99 maximum and
0.1% unexplained error fraction maximum. Stop on the research stop conditions;
unauthorized effects, tenant disclosure and acknowledged loss are integrity
failures. T11 owns operational SLOs, T10 deployment measurement and T5
data recovery parameters. These values describe an experimental workload and
candidate budgets. Hardware capacity, supported clients, freshness SLA and
numerical recovery objectives remain open.

## Closed evidence envelope

`VerificationReceiptV1` is an internal, strict UTF-8 JSON object. Maximum
16,384 encoded bytes, depth six with root at depth one, and 32 elements per
array. Reject duplicate keys at decode time, unknown fields, JSON coercions,
nonfinite or floating numbers, and malformed encoding. Common opaque tokens
use 1–96 ASCII characters from letters, digits, period, underscore and hyphen;
tokens begin with an alphanumeric. Digests are 64 lowercase hexadecimal
characters (SHA-256) and full Git commits are 40 lowercase hexadecimal
characters. Positive issue IDs are exact integers up to 2,147,483,647.
Use second-resolution UTC RFC3339 instants ending in `Z`. Canonical fixture
digests hash sorted-key compact ASCII JSON without a trailing newline.
Production raw-artifact digests hash the exact retained redacted bytes.

The envelope has exactly these fields:

| Field | Type and meaning |
| --- | --- |
| `version` | Integer 1. |
| `gateRow`, `environmentId`, `runId` | Registered row, registered exact environment reference, and unique run token. |
| `executionState` | `completed`, `invalid_configuration`, `prerequisite_unavailable`, or `interrupted`. |
| `cleanup` | `verified`, `untouched`, `pending`, or `failed`, backed by an independent inventory observation. |
| `artifactSha256` | Digest of the exact redacted bytes located by the nested artifact reference. |
| `evidence` | Closed projection implementing T9 `ReleaseEvidenceV1` below. |

The projection retains exactly T9's `version`, `candidateSha`, `nativeIssue`,
`scenarioIds`, `method`, `executedAt`, `environment`, `artifactVersions`,
`verifierRef`, `scope`, `evidenceClass`, `result`, `limitations`,
`artifactRef` and `findingDispositions`. Its integer version is 1.
Scenario IDs are nonempty unique registered tokens. Method, environment,
verifier, scope and artifact reference are opaque tokens linked to the approved
row registries. Artifact versions are nonempty unique-by-reference arrays of
closed `artifactRef, version` token pairs. Finding dispositions are unique
by finding reference and contain exactly `findingRef, dispositionRef` tokens.
Limitations is a nonempty printable ASCII string, up to 240 characters,
reviewed for privacy. Use `fixture`, `local_integration`, `hosted_ci`,
`real_discord`, `real_godaddy`, `independent_review`, or `post_merge`
and `pass`, `fail`, or `blocked` per T9. Resolve redacted refs only in
approved registries, never directly as network or filesystem paths.

A required row passes only with complete, attributable observations, verified
artifact integrity, approved exact candidate, exact row/environment/class, and
current authorization, scope and versions. Require verified cleanup for
completed resourceful runs, or independently observed untouched state for
resource-free completed checks. Invalid setup may satisfy its deterministic
negative scenario when the expected preflight rejection and zero effects are
observed in a completed fixture test. The failed target execution itself
remains blocked or failed. Unavailable prerequisites and interruption cannot
produce a passing target receipt. Independently compare asserted outcomes to
observations and maintain a positive control and a detection-sensitive negative
control. Do not derive observations from expected results.

Reject malformed data as `INVALID_RECORD` and a syntactically valid unknown
version as `UNSUPPORTED_RECORD_VERSION`. A missing registry, verifier
authorization, artifact or trustworthy time produces `DEPENDENCY_UNAVAILABLE`.
Stale revision/support configuration or missing exact evidence leaves the gate
pending; a verified failure remains visible and blocks. An exact-scope
non-applicability decision uses a separate recorded owner rationale with
approved alternate coverage when applicable. It cannot waive a mandatory
external row or create a passing receipt. Use T9's separate exception contract
where repository policy permits an exception. Redact secrets, session contents,
personal identifiers and unnecessary board content before retaining any
evidence. Security findings use the [private route](../../SECURITY.md).

## Release and rerun handoff

| Build to verification | Scope and review owner expertise |
| --- | --- |
| #392 → #393 and #395 → #396 | QE with Identity and Activity: E01–E03 harness behavior and distinct browser/actual SDK rows. |
| #399 → #400 and #402 → #403 | QE with T1/T2/T8/T9 Security and content/storage consumers: E04/E06, server authority and isolation. |
| #406 → #407 and #409 → #410 | QE with T4/T5/T8 and Security: E05–E07, deterministic real-engine and recovery evidence. |
| #413 → #414 and #416 → #417 | QE, Accessibility, T10/T11 and Security: real platform rows, registered workload dispositions, exact regression/smoke results and E08. |
| #455 → #456 | QE integrated [mandatory MVP rows](../../planning/MVP-ACCEPTANCE.md) and T13 approval, followed by separate publication #471. |
| #418 and T12 verification → #470 | QE integration handoff and T12 workstream acceptance, including all eight verification issues and #455. |
| #353, #378, #414 and #417 → #457 | T10/T11/T12 evidence and T13 production/GoDaddy gate. |
| #470, #456, #457 and remaining native blockers → #472 | T13 and maintainer stable v1.0 decision, followed by separate publication #473. |

The release matrix records stable requirement ID, scenario and environment IDs,
native verification issue, required class, responsible verifier role, candidate
SHA and artifact digest, result and trace receipt, open findings and authorized
disposition. Resolve live native blockers at approval. QE checks direct and
integrated coverage, Security verifies security effects and dispositions,
platform/Accessibility verify their own environment evidence, and the
maintainer/T13 verify applicable review and release authority. An independent
review receipt carries actual reviewer identity, full reviewed head, scope,
checks, findings and limitations. Review requests and stale reviews supply no
approval.

On change of candidate, fixture, observed environment/build, policy, or
required prerequisites, mark affected rows pending and record impact,
owner, rerun entry point, expected observations and the exact previous result
in the findings ledger. Re-run required checks and reviewers on the actual
candidate and retain both attempts. A prior pass contributes historical
context and can support a refreshed assessment only with a recorded relevance
decision and current-head verification. After merge pin the actual merge
revision and published artifact digest and rerun applicable checks. Release
evidence must still match the tested build. The T12 workstream records the
offline commands and limits of this specification's own local checks.
