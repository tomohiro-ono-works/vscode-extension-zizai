const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { once, EventEmitter } = require('node:events');
const { waitForManualFinish } = require('../e2e/manual-session.cjs');

test('closed stdin does not end manual wait; file signal finishes and releases the process', { timeout: 10000 }, async t => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'zizai-manual-'));
  const signal = path.join(dir, 'finish.request');
  const helper = path.resolve(__dirname, '../e2e/manual-session.cjs');
  const child = spawn(process.execPath, ['-e', `
    const {waitForManualFinish}=require(${JSON.stringify(helper)});
    const {EventEmitter}=require('node:events');
    waitForManualFinish(new EventEmitter(),process.argv[1]).then(reason=>console.log(reason));
    console.log('ready');
  `, signal], { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
  t.after(async () => { if (child.exitCode === null) child.kill(); await fs.rm(dir, { recursive: true, force: true }); });
  let output = '', errors = '';
  child.stdout.on('data', data => { output += data; });
  child.stderr.on('data', data => { errors += data; });
  const exited = once(child, 'exit');
  while (!output.includes('ready') && child.exitCode === null) await new Promise(r => setTimeout(r, 20));
  assert.match(output, /ready/, errors);
  await fs.writeFile(signal, 'not-approved');
  await new Promise(r => setTimeout(r, 250));
  assert.equal(child.exitCode, null, 'Neither closed stdin nor an unrelated file value may end the wait');
  await fs.writeFile(signal, 'finish\n');
  const [code] = await exited;
  assert.equal(code, 0, errors);
  assert.match(output, /finish_file/);
  assert.equal(await fs.readFile(signal, 'utf8'), 'finish\n', 'Keep the finish evidence');
});

test('user closing the dedicated app also releases the file watcher', { timeout: 3000 }, async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'zizai-manual-'));
  const app = new EventEmitter();
  try {
    const waiting = waitForManualFinish(app, path.join(dir, 'finish.request'));
    app.emit('close');
    assert.equal(await waiting, 'window_closed');
    assert.equal(app.listenerCount('close'), 0);
  } finally { await fs.rm(dir, { recursive: true, force: true }); }
});
