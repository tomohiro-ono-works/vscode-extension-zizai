"use strict";
// Dedicated Python/Jupyter form session. All UI actions use Playwright;
// native Tk folder selection is deliberately left to the user.
const fs = require("node:fs/promises");
const path = require("node:path");
const assert = require("node:assert/strict");
const { createRequire } = require("node:module");
const { execFileSync } = require("node:child_process");
const root = path.resolve(__dirname, "../..");
const requireProbe = createRequire(path.join(root, "docs/research/notebook-host/playwright-probe/package.json"));
const { _electron: electron } = requireProbe("playwright");
const out = path.resolve(process.argv[2] || "");
const relative = path.relative(path.join(root, "results"), out);
assert(relative && !relative.startsWith("..") && !path.isAbsolute(relative), "Use a fresh results subfolder");

async function main() {
  const resume = process.argv.includes("--resume");
  if (!resume) await fs.mkdir(out);
  const workspace = path.join(out, "workspace");
  const profile = path.join(out, "profile");
  const extensions = path.join(out, "extensions");
  const python = path.join(root, "results/task010-forms-env-20261112/Scripts/python.exe");
  const vscode = path.join(root, "results/vscode-insiders-compare-20261108/app/Code - Insiders.exe");
  if (!resume) {
    await fs.mkdir(workspace);
    await fs.mkdir(path.join(workspace, "sample-folder"));
    await fs.mkdir(path.join(profile, "User"), { recursive: true });
    await fs.mkdir(extensions);
    for (const name of ["ms-python.python-2026.10.0-win32-x64", "ms-python.debugpy-2026.6.0-win32-x64",
      "ms-python.vscode-python-envs-1.43.2026111101-win32-x64", "ms-toolsai.jupyter-2025.9.1-win32-x64",
      "ms-toolsai.jupyter-renderers-1.3.0"]) {
      await fs.cp(path.join(process.env.USERPROFILE, ".vscode/extensions", name), path.join(extensions, name), { recursive: true });
    }
    const kernelDir = path.join(out, "jupyter/kernels/zizai-form-preview");
    await fs.mkdir(kernelDir, { recursive: true });
    await fs.writeFile(path.join(kernelDir, "kernel.json"), JSON.stringify({
      argv: [python, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
      display_name: "ZizAI Form Preview (isolated)", language: "python"
    }));
    await fs.writeFile(path.join(profile, "User/settings.json"), JSON.stringify({
      "window.title": "ZizAI Python Form Sample ${activeEditorShort}",
      "window.restoreWindows": "none", "workbench.startupEditor": "none", "files.autoSave": "off",
      "extensions.autoUpdate": false, "extensions.autoCheckUpdates": false, "update.mode": "none",
      "telemetry.telemetryLevel": "off", "python.defaultInterpreterPath": python,
      "python.experiments.enabled": false, "jupyter.experiments.enabled": false,
      "workbench.editorAssociations": { "*.ipynb": "jupyter-notebook" }
    }, null, 2));
    const sample = JSON.parse(await fs.readFile(path.join(root, "examples/python-form.ipynb"), "utf8"));
    sample.metadata.kernelspec = { display_name: "ZizAI Form Preview (isolated)", language: "python", name: "zizai-form-preview" };
    const notebook = path.join(workspace, "python-form.ipynb");
    await fs.writeFile(notebook, JSON.stringify(sample, null, 2));
  }
  const notebook = path.join(workspace, "python-form.ipynb");
  if (resume) {
    const backup = path.join(out, "before-resume-" + Date.now());
    await fs.mkdir(backup);
    for (const name of ["session.local.json", "console.local.json", "request.json", "response.json"]) {
      await fs.copyFile(path.join(out, name), path.join(backup, name)).catch(error => { if (error.code !== "ENOENT") throw error; });
    }
    await fs.copyFile(notebook, path.join(backup, "python-form.ipynb"));
  }
  const report = { startedAt: new Date().toISOString(), runnerPid: process.pid, out, notebook, python,
    playwright: requireProbe("playwright/package.json").version, nativeFolderSelection: "not_automated",
    userProfileModified: false, customExtensionInstalled: false, actions: [] };
  async function writeJson(file, value) {
    const temporary = file + ".writing";
    await fs.writeFile(temporary, JSON.stringify(value, null, 2));
    await fs.rename(temporary, file);
  }
  const save = () => writeJson(path.join(out, "session.local.json"), report);
  const env = { ...process.env, JUPYTER_PATH: path.join(out, "jupyter"),
    JUPYTER_CONFIG_DIR: path.join(out, "jupyter-config"), JUPYTER_RUNTIME_DIR: path.join(out, "jupyter-runtime"),
    JUPYTER_DATA_DIR: path.join(out, "jupyter-data"), IPYTHONDIR: path.join(out, "ipython") };
  delete env.ELECTRON_RUN_AS_NODE; delete env.VSCODE_DEV; delete env.VSCODE_PORTABLE;
  const app = await electron.launch({ executablePath: vscode, env, timeout: 60000, args: [
    "--new-window", "--skip-welcome", "--skip-release-notes", "--disable-telemetry", "--disable-updates",
    "--locale=en", "--remote-debugging-address=127.0.0.1", "--user-data-dir=" + profile,
    "--shared-data-dir=" + path.join(out, "shared-data"), "--extensions-dir=" + extensions, workspace, notebook
  ] });
  const page = await app.firstWindow();
  async function repairNotebookViewport() {
    // Playwright's iframe auto-scroll can change the host's native scrollLeft,
    // which VS Code does not use for its virtual Notebook scrolling. This is
    // viewport preparation only, never a substitute for field input events.
    const repaired = await page.locator(".notebookOverlay .monaco-scrollable-element").evaluateAll(elements =>
      elements.filter(element => element.scrollLeft !== 0).map(element => {
        const previous = element.scrollLeft;
        element.scrollLeft = 0;
        return { previous, current: element.scrollLeft };
      }));
    if (repaired.length) (report.viewportRepairs ||= []).push({ at: new Date().toISOString(), repaired });
  }
  const consoleEvents = [];
  page.on("console", message => { consoleEvents.push({ type: message.type(), text: message.text(), location: message.location() });
    void fs.writeFile(path.join(out, "console.local.json"), JSON.stringify(consoleEvents, null, 2)); });
  page.on("pageerror", error => { consoleEvents.push({ type: "pageerror", text: error.stack });
    void fs.writeFile(path.join(out, "console.local.json"), JSON.stringify(consoleEvents, null, 2)); });
  await page.locator(".monaco-workbench").waitFor({ timeout: 45000 });
  report.launcherPid = app.process().pid;
  report.electronMainPid = await app.evaluate(() => process.pid);
  report.ports = [await app.evaluate(() => process.debugPort), Number((await fs.readFile(path.join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0])];
  await save();
  console.log("READY " + out);
  // Resuming must never replay a previous selection, save, or shutdown action.
  let lastId = await fs.readFile(path.join(out, "request.json"), "utf8").then(text => JSON.parse(text).id, () => undefined);
  let closed = false;
  app.once("close", () => { closed = true; });
  while (!closed) {
    const request = await fs.readFile(path.join(out, "request.json"), "utf8").then(JSON.parse, () => null);
    if (!request || request.id === lastId) { await new Promise(resolve => setTimeout(resolve, 150)); continue; }
    lastId = request.id;
    const response = { id: request.id, at: new Date().toISOString(), results: [] };
    try {
      for (const action of request.actions) {
        await repairNotebookViewport();
        const frame = action.frame === undefined ? page : page.frames()[action.frame];
        const locator = action.role ? frame.getByRole(action.role, { name: action.name, exact: action.exact ?? true })
          : action.text ? frame.getByText(action.text, { exact: action.exact ?? true }) : frame.locator(action.selector || "body");
        const target = action.index === undefined ? locator : locator.nth(action.index);
        if (action.op === "snapshot") response.results.push(await target.ariaSnapshot({ timeout: 10000 }));
        else if (action.op === "frames") response.results.push(page.frames().map((f, index) => ({ index, url: f.url() })));
        else if (action.op === "click") await target.click({ timeout: 15000 });
        else if (action.op === "fill") await target.fill(action.value, { timeout: 15000 });
        else if (action.op === "press") await target.press(action.value, { timeout: 15000 });
        else if (action.op === "select") await target.selectOption(action.value, { timeout: 15000 });
        else if (action.op === "text") response.results.push(await target.allTextContents());
        else if (action.op === "count") response.results.push(await target.count());
        else if (action.op === "expectText") { await requireProbe("playwright/test").expect(target).toContainText(action.value, { timeout: 20000 }); }
        else if (action.op === "inspect") response.results.push(await target.evaluateAll(elements => elements.map(e => ({ tag: e.tagName, text: e.textContent, html: e.outerHTML.slice(0, 2000), rect: e.getBoundingClientRect().toJSON() }))));
        else if (action.op === "screenshot") { const file = path.join(out, "screen-" + request.id + ".png"); await page.screenshot({ path: file }); response.results.push(file); }
        else if (action.op === "finish") { assert(request.authorization === "user_approved_end"); await app.close(); closed = true; }
        else throw new Error("Unsupported Playwright action: " + action.op);
        if (!closed) await repairNotebookViewport();
      }
    } catch (error) { response.error = error.message; }
    report.actions.push({ request, response });
    await writeJson(path.join(out, "response.json"), response);
    await save();
    console.log("RESPONSE " + request.id + (response.error ? " ERROR " + response.error : " OK"));
  }
  report.closedAt = new Date().toISOString();
  report.netstatAtClose = execFileSync("netstat.exe", ["-ano", "-p", "tcp"], { encoding: "utf8", windowsHide: true })
    .split(/\r?\n/).filter(line => report.ports.some(port => line.includes(":" + port + " ")));
  await save();
}
main().catch(error => { console.error(error.stack); process.exitCode = 1; });
