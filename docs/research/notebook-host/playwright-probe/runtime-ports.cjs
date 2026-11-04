'use strict';
// Read only endpoints referenced by this dedicated profile. Never emit kernel keys.
const fs = require('node:fs/promises'), path = require('node:path'), { parseArgs } = require('node:util');
const { execFileSync } = require('node:child_process');
async function files(dir) {
  const result = [];
  for (const e of await fs.readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name); if (e.isDirectory()) result.push(...await files(p)); else result.push(p);
  }
  return result;
}
async function main() {
  const { values } = parseArgs({ options: { out: { type: 'string' }, phase: { type: 'string' } } });
  const repo = path.resolve(__dirname, '../../../..'), out = path.resolve(repo, values.out || '');
  const rel = path.relative(path.join(repo, 'results'), out);
  if (!rel || rel.startsWith('..') || path.isAbsolute(rel)) throw new Error('Dedicated results folder required');
  const inventoryFile = path.join(out, 'ports-before-close.local.json');
  if (values.phase === 'capture') {
    const run = JSON.parse(await fs.readFile(path.join(out, 'result.local.json'), 'utf8'));
    const logs = (await files(path.join(out, 'profile/logs'))).filter(p => /[\\/]\d+-Jupyter\.log$/.test(p));
    if (logs.length !== 1) throw new Error('Exactly one dedicated Jupyter log required');
    const text = await fs.readFile(logs[0], 'utf8');
    const names = [...new Set(text.match(/kernel-[A-Za-z0-9-]+\.json/g) || [])];
    const kernels = [];
    for (const name of names) {
      const metadata = JSON.parse(await fs.readFile(path.join(process.env.APPDATA, 'jupyter/runtime', name), 'utf8'));
      if (metadata.transport !== 'tcp' || !['127.0.0.1', 'localhost', '::1'].includes(metadata.ip)) throw new Error('Unexpected kernel transport/address');
      const ports = ['shell_port', 'iopub_port', 'stdin_port', 'control_port', 'hb_port'].map(k => metadata[k]);
      if (!ports.every(p => Number.isInteger(p) && p > 0 && p < 65536)) throw new Error('Unexpected port');
      kernels.push({ connectionFileBasename: name, ports });
    }
    const inventory = { capturedAt: new Date().toISOString(), diagnosticPorts: [run.nodeInspectorPort, run.chromiumDebugPort], kernels,
      secretKeysIncluded: false, scope: 'dedicated Electron debug endpoints and kernels referenced by its Jupyter log only' };
    await fs.writeFile(inventoryFile, JSON.stringify(inventory, null, 2), { flag: 'wx' });
    console.log(JSON.stringify({ diagnosticPorts: inventory.diagnosticPorts, kernels: kernels.length, kernelPorts: kernels.flatMap(k => k.ports).length }));
  } else if (values.phase === 'check') {
    const inventory = JSON.parse(await fs.readFile(inventoryFile, 'utf8'));
    const ports = [...new Set([...inventory.diagnosticPorts, ...inventory.kernels.flatMap(k => k.ports)])];
    const listing = execFileSync('netstat.exe', ['-ano', '-p', 'tcp'], { encoding: 'utf8', windowsHide: true });
    const checked = ports.map(port => ({ port, listeners: listing.split(/\r?\n/).filter(line => {
      const c = line.trim().split(/\s+/);
      return c[0] === 'TCP' && Number(c[1]?.split(':').at(-1)) === port && c[3] === 'LISTENING';
    }).length }));
    await fs.writeFile(path.join(out, 'ports-after-close.local.json'), JSON.stringify({ at: new Date().toISOString(), checked }, null, 2), { flag: 'wx' });
    console.log(JSON.stringify({ checked: checked.length, listeners: checked.reduce((n, p) => n + p.listeners, 0) }));
    if (checked.some(p => p.listeners)) process.exitCode = 1;
  } else throw new Error('--phase capture or check required');
}
main().catch(e => { console.error(e.message); process.exitCode = 1; });
