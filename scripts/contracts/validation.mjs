import Ajv2020 from 'ajv/dist/2020.js';

const names = ['DraftValue', 'BoundValue', 'DraftValues', 'BoundValues'];

// Visit schema locations only: const/default/example objects are data, not schemas.
const schemaMaps = ['$defs', 'definitions', 'properties', 'patternProperties', 'dependentSchemas'];
const schemaArrays = ['allOf', 'anyOf', 'oneOf', 'prefixItems'];
const schemaSingles = ['items', 'additionalProperties', 'unevaluatedProperties', 'propertyNames',
  'contains', 'not', 'if', 'then', 'else', 'unevaluatedItems', 'contentSchema'];
const pointerKey = key => encodeURIComponent(key.replace(/~/g, '~0').replace(/\//g, '~1'));

function* definitionPointers(schema, pointer = '') {
  if (!schema || typeof schema !== 'object') return;
  for (const keyword of schemaMaps) {
    for (const [key, child] of Object.entries(schema[keyword] ?? {})) {
      const childPointer = `${pointer}/${keyword}/${pointerKey(key)}`;
      if (keyword === '$defs' || keyword === 'definitions') yield childPointer;
      yield* definitionPointers(child, childPointer);
    }
  }
  for (const keyword of schemaArrays) {
    for (const [index, child] of (schema[keyword] ?? []).entries()) {
      yield* definitionPointers(child, `${pointer}/${keyword}/${index}`);
    }
  }
  for (const keyword of schemaSingles) {
    yield* definitionPointers(schema[keyword], `${pointer}/${keyword}`);
  }
}

/** Structural validation only. No defaults, coercion, input mutation or network refs. */
export function createValuesValidator(schema) {
  const ajv = new Ajv2020({
    strict: true,
    strictNumbers: true,
    allErrors: true,
    coerceTypes: false,
    useDefaults: false,
    removeAdditional: false,
  });
  let validators;
  try {
    ajv.addSchema(schema);
    // Ajv otherwise compiles only reachable definitions. Reject invalid unused exports too.
    ajv.getSchema(schema.$id);
    for (const pointer of definitionPointers(schema)) ajv.getSchema(`${schema.$id}#${pointer}`);
    validators = new Map(names.map(name => {
      const validator = ajv.getSchema(`${schema.$id}#/$defs/${name}`);
      if (!validator) throw new Error();
      return [name, validator];
    }));
  } catch {
    throw new Error('Invalid values schema configuration');
  }
  return (name, value) => {
    const validator = validators.get(name);
    if (!validator) throw new Error('Unknown values definition');
    if (validator(value)) return { ok: true };
    return {
      ok: false,
      errors: validator.errors.map(error => ({ path: error.instancePath, keyword: error.keyword })),
    };
  };
}
