"""Generate code from the DuckDB form."""
import ast
from pathlib import Path

from ...connector_codegen import _identifier, _text, absolute_file_path, module_name_for, render_call
from ...sql_magic import render_sql_magic


DATABASE_FIELDS = {'db_file', 'output_variable'}
GENERATION_FIELDS = {
    'duckdb.execute_sql': {'db_file', 'sql', 'output_target'},
    'duckdb.create_db_file': {'db_folder', 'db_file_name', 'output_variable'},
    'duckdb.execute_sql_file': DATABASE_FIELDS | {'sql_file', 'encoding'},
    'duckdb.create_table': DATABASE_FIELDS | {'input_variable', 'table_name', 'mode'},
}


def generate_duckdb(kind, values, module_path):
    if kind not in GENERATION_FIELDS:
        raise ValueError('未対応のDuckDB生成種別です。')
    if kind == 'duckdb.execute_sql':
        return render_sql_magic('duckdb', absolute_file_path(values, 'db_file'),
                                _text(values, 'sql', required=True), _text(values, 'output_target'))
    module_name = module_name_for(module_path)
    variable = _identifier(values, 'output_variable')
    function = kind.split('.', 1)[1]
    if function == 'create_db_file':
        folder = Path(_text(values, 'db_folder', required=True))
        if not folder.is_absolute():
            raise ValueError('フォルダーは絶対パスで指定してください。')
        parameters = {'db_folder': folder.as_posix(),
                      'db_file_name': _text(values, 'db_file_name', required=True).strip()}
    else:
        parameters = {'db_file': absolute_file_path(values, 'db_file')}
        if function == 'execute_sql_file':
            parameters['sql_file'] = absolute_file_path(values, 'sql_file')
            parameters['encoding'] = _text(values, 'encoding', required=True)
        else:
            parameters['table_name'] = _text(values, 'table_name', required=True)
            mode = values.get('mode')
            if mode not in ('新規作成', '置換'):
                raise ValueError('テーブル作成モードを選択してください。')
            parameters['replace'] = mode == '置換'
    arguments = [ast.keyword(arg=name, value=ast.Constant(value)) for name, value in parameters.items()]
    if function == 'create_table':
        input_variable = _identifier(values, 'input_variable')
        arguments.append(ast.keyword(arg='data', value=ast.Name(id=input_variable, ctx=ast.Load())))
    return render_call(module_name, function, arguments, variable, reading=True)
