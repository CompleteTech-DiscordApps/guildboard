# Source-report publication and return-handoff follow-up

Executable/helper/config/test revision:
`9a35817037d5983c7b7faccd5da89cd77f3e7072`.
Before revision: `c9b0e0f61ba290ec1da0d1d7d0e75990d2253d2b`.
A later documentation/evidence commit preserves all six source hashes in
[receipt.json](receipt.json), including `t10-report-publication.py`.

[Normal](suite-normal.log) and [optimized](suite-optimized.log) suites each pass
80 tests without skips. Ten new source methods cover 44 scenario executions per
suite: the large healthy/slow loopback report matrix exercises SIGTERM/SIGINT,
normal/optimized Python, buffered/unbuffered stdio and draining/closed/undrained
stdout. Additional cases cover small buffered closed-pipe output (the old exit
120 boundary), full stderr, output write failure, FIFO/symlink rejection, staging
signals and return/assignment handoffs. The Nginx handoff test uses actual local
Nginx; the Docker handoff test is a simulated command boundary, not actual Docker.

[Raw sanitized capture](source-publication.sanitized.json) records 20 before
cases and 21 fixed cases, plus an actual local Nginx 12-check baseline and all
six detected unsafe controls. Only cases with a captured slow-worker PID assert
PID-based worker reaping; unmeasured PID and file-before-drain fields are null.
Before cases with undrained stdout deliberately demonstrate the hang and rescue
only their captured owned parent process. Return-handoff cases use a trace hook
after an actual healthy fetch has completed, before the returned report is
assigned in `main`. They reproduce the old lost row and verify its retention;
this deterministic injection is not proof for every interpreter instruction or
a distributed/persistence race.

Both CLIs use the co-located, stateless `t10-report-publication.py` I/O helper.
Each CLI owns its own cancellation state. The source collector writes its full
requested JSON report **before** stdout. Ordinary publication retains the existing
summary; cancellation and requested-file failure publish the full result once.
Closed or undrained stdout cannot prevent the already complete file or replace
the first signal's 143/130 exit with a traceback or buffered exit 120. No second
JSON object is appended after partial bytes. A first signal during late staging
can be represented by final exit status rather than a field added to a frozen
snapshot. Completed source/Nginx reports remain referenced by their CLI state
across return/assignment; capture and network work are not signal-deferred.

`--output` accepts regular files only and rejects FIFOs/devices, including
symlinks to them, without blocking. If it cannot be written, an automatic
`guildboard-t10-source-report-*.json` copy is used when possible. Completed stdout
removes an automatic copy; interrupted/failed stdout intentionally preserves it
for caller retention/removal. Recovery notices on stderr are best effort and may
be dropped when stderr is full/closed. Use a valid `--output` file for a known
recovery location. A zero ordinary collector status preserves prior behavior:
inspect its summary/report failure rows to determine which HTTP observations
failed; it does not attest that every source was fetched or a platform worked.

Reproduce with explicit immutable worktrees and an owned Nginx binary:

```sh
python3 -B docs/research/evidence/t10-source-publication-2026-11-14/capture.py \
  --repository <FIXED_WORKTREE> --before-repository <C9_BEFORE_WORKTREE> \
  --tested-revision 9a35817037d5983c7b7faccd5da89cd77f3e7072 \
  --nginx-binary <OWNED_NGINX_BINARY> --output <CAPTURE_JSON>
```

The helper checks all six current sources and five pre-helper before sources
against exact Git blobs before running them. Explicit checks survive `-O`.
[Malformed capture checks](capture-rejections.json) reject a wrong before head,
a mismatched tested source and a modified shared helper under normal/optimized
Python, without executing the modified helper or creating a success artifact.
[Planning validation](planning-validation.json) passes 471 items, 457 parents and
600 dependencies; audit-file writes were disabled to respect the file lease.

Two-second stdout deadlines cover POSIX descriptor backpressure. Custom streams,
non-POSIX buffering, filesystem/kernel stalls, all unavailable destinations,
SIGKILL and host/power failure remain outside that bound; there is no fsync or
durable-backup guarantee. These are new-server loopback observations, without
real GoDaddy, Discord, public TLS/DNS, actual Docker or SQL recovery acceptance.
Old bundles remain unchanged; missing private laptop evidence and uncommitted
work were not recovered. Fresh full-head independent review, native approval,
protected merge and issue completion remain open.
