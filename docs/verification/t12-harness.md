# T12 offline fixture harness

This foundation covers the fixture portion of [GB-T12.01.01.T1](https://github.com/CompleteTech-DiscordApps/guildboard/issues/392) under the [accepted T12 evidence contract](../specifications/GB-T12-S1-verification-evidence-contract.md). It uses Python's standard library. Run from the repository root on Linux with procfs mounted at `/proc`.

```sh
python3 -m unittest discover -s tests/verification -p test_t12_fixture_harness.py -v
python3 -O -m unittest discover -s tests/verification -p test_t12_fixture_harness.py -v
python3 -m unittest discover -s tests/verification -v
python3 scripts/github-bootstrap/validate.py
```

Test consumers import `HarnessConfig` and `fixture_run` from
`scripts.verification.t12_fixture_harness` and use the context manager with a
caller-owned temporary directory with an absolute path and mode 0700. Use
the run synchronously in a single-threaded Python process. The harness validates the opened root and allocates the
namespace relative to its directory descriptor. The worker enters the pinned
namespace through procfs. Cleanup checks that the original namespace name
still identifies the pinned directory before removing it relative to the pinned
root. If opening the new namespace fails, the harness checks its recorded
identity before attempting to remove the empty directory. It reports a failure
if it cannot verify the entry or remove it safely. Treat `run.namespace` as a
pathname and keep the root and namespace names
stable while using it for fixture I/O.

The harness assumes cooperative ownership of the private root. Processes sharing
the effective UID and privileged processes can modify its entries. Namespace
creation and descriptor acquisition are separate operations, and the final
identity check and removal are separate operations. The harness depends on those
processes to leave the entries stable during those operations.

The default fixture target supplies an immutable
versioned dataset, a new UTC clock, and a local Discord membership lookup.
The seed controls dataset identifiers and stays independent of the namespace
and process identifiers. Advancing the clock leaves the worker's cleanup
deadline on real elapsed time.

| Case | Fixture observation |
| --- | --- |
| E01 valid setup | Concurrently open contexts have different namespaces and independent adapters and clocks. Equal seeds produce equal data. Changing the seed changes the fixture identifiers. Clock checks cover before, at, and after an expiry instant and reject invalid advances. |
| E01 invalid setup | Unknown target, invalid seed or timeout, and invalid root fail with field-name diagnostics before directory creation, worker startup, adapter construction or socket creation. The test observes the root inventory and sentinel bytes separately. |
| E02 unavailable integration prerequisites | Selecting `integration` yields `PrerequisiteUnavailable` with the missing capability names for the SQL engine, migrations, API, policy, storage and bot. The same preflight observations confirm zero setup effects. |
| Fixture selectors and identity | Two boards share the subject guild. A foreign board reuses board, asset, receipt and lineage selectors. The in-memory adapter distinguishes guild membership records for the same user ID and returns no membership for an unmatched pair. The dataset includes viewer, moderator, revoked, foreign control and distinct observer records. The test checks that the adapter path creates no socket. |
| Directory ownership | Replacing the root pathname before allocation leaves allocation, worker cwd and removal in the opened root. Replacing the namespace entry after it has been pinned causes cleanup to reap the child, report an identity change and preserve both directories. Independent filesystem observations verify the replacement directories and unrelated sentinel bytes. |
| Acquisition failure | An injected namespace open failure propagates the original error and removes the empty namespace. If the namespace contains an unexpected file, rollback reports a failure and preserves the file. Both tests verify that the unrelated sentinel remains unchanged. |
| Worker acquisition | A real child is created at a controlled barrier before `Popen` returns its handle. A SIGINT delivered to the caller at that barrier remains pending until the handle is registered. Cleanup reaps that child before removing the namespace, and a separately owned child and unrelated filesystem sentinel survive. Successful startup separately verifies the same reap-before-removal ordering. |
| Unknown worker outcome | A real missing-executable failure and injected exceptions before handle registration retain the namespace and report `fixture worker acquisition outcome unknown`. A caught startup error cannot permit a second acquisition. A simulated reap timeout retains the namespace and reports `fixture worker cleanup outcome unknown`. Test-owned fallback handles stop and reap every child created by the tests, with finite waits. |
| E03 catchable interruption | SIGINT after startup and during reap reaches the caller after owned cleanup. A single real SIGINT immediately before or after cleanup's initial mask read triggers bounded recovery, with independent reap-before-removal observations. The same entry barriers with injected reap failure preserve the namespace and chain uncertainty to the original interrupt. An original `KeyboardInterrupt` or `SystemExit` survives a cleanup failure, with a chained cleanup error and a note that resources may remain. Tests also observe caller-installed handlers, an unrelated blocked signal, a preblocked pending SIGINT, a failed block and a transient mask-restore failure. Unexpected namespace contents remain preserved. |

Worker acquisition and cleanup temporarily block only SIGINT on the calling
thread with `pthread_sigmask`; they do not replace signal handlers or signal
process groups. Restoring the exact prior mask delivers a pending SIGINT using
the caller's existing disposition. A preblocked SIGINT remains blocked and
pending until the caller unblocks it. If mask restoration raises, one bounded,
idempotent restoration attempt is made before propagating the error. Persistent
mask-operation failures are errors; caller state cannot be guaranteed if the OS
continues to reject restoration. The private probe child inherits the temporary
mask and is stopped using its own process handle and SIGKILL, then reaped with
the configured timeout. It starts no descendants.

If catchable cancellation interrupts cleanup before the SIGINT mask is installed,
the namespace descriptor remains open for one recovery attempt. The original
cancellation propagates after the known worker is stopped and reaped and the
namespace is removed. If recovery fails, cancellation instead carries the
cleanup failure as its cause and a note that resources may remain. Completed
resource cleanup is not repeated when restoring the caller's mask delivers a
pending interrupt. A resource failure is retained even if a pending SIGINT
arrives while restoring the mask; it prevents removal and is not retried into
success. The tests observe this combination with an injected reap timeout.

Before calling `Popen`, the run records acquisition uncertainty. Only storing
the returned handle clears that uncertainty. Any constructor exception therefore
quarantines the namespace, even a normal exec failure whose child Python may
already have reaped. Unknown outcomes require owner inspection; the harness
does not discover or signal processes from guessed PIDs. If a handle is known,
cleanup attempts its stop and reap before considering directory removal. A
failed stop/reap or unexpected directory contents prevents successful cleanup.

These tests use fixed barrier orderings with seed 42, not exhaustive signal
schedules. Real local child processes and SIGINT delivery are observed; the
reap timeout, exceptional acquisition and mask-operation faults are injected.
The SIGINT guarantee requires the documented single-threaded caller: masking
one thread does not prevent another thread from receiving a process-directed
signal. Concurrent callers, asynchronous injected exceptions, repeated signals,
other signal dispositions such as default SIGTERM, SIGKILL, host loss and
interruption during namespace creation/descriptor acquisition remain unverified.
There is no portability claim beyond Linux/procfs with Python 3.11 or later
(`BaseException.add_note` is used for failed cancellation cleanup). The observer
actor represents test data. The runner's independent observations cover the
local filesystem, child process and preflight call boundaries.

This is fixture-class evidence. The remaining work requires a pinned accepted
SQL engine and migrated schema, a separate observing SQL connection, the
actual shared contract, API/auth, policy, storage and bot entry points, and
associated tests. F12 unavailable membership at a privileged action,
finite queue/quota and slow-consumer recovery, runtime resource inventory and
authorized reconciliation remain pending. Production resource ownership, target
approval, lease expiry and a complete resource inventory are unavailable in
this fixture slice. Independent #393 verification,
browser/platform runs and release qualification require their own evidence.
