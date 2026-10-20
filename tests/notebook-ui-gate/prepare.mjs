// TASK-001-01 throwaway probe. No app build or production dependencies.
import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.dirname(fileURLToPath(import.meta.url));
const mode = process.argv[2];
if (!['stable', 'insets', 'toolbar'].includes(mode)) {
  throw new Error('Usage: node tests/notebook-ui-gate/prepare.mjs stable|insets|toolbar');
}
const target = path.join(root, 'dist', mode);
await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });
const files = mode === 'toolbar'
  ? ['toolbar.cjs', 'toolbar-state.cjs', 'role.cjs']
  : ['extension.cjs', 'role.cjs', 'form.mjs', 'inset.mjs', 'renderer.mjs', 'fixtures'];
for (const name of files) {
  await cp(path.join(root, name), path.join(target, name), { recursive: true });
}
if (mode === 'toolbar') {
  await mkdir(path.join(target, 'fixtures'));
  await cp(path.join(root, 'fixtures', 'empty.ipynb'), path.join(target, 'fixtures', 'empty.ipynb'));
}
const manifest = JSON.parse(await readFile(path.join(root, mode === 'toolbar' ? 'toolbar.package.json' : 'package.json'), 'utf8'));
// Both builds have the same extension id; run only one at a time.
if (mode === 'insets') manifest.enabledApiProposals = ['editorInsets'];
await writeFile(path.join(target, 'package.json'), JSON.stringify(manifest, null, 2) + '\n');
await writeFile(path.join(target, 'mode.json'), JSON.stringify({ mode }) + '\n');
console.log(`Prepared ${mode}: ${target}`);
