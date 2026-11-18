import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import { pathToFileURL } from "node:url";

const output = mkdtempSync(path.join(process.env.ENGINEERING_TEST_TMP || os.tmpdir(), "gb-logs-"));
after(() => rmSync(output, { recursive: true, force: true }));
writeFileSync(path.join(output, "package.json"), '{"type":"module"}');
const build = spawnSync(
  process.execPath,
  ["node_modules/typescript/lib/tsc.js", "-p", "apps/api/tsconfig.json", "--outDir", output],
  { encoding: "utf8" },
);
assert.equal(build.status, 0, build.stderr + build.stdout);
const moduleUrl = pathToFileURL(path.join(output, "operational-logs.js"));
const { createOperationalLogBoundary } = await import(moduleUrl);

const sample = Object.freeze({
  schema_version: 1,
  utc: "2026-11-17T12:00:00Z",
  component: "api",
  event: "journey",
  outcome: "success",
});
const invalid = { status: "invalid_record" };
const unknown = { status: "coverage_unknown" };
const scope = (startedAt = 10) => ({ journey: {}, board: {}, session: {}, startedAt });

function fixture(maxCorrelations = 2) {
  let now = 10;
  return {
    setTime: (value) => {
      now = value;
    },
    logs: createOperationalLogBoundary({
      maxCorrelations,
      correlationTtlMs: 10,
      monotonicNow: () => now,
    }),
  };
}

test("builds closed, immutable v1 records and classifies errors without raw exception data", () => {
  const { logs } = fixture();
  assert.deepEqual(logs.createRecord(sample), { status: "record", record: sample });
  const error = { ...sample, event: "durability", outcome: "commit_unknown" };
  const classified = logs.createClassifiedError(error);
  assert.deepEqual(classified, { status: "record", record: error });
  assert.ok(Object.isFrozen(classified.record));
  assert.notEqual(classified.record, error);
  assert.deepEqual(logs.createClassifiedError(sample), invalid);
  assert.deepEqual(
    logs.createClassifiedError(new Error("synthetic raw stack and message")),
    invalid,
  );
});

test("checks exact UTC syntax and real calendar instants", () => {
  const { logs } = fixture();
  for (const utc of ["2024-02-29T00:00:00Z", "2024-02-29T00:00:00.123Z"]) {
    assert.equal(logs.createRecord({ ...sample, utc }).status, "record", utc);
  }
  for (const utc of [
    "2026-02-29T00:00:00Z",
    "2026-02-30T12:00:00Z",
    "2026-11-17T24:00:00Z",
    "2026-11-17T12:00:60Z",
    "2026-11-17T12:00:00+00:00",
    "2026-11-17T12:00:00.1Z",
    "2026-11-17T12:00:00z",
    "2026-11-17T12:00:00Z\n",
    0,
    new Date(0),
  ]) {
    assert.deepEqual(logs.createRecord({ ...sample, utc }), invalid);
  }
});

test("rejects raw fields, valid-shaped client correlations and unsafe enum values", () => {
  const { logs } = fixture();
  const member = scope();
  assert.equal(logs.issueCorrelation(member), "available");
  const { correlation } = logs.createRecord(sample, member).record;
  for (const extra of [
    { correlation },
    { correlation: "0123456789abcdef0123456789abcdef" },
    { operation_id: "synthetic-op" },
    { board_id: "synthetic-board" },
    { authorization: "synthetic-token" },
    { exception: new Error("synthetic exception") },
    { metadata: { query: "synthetic-user-content" } },
    { [Symbol("synthetic-field")]: "synthetic value" },
  ]) {
    assert.deepEqual(logs.createRecord({ ...sample, ...extra }, member), invalid);
  }
  for (const extra of [
    { schema_version: "1" },
    { component: "synthetic-board-17" },
    { outcome: "Error: synthetic secret" },
    { event: "synthetic-token" },
  ]) {
    assert.deepEqual(logs.createRecord({ ...sample, ...extra }), invalid);
  }
  const { component: omitted, ...missing } = sample;
  assert.equal(omitted, "api");
  assert.deepEqual(logs.createRecord(missing), invalid);
});

test("rejects accessors, hidden fields, prototypes and proxies without executing user code", () => {
  const { logs } = fixture();
  const member = scope();
  let reads = 0;
  const observe = () => {
    reads++;
    throw new Error("unexpected execution");
  };
  const accessor = Object.defineProperty({ ...sample }, "outcome", { get: observe });
  const hidden = Object.defineProperty({ ...sample }, "component", { enumerable: false });
  const proxy = new Proxy(sample, { ownKeys: observe, getPrototypeOf: observe, get: observe });
  const revoked = Proxy.revocable(sample, {});
  revoked.revoke();
  for (const record of [accessor, hidden, Object.create(sample), proxy, revoked.proxy]) {
    assert.deepEqual(logs.createRecord(record), invalid);
  }
  const scopeAccessor = Object.defineProperty({ ...member }, "board", { get: observe });
  assert.equal(logs.issueCorrelation(scopeAccessor), "coverage_unknown");
  assert.deepEqual(logs.createRecord(sample, new Proxy(member, { ownKeys: observe })), unknown);
  assert.equal(reads, 0);
  assert.equal(logs.issueCorrelation(member), "available");
});

test("reuses only the given server journey in its exact board, session and start-time scope", () => {
  const { logs } = fixture();
  const member = scope();
  assert.deepEqual(logs.createRecord(sample, member), unknown);
  assert.equal(logs.issueCorrelation(member), "available");
  const first = logs.createRecord(sample, member).record;
  assert.match(first.correlation, /^[0-9a-f]{32}$/);
  assert.deepEqual(Object.keys(first), [...Object.keys(sample), "correlation"]);
  assert.deepEqual(logs.createRecord(sample, { ...member }), { status: "record", record: first });
  for (const wrongScope of [
    { ...member, board: {} },
    { ...member, session: {} },
    { ...member, startedAt: 9 },
    { ...member, board: "synthetic-board" },
  ]) {
    assert.equal(logs.issueCorrelation(wrongScope), "coverage_unknown");
    assert.deepEqual(logs.createRecord(sample, wrongScope), unknown);
  }
  const newJourney = { ...member, journey: {} };
  assert.equal(logs.issueCorrelation(newJourney), "available");
  assert.notEqual(logs.createRecord(sample, newJourney).record.correlation, first.correlation);
  const { logs: separateBoundary } = fixture();
  assert.deepEqual(separateBoundary.createRecord(sample, member), unknown);
});

test("bounds the mapping and preserves the original clock window on retries", () => {
  const { logs, setTime } = fixture(1);
  const first = scope();
  const second = scope(20);
  assert.equal(logs.issueCorrelation(first), "available");
  const token = logs.createRecord(sample, first).record.correlation;
  setTime(19);
  assert.equal(logs.issueCorrelation(first), "available");
  assert.equal(logs.issueCorrelation(scope(19)), "coverage_unknown");
  assert.equal(logs.createRecord(sample, first).record.correlation, token);
  setTime(20);
  assert.deepEqual(logs.createRecord(sample, first), unknown);
  assert.equal(logs.issueCorrelation(first), "coverage_unknown");
  assert.equal(logs.issueCorrelation(second), "available");
  assert.deepEqual(logs.createRecord(sample, first), unknown);
  setTime(19);
  assert.deepEqual(logs.createRecord(sample, second), unknown);
  setTime(Infinity);
  assert.deepEqual(logs.createRecord(sample, second), unknown);
  setTime(30);
  assert.equal(logs.issueCorrelation(scope(30)), "available");
});

test("rejects invalid input before reading time and reclaims expired slots on issuance", () => {
  let clockReads = 0;
  let now = 10;
  const logs = createOperationalLogBoundary({
    maxCorrelations: 1,
    correlationTtlMs: 10,
    monotonicNow: () => {
      clockReads++;
      return now;
    },
  });
  const first = scope();
  assert.equal(logs.issueCorrelation(first), "available");
  assert.equal(clockReads, 1);
  assert.deepEqual(logs.createRecord({ ...sample, extra: "synthetic-header" }, first), invalid);
  assert.equal(clockReads, 1);
  now = 20;
  assert.equal(logs.issueCorrelation(scope(20)), "available");
  assert.deepEqual(logs.createRecord(sample, first), unknown);
});

test("fails closed for an unavailable clock and writes neither stdout nor stderr", () => {
  const child = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "-e",
      `
    import assert from "node:assert/strict";
    import { createOperationalLogBoundary } from ${JSON.stringify(moduleUrl.href)};
    const boundary = createOperationalLogBoundary({
      maxCorrelations: 1,
      correlationTtlMs: 10,
      monotonicNow: () => { throw new Error("synthetic private clock failure"); },
    });
    assert.equal(boundary.issueCorrelation({ journey: {}, board: {}, session: {}, startedAt: 0 }), "coverage_unknown");
    assert.deepEqual(boundary.createRecord({ exception: "synthetic private message" }), { status: "invalid_record" });
  `,
    ],
    { encoding: "utf8" },
  );
  assert.equal(child.status, 0, child.stderr);
  assert.equal(child.stdout, "");
  assert.equal(child.stderr, "");
});
