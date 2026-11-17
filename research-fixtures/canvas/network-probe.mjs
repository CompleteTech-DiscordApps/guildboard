// Empirical routing controls using synthetic data and two owned loopback servers.
import assert from 'node:assert/strict';
import {mkdtemp, realpath, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {chromium} from 'playwright';
import {browserLaunchOptions, isFixtureNetworkRequest, startFixtureServer} from './fixture-runtime.mjs';

const parent = await realpath(tmpdir());
const root = await mkdtemp(path.join(parent, 'guildboard-canvas-network-'));
const servers = [];
let browser;
try {
  await writeFile(path.join(root, 'index.html'), '<!doctype html><title>Synthetic routing control</title>fixture');
  const server = await startFixtureServer(root);
  servers.push(server);
  const other = await startFixtureServer(root);
  servers.push(other);
  const origin = `http://127.0.0.1:${server.address().port}`;
  const otherOrigin = `http://127.0.0.1:${other.address().port}`;
  let otherOriginRequests = 0;
  other.on('request', () => { otherOriginRequests++; });
  browser = await chromium.launch(browserLaunchOptions(process.env.CHROMIUM_PATH));
  const page = await browser.newPage();
  const intercepted = [];
  const blockedRequests = [];
  await page.route('**/*', route => {
    const url = route.request().url();
    intercepted.push(url);
    if (isFixtureNetworkRequest(url, origin)) return route.continue();
    blockedRequests.push(url);
    return route.abort();
  });
  await page.goto(origin);
  assert.equal(await page.evaluate(() => fetch('/').then(response => response.ok)), true);
  const opaqueResources = await page.evaluate(async () => {
    const dataText = await fetch('data:text/plain,canvas-data').then(response => response.text());
    const textUrl = URL.createObjectURL(new Blob(['canvas-blob'], {type: 'text/plain'}));
    const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>';
    const imageUrl = URL.createObjectURL(new Blob([svg], {type: 'image/svg+xml'}));
    try {
      const blobText = await fetch(textUrl).then(response => response.text());
      const dataImage = new Image();
      dataImage.src = 'data:image/svg+xml,' + encodeURIComponent(svg);
      await dataImage.decode();
      const blobImage = new Image();
      blobImage.src = imageUrl;
      await blobImage.decode();
      return {dataText, blobText, dataImageLoaded: dataImage.naturalWidth === 1,
        blobImageLoaded: blobImage.naturalWidth === 1};
    } finally {
      URL.revokeObjectURL(textUrl);
      URL.revokeObjectURL(imageUrl);
    }
  });
  assert.deepEqual(opaqueResources, {dataText: 'canvas-data', blobText: 'canvas-blob',
    dataImageLoaded: true, blobImageLoaded: true});
  const opaqueIntercepts = intercepted.filter(url => /^(data|blob):/.test(url));
  assert.deepEqual(opaqueIntercepts, []);
  const otherOriginRejected = await page.evaluate(async url => {
    try { await fetch(url); return false; } catch { return true; }
  }, otherOrigin + '/');
  assert.equal(otherOriginRejected, true);
  assert.equal(otherOriginRequests, 0);
  assert.deepEqual(blockedRequests, [otherOrigin + '/']);
  console.log(JSON.stringify({result: 'network-controls-passed', browser: browser.version(),
    opaqueResources, opaqueIntercepts, otherOriginRejected, otherOriginRequests, blockedRequests,
    checks: ['fixture-origin network request succeeds', 'data/blob fetch and images succeed',
      'data/blob requests do not enter Playwright routing in this scenario',
      'another loopback origin is blocked before reaching its server'],
    limitations: ['Synthetic Chromium routing controls, not a universal browser-scheme or CSP assessment'],
  }, null, 2));
} finally {
  try { await browser?.close(); }
  finally {
    await Promise.all(servers.map(server => new Promise((resolve, reject) => {
      server.close(error => error ? reject(error) : resolve());
    })));
    assert.equal(path.dirname(root), parent);
    assert.ok(path.basename(root).startsWith('guildboard-canvas-network-'));
    await rm(root, {recursive: true, force: true});
  }
}
