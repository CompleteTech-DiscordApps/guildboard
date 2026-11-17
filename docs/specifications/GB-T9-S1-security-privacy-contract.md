# GB-T9.S1 security and privacy contract v1

Candidate for Security Engineering and consuming engineering review. The maintainer
claim covers this specification, synthetic acceptance fixtures and the workstream
handoff. The accepted system contract governs shared behavior, including where
its archival header retains proposal-era language. The research supplied eight
trust boundaries and cases A01–A11. This contract carries those decisions into
consumer obligations. Runtime evidence and release approval remain pending.
[Issue #293 and claim](https://github.com/CompleteTech-DiscordApps/guildboard/issues/293#issuecomment-6962774500),
[T0 acceptance](../workstreams/T0.md#evidence-and-handoff),
[GB-T0.S1](GB-T0-S1-system-contract.md), [GB-T9.R1](../research/t9-threat-model.md),
[research acceptance](https://github.com/CompleteTech-DiscordApps/guildboard/issues/292),
[SECURITY.md](../../SECURITY.md).

## Authority and trust boundaries

| Research boundary | Required defense | Consumer |
| --- | --- | --- |
| B1 Activity iframe and SDK | Treat SDK messages and browser/user/guild/channel/role/admin fields as untrusted. T1 verifies sender, application and launch context. T7 renders capabilities as feedback. | T1, T7 |
| B2 public HTTPS/WSS | Authenticate every route and operation, including direct ingress. For browser transports enforce exact accepted origin and redirect sets and session-bound CSRF protection where credentials are ambient. A socket upgrade supplies initial context. Recheck on join, reconnect, presence, commands and delivery. | T1, T8, T10 |
| B3 proxy and host | Trust forwarded metadata only from explicitly configured proxy hops. Enforce approved Host, scheme and external route mappings. Keep database, storage, debug and service listeners private. | T8, T10, T11 |
| B4 OAuth and membership | Bind each server exchange to a short-lived, single-use authorization transaction, initiating context and approved redirect. Concurrent or invalid redemption creates no extra session. Renew by rotating the session and rechecking authority. Revocation invalidates current session authority. Record T1's supported code-binding mechanism and exact minimum scopes. | T1 |
| B5 bot and collaboration | Verify interaction provenance, audience, freshness and replay handling before mapping to the same policy and command service. Role mapping, request-to-draw, grant/revoke, mode, restrictions and lock/unlock are enumerated capabilities. Unknown actions deny. No self approval, self escalation or moderator-to-admin escalation. Lockdown overrides ordinary grants. Presenter and follow status confer no editing power. | T2, T4, T6, T8 |
| B6 durable data | Scope all keys, queries, joins, caches, rooms, references, outbox entries and recipients by server-verified guild and board where applicable. Authorization covers ownership, visibility, channel access, restrictions, current role mappings, grants, mode and trusted time. Enforce atomic write and independent protected read fences. | T2, T4, T5, T8 |
| B7 assets and exports | Keep staged and finalized data private. Verify board and each included asset for every protected release. Constrain imports and exports to enumerated schemas, quotas and authorized storage. | T3, T5, T8 |
| B8 administration and recovery | Separate operator, deployment, evidence, data-plane and backup privileges. Use approved credential storage, scoped services, rotation/revocation and controlled restore. Keep server secrets outside source, images, URLs and diagnostics. | T9–T11, T13 |

Evidence of scope and authority comes from server sessions and verified membership.
Use the existing T0 tuple `(userId, sessionId, sessionGeneration, verifiedGuildId,
verifiedChannelAccess, expiresAt, membershipEvidenceVersion)`. T1/T2 specify the
evidence source, observation time, validity bound and invalidation path. Local
ordering applies when an authority change reaches the trusted boundary. Real
Discord evidence must characterize the interval before observation and the
behavior during an outage. Missing, expired or unverifiable required evidence
fails closed. Any provider credential required by the chosen SDK must use the
minimum tested exposure and lifetime. Never persist it in browser storage or
put it in URLs, logs, support evidence or exports.

## Commit, lookup and read release

1. Authenticate, bind tenant/board scope and check **current read authority
   before any receipt/digest lookup**. A denied caller gets a receipt-independent
   outcome and no protected response, lookup, content mutation, revision
   allocation, receipt creation or accepted event/outbox effect. Bounded redacted
   security telemetry may record denial without changing its observable outcome.
2. Use T0's operation identity `(guildId, boardId, lineageId, actorUserId,
   operationId)` and canonical semantic digest (kind, payload, lineage, base
   revision and expected policy generation, excluding transport request ID).
   Under current read authority, a matching retained receipt prepares the original
   receipt even after write access is revoked and even in a retired lineage. A
   collision prepares `IDEMPOTENCY_CONFLICT`. An absent receipt proceeds to
   lineage checking. On retired lineage return `LINEAGE_CHANGED` with no write.
   Treat any lineage or state dependent response as a protected result.
3. Every new active-lineage operation requires an affirmative current allow for
   its specific write or action. A fresh scoped read-only session still receives
   `FORBIDDEN` for a new write and creates no accepted effects. T2/T4/T5 serialize
   the authoritative commit check with revocation, grant changes, membership invalidation,
   session expiry/revocation, lock and lineage changes. Revalidate policy and
   session generations, current membership, trusted time, active lineage,
   grant expiry and command preconditions at commit. Missing, stale or unavailable required policy, trusted time
   or other authority evidence, or an unavailable fence, returns commit-stage
   `DEPENDENCY_UNAVAILABLE` with zero accepted effects. A proven generation
   mismatch returns `POLICY_STALE` under the T0 rules.
   Regrant must advance the fence and leave old prepared intent stale. If
   commit wins, canonical state, revision, receipt, outbox and required audit
   metadata are accepted atomically. If denial wins, commit none of those
   effects. An ACK is eligible only after durable commit. Confirmed rollback
   leaves no effects. Ambiguous storage outcome remains unresolved.
4. Serialize each transport release with session revocation, expiry, membership
   invalidation and scoped read policy changes. Recheck current session, fresh
   required evidence, applicable policy and trusted time at that boundary. Stale or unavailable
   policy or trusted time, or an unavailable release fence, returns egress-stage
   `DEPENDENCY_UNAVAILABLE` and suppresses protected output. This cannot change
   the commit result.
   Include live/replay events, ACKs, retained receipts, receipt/digest-dependent
   errors (including `LINEAGE_CHANGED`), snapshots, asset/export metadata and each queued chunk. For assets
   and exports check board and each included asset. A first-ordered valid
   release may complete. Revocation or unavailable authority ordered first
   suppresses that output and all subsequent queued protected chunks from
   that delivery, including under backpressure. Already released bytes cannot
   be recalled. Deny if the boundary cannot serialize the release. Direct
   storage and pre-signed URLs with only issuance-time checks fail this rule.
5. Use safe `UNAUTHENTICATED`, `NOT_FOUND` or `FORBIDDEN`, or
   `DEPENDENCY_UNAVAILABLE` according to the independently established denial
   reason. Compare absent, matching and conflicting receipts at both prelookup
   denial and release denial. In the latter case, authorize at prelookup and
   then remove authority immediately before egress. Compare a prepared
   `LINEAGE_CHANGED`, retained receipt and `IDEMPOTENCY_CONFLICT`. The public response/close behavior must conceal lookup branch,
   receipt existence, digest match, lineage and revision, including size and
   timing signals under the declared measurement envelope. Normalize observable
   metadata, allowing only unrelated opaque per-request correlation. A denied
   ACK leaves an already accepted commit intact and the caller's unknown
   outcome unresolved. Only the same identity and digest may reconcile that
   outcome through authorized retry.
6. A historical receipt settles only the original operation and clears that
   pending retry. It never applies the original payload to current state or marks
   the active lineage saved. T7 must perform authorized rejoin/resync and verify
   a complete active snapshot with matching schema, lineage and content digest
   plus any contiguous authorized tail needed to reach the active cut before
   advancing active accepted state or save status. Missing chunks or gaps
   leave active state and save status unchanged. An uncommitted retired intent requires explicit discard or a separate
   authorized new operation with new identity and current-lineage preconditions.
   Missing evidence after disaster recovery leaves prior outcomes unknown.

## Shapes, bounds and errors

T8 and producer workstreams own executable codecs. Use T0 §4 command, receipt,
event and rejection v1 shapes and its status mapping verbatim. Reject duplicates,
unknown fields and kinds, unsupported versions, noncanonical or overflowing
counters and malformed identifiers before scope-dependent processing, digest
calculation or receipt lookup. For an isolated schema defect emit only the safe
T0 rejection with a server-controlled request ID and no protected output or
accepted effects. The `malformed_command` fixture defines one replacement,
addition or repeated wire key per otherwise valid synthetic command. Duplicate
keys are evaluated before mapping the wire object to a key-value structure. Semantically
equivalent encodings must produce the same digest through a single canonical
codec. Authority, roles, audit fields and generation observations are server
derived. New fields, changed semantics and compatibility windows require an
explicit reviewed version. Runtime feature activation requires an accepted
finite profile for every applicable limit.

- T0's candidate ceilings are 64 KiB encoded command bytes, 100 changes per
  compound, 256 KiB inbound queued command bytes per socket and 1 MiB outbound
  durable queue per socket. Validate before adoption. Bound encoded bytes
  before parsing and decoded bytes, depth, field/element counts and parser
  work after decoding. Initially disable transport/message decompression.
  Never truncate a compound. Bound duration, rate, concurrent connections,
  storage and shared budgets per principal, board, guild and globally where
  applicable. Lossy/coalesced presence has a separate budget. Close slow
  consumers safely and recover through authorized resync while preserving
  accepted durable events.
- T3/T5 allowlist content and validate type and decoded geometry/size within
  finite parser and storage budgets. Quarantine off the public path until
  durable validated metadata binds an opaque object to scope. Never serve
  staged or incomplete data. Treat labels and filenames as data, render
  supported content inert, parameterize scoped SQL and map opaque asset IDs
  to server-held paths. Disallow arbitrary remote fetch and active content in
  v1. A separate accepted design is required before enabling either capability.
  T1/T7/T10 verify actual iframe-compatible content policy and origin allowances.
- T8 preserves T0's exact rejection fields and safe meanings. Unknown/foreign
  selectors share `NOT_FOUND`. A proven scoped denial can use `FORBIDDEN`.
  Use `INVALID_MESSAGE` for schema failure, `UNSUPPORTED_VERSION` for an
  unsupported version, `PAYLOAD_TOO_LARGE` for size violations and
  `RATE_LIMITED` for quota throttling. `retryAfterMs` is permitted only for
  throttling under the accepted bounded profile. Use `DEPENDENCY_UNAVAILABLE`
  when an otherwise eligible request lacks required authority evidence or its
  fence. Retries preserve operation identity and ambiguous outcome semantics.
  Responses and diagnostics exclude raw user input, tokens, stacks and storage
  details. Unknown/foreign and denied protected routes cannot receive
  receipt-derived errors, headers or body fields.

## Privacy inventory

| Class | Minimum purpose and access | Lifecycle trigger and copies |
| --- | --- | --- |
| Identity and membership | Discord identifiers, scoped role evidence and channel access for verified sessions/policy. T1/T2 services and specifically authorized support only. No profile expansion by default. | Evidence expires or is invalidated. Remove superseded records according to approved policy, including caches and linked derived indexes. |
| Authorization transactions, credentials and sessions | T1 exchange state and minimal session metadata establish and revoke access. Scoped production services and designated credential operators only. | Consume attempt state once, expire/revoke sessions, rotate credentials. No raw tokens in board, audit, evidence, export or general backup data. Isolate secrets recovery separately if required. |
| Board content and settings | Scoped readers, writers and policy administrators according to action. Includes content, configuration, event history, snapshots and any derived projections. | Board/account/guild lifecycle under approved policy, including scope-specific subject requests, deleted content, snapshots, replicas, caches and derived indexes. |
| Asset, import and export data | Scoped asset service and authorized recipients. Quarantine and temporary exports are purpose-limited. | Expire temporary artifacts, invalidate access on deletion and reconcile references in retained snapshots/history before approved physical purge. External copies already delivered are outside server deletion control. |
| Receipts and lineage | T4/T5 integrity, retry reconciliation and recovery. Current scoped read authorization for caller-visible receipt results. | Retain active and retired-lineage receipts, identities and digests for retained boards. Replay compaction and document restore preserve them. Receipt expiry/compaction needs a separately approved T0-compatible retry and recovery contract. |
| Audit and operational telemetry | Minimal scoped change/security evidence for designated reviewers and operators. Separate support telemetry from accountable audit. | Approved class-specific expiry and access review. Preserve only scoped incident evidence under a documented hold. Include sink copies and archived evidence. |
| Backups and deletion markers | Restricted recovery operators. Encrypted backup recovery and minimal deletion markers prevent re-publication of deleted or revoked state. | Approved backup window and recoverability policy. Markers remain effective over every restorable generation and pending retry/reconciliation window needed to prevent resurrection. |

### Deletion and recovery policy

Authorize and scope requests for board, guild or subject data under the applicable
owner-approved policy. The closed internal `DeletionJobV1` requires integer
`version: 1`, opaque server `jobId`, `kind` (`guild`, `board`, `subject`),
`target` and `phase`. Target fields are exactly `guildRef` for guild,
`guildRef, boardRef` for board and `guildRef, subjectRef` for subject. Phase is
`fenced`, `propagating`, `live_complete` or `complete`. Only an interrupted
propagation can carry optional `failure` from a bounded approved registry.
Malformed or unsupported jobs create no fence or lifecycle effects. Accept and fence atomically
against new access and writers. Disconnect or suppress stale queued delivery and
hide targets from readers. Keep failed or interrupted jobs in their last durable
phase with a bounded internal failure category, and retry idempotently. Inventory
and reconcile each affected live reference, replica, derived record, object/cache
copy and service-controlled export. `live_complete` requires verified live
removal or isolated restricted retention under an approved exception.
`complete` requires verified reconciliation of all required copies and expiry
or approved disposition of remaining exceptions. A rollback or retry must never
make data visible after fencing.

An approved encrypted backup copy or specifically scoped lawful/evidence hold
may outlast live removal only with documented authority, purpose, access,
review date, expiry and destruction criteria. Backups remain isolated with
restricted restore access. Before any isolated restoration can serve,
read authoritative deletion markers and their current high-water mark from a
source independent of the restored generation. Verify uninterrupted marker
coverage from the backup's applied cut through the exposure fence. Apply each
marker and confirm affected content, assets, exports and references stay hidden.
Serialize exposure against later deletion or recheck and reconcile under an
equivalent fence. Missing, stale or gapped coverage, or a later deletion that
has not been applied, keeps the restoration isolated. Reapply revocations,
enforce current authority and verify lineage and receipt rules before exposure.
T5/T11 own the platform adapter and isolation proof. Document
retained copies, expiry and the limits of external downloads in the approved
privacy disclosure. Distinguish document restore, which preserves receipt
history, from disaster recovery with potentially unknown historical outcomes.

## Audit integrity and incident evidence

The closed internal logical `AuditEventV1` requires `version` (integer 1),
`eventId` (canonical opaque ID), `occurredAt` (trusted UTC), `actorKind`
(`user`, `system`, `operator`), bounded opaque `actorRef`, `scope`
(server-derived guild/board references appropriate to the event, or explicit
system scope), `action` (registered action), `outcome` (`accepted`,
`denied`, `failed`), `reason` (bounded enum), optional scoped
`policyGeneration` (T0 counter, required for accepted scoped policy changes)
and server-generated `correlationId`. The exact scope union is `{kind: system}`, `{kind: guild, guildRef}` or
`{kind: board, guildRef, boardRef}`. Require an approved per-action registry for
scope, actor/outcome/reason compatibility and policy generation requirements.
A required audit record that fails validation blocks authoritative acceptance. Enumerate protected transitions including grant, revoke,
lock, unlock, restriction, role mapping, deletion, restore, privileged evidence
access and security administration. Exclude credentials and payloads, raw
selectors, free-form messages, board content and raw personal metadata.

Commit required acceptance audit metadata with its authoritative change. An
unavailable required audit path fails the mutation closed. Bound denial
telemetry separately. Use append-only write authority, separately scoped
read/export rights and independently verifiable integrity checkpoints. Ordinary
writers, moderators and operational application credentials cannot rewrite or
purge audit history, and viewing board data confers no audit access. Reconcile
against protected external checkpoints and an independently anchored accepted
sequence and integrity high-water mark. Verify continuity, record integrity and
the accepted head, including the active tail after the latest checkpoint.
Checkpointed history and accepted active-tail truncation both fail integrity.
No unanchored suffix is eligible to count as accepted audit history. An absent,
unavailable or stale anchor keeps verification blocked. T5/T9/T11 own the
platform adapter, ordering and atomic acceptance proof. Audit
access and approved retention/hold actions are accountable. Test redaction,
access, integrity alerts and independently controlled expiry. Preserve incident
evidence privately with limited custodians and verify integrity at collection and
transfer. Follow the reporting route in [SECURITY.md](../../SECURITY.md).

## Decisions and release evidence

| Owner decision needed | Required record | Until approved |
| --- | --- | --- |
| T1/T2 with Security Engineering | Discord evidence source/scopes, mechanism, validity/session/transaction bounds, observed invalidation delay and outage handling | Deny affected commands/delivery where provenance or freshness is unverified |
| T2/T4/T5/T8 | Lock/serialization and cross-worker commit/release proof, deterministic codec and T0-aligned error precedence | Deny where atomicity, current authority or release placement cannot be established |
| T3/T4/T5/T8/T10 with Security Engineering | Validated finite per-class ingress, parser, resource, queue and storage profile | Disable unbounded actions |
| Privacy decision owner designated by maintainer, with T5/T9/T11 and applicable legal review | Per-class purpose, lawful/product basis, access, retention trigger and duration, deletion/backup window, disaster recovery, audit/hold exception rules and user disclosure | Keep affected collection/features from release until policy is approved. No indefinite backup exception and no implicit receipt expiry |
| T9/T11 with Security Engineering | Audit registries and maximum field/entry sizes, checkpoint and verification protocol, access matrix, incident roles and expiry | Fail transitions that require audit if the required path is unavailable |

Accepted T0 invariants govern the candidate. This document supplies proposed
control requirements and assigns approval of unspecified values to consumers.
See the [research alternatives](../research/t9-threat-model.md#alternatives-and-recommended-direction)
and [server authority ADR](../adr/0002-server-authority-and-interactions.md).
Client authority, prepare-only authorization, direct public storage and copied
SDK tutorial defaults do not meet the accepted fences. T1/T8/T10 must document
selected session transport, tested origins and real platform constraints before
activation. Preserve GoDaddy Linux VPS hosting and its private data plane.

The closed `ReleaseEvidenceV1` requires integer `version: 1`, full
`candidateSha`, `nativeIssue`, nonempty `scenarioIds`, `method`, UTC
`executedAt`, `environment`, `artifactVersions`, `verifierRef`, `scope`,
`evidenceClass` (`fixture`, `local_integration`, `hosted_ci`, `real_discord`,
`real_godaddy`, `independent_review`, `post_merge`), `result` (`pass`, `fail`,
`blocked`), `limitations`, redacted `artifactRef` and `findingDispositions`.
Finding entries carry exactly `findingRef` and `dispositionRef`. Evidence
from a different candidate needs explicit relevance and current-head verification.

The closed `ExceptionV1` requires integer `version: 1`, `scope`, `severity`,
`approverRef`, `rationale`, nonempty `controls`, UTC `expiresAt` and
`closureCriteria`. An exception needs independently verified approver authority,
applicable scope, unexpired coverage and verifiable controls. A data retention
exception additionally requires a closed `RetentionExceptionV1` with integer
`version: 1`, `exceptionRef`, `purpose`, `accessPolicyRef`, UTC `reviewAt` and
`destructionCriteria`. The referenced approved exception supplies scope and expiry.

For these records, references are bounded opaque strings, timestamp fields are
UTC instants, and descriptive fields are bounded redacted strings. Evidence uses
a lowercase 40-hex Git commit ID, positive integer issue number, unique traced
scenario ID array, array of typed artifact reference/version pairs
(`artifactRef, version`) and array of finding entries. Release exceptions use
the approved severity registry and a unique array of control references.
Evidence and exception scope must match their registered gate or retention
subject and requested action. No free-form nested metadata or optional fields
beyond those listed.

All internal v1 records reject unknown/duplicate fields, wrong types, unregistered
values, wrong scope and missing fields as `INVALID_RECORD`, and unsupported
versions as `UNSUPPORTED_RECORD_VERSION`. Unavailable required registries,
authority or trusted time yields `DEPENDENCY_UNAVAILABLE`. Invalid, expired or
unauthorized exceptions confer no retention or release entitlement. Unverified
evidence blocks the release gate. These are internal result classes. Consumers
own finite encoding limits, registries and approval policies before activation.
Critical/high findings block release while unresolved without an authorized
disposition. Required evidence includes threat model review, authorization
negative tests, maintained dependency/license/lockfile provenance review, secret
and static checks with triage, upload/import defenses, actual independent
security review, real Discord client/session/iframe evidence, authorized
GoDaddy exposure/TLS/WSS verification and isolated restore with measured
recovery. Neither fixture passage nor hosted CI substitutes for independent
review or real-environment evidence.

## Consumer handoff

The [v1 scenario fixture](fixtures/GB-T9-S1-scenarios.json) is declarative and
synthetic. Use scenario IDs to trace requirements into native verification.
T12 must verify control effects at service, SQL, egress and client boundaries
and link dated platform results. T13 must require the actual release evidence.

| Native build → verify | Required handoff | Research coverage |
| --- | --- | --- |
| #296 → #297 | T1/T8 authorization transaction, session lifecycle, Discord client and credential exposure | A01, A03, A04 |
| #299 → #300 | T2/T4/T5/T6/T7/T8 scoped policy, effects, receipt and release-order proof | A01, A02, A05, A06, A08 |
| #303 → #304 | T3/T5/T7/T8 inert content, scoped SQL/storage and Discord-compatible content policy | A07 |
| #306 → #307 | T3/T4/T5/T8/T10/T11 quarantine, finite limits, backpressure and tenant isolation | A07, A09 |
| #310 → #311 | T5/T9/T11 approved inventory, expiry, deletion/hold, restore and disclosure | A08, A11 |
| #313 → #314 | T5/T9/T11 audit integrity, access, privacy and incident evidence | A06, A11 |
| #317 → #318 | T9/T10/T13 exact-build dependency, license, static and secret checks with triage | A10, A11 |
| #320 → #321 | T9/T10–T13 independent security review and evidence gate, including real Discord/GoDaddy and restore constraints | A01–A11 |

[#322](https://github.com/CompleteTech-DiscordApps/guildboard/issues/322) owns
integration documentation and privacy disclosure handoff. The
[#467 gate](https://github.com/CompleteTech-DiscordApps/guildboard/issues/467)
consumes all eight native verification items and #322 before T13 release
verification. This specification supplies no issue closure, control deployment
or production acceptance.
