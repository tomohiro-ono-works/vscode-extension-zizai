'use strict';
// Follow up only the D2 fresh-read and D3 partial-source Undo observations.
const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { notebook } = require('./fixtures.cjs');
const { patchMetadata, encode } = require('./model.cjs');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
function state(doc) {
  return { version: doc.version, dirty: doc.isDirty, closed: doc.isClosed,
    cells: doc.getCells().map(c => ({ index: c.index, uri: c.document.uri.toString(), source: c.document.getText(), metadata: c.metadata })) };
}
async function run() {
  const build = JSON.parse(fs.readFileSync(path.join(__dirname, 'build.local.json'), 'utf8'));
  const reportFile = path.join(build.root, 'results/task-002-01/recovery-result.local.json');
  const report = { status: 'running', at: new Date().toISOString(), vscode: vscode.version, pid: process.pid, build, results: [] };
  const persist = () => fs.writeFileSync(reportFile, encode(report) + '\n');
  persist();
  try {
    const api = await vscode.extensions.getExtension('zizai-lab.task-002-01-notebook-host-api-probe').activate();
    report.rawLog = api.logFile;
    const prior = JSON.parse(fs.readFileSync(path.join(build.root, 'results/task-002-01/automated-result.local.json'), 'utf8'));
    const d2 = prior.results.find(r => r.case === 'D2');
    assert.ok(d2, 'previous D2 result is required');
    const basename = d2.before.cells[0].uri.match(/AUTO-D2-save-\d+\.ipynb/)?.[0];
    assert.ok(basename, 'only the generated D2 file may be reopened');
    const file = path.join(api.workspace, basename);
    const uri = vscode.Uri.file(file);
    const alreadyOpen = vscode.workspace.notebookDocuments.some(d => d.uri.toString() === uri.toString());
    assert.equal(alreadyOpen, false, 'fresh process must not already contain the D2 model');
    assert.notEqual(path.dirname(prior.rawLog), path.dirname(api.logFile), 'independent diagnostic session is required');
    const savedBytes = fs.readFileSync(file);
    const saved = JSON.parse(savedBytes);
    assert.deepEqual(saved, d2.saved);
    const doc = await vscode.workspace.openNotebookDocument(uri);
    const reopened = state(doc);
    assert.equal(reopened.cells[0].source, d2.before.cells[0].source);
    assert.equal(reopened.cells[0].metadata.metadata.task00201Diagnostic.draft, 7);
    assert.equal(reopened.cells[0].metadata.metadata.outsideDiagnosticOwner.sentinel, 'keep-D2');
    assert.equal(doc.metadata.metadata.outsideNotebookOwner.sentinel, 'preserve-notebook');
    assert.equal(doc.isDirty, false);
    assert.deepEqual(fs.readFileSync(file), savedBytes, 'reading must not rewrite the saved file');
    report.results.push({ case: 'D2-fresh-process-read', status: 'passed-API', file, previousRawLog: prior.rawLog, alreadyOpen, reopened, saved }); persist();

    const commands = await vscode.commands.getCommands(true);
    assert.ok(commands.includes('notebook.cell.edit'));
    const mixedFile = path.join(api.workspace, `AUTO-D3-source-failure-focused-${Date.now()}.ipynb`);
    fs.writeFileSync(mixedFile, JSON.stringify(notebook('D3-mixed')) + '\n');
    const mixed = await vscode.workspace.openNotebookDocument(vscode.Uri.file(mixedFile));
    const editor = await vscode.window.showNotebookDocument(mixed, { preview: false });
    editor.selections = [new vscode.NotebookRange(0, 1)];
    await vscode.commands.executeCommand('notebook.cell.quitEdit');
    const cell = mixed.cellAt(0), before = state(mixed);
    const changedSource = '# AUTO D3 source-first failure with explicit text focus\nfictional_value = 20\n';
    const edit = new vscode.WorkspaceEdit();
    edit.replace(cell.document.uri, new vscode.Range(0, 0, cell.document.lineCount, 0), changedSource);
    edit.set(mixed.uri, [vscode.NotebookEdit.updateCellMetadata(mixed.cellCount + 100, patchMetadata(cell.metadata, { mixed: 'intentional-failure' }))]);
    let returned, error;
    try { returned = await vscode.workspace.applyEdit(edit); } catch (e) { error = String(e); }
    await pause(100);
    const observation = { case: 'D3-source-first-failure-text-focus', status: 'observed-API', before, returned, error, after: state(mixed) };
    report.results.push(observation); persist();
    assert.equal(returned, false);
    assert.equal(cell.document.getText(), changedSource);
    assert.deepEqual(cell.metadata, before.cells[0].metadata);
    await vscode.commands.executeCommand('notebook.cell.edit');
    for (let i = 0; i < 40 && vscode.window.activeTextEditor?.document !== cell.document; i++) await pause(50);
    observation.cellTextEditorActive = vscode.window.activeTextEditor?.document === cell.document;
    persist();
    assert.equal(observation.cellTextEditorActive, true, 'focus must reach the cell text editor before Undo');
    await vscode.commands.executeCommand('undo'); await pause(100);
    observation.undo = state(mixed); persist();
    await vscode.commands.executeCommand('redo'); await pause(100);
    observation.redo = state(mixed); persist();
    // Record recovery separately from the applyEdit return value; never assume rollback.
    observation.undoRestoredSource = observation.undo.cells[0].source === before.cells[0].source;
    observation.redoRestoredPartialSource = observation.redo.cells[0].source === changedSource;
    observation.metadataUnchangedThroughHistory = [observation.undo, observation.redo].every(s => JSON.stringify(s.cells[0].metadata) === JSON.stringify(before.cells[0].metadata));
    report.status = 'completed'; report.finishedAt = new Date().toISOString(); persist();
  } catch (e) { report.status = 'failed'; report.error = String(e); report.stack = e.stack; persist(); throw e; }
}
module.exports = { run };
