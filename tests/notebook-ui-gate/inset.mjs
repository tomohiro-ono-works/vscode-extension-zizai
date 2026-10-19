import { mountForm } from './form.mjs';
const vscode = acquireVsCodeApi();
const root = document.getElementById('probe');
mountForm(root, JSON.parse(root.dataset.initial), state => {
  vscode.postMessage({ type: 'state', state });
});
vscode.postMessage({ type: 'ready' });
