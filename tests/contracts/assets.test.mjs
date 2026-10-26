import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { cp, mkdir, mkdtemp, readFile, readdir, rm, symlink, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { generateAssets, checkAssets } from '../../scripts/contracts/assets.mjs';
import { createValuesValidator } from '../../scripts/contracts/validation.mjs';

const sourcePath = 'apps/common/contracts/v1/values.schema.json';
const toolsRoot = fileURLToPath(new URL('../../scripts/contracts/', import.meta.url));
const canonical = await readFile(new URL(`../../${sourcePath}`, import.meta.url));
// Preserve fixture bytes on add/checkout without changing any persistent Git config.
const git = (root, ...args) => execFileSync('git', [
  '-c', 'core.autocrlf=false', '-c', 'core.eol=lf', '-C', root, ...args,
], { encoding: 'utf8' }).trim();

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

test('git_fixture_preserves_line_endings_under_inherited_settings', async t => {
  const childFlag = 'ZIZAI_CONTRACT_EOL_CHILD';
  if (!process.env[childFlag]) {
    const temporary = await mkdtemp(path.join(os.tmpdir(), '005-eol-'));
    t.after(() => rm(temporary, { recursive: true, force: true }));
    for (const [autocrlf, eol] of [['true', 'crlf'], ['input', 'lf'], ['false', 'lf']]) {
      const config = path.join(temporary, 'gitconfig');
      const bytes = Buffer.from(`[core]\n\tautocrlf = ${autocrlf}\n\teol = ${eol}\n`);
      await writeFile(config, bytes);
      const env = { ...process.env, GIT_CONFIG_GLOBAL: config, GIT_CONFIG_NOSYSTEM: '1',
        GIT_CONFIG_COUNT: '0', [childFlag]: '1' };
      delete env.NODE_TEST_CONTEXT;
      const result = spawnSync(process.execPath, ['--test',
        '--test-name-pattern=^git_fixture_preserves_line_endings_under_inherited_settings$',
        fileURLToPath(import.meta.url)], { env, encoding: 'utf8' });
      assert.equal(result.status, 0, `${autocrlf}/${eol}: ${result.stdout}\n${result.stderr}`);
      assert.deepEqual(await readFile(config), bytes, 'isolated Git config changed');
    }
    return;
  }

  const lf = canonical.toString('utf8').replace(/\r\n/g, '\n');
  let emitted;
  for (const text of [lf, lf.replace(/\n/g, '\r\n')]) {
    const bytes = Buffer.from(text);
    const options = await fixture(t, bytes);
    const input = path.join(options.repoRoot, sourcePath);
    const blob = execFileSync('git', ['-C', options.repoRoot, 'show', `${options.sourceCommit}:${sourcePath}`]);
    assert.deepEqual(blob, bytes, 'fixture commit changed source bytes');
    await rm(input);
    git(options.repoRoot, 'checkout', '--', sourcePath);
    assert.deepEqual(await readFile(input), bytes, 'fixture checkout changed source bytes');
    const cli = await installCli(options.repoRoot);
    for (const name of ['cli.mjs', 'assets.mjs', 'validation.mjs']) {
      assert.deepEqual(await readFile(path.join(options.repoRoot, 'scripts/contracts', name)),
        await readFile(path.join(toolsRoot, name)), 'CLI copy changed source bytes');
    }
    assert.equal(runCli(cli, os.tmpdir(), ['generate', '--source-commit', options.sourceCommit]).status, 0);
    const manifest = JSON.parse(await readFile(path.join(options.outputRoot, 'manifest.json')));
    assert.deepEqual(manifest.inputs, [{ path: sourcePath, sha256: createHash('sha256').update(bytes).digest('hex') }]);
    const output = path.join(options.outputRoot, 'js/values.schema.json');
    const generated = await readFile(output);
    assert.equal(generated.includes(13), false, 'generated schema must use LF');
    if (emitted) assert.deepEqual(generated, emitted, 'input EOL changed generated schema');
    emitted = generated;
    assert.equal(manifest.outputs[0].sha256, createHash('sha256').update(generated).digest('hex'));
    assert.deepEqual(await checkAssets(options), { ok: true, differences: [] });

    const before = await snapshot(options.outputRoot);
    const changed = Buffer.from(text.includes('\r\n') ? lf : lf.replace(/\n/g, '\r\n'));
    await writeFile(input, changed);
    await assert.rejects(generateAssets(options), /Contract source must match the specified Git commit/);
    await assert.rejects(checkAssets(options), /Contract source must match the specified Git commit/);
    assert.deepEqual(await readFile(input), changed, 'source mismatch was silently repaired');
    assert.deepEqual(await snapshot(options.outputRoot), before);
    await writeFile(input, bytes);
    await writeFile(output, generated.toString('utf8').replace(/\n/g, '\r\n'));
    const altered = await snapshot(options.outputRoot);
    assert.deepEqual(await checkAssets(options), {
      ok: false, differences: [{ path: 'js/values.schema.json', reason: 'changed' }],
    });
    assert.deepEqual(await snapshot(options.outputRoot), altered, 'check repaired output EOL');
  }
});

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

test('canonical_and_generated_schema_conform_to_value_contract', async t => {
  const options = await fixture(t);
  await generateAssets(options);
  const emitted = JSON.parse(await readFile(path.join(options.outputRoot, 'js/values.schema.json')));
  const source = JSON.parse(canonical);
  assert.equal(emitted.$id, 'urn:zizai:contracts:values:v1');
  assert.equal(emitted.$schema, 'https://json-schema.org/draft/2020-12/schema');
  assert.deepEqual(Object.keys(emitted.$defs).sort(), Object.keys(source.$defs).sort());
  const validators = [createValuesValidator(source), createValuesValidator(emitted)];
  const literal = value => ({ kind: 'literal', value });
  const cases = [
    { id: 'strings', name: 'BoundValue', value: literal('  引用"・改行\nC:\\架空 data\\末尾\\  '), ok: true },
    { id: 'distinct-values', name: 'BoundValues', value: {
      boolean: literal(false), zero: literal(0), none: literal(null), empty: literal(''), list: literal([]),
    }, ok: true },
    { id: 'large-integer', name: 'BoundValue', value: { kind: 'integer', decimal: '9007199254740993' }, ok: true },
    { id: 'nested-unsafe-integer', name: 'BoundValue', value: literal({ nested: [9007199254740992] }), ok: false },
    { id: 'noncanonical-integer', name: 'BoundValue', value: { kind: 'integer', decimal: '01' }, ok: false },
    { id: 'incomplete-text', name: 'DraftValue', value: { kind: 'text', text: '-' }, ok: true },
    { id: 'draft-bool-is-structural', name: 'DraftValue', value: { kind: 'json', value: false }, ok: true },
    { id: 'draft-unset', name: 'DraftValues', value: { count: { kind: 'unset' } }, ok: true },
    { id: 'bound-unset', name: 'BoundValues', value: { count: { kind: 'unset' } }, ok: false },
    { id: 'omission', name: 'BoundValues', value: {}, ok: true },
    { id: 'missing-required-wrapper-key', name: 'DraftValue', value: { kind: 'text' }, ok: false },
    { id: 'unknown-wrapper-key', name: 'BoundValue', value: { ...literal('keep'), method: 'unregistered' }, ok: false },
    { id: 'variable-name', name: 'BoundValue', value: { kind: 'variable', name: 'df_sales' }, ok: true },
    { id: 'variable-expression', name: 'BoundValue', value: { kind: 'variable', name: 'df.iloc' }, ok: false },
  ];
  for (const item of cases) {
    const before = structuredClone(item.value);
    for (const validate of validators) {
      assert.equal(validate(item.name, item.value).ok, item.ok, item.id);
      assert.deepEqual(item.value, before, `${item.id}: input changed`);
    }
  }
  assert.deepEqual(await checkAssets(options), { ok: true, differences: [] });
});
