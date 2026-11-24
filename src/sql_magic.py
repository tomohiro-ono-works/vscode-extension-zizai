"""Run an explicitly invoked SQL cell and route the resulting table."""

from importlib import import_module
from importlib.util import find_spec
import json
from keyword import iskeyword
from pathlib import Path
from unicodedata import normalize

from .connector_forms import form_support


def _destination(line):
    line = line.strip()
    if not line:
        return None
    operator, target = line[0], line[1:].strip()
    if operator != '>' or not target:
        raise ValueError('出力先は > 変数名、> ファイル名.csv、> ファイル名.xlsx の形式で指定してください。')
    if target.startswith(('"', "'")):
        if len(target) < 2 or not target.endswith(target[0]):
            raise ValueError('出力先を同じ引用符で囲んでください。')
        target = target[1:-1]
    if not target.strip() or target.startswith('>'):
        raise ValueError('出力先を指定してください。')

    path = Path(target)
    extension = path.suffix.lower()
    if extension:
        if extension not in {'.csv', '.xlsx'}:
            raise ValueError('出力ファイルの拡張子には .csv または .xlsx を指定してください。')
        return path

    name = normalize('NFKC', target)
    if not name.isidentifier() or iskeyword(name):
        raise ValueError('出力先はPythonの変数名、または .csv / .xlsx ファイルにしてください。')
    return name


def render_sql_magic(connector, connection, sql, output):
    support = form_support(connector)
    magic = support.MAGIC_NAME
    option, _, _ = support.SQL_CONNECTION
    target = output.strip()
    if any(character in target for character in '\r\n\0'):
        raise ValueError('出力先は1行で指定してください。')
    redirect = f' > {target}' if target else ''
    _destination(redirect)
    header = f'%%{magic} {option} {json.dumps(connection, ensure_ascii=False)}{redirect}'
    return f'{header}\n{sql}' + ('' if sql.endswith('\n') else '\n')


def _read_arguments(connector, line, namespace):
    option, variable, _ = form_support(connector).SQL_CONNECTION
    line = line.strip()
    if not line.startswith('--'):
        return namespace.get(variable), _destination(line)
    parts = line.split(maxsplit=1)
    if len(parts) != 2 or parts[0] != option:
        raise ValueError(f'接続先は {option} "接続先" の形式で指定してください。')
    argument = parts[1]
    try:
        connection, end = json.JSONDecoder().raw_decode(argument)
    except json.JSONDecodeError as error:
        raise ValueError(f'{option} の接続先は二重引用符で囲んでください。') from error
    if not isinstance(connection, str) or not connection.strip():
        raise ValueError(f'{option} に接続先を指定してください。')
    return connection, _destination(argument[end:])


def _check_file_destination(path):
    if path.exists() or path.is_symlink():
        raise FileExistsError(f'出力先が既にあります: {path}')
    if not path.parent.is_dir():
        raise FileNotFoundError(f'出力先フォルダーがありません: {path.parent}')
    if path.suffix.lower() == '.xlsx' and find_spec('openpyxl') is None:
        raise ModuleNotFoundError('Excel出力にはZizAIの excel 追加ライブラリが必要です。')


def _write_table(frame, path):
    stream = path.open('xb')
    try:
        with stream:
            if path.suffix.lower() == '.csv':
                frame.to_csv(stream, encoding='utf-8-sig', index=False)
            else:
                from pandas import ExcelWriter
                with ExcelWriter(stream, engine='openpyxl') as writer:
                    frame.to_excel(writer, index=False)
                    for row in writer.book.worksheets[0].iter_rows():
                        for cell in row:
                            if cell.data_type == 'f':
                                cell.data_type = 's'
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return str(path)


def run_sql_cell(connector, line, sql, namespace):
    if not sql.strip():
        raise ValueError('マジックの次の行にSQLを入力してください。')
    connection, destination = _read_arguments(connector, line, namespace)
    if isinstance(connection, str):
        connection = connection.strip()
    _, variable, accepted_types = form_support(connector).SQL_CONNECTION
    if not isinstance(connection, accepted_types) or not connection:
        raise ValueError(f'先にPythonセルで {variable} に接続先を指定してください。')
    if isinstance(destination, Path):
        destination = destination.absolute()
        _check_file_destination(destination)
    module = import_module(connector + '_connector')
    frame = module.execute_sql(connection, sql)
    if isinstance(destination, Path):
        return _write_table(frame, destination)
    if destination is not None:
        namespace[destination] = frame
        return None
    return frame
