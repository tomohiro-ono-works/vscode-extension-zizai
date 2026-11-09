const test = require('node:test');
const assert = require('node:assert/strict');
const { parseDefinitions, createDefinitionStore } = require('../../../apps/extension/definitions.cjs');
const yaml = `version: 1
magics:
  ziz.connector.action.selector:
    fields:
      connector.name: {label: C, choices: [csv, excel]}
      connector.action.name:
        label: A
        dependsOn: connector.name
        choicesByValue: {csv: [import, export], excel: [export]}
`;
test('loads YAML data with dependent candidates', () => {
  const d = parseDefinitions(yaml);
  assert.deepEqual(d.magics['ziz.connector.action.selector'].fields['connector.action.name'].choicesByValue.csv, ['import','export']);
});
test('rejects invalid structure, duplicate keys, aliases and executable tags', () => {
  for (const input of ['version: 1\nmagics: []', yaml.replace('[csv, excel]', '[1, true]'), yaml + '\nversion: 1', 'version: 1\nmagics: &x {x: *x}', 'version: 1\nmagics: !!js/function "evil"']) {
    assert.throws(() => parseDefinitions(input));
  }
});
test('rejects missing or cyclic parent definitions', () => {
  assert.throws(() => parseDefinitions(yaml.replace('dependsOn: connector.name', 'dependsOn: missing')));
  assert.throws(() => parseDefinitions(yaml.replace('{label: C, choices: [csv, excel]}', '{label: C, dependsOn: connector.action.name, choicesByValue: {import: [csv]}}')));
});

function fixture() {
  const root = { uri: { toString: () => 'file:///fixture' } };
  const file = { toString: () => 'file:///fixture/.vscode/zizai-definitions.yaml' };
  const notebookUri = { toString: () => 'file:///fixture/book.ipynb' };
  const document = { uri: { toString: () => 'vscode-notebook-cell:/fixture/book.ipynb#cell' } };
  let content, changed;
  const warnings = [];
  const api = {
    Uri: { joinPath: () => file },
    workspace: {
      workspaceFolders: [root], notebookDocuments: [{ uri: notebookUri, getCells: () => [{ document }] }],
      getWorkspaceFolder: uri => uri === notebookUri ? root : undefined,
      fs: { readFile: async () => { if (content === undefined) throw { code: 'FileNotFound' }; return Buffer.from(content); } },
      createFileSystemWatcher: () => ({ onDidCreate: f => { changed = f; return {}; }, onDidChange: f => { changed = f; return {}; }, onDidDelete: f => { changed = f; return {}; }, dispose() {} }),
      onDidChangeWorkspaceFolders: () => ({})
    },
    window: { showWarningMessage: message => warnings.push(message) }
  };
  return { api, document, file, warnings, set: v => { content = v; }, change: () => changed(file) };
}
test('uses bundled fallback only when absent, reloads changes, and disables invalid external data', async () => {
  const f = fixture();
  const fallback = { magics: {} };
  const store = await createDefinitionStore(f.api, { subscriptions: [] }, fallback, () => {});
  assert.equal(store.get(f.document), fallback);
  f.set(yaml); await f.change();
  assert.ok(store.get(f.document).magics['ziz.connector.action.selector']);
  assert.equal(store.get({ uri: { toString: () => 'outside' } }), fallback);
  f.set('bad: ['); await f.change();
  assert.deepEqual(store.get(f.document), { magics: {} });
  assert.equal(f.warnings.length, 1);
  f.set(yaml); await f.change();
  assert.ok(store.get(f.document).magics['ziz.connector.action.selector']);
  f.set(undefined); await f.change();
  assert.equal(store.get(f.document), fallback);
});
