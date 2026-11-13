# GB-T5.R1: persistence and recovery research v1

Status: **proposed research, awaiting Data Engineering/security/consumer review**.
Refs [#146](https://github.com/CompleteTech-DiscordApps/guildboard/issues/146).
Date: 2026-10-25 UTC. Baseline `ac4f656`, package version `0.0.0`; runtime
persistence remains unimplemented. Production target remains a **GoDaddy Linux
VPS**, private MySQL/MariaDB and persistent private assets. No host was purchased,
provisioned or modified. Research SQL below is a disposable fixture, not an
accepted Guildboard schema, migration or application command implementation.

## Scope and compatibility inputs

Reviewed the live #146 issue, [T5 scope](../workstreams/T5.md),
[architecture proposal](../architecture.md), SECURITY and CONTRIBUTING. Supervisor
Project/native graph snapshot at 2026-10-25T23:30:54Z records #146 Ready research,
Backlog/Unblocked and zero native blockers. Live issue had no assignee/comments;
open PR inventory through #489 had no competing T5 research. Claim recorded in
the issue. No native dependency or readiness field was changed by this work.

Cross-checked [draft #481](https://github.com/CompleteTech-DiscordApps/guildboard/pull/481)
at `19d5f5a35511a1edf3a8bd34773fbb4d57546b89`: operation identity is scoped by
guild/board/lineage/actor/operation; current identity and read authorization precede
receipt lookup; same identity/digest returns retained historical receipt **before**
active-lineage checks; different digest conflicts; an unknown old-lineage command
cannot mutate the restored document. Content restore preserves receipts from all
retained lineages atomically with publication/fencing. A historical receipt does
not mean its content exists in the restored active board. No receipt expiration,
compaction or physical purge is authorized by that proposal.

[Draft #484](https://github.com/CompleteTech-DiscordApps/guildboard/pull/484)
originally used a toy restore that cleared receipts and checked lineage first at
`0bfdf0e976ffbe3de3cf22b5280b863db15e72fc`; #481 identified that mismatch.
The 2026-11-12 follow-up at
[`3379307f5b0e64c9b135307a160558347d7299f0`](https://github.com/CompleteTech-DiscordApps/guildboard/commit/3379307f5b0e64c9b135307a160558347d7299f0)
now retains retired receipts and performs current identity/read checks before
historical lookup. Its sequential scalar tests settle a committed lost-ack retry
without reapplying content into the restored lineage; absent old receipts still
fence old commands. This aligns the research candidates without proving a real
application retry protocol, storage retention, or client reconciliation.
The database fixture only demonstrates that preserving retired receipts is
feasible; T4/T5/T7/T8/T9/T12 must review the shared proposal before implementation.
All drafts remain provisional architecture.

## Primary sources, versions and dated observations

All pages inspected 2026-10-25 UTC. MySQL sources are its **8.4 manual**; MariaDB
and Linux manuals are rolling documents, not version-pinned binaries. Runtime
versions actually queried are **MySQL 8.4.11** and **MariaDB
11.4.13-MariaDB-ubu2404-log**. [Source response metadata](t5-source-observations.json)
records 12 successful bounded GET responses, dates and byte hashes, without
redistributing the bodies. Earlier custom-agent MySQL requests failed with
HTTPError; ordinary urllib GET succeeded. MariaDB's large system-variable HTML
exceeded the 4 MiB observation budget; its official `.md` representation succeeded.
Earlier failures remain recorded. Response hashes identify observations; they
cannot reconstruct bodies or prove product/platform compatibility.

| ID / primary source | Relevant source observation |
| --- | --- |
| M1 [MySQL 8.4 InnoDB settings](https://dev.mysql.com/doc/refman/8.4/en/innodb-parameters.html) | `innodb_flush_log_at_trx_commit=1` flushes commit logs; use `sync_binlog=1` with binary logging. Storage/OS can still misreport flush completion. We do not infer power-loss safety from settings alone. |
| M2 [MySQL consistent reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-consistent-read.html) | REPEATABLE READ consistent reads share a snapshot; READ COMMITTED reads can see newer snapshots. Ordinary reads and DML/locking behavior differ. |
| M3 [MySQL InnoDB recovery](https://dev.mysql.com/doc/refman/8.4/en/innodb-recovery.html) | Recovery applies redo and rolls back incomplete transactions. In-place crash recovery and recovery from an older backup are distinct. |
| M4 [MySQL mysqldump](https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html) | `--single-transaction --quick` supports consistent InnoDB dumps; concurrent DDL can invalidate them. Binlog coordinates/retention require separate PITR handling. |
| M5 [MySQL implicit commits](https://dev.mysql.com/doc/refman/8.4/en/implicit-commit.html) | Many DDL statements commit implicitly; wrapping a migration in BEGIN does not make arbitrary multi-statement DDL reversible. |
| M6 [MySQL foreign-key constraints](https://dev.mysql.com/doc/refman/8.4/en/constraint-foreign-key.html) | InnoDB constraints reject invalid parent relationships. Composite tenant keys must be explicit; foreign keys are not per-user authorization. |
| R1 [MariaDB InnoDB variables](https://mariadb.com/docs/server/server-usage/storage-engines/innodb/innodb-system-variables) | Recommends commit-log flush=1 with sync_binlog=1 for fault tolerance. Defaults/flush behavior vary by server version; record actual values. |
| R2 [MariaDB START TRANSACTION](https://mariadb.com/docs/server/reference/sql-statements/transactions/start-transaction) | Supports consistent snapshot/read modes. Select explicit isolation and prevent DDL from crossing the intended data transaction. |
| R3 [MariaDB physical full backup/restore](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/full-backup-and-restore-with-mariadb-backup) | Physical backup requires prepare before restore; copying raw live files is not a ready consistent restore. Physical backup was not exercised here. |
| R4 [MariaDB dump client](https://mariadb.com/docs/server/clients-and-utilities/backup-restore-and-import-clients/mariadb-dump) | Use mariadb-dump with a compatible client; newer dump sandbox commands can fail in older or MySQL clients. Do not assume cross-vendor dump interchangeability. |
| R5 [MariaDB JSON type](https://mariadb.com/docs/server/reference/data-types/string-data-types/json) | JSON aliases LONGTEXT with validation; differs from MySQL's native representation. Do not hash an engine-reformatted JSON representation as the canonical operation digest. |
| L1 [Linux fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html) | File fsync does not necessarily persist its containing directory entry; directory sync is a separate requirement. Local Windows file copies do not verify that Linux publication protocol. |

Recommendations below are research judgments based on these constraints and the
fixture observations, not additional vendor guarantees.

## Alternatives and recommended direction

| Choice | Alternatives and consequence | Proposed direction, pending specification |
| --- | --- | --- |
| Server | MySQL 8.4 versus MariaDB 11.4: both passed the narrow fixture; backup tools, JSON, DDL and operational behavior differ. Neither was benchmarked. | Prefer one pinned MySQL 8.4 InnoDB deployment as the initial reference, with MariaDB 11.4 retained as an evaluated alternative. Prefer the engine the actual GoDaddy image/operations can patch and restore reliably if that changes the operational evidence. No dual-engine compatibility promise or final selection. |
| Acceptance transaction | Memory-first ACK risks acknowledged loss; separate content/receipt commits allow partial acceptance. One InnoDB transaction can join content, event, receipt, outbox and audit. | Require current scoped authority/policy fence and affected-object preconditions in the transaction; ACK only after COMMIT. Establish a shared lock order and handle deadlocks/lock timeouts by rollback and bounded retry of the same logical identity. The fixture does not implement permissions or a general editor reducer. |
| Isolation / snapshots | Default assumptions are brittle. READ COMMITTED is useful for some writes but not a multi-query immutable cut without a separate strategy. Long snapshots retain undo and consume I/O. | Explicit REPEATABLE READ read-only consistent snapshot for a checkpoint, separate from short locking write transactions. Bound snapshot duration/work, serialize migrations, and validate actual indexed lock plans. Isolation alone does not enforce revocation fencing. |
| State/log storage | Full-document last-write-wins loses concurrent intent; unbounded replay grows recovery time; deleting receipts with compacted events breaks retries. | Materialized current state plus immutable versioned accepted events, scoped receipts and outbox. Snapshot S plus events strictly after S. Event/asset compaction and receipt retention are separate policies; do not purge receipts to make room. |
| Assets | SQL BLOBs simplify a common DB cut but grow backup/log I/O. Files outside SQL reduce that pressure but are not in the SQL transaction. | Evaluate private immutable opaque files with SQL metadata/reference manifests, bounded validation/quarantine and crash reconciliation. Include file+directory sync on Linux before publishing finalized references; do not claim rename alone makes SQL/files atomic. Small BLOB adoption remains an alternative, not a selected production schema. |
| Backups | Logical dumps are easy to inspect but slower for large restore; compatible physical backup plus binlogs can reduce recovery cost but adds tool/version/prepare complexity. Provider snapshots alone do not establish an application cut or an independent copy. | Start a measured logical-backup restore baseline; evaluate matched physical tools and PITR at representative size. Keep encrypted independent failure-domain copies of SQL, required logs, manifests and assets. No numerical RPO/RTO accepted from this tiny test. |

The version/collation/schema/protocol tuple must be pinned in the accepted T5
specification and migration manifest. IDs stay strings, counters need unsigned
range/overflow handling, and canonical digests come from the accepted T8 codec.
The fixture deliberately uses simple ASCII strings; it does not select production
collation, JSON storage, schema sizes, SQL grants or an ORM.

## Proposed transaction, crash points and tenant constraints

Resolve server identity/current read permission before revealing a receipt. Lock
the board/policy fence by its full tenant+board key, then perform the #481
receipt/digest/lineage decision order. For a new accepted command, validate current
write authority, generation, server-time expiry and schema limits, then commit
state change, monotonic revision, immutable event, receipt, outbox and required
audit atomically. Delivery occurs after commit; an outbox can redeliver. Consumers
deduplicate by scoped lineage/revision and reauthorize recipients, including
retired-lineage events after restore. No exactly-once transport claim follows.

Every relationship and unique constraint includes the verified tenant and board;
operation identity also includes lineage and actor. Index leading columns serve
scoped lookups. Retired receipts reference a retained board/lineage record, not a
foreign key requiring their lineage to equal the current board lineage. Avoid
CASCADE deletion that silently removes deduplication evidence. Foreign keys block
inconsistent cross-tenant references but cannot stop an application from selecting
a valid foreign tenant; route/socket/asset authorization tests remain mandatory.

| Crash/error point | Required outcome and remaining evidence |
| --- | --- |
| Before transaction or after state update, before COMMIT | No committed content/event/receipt/outbox; process-crash fixture D01 verifies one interruption point. Each internal statement boundary and disk-full/SQL-error rollback still needs fault injection. |
| During COMMIT / connection loss | Outcome unknown until original scoped identity/digest is reconciled. Do not label timeout as rollback/saved or generate a new operation ID automatically. Actual network ambiguity injection pending. |
| COMMIT returned, before application ACK | Durable bundle recoverable; fixture D02 kills after a SQL witness and confirms survival, not a real application lost-ACK test. |
| After publish, before delivery marker | Possible duplicate delivery; retain outbox and deduplicate, never repeat the mutation. Network publisher/crash test pending. |
| Content restore versus receipt history | Atomically publish new lineage/generation and restored content while preserving all retained receipts. Historical receipt settles only its old commit; never apply its old payload to active restored content. D05 proves narrow SQL preservation and zero-row stale selector, not service authorization. |
| Older backup restored after disaster | Missing receipt may represent a previously committed operation beyond the backup cut. Treat outcome as unknown under the RPO/restore contract; don't infer uncommitted or automatically reissue. Cross-backup reconciliation and client handling remain unresolved. |

Recommended runtime settings: InnoDB for every atomic table; verify and enforce
`innodb_flush_log_at_trx_commit=1`, `sync_binlog=1`, enabled binary logs for the
chosen PITR strategy, and doublewrite protection. Both local instances reported
these settings and O_DIRECT. Fsync success still depends on the GoDaddy host's
filesystem/block/cache guarantees. A container process kill leaves host caches
alive; it is not a power-loss or storage-controller test. Do not trade these
settings for throughput without an explicit accepted loss policy.

## Checkpoint, logs, assets and retention cut

1. Choose a scoped active lineage and consistent revision S using one bounded
   read-only snapshot; capture schema/codec version, canonical state hash and
   complete finalized asset manifest. Never combine a state at S with an event
   watermark from a later independent read. Do not mix DDL into this cut.
2. Write immutable snapshot/asset bytes, verify hash/length and Linux persistence,
   then publish metadata only when every required object is complete. A crash
   before publication leaves bounded quarantine/orphans, not public partial data.
   A SQL rollback after file persistence leaves reclaimable unreferenced bytes.
   Missing referenced bytes prevent restore publication, never a partial success.
3. Retain ordered events after S and verify contiguous revisions before replacing
   accepted client state. Keep immutable assets reachable from current state,
   history/checkpoints, retained logs, retained backups and in-flight restore pins.
   Collection requires reachability plus a reviewed grace/pin protocol and audit.
4. Create a backup manifest with engine/tool/schema/codec versions, lineage/cuts,
   complete SQL backup and log-chain coordinates, asset IDs/hashes/lengths,
   encryption/key access and validation status. Pin referenced immutable assets
   until the SQL backup's consistent cut is secured and its manifest committed.
   Asset deletion must not race that pin. SQL dump plus an unrelated file copy is
   not an atomic application backup.
5. Compact replay only after an independently verified checkpoint+tail and asset
   set exists and retention dependencies permit it. **Receipt evidence is not
   event replay**: preserve all committed receipt identities/digests/fields for
   retained boards and active/retired lineages under #481. This proposal authorizes
   no receipt expiry or physical purge.

Retention conflicts need a T5/T9 decision: retry horizons, board deletion, personal
data minimization, backup expiry, incident/legal holds where applicable and client
behavior when commit evidence is unavailable. Deletion must revoke active access,
record propagation through caches/files/exports/backups and ensure a restore
reapplies deletion requirements. No indefinite retention guarantee or silent
deletion policy is manufactured by this research.

## Board scale and bounded admission

Track durable bytes by guild/board plus global headroom: current state, event
tail, receipts+indexes, snapshots, assets/quarantine, undo/redo/binlogs, backup
staging, outbox and audit. A capacity estimate is `operations * measured retained
receipt bytes including indexes + retained event bytes + snapshots + reachable
assets + recovery reserve`; measure each term with representative payloads.
The tiny fixture's row count is not a production capacity estimate.

Define finite per-message/compound/element/asset/decoded-image limits, per-guild
storage budgets, connection/work queues, snapshot duration and backup staging
reserve before exposure. Reserve quota transactionally with acceptance so two
workers cannot both admit the same remaining capacity. At the high watermark,
deny new storage-consuming operations with an accepted explicit outcome and no
content/event/receipt allocation; permit authorized existing-receipt lookup and
safe recovery. Escalate capacity/reviewed retention before deleting anything.
**Never silently purge receipts or acknowledge writes whose evidence cannot be
retained.** Final numerical limits, storage amplification, adversarial load,
disk-full behavior and capacity-restoration procedure remain specification/load
tests; no VPS board count or latency promise is established here.

## Reproducible local experiments and observed results

The 2026-11-12 fixture safety follow-up can be checked without Docker using
`python tests/research/t5-test-db-probe.py -v`. Six fake-Docker tests cover
foreign/unlabeled volume collisions, ownership verification before database
launch, a create response lost after server-side success, foreign-resource
preservation and independent exact-resource cleanup. They exercise client
control flow only; they do not refresh the historical real-engine evidence below.


The [database probe](../../scripts/research/t5-db-probe.py) ran actual engines via
Docker Desktop 4.93.0 / Engine 29.8.1, linux/amd64, context desktop-linux, from
Windows PowerShell/Python 3.14.3. No image pull, port, host mount or shared network.
Each invocation creates its own labeled container and named data volume, capped
at 1 CPU/768 MiB/256 PIDs, one engine at a time. Synthetic no-password root is
confined to network=none and never a production credential recommendation.
Mutation/cleanup checks the exact invocation label; evidence confirms both
containers and volumes absent afterwards. Existing workloads were not targets.

```sh
python scripts/research/t5-db-probe.py --engine mysql --image mysql@sha256:6ea90827b1100f8f2ae306a539f86d2c264a26ed435a2a9f75551dd5c3aeb242 --output docs/research/t5-mysql-evidence.json
python scripts/research/t5-db-probe.py --engine mariadb --image mariadb@sha256:1292844148b311e4ed4300022a996d39083f415a963e970cf47cad1b3b18e3a6 --output docs/research/t5-mariadb-evidence.json
python tests/research/t5-test-assets.py -v
python scripts/research/t5-asset-manifest-probe.py
python scripts/github-bootstrap/validate.py
git diff --check
```

Images must already exist locally at those digests; the probe fails rather than
pull or substitute a tag. Output run IDs/timestamps and dump hashes can change;
the comparison is named check results and canonical fixture row equality, not
byte equality of database-run reports. The asset report is deterministic.

| Check | MySQL 8.4.11 / MariaDB 11.4.13 observed result |
| --- | --- |
| D01 process crash before commit | Pass / pass: no partial board/receipt/event/outbox remained. |
| D02 process crash after commit witness | Pass / pass: revision 2 and all three associated record counts remained 2. |
| D03 tenant/unique constraints | Pass / pass: duplicate scoped identity error 1062 and foreign composite-parent error 1452, fixture rows unchanged. Not application allow/deny evidence. |
| D04 consistent cut with concurrent writer | Pass / pass: reader retained revision/counts 2 and state-2 while separate writer/current reader reached revision/counts 3 and state-3. |
| D05 restore and retired receipt preservation | Pass / pass: restored content under new lineage retained op-3's old lineage/digest/revision; stale-lineage conditional update affected zero rows. |
| D06 logical restore | Pass / pass: dump imported into a fresh separate schema on the **same** isolated engine; every canonical fixture row equal. Not isolated-host/physical/PITR restore. |
| D07 checkpoint and ordered tail | Pass / pass: stored observed cut 2/hash plus ordered after-state event 3 matches state-3. Synthetic state assignment, not canvas reducer/general replay proof. |
| Local filesystem asset probe | Pass: copied bytes/hash match; missing/corrupt asset faults rejected. Nine adversarial tests cover count/byte limits, malformed digest, unsafe paths and directories. No SQL/filesystem atomicity or fsync claim. |

Evidence: [MySQL](t5-mysql-evidence.json), [MariaDB](t5-mariadb-evidence.json),
[asset copy](t5-asset-evidence.json). These are narrow executable fixtures; there
is no mocked SQL engine. The filesystem test uses real temporary Windows files,
not Linux volume durability. No hosted workflow was added; commands above must
be run explicitly. This work does not implement product auth, canonical codecs,
conflict handling, migrations, log compaction, PITR, physical backup or a complete
SQL-plus-assets restore coordinator.

Local verification: all 14 named database checks passed with both exact owned
container/volume cleanup receipts; restored canonical fixture row hashes also
matched across engines. All nine filesystem tests passed, and the checked-in asset
report equaled fresh CLI stdout (SHA-256
`f4e04e902f07072cfedaabca1fce3736615d7f0a0e79a2a4ba41c7ed94cfa634`).
All 12 source-response metadata entries validated. Planning validation passed:
471 items, 457 expected native relationships, 600 expected dependencies, zero
errors. Restored the validator's unrelated CRLF-only audit rewrite. Final
whitespace validation passed. The PR records the exact tested commit and hosted
checks; passing these checks does not complete the remaining runtime gates.

## Restore verification, rollout and remaining gates

An actual restore drill must use an isolated target and verify the complete
manifest/hash set, schema/tool compatibility, tenant constraints, snapshot plus
gap-free tail, retained receipt identity/digest/history, current policy/deletion
fences and asset accessibility. Exercise crash/retry at publication boundaries,
unknown outcomes beyond backup cut, pending outbox delivery, corrupted/missing
files/logs, unavailable keys and a partially uploaded backup. Keep the previous
recoverable lineage until reviewed acceptance; do not mutate production during
a dry-run restore.

Migrations need versioned expand/contract sequencing and application compatibility,
backup/restore rehearsal, interruption/retry tests and a documented forward repair
or rollback path. Arbitrary DDL rollback is not guaranteed by a transaction;
neither cross-vendor datadir reuse nor downgrade is an accepted rollback method.
The physical backup prepare chain and binlog/GTID recovery require matched tools
and a separate verified drill. Provider backups must be inspected for actual
plan-specific scope, retention, failure domain and application consistency.

RPO/RTO remain **unknown**. #481's candidate objectives are not measured promises.
Measure recovered accepted-operation loss against a recorded cutoff, time from
declared incident to verified application readiness, largest retained board/asset
set, restore byte volume, interruption count and failed runs. A local successful
dump import or restart is not a service RTO or evidence of surviving VPS disk loss.

| #146 clause / consumer | Research evidence | Unresolved acceptance |
| --- | --- | --- |
| MySQL/MariaDB transaction/crash strategy | M1–M3/R1–R2, D01–D03 and actual versions/settings | T2/T4/T5 real policy-fence/concurrency/unknown-COMMIT/network/disk-full tests |
| Snapshot/history/asset storage | M2/M4/R3–R5/L1, D04/D06/D07, asset fault controls | T3/T5 canonical reducer, SQL+asset cut/pins/fsync, physical/PITR independent-host restore |
| Retention and board scale | Separate receipt/replay retention, capacity formula and fail-closed admission proposal | T5/T9 accepted retry/deletion/backup retention, quotas and measured workload/storage amplification |
| VPS recovery and rollback | Required GoDaddy target, explicit settings and restore/migration test plan | T10/T11 exact plan/image/filesystem/versions/backup chain, operator access and measured RPO/RTO |
| Alternatives, primary URLs, version/date/uncertainty | Source register, response observations and immutable local image identities | Actual Data Engineering/security/consumer review and accepted #147 specification |

No actual reviewer, architecture acceptance, production security, compatibility,
merged state or issue completion is implied. #147 consumes this proposal; T4/T7/T8
must preserve #481's pending-operation/retired-receipt distinction; T9 reviews
retention/privacy and T10/T11/T12/T13 retain deployment, recovery and release gates.
