'use strict';
const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { notebook } = require('./fixtures.cjs');
const { identities, encode } = require('./model.cjs');
const id = identities();
const pause = () => new Promise(r => setTimeout(r, 40));
function state(doc) { return { object: id(doc), version: doc.version, dirty: doc.isDirty, cells: doc.getCells().map(c => ({ object: id(c), textObject: id(c.document), uri: c.document.uri.toString(), index: c.index, source: c.document.getText(), metadata: c.metadata })) }; }
async function run(modes = ['duplicate-up', 'copy-paste', 'delete']) {
  const build = JSON.parse(fs.readFileSync(path.join(__dirname, 'build.local.json'), 'utf8'));
  const file = path.join(build.root, 'results/task-002-01/structure-result.local.json');
  const report = { status: 'running', at: new Date().toISOString(), vscode: vscode.version, results: [] };
  const persist = () => fs.writeFileSync(file, encode(report) + '\n');
  persist();
  try {
    const api = await vscode.extensions.getExtension('zizai-lab.task-002-01-notebook-host-api-probe').activate();
    report.rawLog = api.logFile;
    const commands = await vscode.commands.getCommands(true);
    for (const cmd of ['notebook.cell.copyUp', 'notebook.cell.copy', 'notebook.cell.paste', 'notebook.cell.delete', 'notebook.cell.quitEdit']) assert.ok(commands.includes(cmd), cmd);
    for (const mode of modes) {
      const fixture = path.join(api.workspace, `AUTO-D1-${mode}-${Date.now()}.ipynb`);
      fs.writeFileSync(fixture, JSON.stringify(notebook('D1-structure')));
      const doc = await vscode.workspace.openNotebookDocument(vscode.Uri.file(fixture));
      const editor = await vscode.window.showNotebookDocument(doc, { preview: false });
      editor.selections = [new vscode.NotebookRange(mode === 'copy-paste' ? 0 : 1, mode === 'copy-paste' ? 1 : 2)];
      await vscode.commands.executeCommand('notebook.cell.quitEdit');
      const before = state(doc);
      if (mode === 'duplicate-up') await vscode.commands.executeCommand('notebook.cell.copyUp');
      if (mode === 'copy-paste') {
        // Standard cell clipboard operation on synthetic data only.
        await vscode.commands.executeCommand('notebook.cell.copy');
        editor.selections = [new vscode.NotebookRange(2, 3)];
        await vscode.commands.executeCommand('notebook.cell.paste');
      }
      if (mode === 'delete') await vscode.commands.executeCommand('notebook.cell.delete');
      await pause();
      const after = state(doc);
      assert.equal(doc.cellCount, mode === 'delete' ? 2 : 4);
      await vscode.commands.executeCommand('notebook.cell.quitEdit');
      await vscode.commands.executeCommand('undo'); await pause();
      const undo = state(doc);
      assert.equal(doc.cellCount, 3);
      await vscode.commands.executeCommand('notebook.cell.quitEdit');
      await vscode.commands.executeCommand('redo'); await pause();
      const redo = state(doc);
      report.results.push({ case: 'D1-' + mode, status: 'observed-standard-command', before, after, undo, redo }); persist();
      assert.equal(doc.cellCount, mode === 'delete' ? 2 : 4);
    }
    report.status = 'completed'; report.finishedAt = new Date().toISOString(); persist();
  } catch (e) { report.status = 'failed'; report.error = String(e); report.stack = e.stack; persist(); throw e; }
}
module.exports = { run };
