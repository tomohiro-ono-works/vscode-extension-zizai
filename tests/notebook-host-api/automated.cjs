'use strict';
// Public API diagnostics for D2/D3/D6. No Python execution or custom controller.
const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { notebook } = require('./fixtures.cjs');
const { patchMetadata, encode, identities } = require('./model.cjs');
const id = identities();
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
let api, reportFile;
const report = { startedAt: new Date().toISOString(), scope: 'D2/D3/D6 public API observations; product acceptance separate', results: [] };
function persist() { fs.writeFileSync(reportFile, encode(report) + '\n'); }
function state(doc) {
  return { object: id(doc), version: doc.version, dirty: doc.isDirty, closed: doc.isClosed, cells: doc.getCells().map(c => ({ object: id(c), textObject: id(c.document), index: c.index, uri: c.document.uri.toString(), source: c.document.getText(), metadata: c.metadata, summary: c.executionSummary })) };
}
function record(caseId, value) { report.results.push({ case: caseId, at: new Date().toISOString(), ...value }); persist(); }
async function open(name) {
  const file = path.join(api.workspace, `AUTO-${name}-${Date.now()}.ipynb`);
  fs.writeFileSync(file, JSON.stringify(notebook(name)) + '\n');
  const doc = await vscode.workspace.openNotebookDocument(vscode.Uri.file(file));
  const editor = await vscode.window.showNotebookDocument(doc, { preview: false });
  editor.selections = [new vscode.NotebookRange(0, 1)];
  await vscode.commands.executeCommand('notebook.cell.quitEdit');
  return { doc, file };
}
async function undoRedo(doc) {
  await vscode.commands.executeCommand('notebook.cell.quitEdit');
  await vscode.commands.executeCommand('undo');
  await pause(30);
  const undo = state(doc);
  await vscode.commands.executeCommand('redo');
  await pause(30);
  return { undo, redo: state(doc) };
}
async function apply(edit) {
  let result, error;
  try { result = await vscode.workspace.applyEdit(edit); } catch (e) { error = String(e); }
  await pause(20);
  return { result, error };
}
async function metadata(doc, cell, value) {
  const edit = new vscode.WorkspaceEdit();
  edit.set(doc.uri, [vscode.NotebookEdit.updateCellMetadata(cell.index, patchMetadata(cell.metadata, value))]);
  return apply(edit);
}
async function run() {
  const build = JSON.parse(fs.readFileSync(path.join(__dirname, 'build.local.json'), 'utf8'));
  reportFile = path.join(build.root, 'results/task-002-01/automated-result.local.json');
  report.status = 'running'; report.vscode = vscode.version; report.build = build; persist();
  try {
    api = await vscode.extensions.getExtension('zizai-lab.task-002-01-notebook-host-api-probe').activate();
    report.rawLog = api.logFile; persist();
    const commands = await vscode.commands.getCommands(true);
    assert.ok(commands.includes('notebook.cell.quitEdit'));
    {
      const { doc, file } = await open('D2-save');
      const before = state(doc), cell = doc.cellAt(0);
      const returned = await metadata(doc, cell, { draft: 7 });
      const after = state(doc);
      assert.equal(returned.result, true);
      assert.equal(cell.document.getText(), before.cells[0].source);
      assert.equal(cell.metadata.metadata.outsideDiagnosticOwner.sentinel, 'keep-D2');
      assert.equal(doc.isDirty, true);
      assert.equal(await doc.save(), true);
      const saved = JSON.parse(fs.readFileSync(file, 'utf8'));
      assert.equal(saved.cells[0].metadata.task00201Diagnostic.draft, 7);
      assert.equal(saved.metadata.outsideNotebookOwner.sentinel, 'preserve-notebook');
      const tabs = vscode.window.tabGroups.all.flatMap(g => g.tabs).filter(t => t.input instanceof vscode.TabInputNotebook && t.input.uri.toString() === doc.uri.toString());
      await vscode.window.tabGroups.close(tabs, true);
      await pause(100);
      const closedAtReopen = doc.isClosed;
      const reopened = await vscode.workspace.openNotebookDocument(vscode.Uri.file(file));
      await vscode.window.showNotebookDocument(reopened);
      assert.equal(reopened.cellAt(0).metadata.metadata.task00201Diagnostic.draft, 7);
      record('D2', { status: 'passed-API', before, returned, after, saved, closedAtReopen, sameObjectOnReopen: reopened === doc, reopened: state(reopened), standardCtrlSUI: 'not-observed-in-automation' });
    }
    for (const mode of ['source-first-success', 'metadata-first-success', 'source-first-failure', 'metadata-first-failure']) {
      const { doc } = await open('D3-mixed');
      const cell = doc.cellAt(0), before = state(doc), edit = new vscode.WorkspaceEdit();
      const source = `# AUTO D3 ${mode}\nfictional_value = 20\n`;
      const text = () => {
        edit.replace(cell.document.uri, new vscode.Range(0, 0, cell.document.lineCount, 0), source);
        if (mode === 'metadata-first-failure') edit.insert(vscode.Uri.file(path.join(api.workspace, 'missing-D3-directory', 'missing.txt')), new vscode.Position(0, 0), 'intentional failure');
      };
      const meta = () => edit.set(doc.uri, [vscode.NotebookEdit.updateCellMetadata(mode === 'source-first-failure' ? doc.cellCount + 100 : cell.index, patchMetadata(cell.metadata, { mixed: mode }))]);
      if (mode.startsWith('source-first')) { text(); meta(); } else { meta(); text(); }
      const returned = await apply(edit), after = state(doc);
      if (mode.endsWith('-success')) {
        assert.equal(returned.result, true);
        assert.equal(cell.document.getText(), source);
        assert.equal(cell.metadata.metadata.task00201Diagnostic.mixed, mode);
      }
      record('D3-' + mode, { status: mode.endsWith('-failure') && returned.result !== false && !returned.error ? 'failure-injection-not-effective' : 'observed-API', before, returned, after, ...(await undoRedo(doc)) });
    }
    for (const mode of ['existing-same-20', 'existing-change-20', 'new-same-20', 'new-change-20']) {
      const { doc } = await open('D6-burst');
      const beforeInsertion = state(doc);
      let cell = doc.cellAt(0);
      if (mode.startsWith('new-')) {
        const data = new vscode.NotebookCellData(vscode.NotebookCellKind.Code, '# AUTO D6 new\n', 'python');
        data.metadata = { metadata: { task00201Diagnostic: { burst: 0 }, outsideDiagnosticOwner: { sentinel: 'keep-new-D6' } } };
        const edit = new vscode.WorkspaceEdit();
        edit.set(doc.uri, [vscode.NotebookEdit.insertCells(doc.cellCount, [data])]);
        assert.equal((await apply(edit)).result, true);
        cell = doc.cellAt(doc.cellCount - 1);
      }
      const before = state(doc), start = performance.now();
      let events = 0, lastTick = start, maxTickGapMs = 0, ticks = 0;
      const subscription = vscode.workspace.onDidChangeNotebookDocument(e => { if (e.notebook === doc) events++; });
      const timer = setInterval(() => { const now = performance.now(); maxTickGapMs = Math.max(maxTickGapMs, now - lastTick); lastTick = now; ticks++; }, 50);
      const returns = [];
      try { for (let i = 0; i < 20; i++) returns.push(await metadata(doc, cell, { burst: mode.includes('-same-') ? 0 : i + 1 })); }
      finally { clearInterval(timer); subscription.dispose(); }
      const elapsedMs = performance.now() - start, after = state(doc);
      const history = await undoRedo(doc);
      const savedResult = await doc.save();
      record('D6-' + mode, { status: 'observed-API', beforeInsertion, before, sent: returns.length, returns, events, after, ...history, savedResult, elapsedMs, ticks, maxTickGapMs, loggingAnd20msSettlingDelayIncluded: true, threshold: 'not-defined', userUIResponsiveness: 'not-observed-in-automation' });
    }
    report.status = 'completed'; report.finishedAt = new Date().toISOString(); persist();
  } catch (e) { report.status = 'failed'; report.error = String(e); report.stack = e.stack; persist(); throw e; }
}
module.exports = { run };
