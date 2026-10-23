import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { createValuesValidator } from '../../scripts/contracts/validation.mjs';

const schema = JSON.parse(await readFile(new URL('../../apps/common/contracts/v1/values.schema.json', import.meta.url)));
const validate = createValuesValidator(schema);

test('draft_is_not_semantic_validation', () => {
  for (const value of [{ kind: 'text', text: '-' }, { kind: 'json', value: false }]) {
    assert.deepEqual(validate('DraftValue', value), { ok: true });
  }
  for (const value of [{ kind: 'text' }, { kind: 'unset', value: null }]) {
    assert.equal(validate('DraftValue', value).ok, false);
  }
});

test('literal_types_and_precision', () => {
  for (const value of [false, 0, null, '', [], { arbitrary: [true, 1.5, 'text'] }, Number.MAX_SAFE_INTEGER, Number.MIN_SAFE_INTEGER]) {
    assert.deepEqual(validate('BoundValue', { kind: 'literal', value }), { ok: true });
  }
  for (const value of [9007199254740992, -9007199254740992, Infinity, -Infinity, NaN, { nested: [Infinity] }]) {
    assert.equal(validate('BoundValue', { kind: 'literal', value }).ok, false);
  }
  for (const decimal of ['9007199254740993', '-9007199254740993', '0', '-1']) {
    assert.deepEqual(validate('BoundValue', { kind: 'integer', decimal }), { ok: true });
  }
  for (const decimal of ['01', '-0', '+1', '', '1.0', '1\n']) {
    assert.equal(validate('BoundValue', { kind: 'integer', decimal }).ok, false);
  }
});

test('unset_is_draft_only', () => {
  assert.deepEqual(validate('DraftValues', {}), { ok: true });
  assert.deepEqual(validate('DraftValues', { count: { kind: 'unset' } }), { ok: true });
  assert.equal(validate('BoundValues', { count: { kind: 'unset' } }).ok, false);
  assert.deepEqual(validate('BoundValues', {}), { ok: true });
});

test('unknown_wrapper_key_and_no_input_mutation', () => {
  const input = { kind: 'literal', value: { secret: 'private marker' }, method: 'private method' };
  const before = structuredClone(input);
  const result = validate('BoundValue', input);
  assert.equal(result.ok, false);
  assert.deepEqual(input, before);
  for (const error of result.errors) {
    assert.deepEqual(Object.keys(error).sort(), ['keyword', 'path']);
    assert.equal(typeof error.path, 'string');
    assert.equal(typeof error.keyword, 'string');
  }
  assert.doesNotMatch(JSON.stringify(result), /private marker|private method/);
  assert.equal(validate('BoundValue', { kind: 'integer', decimal: 1 }).ok, false);
});

test('variable_names_have_only_structural_validation', () => {
  for (const name of ['result', '_value2', 'class']) {
    assert.deepEqual(validate('BoundValue', { kind: 'variable', name }), { ok: true });
  }
  for (const name of ['x.y', 'x[0]', '1x', '日本語', 'x\n', '']) {
    assert.equal(validate('BoundValue', { kind: 'variable', name }).ok, false);
  }
});

test('bad_schema_and_unknown_reference_are_setup_errors', () => {
  assert.throws(() => createValuesValidator({ ...schema, type: 'invalid-type' }));
  const broken = structuredClone(schema);
  broken.$defs.DraftValue = { $ref: 'https://invalid.example/never-fetch' };
  assert.throws(() => createValuesValidator(broken));
  assert.throws(() => validate('Unknown', {}));
});

test('unused_definitions_must_also_be_valid', () => {
  for (const unused of [{ unrecognizedKeyword: true }, { $ref: 'https://invalid.example/never-fetch' }]) {
    const broken = structuredClone(schema);
    broken.$defs.Unused = unused;
    assert.throws(() => createValuesValidator(broken));
  }
  const nested = structuredClone(schema);
  nested.$defs.Unused = { $defs: { Nested: { unrecognizedKeyword: true } } };
  assert.throws(() => createValuesValidator(nested));
});
