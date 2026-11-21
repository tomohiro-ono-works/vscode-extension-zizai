"""Configure ordered value transformations before generating Notebook code."""
from math import isfinite

import ipywidgets as widgets

from .row_preview import _close_widgets


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


def _operation_form(button):
    fields = widgets.HBox(layout=widgets.Layout(
        flex='1 1 0', min_width='0', flex_flow='row nowrap', overflow='auto', align_items='flex-end'))
    fields.add_class('zizai-operation-fields')
    button.layout.flex = '0 0 auto'
    row = widgets.HBox([fields, button], layout=widgets.Layout(width='100%', align_items='flex-end'))
    row.add_class('zizai-operation-form')
    return row, fields


class ValueFields:
    def __init__(self, on_layout):
        self._on_layout = on_layout
        self._columns = []
        self._syncing_columns = False
        self.fields = {}
        self.column = _dropdown('対象列', self._column_options())
        self.category = _dropdown('加工種別', [('選択してください', None)] + [
            (label, key) for key, (label, _) in VALUE_CATEGORIES.items()])
        self.action = _dropdown('操作', [('選択してください', None)])
        self.category.disabled = self.action.disabled = True
        self.output_mode = _dropdown(
            '加工結果', [('対象列を更新', 'existing'), ('新しい列へ出力', 'new')], value='existing')
        self.output_mode.layout.display = 'none'
        self.output_name = widgets.Text(description='新しい列名', layout=widgets.Layout(width='auto', display='none'))
        self.output_name.style.description_width = 'initial'
        self.column.observe(self._select_column, names='value')
        self.category.observe(self._select_category, names='value')
        self.action.observe(self._select_action, names='value')
        self.output_mode.observe(self._toggle_output, names='value')

    def controls(self):
        return (self.column, self.category, self.action, *self.fields.values(), self.output_mode, self.output_name)

    def _column_options(self):
        return [('選択してください', None), *((name, name) for name in self._columns)]

    def set_columns(self, names):
        if self._columns == names:
            return
        self._columns = names
        previous = self.column.value
        self._syncing_columns = True
        try:
            self.column.options = self._column_options()
            self.column.value = previous if previous in names else None
        finally:
            self._syncing_columns = False
        self._select_column(None)
        if 'other_column' in self.fields:
            field = self.fields['other_column']
            previous = field.value
            field.options = self._column_options()
            field.value = previous if previous in names else None

    def _select_column(self, _change):
        if self._syncing_columns:
            return
        self.category.disabled = self.column.value is None
        if self.category.disabled:
            self.category.value = None
        self._on_layout()

    def _select_category(self, _change):
        choice = self.category.value
        choices = VALUE_CATEGORIES[choice][1] if choice else {}
        self.action.value = None
        self.action.options = [('選択してください', None), *((label, key) for key, label in choices.items())]
        self.action.disabled = not choices

    def _select_action(self, _change):
        previous = self.fields
        self.fields = {name: self._make_field(name) for name in ACTION_FIELDS.get(self.action.value, ())}
        self.output_mode.layout.display = '' if self.action.value else 'none'
        self._toggle_output(None)
        if 'operand' in self.fields:
            self.fields['operand'].observe(self._toggle_operand, names='value')
            self._toggle_operand(None)
        self._on_layout()
        _close_widgets(previous.values())

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
        self.output_name.layout.display = '' if self.action.value and self.output_mode.value == 'new' else 'none'

    def operation(self):
        op = self.action.value
        if self.column.value is None or op is None:
            raise ValueError('対象列と操作を選択してください。')
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

    def load(self, operation):
        action = operation['op']
        self.column.value = operation['column']
        self.category.value = next(key for key, (_, ops) in VALUE_CATEGORIES.items() if action in ops)
        self.action.value = action
        self.output_mode.value = 'new' if 'output' in operation else 'existing'
        self.output_name.value = operation.get('output', '')
        if 'operand' in self.fields:
            self.fields['operand'].value = 'other_column' if 'other_column' in operation else 'number'
        if 'value_type' in self.fields:
            raw = operation.get('value')
            self.fields['value_type'].value = 'bool' if type(raw) is bool else 'number' if type(raw) in (int, float) else 'text'
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
