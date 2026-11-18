import { Buffer, constants as bufferConstants } from "node:buffer";
import { createHash, randomUUID } from "node:crypto";
import { constants } from "node:fs";
import { link, lstat, open, unlink } from "node:fs/promises";
import { isAbsolute, normalize } from "node:path";

export interface PrivateAssetStore {
  /** Provisioned private Linux directory under trusted ancestors, outside the web root. */
  readonly root: string;
  readonly maxBytes: number;
}

export interface PrivateAssetIntent {
  readonly guildRef: string;
  readonly boardRef: string;
  readonly assetRef: string;
  readonly byteLength: number;
  readonly sha256: string;
}

export type PrivateAssetPublication =
  | { readonly ok: true; readonly outcome: "published" | "already-published" }
  | {
      readonly ok: false;
      readonly code:
        "INVALID_MESSAGE" | "PAYLOAD_TOO_LARGE" | "ASSET_CONFLICT" | "DEPENDENCY_UNAVAILABLE";
    };

const unavailable = { ok: false, code: "DEPENDENCY_UNAVAILABLE" } as const;
const conflict = { ok: false, code: "ASSET_CONFLICT" } as const;
const invalid = { ok: false, code: "INVALID_MESSAGE" } as const;

function isOpaqueRef(value: string): boolean {
  return (
    typeof value === "string" &&
    value.length >= 1 &&
    value.length <= 128 &&
    !/[^A-Za-z0-9_-]/u.test(value)
  );
}

function hasErrorCode(error: unknown, code: string): boolean {
  return error instanceof Error && "code" in error && error.code === code;
}

async function verifyExisting(
  path: string,
  uid: bigint,
  device: bigint,
  byteLength: number,
  sha256: string,
): Promise<"missing" | "match" | "conflict"> {
  let entry;
  try {
    entry = await lstat(path, { bigint: true });
  } catch (error) {
    if (hasErrorCode(error, "ENOENT")) return "missing";
    throw error;
  }

  if (
    !entry.isFile() ||
    entry.dev !== device ||
    entry.uid !== uid ||
    (entry.mode & 0o7777n) !== 0o400n
  ) {
    throw new Error("Unsafe asset entry");
  }

  const file = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  try {
    const stat = await file.stat({ bigint: true });
    if (
      stat.dev !== entry.dev ||
      stat.ino !== entry.ino ||
      !stat.isFile() ||
      stat.uid !== uid ||
      (stat.mode & 0o7777n) !== 0o400n
    ) {
      throw new Error("Unsafe asset handle");
    }
    if (stat.size !== BigInt(byteLength)) return "conflict";

    const buffer = Buffer.alloc(Math.min(64 * 1024, byteLength));
    const hash = createHash("sha256");
    let offset = 0;
    while (offset < byteLength) {
      const { bytesRead } = await file.read(
        buffer,
        0,
        Math.min(buffer.length, byteLength - offset),
        offset,
      );
      if (bytesRead === 0) return "conflict";
      hash.update(buffer.subarray(0, bytesRead));
      offset += bytesRead;
    }
    const afterRead = await file.stat({ bigint: true });
    if (afterRead.size !== stat.size || afterRead.mtimeNs !== stat.mtimeNs) {
      throw new Error("Asset changed during verification");
    }
    if (hash.digest("hex") !== sha256) return "conflict";
    await file.sync();
    return "match";
  } finally {
    await file.close();
  }
}

async function writeAndVerifyStage(
  stage: string,
  destination: string,
  bytes: Buffer,
  uid: bigint,
  device: bigint,
  sha256: string,
): Promise<boolean> {
  // Exclusive creation makes this invocation the only owner of the staging name.
  const file = await open(
    stage,
    constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
    0o600,
  );
  try {
    try {
      await file.writeFile(bytes);
      await file.chmod(0o400);
      await file.sync();
    } finally {
      await file.close();
    }
    if ((await verifyExisting(stage, uid, device, bytes.length, sha256)) !== "match") {
      throw new Error("Asset stage failed integrity verification");
    }
    try {
      // A same-directory hard link installs a complete object atomically and
      // leaves the current destination alone when a concurrent publisher wins.
      await link(stage, destination);
      return true;
    } catch (error) {
      if (hasErrorCode(error, "EEXIST")) return false;
      throw error;
    }
  } finally {
    await unlink(stage);
  }
}

/**
 * Publish canonical bytes after trusted callers establish scope, authorize the
 * intent, validate the content, and reserve deployment storage and work bounds.
 */
export async function publishPrivateAsset(
  store: PrivateAssetStore,
  intent: PrivateAssetIntent,
  bytes: Uint8Array,
): Promise<PrivateAssetPublication> {
  try {
    const { root, maxBytes } = store;
    const { guildRef, boardRef, assetRef, byteLength, sha256 } = intent;
    if (
      process.platform !== "linux" ||
      process.geteuid === undefined ||
      typeof root !== "string" ||
      !isAbsolute(root) ||
      root.includes("\0") ||
      // O_NOFOLLOW applies to the terminal pathname component.
      root.endsWith("/") ||
      normalize(root) !== root ||
      !Number.isSafeInteger(maxBytes) ||
      maxBytes < 1 ||
      maxBytes > bufferConstants.MAX_LENGTH
    )
      return unavailable;
    if (!(bytes instanceof Uint8Array) || !Number.isSafeInteger(byteLength) || byteLength < 1)
      return invalid;
    if (byteLength > maxBytes || bytes.byteLength > maxBytes) {
      return { ok: false, code: "PAYLOAD_TOO_LARGE" };
    }
    if (
      bytes.byteLength !== byteLength ||
      typeof sha256 !== "string" ||
      sha256.length !== 64 ||
      /[^0-9a-f]/u.test(sha256) ||
      !isOpaqueRef(guildRef) ||
      !isOpaqueRef(boardRef) ||
      !isOpaqueRef(assetRef)
    ) {
      return invalid;
    }
    const snapshot = Buffer.alloc(byteLength);
    snapshot.set(bytes);
    if (createHash("sha256").update(snapshot).digest("hex") !== sha256) return invalid;

    const name = createHash("sha256")
      .update(JSON.stringify(["guildboard-private-asset-v1", guildRef, boardRef, assetRef]))
      .digest("hex");
    const directory = await open(
      root,
      constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW,
    );
    try {
      const stat = await directory.stat({ bigint: true });
      const uid = BigInt(process.geteuid());
      if (stat.uid !== uid || (stat.mode & 0o7777n) !== 0o700n) return unavailable;

      // Anchor all names to this open directory for the lifetime of the attempt.
      const directoryPath = `/proc/self/fd/${directory.fd}`;
      const destination = `${directoryPath}/asset-${name}`;
      const existing = await verifyExisting(destination, uid, stat.dev, byteLength, sha256);
      if (existing === "conflict") return conflict;
      let outcome: "published" | "already-published" = "already-published";
      if (existing === "missing") {
        const stage = `${directoryPath}/stage-${randomUUID()}`;
        if (await writeAndVerifyStage(stage, destination, snapshot, uid, stat.dev, sha256)) {
          outcome = "published";
        } else {
          const winner = await verifyExisting(destination, uid, stat.dev, byteLength, sha256);
          if (winner === "conflict") return conflict;
          if (winner === "missing") return unavailable;
        }
      }
      await directory.sync();
      return { ok: true, outcome };
    } finally {
      await directory.close();
    }
  } catch {
    return unavailable;
  }
}
