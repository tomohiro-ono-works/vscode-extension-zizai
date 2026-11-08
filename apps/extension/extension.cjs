"use strict";
const { findSelections, replaceChoice } = require("./selection.cjs");
const PICK = "zizai.pickValue";

function supported(document) {
  return !document.isClosed && document.uri.scheme === "vscode-notebook-cell" && document.languageId === "python";
}

function register(vscode, context, definitions) {
  context.subscriptions.push(vscode.commands.registerCommand(PICK, async request => {
    if (!request) return false;
    const document = vscode.workspace.textDocuments.find(doc => doc.uri.toString() === request.uri);
    if (!document || !supported(document) || document.version !== request.version) return false;
    const source = document.getText();
    const field = findSelections(source, definitions).find(item => item.start === request.start && item.field === request.field);
    if (!field) return false;
    try {
      const choice = await vscode.window.showQuickPick(
        field.choices.map(value => ({ label: value, value, description: value === field.current ? "現在の値" : undefined })),
        { title: field.field, placeHolder: "値を選択してください" }
      );
      if (!choice) return false;
      if (!supported(document) || document.version !== request.version) {
        vscode.window.showWarningMessage("対象セルが変更されたため反映しませんでした。選び直してください。");
        return false;
      }
      const changed = replaceChoice(source, field, choice.value);
      if (changed === source) return false;
      const edit = new vscode.WorkspaceEdit();
      edit.replace(document.uri,
        new vscode.Range(document.positionAt(field.start), document.positionAt(field.end)),
        JSON.stringify(choice.value));
      const applied = await vscode.workspace.applyEdit(edit);
      if (!applied) vscode.window.showWarningMessage("選択値を反映できませんでした。");
      return applied;
    } catch {
      vscode.window.showWarningMessage("選択値を反映できませんでした。");
      return false;
    }
  }));

  context.subscriptions.push(vscode.languages.registerInlayHintsProvider(
    { language: "python", scheme: "vscode-notebook-cell" },
    {
      provideInlayHints(document, range) {
        if (!supported(document)) return [];
        return findSelections(document.getText(), definitions).flatMap(field => {
          const position = document.positionAt(field.start);
          if (!range.contains(position)) return [];
          const label = new vscode.InlayHintLabelPart("[" + field.label + "]");
          label.tooltip = "値を選択（リンク操作の修飾キー＋クリック）";
          label.command = { command: PICK, title: "値を選択", arguments: [{
            uri: document.uri.toString(), version: document.version,
            start: field.start, field: field.field
          }] };
          const hint = new vscode.InlayHint(position, [label]);
          hint.paddingRight = true;
          return [hint];
        });
      }
    }
  ));
}

function activate(context) {
  register(require("vscode"), context, require("./definitions.json"));
}

module.exports = { activate, register };
