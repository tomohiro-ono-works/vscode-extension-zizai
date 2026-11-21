"""Run an explicitly invoked SQL cell and route the resulting table."""

from importlib import import_module
from importlib.util import find_spec
from keyword import iskeyword
from pathlib import Path
from unicodedata import normalize


_CONNECTIONS = {
    'bigquery': 'zizai_bq_project',
    'duckdb': 'zizai_duck_db',
}


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
        path = path.absolute()
        if path.exists() or path.is_symlink():
            raise FileExistsError(f'出力先が既にあります: {path}')
        if not path.parent.is_dir():
            raise FileNotFoundError(f'出力先フォルダーがありません: {path.parent}')
        if extension == '.xlsx' and find_spec('openpyxl') is None:
            raise ModuleNotFoundError('Excel出力にはZizAIの excel 追加ライブラリが必要です。')
        return path

    name = normalize('NFKC', target)
    if not name.isidentifier() or iskeyword(name):
        raise ValueError('出力先はPythonの変数名、または .csv / .xlsx ファイルにしてください。')
    return name


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
    destination = _destination(line)
    name = _CONNECTIONS[connector]
    connection = namespace.get(name)
    if isinstance(connection, str):
        connection = connection.strip()
    if not (connection and (isinstance(connection, str) or
                            (connector == 'duckdb' and isinstance(connection, Path)))):
        raise ValueError(f'先にPythonセルで {name} に接続先を指定してください。')
    module = import_module(connector + '_connector')
    frame = module.execute_sql(connection, sql)
    if isinstance(destination, Path):
        return _write_table(frame, destination)
    if destination is not None:
        namespace[destination] = frame
        return None
    return frame
