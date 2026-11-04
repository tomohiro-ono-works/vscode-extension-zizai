'use strict';
// Research only: fixed Playwright key input compared with a public command.
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { fileURLToPath } = require('node:url');
const { parseArgs } = require('node:util');
const { _electron: electron } = require('playwright');
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
const pause = ms => new Promise(r => setTimeout(r, ms));
async function main() {
  const { values } = parseArgs({ options: { vscode: { type: 'string' }, out: { type: 'string' }, route: { type: 'string', default: 'both' } } });
  if (!values.vscode || !values.out) throw new Error('--vscode and --out required');
  if (!['both', 'keys', 'public'].includes(values.route)) throw new Error('Invalid route');
  const repo = path.resolve(__dirname, '../../../..'), out = path.resolve(repo, values.out);
  const relative = path.relative(path.join(repo, 'results'), out);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('New results folder required');
  const run = path.basename(out);
  if (!/^[A-Za-z0-9-]+$/.test(run)) throw new Error('ASCII run identifier required');
  const source = path.join(repo, 'tests/notebook-host-api');
  const build = JSON.parse(await fs.readFile(path.join(source, 'dist/build.local.json'), 'utf8'));
  if (path.resolve(build.root) !== repo) throw new Error('Foreign diagnostic build');
  const hashes = {};
  for (const name of ['extension.cjs', 'model.cjs', 'fixtures.cjs', 'package.json']) {
    const bytes = await fs.readFile(path.join(source, name));
    if (!bytes.equals(await fs.readFile(path.join(source, 'dist', name))) || sha(bytes) !== build.hashes[name]) throw new Error('Source/build mismatch: ' + name);
    hashes[name] = sha(bytes);
  }
  await fs.mkdir(path.dirname(out), { recursive: true }); await fs.mkdir(out);
  const folder = path.join(build.workspace, 'PW-' + run); await fs.mkdir(folder);
  const original = require(path.join(source, 'fixtures.cjs')).notebook('D3-mixed');
  for (const route of ['keys', 'public']) await fs.writeFile(path.join(folder, 'PW-' + run + '-D3-' + route + '.ipynb'), JSON.stringify(original, null, 2), { flag: 'wx' });
  const dev = path.join(out, 'extension'); await fs.mkdir(dev);
  for (const name of ['extension.cjs', 'model.cjs', 'fixtures.cjs', 'build.local.json']) await fs.copyFile(path.join(source, 'dist', name), path.join(dev, name));
  await fs.copyFile(path.join(__dirname, 'd3-public-redo.cjs'), path.join(dev, 'd3-public-redo.cjs'));
  const manifest = JSON.parse(await fs.readFile(path.join(source, 'package.json'), 'utf8'));
  manifest.main = './d3-public-redo.cjs';
  manifest.contributes.commands.push({ command: 'task00201.d3PublicRedo', title: 'TASK-002-01: D3 Public Redo Comparison' });
  await fs.writeFile(path.join(dev, 'package.json'), JSON.stringify(manifest, null, 2), { flag: 'wx' });
  const profile = path.join(out, 'profile'); await fs.mkdir(path.join(profile, 'User'), { recursive: true });
  await fs.writeFile(path.join(profile, 'User/settings.json'), JSON.stringify({
    'window.title': 'TASK-002-01 D3 Redo Playwright ${activeEditorShort}',
    'window.restoreWindows': 'none', 'workbench.startupEditor': 'none',
    'window.dialogStyle': 'custom', 'files.autoSave': 'off',
    'extensions.autoUpdate': 'off', 'extensions.autoCheckUpdates': false, 'update.mode': 'none',
    'workbench.editorAssociations': { '*.ipynb': 'jupyter-notebook' }
  }, null, 2), { flag: 'wx' });
  const report = { case: 'D3-same-value-twice-redo-comparison', startedAt: new Date().toISOString(),
    outcome: 'in_progress', requestedRoute: values.route, stages: [], cases: [], diagnosticHashes: hashes,
    runnerSha256: sha(await fs.readFile(__filename)), bridgeSha256: sha(await fs.readFile(path.join(dev, 'd3-public-redo.cjs'))),
    manifestSha256: sha(await fs.readFile(path.join(dev, 'package.json'))),
    originalCoreUnchanged: true, separateResearchBridge: true,
    fixtureFolder: folder, profileCopied: false, kernelExecuted: false,
    securityFeaturesDisabled: false, manualPass: false, playwright: require('playwright/package.json').version };
  await fs.copyFile(__filename, path.join(out, 'runner.cjs'));
  let app, page, closed;
  const save = () => fs.writeFile(path.join(out, 'result.local.json'), JSON.stringify(report, null, 2));
  async function stage(name) { report.stages.push({ name, at: new Date().toISOString() }); await save(); console.log(name); }
  async function focusRow(row) {
    await row.first().waitFor({ state: 'visible', timeout: 15000 });
    if (await row.count() !== 1) throw new Error('Ambiguous quick-input match');
    const n = await page.locator('.quick-input-list .monaco-list-row').count() + 2;
    for (let i = 0; i < n; i++) {
      if (await row.evaluate(el => el.classList.contains('focused'))) return;
      await page.keyboard.press('ArrowDown');
    }
    throw new Error('Quick-input focus unavailable');
  }
  async function accept(text) {
    const row = page.locator('.quick-input-list .monaco-list-row').filter({ hasText: text });
    await focusRow(row); await page.keyboard.press('Enter'); await row.waitFor({ state: 'hidden', timeout: 10000 });
  }
  async function command(title) {
    await page.keyboard.press('Control+Shift+P');
    const input = page.locator('.quick-input-widget input');
    await input.waitFor({ state: 'visible', timeout: 10000 }); await input.fill('>' + title); await accept(title);
  }
  async function events() {
    if (!report.eventLog) {
      for (const ent of await fs.readdir(path.join(repo, 'logs/task-002-01'), { withFileTypes: true })) {
        if (!ent.isDirectory()) continue;
        const file = path.join(repo, 'logs/task-002-01', ent.name, 'events.jsonl');
        const bytes = await fs.readFile(file, 'utf8').catch(() => '');
        if (bytes.includes('PW-' + run + '-D3-')) { report.eventLog = file; break; }
      }
    }
    if (!report.eventLog) return [];
    const s = await fs.readFile(report.eventLog, 'utf8');
    return s.slice(0, s.lastIndexOf('\n')).split('\n').filter(Boolean).map(l => JSON.parse(l));
  }
  async function waitEvents(predicate) {
    const until = Date.now() + 15000;
    while (Date.now() < until) { const es = await events(); if (predicate(es)) return es; await pause(50); }
    throw new Error('Public diagnostic event timeout');
  }
  async function marker(label, target) {
    const start = (await events()).at(-1)?.seq || 0;
    await command('TASK-002-01: Record Step'); await accept(label);
    const es = await waitEvents(es => es.some(e => e.seq > start && e.kind === 'snapshot' && e.label === label));
    const e = es.findLast(e => e.seq > start && e.kind === 'snapshot' && e.label === label);
    const doc = e.notebooks.find(d => d.uri.includes(target));
    if (!doc) throw new Error('Target absent from snapshot');
    return { seq: e.seq, at: e.at, notebook: doc };
  }
  async function notebookFocus(cell, action) {
    await cell.locator('.monaco-editor').click();
    // One Escape can leave native EditContext focused. Use the visible standard
    // command and verify container focus rather than assuming Escape succeeded.
    await command('Stop Editing Cell');
    const focus = await page.evaluate(() => {
      const e = document.activeElement;
      return { at: Date.now(), tag: e?.tagName, role: e?.getAttribute('role'), classes: e?.className,
        inNotebook: Boolean(e?.closest('.notebook-editor')), inCellEditor: Boolean(e?.closest('.monaco-editor')),
        inQuickInput: Boolean(e?.closest('.quick-input-widget')) };
    });
    if (!focus.inNotebook || focus.inCellEditor || focus.inQuickInput) throw new Error('Notebook container focus not established');
    return { action, ...focus };
  }
  const metadataValue = snap => snap.notebook.cells[0].metadata.metadata.task00201Diagnostic.mixed ?? null;
  await save();
  try {
    const env = { ...process.env }; delete env.ELECTRON_RUN_AS_NODE; delete env.VSCODE_DEV; delete env.VSCODE_PORTABLE;
    app = await electron.launch({ executablePath: path.resolve(values.vscode), env, timeout: 45000,
      args: ['--new-window', '--skip-welcome', '--skip-release-notes', '--disable-telemetry', '--disable-updates',
        '--disable-extension=google.colab', '--locale=en', '--remote-debugging-address=127.0.0.1',
        '--user-data-dir=' + profile, '--shared-data-dir=' + path.join(out, 'shared-data'),
        '--extensions-dir=C:/Users/tomoh/.vscode/extensions', '--extensionDevelopmentPath=' + dev, folder] });
    const child = app.process();
    report.pid = child.pid;
    report.processOutput = { stdout: [], stderr: [] };
    child.stdout?.on('data', b => report.processOutput.stdout.push(String(b)));
    child.stderr?.on('data', b => report.processOutput.stderr.push(String(b)));
    child.once('exit', (code, signal) => { report.processExit = { code, signal, at: new Date().toISOString() }; });
    closed = new Promise(resolve => app.once('close', () => { report.closedAt = new Date().toISOString(); resolve(); }));
    await stage('electron_connected');
    page = await app.firstWindow(); await page.locator('.monaco-workbench').waitFor({ state: 'visible', timeout: 30000 });
    const workspaces = [];
    for (const name of await fs.readdir(path.join(profile, 'User/workspaceStorage'))) {
      const s = await fs.readFile(path.join(profile, 'User/workspaceStorage', name, 'workspace.json'), 'utf8').catch(() => null);
      if (s) workspaces.push(JSON.parse(s));
    }
    if (workspaces.length !== 1 || !workspaces[0].folder || path.resolve(fileURLToPath(workspaces[0].folder)).toLowerCase() !== folder.toLowerCase()) throw new Error('Unexpected workspace trust scope');
    await page.getByText('Manage', { exact: true }).click();
    const trust = page.locator('.workspace-trust-editor'); await trust.getByRole('button', { name: 'Trust', exact: true }).click();
    await trust.getByRole('button', { name: "Don't Trust", exact: true }).waitFor({ state: 'visible', timeout: 10000 });
    report.trustScope = workspaces[0];
    await page.locator('.monaco-modal-editor-block').getByRole('button', { name: /Close Modal Editor/ }).click();
    await page.locator('.monaco-modal-editor-block').waitFor({ state: 'hidden', timeout: 10000 });
    await stage('approved_fixture_folder_trusted');
    await page.evaluate(() => {
      window.__task00201D3Keys = [];
      document.addEventListener('keydown', e => {
        if (e.ctrlKey && ['z', 'y'].includes(e.key.toLowerCase())) {
          window.__task00201D3Keys.push({ at: Date.now(), key: e.key, code: e.code, trusted: e.isTrusted,
            tag: e.target.tagName, classes: e.target.className, inNotebook: Boolean(e.target.closest('.notebook-editor')),
            inQuickInput: Boolean(e.target.closest('.quick-input-widget')) });
        }
      }, true);
    });
    for (const route of values.route === 'both' ? ['keys', 'public'] : [values.route]) {
      const target = 'PW-' + run + '-D3-' + route + '.ipynb';
      await page.getByText(target, { exact: true }).dblclick();
      await page.locator('.tab.active').filter({ hasText: target }).waitFor({ state: 'visible', timeout: 15000 });
      // Cached inactive Notebook rows can pass :visible after switching tabs.
      // Bind the row to the exact synthetic target through its rendered data-uri.
      const cell = page.locator('.code-cell-row').filter({ has: page.locator('.monaco-editor[data-uri*="' + target + '"]') });
      await cell.waitFor({ state: 'visible', timeout: 30000 });
      if (await cell.count() !== 1) throw new Error('D3 target cell not unique');
      const item = { route, target, focus: [], states: [], startedAt: new Date().toISOString() }; report.cases.push(item);
      item.states.push({ step: 'baseline', ...await marker('baseline', target) });
      for (let i = 1; i <= 2; i++) {
        const begin = (await events()).at(-1).seq;
        await command('TASK-002-01: D3 Mixed Edit'); await accept('metadata-first-failure');
        const es = await waitEvents(es => es.some(e => e.seq > begin && e.kind === 'snapshot' && e.label === 'D3-metadata-first-failure:after'));
        const ret = es.findLast(e => e.seq > begin && e.kind === 'apply.return');
        const after = es.findLast(e => e.seq > begin && e.kind === 'snapshot' && e.label.endsWith(':after'));
        if (ret?.result !== false) throw new Error('Intentional failure did not return false');
        item.states.push({ step: 'apply' + i, seq: after.seq, at: after.at, notebook: after.notebooks.find(n => n.uri.includes(target)) });
        if (metadataValue(item.states.at(-1)) !== 'metadata-first-failure') throw new Error('Partial metadata not observed');
      }
      for (let i = 1; i <= 2; i++) {
        item.focus.push(await notebookFocus(cell, 'undo' + i));
        await page.keyboard.press('Control+z'); await pause(300);
        item.states.push({ step: 'undo' + i, ...await marker('undo', target) });
      }
      if (metadataValue(item.states.at(-1)) !== null) throw new Error('Undo2 did not restore baseline');
      item.focus.push(await notebookFocus(cell, 'redo'));
      if (route === 'keys') await page.keyboard.press('Control+y');
      else await command('TASK-002-01: D3 Public Redo Comparison');
      await pause(300);
      item.states.push({ step: 'redo', ...await marker('redo', target) });
      item.redoRestored = metadataValue(item.states.at(-1)) === 'metadata-first-failure';
      if (route === 'public') item.publicCall = JSON.parse(await fs.readFile(path.join(folder, 'public-redo.local.json'), 'utf8'));
      item.keys = await page.evaluate(() => window.__task00201D3Keys.splice(0));
      const baseline = original.cells[0];
      for (const s of item.states) {
        const c = s.notebook.cells[0];
        if (s.notebook.cells.length !== 1 || c.source !== baseline.source.join('') || c.metadata.id !== baseline.id ||
            JSON.stringify(c.metadata.metadata.outsideDiagnosticOwner) !== JSON.stringify(baseline.metadata.outsideDiagnosticOwner)) throw new Error('D3 source/id/foreign metadata invariant failed');
      }
      await page.keyboard.press('Control+s');
      item.savedSnapshot = await marker('saved', target);
      const savedFile = path.join(folder, target), raw = await fs.readFile(savedFile);
      item.saved = { sha256: sha(raw), notebook: JSON.parse(raw) };
      if (item.savedSnapshot.notebook.dirty || item.saved.notebook.cells[0].source.join('') !== baseline.source.join('') ||
          item.saved.notebook.cells[0].id !== baseline.id || item.saved.notebook.cells[0].execution_count !== null ||
          item.saved.notebook.cells[0].outputs.length !== 0) throw new Error('Saved D3 state invariant failed');
      await stage(route + '_comparison_recorded');
    }
    report.environment = (await events()).find(e => e.kind === 'environment');
    report.outcome = 'observed_comparison';
    await fs.copyFile(report.eventLog, path.join(out, 'events.jsonl'));
    await page.screenshot({ path: path.join(out, 'final.png') });
  } catch (error) {
    report.outcome = 'not_observed'; report.error = { name: error.name, message: error.message }; process.exitCode = 1;
    if (page) {
      report.keysAtStop = await page.evaluate(() => window.__task00201D3Keys ?? []).catch(() => []);
      await page.screenshot({ path: path.join(out, 'stopped.png') }).catch(() => {});
      await fs.writeFile(path.join(out, 'stopped-dom.txt'), await page.locator('body').innerText().catch(() => 'unavailable'));
    }
    if (report.eventLog) await fs.copyFile(report.eventLog, path.join(out, 'events.jsonl')).catch(() => {});
  }
  await save(); console.log(JSON.stringify({ outcome: report.outcome, cases: report.cases.map(c => ({ route: c.route, redoRestored: c.redoRestored })), error: report.error }));
  if (app && !report.closedAt) {
    console.log('Window retained. Awaiting user end signal (finish).');
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', async input => { if (input.trim() === 'finish') { report.endSignalReceived = true; await app.close(); } });
    process.stdin.resume(); await closed; process.stdin.pause(); await save();
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
