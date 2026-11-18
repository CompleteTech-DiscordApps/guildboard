import assert from 'node:assert/strict';

// Synthetic one-pixel GIF. The scene element carries only a file ID.
const asset = {
  id: 'fixture-image-file',
  mimeType: 'image/gif',
  dataURL: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',
  created: 1,
};

export async function probeAsset(page, frame) {
  await page.evaluate(fileId => {
    window.editor.updateScene({
      elements: window.makeElements([
        {id: 'fixture-image', type: 'image', fileId, x: 100, y: 100, width: 32, height: 32, status: 'saved'},
      ]),
      captureUpdate: window.capture.NEVER,
    });
  }, asset.id);
  await frame();

  const readAsset = () => page.evaluate(fileId => ({
    references: window.editor.getSceneElements().map(element => element.fileId),
    file: window.editor.getFiles()[fileId],
  }), asset.id);
  assert.deepEqual(await readAsset(), {references: [asset.id], file: undefined});

  const serializeAndLoad = type => page.evaluate(async ({fileId, type}) => {
    const {loadFromBlob, serializeAsJSON} = window.assetSerialization;
    const {editor} = window;
    const serialized = serializeAsJSON(editor.getSceneElements(), editor.getAppState(), editor.getFiles(), type);
    const parsed = JSON.parse(serialized);
    // Load with empty local state so the live editor's files cannot supply bytes.
    const restored = await loadFromBlob(new Blob([serialized], {type: 'application/json'}), null, null);
    return {
      serializedReferences: parsed.elements.map(element => element.fileId),
      serializedFile: parsed.files?.[fileId],
      restoredReferences: restored.elements.map(element => element.fileId),
      restoredFile: restored.files?.[fileId],
    };
  }, {fileId: asset.id, type});
  const referenceOnly = {
    serializedReferences: [asset.id], serializedFile: undefined,
    restoredReferences: [asset.id], restoredFile: undefined,
  };
  assert.deepEqual(await serializeAndLoad('local'), referenceOnly);

  await page.evaluate(file => window.editor.addFiles([file]), asset);
  await frame();
  const imported = await readAsset();
  assert.deepEqual(imported.references, [asset.id]);
  assert.ok(imported.file);
  for (const field of Object.keys(asset)) {
    assert.equal(imported.file[field], asset[field]);
  }
  const local = await serializeAndLoad('local');
  assert.deepEqual(local, {
    ...referenceOnly,
    serializedFile: imported.file,
    restoredFile: imported.file,
  });
  assert.deepEqual(await serializeAndLoad('database'), referenceOnly);
  return {
    missingReferenceDidNotCreateFile: true,
    addFilesRoundTrip: true,
    localRoundTripPreservedRegisteredFileIdAndBytes: true,
    localRoundTripWithoutRegistrationPreservedReferenceOnly: true,
    databaseRoundTripWithRegistrationPreservedReferenceOnly: true,
  };
}
