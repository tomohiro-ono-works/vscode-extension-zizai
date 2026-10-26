// Isolated diagnostic build; no product build or external dependency download.
import { mkdir, readFile, writeFile, copyFile, access } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fixtures from './fixtures.cjs';
const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const dist = path.join(here, 'dist');
const workspace = path.join(root, 'results/task-002-01/workspace');
await mkdir(dist, { recursive: true });
await mkdir(workspace, { recursive: true });
await mkdir(path.join(root, 'logs/task-002-01'), { recursive: true });
const files = ['package.json', 'extension.cjs', 'model.cjs', 'fixtures.cjs', 'smoke.cjs', 'automated.cjs', 'structure.cjs', 'structure-delete.cjs', 'structure-ids.cjs', 'structure-focus.cjs', 'recovery.cjs', 'execution-auto.cjs', 'execution-save-followup.cjs', 'execution-save-followup-ui.cjs', 'running-close.cjs'];
const hashes = {};
for (const name of files) {
  const source = path.join(here, name);
  if (name.endsWith('.cjs')) execFileSync(process.execPath, ['--check', source], { stdio: 'pipe' });
  hashes[name] = createHash('sha256').update(await readFile(source)).digest('hex');
  await copyFile(source, path.join(dist, name));
}
const git = (...args) => execFileSync('git', args, { cwd: root, encoding: 'utf8' }).trim();
const build = { root, workspace, preparedAt: new Date().toISOString(), base: git('rev-parse', 'HEAD'), branch: git('branch', '--show-current'), diff: git('status', '--short'), node: process.version, hashes };
await writeFile(path.join(dist, 'build.local.json'), JSON.stringify(build, null, 2) + '\n');
// Preserve previous experiments and saved outputs on every rebuild.
for (const name of Object.keys(fixtures.cases)) {
  const file = path.join(workspace, name + '.ipynb');
  try { await access(file); } catch { await writeFile(file, JSON.stringify(fixtures.notebook(name), null, 2) + '\n'); }
}
// The public standard-kernel selection gate uses this synthetic URI across cases.
// Preserve previous selection experiments and outputs on every rebuild.
try {
  await writeFile(path.join(workspace, 'USER-kernel-bootstrap-20261024.ipynb'), JSON.stringify(fixtures.notebook('D4-environment'), null, 2) + '\n', { flag: 'wx' });
} catch (error) { if (error.code !== 'EEXIST') throw error; }
const probeWorkspace = {
  folders: [{ path: workspace }],
  settings: { 'window.title': 'TASK-002-01 API診断 ${activeEditorShort}', 'files.autoSave': 'off', 'workbench.editorAssociations': { '*.ipynb': 'jupyter-notebook' }, 'python.defaultInterpreterPath': process.env.TASK00201_PYTHON || 'C:\\Python314\\python.exe' }
};
await writeFile(path.join(dist, 'probe.code-workspace'), JSON.stringify(probeWorkspace, null, 2) + '\n');
await writeFile(path.join(dist, 'save-followup.code-workspace'), JSON.stringify({ ...probeWorkspace, settings: { ...probeWorkspace.settings, 'window.title': 'TASK-002-01 保存追加確認 ${activeEditorShort}' } }, null, 2) + '\n');
const profile = path.join(root, 'config/task-002-01-desktop/User');
await mkdir(profile, { recursive: true });
const settingsFile = path.join(profile, 'settings.json');
let settings = {};
try { settings = JSON.parse(await readFile(settingsFile, 'utf8')); } catch (error) { if (error.code !== 'ENOENT') throw error; }
await writeFile(settingsFile, JSON.stringify({ ...settings, 'extensions.autoUpdate': false, 'extensions.autoCheckUpdates': false, 'update.mode': 'none', 'window.restoreWindows': 'none', 'workbench.startupEditor': 'none' }, null, 2) + '\n');
console.log(JSON.stringify({ prepared: dist, workspace, base: build.base, hashes }, null, 2));
