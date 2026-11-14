"""Notebook output forms. Import does not register magics or open any windows."""
from html import escape
import shlex
from .form_definition import load_definition
from .form_model import FormModel


def _select_folder(current):
    # A user button opens a local OS dialog; never called during import/display.
    import tkinter as tk
    from tkinter.filedialog import askdirectory
    from pathlib import Path
    root = tk.Tk()
    try:
        root.withdraw()
        return askdirectory(parent=root, title='フォルダーを選択',
                            initialdir=current if current and Path(current).is_absolute() else None)
    finally:
        root.destroy()


class NotebookForm:
    def __init__(self, definition, *, folder_picker=None):
        import ipywidgets as widgets
        self._widgets = widgets
        self.model = FormModel(definition)
        self._folder_picker = folder_picker or _select_folder
        self._syncing = False
        self._invalid_fields = set()
        self._dynamic = []
        self.result = ''
        self.field_widgets = {}
        self.folder_buttons = {}
        layout = lambda: widgets.Layout(flex='1 1 180px', min_width='150px')
        self.connector = widgets.Dropdown(description='コネクタ', options=[('選択してください', None)] + [
            (entry['label'], key) for key, entry in definition['connectors'].items()], layout=layout())
        self.action = widgets.Dropdown(description='アクション', options=[('選択してください', None)], disabled=True, layout=layout())
        self.generate_button = widgets.Button(description='コード生成', disabled=True, button_style='primary')
        self.toolbar = widgets.HBox(layout=widgets.Layout(display='flex', flex_flow='row wrap', align_items='center'))
        self.details = widgets.VBox()
        self.message = widgets.HTML()
        self.generated = widgets.HTML()
        self.root = widgets.VBox([self.toolbar, self.details, self.message, self.generated])
        self.connector.observe(self._connector_changed, names='value')
        self.action.observe(self._action_changed, names='value')
        self.generate_button.on_click(self._generate)
        self._sync()

    def _clear_result(self):
        self.result = ''
        self.generated.value = ''

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
            self.folder_buttons = {}
            self._invalid_fields.clear()
            for name, field in self.model.fields.items():
                value = self.model.values[name]
                label = field['label'] + (' *' if field.get('required') else '')
                if field['type'] == 'choice':
                    widget = widgets.Dropdown(description=label, options=[('選択してください', None)] + [(x, x) for x in field['choices']], value=value)
                elif field['type'] == 'integer':
                    widget = widgets.IntText(description=label, value=value)
                else:
                    widget = widgets.Text(description=label, value=value, continuous_update=True)
                widget.layout.width = 'auto'
                widget.style.description_width = 'initial'
                widget.observe(lambda change, key=name: self._value_changed(key, change['new']), names='value')
                self.field_widgets[name] = widget
                self._dynamic.append(widget)
                if field['type'] == 'folder':
                    button = widgets.Button(description=field['label'] + 'を選択')
                    button.on_click(lambda _, key=name: self._pick_folder(key))
                    self.folder_buttons[name] = button
                    self._dynamic.append(button)
            self.toolbar.children = [self.connector, self.action, *self.folder_buttons.values(), self.generate_button]
            self.details.children = list(self.field_widgets.values())
            self.message.value = ''
            self._clear_result()
            self._refresh_generate()
        finally:
            self._syncing = False

    def _value_changed(self, name, value):
        if self._syncing:
            return
        self._clear_result()
        try:
            self.model.set_value(name, value)
            self._invalid_fields.discard(name)
        except ValueError:
            self._invalid_fields.add(name)
        if self._invalid_fields:
            self.message.value = '入力値を確認してください。フォルダーは絶対パスを指定します。'
        else:
            self.message.value = ''
            try:
                self.model.generate()
            except ValueError as error:
                self.message.value = escape(str(error))
        self._refresh_generate()

    def _pick_folder(self, name):
        try:
            selected = self._folder_picker(self.field_widgets[name].value)
            if selected:  # Cancellation preserves the existing value and result.
                self.field_widgets[name].value = selected
        except Exception as error:
            self.message.value = 'フォルダー選択を開けません。ローカルPythonのTk環境を確認してください。(' + escape(type(error).__name__) + ')'

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
        self.generated.value = '<p><b>' + label + '</b></p><pre style="white-space:pre-wrap;user-select:text">' + escape(self.result) + '</pre>'

    def close(self):
        for widget in [*self._dynamic, self.connector, self.action, self.generate_button,
                       self.toolbar, self.details, self.message, self.generated, self.root]:
            widget.close()


def create_form(config_path=None, *, folder_picker=None):
    """Return a controller with .root, .model and .result for explicit Python use."""
    return NotebookForm(load_definition(config_path), folder_picker=folder_picker)


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
