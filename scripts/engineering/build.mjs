import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';

const projects = ['packages/contracts', 'packages/canvas', 'packages/auth', 'packages/collaboration', 'packages/config', 'apps/activity', 'apps/api', 'apps/bot'];
const output = 'engineering-build';
fs.rmSync(output, { recursive: true, force: true });
const hash = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
function files(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(dir, entry.name);
    if (entry.isSymbolicLink()) throw new Error(`unexpected symlink: ${file}`);
    if (entry.isDirectory()) return entry.name === 'dist' || entry.name === 'node_modules' ? [] : files(file);
    return [file];
  }).sort();
}
try {
  const rootPackage = JSON.parse(fs.readFileSync('package.json'));
  if (!/^\d+\.\d+\.\d+$/.test(rootPackage.version)) throw new Error('invalid root version');
  const versions = {};
  for (const project of projects) {
    const pkg = JSON.parse(fs.readFileSync(`${project}/package.json`));
    if (!/^\d+\.\d+\.\d+$/.test(pkg.version)) throw new Error(`invalid version: ${project}`);
    versions[pkg.name] = pkg.version;
  }
  const compiler = 'node_modules/typescript/bin/tsc';
  if (!fs.existsSync(compiler)) throw new Error('missing TypeScript compiler');
  for (const project of projects) {
    const result = spawnSync(process.execPath, [compiler, '-p', project], { stdio: 'inherit' });
    if (result.error || result.status !== 0) throw new Error(`build failed: ${project}: ${result.error || result.status}`);
  }
  const inputs = ['package.json', 'package-lock.json', 'tsconfig.base.json', ...projects.flatMap(files)].filter((file) => !file.includes('/dist/')).sort();
  const outputs = projects.flatMap((project) => files(`${project}/dist`)).sort();
  const manifest = { format: 1, rootVersion: rootPackage.version, versions, inputs: Object.fromEntries(inputs.map((file) => [file, hash(file)])), outputs: Object.fromEntries(outputs.map((file) => [file, hash(file)])) };
  fs.mkdirSync(output);
  fs.writeFileSync(`${output}/manifest.pending`, JSON.stringify(manifest, null, 2) + '\n', { flag: 'wx' });
  fs.renameSync(`${output}/manifest.pending`, `${output}/manifest.json`);
} catch (error) {
  console.error(error.message);
  fs.rmSync(output, { recursive: true, force: true });
  process.exitCode = 1;
}
