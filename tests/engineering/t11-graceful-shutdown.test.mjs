import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { performance } from "node:perf_hooks";
import { after, test } from "node:test";
import { pathToFileURL } from "node:url";

const output = mkdtempSync(
  path.join(process.env.ENGINEERING_TEST_TMP || os.tmpdir(), "gb-shutdown-"),
);
after(() => rmSync(output, { recursive: true, force: true }));
writeFileSync(path.join(output, "package.json"), '{"type":"module"}');
const build = spawnSync(
  process.execPath,
  ["node_modules/typescript/lib/tsc.js", "-p", "apps/api/tsconfig.json", "--outDir", output],
  { encoding: "utf8" },
);
assert.equal(build.status, 0, build.stderr + build.stdout);
const { createGracefulShutdownCoordinator } = await import(
  pathToFileURL(path.join(output, "index.js"))
);

const completedDrain = { outcome: "settled", pendingOperations: 0, failedOperations: 0 };

function fixture(overrides = {}) {
  return {
    drainMs: 1000,
    reconnectMs: 1000,
    flushMs: 1000,
    closeSocketsWithReconnectGuidance: () => {},
    flushTelemetry: () => {},
    ...overrides,
  };
}

test("validates host budgets and requires both trusted callbacks before any work", () => {
  let sideEffects = 0;
  const defaults = {
    closeSocketsWithReconnectGuidance: () => sideEffects++,
    flushTelemetry: () => sideEffects++,
  };
  for (const overrides of [
    { drainMs: 0 },
    { drainMs: 1.5 },
    { reconnectMs: Infinity },
    { reconnectMs: "1000" },
    { flushMs: -1 },
    { flushMs: 2_147_483_647 },
    { closeSocketsWithReconnectGuidance: undefined },
    { flushTelemetry: null },
  ]) {
    assert.throws(() => createGracefulShutdownCoordinator(fixture({ ...defaults, ...overrides })), {
      name: "TypeError",
      message: "Invalid graceful shutdown configuration",
    });
  }
  assert.equal(sideEffects, 0);
});

test("atomically stops admission and waits for all in-flight work before closing and flushing", async () => {
  const first = Promise.withResolvers();
  const second = Promise.withResolvers();
  const reconnect = Promise.withResolvers();
  const reconnectStarted = Promise.withResolvers();
  const calls = [];
  const coordinator = createGracefulShutdownCoordinator(
    fixture({
      closeSocketsWithReconnectGuidance(signal) {
        assert.equal(signal.aborted, false);
        calls.push("reconnect");
        reconnectStarted.resolve();
        return reconnect.promise;
      },
      flushTelemetry(signal) {
        assert.equal(signal.aborted, false);
        calls.push("flush");
      },
    }),
  );

  assert.equal(coordinator.isAcceptingWork(), true);
  const firstOperation = coordinator.admit(() => first.promise);
  const secondOperation = coordinator.admit(() => second.promise);
  assert.equal(firstOperation.admitted, true);
  assert.equal(secondOperation.admitted, true);
  const shutdown = coordinator.shutdown();
  assert.equal(coordinator.isAcceptingWork(), false);
  assert.equal(coordinator.shutdown(), shutdown);
  assert.deepEqual(
    coordinator.admit(() => calls.push("late operation")),
    { admitted: false },
  );
  first.resolve({ originalResult: 1 });
  assert.deepEqual(await firstOperation.completion, { originalResult: 1 });
  assert.deepEqual(calls, []);
  second.resolve({ originalResult: 2 });
  assert.deepEqual(await secondOperation.completion, { originalResult: 2 });
  await reconnectStarted.promise;
  assert.deepEqual(calls, ["reconnect"]);
  reconnect.resolve();
  assert.deepEqual(await shutdown, {
    drain: completedDrain,
    reconnect: "completed",
    telemetry: "completed",
  });
  assert.equal(coordinator.shutdown(), shutdown);
  assert.deepEqual(calls, ["reconnect", "flush"]);
});

test("reserves in-flight work before invoking a callback that reenters shutdown", async () => {
  const coordinator = createGracefulShutdownCoordinator(fixture());
  const error = new Error("operation failure fixture");
  let shutdown;
  const admitted = coordinator.admit(() => {
    shutdown = coordinator.shutdown();
    throw error;
  });
  assert.equal(admitted.admitted, true);
  await assert.rejects(admitted.completion, (reason) => reason === error);
  assert.equal(shutdown, coordinator.shutdown());
  assert.deepEqual(await shutdown, {
    drain: { ...completedDrain, failedOperations: 1 },
    reconnect: "completed",
    telemetry: "completed",
  });
});

test("a failed admitted operation and failing hooks return classified outcomes without payloads", async () => {
  const operation = Promise.withResolvers();
  const error = new Error("private operation fixture");
  const calls = [];
  const coordinator = createGracefulShutdownCoordinator(
    fixture({
      closeSocketsWithReconnectGuidance() {
        calls.push("reconnect");
        throw new Error("private reconnect fixture");
      },
      async flushTelemetry() {
        calls.push("flush");
        throw new Error("private telemetry fixture");
      },
    }),
  );
  const admitted = coordinator.admit(() => operation.promise);
  const failed = assert.rejects(admitted.completion, (reason) => reason === error);
  const shutdown = coordinator.shutdown();
  operation.reject(error);
  await failed;
  assert.deepEqual(await shutdown, {
    drain: { ...completedDrain, failedOperations: 1 },
    reconnect: "failed",
    telemetry: "failed",
  });
  assert.deepEqual(calls, ["reconnect", "flush"]);
});

test("a drain deadline leaves the original operation alone and proceeds with cleanup", async () => {
  const operation = Promise.withResolvers();
  const coordinator = createGracefulShutdownCoordinator(fixture({ drainMs: 10 }));
  const admitted = coordinator.admit(() => operation.promise);
  const result = await coordinator.shutdown();
  assert.deepEqual(result, {
    drain: { outcome: "deadline-elapsed", pendingOperations: 1, failedOperations: 0 },
    reconnect: "completed",
    telemetry: "completed",
  });
  operation.resolve("original result");
  assert.equal(await admitted.completion, "original result");
  assert.equal((await coordinator.shutdown()).drain.pendingOperations, 1);
});

test("hung cleanup hooks have independent deadlines and receive cooperative cancellation", async () => {
  const reconnect = Promise.withResolvers();
  const telemetry = Promise.withResolvers();
  const calls = [];
  const coordinator = createGracefulShutdownCoordinator(
    fixture({
      reconnectMs: 10,
      flushMs: 10,
      closeSocketsWithReconnectGuidance(signal) {
        calls.push("reconnect");
        signal.addEventListener("abort", () => calls.push("reconnect canceled"), { once: true });
        return reconnect.promise;
      },
      flushTelemetry(signal) {
        calls.push("flush");
        signal.addEventListener("abort", () => calls.push("flush canceled"), { once: true });
        return telemetry.promise;
      },
    }),
  );

  assert.deepEqual(await coordinator.shutdown(), {
    drain: completedDrain,
    reconnect: "deadline-elapsed",
    telemetry: "deadline-elapsed",
  });
  assert.deepEqual(calls, ["reconnect", "reconnect canceled", "flush", "flush canceled"]);
  reconnect.reject(new Error("late reconnect failure"));
  telemetry.reject(new Error("late telemetry failure"));
});

test("drain settlement uses the monotonic cutoff before timer dispatch", async (t) => {
  const originalNow = performance.now;
  const originalSetTimeout = globalThis.setTimeout;
  for (const offset of [-1, 0, 1]) {
    for (const settlement of ["fulfilled", "rejected"]) {
      await t.test(`${settlement} at deadline ${offset}`, async (t) => {
        let now = 100;
        t.mock.method(performance, "now", () => now);
        // No tick: only promise settlement can finish the phase in these cases.
        t.mock.timers.enable({ apis: ["setTimeout"] });
        const operation = Promise.withResolvers();
        const value = { syntheticResult: true };
        const error = new Error("synthetic operation failure");
        const calls = [];
        const coordinator = createGracefulShutdownCoordinator(
          fixture({
            drainMs: 10,
            closeSocketsWithReconnectGuidance(signal) {
              assert.equal(signal.aborted, false);
              calls.push("reconnect");
            },
            flushTelemetry(signal) {
              assert.equal(signal.aborted, false);
              calls.push("flush");
            },
          }),
        );
        const admitted = coordinator.admit(() => operation.promise);
        assert.equal(admitted.admitted, true);
        const completion =
          settlement === "rejected"
            ? assert.rejects(admitted.completion, (reason) => reason === error)
            : admitted.completion.then((result) => assert.equal(result, value));
        const shutdown = coordinator.shutdown();
        assert.deepEqual(calls, []);
        now = 110 + offset;
        if (settlement === "rejected") operation.reject(error);
        else operation.resolve(value);
        await completion;
        const result = await shutdown;
        assert.deepEqual(result, {
          drain: {
            outcome: offset < 0 ? "settled" : "deadline-elapsed",
            pendingOperations: offset < 0 ? 0 : 1,
            failedOperations: offset < 0 && settlement === "rejected" ? 1 : 0,
          },
          reconnect: "completed",
          telemetry: "completed",
        });
        assert.deepEqual(calls, ["reconnect", "flush"]);
        assert.equal(coordinator.shutdown(), shutdown);
        assert.equal((await coordinator.shutdown()).drain, result.drain);
      });
      assert.equal(performance.now, originalNow);
      assert.equal(globalThis.setTimeout, originalSetTimeout);
    }
  }
});

test("cleanup settlement uses its own monotonic cutoff before timer dispatch", async (t) => {
  const originalNow = performance.now;
  const originalSetTimeout = globalThis.setTimeout;
  for (const phase of ["reconnect", "telemetry"]) {
    for (const offset of [-1, 0, 1]) {
      for (const settlement of ["fulfilled", "rejected", "synchronous failure"]) {
        await t.test(`${phase} ${settlement} at deadline ${offset}`, async (t) => {
          let now = 100;
          t.mock.method(performance, "now", () => now);
          t.mock.timers.enable({ apis: ["setTimeout"] });
          const cleanup = Promise.withResolvers();
          const started = Promise.withResolvers();
          const calls = [];
          const signals = {};
          const error = new Error("synthetic cleanup failure");
          const run = (name, signal) => {
            calls.push(name);
            signals[name] = signal;
            assert.equal(signal.aborted, false);
            if (name !== phase) {
              // Consume most of this phase's independent ten-millisecond budget.
              now += 9;
              return;
            }
            now += 10 + offset;
            started.resolve();
            if (settlement === "synchronous failure") throw error;
            return cleanup.promise;
          };
          const coordinator = createGracefulShutdownCoordinator(
            fixture({
              drainMs: 10,
              reconnectMs: 10,
              flushMs: 10,
              closeSocketsWithReconnectGuidance: (signal) => run("reconnect", signal),
              flushTelemetry: (signal) => run("telemetry", signal),
            }),
          );
          const shutdown = coordinator.shutdown();
          await started.promise;
          if (settlement !== "synchronous failure") {
            assert.equal(signals[phase].aborted, false);
            if (settlement === "rejected") cleanup.reject(error);
            else cleanup.resolve();
          }
          const result = await shutdown;
          const outcome =
            offset >= 0 ? "deadline-elapsed" : settlement === "fulfilled" ? "completed" : "failed";
          assert.deepEqual(result, {
            drain: completedDrain,
            reconnect: phase === "reconnect" ? outcome : "completed",
            telemetry: phase === "telemetry" ? outcome : "completed",
          });
          assert.equal(signals[phase].aborted, offset >= 0);
          assert.equal(signals[phase === "reconnect" ? "telemetry" : "reconnect"].aborted, false);
          assert.deepEqual(calls, ["reconnect", "telemetry"]);
          assert.equal(coordinator.shutdown(), shutdown);
          assert.equal(await coordinator.shutdown(), result);
          assert.deepEqual(calls, ["reconnect", "telemetry"]);
        });
        assert.equal(performance.now, originalNow);
        assert.equal(globalThis.setTimeout, originalSetTimeout);
      }
    }
  }
});
