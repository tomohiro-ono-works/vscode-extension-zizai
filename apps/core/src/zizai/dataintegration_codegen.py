"""Generate data integration calls from the Notebook form."""
import ast
import json
import unicodedata

from .connector_codegen import _identifier, _text, form_input_file_path, module_name_for, render_call


PRE_FLAGS = ('remove_spaces', 'remove_newlines', 'to_halfwidth_alnum', 'symbols_to_snake')
COLUMN_OPERATIONS = 'dataintegration.apply_column_operations'
VALUE_OPERATIONS = 'dataintegration.apply_value_operations'
ROW_OPERATIONS = 'dataintegration.filter_rows'
DATA_OPERATIONS = 'dataintegration.apply_data_operations'
DATAFRAME_OPERATIONS = {
    COLUMN_OPERATIONS: 'apply_column_operations',
    VALUE_OPERATIONS: 'apply_value_operations',
    ROW_OPERATIONS: 'filter_rows',
    DATA_OPERATIONS: 'apply_data_operations',
}
GENERATION_FIELDS = {
    **{kind: {'input_variable', 'output_variable', 'operations'} for kind in DATAFRAME_OPERATIONS},
    'dataintegration.replace_fields_forrenamelist': {
        'folder', 'filename', 'input_variable', 'output_variable', 'exclude_japanese_columns', *PRE_FLAGS,
    },
}


def generate_dataintegration(kind, values, module_path):
    if kind not in GENERATION_FIELDS:
        raise ValueError('未対応のデータ統合操作です。')
    module = module_name_for(module_path)
    incoming = _identifier(values, 'input_variable')
    output = _identifier(values, 'output_variable')
    if kind in DATAFRAME_OPERATIONS:
        label = {COLUMN_OPERATIONS: '列操作', VALUE_OPERATIONS: '値加工', ROW_OPERATIONS: '行の条件',
                 DATA_OPERATIONS: '処理'}[kind]
        if unicodedata.normalize('NFKC', incoming) == unicodedata.normalize('NFKC', output):
            raise ValueError('入力と出力には別の変数名を指定してください。')
        try:
            operations = json.loads(_text(values, 'operations', required=True))
        except json.JSONDecodeError as error:
            raise ValueError(f'{label}の設定を確認してください。') from error
        if not isinstance(operations, list) or not operations or any(not isinstance(op, dict) for op in operations):
            raise ValueError(f'{label}を1件以上設定してください。')
        arguments = [ast.keyword(arg='data', value=ast.Name(id=incoming, ctx=ast.Load())),
                     ast.keyword(arg='operations', value=ast.parse(repr(operations), mode='eval').body)]
        return render_call(module, DATAFRAME_OPERATIONS[kind], arguments, output, reading=True,
                           direct_variables=True, temporary_prefix='_zizai_')
    arguments = [
        ast.keyword(arg='data', value=ast.Name(id=incoming, ctx=ast.Load())),
        ast.keyword(arg='rename_list_path', value=ast.Constant(form_input_file_path(values))),
    ]
    pre_cleaning = tuple(flag for flag in PRE_FLAGS if values.get(flag) is True)
    if pre_cleaning:
        arguments.append(ast.keyword(arg='pre_rename_cleansing', value=ast.Constant(pre_cleaning)))
    if values.get('exclude_japanese_columns') is True:
        arguments.append(ast.keyword(arg='exclude_japanese_columns', value=ast.Constant(True)))
    return render_call(module, 'replace_fields_forrenamelist', arguments, output, reading=True)
