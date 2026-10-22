// TASK-001-02 PROTOTYPE packaging only. No application implementation.
import { readFile, writeFile, mkdir, rm, cp, mkdtemp } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import os from 'node:os';
const root = path.dirname(fileURLToPath(import.meta.url));
const commit = 'f08bfc73350d04e9238b43fa4dbcfdb81fa5150e';
const files = {
  'src/node-form.js': 'e1c24cadbd01b2cad228f58a6504a7d82335c514',
  'src/node-form.css': '13bf86a1f5145178f97a868fd835a78d0419c0de',
  'LICENSE': 'f94f9d5131a475bada426d8e8a4bf001c4c1207e'
};
const target = path.join(root, 'dist', 'webview');
const cache = path.join(root, 'dist', 'upstream', commit);
const temp = await mkdtemp(path.join(os.tmpdir(), 'zizai-nodeform-'));
try {
  for (const [name, expected] of Object.entries(files)) {
    let data;
    if (process.argv[2]) data = await readFile(path.join(process.argv[2], name));
    else {
      try { data = await readFile(path.join(cache, name)); } catch (error) { if (error.code !== 'ENOENT') throw error; }
      if (!data) {
        const response = await fetch(`https://raw.githubusercontent.com/tomohiro-ono-works/zizai-form/${commit}/${name}`, { signal: AbortSignal.timeout(20000) });
        if (!response.ok) throw Error(`${name}: download HTTP ${response.status}`);
        data = Buffer.from(await response.arrayBuffer());
      }
    }
    const blob = createHash('sha1').update(`blob ${data.length}\0`).update(data).digest('hex');
    if (blob !== expected) throw Error(`${name}: pinned upstream blob mismatch`);
    await mkdir(path.dirname(path.join(cache, name)), { recursive: true });
    await writeFile(path.join(cache, name), data);
    await mkdir(path.dirname(path.join(temp, name)), { recursive: true });
    await writeFile(path.join(temp, name), data);
  }
  const patch = path.join(root, 'patches', '0001-combo-listener.patch');
  const patchBytes = await readFile(patch);
  // A Windows checkout may use CRLF. Normalize only the patch input; pinned
  // upstream bytes and their Git blob verification remain unchanged.
  const appliedPatch = Buffer.from(patchBytes.toString('utf8').replace(/\r\n/g, '\n'));
  // Keep an ancestor repository's attributes/settings out of this temporary copy.
  const patchOptions = { cwd: temp, input: appliedPatch,
    env: { ...process.env, GIT_CEILING_DIRECTORIES: path.dirname(temp) } };
  const gitApply = ['-c', 'core.autocrlf=false', '-c', 'core.eol=lf', 'apply'];
  execFileSync('git', [...gitApply, '--check', '-'], patchOptions);
  execFileSync('git', [...gitApply, '-'], patchOptions);
  await rm(target, { recursive: true, force: true });
  await mkdir(path.join(target, 'resources'), { recursive: true });
  for (const name of ['node-form.js', 'node-form.css']) await cp(path.join(temp, 'src', name), path.join(target, 'resources', name));
  await cp(path.join(temp, 'LICENSE'), path.join(target, 'resources', 'UPSTREAM-LICENSE'));
  await cp(path.join(root, '../../docs/decisions/nodeform-reuse-permission.md'), path.join(target, 'resources', 'ZIZAI-PERMISSION.md'));
  for (const name of ['webview.cjs', 'webview-client.mjs', 'vscode-theme-probe.css']) await cp(path.join(root, name), path.join(target, name));
  await writeFile(path.join(target, 'provenance.json'), JSON.stringify({
    upstreamCommit: commit,
    patchSha256: createHash('sha256').update(patchBytes).digest('hex'),
    appliedPatchSha256: createHash('sha256').update(appliedPatch).digest('hex'),
    themeSha256: createHash('sha256').update(await readFile(path.join(root, 'vscode-theme-probe.css'))).digest('hex')
  }, null, 2) + '\n');
  await writeFile(path.join(target, 'package.json'), JSON.stringify({
    name: 'task-001-02-nodeform-probe', publisher: 'zizai-lab', version: '0.0.1', private: true,
    displayName: 'Zizai TASK-001-02 NodeForm PROTOTYPE',
    engines: { vscode: '^1.105.0' }, main: './webview.cjs', extensionKind: ['ui'],
    contributes: { commands: [{ command: 'zizaiNodeFormProbe.open', title: 'Zizai Probe: Open NodeForm Reuse Test' }] }
  }, null, 2) + '\n');
  console.log(`Prepared TASK-001-02 Webview PROTOTYPE: ${target}`);
} finally { await rm(temp, { recursive: true, force: true }); }
