"""Edit ordered column operations and preview them on a DataFrame sample."""
from html import escape

import ipywidgets as widgets
from pandas import isna
from pandas.api.types import is_scalar
from traitlets import Bool, Dict, Unicode

from .row_preview import CELL_WIDTH, MAX_ROWS, _close_widgets


OPERATIONS = {
    'keep': '選択した列だけ残す',
    'drop': '列を削除',
    'rename': '列名を変更',
    'move': '列を移動',
    'convert': '型を変換',
}
TYPES = {'text': '文字列', 'integer': '整数', 'number': '小数', 'date': '日付'}


class ColumnHeader(widgets.Button):
    _view_name = Unicode('ColumnContextView').tag(sync=True)
    _view_module = Unicode('zizai-row-preview').tag(sync=True)
    _view_module_version = Unicode('1.0.0').tag(sync=True)
    _menu_items = Dict().tag(sync=True)
    _column_name = Unicode().tag(sync=True)
    _pending_delete = Bool(False).tag(sync=True)
    _grid_id = Unicode().tag(sync=True)


class ColumnEditor:
    def __init__(self, data, apply_operations, on_change):
        self._apply_operations = apply_operations
        self._on_change = on_change
        self._sample = data.head(MAX_ROWS).copy()
        self.operations = []
        self._transformations = []
        self._deleted = set()
        self._history = []
        self.preview = apply_operations(self._sample, operations=[])
        self._headers = []
        self._editor_widgets = []
        self._intro = widgets.HTML(
            f'<h3>列のプレビュー</h3><p>先頭{MAX_ROWS}行。列見出しを右クリックで操作、'
            'ダブルクリックで名前変更、ドラッグで移動できます。</p>')
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
        self.keep = widgets.Button(description=OPERATIONS['keep'], layout=widgets.Layout(width='auto'))
        self.keep.on_click(lambda _: self._show_controls('keep'))
        self._actions = widgets.HBox([self.keep, self.undo])
        self._actions.add_class('row-preview-footer')
        self.root = widgets.VBox([self._intro, self.grid, self._controls, self.status, self.changes, self._actions])
        self.root.add_class('row-preview')
        self._render()

    def _render(self):
        self._heading.children = ()
        _close_widgets(self._headers)
        self._headers = []
        width = f'{max(1, len(self.preview.columns)) * CELL_WIDTH}px'
        self._heading.layout.min_width = width
        self._body.layout.min_width = width
        names = list(map(str, self.preview.columns))
        deletion_flags = [name in self._deleted for name in names]
        for name, dtype, deleted in zip(names, self.preview.dtypes, deletion_flags):
            description = f'{name} · 削除予定' if deleted else f'{name} · {dtype}'
            menu = {'restore': '元に戻す'} if deleted else {key: OPERATIONS[key] for key in ('drop', 'convert')}
            header = ColumnHeader(description=description, tooltip=name, _column_name=name,
                                  _pending_delete=deleted, _grid_id=self.grid.model_id, _menu_items=menu,
                                  layout=widgets.Layout(flex=f'1 0 {CELL_WIDTH}px'))
            if deleted:
                header.add_class('column-pending-delete')
            header.on_msg(lambda button, message, _, column=name: self._handle_header(button, column, message))
            self._headers.append(header)
        self._heading.children = tuple(self._headers)

        rows = []
        for row in self.preview.itertuples(index=False, name=None):
            cells = []
            for value, deleted in zip(row, deletion_flags):
                text = 'NULL' if is_scalar(value) and isna(value) else str(value)
                label = escape(text[:200] + ('…' if len(text) > 200 else ''))
                classes = 'row-preview-value column-pending-delete' if deleted else 'row-preview-value'
                cells.append(f'<span class="{classes}" title="{label}">{label}</span>')
            rows.append('<div class="row-preview-values-line">' + ''.join(cells) + '</div>')
        self._body.value = ''.join(rows) if rows else '<p>表示できる行がありません。</p>'
        if not self._headers:
            self._body.value = '<p>表示できる列がありません。</p>'
        self.undo.disabled = not self._history
        self.keep.disabled = not any(not deleted for deleted in deletion_flags)
        entries = ''.join(f'<li>{escape(self._describe(change))}</li>' for change in self.operations)
        self.changes.value = '<h3>変更一覧</h3>' + (f'<ol>{entries}</ol>' if entries else '<p>設定した操作はここに表示します。</p>')

    @staticmethod
    def _describe(change):
        op = change['op']
        label = OPERATIONS[op]
        if op in ('keep', 'drop'):
            return f'{label}　' + '、'.join(change['columns'])
        column = change['column']
        if op == 'rename':
            return f'{label}　{column} → {change["name"]}'
        if op == 'convert':
            return f'{label}　{column} → {TYPES[change["type"]]}'
        return f'{label}　{column} → {change["position"]}列目'

    def _handle_header(self, header, column, message):
        if header not in self._headers or not isinstance(message, dict):
            return
        event, role = message.get('event'), message.get('role')
        if column in self._deleted and event != 'column-move':
            if event == 'column-operation' and role == 'restore':
                self._update(self._transformations, self._deleted - {column})
            return
        if event == 'column-operation':
            if role == 'drop':
                self._update(self._transformations, self._deleted | {column})
            elif role == 'convert':
                self._show_controls('convert', column)
        elif event == 'column-rename':
            name = message.get('name')
            if name != column:
                self.add_operation({'op': 'rename', 'column': column, 'name': name})
        elif event == 'column-move':
            source, after = message.get('source'), message.get('after')
            labels = list(map(str, self.preview.columns))
            if (not isinstance(source, str) or source == column or source not in labels
                    or source in self._deleted or type(after) is not bool):
                return
            current = labels.index(source) + 1
            labels.remove(source)
            position = labels.index(column) + 1 + after
            if position != current:
                self.add_operation({'op': 'move', 'column': source, 'position': position})

    def _show_controls(self, op, column=None):
        self._clear_controls()
        suffix = f'　{escape(column)}' if column is not None else ''
        hint = widgets.HTML(f'<strong>{escape(OPERATIONS[op])}</strong>{suffix}')
        if op == 'keep':
            labels = [name for name in map(str, self.preview.columns) if name not in self._deleted]
            if not labels:
                _close_widgets([hint])
                return
            field = widgets.SelectMultiple(
                description='残す列', options=labels, value=tuple(labels), rows=min(8, len(labels)))
            hint.value += '<p>Ctrlキー（macOSは⌘キー）で複数の列を選べます。</p>'
            def apply():
                if not field.value:
                    self.status.value = '<p role="alert">残す列を1つ以上選んでください。</p>'
                    return
                self._update(self._transformations, self._deleted | (set(labels) - set(field.value)))
        else:
            field = widgets.Dropdown(description='変換先', options=[(label, key) for key, label in TYPES.items()])
            def apply():
                self.add_operation({'op': 'convert', 'column': column, 'type': field.value})
        field.layout.width = 'min(100%, 380px)'
        field.style.description_width = 'initial'
        submit = widgets.Button(description='変更を追加', layout=widgets.Layout(width='auto'))
        cancel = widgets.Button(description='キャンセル', layout=widgets.Layout(width='auto'))
        buttons = widgets.HBox([submit, cancel])
        buttons.add_class('row-preview-footer')
        submit.on_click(lambda _: apply() if submit in self._editor_widgets else None)
        cancel.on_click(lambda _: self._clear_controls() if cancel in self._editor_widgets else None)
        self._editor_widgets = [hint, field, submit, cancel, buttons]
        self._controls.children = (hint, field, buttons)

    def _clear_controls(self):
        self._controls.children = ()
        _close_widgets(self._editor_widgets)
        self._editor_widgets = []
        self.status.value = ''

    def add_operation(self, change):
        return self._update([*self._transformations, change], self._deleted)

    def _undo_last(self, _):
        if self._history:
            changes, deleted = self._history.pop()
            self._update(changes, deleted, remember=False)

    def _update(self, changes, deleted, *, remember=True):
        try:
            preview = self._apply_operations(self._sample, operations=changes)
        except (TypeError, ValueError) as error:
            self.status.value = f'<p role="alert">{escape(str(error))}</p>'
            return False
        if remember and (changes != self._transformations or deleted != self._deleted):
            self._history.append((self._transformations, self._deleted))
        self._transformations = changes
        self._deleted = deleted
        drop = [name for name in map(str, preview.columns) if name in deleted]
        self.operations = [*changes, {'op': 'drop', 'columns': drop}] if drop else changes
        self.preview = preview
        self._clear_controls()
        self._render()
        self._on_change(self.operations)
        return True

    def close(self):
        self._clear_controls()
        _close_widgets([*self._headers, self._heading, self._body, self.keep, self.undo, *self.root.children, self.root])
