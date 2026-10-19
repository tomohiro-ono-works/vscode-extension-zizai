// Offline packaging/fixture checks only. These cannot prove Notebook UI works.
import assert from 'node:assert/strict';
import { readFile, access } from 'node:fs/promises';
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
console.log('PASS: two isolated manifests, resources, unexecuted empty/control fixtures. UI NOT tested.');
