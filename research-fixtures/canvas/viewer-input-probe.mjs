// Synthetic local scenes and real browser input; no server authorization claim.
import assert from 'node:assert/strict';
import {isDeepStrictEqual} from 'node:util';
import {isFixtureNetworkRequest} from './fixture-runtime.mjs';

const viewport = {width: 1200, height: 800};
const rectangleId = 'input-rectangle';
const textId = 'input-text';
const tombstoneId = 'input-tombstone';

async function frame(page) {
  const handle = await page.waitForFunction(() => new Promise(resolve => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)));
  }), null, {timeout: 5000});
  await handle.dispose();
}

async function snapshot(page) {
  return page.evaluate(() => {
    const state = window.editor.getAppState();
    return {
      // Keep the complete elements, including text, versions and tombstones.
      elements: window.editor.getSceneElementsIncludingDeleted(),
      selectedIds: Object.keys(state.selectedElementIds).filter(id => state.selectedElementIds[id]),
      viewport: {scrollX: state.scrollX, scrollY: state.scrollY, zoom: state.zoom.value},
      activeTool: state.activeTool.type,
      editingText: !!document.querySelector('textarea.excalidraw-wysiwyg'),
    };
  });
}

export async function probeViewerInput(browser, origin) {
  const blockedRequests = [];
  const pageErrors = [];
  async function fresh(readonly, run) {
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
      await page.evaluate(({rectangleId, textId, tombstoneId}) => {
        const elements = window.makeElements([
          {id: rectangleId, type: 'rectangle', x: 400, y: 280, width: 120, height: 100},
          {id: textId, type: 'text', x: 650, y: 280, text: 'Synthetic input text'},
          {id: tombstoneId, type: 'rectangle', x: 200, y: 280, width: 50, height: 50},
        ]);
        elements[2] = {...elements[2], isDeleted: true};
        window.editor.updateScene({elements, captureUpdate: window.capture.NEVER});
      }, {rectangleId, textId, tombstoneId});
      await frame(page);
      await page.evaluate(readonly => window.setReadonly(readonly), readonly);
      await page.waitForFunction(readonly => window.editor.getAppState().viewModeEnabled === readonly, readonly);
      await page.locator('.excalidraw').click({position: {x: 1050, y: 650}});
      await frame(page);
      const before = await snapshot(page);
      assert.deepEqual(before.elements.map(({id, isDeleted}) => ({id, isDeleted})), [
        {id: rectangleId, isDeleted: false}, {id: textId, isDeleted: false},
        {id: tombstoneId, isDeleted: true},
      ]);
      assert.deepEqual(before.selectedIds, []);
      await page.evaluate(() => {
        window.inputCallbacks = [];
        window.inputCallbackOverflow = false;
        window.observeFixtureChange = elements => {
          if (window.inputCallbacks.length >= 200) {
            window.inputCallbackOverflow = true;
            return;
          }
          const state = window.editor.getAppState();
          window.inputCallbacks.push({
            elements: structuredClone(elements),
            selectedIds: Object.keys(state.selectedElementIds).filter(id => state.selectedElementIds[id]),
            viewMode: state.viewModeEnabled,
          });
        };
      });
      const observations = await run(page, before);
      await frame(page);
      const after = await snapshot(page);
      const callbacks = await page.evaluate(() => ({
        entries: window.inputCallbacks, overflow: window.inputCallbackOverflow,
      }));
      assert.equal(callbacks.overflow, false, 'callback evidence must not be truncated');
      if (readonly) {
        assert.deepEqual(after.elements, before.elements, 'viewer input must preserve the full scene');
        for (const callback of callbacks.entries) {
          assert.deepEqual(callback.elements, before.elements, 'viewer callbacks must preserve every element');
        }
      }
      assert.deepEqual(after.elements.find(element => element.id === tombstoneId),
        before.elements.find(element => element.id === tombstoneId), 'seeded tombstone must survive');
      return {mode: readonly ? 'viewer' : 'writable', before, ...observations, after,
        sceneUnchanged: isDeepStrictEqual(before.elements, after.elements), callbacks: callbacks.entries};
    } catch (error) {
      // Retain the actual scene/callbacks if a positive control or invariant fails.
      const evidence = await page.evaluate(() => window.editor ? {
        elements: window.editor.getSceneElementsIncludingDeleted(),
        selectedIds: window.editor.getAppState().selectedElementIds,
        callbacks: window.inputCallbacks ?? [],
      } : null).catch(() => null);
      console.error(JSON.stringify({viewerInputFailure: {readonly, message: error.message, evidence}}));
      throw error;
    } finally {
      await page.close();
    }
  }

  const trials = [];
  for (const readonly of [false, true]) {
    trials.push({action: 'pointer-select-delete', ...await fresh(readonly, async page => {
      await page.mouse.click(400, 330);
      await frame(page);
      const selected = await snapshot(page);
      if (!readonly) assert.deepEqual(selected.selectedIds, [rectangleId]);
      await page.keyboard.press('Delete');
      await frame(page);
      const deleted = await snapshot(page);
      if (!readonly) assert.equal(deleted.elements.find(element => element.id === rectangleId)?.isDeleted, true);
      return {selected};
    })});
    trials.push({action: 'keyboard-select-all-delete', ...await fresh(readonly, async page => {
      await page.keyboard.press('Control+a');
      await frame(page);
      const selected = await snapshot(page);
      if (!readonly) assert.deepEqual([...selected.selectedIds].sort(), [rectangleId, textId].sort());
      await page.keyboard.press('Delete');
      await frame(page);
      if (!readonly) assert.deepEqual((await snapshot(page)).elements.filter(element => !element.isDeleted), []);
      return {selected};
    })});
    trials.push({action: 'pointer-drag', ...await fresh(readonly, async (page, before) => {
      await page.mouse.move(400, 330);
      await page.mouse.down();
      await page.mouse.move(480, 370, {steps: 5});
      await page.mouse.up();
      await frame(page);
      if (!readonly) {
        const rectangle = (await snapshot(page)).elements.find(element => element.id === rectangleId);
        assert.equal(rectangle.x, before.elements[0].x + 80);
        assert.equal(rectangle.y, before.elements[0].y + 40);
      }
      return {};
    })});
    trials.push({action: 'double-click-text-type', ...await fresh(readonly, async page => {
      await page.mouse.dblclick(670, 290);
      await frame(page);
      const editing = await snapshot(page);
      if (!readonly) assert.equal(editing.editingText, true);
      // Ordinary key input targets whichever surface the same pointer action opened.
      await page.keyboard.press('Control+a');
      await page.keyboard.type('Changed synthetic text');
      await page.keyboard.press('Escape');
      await frame(page);
      if (!readonly) assert.equal((await snapshot(page)).elements.find(element => element.id === textId)?.text,
        'Changed synthetic text');
      return {editing};
    })});
  }
  // Navigation has its own fresh scenes, separate from the edit-denial trials.
  const navigation = [];
  for (const readonly of [false, true]) {
    navigation.push(await fresh(readonly, async (page, before) => {
      await page.mouse.move(1000, 650);
      await page.mouse.wheel(0, 120);
      await page.waitForFunction(previous => {
        const state = window.editor.getAppState();
        return state.scrollX !== previous.scrollX || state.scrollY !== previous.scrollY;
      }, before.viewport);
      assert.deepEqual((await snapshot(page)).elements, before.elements);
      return {action: 'wheel-pan'};
    }));
  }
  assert.deepEqual(blockedRequests, []);
  assert.deepEqual(pageErrors, []);
  return {viewport, trials, navigation, blockedRequests, pageErrors};
}
