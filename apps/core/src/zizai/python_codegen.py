"""Generate a standard connector call for a Python script."""
import ast
from pathlib import Path

from .connector_codegen import _identifier, _text, form_file_path, module_name_for, render_call


GENERATION_FIELDS = {'python.execute_python_file': {'folder', 'filename', 'env_path', 'output_variable'}}


def generate_python(kind, values, module_path):
    if kind not in GENERATION_FIELDS:
        raise ValueError('未対応のPython実行種別です。')
    module = module_name_for(module_path)
    variable = _identifier(values, 'output_variable')
    arguments = [ast.keyword(arg='script_file', value=ast.Constant(form_file_path(values)))]
    env_path = _text(values, 'env_path').strip()
    if env_path:
        arguments.append(ast.keyword(arg='env_path', value=ast.Constant(Path(env_path).as_posix())))
    return render_call(module, 'execute_python_file', arguments, variable, reading=True)
