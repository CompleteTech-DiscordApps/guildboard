import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
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
    const completed = JSON.parse(manifest);
    assert.ok(Object.keys(completed.outputs).length > 0);
    const recipe = "scripts/engineering/build.mjs";
    const recipeDigest = createHash("sha256")
      .update(fs.readFileSync(path.join(dir, recipe)))
      .digest("hex");
    assert.equal(completed.inputs[recipe], recipeDigest);
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
    linkDependencies(dir);
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

// Recreate npm's workspace links in the fixture rather than resolving packages
// from the checkout's node_modules (which would hide stale or missing outputs).
function linkDependencies(dir) {
  const modules = path.join(dir, "node_modules");
  fs.mkdirSync(path.join(modules, "@guildboard"), { recursive: true });
  for (const name of ["typescript", "@types"]) {
    fs.symlinkSync(path.join(root, "node_modules", name), path.join(modules, name), "dir");
  }
  for (const group of ["apps", "packages"]) {
    for (const name of fs.readdirSync(path.join(dir, group))) {
      const workspace = path.join(dir, group, name);
      const pkg = JSON.parse(fs.readFileSync(path.join(workspace, "package.json")));
      fs.symlinkSync(workspace, path.join(modules, pkg.name), "dir");
    }
  }
}
function typecheck(dir) {
  return spawnSync(process.execPath, ["scripts/engineering/typecheck.mjs"], {
    cwd: dir,
    encoding: "utf8",
  });
}
test("clean package consumers typecheck through fresh transitive declarations", () => {
  const dir = copy();
  try {
    linkDependencies(dir);
    fs.writeFileSync(
      path.join(dir, "packages/canvas/src/index.ts"),
      "import { CONTRACT_VERSION } from '@guildboard/contracts';\nexport const version: typeof CONTRACT_VERSION = CONTRACT_VERSION;\n",
    );
    fs.writeFileSync(
      path.join(dir, "apps/activity/src/index.ts"),
      "import { CONTRACT_VERSION } from '@guildboard/contracts';\nimport { version } from '@guildboard/canvas';\nconsole.log(CONTRACT_VERSION, version);\n",
    );
    assert.ok(!fs.existsSync(path.join(dir, "packages/contracts/dist")));
    const result = typecheck(dir);
    assert.equal(result.status, 0, result.stderr + result.stdout);
    assert.ok(fs.existsSync(path.join(dir, "packages/contracts/dist/index.d.ts")));
    assert.ok(fs.existsSync(path.join(dir, "packages/canvas/dist/index.d.ts")));
    const build = run(dir);
    assert.equal(build.status, 0, build.stderr + build.stdout);
    assert.ok(fs.existsSync(path.join(dir, "engineering-build/manifest.json")));
  } finally {
    clean(dir);
  }
});
test("invalid consumer fails despite stale declarations and invalidates build completion", () => {
  const dir = copy();
  try {
    linkDependencies(dir);
    fs.mkdirSync(path.join(dir, "packages/contracts/dist"), { recursive: true });
    fs.writeFileSync(
      path.join(dir, "packages/contracts/dist/index.d.ts"),
      "export const MISSING: string;\n",
    );
    fs.mkdirSync(path.join(dir, "engineering-build"));
    fs.writeFileSync(path.join(dir, "engineering-build/manifest.json"), "stale");
    fs.writeFileSync(
      path.join(dir, "apps/activity/src/index.ts"),
      "import { MISSING } from '@guildboard/contracts';\nconsole.log(MISSING);\n",
    );
    const result = typecheck(dir);
    assert.notEqual(result.status, 0);
    assert.match(result.stdout + result.stderr, /has no exported member 'MISSING'/);
    assert.ok(!fs.existsSync(path.join(dir, "engineering-build/manifest.json")));
  } finally {
    clean(dir);
  }
});
