import assert from 'node:assert/strict';

export async function probeHydration(page, frame) {
  await page.evaluate(async () => {
    const {createHydrationObserver} = await import('/hydration-observer.js');
    const observer = createHydrationObserver(window.editor.getSceneElementsIncludingDeleted());
    window.hydrationCounts = {callbacks: 0, candidates: 0};
    window.observeFixtureChange = elements => {
      window.hydrationCounts.callbacks++;
      if (observer.observe(elements)) window.hydrationCounts.candidates++;
    };
    window.hydrateFixture = x => {
      const elements = window.makeElements([
        {id: 'accepted-rectangle', type: 'rectangle', x, y: 210, width: 50, height: 50},
        {id: 'accepted-tombstone', type: 'rectangle', x: 100, y: 210, width: 50, height: 50},
      ]);
      const [live, deleted] = elements;
      const snapshot = [live, {...deleted, isDeleted: true}];
      observer.accept(snapshot);
      window.editor.updateScene({elements: snapshot, captureUpdate: window.capture.NEVER});
    };
  });

  const readScene = () => page.evaluate(() => ({
    ...window.hydrationCounts,
    elements: window.editor.getSceneElementsIncludingDeleted().map(
      ({id, x, y, width, height, isDeleted}) => ({id, x, y, width, height, isDeleted}),
    ),
  }));
  const changedX = 250;
  const steps = [];
  for (const [name, x] of [['initial', 200], ['replayed', 200], ['changed', changedX]]) {
    const before = await page.evaluate(() => ({...window.hydrationCounts}));
    await page.evaluate(x => window.hydrateFixture(x), x);
    await frame();
    const after = await readScene();
    assert.deepEqual(after.elements, [
      {id: 'accepted-rectangle', x, y: 210, width: 50, height: 50, isDeleted: false},
      {id: 'accepted-tombstone', x: 100, y: 210, width: 50, height: 50, isDeleted: true},
    ]);
    assert.equal(after.candidates, 0, name);
    if (name !== 'replayed') assert.ok(after.callbacks > before.callbacks, name);
    steps.push({name, callbacks: after.callbacks - before.callbacks, candidates: after.candidates});
  }

  // Clear earlier smoke-test history before capturing the rejected pointer edit.
  await page.evaluate(() => window.editor.history.clear());
  const accepted = await readScene();
  await page.keyboard.press('r');
  await page.waitForFunction(() => window.editor.getAppState().activeTool.type === 'rectangle');
  await page.mouse.move(800, 530);
  await page.mouse.down();
  await page.mouse.move(900, 620, {steps: 5});
  await page.mouse.up();
  await page.waitForFunction(() =>
    window.editor.getSceneElements().filter(element => element.type === 'rectangle').length === 2
    && window.hydrationCounts.candidates > 0);
  await frame();
  const pointer = await readScene();
  const acceptedIds = new Set(accepted.elements.map(element => element.id));
  const optimistic = pointer.elements.find(element => !acceptedIds.has(element.id));
  assert.ok(optimistic && !optimistic.isDeleted, 'the rejected element must first exist');

  // The rejection is injected by the fixture; the editor update and callbacks are real.
  await page.evaluate(x => window.hydrateFixture(x), changedX);
  await frame();
  const restored = await readScene();
  assert.deepEqual(restored.elements, accepted.elements);
  assert.ok(restored.callbacks > pointer.callbacks, 'rollback must exercise onChange');
  assert.equal(restored.candidates, pointer.candidates, 'rollback must yield no new candidate');

  await page.keyboard.press('Control+z');
  await frame();
  const undone = await readScene();
  await page.keyboard.press('Control+Shift+z');
  await frame();
  const redone = await readScene();

  // Failure control: native history still acts on the rejected edit after NEVER hydration.
  const undoTombstone = undone.elements.find(element => element.id === optimistic.id);
  const redoElement = redone.elements.find(element => element.id === optimistic.id);
  assert.equal(undoTombstone?.isDeleted, true, 'native undo introduces the rejected ID as a tombstone');
  assert.equal(redoElement?.isDeleted, false, 'native redo resurrects the rejected ID');
  assert.ok(undone.candidates > restored.candidates, 'undo must produce a candidate');
  assert.ok(redone.candidates > undone.candidates, 'redo must produce a candidate');

  return {
    steps,
    pointer: {callbacks: pointer.callbacks - accepted.callbacks,
      candidates: pointer.candidates - accepted.candidates},
    rollback: {
      callbacks: restored.callbacks - pointer.callbacks,
      candidates: restored.candidates - pointer.candidates,
      undo: {
        optimisticElementTombstoned: undoTombstone.isDeleted,
        callbacks: undone.callbacks - restored.callbacks,
        candidates: undone.candidates - restored.candidates,
      },
      redo: {
        optimisticElementLive: !redoElement.isDeleted,
        callbacks: redone.callbacks - undone.callbacks,
        candidates: redone.candidates - undone.candidates,
      },
    },
  };
}
