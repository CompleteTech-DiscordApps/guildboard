import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";

const root = process.cwd();
function copy() {
  const dir = fs.mkdtempSync(
    path.join(process.env.ENGINEERING_TEST_TMP || os.tmpdir(), "gb-build-"),
  );
  for (const name of [
    "apps",
    "packages",
    "scripts",
    "package.json",
    "package-lock.json",
    "tsconfig.base.json",
  ])
    fs.cpSync(path.join(root, name), path.join(dir, name), {
      recursive: true,
      filter: (src) =>
        !src.split(path.sep).includes("dist") && !src.split(path.sep).includes("node_modules"),
    });
  return dir;
}
function run(dir) {
  return spawnSync(process.execPath, [path.join(root, "scripts/engineering/build.mjs")], {
    cwd: dir,
    encoding: "utf8",
  });
}
function clean(dir) {
  fs.rmSync(dir, { recursive: true, force: true });
}
test("invalid version fails without completion", () => {
  const dir = copy();
  try {
    const pkg = JSON.parse(fs.readFileSync(path.join(dir, "package.json")));
    pkg.version = "bad";
    fs.writeFileSync(path.join(dir, "package.json"), JSON.stringify(pkg));
    const result = run(dir);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /invalid root version/);
    assert.ok(!fs.existsSync(path.join(dir, "engineering-build/manifest.json")));
  } finally {
    clean(dir);
  }
});
test("missing compiler fails without completion", () => {
  const dir = copy();
  try {
    const result = run(dir);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /missing TypeScript compiler/);
    assert.ok(!fs.existsSync(path.join(dir, "engineering-build/manifest.json")));
  } finally {
    clean(dir);
  }
});
test("interruption before publication leaves no completion", async () => {
  const dir = copy();
  try {
    fs.symlinkSync(path.join(root, "node_modules"), path.join(dir, "node_modules"), "dir");
    const ready = path.join(dir, "ready");
    const proceed = path.join(dir, "continue");
    const child = spawn(process.execPath, [path.join(root, "scripts/engineering/build.mjs")], {
      cwd: dir,
      env: {
        ...process.env,
        ENGINEERING_BUILD_TEST_READY: ready,
        ENGINEERING_BUILD_TEST_CONTINUE: proceed,
      },
      stdio: "pipe",
    });
    let stderr = "";
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    const exited = new Promise((resolve) =>
      child.once("exit", (code, signal) => resolve({ code, signal })),
    );
    for (let i = 0; i < 600 && !fs.existsSync(ready) && child.exitCode === null; i++)
      await delay(100);
    if (!fs.existsSync(ready)) {
      child.kill("SIGKILL");
      await exited;
      assert.fail(`build never reached handshake: ${stderr}`);
    }
    child.kill("SIGKILL");
    const result = await exited;
    assert.equal(result.signal, "SIGKILL");
    assert.ok(!fs.existsSync(path.join(dir, "engineering-build/manifest.json")));
  } finally {
    clean(dir);
  }
});
test("successful builds remove stale output and bind hashes deterministically", () => {
  const dir = copy();
  try {
    fs.symlinkSync(path.join(root, "node_modules"), path.join(dir, "node_modules"), "dir");
    fs.mkdirSync(path.join(dir, "apps/activity/dist"), { recursive: true });
    fs.writeFileSync(path.join(dir, "apps/activity/dist/deleted.js"), "stale");
    const first = run(dir);
    assert.equal(first.status, 0, first.stderr);
    assert.ok(!fs.existsSync(path.join(dir, "apps/activity/dist/deleted.js")));
    const manifest = fs.readFileSync(path.join(dir, "engineering-build/manifest.json"), "utf8");
    assert.ok(Object.keys(JSON.parse(manifest).outputs).length > 0);
    const second = run(dir);
    assert.equal(second.status, 0, second.stderr);
    assert.equal(
      fs.readFileSync(path.join(dir, "engineering-build/manifest.json"), "utf8"),
      manifest,
    );
  } finally {
    clean(dir);
  }
});
test("actual boundary CLI rejects a forbidden import", () => {
  const dir = copy();
  try {
    fs.symlinkSync(path.join(root, "node_modules"), path.join(dir, "node_modules"), "dir");
    fs.writeFileSync(
      path.join(dir, "apps/activity/src/index.ts"),
      "import '@guildboard/config';\n",
    );
    const result = spawnSync(process.execPath, ["scripts/engineering/boundaries.mjs"], {
      cwd: dir,
      encoding: "utf8",
    });
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /forbidden dependency/);
  } finally {
    clean(dir);
  }
});
