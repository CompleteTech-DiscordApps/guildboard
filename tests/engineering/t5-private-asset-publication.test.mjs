import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { chmod, mkdir, mkdtemp, open, readFile, readdir, stat, symlink } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import { pathToFileURL } from "node:url";

const output = mkdtempSync(
  path.join(process.env.ENGINEERING_TEST_TMP || os.tmpdir(), "gb-private-assets-"),
);
after(() => rmSync(output, { recursive: true, force: true }));
writeFileSync(path.join(output, "package.json"), '{"type":"module"}');
const build = spawnSync(
  process.execPath,
  ["node_modules/typescript/lib/tsc.js", "-p", "apps/api/tsconfig.json", "--outDir", output],
  { encoding: "utf8" },
);
assert.equal(build.status, 0, build.stderr + build.stdout);
const { publishPrivateAsset } = await import(pathToFileURL(path.join(output, "index.js")));

const published = { ok: true, outcome: "published" };
const existing = { ok: true, outcome: "already-published" };
const invalid = { ok: false, code: "INVALID_MESSAGE" };
const conflict = { ok: false, code: "ASSET_CONFLICT" };
const unavailable = { ok: false, code: "DEPENDENCY_UNAVAILABLE" };
const tooLarge = { ok: false, code: "PAYLOAD_TOO_LARGE" };

function intentFor(bytes, scope = {}) {
  return {
    guildRef: "guild-a",
    boardRef: "board-a",
    assetRef: "asset-a",
    byteLength: bytes.length,
    sha256: createHash("sha256").update(bytes).digest("hex"),
    ...scope,
  };
}

async function fixture(t) {
  const root = await mkdtemp(path.join(output, "store-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  return { root, maxBytes: 128 * 1024 };
}

test("validates scope, limits, length and digest before storage I/O", async (t) => {
  const { root } = await fixture(t);
  const absent = path.join(root, "absent");
  const bytes = Buffer.from("1234");
  const intent = intentFor(bytes);
  const store = { root: absent, maxBytes: 4 };
  for (const badIntent of [
    { ...intent, guildRef: "../guild" },
    { ...intent, boardRef: "board\n" },
    { ...intent, assetRef: "" },
    { ...intent, assetRef: "x".repeat(129) },
    { ...intent, byteLength: 3 },
    { ...intent, byteLength: 0 },
    { ...intent, byteLength: 3.5 },
    { ...intent, sha256: "0".repeat(64) },
    { ...intent, sha256: intent.sha256.toUpperCase() },
  ]) {
    assert.deepEqual(await publishPrivateAsset(store, badIntent, bytes), invalid);
  }
  assert.deepEqual(await publishPrivateAsset(store, { ...intent, byteLength: 5 }, bytes), tooLarge);
  assert.deepEqual(await publishPrivateAsset(store, intent, Buffer.from("12345")), tooLarge);
  assert.deepEqual(
    await publishPrivateAsset({ ...store, maxBytes: Infinity }, intent, bytes),
    unavailable,
  );
  assert.deepEqual(await publishPrivateAsset(store, intent, bytes), unavailable);
  assert.deepEqual(await readdir(root), []);
  assert.deepEqual(await publishPrivateAsset({ ...store, root }, intent, bytes), published);
});

test("publishes exact canonical bytes privately and scopes otherwise identical asset IDs", async (t) => {
  const store = await fixture(t);
  const bytes = Buffer.alloc(store.maxBytes, 0x41);
  for (const scope of [
    {},
    { guildRef: "guild-b" },
    { boardRef: "board-b" },
    { assetRef: "asset-b" },
  ]) {
    assert.deepEqual(await publishPrivateAsset(store, intentFor(bytes, scope), bytes), published);
    assert.deepEqual(await publishPrivateAsset(store, intentFor(bytes, scope), bytes), existing);
  }
  const names = await readdir(store.root);
  assert.equal(names.length, 4);
  for (const name of names) {
    assert.match(name, /^asset-[a-f0-9]{64}$/u);
    const file = path.join(store.root, name);
    assert.equal((await stat(file)).mode & 0o7777, 0o400);
    assert.deepEqual(await readFile(file), bytes);
  }
});

test("one concurrent writer installs the object and exact retries converge", async (t) => {
  const store = await fixture(t);
  const bytes = Buffer.from("same canonical bytes");
  const outcomes = await Promise.all(
    Array.from({ length: 8 }, () => publishPrivateAsset(store, intentFor(bytes), bytes)),
  );
  assert.equal(outcomes.filter((outcome) => outcome.outcome === "published").length, 1);
  assert.equal(outcomes.filter((outcome) => outcome.outcome === "already-published").length, 7);
  assert.equal((await readdir(store.root)).length, 1);
});

test("conflicting writers and interrupted retries never replace the winning object", async (t) => {
  const store = await fixture(t);
  const bytes = [Buffer.from("first"), Buffer.from("other")];
  const outcomes = await Promise.all(
    bytes.map((value) => publishPrivateAsset(store, intentFor(value), value)),
  );
  const winner = outcomes.findIndex((outcome) => outcome.ok);
  assert.ok(winner >= 0);
  assert.deepEqual(outcomes[winner], published);
  assert.deepEqual(outcomes[1 - winner], conflict);
  const names = await readdir(store.root);
  assert.equal(names.length, 1);
  assert.deepEqual(await readFile(path.join(store.root, names[0])), bytes[winner]);
  assert.deepEqual(
    await publishPrivateAsset(store, intentFor(bytes[winner]), bytes[winner]),
    existing,
  );
});

test("denies unsafe roots and target entries without changing their contents", async (t) => {
  const store = await fixture(t);
  const bytes = Buffer.from("canonical");
  const intent = intentFor(bytes);
  const alias = path.join(store.root, "alias");
  const privateDir = path.join(store.root, "private");
  await mkdir(privateDir, { mode: 0o700 });
  await symlink(privateDir, alias);
  assert.deepEqual(
    await publishPrivateAsset({ ...store, root: alias }, intent, bytes),
    unavailable,
  );
  await chmod(privateDir, 0o755);
  assert.deepEqual(
    await publishPrivateAsset({ ...store, root: privateDir }, intent, bytes),
    unavailable,
  );
  assert.deepEqual(await readdir(privateDir), []);

  const cleanStore = await fixture(t);
  assert.deepEqual(await publishPrivateAsset(cleanStore, intent, bytes), published);
  const [name] = await readdir(cleanStore.root);
  const other = path.join(cleanStore.root, name);
  const destination = path.join(store.root, name);
  await symlink(other, destination);
  assert.deepEqual(await publishPrivateAsset(store, intent, bytes), unavailable);
  assert.deepEqual(await readFile(other), bytes);
  assert.deepEqual(await readFile(destination), bytes);
  assert.deepEqual((await readdir(store.root)).sort(), ["alias", name, "private"].sort());
});

test("conflicts on wrong stored length or digest and keeps unrelated stages", async (t) => {
  const store = await fixture(t);
  const bytes = Buffer.from("identical length");
  const intent = intentFor(bytes);
  assert.deepEqual(await publishPrivateAsset(store, intent, bytes), published);
  const [name] = await readdir(store.root);
  const destination = path.join(store.root, name);
  const orphan = path.join(store.root, "stage-unrelated");
  writeFileSync(orphan, "prior interrupted stage", { mode: 0o600 });
  for (const stored of [Buffer.alloc(store.maxBytes * 2), Buffer.alloc(bytes.length, 0x62)]) {
    await chmod(destination, 0o600);
    writeFileSync(destination, stored);
    await chmod(destination, 0o400);
    assert.deepEqual(await publishPrivateAsset(store, intent, bytes), conflict);
    assert.deepEqual(await readFile(destination), stored);
  }
  assert.equal(await readFile(orphan, "utf8"), "prior interrupted stage");
});

test("file sync failure removes its own stage and a directory sync failure can retry", async (t) => {
  const store = await fixture(t);
  const bytes = Buffer.from("canonical");
  const intent = intentFor(bytes);
  const directory = await open(store.root, "r");
  const prototype = Object.getPrototypeOf(directory);
  await directory.close();
  const original = prototype.sync;
  const syncs = [];
  let fail = "file";
  t.mock.method(prototype, "sync", async function () {
    const kind = (await this.stat()).isDirectory() ? "directory" : "file";
    syncs.push(kind);
    if (fail === kind) throw Object.assign(new Error("synthetic sync failure"), { code: "EIO" });
    return original.call(this);
  });

  assert.deepEqual(await publishPrivateAsset(store, intent, bytes), unavailable);
  assert.deepEqual(await readdir(store.root), []);
  assert.deepEqual(syncs.splice(0), ["file"]);

  fail = "directory";
  assert.deepEqual(await publishPrivateAsset(store, intent, bytes), unavailable);
  const [name, ...rest] = await readdir(store.root);
  assert.deepEqual(rest, []);
  assert.deepEqual(await readFile(path.join(store.root, name)), bytes);
  assert.deepEqual(syncs.splice(0), ["file", "file", "directory"]);

  fail = undefined;
  assert.deepEqual(await publishPrivateAsset(store, intent, bytes), existing);
  assert.deepEqual(syncs, ["file", "directory"]);
  assert.deepEqual(await readdir(store.root), [name]);
});
