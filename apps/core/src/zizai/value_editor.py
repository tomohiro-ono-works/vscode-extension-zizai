"""Configure ordered value transformations before generating Notebook code."""
from math import isfinite

import ipywidgets as widgets

from .arithmetic_formula import format_column
from .row_preview import _close_widgets


VALUE_ACTIONS = {
    'text': {
        'replace_exact': '置換（完全一致）', 'replace_part': '置換（部分一致）',
        'concat': '列の値を結合', 'split': '区切って取り出す', 'extract_regex': '正規表現で抽出',
        'trim': '前後の空白を除去', 'upper': '大文字に変換', 'lower': '小文字に変換',
    },
    'numeric': {'formula': '計算式', 'round': '丸める', 'abs': '絶対値にする'},
}
NULL_ACTIONS = {'to_null': '指定の値をNULLにする', 'fill_null': 'NULLを補完する'}
ACTION_LABELS = {**VALUE_ACTIONS['text'], **VALUE_ACTIONS['numeric'], **NULL_ACTIONS}
ACTION_FIELDS = {
    'replace_exact': ('search', 'replacement'),
    'replace_part': ('search', 'replacement'),
    'concat': ('other_column', 'separator'),
    'split': ('separator', 'position'),
    'extract_regex': ('pattern', 'group'),
    'round': ('digits',),
    'to_null': ('value_type', 'value'),
    'fill_null': ('value_type', 'value'),
    'formula': ('expression', 'formula_column'),
}
FIELD_LABELS = {
    'search': '検索文字列', 'replacement': '置換後の文字列', 'separator': '区切り文字',
    'pattern': '正規表現', 'value': '指定値', 'other_column': '相手列', 'expression': '計算式',
    'position': '取り出す位置', 'group': 'グループ番号（0は一致全体）', 'digits': '小数点以下の桁数',
}
NULL_VALUE_TYPES = {
    'text': '文字列', 'numeric': '数値', 'bool': '真偽値', 'datetime': '日付・日時',
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


def _operation_form(button):
    fields = widgets.HBox(layout=widgets.Layout(
        flex='1 1 0', min_width='0', flex_flow='row nowrap', overflow='auto', align_items='flex-end'))
    fields.add_class('zizai-operation-fields')
    button.layout.flex = '0 0 auto'
    row = widgets.HBox([fields, button], layout=widgets.Layout(width='100%', align_items='flex-end'))
    row.add_class('zizai-operation-form')
    return row, fields


class ValueFields:
    def __init__(self, column, on_layout):
        self._on_layout = on_layout
        self._columns = {}
        self.fields = {}
        self.column = column
        self.action = _dropdown('操作', [('選択してください', None)])
        self.action.disabled = True
        self.output_mode = _dropdown(
            '加工結果', [('対象列を更新', 'existing'), ('新しい列へ出力', 'new')], value='existing')
        self.output_mode.layout.display = 'none'
        self.output_name = widgets.Text(description='新しい列名', layout=widgets.Layout(width='auto', display='none'))
        self.output_name.style.description_width = 'initial'
        self.action.observe(self._select_action, names='value')
        self.output_mode.observe(self._toggle_output, names='value')

    def controls(self):
        return (self.action, *self.fields.values(), self.output_mode, self.output_name)

    def _column_options(self, *, numeric=False):
        return [('選択してください', None), *((name, name) for name, kind in self._columns.items()
                                          if not numeric or kind == 'numeric')]

    def set_columns(self, columns):
        self._columns = columns

    def select_column(self):
        kind = self._columns.get(self.column.value)
        actions = {**VALUE_ACTIONS.get(kind, {}), **NULL_ACTIONS} if kind is not None else {}
        options = (('選択してください', None), *((label, key) for key, label in actions.items()))
        if options != self.action.options:
            previous = self.action.value
            self.action.options = options
            self.action.value = previous if previous in actions else None
        self.action.disabled = not actions
        for name, choices in [('other_column', self._column_options()),
                              ('formula_column', self._column_options(numeric=True)),
                              ('value_type', self._null_value_options())]:
            if name in self.fields:
                field = self.fields[name]
                if tuple(choices) != field.options:
                    previous = field.value
                    field.options = choices
                    field.value = previous if previous in dict(choices).values() else choices[0][1]
        self._on_layout()

    def _null_value_options(self):
        kind = self._columns.get(self.column.value)
        types = (kind,) if kind in NULL_VALUE_TYPES else ('text', 'numeric', 'bool')
        return [(NULL_VALUE_TYPES[key], key) for key in types]

    def _select_action(self, _change):
        previous = self.fields
        self.fields = {name: self._make_field(name) for name in ACTION_FIELDS.get(self.action.value, ())}
        self.output_mode.layout.display = '' if self.action.value else 'none'
        self._toggle_output(None)
        if 'formula_column' in self.fields:
            self.fields['formula_column'].observe(self._insert_formula_column, names='value')
        self._on_layout()
        _close_widgets(previous.values())

    def _make_field(self, name):
        if name == 'other_column':
            return _dropdown(FIELD_LABELS[name], self._column_options())
        if name == 'formula_column':
            return _dropdown('列を式に追加', self._column_options(numeric=True))
        if name == 'value_type':
            options = self._null_value_options()
            return _dropdown('指定値の型', options, value=options[0][1])
        layout = widgets.Layout(width='auto')
        if name in ('position', 'group', 'digits'):
            widget = widgets.IntText(description=FIELD_LABELS[name], value=1 if name == 'position' else 0, layout=layout)
            widget.add_class('zizai-integer')
        elif name == 'expression':
            widget = widgets.Text(description=FIELD_LABELS[name], value=format_column(self.column.value),
                                  placeholder='数量 * 単価', layout=widgets.Layout(width='240px'))
        else:
            widget = widgets.Text(description=FIELD_LABELS[name], layout=layout,
                                  placeholder='true / false または値' if name == 'value' else '')
        widget.style.description_width = 'initial'
        return widget

    def _insert_formula_column(self, change):
        if change['new'] is not None:
            expression = self.fields['expression']
            expression.value = f"{expression.value.rstrip()} {format_column(change['new'])}".lstrip()
            change['owner'].value = None

    def _toggle_output(self, _change):
        self.output_name.layout.display = '' if self.action.value and self.output_mode.value == 'new' else 'none'

    def operation(self):
        op = self.action.value
        if self.column.value is None or op is None:
            raise ValueError('対象列と操作を選択してください。')
        change = {'op': op, 'column': self.column.value}
        if self.output_mode.value == 'new':
            change['output'] = self.output_name.value
        if op == 'formula':
            change['expression'] = self.fields['expression'].value.strip()
        elif 'value_type' in self.fields:
            kind = self.fields['value_type'].value
            value = self.fields['value'].value
            if kind == 'numeric':
                value = _number(value)
            elif kind == 'bool':
                normalized = value.strip().lower()
                if normalized not in ('true', 'false'):
                    raise ValueError('真偽値には true または false を入力してください。')
                value = normalized == 'true'
            elif kind == 'datetime':
                change['value_type'] = 'datetime'
            change['value'] = value
        else:
            change.update((key, widget.value) for key, widget in self.fields.items())
        return change

    def load(self, operation):
        action = operation['op']
        self.column.value = operation['column']
        self.action.value = action
        self.output_mode.value = 'new' if 'output' in operation else 'existing'
        self.output_name.value = operation.get('output', '')
        if 'value_type' in self.fields:
            raw = operation.get('value')
            kind = operation.get('value_type') or (
                'bool' if type(raw) is bool else 'numeric' if type(raw) in (int, float) else 'text')
            if kind in dict(self.fields['value_type'].options).values():
                self.fields['value_type'].value = kind
        for name, widget in self.fields.items():
            if name in operation:
                widget.value = str(operation[name]) if isinstance(widget, widgets.Text) else operation[name]

    @staticmethod
    def describe(change):
        label = f'{change["column"]}　{ACTION_LABELS[change["op"]]}'
        if 'output' in change:
            label += f' → {change["output"]}'
        details = [f'{FIELD_LABELS[key]} {value!r}' for key, value in change.items() if key in FIELD_LABELS]
        return label + ('　' + '、'.join(details) if details else '')

    def close(self):
        _close_widgets(self.controls())
