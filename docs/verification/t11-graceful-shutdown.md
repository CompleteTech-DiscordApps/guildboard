# Graceful shutdown evidence

[#367](https://github.com/CompleteTech-DiscordApps/guildboard/issues/367)
implements the process-local API coordination from the
[SRE operations contract](../specifications/GB-T11-S1-sre-operations-contract.md#incident-roles-and-handoffs).
Create one coordinator for the ingress paths that share a shutdown lifecycle.
Call `admit` at the final admission boundary before starting work. A readiness
check can read `isAcceptingWork()`. Only the synchronous admission decision
reserves an operation for drain. The admitted callback must return its full
operation lifetime. Its caller remains responsible for awaiting the returned
completion and applying the usual authorization, persistence and response
release rules.

Call `shutdown()` when the approved host integration initiates shutdown. The
call immediately closes admission, including reentrant admission, and returns
a shared promise on repeated calls. The drain result reports operations that
failed during the drain and those still pending at its cutoff. Pending work
can settle later and its original caller still receives its original result or
error. At the cutoff, uncertain commits must follow the authorized receipt
reconciliation procedure in the
[system contract](../specifications/GB-T0-S1-system-contract.md).

The host supplies three positive integer millisecond budgets with a combined
maximum of 2,147,483,647 milliseconds, the Node timer limit. Use budgets that
fit within the approved supervisor's stop allowance, including time for
process teardown. The monotonic drain deadline is followed by independent
budgets for the trusted socket-close/reconnect and telemetry-flush callbacks.
Each callback runs once, even if the earlier phase failed or exceeded its
deadline. A timed-out callback receives an abort signal. Callbacks must
cooperate with cancellation and avoid blocking the event loop. Synchronous
work and a stalled event loop can delay timer dispatch. Report callback failures
through the returned completion. Handle errors in detached host listeners
inside the adapter before they reach the host's uncaught-error boundary.

The host owns the socket set, the reconnect guidance permitted by the
transport, and the approved telemetry adapter. It can use the finite shutdown
outcomes and aggregate counts for diagnostics. The coordinator result carries
no client payloads, operation identifiers or callback error messages. Cleanup
outcomes describe the execution of the injected callbacks. Durable state and
receipt outcomes remain governed by T0, T4 and T5.

## Local verification

Use Linux and Node 24 with the locked dependencies.

```sh
node --test tests/engineering/t11-graceful-shutdown.test.mjs
node --test tests/engineering/t11-operational-log-reporter.test.mjs
npm run test:engineering
npm run lint
npm run typecheck
npm run format:check
npm run boundaries
npm run build
python3 -B tests/verification/test_t11_sre_operations_contract.py -v
python3 -B scripts/github-bootstrap/validate.py
git diff --check
```

The eight top-level focused tests compile and execute the API module. The six
original tests cover invalid budgets and missing callbacks, synchronous
admission cutoff, ordered drain and cleanup, reentrant shutdown, operation and
callback failures, and independent deadlines with late settlement.

The two additional tests contain 24 deterministic subtests. They use a
test-context mock of the shared `performance.now()` and frozen Node mock timers,
with no timer dispatch, sleeps or real-clock timing assertions. Each subtest
checks automatic restoration of the clock and timer functions before its
sibling runs. Controlled operations fulfill or reject one millisecond before,
exactly at, and one millisecond after the monotonic drain deadline. Original
value/error identity is preserved. At and after the cutoff the snapshot reports
one pending operation and excludes that settlement from pre-cutoff failure
counts; before it, the operation settles normally and a failure is counted.

Both cleanup phases are tested at the same three boundaries with fulfillment,
rejection and synchronous failure. At and after the cutoff each returns
`deadline-elapsed` and aborts its signal. The neighboring phase still runs once
under its own budget, including telemetry after expired reconnect cleanup.
Before the cutoff, successful and failing cleanup retain their normal outcomes.
Repeated shutdown calls preserve the shared completion and cutoff snapshot.
These cases cover existing settlement-time cutoff branches; they do not fix a
demonstrated production defect or change the coordinator API or contracts.

On 2026-11-19, Linux with Node 24.22.3, npm 11.9.0 and Python 3.12.14 passed
the focused shutdown command (32 tests), the sibling log-reporter command
(11 tests), `npm run test:engineering` (155 tests), `npm run lint`,
`npm run format:check`, the SRE operations contract command (14 tests), the
planning validator (471 items, 457 expected native relationships, 600 expected
dependencies, zero errors), and `git diff --check`. All commands exited zero;
the reported test runs had no failures or skips. These are local synthetic
fixture and repository checks, with no real Discord, GoDaddy, durable database
or supervised restart acceptance evidence.

## Staged restart acceptance

The deployed API ingress, socket and telemetry adapters, durable operation and
receipt path, and an authorized supervised environment are needed to complete
[#367](https://github.com/CompleteTech-DiscordApps/guildboard/issues/367) and
its [independent verification](https://github.com/CompleteTech-DiscordApps/guildboard/issues/368).
Exercise the supported systemd/Compose configuration on that environment.

1. Start with isolated authorized synthetic traffic and record the build,
   supervisor configuration, operation receipt, revision and board state.
   Trigger a supervised stop with an admitted operation in progress. Confirm
   that readiness drops, new work is refused, and admitted work can still
   finish. Observe mapped WSS reconnect guidance, telemetry flush and exit
   within the approved allowance.
2. Interrupt a run near the commit boundary and deliberately lose a response
   after a separate known commit. After restart, reconnect and reauthorize
   through the actual transport. Reconcile the original scoped operation,
   identity, digest and preconditions. Verify the retained result and compare
   the durable revision, canonical board state and outbox effects against
   independent observations. An authorized response can be delivered again
   for the same receipt. Verify one logical mutation and revision allocation.
3. Exercise invalid startup configuration, unavailable persistence, and
   hung cleanup. Record readiness, classifications, supervisor behavior
   and the reconciliation evidence for unresolved operations.
