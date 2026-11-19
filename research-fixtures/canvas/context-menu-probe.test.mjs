// Offline assertion regressions. These fabricated observations are not browser evidence.
import assert from 'node:assert/strict';
import test from 'node:test';
import {assertContextMenuTrial} from './context-menu-probe.mjs';

function observation(readonly, elements) {
  return {elements: structuredClone(elements), selectedIds: [], menu: null, viewMode: readonly,
    activeTool: 'selection', viewport: {scrollX: 0, scrollY: 0, zoom: 1},
    focus: {tag: 'DIV', role: null, label: null, menuAction: null, inCanvas: true}};
}
function fixture(scenario = 'delete', readonly = false) {
  const elements = [
    {id: 'menu-rectangle', type: 'rectangle', isDeleted: false, version: 1, x: 400, y: 280, width: 120, height: 100},
    {id: 'menu-text', type: 'text', isDeleted: false, version: 1, text: 'Synthetic menu text'},
    {id: 'menu-tombstone', type: 'rectangle', isDeleted: true, version: 1, x: 200},
  ];
  const before = observation(readonly, elements);
  const opened = observation(readonly, elements);
  opened.menu = [{action: 'toggleStats', label: 'Stats', disabled: false, visible: true}];
  const finished = observation(readonly, elements);
  const inputs = [{type: 'contextmenu', trusted: true}];
  if (!readonly && scenario !== 'dismiss-wheel') {
    const action = scenario === 'delete' ? 'deleteSelectedElements' : 'duplicateSelection';
    opened.menu.push({action, label: scenario, disabled: false, visible: true});
    opened.selectedIds = ['menu-rectangle'];
    inputs.push({type: 'click', action, trusted: true});
    if (scenario === 'delete') {
      finished.elements[0] = {...finished.elements[0], isDeleted: true, version: 2};
    } else {
      finished.elements.splice(1, 0, {...elements[0], id: 'new-copy', x: 410, y: 290});
      finished.selectedIds = ['new-copy'];
    }
  } else {
    inputs.push({type: 'keydown', key: 'Escape', trusted: true});
  }
  const settled = structuredClone(finished);
  if (scenario === 'dismiss-wheel') {
    settled.viewport.scrollY = -120;
    inputs.push({type: 'wheel', trusted: true});
  }
  return {scenario, readonly, before, opened, finished, settled, inputs, inputOverflow: false,
    callbacks: [structuredClone(opened), structuredClone(finished)], overflow: false};
}

for (const scenario of ['delete', 'duplicate', 'dismiss-wheel']) for (const readonly of [false, true]) {
  test(`accepts a complete synthetic ${scenario} ${readonly ? 'viewer' : 'writable'} observation`, () => {
    assert.doesNotThrow(() => assertContextMenuTrial(fixture(scenario, readonly)));
  });
}

const corruptions = [
  ['viewer transient element change', 'delete', true, trial => { trial.callbacks[0].elements[1].text = 'changed'; }],
  ['viewer transient tombstone loss', 'duplicate', true, trial => { trial.callbacks[0].elements.pop(); }],
  ['viewer edit affordance', 'delete', true, trial => { trial.opened.menu.push({action: 'deleteSelectedElements', label: 'Delete', visible: true}); }],
  ['delete failed positive control', 'delete', false, trial => {
    trial.finished.elements = structuredClone(trial.before.elements); trial.settled = structuredClone(trial.finished);
  }],
  ['delete unrelated callback mutation', 'delete', false, trial => { trial.callbacks[0].elements[1].text = 'changed'; }],
  ['duplicate original mutation', 'duplicate', false, trial => { trial.finished.elements[0].width = 1; trial.settled = structuredClone(trial.finished); }],
  ['duplicate transient extra element', 'duplicate', false, trial => { trial.callbacks[0].elements.push({id: 'unexpected', isDeleted: false}); }],
  ['missing completed callback', 'duplicate', false, trial => { trial.callbacks = [structuredClone(trial.opened)]; }],
  ['untrusted context event', 'delete', false, trial => { trial.inputs[0].trusted = false; }],
  ['missing visible activation', 'delete', false, trial => { trial.inputs.pop(); }],
  ['callback overflow', 'delete', false, trial => { trial.overflow = true; }],
  ['input overflow', 'delete', false, trial => { trial.inputOverflow = true; }],
  ['wheel without navigation', 'dismiss-wheel', true, trial => { trial.settled.viewport = structuredClone(trial.finished.viewport); }],
  ['menu left open', 'dismiss-wheel', true, trial => { trial.finished.menu = structuredClone(trial.opened.menu); }],
];
for (const [name, scenario, readonly, corrupt] of corruptions) {
  test(`rejects ${name}`, () => {
    const trial = fixture(scenario, readonly);
    corrupt(trial);
    assert.throws(() => assertContextMenuTrial(trial), {name: 'AssertionError'});
  });
}
