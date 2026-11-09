const assert = require("node:assert/strict");
const { register } = require("../../../apps/extension/extension.cjs");

function createHarness(definitions, initial) {
  let source = initial;
  let refresh = () => {};
  let rendered = [];
  let hoverProvider;
  const commands = new Map();
  const executedCommands = [];
  const edits = [];
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
    WorkspaceEdit: class { constructor() { this.changes = []; } replace(uri, range, value) { this.changes.push({ uri, range, value }); } },
    commands: {
      registerCommand(id, callback) { commands.set(id, callback); return { dispose() {} }; },
      async executeCommand(id) { executedCommands.push(id); }
    },
    languages: { registerHoverProvider(selector, provider) { hoverProvider = provider; return { dispose() {} }; } },
    workspace: {
      textDocuments: [document],
      onDidChangeTextDocument(callback) { refresh = callback; return { dispose() {} }; },
      async applyEdit(edit) {
        const lines = source.split("\n");
        const offset = position => lines.slice(0, position.line).reduce((sum, line) => sum + line.length + 1, 0) + position.character;
        edits.push(edit.changes);
        for (const change of [...edit.changes].sort((a, b) => offset(b.range.start) - offset(a.range.start))) {
          assert.equal(change.uri, document.uri);
          source = source.slice(0, offset(change.range.start)) + change.value + source.slice(offset(change.range.end));
        }
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
    api, document, executedCommands, edits, text: () => source,
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

module.exports = { createHarness };
