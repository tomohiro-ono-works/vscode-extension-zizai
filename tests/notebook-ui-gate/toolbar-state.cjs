// Fixture-only selection state; not the product's shared contract.
const { readRole } = require('./role.cjs');
function createState() {
  let cells = new Map();
  const selected = new Map();
  const key = cell => cell?.document?.uri?.toString();
  return {
    refresh(notebooks) {
      const next = new Map();
      for (const notebook of notebooks) {
        const items = notebook.getCells();
        if (notebook.notebookType !== 'jupyter-notebook' || !items.some(cell => readRole(cell.metadata))) continue;
        for (const cell of items) {
          if (cell.kind !== 2 || cell.document.languageId !== 'python' || readRole(cell.metadata) === 'init') continue;
          const uri = key(cell);
          next.set(uri, cell);
          if (!selected.has(uri)) selected.set(uri, readRole(cell.metadata) === 'action' ? 'fake' : 'python');
        }
      }
      cells = next;
      for (const uri of selected.keys()) if (!cells.has(uri)) selected.delete(uri);
      return [...cells.keys()];
    },
    selection(cell) {
      const uri = key(cell);
      return cells.get(uri) === cell ? selected.get(uri) : undefined;
    },
    select(cell, choice) {
      const uri = key(cell);
      if (!cell || cells.get(uri) !== cell || !['python', 'fake'].includes(choice)) return false;
      selected.set(uri, choice);
      return true;
    }
  };
}
module.exports = { createState };
