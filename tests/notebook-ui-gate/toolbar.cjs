// TASK-001-01 PROTOTYPE. Standard cell toolbar only; no HTML or proposed APIs.
const vscode = require('vscode');
const { readRole } = require('./role.cjs');
const { createState } = require('./toolbar-state.cjs');

function activate(context) {
  const log = vscode.window.createOutputChannel('Zizai TASK-001-01 Toolbar');
  const state = createState();
  const emit = (event, data = {}) => log.appendLine(JSON.stringify({ time: new Date().toISOString(), event, ...data }));
  const refresh = async () => {
    const uris = state.refresh(vscode.workspace.notebookDocuments);
    await vscode.commands.executeCommand('setContext', 'zizaiProbe.toolbarCells', uris);
    emit('toolbar-context-ready', { eligibleCells: uris.length });
  };
  const update = () => { refresh().catch(error => emit('context-error', { message: String(error) })); };
  function select(cell, choice) {
    // The toolbar supplies its own cell argument. Never use the active selection
    // as a fallback: clicking another cell must not change the active cell.
    state.refresh(vscode.workspace.notebookDocuments);
    if (!state.select(cell, choice)) {
      emit('selection-rejected', { choice });
      return;
    }
    emit('selected', { cell: cell.index, selected: choice });
    vscode.window.showInformationMessage(`試作: セル${cell.index + 1}で${choice === 'python' ? '通常Python' : '架空コネクタ'}を選択`);
  }
  function report() {
    const extensionVersion = id => vscode.extensions.getExtension(id)?.packageJSON.version ?? 'not installed';
    emit('snapshot', {
      mode: 'toolbar', app: vscode.env.appName, vscodeApiVersion: vscode.version,
      platform: process.platform, extensionHostNode: process.version,
      probeVersion: context.extension.packageJSON.version,
      pythonExtension: extensionVersion('ms-python.python'), jupyterExtension: extensionVersion('ms-toolsai.jupyter'),
      notebooks: vscode.workspace.notebookDocuments.filter(nb => nb.getCells().some(cell => readRole(cell.metadata))).map(nb => ({
        type: nb.notebookType,
        cells: nb.getCells().map(cell => ({
          index: cell.index, role: readRole(cell.metadata) ?? 'python',
          selected: state.selection(cell) ?? null,
          outputTypes: cell.outputs.flatMap(output => output.items.map(item => item.mime)),
          executionOrder: cell.executionSummary?.executionOrder ?? null
        }))
      }))
    });
    log.show(true);
  }
  context.subscriptions.push(log,
    vscode.commands.registerCommand('zizaiProbe.empty', async () => {
      const uri = vscode.Uri.joinPath(context.extensionUri, 'fixtures', 'empty.ipynb');
      await vscode.window.showNotebookDocument(await vscode.workspace.openNotebookDocument(uri));
      await refresh();
    }),
    vscode.commands.registerCommand('zizaiProbe.choosePython', cell => select(cell, 'python')),
    vscode.commands.registerCommand('zizaiProbe.chooseFake', cell => select(cell, 'fake')),
    vscode.commands.registerCommand('zizaiProbe.report', report),
    vscode.workspace.onDidOpenNotebookDocument(update),
    vscode.workspace.onDidCloseNotebookDocument(update),
    vscode.workspace.onDidChangeNotebookDocument(event => {
      if (event.contentChanges.length || event.cellChanges.some(change => change.metadata !== undefined || change.document !== undefined)) update();
      if (event.notebook.getCells().some(cell => readRole(cell.metadata))) {
        for (const change of event.cellChanges) {
          if (change.outputs !== undefined || change.executionSummary !== undefined) {
            emit('cell-changed', { cell: change.cell.index, outputs: change.cell.outputs.length, selected: state.selection(change.cell) ?? null });
          }
        }
      }
    }),
    { dispose: () => { void vscode.commands.executeCommand('setContext', 'zizaiProbe.toolbarCells', []); } }
  );
  emit('activated', { mode: 'toolbar' });
  update();
}
module.exports = { activate };
