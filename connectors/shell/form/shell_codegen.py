"""Generate the Windows batch file call using structured arguments."""
import ast
import json

from ...connector_codegen import _identifier, _text, form_input_file_path, module_name_for, render_call


GENERATION_FIELDS = {'shell.execute_bat': {'folder', 'filename', 'args', 'output_variable'}}


def generate_shell(kind, values, module_path):
    if kind not in GENERATION_FIELDS:
        raise ValueError('未対応のバッチ実行種別です。')
    module = module_name_for(module_path)
    variable = _identifier(values, 'output_variable')
    arguments = [ast.keyword(arg='file_path', value=ast.Constant(form_input_file_path(values)))]
    text = _text(values, 'args').strip()
    if text:
        args = json.loads(text)
        if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
            raise ValueError('引数は文字列のJSON配列で指定してください。')
        arguments.append(ast.keyword(arg='args', value=ast.List(elts=[ast.Constant(arg) for arg in args], ctx=ast.Load())))
    return render_call(module, 'execute_bat', arguments, variable, reading=True)
