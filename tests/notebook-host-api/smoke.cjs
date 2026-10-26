'use strict';
// Real installed VS Code test runner. This checks the harness, not D1-D6 acceptance.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vscode = require('vscode');
async function smoke() {
  const ext = vscode.extensions.getExtension('zizai-lab.task-002-01-notebook-host-api-probe');
  assert.ok(ext, 'diagnostic extension discovered');
  const api = await ext.activate();
  const file = path.join(api.workspace, `SMOKE-${Date.now()}.ipynb`);
  fs.writeFileSync(file, JSON.stringify(require('./fixtures.cjs').notebook('D1-structure')));
  const doc = await vscode.workspace.openNotebookDocument(vscode.Uri.file(file));
  await vscode.window.showNotebookDocument(doc);
  assert.equal(doc.cellCount, 3);
  assert.equal(doc.cellAt(0).metadata.metadata.task00201Diagnostic.label, 'A');
  assert.equal(doc.cellAt(0).metadata.metadata.outsideDiagnosticOwner.sentinel, 'keep-A');
  const source = doc.cellAt(0).document.getText();
  const registered = await vscode.commands.getCommands(true);
  for (const command of require('./package.json').contributes.commands) assert.ok(registered.includes(command.command), command.command);
  await vscode.commands.executeCommand('task00201.metadata');
  assert.equal(doc.cellAt(0).document.getText(), source, 'diagnostic metadata command preserves source');
  assert.equal(doc.cellAt(0).metadata.metadata.task00201Diagnostic.draft, 1);
  assert.equal(doc.cellAt(0).metadata.metadata.outsideDiagnosticOwner.sentinel, 'keep-A');
  assert.equal(doc.isDirty, true);
  assert.equal(await doc.save(), true);
  const saved = JSON.parse(fs.readFileSync(file, 'utf8'));
  assert.equal(saved.cells[0].metadata.task00201Diagnostic.draft, 1);
  await vscode.commands.executeCommand('task00201.arm');
  const tabs = vscode.window.tabGroups.all.flatMap(group => group.tabs).filter(tab => tab.input instanceof vscode.TabInputNotebook && tab.input.uri.toString() === doc.uri.toString());
  assert.equal(tabs.length, 1, 'target notebook tab exists');
  assert.equal(await vscode.window.tabGroups.close(tabs, true), true, 'close the specific notebook tab');
  // Closing the last notebook editor may dispose the document asynchronously.
  const deadline = Date.now() + 5000;
  while (!doc.isClosed && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 20));
  const closedAfterTabClose = doc.isClosed;
  const remainingTabs = vscode.window.tabGroups.all.flatMap(group => group.tabs).filter(tab => tab.input instanceof vscode.TabInputNotebook && tab.input.uri.toString() === doc.uri.toString());
  assert.equal(remainingTabs.length, 0, 'target tab actually closed');
  const reopened = await vscode.workspace.openNotebookDocument(vscode.Uri.file(file));
  await vscode.window.showNotebookDocument(reopened);
  assert.equal(reopened.cellAt(0).metadata.metadata.task00201Diagnostic.draft, 1);
  const guardDeadline = Date.now() + 20000;
  while (!fs.readFileSync(api.logFile, 'utf8').includes('"kind":"local-delay.guard"') && Date.now() < guardDeadline) await new Promise(resolve => setTimeout(resolve, 100));
  api.snapshot();
  const events = fs.readFileSync(api.logFile, 'utf8').trim().split('\n').map(JSON.parse);
  assert.ok(events.some(e => e.kind === 'notebook.open'));
  assert.ok(events.some(e => e.kind === 'environment'));
  assert.ok(events.some(e => e.kind === 'notebook.save'));
  assert.ok(events.some(e => e.kind === 'notebook.tabClosed'));
  const guard = events.find(e => e.kind === 'local-delay.guard');
  assert.ok(guard, 'delayed local guard reported');
  assert.equal(guard.valid, false, 'last tab close invalidates the local request even if document is reused');
  assert.equal(reopened.cellAt(0).metadata.metadata.task00201Diagnostic.delayedLocalToken, undefined);
  if (closedAfterTabClose) assert.ok(events.some(e => e.kind === 'notebook.close'));
  assert.ok(events.some(e => e.kind === 'snapshot' && e.notebooks.some(n => n.cells.length === 3)));
  const report = { status: 'passed', harnessOnly: true, vscode: vscode.version, cells: reopened.cellCount, commands: require('./package.json').contributes.commands.length, metadataCommand: true, savedJsonCapture: true, tabClosed: remainingTabs.length === 0, closedAfterTabClose, documentCloseObserved: events.some(e => e.kind === 'notebook.close'), reopenedSameObject: reopened === doc, delayedLocalUpdateRejected: guard.valid === false, closeWaitLimitMs: 5000, logFile: api.logFile, at: new Date().toISOString() };
  fs.writeFileSync(path.join(api.workspace, '../smoke-result.local.json'), JSON.stringify(report, null, 2) + '\n');
  console.log('TASK-002-01 smoke passed: ' + JSON.stringify(report));
}
async function run() {
  const build = JSON.parse(fs.readFileSync(path.join(__dirname, 'build.local.json'), 'utf8'));
  const report = path.join(build.workspace, '../smoke-result.local.json');
  fs.writeFileSync(report, JSON.stringify({ status: 'running', at: new Date().toISOString() }));
  try { await smoke(); }
  catch (error) {
    fs.writeFileSync(report, JSON.stringify({ status: 'failed', error: String(error), stack: error.stack, at: new Date().toISOString() }, null, 2));
    throw error;
  }
}
module.exports = { run };
