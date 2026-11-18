import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import { pathToFileURL } from "node:url";

const output = mkdtempSync(
  path.join(process.env.ENGINEERING_TEST_TMP || os.tmpdir(), "gb-metric-recorder-"),
);
after(() => rmSync(output, { recursive: true, force: true }));
writeFileSync(path.join(output, "package.json"), '{"type":"module"}');
const build = spawnSync(
  process.execPath,
  ["node_modules/typescript/lib/tsc.js", "-p", "apps/api/tsconfig.json", "--outDir", output],
  { encoding: "utf8" },
);
assert.equal(build.status, 0, build.stderr + build.stdout);
const moduleUrl = pathToFileURL(path.join(output, "operational-metric-recorder.js"));
const { createOperationalMetricRecorderV1: create } = await import(moduleUrl);
const { OPERATIONAL_METRICS_V1: registry, createOperationalMetricParserV1: createParser } =
  await import(pathToFileURL(path.join(output, "operational-metrics.js")));
const start = "2024-02-29T12:00:00Z";
const end = "2024-02-29T12:01:00.000Z";
const layout = { operation_latency: [0, 10, 100] };
const journey = { outcome: "success", cohort: "warm" };
const operation = { outcome: "success" };
const collaboration = { component: "collaboration" };
const maximum = Number.MAX_SAFE_INTEGER;
const recorder = (profile = layout, limit) => create(start, end, profile, limit);

test("counters accumulate and gauges replace without changing declared units", () => {
  const r = recorder();
  assert.equal(r.increment("board_open_outcome", journey), true);
  assert.equal(r.increment("board_open_outcome", { cohort: "warm", outcome: "success" }, 4), true);
  assert.equal(r.setGauge("active_sockets", collaboration, 9), true);
  assert.equal(r.setGauge("active_sockets", collaboration, 2), true);
  assert.equal(r.setGauge("database_health", { component: "persistence" }, 1), true);
  const records = r.snapshot();
  assert.deepEqual(
    records.map(({ signal, unit, value }) => [signal, unit, value]),
    [
      ["board_open_outcome", "items", 5],
      ["active_sockets", "items", 2],
      ["database_health", "boolean", 1],
    ],
  );
  const parse = createParser(layout);
  for (const record of records) {
    assert.equal(record.startUtc, start);
    assert.equal(record.endUtc, end);
    assert.deepEqual(parse(record), record);
  }
  assert.equal(r.status().acceptedUpdates, 5);
  assert.equal(r.status().coverage, "unknown");
});

test("histograms include equality in cumulative buckets and retain above-last totals", () => {
  const r = recorder();
  for (const sample of [0, 1, 10, 11, 100, 101]) {
    assert.equal(r.observe("operation_latency", operation, sample), true);
  }
  assert.equal(r.observe("operation_latency", operation, 10, 2), true);
  const [histogram] = r.snapshot();
  assert.deepEqual(histogram.buckets, [0, 10, 100]);
  assert.deepEqual(histogram.counts, [1, 5, 7]);
  assert.equal(histogram.total, 8);
  assert.deepEqual(createParser(layout)(histogram), histogram);
  assert.equal(r.status().acceptedUpdates, 7);
});

test("histograms without an explicit profile remain disabled and observable", () => {
  for (const r of [create(start, end), recorder({})]) {
    assert.equal(r.observe("operation_latency", operation, 1), false);
    assert.equal(r.observe("operation_latency", { outcome: "dynamic" }, 1), false);
    assert.deepEqual(r.snapshot(), []);
    assert.equal(r.status().allocatedSeries, 0);
    assert.equal(r.status().rejected.disabled, 1);
    assert.equal(r.status().rejected.invalid, 1);
    assert.equal(r.status().lossDetected, true);
  }
  const r = recorder();
  assert.equal(r.observe("probe_latency", operation, 1), false);
  assert.equal(r.observe("operation_latency", operation, 1), true);
});

test("explicit series cap rejects new tuples while preserving updates to existing tuples", () => {
  const r = recorder(layout, 1);
  assert.equal(r.increment("board_open_outcome", journey), true);
  assert.equal(r.increment("board_open_outcome", { ...journey, cohort: "cold" }), false);
  assert.equal(r.setGauge("active_sockets", collaboration, 1), false);
  assert.equal(r.increment("board_open_outcome", journey), true);
  assert.equal(r.snapshot()[0].value, 2);
  assert.equal(r.status().allocatedSeries, 1);
  assert.equal(r.status().rejected.capacity, 2);
  const disabled = recorder(layout, 0);
  assert.equal(disabled.increment("board_open_outcome", journey), false);
  assert.equal(disabled.status().allocatedSeries, 0);
});

test("enumerating every registry tuple reaches the published finite global bound", () => {
  const profiles = Object.fromEntries(
    Object.entries(registry)
      .filter(([, d]) => d.kind === "histogram")
      .map(([name]) => [name, [1]]),
  );
  const r = recorder(profiles);
  let expected = 0;
  for (const [name, definition] of Object.entries(registry)) {
    const tuples = Object.entries(definition.dimensions).reduce(
      (all, [label, domain]) =>
        all.flatMap((tuple) => domain.map((v) => ({ ...tuple, [label]: v }))),
      [{}],
    );
    assert.equal(tuples.length, definition.seriesUpperBound);
    expected += tuples.length;
    for (const tuple of tuples) {
      const result =
        definition.kind === "counter"
          ? r.increment(name, tuple)
          : definition.kind === "gauge"
            ? r.setGauge(name, tuple, 0)
            : r.observe(name, tuple, 1);
      assert.equal(result, true, name);
    }
  }
  assert.equal(r.status().maxSeries, expected);
  assert.equal(r.status().allocatedSeries, expected);
  assert.equal(r.snapshot().length, expected);
  assert.equal(r.increment("board_open_outcome", { ...journey, cohort: "tenant-17" }), false);
  assert.equal(r.status().allocatedSeries, expected);
});

test("invalid labels, signals, kinds and numeric values never allocate or mutate series", () => {
  const r = recorder();
  const invalidLabels = [
    {},
    { outcome: "success" },
    { ...journey, cohort: "tenant-17" },
    { ...journey, board: "board-17" },
    { ...journey, profile: "https://example.invalid" },
    { ...journey, outcome: "commit_unknown" },
  ];
  for (const labels of invalidLabels)
    assert.equal(r.increment("board_open_outcome", labels), false);
  for (const signal of ["unknown", "constructor", "__proto__", {}, null]) {
    assert.equal(r.increment(signal, journey), false);
  }
  for (const value of [-1, 1.5, Infinity, NaN, maximum + 1, "1", {}, true]) {
    assert.equal(r.increment("board_open_outcome", journey, value), false);
    assert.equal(r.setGauge("active_sockets", collaboration, value), false);
    assert.equal(r.observe("operation_latency", operation, value), false);
  }
  assert.equal(r.increment("active_sockets", collaboration), false);
  assert.equal(r.setGauge("database_health", { component: "persistence" }, 2), false);
  assert.equal(r.observe("operation_latency", operation, 1, 0), false);
  assert.equal(r.observe("operation_latency", operation, 1, 1.5), false);
  assert.deepEqual(r.snapshot(), []);
  assert.equal(r.status().allocatedSeries, 0);
  assert.equal(r.increment("board_open_outcome", journey, 3), true);
  const before = r.snapshot();
  assert.equal(r.increment("board_open_outcome", { ...journey, cohort: "x" }), false);
  assert.equal(r.increment("board_open_outcome", journey, -1), false);
  assert.deepEqual(r.snapshot(), before);
});

test("nonplain, accessor and proxy inputs never invoke caller code", () => {
  const unexpected = () => assert.fail("invoked caller code");
  const r = recorder();
  const revoked = Proxy.revocable({}, {});
  revoked.revoke();
  for (const dimensions of [
    new Proxy(journey, { ownKeys: unexpected, getPrototypeOf: unexpected }),
    revoked.proxy,
    Object.create(journey),
    Object.defineProperty({ ...journey }, "outcome", { get: unexpected }),
    Object.defineProperty({ ...journey }, "hidden", { value: 1 }),
    { ...journey, [Symbol("private")]: "hidden" },
    [],
    new Date(0),
  ])
    assert.equal(r.increment("board_open_outcome", dimensions), false);
  assert.equal(
    r.increment("board_open_outcome", journey, { [Symbol.toPrimitive]: unexpected }),
    false,
  );
  for (const profile of [
    new Proxy(layout, { ownKeys: unexpected }),
    revoked.proxy,
    Object.create(layout),
    Object.defineProperty({}, "operation_latency", { get: unexpected }),
    { operation_latency: Object.defineProperty([1], 0, { get: unexpected }) },
    { operation_latency: new Proxy([1], { get: unexpected }) },
  ])
    assert.equal(recorder(profile), undefined);
  assert.equal(r.status().allocatedSeries, 0);
});

test("overflow leaves all counters, histogram buckets and series allocation unchanged", () => {
  const r = recorder();
  assert.equal(r.increment("board_open_outcome", journey, maximum), true);
  assert.equal(r.observe("operation_latency", operation, 1, maximum), true);
  const before = r.snapshot();
  assert.equal(r.increment("board_open_outcome", journey), false);
  // The above-last sample still overflows the total, with no bucket changes.
  assert.equal(r.observe("operation_latency", operation, 101), false);
  assert.equal(r.observe("operation_latency", operation, 0), false);
  assert.deepEqual(r.snapshot(), before);
  assert.equal(r.status().rejected.overflow, 3);
  assert.equal(r.status().allocatedSeries, 2);
  assert.equal(r.status().acceptedUpdates, 2);
});

test("snapshots and configuration are detached, frozen and fixed to one interval", () => {
  const profile = { operation_latency: [0, 10, 100] };
  const r = recorder(profile);
  profile.operation_latency[1] = 99;
  profile.probe_latency = [1];
  const labels = { ...operation };
  assert.equal(r.observe("operation_latency", labels, 5), true);
  labels.outcome = "saturated";
  const first = r.snapshot();
  const [record] = first;
  for (const value of [r, first, record, record.dimensions, record.buckets, record.counts]) {
    assert.equal(Object.isFrozen(value), true);
  }
  assert.throws(() => first.push(record), TypeError);
  assert.throws(() => (record.counts[0] = 42), TypeError);
  assert.equal(r.observe("operation_latency", operation, 0), true);
  assert.equal(r.observe("probe_latency", operation, 1), false);
  const second = r.snapshot();
  assert.deepEqual(record.counts, [0, 1, 1]);
  assert.deepEqual(second[0].counts, [1, 2, 2]);
  assert.deepEqual(record.buckets, [0, 10, 100]);
  for (const property of ["dimensions", "buckets", "counts"]) {
    assert.notEqual(first[0][property], second[0][property]);
  }
  const later = create(end, "2024-02-29T12:02:00Z", layout);
  assert.deepEqual(later.snapshot(), []);
  assert.equal(later.increment("board_open_outcome", journey), true);
  assert.equal(later.snapshot()[0].startUtc, end);
  assert.equal(first[0].startUtc, start);
});

test("invalid setup fails closed without normalizing dates or approving profiles", () => {
  for (const [from, to] of [
    [end, start],
    [start, start],
    ["2024-02-30T12:00:00Z", end],
    [start, "2024-02-29T12:01:00+00:00"],
    [{}, end],
  ]) {
    assert.equal(create(from, to, layout), undefined);
  }
  for (const profile of [
    null,
    { operation_latency: [] },
    { operation_latency: [2, 1] },
    { operation_latency: [1, 1] },
    { active_sockets: [1] },
    { private: [1] },
  ]) {
    assert.equal(recorder(profile), undefined);
  }
  for (const limit of [-1, 1.5, Infinity, "1", {}, 1000]) {
    assert.equal(recorder(layout, limit), undefined);
  }
});

test("coverage stays unknown and loss accounting saturates without becoming success", () => {
  const r = recorder();
  const before = r.status();
  assert.equal(before.lossDetected, false);
  assert.equal(before.coverage, "unknown");
  assert.equal(r.reportMissing(maximum), true);
  assert.equal(r.reportMissing(), true);
  assert.equal(r.reportMissing(0), false);
  assert.equal(r.reportMissing(Infinity), false);
  assert.equal(r.increment("board_open_outcome", journey), true);
  const status = r.status();
  assert.equal(status.reportedMissing, maximum);
  assert.equal(status.accountingSaturated, true);
  assert.equal(status.lossDetected, true);
  assert.equal(status.coverage, "unknown");
  assert.equal(status.rejected.invalid, 2);
  assert.equal(Object.isFrozen(status), true);
  assert.equal(Object.isFrozen(status.rejected), true);
  assert.equal(before.reportedMissing, 0);
  assert.deepEqual(before.rejected, { invalid: 0, disabled: 0, capacity: 0, overflow: 0 });
});

test("offline recording runs with restricted permissions and no ambient calls", () => {
  const result = spawnSync(
    process.execPath,
    [
      "--permission",
      `--allow-fs-read=${output}`,
      "--input-type=module",
      "-e",
      `
    import net from "node:net";
    import dgram from "node:dgram";
    import { syncBuiltinESMExports } from "node:module";
    const unexpected = () => { throw new Error("ambient call"); };
    globalThis.fetch = unexpected;
    globalThis.setTimeout = unexpected;
    console.log = unexpected;
    net.Socket.prototype.connect = unexpected;
    net.Server.prototype.listen = unexpected;
    dgram.createSocket = unexpected;
    syncBuiltinESMExports();
    const { createOperationalMetricRecorderV1 } = await import(${JSON.stringify(moduleUrl.href)});
    const r = createOperationalMetricRecorderV1(${JSON.stringify(start)}, ${JSON.stringify(end)}, ${JSON.stringify(layout)});
    if (!r.observe("operation_latency", { outcome: "success" }, 10) ||
        !r.increment("probe_outcome", { outcome: "coverage_unknown" }) ||
        !r.reportMissing() || r.snapshot().length !== 2 || !r.status().lossDetected) process.exitCode = 1;
  `,
    ],
    { encoding: "utf8" },
  );
  assert.equal(result.status, 0, result.stderr + result.stdout);
  assert.equal(result.stdout, "");
  assert.equal(result.stderr, "");
});
