import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { spawnSync } from "node:child_process";

const projects = [
  "packages/contracts",
  "packages/canvas",
  "packages/auth",
  "packages/collaboration",
  "packages/config",
  "apps/activity",
  "apps/api",
  "apps/bot",
];
const output = "engineering-build";
const hash = (file) => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
function files(dir) {
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .flatMap((entry) => {
      const file = path.join(dir, entry.name);
      if (entry.isSymbolicLink()) throw new Error(`unexpected symlink: ${file}`);
      if (entry.isDirectory())
        return ["dist", "node_modules"].includes(entry.name) ? [] : files(file);
      return [file];
    })
    .sort();
}
try {
  fs.rmSync(output, { recursive: true, force: true });
  for (const project of projects) fs.rmSync(`${project}/dist`, { recursive: true, force: true });
  const rootPackage = JSON.parse(fs.readFileSync("package.json"));
  if (!/^\d+\.\d+\.\d+$/.test(rootPackage.version)) throw new Error("invalid root version");
  const versions = {};
  for (const project of projects) {
    const pkg = JSON.parse(fs.readFileSync(`${project}/package.json`));
    if (!/^\d+\.\d+\.\d+$/.test(pkg.version) || !pkg.name || versions[pkg.name])
      throw new Error(`invalid package identity: ${project}`);
    versions[pkg.name] = pkg.version;
  }
  const compiler = "node_modules/typescript/bin/tsc";
  if (!fs.existsSync(compiler)) throw new Error("missing TypeScript compiler");
  const inputs = [
    "package.json",
    "package-lock.json",
    "tsconfig.base.json",
    ...projects.flatMap(files),
  ].sort();
  const inputHashes = Object.fromEntries(inputs.map((file) => [file, hash(file)]));
  for (const project of projects) {
    const result = spawnSync(process.execPath, [compiler, "-p", project], { stdio: "inherit" });
    if (result.error || result.status !== 0)
      throw new Error(`build failed: ${project}: ${result.error || result.status}`);
  }
  if (
    inputs.some((file) => hash(file) !== inputHashes[file]) ||
    JSON.stringify(inputs) !==
      JSON.stringify(
        [
          "package.json",
          "package-lock.json",
          "tsconfig.base.json",
          ...projects.flatMap(files),
        ].sort(),
      )
  )
    throw new Error("inputs changed during build");
  const outputs = projects.flatMap((project) => files(`${project}/dist`)).sort();
  const manifest = {
    format: 1,
    rootVersion: rootPackage.version,
    versions,
    inputs: inputHashes,
    outputs: Object.fromEntries(outputs.map((file) => [file, hash(file)])),
  };
  fs.mkdirSync(output);
  fs.writeFileSync(`${output}/manifest.pending`, JSON.stringify(manifest, null, 2) + "\n", {
    flag: "wx",
  });
  // CI-only handshake allows a deterministic termination before publication.
  if (process.env.ENGINEERING_BUILD_TEST_READY && process.env.ENGINEERING_BUILD_TEST_CONTINUE) {
    fs.writeFileSync(process.env.ENGINEERING_BUILD_TEST_READY, "ready\n");
    while (!fs.existsSync(process.env.ENGINEERING_BUILD_TEST_CONTINUE))
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 20);
  }
  fs.renameSync(`${output}/manifest.pending`, `${output}/manifest.json`);
} catch (error) {
  console.error(error.message);
  fs.rmSync(output, { recursive: true, force: true });
  process.exitCode = 1;
}
