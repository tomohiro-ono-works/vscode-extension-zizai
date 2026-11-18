"""Local DuckDB operations adapted from ZizAI 64a1be1."""
from datetime import datetime
from pathlib import Path

import duckdb
from zizai.core.tabular import TabularOperations


_DB_ONLY_CONFIG = {
    'enable_external_access': 'false',
    'autoinstall_known_extensions': 'false',
    'autoload_known_extensions': 'false',
    'allow_community_extensions': 'false',
}


def _existing_db_path(db_file):
    path = Path(db_file).resolve()
    if not path.is_file():
        raise FileNotFoundError(f'DBファイルが見つかりません: {path.as_posix()}')
    return path


def create_db_file(db_folder, db_file_name='sample.duckdb'):
    """Create or open a local DuckDB file and return its metadata."""
    if db_folder is None or not str(db_folder).strip():
        raise ValueError('DBファイルの場所を指定してください。')
    if (not isinstance(db_file_name, str) or not db_file_name.strip() or db_file_name in ('.', '..')
            or any(separator in db_file_name for separator in ('/', '\\', ':'))):
        raise ValueError('DBファイル名にはファイル名だけを指定してください。')
    name = db_file_name if Path(db_file_name).suffix else db_file_name + '.duckdb'
    folder = Path(db_folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    with duckdb.connect(str(path), config=_DB_ONLY_CONFIG):
        pass
    metadata = {
        'file_path': path.as_posix(),
        'db_file': path.name,
        'database': path.stem,
        'created_at': datetime.now().isoformat(timespec='seconds'),
    }
    return TabularOperations.attach_dataframe_schema(TabularOperations.to_dataframe(metadata))


def execute_sql(db_file, sql):
    """Run trusted SQL against an existing database with external access disabled."""
    path = _existing_db_path(db_file)
    with duckdb.connect(str(path), config=_DB_ONLY_CONFIG) as connection:
        connection.execute('SET lock_configuration = true')
        cursor = connection.execute(sql)
        if cursor.description is not None:
            result = cursor.df()
        else:
            result = TabularOperations.to_dataframe({
                'db_file': path.as_posix(),
                'status': 'executed',
                'executed_at': datetime.now().isoformat(timespec='seconds'),
            })
    return TabularOperations.attach_dataframe_schema(result)


def execute_sql_file(db_file, sql_file, *, encoding='utf8'):
    """Read the selected script in Python, then run it with the same SQL settings."""
    return execute_sql(db_file, Path(sql_file).read_text(encoding=encoding))


def create_table(db_file, data, table_name='table1', *, replace=False):
    """Persist table data and replace an existing table only when requested."""
    name = table_name.strip() if isinstance(table_name, str) else ''
    if not name or name[0].isdigit() or any(not (char.isalnum() or char == '_') for char in name):
        raise ValueError('テーブル名は英数字とアンダースコアで、先頭は数字以外にしてください。')
    if type(replace) is not bool:
        raise TypeError('replaceは真偽値を指定してください。')
    frame = TabularOperations.to_dataframe(data)
    if frame.empty:
        raise ValueError('入力データが空です。')
    path = _existing_db_path(db_file)
    command = 'CREATE OR REPLACE TABLE' if replace else 'CREATE TABLE'
    with duckdb.connect(str(path), config=_DB_ONLY_CONFIG) as connection:
        connection.register('_zizai_input_df', frame)
        connection.execute(f'{command} main."{name}" AS SELECT * FROM temp.main."_zizai_input_df"')
    result = TabularOperations.to_dataframe({
        'db_file': path.as_posix(),
        'table_name': name,
        'rows': len(frame),
        'created_at': datetime.now().isoformat(timespec='seconds'),
    })
    return TabularOperations.attach_dataframe_schema(result)
