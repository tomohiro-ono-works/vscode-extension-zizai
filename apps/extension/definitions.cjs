"use strict";
const YAML = require('yaml');
const empty = { magics: {} };
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const strings = value => Array.isArray(value) && value.every(item => typeof item === 'string');

function parseDefinitions(text) {
  if (Buffer.byteLength(text, 'utf8') > 1024 * 1024) throw Error('定義は1MiB以下にしてください。');
  const doc = YAML.parseDocument(text, { version: '1.2', schema: 'core', uniqueKeys: true });
  if (doc.errors.length || doc.warnings.length) throw Error('YAMLの記法を確認してください。');
  const data = doc.toJS({ maxAliasCount: 0 });
  if (!object(data) || data.version !== 1 || !object(data.magics)) throw Error('version: 1 と magics が必要です。');
  for (const [magic, value] of Object.entries(data.magics)) {
    if (!/^[\w.]+$/.test(magic) || !object(value) || !object(value.fields)) throw Error('マジックとfieldsの形式が不正です。');
    const fields = value.fields;
    for (const [name, field] of Object.entries(fields)) {
      if (!/^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$/.test(name) || !object(field) ||
          typeof field.label !== 'string' || !field.label || field.label.length > 16 || /[\r\n]/.test(field.label)) throw Error('項目名またはlabelが不正です。');
      const isPath = field.kind === 'file' || field.kind === 'folder';
      if (field.kind !== undefined && !isPath && field.kind !== 'choice') throw Error('kindが不正です。');
      if (isPath) {
        if (field.dependsOn !== undefined || field.choices !== undefined || field.choicesByValue !== undefined) throw Error('パス項目に候補は指定できません。');
      } else if (field.dependsOn !== undefined) {
        if (typeof field.dependsOn !== 'string' || !Object.hasOwn(fields, field.dependsOn) ||
            !object(field.choicesByValue) || !Object.values(field.choicesByValue).every(strings) || field.choices !== undefined) throw Error('依存候補の形式が不正です。');
      } else if (!strings(field.choices) || field.choicesByValue !== undefined) throw Error('choicesは文字列の配列にしてください。');
    }
    for (const name of Object.keys(fields)) {
      const seen = new Set();
      let current = name;
      while (current !== undefined) {
        if (seen.has(current)) throw Error('項目間の依存が循環しています。');
        seen.add(current);
        const parent = fields[current].dependsOn;
        if (parent !== undefined && ['file', 'folder'].includes(fields[parent].kind)) throw Error('パス項目を候補の親にはできません。');
        current = parent;
      }
    }
  }
  return data;
}

async function createDefinitionStore(vscode, context, fallback, onChange) {
  const cache = new Map(), sequences = new Map(), warned = new Set();
  const target = folder => vscode.Uri.joinPath(folder.uri, '.vscode', 'zizai-definitions.yaml');
  async function reload(folder) {
    const key = folder.uri.toString();
    const sequence = (sequences.get(key) || 0) + 1;
    sequences.set(key, sequence);
    let data, invalid = false;
    try { data = parseDefinitions(Buffer.from(await vscode.workspace.fs.readFile(target(folder))).toString('utf8')); }
    catch (error) {
      if (error.code === 'FileNotFound' || error.code === 'ENOENT') data = fallback;
      else { data = empty; invalid = true; }
    }
    if (sequences.get(key) !== sequence) return;
    cache.set(key, data);
    if (invalid && !warned.has(key)) {
      warned.add(key);
      vscode.window.showWarningMessage('zizai-definitions.yamlを読み込めません。YAMLの記法と定義形式を確認してください。Notebookは変更していません。');
    } else if (!invalid) warned.delete(key);
    onChange();
  }
  const watcher = vscode.workspace.createFileSystemWatcher('**/.vscode/zizai-definitions.yaml');
  const changed = uri => {
    const folder = vscode.workspace.workspaceFolders?.find(item => target(item).toString() === uri.toString());
    return folder ? reload(folder) : Promise.resolve();
  };
  context.subscriptions.push(watcher, watcher.onDidCreate(changed), watcher.onDidChange(changed), watcher.onDidDelete(changed),
    vscode.workspace.onDidChangeWorkspaceFolders(async event => {
      for (const folder of event.removed) { const key = folder.uri.toString(); sequences.set(key, (sequences.get(key) || 0) + 1); cache.delete(key); warned.delete(key); }
      await Promise.all(event.added.map(reload));
      onChange();
    }));
  await Promise.all((vscode.workspace.workspaceFolders || []).map(reload));
  return { get(document) {
    const notebook = vscode.workspace.notebookDocuments.find(item => item.getCells().some(cell => cell.document.uri.toString() === document.uri.toString()));
    const folder = notebook && vscode.workspace.getWorkspaceFolder(notebook.uri);
    return folder ? cache.get(folder.uri.toString()) || empty : fallback;
  } };
}

module.exports = { parseDefinitions, createDefinitionStore };
