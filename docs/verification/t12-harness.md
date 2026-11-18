# T12 offline fixture harness

This foundation covers the fixture portion of [GB-T12.01.01.T1](https://github.com/CompleteTech-DiscordApps/guildboard/issues/392) under the [accepted T12 evidence contract](../specifications/GB-T12-S1-verification-evidence-contract.md). It uses Python's standard library. Run from the repository root on Linux.

```sh
python3 -m unittest discover -s tests/verification -p test_t12_fixture_harness.py -v
python3 -O -m unittest discover -s tests/verification -p test_t12_fixture_harness.py -v
python3 -m unittest discover -s tests/verification -v
python3 scripts/github-bootstrap/validate.py
```

Test consumers import `HarnessConfig` and `fixture_run` from
`scripts.verification.t12_fixture_harness` and use the context manager with a
caller-owned temporary directory with an absolute path and mode 0700. The run
allocates a private namespace inside that root and is used synchronously. The default fixture target supplies an immutable
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
| E03 catchable interruption | After the owned worker starts, the test delivers SIGINT to its own Python process while the fixture context is active. The context stops new worker starts and signals and reaps its one tracked child. The test checks the child was reaped, a separately owned child survives and only the unchanged filesystem sentinel remains. Unexpected contents in the namespace surface a cleanup failure and are preserved. |

The interruption case uses one fixed ordering (enter, start, interrupt, reap)
with seed 42. It covers cancellation in the active context after registration
of the worker. Signal interruption during resource acquisition, repeated
signals during teardown, default SIGTERM, SIGKILL and host loss are outside
this fixture result. The observer actor represents test data. The runner's
independent observations cover the local filesystem, child process and
preflight call boundaries.

This is fixture-class evidence. The remaining work requires a pinned accepted
SQL engine and migrated schema, a separate observing SQL connection, the
actual shared contract, API/auth, policy, storage and bot entry points, and
associated tests. F12 unavailable membership at a privileged action,
finite queue/quota and slow-consumer recovery, runtime resource inventory and
authorized reconciliation remain pending. Independent #393 verification,
browser/platform runs and release qualification require their own evidence.
