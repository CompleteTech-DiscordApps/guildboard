# GB-T12.S1 verification evidence contract v1

Specification candidate for [#389](https://github.com/CompleteTech-DiscordApps/guildboard/issues/389).
The native [#388 research](../research/t12-quality-engineering-research.md) is
closed following #498. Use the accepted [T0 disposition](../workstreams/T0.md#deliverable-disposition)
and [system scenarios](fixtures/GB-T0-S1-scenarios.json), the merged
[T9 control and evidence contract](GB-T9-S1-security-privacy-contract.md), and
the applicable domain contracts for expected behavior. The merged
[T13 documentation and release contract](GB-T13-S1-documentation-release-contract.md)
governs release bundles, approvals and publication evidence. Quality Engineering,
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
| E01/E02/E03 | Valid owned setup reaches the harness. Invalid configuration and unavailable setup prerequisites cause zero creates, binds or outbound calls. Separately observe F12’s unavailable privileged-action membership evidence and absence of privilege extension or accepted effects. Interruption reaps owned work and preserves the unrelated sentinel. Observe finite queue/quota and isolated slow-consumer recovery under T9’s resource profile. |
| E04 | Observe the actual decoder, ingress, protected lookup and policy boundaries. Compare authorized and denied viewer, expired/replayed session, stale role, forged claim and foreign guild/board/asset/receipt decisions; no durable or peer side effects on denial. Exercise accepted inert/bounded input controls and generic response equivalence for missing and foreign selectors. |
| E05 | Establish successful preparation, then withdraw each required commit-stage authority or dependency independently. Observe zero accepted effects. For independently ordered commit and revocation, cover both sides of the fence; confirm rollback and retained acceptance when delivery fails. Retry of the same verified scoped operation identity with the same canonical intent digest yields one durable effect. A changed digest on that identity conflicts only after current read authorization. Distinct operation IDs with the same digest can each produce a durable effect when authorized. Same-object/disjoint/compound operations and reconnect/late join converge to accepted revision and canonical projection. |
| E06 | Observe the serialized transport handoff and authority transition in both orders. Cover ACKs, current and historical receipt/digest/lineage results, events, replay, metadata and each snapshot, asset and export chunk. Observe protected bytes independently. Enqueue or preparation grants no release authority. A valid handoff ordered first may complete. Revocation, session expiry, membership invalidation or unavailable authority ordered first suppresses that output and all remaining queued protected bytes in the delivery. Preserve durable acceptance when ACK release is denied. Incomplete/quarantined asset read and reference produce no bytes or content write (F15). |
| E07 | Cover the three separate recovery cases below, including failed complete snapshot validation (F10), read denial after restore, historical receipt retry, digest conflict and unknown retired lineage. Verify each recovered boundary against independent SQL, receipt/outbox and persistent asset inventories. Compare canonical hashes and revisions and fence old writers. |
| E08 | Resolve actual release artifacts and required rows against current approval. Stale, missing or ineligible evidence remains pending or blocked. Keep verified failures visible separately. Review complete T9 security inputs and disposition evidence below.

Use T0 scoping for operation identity as
`(guildId, boardId, lineageId, actorUserId, operationId)`. The canonical intent
digest covers kind, payload, lineage, base revision and expected policy
generation. Transport request identity is outside the digest. Capture the scoped
committed operation and receipt inventory independently of
application state, and independently observe ACKs actually handed off before
the fault. Retain both before recovery with the fault boundary, lineage,
revision and identifiers so missing evidence can be measured by set comparison.
Report lost ACK deliveries independently of missing acknowledged operations.
An original committed receipt can remain durable when its ACK is fenced or
lost in delivery.
For **process restart with intact durable storage**, require zero acknowledged
operations lost, no missing committed receipt and identical authorized retry
for commit-before-ACK. For **document restore**, restore the approved content
cut in a new lineage and retain all committed receipts, including those beyond
that cut. Historical acceptance settles only the original pending operation.
For **disaster recovery**, require an approved recovery point objective and
isolated restore. Compare the actual recovered cut to the pre-fault inventories,
report possible and observed loss and achieved RPO/RTO with measurement
boundaries, and leave missing prior outcomes unknown. Assess isolated disaster
restore against the explicitly approved RPO and recovery criteria. The integrated
workload or authorized crash/recovery run stops on any missing acknowledged
operation under the research rules. Retain and report that failure even if a
separate isolated disaster-recovery exercise meets its approved RPO.

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
unauthorized effects, tenant disclosure and acknowledged loss in the integrated
workload are integrity failures. Record isolated disaster-recovery loss separately
against its own approved boundary. T11 owns operational SLOs, T10 deployment measurement and T5
data recovery parameters. These values describe an experimental workload and
candidate budgets. Hardware capacity, supported clients, freshness SLA and
numerical recovery objectives remain open.

## Closed evidence envelope

`VerificationReceiptV1` is an internal, strict UTF-8 JSON object. Maximum
16,384 encoded bytes, depth six with root at depth one, and 32 elements per
array. Global bounds apply before interpreting versions. Object keys are
opaque tokens. JSON values are objects, arrays, ASCII strings of up to 240
characters, or signed 32-bit integers. Reject duplicate keys at decode time,
coercions, nulls, booleans, nonfinite or floating numbers and malformed encoding.
V1 rejects unknown fields. Common opaque tokens
use 1–96 ASCII characters from letters, digits, period, underscore and hyphen;
tokens begin with an alphanumeric. Digests are 64 lowercase hexadecimal
characters (SHA-256) and full Git commits are 40 lowercase hexadecimal
characters. Positive issue IDs are exact integers up to 2,147,483,647.
Use second-resolution UTC RFC3339 instants ending in `Z`. Canonical fixture
digests hash sorted-key compact ASCII JSON without a trailing newline.
Production raw-artifact digests hash the exact retained redacted bytes.

The envelope has the following fields.

| Field | Type and meaning |
| --- | --- |
| `version` | Integer 1. |
| `requirementId`, `gateRow`, `environmentId`, `runId` | Registered requirement and row, registered exact environment reference, and unique run token. |
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
and `pass`, `fail`, or `blocked` per T9. Resolve redacted refs only in approved registries. The outer `environmentId`
is the same registered exact environment reference as nested T9 `environment`.

Resolve a required row from an independent approved registry keyed by
requirement and row. The registered tuple specifies native verification issue,
required scenarios and class, full candidate SHA, exact environment/build and
artifact versions, approved scope, method and verifier, run ID, redacted artifact
reference and digest, supported configuration, approval and freshness interval,
and authorized prerequisites. Resolve all fields and the current effective
approval and prerequisites using trusted time. Each grant resolves through a
registry that independently selects its permitted issuer by purpose and
reference. The grant must match that issuer, bind the selected row and
configuration, and be current both when the check ran and when it is evaluated.
The evidence freshness deadline also applies when the grant remains current.
Caller-provided expectations or incomplete metadata confer no qualification. An independent result observer and
a separate inventory observer each bind their observation to the same
requirement, row, candidate, environment, run and artifact digest under approved observer identities. The result observer binds
both execution state and result. Compare them independently of the receipt
claim and expected dataset. Require verified cleanup and
preservation of the unrelated sentinel for completed resourceful runs. Accept
untouched only for a resource-free completed check with independently observed
zero resource creation and zero owned remnants.

An invalid setup may satisfy a completed deterministic fixture check of the
expected rejection and zero effects. The target run itself remains blocked or
failed. Unavailable prerequisites and interruption cannot yield a passing target
receipt. Maintain detection-sensitive positive and negative observations.

Reject malformed input and unrecognized gate rows as `INVALID_RECORD`. A
well-formed field that differs from the approved scope, artifact reference or
other bound metadata produces ineligible evidence. A globally valid bounded
JSON object with a positive bounded
integer version field other than 1 returns
`UNSUPPORTED_RECORD_VERSION` after structural decoding and before interpreting
version-specific fields. A missing registry, authority, artifact or trustworthy
time produces `DEPENDENCY_UNAVAILABLE`. Stale evidence and class substitution
cannot qualify. Missing real-environment evidence stays pending. At evaluation time, a matching completed target observation yields a typed
verified pass or verified fail. A pass also requires successful cleanup. A
verified failure remains visible even if separately observed cleanup is pending
or failed. Stale, substituted, or incomplete observations yield ineligible
evidence. Missing dependencies and invalid records keep their controlled
qualification diagnostics and block credit. A verified failure on a required
row fails the matrix even alongside pending evidence. An exact-scope
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
| #455 → #456 | QE integrated [mandatory MVP rows](../../planning/MVP-ACCEPTANCE.md) and T13 approval, plus #446 for separate publication #471. |
| #418 and T12 verification → #470 | QE integration handoff and T12 workstream acceptance, including all eight verification issues and #455. |
| #353, #378, #414 and #417 → #457 | T10/T11/T12 evidence and T13 production/GoDaddy gate. |
| #470, #456, #457 and remaining native blockers → #472 | T13 and maintainer stable v1.0 decision, plus #446 for separate publication #473. |

The following crosswalk binds operational checks to the native issues that
supply the evidence. E08 checks qualification of those receipts.

| Requirement and verification issue | Minimum evidence class and row |
| --- | --- |
| Browser E2E, controlled launch/auth/navigation #396 | `local_integration` or `hosted_ci` on the actual Activity/browser with controlled SDK. Real launch/SDK compatibility observes the applicable registered `discord-*` rows as `real_discord`. |
| Supported client accessibility and performance #414 | `real_discord` for each supported client row with the applicable manual AT workload, plus `real_godaddy` on `vps-network` and `vps-load` for isolated GoDaddy verification and bounded workload. |
| Production networking #353 | `real_godaddy` on `vps-network` and separate applicable `real_discord` proxy-journey evidence. Include accepted-limit large-message delivery, safe oversized rejection, and reconnect/resync without fabricated acceptance. |
| Credential and disaster recovery #378 | `real_godaddy` on isolated `vps-recovery`, including E07 inventories and achieved recovery. Exercise the approved credential-recovery procedure with redacted verification of restored access and retired credential rejection. |
| Regression and production smoke #417 | `hosted_ci` for exact-build integrated regression. Production smoke requires the approved deployed build and `real_godaddy` on `vps-network`, with applicable `real_discord` client journey evidence. |
| Monitoring and rollback #457 | Consume #353, #378, #414 and #417. Require `real_godaddy` VPS network/recovery observations of current monitor signals and the approved rollback and recovery exercise, including service state and continuity checks. |
| T12 handoff #418 and workstream gate #470 | Both consume #393/#396/#400/#403/#407/#410/#414/#417 and integrated #455 with their applicable classes. #418 also depends on #389, and #470 depends on #418. |
| MVP and stable publication #471 and #473 | Consume exact-build gated artifact verification #446 plus the applicable release approval #456 or #472. Record `post_merge` verification against the actual published artifact when applicable. |

T9 security inputs require exact-candidate threat model review, authorization
negative tests, maintained dependency, license and lockfile provenance review,
secret and static checks with triage, upload/import controls and actual independent
security review. Evaluate these as required keys with class and method appropriate
to each input. Resolve the verifier and current approval for the exact tuple,
scope, run and redacted artifact bytes, including expiry and digest, just as for
other qualified rows. A standalone authority boolean supplies no evidence.

Require an independently approved, complete T9 findings inventory for the exact
candidate, scope, selected matrix keys and resolved receipt digests. Reconcile
the inventory's finding-to-receipt and disposition references with each linked
receipt's `findingDispositions`. An empty findings inventory requires the same
affirmative approval and receipt coverage. Missing or inconsistent inventories
block release. Resolve each critical or high finding against its exact receipt,
candidate, scope, severity, current disposition approval and retained
observations. Closure requires independent remediation verification for that
finding and hashes of the actual verification bytes. An exception requires a
separate, current permission from the repository policy authority and a closed
T9 `ExceptionV1` with the approver, rationale,
scope, severity, expiry, controls and closure criteria. Independently verify
current approver authority and the retained observations of controls and closure
criteria against that exact exception and disposition. A missing, altered,
unauthorized or expired record blocks release.

The release matrix records stable requirement ID, scenario and environment IDs,
native verification issue, required class, responsible verifier role, candidate
SHA and artifact digest, result and trace receipt, open findings and authorized
disposition. It resolves the full applicable T12/T9 row set from a currently
approved gate matrix with current native prerequisites. Approval can add
applicable rows but cannot remove the mandatory gate coverage. Resolve each
native prerequisite declared for that gate individually against its accepting
authority. Bind each decision to the exact candidate, scope and matrix, or
require the T13 compatibility assessment for historical evidence. Missing,
malformed or withdrawn authority leaves the gate pending. Each assessment
requalifies the current receipt, artifact, observers and grant for the same
requirement/row key, candidate, scope and trusted time. Separate
requirements may share one environment and carry separate receipts. Bare
status strings cannot substitute for a qualification. Resolve live native
blockers at approval. QE checks direct and
integrated coverage, Security verifies security effects and dispositions,
platform/Accessibility verify their own environment evidence, and the
maintainer/T13 verify applicable review and release authority. An independent
review receipt carries actual reviewer identity, full reviewed head, scope,
checks, findings and limitations. Review requests and stale reviews supply no
approval.

### T13 evidence and publication projection

Map the native issue number through the accepted backlog to its canonical
stable GB ID. For each gate-selected projection, re-resolve the current
approved requirement and row, exact receipt and artifact bytes, freshness,
prerequisites, and independent result and cleanup observations. Only a current
qualified pass supplies the T13
entry's `id`, `issue`, `revision`, UTC `date`, `environment`, `level`, `result`
and resolving `ref`. Map `fixture` to `synthetic`, `local_integration` and
`hosted_ci` to `integration`, `independent_review` to `independent-review`,
`real_discord` to `real-discord`, and `real_godaddy` to `real-godaddy`.
The linked original receipt retains its exact method, class, scope, limitations
and evidence digest, with the actual redacted observation bytes available
for verification. Both integration classes retain their source provenance.
`post_merge` contributes timing and revision provenance only. For an
applicable post-merge check retain and qualify a receipt with its underlying
execution or review class and method. No separate T13 level grants credit
for a merge event.

For #456, #457 and #472, apply the corresponding T13 gate and accepted
requirements to the projected entries. Recompute the entries from the approved
sources and require an exact match to the staged manifest. A caller-supplied
entry can confer no gate credit even if it equals a manifest entry. G1 requires
current real Discord startup evidence for GB-T12.MVP1. G2 requires current
GoDaddy production and recovery evidence. G3 also requires integrated and
regression results, the release fence, applicable client accessibility and
isolated platform network, load and recovery evidence. G3 independently requires the
`production-smoke` GB-T13.G2 `real-godaddy` entry and the authoritative
historical #471 evidence described below. The complete applicable matrix and
native prerequisites apply to each gate. For release automation #446 and
publication #471/#473, resolve actual staged payload, checksum index, build
provenance, manifest and reviewed notes bytes. T12's digest identifies the
redacted execution artifact. T13's candidate artifact digest hashes the
verified complete payload checksum index. Derive the complete candidate
identity from staged bytes, including exact manifest and notes hashes.
Resolve current native decisions and the actual authorized maintainer approval
for that gate, version, revision and all three digests, with matching
provenance and evidence references.

For stable #472, resolve accepted #471 evidence from its authoritative source
independently of the #472 candidate. Use the G1 MVP publication receipt,
candidate identity and canonical release URL designated there. Match both
candidate `mvpPublication` fields to that designation, recompute the historical
identity from the actual published bytes, and verify the historical G1 approval,
receipt, tag target and release bytes. Unavailable, substituted or unverifiable
evidence leaves #472 pending. An accepted #472 decision is a prerequisite for
the separate #473 publication.

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
