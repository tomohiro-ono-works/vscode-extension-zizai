"""XLSX connector adapted from ZizAI 64a1be1 apps/connectors/excel_connector.py."""
from datetime import date, datetime
from itertools import islice
from pathlib import Path
import shutil
import tempfile

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries
from openpyxl.utils.datetime import CALENDAR_MAC_1904
from zizai.core.tabular import TabularOperations


DEFAULT_CHUNK_SIZE = 50000


def _workbook_path(path):
    result = Path(path)
    if result.suffix.lower() != '.xlsx':
        raise ValueError('Excelファイルには .xlsx を指定してください。')
    return result


def _normalize_value(value):
    if isinstance(value, datetime):
        text = value.replace(tzinfo=None).isoformat()
        return text[:10] if text.endswith('T00:00:00') else text
    return value.isoformat() if isinstance(value, date) else value


def _file_version(path):
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_ino, stat.st_size, stat.st_mtime_ns


def _read_table(file_path, sheet_name, header_row, data_start_row, schema, date_cleansing,
                *, bounds=None, chunk_size=DEFAULT_CHUNK_SIZE):
    if header_row < 1 or data_start_row < header_row:
        raise ValueError('ヘッダー行は1以上、データ開始行はヘッダー行以上で指定してください。')
    workbook = load_workbook(_workbook_path(file_path), read_only=True, data_only=True, keep_links=False)
    try:
        if sheet_name and sheet_name not in workbook.sheetnames:
            raise ValueError(f'シートが見つかりません: {sheet_name}')
        worksheet = workbook[sheet_name] if sheet_name else workbook.active
        rows = worksheet.iter_rows(values_only=True, **(bounds or {}))
        header = next(islice(rows, header_row - 1, None), None)
        if header is None:
            raise ValueError('ヘッダー行が読込範囲を超えています。')
        headers = [str(value) if value not in (None, '') else f'col_{index}'
                   for index, value in enumerate(header)]
        # Match the legacy range operation when both positions explicitly refer to the header.
        records = [[_normalize_value(value) for value in header]] if bounds and data_start_row == header_row else []
        chunks = []
        for row in islice(rows, max(0, data_start_row - header_row - 1), None):
            if any(value not in (None, '') for value in row):
                records.append([_normalize_value(value) for value in row])
            if len(records) == chunk_size:
                chunks.append(pd.DataFrame.from_records(records, columns=headers))
                records.clear()
        if records or not chunks:
            chunks.append(pd.DataFrame.from_records(records, columns=headers))
        frame = pd.concat(chunks, ignore_index=True) if len(chunks) > 1 else chunks[0]
        date_system = 'excel_1904' if workbook.epoch == CALENDAR_MAC_1904 else 'excel_1900'
        return TabularOperations.attach_dataframe_schema(frame, schema_override=schema,
                                                        date_serial_system=date_system,
                                                        date_cleansing=date_cleansing)
    finally:
        workbook.close()


def read_excel(file_path, *, sheet_name='シート1', header_row=1, data_start_row=2,
               chunk_size=DEFAULT_CHUNK_SIZE, schema=None, date_cleansing=True):
    """Read a worksheet into a DataFrame using one-based worksheet row numbers."""
    if chunk_size < 1:
        raise ValueError('分割行数は1以上で指定してください。')
    return _read_table(file_path, sheet_name, header_row, data_start_row, schema, date_cleansing,
                       chunk_size=chunk_size)


def read_excel_range(file_path, *, cell_range, sheet_name='シート1', header_row=1, data_start_row=2,
                     schema=None, date_cleansing=True):
    """Read an A1 range into a DataFrame using one-based positions inside the range."""
    left, top, right, bottom = range_boundaries(cell_range)
    if None in (left, top, right, bottom) or not (1 <= left <= right <= 16384 and 1 <= top <= bottom <= 1048576):
        raise ValueError('読込範囲は A1:D100 のように指定してください。')
    if data_start_row > bottom - top + 2:
        raise ValueError('データ開始行が読込範囲を超えています。')
    bounds = {'min_col': left, 'min_row': top, 'max_col': right, 'max_row': bottom}
    return _read_table(file_path, sheet_name, header_row, data_start_row, schema, date_cleansing, bounds=bounds)


def write_excel(data, output_path, *, sheet_name='シート1', mode='create_or_replace', schema=None):
    """Write a table, replacing or appending to the named sheet of an XLSX file."""
    path = _workbook_path(output_path).resolve()
    if mode not in ('create_or_replace', 'create_or_insert'):
        raise ValueError('書き込みモードは対象シートの置換または末尾追記を指定してください。')
    if not isinstance(sheet_name, str) or not sheet_name.strip() or len(sheet_name) > 31:
        raise ValueError('シート名は1～31文字で指定してください。')
    if any(character in sheet_name for character in r'\/*?:[]'):
        raise ValueError('シート名に使用できない文字が含まれています。')
    if data is None:
        raise ValueError('データが空です。')
    frame = TabularOperations.to_dataframe(data)
    if schema is not None and str(schema).strip():
        frame = TabularOperations.apply_schema_to_dataframe(frame, TabularOperations.parse_schema_definition(schema))
    if frame.empty:
        raise ValueError('データが空です。')

    original_version = _file_version(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.xlsx', delete=False) as stream:
        staged = Path(stream.name)
    try:
        writer_options = {}
        if original_version is not None:
            shutil.copy2(path, staged)
            writer_options = {'mode': 'a', 'if_sheet_exists': 'replace' if mode == 'create_or_replace' else 'overlay'}
        with pd.ExcelWriter(staged, engine='openpyxl', **writer_options) as writer:
            sheet_name = next((name for name in writer.sheets if name.casefold() == sheet_name.casefold()), sheet_name)
            append = mode == 'create_or_insert' and sheet_name in writer.sheets
            first_row = writer.sheets[sheet_name].max_row if append else 0
            frame.to_excel(writer, sheet_name=sheet_name, index=False, startrow=first_row, header=not append)
            # A string supplied as table data must not become an executable Excel formula.
            worksheet = writer.sheets[sheet_name]
            for row in worksheet.iter_rows(min_row=first_row + 1, max_row=first_row + len(frame) + int(not append),
                                           max_col=len(frame.columns)):
                for cell in row:
                    if cell.data_type == 'f':
                        cell.data_type = 's'
        if _file_version(path) != original_version:
            raise FileExistsError('書き出し中に保存先が変更されました。')
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)
    return f'Excel保存完了 [{mode}]: {path.as_posix()} (Sheet: {sheet_name})'
