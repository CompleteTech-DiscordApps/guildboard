import assert from "node:assert/strict";
import { execFile, spawn } from "node:child_process";
import { watch } from "node:fs";
import { mkdtemp, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { promisify } from "node:util";

const run = promisify(execFile);
const script = "scripts/research/t11-asset-baseline.mjs";

async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), "gb-asset-baseline-test-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  return { root, env: { ...process.env, TMPDIR: root } };
}

test("built asset API emits complete measurements and removes its stores", async (t) => {
  const { root, env } = await fixture(t);
  const { stdout, stderr } = await run(process.execPath, [script], { env, timeout: 30_000 });
  assert.equal(stderr, "");
  const receipt = JSON.parse(stdout);
  assert.equal(receipt.scope, "local-private-asset-publication");
  assert.match(receipt.assetModuleSha256, /^[a-f0-9]{64}$/u);
  assert.equal(receipt.database, "not-exercised");
  assert.deepEqual(
    receipt.cells.map(({ size, workers }) => [size, workers]),
    [
      [65_536, 1],
      [65_536, 4],
      [524_288, 1],
      [524_288, 4],
      [2_097_152, 1],
      [2_097_152, 4],
    ],
  );
  for (const { size, disk, newObjects, existingObjects } of receipt.cells) {
    assert.equal(disk.files, 12);
    assert.equal(disk.logicalBytes, size * disk.files);
    assert.ok(Number.isSafeInteger(disk.allocatedBytes) && disk.allocatedBytes >= 0);
    assert.equal(newObjects.outcome, "published");
    assert.equal(existingObjects.outcome, "already-published");
    for (const phase of [newObjects, existingObjects]) {
      assert.equal(phase.completed, disk.files);
      assert.equal(phase.callMilliseconds.length, disk.files);
      assert.ok(phase.callMilliseconds.every((value) => Number.isFinite(value) && value >= 0));
      for (const measured of ["wallMilliseconds", "cpuUserMicroseconds", "cpuSystemMicroseconds"]) {
        assert.ok(Number.isFinite(phase[measured]) && phase[measured] >= 0);
      }
    }
  }
  assert.deepEqual(await readdir(root), []);
});

test("invalid invocation and unavailable temp storage yield no receipt", async (t) => {
  const { root, env } = await fixture(t);
  await assert.rejects(run(process.execPath, [script, "--unknown"], { env }), {
    code: 2,
    stdout: "",
    stderr: /^usage:/u,
  });
  await assert.rejects(
    run(process.execPath, [script], { env: { ...env, TMPDIR: join(root, "absent") } }),
    { code: 1, stdout: "", stderr: /^asset baseline failed;/u },
  );
  assert.deepEqual(await readdir(root), []);
});

test("termination during a live cell drains it and emits no receipt", async (t) => {
  const { root, env } = await fixture(t);
  const watcher = watch(root, (_, name) => {
    if (name?.startsWith("gb-asset-baseline-")) child.kill("SIGTERM");
  });
  const child = spawn(process.execPath, [script], { env, timeout: 30_000 });
  let stdout = "";
  let stderr = "";
  child.stdout.setEncoding("utf8").on("data", (chunk) => {
    stdout += chunk;
  });
  child.stderr.setEncoding("utf8").on("data", (chunk) => {
    stderr += chunk;
  });
  const exit = await new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("close", (code, signal) => resolve({ code, signal }));
  }).finally(() => watcher.close());
  assert.deepEqual(exit, { code: 1, signal: null });
  assert.equal(stdout, "");
  assert.match(stderr, /^asset baseline interrupted;/u);
  assert.deepEqual(await readdir(root), []);
});
