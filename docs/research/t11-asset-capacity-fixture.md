# T11 local private-asset capacity fixture

[#370](https://github.com/CompleteTech-DiscordApps/guildboard/issues/370) uses
this component workload alongside the [T11 baseline](t11-sre-objectives.md)
and [SRE operations contract](../specifications/GB-T11-S1-sre-operations-contract.md).
The earlier baseline measures a generic file write and a virtual queue. This
fixture runs the built API package's T5 private asset publication function,
including its hash verification, file and directory sync and publication paths.

## Run and record

From the repository root on Linux with Node.js 24 and the lockfile dependencies
already installed, build the exact revision under test. Use a local filesystem
with a trusted temporary-directory location that supports the T5 store
operations. Set `TMPDIR` to an existing directory on that filesystem to select
it. Allow at least 24 MiB plus filesystem metadata and temporary space for the
build. Use a fresh receipt path.

```sh
git rev-parse HEAD
node --version
npm run build
node --test tests/research/t11-asset-baseline.test.mjs
node scripts/research/t11-asset-baseline.mjs > /path/to/new-receipt.json
```

Record the commit, filesystem and storage device class, host resource limits,
concurrent activity and any relevant Node worker pool settings with the JSON.
Use the receipt only if the process exits zero and the JSON parses. Failed and
interrupted runs provide a nonzero exit and emit no receipt. The fixture waits
for in-flight calls and removes its owned stores on ordinary failure, SIGINT
or SIGTERM. An uncatchable kill may leave a `gb-asset-baseline-*` directory.
Remove it only after identifying it as the failed invocation's own directory.

Each of six cells uses twelve deterministic, distinct byte sequences across
three synthetic board references in one synthetic guild. The sizes are 64 KiB,
512 KiB and 2 MiB. Each size runs at one and four simultaneous publisher calls,
with a new private store per cell. One phase creates the objects and a second
makes exact retries against that store. The fixture verifies the final bytes,
private file mode and counts outside the measured phases. There are no content
or tenant identifiers in the receipt. The total retained payload per cell
ranges from 768 KiB to 24 MiB.

## Interpret and extend the evidence

Each phase reports wall time, user and system CPU time for the Node process,
completed calls and individual call durations in completion order. Durations
start when a worker calls the publication function. Use completed calls divided
by phase wall time in seconds for phase throughput. Process CPU time divided
by wall time gives average CPU cores used by this process during the phase.
The ratio lacks a VPS CPU allocation denominator. File logical bytes and
allocated blocks are measured after publication and retry. Allocated bytes
exclude directory metadata, temporary peaks and other files, and do not
measure device traffic, fsync latency in isolation or disk fullness.

The six fixed cells bound the experiment. The sample count and work performed
cannot establish an operational scale limit, identify a system bottleneck, or
evaluate the candidate journey percentiles. Filesystem cache effects and host
contention can differ across phases and cells. Keep the receipt labeled as
private-asset component evidence. The database field explicitly records that
the fixture did not exercise a database. The [T5 schema verifier](../../database/README.md)
checks real engine schema behavior separately. It exercises neither an
authorized editor transaction nor a concurrent application workload.

For staged acceptance, use the [T11 workload assumptions](t11-sre-objectives.md)
and a Product/SRE-approved profile and sample minimum. Exercise realistic
boards and assets through the integrated editor with concurrent authorized
clients on the intended GoDaddy topology. Include the baseline duration and
approved soak, and record board-open, durable receipts, peer echo, queue
occupancy, rejects and accepted-operation integrity. Align those windows with
CPU and resident memory, SQL transaction and lock waits, and persistent volume
capacity and I/O measurements. Repeat across declared offered load levels.
Record the highest measured in-profile load meeting the approved requirements
and the first reproducibly constrained level, with the responsible resource
supported by concurrent measurements.

The accepted contract's pilot capacity rule opens investigation after two
consecutive complete five-minute in-profile breaches of an applicable latency
percentile or resource headroom, with approved sample minimums. Investigate
using the aligned resource evidence before requesting capacity changes. A
vertical resize candidate requires evidence that the constrained resource can
be increased on the GoDaddy server and that the runs can verify the result.
A topology change candidate requires evidence that vertical headroom is
insufficient or another topology constraint is responsible, followed by
separate architecture, operational and cost authorization. The fixture cannot
select or authorize either action.
