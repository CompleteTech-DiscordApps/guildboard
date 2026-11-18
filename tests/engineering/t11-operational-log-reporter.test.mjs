import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import { setImmediate as turn, setTimeout as wait } from "node:timers/promises";
import { pathToFileURL } from "node:url";

const output = mkdtempSync(
  path.join(process.env.ENGINEERING_TEST_TMP || os.tmpdir(), "gb-reporter-"),
);
after(() => rmSync(output, { recursive: true, force: true }));
writeFileSync(path.join(output, "package.json"), '{"type":"module"}');
const build = spawnSync(
  process.execPath,
  ["node_modules/typescript/lib/tsc.js", "-p", "apps/api/tsconfig.json", "--outDir", output],
  { encoding: "utf8" },
);
assert.equal(build.status, 0, build.stderr + build.stdout);
const moduleUrl = pathToFileURL(path.join(output, "operational-log-reporter.js"));
const { createOperationalLogReporter } = await import(moduleUrl);
const { createOperationalLogBoundary } = await import(
  pathToFileURL(path.join(output, "operational-logs.js"))
);
const { createGracefulShutdownCoordinator } = await import(
  pathToFileURL(path.join(output, "graceful-shutdown.js"))
);
const sample = Object.freeze({
  schema_version: 1,
  utc: "2026-11-17T12:00:00Z",
  component: "api",
  event: "journey",
  outcome: "success",
});
const boundary = { maxCorrelations: 2, correlationTtlMs: 60_000, monotonicNow: () => 10 };
const scope = () => ({ journey: {}, board: {}, session: {}, startedAt: 10 });
const fixture = (sink = () => {}, options = {}) =>
  createOperationalLogReporter({ boundary, capacity: 3, counterLimit: 100, sink, ...options });
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

test("validates finite mechanics and flush budgets before creating work", async () => {
  let effects = 0;
  const sink = () => {
    effects++;
  };
  for (const capacity of [0, -1, 1.5, NaN, Infinity, 4097, "2"]) {
    assert.throws(() => fixture(sink, { capacity }), /Invalid operational reporter configuration/);
  }
  for (const counterLimit of [0, -1, 1.5, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(
      () => fixture(sink, { counterLimit }),
      /Invalid operational reporter configuration/,
    );
  }
  assert.throws(() => fixture(null), /Invalid operational reporter configuration/);
  const logs = fixture(sink);
  for (const budget of [0, -1, 1.5, NaN, Infinity, 2_147_483_648]) {
    assert.throws(() => logs.close(budget), /Invalid operational reporter flush configuration/);
  }
  assert.throws(() => logs.flush(10, {}), /Invalid operational reporter flush configuration/);
  assert.equal(logs.snapshot().accepting, true);
  await turn();
  assert.equal(effects, 0);
});

test("bounds total occupancy including the active delivery, and serializes in order", async () => {
  const gates = [deferred(), deferred(), deferred()];
  const seen = [];
  let live = 0,
    peak = 0;
  const logs = fixture(async (record) => {
    live++;
    peak = Math.max(peak, live);
    seen.push(record);
    await gates[seen.length - 1].promise;
    live--;
  });
  for (const event of ["journey", "dependency", "lifecycle"])
    assert.equal(logs.report({ ...sample, event }), "queued");
  assert.equal(logs.snapshot().pending, 3);
  assert.equal(logs.snapshot().inFlight, 0);
  assert.equal(logs.report(sample), "saturated");
  await turn();
  assert.equal(logs.snapshot().pending, 3);
  assert.equal(logs.snapshot().inFlight, 1);
  assert.equal(logs.report(sample), "saturated");
  const flushing = logs.flush(1000);
  for (let i = 0; i < gates.length; i++) {
    assert.equal(seen.length, i + 1);
    gates[i].resolve();
    await turn();
  }
  const result = await flushing;
  assert.equal(result.outcome, "drained");
  assert.equal(peak, 1);
  assert.deepEqual(
    seen.map(({ event }) => event),
    ["journey", "dependency", "lifecycle"],
  );
  assert.deepEqual(result.observation.counts, { rejected: 0, saturated: 2, lost: 2, delivered: 3 });
  assert.equal(result.observation.coverage, "unknown");
  assert.equal(result.observation.pending, 0);
});

test("owns original correlation provenance, snapshots records and exports no private scope", async () => {
  const seen = [];
  let now = 10;
  const logs = fixture(
    (record) => {
      seen.push(record);
    },
    { boundary: { ...boundary, monotonicNow: () => now } },
  );
  const first = scope();
  assert.equal(logs.issueCorrelation(first), "available");
  const input = { ...sample };
  assert.equal(logs.report(input, first), "queued");
  input.outcome = "synthetic-private-payload";
  assert.equal(logs.reportError({ ...sample, outcome: "commit_unknown" }, { ...first }), "queued");
  assert.equal(logs.issueCorrelation({ ...first, board: {} }), "coverage_unknown");
  assert.equal(logs.report(sample, { ...first, session: {} }), "coverage_unknown");
  await logs.flush(1000);
  assert.equal(seen.length, 2);
  assert.equal(seen[0].outcome, "success");
  assert.equal(seen[1].outcome, "commit_unknown");
  assert.match(seen[0].correlation, /^[0-9a-f]{32}$/);
  assert.equal(seen[0].correlation, seen[1].correlation);
  assert.ok(Object.isFrozen(seen[0]));
  assert.deepEqual(Object.keys(seen[0]), [...Object.keys(sample), "correlation"]);
  assert.throws(() => {
    seen[0].outcome = "integrity_failed";
  }, TypeError);
  const foreign = createOperationalLogBoundary(boundary);
  foreign.issueCorrelation(first);
  assert.equal(logs.report(foreign.createRecord(sample, first).record), "invalid_record");
  assert.equal(logs.report({ ...sample, correlation: seen[0].correlation }), "invalid_record");
  now = 60_010;
  assert.equal(logs.report(sample, first), "coverage_unknown");
  assert.equal(logs.issueCorrelation({ ...first, startedAt: now }), "coverage_unknown");
  assert.equal(seen.length, 2);
  assert.equal(logs.snapshot().coverage, "unknown");
});

test("invalid, accessor and proxy payloads cause no sink, clock or trap effects", async () => {
  let effects = 0;
  const touch = () => {
    effects++;
    throw new Error("synthetic private trap");
  };
  const logs = fixture(touch, { boundary: { ...boundary, monotonicNow: touch } });
  const proxy = new Proxy(
    {},
    { get: touch, getPrototypeOf: touch, ownKeys: touch, getOwnPropertyDescriptor: touch },
  );
  const accessor = { ...sample };
  Object.defineProperty(accessor, "outcome", { get: touch, enumerable: true });
  const invalid = [
    null,
    proxy,
    accessor,
    new Error("synthetic private exception"),
    { ...sample, component: "private" },
    { ...sample, body: "private" },
  ];
  for (const input of invalid) assert.equal(logs.report(input, proxy), "invalid_record");
  assert.equal(logs.reportError(sample), "invalid_record");
  assert.equal(logs.report(sample, proxy), "coverage_unknown");
  assert.equal(logs.issueCorrelation(proxy), "coverage_unknown");
  await turn();
  assert.equal(effects, 0);
  assert.equal(logs.snapshot().pending, 0);
  assert.equal(logs.snapshot().classes.length, 0);
});

test("bounds counter values and classification cardinality with immutable snapshots", async () => {
  const logs = fixture(undefined, { capacity: 128, counterLimit: 2 });
  const components = [
    "activity",
    "api",
    "bot",
    "collaboration",
    "persistence",
    "edge",
    "host",
    "recovery",
    "probe",
  ];
  const outcomes = [
    "success",
    "invalid_input",
    "authorization_denied",
    "dependency_unavailable",
    "saturated",
    "deadline_elapsed",
    "commit_unknown",
    "coverage_unknown",
    "interrupted",
    "integrity_failed",
  ];
  for (const component of components)
    for (const outcome of outcomes) logs.report({ ...sample, component, outcome });
  for (let i = 0; i < 200; i++) logs.report({ ...sample, component: `synthetic-${i}` });
  const { observation } = await logs.flush(1000);
  assert.equal(observation.classes.length, 90);
  assert.deepEqual(observation.counts, { rejected: 2, saturated: 0, lost: 2, delivered: 2 });
  assert.equal(observation.countsCapped, true);
  assert.equal(observation.coverage, "unknown");
  assert.ok(Object.isFrozen(observation));
  assert.ok(Object.isFrozen(observation.counts));
  assert.ok(Object.isFrozen(observation.classes));
  for (const row of observation.classes) {
    assert.ok(Object.isFrozen(row));
    assert.equal(row.delivered, 1);
  }
  const overflow = fixture(undefined, { capacity: 1, counterLimit: 2 });
  overflow.report(sample);
  for (let i = 0; i < 10; i++) assert.equal(overflow.report(sample), "saturated");
  const capped = (await overflow.close(1000)).observation;
  assert.equal(capped.counts.saturated, 2);
  assert.equal(capped.counts.lost, 2);
  assert.equal(capped.classes[0].saturated, 2);
  assert.equal(capped.classes[0].lost, 2);
  assert.equal(capped.countsCapped, true);
});

test("sync throws, rejection and rejecting thenables lose observations without raw errors", async () => {
  let calls = 0;
  const logs = fixture(() => {
    calls++;
    if (calls === 1) throw new Error("synthetic private throw");
    if (calls === 2) return Promise.reject(new Error("synthetic private rejection"));
    return {
      get then() {
        throw new Error("synthetic private thenable");
      },
    };
  });
  for (let i = 0; i < 3; i++) logs.report(sample);
  const result = await logs.flush(1000);
  assert.equal(result.outcome, "drained");
  assert.equal(calls, 3);
  assert.deepEqual(result.observation.counts, { rejected: 0, saturated: 0, lost: 3, delivered: 0 });
  assert.equal(result.observation.coverage, "unknown");
  assert.ok(!JSON.stringify(result).includes("private"));
});

test("deadline bounds a noncooperative sink and never starts overlapping replacements", async () => {
  const gate = deferred();
  let calls = 0,
    signal;
  const logs = fixture((_record, abort) => {
    calls++;
    signal = abort;
    return gate.promise;
  });
  logs.report(sample);
  logs.report(sample);
  await turn();
  const first = logs.flush(10);
  assert.equal(logs.flush(1000), first);
  const result = await first;
  assert.equal(result.outcome, "deadline_elapsed");
  assert.equal(signal.aborted, true);
  assert.equal(result.observation.accepting, false);
  assert.equal(result.observation.inFlight, 1);
  assert.equal(result.observation.pending, 1);
  assert.deepEqual(result.observation.counts, { rejected: 0, saturated: 0, lost: 2, delivered: 0 });
  assert.equal(logs.close(1000), first);
  assert.equal(logs.report(sample), "closed");
  assert.equal(logs.issueCorrelation(scope()), "coverage_unknown");
  gate.resolve();
  await turn();
  assert.equal(calls, 1);
  assert.equal(logs.snapshot().pending, 0);
  assert.equal(logs.snapshot().counts.delivered, 0);
  assert.equal(logs.snapshot().coverage, "unknown");
});

test("cancellation before delivery and during a cooperative sink preserves unknown loss", async () => {
  for (const start of [false, true]) {
    const controller = new AbortController();
    let calls = 0;
    const logs = fixture((_record, signal) => {
      calls++;
      return new Promise((resolve) => signal.addEventListener("abort", resolve, { once: true }));
    });
    logs.report(sample);
    logs.report(sample);
    if (start) await turn();
    else controller.abort("synthetic private reason");
    const completion = logs.close(1000, controller.signal);
    controller.abort("synthetic private reason");
    const result = await completion;
    assert.equal(result.outcome, "interrupted");
    assert.equal(result.observation.counts.lost, 2);
    assert.ok(!JSON.stringify(result).includes("private"));
    await turn();
    assert.equal(calls, start ? 1 : 0);
    assert.equal(logs.snapshot().counts.delivered, 0);
    assert.equal(logs.close(1000), completion);
  }
});

test("successful flush remains usable; close seals synchronously and shares completion", async () => {
  const seen = [];
  const logs = fixture((record) => {
    seen.push(record);
  });
  logs.report(sample);
  assert.equal((await logs.flush(1000)).outcome, "drained");
  assert.equal(logs.reportError({ ...sample, outcome: "authorization_denied" }), "queued");
  const closing = logs.close(1000);
  assert.equal(logs.close(1000), closing);
  assert.equal(logs.flush(1000), closing);
  assert.equal(logs.snapshot().accepting, false);
  assert.equal(logs.report(sample), "closed");
  assert.equal((await closing).outcome, "drained");
  assert.deepEqual(
    seen.map(({ outcome }) => outcome),
    ["success", "authorization_denied"],
  );
});

test("an injected shutdown callback can cancel flush without changing admitted work", async () => {
  let sinkSignal;
  const logs = fixture((_record, signal) => {
    sinkSignal = signal;
    return new Promise(() => {});
  });
  logs.report(sample);
  await turn();
  let flushResult;
  const coordinator = createGracefulShutdownCoordinator({
    drainMs: 20,
    reconnectMs: 20,
    flushMs: 10,
    closeSocketsWithReconnectGuidance: () => {},
    flushTelemetry: async (signal) => {
      flushResult = await logs.close(1000, signal);
    },
  });
  const admitted = coordinator.admit(async () => "synthetic original operation outcome");
  assert.equal(await admitted.completion, "synthetic original operation outcome");
  const result = await coordinator.shutdown();
  await turn();
  assert.equal(result.drain.outcome, "settled");
  assert.equal(result.telemetry, "deadline-elapsed");
  assert.equal(flushResult.outcome, "interrupted");
  assert.equal(sinkSignal.aborted, true);
  assert.equal(logs.snapshot().coverage, "unknown");
});

test("late sink rejection is handled and import or use writes no stdout/stderr", async () => {
  const child = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "-e",
      `
    import assert from "node:assert/strict";
    import { createOperationalLogReporter } from ${JSON.stringify(moduleUrl.href)};
    const reporter = createOperationalLogReporter({
      boundary: { maxCorrelations: 1, correlationTtlMs: 10, monotonicNow: () => 0 },
      capacity: 1, counterLimit: 2,
      sink: () => { throw new Error("synthetic private sink"); },
    });
    assert.equal(reporter.reportError(new Error("synthetic private raw")), "invalid_record");
    reporter.report(${JSON.stringify(sample)});
    const result = await reporter.close(100);
    assert.equal(result.observation.counts.lost, 2);
    assert.ok(!JSON.stringify(result).includes("private"));
  `,
    ],
    { encoding: "utf8", timeout: 5000 },
  );
  assert.equal(child.status, 0, child.stderr + child.stdout);
  assert.equal(child.stdout, "");
  assert.equal(child.stderr, "");
  const gate = deferred();
  const logs = fixture(() => gate.promise);
  logs.report(sample);
  await turn();
  await logs.close(5);
  gate.reject(new Error("synthetic private late rejection"));
  await wait(5);
  assert.equal(logs.snapshot().counts.lost, 1);
  assert.equal(logs.snapshot().counts.delivered, 0);
});
