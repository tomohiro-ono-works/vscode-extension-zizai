"""Build ordered value transformations with settings above the preview table."""
from html import escape
from math import isfinite

import ipywidgets as widgets

from .column_editor import DataFramePreview
from .row_preview import MAX_ROWS, _close_widgets


VALUE_CATEGORIES = {
    'text': ('文字列', {
        'replace_exact': '置換（完全一致）', 'replace_part': '置換（部分一致）',
        'concat': '列の値を結合', 'split': '区切って取り出す', 'extract_regex': '正規表現で抽出',
        'trim': '前後の空白を除去', 'upper': '大文字に変換', 'lower': '小文字に変換',
    }),
    'null': ('NULL処理', {'to_null': '指定の値をNULLにする', 'fill_null': 'NULLを補完する'}),
    'numeric': ('数値', {
        'add': '足す', 'subtract': '引く', 'multiply': '掛ける', 'divide': '割る',
        'round': '丸める', 'abs': '絶対値にする',
    }),
}
ACTION_LABELS = {action: label for _, actions in VALUE_CATEGORIES.values() for action, label in actions.items()}
ARITHMETIC = {'add', 'subtract', 'multiply', 'divide'}
ACTION_FIELDS = {
    'replace_exact': ('search', 'replacement'),
    'replace_part': ('search', 'replacement'),
    'concat': ('other_column', 'separator'),
    'split': ('separator', 'position'),
    'extract_regex': ('pattern', 'group'),
    'round': ('digits',),
    'to_null': ('value_type', 'value'),
    'fill_null': ('value_type', 'value'),
    **{op: ('operand', 'number', 'other_column') for op in ARITHMETIC},
}
FIELD_LABELS = {
    'search': '検索文字列', 'replacement': '置換後の文字列', 'separator': '区切り文字',
    'pattern': '正規表現', 'value': '指定値', 'number': '固定値', 'other_column': '相手列',
    'position': '取り出す位置', 'group': 'グループ番号（0は一致全体）', 'digits': '小数点以下の桁数',
}


def _dropdown(description, options, *, value=None):
    field = widgets.Dropdown(description=description, options=options, value=value, layout=widgets.Layout(width='auto'))
    field.style.description_width = 'initial'
    return field


def _number(value):
    try:
        text = value.strip()
        result = int(text) if text.lstrip('+-').isdigit() else float(text)
        if type(result) is int or isfinite(result):
            return result
    except (ValueError, OverflowError):
        pass
    raise ValueError('有限の数値を入力してください。')


def _settings_row(children):
    row = widgets.HBox(children, layout=widgets.Layout(flex_flow='row wrap', align_items='flex-end'))
    row.add_class('row-preview-controls')
    return row


class ValueEditor:
    def __init__(self, data, apply_operations, on_change):
        self._apply_operations = apply_operations
        self._on_change = on_change
        self._sample = data.head(MAX_ROWS).copy()
        self.operations = []
        self.preview = apply_operations(self._sample, operations=[])
        self.fields = {}
        self._syncing_columns = False
        self.column = _dropdown('対象列', self._column_options())
        self.category = _dropdown('処理分類', [('選択してください', None)] + [
            (label, key) for key, (label, _) in VALUE_CATEGORIES.items()])
        self.action = _dropdown('操作', [('選択してください', None)])
        self.category.disabled = self.action.disabled = True
        self.selectors = _settings_row([self.column, self.category, self.action])
        self.column.observe(self._select_column, names='value')
        self.category.observe(self._select_category, names='value')
        self.action.observe(self._select_action, names='value')

        self._params = _settings_row([])
        self.output_mode = _dropdown(
            '加工結果', [('対象列を更新', 'existing'), ('新しい列へ出力', 'new')], value='existing')
        self.output_name = widgets.Text(description='新しい列名', layout=widgets.Layout(width='auto', display='none'))
        self.output_name.style.description_width = 'initial'
        self.output_mode.observe(self._toggle_output, names='value')
        self.add = widgets.Button(description='変更を追加', layout=widgets.Layout(width='auto'))
        self.add.on_click(self._add_current)
        self._output = _settings_row([self.output_mode, self.output_name, self.add])
        self._output.layout.display = 'none'
        self.status = widgets.HTML()
        self._table = DataFramePreview()
        self.grid = self._table.root
        self.changes = widgets.HTML()
        self.undo = widgets.Button(description='最後の変更を取り消す', layout=widgets.Layout(width='auto'))
        self.undo.on_click(self._undo_last)
        intro = widgets.HTML(f'<h3>値加工のプレビュー</h3><p>先頭{MAX_ROWS}行</p>')
        self.root = widgets.VBox([intro, self.selectors, self._params, self._output,
                                  self.status, self.grid, self.changes, self.undo])
        self.root.add_class('row-preview')
        self._render()

    def _column_options(self):
        return [('選択してください', None), *((str(column), str(column)) for column in self.preview.columns)]

    def _select_column(self, _change):
        if self._syncing_columns:
            return
        self.category.disabled = self.column.value is None
        if self.category.disabled:
            self.category.value = None
        self.status.value = ''

    def _select_category(self, _change):
        choice = self.category.value
        choices = VALUE_CATEGORIES[choice][1] if choice else {}
        self.action.value = None
        self.action.options = [('選択してください', None), *((label, key) for key, label in choices.items())]
        self.action.disabled = not choices

    def _select_action(self, _change):
        self._params.children = ()
        _close_widgets(self.fields.values())
        self.fields = {}
        self.status.value = ''
        self._output.layout.display = '' if self.action.value else 'none'
        for name in ACTION_FIELDS.get(self.action.value, ()):
            self.fields[name] = self._make_field(name)
        self._params.children = tuple(self.fields.values())
        if 'operand' in self.fields:
            self.fields['operand'].observe(self._toggle_operand, names='value')
            self._toggle_operand(None)

    def _make_field(self, name):
        if name == 'operand':
            return _dropdown('計算相手', [('固定値', 'number'), ('別の列', 'other_column')], value='number')
        if name == 'other_column':
            return _dropdown(FIELD_LABELS[name], self._column_options())
        if name == 'value_type':
            return _dropdown('指定値の型', [('文字列', 'text'), ('数値', 'number'), ('真偽値', 'bool')], value='text')
        layout = widgets.Layout(width='auto')
        if name in ('position', 'group', 'digits'):
            widget = widgets.IntText(description=FIELD_LABELS[name], value=1 if name == 'position' else 0, layout=layout)
            widget.add_class('zizai-integer')
        else:
            widget = widgets.Text(description=FIELD_LABELS[name], layout=layout,
                                  placeholder='true / false または値' if name == 'value' else '')
        widget.style.description_width = 'initial'
        return widget

    def _toggle_operand(self, _change):
        chosen = self.fields['operand'].value
        for name in ('number', 'other_column'):
            self.fields[name].layout.display = '' if chosen == name else 'none'

    def _toggle_output(self, _change):
        self.output_name.layout.display = '' if self.output_mode.value == 'new' else 'none'

    def _operation(self):
        op = self.action.value
        change = {'op': op, 'column': self.column.value}
        if self.output_mode.value == 'new':
            change['output'] = self.output_name.value
        if op in ARITHMETIC:
            key = self.fields['operand'].value
            value = self.fields[key].value
            change[key] = _number(value) if key == 'number' else value
        elif 'value_type' in self.fields:
            kind = self.fields['value_type'].value
            value = self.fields['value'].value
            if kind == 'number':
                value = _number(value)
            elif kind == 'bool':
                normalized = value.strip().lower()
                if normalized not in ('true', 'false'):
                    raise ValueError('真偽値には true または false を入力してください。')
                value = normalized == 'true'
            change['value'] = value
        else:
            change.update((key, widget.value) for key, widget in self.fields.items())
        return change

    def _add_current(self, _button):
        if self.column.value is None or self.action.value is None:
            return
        try:
            operations = [*self.operations, self._operation()]
            self._update(operations)
        except ValueError as error:
            self.status.value = f'<p role="alert">{escape(str(error))}</p>'

    def _undo_last(self, _button):
        if self.operations:
            self._update(self.operations[:-1])

    def _update(self, operations):
        preview = self._apply_operations(self._sample, operations=operations)
        self.preview, self.operations = preview, operations
        self.status.value = ''
        self._render()
        self._on_change(operations)

    def _render(self):
        column_options = self._column_options()
        if tuple(column_options) != self.column.options:
            previous = self.column.value
            self._syncing_columns = True
            try:
                self.column.options = column_options
                self.column.value = previous if previous in dict(column_options).values() else None
            finally:
                self._syncing_columns = False
            self._select_column(None)
        if 'other_column' in self.fields:
            field = self.fields['other_column']
            if field.options != tuple(column_options):
                previous = field.value
                field.options = column_options
                field.value = previous if previous in dict(column_options).values() else None
        self._table.render(self.preview)
        self.undo.disabled = not self.operations
        entries = []
        for change in self.operations:
            label = f'{change["column"]}　{ACTION_LABELS[change["op"]]}'
            if 'output' in change:
                label += f' → {change["output"]}'
            entries.append(f'<li>{escape(label)}</li>')
        self.changes.value = '<h3>変更一覧</h3>' + (f'<ol>{"".join(entries)}</ol>' if entries else
                                                '<p>設定した加工はここに表示します。</p>')

    def close(self):
        self._table.close()
        _close_widgets([*self.fields.values(), self.column, self.category, self.action, self.output_mode,
                        self.output_name, self.add, *(child for child in self.root.children if child is not self.grid),
                        self.root])
