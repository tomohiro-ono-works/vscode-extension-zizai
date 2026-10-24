'use strict';
// Standard registered Notebook commands and public vscode API only.
const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { notebook } = require('./fixtures.cjs');
const { identities, encode, patchMetadata } = require('./model.cjs');
const id = identities();
const pause = ms => new Promise(r => setTimeout(r, ms));
const text = cell => cell.outputs.flatMap(o => o.items).filter(i => /text|stdout|stderr/.test(i.mime)).map(i => Buffer.from(i.data).toString('utf8')).join('');
function state(doc) {
  return { object: id(doc), version: doc.version, dirty: doc.isDirty, closed: doc.isClosed,
    cells: doc.getCells().map(c => ({ object: id(c), textObject: id(c.document), uri: c.document.uri.toString(), index: c.index,
      source: c.document.getText(), metadata: c.metadata, summary: c.executionSummary, syntheticTextOutput: text(c) })) };
}
async function waitFor(predicate, timeoutMs, label) {
  const start = Date.now();
  while (!predicate()) { if (Date.now() - start >= timeoutMs) throw new Error(`Timeout: ${label} (${timeoutMs}ms)`); await pause(100); }
}
async function run() {
  const build = JSON.parse(fs.readFileSync(path.join(__dirname, 'build.local.json'), 'utf8'));
  const file = path.join(build.root, 'results/task-002-01/execution-auto-result.local.json');
  const report = { status: 'running', at: new Date().toISOString(), vscode: vscode.version, build,
    scope: 'TASK-002-01 D4/D5 standard command execution; not a custom Run All/kernel', waitSeconds: 20, manualFixtureWaitSeconds: 90,
    results: [], commands: [], unavailable: ['submitted source', 'internal execution ID', 'kernel stop completion from public summary alone'] };
  const persist = () => fs.writeFileSync(file, encode(report) + '\n');
  persist();
  let api;
  async function open(name, suffix) {
    const target = path.join(api.workspace, `AUTO-${name}-${suffix}-${Date.now()}.ipynb`);
    const data = notebook(name);
    for (const cell of data.cells) cell.source = cell.source.map(s => s.replace('time.sleep(90)', 'time.sleep(20)'));
    fs.writeFileSync(target, JSON.stringify(data) + '\n');
    const doc = await vscode.workspace.openNotebookDocument(vscode.Uri.file(target));
    const editor = await vscode.window.showNotebookDocument(doc, { preview: false });
    editor.selections = [new vscode.NotebookRange(0, 1)];
    await vscode.commands.executeCommand('notebook.cell.quitEdit');
    await pause(150);
    return { doc, editor, target };
  }
  function execute(command) {
    const record = { command, requestedAt: new Date().toISOString(), settled: false };
    report.commands.push(record); persist();
    // Execute is the standard VS Code/Jupyter command. Do not await completion
    // before making the diagnostic edit during execution.
    const promise = vscode.commands.executeCommand(command).then(value => {
      Object.assign(record, { settled: true, finishedAt: new Date().toISOString(), value }); persist();
    }, e => { Object.assign(record, { settled: true, finishedAt: new Date().toISOString(), error: String(e) }); persist(); });
    return { record, promise };
  }
  async function saved(doc) {
    const returned = await doc.save();
    return { returned, json: JSON.parse(fs.readFileSync(doc.uri.fsPath, 'utf8')) };
  }
  try {
    api = await vscode.extensions.getExtension('zizai-lab.task-002-01-notebook-host-api-probe').activate();
    report.rawLog = api.logFile;
    report.localConfiguration = { confirmDeleteRunningCell: vscode.workspace.getConfiguration('notebook').get('confirmDeleteRunningCell'), undoRedoPerCell: vscode.workspace.getConfiguration('notebook').get('undoRedoPerCell') };
    assert.equal(report.localConfiguration.confirmDeleteRunningCell, false, 'disable the running-cell deletion prompt in this isolated automation profile only');
    const commands = await vscode.commands.getCommands(true);
    report.standardCommands = commands.filter(c => /^(notebook\.(execute|cell.execute|cell.delete|cell.quitEdit)|workbench.action.focusActiveEditorGroup)$/.test(c));
    for (const command of ['notebook.execute', 'notebook.cell.execute', 'notebook.cell.delete']) assert.ok(commands.includes(command), command);
    persist();
    {
      const { doc } = await open('D4-environment', 'kernel-check');
      const cell = doc.cellAt(0), observation = { case: 'environment-selected-standard-kernel', before: state(doc) };
      report.results.push(observation); persist();
      execute('notebook.cell.execute');
      await waitFor(() => /"ipykernel"/.test(text(cell)), 45000, 'standard kernel environment output; a kernel picker may require UI');
      observation.after = state(doc); observation.saved = await saved(doc); observation.status = 'observed'; persist();
    }
    for (const mode of ['metadata-setting', 'source-changed']) {
      const { doc } = await open('D4-running-edit', mode);
      const cell = doc.cellAt(0), observation = { case: 'D4-running-' + mode, before: state(doc) };
      report.results.push(observation); persist();
      execute('notebook.cell.execute');
      await waitFor(() => text(cell).includes('running-edit started'), 30000, 'D4 started');
      observation.beforeMutation = state(doc); observation.mutationAt = new Date().toISOString();
      const edit = new vscode.WorkspaceEdit();
      if (mode === 'metadata-setting') edit.set(doc.uri, [vscode.NotebookEdit.updateCellMetadata(cell.index, patchMetadata(cell.metadata, { committed: Date.now() }))]);
      else edit.replace(cell.document.uri, new vscode.Range(0, 0, cell.document.lineCount, 0), "print('diagnostic CHANGED current source')\n");
      observation.returned = await vscode.workspace.applyEdit(edit); observation.afterMutation = state(doc); persist();
      await waitFor(() => text(cell).includes('running-edit finished') && cell.executionSummary?.timing?.endTime !== undefined, 35000, 'D4 original standard execution finished');
      observation.after = state(doc); observation.saved = await saved(doc); observation.status = 'observed-standard-execution'; persist();
    }
    for (const name of ['D5-queued-delete', 'D5-running-delete', 'D5-queued-close', 'D5-running-close']) {
      const { doc, editor, target } = await open(name, 'standard');
      const queued = name.includes('queued'), close = name.includes('close');
      const blocker = doc.cellAt(0), cell = doc.cellAt(queued ? 1 : 0);
      const observation = { case: name, before: state(doc), savedBefore: await saved(doc) };
      report.results.push(observation); persist();
      const request = execute(queued ? 'notebook.execute' : 'notebook.cell.execute');
      await waitFor(() => text(blocker).includes('started'), 30000, name + ' started');
      editor.selections = [new vscode.NotebookRange(cell.index, cell.index + 1)];
      observation.beforeRemoval = state(doc); observation.removalAt = new Date().toISOString();
      // Avoid a save dialog after execution has changed persistent outputs.
      observation.savedBeforeRemoval = await saved(doc);
      const logStart = fs.readFileSync(api.logFile, 'utf8').trim().split('\n').length;
      await vscode.commands.executeCommand('task00201.arm');
      let current = doc;
      if (close) {
        const tabs = vscode.window.tabGroups.all.flatMap(g => g.tabs).filter(t => t.input instanceof vscode.TabInputNotebook && t.input.uri.toString() === doc.uri.toString());
        observation.tabsBefore = tabs.length;
        observation.closeReturned = await vscode.window.tabGroups.close(tabs, true);
        observation.oldClosedAfterTabClose = doc.isClosed;
        current = await vscode.workspace.openNotebookDocument(vscode.Uri.file(target));
        await vscode.window.showNotebookDocument(current, { preview: false });
        observation.reopenAt = new Date().toISOString(); observation.sameNotebookObjectOnReopen = current === doc;
        observation.sameCellObjectOnReopen = current.getCells().includes(cell); observation.afterReopen = state(current);
      } else {
        await vscode.commands.executeCommand('notebook.cell.quitEdit');
        await vscode.commands.executeCommand('notebook.cell.delete');
        await waitFor(() => !doc.getCells().includes(cell), 3000, name + ' target removed');
        observation.afterDelete = state(doc); observation.removed = { object: id(cell), uri: cell.document.uri.toString(), textClosed: cell.document.isClosed, index: cell.index };
      }
      persist();
      let guard;
      await waitFor(() => {
        guard = fs.readFileSync(api.logFile, 'utf8').trim().split('\n').slice(logStart).map(JSON.parse).find(x => x.kind === 'local-delay.guard');
        return Boolean(guard);
      }, 20000, name + ' local guard');
      observation.localGuard = { at: guard.at, seq: guard.seq, valid: guard.valid, invalidated: guard.invalidated };
      assert.equal(guard.valid, false, 'old local diagnostic request must not apply');
      assert.ok(current.getCells().every(c => c.metadata.metadata?.task00201Diagnostic?.delayedLocalToken === undefined));
      // Wait for the original 20s interval and command settlement, but do not
      // convert command settlement or cell disposal into a kernel-stop claim.
      await pause(7000);
      observation.standardCommand = request.record;
      observation.oldTargetAfter = { object: id(cell), summary: cell.executionSummary, source: cell.document.getText(), textClosed: cell.document.isClosed, output: text(cell) };
      observation.originalDocumentAfter = state(doc); observation.currentDocumentAfter = state(current);
      observation.kernelStopped = 'not-observable-from-these-events';
      observation.savedAfter = await saved(current); observation.status = 'observed-standard-execution'; persist();
    }
    report.status = 'completed'; report.finishedAt = new Date().toISOString(); persist();
  } catch (e) { report.status = 'failed'; report.error = String(e); report.stack = e.stack; persist(); throw e; }
}
module.exports = { run };
