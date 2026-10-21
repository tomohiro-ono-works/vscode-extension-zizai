// Prototype bridge behavior only. Does not launch VS Code or prove CSP/rendering.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
const { join } = require('node:path');
function setup() {
  let command, receive, close, resolveDialog, calls = 0;
  const messages = [];
  const disposable = () => ({ dispose() {} });
  const panel = {
    webview: { cspSource: 'probe-resource:', asWebviewUri: value => value,
      onDidReceiveMessage(fn) { receive = fn; return disposable(); },
      async postMessage(value) { messages.push(value); return true; } },
    onDidDispose(fn) { close = fn; return disposable(); }, dispose() {}
  };
  const api = { version: '1.142.0', ViewColumn: { Active: 1 },
    Uri: { joinPath: (...parts) => parts.join('/') },
    commands: { registerCommand(_id, fn) { command = fn; return disposable(); } },
    window: { activeColorTheme: { kind: 2 },
      createWebviewPanel() { return panel; },
      showOpenDialog() { calls++; return new Promise(resolve => { resolveDialog = resolve; }); } }
  };
  const sandbox = { module: { exports: {} }, process,
    require(name) { if (name === 'vscode') return api;
      if (name === './provenance.json') return { upstreamCommit: 'pinned' };
      return require(name); } };
  vm.runInNewContext(readFileSync(join(__dirname, 'webview.cjs'), 'utf8'), sandbox);
  sandbox.module.exports.activate({ extensionUri: 'extension-root', extension: { packageJSON: { version: '0.0.1' } }, subscriptions: [] }); command();
  return { panel, messages, get calls() { return calls; }, receive: data => receive(data), close: () => close(),
    resolve: values => resolveDialog(values) };
}
const request = (id = 'one') => ({ type: 'browse', instanceId: 'nodeform_1', requestId: id, key: 'file', kind: 'file' });
test('cancel returns a correlated result and malformed requests do not open dialogs', async () => {
  const s = setup(); await s.receive({ ...request(), kind: 'unsupported' }); assert.equal(s.calls, 0);
  const pending = s.receive(request()); s.resolve(undefined); await pending;
  assert.equal(s.messages[0].result.cancelled, true);
  assert.equal(s.messages[0].result.requestId, 'one');
});
test('closing the panel during a dialog prevents a late postMessage', async () => {
  const s = setup(); const pending = s.receive(request()); s.close();
  s.resolve([{ fsPath: 'C:/fake.txt' }]); await pending; assert.equal(s.messages.length, 0);
});
test('a concurrent second request receives cancellation instead of staying pending', async () => {
  const s = setup(); const first = s.receive(request()); await s.receive(request('two'));
  assert.equal(s.calls, 1);
  assert.equal(s.messages[0]?.result.requestId, 'two');
  assert.equal(s.messages[0]?.result.cancelled, true);
  s.resolve([{ fsPath: 'C:/fake.txt' }]); await first;
  assert.equal(s.messages[1].result.requestId, 'one');
});
test('environment report carries provenance and HTML uses nonce-based scripts', async () => {
  const s = setup(); await s.receive({ type: 'report' });
  assert.equal(s.messages[0].upstreamCommit, 'pinned');
  assert.equal(s.messages[0].probeVersion, '0.0.1');
  assert.match(s.panel.webview.html, /default-src 'none'/);
  assert.match(s.panel.webview.html, /script-src 'nonce-[a-f0-9]+'/);
  assert.doesNotMatch(s.panel.webview.html, /unsafe-inline|unsafe-eval/);
});
