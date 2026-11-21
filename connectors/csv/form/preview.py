"""Read a bounded CSV sample for the row selection form."""
import csv
from itertools import islice


def read_preview_rows(path, settings, *, max_rows, max_cols):
    delimiter = settings['delimiter'] or ','
    if delimiter in (r'\t', 'tab', 'TAB'):
        delimiter = '\t'
    encoding = settings['encoding']
    with path.open(encoding='utf-8-sig' if encoding == 'utf-8' else encoding, newline='') as handle:
        return [row[:max_cols] for row in islice(csv.reader(handle, delimiter=delimiter), max_rows)]
