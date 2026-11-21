"""Notebook settings for the pandas table actions."""
from html import escape

import ipywidgets as widgets
from traitlets import Unicode

from .pandas_table_codegen import (
    AGGREGATE_ROWS, AGGREGATIONS, COMBINE_FRAMES, JOIN_TYPES, RESHAPE_ROWS, SET_OPERATIONS, SORT_ROWS,
    aggregate_sample, column_names, reshape_sample,
)
from .row_preview import MAX_ROWS, _close_widgets
from .value_editor import _dropdown


def _choices(columns):
    return [('選択してください', None), *((column, column) for column in columns)]


def _set_choices(widget, choices, *, preserve=True):
    current = widget.value if preserve else None
    if tuple(choices) != widget.options:
        widget.options = choices
    widget.value = current if current in dict(choices).values() else None


class SettingRows:
    """Manage the repeated keys or aggregation settings in visual order."""
    def __init__(self, label, fields, on_change, *, ordered=False):
        self.fields, self.on_change, self.ordered = fields, on_change, ordered
        self.rows = widgets.VBox()
        self.rows.add_class('zizai-table-step-rows')
        self.add = widgets.Button(description=label, layout=widgets.Layout(width='auto', align_self='flex-start'))
        self.add.on_click(self.add_row)
        self.root = widgets.VBox([self.rows, self.add])
        self.root.add_class('zizai-table-step-rows')
        self.add_row(notify=False)

    def add_row(self, _button=None, *, notify=True):
        fields = self.fields()
        for field in fields:
            field.observe(self.on_change, names='value')
        row = widgets.HBox(fields, layout=widgets.Layout(flex_flow='row wrap', align_items='flex-end'))
        row.add_class('zizai-table-step-row')
        actions = []
        if self.ordered:
            for caption, hint, offset in (('↑', '優先順位を上げる', -1), ('↓', '優先順位を下げる', 1)):
                button = widgets.Button(description=caption, tooltip=hint, layout=widgets.Layout(width='auto'))
                button.add_class('row-preview-cancel')
                button.on_click(lambda _, step=offset: self._move(row, step))
                actions.append(button)
        remove = widgets.Button(description='削除', layout=widgets.Layout(width='auto'))
        remove.add_class('zizai-operation-delete')
        remove.on_click(lambda _: self._remove(row))
        row.children = (*fields, *actions, remove)
        self.rows.children = (*self.rows.children, row)
        self._refresh_buttons()
        if notify:
            self.on_change()

    def _refresh_buttons(self):
        count = len(self.rows.children)
        for index, row in enumerate(self.rows.children):
            row.children[-1].disabled = count == 1
            if self.ordered:
                row.children[-3].disabled = index == 0
                row.children[-2].disabled = index == count - 1

    def _move(self, row, step):
        rows = list(self.rows.children)
        if row in rows:
            position = rows.index(row)
            destination = position + step
            if 0 <= destination < len(rows):
                rows.insert(destination, rows.pop(position))
                self.rows.children = tuple(rows)
                self._refresh_buttons()
                self.on_change()

    def _remove(self, row):
        if row in self.rows.children and len(self.rows.children) > 1:
            self.rows.children = tuple(item for item in self.rows.children if item is not row)
            _close_widgets([*row.children, row])
            self._refresh_buttons()
            self.on_change()

    def close(self):
        for row in self.rows.children:
            _close_widgets([*row.children, row])
        _close_widgets([self.rows, self.add, self.root])


class TableEditor:
    def __init__(self, source, on_change):
        self.columns = column_names(source)
        self.lookup_labels = any(not isinstance(label, str) for label in source.columns)
        self.on_change = on_change
        self.status = widgets.HTML()
        self.root = widgets.VBox()
        self.rules = None
        self.root.add_class('row-preview')
        self._owned = [self.status, self.root]
        self._updating = False

    def controls(self, *children):
        row = widgets.HBox(children, layout=widgets.Layout(flex_flow='row wrap', align_items='flex-end'))
        row.add_class('zizai-table-step-row')
        for child in children:
            child.observe(self.refresh, names='value')
        self._owned.extend([*children, row])
        return row

    def refresh(self, _change=None):
        if self._updating:
            return
        try:
            settings = self.settings()
            if settings and self.lookup_labels:
                settings['lookup_labels'] = True
            self.show_preview(settings)
        except (TypeError, ValueError, KeyError, OverflowError) as error:
            self.status.value = f'<p role="alert">{escape(str(error))}</p>'
            self.show_preview(None)
            settings = None
        else:
            self.status.value = ''
        self.on_change(settings)

    def show_preview(self, _settings):
        pass

    def close(self):
        if self.rules is not None:
            self.rules.close()
        _close_widgets(self._owned)


class SortEditor(TableEditor):
    def __init__(self, source, on_change):
        super().__init__(source, on_change)
        self.rules = SettingRows('並べ替え列を追加', self._fields, self.refresh, ordered=True)
        self.null_position = _dropdown('NULLの位置', [('末尾', 'last'), ('先頭', 'first')], value='last')
        self.reset_index = widgets.Checkbox(description='インデックスを0から振り直す', value=True, indent=False)
        settings = self.controls(self.null_position, self.reset_index)
        self.root.children = (self.rules.root, settings, self.status)

    def _fields(self):
        return (_dropdown('対象列', _choices(self.columns)),
                _dropdown('並べ替え順', [('昇順', True), ('降順', False)], value=True))

    def settings(self):
        keys = [{'column': row.children[0].value, 'ascending': row.children[1].value}
                for row in self.rules.rows.children]
        columns = [key['column'] for key in keys]
        if None in columns:
            return None
        if len(set(columns)) != len(columns):
            raise ValueError('並べ替え列は重複なく指定してください。')
        return {'keys': keys, 'na_position': self.null_position.value, 'reset_index': self.reset_index.value}


class AggregateEditor(TableEditor):
    def __init__(self, source, on_change):
        super().__init__(source, on_change)
        self._sample = source.head(MAX_ROWS).copy()
        self.groups = widgets.SelectMultiple(description='グループ化列', options=list(self.columns),
                                             rows=4, layout=widgets.Layout(width='auto'))
        self.groups.style.description_width = 'initial'
        self.preview = widgets.HTML()
        self.preview.add_class('zizai-aggregate-preview')
        self._owned.append(self.preview)
        self.rules = SettingRows('集計列を追加', self._fields, self.refresh)
        self.root.children = (self.controls(self.groups), self.rules.root, self.status, self.preview)

    def _fields(self):
        return (_dropdown('集計列', _choices(self.columns)),
                _dropdown('集計方法', [('選択してください', None),
                                     *((label, method) for method, label in AGGREGATIONS.items())]))

    def settings(self):
        rows = [{'column': row.children[0].value, 'method': row.children[1].value}
                for row in self.rules.rows.children]
        if any(None in row.values() for row in rows):
            return None
        return {'groups': list(self.groups.value), 'aggregations': rows}

    def show_preview(self, settings):
        if not settings:
            self.preview.value = ''
            return
        preview = aggregate_sample(self._sample, settings).to_html(index=False, escape=True, border=0, na_rep='')
        self.preview.value = f'<p>入力の先頭{len(self._sample)}行で集計した結果</p>{preview}'


class CombineEditor(TableEditor):
    def __init__(self, source, candidates, on_change):
        super().__init__(source, on_change)
        self._candidates = candidates
        self._right_columns = {}
        self._right_error = ''
        self.right = _dropdown('右のDataFrame', _choices(candidates))
        self.kind = _dropdown('結合方法', [(label, key) for key, label in {**JOIN_TYPES, **SET_OPERATIONS}.items()],
                              value='inner')
        self.columns_used = widgets.SelectMultiple(description='共通列', rows=4, layout=widgets.Layout(width='auto'))
        self.columns_used.style.description_width = 'initial'
        self._owned.append(self.columns_used)
        self.rules = SettingRows('結合キーを追加', self._fields, self.refresh)
        self.options_row = widgets.HBox([self.right, self.kind],
                                       layout=widgets.Layout(flex_flow='row wrap', align_items='flex-end'))
        self.options_row.add_class('zizai-table-step-row')
        self._owned.extend([self.right, self.kind, self.options_row])
        self.right.observe(self._change_right, names='value')
        self.kind.observe(self._show_settings, names='value')
        self.columns_used.observe(self.refresh, names='value')
        self._show_settings()

    def _fields(self):
        return (_dropdown('左のキー', _choices(self.columns)),
                _dropdown('右のキー', _choices(self._right_columns)))

    def _change_right(self, _change):
        self._updating = True
        try:
            self._right_error = ''
            try:
                right_frame = self._candidates.get(self.right.value)
                self._right_columns = column_names(right_frame) if right_frame is not None else {}
            except ValueError as error:
                self._right_columns = {}
                self._right_error = str(error)
            for row in self.rules.rows.children:
                _set_choices(row.children[1], _choices(self._right_columns))
            common = [name for name, label in self.columns.items()
                      if name in self._right_columns and label in right_frame.columns]
            self.columns_used.options = common
            self.columns_used.value = tuple(common) if len(common) == len(self.columns) == len(self._right_columns) else ()
        finally:
            self._updating = False
        self.refresh()

    def _show_settings(self, _change=None):
        fields = self.rules.root if self.kind.value in JOIN_TYPES else self.columns_used
        self.root.children = (self.options_row, fields, self.status)
        self.refresh()

    def settings(self):
        if self._right_error:
            raise ValueError(self._right_error)
        if not self.right.value:
            return None
        settings = {'right': self.right.value, 'kind': self.kind.value,
                    'right_lookup': any(not isinstance(label, str) for label in self._right_columns.values())}
        if self.kind.value in JOIN_TYPES:
            keys = [{'left': row.children[0].value, 'right': row.children[1].value}
                    for row in self.rules.rows.children]
            if any(None in key.values() for key in keys):
                return None
            if any(len({key[side] for key in keys}) != len(keys) for side in ('left', 'right')):
                raise ValueError('左右それぞれの結合キーを重複なく指定してください。')
            settings['keys'] = keys
        else:
            if not self.columns_used.options:
                raise ValueError('左右のDataFrameに同名の列が必要です。')
            if not self.columns_used.value:
                raise ValueError('左右で一致させる列を選択してください。')
            selected = set(self.columns_used.value)
            settings['columns'] = [name for name in self.columns if name in selected]
        return settings


class MultiColumnDropdown:
    def __init__(self, label, columns, on_change):
        self.label = label
        self._columns = tuple(columns)
        self._on_change = on_change
        self.heading = widgets.Label(value=label)
        self.heading.add_class('widget-label')
        self.heading.add_class('zizai-column-picker-label')
        self.toggle = widgets.ToggleButton(
            description='選択してください', icon='chevron-down', tooltip=f'{label}を選択',
            layout=widgets.Layout(width='100%'))
        self.toggle.add_class('zizai-column-picker-toggle')
        self.options = widgets.VBox(layout=widgets.Layout(width='100%', display='none'))
        self.options.add_class('zizai-column-picker-options')
        self.root = widgets.VBox([self.heading, self.toggle])
        self.root.add_class('zizai-column-picker')
        self.toggle.observe(self._toggle, names='value')

    @property
    def value(self):
        return tuple(option.description for option in self.options.children if option.value)

    def _toggle(self, change):
        is_open = change['new']
        if is_open and not self.options.children:
            options = [widgets.Checkbox(description=column, indent=False, layout=widgets.Layout(width='100%'))
                       for column in self._columns]
            for option in options:
                option.observe(self._summarize, names='value')
            self.options.children = tuple(options)
        if is_open:
            self.root.add_class('zizai-column-picker-open')
        else:
            self.root.remove_class('zizai-column-picker-open')
        self.options.layout.display = '' if is_open else 'none'
        self.toggle.icon = 'chevron-up' if is_open else 'chevron-down'

    def _summarize(self, _change):
        choices = self.value
        if len(choices) == 1:
            self.toggle.description = choices[0]
        elif choices:
            self.toggle.description = f'{len(choices)}列を選択'
        else:
            self.toggle.description = '選択してください'
        self.toggle.tooltip = f'{self.label}　{"、".join(choices)}' if choices else f'{self.label}を選択'
        self._on_change()

    def close(self):
        _close_widgets([*self.options.children, self.options, self.heading, self.toggle, self.root])


class ReshapeMenuRow(widgets.HBox):
    _view_name = Unicode('ReshapeMenuView').tag(sync=True)
    _view_module = Unicode('zizai-row-preview').tag(sync=True)
    _view_module_version = Unicode('1.0.0').tag(sync=True)


class ReshapeEditor(TableEditor):
    def __init__(self, source, on_change):
        super().__init__(source, on_change)
        self._sample = source.head(MAX_ROWS).copy()
        self.mode = _dropdown('操作', [('ピボット', 'pivot'), ('アンピボット', 'unpivot')], value='pivot')
        self.keep = MultiColumnDropdown('残す列', self.columns, self.refresh)
        self.pivot_by = MultiColumnDropdown('ピボットする列', self.columns, self.refresh)
        self.measures = MultiColumnDropdown('集計列', self.columns, self.refresh)
        self.unpivot_by = MultiColumnDropdown('アンピボットする列', self.columns, self.refresh)
        self.pickers = (self.keep, self.pivot_by, self.measures, self.unpivot_by)
        self.method = _dropdown('集計方法', [('集計なし', 'none'),
                                          *((label, method) for method, label in AGGREGATIONS.items())], value='none')
        self.key_name = widgets.Text(description='キー名', value='項目', layout=widgets.Layout(width='auto'))
        self.value_name = widgets.Text(description='バリュー名', value='値', layout=widgets.Layout(width='auto'))
        for field in (self.key_name, self.value_name):
            field.style.description_width = 'initial'
        self.preview = widgets.HTML()
        self.preview.add_class('zizai-aggregate-preview')
        self.preview.add_class('zizai-reshape-preview')
        self.results = widgets.VBox([self.status, self.preview])
        self.results.add_class('zizai-reshape-results')
        self.settings_row = widgets.Box(layout=widgets.Layout(width='100%'))
        self.settings_row.add_class('zizai-reshape-settings')
        self.menu_row = ReshapeMenuRow(layout=widgets.Layout(width='100%', display='none'))
        self.menu_row.add_class('zizai-reshape-menu')
        self.root.add_class('zizai-reshape-editor')
        self._owned.extend([self.mode, self.method, self.key_name, self.value_name, self.preview,
                            self.results, self.settings_row, self.menu_row])
        for picker in self.pickers:
            picker.toggle.observe(self._show_picker, names='value')
        for field in (self.method, self.key_name, self.value_name):
            field.observe(self.refresh, names='value')
        self.mode.observe(self._show_mode, names='value')
        self.root.children = (self.settings_row, self.results, self.menu_row)
        self._show_mode()

    def _show_picker(self, change):
        selected = next(picker for picker in self.pickers if picker.toggle is change['owner'])
        if change['new']:
            for picker in self.pickers:
                if picker is not selected:
                    picker.toggle.value = False
            self.menu_row.children = (selected.options,)
            self.menu_row.layout.display = ''
        elif self.menu_row.children == (selected.options,):
            self.menu_row.children = ()
            self.menu_row.layout.display = 'none'

    def _show_mode(self, _change=None):
        for picker in self.pickers:
            picker.toggle.value = False
        if self.mode.value == 'pivot':
            rest = (self.pivot_by.root, self.measures.root, self.method)
        else:
            rest = (self.unpivot_by.root, self.key_name, self.value_name)
        self.settings_row.children = (self.mode, self.keep.root, *rest)
        self.refresh()

    def settings(self):
        keep = list(self.keep.value)
        if self.mode.value == 'pivot':
            pivot_by, values = list(self.pivot_by.value), list(self.measures.value)
            if not (keep and pivot_by and values):
                return None
            return {'mode': 'pivot', 'keep': keep, 'pivot_by': pivot_by,
                    'values': values, 'method': None if self.method.value == 'none' else self.method.value}
        columns = list(self.unpivot_by.value)
        if not columns:
            return None
        return {'mode': 'unpivot', 'keep': keep, 'unpivot_by': columns,
                'key_name': self.key_name.value.strip(), 'value_name': self.value_name.value.strip()}

    def show_preview(self, settings):
        if not settings:
            self.preview.value = ''
            return
        result = reshape_sample(self._sample, settings)
        caption = f'入力の先頭{len(self._sample)}行を変換した結果'
        if len(result) > MAX_ROWS:
            caption += f'（先頭{MAX_ROWS}行を表示）'
        preview = result.head(MAX_ROWS).to_html(index=False, escape=True, border=0, na_rep='')
        self.preview.value = f'<p>{caption}</p>{preview}'

    def close(self):
        for picker in self.pickers:
            picker.close()
        super().close()


def create_table_editor(kind, source, on_change, *, candidates):
    if kind == COMBINE_FRAMES:
        return CombineEditor(source, candidates, on_change)
    return {SORT_ROWS: SortEditor, AGGREGATE_ROWS: AggregateEditor, RESHAPE_ROWS: ReshapeEditor}[kind](source, on_change)
