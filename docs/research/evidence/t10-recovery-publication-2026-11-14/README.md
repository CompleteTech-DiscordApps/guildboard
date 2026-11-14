# Report publication cancellation follow-up

Tested code/test revision: `b1ea6c99456d19b0560b63880e8b519bc0eb1f90`.
Before revision: `aae49862fc2c0c4cba63f4742cb8d02b4481cf2e`.
The later publication commit changes documentation/evidence only; source hashes
in [receipt.json](receipt.json) bind the executable, fixture, config and tests.

[Normal](suite-normal.log) and [optimized](suite-optimized.log) suites each pass
70 tests without skips on the recovered Linux/Python 3.12.3 server. Eight new
methods exercise 24 publication scenarios per suite, including real small-pipe
SIGTERM/SIGINT interruption, success and failure reports, requested/automatic
copies, non-draining stdout, full stderr, closed stdout, first signals during
serialization/staging, and FIFO/symlink output rejection.

[Raw sanitized observations](publication.sanitized.json) retain four actual old
CLI failures and ten corrected CLI cases, plus a separate actual local Nginx
12-check baseline and six detected unsafe controls. The publication cases use
an owned synthetic executable that fails startup with large diagnostics; they
do not claim actual Nginx startup failure or production platform acceptance.

The old CLI loses the complete JSON and returns 1 when a first signal interrupts
failure-report output. The corrected CLI stages a complete snapshot before
streaming. A signal, closed pipe or two-second POSIX stdout deadline retains
that snapshot, never appends a replacement JSON object, and returns the first
signal's status (143/130) when one was recorded. Ordinary publication failure
returns 1. A full or closed stderr may drop the best-effort recovery notice;
`--output` names the recovery location in advance and accepts regular files
only. An automatic `guildboard-t10-report-*.json` copy is in Python's selected
temporary directory, normally `$TMPDIR` or `/tmp`; callers retain or remove it
when interrupted output intentionally preserves it. Completed stdout removes
an automatic copy. Cleanup of owned processes/listeners is separate from this
intentional report artifact.

Reproduce with two explicit worktrees and an owned Nginx binary:

```sh
python3 -B docs/research/evidence/t10-recovery-publication-2026-11-14/capture.py \
  --repository <FIXED_WORKTREE> --before-repository <BEFORE_WORKTREE> \
  --tested-revision b1ea6c99456d19b0560b63880e8b519bc0eb1f90 \
  --nginx-binary <OWNED_NGINX_BINARY> --output <CAPTURE_OUTPUT_JSON>
```

The before worktree must be the exact before revision. The fixed worktree's
five source/config/test files must match the tested revision, even when HEAD
is a later documentation publication commit. Checks use explicit exceptions
and remain active under optimized Python. The helper records original byte
hashes; the committed artifact replaces private paths as described in the
receipt. Its old run is the actual old CLI with this capture orchestration,
not a claim that the old full test suite was rerun.

The stdout deadline applies to POSIX descriptors. Arbitrary custom streams,
non-POSIX backpressure, filesystem/kernel stalls, SIGKILL and power loss are
outside that bound. No durable-backup/fsync guarantee, real Docker, public
TLS/DNS, GoDaddy, Discord, native approval, merge or issue completion is claimed.
All prior bundles remain unchanged. Missing private laptop receipts and local
uncommitted work were not recovered by these new-server tests.

[Malformed capture checks](capture-rejections.json) show four explicit failures:
a wrong before-worktree revision and a mismatched tested-source revision are
rejected under both normal and optimized Python, before any success artifact.
[Planning validation](planning-validation.json) passes 471 items, 457 parent
links and 600 dependencies; audit-file writes were disabled to respect the
implementation lease.
