// TASK-001-02 throwaway evaluation surface. Not a product placement decision.
const vscode = require('vscode');
const { randomBytes } = require('node:crypto');
const provenance = require('./provenance.json');
function activate(context) {
  context.subscriptions.push(vscode.commands.registerCommand('zizaiNodeFormProbe.open', () => {
    const panel = vscode.window.createWebviewPanel('zizaiNodeFormProbe', 'NodeForm 再利用検証（試作）', vscode.ViewColumn.Active, {
      enableScripts: true, localResourceRoots: [context.extensionUri]
    });
    let disposed = false;
    let pending = false;
    const resource = (...parts) => panel.webview.asWebviewUri(vscode.Uri.joinPath(context.extensionUri, ...parts));
    const nonce = randomBytes(16).toString('hex');
    panel.webview.html = `<!doctype html><html lang="ja"><head><meta charset="UTF-8">
      <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${panel.webview.cspSource}; script-src 'nonce-${nonce}';">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <link rel="stylesheet" href="${resource('resources', 'node-form.css')}">
      <link rel="stylesheet" href="${resource('vscode-theme-probe.css')}">
      </head><body><h2>NodeForm 再利用検証（試作）</h2>
      <p>この別タブは部品評価専用です。Notebookのセル内配置は未検証です。架空の値を使ってください。</p>
      <div id="form"></div><p id="status" role="status"></p>
      <button id="validate">入力検証</button> <button id="remount">フォームを作り直す</button>
      <button id="report">環境を報告</button><pre id="result"></pre>
      <script nonce="${nonce}" src="${resource('resources', 'node-form.js')}"></script>
      <script nonce="${nonce}" type="module" src="${resource('webview-client.mjs')}"></script>
      </body></html>`;
    const listeners = [];
    listeners.push(panel.webview.onDidReceiveMessage(async message => {
      if (disposed || !message || typeof message !== 'object') return;
      if (message.type === 'report') {
        await panel.webview.postMessage({ type: 'environment', vscode: vscode.version,
          node: process.version, probeVersion: context.extension.packageJSON.version, platform: process.platform, theme: vscode.window.activeColorTheme.kind, ...provenance });
      } else if (message.type === 'browse' && ['file', 'dir'].includes(message.kind)
        && ['file', 'folder'].includes(message.key)
        && typeof message.instanceId === 'string' && message.instanceId.length < 100
        && typeof message.requestId === 'string' && message.requestId.length < 200) {
        const result = { instanceId: message.instanceId, requestId: message.requestId, key: message.key };
        if (pending) { await panel.webview.postMessage({ type: 'browse-result', result: { ...result, cancelled: true } }); return; }
        pending = true;
        try {
          const selected = await vscode.window.showOpenDialog({ canSelectFiles: message.kind === 'file',
            canSelectFolders: message.kind === 'dir', canSelectMany: false, title: 'NodeForm検証用のファイル／フォルダーを選択' });
          result.cancelled = !selected?.length;
          if (!result.cancelled) result.value = selected[0].fsPath;
        } catch { result.error = true; }
        finally { pending = false; }
        if (!disposed) await panel.webview.postMessage({ type: 'browse-result', result });
      }
    }));
    const disposedListener = panel.onDidDispose(() => {
      disposed = true;
      for (const listener of listeners) listener.dispose();
      disposedListener.dispose();
    });
    context.subscriptions.push(panel);
  }));
}
module.exports = { activate };
