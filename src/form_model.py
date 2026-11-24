"""Selection and placeholder generation; no GUI, kernel or business execution."""
from copy import deepcopy
from pathlib import Path
from .form_definition import valid_value
from .connector_forms import form_support, generation_support


class FormModel:
    def __init__(self, definition):
        self.definition = deepcopy(definition)
        self.connector = None
        self.action = None
        self.values = {}

    @property
    def support(self):
        return form_support(self.connector)

    @property
    def connector_folder(self):
        module = self.definition['connectors'].get(self.connector, {}).get('module_path')
        return Path(module).parent if module else None

    @property
    def actions(self):
        return self.definition['connectors'][self.connector]['actions'] if self.connector else {}

    @property
    def generation(self):
        return self.actions.get(self.action, {}).get('generation')

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
                paths = getattr(self.support, 'DEFAULT_PATHS', {})
                if name in paths and self.connector_folder is not None:
                    default = (self.connector_folder / paths[name]).as_posix()
                self.values[name] = field.get('default', default)

    def set_connector(self, connector):
        if connector is not None and connector not in self.definition['connectors']:
            raise ValueError('候補からコネクタを選んでください。')
        fields, values = self.fields, self.values
        old_suffix = getattr(self.support, 'OUTPUT_SUFFIX', None)
        new_suffix = getattr(form_support(connector), 'OUTPUT_SUFFIX', None)
        if old_suffix and new_suffix and old_suffix != new_suffix:
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
        if action != self.action:
            reset = set(getattr(self.support, 'RESET_ON_ACTION_CHANGE', ()))
            for name in getattr(self.support, 'RESET_DEFAULTS_ON_ACTION_CHANGE', ()):
                if name in fields and values[name] == fields[name].get('default'):
                    reset.add(name)
            reset.update(name for name in getattr(self.support, 'RESET_EMPTY_ON_ACTION_CHANGE', ())
                         if values.get(name) == '')
            if reset:
                values = {name: value for name, value in values.items() if name not in reset}
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
            generate_code = generation_support(kind).generate
            return generate_code(kind, self.values, connector.get('module_path'))
        return '{' + self.definition['output_template'].format(connector=self.connector, action=self.action) + '}'
