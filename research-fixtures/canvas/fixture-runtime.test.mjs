import assert from 'node:assert/strict';
import {mkdtemp, mkdir, realpath, rm, symlink, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {browserLaunchOptions, isFixtureNetworkRequest, startFixtureServer} from './fixture-runtime.mjs';

async function fixture(t) {
  const parent = await realpath(tmpdir());
  const sandbox = await mkdtemp(path.join(parent, 'guildboard-canvas-server-'));
  const root = path.join(sandbox, 'served');
  const outside = path.join(sandbox, 'outside');
  const servers = [];
  t.after(async () => {
    await Promise.all(servers.map(server => new Promise((resolve, reject) => {
      server.close(error => error ? reject(error) : resolve());
    })));
    assert.equal(path.dirname(sandbox), parent);
    assert.ok(path.basename(sandbox).startsWith('guildboard-canvas-server-'));
    await rm(sandbox, {recursive: true, force: true});
  });
  await mkdir(path.join(root, 'sub'), {recursive: true});
  await mkdir(outside);
  await writeFile(path.join(root, 'index.html'), 'fixture index');
  await writeFile(path.join(root, 'sub', 'inside.txt'), 'inside fixture');
  await writeFile(path.join(outside, 'secret.txt'), 'synthetic outside sentinel');
  const server = await startFixtureServer(root);
  servers.push(server);
  assert.equal(server.address().address, '127.0.0.1');
  return {root, outside, origin: `http://127.0.0.1:${server.address().port}`};
}

test('fixture server serves only its loopback root and nested files', async t => {
  const {origin} = await fixture(t);
  assert.equal(await (await fetch(origin)).text(), 'fixture index');
  assert.equal(await (await fetch(`${origin}/sub/inside.txt`)).text(), 'inside fixture');
});

test('fixture server rejects encoded traversal, malformed escapes and null bytes', async t => {
  const {origin} = await fixture(t);
  for (const pathname of ['/%2e%2e%2foutside%2fsecret.txt', '/%', '/%00']) {
    const response = await fetch(origin + pathname);
    assert.equal(response.status, 404, pathname);
    assert.equal(await response.text(), '');
  }
});

test('fixture server rejects a symlink or Windows junction escaping its root', async t => {
  const {root, outside, origin} = await fixture(t);
  await symlink(outside, path.join(root, 'escape'), process.platform === 'win32' ? 'junction' : 'dir');
  const response = await fetch(`${origin}/escape/secret.txt`);
  assert.equal(response.status, 404);
  assert.equal(await response.text(), '');
});

test('fixture server permits a symlink or junction whose target stays inside its root', async t => {
  const {root, origin} = await fixture(t);
  await symlink(path.join(root, 'sub'), path.join(root, 'alias'), process.platform === 'win32' ? 'junction' : 'dir');
  const response = await fetch(`${origin}/alias/inside.txt`);
  assert.equal(response.status, 200);
  assert.equal(await response.text(), 'inside fixture');
});

test('browser launch uses Playwright managed defaults unless an explicit path is supplied', () => {
  assert.deepEqual(browserLaunchOptions(), {headless: true, chromiumSandbox: true});
  assert.deepEqual(browserLaunchOptions(''), {headless: true, chromiumSandbox: true});
  assert.deepEqual(browserLaunchOptions('C:/fixture browser/chrome.exe'), {
    headless: true, chromiumSandbox: true, executablePath: 'C:/fixture browser/chrome.exe',
  });
});

test('fixture network policy rejects another loopback port, protocol and foreign origin', () => {
  const origin = 'http://127.0.0.1:32001';
  assert.equal(isFixtureNetworkRequest(`${origin}/asset.js`, origin), true);
  for (const url of ['http://127.0.0.1:32002/asset.js', 'https://127.0.0.1:32001/asset.js',
    'http://example.invalid/asset.js', 'file:///asset.js', 'data:text/plain,fixture',
    `blob:${origin}/fixture`, 'not a URL']) {
    assert.equal(isFixtureNetworkRequest(url, origin), false, url);
  }
});
