// Prototype client lifecycle tests. Does not launch VS Code or prove Webview rendering.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const source = readFileSync(join(__dirname, 'webview-client.mjs'), 'utf8');

// VS Code owns state per panel; opening a new document discards its JS context.
// NodeForm is an external boundary: only its mount/getParams/onChange contract is
// adapted here. The real client script handles saving, restoring, and resetting.
function panel() {
  let saved;
  return {
    get saved() { return structuredClone(saved); },
    open() {
      const listeners = new Map();
      const element = id => ({
        textContent: '',
        addEventListener(type, fn) { listeners.set(id + ':' + type, fn); }
      });
      const elements = Object.fromEntries(['form', 'status', 'result', 'validate', 'remount', 'report']
        .map(id => [id, element(id)]));
      let current, change;
      const document = { getElementById: id => elements[id], dispatchEvent() {} };
      const window = {
        addEventListener() {},
        NodeForm: {
          mount(options) {
            let values = { name: '', choice: '', mode: 'hide', detail: '', file: '', folder: '',
              ...structuredClone(options.node.form) };
            change = (key, value) => {
              values[key] = value;
              options.onChange(structuredClone(values), { key, value });
            };
            current = { getParams: () => structuredClone(values), destroy() {}, validate: () => ({ valid: true }) };
            return current;
          }
        }
      };
      const api = {
        getState: () => structuredClone(saved),
        setState(value) { saved = structuredClone(value); },
        postMessage() {}
      };
      vm.runInNewContext(source, { window, document, acquireVsCodeApi: () => api });
      return {
        input: (key, value) => change(key, value),
        click: id => listeners.get(id + ':click')(),
        params: () => current.getParams()
      };
    }
  };
}

test('a recreated Webview document restores form values including conditional and browse fields', () => {
  const p = panel();
  const first = p.open();
  for (const [key, value] of Object.entries({
    name: 'fictional-name', choice: 'two', mode: 'show', detail: 'fictional-detail',
    file: 'C:/fictional/empty.txt', folder: 'C:/fictional/empty-folder'
  })) first.input(key, value);
  assert.deepEqual(p.open().params(), {
    name: 'fictional-name', choice: 'two', mode: 'show', detail: 'fictional-detail',
    file: 'C:/fictional/empty.txt', folder: 'C:/fictional/empty-folder'
  });
});

test('remount clears saved form values so they do not return in a later document', () => {
  const p = panel();
  const first = p.open();
  first.input('name', 'fictional-name');
  assert.equal(p.saved?.form?.name, 'fictional-name');
  first.click('remount');
  assert.equal(first.params().name, '');
  assert.equal(p.open().params().name, '');
});

test('saving and remounting one panel leaves another panel state independent', () => {
  const a = panel();
  const b = panel();
  const first = a.open();
  const second = b.open();
  first.input('name', 'fictional-first');
  second.input('name', 'fictional-second');
  const restoredFirst = a.open();
  assert.equal(restoredFirst.params().name, 'fictional-first');
  assert.equal(b.open().params().name, 'fictional-second');
  restoredFirst.click('remount');
  assert.equal(a.open().params().name, '');
  assert.equal(b.open().params().name, 'fictional-second');
});
