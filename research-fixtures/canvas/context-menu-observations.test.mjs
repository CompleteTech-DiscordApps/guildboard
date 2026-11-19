// Offline assertion regressions. These fabricated observations are not browser evidence.
import assert from 'node:assert/strict';
import test from 'node:test';
import {assertContextMenuTrial, assertContextMenuAcceptance} from './context-menu-observations.mjs';

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
  return {scenario, readonly, before, opened,
    escaped: readonly || scenario === 'dismiss-wheel' ? structuredClone(finished) : null,
    escapeDismissed: readonly || scenario === 'dismiss-wheel' ? true : null,
    escapeDismissalTimedOut: readonly || scenario === 'dismiss-wheel' ? false : null,
    finished, settled, inputs, inputOverflow: false,
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
  ['menu left open', 'dismiss-wheel', true, trial => {
    for (const entry of [trial.escaped, trial.finished, trial.settled]) entry.menu = structuredClone(trial.opened.menu);
    trial.escapeDismissed = false;
  }, /required menu dismissal remains unmet/],
];
for (const [name, scenario, readonly, corrupt, message] of corruptions) {
  test(`rejects ${name}`, () => {
    const trial = fixture(scenario, readonly);
    corrupt(trial);
    assert.throws(() => assertContextMenuTrial(trial), {name: 'AssertionError', ...(message ? {message} : {})});
  });
}


const completeTrials = () => ['delete', 'duplicate', 'dismiss-wheel']
  .flatMap(scenario => [fixture(scenario), fixture(scenario, true)]);

function failedEscape(scenario = 'delete') {
  const trial = fixture(scenario, true);
  trial.escaped.menu = structuredClone(trial.opened.menu);
  trial.finished.menu = structuredClone(trial.opened.menu);
  trial.settled.menu = structuredClone(trial.opened.menu);
  trial.escapeDismissed = false;
  trial.escapeDismissalTimedOut = true;
  trial.cleanup = {method: 'outside-click', after: structuredClone(trial.settled)};
  trial.cleanup.after.menu = null;
  return trial;
}

test('deferral retains both original close failures and outside-click cannot satisfy them', () => {
  const trial = failedEscape();
  const failures = assertContextMenuTrial(trial, {deferMenuClosure: true});
  assert.deepEqual(failures, [
    ...['finished', 'settled'].map(checkpoint => ({
      scenario: 'delete', readonly: true, checkpoint, control: 'Escape must dismiss menu',
    })),
    {scenario: 'delete', readonly: true, checkpoint: 'escape-wait', control: 'Escape must dismiss menu within 10000ms'},
  ]);
  assert.throws(() => assertContextMenuTrial(trial), {name: 'AssertionError'});
});

test('aggregate rejects an earlier Escape failure even after later successful independent trials', () => {
  const first = failedEscape();
  first.failedControls = []; // Never trust a mutable diagnostic summary.
  const trials = completeTrials();
  trials[1] = first;
  assert.doesNotThrow(() => assertContextMenuTrial(trials[2]));
  assert.throws(() => assertContextMenuAcceptance(trials), {name: 'AssertionError'});
});

test('aggregate retains blank-menu Escape failure despite successful wheel and cleanup', () => {
  const trial = failedEscape('dismiss-wheel');
  assert.notDeepEqual(trial.settled.viewport, trial.finished.viewport);
  const trials = completeTrials();
  trials[5] = trial;
  assert.throws(() => assertContextMenuAcceptance(trials), {name: 'AssertionError'});
});

test('aggregate passes only complete successful observations', () => {
  assert.doesNotThrow(() => assertContextMenuAcceptance(completeTrials()));
});

for (const [name, corrupt] of [
  ['missing escaped checkpoint', trial => { trial.escaped = null; }],
  ['changed escaped scene', trial => { trial.escaped.elements[1].text = 'changed'; }],
  ['falsely reported Escape success', trial => { trial.escapeDismissed = true; }],
  ['cleanup replacing finished checkpoint', trial => { trial.finished = structuredClone(trial.cleanup.after); }],
]) test(`deferral still rejects ${name}`, () => {
  const trial = failedEscape();
  corrupt(trial);
  assert.throws(() => assertContextMenuTrial(trial, {deferMenuClosure: true}), {name: 'AssertionError'});
});


for (const [name, make] of [
  ['empty evidence', () => []],
  ['missing trial', () => completeTrials().slice(0, 5)],
  ['duplicate identity', () => { const trials = completeTrials(); trials[5] = structuredClone(trials[0]); return trials; }],
  ['wrong mode type', () => { const trials = completeTrials(); trials[0].readonly = 'false'; return trials; }],
  ['unknown scenario', () => { const trials = completeTrials(); trials[0].scenario = 'unknown'; return trials; }],
  ['non-array evidence', () => ({})],
  ['null trial', () => { const trials = completeTrials(); trials[0] = null; return trials; }],
]) test(`aggregate rejects ${name}`, () => {
  assert.throws(() => assertContextMenuAcceptance(make()), {name: 'AssertionError'});
});

// Keep correlated final observations consistent, so each negative reaches its
// intended assertion rather than failing on an unrelated stability comparison.
function changeCompleted(trial, change) {
  change(trial.finished);
  trial.settled = structuredClone(trial.finished);
  trial.callbacks = [structuredClone(trial.opened), structuredClone(trial.finished)];
}

const targetedCorruptions = [
  ['cleanup wrong method', () => failedEscape(), trial => { trial.cleanup.method = 'Escape'; },
    /cleanup must identify its separate outside-click method/],
  ['cleanup open menu', () => failedEscape(), trial => { trial.cleanup.after.menu = structuredClone(trial.opened.menu); },
    /separate cleanup must close the menu/],
  ['cleanup changed scene', () => failedEscape(), trial => { trial.cleanup.after.elements[1].text = 'changed'; },
    /cleanup must preserve the settled scene/],
  ...['missing', 'untrusted'].map(kind => [
    `${kind} Escape input`, () => fixture('delete', true), trial => {
      trial.inputs = trial.inputs.filter(input => input.type !== 'keydown');
      if (kind === 'untrusted') trial.inputs.push({type: 'keydown', key: 'Escape', trusted: false});
    }, /Escape dismissal must retain trusted input/,
  ]),
  ...['missing', 'untrusted'].map(kind => [
    `${kind} wheel input`, () => fixture('dismiss-wheel', true), trial => {
      trial.inputs = trial.inputs.filter(input => input.type !== 'wheel');
      if (kind === 'untrusted') trial.inputs.push({type: 'wheel', trusted: false});
    }, /wheel navigation must retain trusted input/,
  ]),
  ['wheel zoom change', () => fixture('dismiss-wheel', true), trial => { trial.settled.viewport.zoom = 2; },
    /ordinary wheel must pan without zoom/],
  ['wrong checkpoint view mode', () => fixture('delete', true), trial => { trial.opened.viewMode = false; },
    /every checkpoint and callback must retain the trial view mode/],
  ['wrong callback view mode', () => fixture('delete'), trial => { trial.callbacks[0].viewMode = true; },
    /every checkpoint and callback must retain the trial view mode/],
  ['duplicate element IDs', () => fixture('delete', true), trial => {
    trial.callbacks[0].elements[0].id = trial.callbacks[0].elements[1].id;
  }, /every checkpoint and callback must have unique element IDs/],
  ['opened scene changed', () => fixture('delete'), trial => { trial.opened.elements[1].text = 'changed'; },
    /opening the menu must preserve every element/],
  ['settled scene unstable', () => fixture('delete'), trial => { trial.settled.elements[1].text = 'changed'; },
    /the completed scene must remain stable/],
  ['duplicate missing offset', () => fixture('duplicate'), trial => changeCompleted(trial, entry => {
    const copy = entry.elements.find(element => element.id === 'new-copy');
    copy.x = trial.before.elements[0].x;
    copy.y = trial.before.elements[0].y;
  }), /copy must be offset/],
  ['duplicate wrong selected copy', () => fixture('duplicate'), trial => changeCompleted(trial, entry => {
    entry.selectedIds = ['menu-rectangle'];
  }), /Duplicate must select its new copy/],
  ['delete without version increase', () => fixture(), trial => changeCompleted(trial, entry => {
    entry.elements[0].version = trial.before.elements[0].version;
  }), /Delete must increase the target version/],
];
for (const [name, make, corrupt, message] of targetedCorruptions) {
  test(`rejects ${name} at its specific invariant`, () => {
    const trial = make();
    corrupt(trial);
    assert.throws(() => assertContextMenuTrial(trial, {deferMenuClosure: true}),
      {name: 'AssertionError', message});
  });
}

const viewerFailures = () => ['delete', 'duplicate', 'dismiss-wheel'].flatMap(scenario => [
  ...['finished', 'settled'].map(checkpoint => ({scenario, readonly: true, checkpoint,
    control: 'Escape must dismiss menu'})),
  {scenario, readonly: true, checkpoint: 'escape-wait', control: 'Escape must dismiss menu within 10000ms'},
]);

test('all three viewer Escape failures retain exactly nine conditions', () => {
  const trials = completeTrials().map(trial => trial.readonly ? failedEscape(trial.scenario) : trial);
  assert.deepEqual(trials.flatMap(trial => assertContextMenuTrial(trial, {deferMenuClosure: true})), viewerFailures());
  assert.throws(() => assertContextMenuAcceptance(trials),
    {name: 'AssertionError', message: /required menu dismissal controls failed; cleanup is not Escape/});
});

for (const ledger of ['missing', 'empty', 'fabricated']) {
  test(`a ${ledger} ledger cannot hide all three viewer Escape failures`, () => {
    const trials = completeTrials().map(trial => trial.readonly ? failedEscape(trial.scenario) : trial);
    for (const trial of trials) {
      if (ledger === 'missing') delete trial.failedControls;
      else trial.failedControls = ledger === 'empty' ? [] : [{control: 'invented success'}];
    }
    assert.throws(() => assertContextMenuAcceptance(trials),
      {name: 'AssertionError', message: /required menu dismissal controls failed; cleanup is not Escape/});
  });
}
