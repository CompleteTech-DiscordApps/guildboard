// Finite synthetic scenes. Only visible pointer controls and real Escape/wheel input.
import assert from 'node:assert/strict';
import {isDeepStrictEqual} from 'node:util';
import {isFixtureNetworkRequest} from './fixture-runtime.mjs';

const viewport = {width: 1200, height: 800};
const seedIds = ['menu-rectangle', 'menu-text', 'menu-tombstone'];
const actions = {delete: 'deleteSelectedElements', duplicate: 'duplicateSelection'};
const snapshot = page => page.evaluate(() => window.menuSnapshot());
const without = (element, keys) => Object.fromEntries(Object.entries(element).filter(([key]) => !keys.includes(key)));

// Shared by the browser observations and independent negative assertion tests.
export function assertContextMenuTrial(trial, {deferMenuClosure = false} = {}) {
  const {scenario, readonly, before, opened, escaped, finished, settled, cleanup, callbacks, overflow, inputs, inputOverflow} = trial;
  assert.ok(['delete', 'duplicate', 'dismiss-wheel'].includes(scenario));
  assert.equal(overflow, false, 'callback evidence must not be truncated');
  assert.equal(inputOverflow, false, 'input evidence must not be truncated');
  assert.deepEqual(before.elements.map(({id, isDeleted}) => ({id, isDeleted})),
    seedIds.map((id, index) => ({id, isDeleted: index === 2})));
  assert.deepEqual(before.selectedIds, []);
  assert.equal(before.menu, null);
  assert.ok(opened.menu?.length > 0, 'ordinary right click must open a visible menu');
  assert.ok(opened.menu.every(item => item.visible && item.label && item.action));
  assert.equal(inputs.filter(input => input.type === 'contextmenu' && input.trusted).length, 1);
  // Retain BOTH original close requirements. Deferral collects diagnostics; it
  // never changes their required outcome or permits an aggregate success.
  const failedControls = [];
  for (const [checkpoint, entry] of [['finished', finished], ['settled', settled]]) {
    if (entry.menu !== null) failedControls.push({scenario, readonly, checkpoint,
      control: readonly || scenario === 'dismiss-wheel' ? 'Escape must dismiss menu' : 'activation must dismiss menu'});
  }
  assert.deepEqual(opened.elements, before.elements, 'opening the menu must preserve every element');
  assert.deepEqual(settled.elements, finished.elements, 'the completed scene must remain stable');
  const editActions = opened.menu.filter(item => Object.values(actions).includes(item.action));
  if (readonly) assert.deepEqual(editActions, [], 'viewer menu must omit Delete and Duplicate');
  if (readonly || scenario === 'dismiss-wheel') {
    assert.ok(escaped, 'retain the actual post-Escape observation');
    assert.deepEqual(escaped, finished, 'finished must precede any outside-click cleanup');
    assert.equal(trial.escapeDismissed, escaped.menu === null);
    assert.equal(typeof trial.escapeDismissalTimedOut, 'boolean');
    if (trial.escapeDismissalTimedOut) failedControls.push({scenario, readonly,
      checkpoint: 'escape-wait', control: 'Escape must dismiss menu within 10000ms'});
  }
  if (cleanup) {
    assert.equal(cleanup.method, 'outside-click');
    assert.equal(cleanup.after.menu, null, 'separate cleanup must close the menu');
    assert.deepEqual(cleanup.after.elements, settled.elements);
  }
  if (scenario === 'dismiss-wheel') {
    assert.deepEqual(opened.selectedIds, []);
    assert.notDeepEqual(settled.viewport, finished.viewport, 'wheel must navigate after Escape');
    assert.equal(settled.viewport.zoom, finished.viewport.zoom, 'ordinary wheel must pan without zoom');
    assert.ok(inputs.some(input => input.type === 'wheel' && input.trusted));
  }
  if (readonly || scenario === 'dismiss-wheel') {
    assert.ok(inputs.some(input => input.type === 'keydown' && input.key === 'Escape' && input.trusted));
    assert.deepEqual(finished.elements, before.elements);
  } else {
    assert.deepEqual(opened.selectedIds, [seedIds[0]], 'right click must select the intended rectangle');
    const control = editActions.find(item => item.action === actions[scenario]);
    assert.ok(control && !control.disabled, 'writable control must be visible and enabled');
    assert.ok(inputs.some(input => input.type === 'click' && input.action === actions[scenario] && input.trusted),
      'the visible action must receive a real pointer click');
    assert.ok(callbacks.some(entry => isDeepStrictEqual(entry.elements, finished.elements)),
      'successful writable edit must appear in a complete callback');
    if (scenario === 'delete') {
      assert.deepEqual(finished.elements.map(element => element.id), seedIds);
      const deleted = finished.elements[0];
      assert.equal(deleted.isDeleted, true, 'Delete must tombstone the targeted live rectangle');
      assert.deepEqual(without(deleted, ['isDeleted', 'version', 'versionNonce', 'updated']),
        without(before.elements[0], ['isDeleted', 'version', 'versionNonce', 'updated']));
      assert.ok(deleted.version > before.elements[0].version);
      assert.deepEqual(finished.elements.slice(1), before.elements.slice(1));
      assert.deepEqual(finished.selectedIds, []);
    } else {
      assert.deepEqual(finished.elements.filter(element => seedIds.includes(element.id)), before.elements,
        'Duplicate must preserve every complete original and its order');
      const copies = finished.elements.filter(element => !seedIds.includes(element.id));
      assert.equal(copies.length, 1, 'Duplicate must create one new element');
      const copy = copies[0];
      assert.ok(typeof copy.id === 'string' && copy.id.length > 0);
      assert.equal(copy.isDeleted, false);
      assert.deepEqual(without(copy, ['id', 'seed', 'version', 'versionNonce', 'updated', 'index', 'x', 'y']),
        without(before.elements[0], ['id', 'seed', 'version', 'versionNonce', 'updated', 'index', 'x', 'y']));
      assert.ok(Number.isFinite(copy.x) && Number.isFinite(copy.y));
      assert.ok(copy.x > before.elements[0].x && copy.y > before.elements[0].y, 'copy must be offset');
      assert.deepEqual(finished.selectedIds, [copy.id]);
    }
  }
  for (const entry of [before, opened, escaped, finished, settled, cleanup?.after, ...callbacks].filter(Boolean)) {
    assert.equal(entry.viewMode, readonly);
    assert.equal(new Set(entry.elements.map(element => element.id)).size, entry.elements.length);
    assert.deepEqual(entry.elements.find(element => element.id === seedIds[2]), before.elements[2],
      'the complete explicit tombstone must survive every checkpoint and callback');
    if (readonly || scenario === 'dismiss-wheel') {
      assert.deepEqual(entry.elements, before.elements, 'unchanged trials must preserve the complete scene in every callback');
    } else {
      assert.ok(isDeepStrictEqual(entry.elements, before.elements) || isDeepStrictEqual(entry.elements, finished.elements),
        'writable callbacks may contain only the complete original or completed scene');
    }
  }
  if (!deferMenuClosure) assert.deepEqual(failedControls, [], 'required menu dismissal remains unmet');
  return failedControls;
}

export function assertContextMenuAcceptance(trials) {
  assert.ok(Array.isArray(trials), 'trial evidence must be an array');
  assert.equal(trials.length, 6, 'exactly six independent trials are required');
  const expected = ['delete', 'duplicate', 'dismiss-wheel'].flatMap(scenario =>
    [false, true].map(readonly => `${scenario}:${readonly}`));
  const identities = trials.map(trial => {
    assert.ok(trial && typeof trial === 'object' && !Array.isArray(trial));
    assert.equal(typeof trial.readonly, 'boolean', 'trial mode must be a boolean');
    return `${trial.scenario}:${trial.readonly}`;
  });
  assert.equal(new Set(identities).size, 6, 'trial identities must be unique');
  assert.deepEqual([...identities].sort(), [...expected].sort(), 'every scenario/mode pair must be present');
  // Recompute from observations; a missing/edited ledger cannot manufacture success.
  const failedControls = trials.flatMap(trial => assertContextMenuTrial(trial, {deferMenuClosure: true}));
  assert.deepEqual(failedControls, [], 'required menu dismissal controls failed; cleanup is not Escape');
}

async function frame(page) {
  const handle = await page.waitForFunction(() => new Promise(resolve => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)));
  }), null, {timeout: 5000});
  await handle.dispose();
}

export async function probeContextMenu(browser, origin) {
  const blockedRequests = [];
  const pageErrors = [];
  const trials = [];
  for (const scenario of ['delete', 'duplicate', 'dismiss-wheel']) {
    // Require the writable positive control before interpreting its fresh viewer pair.
    for (const readonly of [false, true]) {
      const page = await browser.newPage({viewport, serviceWorkers: 'block'});
      page.setDefaultTimeout(10000);
      try {
        page.on('pageerror', error => pageErrors.push(error.message));
        await page.route('**/*', route => {
          const url = route.request().url();
          if (isFixtureNetworkRequest(url, origin)) return route.continue();
          blockedRequests.push(url);
          return route.abort();
        });
        await page.goto(origin);
        await page.waitForFunction(() => window.editor && !window.editor.getAppState().isLoading);
        await frame(page);
        await page.evaluate(seedIds => {
          const elements = window.makeElements([
            {id: seedIds[0], type: 'rectangle', x: 400, y: 280, width: 120, height: 100},
            {id: seedIds[1], type: 'text', x: 650, y: 280, text: 'Synthetic menu text'},
            {id: seedIds[2], type: 'rectangle', x: 200, y: 280, width: 50, height: 50},
          ]);
          elements[2] = {...elements[2], isDeleted: true};
          window.editor.updateScene({elements, captureUpdate: window.capture.NEVER});
        }, seedIds);
        await frame(page);
        await page.evaluate(readonly => window.setReadonly(readonly), readonly);
        await page.waitForFunction(readonly => window.editor.getAppState().viewModeEnabled === readonly, readonly);
        await page.mouse.click(1050, 650);
        await frame(page);
        await page.evaluate(() => {
          window.menuSnapshot = (elements = window.editor.getSceneElementsIncludingDeleted()) => {
            const state = window.editor.getAppState();
            const active = document.activeElement;
            const menu = document.querySelector('.context-menu');
            const buttons = [...(menu?.querySelectorAll('button') ?? [])];
            if (buttons.length > 40) throw Error('menu inventory exceeds fixture bound');
            const inventory = buttons.map(button => {
              const label = button.querySelector('.context-menu-item__label')?.textContent.trim() ?? '';
              if (label.length > 120) throw Error('menu label exceeds fixture bound');
              return {action: button.closest('li')?.dataset.testid ?? null, label,
                disabled: button.disabled, visible: button.getClientRects().length > 0};
            });
            return {elements: structuredClone(elements),
              selectedIds: Object.keys(state.selectedElementIds).filter(id => state.selectedElementIds[id]),
              activeTool: state.activeTool.type, viewMode: state.viewModeEnabled,
              viewport: {scrollX: state.scrollX, scrollY: state.scrollY, zoom: state.zoom.value},
              menu: menu ? inventory : null,
              focus: {tag: active?.tagName ?? null, role: active?.getAttribute('role') ?? null,
                label: active?.getAttribute('aria-label') ?? null,
                menuAction: active?.closest('.context-menu li')?.dataset.testid ?? null,
                inCanvas: !!active?.closest('.excalidraw')},
            };
          };
          window.menuCallbacks = [];
          window.menuOverflow = false;
          window.menuInputs = [];
          window.menuInputOverflow = false;
          window.menuPhase = 'opening';
          window.observeFixtureChange = elements => {
            if (window.menuCallbacks.length >= 200) { window.menuOverflow = true; return; }
            window.menuCallbacks.push({phase: window.menuPhase, ...window.menuSnapshot(elements)});
          };
          for (const type of ['contextmenu', 'click', 'keydown', 'wheel']) {
            document.addEventListener(type, event => {
              if (window.menuInputs.length >= 40) { window.menuInputOverflow = true; return; }
              window.menuInputs.push({type, trusted: event.isTrusted, key: event.key ?? null,
                action: event.target.closest?.('.context-menu li')?.dataset.testid ?? null});
            }, {capture: true, passive: true});
          }
        });
        const before = await snapshot(page);
        const point = scenario === 'dismiss-wheel' ? {x: 1000, y: 600} : {x: 400, y: 330};
        await page.mouse.click(point.x, point.y, {button: 'right'});
        await page.locator('.context-menu').waitFor({state: 'visible'});
        await frame(page);
        const opened = await snapshot(page);
        await page.evaluate(() => { window.menuPhase = 'finishing'; });
        let escaped = null;
        let escapeDismissalTimedOut = null;
        if (!readonly && scenario !== 'dismiss-wheel') {
          // The allowlisted visible button is the only menu item activated.
          const control = page.locator(`.context-menu li[data-testid="${actions[scenario]}"] button`);
          await control.waitFor({state: 'visible'});
          assert.equal(await control.isEnabled(), true);
          await control.click();
          await page.locator('.context-menu').waitFor({state: 'hidden'});
        } else {
          assert.equal(opened.menu.some(item => readonly && Object.values(actions).includes(item.action)), false);
          await page.keyboard.press('Escape');
          escapeDismissalTimedOut = false;
          try {
            await page.locator('.context-menu').waitFor({state: 'hidden', timeout: 10000});
          } catch (error) {
            if (error.name !== 'TimeoutError') throw error;
            escapeDismissalTimedOut = true;
          }
          await frame(page);
          escaped = await snapshot(page);
        }
        await frame(page);
        const finished = escaped ?? await snapshot(page);
        await page.evaluate(() => { window.menuPhase = 'settled'; });
        if (scenario === 'dismiss-wheel') {
          // Select an ordinary canvas point outside the actual open menu, if any.
          const bounds = escaped?.menu ? await page.locator('.context-menu').boundingBox() : null;
          const point = [{x: 800, y: 650}, {x: 600, y: 500}].find(({x, y}) =>
            !bounds || x < bounds.x || x > bounds.x + bounds.width || y < bounds.y || y > bounds.y + bounds.height);
          assert.ok(point, 'wheel requires an exposed canvas point');
          assert.equal(await page.evaluate(({x, y}) => document.elementFromPoint(x, y)?.tagName, point), 'CANVAS');
          await page.mouse.move(point.x, point.y);
          await page.mouse.wheel(0, 120);
          await page.waitForFunction(previous => {
            const state = window.editor.getAppState();
            return state.scrollX !== previous.scrollX || state.scrollY !== previous.scrollY;
          }, finished.viewport);
        }
        await frame(page);
        const settled = await snapshot(page);
        let cleanup = null;
        if (settled.menu) {
          // Only a separate continuation/cleanup observation, never Escape success.
          await page.evaluate(() => { window.menuPhase = 'outside-click-cleanup'; });
          const bounds = await page.locator('.context-menu').boundingBox();
          assert.ok(bounds, 'cleanup requires the actual visible menu bounds');
          const point = await page.evaluate(bounds =>
            [{x: 600, y: 650}, {x: 800, y: 500}, {x: 900, y: 400}].find(({x, y}) =>
              (x < bounds.x || x > bounds.x + bounds.width || y < bounds.y || y > bounds.y + bounds.height) &&
              document.elementFromPoint(x, y)?.tagName === 'CANVAS'), bounds);
          assert.ok(point, 'cleanup requires an exposed canvas point outside the menu');
          await page.mouse.click(point.x, point.y);
          await page.locator('.context-menu').waitFor({state: 'hidden'});
          await frame(page);
          cleanup = {method: 'outside-click', point, menuBounds: bounds, after: await snapshot(page)};
        }
        const evidence = await page.evaluate(() => ({callbacks: window.menuCallbacks, overflow: window.menuOverflow,
          inputs: window.menuInputs, inputOverflow: window.menuInputOverflow}));
        const trial = {scenario, readonly, before, opened, escaped,
          escapeDismissed: escaped ? escaped.menu === null : null, escapeDismissalTimedOut,
          finished, settled, cleanup, ...evidence};
        trial.failedControls = assertContextMenuTrial(trial, {deferMenuClosure: true});
        trials.push(trial);
      } catch (error) {
        const evidence = await page.evaluate(() => ({scene: window.menuSnapshot?.() ?? null,
          callbacks: window.menuCallbacks ?? [], overflow: window.menuOverflow ?? false,
          inputs: window.menuInputs ?? [], inputOverflow: window.menuInputOverflow ?? false})).catch(() => null);
        console.error(JSON.stringify({contextMenuFailure: {scenario, readonly, message: error.message, evidence}}));
        throw error;
      } finally {
        await page.close();
      }
    }
  }
  assert.deepEqual(blockedRequests, []);
  assert.deepEqual(pageErrors, []);
  const result = {viewport, trials, blockedRequests, pageErrors,
    failedControls: trials.flatMap(trial => trial.failedControls)};
  // Emit every independent observation before the original close requirements fail.
  console.log(JSON.stringify({contextMenuObservations: result}, null, 2));
  assertContextMenuAcceptance(trials);
  return result;
}
