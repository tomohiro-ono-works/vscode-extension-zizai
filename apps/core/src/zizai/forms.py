"""Notebook output forms. Import does not register magics or open any windows."""
from html import escape
from importlib import import_module
from importlib.resources import files
from importlib.util import find_spec
import json
from keyword import iskeyword
from pathlib import Path
import shlex
from .connector_codegen import module_name_for
from .dataintegration_codegen import DATAFRAME_OPERATIONS, ROW_OPERATIONS, VALUE_OPERATIONS
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
    import sys
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
        self._dynamic = []
        self.result = ''
        self.field_widgets = {}
        self.browse_buttons = {}
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
        self.generate_button.disabled = not ready or bool(self._invalid_fields)

    def _connector_changed(self, change):
        if not self._syncing:
            self.model.set_connector(change['new'])
            self._sync()

    def _action_changed(self, change):
        if not self._syncing:
            self.model.set_action(change['new'])
            self._sync()

    def _sync(self):
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
            dataframe_mode = self._has_dataframe_editor()
            self.root.layout.max_width = 'none' if dataframe_mode else self._form_width
            for name, field in self.model.fields.items():
                value = self.model.values[name]
                label = escape(field['label']) + (' <span class="zizai-required">*</span>' if field.get('required') else '')
                if dataframe_mode and name == 'operations':
                    self.model.set_value(name, '')
                    continue
                if dataframe_mode and name == 'input_variable':
                    options = [('選択してください', '')] + [(name, name) for name in self._dataframe_names()]
                    if value not in dict(options).values():
                        value = ''
                        self.model.set_value(name, value)
                    widget = widgets.Dropdown(description=label, options=options, value=value)
                elif field['type'] == 'choice':
                    widget = widgets.Dropdown(description=label, options=[('選択してください', None)] + [(x, x) for x in field['choices']], value=value)
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
            pairs = [('encoding', 'delimiter')]
            if dataframe_mode:
                pairs.append(('input_variable', 'output_variable'))
            if (self.model.connector, self.model.action) in {
                ('csv', 'import'), ('excel', 'read_excel'), ('excel', 'read_excel_range'),
            }:
                pairs.extend([('output_variable', 'chunk_size'), ('header_row', 'data_start_row')])
            paired_fields = {left: right for left, right in pairs if left in self.field_widgets and right in self.field_widgets}
            for name, widget in self.field_widgets.items():
                if name in self.browse_buttons:
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
                elif name in paired_fields:
                    pair = [widget, self.field_widgets[paired_fields[name]]]
                    for item in pair:
                        item.layout.flex = '1 1 240px'
                        item.layout.min_width = '0'
                    row = widgets.HBox(pair, layout=widgets.Layout(flex_flow='row wrap', width='100%'))
                    row.add_class('zizai-pair')
                    self._dynamic.append(row)
                    rows.append(row)
                elif name not in paired_fields.values():
                    rows.append(widget)
            if dataframe_mode:
                self._dataframe_slot = widgets.VBox()
                self._dynamic.append(self._dataframe_slot)
                rows.append(self._dataframe_slot)
                self._show_dataframe_editor(self.model.values['input_variable'])
            self.details.children = rows
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
        if name == 'input_variable' and self._dataframe_slot is not None:
            self.model.set_value('operations', '')
            self._show_dataframe_editor(value)
        if name == 'file_path' and self.row_preview_button is not None:
            self.row_preview_button.disabled = not value.strip() or name in self._invalid_fields
        if self._invalid_fields:
            self.message.value = '入力値を確認してください。ファイルとフォルダーは絶対パスを指定します。'
        else:
            self.message.value = ''
            if self._dataframe_slot is None or self.model.values['operations']:
                try:
                    self.model.generate()
                except ValueError as error:
                    self.message.value = escape(str(error))
        self._refresh_generate()

    def _has_dataframe_editor(self):
        action = self.model.actions.get(self.model.action, {})
        return action.get('generation') in DATAFRAME_OPERATIONS

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
        path = self.model.definition['connectors'][self.model.connector].get('module_path')
        try:
            module = module_name_for(path)
            spec = find_spec(module)
            if spec is None or spec.origin is None or Path(spec.origin).resolve() != Path(path).resolve():
                raise ValueError('設定したデータ統合コネクタをカーネルに登録してください。')
            generation = self.model.actions[self.model.action]['generation']
            apply_operations = getattr(import_module(module), DATAFRAME_OPERATIONS[generation], None)
            if not callable(apply_operations):
                raise ValueError('データ統合コネクタを更新し、カーネルを再起動してください。')
            if generation == VALUE_OPERATIONS:
                from .value_editor import ValueEditor as editor_class
            elif generation == ROW_OPERATIONS:
                from .row_filter_editor import RowFilterEditor as editor_class
            else:
                from .column_editor import ColumnEditor as editor_class
            self._dataframe_editor = editor_class(self._namespace[name], apply_operations, self._set_dataframe_operations)
        except (ImportError, TypeError, ValueError, KeyError, OSError) as error:
            self._dataframe_slot.children = (widgets.HTML(f'<p role="alert">{escape(str(error))}</p>'),)
            return
        self._dataframe_slot.children = (self._dataframe_editor.root,)

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

    def _generate(self, _):
        if self._invalid_fields:
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
        self._dismiss_row_preview()
        self._close_dataframe_editor()
        for widget in [*self._dynamic, self.connector, self.action, self.generate_button, self.copy_button,
                       self.toolbar, self.details, self.message, self.generated, self.code_actions, self.root]:
            widget.close()
        self.styles.close()


def create_form(config_path=None, *, folder_picker=None, clipboard_writer=None, namespace=None):
    """Return a controller with .root, .model and .result for explicit Python use."""
    if namespace is None:
        from IPython import get_ipython
        shell = get_ipython()
        namespace = shell.user_ns if shell is not None else None
    return NotebookForm(load_definition(config_path), folder_picker=folder_picker, clipboard_writer=clipboard_writer,
                        namespace=namespace)


def show_form(config_path=None):
    """Display in the current cell output; do not insert or run notebook cells."""
    from IPython.display import display
    display(create_form(config_path).root)


def load_ipython_extension(ipython):
    """Register %form only when the user explicitly loads this extension."""
    from IPython.core.magic import Magics, magics_class, line_magic
    existing = ipython.find_line_magic('form')
    if existing:
        if getattr(getattr(existing, '__self__', None), '_zizai_form_magic', False):
            return
        raise ValueError('別の%formが登録済みのため上書きしません。')

    @magics_class
    class FormMagics(Magics):
        _zizai_form_magic = True

        @line_magic
        def form(self, line):
            args = shlex.split(line)
            if len(args) > 1:
                raise ValueError('%form または %form "設定ファイルのパス" を指定してください。')
            show_form(args[0] if args else None)

    ipython.register_magics(FormMagics)
