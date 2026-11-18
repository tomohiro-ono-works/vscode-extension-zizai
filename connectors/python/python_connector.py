"""Run a user-provided main() in a separate Python process."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


_RUN_MAIN = """
import json
from pathlib import Path
import runpy
import sys

source, destination = map(Path, sys.argv[1:])
main = runpy.run_path(str(source), run_name='__ziz_user__').get('main')
if not callable(main):
    raise ValueError('引数なしの main() を定義してください。')
result = main()
pandas = sys.modules.get('pandas')
if pandas is not None and isinstance(result, pandas.DataFrame):
    payload = {'kind': 'dataframe', 'value': result.to_dict(orient='split', index=False)}
else:
    payload = {'kind': 'value', 'value': result}
destination.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding='utf-8')
"""


def _interpreter(env_path):
    selection = str(env_path or '').strip()
    if selection.lower() in ('', 'default', 'defult', 'system'):
        return sys.executable
    path = Path(selection).expanduser()
    if not path.is_absolute():
        raise ValueError('Python実行ファイルまたは仮想環境を絶対パスで指定してください。')
    if path.is_dir():
        path = path / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not path.is_file():
        raise FileNotFoundError(f'Python実行ファイルが見つかりません: {path.as_posix()}')
    if os.name == 'nt' and path.suffix.lower() != '.exe':
        raise ValueError('WindowsではPythonの.exeを指定してください。')
    return str(path)


def execute_python(script, *, env_path=None):
    """Run trusted code and return main()'s result separately from process logs."""
    if not isinstance(script, str) or not script.strip():
        raise ValueError('スクリプトを入力してください。')
    python = _interpreter(env_path)
    with TemporaryDirectory(prefix='zizai-python-') as directory:
        source = Path(directory) / 'user_script.py'
        output = Path(directory) / 'result.json'
        source.write_text(script, encoding='utf-8')
        process = subprocess.run(
            [python, '-B', '-X', 'utf8', '-c', _RUN_MAIN, str(source), str(output)],
            capture_output=True, encoding='utf-8', errors='replace',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if process.stdout:
            print(process.stdout, end='')
        if process.stderr:
            print(process.stderr, end='', file=sys.stderr)
        if process.returncode:
            raise RuntimeError(f'Python実行に失敗しました。終了コード {process.returncode}')
        if not output.is_file():
            raise RuntimeError('Pythonのmain()から戻り値を取得できませんでした。')
        payload = json.loads(output.read_text(encoding='utf-8'))
    if payload['kind'] == 'dataframe':
        from pandas import DataFrame

        return DataFrame(**payload['value'])
    value = payload['value']
    if isinstance(value, (list, dict)):
        from zizai.core.tabular import TabularOperations

        return TabularOperations.to_dataframe(value)
    return value
