"""Load form data without evaluating YAML tags, aliases or templates as code."""
from importlib.resources import files
from pathlib import Path
import re
from string import Formatter
from .csv_codegen import GENERATION_KINDS

MAX_BYTES = 1024 * 1024
ID = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')


def valid_value(field, value, *, require=False):
    if value is None or (isinstance(value, str) and not value.strip()):
        return not (require and field.get('required', False))
    kind = field['type']
    if kind == 'integer':
        return type(value) is int and value >= field.get('minimum', value)
    if not isinstance(value, str):
        return False
    if kind == 'choice':
        return value in field['choices']
    if kind == 'folder':
        return Path(value).is_absolute()
    return kind == 'text'


def _mapping(value, name):
    if not isinstance(value, dict) or not value:
        raise ValueError(f'{name}は空でない項目一覧にしてください。')
    return value


def _label(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('labelは空でない文字列にしてください。')


def parse_definition(text):
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('設定ファイルは1MiB以下にしてください。')
    import yaml

    class UniqueSafeLoader(yaml.SafeLoader):
        def compose_node(self, parent, index):
            if self.check_event(yaml.AliasEvent):
                raise ValueError('YAMLのaliasは使用できません。')
            return super().compose_node(parent, index)

        def construct_mapping(self, node, deep=False):
            mapping = {}
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, (str, int, float, bool, type(None))):
                    raise ValueError('YAMLのキーは単一の値にしてください。')
                if key in mapping:
                    raise ValueError('YAMLのキーが重複しています。')
                mapping[key] = self.construct_object(value_node, deep=deep)
            return mapping

    try:
        data = yaml.load(text, Loader=UniqueSafeLoader)
    except yaml.YAMLError as error:
        raise ValueError('YAMLの記法を確認してください。') from error
    _mapping(data, '設定')
    if type(data.get('version')) is not int or data['version'] != 1:
        raise ValueError('version: 1が必要です。')
    if set(data) - {'version', 'output_template', 'connectors'}:
        raise ValueError('設定に未対応の項目があります。')
    template = data.get('output_template')
    if not isinstance(template, str) or not template.strip():
        raise ValueError('output_templateが必要です。')
    try:
        for _, name, spec, conversion in Formatter().parse(template):
            if name is not None and (name not in {'connector', 'action'} or spec or conversion):
                raise ValueError('表示文では{connector}と{action}だけを使用できます。')
    except ValueError as error:
        raise ValueError('output_templateの置換項目を確認してください。') from error
    for connector_id, connector in _mapping(data.get('connectors'), 'connectors').items():
        if not isinstance(connector_id, str) or not ID.fullmatch(connector_id):
            raise ValueError('コネクタIDが不正です。')
        _mapping(connector, 'コネクタ')
        _label(connector.get('label'))
        if set(connector) - {'label', 'actions'}:
            raise ValueError('コネクタ定義に未対応の項目があります。')
        for action_id, action in _mapping(connector.get('actions'), 'actions').items():
            if not isinstance(action_id, str) or not ID.fullmatch(action_id):
                raise ValueError('アクションIDが不正です。')
            _mapping(action, 'アクション')
            _label(action.get('label'))
            if set(action) - {'label', 'fields', 'generation'}:
                raise ValueError('アクション定義に未対応の項目があります。')
            if 'generation' in action and (not isinstance(action['generation'], str) or action['generation'] not in GENERATION_KINDS):
                raise ValueError('generationはcsv.read_csv／csv.write_csvだけ指定できます。')
            fields = action.get('fields', {})
            if not isinstance(fields, dict):
                raise ValueError('fieldsは項目一覧にしてください。')
            if 'generation' in action:
                needed = {'folder', 'filename', 'encoding', 'delimiter', 'schema'}
                needed |= ({'output_variable', 'header_row', 'data_start_row', 'chunk_size', 'date_cleansing'}
                           if action['generation'] == 'csv.read_csv' else {'input_variable'})
                if not needed <= fields.keys():
                    raise ValueError('CSV生成に必要な入力項目が不足しています。')
            for name, field in fields.items():
                if not isinstance(name, str) or not ID.fullmatch(name) or not isinstance(field, dict):
                    raise ValueError('入力項目の定義が不正です。')
                _label(field.get('label'))
                if field.get('type') not in {'text', 'choice', 'folder', 'integer'}:
                    raise ValueError('項目型はtext/choice/folder/integerにしてください。')
                if set(field) - {'label', 'type', 'required', 'default', 'choices', 'minimum'}:
                    raise ValueError('入力項目に未対応の設定があります。')
                if 'required' in field and type(field['required']) is not bool:
                    raise ValueError('requiredはtrue/falseにしてください。')
                if field['type'] == 'choice':
                    choices = field.get('choices')
                    if not isinstance(choices, list) or not choices or any(not isinstance(x, str) or not x.strip() for x in choices) or len(set(choices)) != len(choices):
                        raise ValueError('choicesは重複のない文字列一覧にしてください。')
                elif 'choices' in field:
                    raise ValueError('choicesはchoice項目だけに指定できます。')
                if 'minimum' in field and (field['type'] != 'integer' or type(field['minimum']) is not int):
                    raise ValueError('minimumはinteger項目の整数にしてください。')
                if 'default' in field:
                    default = field['default']
                    correct_type = (type(default) is int if field['type'] == 'integer' else
                                    (default is None or isinstance(default, str)) if field['type'] == 'choice' else
                                    isinstance(default, str))
                    if not correct_type or not valid_value(field, default):
                        raise ValueError('defaultが項目の条件を満たしません。')
    return data


def load_definition(path=None):
    if path is None:
        raw = files('zizai').joinpath('forms.yaml').read_bytes()
    else:
        with Path(path).expanduser().open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('設定ファイルは1MiB以下にしてください。')
    return parse_definition(raw.decode('utf-8'))
