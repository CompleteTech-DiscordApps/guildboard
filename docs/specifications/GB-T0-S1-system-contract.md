# GB-T0.S1: proposed system boundary contract, revision 0.1

Status: **proposed, not accepted and not an implementation authorization**.
Issue: [#3](https://github.com/CompleteTech-DiscordApps/guildboard/issues/3).
Prepared 2026-10-24 against main `da811252acc975a0e5a1b087ab653b523443f3fa`.
Native prerequisite [#2](https://github.com/CompleteTech-DiscordApps/guildboard/issues/2)
and its delivery [#477](https://github.com/CompleteTech-DiscordApps/guildboard/pull/477)
remain unmerged. Architecture, security and consuming engineering reviews are
outstanding. This document does not alter issue readiness or Project fields.

## 1. Decision scope and evidence

This proposes the cross-workstream invariants that prevent independently built
components from disagreeing about identity, ownership, authorization or saves.
It does not replace T1–T13 specifications, select untested package versions, or
prove a running application. MVP means the integrated scenarios in
[the MVP matrix](../../planning/MVP-ACCEPTANCE.md); v1.0 additionally needs all
mandatory workstream and GoDaddy production gates. Neither is achieved here.

The input is the limited static research at PR #477 head
`47964d5b697aeae70e99403c6b42dfea0ace6816`, including its exact Excalidraw 0.18.1
and Discord SDK 2.5.0 artifact identities. It supports a controlled editor
experiment, not browser compatibility, distribution clearance or VPS readiness.
The main [boundary proposal](../architecture.md), all T0–T13 scope documents,
[security policy](../../SECURITY.md), and issue #3's handoff comment were reviewed.
No new external platform facts are asserted or measured by this specification.

## 2. Boundaries, ownership and data flow

```text
Untrusted Discord Activity / editor / imported files
  | HTTPS/WSS through verified Discord mappings (external trust boundary)
  v
GoDaddy Linux VPS: Nginx TLS + bounded ingress
  | private HTTP/WSS, explicitly trusted proxy hops only
  v
API transport + collaboration command service <--- verified bot interactions
  | session authority -> tenant binding -> policy -> command transaction
  +--> private MySQL/MariaDB: board/policy/revision/receipt/outbox/audit
  +--> private asset store: quarantine -> validated opaque objects
  +--> authorized accepted-event delivery / bounded replay
```

| Owner | Exclusive responsibilities | Must not do |
|---|---|---|
| T1 identity (`apps/activity`, server adapter) | SDK lifecycle, OAuth exchange, server-verified membership/session provenance and refresh | Trust client guild/role flags, expose bot/client secrets to iframe |
| T2 policy (`packages/auth`) | Pure allow/deny decisions from verified identity and current scoped policy; grant/mode/lock fencing | Infer authority from visible controls or presenter status |
| T3 canvas (`packages/canvas`) | Editor mapping, canonical supported element schema, tentative local state and accepted-state rendering | Write SQL or publish authoritative revisions |
| T4 collaboration (`packages/collaboration`) | Validated command sequencing, conflict/idempotency rules, replay and lossy presence | Acknowledge durable success from memory alone |
| T5 data/asset services (`database`) | Atomic durable state/receipts/outbox, snapshots, restore lineage and private assets | Accept unscoped object IDs or arbitrary filesystem paths |
| T6 modes | Proposed mode/presenter transitions through the same policy/transaction boundary | Grant editing merely by enabling presentation/follow |
| T7 UI | Accessible pending/saved/rejected/reconnecting state, deliberate retry/discard | Label tentative or timed-out edits saved |
| T8 transports (`apps/api`, `apps/bot`, `packages/contracts`) | Decode bounded HTTP/WS/interaction messages into shared commands and map safe errors | Duplicate authorization or trust body fields over session identity |
| T9 security | Review boundaries, abuse/retention controls and evidence | Treat a test stub as platform verification |
| T10/T11 platform/operations | Mandatory GoDaddy Linux VPS, private data plane, secrets, staged deploy/rollback, backups and measured recovery | Publish database/assets directly or claim an untested SLA |
| T12/T13 quality/release | Trace fixtures to implementation and evidence; publish only supported behavior | Close parents with mandatory incomplete descendants |

Browser packages may import public contracts and pure rendering helpers, never
server auth implementations, database clients, bot secrets or private modules.
Server transports call one command service; the bot does not bypass it. SQL and
storage adapters are injected behind server-only interfaces. T0 #20 owns
executable import-boundary enforcement. A single initial API/collaboration
process is proposed; correctness still uses database fencing so accidental
parallel instances cannot both allocate the same board revision.

## 3. Identity and authorization invariant

An authenticated server session supplies `(userId, sessionId, sessionGeneration,
verifiedGuildId, verifiedChannelAccess, expiresAt, membershipEvidenceVersion)`.
It is internal, never accepted from a command body. Guild/board IDs in URLs are
selectors only: resolve them under the session's verified guild, then compare
all referenced objects/assets to the resulting tenant. Unknown or foreign
resources return the same public `NOT_FOUND` response; internal denied reasons
are separately classified without board content.

T1 must define and verify exact Discord scopes, membership source, freshness
bound and event invalidation before privileged writes can ship. Unavailable or
stale membership evidence denies privileged mutations; it does not preserve a
previous grant indefinitely. Session expiration/revocation and tenant checks
apply to every command, not just HTTP login or WSS upgrade.

Policy decisions cover action, object ownership, current mode/lock, explicit
restrictions, role mapping, temporary grants and server-time expiry. An ordinary
writer cannot change mappings, self-grant, unlock or escalate to administrator.
A lock/lockdown denies ordinary content writes even with a temporary grant.
Presenter/follow changes do not imply content-write permission. Exact role and
mode matrices remain T2/T6 contracts; until an action is enumerated, deny it.

**Linearization:** each write transaction locks the scoped policy/board state in
a documented global lock order, validates the authoritative identity/session
and policy generation, applies expiry using server/database time, validates the
command and commits. Revocation, role invalidation, lock and grant changes
serialize against that same fence. A command committed before a revoke remains
accepted; no command using the invalidated authority may commit after the revoke
commits. Broadcasting a revoke before/after this point cannot substitute for
fencing. Multi-board or multi-guild effects require a separate reviewed contract.

## 4. Versioned command, receipt and error shapes

These are **proposed logical schemas**. T8 must publish executable strict schemas
and T3/T4 the payload schemas before runtime adoption. Unknown fields and
unknown command kinds are rejected, not silently coerced. JSON duplicate-key
handling and canonical hashing must be fixed by that executable codec; no
receipt hash may depend on an ambiguous parser representation.

| Shape | Required fields and constraints |
|---|---|
| Client command | `version: 1`, `requestId`, `operationId`, `boardId`, `lineageId`, `expectedPolicyGeneration`, `baseRevision`, `kind`, `payload` |
| ID encoding | Guild/user/channel: nonempty ASCII decimal strings, never JS numbers. Board/lineage/operation/request IDs: proposed lowercase UUID textual encoding. Server-generated correlation ID may replace untrusted request IDs in logs. |
| Counters | `baseRevision`, policy generation, event revision: canonical decimal strings `0` or nonzero digit followed by digits, unsigned 64-bit range; reject leading zeroes, signs and overflow. On exhaustion, stop writes safely; never wrap. |
| `kind`/`payload` | Explicit discriminated registry, owned by T2/T3/T4/T5/T6. Payload must pass the kind's strict schema and all resource/tenant checks. A generic arbitrary JSON patch or full-document replacement is not a supported command. |
| Durable receipt | `version:1`, `operationId`, `boardId`, `lineageId`, `revision`, `policyGeneration`, `outcome:'accepted'`; authoritative event body fetched only after current read authorization |
| Accepted event | `version:1`, `boardId`, `lineageId`, `revision`, `operationId`, `kind`, `payload`, server-derived actor attribution; only recipient-authorized fields |
| Rejection | `version:1`, safe server `requestId`, `error:{code,retryable}`; optional `retryAfterMs` only for throttling; no raw input, stack, token, SQL or credential values |

HTTP proposed mapping: `INVALID_MESSAGE`/`UNSUPPORTED_VERSION` → 400;
`UNAUTHENTICATED` → 401; `FORBIDDEN` → 403 after scoped access is established;
`NOT_FOUND` → 404; `CONFLICT`/`POLICY_STALE`/`LINEAGE_CHANGED`/
`IDEMPOTENCY_CONFLICT` → 409; `PAYLOAD_TOO_LARGE` → 413; `RATE_LIMITED` → 429;
`DEPENDENCY_UNAVAILABLE` → 503. WSS carries the same error codes. Clients must
not infer that a retryable/timeout response proves no commit occurred.

Proposed initial safety budgets, subject to T3/T4/T9 validation: 64 KiB decoded
command message; 100 element changes per compound; 256 KiB inbound queued
command bytes per socket; 1 MiB outbound durable queue per socket. Enforce byte
limits before expensive parse and expanded/decoded limits afterwards. Never
split a compound to get under the limit. Presence has a separate small schema,
coalescing and rate limit; it is not persisted. T3/T5 define image/geometry/asset
budgets; missing budgets block that operation kind rather than permit infinity.

## 5. Ordering, conflict, idempotency and save semantics

1. Scope the request and check current identity/session validity and read
   authority before accessing receipts or revealing state. Returning an existing
   receipt is not a new write and does not require current write permission;
   steps 4–5 require current write authority for every new operation. Operation identity is
   `(guildId, boardId, lineageId, actorUserId, operationId)`, not a global UUID.
2. Compute a canonical digest covering kind, payload and semantic preconditions
   (lineage, base revision and expected policy generation); exclude transport
   request ID. Same identity with different digest is `IDEMPOTENCY_CONFLICT`.
3. A prior committed receipt with the same digest returns the existing receipt
   only if the caller still has read access; it causes no new write or sequence.
   This applies to retained receipts from retired lineages after restore, before
   checking whether the command lineage is active. A different digest still
   returns `IDEMPOTENCY_CONFLICT` at step 2, even for a retired lineage. Current
   loss of write permission must not repeat the mutation. If the identity is no
   longer authorized to read, deny at step 1 without exposing the receipt or
   digest-match result. A historical receipt records acceptance in its original
   lineage; it does not assert that its content exists in the active document.
4. Only when no committed receipt exists, reject an inactive command lineage
   with `LINEAGE_CHANGED` before attempting a new write. For an active-lineage
   new operation, require current write authority and validate the latest
   authoritative fence and affected element versions. Proposed conservative
   conflict policy: reject stale
   affected-element preconditions; edits on distinct unchanged elements may
   proceed despite a newer board revision. T3/T4 must prove the adapter's
   precondition/compound/undo mapping before adopting this policy.
5. Apply all compound changes or none. In one database transaction commit
   canonical state changes, one increasing board revision, deduplication receipt,
   durable event/outbox and required audit metadata. Failed commands allocate no
   committed revision and leave no durable content side effects.
6. Send accepted acknowledgment only after durable commit. A crash after commit
   but before acknowledgment is resolved by retry with the identical operation
   identity/digest. A database timeout is an unknown outcome, not success or
   guaranteed failure. Never generate a new operation ID merely to retry it.
7. Outbox broadcast may duplicate; clients apply each `(lineage,revision)` once,
   detect gaps and recover. Delivery order alone is not durable ordering.

Undo/redo is a new authorized intent with affected-element preconditions, not
restoration of an entire old scene. Reject if it would overwrite another user's
subsequent change or resurrect a prohibited/deleted element. Group/connectors
must preserve referential constraints atomically. T3/T4 own exact transform and
conflict rules; this document does not claim these are implemented.

## 6. Recovery, snapshots, assets and lifecycle

Join/reconnect sends authenticated board selector plus last applied lineage and
revision. The server reauthorizes, then supplies bounded ordered missing events
or a consistent snapshot at revision S plus a tail strictly after S. Snapshot
metadata includes schema version, lineage, revision, content digest and scoped
asset references. Verify complete content and digest before replacing the
client's accepted state. Interrupted transfer never promotes a partial snapshot.
A slow client is disconnected with recoverable guidance rather than losing
accepted durable events.

Proposed receipt retention covers every committed operation in the active and
all retired lineages of a retained board, including its original scoped identity,
canonical digest and receipt fields. A document restore must preserve this
commit evidence even when it restores an earlier content checkpoint; it must
not roll receipt history back to that checkpoint. Restore publication, lineage
fencing and preservation of these receipts must be atomic from command
processing's perspective. Receipt storage/lookup is separate from bounded event
replay: snapshotting or event compaction cannot remove deduplication evidence.
This draft authorizes no receipt expiry, compaction or physical purge. A future
T5/T9 retention policy must explicitly define retry horizons, client handling
when commit evidence is unavailable, resource bounds and deletion obligations
before any such behavior ships. Missing durable evidence after disaster recovery
is not proof that a command never committed; the separate RPO/restore contract
must address that case rather than treating it as an ordinary document restore.

Restore/archive/delete increment a fencing generation and prevent stale active
writers from committing. A restore starts a new lineage with an audited reference
to the source checkpoint and preserves the previous recoverable lineage. The
§5 ordering is normative for this proposal: after current identity/read checks,
an identical retained committed operation returns its original receipt; an
identity/digest collision returns `IDEMPOTENCY_CONFLICT`; an old-lineage command
without a committed receipt receives `LINEAGE_CHANGED`. None of these paths
changes the restored document, allocates a revision or emits a new accepted
event. Never silently replay old commands into the new document. Board revision
within each lineage is monotonic. Physical purges
and backup retention are a separately approved T5/T9 policy, not implied by an
archive command. During deletion, existing sockets lose scoped access.

Client reconciliation keeps original operation identity, digest and preconditions
across unknown outcomes. A returned receipt from a retired lineage settles only
that operation's historical commit: clear its pending retry, but do not apply its
payload/event to the active document or mark the restored document saved from
that receipt. Rejoin/reconnect and validate the current lineage's snapshot/tail
before rendering its accepted state and save status. On `LINEAGE_CHANGED` for an
uncommitted old intent, reconcile current state and offer deliberate discard or
a separately authorized new intent with a new operation ID and current-lineage
preconditions. Do not automatically relabel or replay the old intent. Read denial
or a digest conflict cannot settle an unknown outcome as accepted or uncommitted;
keep it unresolved/rejected as appropriate without exposing protected history.

Compatibility handoff: the unaccepted T4 experiment in
[PR #484](https://github.com/CompleteTech-DiscordApps/guildboard/pull/484) originally
cleared receipts and rejected old lineages before lookup at head
`0bfdf0e976ffbe3de3cf22b5280b863db15e72fc`. Candidate head
`3379307f5b0e64c9b135307a160558347d7299f0` retains historical scoped receipts and
checks current identity/read access before receipt/digest lookup and lineage
rejection. Its dated follow-up evidence records 17 passing finite-model tests,
including historical lost-ack recovery without replay and old-lineage rejection
without a receipt. This reconciles the identified toy-model ordering difference;
it does not implement durable receipt storage or client reconciliation.
T4/T5/T7/T8/T9/T12 must still review precedence, retention and client recovery
together before adoption. Neither the toy's results nor these declarative fixtures
prove the proposed runtime behavior. This remains a proposed clarification, not
architecture acceptance.

Upload bytes enter bounded quarantine outside the web root, are validated by
content/decoded size, and become addressable only through an authorized opaque
asset ID after durable metadata binding. Never serve a quarantined or partial
file. Finalization and cleanup need crash-safe reconciliation because filesystem
and SQL are not one transaction; T5 must choose the exact protocol. Content
commands reference only finalized same-guild permitted assets. Unreferenced
cleanup cannot delete assets still retained by snapshots, history or backups.
Imports go through schema/limits/asset validation and an authorized atomic
operation; no user filenames become disk paths. Exports exclude credentials,
sessions, internal grants and unnecessary audit data; authorize each included
asset and review font embedding/licensing independently.

## 7. Proposed objectives, not measured promises

Before production capacity is advertised, T0 #6, T11 and T12 must accept a
workload, test duration and environment. Candidate baseline for that review:
10 active boards, 20 connected participants per board (up to 5 simultaneous
writers), 5,000 elements per board, each writer submitting 5 bounded operations
per second; assets excluded until separate byte/decoded limits are agreed.
Measure p95 durable command acknowledgment <=250 ms and p99 <=1 s at the server,
separately from Discord/client network latency, over a 30-minute steady workload.
Measure reconnect to current state <=5 s for the declared board size, report
snapshot bytes and RTT. These numbers are proposed test targets, not achieved
results or a staffing/hosting commitment.

Safety objective: zero acknowledged-operation loss on a process restart with
intact durable storage. Disaster recovery is different: proposed backup RPO
<=24 h and RTO <=4 h require an actual restore exercise and explicit acceptance
of possible data loss. Proposed monthly service availability target 99.5% needs
an agreed observation definition; it is not an SLA, guarantee or current result.
Single-VPS failure remains a real availability limit. Record unmet objectives,
not an inferred pass from unit tests or a green deployment job.

## 8. ADR alternatives and change/review procedure

Proposed alternatives: server-authoritative transactional log with explicit
stale-intent rejection; CRDT/OT with equally strong server authorization; narrowly
scoped editor fork if public hooks fail; custom canvas only after documented
adapter failure. Full-document last-write-wins is rejected for shared editing
because it can erase accepted intent and bypass per-operation checks. CRDT/OT
is not rejected universally, but needs element semantics, tombstone, undo and
revocation evidence before replacing the conservative proposal. In-memory-only
acknowledgment, browser-authoritative permissions and public database access are
not acceptable fallbacks. Managed Node hosting does not replace mandatory
GoDaddy Linux VPS production acceptance.

Every ADR records stable issue ID, status, version, exact evidence revisions,
alternatives, threats, schema/compatibility impact, migration/rollback boundary,
consumer handoffs and actual review links. Lifecycle: proposed → reviewed →
accepted only after required dependency and formal repository gates → superseded
with replacement link. Rejection/withdrawal is recorded, not erased. Major wire
changes require a new version with explicit compatibility negotiation and safe
unsupported-version rejection; additive changes still require schema/consumer
review. Never rewrite a previously accepted decision to hide its prior meaning.

Review responsibilities are expertise requirements, not invented appointments:
Architecture for boundaries; T1/T2/T9 for identity/revocation/tenant controls;
T3/T4 for editor/conflict/undo; T5 for SQL/durability/restore; T8 for transport
schemas; T10/T11 for platform/recovery; T12 for deterministic and real-platform
acceptance. Record reviewer, exact commit, findings and remediation; fresh
independent review follows material edits. Formal CODEOWNER approval remains
separate. A sole-author approval conflict is not resolved by writing “reviewed”.

## 9. Fixtures, traceability and acceptance still required

[Fixture scenarios](fixtures/GB-T0-S1-scenarios.json) are deterministic input/
expected-outcome specifications, **not executable product tests**. Each names
an invariant and consumer owner. T12 must implement them against real service
and database boundaries, including no-side-effect assertions. A fake Discord
adapter can exercise policy branches but cannot prove Discord membership APIs.

| Issue #3 clause | Reviewable artifact | Required result not yet obtained |
|---|---|---|
| Boundaries/trust zones/ownership | §§2–3 and transport-to-transaction flow | Architecture + T1/T2/T8/T9 review |
| Consistency and versioned schemas | §§4–6; fixtures F01–F22 | T3/T4/T5/T8 integration review and executable payload schemas |
| Errors/security/fixtures | Error table and negative/crash fixtures | T9/T12 no-side-effect and fault-injection evidence |
| ADR process | §8 | Maintainer/consumer review, native #2 gate and formal PR approval |
| Measurable scope/limits | §7, bounded-ingress proposal | T0 #6/T11/T12 accepted workload and actual measurements |
| Integration documentation | T0 handoff link | Post-merge evidence and truthful downstream adoption |

Unresolved implementation gates: Discord client/scope/membership/cookie/proxy
matrix (T1); role/mode policy and revocation freshness (T2/T6); editor echo/undo/
compound mapping and exact payload schema (T3/T4); database version/isolation,
receipt retention, snapshot/asset crash protocol (T5); dependency/font licenses
(#16/#17); real GoDaddy plan/image/TLS/WSS/storage/backup/rollback (T10/T11);
accessibility/load/security acceptance (T7/T9/T12). Record unavailable evidence
as blocked. No credential provisioning, purchase, deployment, runtime change,
legal clearance, acceptance or issue closure is performed by this draft.

Local checks for this documentation are planning manifest validation, JSON parse,
fixture ID/reference consistency and whitespace validation. They establish
repository/document consistency only. Commands/results are recorded in T0;
actual consuming reviews must be appended with verified links before acceptance.

```sh
python3 scripts/github-bootstrap/validate.py
python3 - <<'PY'
import json
from pathlib import Path
p = Path('docs/specifications/fixtures/GB-T0-S1-scenarios.json')
d = json.loads(p.read_text())
s = d['scenarios']
assert d['status'] == 'proposed-not-executed'
assert [x['id'] for x in s] == [f'F{i:02}' for i in range(1, 23)]
assert len({x['invariant'] for x in s}) == 22
assert all(set(x) == {'id', 'invariant', 'owner', 'given', 'when', 'expected'}
           and x['expected'] for x in s)
print('22 declarative scenarios structurally valid; product behavior not executed')
PY
git diff --check
```
