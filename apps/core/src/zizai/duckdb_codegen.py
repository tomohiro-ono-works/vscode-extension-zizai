"""Generate ordinary Python calls from DuckDB form values."""
import ast
from pathlib import Path

from .connector_codegen import _identifier, _text, module_name_for, render_call


GENERATION_FIELDS = {
    'duckdb.create_db_file': {'db_folder', 'db_file_name', 'output_variable'},
}


def generate_duckdb(kind, values, module_path):
    if kind not in GENERATION_FIELDS:
        raise ValueError('未対応のDuckDB生成種別です。')
    module_name = module_name_for(module_path)
    variable = _identifier(values, 'output_variable')
    folder = Path(_text(values, 'db_folder', required=True))
    if not folder.is_absolute():
        raise ValueError('DBファイルの場所は絶対パスで指定してください。')
    filename = _text(values, 'db_file_name', required=True).strip()
    arguments = [
        ast.keyword(arg='db_folder', value=ast.Constant(folder.as_posix())),
        ast.keyword(arg='db_file_name', value=ast.Constant(filename)),
    ]
    return render_call(module_name, 'create_db_file', arguments, variable, reading=True)
