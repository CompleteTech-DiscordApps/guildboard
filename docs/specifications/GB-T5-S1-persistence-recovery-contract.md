# GB-T5.S1 persistence and recovery contract v1

Status: proposed for Data Engineering, security and consumer review under
[#147](https://github.com/CompleteTech-DiscordApps/guildboard/issues/147).
The accepted [T0 system contract](GB-T0-S1-system-contract.md) governs command,
receipt, sequencing and release semantics. [T9](GB-T9-S1-security-privacy-contract.md)
governs deletion, audit and privacy. [T5 research](../research/t5-durability-research.md)
supplies failure evidence and alternatives. [ADR 0004](../adr/0004-editor-and-database-selection.md)
selects the first MySQL/InnoDB experiment and a separately verified MariaDB
fallback. The storage interface requires equivalent evidence for each supported
engine/version. The production target remains private SQL and private persistent
assets behind the application on the GoDaddy Linux VPS.

## 1. Logical schema and privileges

The following are v1 logical relations. All relation keys include the indicated
scope even when IDs are globally generated. Use exact canonical byte comparison.
Use T0 ID and unsigned 64-bit counter encodings at interfaces. Persist counters
with lossless representation, allocate them with checked increments, and fail
closed at exhaustion. Versions are exact supported positive integers. The
command, event and receipt wire shapes remain T0 v1.

| Relation | Keys, references and required values |
| --- | --- |
| Guild | PK `guildId`, verified server-side guild identity and lifecycle state. |
| Board | PK `(guildId, boardId)`, guild FK. Lifecycle state, one active `lineageId`, active revision, policy generation, materialized canonical state and codec version. Active lineage FK uses the full board key. |
| Channel default | PK `(guildId, channelId)`, scoped board FK. Channel ownership is verified before publication. |
| Policy and grants | PK under `(guildId, boardId)` with trusted subject and policy-rule/grant ID. Board FK, versioned rule, expiry where applicable. Authoritative changes advance the board fence atomically. |
| Lineage | PK `(guildId, boardId, lineageId)`, board FK, immutable origin (creation, document restore or disaster promotion), optional parent lineage and source checkpoint with full scope, and initial/final cut when known. Retired lineages remain resolvable through retained references. |
| Accepted event | PK `(guildId, boardId, lineageId, revision)`, scoped lineage FK, command identity FK to receipt, event version, kind and deterministic canonical payload. v1 allocates one revision per atomic accepted operation, never per element or delivery. |
| Receipt | PK `(guildId, boardId, lineageId, actorUserId, operationId)`, scoped lineage FK, canonical digest including its codec version, original receipt and unique scoped accepted revision. No FK to a compactable event. Retain evidence across every retained lineage. |
| Outbox | PK scoped accepted event revision, event FK, bounded delivery state. Only committed events are eligible for delivery. Retain events referenced by unfinished outbox work. |
| Snapshot/checkpoint | PK `(guildId, boardId, lineageId, snapshotId)`, lineage FK, cut revision, format/codec version, canonical digest, byte length, finalized object reference, immutable asset manifest and optional authorized checkpoint label/attribution. |
| Asset and reachability | PK `(guildId, boardId, assetId)`, board FK, bounded validated metadata, hash, byte length, opaque immutable object reference, finalized state. Reference edges and pins bind the full scope on both ends and record their source cut/owner. |
| Audit and deletion | T9 logical schemas and authorized access. Scoped indexes and referential checks must preserve actor/action attribution and deletion scope. Independently protected deletion coverage and audit anchors remain outside the recoverable generation. |

Index scoped access paths for board history, ordered replay ranges, receipt
lookup, outbox scan, asset reachability and authorized audit retrieval. Composite
FKs, uniqueness, and indexed transactional validation together enforce scope,
including where a lifecycle/reference rule spans relations. Keep receipt and
lineage keys out of event cascades. Use verified guild/board selectors for every
join, FK, lock, cache key, and object lookup. Board duplication creates new
scoped references through an authorized source read and destination write with
validated assets. Object locators never grant access or accept client paths.
Separate application writer, migration, backup/restore and audit privileges.
Expose scoped reads through the application and T0/T9 release checks.

## 2. Schema change and recovery

Record each ordered migration ID, expected source/target schema versions,
immutable migration digest, compatible readers/writers and phase
(`planned`, `expanded`, `backfilled`, `verified`, `activated`, `contracted`).
Bind progress to the database generation and verify actual catalog/data
postconditions before advancing. Serialize migration ownership with a durable
fence. Stop startup or remain isolated when schema, migration identity or
compatible binary set cannot be verified. Use expansion compatible with still
running versions, followed by bounded resumable backfill with scoped durable
progress. Verify nullability, uniqueness and tenant FKs, canonical data and
receipt identities before activation. Concurrent writes must use a compatible
write path or be fenced. Switch only when all active binaries support the target.
Contract only after old processes are fenced and a verified recovery path exists.

An interrupted step is retried idempotently after checking its recorded progress
and actual effects, including a crash between DDL and journal advancement.
A digest mismatch, partial unrecognized catalog, incompatible binary or failed
verification stays fenced for reviewed forward repair or isolated restore.
For each migration require clean install and upgrade from every supported source,
retry at interruption boundaries, preservation of scoped data/receipts, and an
explicit rollback boundary. Before incompatible activation an older compatible
binary may resume after verification. Beyond that boundary use a verified
compatible forward repair or restore drill with a declared loss cut and current
T9 fences. Cross-engine datadir reuse and arbitrary DDL rollback are outside
the supported path.

## 3. Durable acceptance and uncertain outcomes

1. Authenticate and derive scope. Enforce current read authority before lookup.
   Validate bounded T0 shape before digest work. Bind the digest to canonical
   kind, payload and semantic preconditions including lineage, base revision and
   expected policy generation. Exclude transport request ID. T8 supplies one
   strict codec and digest conformance vectors shared by retries and persistence.
2. Serialize on the same scoped board/policy fence as authorization changes.
   For a retained identity, prepare its original receipt on an exact digest
   match or `IDEMPOTENCY_CONFLICT` on mismatch. Apply this before active
   lineage and new-write checks. Route these results through current read
   authorization at release. A denied request exposes a receipt-independent
   result under T9.
3. An absent receipt for an inactive lineage normally gets `LINEAGE_CHANGED`.
   During disaster reconciliation apply §5's uncertainty rule first. A new
   active-lineage operation requires current write authority, current policy
   generation, eligible lifecycle, object/version preconditions and quota.
4. In one durable transaction commit canonical state, revision, event, receipt,
   outbox, transactional quota effects and required audit metadata. Lock the
   scoped guild capacity row before the scoped board/policy fence when both are
   needed, and take dependent object locks in canonical key order. On uniqueness
   or serialization races, rollback and reevaluate the same identity through
   step 1. A proven rollback consumes no committed revision, capacity, outbox
   or acceptance record. Bound retries/deadlines and recheck authorization.
5. Release the accepted ACK only after a durable commit witness and at the
   T0/T9 serialized read-release fence. A failed release preserves prior durable
   state and the receipt. Outbox is at-least-once delivery with recipient
   authorization per release. Consumers deduplicate by scoped lineage/revision
   and recover gaps. A timeout, uncertain COMMIT result or lost ACK preserves the
   original identity, digest and preconditions. Return the T0 safe
   `DEPENDENCY_UNAVAILABLE` semantics where possible and reconcile with the
   same identity. Never infer uncommitted from timeout or synthesize an ACK.

Malformed/unsupported inputs use T0 errors. Unauthorized or cross-scope reads
use the T0/T9 concealment mapping. Authorized stale attempts use `POLICY_STALE`,
`LINEAGE_CHANGED` or `CONFLICT` as applicable. Exhausted admission uses
`RATE_LIMITED` when the capacity limit is explicit and
`DEPENDENCY_UNAVAILABLE` for an unavailable or uncertain storage dependency.
No denial creates accepted state, a receipt, outbox or acceptance audit. T9
allows separately bounded redacted denial telemetry.

## 4. Snapshot cut, immutable assets and bounds

Capture state, lineage, S, format/codec and complete scoped finalized asset
manifest from one bounded consistent read. Pin the cut and referenced objects
against compaction/collection before the read can lose their protection. Use
immutable bytes with canonical hash and length checks. For files, stage in
private bounded quarantine, verify validated canonical bytes and content type,
write and verify durable file and directory publication on the same filesystem
before SQL makes references reachable. An interruption before SQL publication
leaves private unreferenced bytes. Cleanup uses scoped inventory, verifies no
reachable or pinned references under an ordered fence, and is independently
retryable under approved deletion policy. Missing/truncated/mismatched assets
block publication or promotion. Authorize metadata and every queued chunk at
release, including snapshot, export and individual asset delivery.

Recovery chooses a target cut H on the same lineage with a retained snapshot at
S and a contiguous ordered tail (S,H]. Verify versions, exact scope, all hashes
and lengths, manifest reachability, count and no gaps or duplicates, then
verify final canonical digest at H before promoting. A later cut is a new bounded
read target. An interruption never promotes partial state. Retain events required
by authorized replay, incomplete outbox, recovery pins or backup coverage.
Replay compaction requires a verified alternative checkpoint and complete
reachable bytes, plus approved retention. Receipt retention is independent;
capacity pressure never authorizes receipt expiry or physical purge.

Apply T0 initial 64 KiB encoded command and 100-element compound caps. Require
positive finite deployment bounds for asset encoded and decoded sizes/dimensions,
element totals, stage duration and bytes, tail events and bytes, snapshot
bytes/transfer time, backup staging and concurrent work. Block the affected
path when a bound is absent. Check bytes before allocation and enforce decoded
limits during decoding. Reserve finite guild/board and storage headroom against
concurrent writes, snapshots and uploads. Include state, retained receipts and
indexes, events, assets/staging, backup, outbox, database logs and audit in capacity
measurements. At the high watermark retain recovery reserve and allow authorized
historical receipt reads. Exact launch thresholds require approved quotas and
measured operating-envelope evidence.

## 5. Distinct recovery boundaries

| Boundary | Cutover and outcome |
| --- | --- |
| Ordinary process restart | Reopen the same authoritative storage generation and lineage after schema/integrity validation. Recover committed state/outbox and resolve uncertain outcomes with retained receipts or safe same-identity retry. Keep the accepted revision monotonic. |
| Board document restore | Authorize current write and restore privilege, verified source checkpoint and assets. Serialize against writers and deletion; publish a fresh lineage at its verified baseline revision 0 and a higher policy generation, source checkpoint, prior recoverable head, restored state and scoped audit atomically. Retain all original scoped receipts. The publication is a durable visibility transition; old delivery is fenced. Old matching receipts settle their original acceptance only; a mismatch is a conflict and old absent receipt gets lineage change. Rejoin before rendering the new accepted state. |
| Disaster recovery | Restore the manifest, SQL/logs and pinned assets to an isolated generation. Record the actual recovered cut and independently verify integrity and T9 exposure prerequisites. Fence the prior serving generation and use fresh lineage identifiers and current policy fences before admitting new writes. Persist the cut and provenance of any incomplete historical receipt coverage. Matching retained receipts settle original acceptance after current read checks. For a missing pre-recovery receipt without affirmative completeness proof for that operation's history, keep its outcome unknown (`DEPENDENCY_UNAVAILABLE`); this applies even to an unrecognized historical lineage. Never manufacture a receipt or reapply old intent. With proven complete receipt coverage an absent retired identity follows `LINEAGE_CHANGED`. |

Normal restart cannot repair an older backup cut. A document restore preserves
receipt history and cannot cross guild/board or expose an already fenced target.
A disaster cut may lose acknowledged writes after the recovered cut. T7 keeps
those pending outcomes unresolved and offers deliberate reconciliation, with a
new identity only for a separately authorized new intent after rejoin. A receipt
from any retired lineage does not mark active content saved.

The disaster backup manifest records generation, engine/tool/schema/codec
versions, board lineage/cuts, SQL/log-chain coordinates, object IDs/digests/lengths,
applied deletion cut, encryption/key access reference and validation state. Pin
all cut-reachable bytes until the consistent SQL/log and asset manifest is
durable. Verify restore in isolation with all required keys and the complete
chain. Read authoritative deletion markers and current watermark from a source
independent of the restored generation. Verify uninterrupted coverage from the
applied cut through the exposure fence, apply markers, reapply revocations and
verify hidden content, assets, exports and references. Order exposure against
new deletions or re-reconcile at an equivalent fence. Keep the target isolated
on stale, unavailable, invalid, gapped or unapplied coverage.

Verify audit integrity against protected external checkpoints and an independently
anchored accepted sequence and integrity high-water mark. Verify continuity and
integrity through the accepted head including its active tail. Missing anchors,
truncation, and unanchored suffixes cannot establish accepted history. Require
the current authority, deletion and audit proofs, lineage/receipt integrity and
asset verification to hold before serving. Preserve failed isolation and audit
evidence for authorized operators.

## 6. Evidence and handoff

| Consumer | Required handoff |
| --- | --- |
| T2/T4/T8 | One scoped policy and release ordering, command/digest conformance, race and retry fault tests, and strict wire compatibility. |
| T3/T5/T7 | Canonical state and asset bounds, deterministic replay and hash verification, restored-lineage rejoin and honest pending/save states. |
| T5/T9 | Engine-level scope and migration tests, audit acceptance and anchoring, authorized retention and deletion policy. |
| T10–T13 | Isolated restore and cutover drills with current markers and audit provenance, tested VPS/filesystem, achieved RPO measured against accepted cut and RTO to verified readiness. Include interruption, disk-full, uncertain commit, lost ACK, incomplete backup, and stale-generation tests. |

[Typed bounded fixtures](fixtures/GB-T5-S1-scenarios.json) and the offline
verification test exercise the logical rules with synthetic identities and an
in-memory oracle. Actual T5 implementation remains gated on Data Engineering,
security and consuming engineering review and repository gates. Retention
durations, holds, quota policy and RPO/RTO objectives require designated owner
approval. Actual engine behavior, filesystem durability, migration interruption,
independent backup/restore and GoDaddy operation require downstream evidence.
Discord transport compatibility is T8/T10 evidence because this specification
defines storage and release requirements through the existing T0 boundary.
