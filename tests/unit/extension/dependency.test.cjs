const test = require('node:test');
const assert = require('node:assert/strict');
const { findSelections } = require('../../../apps/extension/selection.cjs');
const { createHarness } = require('./vscode-harness.cjs');
const definitions = { magics: { 'ziz.connector.action.selector': { fields: {
  'connector.name': { label: 'C', choices: ['csv', 'excel'] },
  'connector.action.name': { label: 'A', dependsOn: 'connector.name', choicesByValue: {
    csv: ['shared', 'csv_only'], excel: ['shared', 'excel_only']
  } }
} } } };
const source = action => '%%ziz.connector.action.selector\nconnector.name = "csv" # parent\nconnector.action.name = ' + JSON.stringify(action) + ' # child\nother = "keep"';

test('dependent choices come from the current parent even when the child precedes it', () => {
  const text = '%%ziz.connector.action.selector\nconnector.action.name = ""\nconnector.name = "excel"';
  assert.deepEqual(findSelections(text, definitions).find(f => f.field === 'connector.action.name')?.choices, ['shared', 'excel_only']);
});
test('selecting a parent clears only an invalid child in the same WorkspaceEdit', async () => {
  const h = createHarness(definitions, source('csv_only'));
  assert.equal(await h.pick(h.choiceRequest('excel')), true);
  assert.equal(h.text(), source('').replace('= "csv"', '= "excel"'));
  assert.equal(h.edits.length, 1);
  assert.equal(h.edits[0].length, 2);
});
test('selecting a parent preserves a still-valid child', async () => {
  const h = createHarness(definitions, source('shared'));
  assert.equal(await h.pick(h.choiceRequest('excel')), true);
  assert.equal(h.text(), source('shared').replace('= "csv"', '= "excel"'));
});
test('missing or ambiguous parent offers no child choices and never edits source', () => {
  for (const text of ['%%ziz.connector.action.selector\nconnector.action.name = "csv_only"', source('csv_only') + '\nconnector.name = "excel"']) {
    assert.deepEqual(findSelections(text, definitions).find(f => f.field === 'connector.action.name')?.choices, []);
  }
});
test('an empty or unlisted parent cannot enable a child even if a mapping exists', () => {
  const d = structuredClone(definitions);
  Object.assign(d.magics['ziz.connector.action.selector'].fields['connector.action.name'].choicesByValue, { '': ['unexpected'], unknown: ['unexpected'] });
  for (const parent of ['', 'unknown']) {
    const text = source('').replace('= "csv"', '= ' + JSON.stringify(parent));
    assert.deepEqual(findSelections(text, d).find(f => f.field === 'connector.action.name').choices, []);
  }
});
