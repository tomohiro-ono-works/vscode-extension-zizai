const test = require("node:test");
const assert = require("node:assert/strict");
const { createHarness } = require("./vscode-harness.cjs");
const definitions = {
  magics: { "ziz.connector.action.selector": {
    fields: { "connector.name": { label: "C", choices: ["csv", "excel"] } }
  } }
};
const initial = '%%ziz.connector.action.selector\nconnector.name = "" # keep\nother = 1';

function harness() { return createHarness(definitions, initial); }

test("hint command selects and reselects the actual target literal", async () => {
  const h = harness();
  let hints = h.decorations();
  assert.equal(hints.length, 1);
  assert.equal(hints[0].renderOptions.before.contentText, "[C]");
  assert.equal(hints[0].range.start.character, 17, "Anchor to the target, not the beginning of the line");
  assert.equal(hints[0].range.end.character, 19, "Hover covers the target literal");
  assert.equal(await h.pick(h.choiceRequest("csv")), true);
  assert.equal(h.text(), initial.replace('= ""', '= "csv"'));
  hints = h.decorations();
  assert.equal(await h.pick(h.choiceRequest("excel")), true);
  assert.equal(h.text(), initial.replace('= ""', '= "excel"'));
});

test("cancel and stale hint leave the source untouched", async () => {
  const h = harness();
  const request = h.choiceRequest("csv");
  assert.equal(await h.pick(undefined), false);
  assert.equal(h.text(), initial);
  h.document.version += 1;
  assert.equal(await h.pick(request), false);
  assert.equal(h.text(), initial);
});

test("selection dismisses the cached menu and reselection uses the current document", async () => {
  const h = harness();
  const cachedExcel = h.choiceRequest("excel");
  assert.equal(await h.pick(h.choiceRequest("csv")), true);
  assert.deepEqual(h.executedCommands, ["editor.action.hideHover"]);
  assert.equal(await h.pick(cachedExcel), false, "Stale menus must still be rejected");
  assert.equal(await h.pick(h.choiceRequest("excel")), true);
  assert.equal(h.text(), initial.replace('= ""', '= "excel"'));
});

test("ordinary Python documents are not edited by a command request", async () => {
  const h = harness();
  const request = h.choiceRequest("csv");
  h.document.uri.scheme = "file";
  assert.equal(await h.pick(request), false);
  assert.equal(h.text(), initial);
});

test("hover offers a directly clickable choice without opening QuickPick", async () => {
  const h = harness();
  h.api.window.showQuickPick = () => { throw Error("Hover must not open QuickPick"); };
  const tooltip = h.tooltip();
  assert.equal(typeof tooltip, "object");
  const link = /\[csv\]\((command:[^)]+)\)/.exec(tooltip.value);
  assert.ok(link, "CSV is a command link in the hover");
  const [id, encoded] = link[1].slice("command:".length).split("?");
  const [request] = JSON.parse(decodeURIComponent(encoded));
  assert.equal(await h.invoke(id, request), true);
  assert.equal(h.text(), initial.replace('= ""', '= "csv"'));
});

test("hover permits only the selection command and rejects a value outside the definition", async () => {
  const h = harness();
  const tooltip = h.tooltip();
  assert.deepEqual(tooltip.isTrusted, { enabledCommands: ["zizai.setValue"] });
  assert.equal(tooltip.supportHtml, false);
  const link = /\[csv\]\((command:[^)]+)\)/.exec(tooltip.value);
  const [id, encoded] = link[1].slice("command:".length).split("?");
  const [request] = JSON.parse(decodeURIComponent(encoded));
  request.value = "outside-the-definition";
  assert.equal(await h.invoke(id, request), false);
  assert.equal(h.text(), initial);
});

test("hover preserves the exact encoded Notebook URI across Markdown command links", async () => {
  const h = harness();
  const uri = "vscode-notebook-cell:/c%3A/%E8%B3%87%E6%96%99/book.ipynb#cell%3D%3D";
  h.document.uri.toString = () => uri;
  const tooltip = h.tooltip();
  const link = /\[csv\]\((command:[^)]+)\)/.exec(tooltip.value);
  const [id, encoded] = link[1].slice("command:".length).split("?");
  const [request] = JSON.parse(decodeURIComponent(encoded));
  assert.equal(typeof request.documentKey, "string");
  assert.equal(request.uri, undefined, "Do not expose a URI-looking value to Markdown normalization");
  assert.equal(Buffer.from(request.documentKey, "base64").toString("utf8"), uri);
  assert.equal(await h.invoke(id, request), true);
  assert.equal(h.text(), initial.replace('= ""', '= "csv"'));
});
