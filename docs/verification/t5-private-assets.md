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
npm ci --offline --ignore-scripts
node --test tests/engineering/t5-private-asset-publication.test.mjs
npm run lint
npm run typecheck
npm run format:check
npm run boundaries
git diff --check
```

The offline install requires a populated npm cache. Planning changes additionally
require `python3 -B scripts/github-bootstrap/validate.py`.

The focused suite uses a temporary filesystem namespace. It covers pre-I/O
limit and integrity rejection, independent scope keys, concurrent identical and
conflicting attempts, matching retry, unsafe roots and targets, corrupted files
and preservation of unrelated stages. A test injects file and directory sync
failures and observes the real namespace between attempts. These checks establish
local file behavior and the ordering of sync calls. Hardware power-loss and
GoDaddy storage behavior, end-to-end resource accounting, and SQL reachability
need downstream verification.

### Process interruption and fresh-process retry

[#575](https://github.com/CompleteTech-DiscordApps/guildboard/issues/575) exercises
the existing publisher under the accepted
[T5 §4 boundary](https://github.com/CompleteTech-DiscordApps/guildboard/issues/147#issuecomment-6967090227),
[T9 quarantine boundary](https://github.com/CompleteTech-DiscordApps/guildboard/issues/293#issuecomment-6963112097)
and [bounded #189 claim](https://github.com/CompleteTech-DiscordApps/guildboard/issues/189#issuecomment-6967109274).
The test compiles the real API module and spawns a Node child for each attempt.
Only the child test harness wraps `FileHandle.sync`; the publisher has no
production fault hook. A trace records entry and successful completion of actual
file and directory sync calls. IPC identifies each deterministic barrier:

| Barrier | State after confirmed process death | Fresh-child retry |
| --- | --- | --- |
| `verified-stage`: after the stage's second file sync completes, following persisted-byte verification, before final linking | One complete private stage, mode `0400`; no final object | Returns `published`; creates one complete final object and preserves the abandoned stage |
| `before-directory-sync`: on directory sync entry, before calling the real sync, after linking and removing the attempt's stage | One complete final object, mode `0400`; no attempt stage and no delivered result | Verifies and syncs the existing file and directory; returns `already-published` |
| `after-directory-sync`: after the real directory sync completes, before returning from the wrapped call and delivering the result | One complete final object, mode `0400`; no attempt stage and no delivered result | Verifies and syncs the existing file and directory; returns `already-published` |

The parent sends `SIGKILL` only through the `ChildProcess` it spawned. It waits
for confirmed termination and closed child streams before spawning the retry.
Every barrier, result and exit wait has a five-second parent deadline. A
30-second child watchdog and exit on IPC disconnect limit abandoned harnesses;
cleanup also terminates and reaps owned children before removing the exclusively
owned temporary tree. There are no sleeps or process-name/PID discovery calls.

Each case uses 98,321 synthetic bytes, crossing the verifier's 64 KiB chunk
boundary, in a mode-`0700` directory. Checks compare exact bytes, SHA-256, length,
regular-file type, device, service ownership, mode `0400` and final-entry count.
The interrupted inode's identity, link count and modification/change timestamps
must remain unchanged across retry. An unrelated synthetic mode-`0600` sentinel
stage must keep its exact bytes, identity and metadata throughout. The pre-link
case additionally preserves the complete abandoned stage. Tests reject a wrong
barrier/trace, premature exit, an interrupted child's result, duplicate messages
or an unexpected retry outcome. All seven earlier cases remain in the suite.

On 2026-11-18 UTC the ten-case suite passed on Linux 6.18.57 x86_64, Node
v24.22.3, npm 11.9.0 and TypeScript 5.9.3, using local `/tmp` tmpfs storage.
The test-only change starts from publisher revision
`bed59c7db7f4b6592ddf9ad94e3e65812db251a6`; the PR validation receipt records the
exact tested candidate head/tree and command exits. The focused run observed all
three `SIGKILL` exits and successful clean retry exits, with no failures or skips.

This is local child-process and filesystem evidence. It does not prove hardware
power-loss durability or physical-storage guarantees from `fsync`, SQL reference
reachability or transaction acceptance, ingress decoding/scanning, authorization
or quota reservation, orphan deletion, Discord or GoDaddy behavior, or full #190
acceptance. Fresh independent functional and defensive review, protected merge
and focused post-merge verification remain separate gates. #189/#190 retain their
broader implementation and platform obligations.
