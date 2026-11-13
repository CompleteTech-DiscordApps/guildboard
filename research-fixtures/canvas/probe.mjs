// Local fixture only. No Discord, server authorization or production claims.
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {browserLaunchOptions, isFixtureNetworkRequest, startFixtureServer} from './fixture-runtime.mjs';

const server = await startFixtureServer(process.cwd());
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  browser = await chromium.launch(browserLaunchOptions(process.env.CHROMIUM_PATH));
  const page = await browser.newPage({viewport: {width: 1200, height: 800}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const blockedRequests = [];
  await page.route('**/*', route => {
    const url = route.request().url();
    if (isFixtureNetworkRequest(url, origin)) return route.continue();
    blockedRequests.push(url);
    return route.abort();
  });
  await page.goto(origin);
  await page.waitForFunction(() => window.editor && !window.editor.getAppState().isLoading);
  const frame = () => page.evaluate(() => new Promise(resolve => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  }));
  await frame();
  await page.evaluate(() => {
    window.events.length = 0;
    window.editor.updateScene({
      elements: window.makeElements([{id: 'remote-baseline', type: 'rectangle', x: 500, y: 300, width: 100, height: 100}]),
      captureUpdate: window.capture.NEVER,
    });
  });
  await page.waitForFunction(() => window.editor.getSceneElements().some(element => element.id === 'remote-baseline'));
  await frame();
  const remoteCallbacks = await page.evaluate(() => window.events.length);
  // Callback counts are observations, not local intent or authenticated writes.
  const addLocalHistory = id => page.evaluate(id => {
    window.editor.updateScene({
      elements: [...window.editor.getSceneElements(), ...window.makeElements([
        {id, type: 'ellipse', x: 700, y: 300, width: 100, height: 100},
      ])],
      captureUpdate: window.capture.IMMEDIATELY,
    });
  }, id);
  await addLocalHistory('local-history');
  await page.waitForFunction(() => window.editor.getSceneElements().length === 2);
  await page.locator('.excalidraw').click({position: {x: 1000, y: 650}});
  await page.keyboard.press('Control+z');
  await page.waitForFunction(() => window.editor.getSceneElements().length === 1);
  assert.deepEqual(await page.evaluate(() => window.editor.getSceneElements().map(element => element.id)), ['remote-baseline']);

  // Prepare real undo history, then explicitly select existing content in view mode.
  await addLocalHistory('readonly-history');
  await page.waitForFunction(() => window.editor.getSceneElements().length === 2);
  await frame();
  await page.evaluate(() => window.setReadonly(true));
  await page.waitForFunction(() => window.editor.getAppState().viewModeEnabled === true);
  await page.evaluate(() => window.editor.updateScene({
    appState: {selectedElementIds: {'remote-baseline': true}},
    captureUpdate: window.capture.NEVER,
  }));
  assert.equal(await page.evaluate(() => window.editor.getAppState().selectedElementIds['remote-baseline']), true);
  const before = await page.evaluate(() => JSON.stringify(window.editor.getSceneElements()));
  await page.keyboard.press('Delete');
  await frame();
  assert.equal(await page.evaluate(() => JSON.stringify(window.editor.getSceneElements())), before);
  await page.keyboard.press('Control+z');
  await frame();
  assert.equal(await page.evaluate(() => JSON.stringify(window.editor.getSceneElements())), before);
  await page.keyboard.press('r');
  await page.mouse.move(800, 500);
  await page.mouse.down();
  await page.mouse.move(900, 600, {steps: 5});
  await page.mouse.up();
  await frame();
  assert.equal(await page.evaluate(() => JSON.stringify(window.editor.getSceneElements())), before);
  // Positive control proves a real undoable edit survived the view-mode attempts.
  await page.evaluate(() => window.setReadonly(false));
  await page.waitForFunction(() => window.editor.getAppState().viewModeEnabled === false);
  await page.keyboard.press('Control+z');
  await page.waitForFunction(() => window.editor.getSceneElements().length === 1);
  assert.deepEqual(await page.evaluate(() => window.editor.getSceneElements().map(element => element.id)), ['remote-baseline']);
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({
    result: 'local-fixture-passed', browser: browser.version(), remoteCallbacks,
    checks: ['remote ID preserved', 'NEVER remote baseline survives local undo',
      'view-mode Delete with selected content leaves scene unchanged',
      'view-mode undo with retained local history leaves scene unchanged',
      'view-mode pointer smoke leaves scene unchanged',
      're-enabled undo removes the prepared local-history edit'],
    blockedRequests,
    limitations: ['Not yet tested in Discord', 'No server permission checks',
      'No touch/stylus or accessibility acceptance', 'No concurrent remote overwrite/rollback coverage',
      'Selection is supplied through the editor API; paste/drop/text/context-menu controls remain untested'],
  }, null, 2));
} finally {
  try { await browser?.close(); }
  finally { await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve())); }
}
