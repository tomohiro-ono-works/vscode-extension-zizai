const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { createHarness } = require("./vscode-harness.cjs");
const { findSelections, replacePath } = require("../../../apps/extension/selection.cjs");
const source = '%%ziz.connector.action.setting\nfile_path = "" # keep\nother = 1';
const definitions = kind => ({ magics: { "ziz.connector.action.setting": {
  fields: { file_path: { label: "P", kind } }
} } });
function setup(kind = "file", initial = source) {
  const h = createHarness(definitions(kind), initial);
  const options = [];
  h.api.Uri = { file: fsPath => ({ scheme: "file", fsPath }) };
  h.api.window.showOpenDialog = async value => { options.push(value); return h.result; };
  const tooltip = h.tooltip();
  const match = /command:zizai\.pickPath\?([^)]*)/.exec(tooltip.value);
  assert.ok(match, "Path fields offer the extension's path command");
  const [request] = JSON.parse(decodeURIComponent(match[1]));
  return { h, options, request };
}
const chosen = path.join(path.parse(process.cwd()).root, "資料 O'Reilly-${HOME}", "売上.csv");

test("recognizes a path field and quotes only its literal", () => {
  const fields = findSelections(source, definitions("file"));
  assert.equal(fields.length, 1);
  assert.equal(fields[0].kind, "file");
  assert.equal(replacePath(source, fields[0], chosen), source.replace('= ""', "= " + JSON.stringify(chosen)));
});

test("file selection and reselection preserve surrounding code", async () => {
  const { h, options, request } = setup();
  h.result = [{ scheme: "file", fsPath: chosen }];
  assert.equal(await h.invoke("zizai.pickPath", request), true);
  assert.equal(h.text(), source.replace('= ""', "= " + JSON.stringify(chosen)));
  assert.equal(options[0].canSelectFiles, true);
  assert.equal(options[0].canSelectFolders, false);
  const tooltip = h.tooltip();
  const [next] = JSON.parse(decodeURIComponent(/command:zizai\.pickPath\?([^)]*)/.exec(tooltip.value)[1]));
  h.result = [{ scheme: "file", fsPath: path.dirname(chosen) + path.sep + "別ファイル.csv" }];
  assert.equal(await h.invoke("zizai.pickPath", next), true);
  assert.equal(options[1].defaultUri.fsPath, chosen);
  assert.match(h.text(), /別ファイル\.csv/);
  assert.ok(h.text().endsWith(" # keep\nother = 1"));
});

test("folder selection uses the folder-only dialog", async () => {
  const { h, options, request } = setup("folder");
  h.result = [{ scheme: "file", fsPath: path.dirname(chosen) }];
  assert.equal(await h.invoke("zizai.pickPath", request), true);
  assert.equal(options[0].canSelectFiles, false);
  assert.equal(options[0].canSelectFolders, true);
  assert.equal(options[0].canSelectMany, false);
});

test("cancellation leaves an existing path unchanged", async () => {
  const initial = source.replace('= ""', "= " + JSON.stringify(chosen));
  const { h, request } = setup("file", initial);
  h.result = undefined;
  assert.equal(await h.invoke("zizai.pickPath", request), false);
  assert.equal(h.text(), initial);
});

test("a cell changed during the dialog is not overwritten", async () => {
  const { h, request } = setup();
  h.api.window.showOpenDialog = async () => { h.document.version += 1; return [{ scheme: "file", fsPath: chosen }]; };
  assert.equal(await h.invoke("zizai.pickPath", request), false);
  assert.equal(h.text(), source);
});
