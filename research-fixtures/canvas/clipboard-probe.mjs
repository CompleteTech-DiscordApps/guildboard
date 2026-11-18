// Synthetic-only Linux headless clipboard. Never attach to a desktop browser.
import assert from 'node:assert/strict';
import {isDeepStrictEqual} from 'node:util';
import {chromium} from 'playwright';
import {browserLaunchOptions, isFixtureNetworkRequest} from './fixture-runtime.mjs';

const viewport = {width: 1200, height: 800};
const managedVersion = '141.0.7390.37'; // Playwright 1.56.1; isolation source inspected for this version.
const seedIds = ['clipboard-box', 'clipboard-text', 'clipboard-tombstone'];
const seedGroup = 'clipboard-original-group';
const intendedText = 'Synthetic clipboard text';
const boundText = 'Bound note';
const snapshot = page => page.evaluate(() => window.clipboardSnapshot());
const extras = observation => observation.elements.filter(element => !seedIds.includes(element.id));

async function frame(page) {
  const handle = await page.waitForFunction(() => new Promise(resolve => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)));
  }), null, {timeout: 5000});
  await handle.dispose();
}

async function clipboard(page, operation, value) {
  // Only called after the isolated backend/version gate. No preexisting reads.
  return page.evaluate(({operation, value}) => new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(Error('synthetic clipboard API timeout')), 5000);
    const task = operation === 'write' ? navigator.clipboard.writeText(value) : navigator.clipboard.readText();
    task.then(result => { clearTimeout(timer); resolve(result); }, error => { clearTimeout(timer); reject(error); });
  }), {operation, value});
}

async function seed(page) {
  await page.goto(page.fixtureOrigin);
  await page.waitForFunction(() => window.editor && !window.editor.getAppState().isLoading);
  await page.evaluate(({seedIds, seedGroup, boundText}) => {
    const elements = window.makeElements([
      {id: seedIds[0], type: 'rectangle', x: 400, y: 280, width: 180, height: 100},
      {id: seedIds[1], type: 'text', x: 420, y: 310, text: boundText},
      {id: seedIds[2], type: 'rectangle', x: 200, y: 280, width: 50, height: 50},
    ]);
    elements[0] = {...elements[0], groupIds: [seedGroup], boundElements: [{id: seedIds[1], type: 'text'}]};
    elements[1] = {...elements[1], groupIds: [seedGroup], containerId: seedIds[0]};
    elements[2] = {...elements[2], isDeleted: true};
    window.editor.updateScene({elements, captureUpdate: window.capture.NEVER});
  }, {seedIds, seedGroup, boundText});
  await frame(page);
}

function assertSeeds(observation, before) {
  assert.deepEqual(observation.elements.filter(element => seedIds.includes(element.id)), before.elements,
    'all original fields, scene order and tombstone must remain exact');
  assert.equal(new Set(observation.elements.map(element => element.id)).size, observation.elements.length);
}

function assertGroup(elements, forbiddenGroups) {
  assert.equal(elements.length, 2, 'one copied group must contain exactly two live members');
  const box = elements.find(element => element.type === 'rectangle');
  const text = elements.find(element => element.type === 'text');
  assert.ok(box && text);
  assert.equal(box.isDeleted, false);
  assert.equal(text.isDeleted, false);
  assert.equal(text.text, boundText);
  assert.equal(text.originalText, boundText);
  assert.equal(box.width, 180);
  assert.equal(box.height, 100);
  assert.equal(box.groupIds.length, 1);
  assert.deepEqual(text.groupIds, box.groupIds);
  assert.equal(typeof box.groupIds[0], 'string');
  assert.ok(box.groupIds[0].length > 0 && !forbiddenGroups.has(box.groupIds[0]), 'group ID must be fresh');
  // Both directions are required, so this cannot pass on an unbound seed.
  assert.equal(text.containerId, box.id);
  assert.deepEqual(box.boundElements, [{id: text.id, type: 'text'}]);
  return box.groupIds[0];
}

export async function probeClipboard(origin) {
  if (process.platform !== 'linux') return {result: 'unavailable', reason: 'isolated clipboard backend inspected only for Linux'};
  // The reviewed Ozone headless backend has no platform clipboard, selecting
  // ClipboardNonBacked. Do not use CHROMIUM_PATH or a user's connected browser.
  const env = {...process.env};
  for (const name of ['DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY']) delete env[name];
  const browser = await chromium.launch({...browserLaunchOptions(), env, args: ['--ozone-platform=headless']});
  const blockedRequests = [];
  const pageErrors = [];
  const trials = [];
  try {
    if (browser.version() !== managedVersion) return {result: 'unavailable', browser: browser.version(),
      reason: `clipboard isolation source gate requires managed Chromium ${managedVersion}; no clipboard calls made`};
    const session = await browser.newBrowserCDPSession();
    const {arguments: arguments_} = await session.send('Browser.getBrowserCommandLine');
    assert.ok(arguments_.includes('--ozone-platform=headless'));
    assert.ok(arguments_.some(argument => argument.startsWith('--headless')));
    assert.equal(arguments_.includes('--no-sandbox'), false);
    await session.detach();
    for (const scenario of ['plain-text', 'copied-bound-group']) {
      for (const readonly of [false, true]) {
        const context = await browser.newContext({viewport, serviceWorkers: 'block'});
        context.setDefaultTimeout(10000);
        await context.grantPermissions(['clipboard-read', 'clipboard-write'], {origin});
        await context.route('**/*', route => {
          const url = route.request().url();
          if (isFixtureNetworkRequest(url, origin)) return route.continue();
          if (blockedRequests.length < 20) blockedRequests.push(url);
          return route.abort();
        });
        context.on('page', page => page.on('pageerror', error => {
          if (pageErrors.length < 20) pageErrors.push(error.message);
        }));
        let page;
        try {
          page = await context.newPage();
          page.fixtureOrigin = origin;
          await seed(page);
          await page.bringToFront();
          // Overwrite before every read, copy or paste event, even in a fresh process.
          await clipboard(page, 'write', intendedText);
          let payload = intendedText;
          let donor = null;
          if (scenario === 'copied-bound-group') {
            // A separate writable donor provides identical clipboard data to viewers.
            await page.evaluate(() => {
              window.donorBefore = structuredClone(window.editor.getSceneElementsIncludingDeleted());
              window.donorCallbacks = [];
              window.donorCopies = [];
              window.donorOverflow = false;
              window.observeFixtureChange = elements => {
                if (window.donorCallbacks.length >= 200) { window.donorOverflow = true; return; }
                window.donorCallbacks.push(structuredClone(elements));
              };
              document.addEventListener('copy', event => {
                if (window.donorCopies.length >= 2) { window.donorOverflow = true; return; }
                window.donorCopies.push({trusted: event.isTrusted});
              }, {capture: true, passive: true});
            });
            await page.locator('.excalidraw').click({position: {x: 410, y: 290}});
            await frame(page);
            const selection = await page.evaluate(() => Object.keys(window.editor.getAppState().selectedElementIds)
              .filter(id => window.editor.getAppState().selectedElementIds[id]));
            assert.ok(selection.includes(seedIds[0]), 'ordinary pointer must select the donor container');
            assert.equal(selection.includes(seedIds[2]), false);
            await page.keyboard.press('Control+c');
            // Read only the already-primed isolated clipboard, waiting for async copy.
            await page.waitForFunction(async intended => {
              const text = await navigator.clipboard.readText();
              return text !== intended && text.length <= 65536;
            }, intendedText, {timeout: 5000});
            payload = await clipboard(page, 'read');
            assert.ok(payload.length <= 65536);
            const copied = JSON.parse(payload);
            assert.equal(copied.type, 'excalidraw/clipboard');
            assert.deepEqual(copied.elements.map(element => element.id), seedIds.slice(0, 2));
            assertGroup(copied.elements, new Set());
            assert.equal(copied.elements[0].groupIds[0], seedGroup);
            await frame(page);
            const donorEvidence = await page.evaluate(() => ({before: window.donorBefore,
              after: structuredClone(window.editor.getSceneElementsIncludingDeleted()),
              callbacks: window.donorCallbacks, copies: window.donorCopies, overflow: window.donorOverflow}));
            assert.equal(donorEvidence.overflow, false);
            assert.deepEqual(donorEvidence.copies, [{trusted: true}], 'ordinary keyboard must deliver copy');
            for (const scene of [donorEvidence.after, ...donorEvidence.callbacks]) {
              assert.deepEqual(scene, donorEvidence.before, 'donor copy must preserve every original field and tombstone');
            }
            donor = {selection, elements: copied.elements, ...donorEvidence};
            await page.close();
            page = await context.newPage();
            page.fixtureOrigin = origin;
            await seed(page);
          } else {
            assert.equal(await clipboard(page, 'read'), intendedText);
          }
          await page.evaluate(readonly => window.setReadonly(readonly), readonly);
          await page.waitForFunction(readonly => window.editor.getAppState().viewModeEnabled === readonly, readonly);
          await page.locator('.excalidraw').click({position: {x: 1000, y: 600}});
          await page.mouse.move(900, 500);
          await frame(page);
          await page.evaluate(() => {
            window.clipboardSnapshot = (elements = window.editor.getSceneElementsIncludingDeleted()) => {
              const state = window.editor.getAppState();
              const active = document.activeElement;
              return {elements: structuredClone(elements),
                selectedIds: Object.keys(state.selectedElementIds).filter(id => state.selectedElementIds[id]),
                selectedGroupIds: Object.keys(state.selectedGroupIds).filter(id => state.selectedGroupIds[id]),
                activeTool: state.activeTool.type, viewMode: state.viewModeEnabled,
                textEditor: !!document.querySelector('textarea.excalidraw-wysiwyg'),
                focus: {tag: active?.tagName ?? null, inCanvas: !!active?.closest('.excalidraw')},
              };
            };
            window.clipboardPhase = 'before';
            window.clipboardCallbacks = [];
            window.clipboardEvents = [];
            window.clipboardOverflow = false;
            window.observeFixtureChange = elements => {
              if (window.clipboardCallbacks.length >= 200) { window.clipboardOverflow = true; return; }
              window.clipboardCallbacks.push({phase: window.clipboardPhase, ...window.clipboardSnapshot(elements)});
            };
            // Passive observation only: no dispatch, preventDefault, setData or API insertion.
            document.addEventListener('paste', event => {
              if (window.clipboardEvents.length >= 8) { window.clipboardOverflow = true; return; }
              const text = event.clipboardData?.getData('text/plain') ?? '';
              if (text.length > 65536) { window.clipboardOverflow = true; return; }
              window.clipboardEvents.push({phase: window.clipboardPhase, trusted: event.isTrusted,
                types: Array.from(event.clipboardData?.types ?? []), text, ...window.clipboardSnapshot()});
            }, {capture: true, passive: true});
          });
          const before = await snapshot(page);
          assert.deepEqual(before.elements.map(({id, isDeleted}) => ({id, isDeleted})),
            seedIds.map((id, index) => ({id, isDeleted: index === 2})));
          assert.equal(before.textEditor, false);
          assert.equal(before.focus.inCanvas, true);
          const checkpoints = [];
          const pasteSets = [];
          const groups = new Set([seedGroup]);
          for (const iteration of [1, 2]) {
            await page.evaluate(iteration => { window.clipboardPhase = `paste-${iteration}`; }, iteration);
            await page.keyboard.press('Control+v');
            await page.waitForFunction(count => window.clipboardEvents.length === count, iteration, {timeout: 5000});
            if (!readonly) {
              const expected = iteration * (scenario === 'plain-text' ? 1 : 2);
              await page.waitForFunction(({seedIds, expected}) =>
                window.editor.getSceneElementsIncludingDeleted().filter(element => !seedIds.includes(element.id)).length === expected,
              {seedIds, expected}, {timeout: 5000});
            }
            await frame(page);
            const pasted = await snapshot(page);
            const previousIds = pasteSets.flat().map(element => element.id);
            const fresh = extras(pasted).filter(element => !previousIds.includes(element.id));
            if (!readonly) {
              assert.equal(fresh.length, scenario === 'plain-text' ? 1 : 2);
              for (const element of fresh) {
                assert.equal(typeof element.id, 'string');
                assert.ok(element.id.length > 0 && ![...seedIds, ...previousIds].includes(element.id));
                assert.equal(element.isDeleted, false);
              }
              if (scenario === 'plain-text') {
                assert.equal(fresh[0].type, 'text');
                assert.equal(fresh[0].text, intendedText);
                assert.equal(fresh[0].originalText, intendedText);
                assert.equal(fresh[0].containerId, null);
              } else {
                groups.add(assertGroup(fresh, groups));
              }
              pasteSets.push(fresh);
            }
            checkpoints.push({phase: `paste-${iteration}`, ...pasted});
          }
          await page.evaluate(() => { window.clipboardPhase = 'settled'; });
          await frame(page);
          const settled = await snapshot(page);
          assert.deepEqual(settled.elements, checkpoints[1].elements);
          const evidence = await page.evaluate(() => ({callbacks: window.clipboardCallbacks,
            events: window.clipboardEvents, overflow: window.clipboardOverflow}));
          assert.equal(evidence.overflow, false, 'bounded evidence must not be truncated');
          assert.equal(evidence.events.length, 2);
          for (const event of evidence.events) {
            assert.equal(event.trusted, true, 'browser must deliver ordinary keyboard paste');
            assert.equal(event.text, payload, 'actual delivered clipboard content must match the synthetic source');
            assert.ok(event.types.includes('text/plain'));
          }
          for (const observation of [...checkpoints, settled, ...evidence.callbacks, ...evidence.events]) {
            assertSeeds(observation, before);
            if (readonly) assert.deepEqual(observation.elements, before.elements, 'viewer full scene must remain exact');
            else {
              const allowed = pasteSets.flat().map(element => element.id);
              assert.ok(extras(observation).every(element => allowed.includes(element.id)));
              for (const pastedSet of pasteSets) {
                const present = observation.elements.filter(element => pastedSet.some(pasted => pasted.id === element.id));
                if (!present.length) continue;
                assert.equal(present.length, pastedSet.length, 'callback must contain each complete paste set');
                if (scenario === 'copied-bound-group') assertGroup(present,
                  new Set([seedGroup, ...pasteSets.filter(other => other !== pastedSet).map(other => other[0].groupIds[0])]));
                else {
                  assert.equal(present[0].type, 'text');
                  assert.equal(present[0].text, intendedText);
                  assert.equal(present[0].originalText, intendedText);
                  assert.equal(present[0].isDeleted, false);
                }
              }
              // Every completed paste must remain exact throughout the next paste.
              if (observation.phase === 'paste-2') assert.deepEqual(
                observation.elements.filter(element => pasteSets[0].some(prior => prior.id === element.id)), pasteSets[0]);
            }
          }
          if (!readonly) for (const checkpoint of checkpoints) assert.ok(evidence.callbacks.some(entry =>
            entry.phase === checkpoint.phase && isDeepStrictEqual(entry.elements, checkpoint.elements)),
          'each writable result must occur in a complete real onChange callback');
          trials.push({scenario, mode: readonly ? 'viewer' : 'writable', donor, before, checkpoints, settled,
            pasteSets, sceneUnchanged: isDeepStrictEqual(before.elements, settled.elements), ...evidence});
        } catch (error) {
          const evidence = await page?.evaluate(() => ({scene: window.clipboardSnapshot?.() ?? null,
            callbacks: window.clipboardCallbacks ?? [], events: window.clipboardEvents ?? [],
            overflow: window.clipboardOverflow ?? false})).catch(() => null);
          console.error(JSON.stringify({clipboardFailure: {scenario, readonly, message: error.message, evidence}}));
          throw error;
        } finally { await context.close(); }
      }
    }
    assert.deepEqual(blockedRequests, []);
    assert.deepEqual(pageErrors, []);
    return {result: 'synthetic-clipboard-passed', browser: browser.version(), viewport,
      isolation: 'Linux managed Chromium, Ozone headless non-backed clipboard, display env removed, synthetic prime before reads',
      trials, blockedRequests, pageErrors};
  } finally { await browser.close(); }
}
