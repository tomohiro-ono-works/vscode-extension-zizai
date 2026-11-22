"""Notebook output forms. Import does not register magics or open any windows."""
from asyncio import get_running_loop
from html import escape
from importlib import import_module
from importlib.resources import files
from importlib.util import find_spec
import json
from keyword import iskeyword
from pathlib import Path
import shlex
import sys
from .connector_codegen import module_name_for
from .connector_forms.dataintegration.dataintegration_codegen import COLUMN_OPERATIONS, DATAFRAME_OPERATIONS, ROW_OPERATIONS, VALUE_OPERATIONS
from .connector_forms.dataintegration.pandas_table_codegen import TABLE_ACTIONS
from .connector_forms.slides.slides_codegen import CONVERSION as SLIDES_CONVERSION
from .connector_forms.vector.collection_names import _vector_collection_names
from .connector_forms.vector.vector_codegen import BUILD as VECTOR_BUILD, CORRECTION_FIELDS, SEARCH as VECTOR_SEARCH
from .connector_forms.windows.cursor import _read_cursor_position
from .form_definition import load_definition
from .form_model import FormModel


_ROW_PREVIEW_FIELDS = {
    ('csv', 'import'): {'encoding': 'choice', 'delimiter': 'text'},
    ('excel', 'read_excel'): {'sheet_name': 'text'},
}


def _show_native_picker(choose, **options):
    # A user button opens a local OS dialog; never called during import/display.
    import tkinter as tk
    root = tk.Tk()
    try:
        root.withdraw()
        root.attributes('-topmost', True)
        root.update_idletasks()
        return choose(parent=root, **options)
    finally:
        root.destroy()


def _select_folder(current):
    from tkinter.filedialog import askdirectory
    return _show_native_picker(askdirectory, title='フォルダーを選択',
                               initialdir=current if current and Path(current).is_absolute() else None)


def _select_file(current, extension):
    from tkinter.filedialog import askopenfilename
    path = Path(current)
    absolute = path.is_absolute()
    patterns = [(extension.upper().lstrip('.') + 'ファイル', '*' + extension)] if extension else []
    patterns.append(('すべてのファイル', '*'))
    return _show_native_picker(askopenfilename, title='ファイルを選択', filetypes=patterns,
                               initialdir=str(path.parent) if absolute else None,
                               initialfile=path.name if absolute else None)


def _copy_to_clipboard(text):
    if sys.platform == 'win32':
        # Use persistent Windows text storage rather than a temporary Tk owner.
        # The command is fixed; generated code is stdin data, never shell code.
        import os
        from pathlib import Path
        import subprocess
        powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        command = "$ErrorActionPreference='Stop';[Console]::InputEncoding=[Text.UTF8Encoding]::new($false);Set-Clipboard -Value ([Console]::In.ReadToEnd())"
        subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-STA', '-Command', command],
                       input=text, encoding='utf-8', capture_output=True, check=True, shell=False,
                       timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        return
    # Preserve the existing Tk path outside the current Windows target.
    import tkinter as tk
    root = tk.Tk()
    try:
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
    finally:
        root.destroy()


class NotebookForm:
    def __init__(self, definition, *, folder_picker=None, clipboard_writer=None, namespace=None):
        import ipywidgets as widgets
        self._widgets = widgets
        self.model = FormModel(definition)
        self._folder_picker = folder_picker or _select_folder
        self._clipboard_writer = clipboard_writer or _copy_to_clipboard
        self._namespace = {} if namespace is None else namespace
        self._syncing = False
        self._invalid_fields = set()
        self._slide_file_row = None
        self._dynamic = []
        self.result = ''
        self.field_widgets = {}
        self.browse_buttons = {}
        self.cursor_capture_button = None
        self._cursor_capture_timer = None
        self.row_preview_button = None
        self._row_preview = None
        self._dataframe_editor = None
        self._dataframe_slot = None
        layout = lambda: widgets.Layout(flex='1 1 180px', min_width='150px')
        self.connector = widgets.Dropdown(description='コネクタ', options=[('選択してください', None)] + [
            (entry['label'], key) for key, entry in definition['connectors'].items()], layout=layout())
        self.action = widgets.Dropdown(description='アクション', options=[('選択してください', None)], disabled=True, layout=layout())
        self.generate_button = widgets.Button(description='コード生成', disabled=True, button_style='primary')
        self.generate_button.add_class('zizai-generate')
        self.copy_button = widgets.Button(description='コードをコピー', disabled=True, icon='copy')
        self.copy_button.add_class('zizai-copy')
        self.code_actions = widgets.HBox([self.generate_button, self.copy_button],
                                         layout=widgets.Layout(flex_flow='row wrap'))
        self.code_actions.add_class('zizai-code-actions')
        self.toolbar = widgets.HBox(layout=widgets.Layout(display='flex', flex_flow='row wrap', align_items='center'))
        self.toolbar.add_class('zizai-toolbar')
        self.details = widgets.VBox()
        self.details.add_class('zizai-details')
        self.message = widgets.HTML()
        self.generated = widgets.HTML()
        css = files('zizai').joinpath('form.css').read_text(encoding='utf-8')
        self.styles = widgets.HTML('<style>' + css + '</style>', layout=widgets.Layout(display='none'))
        self._form_children = (self.styles, self.toolbar, self.details, self.message, self.generated, self.code_actions)
        self.root = widgets.VBox(self._form_children,
                                 layout=widgets.Layout(width='100%', max_width='880px'))
        self._form_width = self.root.layout.max_width
        self.root.add_class('zizai-form')
        self.connector.observe(self._connector_changed, names='value')
        self.action.observe(self._action_changed, names='value')
        self.generate_button.on_click(self._generate)
        self.copy_button.on_click(self._copy_code)
        self._sync()

    def _clear_result(self):
        self.result = ''
        self.generated.value = ''
        self.copy_button.disabled = True

    def _refresh_generate(self):
        try:
            self.model.generate()
            ready = True
        except ValueError:
            ready = False
        self.generate_button.disabled = not ready or bool(self._relevant_invalid_fields())

    def _relevant_invalid_fields(self):
        if self._slide_file_row is None:
            return self._invalid_fields
        hidden = 'markdown_text' if self.model.values['input_mode'] == 'file' else 'markdown_file'
        return self._invalid_fields - {hidden}

    def _connector_changed(self, change):
        if not self._syncing:
            self.model.set_connector(change['new'])
            self._sync()

    def _action_changed(self, change):
        if not self._syncing:
            self.model.set_action(change['new'])
            self._sync()

    def _sync(self):
        self._cancel_cursor_capture()
        self.cursor_capture_button = None
        self._dismiss_row_preview()
        self._close_dataframe_editor()
        self._dataframe_slot = None
        widgets = self._widgets
        self._syncing = True
        try:
            options = [('選択してください', None)] + [
                (entry['label'], key) for key, entry in self.model.actions.items()]
            if self.action.options != tuple(options):
                # A queued frontend index belongs to the old candidate list.
                # Give the new list its own comm rather than reinterpreting it.
                previous = self.action
                self.action = widgets.Dropdown(description='アクション', options=options,
                                               value=self.model.action, layout=previous.layout)
                self.action.observe(self._action_changed, names='value')
                previous.close()
            self.action.value = self.model.action
            self.action.disabled = not bool(self.model.actions)
            for widget in self._dynamic:
                widget.close()
            self._dynamic = []
            self.field_widgets = {}
            self.browse_buttons = {}
            self.row_preview_button = None
            self._invalid_fields.clear()
            self._slide_file_row = None
            dataframe_mode = self._has_dataframe_editor()
            generation = self.model.actions.get(self.model.action, {}).get('generation')
            slides = generation == SLIDES_CONVERSION
            vector_build = generation == VECTOR_BUILD
            vector_search = generation == VECTOR_SEARCH
            self.root.layout.max_width = 'none' if dataframe_mode else self._form_width
            for name, field in self.model.fields.items():
                value = self.model.values[name]
                label = escape(field['label']) + (' <span class="zizai-required">*</span>' if field.get('required') else '')
                if dataframe_mode and name == 'operations':
                    self.model.set_value(name, '')
                    continue
                if vector_search and name == 'include_vector':
                    continue  # Older connector definitions may still declare the former checkbox.
                if vector_search and name == 'collection_name':
                    widget = self._vector_collection_picker(self.model.values['db_folder'], label)
                elif vector_search and name == 'batch_search':
                    widget = widgets.ToggleButtons(options=[('検索文', False), ('DataFrameで検索', True)],
                                                    value=value, style={'button_width': 'auto'})
                    widget.add_class('zizai-batch-toggle')
                elif vector_search and name == 'query_column':
                    widget = self._vector_column_picker(name, label, source_field='query_input_variable')
                elif vector_build and name in {'id_column', 'text_column'}:
                    widget = self._vector_column_picker(name, label)
                elif ((dataframe_mode or vector_build) and name == 'input_variable'
                      or vector_search and name == 'query_input_variable'):
                    options = [('選択してください', '')] + [(name, name) for name in self._dataframe_names()]
                    if value not in dict(options).values():
                        value = ''
                        self.model.set_value(name, value)
                    widget = widgets.Dropdown(description=label, options=options, value=value)
                elif slides and name == 'input_mode':
                    widget = widgets.ToggleButtons(description=label, options=[('直接入力', 'text'), ('ファイル指定', 'file')],
                                                    value=value, style={'button_width': 'auto'})
                    widget.add_class('zizai-batch-toggle')
                elif field['type'] == 'choice':
                    placeholder = ('既存DBのモデルを使用（新規は130m）'
                                   if vector_build and name == 'model_name' else '選択してください')
                    options = [(placeholder, None), *((choice, choice) for choice in field['choices'])]
                    widget = widgets.Dropdown(description=label, options=options, value=value)
                elif field['type'] == 'integer':
                    widget = widgets.IntText(description=label, value=value)
                    widget.add_class('zizai-integer')
                elif field['type'] == 'textarea':
                    widget = widgets.Textarea(description=label, value=value, rows=5, continuous_update=True)
                    widget.add_class('zizai-textarea')
                elif field['type'] == 'checkbox':
                    widget = widgets.Checkbox(description=label, value=value, indent=False)
                else:
                    widget = widgets.Text(description=label, value=value, continuous_update=True)
                widget.layout.width = 'auto'
                widget.description_allow_html = True
                widget.style.description_width = 'initial'
                widget.observe(lambda change, key=name: self._value_changed(key, change['new']), names='value')
                self.field_widgets[name] = widget
                self._dynamic.append(widget)
                if field['type'] in ('file', 'folder'):
                    button = widgets.Button(description='参照…', tooltip=field['label'] + 'を選択',
                                            layout=widgets.Layout(width='85px', flex='0 0 85px'))
                    button.on_click(lambda _, key=name: self._pick_path(key))
                    self.browse_buttons[name] = button
                    self._dynamic.append(button)
            self.toolbar.children = [self.connector, self.action]
            rows = []
            query_switch = self.field_widgets.get('batch_search') if vector_search else None
            pairs = [('encoding', 'delimiter'), ('wait_before_seconds', 'wait_after_seconds')]
            if self.model.connector == 'windows':
                pairs.append(('x', 'y'))
            if dataframe_mode:
                pairs.append(('input_variable', 'output_variable'))
            if vector_build:
                pairs.extend([('input_variable', 'output_variable'), ('id_column', 'text_column')])
            if vector_search:
                pairs.extend([('collection_name', 'search_mode'), ('output_variable', 'top_k')])
                pairs.append(('query_input_variable', 'query_column'))
            if (self.model.connector, self.model.action) in {
                ('csv', 'import'), ('excel', 'read_excel'), ('excel', 'read_excel_range'),
            }:
                pairs.extend([('output_variable', 'chunk_size'), ('header_row', 'data_start_row')])
            paired_fields = {left: right for left, right in pairs if left in self.field_widgets and right in self.field_widgets}
            correction_controls = []
            for name, widget in self.field_widgets.items():
                if vector_build and name in CORRECTION_FIELDS:
                    correction_controls.append(widget)
                elif name == 'query_text' and query_switch is not None:
                    query_switch.layout.align_self = 'flex-start'
                    widget.add_class('zizai-query-text')
                    widget.layout.width = '100%'
                    section = widgets.VBox([query_switch, widget])
                    section.add_class('zizai-query-section')
                    self._dynamic.append(section)
                    rows.append(section)
                elif name in self.browse_buttons:
                    widget.layout.flex = '1 1 0'
                    widget.layout.min_width = '0'
                    controls = [widget, self.browse_buttons[name]]
                    if name == 'file_path' and self._supports_row_preview():
                        button = widgets.Button(description='行を確認', layout=widgets.Layout(width='auto'))
                        button.disabled = not widget.value or not Path(widget.value).is_absolute()
                        button.on_click(self._open_row_preview)
                        self.row_preview_button = button
                        self._dynamic.append(button)
                        controls.append(button)
                    row = widgets.HBox(controls,
                                       layout=widgets.Layout(width='100%', align_items='flex-end'))
                    row.add_class('zizai-folder-row')
                    self._dynamic.append(row)
                    rows.append(row)
                    if slides and name == 'markdown_file':
                        self._slide_file_row = row
                    if slides and name == 'style_path':
                        css = widgets.HTML(self._slide_css_help())
                        self._dynamic.append(css)
                        rows.append(css)
                elif name in paired_fields:
                    pair = [widget, self.field_widgets[paired_fields[name]]]
                    for item in pair:
                        item.layout.flex = '1 1 240px'
                        item.layout.min_width = '0'
                    if name == 'x' and self.model.actions.get(self.model.action, {}).get('generation') == 'windows.mouse_click':
                        button = widgets.Button(description='3秒後に座標取得',
                                                layout=widgets.Layout(width='auto', flex='0 0 auto',
                                                                      align_self='flex-end'))
                        button.on_click(self._schedule_cursor_capture)
                        self.cursor_capture_button = button
                        self._dynamic.append(button)
                        pair.append(button)
                    row = widgets.HBox(pair, layout=widgets.Layout(flex_flow='row wrap', width='100%'))
                    row.add_class('zizai-pair')
                    self._dynamic.append(row)
                    rows.append(row)
                elif name not in paired_fields.values() and widget is not query_switch:
                    rows.append(widget)
            if correction_controls:
                settings = widgets.VBox(correction_controls)
                advanced = widgets.Accordion(children=[settings], selected_index=None)
                advanced.set_title(0, '補正検索の詳細設定')
                self._dynamic.extend([settings, advanced])
                rows.append(advanced)
            if dataframe_mode:
                self._dataframe_slot = widgets.VBox()
                self._dynamic.append(self._dataframe_slot)
                rows.append(self._dataframe_slot)
                self._show_dataframe_editor(self.model.values['input_variable'])
            self.details.children = rows
            if slides:
                self._show_slide_input_mode()
            if vector_search and 'batch_search' in self.field_widgets:
                self._show_vector_query_mode()
            self.message.value = ''
            self._clear_result()
            self._refresh_generate()
        finally:
            self._syncing = False

    def _value_changed(self, name, value):
        if self._syncing:
            return
        if name == 'file_path' and self.row_preview_button is not None:
            self._dismiss_row_preview()
        self._clear_result()
        try:
            self.model.set_value(name, value)
            self._invalid_fields.discard(name)
        except ValueError:
            self._invalid_fields.add(name)
        generation = self.model.actions.get(self.model.action, {}).get('generation')
        if generation == SLIDES_CONVERSION and name == 'input_mode':
            self._show_slide_input_mode()
        if name == 'db_folder' and generation == VECTOR_SEARCH:
            name_field = self.field_widgets['collection_name']
            self._replace_vector_picker('collection_name', self._vector_collection_picker(value, name_field.description))
        if generation == VECTOR_SEARCH:
            if name == 'batch_search':
                self._show_vector_query_mode()
            elif name == 'query_input_variable':
                label = self.field_widgets['query_column'].description
                picker = self._vector_column_picker('query_column', label, source_field=name)
                self._replace_vector_picker('query_column', picker)
        if name == 'input_variable' and generation == VECTOR_BUILD:
            for column_field in ('id_column', 'text_column'):
                label = self.field_widgets[column_field].description
                self._replace_vector_picker(column_field, self._vector_column_picker(column_field, label))
        if name == 'input_variable' and self._dataframe_slot is not None:
            self.model.set_value('operations', '')
            self._show_dataframe_editor(value)
        if name == 'file_path' and self.row_preview_button is not None:
            self.row_preview_button.disabled = not value.strip() or name in self._invalid_fields
        if self._relevant_invalid_fields():
            self.message.value = '入力値を確認してください。ファイルとフォルダーは絶対パスを指定します。'
        else:
            self.message.value = ''
            if self._dataframe_slot is None or self.model.values['operations']:
                try:
                    self.model.generate()
                except ValueError as error:
                    self.message.value = escape(str(error))
        self._refresh_generate()

    def _show_slide_input_mode(self):
        use_file = self.model.values['input_mode'] == 'file'
        self.field_widgets['markdown_text'].layout.display = 'none' if use_file else ''
        self._slide_file_row.layout.display = '' if use_file else 'none'

    def _slide_css_help(self):
        module_path = self.model.definition['connectors']['slides'].get('module_path')
        folder = Path(module_path).parent if module_path else Path('connectors/slides')
        default = folder / 'zizai_slides/assets/slide.css'
        example = folder / 'config/custom.example.css'
        return (f'組み込みCSS <code>{escape(str(default))}</code><br>'
                f'自作CSSのひな形 <code>{escape(str(example))}</code><br>'
                'CSS欄が空でファイルを指定した場合は、Markdownと同名のCSSがあれば使います。')

    def _show_vector_query_mode(self):
        batch = self.model.values['batch_search']
        fields = self.field_widgets
        fields['query_text'].layout.display = 'none' if batch else ''
        row = next(row for row in self.details.children
                   if fields['query_input_variable'] in getattr(row, 'children', ()))
        row.layout.display = '' if batch else 'none'

    def _vector_collection_picker(self, folder, label):
        names = _vector_collection_names(folder)
        current = self.model.values['collection_name']
        selected = current if current in names else (names[0] if len(names) == 1 else '')
        self.model.set_value('collection_name', selected)
        placeholder = ('選択してください' if names else
                       'コレクションがありません' if folder else 'フォルダーを選択してください')
        options = [(placeholder, ''), *((name, name) for name in names)]
        picker = self._widgets.Dropdown(description=label, options=options, value=selected, disabled=not names,
                                        description_allow_html=True)
        picker.style.description_width = 'initial'
        return picker

    def _vector_column_picker(self, name, label, *, source_field='input_variable'):
        source = self.model.values.get(source_field)
        data = self._namespace.get(source)
        labels = getattr(data, 'columns', None)
        if labels is None:
            labels = ()
        elif name == 'query_column':
            labels = labels[~labels.duplicated(keep=False)]
        columns = tuple(dict.fromkeys(column for column in labels
                                      if isinstance(column, str) and column.strip()))
        selected = self.model.values[name]
        if selected not in columns:
            default = self.model.fields[name].get('default')
            selected = default if default in columns else ''
        self.model.set_value(name, selected)
        placeholder = ('選択してください' if columns else
                       '選択できる列がありません' if source else '入力DataFrameを選択してください')
        options = [(placeholder, ''), *((column, column) for column in columns)]
        picker = self._widgets.Dropdown(description=label, options=options, value=selected, disabled=not columns,
                                        description_allow_html=True)
        picker.style.description_width = 'initial'
        return picker

    def _replace_vector_picker(self, name, picker):
        previous = self.field_widgets[name]
        picker.layout = previous.layout
        picker.observe(lambda change: self._value_changed(name, change['new']), names='value')
        row = next(row for row in self.details.children if previous in getattr(row, 'children', ()))
        row.children = tuple(picker if item is previous else item for item in row.children)
        self.field_widgets[name] = picker
        self._dynamic[self._dynamic.index(previous)] = picker
        previous.unobserve_all('value')
        previous.close()

    def _has_dataframe_editor(self):
        action = self.model.actions.get(self.model.action, {})
        generation = action.get('generation')
        return generation in DATAFRAME_OPERATIONS or generation in TABLE_ACTIONS

    def _dataframe_names(self):
        try:
            from pandas import DataFrame
        except ImportError:
            return []
        return sorted(name for name, value in self._namespace.items()
                      if isinstance(name, str) and name.isidentifier() and not iskeyword(name)
                      and isinstance(value, DataFrame))

    def _show_dataframe_editor(self, name):
        self._close_dataframe_editor()
        widgets = self._widgets
        if not name:
            help_text = ('入力DataFrameを選択してください。' if len(self.field_widgets['input_variable'].options) > 1
                         else 'NotebookでDataFrameを作成してから、フォームを再表示してください。')
            self._dataframe_slot.children = (widgets.HTML(f'<p>{help_text}</p>'),)
            return
        try:
            generation = self.model.actions[self.model.action]['generation']
            if generation in TABLE_ACTIONS:
                from .connector_forms.dataintegration.table_action_editor import create_table_editor
                candidates = {candidate: self._namespace[candidate] for candidate in self._dataframe_names()}
                self._dataframe_editor = create_table_editor(
                    generation, self._namespace[name], self._set_dataframe_operations, candidates=candidates)
            else:
                self._dataframe_editor = self._create_connector_editor(name, generation)
        except (ImportError, TypeError, ValueError, KeyError, OSError) as error:
            self._dataframe_slot.children = (widgets.HTML(f'<p role="alert">{escape(str(error))}</p>'),)
            return
        self._dataframe_slot.children = (self._dataframe_editor.root,)

    def _create_connector_editor(self, name, generation):
        path = self.model.definition['connectors'][self.model.connector].get('module_path')
        module = module_name_for(path)
        spec = find_spec(module)
        if spec is None or spec.origin is None or Path(spec.origin).resolve() != Path(path).resolve():
            raise ValueError('設定したデータ統合コネクタをカーネルに登録してください。')
        apply_operations = getattr(import_module(module), DATAFRAME_OPERATIONS[generation], None)
        if not callable(apply_operations):
            raise ValueError('データ統合コネクタを更新し、カーネルを再起動してください。')
        args = self._namespace[name], apply_operations, self._set_dataframe_operations
        if generation == COLUMN_OPERATIONS:
            from .connector_forms.dataintegration.column_editor import ColumnEditor
            return ColumnEditor(*args)
        from .connector_forms.dataintegration.data_operations_editor import DataOperationsEditor
        mode = {VALUE_OPERATIONS: 'value', ROW_OPERATIONS: 'condition'}.get(generation)
        return DataOperationsEditor(*args, mode=mode)

    def _set_dataframe_operations(self, operations):
        self._value_changed('operations', json.dumps(operations, ensure_ascii=False) if operations else '')

    def _close_dataframe_editor(self):
        if self._dataframe_slot is not None:
            previous = self._dataframe_slot.children
            self._dataframe_slot.children = ()
            if self._dataframe_editor is not None:
                self._dataframe_editor.close()
                self._dataframe_editor = None
            else:
                for widget in previous:
                    widget.close()

    def _supports_row_preview(self):
        settings = _ROW_PREVIEW_FIELDS.get((self.model.connector, self.model.action))
        if settings is None or self.model.is_placeholder:
            return False
        fields = dict(settings, file_path='file', header_row='integer', data_start_row='integer')
        return all(self.model.fields.get(name, {}).get('type') == kind for name, kind in fields.items())

    def _open_row_preview(self, button):
        if button is not self.row_preview_button or button.disabled or self._row_preview is not None:
            return
        from .row_preview import RowPreview
        try:
            self._row_preview = RowPreview(self, Path(self.field_widgets['file_path'].value))
        except Exception as error:
            self.message.value = '<p role="alert">行のプレビューを開けません。' + escape(str(error)) + '</p>'
            return
        self.root.layout.max_width = 'none'
        self.root.children = (self.styles, self._row_preview.root)

    def _dismiss_row_preview(self):
        if self._row_preview is not None:
            preview, self._row_preview = self._row_preview, None
            self.root.layout.max_width = self._form_width
            self.root.children = self._form_children
            preview.close()

    def _pick_path(self, name):
        field = self.model.fields[name]
        widget = self.field_widgets[name]
        is_file = field['type'] == 'file'
        try:
            selected = (_select_file(widget.value, field.get('extension')) if is_file
                        else self._folder_picker(widget.value))
            if selected:  # Cancellation preserves the existing value and result.
                widget.value = selected
        except Exception as error:
            kind = 'ファイル' if is_file else 'フォルダー'
            self.message.value = kind + '選択を開けません。ローカルPythonのTk環境を確認してください。(' + escape(type(error).__name__) + ')'

    def _schedule_cursor_capture(self, button):
        if button is not self.cursor_capture_button or self._cursor_capture_timer is not None:
            return
        try:
            self._cursor_capture_timer = get_running_loop().call_later(3, self._capture_cursor, button)
        except RuntimeError:
            self.message.value = '座標取得にはNotebookのカーネルが必要です。'
            return
        button.disabled = True
        button.description = '取得中…'
        self.message.value = '取得したい位置にマウスを移動してください。'

    def _capture_cursor(self, button):
        if button is not self.cursor_capture_button or self._cursor_capture_timer is None:
            return
        self._cursor_capture_timer = None
        button.description = '3秒後に座標取得'
        button.disabled = False
        try:
            x, y = _read_cursor_position()
        except OSError:
            self.message.value = '座標を取得できません。ローカルWindowsの画面で試してください。'
            return
        self.field_widgets['x'].value = str(x)
        self.field_widgets['y'].value = str(y)
        self.field_widgets['coordinate_mode'].value = '座標指定'
        self.message.value = f'座標を取得しました。X = {x}、Y = {y}'

    def _cancel_cursor_capture(self):
        if self._cursor_capture_timer is not None:
            self._cursor_capture_timer.cancel()
            self._cursor_capture_timer = None

    def _generate(self, _):
        if self._relevant_invalid_fields():
            return
        try:
            self.result = self.model.generate()
        except ValueError as error:
            self._clear_result()
            self.message.value = escape(str(error))
            return
        self.message.value = ''
        label = '生成結果（仮表示・実行可能なPythonコードではありません）' if self.model.is_placeholder else '生成コード'
        self.generated.value = '<p><b>' + label + '</b></p><pre style="white-space:pre-wrap;user-select:text;overflow:auto;max-height:320px"><code class="language-python">' + escape(self.result) + '</code></pre>'
        self.copy_button.disabled = self.model.is_placeholder

    def _copy_code(self, _):
        if self.copy_button.disabled or not self.result:
            return
        try:
            self._clipboard_writer(self.result)
            self.message.value = 'コードをコピーしました。'
        except Exception as error:
            self.message.value = 'コピーできません。コード欄を選択してコピーしてください。(' + escape(type(error).__name__) + ')'

    def close(self):
        self._cancel_cursor_capture()
        self._dismiss_row_preview()
        self._close_dataframe_editor()
        for widget in [*self._dynamic, self.connector, self.action, self.generate_button, self.copy_button,
                       self.toolbar, self.details, self.message, self.generated, self.code_actions, self.root]:
            widget.close()
        self.styles.close()


def create_form(config_path=None, *, folder_picker=None, clipboard_writer=None, namespace=None, connector=None):
    """Return a controller with .root, .model and .result for explicit Python use."""
    if namespace is None:
        from IPython import get_ipython
        shell = get_ipython()
        namespace = shell.user_ns if shell is not None else None
    definition = load_definition(config_path)
    if connector is not None and connector not in definition['connectors']:
        raise ValueError(f'{connector} コネクタを共通フォルダーに登録してください。')
    form = NotebookForm(definition, folder_picker=folder_picker, clipboard_writer=clipboard_writer, namespace=namespace)
    if connector is not None:
        form.connector.value = connector
    return form


def show_form(config_path=None, *, connector=None):
    """Display in the current cell output; do not insert or run notebook cells."""
    from IPython.display import display
    display(create_form(config_path, connector=connector).root)


def load_ipython_extension(ipython):
    """Register the ZizAI magic and its compatibility name on explicit load."""
    from IPython.core.magic import Magics, line_cell_magic, line_magic, magics_class, no_var_expand

    connectors = ('zizai_bq', 'zizai_duck', 'zizai_csv', 'zizai_excel')
    existing = {
        **{f'%{name}': ipython.find_line_magic(name) for name in ('zizai_form', 'form', *connectors)},
        **{f'%%{name}': ipython.find_cell_magic(name) for name in connectors},
    }
    for name, magic in existing.items():
        if magic and not getattr(getattr(magic, '__self__', None), '_zizai_form_magic', False):
            raise ValueError(f'別の{name}が登録済みのため上書きしません。')
    if all(existing.values()):
        return

    @magics_class
    class FormMagics(Magics):
        _zizai_form_magic = True

        @line_magic
        def zizai_form(self, line):
            args = shlex.split(line)
            if len(args) > 1:
                raise ValueError('%zizai_form または %zizai_form "設定ファイルのパス" を指定してください。')
            show_form(args[0] if args else None)

        @line_magic
        def form(self, line):
            return self.zizai_form(line)

        def _connector_form(self, connector, line, cell=None):
            if line.strip() or (cell and any(
                    entry.strip() and not entry.lstrip().startswith('#') for entry in cell.splitlines())):
                raise ValueError('フォーム表示には引数やコードを指定しないでください。')
            show_form(connector=connector)

        @line_cell_magic
        @no_var_expand
        def zizai_bq(self, line, cell=None):
            if cell is None:
                return self._connector_form('bigquery', line)
            from .sql_magic import run_sql_cell
            return run_sql_cell('bigquery', line, cell, self.shell.user_ns)

        @line_cell_magic
        @no_var_expand
        def zizai_duck(self, line, cell=None):
            if cell is None:
                return self._connector_form('duckdb', line)
            from .sql_magic import run_sql_cell
            return run_sql_cell('duckdb', line, cell, self.shell.user_ns)

        @line_cell_magic
        def zizai_csv(self, line, cell=None):
            return self._connector_form('csv', line, cell)

        @line_cell_magic
        def zizai_excel(self, line, cell=None):
            return self._connector_form('excel', line, cell)

    ipython.register_magics(FormMagics)
