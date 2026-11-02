'use strict';
// Diagnostic UI research only. Fixed Playwright input; no internal IDE calls.
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { parseArgs } = require('node:util');
const { _electron: electron } = require('playwright');

async function main() {
  const { values } = parseArgs({ options: {
    vscode: { type: 'string' }, out: { type: 'string' }
  }});
  if (!values.vscode || !values.out) throw new Error('--vscode and --out are required');
  const repo = path.resolve(__dirname, '../../../..');
  const out = path.resolve(repo, values.out);
  const relative = path.relative(path.join(repo, 'results'), out);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('New results/ directory required');
  const source = path.join(repo, 'tests/notebook-host-api');
  const build = JSON.parse(await fs.readFile(path.join(source, 'dist/build.local.json'), 'utf8'));
  if (path.resolve(build.root) !== repo) throw new Error('Diagnostic build belongs to another checkout');
  for (const name of ['extension.cjs', 'model.cjs', 'fixtures.cjs', 'package.json']) {
    const a = await fs.readFile(path.join(source, name));
    const b = await fs.readFile(path.join(source, 'dist', name));
    if (!a.equals(b) || crypto.createHash('sha256').update(a).digest('hex') !== build.hashes[name]) {
      throw new Error(`Diagnostic source/build mismatch: ${name}`);
    }
  }
  await fs.mkdir(path.dirname(out), { recursive: true });
  await fs.mkdir(out); // Preserve all previous runs.
  const run = path.basename(out);
  if (!/^[A-Za-z0-9-]+$/.test(run)) throw new Error('ASCII run identifier required');
  const { notebook } = require(path.join(source, 'fixtures.cjs'));
  const target = path.join(build.workspace, `PW-${run}-D5-queued-delete.ipynb`);
  const bootstrap = path.join(build.workspace, `PW-${run}-kernel.ipynb`);
  await fs.writeFile(target, JSON.stringify(notebook('D5-queued-delete'), null, 2), { flag: 'wx' });
  await fs.writeFile(bootstrap, JSON.stringify(notebook('D4-environment'), null, 2), { flag: 'wx' });
  const profile = path.join(out, 'profile');
  await fs.mkdir(path.join(profile, 'User'), { recursive: true });
  await fs.writeFile(path.join(profile, 'User/settings.json'), JSON.stringify({
    'window.title': 'TASK-002-01 D5 Playwright ${activeEditorShort}',
    'window.restoreWindows': 'none', 'workbench.startupEditor': 'none',
    'files.autoSave': 'off', 'extensions.autoUpdate': false,
    'extensions.autoCheckUpdates': false, 'update.mode': 'none',
    'python.defaultInterpreterPath': 'C:\\Python314\\python.exe'
  }, null, 2), { flag: 'wx' });
  const report = {
    case: 'D5-queued-delete', route: 'fixed Playwright UI automation',
    manualPass: false, outcome: 'not_started', stages: [],
    startedAt: new Date().toISOString(), target, bootstrap,
    playwright: require('playwright/package.json').version,
    profileCopied: false, securityFeaturesDisabled: false
  };
  let app, page, closed;
  const save = () => fs.writeFile(path.join(out, 'result.local.json'), JSON.stringify(report, null, 2));
  async function stage(name, data = {}) {
    report.stages.push({ name, at: new Date().toISOString(), ...data });
    await save(); console.log(name);
  }
  async function command(title) {
    await page.keyboard.press('Control+Shift+P');
    const input = page.locator('.quick-input-widget input');
    await input.waitFor({ state: 'visible', timeout: 10000 });
    await input.fill(`>${title}`);
    const option = page.locator('.quick-input-list .monaco-list-row').filter({ hasText: title });
    if (await option.count() > 1) throw new Error(`Ambiguous command: ${title}`);
    await option.first().waitFor({ state: 'visible', timeout: 10000 });
    await input.press('Enter');
  }
  async function choice(text) {
    const option = page.locator('.quick-input-list .monaco-list-row').filter({ hasText: text });
    await option.first().waitFor({ state: 'visible', timeout: 15000 });
    if (await option.count() !== 1) throw new Error(`Ambiguous choice: ${text}`);
    await option.click();
  }
  async function open(file) {
    await page.keyboard.press('Control+p');
    const input = page.locator('.quick-input-widget input');
    await input.fill(file); await input.press('Enter');
    await page.locator('.code-cell-row').first().waitFor({ state: 'visible', timeout: 30000 });
  }
  async function marker(name) {
    await command('TASK-002-01: Record Step'); await choice(name);
  }
  async function diagnosticLog() {
    const entries = await fs.readdir(path.join(repo, 'logs/task-002-01'), { withFileTypes: true });
    for (const entry of entries.filter(e => e.isDirectory())) {
      const file = path.join(repo, 'logs/task-002-01', entry.name, 'events.jsonl');
      const text = await fs.readFile(file, 'utf8').catch(() => '');
      if (text.includes(path.basename(target)) || text.includes(path.basename(bootstrap))) return file;
    }
    return null;
  }
  async function waitEvents(predicate, timeout) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      const file = report.eventLog || await diagnosticLog();
      if (file) {
        report.eventLog = file;
        const events = (await fs.readFile(file, 'utf8')).trim().split('\n').map(s => JSON.parse(s));
        if (predicate(events)) return events;
      }
      await new Promise(resolve => setTimeout(resolve, 250));
    }
    throw new Error(`Diagnostic observation timeout (${timeout}ms)`);
  }
  try {
    const env = { ...process.env };
    delete env.ELECTRON_RUN_AS_NODE; delete env.VSCODE_DEV; delete env.VSCODE_PORTABLE;
    app = await electron.launch({ executablePath: path.resolve(values.vscode), env, timeout: 45000,
      args: ['--new-window', '--skip-welcome', '--skip-release-notes', '--disable-telemetry',
        '--disable-updates', '--disable-extension=google.colab', '--locale=en',
        '--remote-debugging-address=127.0.0.1', `--user-data-dir=${profile}`,
        `--shared-data-dir=${path.join(out, 'shared-data')}`,
        `--extensionDevelopmentPath=${path.join(source, 'dist')}`, bootstrap] });
    closed = new Promise(resolve => app.once('close', () => { report.closedAt = new Date().toISOString(); resolve(); }));
    page = await app.firstWindow();
    await page.locator('.monaco-workbench').waitFor({ state: 'visible', timeout: 30000 });
    await page.locator('.code-cell-row').first().waitFor({ state: 'visible', timeout: 30000 });
    await stage('notebook_rendered');
    // Stop on any trust, installation, or authentication prompt; never bypass it.
    if (await page.locator('.monaco-dialog-box').isVisible()) throw new Error('Dialog requires review; no automatic security decision');
    await command('Notebook: Select Notebook Kernel');
    await choice('Python Environments');
    await choice('C:\\Python314\\python.exe');
    await stage('standard_python_kernel_selected');
    await command('Notebook: Run All');
    // Environment check is for this new profile, not a rerun of D4 mutation cases.
    await waitEvents(es => es.some(e => e.notebook?.uri?.includes(path.basename(bootstrap)) && e.notebook.cells[0]?.executionSummary?.success === true), 60000);
    await page.keyboard.press('Control+s');
    await waitEvents(es => es.some(e => e.kind === 'notebook.save' && e.notebook.uri.includes(path.basename(bootstrap))), 10000);
    const environmentFile = JSON.parse(await fs.readFile(bootstrap, 'utf8'));
    const environmentOutput = environmentFile.cells[0].outputs.map(o => (o.text || []).join('')).join('');
    report.kernelEnvironment = JSON.parse(environmentOutput);
    if (!report.kernelEnvironment.ipykernel || !report.kernelEnvironment.jupyter_client) throw new Error('Kernel environment output missing');
    await stage('kernel_preflight_saved_output_verified');
    await open(target);
    await command('Notebook: Select Notebook Kernel');
    await choice('Python Environments');
    await choice('C:\\Python314\\python.exe');
    await marker('execution-request-before');
    await command('Notebook: Run All');
    await page.getByText('D5 blocker started', { exact: true }).waitFor({ state: 'visible', timeout: 60000 });
    await stage('blocker_started');
    const queued = page.locator('.code-cell-row').nth(1);
    await queued.locator('.cell-focus-indicator-left').click();
    await command('TASK-002-01: D5 Arm Delayed Local Update');
    const armed = await waitEvents(events => events.some(e => e.kind === 'local-delay.arm'), 5000);
    const arm = armed.find(e => e.kind === 'local-delay.arm');
    report.arm = arm;
    const prior = [...armed].reverse().find(e => e.notebook?.uri?.includes(path.basename(target)));
    const targetState = prior?.notebook?.cells?.[1];
    if (!targetState || targetState.object !== arm.cellObject) throw new Error('Arm target is not the queued cell');
    if (targetState.executionSummary?.timing?.startTime) throw new Error('Queued target already started');
    report.queuedBeforeDeletion = { cell: targetState, uiText: await queued.innerText() };
    await page.screenshot({ path: path.join(out, 'queued-before-delete.png') });
    await marker('D5-before-close-or-delete');
    await queued.hover();
    const remove = queued.getByRole('button', { name: /Delete Cell/ });
    await remove.click();
    await stage('queued_cell_delete_button_clicked');
    const events = await waitEvents(es => es.some(e => e.kind === 'local-delay.guard' && e.token === arm.token), 20000);
    report.guard = events.find(e => e.kind === 'local-delay.guard' && e.token === arm.token);
    if (report.guard.valid !== false) throw new Error('Old diagnostic target remained valid');
    await waitEvents(es => es.some(e => e.notebook?.uri?.includes(path.basename(target)) && e.notebook.cells.length === 1 && e.notebook.cells[0].executionSummary?.success === true), 105000);
    await marker('observation-complete'); await page.keyboard.press('Control+s');
    await waitEvents(es => es.some(e => e.kind === 'notebook.save' && e.notebook.uri.includes(path.basename(target))), 10000);
    const saved = JSON.parse(await fs.readFile(target, 'utf8'));
    if (saved.cells.length !== 1 || saved.cells[0].metadata.outsideDiagnosticOwner.sentinel !== 'keep-blocker') throw new Error('Saved fixture invariant failed');
    report.saved = saved;
    await fs.copyFile(report.eventLog, path.join(out, 'events.jsonl'));
    report.outcome = 'observed'; await stage('saved_one_cell_and_guard_rejected_old_target');
  } catch (error) {
    report.outcome = 'not_observed'; report.error = { name: error.name, message: error.message };
    process.exitCode = 1;
    if (page) {
      await page.screenshot({ path: path.join(out, 'stopped.png') }).catch(() => {});
      await fs.writeFile(path.join(out, 'stopped-dom.txt'), await page.locator('body').innerText().catch(() => 'unavailable'));
    }
  }
  await save(); console.log(JSON.stringify({ outcome: report.outcome, error: report.error }));
  if (app && !report.closedAt) {
    console.log('Window retained. Awaiting user end signal (finish).');
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', async input => { if (input.trim() === 'finish') { report.endSignalReceived = true; await app.close(); } });
    process.stdin.resume(); await closed; process.stdin.pause(); await save();
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
