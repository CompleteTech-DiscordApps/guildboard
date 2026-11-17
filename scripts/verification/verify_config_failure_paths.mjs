// Native CI only: exercise runner failures in a disposable isolated tree.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, copyFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const marker = 'config-negative-secret-sentinel';
const root = await mkdtemp(join(tmpdir(), 'config-verification-'));
const harness = resolve('scripts/verification/verify_config.mjs');
const isolated = join(root, 'scripts/verification/verify_config.mjs');
const timeoutMs = 15000;
function run(args, env, onData = () => {}) {
  return new Promise((resolveRun, reject) => {
    const child = spawn(process.execPath, args, { env, stdio: ['pipe', 'pipe', 'pipe'] });
    let output = '';
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; child.kill('SIGKILL'); }, timeoutMs);
    child.on('error', error => { clearTimeout(timer); reject(error); });
    for (const stream of [child.stdout, child.stderr]) stream.on('data', chunk => {
      output += chunk.toString();
      if (output.length > 65536) child.kill('SIGKILL');
      onData(output, child);
    });
    child.on('close', (code, signal) => { clearTimeout(timer); resolveRun({ code, signal, output, timedOut }); });
  });
}
try {
  await mkdir(join(root, 'scripts/verification'), { recursive: true });
  await copyFile(harness, isolated);
  const env = { ...process.env, SESSION_SECRET: marker, DATABASE_URL: `mysql://user:${marker}@localhost/db` };
  const missing = await run([isolated], env);
  assert.equal(missing.timedOut, false);
  assert.notEqual(missing.code, 0);
  assert.match(missing.output, /"status":"failed","scenario":"prerequisite"/);
  assert.doesNotMatch(missing.output, /"status":"passed"/);
  assert.equal(missing.output.includes(marker), false);

  let ready = false;
  const interrupted = await run([harness], { ...env, CONFIG_VERIFY_HANDSHAKE: '1' }, (output, child) => {
    if (!ready && output.split('\n').includes('{"status":"ready"}')) {
      ready = true;
      child.kill('SIGKILL');
    }
  });
  assert.equal(interrupted.timedOut, false);
  assert.equal(ready, true);
  assert.notEqual(interrupted.code, 0);
  assert.equal(interrupted.signal, 'SIGKILL');
  assert.doesNotMatch(interrupted.output, /"status":"passed"/);
  assert.equal(interrupted.output.includes(marker), false);
  let released = false;
  const continued = await run([harness], { ...env, CONFIG_VERIFY_HANDSHAKE: '1' }, (output, child) => {
    if (!released && output.split('\n').includes('{"status":"ready"}')) {
      released = true;
      child.stdin.end('continue\n');
    }
  });
  assert.equal(continued.timedOut, false);
  assert.equal(released, true);
  assert.equal(continued.code, 0);
  assert.match(continued.output, /"status":"passed","scenarios":131125,"assertions":262252/);
  assert.equal(continued.output.includes(marker), false);
  console.log(JSON.stringify({ status: 'passed', checks: ['missing-compiled-module', 'interrupted-before-continuation', 'handshake-continuation'] }));
} catch {
  // Do not print child output, environment, or assertion values.
  console.error(JSON.stringify({ status: 'failed', scenario: 'runner-failure-paths' }));
  process.exitCode = 1;
} finally {
  await rm(root, { recursive: true, force: true });
}
