"""Execute a selected Windows batch file with explicit arguments."""
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

import pandas as pd


def execute_bat(file_path, *, args=()):
    """Run a trusted .bat file and return its stdout, stderr and status."""
    if os.name != 'nt':
        raise NotImplementedError('BATファイルの実行はWindowsで利用できます。')
    path = Path(file_path).absolute()
    if path.suffix.lower() != '.bat':
        raise ValueError('拡張子が .bat のファイルを指定してください。')
    if not path.is_file():
        raise FileNotFoundError(f'BATファイルが見つかりません: {path.as_posix()}')
    if not isinstance(args, (list, tuple)) or any(
        not isinstance(arg, str) or any(char in arg for char in ('"', '\r', '\n', '\0')) for arg in args
    ):
        raise ValueError('引数はダブルクォート、改行、NULを含まない文字列の配列で指定してください。')

    cmd = str(Path(os.environ['SystemRoot']) / 'System32' / 'cmd.exe')
    env = {**os.environ, 'ZIZAI_BATCH_FILE': str(path)}
    tokens = ['"%ZIZAI_BATCH_FILE%"']
    for index, argument in enumerate(args):
        name = f'ZIZAI_BATCH_ARG_{index}'
        env[name] = argument
        tokens.append(f'"%{name}%"')
    # Use fixed variable references and one expansion pass, with delayed expansion off.
    command = f'{subprocess.list2cmdline([cmd])} /d /s /v:off /c "' + ' '.join(tokens) + '"'
    process = subprocess.run(
        command, executable=cmd, env=env, stdin=subprocess.DEVNULL, capture_output=True,
        encoding='cp932', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW,
    )
    stdout = process.stdout.strip()
    stderr = process.stderr.strip()
    if process.returncode:
        raise RuntimeError(f'BAT実行に失敗しました。終了コード {process.returncode}\n'
                           f'Stdout: {stdout}\nStderr: {stderr}')
    return pd.DataFrame([{
        'status': 'success',
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'connector': 'ShellConnector',
        'action': 'execute_bat',
        'target': path.as_posix(),
        'message': 'BAT実行成功' if stdout else 'BAT実行成功（出力なし）',
        'stdout': stdout,
        'stderr': stderr,
        'returncode': process.returncode,
    }])
