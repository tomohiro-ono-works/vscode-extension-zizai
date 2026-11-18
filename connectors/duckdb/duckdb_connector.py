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
