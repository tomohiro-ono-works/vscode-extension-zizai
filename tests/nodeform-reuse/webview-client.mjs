// TASK-001-02 PROTOTYPE bridge only. No formal UI/Host contract or Python execution.
const host = acquireVsCodeApi();
const root = document.getElementById('form');
const status = document.getElementById('status');
const result = document.getElementById('result');
const forms = { 'Probe.run': [
  { key: 'name', label: '検証用の名前', kind: 'text', required: true },
  { key: 'choice', label: '候補付き入力', kind: 'combo', options: ['one', 'two', 'three'] },
  { key: 'mode', label: '追加項目', kind: 'select', options: ['hide', 'show'], default: 'hide' },
  { key: 'detail', label: '追加項目（必須）', kind: 'text', required: true, visible_if: { key: 'mode', equals: 'show' } },
  { key: 'file', label: 'ファイル選択（内容は読み込みません）', kind: 'file' },
  { key: 'folder', label: 'フォルダー選択', kind: 'dir' }
] };
let editor;
function mount() {
  editor?.destroy();
  editor = window.NodeForm.mount({ root, node: { connector: 'Probe', action: 'run', form: {} }, forms,
    onChange(_params, change) { status.textContent = `${change.key} を変更しました`; } });
  result.textContent = '';
}
root.addEventListener('nodeform:browse-request', event => {
  host.postMessage({ type: 'browse', ...event.detail });
});
window.addEventListener('message', event => {
  if (event.data?.type === 'browse-result') {
    document.dispatchEvent(new CustomEvent('nodeform:browse-result', { detail: event.data.result }));
    if (event.data.result.error) status.textContent = '選択ダイアログを開けませんでした';
  } else if (event.data?.type === 'environment') {
    result.textContent = JSON.stringify(event.data, null, 2);
  }
});
document.getElementById('validate').addEventListener('click', () => {
  const validation = editor.validate();
  status.textContent = validation.valid ? '入力検証OK' : '項目のエラーを確認してください';
});
document.getElementById('remount').addEventListener('click', () => { mount(); status.textContent = 'フォームを作り直しました'; });
document.getElementById('report').addEventListener('click', () => host.postMessage({ type: 'report' }));
mount();
