"""CSV read/write functions for an ordinary Python or Jupyter process.

Adapted from apps/connectors/csv_connector.py in
tomohiro-ono-works/zizai@64a1be160c06f4a6924b2fcdb6d007f22b1fce78.
The data operations are preserved; Engine/context lookup and callbacks are
replaced by direct arguments, return values, and normal Python exceptions.
"""
import os

import pandas as pd
from zizai.core.tabular import TabularOperations as _Tables

DEFAULT_CHUNK_SIZE = 50000


def _path(value, name):
    if value is None or value == '':
        raise ValueError(f'{name} は必須です。')
    return _Tables.normalize_file_path(os.fspath(value))


def _delimiter(value):
    text = str(value or ',')
    return '\t' if text in ('\\t', 'tab', 'TAB') else text


def _chunk_size(value):
    if value is None or not str(value).strip():
        return 0
    result = int(str(value).strip())
    if result < 0:
        raise ValueError('chunk_size は 0 以上で指定してください。')
    return result


def _usecols(schema):
    if schema is None or not str(schema).strip():
        return None
    items = _Tables.parse_schema_definition(schema)
    if not isinstance(items, list):
        return None
    names = []
    for item in items:
        if isinstance(item, dict):
            name = str(item.get('origin_name') or '').strip()
            if name and name not in names:
                names.append(name)
    return names or None


def read_csv(file_path, *, encoding='utf-8', delimiter=',', header_row=1,
             data_start_row=2, chunk_size=DEFAULT_CHUNK_SIZE, schema=None,
             date_cleansing=True):
    """Return a DataFrame; row numbers are one-based, chunk_size=0 reads at once.

    Relative paths use this Python process's cwd. Chunked reads are combined
    into one in-memory DataFrame, as in the original connector.
    """
    path = _path(file_path, 'file_path')
    header_row, data_start_row = int(header_row), int(data_start_row)
    if header_row < 1:
        raise ValueError('header_row は 1 以上で指定してください。')
    if data_start_row < header_row:
        raise ValueError('data_start_row は header_row 以上で指定してください。')
    skiprows = list(range(header_row, data_start_row - 1)) if data_start_row > header_row + 1 else None
    columns = _usecols(schema)
    size = _chunk_size(chunk_size)
    kwargs = dict(encoding=encoding, sep=_delimiter(delimiter), header=header_row - 1,
                  skiprows=skiprows, dtype=object, usecols=columns)
    try:
        if size:
            with pd.read_csv(path, chunksize=size, **kwargs) as reader:
                chunks = list(reader)
            frame = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
        else:
            frame = pd.read_csv(path, **kwargs)
    except pd.errors.EmptyDataError:
        frame = pd.DataFrame()
    except ValueError as error:
        if columns:
            raise ValueError('schema適用エラー(列存在チェック): 指定列が存在しません [' + ', '.join(columns) + ']') from error
        raise
    return _Tables.attach_dataframe_schema(frame, schema_override=schema,
        date_serial_system='excel_1900', date_cleansing=_Tables._to_bool_flag(date_cleansing))


def write_csv(data, output_path, *, encoding='utf-8-sig', delimiter=',', schema=None):
    """Write actual table data without an index, overwriting the named file.

    Accept a DataFrame, list of records, or one dict. The caller's data is not
    modified. Return the original connector's completion message.
    """
    path = _path(output_path, 'output_path')
    if data is None:
        raise ValueError('データが空です')
    frame = _Tables.to_dataframe(data)
    if frame.empty:
        raise ValueError('データが空です')
    if schema is not None and str(schema).strip():
        frame = _Tables.apply_schema_to_dataframe(frame, _Tables.parse_schema_definition(schema))
    frame.to_csv(path, index=False, encoding=encoding, sep=_delimiter(delimiter))
    return f'CSV保存完了: {path}'
