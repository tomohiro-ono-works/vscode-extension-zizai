"use strict";
// Existing preview only. Change a form filename temporarily, never execute CSV
// code, and verify a single copy click through a separate Windows process.
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const { createRequire } = require("node:module");
const { execFile } = require("node:child_process");
const { promisify } = require("node:util");
const root = path.resolve(__dirname, "../..");
const req = createRequire(path.join(root, "docs/research/notebook-host/playwright-probe/package.json"));
const sessionDir = path.resolve(process.argv[2] || "");
const out = path.resolve(process.argv[3] || "");
for (const target of [sessionDir, out]) {
  const relative = path.relative(path.join(root, "results"), target);
  assert(relative && !relative.startsWith("..") && !path.isAbsolute(relative), "Use results subfolders");
}
async function main() {
  await fs.mkdir(out);
  const session = JSON.parse(await fs.readFile(path.join(sessionDir, "session.local.json"), "utf8"));
  const browser = await req("playwright").chromium.connectOverCDP("http://127.0.0.1:" + session.ports[1], { timeout: 8000 });
  const page = browser.contexts()[0].pages().find(p => p.url().includes("workbench.html"));
  const expect = req("playwright/test").expect;
  let frame;
  for (const candidate of page.frames()) if (await candidate.locator(".zizai-form pre code").count()) { frame = candidate; break; }
  assert(frame, "Display one prepared form with generated code first");
  const generate = frame.getByRole("button", { name: "コード生成", exact: true });
  const copy = frame.getByRole("button", { name: /コードをコピー/ });
  await copy.scrollIntoViewIfNeeded();
  const left = await generate.boundingBox(), right = await copy.boundingBox();
  assert(left && right && left.x < right.x && Math.abs(left.y - right.y) < 2, "Generation must be immediately left of copy");
  const filename = frame.getByRole("textbox", { name: "ファイル名 *", exact: true });
  const original = await filename.inputValue();
  const report = { adjacentButtons: true, generatedCodeNotExecuted: true, copies: [], passed: false };
  const read = async expected => {
    try {
      const { stdout } = await promisify(execFile)("powershell.exe", ["-NoProfile", "-File", path.join(__dirname, "read-generated-code-clipboard.ps1"), expected], { windowsHide: true, timeout: 10000 });
      return JSON.parse(stdout).matchesExpected;
    } catch { return false; }
  };
  async function generateAndCopy(name, value) {
    await filename.fill(value);
    await expect(copy).toBeDisabled();
    await generate.click();
    await expect(copy).toBeEnabled();
    await expect(frame.locator(".zizai-form pre code")).toContainText(value);
    const code = await frame.locator(".zizai-form pre code").innerText();
    assert(code.includes(value), "Wait for the current generated code");
    const expected = path.join(out, name + ".py");
    await fs.writeFile(expected, code);
    assert.equal(await read(expected), false, "Require different clipboard content before the tested click");
    await copy.click(); // Exactly one click, no retry of the action.
    await expect.poll(() => read(expected), { timeout: 10000 }).toBe(true);
    await expect(frame.getByText("コードをコピーしました。", { exact: true })).toBeVisible();
    report.copies.push({ name, clicks: 1, externalClipboardMatches: true });
  }
  try {
    await generateAndCopy("changed-filename", "clipboard-check-" + Date.now() + ".csv");
    await generateAndCopy("original-filename", original);
    report.passed = true;
    await page.screenshot({ path: path.join(out, "copy-controls.png") });
  } finally {
    if (await filename.inputValue() !== original) { await filename.fill(original); await generate.click(); }
    await fs.writeFile(path.join(out, "result.local.json"), JSON.stringify(report, null, 2));
  }
  await page.bringToFront();
  console.log(JSON.stringify(report));
}
main().then(() => process.exit(0)).catch(e => { console.error(e.message); process.exit(1); });
