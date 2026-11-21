"use strict";
// Reuse an accepted Playwright VS Code session. Never close it or change
// an existing Notebook; only create and operate the named synthetic sample.
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const { createRequire } = require("node:module");
const root = path.resolve(__dirname, "../..");
const req = createRequire(path.join(root, "docs/research/notebook-host/playwright-probe/package.json"));
const sessionDir = path.resolve(process.argv[2] || "");
const out = path.resolve(process.argv[3] || "");
const mode = process.argv[4];
for (const target of [sessionDir, out]) {
  const relative = path.relative(path.join(root, "results"), target);
  assert(relative && !relative.startsWith("..") && !path.isAbsolute(relative), "Use a results subfolder");
}
assert(["prepare", "run"].includes(mode), "Specify prepare or run");
const filename = "csv-standard-import.ipynb";
const notebook = path.join(sessionDir, "workspace", filename);
const data = path.join(sessionDir, "workspace/csv-standard-import-data");
const expectedCsv = "名前,個数\nりんご,1\nみかん,2\n";

async function main() {
  const session = JSON.parse(await fs.readFile(path.join(sessionDir, "session.local.json"), "utf8"));
  const browser = await req("playwright").chromium.connectOverCDP("http://127.0.0.1:" + session.ports[1], { timeout: 8000 });
  const page = browser.contexts()[0].pages().find(item => item.url().includes("workbench.html"));
  const expect = req("playwright/test").expect;
  const progress = { mode, notebook, existingSession: true, steps: [], passed: false };
  async function save() { await fs.writeFile(path.join(out, mode + ".local.json"), JSON.stringify(progress, null, 2)); }
  async function step(name, action) {
    progress.currentStep = name; await save();
    await action(); progress.steps.push({ name, passed: true }); await save();
  }
  if (mode === "prepare") {
    await fs.mkdir(path.dirname(out), { recursive: true });
    await fs.mkdir(out);
    await step("prepare-synthetic-sample", async () => {
      await fs.mkdir(data);
      await fs.writeFile(path.join(data, "input.csv"), expectedCsv, { flag: "wx" });
      const sample = JSON.parse(await fs.readFile(path.join(root, "examples/csv-form.ipynb"), "utf8"));
      sample.cells[0].source = ["# CSV：通常importのサンプル\n",
        "フォームとCSV処理は実装本体です。サンプルなのは、りんご・みかんの架空CSVデータです。\n",
        "Python環境への導入・共通フォルダーの登録は済んでいます。Notebookでwheelやsys.pathを操作する必要はありません。\n",
        "表示済みフォームを変更して生成し、下のPythonセルへコピーして実行できます。"];
      sample.metadata.kernelspec = { display_name: "ZizAI Form Preview (isolated)", language: "python", name: "zizai-form-preview" };
      await fs.writeFile(notebook, JSON.stringify(sample, null, 2), { flag: "wx" });
    });
    await step("open-in-accepted-window", async () => {
      await page.bringToFront();
      const sidebar = page.getByRole("button", { name: "Toggle Primary Side Bar (Ctrl+B)", exact: true });
      if (await sidebar.getAttribute("aria-pressed") !== "true") await sidebar.click();
      await page.getByRole("treeitem", { name: filename, exact: false }).dblclick({ timeout: 20000 });
      await expect.poll(() => page.title(), { timeout: 20000 }).toContain(filename);
      await page.locator('[role="code"][data-uri*="' + filename + '"]').first().waitFor({ timeout: 30000 });
    });
    progress.passed = true; await save();
    console.log(JSON.stringify({ mode, prepared: true, notebook }));
    return;
  }
  await fs.copyFile(path.join(out, "run.local.json"), path.join(out, "run-before-" + Date.now() + ".local.json"))
    .catch(error => { if (error.code !== "ENOENT") throw error; });
  let widget, lastUri;
  async function runEditor(editor) {
    lastUri = await editor.getAttribute("data-uri");
    await editor.locator('xpath=ancestor::*[@role="listitem"][1]')
      .getByRole("button", { name: "Execute Cell (Ctrl+Alt+Enter)", exact: true }).last().click({ timeout: 10000 });
  }
  async function nextCode(marker, code) {
    const anchor = page.locator('[role="code"][data-uri=' + JSON.stringify(lastUri) + ']');
    await anchor.click({ timeout: 10000 });
    await page.keyboard.press("Escape"); await page.keyboard.press("ArrowDown"); await page.keyboard.press("Enter");
    const focused = await page.evaluate(() => {
      const editor = document.activeElement?.closest('[role="code"]');
      return editor && { uri: editor.getAttribute("data-uri"), text: editor.textContent };
    });
    assert(focused?.uri.includes(filename) && focused.text.includes(marker), "Unexpected Notebook target; no code inserted");
    await page.keyboard.press("Control+a"); await page.keyboard.insertText(code);
    await runEditor(page.locator('[role="code"][data-uri=' + JSON.stringify(focused.uri) + ']'));
  }
  async function chooseAction(index, label) {
    await widget.getByRole("combobox", { name: "コネクタ", exact: true }).nth(index).selectOption({ label: "CSV" });
    const action = widget.getByRole("combobox", { name: "アクション", exact: true }).nth(index);
    await expect(action.locator("option")).toHaveText(["選択してください", "読み込み", "書き出し"]);
    await action.selectOption({ label });
  }
  try {
    await step("use-existing-registered-python", async () => {
      await page.bringToFront();
      await page.getByRole("tab", { name: filename, exact: true }).click();
      const select = page.getByRole("button", { name: "Select Kernel", exact: true });
      const environmentName = path.basename(path.dirname(path.dirname(session.python)));
      if (await select.count()) {
        await select.click();
        await expect.poll(() => page.getByRole("option").count(), { timeout: 5000 }).toBeGreaterThan(0);
        progress.kernelChoices = await page.getByRole("option").allTextContents(); await save();
        const target = page.getByRole("option", { name: new RegExp("ZizAI Form Preview \\(isolated\\)|" + environmentName) });
        if (await target.count()) await target.first().click();
        else {
          const another = page.getByRole("option", { name: "Select Another Kernel...", exact: true });
          if (await another.count()) await another.click();
          const source = page.getByRole("option", { name: "Jupyter Kernel...", exact: true });
          await source.click({ timeout: 10000 });
          await page.getByRole("option", { name: /ZizAI Form Preview \(isolated\)/ }).click({ timeout: 10000 });
        }
      }
      await expect(page.getByRole("button", { name: new RegExp(environmentName + ".*python\\.exe") })).toBeVisible();
    });
    await step("show-installed-form", async () => {
      const first = page.locator('[role="code"][data-uri*="' + filename + '"]').first();
      await first.click(); await runEditor(first);
      const until = Date.now() + 40000;
      while (Date.now() < until) {
        for (const frame of page.frames()) {
          if (await frame.getByRole("heading", { name: "CSV：通常importのサンプル", exact: true }).count()
            && await frame.getByRole("combobox", { name: "コネクタ", exact: true }).count()) { widget = frame; break; }
        }
        if (widget) break;
        await new Promise(resolve => setTimeout(resolve, 200));
      }
      assert(widget, "Installed form did not render");
    });
    await step("generate-and-run-read", async () => {
      await chooseAction(0, "読み込み");
      const generate = widget.getByRole("button", { name: "コード生成", exact: true }).first();
      await expect(generate).toBeDisabled();
      await widget.getByRole("textbox", { name: "入力ファイル *", exact: true }).fill(path.join(data, "input.csv"));
      await expect(generate).toBeEnabled(); await generate.click();
      await expect(widget.locator("pre").first()).toContainText("csv_connector.read_csv", { timeout: 15000 });
      const code = await widget.locator("pre").first().innerText();
      assert(code.startsWith("import csv_connector\n") && !code.includes("load_connector") && !code.includes("sys.path"));
      await fs.writeFile(path.join(out, "generated-read.py"), code);
      await nextCode("読み込みの生成コード", code);
      await expect(widget.getByRole("cell", { name: "りんご", exact: true })).toBeVisible({ timeout: 20000 });
    });
    await step("generate-and-run-write", async () => {
      await nextCode("%zizai_form", "%zizai_form");
      await expect(widget.getByRole("combobox", { name: "コネクタ", exact: true })).toHaveCount(2, { timeout: 15000 });
      await chooseAction(1, "書き出し");
      await expect(widget.getByRole("textbox", { name: "入力変数 *", exact: true })).toHaveValue("df");
      const generate = widget.getByRole("button", { name: "コード生成", exact: true }).last();
      await expect(generate).toBeDisabled();
      await widget.getByRole("textbox", { name: "保存先 *", exact: true }).fill(data);
      await expect(generate).toBeEnabled(); await generate.click();
      await expect(widget.locator("pre").last()).toContainText("csv_connector.write_csv", { timeout: 15000 });
      const code = await widget.locator("pre").last().innerText();
      assert(code.startsWith("import csv_connector\n") && !code.includes("load_connector"));
      await fs.writeFile(path.join(out, "generated-write.py"), code);
      await nextCode("書き出しの生成コード", code);
      await expect(widget.locator("body")).toContainText("CSV保存完了", { timeout: 20000 });
      const output = await fs.readFile(path.join(data, "output.csv"));
      assert(output.subarray(0, 3).equals(Buffer.from([239, 187, 191])));
      assert.equal(output.toString("utf8").replace(/^\uFEFF/, "").replaceAll("\r\n", "\n"), expectedCsv);
      assert.equal(await fs.readFile(path.join(data, "input.csv"), "utf8"), expectedCsv);
      await page.keyboard.press("Control+s");
      await expect.poll(async () => (await fs.readFile(notebook, "utf8")).includes("CSV保存完了")).toBe(true);
    });
    progress.passed = true; progress.rows = 2; progress.inputPreserved = true; await save();
    await fs.writeFile(path.join(out, "snapshot.local.txt"), await widget.locator("body").ariaSnapshot());
    await page.screenshot({ path: path.join(out, "sample-ready.png") });
    await page.bringToFront();
    console.log(JSON.stringify({ passed: true, rows: 2, standardImport: true, notebook }));
  } catch (error) {
    progress.error = error.message;
    progress.failureSnapshot = await page.locator("body").ariaSnapshot();
    await save();
    console.error(JSON.stringify({ passed: false, step: progress.currentStep, error: error.message }));
    process.exitCode = 1;
  }
}
main().then(() => process.exit(process.exitCode || 0)).catch(error => { console.error(error.stack); process.exit(1); });
