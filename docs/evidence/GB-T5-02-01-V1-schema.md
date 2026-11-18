# GB-T5.02.01.V1 initial schema verification

On 2026-11-18 UTC, an independent run for [#149](https://github.com/CompleteTech-DiscordApps/guildboard/issues/149) passed on MySQL Community 8.4.11 and MariaDB 11.4.13-MariaDB-ubu2404. The run used the exact squash commit for [#148](https://github.com/CompleteTech-DiscordApps/guildboard/issues/148), delivered by [PR #558](https://github.com/CompleteTech-DiscordApps/guildboard/pull/558). The only supported source for migration 0001 is **empty v0**.

## Source and commands

- Commit `6f5e0b24f2e50fdca5e218a75bf0fd4266a21ef9`, tree `761c8f08cf117573fc154d2530ebcfaa5664c1c3`.
- Uncompressed `git archive` tar SHA-256 `72a71afe9a816902a91bff9ac827e6b372a8487152e4b28f2f8db5ad572b4af4`.
- [Migration SQL](../../database/migrations/0001_initial_innodb.sql) SHA-256 `045a76201bd00c399905a7e19b4f50c74dd141d00ca06eded8f3225c91987f8d`. [Installer and fixture instructions](../../database/README.md).

```bash
umask 077
bash "$handoff/verify-exact-initial-sql.sh" 6f5e0b24f2e50fdca5e218a75bf0fd4266a21ef9
```

Here `$handoff` is the private campaign handoff directory. The wrapper extracts `git archive` into a fresh directory and runs the local fixture against that archive on each engine. With the absolute `GB_SCHEMA_CLIENT`, `GB_SCHEMA_SOCKET` and fixture administrator in `GB_SCHEMA_USER` set, the fixture executes the [checked-in suite](../../tests/verification/test_t5_initial_schema.py) from the archive root:

```bash
python3 -B -m unittest discover -s tests/verification -p test_t5_initial_schema.py -v
```

The host was unprivileged x86_64 Linux (Omarchy) with Python 3.14.8. The preflight recorded Oracle's detached-signature verification of the MySQL archive and MariaDB's signed Noble package index verification. The run rechecked the MySQL input archive and fixture dependency hashes, and the MariaDB engine binary and package hashes. Each daemon had its own fresh private datadir, Unix socket, and isolated process environment. Both reported `skip_networking=1` and had zero owned TCP sockets. The suite created randomly named synthetic databases and a database-scoped read-only account. Both daemons exited 0, were reaped, and their sockets and disposable datadirs were removed by the fixture.

## Observed results

Eight tests passed on each engine with zero skips, comprising seven SQL-backed tests and one source-manifest test. Both runs checked the source digest and the engine-specific catalog manifest for all 20 ordered DDL steps. Catalog verification covers scoped tables, keys and indexes for boards, policy, operation events and receipts, outbox, snapshots, assets, audit and deletion.

| Scenario | Result on both engines |
| --- | --- |
| Clean install and repeat | Verify-only rejected empty v0. Apply activated v1, verify-only passed, and repeat apply left the owner epoch and completed count unchanged. Wrong generation and changed migration digest were rejected. |
| Interrupted DDL and retry | The fixture committed an ALTER while holding the migration lock. A second apply was denied while the owner held the lock. After the fixture terminated the owner client, verify-only rejected the incomplete phase. Apply recognized the single committed, unjournaled step and activated v1 at owner epoch 6 with all steps recorded. |
| Fencing and failure | Unexpected pre-activation data remained present, and a mismatched catalog left the journal epoch and completed count unchanged. An exhausted owner epoch preserved the one-table catalog. After activation, verify-only and apply both rejected a removed foreign key. |
| Scoped integrity | Cross-guild channel-default and deletion references and a same-guild cross-board lineage reference were rejected. A malformed deletion shape left zero deletion rows. A valid operation and receipt round-tripped the unsigned 64-bit maximum. The outbox prevented deletion of its referenced event, and the receipt survived event compaction. |
| Insufficient privileges | A SELECT-only fixture user connecting over the Unix socket reached preflight. Direct CREATE was denied with SQL error 1142. Migration apply failed without success output, and an administrator confirmed the catalog remained empty. |

## Retained evidence and defects

Raw output, per-engine initialization and server logs, signing receipts, and earlier failure logs are retained in the private campaign inventory. The independent run is indexed by receipt `sql-6f5e0b24.HmRZ5xfv`.

| Raw result | SHA-256 |
| --- | --- |
| `mysql-verify.log` | `a5acbfc700bfcc675f36b57b9a42fc2e9de9921d46dc457271a91fde954e9c8a` |
| `mariadb-verify.log` | `9b3b428959dce91c6435d4525f85833cebe63c41b190d0c15b5a4634d8b6b0cb` |
| `offline-verify.log` | `9b2acb8556b6c425c19a56ed38c73214f5e2dcf7756def87c5a09509d5abdbc7` |

A separate offline run of `python3 -B -m unittest discover -s tests/verification -p 'test_t5*' -v` passed 15 tests with seven explicit engine-only skips. Earlier #148 candidate runs found a short synthetic UUID and locale-dependent MySQL catalog output. The accepted implementation uses explicit session character settings and normalizes constraint-clause order while preserving column and index order. The early hosted architecture checks also rejected missing decisions for the database instructions, SQL and verifier. The merged change includes the missing boundary records DEC-0012 through DEC-0014. See the [exact implementation reviews](https://github.com/CompleteTech-DiscordApps/guildboard/pull/558#issuecomment-6967635991).

The interruption test ended a migration client while the database daemon kept running. Engine crash and outage durability, nonempty historical upgrades and backfills, serving startup and application authorization (including stale sessions), disaster restore, and actual Discord and GoDaddy operation remain outside this evidence.
