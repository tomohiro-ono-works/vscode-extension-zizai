const test = require("node:test");
const assert = require("node:assert/strict");
const { register } = require("../../../apps/extension/extension.cjs");
const definitions = {
  magics: { "ziz.connector.action.selector": {
    fields: { "connector.name": { label: "C", choices: ["csv", "excel"] } }
  } }
};
const initial = '%%ziz.connector.action.selector\nconnector.name = "" # keep\nother = 1';

function harness() {
  let source = initial;
  let provider, command;
  const document = {
    uri: { scheme: "vscode-notebook-cell", toString: () => "vscode-notebook-cell:/fixture.ipynb#cell" },
    languageId: "python", version: 1, isClosed: false,
    getText: () => source,
    positionAt(offset) {
      const before = source.slice(0, offset).split("\n");
      return new api.Position(before.length - 1, before.at(-1).length);
    }
  };
  const api = {
    Position: class { constructor(line, character) { Object.assign(this, { line, character }); } },
    Range: class { constructor(start, end) { Object.assign(this, { start, end }); } },
    InlayHintLabelPart: class { constructor(value) { this.value = value; } },
    InlayHint: class { constructor(position, label) { Object.assign(this, { position, label }); } },
    WorkspaceEdit: class { replace(uri, range, value) { Object.assign(this, { uri, range, value }); } },
    commands: { registerCommand(id, callback) { command = callback; return { dispose() {} }; } },
    languages: { registerInlayHintsProvider(selector, value) { provider = value; return { dispose() {} }; } },
    workspace: {
      textDocuments: [document],
      async applyEdit(edit) {
        assert.equal(edit.uri, document.uri);
        const lines = source.split("\n");
        const offset = position => lines.slice(0, position.line).reduce((sum, line) => sum + line.length + 1, 0) + position.character;
        source = source.slice(0, offset(edit.range.start)) + edit.value + source.slice(offset(edit.range.end));
        document.version += 1;
        return true;
      }
    },
    window: { async showQuickPick(items) { return items.find(item => item.value === api.nextValue); }, showWarningMessage() {} },
    nextValue: "csv"
  };
  register(api, { subscriptions: [] }, definitions);
  return {
    api, document, text: () => source,
    hints: () => provider.provideInlayHints(document, { contains: () => true }),
    pick: request => command(request)
  };
}

test("hint command selects and reselects the actual target literal", async () => {
  const h = harness();
  let hints = h.hints();
  assert.equal(hints.length, 1);
  assert.equal(hints[0].label[0].value, "[C]");
  assert.equal(await h.pick(hints[0].label[0].command.arguments[0]), true);
  assert.equal(h.text(), initial.replace('= ""', '= "csv"'));
  h.api.nextValue = "excel";
  hints = h.hints();
  assert.equal(await h.pick(hints[0].label[0].command.arguments[0]), true);
  assert.equal(h.text(), initial.replace('= ""', '= "excel"'));
});

test("cancel and stale hint leave the source untouched", async () => {
  const h = harness();
  const request = h.hints()[0].label[0].command.arguments[0];
  h.api.nextValue = undefined;
  assert.equal(await h.pick(request), false);
  assert.equal(h.text(), initial);
  h.document.version += 1;
  h.api.nextValue = "csv";
  assert.equal(await h.pick(request), false);
  assert.equal(h.text(), initial);
});

test("ordinary Python documents are not edited by a command request", async () => {
  const h = harness();
  const request = h.hints()[0].label[0].command.arguments[0];
  h.document.uri.scheme = "file";
  assert.equal(await h.pick(request), false);
  assert.equal(h.text(), initial);
});
