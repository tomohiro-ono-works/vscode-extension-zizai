// API adapter tests only: these cannot prove desktop placement or rendering.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
function setup() {
  const commands = new Map();
  const events = [];
  let provider, pick, finishPick, outputCalls = 0;
  const disposable = () => ({ dispose() {} });
  const cells = ['init', undefined, 'action'].map((role, index) => ({
    index, kind: 2, metadata: { metadata: { task00101Probe: { role } } }, outputs: [],
    document: { languageId: 'python', uri: { toString: () => `cell:test/${index}` } }
  }));
  const nb = { notebookType: 'jupyter-notebook', getCells: () => cells };
  const api = {
    version: '1.142.0', env: { appName: 'test' },
    EventEmitter: class { event = () => disposable(); fire() {} dispose() {} },
    NotebookCellStatusBarAlignment: { Right: 2 },
    NotebookCellStatusBarItem: class { constructor(text, alignment) { Object.assign(this, { text, alignment }); } },
    notebooks: { registerNotebookCellStatusBarItemProvider(type, value) { assert.equal(type, 'jupyter-notebook'); provider = value; return disposable(); } },
    commands: { registerCommand(id, fn) { commands.set(id, fn); return disposable(); } },
    workspace: { notebookDocuments: [nb], onDidOpenNotebookDocument: disposable, onDidCloseNotebookDocument: disposable, onDidChangeNotebookDocument: disposable,
      getConfiguration: () => ({ get: () => 'visible' }) },
    extensions: { getExtension: () => undefined },
    window: {
      createOutputChannel() { outputCalls++; throw Error('Output channel should not be needed'); },
      showQuickPick(items) { pick = items; return new Promise(resolve => { finishPick = resolve; }); }
    }
  };
  const sandbox = { module: { exports: {} }, require: name => name === 'vscode' ? api : require(join(__dirname, name)),
    console: { info: line => events.push(JSON.parse(line)) }, process };
  vm.runInNewContext(readFileSync(join(__dirname, 'statusbar.cjs'), 'utf8'), sandbox);
  const context = { subscriptions: [], extension: { packageJSON: { version: '0.0.3' } } };
  sandbox.module.exports.activate(context);
  const item = index => provider.provideCellStatusBarItems(cells[index], { isCancellationRequested: false });
  return { cells, nb, api, context, events, item, get outputCalls() { return outputCalls; },
    choose(index) { const command = item(index).command; return commands.get(command.command)(...command.arguments); },
    finish(choice) { finishPick(choice === undefined ? undefined : pick.find(x => x.choice === choice)); },
    dispose() { for (const d of [...context.subscriptions].reverse()) d.dispose(); } };
}
test('provides a right-side selector before execution; init has none', () => {
  const s = setup();
  assert.equal(s.item(0), undefined);
  assert.match(s.item(1).text, /Zizai: 通常Python/);
  assert.equal(s.item(1).alignment, 2);
  assert.match(s.item(2).text, /架空コネクタ/);
  s.dispose();
});
test('selection changes only the clicked cell and leaves notebook data unchanged', async () => {
  const s = setup();
  const before = JSON.stringify(s.cells);
  const pending = s.choose(1); s.finish('fake'); await pending;
  assert.match(s.item(1).text, /架空コネクタ/);
  const next = s.choose(2); s.finish('python'); await next;
  assert.match(s.item(1).text, /架空コネクタ/);
  assert.match(s.item(2).text, /通常Python/);
  assert.equal(JSON.stringify(s.cells), before);
  s.dispose();
});
test('cancel leaves the previous selection unchanged', async () => {
  const s = setup(); const pending = s.choose(1); s.finish(); await pending;
  assert.match(s.item(1).text, /通常Python/); s.dispose();
});
test('closing a notebook while selection is open rejects a stale result', async () => {
  const s = setup(); const pending = s.choose(1);
  s.api.workspace.notebookDocuments.length = 0; s.finish('fake'); await pending;
  assert.equal(s.events.some(e => e.event === 'selected'), false); s.dispose();
});
test('deactivation during selection causes no late event or OutputChannel creation', async () => {
  const s = setup(); const pending = s.choose(1); s.dispose();
  const count = s.events.length; s.finish('fake'); await pending;
  assert.equal(s.events.length, count); assert.equal(s.outputCalls, 0);
});
