import { spawnSync } from 'node:child_process';

for (const project of ['packages/contracts', 'packages/canvas', 'packages/auth', 'packages/collaboration', 'packages/config', 'apps/activity', 'apps/api', 'apps/bot']) {
  const result = spawnSync(process.execPath, ['node_modules/typescript/bin/tsc', '-p', project, '--noEmit'], { stdio: 'inherit' });
  if (result.error || result.status !== 0) { console.error(result.error || `typecheck failed: ${project}`); process.exit(1); }
}
