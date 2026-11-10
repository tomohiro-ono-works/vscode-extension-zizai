'use strict';
// Fixed Playwright research: real completion -> VS Code simple file dialog -> Notebook save.
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const { parseArgs } = require('node:util');
const { _electron: electron } = require('playwright');

async function main() {
  const { values } = parseArgs({ options: { vscode: { type: 'string' }, out: { type: 'string' } } });
  if (!values.vscode || !values.out) throw Error('--vscode and --out required');
  const repo = path.resolve(__dirname, '../../../..');
  const out = path.resolve(repo, values.out);
  const relative = path.relative(path.join(repo, 'results'), out);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) throw Error('New results subdirectory required');
  await fs.mkdir(out); // Refuse to overwrite any earlier run or profile.
  const workspace = path.join(out, 'workspace');
  const profile = path.join(out, 'profile');
  const extensions = path.join(out, 'extensions');
  await fs.mkdir(workspace); await fs.mkdir(extensions);
  await fs.mkdir(path.join(profile, 'User'), { recursive: true });
  const chosenFolder = path.join(workspace, '資料');
  await fs.mkdir(chosenFolder);
  const chosenFile = path.join(chosenFolder, "売上 O'Reilly-${HOME}.csv");
  await fs.writeFile(chosenFile, 'value\n1\n', { flag: 'wx' });
  const notebookFile = path.join(workspace, 'path-completion.ipynb');
  const original = { cells: [{ cell_type: 'code', execution_count: null,
    id: 'path-completion-cell', metadata: { researchPreserve: true }, outputs: [], source: ['path = '] }],
    metadata: { language_info: { name: 'python' }, researchPreserve: true }, nbformat: 4, nbformat_minor: 5 };
  await fs.writeFile(notebookFile, JSON.stringify(original, null, 2), { flag: 'wx' });
  await fs.writeFile(path.join(profile, 'User/settings.json'), JSON.stringify({
    'window.title': 'Zizai Path Completion Research ${activeEditorShort}',
    'window.restoreWindows': 'none', 'workbench.startupEditor': 'none',
    'files.simpleDialog.enable': true, 'window.dialogStyle': 'custom',
    'files.autoSave': 'off', 'extensions.autoUpdate': 'off', 'extensions.autoCheckUpdates': false,
    'update.mode': 'none', 'editor.wordBasedSuggestions': 'off',
    'editor.quickSuggestions': { other: 'on', comments: 'off', strings: 'off' },
    'editor.suggest.snippetsPreventQuickSuggestions': false,
    'workbench.editorAssociations': { '*.ipynb': 'jupyter-notebook' }
  }, null, 2), { flag: 'wx' });
  const extension = path.join(repo, 'tests/notebook-ui-gate/path-completion');
  const report = { purpose: 'path completion; real workbench + standard simple dialog; no kernel',
    startedAt: new Date().toISOString(), outcome: 'in_progress', stages: [],
    playwright: require('playwright/package.json').version, node: process.version,
    fixtureWorkspace: workspace, dialog: 'VS Code simple dialog (not OS native dialog)',
    commandPaletteUsed: false, kernelExecuted: false, userProfileModified: false,
    extensionHash: crypto.createHash('sha256').update(await fs.readFile(path.join(extension, 'extension.cjs'))).digest('hex') };
  const save = () => fs.writeFile(path.join(out, 'result.local.json'), JSON.stringify(report, null, 2));
  const stage = async name => { report.stages.push({ name, at: new Date().toISOString() }); await save(); console.log(name); };
  let app, page, closed;
  async function screenshot(name) { await page.screenshot({ path: path.join(out, name + '.png') }); }
  async function selectCompletion(label) {
    const row = page.locator('.suggest-widget.visible .monaco-list-row').filter({ hasText: label });
    await row.waitFor({ state: 'visible', timeout: 15000 });
    const count = await page.locator('.suggest-widget.visible .monaco-list-row').count();
    for (let i = 0; i <= count; i++) {
      if (await row.evaluate(e => e.classList.contains('focused'))) {
        await page.keyboard.press('Enter'); return;
      }
      await page.keyboard.press('ArrowDown');
    }
    throw Error('Expected completion was not focused');
  }
  async function savedCell(expected) {
    await page.keyboard.press('Control+s');
    // VS Code's file URI normalizes Windows drive letters; do not change the chosen path.
    const lowerDrive = expected.replace(/^path = "([A-Z]):/, (_, drive) => 'path = "' + drive.toLowerCase() + ':');
    let parsed;
    const until = Date.now() + 10000;
    while (Date.now() < until) {
      parsed = JSON.parse(await fs.readFile(notebookFile, 'utf8'));
      const text = Array.isArray(parsed.cells[0].source) ? parsed.cells[0].source.join('') : parsed.cells[0].source;
      if (text === expected || text === lowerDrive) break;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    const cell = parsed.cells[0];
    const text = Array.isArray(cell.source) ? cell.source.join('') : cell.source;
    if ((text !== expected && text !== lowerDrive) || cell.execution_count !== null || cell.outputs.length !== 0 ||
        cell.metadata.researchPreserve !== true || parsed.metadata.researchPreserve !== true || parsed.cells.length !== 1) {
      throw Error('Saved Notebook does not match the expected insertion or preservation');
    }
    return { sourceMatches: true, metadataPreserved: true, outputsEmpty: true, executionCount: null };
  }
  try {
    const env = { ...process.env };
    delete env.ELECTRON_RUN_AS_NODE; delete env.VSCODE_DEV; delete env.VSCODE_PORTABLE;
    app = await electron.launch({ executablePath: path.resolve(values.vscode), env, timeout: 45000,
      args: ['--new-window', '--skip-welcome', '--skip-release-notes', '--disable-telemetry', '--disable-updates',
        '--locale=en', '--remote-debugging-address=127.0.0.1', '--user-data-dir=' + profile,
        '--shared-data-dir=' + path.join(out, 'shared-data'), '--extensions-dir=' + extensions,
        '--extensionDevelopmentPath=' + extension, workspace] });
    closed = new Promise(resolve => app.once('close', () => { report.closedAt = new Date().toISOString(); resolve(); }));
    report.pid = app.process().pid;
    report.nodeInspectorPort = await app.evaluate(() => process.debugPort);
    report.chromiumDebugPort = Number((await fs.readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]);
    page = await app.firstWindow();
    await page.locator('.monaco-workbench').waitFor({ state: 'visible', timeout: 30000 });
    await stage('dedicated_workbench_open');
    const trust = page.getByRole('button', { name: /Yes, I trust the authors/ });
    if (await trust.waitFor({ state: 'visible', timeout: 3500 }).then(() => true, () => false)) {
      await trust.click(); await stage('dedicated_fixture_trusted');
    } else {
      const manage = page.getByText('Manage', { exact: true });
      if (await manage.isVisible()) {
        await manage.click();
        await page.locator('.workspace-trust-editor').getByRole('button', { name: 'Trust', exact: true }).click();
        await page.locator('.workspace-trust-editor').getByRole('button', { name: "Don't Trust", exact: true }).waitFor({ state: 'visible' });
        await page.locator('.monaco-modal-editor-block').getByRole('button', { name: /Close Modal Editor/ }).click();
        await stage('dedicated_fixture_trusted');
      }
    }
    await page.getByText('path-completion.ipynb', { exact: true }).dblclick();
    const editor = page.locator('.monaco-editor[data-uri*="path-completion.ipynb"]').first();
    await editor.waitFor({ state: 'visible', timeout: 30000 });
    await editor.locator('.view-lines').click();
    await page.keyboard.press('Control+End');
    await page.keyboard.type('@folder', { delay: 100 });
    await screenshot('folder-completion');
    await selectCompletion('@folder');
    const input = page.locator('.quick-input-widget input').first();
    await input.waitFor({ state: 'visible', timeout: 15000 });
    await screenshot('folder-dialog');
    await stage('folder_completion_opened_standard_dialog');
    await input.fill(chosenFolder.replaceAll('\\', '/') + '/');
    await page.keyboard.press('Enter');
    // The simple file picker may navigate on Enter; its accept button selects the folder.
    const ok = page.getByRole('button', { name: /^(OK|フォルダパスを挿入)$/ });
    if (await input.isVisible() && await ok.count() === 1) await ok.click();
    await input.waitFor({ state: 'hidden', timeout: 10000 });
    report.folder = await savedCell('path = ' + JSON.stringify(chosenFolder));
    await screenshot('folder-inserted'); await stage('folder_literal_inserted_and_saved');
    await editor.locator('.view-lines').click(); await page.keyboard.press('Control+a');
    await page.keyboard.type('path = @file', { delay: 100 });
    await selectCompletion('@file');
    await input.waitFor({ state: 'visible', timeout: 10000 });
    await input.fill(chosenFile.replaceAll('\\', '/'));
    await page.keyboard.press('Enter');
    if (await input.isVisible()) await page.getByRole('button', { name: 'ファイルパスを挿入', exact: true }).click();
    await input.waitFor({ state: 'hidden', timeout: 10000 });
    report.file = await savedCell('path = ' + JSON.stringify(chosenFile));
    await screenshot('file-inserted'); await stage('file_literal_inserted_and_saved');
    await editor.locator('.view-lines').click(); await page.keyboard.press('Control+a');
    await page.keyboard.type('path = @folder', { delay: 100 }); await selectCompletion('@folder');
    await input.waitFor({ state: 'visible', timeout: 10000 }); await page.keyboard.press('Escape');
    await input.waitFor({ state: 'hidden', timeout: 10000 });
    report.cancel = await savedCell('path = ""');
    await stage('cancel_preserved_empty_literal_and_surrounding_code');
    report.outcome = 'observed';
  } catch (error) {
    report.outcome = 'not_observed'; report.error = { name: error.name, message: error.message };
    if (page) {
      await screenshot('failure').catch(() => {});
      report.visibleUI = await page.locator('body').innerText().catch(() => 'unavailable');
    }
    process.exitCode = 1;
  }
  await save(); console.log(JSON.stringify({ outcome: report.outcome, error: report.error }));
  if (app && !report.closedAt) {
    console.log('Dedicated window retained. Send finish only after user end signal.');
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', async input => {
      if (input.trim() !== 'finish' || report.endSignalReceived) return;
      report.endSignalReceived = true;
      try {
        await app.close(); await closed;
        const ports = [report.nodeInspectorPort, report.chromiumDebugPort].filter(Number.isInteger);
        const listing = execFileSync('netstat.exe', ['-ano', '-p', 'tcp'], { encoding: 'utf8', windowsHide: true });
        report.portCheck = ports.map(port => ({ port, listeners: listing.split(/\r?\n/).filter(line => {
          const c = line.trim().split(/\s+/);
          return c[0] === 'TCP' && Number(c[1]?.split(':').at(-1)) === port && c[3] === 'LISTENING';
        }).length }));
      } catch (error) { report.closeError = error.message; process.exitCode = 1; }
      await save(); process.stdin.pause();
    });
    process.stdin.resume(); await closed;
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
