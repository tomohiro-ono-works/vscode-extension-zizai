"use strict";
const fs = require("node:fs/promises");
const path = require("node:path");
const assert = require("node:assert/strict");

async function runPathFlow({ page, editor, workspace, notebookFile, originalSource, report, out, stage }) {
  const folder1 = path.join(workspace, "資料 O'Reilly-${HOME}");
  const folder2 = path.join(workspace, "別のフォルダー");
  await fs.mkdir(folder1); await fs.mkdir(folder2);
  const file1 = path.join(folder1, "売上1.csv");
  const file2 = path.join(folder1, "別ファイル.csv");
  await fs.writeFile(file1, "value\n1\n", { flag: "wx" });
  await fs.writeFile(file2, "value\n2\n", { flag: "wx" });
  const expected = { file_path: "", folder_path: "" };
  const normalize = text => text.replace(/\u00a0/g, " ").replace(/[A-Z]:/g, drive => drive.toLowerCase());
  const sourceText = async () => (await editor.locator(".view-lines .view-line").allTextContents()).join("");
  async function verifyVisible() {
    let ok = false;
    for (let attempt = 0; attempt < 40; attempt += 1) {
      const text = normalize(await sourceText());
      ok = Object.entries(expected).every(([key, value]) => text.includes(normalize(key + " = " + JSON.stringify(value))));
      if (ok) break;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert(ok, "Both path values must match without saving or changing the other field");
  }
  async function select(kind, selected) {
    const marker = editor.locator("zizaiMarker=[P]").nth(kind === "file" ? 0 : 1);
    await marker.hover();
    const name = kind === "file" ? "ファイルを選択" : "フォルダーを選択";
    const hover = page.locator(".monaco-hover").filter({ has: page.getByRole("link", { name, exact: true }) });
    const link = hover.getByRole("link", { name, exact: true });
    await link.waitFor({ state: "visible", timeout: 10000 });
    const start = await marker.boundingBox();
    const target = await link.boundingBox();
    assert(start && target);
    const from = { x: start.x + start.width / 2, y: start.y + start.height / 2 };
    const to = { x: target.x + target.width / 2, y: target.y + target.height / 2 };
    const steps = Math.ceil(Math.hypot(to.x - from.x, to.y - from.y));
    const movement = { kind, from, to, steps, marker: start, menu: await hover.boundingBox() };
    (report.pathPointerMovements ||= []).push(movement);
    for (let step = 1; step <= steps; step += 1) {
      await page.mouse.move(from.x + (to.x - from.x) * step / steps, from.y + (to.y - from.y) * step / steps);
      await new Promise(resolve => setTimeout(resolve, 8));
      if (!await link.isVisible()) {
        movement.disappearedAtStep = step;
        throw Error("Path menu must remain visible while moving into it");
      }
    }
    await page.mouse.down(); await page.mouse.up();
    const input = page.locator(".quick-input-widget input").first();
    await input.waitFor({ state: "visible", timeout: 10000 });
    if (selected === undefined) {
      await page.keyboard.press("Escape");
    } else {
      await input.fill(selected.replaceAll("\\", "/") + (kind === "folder" ? "/" : ""));
      await page.keyboard.press("Enter");
      const accepted = await input.waitFor({ state: "hidden", timeout: 1500 }).then(() => true, () => false);
      if (!accepted) {
        await page.getByRole("button", { name: kind === "file" ? "このファイルを使用" : "このフォルダーを使用", exact: true }).click({ timeout: 5000 });
      }
      expected[kind === "file" ? "file_path" : "folder_path"] = selected;
    }
    await input.waitFor({ state: "hidden", timeout: 10000 });
    await verifyVisible();
  }
  await select("file", file1); await stage("file_selected_without_save");
  await select("file", file2); await stage("file_reselected_without_save");
  await select("file", undefined); await stage("file_cancel_kept_previous_value");
  await select("folder", folder1); await stage("folder_selected_without_save");
  await select("folder", folder2); await stage("folder_reselected_without_save");
  await select("folder", undefined); await stage("folder_cancel_kept_previous_value");
  await editor.locator(".view-lines").click();
  await page.keyboard.press("Control+s");
  let saved;
  const expectedSource = originalSource
    .replace('file_path = ""', "file_path = " + JSON.stringify(file2))
    .replace('folder_path = ""', "folder_path = " + JSON.stringify(folder2));
  for (let attempt = 0; attempt < 50; attempt += 1) {
    saved = JSON.parse(await fs.readFile(notebookFile, "utf8"));
    if (normalize(saved.cells[0].source.join("")) === normalize(expectedSource)) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.equal(normalize(saved.cells[0].source.join("")), normalize(expectedSource));
  assert.equal(saved.cells.length, 2);
  assert.deepEqual(saved.cells[1], { cell_type: "code", execution_count: null, id: "untouched-cell", metadata: { keep: "untouched" }, outputs: [], source: ['untouched = "keep"'] });
  assert.equal(saved.cells[0].metadata.trialPreserve, true);
  assert.equal(saved.metadata.trialPreserve, true);
  assert.equal(saved.cells[0].execution_count, null);
  assert.deepEqual(saved.cells[0].outputs, []);
  report.paths = { fileSelection: true, fileReselection: true, fileCancelPreserved: true,
    folderSelection: true, folderReselection: true, folderCancelPreserved: true,
    sourceAndMetadataPreserved: true, absolutePaths: true, saveOnlyAfterAllSixOperations: true,
    dialog: "VS Code standard simple file dialog; OS native dialog not exercised" };
  await page.screenshot({ path: path.join(out, "paths-final.png") });
  await stage("all_path_operations_saved_and_preserved");
  return { currentSource: expectedSource, previousSource: originalSource
    .replace('file_path = ""', "file_path = " + JSON.stringify(file2))
    .replace('folder_path = ""', "folder_path = " + JSON.stringify(folder1)) };
}

module.exports = { runPathFlow };
