import fs from "node:fs";
import { spawnSync } from "node:child_process";

// Keep this topological order aligned with the boundary graph and build.
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

// Declarations are build outputs. Never leave a completion manifest describing
// outputs that this command has removed or replaced.
fs.rmSync("engineering-build", { recursive: true, force: true });
for (const project of projects) fs.rmSync(`${project}/dist`, { recursive: true, force: true });
for (const project of projects) {
  for (const mode of ["--noEmit", "--emitDeclarationOnly"]) {
    const result = spawnSync(
      process.execPath,
      ["node_modules/typescript/bin/tsc", "-p", project, mode],
      { stdio: "inherit" },
    );
    if (result.error || result.status !== 0) {
      console.error(result.error || `typecheck failed: ${project} (${mode})`);
      process.exit(1);
    }
  }
}
