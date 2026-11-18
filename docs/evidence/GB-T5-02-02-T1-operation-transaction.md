# GB-T5.02.02.T1 isolated operation transaction

On 2026-11-18 UTC, an isolated InnoDB fixture passed five cases each on
MySQL Community 8.4.11 and MariaDB 11.4.13-MariaDB-ubu2404. This records the
SQL transaction portion of [#178](https://github.com/CompleteTech-DiscordApps/guildboard/issues/178)
under §3 of the [accepted T5 contract](../specifications/GB-T5-S1-persistence-recovery-contract.md).
The [independent initial schema verification](GB-T5-02-01-V1-schema.md)
records how the prerequisite migration was verified.

## Source and execution

The tests ran from an exact archive of commit
`41323d642dae51e82d2a2bb335888b2b1317c17d`. Each test installed and activated
the accepted v1 schema through the real verifier in its own newly named
synthetic database. The [migration SQL](../../database/migrations/0001_initial_innodb.sql)
SHA-256 was `045a76201bd00c399905a7e19b4f50c74dd141d00ca06eded8f3225c91987f8d`.

The private runner reused the preflighted signed engine inputs from the initial
schema evidence. It ran each engine serially with a freshly initialized private
datadir and socket. Both engines reported `skip_networking=1`, had zero owned
TCP sockets, exited with status 0, and were reaped. The runner removed the owned
datadirs and sockets. An earlier launch hit a scratch quota before the tests
started. That attempt's logs were retained and the failed disposable datadirs
were removed before the serial run.

With the absolute client and socket paths in `GB_SCHEMA_CLIENT` and
`GB_SCHEMA_SOCKET`, and the disposable fixture administrator in `GB_SCHEMA_USER`,
run this command from the archive root. Use the owned fixture with a
canonical Unix socket path and mode-0700 socket parent and sibling `data`
directory. The verifier checks the owner and the server's actual datadir
before creating any test database. See the
[initial fixture instructions](../../database/README.md).

```bash
python3 -B -m unittest discover -s tests/verification -p test_t5_operation_transaction.py -v
```

## Observed results

| Scenario | Observation on both engines |
| --- | --- |
| Commit visibility | The writer locked the board by composite guild and board key, checked its active lineage, revision and policy generation, then wrote the next revision and state, receipt, accepted event, pending outbox row and acceptance audit. Its separate observer saw only the baseline before commit and the exact five effects after commit. A control board in the same guild and an identical board ID in a different guild stayed unchanged. |
| Replay after discarding a local result | A new connection repeated the identity and digest and recovered the retained receipt even after synthetic write authority was removed. A changed digest returned the fixture conflict outcome and current synthetic read denial concealed the lookup. The committed collections stayed unchanged. |
| Denial and stale state | The fixture rejected malformed shape, denied read or write, a different actor, another guild or board, and a stale revision, lineage or policy generation. Neither the writer nor observer saw acceptance effects. |
| Rollback and SQL session failure | An explicit rollback removed all five staged effects. A duplicate audit primary key ended another staged transaction's client with an error, and the observer saw the original baseline. Retry then committed one exact result. |
| Duplicate contention | The contender was observed waiting at the scoped locking query while the first transaction held the row. After commit it resolved to the retained receipt, with one revision, receipt, event, pending outbox row and audit. |
| Lock timeout | A separate client holding no board lock returned native error 1205 after its bounded wait on the same scoped board. The observer saw the baseline, the owner rolled back, and the same operation identity could then commit once. |

The five named tests and their assertions are in the
[operation transaction suite](../../tests/verification/test_t5_operation_transaction.py).
Raw logs and both exit receipts are indexed in the private campaign inventory
under `sql-41323d64.9JbS3d8P`.

| Raw output | SHA-256 |
| --- | --- |
| `mysql-verify.log` | `b150cbe54b8b432d7c7a47f346b4dbb3b97ff12615dee3858ff131966ccd929c` |
| `mariadb-verify.log` | `44de71cd7c181bd43257cd53beddc287a6c05e384e70211d7f13722a71eb9f66` |

## Remaining verification

The fixture uses fixed authorized scope, decisions and opaque synthetic command
bytes. Product dispatch, T8 command and digest conformance, canonical edit
semantics, live T0/T9 authority and release fencing, transactional quota and
capacity, and the authoritative generation-bound commit witness remain open.
A lock wait timeout before mutation and a discarded local result leave uncertain
COMMIT recovery, daemon or host crash durability, transport ACK, outbox release
and honest client save status for integrated verification. The case remains
local to the owned engines with synthetic data.
