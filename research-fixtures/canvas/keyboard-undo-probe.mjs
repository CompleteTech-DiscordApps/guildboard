// Keyboard-only interaction with synthetic, API-seeded history in the local fixture.
import assert from 'node:assert/strict';
import {isDeepStrictEqual} from 'node:util';
import {isFixtureNetworkRequest} from './fixture-runtime.mjs';

const baselineId = 'keyboard-baseline';
const editId = 'keyboard-local-edit';
const viewport = {width: 1200, height: 800};

async function frame(page) {
  const settled = await page.waitForFunction(() => new Promise(resolve => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)));
  }));
  await settled.dispose();
}

function visibleScene(page) {
  return page.evaluate(() => window.editor.getSceneElements());
}

function sceneIds(elements) {
  return elements.map(element => element.id);
}

function activeElement(page) {
  return page.evaluate(() => {
    const element = document.activeElement;
    const path = [];
    for (let node = element; node?.parentElement; node = node.parentElement) {
      path.unshift(Array.prototype.indexOf.call(node.parentElement.children, node));
    }
    return {
      tag: element.tagName.toLowerCase(),
      id: element.id || undefined,
      ariaLabel: element.getAttribute('aria-label') ?? undefined,
      title: element.getAttribute('title') ?? undefined,
      text: element.matches('body, .excalidraw') ? undefined : element.textContent.trim().slice(0, 80) || undefined,
      editor: element.matches('.excalidraw'),
      path: path.join('.'),
    };
  });
}

async function seed(page, origin) {
  await page.goto(origin);
  await page.waitForFunction(() => window.editor && !window.editor.getAppState().isLoading);
  await frame(page);
  await page.evaluate(({baselineId, editId}) => {
    const [baseline, edit] = window.makeElements([
      {id: baselineId, type: 'rectangle', x: 500, y: 300, width: 100, height: 100},
      {id: editId, type: 'ellipse', x: 700, y: 300, width: 100, height: 100},
    ]);
    window.editor.updateScene({elements: [baseline], captureUpdate: window.capture.NEVER});
    window.seededKeyboardEdit = edit;
  }, {baselineId, editId});
  await frame(page);
  assert.deepEqual(sceneIds(await visibleScene(page)), [baselineId]);
  await page.evaluate(() => window.editor.updateScene({
    elements: [...window.editor.getSceneElements(), window.seededKeyboardEdit],
    captureUpdate: window.capture.IMMEDIATELY,
  }));
  await frame(page);
  assert.deepEqual(sceneIds(await visibleScene(page)), [baselineId, editId]);
}

async function traceFocus(page, tabKey, reached) {
  const trace = [await activeElement(page)];
  if (await reached(trace[0])) return {trace, reached: true};
  const seen = new Set();
  for (let step = 0; step < 64; step++) {
    await page.keyboard.press(tabKey);
    const focus = await activeElement(page);
    trace.push(focus);
    if (await reached(focus)) return {trace, reached: true};
    if (seen.has(focus.path)) return {trace, reached: false, stop: 'repeated-focus'};
    seen.add(focus.path);
  }
  throw new Error(`${tabKey} exceeded trace limit`);
}

export async function probeKeyboardUndo(browser, origin) {
  const blockedRequests = [];
  const pageErrors = [];

  async function runFresh(run) {
    const page = await browser.newPage({viewport, serviceWorkers: 'block'});
    try {
      page.on('pageerror', error => pageErrors.push(error.message));
      await page.route('**/*', route => {
        const url = route.request().url();
        if (isFixtureNetworkRequest(url, origin)) return route.continue();
        blockedRequests.push(url);
        return route.abort();
      });
      await seed(page, origin);
      const undo = page.getByRole('button', {name: 'Undo', exact: true});
      await undo.waitFor({state: 'visible'});
      assert.equal(await undo.isEnabled(), true);
      return await run(page, undo);
    } finally {
      await page.close();
    }
  }

  async function trial(tabKey, activationKey) {
    return runFresh(async (page, undo) => {
      const traversal = await traceFocus(page, tabKey, () =>
        undo.evaluate(button => button === document.activeElement));
      const before = await visibleScene(page);
      const sceneBefore = sceneIds(before);
      assert.deepEqual(sceneBefore, [baselineId, editId]);
      const result = {tabKey, traversal, sceneBefore, activation: {key: activationKey, attempted: false}};
      if (!traversal.reached) return result;
      await page.keyboard.press(activationKey);
      await frame(page);
      const after = await visibleScene(page);
      result.activation = {
        key: activationKey,
        attempted: true,
        sceneAfter: sceneIds(after),
        sceneUnchanged: isDeepStrictEqual(before, after),
        focusAfter: await activeElement(page),
      };
      return result;
    });
  }

  const trials = [];
  for (const tabKey of ['Tab', 'Shift+Tab']) {
    for (const activationKey of ['Enter', 'Space']) {
      trials.push(await trial(tabKey, activationKey));
    }
  }

  // The shortcut tests the same seed in a separate fresh editor.
  const positiveControl = await runFresh(async page => {
    const traversal = await traceFocus(page, 'Tab', focus => focus.editor);
    assert.equal(traversal.reached, true, 'Tab must reach the editor for the shortcut control');
    const sceneBefore = sceneIds(await visibleScene(page));
    assert.deepEqual(sceneBefore, [baselineId, editId]);
    await page.keyboard.press('Control+z');
    await page.waitForFunction(() => window.editor.getSceneElements().length === 1);
    const sceneAfter = sceneIds(await visibleScene(page));
    assert.deepEqual(sceneAfter, [baselineId]);
    return {key: 'Control+z', traversal, sceneBefore, sceneAfter};
  });
  assert.deepEqual(blockedRequests, []);
  assert.deepEqual(pageErrors, []);
  return {
    viewport,
    undo: {role: 'button', accessibleName: 'Undo', visible: true, enabled: true},
    trials,
    positiveControl,
    blockedRequests,
    pageErrors,
  };
}
