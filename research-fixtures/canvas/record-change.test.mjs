import assert from 'node:assert/strict';
import test from 'node:test';
import {recordSceneChange} from './record-change.mjs';

test('named recorder retains the event shape and snapshots only the existing fields', () => {
  const events = [];
  const element = {id: 'fixture', type: 'rectangle', x: 1, y: 2, width: 3, height: 4,
    version: 5, isDeleted: false, text: 'not captured'};
  recordSceneChange(events, [element], {viewModeEnabled: true}, {fileA: {dataURL: 'not captured'}});
  assert.deepEqual(events, [{elements: [{id: 'fixture', type: 'rectangle', x: 1, y: 2,
    width: 3, height: 4, version: 5, isDeleted: false}], viewMode: true, files: ['fileA']}]);
  element.x = 99;
  assert.equal(events[0].elements[0].x, 1);
});

test('named recorder stops at 200 and does not inspect another event at capacity', () => {
  const events = [];
  for (let index = 0; index < 201; index++) {
    recordSceneChange(events, [], {viewModeEnabled: false}, {});
  }
  assert.equal(events.length, 200);
  const hostile = new Proxy({}, {get() { throw Error('recording past capacity'); }});
  assert.doesNotThrow(() => recordSceneChange(events, hostile, hostile, hostile));
  assert.equal(events.length, 200);
});
