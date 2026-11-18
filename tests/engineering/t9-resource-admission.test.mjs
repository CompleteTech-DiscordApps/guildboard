import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import { pathToFileURL } from "node:url";

const output = mkdtempSync(
  path.join(process.env.ENGINEERING_TEST_TMP || os.tmpdir(), "gb-limits-"),
);
after(() => rmSync(output, { recursive: true, force: true }));
writeFileSync(path.join(output, "package.json"), '{"type":"module"}');
const build = spawnSync(
  process.execPath,
  ["node_modules/typescript/lib/tsc.js", "-p", "apps/api/tsconfig.json", "--outDir", output],
  { encoding: "utf8" },
);
assert.equal(build.status, 0, build.stderr + build.stdout);
const { evaluateResourceAdmission } = await import(pathToFileURL(path.join(output, "index.js")));

const allow = { ok: true };
const unavailable = { ok: false, code: "DEPENDENCY_UNAVAILABLE" };
const invalid = { ok: false, code: "INVALID_MESSAGE" };
const tooLarge = { ok: false, code: "PAYLOAD_TOO_LARGE" };
const rateLimited = { ok: false, code: "RATE_LIMITED" };

function fixture(resourceClass = "encoded-bytes") {
  const epoch = { version: 1, resourceClass, profileRef: "fixture-profile-1" };
  const scope = {
    guildRef: "guild-a",
    principalRef: "principal-a",
    boardRef: "board-a",
    socketRef: "socket-a",
  };
  return {
    profile: {
      ...epoch,
      maxPerAttempt: 10,
      limits: { global: 100, guild: 50, principal: 30, board: 30, socket: 20 },
    },
    demand: { ...epoch, scope, amount: 10 },
    accounting: {
      ...epoch,
      scope,
      used: { global: 20, guild: 10, principal: 5, board: 5, socket: 5 },
    },
  };
}

test("admits up to the configured per-attempt bound and denies beyond it", () => {
  for (const resourceClass of [
    "encoded-bytes",
    "decoded-bytes",
    "decoded-width",
    "decoded-height",
    "parse-depth",
    "fields",
    "elements",
    "compound-changes",
    "parser-work",
    "work-duration",
    "requests",
    "connections",
    "inbound-queue-bytes",
    "durable-queue-bytes",
    "presence-queue-bytes",
    "storage-bytes",
  ]) {
    const { profile, demand, accounting } = fixture(resourceClass);
    assert.deepEqual(
      evaluateResourceAdmission(profile, { ...demand, amount: 9 }, accounting),
      allow,
    );
    assert.deepEqual(evaluateResourceAdmission(profile, demand, accounting), allow);
    assert.deepEqual(
      evaluateResourceAdmission(profile, { ...demand, amount: 11 }, accounting),
      [
        "encoded-bytes",
        "decoded-bytes",
        "decoded-width",
        "decoded-height",
        "parse-depth",
        "fields",
        "elements",
        "compound-changes",
      ].includes(resourceClass)
        ? tooLarge
        : rateLimited,
    );
  }
});

test("enforces each active scope at and above its ceiling", async (t) => {
  for (const key of ["global", "guild", "principal", "board", "socket"]) {
    await t.test(key, () => {
      const { profile, demand, accounting } = fixture("storage-bytes");
      const at = {
        ...accounting,
        used: { ...accounting.used, [key]: profile.limits[key] - demand.amount },
      };
      const above = { ...at, used: { ...at.used, [key]: at.used[key] + 1 } };
      assert.deepEqual(evaluateResourceAdmission(profile, demand, at), allow);
      assert.deepEqual(evaluateResourceAdmission(profile, demand, above), rateLimited);
    });
  }
});

test("distinguishes optional scopes from missing or inconsistent evidence", () => {
  const { profile, demand, accounting } = fixture("requests");
  const scope = { ...demand.scope, boardRef: null, socketRef: null };
  const unscoped = { ...demand, scope };
  const source = { ...accounting, scope, used: { ...accounting.used, board: null, socket: null } };
  assert.deepEqual(evaluateResourceAdmission(profile, unscoped, source), unavailable);

  const policy = { ...profile, limits: { ...profile.limits, board: null, socket: null } };
  assert.deepEqual(evaluateResourceAdmission(policy, unscoped, source), allow);
  assert.deepEqual(
    evaluateResourceAdmission(policy, unscoped, { ...source, used: { ...source.used, board: 0 } }),
    unavailable,
  );
});

test("requires evidence for the exact scope, profile revision and resource class", () => {
  const { profile, demand, accounting } = fixture("durable-queue-bytes");
  for (const key of ["guildRef", "boardRef", "principalRef", "socketRef"]) {
    const otherScope = { ...accounting.scope, [key]: "other" };
    assert.deepEqual(
      evaluateResourceAdmission(profile, demand, { ...accounting, scope: otherScope }),
      unavailable,
    );
  }
  for (const evidence of [
    undefined,
    { ...accounting, version: 2 },
    { ...accounting, profileRef: "retired" },
    { ...accounting, resourceClass: "presence-queue-bytes" },
    { ...accounting, used: { ...accounting.used, global: undefined } },
  ]) {
    assert.deepEqual(evaluateResourceAdmission(profile, demand, evidence), unavailable);
  }
  for (const evidence of [
    undefined,
    { ...profile, version: 2 },
    { ...profile, profileRef: "retired" },
    { ...profile, maxPerAttempt: Infinity },
    { ...profile, limits: { ...profile.limits, guild: -1 } },
  ]) {
    assert.deepEqual(evaluateResourceAdmission(evidence, demand, accounting), unavailable);
  }
});

test("separates tenant quota and presence pressure from durable queue accounting", () => {
  const { profile, demand, accounting } = fixture("durable-queue-bytes");
  const full = { ...accounting, used: { ...accounting.used, guild: profile.limits.guild } };
  assert.deepEqual(evaluateResourceAdmission(profile, demand, full), rateLimited);

  const neighbor = { ...demand.scope, guildRef: "guild-b" };
  const neighborDemand = { ...demand, scope: neighbor };
  assert.deepEqual(evaluateResourceAdmission(profile, neighborDemand, full), unavailable);
  const neighborAccounting = { ...accounting, scope: neighbor };
  assert.deepEqual(evaluateResourceAdmission(profile, neighborDemand, neighborAccounting), allow);

  const presence = fixture("presence-queue-bytes");
  const fullPresence = {
    ...presence.accounting,
    used: { ...presence.accounting.used, socket: presence.profile.limits.socket },
  };
  assert.deepEqual(
    evaluateResourceAdmission(presence.profile, presence.demand, fullPresence),
    rateLimited,
  );
  assert.deepEqual(evaluateResourceAdmission(profile, demand, fullPresence), unavailable);
  assert.deepEqual(evaluateResourceAdmission(profile, demand, accounting), allow);
});

test("uses integer-safe arithmetic for the maximum supported representable ceiling", () => {
  const { profile, demand, accounting } = fixture("storage-bytes");
  const max = Number.MAX_SAFE_INTEGER;
  const policy = {
    ...profile,
    maxPerAttempt: max,
    limits: { global: max, guild: max, principal: max, board: max, socket: max },
  };
  const used = { global: max - 1, guild: 0, principal: 0, board: 0, socket: 0 };
  assert.deepEqual(
    evaluateResourceAdmission(policy, { ...demand, amount: 1 }, { ...accounting, used }),
    allow,
  );
  assert.deepEqual(
    evaluateResourceAdmission(policy, { ...demand, amount: 2 }, { ...accounting, used }),
    rateLimited,
  );
  assert.deepEqual(
    evaluateResourceAdmission(profile, { ...demand, amount: max + 1 }, accounting),
    invalid,
  );
});

test("rejects malformed demand and never invokes getters or proxy traps", () => {
  const { profile, demand, accounting } = fixture();
  for (const bad of [
    null,
    { ...demand, version: 2 },
    { ...demand, resourceClass: "unknown" },
    { ...demand, scope: { ...demand.scope, guildRef: "x".repeat(129) } },
    { ...demand, amount: -1 },
    { ...demand, amount: 0.5 },
    { ...demand, amount: NaN },
    Object.create(demand),
    {
      ...demand,
      get amount() {
        assert.fail("demand getter ran");
      },
    },
    new Proxy(demand, {
      getPrototypeOf() {
        assert.fail("demand proxy trap ran");
      },
    }),
  ]) {
    assert.deepEqual(evaluateResourceAdmission(profile, bad, accounting), invalid);
  }
  const badUsed = {
    ...accounting.used,
    get global() {
      assert.fail("counter getter ran");
    },
  };
  assert.deepEqual(
    evaluateResourceAdmission(profile, demand, { ...accounting, used: badUsed }),
    unavailable,
  );
});

test("repeated, abandoned and denied decisions leave caller evidence untouched", () => {
  const { profile, demand, accounting } = fixture("inbound-queue-bytes");
  Object.freeze(profile.limits);
  Object.freeze(profile);
  Object.freeze(demand.scope);
  Object.freeze(demand);
  Object.freeze(accounting.used);
  Object.freeze(accounting);
  assert.deepEqual(evaluateResourceAdmission(profile, demand, accounting), allow);
  assert.deepEqual(
    evaluateResourceAdmission(profile, { ...demand, amount: 11 }, accounting),
    rateLimited,
  );
  assert.deepEqual(evaluateResourceAdmission(profile, demand, accounting), allow);
});
