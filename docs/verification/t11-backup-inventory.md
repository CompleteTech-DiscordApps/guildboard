# Offline backup artifact inventory check

The fixture for [#374][task] checks a private synthetic bundle against an
independently supplied file inventory. The expected inventory represents a
single synthetic database cut, two required replay files, and its referenced
asset. Verification matches the exact member names, byte lengths and
SHA-256 digests. The fixture covers a missing replay member replaced by an
unclaimed asset, an interrupted asset write, equal-length corruption,
external links, nonregular entries, invalid expectations and an unsafe root.

Run with Python on Linux from the repository root:

```sh
python3 -B -m unittest discover -s tests/verification -p test_t11_backup_inventory.py -v
```

The inventory is fixed by the trusted test fixture before it creates the
bundle. A passing byte check establishes that the fixture can read the
expected files and match their bytes while the private directory is
quiescent. The SQL and log contents are synthetic opaque artifacts. Semantic
verification of the SQL/log chain, manifest authenticity, database lineage and
references, applied deletion cut, historic audit continuity, and isolated
restore require the additional proofs in the accepted [T5 contract][t5] and
[T11 contract][t11].

Operational acceptance requires T5/T10/SRE approval of backup schedules,
finish deadlines, maximum recovery-point age, retention and key policy,
plus a designated recovery role, a verified encrypted off-host copy and
an independently verified isolated rehearsal. Follow the [operations
guide][guide] for the approved staged procedure.

[task]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/374
[t5]: ../specifications/GB-T5-S1-persistence-recovery-contract.md#5-distinct-recovery-boundaries
[t11]: ../specifications/GB-T11-S1-sre-operations-contract.md#independent-backup-and-restore-acceptance
[guide]: ../godaddy-operations-guide.md#backups-recovery-and-rollback
