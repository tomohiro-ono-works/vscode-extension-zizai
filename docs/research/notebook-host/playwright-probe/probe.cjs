// Research only: observe startup and command-palette input in an empty window.
const fs = require('node:fs/promises');
const path = require('node:path');
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
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error('--out must be a new directory inside results/');
  }
  await fs.access(values.vscode);
  await fs.mkdir(path.dirname(out), { recursive: true });
  await fs.mkdir(out); // Do not reuse or overwrite a previous run.
  const profile = path.join(out, 'profile');
  await fs.mkdir(path.join(profile, 'User'), { recursive: true });
  await fs.writeFile(path.join(profile, 'User/settings.json'), JSON.stringify({
    'window.title': 'VS Code Playwright 調査 ${activeEditorShort}',
    'window.restoreWindows': 'none',
    'workbench.startupEditor': 'none'
  }, null, 2), { flag: 'wx' });
  const report = {
    purpose: 'research only; empty-window startup and palette open/close',
    playwright: require('playwright/package.json').version,
    node: process.version,
    started: new Date().toISOString(),
    outcome: 'pending', stages: [],
    extensionsDisabled: true, notebookExecuted: false,
    debugHostRequested: '127.0.0.1',
    profileCopied: false, sharedDataIsolated: true
  };
  const save = () => fs.writeFile(path.join(out, 'result.local.json'), JSON.stringify(report, null, 2));
  const stage = async (name) => {
    report.stages.push({ name, at: new Date().toISOString() });
    await save();
    console.log(name);
  };
  await save();
  let app;
  let closed;
  try {
    const env = { ...process.env };
    delete env.ELECTRON_RUN_AS_NODE;
    delete env.VSCODE_DEV;
    delete env.VSCODE_PORTABLE;
    app = await electron.launch({
      executablePath: path.resolve(values.vscode),
      args: ['--new-window', '--disable-extensions', '--skip-welcome',
        '--skip-release-notes', '--disable-telemetry', '--disable-updates',
        '--remote-debugging-address=127.0.0.1',
        `--shared-data-dir=${path.join(out, 'shared-data')}`,
        '--locale=en', `--user-data-dir=${profile}`],
      env, timeout: 45000
    });
    closed = new Promise(resolve => app.once('close', () => {
      report.closedAt = new Date().toISOString();
      resolve();
    }));
    report.pid = app.process().pid;
    await stage('electron_connected');
    const page = await app.firstWindow({ timeout: 30000 });
    await page.locator('.monaco-workbench').waitFor({ state: 'visible', timeout: 30000 });
    report.title = await page.title();
    report.product = await app.evaluate(({ app }) => ({
      name: app.getName(), version: app.getVersion()
    }));
    await stage('workbench_visible');
    await page.screenshot({ path: path.join(out, 'workbench.png') });
    await page.keyboard.press('Control+Shift+P');
    await page.locator('.quick-input-widget').waitFor({ state: 'visible', timeout: 10000 });
    await stage('command_palette_open');
    await page.screenshot({ path: path.join(out, 'command-palette.png') });
    await page.keyboard.press('Escape');
    await page.locator('.quick-input-widget').waitFor({ state: 'hidden', timeout: 10000 });
    await stage('command_palette_closed');
    report.outcome = 'observed';
  } catch (error) {
    report.outcome = 'not_observed';
    report.error = { name: error.name, message: error.message };
    process.exitCode = 1;
  }
  await save();
  console.log(JSON.stringify({ outcome: report.outcome, stages: report.stages.map(x => x.name) }));
  if (app && !report.closedAt) {
    console.log('Window retained. Awaiting user end signal; CLI input "finish" closes this probe only.');
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', async input => {
      if (input.trim() === 'finish') {
        report.endSignalReceived = true;
        await app.close();
      }
    });
    process.stdin.resume();
    await closed;
    process.stdin.pause();
    await save();
  }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
