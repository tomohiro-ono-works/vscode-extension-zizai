"""Generate a standard connector call for a Python script."""
import ast

from .connector_codegen import _identifier, absolute_file_path, module_name_for, render_call


GENERATION_FIELDS = {'python.execute_python_file': {'file_path', 'output_variable'}}


def generate_python(kind, values, module_path):
    if kind not in GENERATION_FIELDS:
        raise ValueError('未対応のPython実行種別です。')
    module = module_name_for(module_path)
    variable = _identifier(values, 'output_variable')
    script_file = absolute_file_path(values, 'file_path')
    arguments = [ast.keyword(arg='script_file', value=ast.Constant(script_file))]
    return render_call(module, 'execute_python_file', arguments, variable, reading=True)
