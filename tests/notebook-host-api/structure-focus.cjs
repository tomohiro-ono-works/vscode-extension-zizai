'use strict';
// D1 diagnostic control: identical standard commands/focus, with/without cell.id.
// No keyboard dispatch, kernel, internal modules, or acceptance-threshold changes.
const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { notebook } = require('./fixtures.cjs');
const { identities, encode } = require('./model.cjs');
const id = identities();
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
function state(doc) {
  return { at: new Date().toISOString(), object: id(doc), version: doc.version, dirty: doc.isDirty,
    cells: doc.getCells().map(c => ({ object: id(c), uri: c.document.uri.toString(), index: c.index, source: c.document.getText(), metadata: c.metadata })) };
}
async function run() {
  const build = JSON.parse(fs.readFileSync(path.join(__dirname, 'build.local.json'), 'utf8'));
  const file = path.join(build.root, 'results/task-002-01/structure-focus-result.local.json');
  const report = { status: 'running', at: new Date().toISOString(), vscode: vscode.version, build,
    conditions: 'first-cell selection; notebook.focusTop + quitEdit before each command; 300ms settling; installed extensions disabled by CLI', results: [] };
  const persist = () => fs.writeFileSync(file, encode(report) + '\n');
  persist();
  try {
    const api = await vscode.extensions.getExtension('zizai-lab.task-002-01-notebook-host-api-probe').activate();
    report.rawLog = api.logFile;
    const commands = await vscode.commands.getCommands(true);
    for (const cmd of ['notebook.focusTop', 'notebook.cell.quitEdit', 'notebook.cell.delete', 'undo', 'redo']) assert.ok(commands.includes(cmd), cmd);
    for (const cellIds of [false, true]) {
      const data = notebook('D1-structure');
      if (cellIds) data.cells.forEach((cell, index) => { cell.id = `task00201-control-${index}`; });
      else data.cells.forEach(cell => { delete cell.id; }); // Explicit historical invalid-fixture control.
      const fixture = path.join(api.workspace, `AUTO-D1-focus-${cellIds ? 'ids' : 'no-ids'}-${Date.now()}.ipynb`);
      fs.writeFileSync(fixture, JSON.stringify(data));
      const opened = await vscode.workspace.openNotebookDocument(vscode.Uri.file(fixture));
      const editor = await vscode.window.showNotebookDocument(opened, { preview: false });
      const doc = editor.notebook;
      const focus = async () => {
        await vscode.commands.executeCommand('notebook.focusTop');
        editor.selections = [new vscode.NotebookRange(0, 1)];
        await vscode.commands.executeCommand('notebook.cell.quitEdit');
        await pause(300);
      };
      await focus();
      const result = { cellIds, before: state(doc) };
      report.results.push(result); persist();
      for (const [key, command] of [['deleted', 'notebook.cell.delete'], ['undo', 'undo'], ['redo', 'redo']]) {
        await focus();
        await vscode.commands.executeCommand(command);
        await pause(300);
        result[key] = state(doc); persist();
      }
      result.expectedCounts = [3, 2, 3, 2];
      result.actualCounts = ['before', 'deleted', 'undo', 'redo'].map(key => result[key].cells.length);
      result.matches = result.actualCounts.every((n, index) => n === result.expectedCounts[index]);
      result.saved = await doc.save(); persist();
    }
    report.status = 'completed-observations'; report.finishedAt = new Date().toISOString(); persist();
  } catch (error) { report.status = 'failed'; report.error = String(error); persist(); throw error; }
}
module.exports = { run };
