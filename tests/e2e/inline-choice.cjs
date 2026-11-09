"use strict";
// Fixed Playwright flow: no CUA, command palette, Python execution, or user profile.
const fs = require("node:fs/promises");
const path = require("node:path");
const { createRequire } = require("node:module");
const { execFileSync } = require("node:child_process");
const assert = require("node:assert/strict");
const { parseArgs } = require("node:util");
const root = path.resolve(__dirname, "../..");
const researchRequire = createRequire(path.join(root, "docs/research/notebook-host/playwright-probe/package.json"));
const playwright = researchRequire("playwright");
const { _electron: electron } = playwright;

async function main() {
  await playwright.selectors.register("zizaiMarker", () => ({
    query(root, text) {
      return [...root.querySelectorAll("span")].find(element => getComputedStyle(element, "::before").content === JSON.stringify(text)) || null;
    },
    queryAll(root, text) {
      return [...root.querySelectorAll("span")].filter(element => getComputedStyle(element, "::before").content === JSON.stringify(text));
    }
  }));
  const { values } = parseArgs({ options: { vscode: { type: "string" }, out: { type: "string" }, vsix: { type: "string" }, undo: { type: "boolean" }, dependent: { type: "boolean" }, manual: { type: "boolean" }, hover: { type: "boolean", default: true }, human: { type: "boolean" }, paths: { type: "boolean" } } });
  assert(values.vscode && values.out, "--vscode and --out are required");
  const out = path.resolve(root, values.out);
  const relative = path.relative(path.join(root, "results"), out);
  assert(relative && !relative.startsWith("..") && !path.isAbsolute(relative), "Use a new results subfolder");
  await fs.mkdir(out);
  const profile = path.join(out, "profile");
  const workspace = path.join(out, "workspace");
  const extensions = path.join(out, "extensions");
  await fs.mkdir(workspace); await fs.mkdir(extensions);
  // Freeze the new hover trial so neither dedicated window follows live source edits.
  const extension = values.hover ? path.join(out, "extension") : path.join(root, "apps/extension");
  if (values.hover && !values.vsix) {
    await fs.mkdir(extension);
    for (const file of ["extension.cjs", "selection.cjs", "definitions.cjs", "definitions.yaml", "package.json"]) {
      await fs.copyFile(path.join(root, "apps/extension", file), path.join(extension, file));
    }
  }
  if (values.hover && !values.vsix) await fs.cp(path.join(root, "apps/extension/node_modules/yaml"), path.join(extension, "node_modules/yaml"), { recursive: true });
  await fs.mkdir(path.join(profile, "User"), { recursive: true });
  await fs.writeFile(path.join(profile, "User/settings.json"), JSON.stringify({
    "window.title": values.manual
      ? (path.basename(values.vscode).includes("Insiders") ? "ZizAI Insiders Hands-on ${activeEditorShort}" : "ZizAI Hover Hands-on ${activeEditorShort}")
      : "ZizAI Hover Trial ${activeEditorShort}",
    "window.restoreWindows": "none", "workbench.startupEditor": "none",
    "files.autoSave": "off", "extensions.autoUpdate": false, "extensions.autoCheckUpdates": false,
    "update.mode": "none", "editor.inlayHints.enabled": "on", "editor.multiCursorModifier": "alt",
    "files.simpleDialog.enable": values.paths ? true : undefined,
    "window.dialogStyle": values.paths ? "custom" : undefined,
    "workbench.editorAssociations": { "*.ipynb": "jupyter-notebook" }
  }), { flag: "wx" });
  const originalSource = values.paths
    ? '%%ziz.connector.action.setting\nfile_path = "" # file\nfolder_path = "" # folder\nother = "keep"'
    : values.dependent ? '%%ziz.connector.action.selector\nconnector.name = "" # parent\nconnector.action.name = "" # child\nother = "keep"'
    : '%%ziz.connector.action.selector\nconnector.name = "" # preserve\nother = "keep"';
  let externalYaml;
  if (values.dependent) {
    await fs.mkdir(path.join(workspace, '.vscode'));
    externalYaml = 'version: 1\nmagics:\n  ziz.connector.action.selector:\n    fields:\n      connector.name: {label: C, choices: [csv, excel]}\n      connector.action.name:\n        label: A\n        dependsOn: connector.name\n        choicesByValue: {csv: [shared, csv_only], excel: [shared, excel_only]}\n';
    await fs.writeFile(path.join(workspace, '.vscode/zizai-definitions.yaml'), externalYaml, { flag: 'wx' });
  }
  const fixture = { cells: [{ cell_type: "code", execution_count: null, id: "inline-choice-cell",
    metadata: { trialPreserve: true }, outputs: [], source: originalSource.split(/(?<=\n)/) },
    { cell_type: "code", execution_count: null, id: "untouched-cell", metadata: { keep: "untouched" }, outputs: [], source: ['untouched = "keep"'] }],
    metadata: { language_info: { name: "python" }, trialPreserve: true }, nbformat: 4, nbformat_minor: 5 };
  const notebookFile = path.join(workspace, "inline-choice.ipynb");
  await fs.writeFile(notebookFile, JSON.stringify(fixture, null, 2), { flag: "wx" });
  const report = { startedAt: new Date().toISOString(), outcome: "in_progress", stages: [],
    playwright: researchRequire("playwright/package.json").version, node: process.version,
    commandPaletteUsed: false, kernelExecuted: false, userProfileModified: false, ports: [],
    mode: values.hover ? "hover" : "ctrl-click", hoverGeometry: [],
    continuousPointerMovement: !!(values.human || values.paths || values.dependent), savesBetweenChoices: !(values.human || values.paths || values.dependent),
    deployment: values.vsix ? "installed-vsix" : "extensionDevelopmentPath" };
  const save = () => fs.writeFile(path.join(out, "result.local.json"), JSON.stringify(report, null, 2));
  async function stage(name) { report.stages.push(name); await save(); console.log(name); }
  let app, page;
  try {
    const env = { ...process.env };
    delete env.ELECTRON_RUN_AS_NODE; delete env.VSCODE_DEV; delete env.VSCODE_PORTABLE;
    if (values.vsix) {
      const appRoot = path.dirname(path.resolve(values.vscode));
      const candidates = [appRoot, ...(await fs.readdir(appRoot, { withFileTypes: true })).filter(e => e.isDirectory()).map(e => path.join(appRoot, e.name))];
      let cli;
      for (const candidate of candidates) {
        const file = path.join(candidate, "resources/app/out/cli.js");
        if (await fs.access(file).then(() => true, () => false)) { cli = file; break; }
      }
      assert(cli, "VS Code bundled CLI must be present");
      const cliArgs = [cli, "--user-data-dir=" + profile, "--extensions-dir=" + extensions];
      const cliOptions = { env: { ...env, ELECTRON_RUN_AS_NODE: "1" }, encoding: "utf8", windowsHide: true, timeout: 60000 };
      report.installOutput = execFileSync(path.resolve(values.vscode), [...cliArgs, "--install-extension", path.resolve(values.vsix)], cliOptions);
      report.installedExtensions = execFileSync(path.resolve(values.vscode), [...cliArgs, "--list-extensions", "--show-versions"], cliOptions).trim();
      const version = JSON.parse(await fs.readFile(path.join(root, 'apps/extension/package.json'), 'utf8')).version;
      assert(report.installedExtensions.includes("zizai-lab.zizai-notebook-input@" + version));
      await stage("vsix_installed_in_isolated_profile");
    }
    app = await electron.launch({ executablePath: path.resolve(values.vscode), env, timeout: 45000,
      args: ["--new-window", "--skip-welcome", "--skip-release-notes", "--disable-telemetry", "--disable-updates",
        "--locale=en", "--remote-debugging-address=127.0.0.1", "--user-data-dir=" + profile,
        "--shared-data-dir=" + path.join(out, "shared-data"), "--extensions-dir=" + extensions,
        ...(values.vsix ? [] : ["--extensionDevelopmentPath=" + extension]), workspace] });
    report.pid = app.process().pid;
    report.ports.push(await app.evaluate(() => process.debugPort));
    report.ports.push(Number((await fs.readFile(path.join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]));
    page = await app.firstWindow();
    await page.locator(".monaco-workbench").waitFor({ state: "visible", timeout: 30000 });
    const trust = page.getByRole("button", { name: /Yes, I trust the authors/ });
    if (await trust.waitFor({ state: "visible", timeout: 3500 }).then(() => true, () => false)) {
      await trust.click();
    } else {
      const manage = page.getByText("Manage", { exact: true });
      if (await manage.isVisible()) {
        await manage.click();
        await page.locator(".workspace-trust-editor").getByRole("button", { name: "Trust", exact: true }).click();
        await page.locator(".workspace-trust-editor").getByRole("button", { name: "Don't Trust", exact: true }).waitFor({ state: "visible" });
        await page.locator(".monaco-modal-editor-block").getByRole("button", { name: /Close Modal Editor/ }).click();
      }
    }
    await stage("dedicated_workbench_ready");
    await page.getByText("inline-choice.ipynb", { exact: true }).dblclick();
    const editor = page.locator('.monaco-editor[data-uri*="inline-choice.ipynb"]').first();
    await editor.waitFor({ state: "visible", timeout: 30000 });
    // Decorations use generated CSS text, not source text. Read its selector; interact via Playwright.
    let markerSelector;
    for (let i = 0; i < 100 && !markerSelector; i += 1) {
      markerSelector = await editor.locator(".view-line span").evaluateAll((elements, label) => {
        const marker = elements.find(element => getComputedStyle(element, "::before").content === JSON.stringify(label));
        return marker ? "span." + [...marker.classList].map(value => CSS.escape(value)).join(".") : undefined;
      }, values.paths ? "[P]" : "[C]");
      if (!markerSelector) await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert(markerSelector, "[C] decoration must be rendered");
    report.decorationElements = await editor.locator('span[class*="ced-"]').evaluateAll(elements => elements.map(element => ({
      text: element.textContent, before: getComputedStyle(element, "::before").content
    })));
    const hint = editor.locator("zizaiMarker=" + (values.paths ? "[P]" : "[C]")).first();
    await hint.waitFor({ state: "visible", timeout: 20000 });
    await page.screenshot({ path: path.join(out, "inline-hint.png") });
    await stage(values.paths ? "inline_P_visible" : "inline_C_visible");
    async function verifyUndo(previous, current) {
      if (!values.undo) return;
      const normalize = text => {
        text = text.replaceAll("\r\n", "\n");
        return values.paths ? text.replace(/[A-Z]:/g, drive => drive.toLowerCase()) : text;
      };
      for (const [key, expected] of [["Control+z", previous], ["Control+y", current]]) {
        await editor.locator(".view-lines").click();
        await page.keyboard.press(key);
        await page.keyboard.press("Control+s");
        let saved;
        for (let attempt = 0; attempt < 50; attempt += 1) {
          saved = JSON.parse(await fs.readFile(notebookFile, "utf8"));
          if (normalize(saved.cells[0].source.join("")) === normalize(expected)) break;
          await new Promise(resolve => setTimeout(resolve, 100));
        }
        assert.equal(normalize(saved.cells[0].source.join("")), normalize(expected));
        assert.deepEqual(saved.cells[1], fixture.cells[1]);
        assert.equal(saved.cells[0].metadata.trialPreserve, true);
        assert.equal(saved.cells[0].execution_count, null);
        assert.deepEqual(saved.cells[0].outputs, []);
        await stage(key === "Control+z" ? "undo_saved_and_unrelated_cell_preserved" : "redo_saved_and_unrelated_cell_preserved");
      }
      report.undoRedo = true;
    }
    if (values.manual) {
      report.outcome = "awaiting_user";
      await stage("ready_for_user_no_automatic_selection");
      console.log("READY: Hands-on window stays open until user closes it or an approved finish signal arrives.");
      await new Promise(resolve => {
        const onInput = input => {
          if (input.trim() !== "finish") return;
          report.endSignalReceived = true;
          process.stdin.off("data", onInput);
          resolve();
        };
        process.stdin.setEncoding("utf8");
        process.stdin.on("data", onInput);
        app.once("close", () => {
          report.closedAt = new Date().toISOString();
          process.stdin.off("data", onInput);
          resolve();
        });
      });
      report.outcome = "manual_handoff_finished_not_automatically_graded";
      return;
    }
    if (values.paths) {
      const flow = await require("./path-flow.cjs").runPathFlow({ page, editor, workspace, notebookFile, originalSource, report, out, stage });
      await verifyUndo(flow.previousSource, flow.currentSource);
      report.outcome = "observed";
      return;
    }
    if (values.dependent) {
      await require('./dependent-flow.cjs').runDependentFlow({ page, editor, workspace, notebookFile, fixture, report, stage, externalYaml });
      report.outcome = 'observed';
      return;
    }
    for (const value of ["csv", "excel"]) {
      if (values.hover) {
        await hint.hover();
        const hover = page.locator(".monaco-hover").filter({ has: page.getByRole("link", { name: value, exact: true }) });
        const link = hover.getByRole("link", { name: value, exact: true });
        await link.waitFor({ state: "visible", timeout: 10000 });
        const hintBox = await hint.boundingBox();
        const hoverBox = await hover.boundingBox();
        assert(hintBox && hoverBox, "Hint and hover must be visible");
        const direction = hoverBox.y + hoverBox.height <= hintBox.y + 3 ? "above"
          : hoverBox.y >= hintBox.y + hintBox.height - 3 ? "below" : "overlap";
        const sameColumn = hoverBox.x <= hintBox.x + hintBox.width && hoverBox.x + hoverBox.width >= hintBox.x;
        report.hoverGeometry.push({ value, hint: hintBox, menu: hoverBox, direction, sameColumn });
        report.hoverLinks = await hover.getByRole("link").evaluateAll(elements => elements.map(element => ({
          text: element.textContent, href: element.getAttribute("href"), dataHref: element.getAttribute("data-href")
        })));
        assert.notEqual(direction, "overlap", "Menu must be above or below [C]");
        assert(sameColumn, "Menu must share [C]'s horizontal position");
        assert.equal(await page.locator(".quick-input-widget").isVisible(), false);
        await page.screenshot({ path: path.join(out, "hover-" + value + ".png") });
        if (values.human) {
          const box = await link.boundingBox();
          assert(box, "Candidate must have a visible target");
          const from = { x: hintBox.x + hintBox.width / 2, y: hintBox.y + hintBox.height / 2 };
          const to = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
          const steps = Math.ceil(Math.hypot(to.x - from.x, to.y - from.y));
          report.pointer = { value, from, to, steps, stepDelayMs: 8 };
          for (let step = 1; step <= steps; step += 1) {
            await page.mouse.move(from.x + (to.x - from.x) * step / steps, from.y + (to.y - from.y) * step / steps);
            await new Promise(resolve => setTimeout(resolve, 8));
            if (!await link.isVisible()) {
              report.pointer.disappearedAtStep = step;
              throw Error("Hover disappeared while moving from [C] to " + value);
            }
          }
          await page.mouse.down(); await page.mouse.up();
          let reflected = false;
          for (let attempt = 0; attempt < 30; attempt += 1) {
            const text = await editor.locator(".view-lines").innerText();
            if (text.includes('"' + value + '"')) { reflected = true; break; }
            await new Promise(resolve => setTimeout(resolve, 100));
          }
          assert(reflected, "Selected value must appear in the editor without saving first");
          await hover.waitFor({ state: "hidden", timeout: 5000 });
          if (value === "csv") {
            report.csvBeforeSave = { reflected: true, menuClosed: true };
            await stage("csv_reflected_without_save");
            continue;
          }
        } else {
          await link.click({ modifiers: [] });
        }
      } else {
      await hint.click({ modifiers: ["Control"] });
      const input = page.locator(".quick-input-widget input").first();
      await input.waitFor({ state: "visible", timeout: 10000 });
      if (value === "csv") await page.screenshot({ path: path.join(out, "standard-choice-list.png") });
      await input.fill(value);
      await page.keyboard.press("Enter");
      await input.waitFor({ state: "hidden", timeout: 10000 });
      }
      await editor.locator(".view-lines").click();
      await page.keyboard.press("Control+s");
      const expected = originalSource.replace('= ""', '= "' + value + '"');
      let saved;
      for (let i = 0; i < 50; i += 1) {
        saved = JSON.parse(await fs.readFile(notebookFile, "utf8"));
        if (saved.cells[0].source.join("") === expected) break;
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      assert.equal(saved.cells.length, 2);
      assert.deepEqual(saved.cells[1], fixture.cells[1]);
      assert.equal(saved.cells[0].source.join(""), expected);
      assert.equal(saved.cells[0].execution_count, null);
      assert.deepEqual(saved.cells[0].outputs, []);
      assert.equal(saved.cells[0].metadata.trialPreserve, true);
      assert.equal(saved.metadata.trialPreserve, true);
      report[value] = { sourceMatches: true, metadataPreserved: true, executionCount: null, outputsEmpty: true };
      await stage(value + "_chosen_and_saved");
    }
    await verifyUndo(originalSource.replace('= ""', '= "csv"'), originalSource.replace('= ""', '= "excel"'));
    await page.screenshot({ path: path.join(out, "reselected-excel.png") });
    report.outcome = "observed";
  } catch (error) {
    report.outcome = "not_observed";
    report.error = { name: error.name, message: error.message };
    if (page) {
      await page.screenshot({ path: path.join(out, "failure.png") }).catch(() => {});
      report.visibleUI = await page.locator("body").innerText().catch(() => "unavailable");
    }
    process.exitCode = 1;
  } finally {
    await save();
    if (app) {
      try { if (!report.closedAt) await app.close(); report.closedAt ||= new Date().toISOString(); }
      catch (error) { report.closeError = error.message; process.exitCode = 1; }
      // Electron's protocol endpoint can outlive the window briefly during normal shutdown.
      for (let attempt = 0; attempt < 25; attempt += 1) {
        const listing = execFileSync("netstat.exe", ["-ano", "-p", "tcp"], { encoding: "utf8", windowsHide: true });
        report.portCheck = report.ports.filter(Number.isInteger).map(port => ({ port,
          listeners: listing.split(/\r?\n/).filter(line => {
            const columns = line.trim().split(/\s+/);
            return columns[0] === "TCP" && Number(columns[1]?.split(":").at(-1)) === port && columns[3] === "LISTENING";
          }).length }));
        if (report.portCheck.every(item => item.listeners === 0)) break;
        await new Promise(resolve => setTimeout(resolve, 200));
      }
      if (report.portCheck.some(item => item.listeners)) process.exitCode = 1;
    }
    await save();
    console.log(JSON.stringify({ outcome: report.outcome, error: report.error, closed: !!report.closedAt, ports: report.portCheck }));
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
