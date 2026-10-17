/** Parse one source ID per line without treating identifier punctuation as separators. */
export function parseSourceIds(text) {
  if (typeof text !== 'string') throw new TypeError('Source document IDs must be text.')
  return text.split(/\r\n|\r|\n/).map(value => value.trim()).filter(Boolean)
}
