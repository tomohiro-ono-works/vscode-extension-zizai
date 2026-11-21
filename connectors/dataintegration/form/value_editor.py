"""Configure ordered value transformations before generating Notebook code."""
from math import isfinite

import ipywidgets as widgets

from .arithmetic_formula import format_column
from ...row_preview import _close_widgets


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
    'formula': ('expression',),
}
FIELD_LABELS = {
    'search': '検索文字列', 'replacement': '置換後の文字列', 'separator': '区切り文字',
    'pattern': '正規表現', 'value': '指定値', 'other_column': '相手列', 'expression': '計算式',
    'position': '取り出す位置', 'group': 'グループ番号（0は一致全体）', 'digits': '小数点以下の桁数',
}
NULL_VALUE_TYPES = {
    'text': '文字列', 'numeric': '数値', 'bool': '真偽値', 'datetime': '日付・日時',
}
NEW_COLUMN = True


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
        self.new_column = widgets.Text(description='新しい列名', layout=widgets.Layout(width='auto'))
        self.new_column.style.description_width = 'initial'
        self.source = _dropdown('入力列', [('選択してください', None)])
        self.source.observe(self._change_source, names='value')
        self.action.observe(self._select_action, names='value')

    def controls(self):
        source = (self.source,) if self._needs_source else ()
        return (self.action, *source, *(widget for name, widget in self.fields.items() if name != 'expression'))

    @property
    def _needs_source(self):
        return self.column.value is NEW_COLUMN and self.action.value not in (None, 'formula')

    def _column_options(self):
        return [('選択してください', None), *((name, name) for name in self._columns)]

    def set_columns(self, columns):
        self._columns = columns

    def select_column(self):
        kind = self._columns.get(self.column.value)
        if self.column.value is NEW_COLUMN:
            actions = {'formula': ACTION_LABELS['formula']}
            for column_kind in dict.fromkeys(self._columns.values()):
                actions.update(VALUE_ACTIONS.get(column_kind, {}))
            if self._columns:
                actions.update(NULL_ACTIONS)
        else:
            actions = {**VALUE_ACTIONS.get(kind, {}), **NULL_ACTIONS} if kind is not None else {}
        options = (('選択してください', None), *((label, key) for key, label in actions.items()))
        if options != self.action.options:
            previous = self.action.value
            self.action.options = options
            self.action.value = previous if previous in actions else None
        self.action.disabled = not actions
        self._sync_source()
        self._change_source(None)

    @staticmethod
    def _sync_options(field, choices):
        if tuple(choices) != field.options:
            previous = field.value
            field.options = choices
            field.value = previous if previous in dict(choices).values() else choices[0][1]

    def _sync_source(self):
        op = self.action.value
        choices = [('選択してください', None)]
        if self._needs_source:
            choices.extend((name, name) for name, kind in self._columns.items()
                           if op in NULL_ACTIONS or op in VALUE_ACTIONS.get(kind, {}))
        self._sync_options(self.source, choices)

    def _change_source(self, _change):
        for name, choices in [('other_column', self._column_options()), ('value_type', self._null_value_options())]:
            if name in self.fields:
                self._sync_options(self.fields[name], choices)
        self._on_layout()

    def _null_value_options(self):
        kind = self._columns.get(self.source.value if self._needs_source else self.column.value)
        types = (kind,) if kind in NULL_VALUE_TYPES else ('text', 'numeric', 'bool')
        return [(NULL_VALUE_TYPES[key], key) for key in types]

    def _select_action(self, _change):
        previous = self.fields
        self._sync_source()
        self.fields = {name: self._make_field(name) for name in ACTION_FIELDS.get(self.action.value, ())}
        self._on_layout()
        _close_widgets(previous.values())

    def _make_field(self, name):
        if name == 'other_column':
            return _dropdown(FIELD_LABELS[name], self._column_options())
        if name == 'value_type':
            options = self._null_value_options()
            return _dropdown('指定値の型', options, value=options[0][1])
        layout = widgets.Layout(width='auto')
        if name in ('position', 'group', 'digits'):
            widget = widgets.IntText(description=FIELD_LABELS[name], value=1 if name == 'position' else 0, layout=layout)
            widget.add_class('zizai-integer')
        elif name == 'expression':
            target = self.column.value
            widget = widgets.Textarea(description=FIELD_LABELS[name], value=format_column(target) if isinstance(target, str) else '',
                                      rows=3, placeholder='数量 * 単価', layout=widgets.Layout(width='100%'))
            widget.add_class('zizai-textarea')
            widget.add_class('zizai-operation-expression')
        else:
            widget = widgets.Text(description=FIELD_LABELS[name], layout=layout,
                                  placeholder='true / false または値' if name == 'value' else '')
        widget.style.description_width = 'initial'
        return widget

    def operation(self):
        op = self.action.value
        if self.column.value is None or op is None:
            raise ValueError('対象列と操作を選択してください。')
        change = {'op': op}
        if self.column.value is NEW_COLUMN:
            change['output'] = self.new_column.value.strip()
            if not change['output']:
                raise ValueError('新しい列名を入力してください。')
            if self._needs_source:
                if self.source.value is None:
                    raise ValueError('入力列を選択してください。')
                change['column'] = self.source.value
        else:
            change['column'] = self.column.value
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
        self.column.value = NEW_COLUMN if 'output' in operation else operation['column']
        self.action.value = action
        self.new_column.value = operation.get('output', '')
        if self._needs_source:
            self.source.value = operation.get('column')
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
        op = change['op']
        target = f'{change["output"]}（新規）' if 'output' in change else change['column']
        details = []
        if 'output' in change and 'column' in change:
            details.append(f'入力列 {change["column"]}')
        for key in ACTION_FIELDS.get(op, ()):
            if key == 'expression':
                details.append(' '.join(line.strip() for line in change[key].splitlines()))
            elif key in FIELD_LABELS and key in change:
                details.append(f'{FIELD_LABELS[key]} {change[key]!r}')
        return target, ACTION_LABELS[op], '、'.join(details)

    def close(self):
        _close_widgets([self.action, self.new_column, self.source, *self.fields.values()])
