// Fresh synthetic scenes; creation and draft removal use ordinary browser input.
import assert from 'node:assert/strict';
import {isDeepStrictEqual} from 'node:util';
import {isFixtureNetworkRequest} from './fixture-runtime.mjs';

const viewport = {width: 1200, height: 800};
const seedIds = ['creation-rectangle', 'creation-text', 'creation-tombstone'];
const intendedText = 'Fresh synthetic text';

async function frame(page) {
  const handle = await page.waitForFunction(() => new Promise(resolve => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)));
  }), null, {timeout: 5000});
  await handle.dispose();
}

const snapshot = page => page.evaluate(() => window.creationSnapshot());
const newElements = observation => observation.elements.filter(element => !seedIds.includes(element.id));

function assertSeeds(observation, before) {
  assert.deepEqual(observation.elements.filter(element => seedIds.includes(element.id)), before.elements,
    'every complete seeded element, scene order and explicit tombstone must survive');
  assert.equal(new Set(observation.elements.map(element => element.id)).size, observation.elements.length,
    'element IDs must stay unique');
}

export async function probeTextCreation(browser, origin) {
  const blockedRequests = [];
  const pageErrors = [];
  const trials = [];
  const scenarios = [
    {open: 'double-click', finish: 'Control+Enter'},
    {open: 'text-shortcut-click', finish: 'Escape'},
    {open: 'text-shortcut-click', finish: 'outside-click'},
    // Escape submits in the pinned editor. Explicitly clear the draft first.
    {open: 'double-click', finish: 'clear-then-Escape'},
  ];
  for (const scenario of scenarios) {
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
            {id: seedIds[1], type: 'text', x: 650, y: 280, text: 'Seeded synthetic text'},
            {id: seedIds[2], type: 'rectangle', x: 200, y: 280, width: 50, height: 50},
          ]);
          elements[2] = {...elements[2], isDeleted: true};
          window.editor.updateScene({elements, captureUpdate: window.capture.NEVER});
        }, seedIds);
        await frame(page);
        await page.evaluate(readonly => window.setReadonly(readonly), readonly);
        await page.waitForFunction(readonly => window.editor.getAppState().viewModeEnabled === readonly, readonly);
        await page.locator('.excalidraw').click({position: {x: 1050, y: 650}});
        await frame(page);
        await page.evaluate(() => {
          window.creationSnapshot = (elements = window.editor.getSceneElementsIncludingDeleted()) => {
            const state = window.editor.getAppState();
            const editor = document.querySelector('textarea.excalidraw-wysiwyg');
            const active = document.activeElement;
            return {
              elements: structuredClone(elements),
              selectedIds: Object.keys(state.selectedElementIds).filter(id => state.selectedElementIds[id]),
              activeTool: state.activeTool.type,
              viewMode: state.viewModeEnabled,
              viewport: {scrollX: state.scrollX, scrollY: state.scrollY, zoom: state.zoom.value},
              textEditor: editor ? {value: editor.value, focused: active === editor,
                selectionStart: editor.selectionStart, selectionEnd: editor.selectionEnd} : null,
              focus: {tag: active?.tagName ?? null, role: active?.getAttribute('role') ?? null,
                label: active?.getAttribute('aria-label') ?? null,
                inCanvas: !!active?.closest('.excalidraw')},
            };
          };
          window.creationCallbacks = [];
          window.creationOverflow = false;
          window.creationPhase = 'opening';
          window.observeFixtureChange = elements => {
            if (window.creationCallbacks.length >= 200) {
              window.creationOverflow = true;
              return;
            }
            window.creationCallbacks.push({phase: window.creationPhase, ...window.creationSnapshot(elements)});
          };
        });
        const before = await snapshot(page);
        assert.deepEqual(before.elements.map(({id, isDeleted}) => ({id, isDeleted})),
          seedIds.map((id, index) => ({id, isDeleted: index === 2})));
        assert.deepEqual(before.selectedIds, []);
        assert.equal(before.textEditor, null);

        let toolSelection = null;
        if (scenario.open === 'text-shortcut-click') {
          await page.keyboard.press('t');
          await frame(page);
          toolSelection = await snapshot(page);
          if (!readonly) assert.equal(toolSelection.activeTool, 'text', 'real shortcut must select text tool');
          await page.mouse.click(900, 500);
        } else {
          await page.mouse.dblclick(900, 500);
        }
        await frame(page);
        const opened = await snapshot(page);
        let createdId = null;
        if (!readonly) {
          assert.equal(opened.textEditor?.focused, true, 'creation must open and focus the real text editor');
          assert.equal(opened.textEditor.value, '');
          const created = newElements(opened);
          assert.equal(created.length, 1, 'blank-canvas input must generate exactly one new element');
          assert.equal(created[0].type, 'text');
          assert.equal(created[0].isDeleted, false);
          assert.equal(typeof created[0].id, 'string');
          assert.ok(created[0].id.length > 0);
          createdId = created[0].id;
        } else {
          assert.equal(opened.textEditor, null, 'viewer must not open a creation editor');
        }
        await page.evaluate(() => { window.creationPhase = 'typing'; });
        // Same input in both modes; no fill(), synthetic input dispatch or scene update.
        await page.keyboard.type(intendedText);
        await frame(page);
        const typed = await snapshot(page);
        if (!readonly) {
          assert.equal(typed.textEditor?.focused, true);
          assert.equal(typed.textEditor.value, intendedText);
          assert.equal(typed.textEditor.selectionStart, intendedText.length);
          assert.equal(typed.textEditor.selectionEnd, intendedText.length);
          const created = newElements(typed);
          assert.equal(created.length, 1);
          assert.equal(created[0].id, createdId, 'typing must retain the generated ID');
          assert.equal(created[0].text, intendedText);
          assert.equal(created[0].originalText, intendedText);
          assert.equal(created[0].isDeleted, false);
        } else {
          assert.equal(typed.textEditor, null);
        }
        await page.evaluate(() => { window.creationPhase = 'finishing'; });
        let cleared = null;
        if (scenario.finish === 'clear-then-Escape') {
          await page.keyboard.press('Control+a');
          await page.keyboard.press('Backspace');
          await frame(page);
          cleared = await snapshot(page);
          if (!readonly) assert.equal(cleared.textEditor?.value, '', 'cancel control must clear the actual draft');
          await page.keyboard.press('Escape');
        } else if (scenario.finish === 'outside-click') {
          await page.mouse.click(1050, 650);
        } else {
          await page.keyboard.press(scenario.finish);
        }
        await frame(page);
        const finished = await snapshot(page);
        assert.equal(finished.textEditor, null, 'finish/cancel must close the editor');
        if (!readonly) {
          const created = newElements(finished);
          assert.equal(created.length, 1);
          assert.equal(created[0].id, createdId, 'finish/cancel must retain the generated ID');
          const cancelled = scenario.finish === 'clear-then-Escape';
          assert.equal(created[0].isDeleted, cancelled);
          assert.equal(created[0].text, cancelled ? '' : intendedText);
          assert.equal(created[0].originalText, cancelled ? '' : intendedText);
        }
        // A separate bounded settling window checks ID/scene stability after closure.
        await page.evaluate(() => { window.creationPhase = 'settled'; });
        await frame(page);
        const settled = await snapshot(page);
        assert.deepEqual(settled.elements, finished.elements, 'closed draft scene must remain stable');
        const callbacks = await page.evaluate(() => ({entries: window.creationCallbacks, overflow: window.creationOverflow}));
        assert.equal(callbacks.overflow, false, 'callback evidence must not be truncated');
        for (const observation of [toolSelection, opened, typed, cleared, finished, settled,
          ...callbacks.entries].filter(Boolean)) {
          assertSeeds(observation, before);
          if (readonly) {
            assert.deepEqual(observation.elements, before.elements, 'viewer must preserve the complete baseline at every observation');
            assert.equal(observation.textEditor, null, 'viewer callback must not expose a text editor');
          } else {
            const extras = newElements(observation);
            assert.ok(extras.length <= 1);
            for (const element of extras) assert.equal(element.id, createdId, 'all creation callbacks must use the same new ID');
          }
        }
        if (!readonly) {
          assert.ok(callbacks.entries.some(entry => newElements(entry).some(element =>
            element.id === createdId && element.text === intendedText && !element.isDeleted)),
          'writable positive control must include a real typed-scene callback');
          assert.ok(callbacks.entries.some(entry => isDeepStrictEqual(entry.elements, finished.elements)),
            'writable finish/cancel must be observed in a complete callback');
        }
        trials.push({mode: readonly ? 'viewer' : 'writable', ...scenario, intendedText, createdId,
          before, toolSelection, opened, typed, cleared, finished, settled,
          sceneUnchanged: isDeepStrictEqual(before.elements, settled.elements), callbacks: callbacks.entries});
      } catch (error) {
        const evidence = await page.evaluate(() => ({
          scene: window.creationSnapshot?.() ?? null,
          callbacks: window.creationCallbacks ?? [], overflow: window.creationOverflow ?? false,
        })).catch(() => null);
        console.error(JSON.stringify({textCreationFailure: {readonly, ...scenario, message: error.message, evidence}}));
        throw error;
      } finally {
        await page.close();
      }
    }
  }
  assert.deepEqual(blockedRequests, []);
  assert.deepEqual(pageErrors, []);
  return {viewport, trials, blockedRequests, pageErrors};
}
