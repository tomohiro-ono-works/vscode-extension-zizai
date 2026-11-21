"""Selection and placeholder generation; no GUI, kernel or business execution."""
from copy import deepcopy
from .form_definition import valid_value
from .connector_forms.bigquery.bigquery_codegen import generate_bigquery
from .connector_forms.csv.csv_codegen import generate_csv
from .connector_forms.dataintegration.dataintegration_codegen import generate_dataintegration
from .connector_forms.duckdb.duckdb_codegen import generate_duckdb
from .connector_forms.excel.excel_codegen import generate_excel
from .connector_forms.python.python_codegen import generate_python
from .connector_forms.shell.shell_codegen import generate_shell
from .connector_forms.vector.vector_codegen import generate_vector
from .connector_forms.windows.windows_codegen import generate_windows


GENERATORS = {
    'bigquery': generate_bigquery, 'csv': generate_csv, 'dataintegration': generate_dataintegration,
    'duckdb': generate_duckdb, 'excel': generate_excel, 'python': generate_python, 'shell': generate_shell,
    'vector': generate_vector, 'windows': generate_windows,
}


class FormModel:
    def __init__(self, definition):
        self.definition = deepcopy(definition)
        self.connector = None
        self.action = None
        self.values = {}

    @property
    def actions(self):
        return self.definition['connectors'][self.connector]['actions'] if self.connector else {}

    @property
    def fields(self):
        return self.actions[self.action].get('fields', {}) if self.action else {}

    def _restore_fields(self, previous_fields, previous_values):
        self.values = {}
        for name, field in self.fields.items():
            if name in previous_values and previous_fields.get(name, {}).get('type') == field['type'] and valid_value(field, previous_values[name]):
                self.values[name] = previous_values[name]
            else:
                default = field.get('minimum', 0) if field['type'] == 'integer' else (None if field['type'] == 'choice' else '')
                if field['type'] == 'checkbox':
                    default = False
                self.values[name] = field.get('default', default)

    def set_connector(self, connector):
        if connector is not None and connector not in self.definition['connectors']:
            raise ValueError('候補からコネクタを選んでください。')
        fields, values = self.fields, self.values
        if {self.connector, connector} == {'csv', 'excel'}:
            # Keep a shared folder or variable, but give a different file format its own filename.
            values = {key: value for key, value in values.items() if key != 'filename'}
        self.connector = connector
        if self.action not in self.actions:
            self.action = None
        self._restore_fields(fields, values)

    def set_action(self, action):
        if action is not None and action not in self.actions:
            raise ValueError('候補からアクションを選んでください。')
        fields, values = self.fields, self.values
        if self.connector == 'vector' and action != self.action:
            if 'output_variable' in fields and values['output_variable'] == fields['output_variable'].get('default'):
                values = {key: value for key, value in values.items() if key != 'output_variable'}
            if values.get('collection_name') == '':
                values = {key: value for key, value in values.items() if key != 'collection_name'}
        if self.connector == 'windows' and action != self.action:
            reset_fields = {'wait_before_seconds', 'wait_after_seconds'}
            previous_default = fields.get('output_variable', {}).get('default')
            if values.get('output_variable') == previous_default:
                reset_fields.add('output_variable')
            values = {name: value for name, value in values.items() if name not in reset_fields}
        self.action = action
        self._restore_fields(fields, values)

    def set_value(self, name, value):
        if name not in self.fields or not valid_value(self.fields[name], value):
            raise ValueError('入力値が項目の条件を満たしません。')
        self.values[name] = value

    @property
    def is_placeholder(self):
        return not (self.action and self.actions[self.action].get('generation'))

    def generate(self):
        if self.connector is None or self.action is None:
            raise ValueError('コネクタとアクションを選んでください。')
        for name, field in self.fields.items():
            if not valid_value(field, self.values[name], require=True):
                raise ValueError(f'{field["label"]}を確認してください。')
        if not self.is_placeholder:
            connector = self.definition['connectors'][self.connector]
            kind = self.actions[self.action]['generation']
            generate_code = GENERATORS[kind.split('.', 1)[0]]
            return generate_code(kind, self.values, connector.get('module_path'))
        return '{' + self.definition['output_template'].format(connector=self.connector, action=self.action) + '}'
