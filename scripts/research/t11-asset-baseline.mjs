// Linux-only offline measurements of the built T5 private asset publication API.
import { createHash } from "node:crypto";
import { mkdtemp, readFile, readdir, rm, stat, statfs } from "node:fs/promises";
import { availableParallelism, release, tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { performance } from "node:perf_hooks";

const sizes = [64 * 1024, 512 * 1024, 2 * 1024 * 1024];
const parallelism = [1, 4];
const assetsPerCell = 12;
let interrupted = false;

function stop() {
  interrupted = true;
}

function checkInterrupted() {
  if (interrupted) throw new Error("interrupted");
}

function digest(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function fixture(byteLength) {
  return Array.from({ length: assetsPerCell }, (_, index) => {
    const bytes = createHash("shake256", { outputLength: byteLength })
      .update(`guildboard-asset-baseline-v1:${byteLength}:${index}`)
      .digest();
    const intent = {
      guildRef: "fixture-guild",
      boardRef: `fixture-board-${index % 3}`,
      assetRef: `fixture-asset-${index}`,
      byteLength,
      sha256: digest(bytes),
    };
    return { bytes, intent };
  });
}

async function measure(publish, store, assets, workers, expected) {
  let next = 0;
  let failed = false;
  const callMilliseconds = [];
  const cpuStart = process.cpuUsage();
  const start = performance.now();
  const results = await Promise.allSettled(
    Array.from({ length: workers }, async () => {
      try {
        while (!failed && !interrupted && next < assets.length) {
          const { bytes, intent } = assets[next++];
          const before = performance.now();
          const result = await publish(store, intent, bytes);
          callMilliseconds.push(performance.now() - before);
          if (!result.ok || result.outcome !== expected) {
            throw new Error("publication outcome mismatch");
          }
        }
      } catch (error) {
        failed = true;
        throw error;
      }
    }),
  );
  const cpu = process.cpuUsage(cpuStart);
  const wallMilliseconds = performance.now() - start;
  checkInterrupted();
  if (results.some((result) => result.status === "rejected")) {
    throw new Error("publication outcome mismatch");
  }
  return {
    outcome: expected,
    completed: callMilliseconds.length,
    wallMilliseconds,
    cpuUserMicroseconds: cpu.user,
    cpuSystemMicroseconds: cpu.system,
    callMilliseconds,
  };
}

async function inspectStore(root, assets) {
  const names = await readdir(root);
  if (names.length !== assets.length) throw new Error("unexpected store entries");
  const expected = new Map(assets.map(({ intent }) => [intent.sha256, intent.byteLength]));
  let logicalBytes = 0;
  let allocatedBytes = 0;
  for (const name of names) {
    if (!/^asset-[a-f0-9]{64}$/u.test(name)) throw new Error("unexpected store entry");
    const path = join(root, name);
    const file = await stat(path);
    if (!file.isFile() || (file.mode & 0o7777) !== 0o400) {
      throw new Error("unexpected asset type or permissions");
    }
    const sha256 = digest(await readFile(path));
    if (file.size !== expected.get(sha256)) throw new Error("asset verification failed");
    expected.delete(sha256);
    logicalBytes += file.size;
    allocatedBytes += file.blocks * 512;
  }
  return { files: names.length, logicalBytes, allocatedBytes };
}

async function collect(publish) {
  const cells = [];
  for (const size of sizes) {
    const assets = fixture(size);
    for (const workers of parallelism) {
      checkInterrupted();
      const root = await mkdtemp(join(resolve(tmpdir()), "gb-asset-baseline-"));
      try {
        const store = { root, maxBytes: sizes.at(-1) };
        const filesystemType = (await statfs(root)).type.toString(16);
        const newObjects = await measure(publish, store, assets, workers, "published");
        const existingObjects = await measure(publish, store, assets, workers, "already-published");
        const disk = await inspectStore(root, assets);
        cells.push({ size, workers, filesystemType, newObjects, existingObjects, disk });
      } finally {
        await rm(root, { recursive: true, force: true });
      }
    }
  }
  return cells;
}

async function main() {
  if (process.argv.length !== 2) {
    process.stderr.write("usage: node scripts/research/t11-asset-baseline.mjs\n");
    return 2;
  }
  if (process.platform !== "linux" || process.versions.node.split(".")[0] !== "24") {
    process.stderr.write("the asset baseline requires Linux and Node.js 24\n");
    return 1;
  }
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  try {
    const api = import.meta.resolve("@guildboard/api");
    const { publishPrivateAsset } = await import(api);
    if (typeof publishPrivateAsset !== "function") throw new Error("missing built API");
    const assetModule = new URL("private-asset-publication.js", api);
    const assetModuleSha256 = digest(await readFile(assetModule));
    const cells = await collect(publishPrivateAsset);
    checkInterrupted();
    process.stdout.write(
      JSON.stringify(
        {
          version: 1,
          scope: "local-private-asset-publication",
          capturedAtUtc: new Date().toISOString(),
          assetModuleSha256,
          environment: {
            node: process.version,
            architecture: process.arch,
            kernel: release(),
            availableParallelism: availableParallelism(),
          },
          database: "not-exercised",
          cells,
        },
        null,
        2,
      ) + "\n",
    );
    return 0;
  } catch {
    process.stderr.write(
      interrupted
        ? "asset baseline interrupted; no receipt emitted\n"
        : "asset baseline failed; verify the built API and private local temporary storage\n",
    );
    return 1;
  } finally {
    process.off("SIGINT", stop);
    process.off("SIGTERM", stop);
  }
}

process.exitCode = await main();
