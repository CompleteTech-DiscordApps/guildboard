import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import { pathToFileURL } from "node:url";

const output = mkdtempSync(path.join(process.env.ENGINEERING_TEST_TMP || os.tmpdir(), "gb-audit-"));
after(() => rmSync(output, { recursive: true, force: true }));
writeFileSync(path.join(output, "package.json"), '{"type":"module"}');
const build = spawnSync(
  process.execPath,
  ["node_modules/typescript/lib/tsc.js", "-p", "apps/api/tsconfig.json", "--outDir", output],
  { encoding: "utf8" },
);
assert.equal(build.status, 0, build.stderr + build.stdout);
const { AUDIT_MAX_RECORDS, createAuditEvidenceService, parseAuditEventV1 } = await import(
  pathToFileURL(path.join(output, "index.js"))
);

const ref = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const scope = { kind: "board", guildRef: ref(1), boardRef: ref(2) };
const foreign = { ...scope, guildRef: ref(3) };
const now = "2026-11-17T22:45:00.000Z";
const later = "2026-11-17T22:46:00.000Z";
const root = { sequence: "0", hash: "0".repeat(64) };
const invalid = { ok: false, code: "INVALID_MESSAGE" };
const forbidden = { ok: false, code: "FORBIDDEN" };
const unavailable = { ok: false, code: "DEPENDENCY_UNAVAILABLE" };
const inconsistent = { ok: false, code: "INTEGRITY_FAILED" };
const unknownCommit = { ok: false, code: "COMMIT_UNKNOWN" };

function event(n = 1) {
  return {
    version: 1,
    eventId: ref(100 + n),
    occurredAt: now,
    actorKind: "user",
    actorRef: ref(4),
    scope: { ...scope },
    action: "grant",
    outcome: "accepted",
    reason: "completed",
    policyGeneration: String(n),
    correlationId: ref(200 + n),
  };
}

function chain(...events) {
  let previous = root.hash;
  return events.map((value, index) => {
    const sequence = String(index + 1);
    const hash = createHash("sha256")
      .update(JSON.stringify(["guildboard.audit.record.v1", sequence, previous, value]))
      .digest("hex");
    previous = hash;
    return { sequence, hash, event: value };
  });
}

function position(record = root) {
  return { sequence: record.sequence, hash: record.hash };
}

function fixture({
  anchorUpdate = {},
  historyUpdate = {},
  grantUpdate = {},
  commitResult = "committed",
  custodyResult = "committed",
  dropRelease = false,
  throwRelease = false,
  anchorDown = false,
  accessResult = "recorded",
  accessDown = false,
  clockSamples = [],
} = {}) {
  const records = chain(event(1), event(2), event(3));
  const head = position(records.at(-1));
  const anchor = {
    scope,
    observedAt: now,
    expiresAt: later,
    checkpoint: position(records[0]),
    acceptedHead: head,
    ...anchorUpdate,
  };
  const visits = [];
  const changes = [];
  const custody = [];
  const access = [];
  let clockReads = 0;
  const service = createAuditEvidenceService({
    authority: {
      async withFence(subject, auditScope, operation, use) {
        const { right } = operation;
        visits.push("fence");
        const permitted = { transition: "append", reviewer: "verify", custodian: "preserve" };
        if (permitted[subject] !== right) return undefined;
        const result = await use({
          scope,
          operation,
          actorKind: right === "append" ? "user" : "operator",
          actorRef: ref(5),
          now,
          expiresAt: later,
          policyGeneration: "4",
          ...grantUpdate,
        });
        if (throwRelease) throw new Error("synthetic release failure");
        return dropRelease ? undefined : result;
      },
    },
    clock: {
      now() {
        return clockReads < clockSamples.length ? clockSamples[clockReads++] : now;
      },
    },
    ...(accessDown
      ? {}
      : {
          access: {
            async record(auditScope, right, record) {
              assert.deepEqual(auditScope, scope);
              visits.push(right + "-access");
              if (accessResult === "throw") throw new Error("synthetic access failure");
              if (accessResult === "recorded") access.push({ right, record });
              return accessResult;
            },
          },
        }),
    anchor: {
      async readCurrent(auditScope) {
        assert.deepEqual(auditScope, scope);
        visits.push("anchor");
        return anchorDown ? undefined : anchor;
      },
    },
    history: {
      async read(auditScope, maximumRecords) {
        assert.deepEqual(auditScope, scope);
        assert.equal(maximumRecords, AUDIT_MAX_RECORDS);
        visits.push("history");
        return { acceptedSequence: head.sequence, records, ...historyUpdate };
      },
    },
    acceptance: {
      async commitChange(auditScope, expected, record, change) {
        visits.push("commit");
        assert.deepEqual(auditScope, scope);
        assert.deepEqual(expected, head);
        if (commitResult === "committed") changes.push({ record, change });
        return commitResult;
      },
      async preserve(auditScope, expected, preserved, access) {
        visits.push("custody");
        assert.deepEqual(auditScope, scope);
        assert.deepEqual(expected, head);
        if (custodyResult === "committed") custody.push({ preserved, access });
        return custodyResult;
      },
    },
  });
  return { service, visits, changes, custody, records, access };
}

function noEffects(state, visits) {
  assert.deepEqual(state.visits, visits);
  assert.deepEqual(state.changes, []);
  assert.deepEqual(state.custody, []);
}

test("closed v1 codec constructs immutable canonical metadata with names-only diagnostics", () => {
  const source = event();
  const rearranged = Object.fromEntries(Object.entries(source).reverse());
  const parsed = parseAuditEventV1(rearranged);
  assert.deepEqual(parsed, { ok: true, event: source });
  assert.equal(JSON.stringify(parsed.event), JSON.stringify(source));
  assert.ok(Object.isFrozen(parsed.event));
  assert.ok(Object.isFrozen(parsed.event.scope));

  const sentinels = ["synthetic-token-value", "synthetic-board-text", "synthetic-credential-key"];
  const malformed = [
    [{ ...source, version: "1" }, "version"],
    [{ ...source, eventId: ref(9) + "\n" }, "eventId"],
    [{ ...source, eventId: 123 }, "eventId"],
    [{ ...source, occurredAt: "2026-02-30T12:00:00.000Z" }, "occurredAt"],
    [{ ...source, occurredAt: "2026-11-17T22:45:00+00:00" }, "occurredAt"],
    [{ ...source, actorKind: "operator" }, "actorKind"],
    [{ ...source, actorRef: sentinels[0] }, "actorRef"],
    [{ ...source, action: "__proto__" }, "action"],
    [{ ...source, reason: sentinels[0] }, "reason"],
    [{ ...source, outcome: "denied", reason: "completed" }, "reason"],
    [{ ...source, scope: { ...scope, rawSelector: sentinels[1] } }, "scope"],
    [{ ...source, scope: { kind: "system" } }, "scope"],
    [{ ...source, policyGeneration: undefined }, "policyGeneration"],
    [{ ...source, policyGeneration: "01" }, "policyGeneration"],
    [{ ...source, policyGeneration: "1\n" }, "policyGeneration"],
    [{ ...source, policyGeneration: "18446744073709551616" }, "policyGeneration"],
    [{ ...source, correlationId: sentinels[1] }, "correlationId"],
    [{ ...source, [sentinels[2]]: sentinels[0] }, "record"],
    [Object.create(source), "record"],
    [
      Object.defineProperty({ ...source }, "actorRef", {
        get() {
          throw new Error(sentinels[0]);
        },
      }),
      "record",
    ],
    [Object.defineProperty({ ...source }, "hidden", { value: sentinels[0] }), "record"],
  ];
  const missingGeneration = { ...source };
  delete missingGeneration.policyGeneration;
  malformed.push([missingGeneration, "policyGeneration"]);
  for (const [record, field] of malformed) {
    assert.deepEqual(parseAuditEventV1(record), { ok: false, fields: [field] });
  }
  assert.equal(parseAuditEventV1({ ...source, policyGeneration: "18446744073709551615" }).ok, true);
  assert.equal(
    parseAuditEventV1({ ...missingGeneration, outcome: "denied", reason: "forbidden" }).ok,
    true,
  );
});

test("ordinary board writers and moderators cannot inspect, append or preserve audit history", async () => {
  const state = fixture();
  for (const subject of ["writer", "moderator"]) {
    assert.deepEqual(await state.service.verify(subject, scope), forbidden);
    assert.deepEqual(await state.service.append(subject, scope, "grant", null), forbidden);
    assert.deepEqual(await state.service.preserve(subject, scope), forbidden);
  }
  assert.deepEqual(await state.service.preserve("reviewer", scope), forbidden);
  assert.deepEqual(await state.service.verify("custodian", scope), forbidden);
  noEffects(state, Array(8).fill("fence"));
  assert.deepEqual(state.access, []);
});

test("malformed, expired and cross-guild requests never reach an audit read or effect port", async () => {
  const malformed = fixture();
  assert.deepEqual(
    await malformed.service.verify("reviewer", { ...scope, token: "synthetic" }),
    invalid,
  );
  assert.deepEqual(
    await malformed.service.append("transition", scope, "unregistered", null),
    invalid,
  );
  assert.deepEqual(
    await malformed.service.append("transition", scope, "evidence-access", null),
    invalid,
  );
  noEffects(malformed, []);

  const stale = fixture({ grantUpdate: { expiresAt: now, policyGeneration: "3" } });
  assert.deepEqual(await stale.service.append("transition", scope, "grant", null), forbidden);
  assert.deepEqual(await stale.service.verify("reviewer", scope), forbidden);
  assert.deepEqual(await stale.service.preserve("custodian", scope), forbidden);
  noEffects(stale, ["fence", "fence", "fence"]);

  const unvalidatedPolicy = fixture({ grantUpdate: { policyGeneration: "04" } });
  assert.deepEqual(
    await unvalidatedPolicy.service.append("transition", scope, "grant", null),
    invalid,
  );
  noEffects(unvalidatedPolicy, ["fence"]);

  const wrongAction = fixture({ grantUpdate: { operation: { right: "append", action: "lock" } } });
  assert.deepEqual(await wrongAction.service.append("transition", scope, "grant", null), forbidden);
  noEffects(wrongAction, ["fence"]);

  const foreignScope = fixture();
  assert.deepEqual(await foreignScope.service.verify("reviewer", foreign), forbidden);
  assert.deepEqual(
    await foreignScope.service.append("transition", foreign, "grant", null),
    forbidden,
  );
  assert.deepEqual(await foreignScope.service.preserve("custodian", foreign), forbidden);
  noEffects(foreignScope, ["fence", "fence", "fence"]);
});

test("verification blocks before primary history reads when independent anchor is unavailable or invalid", async () => {
  for (const options of [
    { anchorDown: true },
    { anchorUpdate: { expiresAt: now } },
    { anchorUpdate: { observedAt: later } },
    { anchorUpdate: { scope: foreign } },
    { anchorUpdate: { acceptedHead: { ...root, sequence: String(AUDIT_MAX_RECORDS + 1) } } },
  ]) {
    const state = fixture(options);
    assert.deepEqual(await state.service.verify("reviewer", scope), unavailable);
    assert.deepEqual(await state.service.append("transition", scope, "grant", null), unavailable);
    assert.deepEqual(await state.service.preserve("custodian", scope), unavailable);
    noEffects(state, [
      "fence",
      "verify-access",
      "anchor",
      "fence",
      "anchor",
      "fence",
      "preserve-access",
      "anchor",
    ]);
  }
});

test("unavailable operator access accounting blocks privileged reads and custody", async () => {
  for (const options of [
    { accessDown: true },
    { accessResult: "unavailable" },
    { accessResult: "unknown" },
    { accessResult: "throw" },
  ]) {
    const state = fixture(options);
    assert.deepEqual(await state.service.verify("reviewer", scope), unavailable);
    assert.deepEqual(await state.service.preserve("custodian", scope), unavailable);
    noEffects(
      state,
      options.accessDown
        ? ["fence", "fence"]
        : ["fence", "verify-access", "fence", "preserve-access"],
    );
    assert.deepEqual(state.access, []);
  }
});

test("anchor freshness covers the live fetch and completed proof", async () => {
  const between = "2026-11-17T22:45:30.000Z";
  const cases = [
    { clockSamples: [between, between], historyRead: false },
    { clockSamples: [now, later], historyRead: false },
    { clockSamples: [now, now, later], historyRead: true },
    { clockSamples: [now, now, between, later], historyRead: true },
    { clockSamples: [now, between, now], historyRead: true },
    { clockSamples: [now, now, "invalid"], historyRead: true },
  ];
  for (const { clockSamples, historyRead } of cases) {
    for (const [right, subject, accounting] of [
      ["verify", "reviewer", ["verify-access"]],
      ["append", "transition", []],
      ["preserve", "custodian", ["preserve-access"]],
    ]) {
      const state = fixture({ clockSamples });
      assert.deepEqual(await state.service[right](subject, scope, "grant", null), unavailable);
      noEffects(state, ["fence", ...accounting, "anchor", ...(historyRead ? ["history"] : [])]);
    }
  }
  const fresh = fixture({
    clockSamples: [now, between, between, between],
    anchorUpdate: { observedAt: between },
  });
  assert.deepEqual(await fresh.service.verify("reviewer", scope), { ok: true });
  noEffects(fresh, ["fence", "verify-access", "anchor", "history"]);
});

test("checks checkpointed history and accepted active tail against the independent head", async () => {
  const original = chain(event(1), event(2), event(3));
  const cases = [
    { records: original.slice(0, 0) },
    { records: original.slice(0, 2) },
    { records: chain({ ...event(1), actorRef: ref(80) }, event(2), event(3)) },
    { records: chain(event(1), event(2), { ...event(3), actorRef: ref(80) }) },
    { records: [...original, chain(event(4))[0]] },
    { records: [original[0], original[2], original[1]] },
    {
      records: [
        original[0],
        original[1],
        { ...original[2], event: { ...event(3), scope: foreign } },
      ],
    },
    { records: original, acceptedSequence: "2" },
  ];
  for (const historyUpdate of cases) {
    const state = fixture({ historyUpdate });
    assert.deepEqual(await state.service.verify("reviewer", scope), inconsistent);
    assert.deepEqual(await state.service.preserve("custodian", scope), inconsistent);
    assert.deepEqual(await state.service.append("transition", scope, "grant", null), inconsistent);
    noEffects(state, [
      "fence",
      "verify-access",
      "anchor",
      "history",
      "fence",
      "preserve-access",
      "anchor",
      "history",
      "fence",
      "anchor",
      "history",
    ]);
  }
  const state = fixture({ anchorUpdate: { acceptedHead: position(original[1]) } });
  assert.deepEqual(await state.service.verify("reviewer", scope), inconsistent);
  noEffects(state, ["fence", "verify-access", "anchor", "history"]);
  const checkpointMismatch = fixture({
    anchorUpdate: { checkpoint: { sequence: "1", hash: "f".repeat(64) } },
  });
  assert.deepEqual(await checkpointMismatch.service.verify("reviewer", scope), inconsistent);
  noEffects(checkpointMismatch, ["fence", "verify-access", "anchor", "history"]);
});

test("permitted rights verify, produce metadata only and transfer validated evidence privately", async () => {
  const state = fixture();
  assert.deepEqual(await state.service.verify("reviewer", scope), { ok: true });

  const change = { privateValue: "synthetic-board-text" };
  assert.deepEqual(await state.service.append("transition", scope, "grant", change), { ok: true });
  const appended = state.changes[0];
  assert.equal(appended.change, change);
  assert.equal(appended.record.sequence, "4");
  assert.deepEqual(appended.record.event.scope, scope);
  assert.equal(appended.record.event.actorRef, ref(5));
  assert.equal(appended.record.event.occurredAt, now);
  assert.equal(appended.record.event.policyGeneration, "4");
  assert.notEqual(appended.record.event.eventId, appended.record.event.correlationId);
  assert.equal(JSON.stringify(appended.record).includes(change.privateValue), false);

  assert.deepEqual(await state.service.preserve("custodian", scope), { ok: true });
  assert.equal(state.custody.length, 1);
  assert.deepEqual(state.custody[0].preserved, state.records);
  assert.equal(state.custody[0].access.event.action, "evidence-access");
  assert.equal(state.custody[0].access.event.actorKind, "operator");
  assert.equal(state.custody[0].access.event.policyGeneration, undefined);
  assert.deepEqual(
    state.access.map(({ right }) => right),
    ["verify", "preserve"],
  );
  for (const { record } of state.access) {
    assert.deepEqual(record.scope, scope);
    assert.equal(record.actorKind, "operator");
    assert.equal(record.actorRef, ref(5));
    assert.equal(record.action, "evidence-access");
    assert.equal(record.occurredAt, now);
    assert.notEqual(record.eventId, state.custody[0].access.event.eventId);
  }
  assert.deepEqual(state.visits, [
    "fence",
    "verify-access",
    "anchor",
    "history",
    "fence",
    "anchor",
    "history",
    "commit",
    "fence",
    "preserve-access",
    "anchor",
    "history",
    "custody",
  ]);
});

test("a rejected atomic effect, unknown completion and revoked result remain distinct", async () => {
  const rejected = fixture({ commitResult: "rejected", custodyResult: "rejected" });
  assert.deepEqual(await rejected.service.append("transition", scope, "grant", null), unavailable);
  assert.deepEqual(await rejected.service.preserve("custodian", scope), unavailable);
  noEffects(rejected, [
    "fence",
    "anchor",
    "history",
    "commit",
    "fence",
    "preserve-access",
    "anchor",
    "history",
    "custody",
  ]);
  const uncertain = fixture({ commitResult: "unknown", custodyResult: "unknown" });
  assert.deepEqual(
    await uncertain.service.append("transition", scope, "grant", null),
    unknownCommit,
  );
  assert.deepEqual(await uncertain.service.preserve("custodian", scope), unknownCommit);

  for (const release of [{ dropRelease: true }, { throwRelease: true }]) {
    const revoked = fixture(release);
    assert.deepEqual(
      await revoked.service.verify("reviewer", scope),
      release.dropRelease ? forbidden : unavailable,
    );
    assert.deepEqual(
      await revoked.service.append("transition", scope, "grant", null),
      unknownCommit,
    );
    assert.deepEqual(await revoked.service.preserve("custodian", scope), unknownCommit);
    assert.equal(revoked.changes.length, 1);
    assert.equal(revoked.custody.length, 1);

    const denied = fixture({ ...release, commitResult: "rejected", custodyResult: "rejected" });
    assert.deepEqual(
      await denied.service.append("transition", scope, "grant", null),
      release.dropRelease ? forbidden : unavailable,
    );
    assert.deepEqual(
      await denied.service.preserve("custodian", scope),
      release.dropRelease ? forbidden : unavailable,
    );
    assert.deepEqual(denied.changes, []);
    assert.deepEqual(denied.custody, []);

    const possible = fixture({ ...release, commitResult: "unknown", custodyResult: "unknown" });
    assert.deepEqual(
      await possible.service.append("transition", scope, "grant", null),
      unknownCommit,
    );
    assert.deepEqual(await possible.service.preserve("custodian", scope), unknownCommit);
  }
});
