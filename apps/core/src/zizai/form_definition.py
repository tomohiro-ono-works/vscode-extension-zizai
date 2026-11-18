"""Load form data without evaluating YAML tags, aliases or templates as code."""
from importlib.resources import files
from pathlib import Path
import keyword
import re
from string import Formatter
from .csv_codegen import GENERATION_KINDS
from .excel_codegen import GENERATION_FIELDS as EXCEL_GENERATION_FIELDS
from .core.connector_config import get_connector_directory

MAX_BYTES = 1024 * 1024
ID = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')
ALLOWED_GENERATIONS = GENERATION_KINDS.union(EXCEL_GENERATION_FIELDS)


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
        if set(connector) - {'label', 'actions', 'module_file'}:
            raise ValueError('コネクタ定義に未対応の項目があります。')
        if 'module_file' in connector:
            module_file = connector['module_file']
            if (not isinstance(module_file, str) or '/' in module_file or '\\' in module_file
                    or Path(module_file).suffix.lower() != '.py' or Path(module_file).name != module_file
                    or not Path(module_file).stem.isidentifier() or keyword.iskeyword(Path(module_file).stem)):
                raise ValueError('module_fileは同じフォルダー内の.pyファイル名にしてください。')
        for action_id, action in _mapping(connector.get('actions'), 'actions').items():
            if not isinstance(action_id, str) or not ID.fullmatch(action_id):
                raise ValueError('アクションIDが不正です。')
            _mapping(action, 'アクション')
            _label(action.get('label'))
            if set(action) - {'label', 'fields', 'generation'}:
                raise ValueError('アクション定義に未対応の項目があります。')
            if 'generation' in action:
                generation = action['generation']
                if not isinstance(generation, str) or generation not in ALLOWED_GENERATIONS:
                    raise ValueError('generationは許可されたCSV／Excel操作を指定してください。')
            fields = action.get('fields', {})
            if not isinstance(fields, dict):
                raise ValueError('fieldsは項目一覧にしてください。')
            if 'generation' in action:
                needed = EXCEL_GENERATION_FIELDS.get(generation)
                if needed is None:
                    needed = {'folder', 'filename', 'encoding', 'delimiter', 'schema'}
                    needed |= ({'output_variable', 'header_row', 'data_start_row', 'chunk_size'}
                               if generation == 'csv.read_csv' else {'input_variable'})
                if not needed <= fields.keys():
                    raise ValueError('コード生成に必要な入力項目が不足しています。')
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


def _load_file(path):
    path = Path(path).expanduser().resolve()
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('設定ファイルは1MiB以下にしてください。')
    data = parse_definition(raw.decode('utf-8'))
    for connector in data['connectors'].values():
        if 'module_file' in connector:
            module = (path.parent / connector['module_file']).resolve()
            if module.parent != path.parent:
                raise ValueError('モジュールは定義と同じフォルダー内に置いてください。')
            connector['module_path'] = str(module)
        elif any(action.get('generation') for action in connector['actions'].values()):
            raise ValueError('実コード生成にはmodule_fileが必要です。')
    return data


def load_definition(path=None):
    selected = Path(path).expanduser() if path is not None else get_connector_directory()
    if selected is not None and not selected.is_dir():
        return _load_file(selected)
    data = parse_definition(files('zizai').joinpath('forms.yaml').read_text(encoding='utf-8'))
    if selected is None:
        return data
    definitions = sorted(selected.glob('*/*_definition.yaml'))
    if not definitions:
        raise ValueError('共通フォルダーにコネクタの*_definition.yamlがありません。')
    seen = set()
    for definition in definitions:
        if not definition.resolve().is_relative_to(selected.resolve()):
            raise ValueError('定義は共通フォルダー内に置いてください。')
        external = _load_file(definition)
        for connector_id, connector in external['connectors'].items():
            if connector_id in seen:
                raise ValueError('外部定義のコネクタIDが重複しています。')
            seen.add(connector_id)
            data['connectors'][connector_id] = connector
    return data
