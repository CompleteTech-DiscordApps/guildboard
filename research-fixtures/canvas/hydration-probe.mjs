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

  const steps = [];
  for (const [name, x] of [['initial', 200], ['replayed', 200], ['changed', 250]]) {
    const before = await page.evaluate(() => ({...window.hydrationCounts}));
    await page.evaluate(x => window.hydrateFixture(x), x);
    await frame();
    const after = await page.evaluate(() => ({
      ...window.hydrationCounts,
      elements: window.editor.getSceneElementsIncludingDeleted().map(({id, x, y, width, height, isDeleted}) =>
        ({id, x, y, width, height, isDeleted})),
    }));
    assert.deepEqual(after.elements, [
      {id: 'accepted-rectangle', x, y: 210, width: 50, height: 50, isDeleted: false},
      {id: 'accepted-tombstone', x: 100, y: 210, width: 50, height: 50, isDeleted: true},
    ]);
    assert.equal(after.candidates, 0, name);
    if (name !== 'replayed') assert.ok(after.callbacks > before.callbacks, name);
    steps.push({name, callbacks: after.callbacks - before.callbacks, candidates: after.candidates});
  }

  // A real pointer gesture exercises the callback path as a positive control.
  const beforePointer = await page.evaluate(() => window.hydrationCounts.callbacks);
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
  const pointer = await page.evaluate(() => ({...window.hydrationCounts}));
  return {
    steps,
    pointer: {callbacks: pointer.callbacks - beforePointer,
      candidates: pointer.candidates},
  };
}
