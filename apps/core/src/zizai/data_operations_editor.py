"""Edit one ordered list of row conditions and value transformations."""
from html import escape

import ipywidgets as widgets
from traitlets import Unicode

from .row_filter_editor import RowFields
from .row_preview import MAX_ROWS, _close_widgets
from .value_editor import ValueFields, _dropdown, _operation_form


CATEGORIES = {'condition': '条件', 'value': '値加工'}


class OperationEntry(widgets.HBox):
    _view_name = Unicode('OperationEntryView').tag(sync=True)
    _view_module = Unicode('zizai-row-preview').tag(sync=True)
    _view_module_version = Unicode('1.0.0').tag(sync=True)
    _entry_id = Unicode().tag(sync=True)
    _list_id = Unicode().tag(sync=True)


class OperationList:
    def __init__(self, on_edit, on_remove, on_move):
        self._on_edit, self._on_remove, self._on_move = on_edit, on_remove, on_move
        self._title = widgets.HTML('<h3>処理一覧</h3>')
        self.rows = widgets.VBox()
        self.rows.add_class('zizai-operation-list')
        self.root = widgets.VBox([self._title, self.rows])

    def render(self, descriptions):
        previous = self.rows.children
        rows = []
        for index, description in enumerate(descriptions):
            handle = widgets.HTML('<span title="ドラッグして順番を変更">↕</span>')
            handle.add_class('zizai-operation-handle')
            label = widgets.HTML(f'<p>{escape(description)}</p>', layout=widgets.Layout(flex='1 1 0', min_width='0'))
            edit = widgets.Button(description='編集', tooltip=description,
                                  layout=widgets.Layout(width='auto', flex='0 0 auto'))
            remove = widgets.Button(description='削除', tooltip=description,
                                    layout=widgets.Layout(width='auto', flex='0 0 auto'))
            for button in (edit, remove):
                button.add_class('row-preview-cancel')
            row = OperationEntry([handle, label, edit, remove], _list_id=self.rows.model_id,
                                 layout=widgets.Layout(width='100%', align_items='center'))
            row._entry_id = row.model_id
            row.add_class('zizai-operation-entry')
            edit.on_click(lambda _, index=index, row=row: self._dispatch(self._on_edit, index, row))
            remove.on_click(lambda _, index=index, row=row: self._dispatch(self._on_remove, index, row))
            row.on_msg(self._handle_drop)
            rows.append(row)
        self.rows.children = tuple(rows)
        self._close_rows(previous)

    def _dispatch(self, callback, index, row):
        if row in self.rows.children:
            callback(index)

    def _handle_drop(self, row, message, _buffers):
        rows = self.rows.children
        if row not in rows or not isinstance(message, dict) or message.get('event') != 'operation-move':
            return
        source, after = message.get('source'), message.get('after')
        source_index = next((index for index, item in enumerate(rows) if item.model_id == source), None)
        if source_index is not None and type(after) is bool:
            self._on_move(source_index, rows.index(row), after=after)

    @staticmethod
    def _close_rows(rows):
        for row in rows:
            _close_widgets([*row.children, row])

    def close(self):
        self._close_rows(self.rows.children)
        _close_widgets([self._title, self.rows, self.root])


class DataOperationsEditor:
    def __init__(self, data, apply_operations, on_change, *, mode=None):
        self._apply_operations, self._on_change = apply_operations, on_change
        self._mode = mode
        self._sample = data.head(MAX_ROWS).copy()
        self._result = apply_operations(self._sample, operations=[])
        self.operations = []
        self._editing = None
        self.category = _dropdown('処理分類', [('選択してください', None), *((label, key) for key, label in CATEGORIES.items())],
                                  value=mode)
        self.apply = widgets.Button(description='処理を追加', disabled=True, layout=widgets.Layout(width='auto'))
        self.apply.on_click(self._submit)
        self.cancel = widgets.Button(description='編集をキャンセル', layout=widgets.Layout(width='auto', display='none'))
        self.cancel.add_class('row-preview-cancel')
        self.cancel.on_click(self._cancel_edit)
        self.settings, self._inputs = _operation_form(self.apply)
        self.settings.children = (self._inputs, self.cancel, self.apply)
        self.status = widgets.HTML()
        self.entries = OperationList(self._edit, self._remove, self._move)
        self.value_fields = ValueFields(self._refresh_inputs)
        self.row_fields = RowFields(self._refresh_inputs)
        self.root = widgets.VBox([self.settings, self.status, self.entries.root])
        self.root.add_class('row-preview')
        self.category.observe(self._change_category, names='value')
        self._refresh_context()

    def _active_fields(self):
        return {'condition': self.row_fields, 'value': self.value_fields}.get(self.category.value)

    def _payload(self, steps):
        return [step['operation'] for step in steps] if self._mode else steps

    def _position(self):
        return next((i for i, step in enumerate(self.operations) if step is self._editing), len(self.operations))

    @staticmethod
    def _previous_condition(steps, position):
        if position and steps[position - 1]['category'] == 'condition':
            return steps[position - 1]['operation']
        return {}

    def _refresh_context(self):
        position = self._position()
        frame = self._result if self._editing is None else self._apply_operations(
            self._sample, operations=self._payload(self.operations[:position]))
        columns = list(map(str, frame.columns))
        self.value_fields.set_columns(columns)
        self.row_fields.set_columns(columns)
        self.row_fields.set_previous(self._previous_condition(self.operations, position))
        self._refresh_inputs()

    def _refresh_inputs(self):
        active = self._active_fields()
        category_controls = () if self._mode else (self.category,)
        self._inputs.children = (*category_controls, *(active.controls() if active else ()))
        enabled = active is not None and active.action.value is not None
        self.apply.disabled = not enabled
        self.cancel.layout.display = '' if self._editing is not None else 'none'
        if self._editing is not None:
            self.apply.description = '編集を保存'
        elif self.category.value == 'value':
            self.apply.description = '変数を追加'
        elif self.category.value == 'condition':
            self.apply.description = '条件を追加'
        else:
            self.apply.description = '処理を追加'

    def _change_category(self, _change):
        self.status.value = ''
        self._refresh_inputs()

    def _edit(self, index):
        self._editing = self.operations[index]
        self.status.value = ''
        self.category.value = self._editing['category']
        self._refresh_context()
        self._active_fields().load(self._editing['operation'])
        self._refresh_inputs()

    def _cancel_edit(self, _button):
        self._editing = None
        self.status.value = ''
        self._refresh_context()

    def _submit(self, _button):
        if self.apply.disabled:
            return
        try:
            active = self._active_fields()
            step = {'category': self.category.value, 'operation': active.operation()}
            steps = self.operations.copy()
            if self._editing is None:
                steps.append(step)
            else:
                steps[self._position()] = step
            self._commit(steps, finish_edit=True)
        except ValueError as error:
            self._error(error)
        else:
            if self.row_fields.logic.value == 'new':
                self.row_fields.logic.value = 'and'

    def _remove(self, index):
        try:
            self._commit(self.operations[:index] + self.operations[index + 1:])
        except ValueError as error:
            self._error(error, prefix='削除できません。')

    def _move(self, source, target, *, after):
        if source == target:
            return
        position = target - (source < target) + after
        if position == source:
            return
        steps = self.operations.copy()
        steps.insert(position, steps.pop(source))
        try:
            self._commit(steps)
        except ValueError as error:
            self._error(error, prefix='並べ替えできません。')

    def _commit(self, steps, *, finish_edit=False):
        payload = self._payload(steps)
        self._result = self._apply_operations(self._sample, operations=payload)
        self.operations = steps
        if finish_edit or not any(step is self._editing for step in steps):
            self._editing = None
        self.status.value = ''
        self._refresh_context()
        descriptions = []
        for index, step in enumerate(steps):
            operation = step['operation']
            if step['category'] == 'value':
                label = self.value_fields.describe(operation)
            else:
                label = self.row_fields.describe(operation, self._previous_condition(steps, index))
            descriptions.append(f'{CATEGORIES[step["category"]]}　{label}')
        self.entries.render(descriptions)
        self._on_change(payload)

    def _error(self, error, *, prefix=''):
        self.status.value = f'<p role="alert">{prefix}{escape(str(error))}</p>'

    def close(self):
        self.entries.close()
        self.value_fields.close()
        self.row_fields.close()
        _close_widgets([self.category, self.apply, self.cancel, self._inputs, self.settings, self.status, self.root])
