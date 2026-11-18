export const IMPORT_CONTENT_VERSION = 1;
export const IMPORT_CONTENT_LIMITS = Object.freeze({
  encodedBytes: 64 * 1024,
  jsonDepth: 3,
  entries: 100,
  textCodeUnits: 4096,
  urlCodeUnits: 2048,
});

export type ImportContentEntry =
  | { readonly kind: "text"; readonly text: string }
  | { readonly kind: "link"; readonly text: string; readonly url: string }
  | { readonly kind: "asset"; readonly text: string; readonly assetId: string };

export interface ImportContent {
  readonly version: typeof IMPORT_CONTENT_VERSION;
  readonly entries: readonly ImportContentEntry[];
}

export interface ImportContentPolicy {
  /** Exact canonical HTTPS URLs supplied by the trusted caller. */
  readonly approvedUrls: ReadonlySet<string>;
}

export type ImportContentError = "INVALID_MESSAGE" | "PAYLOAD_TOO_LARGE" | "UNSUPPORTED_VERSION";

export type ImportContentResult =
  | { readonly ok: true; readonly content: ImportContent }
  | { readonly ok: false; readonly code: ImportContentError };

const textEncoder = new TextEncoder();
const unpairedSurrogate = /[\uD800-\uDFFF]/u;
const assetToken = /^asset_[A-Za-z0-9_-]{1,64}$/u;
const metadataUrl = /^https:\/\/[a-z0-9.-]+\/[A-Za-z0-9._~/-]*$/u;

function exceedsDepth(serialized: string): boolean {
  let depth = 0;
  let quoted = false;
  let escaped = false;
  for (const character of serialized) {
    if (quoted) {
      if (escaped) {
        escaped = false;
      } else if (character === "\\") {
        escaped = true;
      } else if (character === '"') {
        quoted = false;
      }
    } else if (character === '"') {
      quoted = true;
    } else if (character === "{" || character === "[") {
      if (++depth > IMPORT_CONTENT_LIMITS.jsonDepth) return true;
    } else if (character === "}" || character === "]") {
      depth--;
    }
  }
  return false;
}

/** Inspect names before JSON.parse can collapse them; leave value/syntax parsing to it. */
function hasRepeatedMembers(serialized: string): boolean {
  const scopes: (Set<string> | null)[] = [];
  for (let index = 0; index < serialized.length; index++) {
    const character = serialized[index];
    if (character === "{" || character === "[") {
      // The earlier depth check handles well-formed nesting. Bound malformed nesting too.
      if (scopes.length >= IMPORT_CONTENT_LIMITS.jsonDepth) throw new SyntaxError();
      scopes.push(character === "{" ? new Set<string>() : null);
    } else if (character === "}" || character === "]") {
      const scope = scopes.pop();
      if (scope === undefined || (scope === null) !== (character === "]")) {
        throw new SyntaxError();
      }
    } else if (character === '"') {
      const start = index++;
      while (index < serialized.length && serialized[index] !== '"') {
        if (serialized[index] === "\\") index++;
        index++;
      }
      if (index >= serialized.length) throw new SyntaxError();

      let next = index + 1;
      while (next < serialized.length && /[ \t\r\n]/u.test(serialized.charAt(next))) next++;
      if (serialized[next] !== ":") continue;
      const names = scopes.at(-1);
      if (!names) throw new SyntaxError();
      // Decode only the string token so equivalent JSON escapes name the same member.
      const name = JSON.parse(serialized.slice(start, index + 1)) as string;
      if (names.has(name)) return true;
      names.add(name);
    }
  }
  return false;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function hasOnlyFields(value: Record<string, unknown>, ...fields: string[]): boolean {
  return (
    Object.keys(value).length === fields.length &&
    fields.every((field) => Object.hasOwn(value, field))
  );
}

function isApprovedUrl(value: unknown, policy?: ImportContentPolicy): value is string {
  if (typeof value !== "string" || !metadataUrl.test(value) || !policy?.approvedUrls.has(value)) {
    return false;
  }
  try {
    return new URL(value).href === value;
  } catch {
    return false;
  }
}

/** Validate a bounded JSON content envelope. Callers authorize each opaque asset ID before use. */
export function parseImportContent(
  serialized: unknown,
  policy?: ImportContentPolicy,
): ImportContentResult {
  if (typeof serialized !== "string") return { ok: false, code: "INVALID_MESSAGE" };
  if (
    serialized.length > IMPORT_CONTENT_LIMITS.encodedBytes ||
    textEncoder.encode(serialized).byteLength > IMPORT_CONTENT_LIMITS.encodedBytes ||
    exceedsDepth(serialized)
  ) {
    return { ok: false, code: "PAYLOAD_TOO_LARGE" };
  }

  let decoded: unknown;
  try {
    if (hasRepeatedMembers(serialized)) return { ok: false, code: "INVALID_MESSAGE" };
    decoded = JSON.parse(serialized);
  } catch {
    return { ok: false, code: "INVALID_MESSAGE" };
  }

  if (!isRecord(decoded) || !hasOnlyFields(decoded, "version", "entries")) {
    return { ok: false, code: "INVALID_MESSAGE" };
  }
  const { version, entries } = decoded;
  if (typeof version !== "number" || !Number.isSafeInteger(version) || version < 1) {
    return { ok: false, code: "INVALID_MESSAGE" };
  }
  if (version !== IMPORT_CONTENT_VERSION) return { ok: false, code: "UNSUPPORTED_VERSION" };
  if (!Array.isArray(entries)) return { ok: false, code: "INVALID_MESSAGE" };
  if (entries.length > IMPORT_CONTENT_LIMITS.entries)
    return { ok: false, code: "PAYLOAD_TOO_LARGE" };

  const content: ImportContentEntry[] = [];
  for (const entry of entries as unknown[]) {
    if (!isRecord(entry) || typeof entry.text !== "string" || unpairedSurrogate.test(entry.text)) {
      return { ok: false, code: "INVALID_MESSAGE" };
    }
    const { kind, text } = entry;
    if (
      text.length > IMPORT_CONTENT_LIMITS.textCodeUnits ||
      (kind === "link" &&
        typeof entry.url === "string" &&
        entry.url.length > IMPORT_CONTENT_LIMITS.urlCodeUnits)
    ) {
      return { ok: false, code: "PAYLOAD_TOO_LARGE" };
    }

    if (kind === "text" && hasOnlyFields(entry, "kind", "text")) {
      content.push({ kind, text });
    } else if (
      kind === "link" &&
      hasOnlyFields(entry, "kind", "text", "url") &&
      isApprovedUrl(entry.url, policy)
    ) {
      content.push({ kind, text, url: entry.url });
    } else if (
      kind === "asset" &&
      hasOnlyFields(entry, "kind", "text", "assetId") &&
      typeof entry.assetId === "string" &&
      assetToken.test(entry.assetId)
    ) {
      content.push({ kind, text, assetId: entry.assetId });
    } else {
      return { ok: false, code: "INVALID_MESSAGE" };
    }
  }
  return { ok: true, content: { version, entries: content } };
}

/** Create a text node for an ordinary canvas label. URL and asset metadata stay separate. */
export function createImportTextNode(
  document: Pick<Document, "createTextNode">,
  entry: ImportContentEntry,
): Text {
  return document.createTextNode(entry.text);
}
