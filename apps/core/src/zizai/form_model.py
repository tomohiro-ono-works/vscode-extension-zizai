"""Selection and placeholder generation; no GUI, kernel or business execution."""
from copy import deepcopy
from .form_definition import valid_value
from .csv_codegen import generate_csv


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
                self.values[name] = field.get('default', default)

    def set_connector(self, connector):
        if connector is not None and connector not in self.definition['connectors']:
            raise ValueError('候補からコネクタを選んでください。')
        fields, values = self.fields, self.values
        self.connector = connector
        if self.action not in self.actions:
            self.action = None
        self._restore_fields(fields, values)

    def set_action(self, action):
        if action is not None and action not in self.actions:
            raise ValueError('候補からアクションを選んでください。')
        fields, values = self.fields, self.values
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
            return generate_csv(self.actions[self.action]['generation'], self.values)
        return '{' + self.definition['output_template'].format(connector=self.connector, action=self.action) + '}'
