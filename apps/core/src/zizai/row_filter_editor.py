"""Configure ordered row conditions and cleanup before generating Notebook code."""
import ipywidgets as widgets

from .row_preview import _close_widgets
from .value_editor import _dropdown, _number


OP_LABELS = {
    'keep': '条件に合う行だけ残す', 'exclude': '条件に合う行を除外',
    'drop_duplicates': '重複行を削除', 'drop_nulls': 'NULLを含む行を削除',
    'head': '先頭から指定行数を残す', 'tail': '末尾から指定行数を残す',
}
COMPARISONS = {
    'text_equal': '文字列が一致する', 'contains': '文字列を含む',
    'number_equal': '数値が等しい', 'greater': 'より大きい', 'greater_equal': '以上',
    'less': 'より小さい', 'less_equal': '以下', 'between': '数値が範囲内',
    'is_null': 'NULLである', 'not_null': 'NULLでない',
}
NULL_COMPARISONS = {'is_null', 'not_null'}
TEXT_COMPARISONS = {'text_equal', 'contains'}
CONDITIONAL = {'keep', 'exclude'}


class RowFields:
    def __init__(self, on_layout):
        self._on_layout = on_layout
        self._columns = []
        self._previous = {}
        self.action = _dropdown('操作', [('選択してください', None), *((label, key) for key, label in OP_LABELS.items())])
        self.logic = _dropdown('結合', [('AND', 'and'), ('OR', 'or'), ('新しいグループ', 'new')], value='and')
        self.column = _dropdown('対象列', [('選択してください', None)])
        self.comparison = _dropdown('比較', [('選択してください', None), *((label, key) for key, label in COMPARISONS.items())])
        self.value = widgets.Text(description='比較値', layout=widgets.Layout(width='auto'))
        self.upper = widgets.Text(description='上限', layout=widgets.Layout(width='auto'))
        self.subset = widgets.SelectMultiple(description='判定列（未選択は全列）', rows=3,
                                             layout=widgets.Layout(width='auto'))
        self.count = widgets.IntText(description='行数', value=1, layout=widgets.Layout(width='auto'))
        self.count.add_class('zizai-integer')
        for control in (self.value, self.upper, self.subset, self.count):
            control.style.description_width = 'initial'
        self.action.observe(self._changed, names='value')
        self.comparison.observe(self._changed, names='value')
        self._show_fields()

    def controls(self):
        return (self.action, self.logic, self.column, self.comparison, self.value, self.upper, self.subset, self.count)

    def set_columns(self, names):
        if names == self._columns:
            return
        self._columns = names
        column, subset = self.column.value, self.subset.value
        self.column.options = [('選択してください', None), *((name, name) for name in names)]
        self.column.value = column if column in names else None
        self.subset.options = names
        self.subset.value = tuple(name for name in subset if name in names)

    def set_previous(self, previous):
        self._previous = previous
        self._show_fields()

    @staticmethod
    def can_join(previous, mode):
        return mode in CONDITIONAL and previous.get('op') == 'condition' and previous.get('mode') == mode

    def _changed(self, _change):
        self._show_fields()
        self._on_layout()

    def _show_fields(self):
        action, comparison = self.action.value, self.comparison.value
        conditional = action in CONDITIONAL
        self.logic.layout.display = '' if self.can_join(self._previous, action) else 'none'
        self.column.layout.display = self.comparison.layout.display = '' if conditional else 'none'
        self.value.layout.display = '' if conditional and comparison and comparison not in NULL_COMPARISONS else 'none'
        self.value.description = '下限' if comparison == 'between' else '比較値'
        self.upper.layout.display = '' if conditional and comparison == 'between' else 'none'
        self.subset.layout.display = '' if action in ('drop_duplicates', 'drop_nulls') else 'none'
        self.count.layout.display = '' if action in ('head', 'tail') else 'none'

    def operation(self):
        action = self.action.value
        if action in CONDITIONAL:
            column, comparison = self.column.value, self.comparison.value
            if column is None or comparison is None:
                raise ValueError('対象列と比較方法を選択してください。')
            rule = {'column': column, 'comparison': comparison}
            if comparison not in NULL_COMPARISONS:
                rule['value'] = self.value.value if comparison in TEXT_COMPARISONS else _number(self.value.value)
            if comparison == 'between':
                rule['upper'] = _number(self.upper.value)
            if self.can_join(self._previous, action) and self.logic.value != 'new':
                rule['logic'] = self.logic.value
            return {'op': 'condition', 'mode': action, 'condition': rule}
        if action in ('head', 'tail'):
            return {'op': action, 'count': self.count.value}
        if action in ('drop_duplicates', 'drop_nulls'):
            return {'op': action, 'columns': list(self.subset.value)}
        raise ValueError('操作を選択してください。')

    def load(self, operation):
        op = operation['op']
        if op == 'condition':
            self.action.value = operation['mode']
            rule = operation['condition']
            self.logic.value = rule.get('logic') or 'new'
            self.column.value = rule['column']
            self.comparison.value = rule['comparison']
            self.value.value = str(rule.get('value', ''))
            self.upper.value = str(rule.get('upper', ''))
        else:
            self.action.value = op
            if op in ('head', 'tail'):
                self.count.value = operation['count']
            else:
                self.subset.value = tuple(operation['columns'])

    @staticmethod
    def describe(operation, previous):
        op = operation['op']
        if op == 'condition':
            rule, mode = operation['condition'], operation['mode']
            comparison = rule['comparison']
            logic = rule.get('logic') if RowFields.can_join(previous, mode) else None
            prefix = logic.upper() if logic else OP_LABELS[mode]
            text = f'{prefix}　{rule["column"]} {COMPARISONS[comparison]}'
            if 'value' in rule:
                text += f' {rule["value"]!r}'
            if 'upper' in rule:
                text += f' 〜 {rule["upper"]}'
            return text
        details = f'{operation["count"]}行' if op in ('head', 'tail') else '、'.join(operation['columns']) or '全列'
        return f'{OP_LABELS[op]}　{details}'

    def close(self):
        _close_widgets(self.controls())
