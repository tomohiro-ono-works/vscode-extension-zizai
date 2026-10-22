"""TASK-001-02 evaluation only. Runs pinned upstream or a prototype patch in Chromium, not VS Code.

Usage: python browser-probe.py /path/to/pinned/zizai-form [--chromium PATH] [--patched] [--theme-checks] [--theme-override CSS]
No Python kernel, real OS dialog, connector, or product integration is exercised.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("upstream", type=Path)
parser.add_argument("--chromium", default=shutil.which("chromium"))
parser.add_argument("--report", type=Path)
parser.add_argument("--theme-checks", action="store_true")
parser.add_argument("--theme-override", type=Path)
parser.add_argument("--patched", action="store_true", help="Apply the evaluation-only combo patch to a temporary copy")
args = parser.parse_args()
EXPECTED = {
    "src/node-form.js": "e1c24cadbd01b2cad228f58a6504a7d82335c514",
    "src/node-form.css": "13bf86a1f5145178f97a868fd835a78d0419c0de",
    "sample/index.html": "434fe2bebb6f864289c5d7a612aaf5ec34be4c4e",
    "sample/config.js": "0fc1daed7dc2ab9437cd564b852e960f7b5e5940",
}
for name, expected in EXPECTED.items():
    data = (args.upstream / name).read_bytes()
    actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if actual != expected:
        raise SystemExit(f"Pinned upstream blob mismatch: {name}")
patch_sha256 = None
applied_patch_sha256 = None
if args.patched:
    patch = Path(__file__).resolve().parent / "patches/0001-combo-listener.patch"
    patch_bytes = patch.read_bytes()
    patch_sha256 = hashlib.sha256(patch_bytes).hexdigest()
    # Match the packaging probe: normalize patch input, never pinned source bytes.
    applied_patch_bytes = patch_bytes.replace(b"\r\n", b"\n")
    applied_patch_sha256 = hashlib.sha256(applied_patch_bytes).hexdigest()
    patch_temp = tempfile.TemporaryDirectory(prefix="nodeform-patched-")
    shutil.copytree(args.upstream, patch_temp.name, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", "node_modules"))
    patch_env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(Path(patch_temp.name).parent)}
    git_apply = ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "apply"]
    subprocess.run(git_apply + ["--check", "-"], cwd=patch_temp.name, env=patch_env, input=applied_patch_bytes, check=True)
    subprocess.run(git_apply + ["-"], cwd=patch_temp.name, env=patch_env, input=applied_patch_bytes, check=True)
    args.upstream = Path(patch_temp.name)
upstream_test = subprocess.run(["node", str(args.upstream.resolve() / "test/node-form.test.js")],
                               capture_output=True, text=True)
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=args.chromium, headless=True, args=["--no-sandbox"])
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    pointer_instrumentation = """(() => {
      const added = document.addEventListener.bind(document);
      const removed = document.removeEventListener.bind(document);
      const active = new Set();
      document.addEventListener = (type, callback, options) => {
        if (type === 'pointerdown') active.add(callback);
        return added(type, callback, options);
      };
      document.removeEventListener = (type, callback, options) => {
        if (type === 'pointerdown') active.delete(callback);
        return removed(type, callback, options);
      };
      window.probePointerListeners = active;
    })();"""
    # file:// navigation is blocked by this environment's browser policy.
    # Load the authorized, hash-checked source text in the test page instead.
    page.add_script_tag(content=(args.upstream / "sample/config.js").read_text())
    page.add_script_tag(content=(args.upstream / "src/node-form.js").read_text())
    html = (args.upstream / "sample/index.html").read_text()
    for tag in ['<script src="./config.js"></script>', '<script src="../src/node-form.js"></script>']:
        html = html.replace(tag, "")
    page.set_content(html)
    page.locator("#nodeForm .node-form__field").first.wait_for()
    sample_loaded = page.locator("#nodeForm .node-form__field").count() > 0
    page.evaluate(pointer_instrumentation)
    results = page.evaluate("""() => {
      const results = [];
      function check(name, fn) {
        try { results.push({ name, status: 'pass', details: fn() }); }
        catch (error) { results.push({ name, status: 'fail', details: String(error.message) }); }
      }
      function assert(condition, message) { if (!condition) throw Error(message); }
      function mount(fields, values = {}, onChange) {
        const root = document.createElement('div'); document.body.append(root);
        const node = { connector: 'Probe', action: 'run', form: values };
        const editor = NodeForm.mount({ root, node, forms: { 'Probe.run': fields }, onChange });
        return { root, node, editor, close() { editor.destroy(); root.remove(); } };
      }
      check('values, validation, restore without notification, original values untouched', () => {
        let changes = 0;
        const values = { name: 'before' };
        const f = mount([{ key: 'name', kind: 'text', required: true }], values, () => changes++);
        try {
          f.editor.setParams({ name: 'after' });
          assert(f.editor.getParams().name === 'after', 'value not restored');
          assert(changes === 0 && values.name === 'before', 'restore notified or mutated original');
          f.editor.setParams({ name: '' });
          assert(!f.editor.validate().valid, 'required validation absent');
          assert(f.root.querySelector('.node-form__error').textContent, 'no inline validation message');
          return { restoreNotified: changes, original: values.name };
        } finally { f.close(); }
      });
      check('user input emits change and separate forms keep separate values', () => {
        const changes = [];
        const a = mount([{ key: 'name', kind: 'text' }], { name: 'one' }, params => changes.push(params));
        const b = mount([{ key: 'name', kind: 'text' }], { name: 'two' });
        try {
          const input = a.root.querySelector('input'); input.value = 'edited';
          input.dispatchEvent(new Event('input', { bubbles: true }));
          assert(changes.at(-1).name === 'edited', 'user edit not notified');
          assert(b.editor.getParams().name === 'two', 'other form overwritten');
          return { first: a.editor.getParams().name, second: b.editor.getParams().name };
        } finally { a.close(); b.close(); }
      });
      check('visible_if hides validation but retains value in getParams', () => {
        const f = mount([{ key: 'mode', kind: 'text' },
          { key: 'detail', kind: 'text', required: true, visible_if: { key: 'mode', equals: 'show' } }],
          { mode: 'hide', detail: '' });
        try {
          assert(f.root.querySelector('[data-field-key="detail"]').hidden, 'detail not hidden');
          assert(f.editor.validate().valid, 'hidden field validated');
          assert(Object.hasOwn(f.editor.getParams(), 'detail'), 'expected retained hidden value');
          f.editor.setParams({ mode: 'show' });
          assert(!f.editor.validate().valid, 'shown required field skipped');
          return { hiddenValueExported: true };
        } finally { f.close(); }
      });
      check('simulated file selection result and cancellation', () => {
        let request;
        const f = mount([{ key: 'file', kind: 'file' }], { file: 'before.txt' });
        f.root.addEventListener('nodeform:browse-request', e => { request = e.detail; e.stopPropagation(); });
        try {
          const button = f.root.querySelector('.node-form__browse-button'); button.click();
          assert(request && button.disabled, 'no pending request');
          document.dispatchEvent(new CustomEvent('nodeform:browse-result', { detail: { ...request, value: 'after.txt' } }));
          assert(f.editor.getParams().file === 'after.txt' && !button.disabled, 'result not applied');
          button.click();
          document.dispatchEvent(new CustomEvent('nodeform:browse-result', { detail: { ...request, cancelled: true } }));
          assert(f.editor.getParams().file === 'after.txt' && !button.disabled, 'cancel changed value or left disabled');
          return { dialog: 'simulated DOM events only' };
        } finally { f.close(); }
      });
      check('destroy removes DOM and ignores a pending browse result', () => {
        let changes = 0, request;
        const f = mount([{ key: 'file', kind: 'file' }], {}, () => changes++);
        f.root.addEventListener('nodeform:browse-request', e => { request = e.detail; e.stopPropagation(); });
        f.root.querySelector('.node-form__browse-button').click();
        f.editor.destroy();
        document.dispatchEvent(new CustomEvent('nodeform:browse-result', { detail: { ...request, value: 'late.txt' } }));
        assert(changes === 0 && f.root.children.length === 0, 'late result applied after destroy');
        f.root.remove(); return { lateResultIgnored: true };
      });
      check('combo releases document pointerdown listeners after repeated input and destroy', () => {
        const baseline = window.probePointerListeners.size;
        const f = mount([{ key: 'choice', kind: 'combo', options: ['one', 'two'] }]);
        const input = f.root.querySelector('input');
        for (const text of ['o', 'on', 'one']) {
          input.value = text; input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        f.close();
        const remaining = window.probePointerListeners.size - baseline;
        assert(remaining === 0, `document pointerdown listeners remaining: ${remaining}`);
        return { remaining };
      });
      return results;
    }""")
    # Base CSS, evaluated separately from the sample's own inline style.
    style_page = browser.new_page()
    style_page.set_content('<body style="color:rgb(238,238,238);background:rgb(30,30,30)"><div class="node-form"><input class="node-form__input"></div></body>')
    style_page.add_style_tag(path=str(args.upstream / "src/node-form.css"))
    colors = style_page.locator("input").evaluate("el => ({ foreground: getComputedStyle(el).color, background: getComputedStyle(el).backgroundColor })")
    theme_results = []
    if args.theme_checks:
        fixtures = {
            "light": {"input": "rgb(255, 255, 255)", "foreground": "rgb(32, 32, 32)",
                      "button": "rgb(0, 122, 204)", "buttonText": "rgb(255, 255, 255)",
                      "menu": "rgb(255, 255, 255)", "border": "rgb(136, 136, 136)",
                      "focus": "rgb(0, 144, 241)", "error": "rgb(161, 38, 13)"},
            "dark": {"input": "rgb(60, 60, 60)", "foreground": "rgb(238, 238, 238)",
                     "button": "rgb(14, 99, 156)", "buttonText": "rgb(255, 255, 255)",
                     "menu": "rgb(45, 45, 45)", "border": "rgb(136, 136, 136)",
                     "focus": "rgb(0, 144, 241)", "error": "rgb(244, 135, 113)"},
            "high-contrast": {"input": "rgb(0, 0, 0)", "foreground": "rgb(255, 255, 255)",
                              "button": "rgb(0, 0, 0)", "buttonText": "rgb(255, 255, 255)",
                              "menu": "rgb(0, 0, 0)", "border": "rgb(255, 255, 0)",
                              "focus": "rgb(0, 255, 255)", "error": "rgb(255, 128, 128)"},
        }
        for name, theme in fixtures.items():
            target = browser.new_page()
            target.set_content('<body><input id="outside" style="background:rgb(7,8,9)"><div class="node-form">'
                               '<input class="node-form__input"><textarea class="node-form__textarea"></textarea>'
                               '<select class="node-form__select"><option>test</option></select>'
                               '<button class="node-form__browse-button">test</button>'
                               '<div class="node-form__combo-menu">test</div>'
                               '<div class="node-form__error">test</div></div></body>')
            variables = {
                "input-background": theme["input"], "input-foreground": theme["foreground"],
                "input-border": theme["border"], "button-background": theme["button"],
                "button-foreground": theme["buttonText"], "dropdown-background": theme["menu"],
                "dropdown-foreground": theme["foreground"], "dropdown-border": theme["border"],
                "focusBorder": theme["focus"], "errorForeground": theme["error"],
            }
            if name == "high-contrast":
                variables["contrastBorder"] = theme["border"]
            target.evaluate("vars => { for (const [key, value] of Object.entries(vars)) document.documentElement.style.setProperty('--vscode-' + key, value); }", variables)
            target.add_style_tag(path=str(args.upstream / "src/node-form.css"))
            if args.theme_override:
                target.add_style_tag(path=str(args.theme_override))
            target.locator(".node-form__input").focus()
            actual = target.evaluate("""() => {
                const css = cls => getComputedStyle(document.querySelector(cls));
                return { input: css('.node-form__input').backgroundColor,
                    inputText: css('.node-form__input').color,
                    textarea: css('.node-form__textarea').backgroundColor,
                    select: css('.node-form__select').backgroundColor,
                    button: css('.node-form__browse-button').backgroundColor,
                    buttonText: css('.node-form__browse-button').color,
                    menu: css('.node-form__combo-menu').backgroundColor,
                    border: css('.node-form__input').borderTopColor,
                    focus: css('.node-form__input').outlineColor,
                    error: css('.node-form__error').color,
                    outside: css('#outside').backgroundColor };
            }""")
            expected = {"input": theme["input"], "inputText": theme["foreground"],
                        "textarea": theme["input"], "select": theme["input"],
                        "button": theme["button"], "buttonText": theme["buttonText"],
                        "menu": theme["menu"], "border": theme["border"], "focus": theme["focus"],
                        "error": theme["error"], "outside": "rgb(7, 8, 9)"}
            mismatches = {key: {"expected": value, "actual": actual[key]}
                          for key, value in expected.items() if actual[key] != value}
            theme_results.append({"name": name, "status": "fail" if mismatches else "pass",
                                  "actual": actual, "mismatches": mismatches})
            target.close()
    report = {"upstreamCommit": "f08bfc73350d04e9238b43fa4dbcfdb81fa5150e",
              "python": platform.python_version(), "surface": "standalone upstream sample, not Notebook or Webview", "browser": browser.version,
              "sampleLoaded": sample_loaded, "resourceLoading": "injected local source in blank page", "pageErrors": errors, "checks": results,
              "baseCssDarkParent": colors, "variant": "patched-prototype" if args.patched else "upstream",
              "patchSha256": patch_sha256, "sourceCheckoutModified": False,
              "appliedPatchSha256": applied_patch_sha256,
              "themeChecks": theme_results,
              "themeOverrideSha256": hashlib.sha256(args.theme_override.read_bytes()).hexdigest() if args.theme_override else None,
              "upstreamTest": {"exitCode": upstream_test.returncode, "stdout": upstream_test.stdout.strip(), "stderr": upstream_test.stderr.strip()}}
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    print(output)
    browser.close()
    if upstream_test.returncode or errors or any(item["status"] == "fail" for item in results + theme_results):
        raise SystemExit(1)
