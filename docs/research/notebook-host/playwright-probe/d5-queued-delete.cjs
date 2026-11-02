'use strict';
// Diagnostic UI research only. Fixed Playwright input; no internal IDE calls.
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { fileURLToPath } = require('node:url');
const { parseArgs } = require('node:util');
const { _electron: electron } = require('playwright');

async function main() {
  const { values } = parseArgs({ options: {
    vscode: { type: 'string' }, out: { type: 'string' }, case: { type: 'string', default: 'D5-queued-delete' }
  }});
  if (!values.vscode || !values.out) throw new Error('--vscode and --out are required');
  const caseName = values.case;
  if (!['D5-queued-delete', 'D5-running-delete', 'D5-queued-close', 'D5-running-close'].includes(caseName)) throw new Error('Unapproved D5 case');
  const queuedCase = caseName.includes('-queued-');
  const closeCase = caseName.endsWith('-close');
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
  // User approved trust for this new folder only, not its parents or old data.
  const fixtureFolder = path.join(build.workspace, `PW-${run}`);
  await fs.mkdir(fixtureFolder);
  const target = path.join(fixtureFolder, `PW-${run}-${caseName}.ipynb`);
  const bootstrap = path.join(fixtureFolder, `PW-${run}-kernel.ipynb`);
  const originalFixture = notebook(caseName);
  await fs.writeFile(target, JSON.stringify(originalFixture, null, 2), { flag: 'wx' });
  await fs.writeFile(bootstrap, JSON.stringify(notebook('D4-environment'), null, 2), { flag: 'wx' });
  const profile = path.join(out, 'profile');
  await fs.mkdir(path.join(profile, 'User'), { recursive: true });
  await fs.writeFile(path.join(profile, 'User/settings.json'), JSON.stringify({
    'window.title': 'TASK-002-01 D5 Playwright ${activeEditorShort}',
    'window.restoreWindows': 'none', 'workbench.startupEditor': 'none',
    'window.dialogStyle': 'custom',
    'files.autoSave': 'off', 'extensions.autoUpdate': false,
    'extensions.autoCheckUpdates': false, 'update.mode': 'none',
    'workbench.editorAssociations': { '*.ipynb': 'jupyter-notebook' },
    'python.defaultInterpreterPath': 'C:\\Python314\\python.exe'
  }, null, 2), { flag: 'wx' });
  const report = {
    case: caseName, route: 'fixed Playwright UI automation',
    manualPass: false, outcome: 'not_started', stages: [],
    startedAt: new Date().toISOString(), target, bootstrap, fixtureFolder,
    playwright: require('playwright/package.json').version,
    profileCopied: false, securityFeaturesDisabled: false
  };
  report.runnerSha256 = crypto.createHash('sha256').update(await fs.readFile(__filename)).digest('hex');
  await fs.copyFile(__filename, path.join(out, 'runner.cjs'));
  let app, page, closed;
  const save = () => fs.writeFile(path.join(out, 'result.local.json'), JSON.stringify(report, null, 2));
  async function stage(name, data = {}) {
    report.stages.push({ name, at: new Date().toISOString(), ...data });
    await save(); console.log(name);
  }
  async function accept(option) {
    await option.first().waitFor({ state: 'visible', timeout: 15000 });
    if (await option.count() !== 1) throw new Error('Ambiguous quick-input match');
    const limit = await page.locator('.quick-input-list .monaco-list-row').count() + 2;
    // Match VS Code's automation: move focus to the exact row, Enter, await acceptance.
    for (let i = 0; i < limit; i++) {
      if (await option.evaluate(el => el.classList.contains('focused'))) {
        await page.keyboard.press('Enter');
        await option.waitFor({ state: 'hidden', timeout: 10000 });
        return;
      }
      await page.keyboard.press('ArrowDown');
    }
    throw new Error('Quick-input focus did not reach the required row');
  }
  async function command(title) {
    await page.keyboard.press('Control+Shift+P');
    const input = page.locator('.quick-input-widget input');
    await input.waitFor({ state: 'visible', timeout: 10000 });
    await input.fill(`>${title}`);
    report.lastCommand = { title, input: await input.inputValue() };
    const option = page.locator('.quick-input-list .monaco-list-row').filter({ hasText: title });
    await accept(option);
  }
  async function choice(text) {
    const option = page.locator('.quick-input-list .monaco-list-row').filter({ hasText: text });
    await accept(option);
  }
  async function selectPython() {
    const rows = page.locator('.quick-input-list .monaco-list-row');
    await rows.first().waitFor({ state: 'visible', timeout: 10000 });
    const existing = rows.filter({ hasText: /c:\\Python314\\python\.exe/i });
    if (await existing.count() === 1) await accept(existing);
    else {
      await choice('Python Environments');
      await choice('C:\\Python314\\python.exe');
    }
    await page.locator('.quick-input-widget').waitFor({ state: 'hidden', timeout: 10000 });
  }
  async function runAll() {
    await command('Notebook: Run All');
    // In this VS Code build Run All can request a kernel even after selection.
    const pick = page.locator('.quick-input-widget');
    const prompted = await pick.waitFor({ state: 'visible', timeout: 3000 }).then(() => true, () => false);
    if (prompted) {
      await selectPython();
      await stage('run_all_kernel_prompt_completed');
    }
  }
  async function open(file) {
    await page.keyboard.press('Control+p');
    const input = page.locator('.quick-input-widget input');
    await input.fill(file); await input.press('Enter');
    await page.locator('.tabs-container .tab.active').filter({ hasText: path.basename(file) }).waitFor({ state: 'visible', timeout: 15000 });
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
        '--extensions-dir=C:/Users/tomoh/.vscode/extensions',
        `--extensionDevelopmentPath=${path.join(source, 'dist')}`, fixtureFolder] });
    closed = new Promise(resolve => app.once('close', () => { report.closedAt = new Date().toISOString(); resolve(); }));
    page = await app.firstWindow();
    await page.locator('.monaco-workbench').waitFor({ state: 'visible', timeout: 30000 });
    const storage = path.join(profile, 'User/workspaceStorage');
    const workspaceFiles = [];
    for (const entry of await fs.readdir(storage)) {
      const file = path.join(storage, entry, 'workspace.json');
      const json = await fs.readFile(file, 'utf8').catch(() => null);
      if (json) workspaceFiles.push(JSON.parse(json));
    }
    if (workspaceFiles.length !== 1 || !workspaceFiles[0].folder ||
        path.resolve(fileURLToPath(workspaceFiles[0].folder)).toLowerCase() !== fixtureFolder.toLowerCase()) {
      throw new Error('Window does not contain exactly the approved fixture folder');
    }
    await page.getByText('Manage', { exact: true }).click();
    const trustEditor = page.locator('.workspace-trust-editor');
    await trustEditor.waitFor({ state: 'visible', timeout: 10000 });
    const trustText = await trustEditor.innerText();
    report.trustScope = workspaceFiles[0];
    report.trustEditor = trustText;
    await trustEditor.getByRole('button', { name: 'Trust', exact: true }).click();
    await trustEditor.getByRole('button', { name: "Don't Trust", exact: true }).waitFor({ state: 'visible', timeout: 10000 });
    await stage('trust_granted_for_new_fixture_folder_only');
    await open(bootstrap);
    await stage('notebook_rendered');
    // Stop on any trust, installation, or authentication prompt; never bypass it.
    if (await page.locator('.monaco-dialog-box').isVisible()) throw new Error('Dialog requires review; no automatic security decision');
    await command('Notebook: Select Notebook Kernel');
    await selectPython();
    await stage('standard_python_kernel_selected');
    await runAll();
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
    await selectPython();
    await marker('execution-request-before');
    await runAll();
    const startedLabel = queuedCase ? 'D5 blocker' : 'D5 running';
    const startedHashes = [`${startedLabel} started\n`, `${startedLabel} started\r\n`].map(text => crypto.createHash('sha256').update(text).digest('hex'));
    await waitEvents(es => es.some(e => e.notebook?.uri?.includes(path.basename(target)) && e.notebook.cells[0]?.outputs.some(o => o.items.some(i => startedHashes.includes(i.sha256)))), 60000);
    await stage('blocker_started_output_observed_in_public_event');
    const targetIndex = queuedCase ? 1 : 0;
    const selectedCell = page.locator('.code-cell-row:visible').filter({ hasText: queuedCase ? 'D5 queued original' : "print('D5 running started'" });
    if (await selectedCell.count() !== 1) throw new Error('Target cell UI is not unique');
    await selectedCell.locator('.monaco-editor').click();
    await page.keyboard.press('Escape');
    await command('TASK-002-01: D5 Arm Delayed Local Update');
    const armed = await waitEvents(events => events.some(e => e.kind === 'local-delay.arm'), 5000);
    const arm = armed.find(e => e.kind === 'local-delay.arm');
    report.arm = arm;
    const prior = [...armed].reverse().find(e => e.notebook?.uri?.includes(path.basename(target)));
    const targetState = prior?.notebook?.cells?.[targetIndex];
    if (!targetState || targetState.object !== arm.cellObject) throw new Error('Arm target does not match the intended cell');
    if (queuedCase && targetState.executionSummary?.timing?.startTime) throw new Error('Queued target already started');
    report.targetBeforeMutation = { cell: targetState, uiText: await selectedCell.innerText() };
    await page.screenshot({ path: path.join(out, 'target-before-mutation.png') });
    await marker('D5-before-close-or-delete');
    if (closeCase) {
      // Explicit condition: save before closing; this does not test unsaved-close dialogs.
      await page.keyboard.press('Control+s');
      await waitEvents(es => es.some(e => e.kind === 'notebook.save' && e.notebook.uri.includes(path.basename(target))), 5000);
      report.closeCondition = 'saved before closing; no unsaved-close dialog acceptance inferred';
      await page.keyboard.press('Control+w');
      await waitEvents(es => es.some(e => e.kind === 'notebook.tabClosed' && e.uri.includes(path.basename(target))), 5000);
      await page.keyboard.press('Control+Shift+t');
      await page.locator('.tabs-container .tab.active').filter({ hasText: path.basename(target) }).waitFor({ state: 'visible', timeout: 5000 });
      await marker('reopened');
      await stage('tab_closed_and_same_path_reopened_through_UI');
    } else {
      await selectedCell.hover();
      await selectedCell.getByRole('button', { name: /Delete Cell/ }).click();
      if (!queuedCase) {
        const confirmation = page.locator('.monaco-dialog-box');
        await confirmation.waitFor({ state: 'visible', timeout: 3000 });
        report.deleteConfirmation = await confirmation.innerText();
        if (!report.deleteConfirmation.includes('This cell is running, are you sure you want to delete it?')) throw new Error('Unexpected deletion confirmation');
        await confirmation.getByRole('button', { name: 'Delete', exact: true }).click();
        await confirmation.waitFor({ state: 'hidden', timeout: 3000 });
      }
      await stage('target_cell_delete_button_clicked');
    }
    const events = await waitEvents(es => es.some(e => e.kind === 'local-delay.guard' && e.token === arm.token), 20000);
    report.guard = events.find(e => e.kind === 'local-delay.guard' && e.token === arm.token);
    if (report.guard.valid !== false) throw new Error('Old diagnostic target remained valid');
    if (caseName === 'D5-queued-delete') {
      await waitEvents(es => es.some(e => e.notebook?.uri?.includes(path.basename(target)) && e.notebook.cells.length === 1 && e.notebook.cells[0].executionSummary?.success === true), 105000);
    } else {
      const completion = es => es.some(e => e.notebook?.uri?.includes(path.basename(target)) &&
        e.notebook.retainedCells.some(c => c.source === originalFixture.cells[0].source.join('') && typeof c.executionSummary?.success === 'boolean'));
      try { await waitEvents(completion, Math.max(1000, Date.parse(arm.at) + 100000 - Date.now())); }
      catch (error) {
        if (!error.message.startsWith('Diagnostic observation timeout')) throw error;
        report.executionCompletion = 'not observed within 100 seconds after arm';
      }
    }
    await marker('observation-complete'); await page.keyboard.press('Control+s');
    await marker('saved');
    const finalEvents = await waitEvents(es => es.some(e => e.kind === 'snapshot' && e.label === 'saved'), 10000);
    const finalSnapshot = finalEvents.filter(e => e.kind === 'snapshot' && e.label === 'saved').at(-1);
    const active = finalSnapshot.notebooks.filter(n => n.uri.includes(path.basename(target)) && !n.closed);
    if (active.length !== 1 || active[0].dirty) throw new Error('Final Notebook saved state not verified');
    report.finalObservation = finalSnapshot;
    const saved = JSON.parse(await fs.readFile(target, 'utf8'));
    const expectedCells = closeCase ? originalFixture.cells : originalFixture.cells.filter((_, i) => i !== targetIndex);
    if (saved.cells.length !== expectedCells.length) throw new Error('Saved cell count differs');
    for (let i = 0; i < expectedCells.length; i++) {
      if (saved.cells[i].source.join('') !== expectedCells[i].source.join('') || saved.cells[i].id !== expectedCells[i].id ||
          JSON.stringify(saved.cells[i].metadata.outsideDiagnosticOwner) !== JSON.stringify(expectedCells[i].metadata.outsideDiagnosticOwner) ||
          saved.cells[i].metadata.task00201Diagnostic?.delayedLocalToken) throw new Error('Saved fixture invariant failed');
    }
    if (JSON.stringify(saved.metadata.outsideNotebookOwner) !== JSON.stringify(originalFixture.metadata.outsideNotebookOwner)) throw new Error('Unowned Notebook metadata changed');
    report.saved = saved;
    await fs.copyFile(report.eventLog, path.join(out, 'events.jsonl'));
    report.outcome = 'observed'; await stage('saved_expected_cells_and_guard_rejected_old_target');
  } catch (error) {
    report.outcome = 'not_observed'; report.error = { name: error.name, message: error.message };
    process.exitCode = 1;
    if (page) {
      report.quickInput = await page.locator('.quick-input-widget input').inputValue().catch(() => null);
      report.quickInputChoices = await page.locator('.quick-input-list .monaco-list-row').allTextContents().catch(() => []);
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
