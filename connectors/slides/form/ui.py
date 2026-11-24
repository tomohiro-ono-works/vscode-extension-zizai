"""Markdown source mode and stylesheet help for slide generation."""
from html import escape
from pathlib import Path

from ...connector_forms.controls import FormControls, find_row
from .slides_codegen import CONVERSION


class Controls(FormControls):
    def __init__(self, form):
        super().__init__(form)
        self.file_row = None

    def widget(self, name, label, value):
        if self.form.model.generation == CONVERSION and name == 'input_mode':
            widget = self.form._widgets.ToggleButtons(
                description=label, options=[('直接入力', 'text'), ('ファイル指定', 'file')],
                value=value, style={'button_width': 'auto'})
            widget.add_class('zizai-batch-toggle')
            return widget
        return None

    def rows(self):
        rows = super().rows()
        if self.form.model.generation == CONVERSION:
            fields = self.form.field_widgets
            if 'markdown_file' in fields:
                self.file_row = find_row(rows, fields['markdown_file'])
            if 'style_path' in fields:
                row = find_row(rows, fields['style_path'])
                if row is not None:
                    help_text = self.form._widgets.HTML(self._slide_css_help())
                    self.form._dynamic.append(help_text)
                    rows.insert(rows.index(row) + 1, help_text)
        return rows

    def after_render(self):
        if self.file_row is not None:
            self._show_slide_input_mode()

    def value_changed(self, name, value):
        if name == 'input_mode':
            self.after_render()

    def invalid_fields(self, fields):
        if self.file_row is None:
            return fields
        hidden = 'markdown_text' if self.form.model.values['input_mode'] == 'file' else 'markdown_file'
        return fields - {hidden}

    def _show_slide_input_mode(self):
        use_file = self.form.model.values['input_mode'] == 'file'
        self.form.field_widgets['markdown_text'].layout.display = 'none' if use_file else ''
        self.file_row.layout.display = '' if use_file else 'none'

    def _slide_css_help(self):
        folder = self.form.model.connector_folder or (Path('connectors') / self.form.model.connector)
        default = folder / 'zizai_slides/assets/slide.css'
        example = folder / 'config/custom.example.css'
        return (f'組み込みCSS <code>{escape(str(default))}</code><br>'
                f'自作CSSのひな形 <code>{escape(str(example))}</code><br>'
                'CSS欄が空でファイルを指定した場合は、Markdownと同名のCSSがあれば使います。')
