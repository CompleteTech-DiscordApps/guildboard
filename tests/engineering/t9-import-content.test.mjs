import assert from "node:assert/strict";
import { test } from "node:test";
import {
  createImportTextNode,
  IMPORT_CONTENT_LIMITS,
  IMPORT_CONTENT_VERSION,
  parseImportContent,
} from "../../packages/canvas/src/import-content.ts";

const approvedUrl = "https://docs.example/board/guide";
const policy = { approvedUrls: new Set([approvedUrl]) };
const envelope = (entries) => JSON.stringify({ version: IMPORT_CONTENT_VERSION, entries });
const textEntry = (text) => ({ kind: "text", text });
const linkEntry = (url) => ({ kind: "link", text: "Board guide", url });
const assetEntry = (assetId) => ({ kind: "asset", text: "Map label", assetId });
const invalid = { ok: false, code: "INVALID_MESSAGE" };
const tooLarge = { ok: false, code: "PAYLOAD_TOO_LARGE" };

test("projects supported content to literal text nodes without projecting metadata", () => {
  const entries = [
    textEntry('Board <draft> & notes "A" \\ {[]} café 🗺️'),
    linkEntry(approvedUrl),
    assetEntry("asset_Map-12_2"),
  ];
  const result = parseImportContent(envelope(entries), policy);
  assert.deepEqual(result, {
    ok: true,
    content: { version: IMPORT_CONTENT_VERSION, entries },
  });

  const labels = [];
  const document = {
    createTextNode(text) {
      const node = { data: text };
      labels.push(node);
      return node;
    },
  };
  assert.deepEqual(
    result.content.entries.map((entry) => createImportTextNode(document, entry)),
    labels,
  );
  assert.deepEqual(
    labels,
    entries.map(({ text }) => ({ data: text })),
  );
});

test("rejects invalid envelopes, unsupported versions and unknown entry fields", () => {
  for (const input of [
    null,
    { version: 1, entries: [] },
    '{"version":1,"entries":',
    "[]",
    '{"version":"1","entries":[]}',
    '{"version":0,"entries":[]}',
    '{"version":1,"entries":{}}',
    '{"version":1,"entries":[],"title":"Draft"}',
    envelope([null]),
    envelope([{ kind: "text", text: 42 }]),
    envelope([textEntry("\uD800")]),
    envelope([{ kind: "text", text: "Draft", format: "rich" }]),
    envelope([{ kind: "note", text: "Draft" }]),
    envelope([textEntry("First"), { kind: "note", text: "Second" }]),
  ]) {
    assert.deepEqual(parseImportContent(input), invalid);
  }
  assert.deepEqual(parseImportContent('{"version":2,"entries":[]}'), {
    ok: false,
    code: "UNSUPPORTED_VERSION",
  });
});

test("bounds UTF-8 input, nesting, entry count, text and URL lengths", () => {
  const empty = envelope([]);
  const exactBytes = empty + " ".repeat(IMPORT_CONTENT_LIMITS.encodedBytes - empty.length);
  assert.equal(parseImportContent(exactBytes).ok, true);
  assert.deepEqual(parseImportContent(exactBytes + " "), tooLarge);
  const multibyte = envelope(
    Array.from({ length: 10 }, () => textEntry("é".repeat(IMPORT_CONTENT_LIMITS.textCodeUnits))),
  );
  assert.ok(multibyte.length < IMPORT_CONTENT_LIMITS.encodedBytes);
  assert.deepEqual(parseImportContent(multibyte), tooLarge);
  assert.deepEqual(parseImportContent('{"version":1,"entries":[{"nested":[]}]}'), tooLarge);

  const maximumEntries = Array.from({ length: IMPORT_CONTENT_LIMITS.entries }, () => textEntry(""));
  assert.equal(parseImportContent(envelope(maximumEntries)).ok, true);
  assert.deepEqual(parseImportContent(envelope([...maximumEntries, textEntry("")])), tooLarge);
  const maximumText = "a".repeat(IMPORT_CONTENT_LIMITS.textCodeUnits);
  assert.equal(parseImportContent(envelope([textEntry(maximumText)])).ok, true);
  assert.deepEqual(parseImportContent(envelope([textEntry(maximumText + "a")])), tooLarge);
  const prefix = "https://docs.example/";
  const maximumUrl = prefix + "a".repeat(IMPORT_CONTENT_LIMITS.urlCodeUnits - prefix.length);
  assert.equal(
    parseImportContent(envelope([linkEntry(maximumUrl)]), {
      approvedUrls: new Set([maximumUrl]),
    }).ok,
    true,
  );
  assert.deepEqual(parseImportContent(envelope([linkEntry(maximumUrl + "a")]), policy), tooLarge);
});

test("URL metadata requires exact approval and the canonical HTTPS shape", () => {
  assert.deepEqual(parseImportContent(envelope([linkEntry(approvedUrl)])), invalid);
  assert.deepEqual(
    parseImportContent(envelope([linkEntry(approvedUrl + "/extra")]), policy),
    invalid,
  );
  for (const url of [
    "/board/guide",
    "http://docs.example/board/guide",
    "https://DOCS.example/board/guide",
    "https://docs.example:8443/board/guide",
    "https://docs.example",
    "https://docs.example/board/guide?edition=2",
    "https://docs.example/board/guide#intro",
    "https://docs.example/board/%67uide",
    "https://docs.example/board/./guide",
    "https://docs.example/board/guide ",
  ]) {
    assert.deepEqual(
      parseImportContent(envelope([linkEntry(url)]), { approvedUrls: new Set([url]) }),
      invalid,
    );
  }
});

test("asset entries carry an opaque token and a label", () => {
  assert.equal(parseImportContent(envelope([assetEntry("asset_" + "A".repeat(64))])).ok, true);
  for (const reference of [
    "map.png",
    "images/map.png",
    "https://docs.example/image/map.png",
    "asset_",
    "asset_Map 12",
    "asset_" + "A".repeat(65),
    42,
  ]) {
    assert.deepEqual(parseImportContent(envelope([assetEntry(reference)])), invalid);
  }
  assert.deepEqual(
    parseImportContent(envelope([{ ...assetEntry("asset_Map12"), filename: "map.png" }])),
    invalid,
  );
});
