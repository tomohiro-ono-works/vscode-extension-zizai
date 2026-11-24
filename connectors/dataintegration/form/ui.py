"""DataFrame editing and reference-file defaults for data integration."""
from html import escape
from importlib import import_module
from importlib.util import find_spec
import json
from pathlib import Path

from ...connector_codegen import module_name_for
from ...connector_forms.controls import FormControls
from .dataintegration_codegen import COLUMN_OPERATIONS, DATAFRAME_OPERATIONS, ROW_OPERATIONS, VALUE_OPERATIONS
from .pandas_table_codegen import TABLE_ACTIONS


class Controls(FormControls):
    def __init__(self, form):
        super().__init__(form)
        kind = form.model.generation
        self.wide = kind in DATAFRAME_OPERATIONS or kind in TABLE_ACTIONS
        self._dataframe_editor = None
        self._dataframe_slot = None

    def skip_field(self, name):
        if self.wide and name == 'operations':
            self.form.model.set_value(name, '')
            return True
        return False

    def widget(self, name, label, value):
        if self.wide and name == 'input_variable':
            return self.form._dataframe_picker(name, label)
        return None

    def rows(self):
        if not self.wide:
            return super().rows()
        form = self.form
        self._dataframe_slot = form._widgets.VBox()
        form._dynamic.append(self._dataframe_slot)
        self._show_dataframe_editor(form.model.values['input_variable'])
        return [*form._field_rows((('input_variable', 'output_variable'),)), self._dataframe_slot]

    def value_changed(self, name, value):
        if name == 'input_variable' and self.wide:
            self.form.model.set_value('operations', '')
            self._show_dataframe_editor(value)

    def show_generation_error(self):
        return not self.wide or bool(self.form.model.values['operations'])

    def initial_directory(self, name):
        if self.form.model.action == 'replace_fields_forrenamelist' and name == 'file_path':
            folder = self.form.model.connector_folder
            if folder is not None:
                references = folder / 'references'
                if references.is_dir():
                    return str(references)
        return None

    def close(self):
        self._close_dataframe_editor()

    def _show_dataframe_editor(self, name):
        self._close_dataframe_editor()
        widgets = self.form._widgets
        if not name:
            help_text = ('入力DataFrameを選択してください。' if len(self.form.field_widgets['input_variable'].options) > 1
                         else 'NotebookでDataFrameを作成してから、フォームを再表示してください。')
            self._dataframe_slot.children = (widgets.HTML(f'<p>{help_text}</p>'),)
            return
        try:
            generation = self.form.model.actions[self.form.model.action]['generation']
            if generation in TABLE_ACTIONS:
                from .table_action_editor import create_table_editor
                candidates = {candidate: self.form._namespace[candidate] for candidate in self.form._dataframe_names()}
                self._dataframe_editor = create_table_editor(
                    generation, self.form._namespace[name], self._set_dataframe_operations, candidates=candidates)
            else:
                self._dataframe_editor = self._create_connector_editor(name, generation)
        except (ImportError, TypeError, ValueError, KeyError, OSError) as error:
            self._dataframe_slot.children = (widgets.HTML(f'<p role="alert">{escape(str(error))}</p>'),)
            return
        self._dataframe_slot.children = (self._dataframe_editor.root,)

    def _create_connector_editor(self, name, generation):
        path = self.form.model.definition['connectors'][self.form.model.connector].get('module_path')
        module = module_name_for(path)
        spec = find_spec(module)
        if spec is None or spec.origin is None or Path(spec.origin).resolve() != Path(path).resolve():
            raise ValueError('設定したデータ統合コネクタをカーネルに登録してください。')
        apply_operations = getattr(import_module(module), DATAFRAME_OPERATIONS[generation], None)
        if not callable(apply_operations):
            raise ValueError('データ統合コネクタを更新し、カーネルを再起動してください。')
        args = self.form._namespace[name], apply_operations, self._set_dataframe_operations
        if generation == COLUMN_OPERATIONS:
            from .column_editor import ColumnEditor
            return ColumnEditor(*args)
        from .data_operations_editor import DataOperationsEditor
        mode = {VALUE_OPERATIONS: 'value', ROW_OPERATIONS: 'condition'}.get(generation)
        return DataOperationsEditor(*args, mode=mode)

    def _set_dataframe_operations(self, operations):
        self.form._value_changed('operations', json.dumps(operations, ensure_ascii=False) if operations else '')

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
