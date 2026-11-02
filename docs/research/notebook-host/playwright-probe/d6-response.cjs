'use strict';
// Research probe: actual Playwright input during the existing 20-update D6 mode.
// DOM listeners observe input/cursor only; no internal IDE calls or synthetic DOM events.
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { fileURLToPath } = require('node:url');
const { parseArgs } = require('node:util');
const { _electron: electron } = require('playwright');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

async function main() {
  const { values } = parseArgs({ options: { vscode: { type: 'string' }, out: { type: 'string' } } });
  if (!values.vscode || !values.out) throw new Error('--vscode and --out required');
  const repo = path.resolve(__dirname, '../../../..');
  const out = path.resolve(repo, values.out);
  const relative = path.relative(path.join(repo, 'results'), out);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('New results/ folder required');
  const run = path.basename(out);
  if (!/^[A-Za-z0-9-]+$/.test(run)) throw new Error('ASCII run identifier required');
  const source = path.join(repo, 'tests/notebook-host-api');
  const build = JSON.parse(await fs.readFile(path.join(source, 'dist/build.local.json'), 'utf8'));
  if (path.resolve(build.root) !== repo) throw new Error('Foreign diagnostic build');
  const hashes = {};
  for (const name of ['extension.cjs', 'model.cjs', 'fixtures.cjs', 'package.json']) {
    const bytes = await fs.readFile(path.join(source, name));
    if (!bytes.equals(await fs.readFile(path.join(source, 'dist', name))) || sha(bytes) !== build.hashes[name]) throw new Error(`Source/build mismatch: ${name}`);
    hashes[name] = sha(bytes);
  }
  await fs.mkdir(path.dirname(out), { recursive: true });
  await fs.mkdir(out);
  const fixtureFolder = path.join(build.workspace, `PW-${run}`);
  await fs.mkdir(fixtureFolder);
  const target = path.join(fixtureFolder, `PW-${run}-D6.ipynb`);
  const original = require(path.join(source, 'fixtures.cjs')).notebook('D6-burst');
  await fs.writeFile(target, JSON.stringify(original, null, 2), { flag: 'wx' });
  const profile = path.join(out, 'profile');
  await fs.mkdir(path.join(profile, 'User'), { recursive: true });
  await fs.writeFile(path.join(profile, 'User/settings.json'), JSON.stringify({
    'window.title': 'TASK-002-01 D6 Playwright ${activeEditorShort}',
    'window.restoreWindows': 'none', 'workbench.startupEditor': 'none',
    'window.dialogStyle': 'custom', 'files.autoSave': 'off',
    'extensions.autoUpdate': 'off', 'extensions.autoCheckUpdates': false, 'update.mode': 'none',
    'workbench.editorAssociations': { '*.ipynb': 'jupyter-notebook' }
  }, null, 2), { flag: 'wx' });
  const report = {
    case: 'D6-existing-change-20-response', mode: 'existing-change-20',
    route: 'fixed Playwright input plus public API diagnostic logs',
    startedAt: new Date().toISOString(), outcome: 'in_progress', stages: [],
    runnerSha256: sha(await fs.readFile(__filename)), diagnosticHashes: hashes,
    target, fixtureFolder, profileCopied: false, kernelExecuted: false,
    securityFeaturesDisabled: false, artificialUpdateDelay: false,
    manualPass: false, performanceThreshold: 'not defined', timestampResolutionMs: 1,
    playwright: require('playwright/package.json').version
  };
  await fs.copyFile(__filename, path.join(out, 'runner.cjs'));
  let app, page, closed;
  const save = () => fs.writeFile(path.join(out, 'result.local.json'), JSON.stringify(report, null, 2));
  async function stage(name) { report.stages.push({ name, at: new Date().toISOString() }); await save(); console.log(name); }
  async function focus(option) {
    await option.first().waitFor({ state: 'visible', timeout: 15000 });
    if (await option.count() !== 1) throw new Error('Ambiguous quick-input match');
    const limit = await page.locator('.quick-input-list .monaco-list-row').count() + 2;
    for (let i = 0; i < limit; i++) {
      if (await option.evaluate(el => el.classList.contains('focused'))) return;
      await page.keyboard.press('ArrowDown');
    }
    throw new Error('Quick-input focus not established');
  }
  async function accept(text) {
    const row = page.locator('.quick-input-list .monaco-list-row').filter({ hasText: text });
    await focus(row); await page.keyboard.press('Enter');
    await row.waitFor({ state: 'hidden', timeout: 10000 });
  }
  async function command(title) {
    await page.keyboard.press('Control+Shift+P');
    const input = page.locator('.quick-input-widget input');
    await input.waitFor({ state: 'visible', timeout: 10000 });
    await input.fill(`>${title}`); await accept(title);
  }
  async function readEvents() {
    if (!report.eventLog) {
      for (const entry of await fs.readdir(path.join(repo, 'logs/task-002-01'), { withFileTypes: true })) {
        if (!entry.isDirectory()) continue;
        const file = path.join(repo, 'logs/task-002-01', entry.name, 'events.jsonl');
        const text = await fs.readFile(file, 'utf8').catch(() => '');
        if (text.includes(path.basename(target))) { report.eventLog = file; break; }
      }
    }
    if (!report.eventLog) return [];
    const text = await fs.readFile(report.eventLog, 'utf8');
    return text.slice(0, text.lastIndexOf('\n')).split('\n').filter(Boolean).map(line => JSON.parse(line));
  }
  async function waitEvents(predicate, timeout = 30000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      const events = await readEvents();
      if (predicate(events)) return events;
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    throw new Error(`Diagnostic observation timeout (${timeout}ms)`);
  }
  await save();
  try {
    const env = { ...process.env };
    delete env.ELECTRON_RUN_AS_NODE; delete env.VSCODE_DEV; delete env.VSCODE_PORTABLE;
    app = await electron.launch({ executablePath: path.resolve(values.vscode), env, timeout: 45000,
      args: ['--new-window', '--skip-welcome', '--skip-release-notes', '--disable-telemetry',
        '--disable-updates', '--disable-extension=google.colab', '--locale=en',
        '--remote-debugging-address=127.0.0.1', `--user-data-dir=${profile}`,
        `--shared-data-dir=${path.join(out, 'shared-data')}`, '--extensions-dir=C:/Users/tomoh/.vscode/extensions',
        `--extensionDevelopmentPath=${path.join(source, 'dist')}`, fixtureFolder] });
    closed = new Promise(resolve => app.once('close', () => { report.closedAt = new Date().toISOString(); resolve(); }));
    page = await app.firstWindow();
    await page.locator('.monaco-workbench').waitFor({ state: 'visible', timeout: 30000 });
    const storage = path.join(profile, 'User/workspaceStorage');
    const workspaces = [];
    for (const name of await fs.readdir(storage)) {
      const text = await fs.readFile(path.join(storage, name, 'workspace.json'), 'utf8').catch(() => null);
      if (text) workspaces.push(JSON.parse(text));
    }
    if (workspaces.length !== 1 || !workspaces[0].folder || path.resolve(fileURLToPath(workspaces[0].folder)).toLowerCase() !== fixtureFolder.toLowerCase()) throw new Error('Unexpected workspace trust scope');
    await page.getByText('Manage', { exact: true }).click();
    const trust = page.locator('.workspace-trust-editor');
    await trust.getByRole('button', { name: 'Trust', exact: true }).click();
    await trust.getByRole('button', { name: "Don't Trust", exact: true }).waitFor({ state: 'visible', timeout: 10000 });
    report.trustScope = workspaces[0];
    await page.locator('.monaco-modal-editor-block').getByRole('button', { name: /Close Modal Editor/ }).click();
    await page.locator('.monaco-modal-editor-block').waitFor({ state: 'hidden', timeout: 10000 });
    await stage('approved_fixture_folder_trusted');
    // Use the unique generated Explorer entry; do not accept an unsettled Quick Open result.
    await page.getByText(path.basename(target), { exact: true }).dblclick();
    await page.locator('.tab.active').filter({ hasText: path.basename(target) }).waitFor({ state: 'visible', timeout: 15000 });
    const cell = page.locator('.code-cell-row:visible').filter({ hasText: 'fictional_value = 60' });
    await cell.waitFor({ state: 'visible', timeout: 30000 });
    if (await cell.count() !== 1) throw new Error('D6 target cell not unique');
    const editor = cell.locator('.monaco-editor');
    await editor.click(); await page.keyboard.press('Home');
    await waitEvents(events => events.some(e => e.kind === 'snapshot'));
    await editor.evaluate(element => {
      const data = window.__task00201D6 = { inputs: [], cursors: [] };
      let last = '';
      const record = (reason, force = false) => {
        const positions = [...element.querySelectorAll('.cursors-layer .cursor')].map(c => ({ left: c.style.left, top: c.style.top }));
        const value = JSON.stringify(positions);
        if (force || value !== last) { data.cursors.push({ reason, at: Date.now(), positions }); last = value; }
      };
      data.record = record;
      document.addEventListener('pointerdown', e => {
        if (element.contains(e.target)) data.inputs.push({ kind: 'pointerdown', at: Date.now(), trusted: e.isTrusted, x: e.clientX, y: e.clientY });
      }, true);
      document.addEventListener('keydown', e => {
        if (e.key === 'ArrowRight' && element.contains(e.target)) data.inputs.push({ kind: 'ArrowRight', at: Date.now(), trusted: e.isTrusted });
      }, true);
      new MutationObserver(() => record('cursor_mutation')).observe(element, { subtree: true, childList: true, attributes: true, attributeFilter: ['style'] });
      record('baseline', true);
    });
    const lines = editor.locator('.view-lines .view-line').first();
    const box = await lines.boundingBox();
    if (!box || box.width < 60 || box.height < 15) throw new Error('D6 text input point unavailable');
    const point = { x: box.x + 50, y: box.y + 10 };
    await stage('input_observers_ready');
    await command('TASK-002-01: D6 Metadata Burst');
    const modeRow = page.locator('.quick-input-list .monaco-list-row').filter({ hasText: 'existing-change-20' });
    await focus(modeRow);
    // Do not wait for burst completion or insert any artificial update delay.
    await page.keyboard.press('Enter');
    await page.mouse.click(point.x, point.y);
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => { window.__task00201D6.record('after_click', true); resolve(); })));
    await page.keyboard.press('ArrowRight');
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => { window.__task00201D6.record('after_arrow_frame', true); resolve(); })));
    const events = await waitEvents(es => es.some(e => e.kind === 'burst.summary'));
    const summary = events.find(e => e.kind === 'burst.summary');
    if (summary.mode !== 'existing-change-20' || summary.sent !== 20 || !summary.returns.every(r => r.result === true)) throw new Error('D6 update result mismatch');
    report.burst = summary;
    report.input = await page.evaluate(() => ({ inputs: window.__task00201D6.inputs, cursors: window.__task00201D6.cursors }));
    const requests = events.filter(e => e.kind === 'apply.request' && /^D6-send-\d+$/.test(e.label));
    const returns = events.filter(e => e.kind === 'apply.return' && /^D6-send-\d+$/.test(e.label));
    if (requests.length !== 20 || returns.length !== 20) throw new Error('D6 request/return evidence incomplete');
    const first = Date.parse(requests[0].at), last = Date.parse(returns.at(-1).at);
    // Strict inner interval: leave a 1ms margin for timestamp quantization, not a performance threshold.
    const inside = at => at > first + 1 && at < last - 1;
    const pointer = report.input.inputs.find(e => e.kind === 'pointerdown');
    const key = report.input.inputs.find(e => e.kind === 'ArrowRight');
    const base = report.input.cursors.find(e => e.reason === 'after_click');
    const moved = base?.positions.length && key && report.input.cursors.find(e => e.at >= key.at && e.positions.length === base.positions.length && JSON.stringify(e.positions) !== JSON.stringify(base.positions));
    report.overlap = { firstRequestAt: requests[0].at, lastReturnAt: returns.at(-1).at,
      pointerDuring: Boolean(pointer && pointer.trusted && inside(pointer.at)),
      arrowDuring: Boolean(key && key.trusted && inside(key.at)),
      cursorMovedDuring: Boolean(moved && inside(moved.at)), cursorChange: moved || null };
    await stage('burst_and_input_evidence_collected');
    await page.keyboard.press('Control+s');
    await command('TASK-002-01: Record Step'); await accept('saved');
    const finalEvents = await waitEvents(es => es.some(e => e.kind === 'snapshot' && e.label === 'saved'));
    report.finalSnapshot = finalEvents.filter(e => e.kind === 'snapshot' && e.label === 'saved').at(-1);
    const doc = report.finalSnapshot.notebooks.find(n => !n.closed && n.uri.includes(path.basename(target)));
    const saved = JSON.parse(await fs.readFile(target, 'utf8'));
    if (!doc || doc.dirty || saved.cells.length !== 1 || saved.cells[0].source.join('') !== original.cells[0].source.join('') ||
      saved.cells[0].id !== original.cells[0].id || saved.cells[0].execution_count !== null || saved.cells[0].outputs.length !== 0 || saved.cells[0].metadata.task00201Diagnostic.burst !== 20 ||
      JSON.stringify(saved.cells[0].metadata.outsideDiagnosticOwner) !== JSON.stringify(original.cells[0].metadata.outsideDiagnosticOwner) ||
      JSON.stringify(saved.metadata.outsideNotebookOwner) !== JSON.stringify(original.metadata.outsideNotebookOwner)) throw new Error('D6 saved-data invariant failed');
    report.saved = { notebook: saved, sha256: sha(await fs.readFile(target)) };
    await fs.copyFile(report.eventLog, path.join(out, 'events.jsonl'));
    await page.screenshot({ path: path.join(out, 'final.png') });
    const o = report.overlap;
    report.outcome = o.pointerDuring && o.arrowDuring && o.cursorMovedDuring ? 'observed_during_updates' : 'overlap_not_established';
    if (report.outcome !== 'observed_during_updates') process.exitCode = 2;
    await stage('saved_and_overlap_classified');
  } catch (error) {
    report.outcome = 'not_observed'; report.error = { name: error.name, message: error.message }; process.exitCode = 1;
    if (page) {
      report.modalControls = await page.locator('.monaco-modal-editor-block [role="button"]').evaluateAll(nodes => nodes.map(n => ({ label: n.getAttribute('aria-label'), title: n.getAttribute('title'), text: n.textContent }))).catch(() => []);
      await page.screenshot({ path: path.join(out, 'stopped.png') }).catch(() => {});
      await fs.writeFile(path.join(out, 'stopped-dom.txt'), await page.locator('body').innerText().catch(() => 'unavailable'));
    }
  }
  await save(); console.log(JSON.stringify({ outcome: report.outcome, overlap: report.overlap, error: report.error }));
  if (app && !report.closedAt) {
    console.log('Window retained. Awaiting user end signal (finish).');
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', async input => { if (input.trim() === 'finish') { report.endSignalReceived = true; await app.close(); } });
    process.stdin.resume(); await closed; process.stdin.pause(); await save();
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
