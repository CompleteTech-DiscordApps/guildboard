import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { checkBoundaries } from "../../scripts/engineering/boundaries.mjs";

const projects = [
  "apps/activity",
  "apps/api",
  "apps/bot",
  "packages/contracts",
  "packages/canvas",
  "packages/auth",
  "packages/collaboration",
  "packages/config",
];
function fixture(run) {
  const root = fs.mkdtempSync(
    path.join(process.env.ENGINEERING_TEST_TMP || os.tmpdir(), "gb-boundary-"),
  );
  try {
    for (const project of projects) {
      fs.mkdirSync(path.join(root, project, "src"), { recursive: true });
      fs.writeFileSync(
        path.join(root, project, "tsconfig.json"),
        JSON.stringify({
          compilerOptions: { baseUrl: ".", paths: { "@secret/*": ["../../packages/auth/src/*"] } },
          include: ["src"],
        }),
      );
      fs.writeFileSync(path.join(root, project, "src/index.ts"), "export {};\n");
    }
    run(root);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}
for (const [title, project, source, allowed] of [
  [
    "activity contract type",
    "apps/activity",
    "import type { X } from '@guildboard/contracts';",
    true,
  ],
  ["canvas contract export", "packages/canvas", "export * from '@guildboard/contracts';", true],
  ["server builtin", "apps/api", "import fs from 'node:fs';", true],
  ["activity server package", "apps/activity", "import '@guildboard/auth';", false],
  ["app to app", "apps/api", "export * from '@guildboard/bot';", false],
  ["browser builtin", "packages/contracts", "import('node:fs');", false],
  ["relative traversal", "apps/activity", "import '../../../packages/auth/src/index';", false],
  ["alias traversal", "apps/activity", "import '@secret/index';", false],
  ["import equals", "apps/activity", "import x = require('@guildboard/config');", false],
  ["import type", "apps/activity", "type X = import('@guildboard/config').X;", false],
  ["nonliteral", "apps/api", "require(variable);", false],
  ["indirect require", "apps/api", "const load = require;", false],
  ["indirect global loader", "apps/api", "globalThis['require']('fs');", false],
  ["unknown workspace", "apps/api", "import '@guildboard/unknown';", false],
  ["syntax", "apps/api", "import { from;", false],
])
  test(title, () =>
    fixture((root) => {
      fs.writeFileSync(path.join(root, project, "src/index.ts"), source);
      const errors = checkBoundaries(root);
      assert.equal(errors.length === 0, allowed, errors.join("\n"));
    }),
  );
test("invalid config and symlink rejected", () =>
  fixture((root) => {
    fs.writeFileSync(path.join(root, "apps/api/tsconfig.json"), "{");
    fs.symlinkSync("index.ts", path.join(root, "apps/activity/src/link.ts"));
    const errors = checkBoundaries(root).join("\n");
    assert.match(errors, /invalid tsconfig/);
    assert.match(errors, /symlink forbidden/);
  }));
