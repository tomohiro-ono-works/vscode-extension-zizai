// Real Git + packaging regression tests; no VS Code or Windows GUI is started.
// Populate the pinned cache with prepare-webview.mjs before running this file.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cp, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { execFileSync, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import os from 'node:os';
import path from 'node:path';

const sourceRoot = path.dirname(fileURLToPath(import.meta.url));
const commit = 'f08bfc73350d04e9238b43fa4dbcfdb81fa5150e';
const digest = data => createHash('sha256').update(data).digest('hex');

async function fixture(t, { crlf = false, parentRepository = false } = {}) {
  const area = await mkdtemp(path.join(os.tmpdir(), 'zizai-prepare-regression-'));
  t.after(() => rm(area, { recursive: true, force: true }));
  const project = path.join(area, 'checkout');
  const root = path.join(project, 'tests', 'nodeform-reuse');
  const temp = path.join(area, 'AppData', 'Local', 'Temp');
  await mkdir(root, { recursive: true });
  await mkdir(temp, { recursive: true });
  for (const name of ['prepare-webview.mjs', 'webview.cjs', 'webview-client.mjs', 'vscode-theme-probe.css', 'patches']) {
    await cp(path.join(sourceRoot, name), path.join(root, name), { recursive: true });
  }
  await mkdir(path.join(project, 'docs', 'decisions'), { recursive: true });
  await cp(path.join(sourceRoot, '../../docs/decisions/nodeform-reuse-permission.md'),
    path.join(project, 'docs', 'decisions', 'nodeform-reuse-permission.md'));
  const cache = path.join(root, 'dist', 'upstream', commit);
  for (const name of ['src/node-form.js', 'src/node-form.css', 'LICENSE']) {
    const original = path.join(sourceRoot, 'dist', 'upstream', commit, name);
    let data;
    try { data = await readFile(original); }
    catch (error) { throw new Error('Pinned cache required: run node tests/nodeform-reuse/prepare-webview.mjs first', { cause: error }); }
    await mkdir(path.dirname(path.join(cache, name)), { recursive: true });
    await writeFile(path.join(cache, name), data);
  }
  const patch = path.join(root, 'patches', '0001-combo-listener.patch');
  const canonicalPatch = (await readFile(patch, 'utf8')).replace(/\r\n/g, '\n');
  await writeFile(patch, crlf ? canonicalPatch.replace(/\n/g, '\r\n') : canonicalPatch);
  const guard = path.join(project, 'deny-fetch.mjs');
  await writeFile(guard, "globalThis.fetch = () => { throw Error('Unexpected network request in cached regression test'); };\n");
  if (parentRepository) {
    execFileSync('git', ['init', '--quiet', area]);
    execFileSync('git', ['-C', area, 'config', 'core.autocrlf', 'true']);
  }
  const env = { ...process.env, TMPDIR: temp, TMP: temp, TEMP: temp };
  if (parentRepository) {
    env.GIT_CONFIG_GLOBAL = path.join(area, 'global-gitconfig');
    await writeFile(env.GIT_CONFIG_GLOBAL, '[core]\n\tautocrlf = true\n');
  }
  const run = () => spawnSync(process.execPath, ['--import', guard, path.join(root, 'prepare-webview.mjs')], {
    cwd: project, env, encoding: 'utf8'
  });
  return { root, cache, patch, temp, run, target: path.join(root, 'dist', 'webview') };
}

function succeeds(result) {
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr || result.stdout);
}

async function snapshot(root, prefix = '') {
  const result = {};
  for (const entry of await readdir(path.join(root, prefix), { withFileTypes: true })) {
    const relative = path.join(prefix, entry.name);
    if (entry.isDirectory()) Object.assign(result, await snapshot(root, relative));
    else result[relative.split(path.sep).join('/')] = digest(await readFile(path.join(root, relative)));
  }
  return result;
}

test('LF patch prepares the pinned cached sources without network access', async t => {
  const f = await fixture(t);
  succeeds(f.run());
  const generated = await snapshot(f.target);
  assert.equal(Object.keys(generated).length, 9);
  const js = await readFile(path.join(f.target, 'resources', 'node-form.js'), 'utf8');
  assert.match(js, /function openMenu\(forceAll\) \{\n      close\(\);/);
  assert.deepEqual(await readdir(f.temp), []);
});

test('CRLF patch prepares the same pinned LF upstream successfully', async t => {
  const f = await fixture(t, { crlf: true });
  succeeds(f.run());
  const js = await readFile(path.join(f.target, 'resources', 'node-form.js'), 'utf8');
  assert.match(js, /function openMenu\(forceAll\) \{\n      close\(\);/);
  assert.deepEqual(await readdir(f.temp), []);
});

test('CRLF patch also works beneath an ancestor Git repository with core.autocrlf=true', async t => {
  const f = await fixture(t, { crlf: true, parentRepository: true });
  succeeds(f.run());
  const js = await readFile(path.join(f.target, 'resources', 'node-form.js'), 'utf8');
  assert.match(js, /function openMenu\(forceAll\) \{\n      close\(\);/);
  assert.deepEqual(await readdir(f.temp), []);
});

test('LF and CRLF patches yield identical payloads and preserve raw/applied patch provenance', async t => {
  const lf = await fixture(t);
  const crlf = await fixture(t, { crlf: true });
  succeeds(lf.run());
  succeeds(crlf.run());
  const a = await snapshot(lf.target);
  const b = await snapshot(crlf.target);
  delete a['provenance.json'];
  delete b['provenance.json'];
  assert.deepEqual(a, b);
  const provenance = [];
  for (const f of [lf, crlf]) {
    const raw = await readFile(f.patch);
    const p = JSON.parse(await readFile(path.join(f.target, 'provenance.json'), 'utf8'));
    assert.equal(p.patchSha256, digest(raw));
    provenance.push(p);
  }
  assert.notEqual(provenance[0].patchSha256, provenance[1].patchSha256);
  assert.equal(provenance[0].appliedPatchSha256, digest(await readFile(lf.patch)));
  assert.equal(provenance[1].appliedPatchSha256, provenance[0].appliedPatchSha256);
});

for (const kind of ['modified', 'CRLF-converted']) {
  test(`rejects ${kind} upstream bytes and preserves the existing build`, async t => {
    const f = await fixture(t);
    succeeds(f.run());
    const before = await snapshot(f.target);
    const file = path.join(f.cache, 'src', 'node-form.js');
    const raw = await readFile(file);
    const changed = kind === 'modified' ? Buffer.concat([raw, Buffer.from('\n// changed\n')])
      : Buffer.from(raw.toString('utf8').replace(/\n/g, '\r\n'));
    await writeFile(file, changed);
    const result = f.run();
    assert.ifError(result.error);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /pinned upstream blob mismatch/);
    assert.deepEqual(await snapshot(f.target), before);
    assert.deepEqual(await readFile(file), changed);
    assert.deepEqual(await readdir(f.temp), []);
  });
}

test('invalid patch context still fails before replacing the existing build', async t => {
  const f = await fixture(t);
  succeeds(f.run());
  const before = await snapshot(f.target);
  const patch = await readFile(f.patch, 'utf8');
  await writeFile(f.patch, patch.replace('function openMenu(forceAll)', 'function contextMustNotMatch(forceAll)'));
  const result = f.run();
  assert.ifError(result.error);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /patch does not apply/);
  assert.deepEqual(await snapshot(f.target), before);
  assert.deepEqual(await readdir(f.temp), []);
});
