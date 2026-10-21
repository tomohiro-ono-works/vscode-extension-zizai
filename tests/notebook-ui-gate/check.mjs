// Offline packaging/fixture checks only. These cannot prove Notebook UI works.
import assert from 'node:assert/strict';
import { readFile, access, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import roles from './role.cjs';

// getNotebookCellMetadata in VS Code 1.142.0 wraps ipynb metadata in `metadata`.
// A direct-only lookup would hide all probe UI, falsely suggesting API failure.
assert.equal(roles.readRole({ metadata: { task00101Probe: { role: 'init' } } }), 'init');
assert.equal(roles.readRole({ metadata: {} }), undefined);

const root = path.dirname(fileURLToPath(import.meta.url));
const json = async file => JSON.parse(await readFile(file, 'utf8'));
for (const mode of ['stable', 'insets']) {
  const built = path.join(root, 'dist', mode);
  const manifest = await json(path.join(built, 'package.json'));
  assert.equal(manifest.publisher + '.' + manifest.name, 'zizai-lab.task-001-01-probe');
  assert.deepEqual(manifest.enabledApiProposals, mode === 'insets' ? ['editorInsets'] : undefined);
  assert.equal((await json(path.join(built, 'mode.json'))).mode, mode);
  await access(path.join(built, manifest.main));
  for (const renderer of manifest.contributes.notebookRenderer) await access(path.join(built, renderer.entrypoint));
  for (const resource of ['form.mjs', 'inset.mjs', 'fixtures/inset-control.py']) await access(path.join(built, resource));
  for (const name of ['empty.ipynb', 'renderer-control.ipynb']) {
    const notebook = await json(path.join(built, 'fixtures', name));
    assert.equal(notebook.nbformat, 4);
    assert.equal(notebook.cells.length, 3);
    assert.equal(notebook.cells[0].metadata.task00101Probe.role, 'init');
    assert.deepEqual(notebook.cells[1].metadata, {}); // ordinary unmarked Python
    assert.equal(notebook.cells[2].metadata.task00101Probe.role, 'action');
    for (const cell of notebook.cells) assert.equal(cell.execution_count, null);
    const outputs = notebook.cells.flatMap(cell => cell.outputs);
    assert.equal(outputs.length, name === 'empty.ipynb' ? 0 : 1);
    if (outputs.length) assert.deepEqual(Object.keys(outputs[0].data), manifest.contributes.notebookRenderer[0].mimeTypes);
  }
}
const toolbar = path.join(root, 'dist', 'toolbar');
const manifest = await json(path.join(toolbar, 'package.json'));
assert.equal(manifest.main, './toolbar.cjs');
assert.equal(manifest.enabledApiProposals, undefined);
assert.equal(manifest.contributes.notebookRenderer, undefined);
assert.equal(manifest.contributes.menus['notebook/cell/title'][0].submenu, manifest.contributes.submenus[0].id);
assert.match(manifest.contributes.menus['notebook/cell/title'][0].when, /notebookCellResource in zizaiProbe\.toolbarCells/);
const commands = new Set(manifest.contributes.commands.map(command => command.command));
for (const item of manifest.contributes.menus['zizaiProbe.cellMenu']) assert(commands.has(item.command));
assert.deepEqual((await readdir(toolbar)).sort(), ['fixtures', 'mode.json', 'package.json', 'role.cjs', 'toolbar-state.cjs', 'toolbar.cjs']);
assert((await json(path.join(toolbar, 'fixtures', 'empty.ipynb'))).cells.every(cell => cell.execution_count === null && cell.outputs.length === 0));
console.log('PASS: three isolated manifests and fixtures; toolbar has no HTML/renderer/proposed API. UI NOT tested.');
const statusbar = path.join(root, 'dist', 'statusbar');
const footerManifest = await json(path.join(statusbar, 'package.json'));
assert.equal(footerManifest.version, '0.0.3');
assert.equal(footerManifest.main, './statusbar.cjs');
assert.equal(footerManifest.enabledApiProposals, undefined);
assert.equal(footerManifest.contributes.notebookRenderer, undefined);
assert.equal(footerManifest.contributes.menus['notebook/cell/title'], undefined);
assert.equal((await json(path.join(statusbar, 'probe.code-workspace'))).settings['notebook.showCellStatusBar'], 'visible');
assert.deepEqual((await readdir(statusbar)).sort(), ['fixtures', 'mode.json', 'package.json', 'probe.code-workspace', 'role.cjs', 'statusbar.cjs', 'toolbar-state.cjs']);
assert((await json(path.join(statusbar, 'fixtures', 'empty.ipynb'))).cells.every(cell => cell.execution_count === null && cell.outputs.length === 0));
console.log('PASS: footer build has no title-toolbar contribution, HTML or proposed API. Desktop placement NOT tested.');
