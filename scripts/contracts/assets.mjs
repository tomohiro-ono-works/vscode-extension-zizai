import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { lstat, mkdir, mkdtemp, readFile, readdir, rename, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { promisify } from 'node:util';
import { createValuesValidator } from './validation.mjs';

const run = promisify(execFile);
const inputPath = 'apps/common/contracts/v1/values.schema.json';
const outputPath = 'js/values.schema.json';

const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const ordered = value => Array.isArray(value) ? value.map(ordered)
  : value && typeof value === 'object'
    ? Object.fromEntries(Object.keys(value).sort().map(key => [key, ordered(value[key])])) : value;
const jsonBytes = value => Buffer.from(`${JSON.stringify(ordered(value), null, 2)}\n`, 'utf8');

async function statIfPresent(target) {
  try { return await lstat(target); } catch (error) {
    if (error.code === 'ENOENT') return undefined;
    throw error;
  }
}

/** Inspect every existing component without resolving a symlink to its target. */
async function assertNoLinks(target) {
  const absolute = path.resolve(target);
  let current = path.parse(absolute).root;
  for (const part of absolute.slice(current.length).split(path.sep).filter(Boolean)) {
    current = path.join(current, part);
    if ((await statIfPresent(current))?.isSymbolicLink()) throw new Error('Symlink path is forbidden');
  }
}

async function checkedOptions(options) {
  if (!options || typeof options.repoRoot !== 'string' || typeof options.outputRoot !== 'string'
    || typeof options.sourceCommit !== 'string' || !/^[a-fA-F0-9]{40}$/.test(options.sourceCommit)) {
    throw new Error('Invalid contract generation options');
  }
  const repoRoot = path.resolve(options.repoRoot);
  const outputRoot = path.resolve(options.outputRoot);
  if (outputRoot !== path.join(repoRoot, 'build', 'contracts')) throw new Error('Invalid contract output root');
  await assertNoLinks(repoRoot);
  await assertNoLinks(outputRoot);
  await assertNoLinks(path.join(repoRoot, inputPath));
  if (!(await statIfPresent(repoRoot))?.isDirectory()) throw new Error('Invalid repository root');
  const info = await statIfPresent(outputRoot);
  if (info && !info.isDirectory()) throw new Error('Invalid contract output root');
  return { repoRoot, outputRoot, sourceCommit: options.sourceCommit.toLowerCase() };
}

async function expectedAssets(options) {
  const { repoRoot, sourceCommit } = options;
  let source;
  try {
    const git = async args => (await run('git', ['-C', repoRoot, ...args], { encoding: 'buffer', maxBuffer: 16 * 1024 * 1024 })).stdout;
    const topLine = (await git(['rev-parse', '--show-toplevel'])).toString('utf8');
    const top = topLine.endsWith('\n') ? topLine.slice(0, -1) : topLine;
    if (path.resolve(top) !== repoRoot) throw new Error();
    if ((await git(['cat-file', '-t', sourceCommit])).toString('utf8').trim() !== 'commit') throw new Error();
    const committed = await git(['show', `${sourceCommit}:${inputPath}`]);
    if (!(await statIfPresent(path.join(repoRoot, inputPath)))?.isFile()) throw new Error();
    source = await readFile(path.join(repoRoot, inputPath));
    if (!source.equals(committed)) throw new Error();
  } catch {
    throw new Error('Contract source must match the specified Git commit');
  }
  let schema;
  try {
    schema = JSON.parse(source.toString('utf8'));
    if (schema.$schema !== 'https://json-schema.org/draft/2020-12/schema'
      || schema.$id !== 'urn:zizai:contracts:values:v1') throw new Error();
    createValuesValidator(schema);
  } catch {
    throw new Error('Invalid canonical values schema');
  }
  const output = jsonBytes(schema);
  const manifest = {
    manifestVersion: 1,
    generatorVersion: '0.1.0',
    schemaDialect: '2020-12',
    sourceCommit,
    inputs: [{ path: inputPath, sha256: hash(source) }],
    outputs: [{ path: outputPath, sha256: hash(output), consumers: ['host', 'gui'] }],
    actions: [],
  };
  return { manifest, files: new Map([[outputPath, output], ['manifest.json', jsonBytes(manifest)]]) };
}

async function existingFiles(root, relative = '') {
  const files = new Map();
  const info = await statIfPresent(path.join(root, relative));
  if (!info) return files;
  if (info.isSymbolicLink() || !info.isDirectory()) throw new Error('Invalid contract output entry');
  const entries = await readdir(path.join(root, relative), { withFileTypes: true });
  for (const entry of entries) {
    const name = path.posix.join(relative, entry.name);
    const target = path.join(root, name);
    const stat = await lstat(target);
    if (stat.isSymbolicLink()) throw new Error('Symlink output entry is forbidden');
    if (stat.isDirectory()) {
      const children = await existingFiles(root, name);
      if (!children.size) files.set(`${name}/`, Buffer.alloc(0));
      for (const [key, bytes] of children) files.set(key, bytes);
    } else if (stat.isFile()) files.set(name, await readFile(target));
    else throw new Error('Invalid contract output entry');
  }
  return files;
}

/** Generate only after source verification. Publish manifest last; consumers must run check. */
export async function generateAssets(rawOptions) {
  const options = await checkedOptions(rawOptions);
  const { manifest, files } = await expectedAssets(options);
  await existingFiles(options.outputRoot);
  await mkdir(options.outputRoot, { recursive: true });
  // Staging and all deletions stay inside the designated output root.
  const stage = await mkdtemp(path.join(options.outputRoot, '.stage-'));
  try {
    for (const [name, bytes] of files) {
      await mkdir(path.dirname(path.join(stage, name)), { recursive: true });
      await writeFile(path.join(stage, name), bytes);
    }
    await assertNoLinks(options.outputRoot);
    await existingFiles(options.outputRoot);
    // Invalidate the previous manifest before replacing its assets.
    await rm(path.join(options.outputRoot, 'manifest.json'), { recursive: true, force: true });
    for (const name of await readdir(options.outputRoot)) {
      if (name !== path.basename(stage)) await rm(path.join(options.outputRoot, name), { recursive: true, force: true });
    }
    await mkdir(path.join(options.outputRoot, 'js'));
    await rename(path.join(stage, outputPath), path.join(options.outputRoot, outputPath));
    await rename(path.join(stage, 'manifest.json'), path.join(options.outputRoot, 'manifest.json'));
    return manifest;
  } finally {
    await rm(stage, { recursive: true, force: true });
  }
}

/** Byte-for-byte comparison, including the manifest and unlisted entries. Never writes. */
export async function checkAssets(rawOptions) {
  const options = await checkedOptions(rawOptions);
  const { files: expected } = await expectedAssets(options);
  const actual = await existingFiles(options.outputRoot);
  // An empty expected directory indicates missing files, not an extra directory.
  const expectedDirectories = new Set([...expected.keys()].flatMap(name => {
    const parts = name.split('/');
    return parts.slice(0, -1).map((_, index) => `${parts.slice(0, index + 1).join('/')}/`);
  }));
  const differences = [];
  for (const name of [...new Set([...expected.keys(), ...actual.keys()])].sort()) {
    if (expectedDirectories.has(name)) continue;
    const reason = !expected.has(name) ? 'extra' : !actual.has(name) ? 'missing'
      : !expected.get(name).equals(actual.get(name)) ? 'changed' : undefined;
    if (reason) differences.push({ path: name, reason });
  }
  return { ok: differences.length === 0, differences };
}
