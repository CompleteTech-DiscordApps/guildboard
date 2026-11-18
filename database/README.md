# Database

[GB-T5.S1 §§1–2](../docs/specifications/GB-T5-S1-persistence-recovery-contract.md)
defines the scope and recovery rules for [migration 0001](migrations/0001_initial_innodb.sql).
MySQL Community 8.4.11 and MariaDB 11.4.13-MariaDB-ubu2404 have separate
catalog manifests. Other versions require separately verified manifests.

Guild, channel and user selectors use exact decimal bytes, with a 20-byte
storage bound. Canonical UUID selectors use their 16 decoded bytes. Validate
the T0 representations before selecting or persisting IDs. SQL counters use
unsigned 64-bit integers. Consumers must round-trip counters as decimal
strings or lossless integers and check increments before writing. The codec
and record version columns admit v1.

The board is created in one transaction with a temporary `initializing` row,
its lineage and its scoped receipt-coverage cut. Set both scoped pointers
as part of activation. Completeness rows are affirmative evidence for a
specific lineage under the board's published proof. Absence defaults to
unknown where the recovery contract requires it. Scoped logical rules and
grants belong to `board_policy_rules`. The authoritative transaction must
advance the board fence on policy changes.

Receipt identity and accepted revision are unique within their defined scope.
Events bind that exact identity and revision. An outbox entry pins its event.
Compacting a delivered event after approved retention checks leaves its
receipt intact. The snapshot object and finalized asset locators represent
privately published immutable objects. Insert them after publication and
verification. Snapshot edges bind the manifest and its assets to the same
board. Pins identify their same-board lineage, cut and owning operation.

## Install and recover v1 in isolation

Create a dedicated empty database on a privately configured supported engine
with TCP disabled, using trusted binaries. Keep the generation isolated
from application access while installing or repairing. Obtain its 128-bit
generation ID from trusted state independent of the schema. Provide local
socket credentials through the fixture account. Use a trusted migration
principal with complete visibility of this database's catalog and exclusive
DDL/journal authority. Separate migration, writer, backup and audit grants.

```bash
python3 database/verify_initial_schema.py \
  --client /absolute/path/to/mysql --socket /absolute/path/to/private.sock \
  --user fixture_user --database guildboard_fixture \
  --generation 0123456789abcdef0123456789abcdef --apply
```

Use the MariaDB distribution's `mariadb` client for that engine. Keep the
same trusted generation ID on retry. Omit `--apply` to require a matching
activated v1 journal and catalog without writing durable changes. An initial
activation records the `schema-v1` compatibility identifier for this empty
generation. Runtime startup and actual serving binary compatibility will
need to consume that identifier and enforce fencing.

A connection-held lock serializes this tool's work on the selected database.
The journal binds the immutable SQL digest, v0→v1, generation, migration
owner epoch and ordered completed step. Each autocommitted statement has a
reviewable catalog postcondition derived from complete engine SHOW CREATE
output. A retry accepts the recorded prefix or exactly the next catalog
prefix if its DDL committed before progress was recorded. It requires empty
application tables until activation. A verification failure keeps the
generation isolated. Preserve its journal and catalog, review the discrepancy,
and use a separately verified forward repair or a new isolated generation
from a trusted empty v0 source. After activation use an approved recovery
procedure with a declared loss cut and T9 fences. v0 is empty. There is no
historical nonempty release upgrade, backfill, or contraction in migration 0001.

Run the focused tests on a **disposable SQL instance** with
`GB_SCHEMA_CLIENT`, `GB_SCHEMA_SOCKET` and `GB_SCHEMA_USER` set. Use an
isolated fixture administrator. The tests create and drop uniquely named
synthetic databases and a read-only fixture account, and verify that the
read-only principal cannot create any migration object.

```bash
python3 -B -m unittest discover -s tests/verification -p test_t5_initial_schema.py -v
```

Application authorization, transaction ordering, lifecycle transitions,
stable IDs, canonical payloads, quota admission and append-only audit
privileges require their own verification. The externally protected deletion
watermark and audit anchor are outside this schema. Restore, storage object
durability, outage behavior and a GoDaddy deployment require separate evidence.
