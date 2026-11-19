"""Generate the RENAME-list call from the Notebook form."""
import ast

from .connector_codegen import _identifier, form_input_file_path, module_name_for, render_call


PRE_FLAGS = ('remove_spaces', 'remove_newlines', 'to_halfwidth_alnum', 'symbols_to_snake')
GENERATION_FIELDS = {
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
