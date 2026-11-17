// A bounded experiment for synthetic rectangles, with tombstones in scene order.
// The tuple is a test projection. It is not a canonical schema or intent proof.
function project(elements) {
  return JSON.stringify(elements.map(({id, type, x, y, width, height, isDeleted}) =>
    [id, type, x, y, width, height, isDeleted]));
}

export function createHydrationObserver(initialElements) {
  let accepted = project(initialElements);
  let observed = accepted;
  return {
    accept(elements) {
      accepted = project(elements);
    },
    observe(elements) {
      const next = project(elements);
      const isCandidate = next !== accepted && next !== observed;
      observed = next;
      return isCandidate;
    },
  };
}
