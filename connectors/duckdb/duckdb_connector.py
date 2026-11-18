"""Local DuckDB operations adapted from ZizAI 64a1be1."""
from datetime import datetime
from pathlib import Path

import duckdb
from zizai.core.tabular import TabularOperations


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
    with duckdb.connect(str(path), config={'enable_external_access': 'false'}):
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
    path = Path(db_file).resolve()
    if not path.is_file():
        raise FileNotFoundError(f'DBファイルが見つかりません: {path.as_posix()}')
    config = {
        'enable_external_access': 'false',
        'autoinstall_known_extensions': 'false',
        'autoload_known_extensions': 'false',
        'allow_community_extensions': 'false',
    }
    with duckdb.connect(str(path), config=config) as connection:
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
