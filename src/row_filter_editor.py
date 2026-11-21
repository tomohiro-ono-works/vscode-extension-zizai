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
    'bool_equal': '真偽値が一致する', 'date_equal': '日時が一致する',
    'date_before': '指定日時より前', 'date_after': '指定日時より後', 'date_between': '指定期間内',
    'is_null': 'NULLである', 'not_null': 'NULLでない',
}
NULL_COMPARISONS = {'is_null', 'not_null'}
TEXT_COMPARISONS = {'text_equal', 'contains'}
CONDITIONAL = {'keep', 'exclude'}
ROW_CLEANUP = {'drop_duplicates', 'drop_nulls'}
RANGE_COMPARISONS = {'between', 'date_between'}
WHOLE_TABLE = False
TYPED_COMPARISONS = {
    'text': TEXT_COMPARISONS,
    'numeric': {'number_equal', 'greater', 'greater_equal', 'less', 'less_equal', 'between'},
    'bool': {'bool_equal'},
    'datetime': {'date_equal', 'date_before', 'date_after', 'date_between'},
}


class RowFields:
    def __init__(self, column, on_layout):
        self._on_layout = on_layout
        self._columns = {}
        self._previous = {}
        self.action = _dropdown('操作', [('選択してください', None)])
        self.logic = _dropdown('結合', [('AND', 'and'), ('OR', 'or'), ('新しいグループ', 'new')], value='and')
        self.column = column
        self.comparison = _dropdown('比較', [('選択してください', None)])
        self.boolean = _dropdown('比較値', [('True', True), ('False', False)], value=True)
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
        return (self.action, self.comparison, self.value, self.boolean, self.upper, self.logic, self.subset, self.count)

    def set_columns(self, columns):
        self._columns = columns
        if tuple(columns) != self.subset.options:
            subset = self.subset.value
            self.subset.options = tuple(columns)
            self.subset.value = tuple(name for name in subset if name in columns)

    def select_column(self):
        column = self.column.value
        kind = self._columns.get(column)
        actions = set()
        comparisons = set()
        if column is WHOLE_TABLE:
            actions = set(OP_LABELS) - CONDITIONAL
        elif kind is not None:
            actions = CONDITIONAL | ROW_CLEANUP
            comparisons = NULL_COMPARISONS | TYPED_COMPARISONS.get(kind, set())
        for field, labels, available in ((self.action, OP_LABELS, actions),
                                         (self.comparison, COMPARISONS, comparisons)):
            options = (('選択してください', None), *((label, key) for key, label in labels.items() if key in available))
            if options != field.options:
                previous = field.value
                field.options = options
                field.value = previous if previous in available else None
            field.disabled = not available
        self._changed(None)

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
        self.comparison.layout.display = '' if conditional else 'none'
        show_value = conditional and comparison and comparison not in NULL_COMPARISONS
        self.value.layout.display = '' if show_value and comparison != 'bool_equal' else 'none'
        self.boolean.layout.display = '' if conditional and comparison == 'bool_equal' else 'none'
        self.value.description = '下限' if comparison in RANGE_COMPARISONS else '比較値'
        self.value.placeholder = 'YYYY-MM-DD または日時' if comparison and comparison.startswith('date_') else ''
        self.upper.placeholder = self.value.placeholder
        self.upper.layout.display = '' if conditional and comparison in RANGE_COMPARISONS else 'none'
        self.subset.layout.display = '' if action in ROW_CLEANUP and self.column.value is WHOLE_TABLE else 'none'
        self.count.layout.display = '' if action in ('head', 'tail') else 'none'

    def operation(self):
        action = self.action.value
        if action in CONDITIONAL:
            column, comparison = self.column.value, self.comparison.value
            if column is None or comparison is None:
                raise ValueError('対象列と比較方法を選択してください。')
            rule = {'column': column, 'comparison': comparison}
            if comparison not in NULL_COMPARISONS:
                if comparison == 'bool_equal':
                    rule['value'] = self.boolean.value
                elif comparison in TEXT_COMPARISONS or comparison.startswith('date_'):
                    rule['value'] = self.value.value
                else:
                    rule['value'] = _number(self.value.value)
            if comparison in RANGE_COMPARISONS:
                rule['upper'] = self.upper.value if comparison == 'date_between' else _number(self.upper.value)
            if self.can_join(self._previous, action) and self.logic.value != 'new':
                rule['logic'] = self.logic.value
            return {'op': 'condition', 'mode': action, 'condition': rule}
        if action in ('head', 'tail'):
            return {'op': action, 'count': self.count.value}
        if action in ROW_CLEANUP:
            columns = list(self.subset.value) if self.column.value is WHOLE_TABLE else [self.column.value]
            return {'op': action, 'columns': columns}
        raise ValueError('操作を選択してください。')

    def load(self, operation):
        op = operation['op']
        if op == 'condition':
            rule = operation['condition']
            self.column.value = rule['column']
            self.action.value = operation['mode']
            self.logic.value = rule.get('logic') or 'new'
            self.comparison.value = rule['comparison']
            if rule['comparison'] == 'bool_equal':
                self.boolean.value = rule['value']
            self.value.value = str(rule.get('value', ''))
            self.upper.value = str(rule.get('upper', ''))
        else:
            columns = operation.get('columns', [])
            self.column.value = columns[0] if len(columns) == 1 else WHOLE_TABLE
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
            details = COMPARISONS[comparison]
            if 'value' in rule:
                details += f' {rule["value"]!r}'
            if 'upper' in rule:
                details += f' 〜 {rule["upper"]!r}'
            if logic:
                details += f'、結合 {logic.upper()}'
            return rule['column'], OP_LABELS[mode], details
        if op in ('head', 'tail'):
            return '表全体', OP_LABELS[op], f'{operation["count"]}行'
        columns = operation['columns']
        if len(columns) == 1:
            return columns[0], OP_LABELS[op], ''
        details = f'判定列 {"、".join(columns)}' if columns else ''
        return '表全体', OP_LABELS[op], details

    def close(self):
        _close_widgets(self.controls())
