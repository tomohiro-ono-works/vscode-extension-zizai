// Probe logic only. These tests do not start VS Code or prove toolbar rendering.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createState } = require('./toolbar-state.cjs');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const fixture = JSON.parse(readFileSync(join(__dirname, 'fixtures/empty.ipynb'), 'utf8'));

function notebook(id = 'one', type = 'jupyter-notebook') {
  const cells = fixture.cells.map((item, index) => ({
    index, kind: 2, metadata: { metadata: structuredClone(item.metadata) },
    document: { languageId: 'python', uri: { toString: () => `cell:${id}/${index}` } }
  }));
  return { notebookType: type, getCells: () => cells };
}

test('empty-output fixture exposes ordinary/action cells and hides init', () => {
  const state = createState();
  const nb = notebook();
  assert.deepEqual(state.refresh([nb]), ['cell:one/1', 'cell:one/2']);
  assert.equal(state.selection(nb.getCells()[0]), undefined);
  assert.equal(state.selection(nb.getCells()[1]), 'python');
  assert.equal(state.selection(nb.getCells()[2]), 'fake');
});

test('selection targets clicked cell, remains independent across notebooks and refresh', () => {
  const state = createState();
  const first = notebook(), second = notebook('two');
  state.refresh([first, second]);
  assert.equal(state.select(first.getCells()[1], 'fake'), true);
  assert.equal(state.selection(second.getCells()[1]), 'python');
  assert.equal(state.select(first.getCells()[2], 'python'), true);
  state.refresh([first, second]);
  assert.equal(state.selection(first.getCells()[1]), 'fake');
  assert.equal(state.selection(first.getCells()[2]), 'python');
  state.refresh([second]);
  assert.equal(state.selection(first.getCells()[1]), undefined);
  state.refresh([first, second]);
  assert.equal(state.selection(first.getCells()[1]), 'python');
});

test('rejects init, stale or missing cell arguments and unsupported choices', () => {
  const state = createState();
  const nb = notebook();
  state.refresh([nb]);
  assert.equal(state.select(nb.getCells()[0], 'fake'), false);
  assert.equal(state.select(undefined, 'fake'), false);
  assert.equal(state.select({ ...nb.getCells()[1] }, 'fake'), false);
  assert.equal(state.select(nb.getCells()[1], 'unknown'), false);
  assert.equal(state.selection(nb.getCells()[1]), 'python');
});

test('ordinary notebooks and non-Python/markup cells are not probe targets', () => {
  const state = createState();
  const nb = notebook();
  nb.getCells()[1].document.languageId = 'javascript';
  nb.getCells()[2].kind = 1;
  assert.deepEqual(state.refresh([nb]), []);
  assert.deepEqual(state.refresh([notebook('other', 'other-notebook')]), []);
  const unmarked = notebook();
  for (const cell of unmarked.getCells()) cell.metadata = {};
  assert.deepEqual(state.refresh([unmarked]), []);
});
