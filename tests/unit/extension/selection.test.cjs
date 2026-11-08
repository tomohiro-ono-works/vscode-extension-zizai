const test = require("node:test");
const assert = require("node:assert/strict");
const { findSelections, replaceChoice } = require("../../../apps/extension/selection.cjs");

const definitions = {
  magics: {
    "ziz.connector.action.selector": {
      fields: {
        "connector.name": { label: "C", choices: ["csv", "excel", '日本語 "quoted"\\path'] }
      }
    }
  }
};
const source = '%%ziz.connector.action.selector\nconnector.name = "" # 選択\nother = "keep"\n';

test("finds only the configured value in the matching magic", () => {
  const fields = findSelections(source, definitions);
  assert.equal(fields.length, 1);
  assert.equal(fields[0].field, "connector.name");
  assert.equal(fields[0].line, 1);
  assert.equal(fields[0].character, 17);
  assert.equal(source.slice(fields[0].start, fields[0].end), '""');
  assert.equal(fields[0].current, "");
});

test("changes and reselects the value without changing surrounding code", () => {
  const first = findSelections(source, definitions)[0];
  const csv = replaceChoice(source, first, "csv");
  assert.equal(csv, source.replace('= ""', '= "csv"'));
  const second = findSelections(csv, definitions)[0];
  assert.equal(second.current, "csv");
  assert.equal(replaceChoice(csv, second, "excel"), source.replace('= ""', '= "excel"'));
});

test("quotes an allowed string instead of inserting executable source", () => {
  const value = definitions.magics["ziz.connector.action.selector"].fields["connector.name"].choices[2];
  const field = findSelections(source, definitions)[0];
  const changed = replaceChoice(source, field, value);
  assert.equal(changed, source.slice(0, field.start) + JSON.stringify(value) + source.slice(field.end));
  assert.equal(findSelections(changed, definitions)[0].current, value);
});

test("leaves cancelled, stale and unlisted selections untouched", () => {
  const field = findSelections(source, definitions)[0];
  assert.equal(replaceChoice(source, field, undefined), source);
  assert.equal(replaceChoice(source, field, "not-allowed"), source);
  const edited = source.replace('= ""', '= "user edited"');
  assert.equal(replaceChoice(edited, field, "csv"), edited);
});

test("ignores other magics, comments, ordinary code and unsupported literals", () => {
  assert.deepEqual(findSelections(source.replace("%%ziz.connector.action.selector", "%%other"), definitions), []);
  assert.deepEqual(findSelections('connector.name = ""', definitions), []);
  assert.deepEqual(findSelections(source.replace("connector.name =", "# connector.name ="), definitions), []);
  assert.deepEqual(findSelections(source.replace('= ""', "= get_value()"), definitions), []);
  assert.deepEqual(findSelections(source.replace('= ""', "= 'csv'"), definitions), []);
});

test("uses correct offsets with Windows line endings", () => {
  const windows = source.replaceAll("\n", "\r\n");
  const field = findSelections(windows, definitions)[0];
  assert.equal(windows.slice(field.start, field.end), '""');
  assert.equal(replaceChoice(windows, field, "csv"), windows.replace('= ""', '= "csv"'));
});
