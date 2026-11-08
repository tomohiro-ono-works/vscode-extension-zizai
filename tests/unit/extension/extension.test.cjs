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
  let refresh = () => {};
  let rendered = [];
  let hoverProvider;
  const commands = new Map();
  const executedCommands = [];
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
    ThemeColor: class { constructor(id) { this.id = id; } },
    DecorationRangeBehavior: { ClosedClosed: 0 },
    Position: class { constructor(line, character) { Object.assign(this, { line, character }); } },
    Range: class { constructor(start, end) { Object.assign(this, { start, end }); } },
    InlayHintLabelPart: class { constructor(value) { this.value = value; } },
    InlayHint: class { constructor(position, label) { Object.assign(this, { position, label }); } },
    MarkdownString: class { constructor(value) { this.value = value; } },
    Hover: class { constructor(content, range) { this.contents = [content]; this.range = range; } },
    WorkspaceEdit: class { replace(uri, range, value) { Object.assign(this, { uri, range, value }); } },
    commands: {
      registerCommand(id, callback) { commands.set(id, callback); return { dispose() {} }; },
      async executeCommand(id) { executedCommands.push(id); }
    },
    languages: { registerHoverProvider(selector, provider) { hoverProvider = provider; return { dispose() {} }; } },
    workspace: {
      textDocuments: [document],
      onDidChangeTextDocument(callback) { refresh = callback; return { dispose() {} }; },
      async applyEdit(edit) {
        assert.equal(edit.uri, document.uri);
        const lines = source.split("\n");
        const offset = position => lines.slice(0, position.line).reduce((sum, line) => sum + line.length + 1, 0) + position.character;
        source = source.slice(0, offset(edit.range.start)) + edit.value + source.slice(offset(edit.range.end));
        document.version += 1;
        refresh();
        return true;
      }
    },
    window: {
      visibleTextEditors: [{ document, setDecorations(type, values) { rendered = values; } }],
      createTextEditorDecorationType() { return { dispose() {} }; },
      onDidChangeVisibleTextEditors(callback) { refresh = callback; return { dispose() {} }; },
      showWarningMessage() {}
    }
  };
  register(api, { subscriptions: [] }, definitions);
  return {
    api, document, executedCommands, text: () => source,
    decorations: () => { refresh(); return rendered; },
    tooltip: () => hoverProvider.provideHover(document, new api.Position(1, 17)).contents[0],
    pick: request => commands.get("zizai.setValue")(request),
    choiceRequest(value) {
      refresh();
      const tooltip = hoverProvider.provideHover(document, new api.Position(1, 17)).contents[0];
      return [...tooltip.value.matchAll(/\]\(command:zizai\.setValue\?([^)]*)\)/g)]
        .map(match => JSON.parse(decodeURIComponent(match[1]))[0]).find(request => request.value === value);
    },
    invoke: (id, request) => commands.get(id)(request)
  };
}

test("hint command selects and reselects the actual target literal", async () => {
  const h = harness();
  let hints = h.decorations();
  assert.equal(hints.length, 1);
  assert.equal(hints[0].renderOptions.before.contentText, "[C]");
  assert.equal(hints[0].range.start.character, 17, "Anchor to the target, not the beginning of the line");
  assert.equal(hints[0].range.end.character, 19, "Hover covers the target literal");
  assert.equal(await h.pick(h.choiceRequest("csv")), true);
  assert.equal(h.text(), initial.replace('= ""', '= "csv"'));
  hints = h.decorations();
  assert.equal(await h.pick(h.choiceRequest("excel")), true);
  assert.equal(h.text(), initial.replace('= ""', '= "excel"'));
});

test("cancel and stale hint leave the source untouched", async () => {
  const h = harness();
  const request = h.choiceRequest("csv");
  assert.equal(await h.pick(undefined), false);
  assert.equal(h.text(), initial);
  h.document.version += 1;
  assert.equal(await h.pick(request), false);
  assert.equal(h.text(), initial);
});

test("selection dismisses the cached menu and reselection uses the current document", async () => {
  const h = harness();
  const cachedExcel = h.choiceRequest("excel");
  assert.equal(await h.pick(h.choiceRequest("csv")), true);
  assert.deepEqual(h.executedCommands, ["editor.action.hideHover"]);
  assert.equal(await h.pick(cachedExcel), false, "Stale menus must still be rejected");
  assert.equal(await h.pick(h.choiceRequest("excel")), true);
  assert.equal(h.text(), initial.replace('= ""', '= "excel"'));
});

test("ordinary Python documents are not edited by a command request", async () => {
  const h = harness();
  const request = h.choiceRequest("csv");
  h.document.uri.scheme = "file";
  assert.equal(await h.pick(request), false);
  assert.equal(h.text(), initial);
});

test("hover offers a directly clickable choice without opening QuickPick", async () => {
  const h = harness();
  h.api.window.showQuickPick = () => { throw Error("Hover must not open QuickPick"); };
  const tooltip = h.tooltip();
  assert.equal(typeof tooltip, "object");
  const link = /\[csv\]\((command:[^)]+)\)/.exec(tooltip.value);
  assert.ok(link, "CSV is a command link in the hover");
  const [id, encoded] = link[1].slice("command:".length).split("?");
  const [request] = JSON.parse(decodeURIComponent(encoded));
  assert.equal(await h.invoke(id, request), true);
  assert.equal(h.text(), initial.replace('= ""', '= "csv"'));
});

test("hover permits only the selection command and rejects a value outside the definition", async () => {
  const h = harness();
  const tooltip = h.tooltip();
  assert.deepEqual(tooltip.isTrusted, { enabledCommands: ["zizai.setValue"] });
  assert.equal(tooltip.supportHtml, false);
  const link = /\[csv\]\((command:[^)]+)\)/.exec(tooltip.value);
  const [id, encoded] = link[1].slice("command:".length).split("?");
  const [request] = JSON.parse(decodeURIComponent(encoded));
  request.value = "outside-the-definition";
  assert.equal(await h.invoke(id, request), false);
  assert.equal(h.text(), initial);
});

test("hover preserves the exact encoded Notebook URI across Markdown command links", async () => {
  const h = harness();
  const uri = "vscode-notebook-cell:/c%3A/%E8%B3%87%E6%96%99/book.ipynb#cell%3D%3D";
  h.document.uri.toString = () => uri;
  const tooltip = h.tooltip();
  const link = /\[csv\]\((command:[^)]+)\)/.exec(tooltip.value);
  const [id, encoded] = link[1].slice("command:".length).split("?");
  const [request] = JSON.parse(decodeURIComponent(encoded));
  assert.equal(typeof request.documentKey, "string");
  assert.equal(request.uri, undefined, "Do not expose a URI-looking value to Markdown normalization");
  assert.equal(Buffer.from(request.documentKey, "base64").toString("utf8"), uri);
  assert.equal(await h.invoke(id, request), true);
  assert.equal(h.text(), initial.replace('= ""', '= "csv"'));
});
