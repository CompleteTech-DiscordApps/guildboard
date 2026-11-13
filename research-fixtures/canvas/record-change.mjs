/** Preserve the fixture's original event shape and fixed 200-entry bound. */
export function recordSceneChange(events, elements, state, files) {
  if (events.length >= 200) return;
  events.push({
    elements: elements.map(({id, type, x, y, width, height, version, isDeleted}) => ({
      id, type, x, y, width, height, version, isDeleted,
    })),
    viewMode: state.viewModeEnabled,
    files: Object.keys(files),
  });
}
