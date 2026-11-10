'use strict';
// Research extension only. No kernel, metadata, webview or command-palette contribution.
const vscode = require('vscode');
const PICK_PATH = 'zizaiPathResearch.pickPath';

function activate(context) {
  context.subscriptions.push(vscode.commands.registerCommand(PICK_PATH, async request => {
    const editor = vscode.window.activeTextEditor;
    if (!request || !editor) return false;
    const document = editor.document;
    if (document.isClosed || document.uri.toString() !== request.uri ||
        document.version <= request.sourceVersion ||
        !['file', 'folder'].includes(request.mode)) return false;
    const range = new vscode.Range(
      new vscode.Position(request.line, request.start),
      new vscode.Position(request.line, request.start + 2)
    );
    if (document.getText(range) !== '""') return false;
    const version = document.version;
    try {
      const selected = await vscode.window.showOpenDialog({
        canSelectFiles: request.mode === 'file',
        canSelectFolders: request.mode === 'folder',
        canSelectMany: false,
        openLabel: request.mode === 'file' ? 'ファイルパスを挿入' : 'フォルダパスを挿入'
      });
      if (!selected?.length) return false;
      if (selected[0].scheme !== 'file') return false;
      if (document.isClosed || document.version !== version ||
          vscode.window.activeTextEditor?.document !== document ||
          document.getText(range) !== '""') return false;
      const edit = new vscode.WorkspaceEdit();
      // A quoted string, not code interpolation or a new snippet expansion.
      edit.replace(document.uri, range, JSON.stringify(selected[0].fsPath));
      return await vscode.workspace.applyEdit(edit);
    } catch {
      vscode.window.showWarningMessage('パスを挿入できませんでした。対象セルで補完を選び直してください。');
      return false;
    }
  }));

  context.subscriptions.push(vscode.languages.registerCompletionItemProvider(
    { language: 'python', scheme: 'vscode-notebook-cell' },
    {
      provideCompletionItems(document, position) {
        const prefix = document.lineAt(position.line).text.slice(0, position.character);
        const match = /@([a-z]*)$/.exec(prefix);
        if (!match) return [];
        const start = position.character - match[0].length;
        return ['file', 'folder'].filter(mode => mode.startsWith(match[1])).map(mode => {
          const item = new vscode.CompletionItem('@' + mode, vscode.CompletionItemKind.Snippet);
          item.detail = mode === 'file' ? 'ファイルを選んでPython文字列を挿入' : 'フォルダを選んでPython文字列を挿入';
          item.insertText = new vscode.SnippetString('""$0');
          item.range = new vscode.Range(new vscode.Position(position.line, start), position);
          item.command = {
            command: PICK_PATH,
            title: 'パスを選択',
            arguments: [{ uri: document.uri.toString(), sourceVersion: document.version,
              line: position.line, start, mode }]
          };
          return item;
        });
      }
    }, '@'
  ));
}

module.exports = { activate };
