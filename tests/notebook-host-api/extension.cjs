'use strict';
// Diagnostic instrumentation only. No kernel/controller, execution ID or internal IDE modules.
const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { KEY, identities, patchMetadata, encode, validTarget, within } = require('./model.cjs');
const { cases, notebook: makeNotebook } = require('./fixtures.cjs');

function activate(context) {
  const build = JSON.parse(fs.readFileSync(path.join(__dirname, 'build.local.json'), 'utf8'));
  const session = new Date().toISOString().replace(/[:.]/g, '-') + '-' + process.pid;
  const logDir = path.join(build.root, 'logs/task-002-01', session);
  fs.mkdirSync(logDir, { recursive: true });
  const logFile = path.join(logDir, 'events.jsonl');
  const output = vscode.window.createOutputChannel('TASK-002-01 Notebook API');
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 80);
  status.command = 'task00201.snapshot';
  status.text = 'TASK-002-01: 診断ログ記録中';
  status.show();
  context.subscriptions.push(output, status);
  const id = identities();
  const observed = new Set();
  const cellHistory = new Map();
  const pending = new Set();
  let seq = 0, notebookEvents = 0, textEvents = 0, activeStep = 'startup', busy = false;
  const start = process.hrtime.bigint();
  const allowed = doc => doc?.uri.scheme === 'file' && within(build.workspace, doc.uri.fsPath) && doc.uri.fsPath.endsWith('.ipynb');
  function log(kind, value = {}) {
    fs.appendFileSync(logFile, encode({ seq: ++seq, at: new Date().toISOString(), elapsedMs: Number(process.hrtime.bigint() - start) / 1e6, step: activeStep, kind, ...value }) + '\n');
    output.appendLine(`${seq} ${kind}`);
  }
  function cellState(cell) {
    return { object: id(cell), notebookObject: id(cell.notebook), index: cell.index, uri: cell.document.uri.toString(), textObject: id(cell.document), textClosed: cell.document.isClosed, textVersion: cell.document.version, language: cell.document.languageId, source: cell.document.getText(), metadata: cell.metadata, executionSummary: cell.executionSummary, outputs: cell.outputs.map(o => ({ id: id(o), metadata: o.metadata, items: o.items.map(item => ({ mime: item.mime, bytes: item.data.byteLength, sha256: crypto.createHash('sha256').update(item.data).digest('hex') })) })) };
  }
  function track(doc) {
    observed.add(doc);
    let cells = cellHistory.get(doc);
    if (!cells) cellHistory.set(doc, cells = new Set());
    for (const cell of doc.getCells()) cells.add(cell);
  }
  function docState(doc) {
    track(doc);
    return { object: id(doc), uri: doc.uri.toString(), type: doc.notebookType, version: doc.version, dirty: doc.isDirty, closed: doc.isClosed, metadata: doc.metadata, cells: doc.getCells().map(cellState), retainedCells: [...cellHistory.get(doc)].map(cellState) };
  }
  function snapshot(label, doc) {
    log('snapshot', { label, notebookEvents, textEvents, notebooks: doc ? [docState(doc)] : [...observed].map(docState), pending: [...pending].map(p => ({ token: p.token, notebookObject: id(p.doc), cellObject: id(p.cell), invalidated: p.invalidated })) });
  }
  function selected() {
    const editor = vscode.window.activeNotebookEditor;
    if (!editor || !allowed(editor.notebook)) throw new Error('診断用Notebookを選択してください（results/task-002-01/workspace 配下のみ）。');
    const doc = editor.notebook;
    const index = editor.selections[0]?.start ?? 0;
    if (index >= doc.cellCount) throw new Error('コードセルを選択してください。');
    track(doc);
    return { doc, cell: doc.cellAt(index) };
  }
  async function apply(edit, label, doc) {
    snapshot(label + ':before', doc);
    log('apply.request', { label, entries: edit.entries().map(([uri, edits]) => ({ uri: uri.toString(), textEdits: edits.length })) });
    let result, error;
    try { result = await vscode.workspace.applyEdit(edit); } catch (e) { error = String(e); }
    log('apply.return', { label, result, error });
    snapshot(label + ':after', doc);
    return { result, error };
  }
  async function metadata(doc, cell, patch, label) {
    if (!validTarget(doc, cell, vscode.workspace.notebookDocuments)) throw new Error('対象Notebookまたはセルの寿命が終了しました。');
    const edit = new vscode.WorkspaceEdit();
    edit.set(doc.uri, [vscode.NotebookEdit.updateCellMetadata(cell.index, patchMetadata(cell.metadata, patch))]);
    return apply(edit, label, doc);
  }
  function subscribe(event, listener) { context.subscriptions.push(event(listener)); }
  subscribe(vscode.workspace.onDidOpenNotebookDocument, doc => {
    if (!allowed(doc)) return;
    track(doc); log('notebook.open', { notebook: docState(doc) });
  });
  subscribe(vscode.workspace.onDidChangeNotebookDocument, event => {
    if (!allowed(event.notebook)) return;
    notebookEvents++;
    track(event.notebook);
    log('notebook.change', {
      metadata: event.metadata,
      contentChanges: event.contentChanges.map(change => ({ range: { start: change.range.start, end: change.range.end }, added: change.addedCells.map(cellState), removed: change.removedCells.map(cellState) })),
      cellChanges: event.cellChanges.map(change => ({ cell: cellState(change.cell), fields: Object.keys(change), document: change.document ? { object: id(change.document), version: change.document.version, source: change.document.getText() } : undefined, metadata: change.metadata, outputsPresent: change.outputs !== undefined, executionSummary: change.executionSummary })),
      notebook: docState(event.notebook)
    });
  });
  subscribe(vscode.workspace.onDidChangeTextDocument, event => {
    const match = [...observed].find(doc => [...cellHistory.get(doc)].some(cell => cell.document === event.document));
    if (!match) return;
    textEvents++;
    log('text.change', { object: id(event.document), uri: event.document.uri.toString(), version: event.document.version, reason: event.reason, changes: event.contentChanges.map(change => ({ rangeOffset: change.rangeOffset, rangeLength: change.rangeLength, text: change.text })), source: event.document.getText() });
  });
  subscribe(vscode.workspace.onDidCloseTextDocument, doc => {
    if ([...cellHistory.values()].some(cells => [...cells].some(cell => cell.document === doc))) log('text.close', { object: id(doc), uri: doc.uri.toString(), closed: doc.isClosed });
  });
  subscribe(vscode.workspace.onDidCloseNotebookDocument, doc => {
    if (!allowed(doc)) return;
    for (const p of pending) if (p.doc === doc) p.invalidated = true;
    log('notebook.close', { notebook: docState(doc) });
    snapshot('close:retained-objects', doc);
  });
  // A tab can close while the public NotebookDocument remains loaded.
  // Record that separately and invalidate local probe requests even if the same
  // API document is reused when the path is reopened. This is not a product contract.
  subscribe(vscode.window.tabGroups.onDidChangeTabs, event => {
    for (const tab of event.closed) {
      if (!(tab.input instanceof vscode.TabInputNotebook)) continue;
      const uri = tab.input.uri.toString();
      const docs = [...observed].filter(doc => doc.uri.toString() === uri);
      if (!docs.length) continue;
      const stillVisible = vscode.window.tabGroups.all.some(group => group.tabs.some(other => other.input instanceof vscode.TabInputNotebook && other.input.uri.toString() === uri));
      if (!stillVisible) for (const request of pending) if (docs.includes(request.doc)) request.invalidated = true;
      log('notebook.tabClosed', { uri, stillVisible, notebooks: docs.map(docState), documentClosedIsSeparateObservation: true });
    }
  });
  subscribe(vscode.workspace.onDidSaveNotebookDocument, doc => {
    if (!allowed(doc)) return;
    const target = path.join(logDir, `${seq + 1}-saved-${path.basename(doc.uri.fsPath)}`);
    try {
      const data = fs.readFileSync(doc.uri.fsPath);
      fs.writeFileSync(target, data);
      log('notebook.save', { notebook: docState(doc), file: path.basename(target), sha256: crypto.createHash('sha256').update(data).digest('hex'), json: JSON.parse(data.toString('utf8')) });
    } catch (e) { log('save.capture.error', { error: String(e) }); }
  });
  function command(name, action, mutation = false) {
    context.subscriptions.push(vscode.commands.registerCommand(name, async (...args) => {
      if (mutation && busy) { vscode.window.showWarningMessage('前の診断更新が終了するまでお待ちください。'); return; }
      if (mutation) busy = true;
      try { return await action(...args); }
      catch (e) { log('command.error', { name, error: String(e) }); vscode.window.showErrorMessage(`TASK-002-01: ${e.message}`); }
      finally { if (mutation) busy = false; }
    }));
  }
  command('task00201.openCase', async () => {
    const name = await vscode.window.showQuickPick(Object.keys(cases), { title: 'TASK-002-01: 新しい架空データNotebookを開く' });
    if (!name) return;
    const file = path.join(build.workspace, `${name}-${Date.now()}.ipynb`);
    fs.writeFileSync(file, JSON.stringify(makeNotebook(name), null, 2) + '\n');
    activeStep = name + ':baseline';
    await vscode.window.showNotebookDocument(await vscode.workspace.openNotebookDocument(vscode.Uri.file(file)));
    snapshot('new-case');
  }, true);
  command('task00201.snapshot', async () => {
    const label = await vscode.window.showQuickPick(['baseline', 'D1-move-down', 'D1-move-up', 'D1-duplicate-down', 'D1-duplicate-up', 'D1-copy-paste', 'D1-delete', 'undo', 'redo', 'saved', 'reopened', 'execution-request-before', 'execution-request-after', 'cancel-request-before', 'cancel-request-after', 'D5-before-close-or-delete', 'observation-complete'], { title: 'TASK-002-01: 今回の操作マーカー' });
    if (!label) return;
    activeStep = label;
    snapshot(label);
    vscode.window.showInformationMessage(`TASK-002-01: ${label} 記録済み`);
  });
  command('task00201.metadata', async () => {
    const { doc, cell } = selected();
    activeStep = 'D2-metadata-only';
    await metadata(doc, cell, { draft: (cell.metadata.metadata?.[KEY]?.draft || 0) + 1 }, activeStep);
    vscode.window.showInformationMessage('TASK-002-01: metadataのみ更新。通常保存の前後を観測してください。');
  }, true);
  command('task00201.mixed', async () => {
    const mode = await vscode.window.showQuickPick(['source-first-success', 'metadata-first-success', 'source-first-failure', 'metadata-first-failure'], { title: 'D3: 追加順と意図的な失敗' });
    if (!mode) return;
    const { doc, cell } = selected();
    activeStep = 'D3-' + mode;
    const edit = new vscode.WorkspaceEdit();
    const next = '# D3 edited ' + mode + '\nfictional_value = 20\n';
    const textEdit = () => {
      edit.replace(cell.document.uri, new vscode.Range(0, 0, cell.document.lineCount, 0), next);
      if (mode === 'metadata-first-failure') edit.insert(vscode.Uri.file(path.join(build.workspace, 'intentionally-missing-directory', 'missing.txt')), new vscode.Position(0, 0), 'expected preparation failure');
    };
    const metaEdit = () => edit.set(doc.uri, [vscode.NotebookEdit.updateCellMetadata(mode === 'source-first-failure' ? doc.cellCount + 100 : cell.index, patchMetadata(cell.metadata, { mixed: mode }))]);
    if (mode.startsWith('source-first')) { textEdit(); metaEdit(); } else { metaEdit(); textEdit(); }
    const result = await apply(edit, activeStep, doc);
    vscode.window.showInformationMessage(`TASK-002-01: applyEdit=${String(result.result)}。両データの実状態を記録しました。`);
  }, true);
  command('task00201.mutate', async () => {
    const mode = await vscode.window.showQuickPick(['metadata-setting', 'source-changed', 'source-empty'], { title: 'D4: 実行中／待機中の選択セルに行う変更' });
    if (!mode) return;
    const { doc, cell } = selected();
    activeStep = 'D4-' + mode;
    if (mode === 'metadata-setting') await metadata(doc, cell, { committed: Date.now() }, activeStep);
    else {
      const edit = new vscode.WorkspaceEdit();
      edit.replace(cell.document.uri, new vscode.Range(0, 0, cell.document.lineCount, 0), mode === 'source-empty' ? '' : "print('diagnostic CHANGED current source')\n");
      await apply(edit, activeStep, doc);
    }
  }, true);
  command('task00201.arm', async () => {
    const { doc, cell } = selected();
    activeStep = 'D5-arm-local-only';
    const request = { doc, cell, token: crypto.randomUUID(), invalidated: false };
    pending.add(request);
    log('local-delay.arm', { token: request.token, notebookObject: id(doc), cellObject: id(cell), delayMs: 15000, kernelRequest: false });
    const timer = setTimeout(async () => {
      try {
        const valid = !request.invalidated && validTarget(doc, cell, vscode.workspace.notebookDocuments);
        log('local-delay.guard', { token: request.token, valid, invalidated: request.invalidated, originalNotebook: docState(doc), openSamePath: vscode.workspace.notebookDocuments.filter(n => allowed(n) && n.uri.toString() === doc.uri.toString()).map(docState), kernelStopped: 'not-observed' });
        if (valid) await metadata(doc, cell, { delayedLocalToken: request.token }, 'D5-local-delay');
      } catch (e) { log('local-delay.error', { token: request.token, error: String(e) }); }
      finally { pending.delete(request); snapshot('local-delay-finished'); }
    }, 15000);
    context.subscriptions.push({ dispose: () => clearTimeout(timer) });
    vscode.window.showInformationMessage('TASK-002-01: 15秒のローカル更新待機を開始。これはカーネル実行要求ではありません。');
  }, true);
  command('task00201.burst', async () => {
    const mode = await vscode.window.showQuickPick(['existing-same-20', 'existing-change-20', 'new-same-20', 'new-change-20', 'existing-same-100', 'existing-change-100'], { title: 'D6: 数値は測定条件（合格基準ではない）' });
    if (!mode) return;
    let { doc, cell } = selected();
    activeStep = 'D6-' + mode;
    if (mode.startsWith('new-')) {
      const data = new vscode.NotebookCellData(vscode.NotebookCellKind.Code, '# D6 newly inserted\n', 'python');
      data.metadata = { metadata: { outsideDiagnosticOwner: { sentinel: 'new-cell' }, [KEY]: { burst: 0 } } };
      const insert = new vscode.WorkspaceEdit();
      insert.set(doc.uri, [vscode.NotebookEdit.insertCells(doc.cellCount, [data])]);
      const inserted = await apply(insert, 'D6-insert-before-burst', doc);
      if (!inserted.result) throw new Error('D6用セルの追加に失敗しました。');
      cell = doc.cellAt(doc.cellCount - 1);
    }
    const count = Number(mode.split('-').at(-1));
    const same = mode.includes('-same-');
    const value = cell.metadata.metadata?.[KEY]?.burst ?? 0;
    const before = { notebookEvents, textEvents, version: doc.version, dirty: doc.isDirty };
    const begin = performance.now();
    let lastTick = begin, maxTickGapMs = 0, ticks = 0;
    const heartbeat = setInterval(() => { const now = performance.now(); maxTickGapMs = Math.max(maxTickGapMs, now - lastTick); lastTick = now; ticks++; }, 50);
    const returns = [];
    try {
      for (let i = 0; i < count; i++) returns.push(await metadata(doc, cell, { burst: same ? value : value + i + 1 }, `D6-send-${i + 1}`));
    } finally { clearInterval(heartbeat); }
    log('burst.summary', { mode, sent: returns.length, returns, before, after: { notebookEvents, textEvents, version: doc.version, dirty: doc.isDirty }, elapsedMs: performance.now() - begin, ticks, maxTickGapMs, finalUnobservedTickGapMs: performance.now() - lastTick, loggingOverheadIncluded: true, performanceThreshold: 'not-defined' });
    snapshot('burst-complete', doc);
    vscode.window.showInformationMessage(`TASK-002-01: ${returns.length}回送信済み。Undo／Redo・保存・表示の応答を確認してください。`);
  }, true);
  log('environment', { session, build, vscode: vscode.version, appName: vscode.env.appName, platform: process.platform, arch: process.arch, node: process.version, electron: process.versions.electron, extensions: ['ms-toolsai.jupyter', 'ms-python.python', 'ms-python.vscode-python-envs', 'vscode.ipynb'].map(name => ({ id: name, version: vscode.extensions.getExtension(name)?.packageJSON.version, active: vscode.extensions.getExtension(name)?.isActive })), notObservable: ['kernel submitted source', 'internal execution ID', 'kernel cancellation completion from summary alone'] });
  for (const doc of vscode.workspace.notebookDocuments) if (allowed(doc)) track(doc);
  snapshot('activation');
  output.appendLine(`Log: ${logFile}`);
  vscode.window.showInformationMessage('TASK-002-01: Notebook API診断の準備完了（自動ログ記録中）');
  return { logFile, workspace: build.workspace, snapshot: () => snapshot('smoke-read-only') };
}
module.exports = { activate };
