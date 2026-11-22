"""HTML->PDF using installed Microsoft Edge or Google Chrome, standard library only."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def browser_candidates() -> list[str]:
    candidates = []
    if os.name == 'nt':
        for name in ('msedge.exe', 'chrome.exe'):
            found = shutil.which(name)
            if found:
                candidates.append(found)
        for env, relative in (
            ('PROGRAMFILES(X86)', 'Microsoft/Edge/Application/msedge.exe'),
            ('PROGRAMFILES', 'Microsoft/Edge/Application/msedge.exe'),
            ('PROGRAMFILES', 'Google/Chrome/Application/chrome.exe'),
            ('LOCALAPPDATA', 'Microsoft/Edge/Application/msedge.exe'),
        ):
            if os.environ.get(env):
                candidates.append(str(Path(os.environ[env]) / relative))
    else:
        for name in ('chromium', 'chromium-browser', 'google-chrome', 'microsoft-edge'):
            found = shutil.which(name)
            if found:
                candidates.append(found)
    return [p for p in dict.fromkeys(candidates) if Path(p).is_file()]


def export_pdf(html: str, target: str) -> str:
    if not browser_candidates():
        raise RuntimeError('PDF出力にはインストール済みのMicrosoft EdgeまたはGoogle Chromeが必要です。HTML出力は利用できます。')
    output = Path(target).expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix='zizai-slide-') as temp:
        page = Path(temp) / 'slides.html'
        page.write_text(html, encoding='utf-8')
        errors = []
        rendered = Path(temp) / 'rendered.pdf'
        for browser in browser_candidates():
            command = [browser, '--headless=new', '--disable-gpu', '--no-first-run',
                       '--no-default-browser-check', '--disable-background-networking',
                       '--disable-extensions', '--print-to-pdf-no-header',
                       f'--print-to-pdf={rendered}', page.as_uri()]
            try:
                run = subprocess.run(command, capture_output=True, text=True, timeout=70, check=False)
                if run.returncode == 0 and rendered.is_file() and rendered.stat().st_size > 500:
                    shutil.copyfile(rendered, output)
                    return str(output)
                errors.append(f'{Path(browser).name}: {run.stderr[-200:]}')
            except (OSError, subprocess.TimeoutExpired) as error:
                errors.append(f'{Path(browser).name}: {error}')
        raise RuntimeError('ブラウザからPDFを出力できませんでした。' + '; '.join(errors)[:400])


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload.get('html'), str) or not isinstance(payload.get('output'), str):
            raise ValueError('htmlとoutputを指定してください。')
        target = export_pdf(payload['html'], payload['output'])
        print(json.dumps({'ok': True, 'path': target}, ensure_ascii=False))
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
