"use strict";
const path = require("node:path");
const { findSelections, replaceChoice, replacePath } = require("./selection.cjs");
const SET = "zizai.setValue";
const PICK_PATH = "zizai.pickPath";

function supported(document) {
  return !document.isClosed && document.uri.scheme === "vscode-notebook-cell" && document.languageId === "python";
}

function register(vscode, context, definitions) {
  async function setValue(request) {
    if (!request) return false;
    // Markdown command links normalize URI-looking strings. Carry the exact identity as data.
    const uri = typeof request.documentKey === "string"
      ? Buffer.from(request.documentKey, "base64").toString("utf8") : request.uri;
    const document = vscode.workspace.textDocuments.find(doc => doc.uri.toString() === uri);
    if (!document || !supported(document) || document.version !== request.version) return false;
    const source = document.getText();
    const field = findSelections(source, definitions).find(item => item.start === request.start && item.field === request.field);
    if (!field || replaceChoice(source, field, request.value) === source) return false;
    try {
      const edit = new vscode.WorkspaceEdit();
      edit.replace(document.uri,
        new vscode.Range(document.positionAt(field.start), document.positionAt(field.end)),
        JSON.stringify(request.value));
      const applied = await vscode.workspace.applyEdit(edit);
      if (!applied) vscode.window.showWarningMessage("選択値を反映できませんでした。");
      if (applied) await vscode.commands.executeCommand("editor.action.hideHover");
      return applied;
    } catch {
      vscode.window.showWarningMessage("選択値を反映できませんでした。");
      return false;
    }
  }
  context.subscriptions.push(vscode.commands.registerCommand(SET, setValue));

  context.subscriptions.push(vscode.commands.registerCommand(PICK_PATH, async request => {
    if (!request || typeof request.documentKey !== "string") return false;
    const uri = Buffer.from(request.documentKey, "base64").toString("utf8");
    const document = vscode.workspace.textDocuments.find(doc => doc.uri.toString() === uri);
    if (!document || !supported(document) || document.version !== request.version) return false;
    const source = document.getText();
    const field = findSelections(source, definitions).find(item => item.start === request.start && item.field === request.field);
    if (!field || !["file", "folder"].includes(field.kind)) return false;
    try {
      await vscode.commands.executeCommand("editor.action.hideHover");
      const selected = await vscode.window.showOpenDialog({
        canSelectFiles: field.kind === "file", canSelectFolders: field.kind === "folder", canSelectMany: false,
        defaultUri: path.isAbsolute(field.current) ? vscode.Uri.file(field.current) : undefined,
        openLabel: field.kind === "file" ? "このファイルを使用" : "このフォルダーを使用"
      });
      if (!selected?.length) return false;
      if (selected[0].scheme !== "file" || !supported(document) || document.version !== request.version) return false;
      if (replacePath(source, field, selected[0].fsPath) === source) return false;
      const edit = new vscode.WorkspaceEdit();
      edit.replace(document.uri,
        new vscode.Range(document.positionAt(field.start), document.positionAt(field.end)),
        JSON.stringify(selected[0].fsPath));
      const applied = await vscode.workspace.applyEdit(edit);
      if (!applied) vscode.window.showWarningMessage("パスを反映できませんでした。");
      return applied;
    } catch {
      vscode.window.showWarningMessage("パスを反映できませんでした。対象セルで選び直してください。");
      return false;
    }
  }));

  function tooltipFor(document, field) {
    const target = { version: document.version, start: field.start, field: field.field,
      documentKey: Buffer.from(document.uri.toString(), "utf8").toString("base64") };
    const isPath = ["file", "folder"].includes(field.kind);
    const command = isPath ? PICK_PATH : SET;
    const links = isPath ? ["[" + (field.kind === "file" ? "ファイルを選択" : "フォルダーを選択") + "]" +
      "(command:" + command + "?" + encodeURIComponent(JSON.stringify([target])) + ")"] : field.choices.map(value => {
      const text = value.replace(/[\\`*_{}\[\]()<>#+.!|]/g, "\\$&");
      const args = encodeURIComponent(JSON.stringify([{ ...target, value }]));
      return "[" + text + "](command:" + SET + "?" + args + ")";
    });
    const tooltip = new vscode.MarkdownString("値を選択\n\n" + links.join("\n\n"));
    tooltip.isTrusted = { enabledCommands: [command] };
    tooltip.supportHtml = false;
    return tooltip;
  }
  context.subscriptions.push(vscode.languages.registerHoverProvider(
    { language: "python", scheme: "vscode-notebook-cell" }, {
      provideHover(document, position) {
        if (!supported(document)) return undefined;
        const field = findSelections(document.getText(), definitions).find(item => item.line === position.line);
        if (!field) return undefined;
        return new vscode.Hover(tooltipFor(document, field),
          new vscode.Range(document.positionAt(field.start), document.positionAt(field.end)));
      }
    }
  ));

  const decoration = vscode.window.createTextEditorDecorationType({
    before: { color: new vscode.ThemeColor("editorInlayHint.foreground"), margin: "0 0.4em 0 0" },
    rangeBehavior: vscode.DecorationRangeBehavior.ClosedClosed
  });
  context.subscriptions.push(decoration);
  function refresh() {
    for (const editor of vscode.window.visibleTextEditors) {
      const document = editor.document;
      const fields = supported(document) ? findSelections(document.getText(), definitions) : [];
      editor.setDecorations(decoration, fields.map(field => {
          const position = document.positionAt(field.start);
          return {
            range: new vscode.Range(position, document.positionAt(field.end)),
            renderOptions: { before: { contentText: "[" + field.label + "]" } }
          };
      }));
    }
  }
  context.subscriptions.push(vscode.window.onDidChangeVisibleTextEditors(refresh));
  context.subscriptions.push(vscode.workspace.onDidChangeTextDocument(refresh));
  refresh();
}

function activate(context) {
  register(require("vscode"), context, require("./definitions.json"));
}

module.exports = { activate, register };
