'use strict';
// One approved D4 queued-edit/save observation. Fixed Playwright; public diagnostic API only.
const fs = require('node:fs/promises'), path = require('node:path'), crypto = require('node:crypto');
const { fileURLToPath } = require('node:url'), { parseArgs } = require('node:util');
const { execFileSync } = require('node:child_process');
const { _electron: electron } = require('playwright');
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
const pause = ms => new Promise(r => setTimeout(r, ms));
async function main() {
  const { values } = parseArgs({ options: { vscode: { type: 'string' }, out: { type: 'string' } } });
  if (!values.vscode || !values.out) throw new Error('--vscode and --out required');
  const repo = path.resolve(__dirname, '../../../..'), out = path.resolve(repo, values.out), run = path.basename(out);
  const rel = path.relative(path.join(repo, 'results'), out);
  if (!rel || rel.startsWith('..') || path.isAbsolute(rel) || !/^[A-Za-z0-9-]+$/.test(run)) throw new Error('New ASCII results folder required');
  const source = path.join(repo, 'tests/notebook-host-api');
  const build = JSON.parse(await fs.readFile(path.join(source, 'dist/build.local.json'), 'utf8'));
  if (path.resolve(build.root) !== repo) throw new Error('Foreign diagnostic build');
  const hashes = {};
  for (const name of ['extension.cjs', 'model.cjs', 'fixtures.cjs', 'package.json']) {
    const b = await fs.readFile(path.join(source, name));
    if (!b.equals(await fs.readFile(path.join(source, 'dist', name))) || sha(b) !== build.hashes[name]) throw new Error('Diagnostic source/build mismatch: ' + name);
    hashes[name] = sha(b);
  }
  await fs.mkdir(path.dirname(out), { recursive: true }); await fs.mkdir(out);
  const folder = path.join(build.workspace, 'PW-' + run); await fs.mkdir(folder);
  const target = path.join(folder, 'PW-' + run + '-D4-queued-edit.ipynb');
  const bootstrap = path.join(folder, 'PW-' + run + '-kernel.ipynb');
  const { notebook } = require(path.join(source, 'fixtures.cjs')), original = notebook('D4-queued-edit');
  await fs.writeFile(target, JSON.stringify(original, null, 2), { flag: 'wx' });
  await fs.writeFile(bootstrap, JSON.stringify(notebook('D4-environment'), null, 2), { flag: 'wx' });
  const profile = path.join(out, 'profile'); await fs.mkdir(path.join(profile, 'User'), { recursive: true });
  await fs.writeFile(path.join(profile, 'User/settings.json'), JSON.stringify({
    'window.title': 'TASK-002-01 D4 Save Playwright ${activeEditorShort}', 'window.restoreWindows': 'none',
    'workbench.startupEditor': 'none', 'window.dialogStyle': 'custom', 'files.autoSave': 'off',
    'extensions.autoUpdate': 'off', 'extensions.autoCheckUpdates': false, 'update.mode': 'none',
    'workbench.editorAssociations': { '*.ipynb': 'jupyter-notebook' }, 'python.defaultInterpreterPath': 'C:\\Python314\\python.exe'
  }, null, 2), { flag: 'wx' });
  const report = { case: 'D4-queued-edit-rerequest-save', startedAt: new Date().toISOString(), outcome: 'in_progress', stages: [],
    target, bootstrap, fixtureFolder: folder, diagnosticHashes: hashes,
    runnerSha256: sha(await fs.readFile(__filename)), playwright: require('playwright/package.json').version,
    route: 'Agent CLI / fixed Playwright / existing standard Python kernel',
    profileCopied: false, securityFeaturesDisabled: false, manualPass: false, waitSeconds: 90, executionCount: 'not inferred' };
  await fs.copyFile(__filename, path.join(out, 'runner.cjs'));
  let app, page, closed;
  const save = () => fs.writeFile(path.join(out, 'result.local.json'), JSON.stringify(report, null, 2));
  async function stage(name) { report.stages.push({ name, at: new Date().toISOString() }); await save(); console.log(name); }
  async function accept(text) {
    const row = page.locator('.quick-input-list .monaco-list-row').filter({ hasText: text });
    await row.first().waitFor({ state: 'visible', timeout: 15000 });
    if (await row.count() !== 1) throw new Error('Ambiguous quick-input match');
    const limit = await page.locator('.quick-input-list .monaco-list-row').count() + 2;
    for (let i = 0; i < limit; i++) {
      if (await row.evaluate(e => e.classList.contains('focused'))) {
        await page.keyboard.press('Enter'); await row.waitFor({ state: 'hidden', timeout: 10000 }); return;
      }
      await page.keyboard.press('ArrowDown');
    }
    throw new Error('Required quick-input row not focused');
  }
  async function command(title) {
    await page.keyboard.press('Control+Shift+P'); const input = page.locator('.quick-input-widget input');
    await input.waitFor({ state: 'visible', timeout: 10000 }); await input.fill('>' + title); await accept(title);
  }
  async function selectPython() {
    const rows = page.locator('.quick-input-list .monaco-list-row'); await rows.first().waitFor({ state: 'visible', timeout: 10000 });
    const existing = rows.filter({ hasText: /c:\\Python314\\python\.exe/i });
    if (await existing.count() === 1) {
      const title = await existing.innerText(); await accept(title);
    } else { await accept('Python Environments'); await accept('C:\\Python314\\python.exe'); }
    await page.locator('.quick-input-widget').waitFor({ state: 'hidden', timeout: 10000 });
  }
  async function runAll() {
    await command('Notebook: Run All');
    const prompted = await page.locator('.quick-input-widget').waitFor({ state: 'visible', timeout: 3000 }).then(() => true, () => false);
    if (prompted) { await selectPython(); await stage('run_all_kernel_prompt_completed'); }
  }
  async function open(file) {
    await page.getByText(path.basename(file), { exact: true }).dblclick();
    await page.locator('.tab.active').filter({ hasText: path.basename(file) }).waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('.monaco-editor[data-uri*="' + path.basename(file) + '"]').first().waitFor({ state: 'visible', timeout: 30000 });
  }
  async function events() {
    if (!report.eventLog) {
      for (const e of await fs.readdir(path.join(repo, 'logs/task-002-01'), { withFileTypes: true })) {
        if (!e.isDirectory()) continue;
        const f = path.join(repo, 'logs/task-002-01', e.name, 'events.jsonl'), s = await fs.readFile(f, 'utf8').catch(() => '');
        if (s.includes(path.basename(target)) || s.includes(path.basename(bootstrap))) { report.eventLog = f; break; }
      }
    }
    if (!report.eventLog) return [];
    const s = await fs.readFile(report.eventLog, 'utf8');
    return s.slice(0, s.lastIndexOf('\n')).split('\n').filter(Boolean).map(s => JSON.parse(s));
  }
  async function waitEvents(predicate, timeout = 15000) {
    const end = Date.now() + timeout;
    while (Date.now() < end) { const es = await events(); if (predicate(es)) return es; await pause(100); }
    throw new Error('Diagnostic observation timeout: ' + timeout + 'ms');
  }
  async function marker(label) {
    const last = (await events()).at(-1)?.seq || 0;
    await command('TASK-002-01: Record Step'); await accept(label);
    const es = await waitEvents(es => es.some(e => e.seq > last && e.kind === 'snapshot' && e.label === label));
    const s = es.findLast(e => e.seq > last && e.kind === 'snapshot' && e.label === label);
    const doc = s.notebooks.find(d => d.uri.includes(path.basename(target)) && !d.closed);
    if (!doc) throw new Error('Target missing from snapshot'); return { seq: s.seq, at: s.at, notebook: doc };
  }
  const hasSummaryEnd = c => typeof c.executionSummary?.timing?.endTime === 'number';
  const targetDoc = e => e.notebook?.uri?.includes(path.basename(target)) ? e.notebook : null;
  await save();
  try {
    const env = { ...process.env }; delete env.ELECTRON_RUN_AS_NODE; delete env.VSCODE_DEV; delete env.VSCODE_PORTABLE;
    app = await electron.launch({ executablePath: path.resolve(values.vscode), env, timeout: 45000,
      args: ['--new-window', '--skip-welcome', '--skip-release-notes', '--disable-telemetry', '--disable-updates',
        '--disable-extension=google.colab', '--locale=en', '--remote-debugging-address=127.0.0.1',
        '--user-data-dir=' + profile, '--shared-data-dir=' + path.join(out, 'shared-data'),
        '--extensions-dir=C:/Users/tomoh/.vscode/extensions', '--extensionDevelopmentPath=' + path.join(source, 'dist'), folder] });
    const child = app.process(); report.pid = child.pid; report.processOutput = { stdout: [], stderr: [] };
    child.stdout?.on('data', b => report.processOutput.stdout.push(String(b)));
    child.stderr?.on('data', b => report.processOutput.stderr.push(String(b)));
    child.once('exit', (code, signal) => { report.processExit = { code, signal, at: new Date().toISOString() }; });
    closed = new Promise(resolve => app.once('close', () => { report.closedAt = new Date().toISOString(); resolve(); }));
    report.nodeInspectorPort = await app.evaluate(() => process.debugPort);
    report.chromiumDebugPort = Number((await fs.readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]);
    await stage('electron_connected');
    page = await app.firstWindow(); await page.locator('.monaco-workbench').waitFor({ state: 'visible', timeout: 30000 });
    const workspaces = [];
    for (const name of await fs.readdir(path.join(profile, 'User/workspaceStorage'))) {
      const s = await fs.readFile(path.join(profile, 'User/workspaceStorage', name, 'workspace.json'), 'utf8').catch(() => null);
      if (s) workspaces.push(JSON.parse(s));
    }
    if (workspaces.length !== 1 || !workspaces[0].folder || path.resolve(fileURLToPath(workspaces[0].folder)).toLowerCase() !== folder.toLowerCase()) throw new Error('Unexpected trust scope');
    await page.getByText('Manage', { exact: true }).click(); const trust = page.locator('.workspace-trust-editor');
    await trust.getByRole('button', { name: 'Trust', exact: true }).click();
    await trust.getByRole('button', { name: "Don't Trust", exact: true }).waitFor({ state: 'visible', timeout: 10000 });
    report.trustScope = workspaces[0];
    await page.locator('.monaco-modal-editor-block').getByRole('button', { name: /Close Modal Editor/ }).click();
    await page.locator('.monaco-modal-editor-block').waitFor({ state: 'hidden', timeout: 10000 });
    await stage('approved_fixture_folder_trusted');
    await open(bootstrap); await command('Notebook: Select Notebook Kernel'); await selectPython(); await runAll();
    await waitEvents(es => es.some(e => e.notebook?.uri?.includes(path.basename(bootstrap)) && e.notebook.cells[0]?.executionSummary?.success === true), 60000);
    await page.keyboard.press('Control+s');
    await waitEvents(es => es.some(e => e.kind === 'notebook.save' && e.notebook.uri.includes(path.basename(bootstrap))));
    const b = JSON.parse(await fs.readFile(bootstrap, 'utf8'));
    report.kernelEnvironment = JSON.parse(b.cells[0].outputs.map(o => Array.isArray(o.text) ? o.text.join('') : o.text || '').join(''));
    if (!report.kernelEnvironment.ipykernel || !report.kernelEnvironment.jupyter_client) throw new Error('Kernel environment missing');
    await stage('kernel_preflight_saved');
    await open(target); await command('Notebook: Select Notebook Kernel'); await selectPython();
    report.beforeRun = await marker('execution-request-before'); await runAll();
    const startedHashes = ['blocker started\n', 'blocker started\r\n'].map(sha);
    const began = await waitEvents(es => es.some(e => targetDoc(e)?.cells[0].outputs.some(o => o.items.some(i => startedHashes.includes(i.sha256)))), 60000);
    report.startedEvent = began.find(e => targetDoc(e)?.cells[0].outputs.some(o => o.items.some(i => startedHashes.includes(i.sha256))));
    await stage('blocker_started');
    const name = path.basename(target);
    const downstreamEditor = page.locator('.monaco-editor[data-uri*="' + name + '"]').filter({ hasText: 'queued ORIGINAL' });
    if (await downstreamEditor.count() !== 1) throw new Error('Downstream editor not unique');
    await downstreamEditor.click(); await command('Stop Editing Cell');
    report.beforeMutation = await marker('baseline');
    if (report.beforeMutation.notebook.cells[1].outputs.length || typeof report.beforeMutation.notebook.cells[1].executionSummary?.timing?.startTime === 'number') throw new Error('Downstream already started before mutation');
    const beginSeq = (await events()).at(-1).seq;
    await command('TASK-002-01: D4 Change Selected Cell'); await accept('source-changed');
    const changed = await waitEvents(es => es.some(e => e.seq > beginSeq && e.kind === 'snapshot' && e.label === 'D4-source-changed:after'));
    report.mutationReturn = changed.findLast(e => e.seq > beginSeq && e.kind === 'apply.return');
    report.afterMutation = changed.findLast(e => e.seq > beginSeq && e.kind === 'snapshot' && e.label === 'D4-source-changed:after');
    const updated = report.afterMutation.notebooks.find(d => d.uri.includes(name));
    const changedSource = "print('diagnostic CHANGED current source')\n";
    if (report.mutationReturn.result !== true || updated.cells[1].source !== changedSource) throw new Error('D4 mutation target/result mismatch');
    if (updated.cells[1].outputs.length || typeof updated.cells[1].executionSummary?.timing?.startTime === 'number') throw new Error('Downstream began before repeat input');
    const editor = page.locator('.monaco-editor[data-uri*="' + name + '"]').filter({ hasText: 'diagnostic CHANGED current source' });
    await editor.click(); await command('Stop Editing Cell');
    report.focus = await page.evaluate(() => ({ at: Date.now(), role: document.activeElement?.getAttribute('role'),
      inNotebook: Boolean(document.activeElement?.closest('.notebook-editor')), inCellEditor: Boolean(document.activeElement?.closest('.monaco-editor')) }));
    if (!report.focus.inNotebook || report.focus.inCellEditor || report.focus.role !== 'list') throw new Error('Container focus not established');
    await page.evaluate(() => {
      window.__task00201D4Keys = [];
      document.addEventListener('keydown', e => {
        if (e.ctrlKey && e.altKey && e.key === 'Enter') window.__task00201D4Keys.push({
          at: Date.now(), trusted: e.isTrusted, key: e.key, ctrl: e.ctrlKey, alt: e.altKey,
          inNotebook: Boolean(e.target.closest('.notebook-editor')), inEditor: Boolean(e.target.closest('.monaco-editor')) });
      }, true);
    });
    await page.keyboard.press('Control+Alt+Enter');
    report.repeatInput = await page.evaluate(() => window.__task00201D4Keys);
    if (report.repeatInput.length !== 1 || !report.repeatInput[0].trusted || !report.repeatInput[0].inNotebook) throw new Error('Repeat key observation missing');
    await stage('repeat_standard_ui_key_sent_once');
    await waitEvents(es => es.some(e => { const d = targetDoc(e); return d?.cells.length === 2 && hasSummaryEnd(d.cells[0]) && hasSummaryEnd(d.cells[1]); }), 120000);
    report.afterExecution = await marker('observation-complete');
    await page.keyboard.press('Control+s'); report.savedSnapshot = await marker('saved');
    const raw = await fs.readFile(target), saved = JSON.parse(raw);
    report.saved = { sha256: sha(raw), notebook: saved };
    if (report.savedSnapshot.notebook.dirty || saved.cells.length !== 2 || saved.cells[1].source.join('') !== changedSource) throw new Error('Saved current source not verified');
    for (let i = 0; i < 2; i++) {
      if (saved.cells[i].id !== original.cells[i].id ||
          JSON.stringify(saved.cells[i].metadata.outsideDiagnosticOwner) !== JSON.stringify(original.cells[i].metadata.outsideDiagnosticOwner)) throw new Error('Cell ID/foreign metadata changed');
    }
    if (JSON.stringify(saved.metadata.outsideNotebookOwner) !== JSON.stringify(original.metadata.outsideNotebookOwner) ||
        saved.cells[0].source.join('') !== original.cells[0].source.join('')) throw new Error('Notebook/blocker invariant failed');
    report.downstreamOutput = saved.cells[1].outputs.map(o => Array.isArray(o.text) ? o.text.join('') : o.text || '').join('');
    report.downstreamSuccess = report.savedSnapshot.notebook.cells[1].executionSummary?.success;
    report.outcome = report.downstreamSuccess === true && report.downstreamOutput.includes('diagnostic CHANGED current source') ? 'observed_saved_changed_result' : 'saved_with_different_execution_result';
    if (report.outcome !== 'observed_saved_changed_result') process.exitCode = 2;
    report.environment = (await events()).find(e => e.kind === 'environment');
    await fs.copyFile(report.eventLog, path.join(out, 'events.jsonl')); await page.screenshot({ path: path.join(out, 'final.png') });
    await stage('saved_source_output_metadata_observed');
  } catch (error) {
    report.outcome = 'not_observed'; report.error = { name: error.name, message: error.message }; process.exitCode = 1;
    if (page) {
      report.quickInputChoices = await page.locator('.quick-input-list .monaco-list-row').allTextContents().catch(() => []);
      await page.screenshot({ path: path.join(out, 'stopped.png') }).catch(() => {});
      await fs.writeFile(path.join(out, 'stopped-dom.txt'), await page.locator('body').innerText().catch(() => 'unavailable'));
    }
    if (report.eventLog) await fs.copyFile(report.eventLog, path.join(out, 'events.jsonl')).catch(() => {});
  }
  await save(); console.log(JSON.stringify({ outcome: report.outcome, error: report.error }));
  if (app && !report.closedAt) {
    console.log('Window retained. Awaiting user end signal (finish).'); process.stdin.setEncoding('utf8');
    process.stdin.on('data', async input => {
      if (input.trim() !== 'finish' || report.endSignalReceived) return;
      report.endSignalReceived = true; await save();
      try {
        await app.close(); await closed;
        const ports = [report.nodeInspectorPort, report.chromiumDebugPort].filter(p => Number.isInteger(p) && p > 0);
        const listing = execFileSync('netstat.exe', ['-ano', '-p', 'tcp'], { encoding: 'utf8', windowsHide: true });
        report.portCheck = { at: new Date().toISOString(), ports: ports.map(port => ({ port, listeners: listing.split(/\r?\n/).filter(line => {
          const cols = line.trim().split(/\s+/); return cols[0] === 'TCP' && Number(cols[1]?.split(':').at(-1)) === port && cols[3] === 'LISTENING';
        }).length })) };
      } catch (error) { report.closeError = String(error); process.exitCode = 1; }
      await save(); process.stdin.pause();
    });
    process.stdin.resume(); await closed;
    // The finish handler finishes port verification before it pauses stdin.
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
