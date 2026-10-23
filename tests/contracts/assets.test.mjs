import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { cp, mkdir, mkdtemp, readFile, readdir, rm, symlink, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { generateAssets, checkAssets } from '../../scripts/contracts/assets.mjs';

const sourcePath = 'apps/common/contracts/v1/values.schema.json';
const toolsRoot = fileURLToPath(new URL('../../scripts/contracts/', import.meta.url));
const canonical = await readFile(new URL(`../../${sourcePath}`, import.meta.url));
const git = (root, ...args) => execFileSync('git', ['-C', root, ...args], { encoding: 'utf8' }).trim();

async function commit(root) {
  git(root, 'add', sourcePath);
  git(root, '-c', 'user.name=Contract Fixture', '-c', 'user.email=fixture@example.invalid',
    '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture');
  return git(root, 'rev-parse', 'HEAD');
}

async function fixture(t, bytes = canonical, repoName) {
  const temporary = await mkdtemp(path.join(os.tmpdir(), '005 日本語 space '));
  t.after(() => rm(temporary, { recursive: true, force: true }));
  const root = repoName ? path.join(temporary, repoName) : temporary;
  await mkdir(path.dirname(path.join(root, sourcePath)), { recursive: true });
  await writeFile(path.join(root, sourcePath), bytes);
  git(root, 'init', '-q');
  return { repoRoot: root, outputRoot: path.join(root, 'build/contracts'), sourceCommit: await commit(root) };
}

async function snapshot(root, relative = '') {
  const entries = {};
  for (const entry of await readdir(path.join(root, relative), { withFileTypes: true })) {
    const name = path.posix.join(relative, entry.name);
    if (entry.isDirectory()) Object.assign(entries, await snapshot(root, name));
    else entries[name] = (await readFile(path.join(root, name))).toString('base64');
  }
  return entries;
}

async function installCli(root) {
  const target = path.join(root, 'scripts/contracts');
  await mkdir(target, { recursive: true });
  for (const name of ['cli.mjs', 'assets.mjs', 'validation.mjs']) {
    await cp(path.join(toolsRoot, name), path.join(target, name));
  }
  await symlink(path.join(toolsRoot, 'node_modules'), path.join(target, 'node_modules'), 'dir');
  return path.join(target, 'cli.mjs');
}

const runCli = (cli, cwd, args) => spawnSync(process.execPath, [cli, ...args], { cwd, encoding: 'utf8' });

test('cwd_and_paths_do_not_change_output', async t => {
  const options = await fixture(t);
  const cli = await installCli(options.repoRoot);
  assert.equal(runCli(cli, options.repoRoot, ['generate', '--source-commit', options.sourceCommit]).status, 0);
  const first = await snapshot(options.outputRoot);
  assert.equal(runCli(cli, os.tmpdir(), ['generate', '--source-commit', options.sourceCommit]).status, 0);
  assert.deepEqual(await snapshot(options.outputRoot), first);
  assert.deepEqual(await checkAssets(options), { ok: true, differences: [] });
  const manifest = JSON.parse(await readFile(path.join(options.outputRoot, 'manifest.json')));
  assert.equal(manifest.sourceCommit, options.sourceCommit);
  assert.equal(manifest.manifestVersion, 1);
  assert.equal(manifest.generatorVersion, '0.1.0');
  assert.equal(manifest.schemaDialect, '2020-12');
  assert.deepEqual(manifest.actions, []);
  assert.deepEqual(manifest.inputs, [{ path: sourcePath, sha256: createHash('sha256').update(canonical).digest('hex') }]);
  assert.deepEqual(manifest.outputs, [{
    path: 'js/values.schema.json', consumers: ['host', 'gui'],
    sha256: createHash('sha256').update(await readFile(path.join(options.outputRoot, 'js/values.schema.json'))).digest('hex'),
  }]);
  assert.doesNotMatch(JSON.stringify(manifest), /005 日本語|generatedAt/);
  assert.equal(runCli(cli, os.tmpdir(), ['check', '--source-commit', options.sourceCommit]).status, 0);
});

test('stale_extra_and_missing_output', async t => {
  const options = await fixture(t);
  assert.deepEqual((await checkAssets(options)).differences, [
    { path: 'js/values.schema.json', reason: 'missing' }, { path: 'manifest.json', reason: 'missing' },
  ]);
  await generateAssets(options);
  await rm(path.join(options.outputRoot, 'js/values.schema.json'));
  await writeFile(path.join(options.outputRoot, 'extra.json'), '{}');
  assert.deepEqual((await checkAssets(options)).differences, [
    { path: 'extra.json', reason: 'extra' }, { path: 'js/values.schema.json', reason: 'missing' },
  ]);
  await generateAssets(options);
  const schema = JSON.parse(canonical);
  schema.description = 'changed fixture';
  await writeFile(path.join(options.repoRoot, sourcePath), JSON.stringify(schema));
  options.sourceCommit = await commit(options.repoRoot);
  assert.deepEqual((await checkAssets(options)).differences, [
    { path: 'js/values.schema.json', reason: 'changed' }, { path: 'manifest.json', reason: 'changed' },
  ]);
});

test('check_is_read_only_and_detects_manifest_changes', async t => {
  const options = await fixture(t);
  const cli = await installCli(options.repoRoot);
  await generateAssets(options);
  await writeFile(path.join(options.outputRoot, 'manifest.json'), '{}');
  const before = await snapshot(options.outputRoot);
  assert.deepEqual(await checkAssets(options), {
    ok: false, differences: [{ path: 'manifest.json', reason: 'changed' }],
  });
  const result = runCli(cli, os.tmpdir(), ['check', '--source-commit', options.sourceCommit]);
  assert.equal(result.status, 1);
  assert.deepEqual(await snapshot(options.outputRoot), before);
});

test('failed_generation_does_not_publish_manifest', async t => {
  const options = await fixture(t);
  await generateAssets(options);
  const before = await snapshot(options.outputRoot);
  for (const sourceCommit of ['', 'HEAD', '0'.repeat(40), 'a'.repeat(39)]) {
    await assert.rejects(generateAssets({ ...options, sourceCommit }));
  }
  for (const outputRoot of [options.repoRoot, path.join(options.repoRoot, 'outside')]) {
    await assert.rejects(generateAssets({ ...options, outputRoot }));
  }
  await writeFile(path.join(options.repoRoot, sourcePath), 'uncommitted private marker');
  await assert.rejects(generateAssets(options), error => !error.message.includes('private marker'));
  assert.deepEqual(await snapshot(options.outputRoot), before);
  await writeFile(path.join(options.repoRoot, sourcePath), '{invalid schema private marker');
  options.sourceCommit = await commit(options.repoRoot);
  await assert.rejects(generateAssets(options), error => !error.message.includes('private marker'));
  assert.deepEqual(await snapshot(options.outputRoot), before);
  const fresh = await fixture(t, '{}');
  await assert.rejects(generateAssets(fresh));
  await assert.rejects(readFile(path.join(fresh.outputRoot, 'manifest.json')), { code: 'ENOENT' });
});

test('symlink_paths_and_entries_are_rejected_without_touching_targets', async t => {
  const options = await fixture(t);
  const outside = await mkdtemp(path.join(os.tmpdir(), '005 outside '));
  t.after(() => rm(outside, { recursive: true, force: true }));
  await writeFile(path.join(outside, 'sentinel'), 'keep');
  await symlink(outside, path.join(options.repoRoot, 'build'), 'dir');
  await assert.rejects(generateAssets(options));
  await assert.rejects(checkAssets(options));
  assert.equal(await readFile(path.join(outside, 'sentinel'), 'utf8'), 'keep');
  assert.deepEqual(await readdir(outside), ['sentinel']);
  await rm(path.join(options.repoRoot, 'build'));
  await generateAssets(options);
  await symlink(path.join(outside, 'sentinel'), path.join(options.outputRoot, 'linked'));
  await assert.rejects(generateAssets(options));
  await assert.rejects(checkAssets(options));
  assert.equal(await readFile(path.join(outside, 'sentinel'), 'utf8'), 'keep');
});

test('cli_rejects_misuse_with_exit_one', async t => {
  const options = await fixture(t);
  const cli = await installCli(options.repoRoot);
  for (const args of [[], ['generate'], ['check', '--source-commit'],
    ['unknown', '--source-commit', options.sourceCommit], ['generate', '--source-commit', 'HEAD'],
    ['generate', '--source-commit', options.sourceCommit, '--unknown']]) {
    assert.equal(runCli(cli, os.tmpdir(), args).status, 1);
  }
});

test('trailing_whitespace_in_repository_name_is_preserved', async t => {
  const options = await fixture(t, canonical, '日本語 trailing space ');
  await generateAssets(options);
  assert.deepEqual(await checkAssets(options), { ok: true, differences: [] });
});

test('unused_invalid_schema_definitions_are_never_published', async t => {
  for (const unused of [{ unrecognizedKeyword: true }, { $ref: 'https://invalid.example/never-fetch' }]) {
    const schema = JSON.parse(canonical);
    schema.$defs.Unused = unused;
    const options = await fixture(t, JSON.stringify(schema));
    await assert.rejects(generateAssets(options));
    await assert.rejects(checkAssets(options));
    await assert.rejects(readFile(path.join(options.outputRoot, 'manifest.json')), { code: 'ENOENT' });
  }
});
