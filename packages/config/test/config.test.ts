import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createConfigFailure } from "../src/index.js";
import type { ConfigKey } from "../src/index.js";

test("failure snapshot has only the code and sorted canonical names", () => {
  const actual = createConfigFailure([
    "SESSION_SECRET", "PORT", "DATABASE_URL", "NODE_ENV", "DISCORD_CLIENT_ID", "PORT",
  ]);
  const expected: unknown = JSON.parse(readFileSync(
    new URL("../../test/snapshots/config-invalid.json", import.meta.url), "utf8",
  ));
  assert.deepEqual(actual, expected);
});

test("partial failures are deduplicated without mutating the input", () => {
  const input = Object.freeze(["PORT", "DATABASE_URL", "PORT"] as const);
  assert.deepEqual(createConfigFailure(input), {
    ok: false, error: { code: "CONFIG_INVALID", invalidKeys: ["DATABASE_URL", "PORT"] },
  });
  assert.deepEqual(input, ["PORT", "DATABASE_URL", "PORT"]);
});

test("runtime values and unrelated names cannot appear in diagnostics", () => {
  const password = "SENTINEL_DB_PASSWORD";
  const secret = "SENTINEL_SESSION_SECRET_1234567890123456789";
  const input = ["PORT", `mysql://user:${password}@localhost/board`, secret, "UNRELATED_TOKEN"];
  // Exercise JS callers that bypass the TypeScript key restriction.
  const actual = createConfigFailure(input as ConfigKey[]);
  assert.deepEqual(actual.error.invalidKeys, ["PORT"]);
  const rendered = JSON.stringify(actual);
  for (const value of [password, secret, "UNRELATED_TOKEN", "mysql://"]) {
    assert.equal(rendered.includes(value), false);
  }
});

test("diagnostics never invoke conversion hooks on unexpected runtime values", () => {
  const hostile = {
    toString() { throw new Error("unexpected coercion"); },
    toJSON() { throw new Error("unexpected serialization"); },
  };
  const result = createConfigFailure([hostile, "SESSION_SECRET"] as unknown as ConfigKey[]);
  assert.equal(JSON.stringify(result), '{"ok":false,"error":{"code":"CONFIG_INVALID","invalidKeys":["SESSION_SECRET"]}}');
});

test("results have no shared mutable diagnostic arrays", () => {
  const first = createConfigFailure(["PORT"]);
  first.error.invalidKeys.push("SESSION_SECRET");
  assert.deepEqual(createConfigFailure(["PORT"]).error.invalidKeys, ["PORT"]);
  assert.deepEqual(createConfigFailure([]), {
    ok: false, error: { code: "CONFIG_INVALID", invalidKeys: [] },
  });
});

test("import and failure creation neither log nor terminate startup", () => {
  const moduleUrl = new URL("../src/index.js", import.meta.url).href;
  const program = `
    import assert from 'node:assert/strict';
    const {createConfigFailure} = await import(${JSON.stringify(moduleUrl)});
    const result = createConfigFailure(['PORT']);
    assert.equal(result.ok, false);
    assert.deepEqual(result.error.invalidKeys, ['PORT']);
    process.stdout.write('CALLER_CONTINUES');
  `;
  const child = spawnSync(process.execPath, ["--input-type=module", "--eval", program], {
    encoding: "utf8",
    env: {
      PORT: "bad",
      DATABASE_URL: "mysql://user:SENTINEL_DB_PASSWORD@localhost/board",
      SESSION_SECRET: "SENTINEL_SESSION_SECRET_1234567890123456789",
    },
    timeout: 5000,
  });
  assert.equal(child.error, undefined);
  assert.equal(child.status, 0);
  assert.equal(child.signal, null);
  assert.equal(child.stdout, "CALLER_CONTINUES");
  assert.equal(child.stderr, "");
});
