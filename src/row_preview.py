"""Bounded CSV and Excel previews for selecting rows in the notebook form."""
import csv
from html import escape
from itertools import islice
from string import ascii_uppercase
from zipfile import BadZipFile

import ipywidgets as w
from traitlets import Unicode
from .form_definition import valid_value


MAX_ROWS = 30
MAX_COLS = 40
ROW_NUMBER_WIDTH = 114
CELL_WIDTH = 138
COLUMN_LABELS = (*ascii_uppercase, *('A' + letter for letter in ascii_uppercase))


def _preview_rows(path, connector, settings):
    if connector == 'csv':
        delimiter = settings['delimiter'] or ','
        if delimiter in (r'\t', 'tab', 'TAB'):
            delimiter = '\t'
        encoding = settings['encoding']
        with path.open(encoding='utf-8-sig' if encoding == 'utf-8' else encoding, newline='') as handle:
            return [row[:MAX_COLS] for row in islice(csv.reader(handle, delimiter=delimiter), MAX_ROWS)]
    from openpyxl import load_workbook
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook[settings['sheet_name']]
        return list(sheet.iter_rows(max_row=min(sheet.max_row or MAX_ROWS, MAX_ROWS),
                                    max_col=min(sheet.max_column or MAX_COLS, MAX_COLS), values_only=True))
    finally:
        workbook.close()


def _sheet_names(path):
    from openpyxl import load_workbook
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        return workbook.sheetnames
    finally:
        workbook.close()


def _close_widgets(widgets):
    for widget in widgets:
        widget.close()
        widget.layout.close()
        if hasattr(widget, 'style'):
            widget.style.close()


class RowNumber(w.Button):
    _view_name = Unicode('RowContextView').tag(sync=True)
    _view_module = Unicode('zizai-row-preview').tag(sync=True)
    _view_module_version = Unicode('1.0.0').tag(sync=True)


class RowPreview:
    def __init__(self, form, path):
        self.form = form
        self.path = path
        self.connector = form.model.connector
        self.rows = []
        self.table_rows = []
        self.row_buttons = []
        self.grid_widgets = []
        fields = form.field_widgets
        self.picks = {name: fields[name].value for name in ('header_row', 'data_start_row')}
        self.settings = self._make_settings(fields)
        self.grid = w.VBox(layout=w.Layout(width='100%', max_height='310px', overflow='auto'))
        self.grid.add_class('row-preview-grid')
        self.summary = w.HTML()
        self.summary.add_class('row-preview-summary')
        self.status = w.HTML()
        self.confirm = w.Button(description='確定')
        self.confirm.on_click(self._apply)
        self.cancel = w.Button(description='キャンセル')
        self.cancel.add_class('row-preview-cancel')
        self.cancel.on_click(lambda _: form._dismiss_row_preview())
        footer = w.HBox([self.summary, self.cancel, self.confirm],
                        layout=w.Layout(flex_flow='row wrap', align_items='center', justify_content='space-between'))
        footer.add_class('row-preview-footer')
        controls = w.HBox(list(self.settings.values()), layout=w.Layout(flex_flow='row wrap'))
        controls.add_class('row-preview-controls')
        intro = w.HTML(f'<h3>行のプレビュー</h3><p>{escape(path.name)} · 先頭{MAX_ROWS}行、最大{MAX_COLS}列</p>')
        help_text = w.HTML('<p>左端の行番号を右クリックして指定します。</p>')
        self.root = w.VBox([intro, controls, help_text, self.status, self.grid, footer])
        self.root.add_class('row-preview')
        for setting in self.settings.values():
            setting.observe(self._render_table, names='value')
        self._render_table()

    def _make_settings(self, fields):
        if self.connector == 'csv':
            encoding = fields['encoding']
            return {
                'encoding': w.Dropdown(description='文字コード', options=encoding.options,
                                       value=encoding.value),
                'delimiter': w.Text(description='区切り文字', value=fields['delimiter'].value,
                                    continuous_update=False),
            }
        sheets = _sheet_names(self.path)
        current = fields['sheet_name'].value
        return {'sheet_name': w.Dropdown(description='シート', options=sheets,
                                        value=current if current in sheets else sheets[0])}

    def _render_table(self, _change=None):
        self.grid.children = ()
        _close_widgets(self.grid_widgets)
        self.grid_widgets = []
        self.table_rows = []
        self.row_buttons = []
        self.rows = []
        try:
            settings = {name: widget.value for name, widget in self.settings.items()}
            if self.connector == 'csv' and settings['encoding'] is None:
                raise ValueError('文字コードを選択してください。')
            self.rows = _preview_rows(self.path, self.connector, settings)
        except (OSError, ValueError, LookupError, TypeError, csv.Error, BadZipFile) as error:
            self.status.value = f'<p role="alert">{escape(str(error))}</p>'
            self._update_picks()
            return

        width = max(1, max(map(len, self.rows), default=0))
        columns = [w.HTML('行', layout=w.Layout(flex=f'0 0 {ROW_NUMBER_WIDTH}px'))]
        columns.extend(w.HTML(label, layout=w.Layout(flex=f'1 0 {CELL_WIDTH}px')) for label in COLUMN_LABELS[:width])
        columns[0].add_class('row-preview-first')
        minimum_width = f'{ROW_NUMBER_WIDTH + CELL_WIDTH * width}px'
        heading = w.HBox(columns, layout=w.Layout(width='100%', min_width=minimum_width, overflow='visible'))
        heading.add_class('row-preview-heading')
        self.grid_widgets.extend([*columns, heading])
        for number, values in enumerate(self.rows, 1):
            count = RowNumber(description=f'{number}行目',
                              layout=w.Layout(flex=f'0 0 {ROW_NUMBER_WIDTH}px', width=f'{ROW_NUMBER_WIDTH}px'))
            count.add_class('row-preview-first')
            count.on_msg(lambda _, message, buffers, row=number: self._choose_role(row, message))
            self.row_buttons.append(count)
            values_html = []
            for index in range(width):
                value = values[index] if index < len(values) else None
                label = escape('' if value is None else str(value))
                values_html.append(f'<span class="row-preview-value" title="{label}">{label}</span>')
            cells = w.HTML('<div class="row-preview-values-line">' + ''.join(values_html) + '</div>',
                           layout=w.Layout(flex='1 0 0', min_width=f'{CELL_WIDTH * width}px'))
            row = w.HBox([count, cells], layout=w.Layout(width='100%', min_width=minimum_width, overflow='visible'))
            self.table_rows.append(row)
            self.grid_widgets.extend([count, cells, row])
        self.grid.children = (heading, *self.table_rows)
        self.status.value = '' if self.rows else '<p>表示できる行がありません。</p>'
        self._update_picks()

    def _choose_role(self, row, message):
        role = message.get('role')
        if (self.form._row_preview is self and message.get('event') == 'row-role'
                and isinstance(role, str) and role in self.picks and 1 <= row <= len(self.rows)):
            self.picks[role] = row
            self._update_picks()

    def _update_picks(self):
        header, start = (self.picks[name] for name in ('header_row', 'data_start_row'))
        for number, (row, button) in enumerate(zip(self.table_rows, self.row_buttons), 1):
            labels = []
            if number == header:
                labels.append('ヘッダー')
            if number == start:
                labels.append('開始')
            button.description = f'{number}行目'
            if labels:
                button.description += ' · ' + '／'.join(labels)
            if labels:
                row.add_class('row-preview-picked')
            else:
                row.remove_class('row-preview-picked')
        message = ''
        if self.rows and not 1 <= header <= start <= len(self.rows):
            message = '表示範囲で、データ開始行をヘッダー行以降に指定してください。'
        elif self.connector == 'csv' and any(
            not row or (len(row) == 1 and not row[0].strip()) for row in self.rows[:start]
        ):
            message = 'CSVの空行で読み込み時と行番号がずれる場合があります。フォームで行番号を直接指定してください。'
        self.confirm.disabled = not self.rows or bool(message)
        detail = f'<br><small>{message}</small>' if message else ''
        self.summary.value = f'<p>ヘッダー行 {header} ／ データ開始行 {start}{detail}</p>'

    def _apply(self, _):
        if self.form._row_preview is not self or self.confirm.disabled:
            return
        values = self.picks | {name: widget.value for name, widget in self.settings.items()}
        for name, value in values.items():
            field = self.form.model.fields[name]
            if not valid_value(field, value, require=True):
                self.status.value = f'<p role="alert">{escape(field["label"])}を確認してください。</p>'
                return
        for name, value in values.items():
            self.form.field_widgets[name].value = value
        self.form._dismiss_row_preview()

    def close(self):
        _close_widgets([*self.grid_widgets, *self.settings.values(), self.summary,
                        self.confirm, self.cancel, *self.root.children, self.root])
