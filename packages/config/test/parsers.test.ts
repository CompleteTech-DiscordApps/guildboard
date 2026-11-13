import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { parseDatabaseUrl, parsePort } from "../src/index.js";

test("ports accept inclusive boundaries and decimal leading zeroes", () => {
  for (const [input, expected] of [
    ["1", 1], ["65535", 65535], ["80", 80], ["00080", 80], ["0123", 123],
    ["0".repeat(10000) + "42", 42],
  ] as const) {
    assert.equal(parsePort(input), expected);
  }
});

test("ports reject missing, non-decimal, whitespace, fractional and overflow forms", () => {
  const invalid = [
    undefined, "", "0", "000", "65536", "9999999999999999999999999", "9".repeat(10000),
    "-1", "-0", "+80", "1.0", "80.5", ".5", "8e1", "8E1", "0x50", "0o120", "0b1010",
    "Infinity", "NaN", " ", " 80", "80 ", "80\n", "80\r\n", "80\t", "8\n0", "\u00a080",
    "8\u200b0", "８０", "٨٠", "80abc", "80\u0000",
  ];
  for (const [index, input] of invalid.entries()) {
    assert.equal(parsePort(input), undefined, `invalid port case ${index}`);
  }
});

test("numeric JavaScript values are not coerced into valid ports", () => {
  for (const value of [80, null, true, { toString() { throw new Error("coercion"); } }]) {
    assert.equal(parsePort(value as unknown as string), undefined);
  }
});

test("database URLs require mysql, hostname and a database path; accepted strings remain exact", () => {
  const accepted = [
    "mysql://localhost/guildboard",
    "mysql://user:SENTINEL_DB_PASSWORD@database:3306/guildboard?charset=utf8mb4",
    "mysql://[::1]:3306/guildboard",
    "MYSQL://database/guildboard",
    "mysql://database/encoded%20database",
  ];
  for (const input of accepted) {
    assert.equal(parseDatabaseUrl(input), input);
  }
});

test("malformed URLs, absent database/host and wrong protocols return no value or exception", () => {
  const invalid = [
    undefined, "", " ", "not a URL", "://database/board", "mysql:board", "mysql:///board",
    "mysql://user:password@/board", "mysql://database", "mysql://database/",
    "mysql://database/?database=board", "mysql://database/#board", "mysql://[::1/board",
    "mysql://database:invalid/board", "mysql://database:65536/board",
    "https://database/board", "postgres://database/board", "mariadb://database/board",
    "file://database/board", "javascript:alert(1)",
  ];
  for (const [index, input] of invalid.entries()) {
    assert.equal(parseDatabaseUrl(input), undefined, `invalid URL case ${index}`);
  }
  assert.equal(parseDatabaseUrl({ toString() { throw new Error("coercion"); } } as unknown as string), undefined);
});

test("URL checks and rejected ports do not log credential-bearing inputs or terminate the caller", () => {
  const moduleUrl = new URL("../src/index.js", import.meta.url).href;
  const child = spawnSync(process.execPath, ["--input-type=module", "--eval", `
    import assert from 'node:assert/strict';
    const {parseDatabaseUrl, parsePort} = await import(${JSON.stringify(moduleUrl)});
    const password = 'SENTINEL_DB_PASSWORD';
    const accepted = 'mysql://user:' + password + '@localhost/board';
    assert.equal(parseDatabaseUrl(accepted), accepted);
    assert.equal(parseDatabaseUrl('mysql://user:' + password + '@[invalid/board'), undefined);
    assert.equal(parsePort('65536'), undefined);
    process.stdout.write('CALLER_CONTINUES');
  `], { encoding: "utf8", env: {}, timeout: 5000 });
  assert.equal(child.error, undefined);
  assert.equal(child.status, 0);
  assert.equal(child.signal, null);
  assert.equal(child.stdout, "CALLER_CONTINUES");
  assert.equal(child.stderr, "");
});
