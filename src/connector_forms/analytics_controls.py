"""Column selection and safe code generation for analytics forms."""
import ast
import json
from collections import Counter

from ..connector_codegen import _identifier, _text, module_name_for, render_call
from .controls import FormControls


def decode_columns(value):
    if value == '':
        return []
    try:
        columns = json.loads(value)
    except (TypeError, ValueError) as error:
        raise ValueError('列を候補から選択してください。') from error
    if (not isinstance(columns, list) or
            any(not isinstance(c, str) or not c.strip() for c in columns) or
            len(set(columns)) != len(columns)):
        raise ValueError('列は重複なく選択してください。')
    return columns


def encode_columns(columns):
    return json.dumps(list(columns), ensure_ascii=False) if columns else ''


def columns_argument(values, name, required=False):
    columns = decode_columns(_text(values, name, required=required))
    if required and not columns:
        raise ValueError(f'{name}を選択してください。')
    return columns


def generate_call(values, module_path, action, parameters):
    arguments = [ast.keyword(arg='data', value=ast.Name(
        id=_identifier(values, 'input_variable'), ctx=ast.Load()))]
    for name, value in parameters.items():
        node = (ast.List(elts=[ast.Constant(v) for v in value], ctx=ast.Load())
                if isinstance(value, list) else ast.Constant(value))
        arguments.append(ast.keyword(arg=name, value=node))
    return render_call(module_name_for(module_path), action, arguments,
                       _identifier(values, 'output_variable'), reading=True)


class AnalyticsControls(FormControls):
    """Use the existing Notebook namespace and ipywidgets column controls."""
    multi_fields = ()
    single_fields = ()

    def widget(self, name, label, value):
        if name == 'input_variable':
            return self.form._dataframe_picker(name, label)
        if name in (*self.multi_fields, *self.single_fields):
            return self._picker(name, label)
        return None

    def _columns(self):
        form = self.form
        frame = form._namespace.get(form.model.values.get('input_variable'))
        labels = getattr(frame, 'columns', ())
        counts = Counter(labels)
        return tuple(c for c in labels if isinstance(c, str) and c.strip() and counts[c] == 1)

    def _picker(self, name, label):
        form = self.form
        columns = self._columns()
        current = form.model.values[name]
        if name in self.multi_fields:
            try:
                saved = decode_columns(current)
            except ValueError:
                saved = []
            selected = tuple(c for c in saved if c in columns)
            form.model.set_value(name, encode_columns(selected))
            picker = form._widgets.SelectMultiple(
                description=label, options=columns, value=selected,
                rows=max(2, min(8, len(columns))), disabled=not columns)
        else:
            selected = current if current in columns else ''
            form.model.set_value(name, selected)
            placeholder = '選択してください' if columns else '入力DataFrameの列を確認してください'
            picker = form._widgets.Dropdown(
                description=label, options=[(placeholder, ''), *((c, c) for c in columns)],
                value=selected, disabled=not columns)
        picker.description_allow_html = True
        picker.style.description_width = 'initial'
        return picker

    def value_changed(self, name, value):
        form = self.form
        if name in self.multi_fields:
            # NotebookForm initially validates the raw tuple as a text value.
            # Store its serialized representation and clear that transient error.
            if isinstance(value, tuple) and set(value) <= set(self._columns()):
                form.model.set_value(name, encode_columns(value))
                form._invalid_fields.discard(name)
            return
        if name != 'input_variable':
            return
        # Replace widgets, as Vector does, so queued indices from the old
        # DataFrame cannot be interpreted against the new candidate list.
        for field in (*self.multi_fields, *self.single_fields):
            previous = form.field_widgets[field]
            form.model.set_value(field, '')
            form._invalid_fields.discard(field)
            picker = self._picker(field, previous.description)
            picker.layout = previous.layout
            picker.observe(lambda change, key=field:
                           form._value_changed(key, change['new']), names='value')
            form.details.children = tuple(picker if item is previous else item
                                          for item in form.details.children)
            form.field_widgets[field] = picker
            form._dynamic[form._dynamic.index(previous)] = picker
            previous.unobserve_all('value')
            previous.close()

    def rows(self):
        # Column pickers are top-level rows, allowing safe replacement.
        return self.form._field_rows(())
