// TASK-001-01 THROWAWAY PROTOTYPE. Cell footer, no HTML or Python execution.
const vscode = require('vscode');
const { createState } = require('./toolbar-state.cjs');
const { readRole } = require('./role.cjs');
function activate(context) {
  let disposed = false;
  const state = createState();
  const changed = new vscode.EventEmitter();
  const events = [];
  // Do not create an OutputChannel: diagnostics use console + an explicit JSON report.
  const emit = (event, data = {}) => {
    if (disposed) return;
    const entry = { time: new Date().toISOString(), event, mode: 'statusbar', ...data };
    events.push(entry);
    if (events.length > 200) events.shift();
    console.info(JSON.stringify(entry));
  };
  const refresh = () => {
    if (disposed) return;
    state.refresh(vscode.workspace.notebookDocuments);
    changed.fire();
  };
  const provider = {
    onDidChangeCellStatusBarItems: changed.event,
    provideCellStatusBarItems(cell, token) {
      if (disposed || token.isCancellationRequested) return;
      state.refresh(vscode.workspace.notebookDocuments);
      const choice = state.selection(cell);
      if (!choice) return;
      const item = new vscode.NotebookCellStatusBarItem(
        `Zizai: ${choice === 'python' ? '通常Python' : '架空コネクタ'} $(chevron-down)`,
        vscode.NotebookCellStatusBarAlignment.Right
      );
      // Built-in language picker is -MAX_SAFE_INTEGER in the inspected VS Code version.
      item.priority = -Number.MAX_SAFE_INTEGER + 2;
      item.tooltip = 'Zizai（試作）: このセルの処理を選択。Pythonは実行しません';
      item.command = { command: 'zizaiProbe.pickCellMode', title: 'Zizai（試作）', arguments: [cell] };
      return item;
    }
  };
  async function select(cell) {
    if (disposed) return;
    state.refresh(vscode.workspace.notebookDocuments);
    if (!state.selection(cell)) return;
    const result = await vscode.window.showQuickPick([
      { label: '通常Python（試作）', choice: 'python' },
      { label: '架空コネクタ（試作）', choice: 'fake' }
    ], { title: `Zizai（試作）: セル${cell.index + 1}`, placeHolder: 'このセルの処理を選択' });
    if (disposed || !result) return;
    state.refresh(vscode.workspace.notebookDocuments);
    if (!state.select(cell, result.choice)) { emit('stale-selection-rejected'); return; }
    emit('selected', { cell: cell.index, selected: result.choice });
    changed.fire();
  }
  async function report() {
    if (disposed) return;
    state.refresh(vscode.workspace.notebookDocuments);
    const version = id => vscode.extensions.getExtension(id)?.packageJSON.version ?? 'not installed';
    emit('snapshot', {
      app: vscode.env.appName, vscodeApiVersion: vscode.version, platform: process.platform,
      extensionHostNode: process.version, probeVersion: context.extension.packageJSON.version,
      pythonExtension: version('ms-python.python'), jupyterExtension: version('ms-toolsai.jupyter'),
      showCellStatusBar: vscode.workspace.getConfiguration('notebook').get('showCellStatusBar'),
      notebooks: vscode.workspace.notebookDocuments.filter(nb => nb.getCells().some(cell => readRole(cell.metadata))).map(nb => ({
        type: nb.notebookType, cells: nb.getCells().map(cell => ({
          index: cell.index, role: readRole(cell.metadata) ?? 'python', selected: state.selection(cell) ?? null,
          outputTypes: cell.outputs.flatMap(output => output.items.map(item => item.mime)),
          executionOrder: cell.executionSummary?.executionOrder ?? null
        }))
      }))
    });
    const doc = await vscode.workspace.openTextDocument({ language: 'json', content: JSON.stringify(events, null, 2) });
    if (!disposed) await vscode.window.showTextDocument(doc, { preview: false });
  }
  context.subscriptions.push(
    { dispose() { disposed = true; } }, changed,
    vscode.commands.registerCommand('zizaiProbe.pickCellMode', select),
    vscode.commands.registerCommand('zizaiProbe.reportStatusBar', report),
    vscode.commands.registerCommand('zizaiProbe.empty', async () => {
      const uri = vscode.Uri.joinPath(context.extensionUri, 'fixtures', 'empty.ipynb');
      const notebook = await vscode.workspace.openNotebookDocument(uri);
      if (!disposed) await vscode.window.showNotebookDocument(notebook);
      refresh();
    }),
    vscode.notebooks.registerNotebookCellStatusBarItemProvider('jupyter-notebook', provider),
    vscode.workspace.onDidOpenNotebookDocument(refresh),
    vscode.workspace.onDidCloseNotebookDocument(refresh),
    vscode.workspace.onDidChangeNotebookDocument(refresh)
  );
  emit('activated', { probeVersion: context.extension.packageJSON.version });
  refresh();
}
module.exports = { activate };
