import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createConfigFailure, parseConfig } from "../src/index.js";
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

const validEnv = Object.freeze({
  PORT: "03000",
  NODE_ENV: "development",
  DATABASE_URL: "mysql://user:SENTINEL_DB_PASSWORD@localhost/guildboard?charset=utf8mb4",
  DISCORD_CLIENT_ID: "00123456789012345678901234567890",
  SESSION_SECRET: " SENTINEL_SESSION_SECRET_1234567890123456789 ",
});

test("parseConfig returns only the contract fields, preserving strings and accepting each environment", () => {
  for (const nodeEnv of ["development", "test", "production"] as const) {
    const input = Object.freeze({ ...validEnv, NODE_ENV: nodeEnv });
    assert.deepEqual(parseConfig(input), {
      ok: true,
      value: {
        port: 3000,
        nodeEnv,
        databaseUrl: validEnv.DATABASE_URL,
        discordClientId: validEnv.DISCORD_CLIENT_ID,
        sessionSecret: validEnv.SESSION_SECRET,
      },
    });
  }
});

test("all missing or empty required values produce sorted names only", () => {
  const expected = createConfigFailure([
    "PORT", "NODE_ENV", "DATABASE_URL", "DISCORD_CLIENT_ID", "SESSION_SECRET",
  ]);
  for (const input of [{}, Object.fromEntries(Object.keys(validEnv).map(key => [key, undefined])),
    Object.fromEntries(Object.keys(validEnv).map(key => [key, ""]))]) {
    assert.deepEqual(parseConfig(input), expected);
  }
});

test("facade rejects invalid fields with no coercion, defaults or normalization", () => {
  const invalid: Readonly<Record<ConfigKey, readonly (string | undefined)[]>> = {
    PORT: [undefined, "", "0", "65536", "-1", "+1", "1.5", "1e3", " 80", "80\n", "9".repeat(10000)],
    DATABASE_URL: [undefined, "", "not a URL", "postgres://host/db", "mysql:///db", "mysql://host", "mysql://host/"],
    NODE_ENV: [undefined, "", "Development", "PRODUCTION", "development ", "test\n", "staging"],
    DISCORD_CLIENT_ID: [undefined, "", " ", "123\n", "+123", "-123", "1.0", "1e3", "0x12", "１２３", "١٢٣"],
    SESSION_SECRET: [undefined, "", "x".repeat(31), " ".repeat(32), "\t\n".repeat(32), "\u00a0".repeat(32)],
  };
  for (const key of Object.keys(invalid) as ConfigKey[]) {
    for (const [index, value] of invalid[key].entries()) {
      assert.deepEqual(parseConfig({ ...validEnv, [key]: value }), createConfigFailure([key]), `${key} case ${index}`);
    }
  }
});

test("facade accepts exact port and secret boundaries without modifying valid values", () => {
  for (const [port, expected] of [["1", 1], ["65535", 65535], ["00042", 42]] as const) {
    const result = parseConfig({ ...validEnv, PORT: port, SESSION_SECRET: "x".repeat(32) });
    assert.equal(result.ok, true);
    if (result.ok) {
      assert.equal(result.value.port, expected);
      assert.equal(result.value.sessionSecret, "x".repeat(32));
    }
  }
  const secret = " ".repeat(31) + "x";
  const result = parseConfig({ ...validEnv, SESSION_SECRET: secret, DISCORD_CLIENT_ID: "0" });
  assert.equal(result.ok, true);
  if (result.ok) {
    assert.equal(result.value.sessionSecret, secret);
    assert.equal(result.value.discordClientId, "0");
  }
});

test("simultaneous failures are aggregated without credential-bearing values or exceptions", () => {
  const input = Object.freeze({
    ...validEnv, PORT: "65536", NODE_ENV: "invalid", SESSION_SECRET: "SHORT_SENTINEL_SECRET",
    DATABASE_URL: "mysql://user:SENTINEL_DB_PASSWORD@[invalid/board",
  });
  const result = parseConfig(input);
  assert.deepEqual(result, createConfigFailure(["PORT", "NODE_ENV", "SESSION_SECRET", "DATABASE_URL"]));
  assert.equal(JSON.stringify(result).includes("SENTINEL"), false);
  assert.equal(JSON.stringify(result).includes("mysql:"), false);
});

test("parser does not mutate input, enumerate unrelated keys or retain the input map", () => {
  const input = { ...validEnv };
  Object.defineProperty(input, "UNRELATED_TOKEN", {
    enumerable: true, get() { throw new Error("unrelated value read"); },
  });
  Object.freeze(input);
  const result = parseConfig(input);
  assert.equal(result.ok, true);
  for (const key of Object.keys(validEnv) as ConfigKey[]) assert.equal(input[key], validEnv[key]);
  if (result.ok) {
    assert.deepEqual(Object.keys(result.value).sort(), ["databaseUrl", "discordClientId", "nodeEnv", "port", "sessionSecret"]);
    assert.notEqual(result.value, input);
  }
});

test("unexpected JavaScript field types fail without invoking conversion hooks", () => {
  const hostile = { toString() { throw new Error("coercion"); } };
  for (const key of Object.keys(validEnv)) {
    for (const value of [null, 123, true, hostile]) {
      const input = { ...validEnv, [key]: value } as unknown as Record<string, string | undefined>;
      assert.deepEqual(parseConfig(input), createConfigFailure([key as ConfigKey]));
    }
  }
});

test("full parser is independent of global environment, silent and does not exit on failure", () => {
  const moduleUrl = new URL("../src/index.js", import.meta.url).href;
  const program = `
    import assert from 'node:assert/strict';
    const {parseConfig} = await import(${JSON.stringify(moduleUrl)});
    const input = ${JSON.stringify(validEnv)};
    const originalEnv = process.env;
    process.env = new Proxy({}, { get() { throw new Error('global environment read'); } });
    try {
      assert.equal(parseConfig(input).ok, true);
      assert.deepEqual(parseConfig({...input, PORT: 'bad'}), {
        ok: false, error: { code: 'CONFIG_INVALID', invalidKeys: ['PORT'] }
      });
      assert.equal(parseConfig({}).ok, false);
    } finally { process.env = originalEnv; }
    process.stdout.write('CALLER_CONTINUES');
  `;
  const child = spawnSync(process.execPath, ["--input-type=module", "--eval", program], {
    encoding: "utf8", env: {}, timeout: 5000,
  });
  assert.equal(child.error, undefined);
  assert.equal(child.status, 0);
  assert.equal(child.signal, null);
  assert.equal(child.stdout, "CALLER_CONTINUES");
  assert.equal(child.stderr, "");
});
