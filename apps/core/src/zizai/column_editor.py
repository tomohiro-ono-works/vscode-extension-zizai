"""Edit ordered column operations and preview them on a DataFrame sample."""
from html import escape

import ipywidgets as widgets
from pandas import isna
from pandas.api.types import is_scalar
from traitlets import Dict, Unicode

from .row_preview import CELL_WIDTH, MAX_ROWS, _close_widgets


OPERATIONS = {
    'keep': '選択した列だけ残す',
    'drop': '列を削除',
    'rename': '列名を変更',
    'duplicate': '列を複製',
    'move': '列を移動',
    'convert': '型を変換',
}
TYPES = {'text': '文字列', 'integer': '整数', 'number': '小数', 'date': '日付'}


class ColumnHeader(widgets.Button):
    _view_name = Unicode('ColumnContextView').tag(sync=True)
    _view_module = Unicode('zizai-row-preview').tag(sync=True)
    _view_module_version = Unicode('1.0.0').tag(sync=True)
    _menu_items = Dict(default_value=OPERATIONS).tag(sync=True)


class ColumnEditor:
    def __init__(self, data, apply_operations, on_change):
        self._apply_operations = apply_operations
        self._on_change = on_change
        self._sample = data.head(MAX_ROWS).copy()
        self.operations = []
        self.preview = apply_operations(self._sample, operations=[])
        self._headers = []
        self._editor_widgets = []
        self._intro = widgets.HTML(
            f'<h3>列のプレビュー</h3><p>先頭{MAX_ROWS}行。列見出しを右クリックして操作を選びます。</p>')
        self._heading = widgets.HBox(layout=widgets.Layout(flex='0 0 32px', overflow='visible'))
        self._heading.add_class('column-preview-heading')
        self._body = widgets.HTML()
        self.grid = widgets.VBox([self._heading, self._body], layout=widgets.Layout(
            width='100%', max_height='310px', overflow='auto'))
        self.grid.add_class('row-preview-grid')
        self._controls = widgets.VBox()
        self._controls.add_class('column-preview-controls')
        self.status = widgets.HTML()
        self.changes = widgets.HTML()
        self.undo = widgets.Button(description='最後の変更を取り消す', layout=widgets.Layout(width='auto'))
        self.undo.on_click(self._undo_last)
        self.root = widgets.VBox([self._intro, self.grid, self._controls, self.status, self.changes, self.undo])
        self.root.add_class('row-preview')
        self._render()

    def _render(self):
        self._heading.children = ()
        _close_widgets(self._headers)
        self._headers = []
        width = f'{max(1, len(self.preview.columns)) * CELL_WIDTH}px'
        self._heading.layout.min_width = width
        self._body.layout.min_width = width
        for label, dtype in zip(self.preview.columns, self.preview.dtypes):
            name = str(label)
            header = ColumnHeader(description=f'{name} · {dtype}', tooltip=name,
                                  layout=widgets.Layout(flex=f'1 0 {CELL_WIDTH}px'))
            header.on_msg(lambda button, message, _, column=name: self._select(button, column, message))
            self._headers.append(header)
        self._heading.children = tuple(self._headers)

        rows = []
        for row in self.preview.itertuples(index=False, name=None):
            cells = []
            for value in row:
                text = 'NULL' if is_scalar(value) and isna(value) else str(value)
                label = escape(text[:200] + ('…' if len(text) > 200 else ''))
                cells.append(f'<span class="row-preview-value" title="{label}">{label}</span>')
            rows.append('<div class="row-preview-values-line">' + ''.join(cells) + '</div>')
        self._body.value = ''.join(rows) if rows else '<p>表示できる行がありません。</p>'
        if not self._headers:
            self._body.value = '<p>表示できる列がありません。</p>'
        self.undo.disabled = not self.operations
        entries = ''.join(f'<li>{escape(self._describe(change))}</li>' for change in self.operations)
        self.changes.value = '<h3>変更一覧</h3>' + (f'<ol>{entries}</ol>' if entries else '<p>設定した操作はここに表示します。</p>')

    @staticmethod
    def _describe(change):
        op = change['op']
        label = OPERATIONS[op]
        if op in ('keep', 'drop'):
            return f'{label}　' + '、'.join(change['columns'])
        column = change['column']
        if op in ('rename', 'duplicate'):
            return f'{label}　{column} → {change["name"]}'
        if op == 'convert':
            return f'{label}　{column} → {TYPES[change["type"]]}'
        return f'{label}　{column} → {change["position"]}列目'

    def _select(self, header, column, message):
        if header not in self._headers or not isinstance(message, dict) or message.get('event') != 'column-operation':
            return
        op = message.get('role')
        if not isinstance(op, str) or op not in OPERATIONS:
            return
        self._clear_controls()
        self.status.value = ''
        labels = list(map(str, self.preview.columns))
        hint = widgets.HTML(f'<strong>{escape(OPERATIONS[op])}</strong>　{escape(column)}')
        if op in ('keep', 'drop'):
            field = widgets.SelectMultiple(
                description='対象列', options=labels, value=(column,), rows=min(8, len(labels)))
            hint.value += '<p>Ctrlキー（macOSは⌘キー）で複数の列を選べます。</p>'
            extra = lambda: {'columns': list(field.value)}
        elif op in ('rename', 'duplicate'):
            field = widgets.Text(description='新しい列名', value=column if op == 'rename' else f'{column}_copy')
            extra = lambda: {'column': column, 'name': field.value}
        elif op == 'move':
            field = widgets.BoundedIntText(description='移動先（列目）', min=1, max=len(labels),
                                           value=labels.index(column) + 1)
            extra = lambda: {'column': column, 'position': field.value}
        else:
            field = widgets.Dropdown(description='変換先', options=[(label, key) for key, label in TYPES.items()])
            extra = lambda: {'column': column, 'type': field.value}
        field.layout.width = 'min(100%, 380px)'
        field.style.description_width = 'initial'
        submit = widgets.Button(description='変更を追加', layout=widgets.Layout(width='auto'))
        cancel = widgets.Button(description='キャンセル', layout=widgets.Layout(width='auto'))
        buttons = widgets.HBox([submit, cancel])
        buttons.add_class('row-preview-footer')
        submit.on_click(lambda _: self.add_operation({'op': op, **extra()}) if submit in self._editor_widgets else None)
        cancel.on_click(lambda _: self._clear_controls() if cancel in self._editor_widgets else None)
        self._editor_widgets = [hint, field, submit, cancel, buttons]
        self._controls.children = (hint, field, buttons)

    def _clear_controls(self):
        self._controls.children = ()
        _close_widgets(self._editor_widgets)
        self._editor_widgets = []
        self.status.value = ''

    def add_operation(self, change):
        return self._update([*self.operations, change])

    def _undo_last(self, _):
        if self.operations:
            self._update(self.operations[:-1])

    def _update(self, operations):
        try:
            preview = self._apply_operations(self._sample, operations=operations)
        except (TypeError, ValueError) as error:
            self.status.value = f'<p role="alert">{escape(str(error))}</p>'
            return False
        self.operations = operations
        self.preview = preview
        self._clear_controls()
        self._render()
        self._on_change(operations)
        return True

    def close(self):
        self._clear_controls()
        _close_widgets([*self._headers, self._heading, self._body, *self.root.children, self.root])
