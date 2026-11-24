"""Read a bounded CSV sample for the row selection form."""
import csv
from itertools import islice


def read_preview_rows(path, settings, *, max_rows, max_cols):
    delimiter = settings['delimiter'] or ','
    if delimiter in (r'\t', 'tab', 'TAB'):
        delimiter = '\t'
    encoding = settings['encoding']
    if encoding is None:
        raise ValueError('文字コードを選択してください。')
    with path.open(encoding='utf-8-sig' if encoding == 'utf-8' else encoding, newline='') as handle:
        return [row[:max_cols] for row in islice(csv.reader(handle, delimiter=delimiter), max_rows)]


def make_settings(widgets, path, fields):
    encoding = fields['encoding']
    return {
        'encoding': widgets.Dropdown(description='文字コード', options=encoding.options, value=encoding.value),
        'delimiter': widgets.Text(description='区切り文字', value=fields['delimiter'].value, continuous_update=False),
    }


def row_selection_error(rows, start):
    if any(not row or (len(row) == 1 and not row[0].strip()) for row in rows[:start]):
        return 'CSVの空行で読み込み時と行番号がずれる場合があります。フォームで行番号を直接指定してください。'
    return ''
