"""Generate ordinary Python calls from DuckDB form values."""
import ast
from pathlib import Path

from .connector_codegen import _identifier, _text, module_name_for, render_call


DATABASE_FIELDS = {'db_folder', 'db_file_name', 'output_variable'}
GENERATION_FIELDS = {
    'duckdb.create_db_file': DATABASE_FIELDS,
    'duckdb.execute_sql': DATABASE_FIELDS | {'sql'},
    'duckdb.execute_sql_file': DATABASE_FIELDS | {'sql_folder', 'sql_file_name', 'encoding'},
}


def _absolute_folder(values, field):
    folder = Path(_text(values, field, required=True))
    if not folder.is_absolute():
        raise ValueError('フォルダーは絶対パスで指定してください。')
    return folder


def generate_duckdb(kind, values, module_path):
    if kind not in GENERATION_FIELDS:
        raise ValueError('未対応のDuckDB生成種別です。')
    module_name = module_name_for(module_path)
    variable = _identifier(values, 'output_variable')
    folder = _absolute_folder(values, 'db_folder')
    filename = _text(values, 'db_file_name', required=True).strip()
    function = kind.split('.', 1)[1]
    if function == 'create_db_file':
        parameters = {'db_folder': folder.as_posix(), 'db_file_name': filename}
    else:
        parameters = {'db_file': (folder / filename).as_posix()}
        if function == 'execute_sql':
            parameters['sql'] = _text(values, 'sql', required=True)
        else:
            sql_folder = _absolute_folder(values, 'sql_folder')
            sql_name = _text(values, 'sql_file_name', required=True).strip()
            parameters['sql_file'] = (sql_folder / sql_name).as_posix()
            parameters['encoding'] = _text(values, 'encoding', required=True)
    arguments = [ast.keyword(arg=name, value=ast.Constant(value)) for name, value in parameters.items()]
    return render_call(module_name, function, arguments, variable, reading=True)
