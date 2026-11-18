import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import { pathToFileURL } from "node:url";

const output = mkdtempSync(
  path.join(process.env.ENGINEERING_TEST_TMP || os.tmpdir(), "gb-metrics-"),
);
after(() => rmSync(output, { recursive: true, force: true }));
writeFileSync(path.join(output, "package.json"), '{"type":"module"}');
const build = spawnSync(
  process.execPath,
  ["node_modules/typescript/lib/tsc.js", "-p", "apps/api/tsconfig.json", "--outDir", output],
  { encoding: "utf8" },
);
assert.equal(build.status, 0, build.stderr + build.stdout);
const moduleUrl = pathToFileURL(path.join(output, "operational-metrics.js"));
const { OPERATIONAL_METRICS_V1: registry, parseOperationalMetricV1: parse } = await import(
  moduleUrl
);

const window = {
  version: 1,
  startUtc: "2024-02-29T12:00:00Z",
  endUtc: "2024-02-29T12:01:00.000Z",
};
const count = {
  ...window,
  signal: "board_open_outcome",
  unit: "items",
  kind: "counter",
  dimensions: { outcome: "success", cohort: "warm" },
  value: 2,
};
const layout = { operation_latency: [10, 20, 100] };
const histogram = {
  ...window,
  signal: "operation_latency",
  unit: "milliseconds",
  kind: "histogram",
  dimensions: { outcome: "dependency_unavailable" },
  buckets: [10, 20, 100],
  counts: [0, 2, 2],
  total: 3,
};

test("registry defines an exact, frozen set of signal names and finite label products", () => {
  const series = {
    board_open_outcome: 21,
    edit_outcome: 24,
    reconnect_outcome: 7,
    probe_outcome: 4,
    operation_latency: 6,
    board_open_latency: 21,
    edit_latency: 24,
    reconnect_latency: 7,
    probe_latency: 4,
    active_sockets: 1,
    active_boards: 1,
    admission_depth: 2,
    admission_capacity: 2,
    output_depth: 1,
    output_capacity: 1,
    cpu_used: 1,
    cpu_allocatable: 1,
    resident_memory: 1,
    allocatable_memory: 1,
    persistent_disk_used: 1,
    persistent_disk_usable: 1,
    database_health: 1,
    verified_recovery_point_age: 1,
    backup_job_outcome: 6,
  };
  assert.deepEqual(Object.keys(registry).sort(), Object.keys(series).sort());
  assert.ok(Object.isFrozen(registry));
  for (const [signal, definition] of Object.entries(registry)) {
    assert.equal(definition.seriesUpperBound, series[signal], signal);
    assert.ok(Object.isFrozen(definition) && Object.isFrozen(definition.dimensions));
    const labelTuples = Object.entries(definition.dimensions).reduce(
      (tuples, [label, values]) => {
        assert.ok(Object.isFrozen(values));
        assert.equal(new Set(values).size, values.length);
        return tuples.flatMap((tuple) => values.map((value) => ({ ...tuple, [label]: value })));
      },
      [{}],
    );
    assert.equal(labelTuples.length, series[signal], signal);
    for (const dimensions of labelTuples) {
      const { unit, kind } = definition;
      const measurement =
        kind === "histogram" ? { buckets: [10], counts: [0], total: 0 } : { value: 0 };
      const record = { ...window, signal, kind, unit, dimensions, ...measurement };
      assert.deepEqual(parse(record, { [signal]: [10] }), record);
    }
  }
  assert.throws(() => registry.board_open_outcome.dimensions.cohort.push("dynamic"), TypeError);
});

test("returns immutable values detached from input and accepts a safe integer maximum", () => {
  const input = { ...histogram, dimensions: { ...histogram.dimensions }, counts: [0, 2, 2] };
  const result = parse(input, layout);
  assert.deepEqual(result, histogram);
  assert.ok(Object.isFrozen(result));
  assert.ok(Object.isFrozen(result.dimensions));
  assert.ok(Object.isFrozen(result.buckets));
  assert.ok(Object.isFrozen(result.counts));
  input.dimensions.outcome = "commit_unknown";
  input.counts[0] = 1;
  assert.deepEqual(result, histogram);
  assert.equal(parse({ ...count, value: Number.MAX_SAFE_INTEGER }).value, Number.MAX_SAFE_INTEGER);
});

test("rejects unknown names, dynamic IDs and label combinations without expanding the registry", () => {
  const before = JSON.stringify(registry);
  for (const signal of [
    "ad_hoc_outcome",
    "board_open_outcome.synthetic-0017",
    "constructor",
    "__proto__",
  ]) {
    assert.equal(parse({ ...count, signal }), undefined);
  }
  for (const dimensions of [
    { outcome: "success" },
    { outcome: "success", cohort: "synthetic-0017" },
    { outcome: "success", cohort: "warm", board: "synthetic-board-17" },
    { outcome: "success", cohort: "warm", tenant: "synthetic-tenant-17" },
    { outcome: "success", cohort: "warm", correlation: "a".repeat(32) },
    { outcome: "success", cohort: "warm", profile: "https://example.invalid/private" },
    { outcome: "success", cohort: "solo" },
    { outcome: "commit_unknown", cohort: "warm" },
    { outcome: "interrupted", cohort: "warm" },
  ]) {
    assert.equal(parse({ ...count, dimensions }), undefined);
  }
  assert.equal(
    parse({ ...count, signal: "active_sockets", kind: "gauge", dimensions: { component: "host" } }),
    undefined,
  );
  for (let index = 0; index < 100; index += 1) {
    assert.equal(
      parse({ ...count, dimensions: { outcome: "success", cohort: `guild-${index}` } }),
      undefined,
    );
  }
  assert.deepEqual(parse(count), count);
  assert.equal(JSON.stringify(registry), before);
});

test("rejects invalid intervals, values, record types and mismatched units", () => {
  for (const patch of [
    { version: 2 },
    { version: "1" },
    { startUtc: "2024-02-30T12:00:00Z" },
    { startUtc: "2024-02-29T24:00:00Z" },
    { startUtc: "2024-02-29T12:00:00+00:00" },
    { startUtc: "2024-02-29T12:00:00Z\n" },
    { startUtc: "2024-02-29T12:01:00Z" },
    { endUtc: "2024-02-29T11:00:00Z" },
    { value: Number.MAX_SAFE_INTEGER + 1 },
    { value: Number.POSITIVE_INFINITY },
    { value: NaN },
    { value: 1.5 },
    { value: -1 },
    { value: "2" },
    { kind: "gauge" },
    { unit: "bytes" },
    { comment: "private content" },
    { buckets: [10] },
  ]) {
    assert.equal(parse({ ...count, ...patch }), undefined);
  }
  const { value, ...missing } = count;
  assert.equal(parse(missing), undefined);
  assert.equal(parse(null), undefined);
  assert.equal(parse([count]), undefined);
  const health = {
    ...window,
    signal: "database_health",
    kind: "gauge",
    unit: "boolean",
    dimensions: { component: "persistence" },
    value,
  };
  assert.equal(parse(health), undefined);
  assert.deepEqual(parse({ ...health, value: 1 }), { ...health, value: 1 });
});

test("cumulative finite histogram counts stay within an independently supplied total", () => {
  assert.deepEqual(parse(histogram, layout), histogram);
  assert.deepEqual(parse({ ...histogram, counts: [1, 2, 3] }, layout), {
    ...histogram,
    counts: [1, 2, 3],
  });
  for (const patch of [
    { counts: [2, 1, 3] },
    { counts: [0, 2, 4] },
    { counts: [0, -1, 2] },
    { counts: [0, 2] },
    { counts: [0, , 2] },
    { counts: [0, 2, 2, 2] },
    { total: 0 },
    { total: 1.5 },
    { total: Number.MAX_SAFE_INTEGER + 1 },
    { buckets: [10, 21, 100] },
    { buckets: [10, 20] },
    { buckets: [20, 10, 100] },
    { buckets: [10, 10, 100] },
    { value: 2 },
  ]) {
    assert.equal(parse({ ...histogram, ...patch }, layout), undefined);
  }
  for (const invalid of [
    undefined,
    {},
    { operation_latency: [] },
    { operation_latency: [10, 20, Infinity] },
    { operation_latency: [10, 10, 100] },
    { operation_latency: [10, 100, 20] },
    { operation_latency: [10, 20, 101] },
    { operation_latency: [10, 20, 100], active_sockets: [10] },
    { operation_latency: [10, 20, 100], "synthetic-0017": [10] },
  ]) {
    assert.equal(parse(histogram, invalid), undefined);
  }
  const maximum = Array.from({ length: 32 }, (_, i) => i);
  const wide = { ...histogram, buckets: maximum, counts: maximum.map(() => 0), total: 0 };
  assert.deepEqual(parse(wide, { operation_latency: maximum }), wide);
  const tooWide = [...maximum, 32];
  assert.equal(
    parse(
      { ...wide, buckets: tooWide, counts: tooWide.map(() => 0) },
      { operation_latency: tooWide },
    ),
    undefined,
  );
});

test("rejects non-data shapes before invoking accessors, proxies or value coercion", () => {
  const unexpected = () => assert.fail("validation called untrusted code");
  const accessor = Object.defineProperty({ ...count }, "value", { get: unexpected });
  const proxy = new Proxy(count, { ownKeys: unexpected, getPrototypeOf: unexpected });
  const revoked = Proxy.revocable([], {});
  revoked.revoke();
  const accessorArray = Object.defineProperty([10, 20, 100], 1, { get: unexpected });
  const coerced = { [Symbol.toPrimitive]: unexpected };
  const inherited = Object.create(count);
  for (const input of [
    accessor,
    proxy,
    inherited,
    { ...count, [Symbol("secret")]: true },
    { ...count, value: coerced },
    Object.defineProperty({ ...count }, "hidden", { value: "secret" }),
    { ...count, dimensions: Object.create(count.dimensions) },
  ]) {
    assert.equal(parse(input), undefined);
  }
  for (const counts of [accessorArray, revoked.proxy, new Proxy([], { ownKeys: unexpected })]) {
    assert.equal(parse({ ...histogram, counts }, layout), undefined);
  }
});

test("import and validation need no ambient facilities", () => {
  const result = spawnSync(
    process.execPath,
    [
      "--permission",
      `--allow-fs-read=${output}`,
      "--input-type=module",
      "-e",
      `import net from "node:net";
       import dgram from "node:dgram";
       import { syncBuiltinESMExports } from "node:module";
       const hostCall = () => { throw new Error("ambient host call"); };
       globalThis.fetch = hostCall;
       globalThis.setTimeout = hostCall;
       console.log = hostCall;
       net.Socket.prototype.connect = hostCall;
       net.Server.prototype.listen = hostCall;
       dgram.createSocket = hostCall;
       syncBuiltinESMExports();
       const { parseOperationalMetricV1 } = await import(${JSON.stringify(moduleUrl.href)});
       if (!parseOperationalMetricV1(${JSON.stringify(histogram)}, ${JSON.stringify(layout)})) {
         process.exitCode = 1;
       }
       if (parseOperationalMetricV1({ ...${JSON.stringify(count)}, signal: "dynamic" })) {
         process.exitCode = 1;
       }`,
    ],
    { encoding: "utf8" },
  );
  assert.equal(result.status, 0, result.stderr + result.stdout);
  assert.equal(result.stdout, "");
  assert.equal(result.stderr, "");
});
