// TASK-001-01 throwaway probe, not production Zizai.
// No controller, serializer, output injection, source edits, or metadata writes.
const vscode = require('vscode');
const { randomBytes } = require('node:crypto');
const { mode } = require('./mode.json');
const { readRole } = require('./role.cjs');

function activate(context) {
  const log = vscode.window.createOutputChannel('Zizai TASK-001-01 Probe');
  context.subscriptions.push(log);
  const entries = new Map(); // TextEditor -> inset, never fabricate a TextEditor
  const states = new Map(); // URI -> ephemeral UI values, not a metadata contract
  const attempted = new WeakSet();
  const emit = (event, data = {}) => log.appendLine(JSON.stringify({ time: new Date().toISOString(), event, ...data }));
  const isProbe = notebook => notebook.getCells().some(cell => role(cell) !== undefined);
  function role(cell) {
    return readRole(cell.metadata);
  }
  function cellFor(editor) {
    for (const notebookEditor of vscode.window.visibleNotebookEditors) {
      if (!isProbe(notebookEditor.notebook)) continue;
      const cell = notebookEditor.notebook.getCells().find(item => item.document.uri.toString() === editor.document.uri.toString());
      if (cell) return cell;
    }
  }
  function attach(editor, cell) {
    if (entries.has(editor) || attempted.has(editor)) return;
    attempted.add(editor);
    const kind = cell ? role(cell) ?? 'python' : 'text-control';
    const key = editor.document.uri.toString();
    const initial = states.get(key) ?? { mode: kind === 'action' ? 'fake' : 'python', value: '' };
    try {
      // Proposed API only; -1 maps to the zone before the first source line.
      const inset = vscode.window.createWebviewTextEditorInset(editor, -1, 11, {
        enableScripts: true, localResourceRoots: [context.extensionUri]
      });
      entries.set(editor, inset);
      const tag = { kind, cell: cell?.index ?? null };
      emit('inset-requested', tag); // request is NOT evidence that it rendered
      context.subscriptions.push(inset, inset.onDidDispose(() => {
        entries.delete(editor);
        attempted.delete(editor); // allow a later visibility/focus event to retry
        emit('inset-disposed', tag);
      }), inset.webview.onDidReceiveMessage(message => {
        if (message?.type === 'ready') emit('inset-ready', tag);
        if (message?.type === 'state' && ['python', 'fake'].includes(message.state?.mode) && typeof message.state?.value === 'string') {
          states.set(key, { mode: message.state.mode, value: message.state.value.slice(0, 120) });
          emit('input-received', { ...tag, selected: message.state.mode }); // never log the input
        }
      }));
      const nonce = randomBytes(16).toString('hex');
      const script = inset.webview.asWebviewUri(vscode.Uri.joinPath(context.extensionUri, 'inset.mjs'));
      const initialAttribute = JSON.stringify(initial).replace(/&/g, '&amp;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      inset.webview.html = `<!doctype html><html lang="ja"><head><meta charset="UTF-8">
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src ${inset.webview.cspSource}; style-src 'nonce-${nonce}';">
        <style nonce="${nonce}">body{font-family:var(--vscode-font-family);color:var(--vscode-editor-foreground);background:var(--vscode-editor-background);padding:4px}label{display:block;margin:8px 0}input,select{color:var(--vscode-input-foreground);background:var(--vscode-input-background);border:1px solid var(--vscode-input-border);padding:3px}p{margin:2px 0}</style>
        </head><body><p>PROTOTYPE: editorInsets / Python実行とは独立</p>
        <div id="probe" data-initial='${initialAttribute}'></div>
        <script type="module" src="${script}"></script></body></html>`;
    } catch (error) {
      emit('inset-error', { kind, message: String(error) });
    }
  }
  function reconcile() {
    if (mode !== 'insets') return;
    for (const editor of vscode.window.visibleTextEditors) {
      const cell = cellFor(editor);
      const textControl = editor.document.uri.toString() === vscode.Uri.joinPath(context.extensionUri, 'fixtures', 'inset-control.py').toString();
      if (cell && cell.kind === vscode.NotebookCellKind.Code && cell.document.languageId === 'python' && role(cell) !== 'init') attach(editor, cell);
      else if (textControl) attach(editor);
    }
  }
  function report() {
    const extensionVersion = id => vscode.extensions.getExtension(id)?.packageJSON.version ?? 'not installed';
    emit('snapshot', {
      mode, app: vscode.env.appName, vscodeApiVersion: vscode.version,
      platform: process.platform, extensionHostNode: process.version, remote: vscode.env.remoteName ?? null,
      probeVersion: context.extension.packageJSON.version,
      pythonExtension: extensionVersion('ms-python.python'), jupyterExtension: extensionVersion('ms-toolsai.jupyter'),
      insetFunctionExposed: typeof vscode.window.createWebviewTextEditorInset === 'function',
      // Function presence alone does NOT mean proposed API authorization or support.
      visibleEditors: vscode.window.visibleTextEditors.map(editor => ({
        scheme: editor.document.uri.scheme, language: editor.document.languageId,
        cell: cellFor(editor)?.index ?? null, hasInsetRequest: entries.has(editor)
      })),
      notebooks: vscode.window.visibleNotebookEditors.filter(editor => isProbe(editor.notebook)).map(editor => ({
        type: editor.notebook.notebookType,
        cells: editor.notebook.getCells().map(cell => ({
          index: cell.index, role: role(cell) ?? 'python', language: cell.document.languageId,
          outputTypes: cell.outputs.flatMap(output => output.items.map(item => item.mime)),
          executionOrder: cell.executionSummary?.executionOrder ?? null
        }))
      }))
    });
    log.show(true);
  }
  for (const [id, file] of [['empty', 'empty.ipynb'], ['renderer', 'renderer-control.ipynb'], ['text', 'inset-control.py']]) {
    context.subscriptions.push(vscode.commands.registerCommand(`zizaiProbe.${id}`, async () => {
      const uri = vscode.Uri.joinPath(context.extensionUri, 'fixtures', file);
      if (file.endsWith('.ipynb')) await vscode.window.showNotebookDocument(await vscode.workspace.openNotebookDocument(uri));
      else await vscode.window.showTextDocument(uri);
      reconcile();
    }));
  }
  context.subscriptions.push(vscode.commands.registerCommand('zizaiProbe.report', report));
  context.subscriptions.push(vscode.notebooks.registerNotebookCellStatusBarItemProvider('jupyter-notebook', {
    provideCellStatusBarItems(cell) {
      if (!isProbe(cell.notebook) || role(cell) === 'init' || cell.kind !== vscode.NotebookCellKind.Code) return [];
      const item = new vscode.NotebookCellStatusBarItem('SPIKE: 文字列／コマンドのみ', vscode.NotebookCellStatusBarAlignment.Left);
      item.command = 'zizaiProbe.report';
      item.tooltip = '標準Status Barの対照実験。セル内フォームではありません。';
      return [item];
    }
  }));
  for (const event of [vscode.window.onDidChangeVisibleTextEditors, vscode.window.onDidChangeActiveTextEditor,
    vscode.window.onDidChangeVisibleNotebookEditors, vscode.window.onDidChangeNotebookEditorSelection]) {
    context.subscriptions.push(event(reconcile));
  }
  context.subscriptions.push(vscode.workspace.onDidChangeNotebookDocument(event => {
    if (!isProbe(event.notebook)) return;
    for (const change of event.cellChanges) {
      if (change.outputs !== undefined || change.executionSummary !== undefined) {
        emit('cell-changed', { cell: change.cell.index, outputs: change.cell.outputs.length, executionOrder: change.cell.executionSummary?.executionOrder ?? null });
      }
    }
  }), vscode.workspace.onDidCloseNotebookDocument(notebook => {
    for (const cell of notebook.getCells()) states.delete(cell.document.uri.toString());
  }));
  emit('activated', { mode });
  reconcile();
}
module.exports = { activate };
