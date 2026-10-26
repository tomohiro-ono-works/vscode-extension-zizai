'use strict';
const path = require('node:path');
const KEY = 'task00201Diagnostic'; // Probe only; never a product schema.
function identities() {
  const map = new WeakMap();
  let next = 0;
  return object => { if (!map.has(object)) map.set(object, ++next); return map.get(object); };
}
function patchMetadata(metadata, patch) {
  return { ...metadata, metadata: { ...metadata.metadata, [KEY]: { ...metadata.metadata?.[KEY], ...patch } } };
}
function encode(value) { return JSON.stringify(value, (_key, item) => item === undefined ? { $undefined: true } : item); }
function validTarget(notebook, cell, open) {
  return !notebook.isClosed && open.includes(notebook) && notebook.getCells().includes(cell);
}
function within(root, file) {
  const relative = path.relative(path.resolve(root), path.resolve(file));
  return relative !== '' && !relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative);
}
module.exports = { KEY, identities, patchMetadata, encode, validTarget, within };
