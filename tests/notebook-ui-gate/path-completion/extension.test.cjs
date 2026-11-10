'use strict';
// Public API adapter checks only; no VS Code desktop or Python kernel is launched.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup(text = 'path = @fi') {
  const commands = new Map();
  const dialogs = [];
  const writes = [];
  let provider, selector, resolveDialog;
  const disposable = { dispose() {} };
  class Position { constructor(line, character) { Object.assign(this, { line, character }); } }
  class Range {
    constructor(start, end) { Object.assign(this, { start, end }); }
  }
  const document = {
    uri: { scheme: 'vscode-notebook-cell', toString: () => 'vscode-notebook-cell:/example/one' },
    languageId: 'python', version: 1, isClosed: false,
    lineAt: () => ({ text }),
    getText(range) { return range ? text.slice(range.start.character, range.end.character) : text; }
  };
  const editor = { document };
  const api = {
    Position, Range,
    CompletionItemKind: { Snippet: 14 },
    CompletionItem: class { constructor(label, kind) { Object.assign(this, { label, kind }); } },
    SnippetString: class { constructor(value) { this.value = value; } },
    WorkspaceEdit: class { replace(uri, range, value) { this.change = { uri, range, value }; } },
    languages: { registerCompletionItemProvider(s, p, trigger) {
      selector = s; provider = p; assert.equal(trigger, '@'); return disposable;
    } },
    commands: { registerCommand(id, fn) { commands.set(id, fn); return disposable; } },
    workspace: { async applyEdit(edit) { writes.push(edit.change); return true; } },
    window: {
      activeTextEditor: editor,
      showOpenDialog(options) { dialogs.push(options); return new Promise(resolve => { resolveDialog = resolve; }); },
      showWarningMessage() { throw Error('No unexpected warning expected'); }
    }
  };
  const sandbox = { module: { exports: {} }, require(name) {
    assert.equal(name, 'vscode'); return api;
  } };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'extension.cjs'), 'utf8'), sandbox);
  sandbox.module.exports.activate({ subscriptions: [] });
  const items = () => provider.provideCompletionItems(document, new Position(0, text.length));
  return { api, document, dialogs, writes, get selector() { return selector; }, items,
    async accept(label) {
      const item = items().find(i => i.label === label);
      assert.ok(item, label);
      assert.equal(item.insertText.value, '""$0');
      text = text.slice(0, item.range.start.character) + '""' + text.slice(item.range.end.character);
      document.version++;
      return commands.get(item.command.command)(...item.command.arguments);
    },
    finish(result) { resolveDialog(result); },
    setText(value) { text = value; document.version++; }
  };
}

test('offers only matching Notebook path snippets and never opens a dialog for suggestions', () => {
  const s = setup();
  assert.equal(s.selector.language, 'python');
  assert.equal(s.selector.scheme, 'vscode-notebook-cell');
  assert.deepEqual(Array.from(s.items(), i => i.label), ['@file']);
  assert.equal(s.dialogs.length, 0);
  s.setText('path = @f');
  assert.deepEqual(Array.from(s.items(), i => i.label), ['@file', '@folder']);
  s.setText('ordinary_python');
  assert.equal(s.items().length, 0);
});

test('file selection replaces only its inserted literal, escaping paths without snippet expansion', async () => {
  const s = setup();
  const pending = s.accept('@file');
  assert.equal(s.dialogs.length, 1);
  assert.equal(s.dialogs[0].canSelectFiles, true);
  assert.equal(s.dialogs[0].canSelectFolders, false);
  const chosen = 'C:\\売上\\O\'Reilly "${1:keep}"\\data.csv';
  s.finish([{ scheme: 'file', fsPath: chosen }]);
  await pending;
  assert.equal(s.writes.length, 1);
  assert.equal(s.writes[0].value, '"C:\\\\売上\\\\O\'Reilly \\"${1:keep}\\"\\\\data.csv"');
  assert.equal(s.writes[0].range.start.character, 7);
  assert.equal(s.writes[0].range.end.character, 9);
});

test('folder selection and cancellation preserve surrounding code and do not execute Python', async () => {
  const s = setup('folder = @folder');
  const pending = s.accept('@folder');
  assert.equal(s.dialogs[0].canSelectFiles, false);
  assert.equal(s.dialogs[0].canSelectFolders, true);
  assert.equal(s.dialogs[0].canSelectMany, false);
  s.finish(undefined);
  await pending;
  assert.equal(s.document.getText(), 'folder = ""');
  assert.equal(s.writes.length, 0);
});

test('folder selection inserts its chosen directory as a quoted literal', async () => {
  const s = setup('folder = @folder');
  const pending = s.accept('@folder');
  s.finish([{ scheme: 'file', fsPath: 'C:\\work\\入力' }]);
  await pending;
  assert.equal(s.writes.length, 1);
  assert.equal(s.writes[0].value, '"C:\\\\work\\\\入力"');
});

test('ignores selection after switching to another cell or editing the target', async () => {
  for (const change of ['switch', 'edit', 'close']) {
    const s = setup();
    const pending = s.accept('@file');
    if (change === 'switch') s.api.window.activeTextEditor = { document: {} };
    if (change === 'edit') s.setText('user changed this');
    if (change === 'close') s.document.isClosed = true;
    s.finish([{ scheme: 'file', fsPath: 'C:\\data.csv' }]);
    await pending;
    assert.equal(s.writes.length, 0, change);
  }
});

test('does not invent a local path from a remote URI', async () => {
  const s = setup();
  const pending = s.accept('@file');
  s.finish([{ scheme: 'vscode-remote', fsPath: '/remote/data.csv' }]);
  await pending;
  assert.equal(s.writes.length, 0);
});
