// Agent-side evidence summary. Raw logs and saved notebooks remain local.
import { readFile, readdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const parent = path.join(root, 'logs/task-002-01');
const names = (await readdir(parent, { withFileTypes: true })).filter(d => d.isDirectory() && /^\d{4}-/.test(d.name)).map(d => d.name).sort();
const name = process.argv[2] || names.at(-1);
if (!names.includes(name)) throw new Error('Select an existing session directory name');
const dir = path.join(parent, name);
const events = (await readFile(path.join(dir, 'events.jsonl'), 'utf8')).trim().split('\n').filter(Boolean).map(JSON.parse);
const counts = {};
for (const event of events) counts[event.kind] = (counts[event.kind] || 0) + 1;
const summary = {
  session: name,
  environment: events.find(e => e.kind === 'environment'),
  counts,
  markers: events.filter(e => e.kind === 'snapshot').map(e => ({ seq: e.seq, at: e.at, label: e.label, notebooks: e.notebooks.map(n => ({ object: n.object, version: n.version, dirty: n.dirty, closed: n.closed, cells: n.cells.map(c => ({ object: c.object, index: c.index, textObject: c.textObject, source: c.source, metadata: c.metadata, executionSummary: c.executionSummary })) })) })),
  applyReturns: events.filter(e => e.kind === 'apply.return'),
  saveFiles: events.filter(e => e.kind === 'notebook.save').map(e => ({ seq: e.seq, file: e.file, sha256: e.sha256 })),
  localGuards: events.filter(e => e.kind === 'local-delay.guard'),
  bursts: events.filter(e => e.kind === 'burst.summary'),
  errors: events.filter(e => e.kind.endsWith('.error'))
};
await writeFile(path.join(dir, 'summary.local.json'), JSON.stringify(summary, null, 2) + '\n');
console.log(JSON.stringify({ session: name, counts, errors: summary.errors, markers: summary.markers.map(m => ({ seq: m.seq, label: m.label })), summary: path.join(dir, 'summary.local.json') }, null, 2));
