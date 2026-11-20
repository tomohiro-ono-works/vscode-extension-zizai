"""Configure row selection and cleanup before generating Notebook code."""
from html import escape

import ipywidgets as widgets

from .column_editor import DataFramePreview
from .row_preview import MAX_ROWS, _close_widgets
from .value_editor import _dropdown, _number, _settings_row


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


class RowCondition:
    def __init__(self, columns, *, first):
        self.logic = None if first else _dropdown('結合', [('AND', 'and'), ('OR', 'or')], value='and')
        self.column = _dropdown('対象列', [('選択してください', None), *((name, name) for name in columns)])
        self.comparison = _dropdown('比較', [('選択してください', None), *((label, key) for key, label in COMPARISONS.items())])
        self.value = widgets.Text(description='比較値', layout=widgets.Layout(width='auto', display='none'))
        self.upper = widgets.Text(description='上限', layout=widgets.Layout(width='auto', display='none'))
        for control in (self.value, self.upper):
            control.style.description_width = 'initial'
        self.comparison.observe(self._toggle_comparison, names='value')
        controls = [self.column, self.comparison, self.value, self.upper]
        self.root = _settings_row(controls if first else [self.logic, *controls])

    def _toggle_comparison(self, _change):
        comparison = self.comparison.value
        self.value.layout.display = '' if comparison and comparison not in NULL_COMPARISONS else 'none'
        self.value.description = '下限' if comparison == 'between' else '比較値'
        self.upper.layout.display = '' if comparison == 'between' else 'none'

    def build(self):
        column, comparison = self.column.value, self.comparison.value
        if not column or not comparison:
            raise ValueError('各条件の対象列と比較方法を選択してください。')
        data = {'column': column, 'comparison': comparison}
        if self.logic is not None:
            data['logic'] = self.logic.value
        if comparison not in NULL_COMPARISONS:
            data['value'] = self.value.value if comparison in TEXT_COMPARISONS else _number(self.value.value)
        if comparison == 'between':
            data['upper'] = _number(self.upper.value)
        return data

    def close(self):
        _close_widgets([*self.root.children, self.root])


class RowFilterEditor:
    def __init__(self, data, apply_operations, on_change):
        self._apply_operations = apply_operations
        self._on_change = on_change
        self._sample = data.head(MAX_ROWS).copy()
        self.preview = apply_operations(self._sample, operations=[])
        self.operations = []
        self._columns = list(map(str, self._sample.columns))
        self.conditions = []

        self.action = _dropdown('操作', [('選択してください', None), *((label, key) for key, label in OP_LABELS.items())])
        self._operation_row = _settings_row([self.action])
        self._rows = widgets.VBox()
        self.add_condition = widgets.Button(description='条件を追加', layout=widgets.Layout(width='auto'))
        self.add_condition.on_click(lambda _: self._append_condition())
        self.remove_condition = widgets.Button(description='最後の条件を外す', layout=widgets.Layout(width='auto'))
        self.remove_condition.on_click(self._remove_condition)
        self._condition_actions = _settings_row([self.add_condition, self.remove_condition])
        self._precedence = widgets.HTML('<p>ANDを先に評価します。</p>')
        self._condition_settings = widgets.VBox([self._rows, self._condition_actions, self._precedence],
                                                 layout=widgets.Layout(display='none'))
        self.subset = widgets.SelectMultiple(description='判定列（未選択は全列）', options=self._columns,
                                             rows=min(5, max(1, len(self._columns))),
                                             layout=widgets.Layout(width='min(100%, 420px)'))
        self.subset.style.description_width = 'initial'
        self._subset_row = _settings_row([self.subset])
        self._subset_row.layout.display = 'none'
        self.count = widgets.IntText(description='行数', value=1, layout=widgets.Layout(width='auto', display='none'))
        self.count.style.description_width = 'initial'
        self.count.add_class('zizai-integer')
        self.apply = widgets.Button(description='変更を追加', disabled=True, layout=widgets.Layout(width='auto'))
        self.apply.on_click(self._add_current)
        self.settings = widgets.VBox([
            self._operation_row, self._condition_settings, self._subset_row, self.count, self.apply,
        ])
        self.status = widgets.HTML()
        self._table = DataFramePreview()
        self.grid = self._table.root
        self.summary = widgets.HTML()
        self.changes = widgets.HTML()
        self.undo = widgets.Button(description='最後の変更を取り消す', layout=widgets.Layout(width='auto'))
        self.undo.on_click(self._undo_last)
        self.root = widgets.VBox([self.settings, self.status, self.summary, self.grid, self.changes, self.undo])
        self.root.add_class('row-preview')
        self.action.observe(self._select_action, names='value')
        self._render()

    def _select_action(self, _change):
        action = self.action.value
        self.status.value = ''
        conditional = action in ('keep', 'exclude')
        self._condition_settings.layout.display = '' if conditional else 'none'
        self._subset_row.layout.display = '' if action in ('drop_duplicates', 'drop_nulls') else 'none'
        self.count.layout.display = '' if action in ('head', 'tail') else 'none'
        self.apply.disabled = action is None
        if conditional and not self.conditions:
            self._append_condition()

    def _append_condition(self):
        self.conditions.append(RowCondition(self._columns, first=not self.conditions))
        self._render_conditions()

    def _remove_condition(self, _button):
        if len(self.conditions) > 1:
            condition = self.conditions.pop()
            self._render_conditions()
            condition.close()

    def _render_conditions(self):
        self._rows.children = tuple(condition.root for condition in self.conditions)
        self.remove_condition.disabled = len(self.conditions) < 2
        self._precedence.layout.display = '' if len(self.conditions) > 2 else 'none'

    def _operation(self):
        action = self.action.value
        if action in ('keep', 'exclude'):
            return {'op': 'filter', 'mode': action, 'conditions': [condition.build() for condition in self.conditions]}
        if action in ('head', 'tail'):
            return {'op': action, 'count': self.count.value}
        return {'op': action, 'columns': list(self.subset.value)}

    def _add_current(self, _button):
        if self.action.value is None:
            return
        try:
            self._update([*self.operations, self._operation()])
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

    @staticmethod
    def _describe(operation):
        op = operation['op']
        if op == 'filter':
            conditions = operation['conditions']
            descriptions = []
            for condition in conditions:
                comparison = condition['comparison']
                text = f'{condition["column"]} {COMPARISONS[comparison]}'
                if 'value' in condition:
                    text += f' {condition["value"]!r}'
                if 'upper' in condition:
                    text += f' 〜 {condition["upper"]}'
                if 'logic' in condition:
                    text = f'{condition["logic"].upper()} {text}'
                descriptions.append(text)
            return OP_LABELS[operation['mode']] + '　' + ' '.join(descriptions)
        if op in ('head', 'tail'):
            return f'{OP_LABELS[op]}　{operation["count"]}行'
        return OP_LABELS[op] + '　' + ('、'.join(operation['columns']) or '全列')

    def _render(self):
        self._table.render(self.preview)
        self.summary.value = (f'<h3>行のプレビュー</h3><p>元の表の先頭{len(self._sample)}行で試行し、'
                              f'{len(self.preview)}行が残ります。</p>')
        entries = ''.join(f'<li>{escape(self._describe(change))}</li>' for change in self.operations)
        self.changes.value = '<h3>変更一覧</h3>' + (f'<ol>{entries}</ol>' if entries else
                                                '<p>設定した操作はここに表示します。</p>')
        self.undo.disabled = not self.operations

    def close(self):
        for condition in self.conditions:
            condition.close()
        self._table.close()
        _close_widgets([self.action, self._operation_row, self._rows, self.add_condition, self.remove_condition,
                        self._condition_actions, self._precedence, self._condition_settings, self.subset,
                        self._subset_row, self.count, self.apply, self.settings, self.status, self.summary,
                        self.changes, self.undo, self.root])
