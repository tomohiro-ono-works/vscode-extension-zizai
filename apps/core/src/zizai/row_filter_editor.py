"""Configure ordered row conditions and cleanup before generating Notebook code."""
from html import escape

import ipywidgets as widgets

from .row_preview import MAX_ROWS, _close_widgets
from .value_editor import _dropdown, _number, _operation_form, _OperationList


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


class RowFilterEditor:
    def __init__(self, data, apply_operations, on_change):
        self._apply_operations = apply_operations
        self._on_change = on_change
        self._sample = data.head(MAX_ROWS).copy()
        apply_operations(self._sample, operations=[])
        self.operations = []
        columns = list(map(str, self._sample.columns))

        self.action = _dropdown('操作', [('選択してください', None), *((label, key) for key, label in OP_LABELS.items())])
        self.logic = _dropdown('結合', [('AND', 'and'), ('OR', 'or'), ('新しいグループ', 'new')], value='and')
        self.column = _dropdown('対象列', [('選択してください', None), *((name, name) for name in columns)])
        self.comparison = _dropdown('比較', [('選択してください', None), *((label, key) for key, label in COMPARISONS.items())])
        self.value = widgets.Text(description='比較値', layout=widgets.Layout(width='auto'))
        self.upper = widgets.Text(description='上限', layout=widgets.Layout(width='auto'))
        self.subset = widgets.SelectMultiple(description='判定列（未選択は全列）', options=columns,
                                             rows=min(3, max(1, len(columns))), layout=widgets.Layout(width='auto'))
        self.count = widgets.IntText(description='行数', value=1, layout=widgets.Layout(width='auto'))
        self.count.add_class('zizai-integer')
        for control in (self.value, self.upper, self.subset, self.count):
            control.style.description_width = 'initial'
        self.apply = widgets.Button(description='条件を追加', disabled=True, layout=widgets.Layout(width='auto'))
        self.apply.on_click(self._add_current)
        self.settings, self._inputs = _operation_form(self.apply)
        self._inputs.children = (self.action, self.logic, self.column, self.comparison,
                                 self.value, self.upper, self.subset, self.count)
        self.status = widgets.HTML()
        self.entries = _OperationList('条件一覧', self._remove)
        self.root = widgets.VBox([self.settings, self.status, self.entries.root])
        self.root.add_class('row-preview')
        self.action.observe(self._show_fields, names='value')
        self.comparison.observe(self._show_fields, names='value')
        self._show_fields(None)

    def _same_group(self):
        return bool(self.operations and self.operations[-1].get('mode') == self.action.value
                    and self.action.value in CONDITIONAL)

    def _show_fields(self, _change):
        action, comparison = self.action.value, self.comparison.value
        conditional = action in CONDITIONAL
        self.status.value = ''
        self.logic.layout.display = '' if self._same_group() else 'none'
        self.column.layout.display = self.comparison.layout.display = '' if conditional else 'none'
        self.value.layout.display = '' if conditional and comparison and comparison not in NULL_COMPARISONS else 'none'
        self.value.description = '下限' if comparison == 'between' else '比較値'
        self.upper.layout.display = '' if conditional and comparison == 'between' else 'none'
        self.subset.layout.display = '' if action in ('drop_duplicates', 'drop_nulls') else 'none'
        self.count.layout.display = '' if action in ('head', 'tail') else 'none'
        self.apply.description = '条件を追加' if conditional or action is None else '操作を追加'
        self.apply.disabled = action is None

    def _condition(self):
        column, comparison = self.column.value, self.comparison.value
        if column is None or comparison is None:
            raise ValueError('対象列と比較方法を選択してください。')
        condition = {'column': column, 'comparison': comparison}
        if comparison not in NULL_COMPARISONS:
            condition['value'] = self.value.value if comparison in TEXT_COMPARISONS else _number(self.value.value)
        if comparison == 'between':
            condition['upper'] = _number(self.upper.value)
        return condition

    def _operations_with_current(self):
        action = self.action.value
        if action in CONDITIONAL:
            condition = self._condition()
            if self._same_group() and self.logic.value != 'new':
                previous = self.operations[-1]
                condition['logic'] = self.logic.value
                return [*self.operations[:-1], {**previous, 'conditions': [*previous['conditions'], condition]}]
            operation = {'op': 'filter', 'mode': action, 'conditions': [condition]}
        elif action in ('head', 'tail'):
            operation = {'op': action, 'count': self.count.value}
        else:
            operation = {'op': action, 'columns': list(self.subset.value)}
        return [*self.operations, operation]

    def _add_current(self, _button):
        if self.action.value is None:
            return
        try:
            self._update(self._operations_with_current())
        except ValueError as error:
            self.status.value = f'<p role="alert">{escape(str(error))}</p>'
            return
        if self.logic.value == 'new':
            self.logic.value = 'and'

    def _remove(self, key):
        index, condition_index = key
        operations = self.operations.copy()
        if condition_index is None:
            operations.pop(index)
        else:
            operation = operations[index]
            conditions = operation['conditions'][:condition_index] + operation['conditions'][condition_index + 1:]
            if not conditions:
                operations.pop(index)
            else:
                conditions[0] = {name: value for name, value in conditions[0].items() if name != 'logic'}
                operations[index] = {**operation, 'conditions': conditions}
        try:
            self._update(operations)
        except ValueError as error:
            self.status.value = f'<p role="alert">削除できません。{escape(str(error))}</p>'

    def _update(self, operations):
        self._apply_operations(self._sample, operations=operations)
        self.operations = operations
        self._show_fields(None)
        self._render_entries()
        self._on_change(operations)

    @staticmethod
    def _describe_condition(mode, condition):
        comparison = condition['comparison']
        prefix = condition.get('logic', '').upper() or OP_LABELS[mode]
        text = f'{prefix}　{condition["column"]} {COMPARISONS[comparison]}'
        if 'value' in condition:
            text += f' {condition["value"]!r}'
        if 'upper' in condition:
            text += f' 〜 {condition["upper"]}'
        return text

    def _render_entries(self):
        entries = []
        for index, operation in enumerate(self.operations):
            op = operation['op']
            if op == 'filter':
                entries.extend(((index, offset), self._describe_condition(operation['mode'], condition))
                               for offset, condition in enumerate(operation['conditions']))
            else:
                details = f'{operation["count"]}行' if op in ('head', 'tail') else '、'.join(operation['columns']) or '全列'
                entries.append(((index, None), f'{OP_LABELS[op]}　{details}'))
        self.entries.render(entries)

    def close(self):
        self.entries.close()
        _close_widgets([*self._inputs.children, self._inputs, self.apply, self.settings, self.status, self.root])
