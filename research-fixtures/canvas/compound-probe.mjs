import assert from 'node:assert/strict';

export async function probeCompound(page, frame) {
  const compound = [
    {id: 'compound-box', type: 'rectangle', x: 200, y: 200, width: 120, height: 100},
    {id: 'compound-text', type: 'text', x: 220, y: 220, text: 'Synthetic note'},
  ];
  const ids = compound.map(element => element.id);
  const groupId = 'synthetic-note-group';
  const accepted = await page.evaluate(() => window.editor.getSceneElementsIncludingDeleted());
  await page.evaluate(({compound, ids, groupId}) => {
    window.compoundObservations = [];
    window.observeFixtureChange = elements => {
      window.compoundObservations.push(elements
        .filter(element => ids.includes(element.id))
        .map(({id, groupIds, isDeleted}) => ({id, groupIds, isDeleted})));
    };
    const group = window.makeElements(compound).map(element => ({...element, groupIds: [groupId]}));
    window.editor.updateScene({
      elements: [...window.editor.getSceneElementsIncludingDeleted(), ...group],
      captureUpdate: window.capture.NEVER,
    });
  }, {compound, ids, groupId});
  await frame();
  const staged = await page.evaluate(() => window.compoundObservations.splice(0));
  const expected = ids.map(id => ({id, groupIds: [groupId], isDeleted: false}));
  assert.ok(staged.length > 0, 'staging must exercise the real callback');
  for (const members of staged) assert.deepEqual(members, expected);

  // The fixture injects a denial. One replacement restores the accepted projection.
  await page.evaluate(elements => window.editor.updateScene({elements, captureUpdate: window.capture.NEVER}), accepted);
  await frame();
  const denied = await page.evaluate(() => ({
    scene: window.editor.getSceneElementsIncludingDeleted(),
    observations: window.compoundObservations,
  }));
  assert.deepEqual(denied.scene, accepted);
  assert.ok(denied.observations.length > 0, 'rollback must exercise the real callback');
  for (const members of denied.observations) assert.deepEqual(members, []);
  return {stagedCallbacks: staged.length, deniedCallbacks: denied.observations.length, partialCallbacks: 0};
}
