# Private asset publication evidence

[GB-T5.S1 §4](../specifications/GB-T5-S1-persistence-recovery-contract.md#4-snapshot-cut-immutable-assets-and-bounds)
requires same-filesystem file and directory durability before SQL references
become reachable. The internal API module takes canonical bytes, the expected
SHA-256 and byte length, and the full guild, board and asset identity from an
authorized caller. The caller supplies a positive finite deployment byte budget.
Validation precedes storage I/O, and publication works from a private snapshot of
the supplied byte view. Ingress validation and content checks, authentication,
authorization and resource reservations belong to the caller.

The deployment must provision a dedicated Linux directory owned by the service
effective UID with mode `0700`, outside every served path and under stable,
trusted ancestors. The filesystem must support same-directory hard links and
file and directory sync. Linux procfs must expose the open directory descriptor.
The service and its operators must control the namespace and serialize any
future collection or maintenance with publication. Names derive from a
versioned, unambiguous hash of the full identity tuple. The caller receives an
internal result without a filesystem path.

Each attempt exclusively creates its own randomly named stage. It writes the
bytes, changes the file to service-owned read-only mode, syncs it and verifies
the persisted bytes. A hard link installs the complete inode only if the scoped
destination is vacant. The attempt removes its own staging name and syncs the
directory before returning success. Exact retries verify length before reading,
hash in chunks of at most 64 KiB, and sync the file and directory again.
A safe existing file with a different length or digest returns
`ASSET_CONFLICT`. Unsafe entries and filesystem errors return a generic
`DEPENDENCY_UNAVAILABLE`. The directory descriptor anchors all file operations.
Existing entries require regular file type, expected device, service ownership
and mode `0400`. The verifier opens with no-follow and checks the opened inode
against the inspected entry.

If an attempt is interrupted before linking, its stage may remain private and
unreferenced. Once linked, the final object may remain after a lost result or
directory sync failure. A matching retry verifies and syncs it. Collection of
abandoned files requires the separate ordered reachability and pin checks in
GB-T5.S1. SQL reference publication, authorized delivery, ingestion and
scanning, retention, and orphan collection remain separate work under #189 and
its verification.

## Local verification

Run on Linux with Node 24 and the locked engineering dependencies.

```sh
node --test tests/engineering/t5-private-asset-publication.test.mjs
npm run lint
npm run typecheck
npm run format:check
npm run boundaries
python3 -B scripts/github-bootstrap/validate.py
```

The focused suite uses a temporary filesystem namespace. It covers pre-I/O
limit and integrity rejection, independent scope keys, concurrent identical and
conflicting attempts, matching retry, unsafe roots and targets, corrupted files
and preservation of unrelated stages. A test injects file and directory sync
failures and observes the real namespace between attempts. These checks establish
local file behavior and the ordering of sync calls. Hardware power-loss and
GoDaddy storage behavior, end-to-end resource accounting, and SQL reachability
need downstream verification.
