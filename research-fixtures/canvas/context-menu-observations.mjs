// Offline validation of finite synthetic observations; no browser or network code.
import assert from 'node:assert/strict';
import {isDeepStrictEqual} from 'node:util';

const seedIds = ['menu-rectangle', 'menu-text', 'menu-tombstone'];
const actions = {delete: 'deleteSelectedElements', duplicate: 'duplicateSelection'};
const without = (element, keys) => Object.fromEntries(Object.entries(element).filter(([key]) => !keys.includes(key)));

// Extracted from preserved #607 head 779384fbfde4e5c46be6eb88f1f557bc862a5daa.
// A future separately reviewed collector should consume this canonical validator.
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
    assert.equal(cleanup.method, 'outside-click', 'cleanup must identify its separate outside-click method');
    assert.equal(cleanup.after.menu, null, 'separate cleanup must close the menu');
    assert.deepEqual(cleanup.after.elements, settled.elements, 'cleanup must preserve the settled scene');
  }
  if (scenario === 'dismiss-wheel') {
    assert.deepEqual(opened.selectedIds, []);
    assert.notDeepEqual(settled.viewport, finished.viewport, 'wheel must navigate after Escape');
    assert.equal(settled.viewport.zoom, finished.viewport.zoom, 'ordinary wheel must pan without zoom');
    assert.ok(inputs.some(input => input.type === 'wheel' && input.trusted), 'wheel navigation must retain trusted input');
  }
  if (readonly || scenario === 'dismiss-wheel') {
    assert.ok(inputs.some(input => input.type === 'keydown' && input.key === 'Escape' && input.trusted),
      'Escape dismissal must retain trusted input');
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
      assert.ok(deleted.version > before.elements[0].version, 'Delete must increase the target version');
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
      assert.deepEqual(finished.selectedIds, [copy.id], 'Duplicate must select its new copy');
    }
  }
  for (const entry of [before, opened, escaped, finished, settled, cleanup?.after, ...callbacks].filter(Boolean)) {
    assert.equal(entry.viewMode, readonly, 'every checkpoint and callback must retain the trial view mode');
    assert.equal(new Set(entry.elements.map(element => element.id)).size, entry.elements.length,
      'every checkpoint and callback must have unique element IDs');
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
