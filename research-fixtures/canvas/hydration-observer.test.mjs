import assert from 'node:assert/strict';
import test from 'node:test';
import {createHydrationObserver} from './hydration-observer.js';

const rectangle = {id: 'rect', type: 'rectangle', x: 50, y: 50, width: 20, height: 20, isDeleted: false};
const tombstone = {...rectangle, id: 'deleted', isDeleted: true};

test('repeated accepted snapshots and duplicate callbacks produce no candidate', () => {
  const observer = createHydrationObserver([]);
  observer.accept([rectangle, tombstone]);
  assert.equal(observer.observe([rectangle, tombstone]), false);
  observer.accept([{...rectangle}, {...tombstone}]);
  assert.equal(observer.observe([rectangle, tombstone]), false);
  assert.equal(observer.observe([rectangle, tombstone]), false);
});

test('missing or revived tombstones differ from the accepted projection', () => {
  const observer = createHydrationObserver([rectangle, tombstone]);
  assert.equal(observer.observe([rectangle]), true);
  assert.equal(observer.observe([rectangle]), false);
  assert.equal(observer.observe([rectangle, {...tombstone, isDeleted: false}]), true);
  assert.equal(observer.observe([rectangle, tombstone]), false);
});

test('a delayed older observation is indistinguishable from a scene edit', () => {
  const observer = createHydrationObserver([rectangle]);
  const moved = {...rectangle, x: 75};
  observer.accept([moved]);
  assert.equal(observer.observe([moved]), false);
  assert.equal(observer.observe([rectangle]), true);
});
