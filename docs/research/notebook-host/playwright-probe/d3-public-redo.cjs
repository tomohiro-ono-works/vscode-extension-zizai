'use strict';
// Research-only bridge. Public commands API; no internal editor/model access.
const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const core = require('./extension.cjs');
function activate(context) {
  const api = core.activate(context);
  context.subscriptions.push(vscode.commands.registerCommand('task00201.d3PublicRedo', async () => {
    const folder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    const doc = vscode.window.activeNotebookEditor?.notebook;
    if (!folder || !doc || path.dirname(doc.uri.fsPath) !== folder || !/^PW-.*-D3-public.ipynb$/.test(path.basename(doc.uri.fsPath))) throw new Error('D3 public comparison target required');
    const value = () => ({ uri: doc.uri.toString(), version: doc.version, dirty: doc.isDirty, source: doc.cellAt(0).document.getText(), metadata: doc.cellAt(0).metadata });
    const result = { route: 'vscode.commands.executeCommand(redo)', at: new Date().toISOString(), before: value() };
    try {
      await vscode.commands.executeCommand('redo');
      result.returnedAt = new Date().toISOString();
      result.after = value();
    } catch (error) { result.error = String(error); }
    fs.writeFileSync(path.join(folder, 'public-redo.local.json'), JSON.stringify(result, null, 2), { flag: 'wx' });
    api.snapshot();
  }));
  return api;
}
module.exports = { activate };
