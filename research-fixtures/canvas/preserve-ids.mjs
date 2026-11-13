/** Keep fixture-owned IDs: the pinned converter otherwise regenerates them. */
export function preserveElementIds(convert, elements) {
  return convert(elements, { regenerateIds: false });
}
