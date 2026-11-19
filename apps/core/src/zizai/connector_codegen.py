"""Shared validation and AST rendering for form-generated connector calls."""
import ast
import keyword
from pathlib import Path


def _text(values, name, *, required=False):
    value = values.get(name)
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f'{name}を入力してください。')
    return value


def _identifier(values, name):
    value = _text(values, name, required=True)
    if not value.isidentifier() or keyword.iskeyword(value):
        raise ValueError('入出力変数には単一のPython変数名を指定してください。')
    return value


def _integer(values, name, minimum):
    value = values.get(name)
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name}は{minimum}以上の整数にしてください。')
    return value


def module_name_for(module_path):
    if not isinstance(module_path, str) or not Path(module_path).is_absolute() or Path(module_path).suffix.lower() != '.py':
        raise ValueError('コネクタモジュールの絶対パスが必要です。')
    module_name = Path(module_path).stem
    if not module_name.isidentifier() or keyword.iskeyword(module_name):
        raise ValueError('コネクタのファイル名はPythonのモジュール名にしてください。')
    return module_name


def form_file_path(values, *, default_extension=None):
    folder = _text(values, 'folder', required=True)
    if not Path(folder).is_absolute():
        raise ValueError('フォルダーは絶対パスで指定してください。')
    filename = _text(values, 'filename', required=True)
    if default_extension and not Path(filename).suffix:
        filename += default_extension
    return (Path(folder) / filename).as_posix()


def form_input_file_path(values):
    if 'file_path' not in values:  # Accept existing folder/filename definitions.
        return form_file_path(values)
    path = Path(_text(values, 'file_path', required=True))
    if not path.is_absolute():
        raise ValueError('入力ファイルは絶対パスで指定してください。')
    return path.as_posix()


def render_call(module_name, function, arguments, variable, *, reading):
    handle = '_zizai_' + module_name if variable == module_name else module_name
    body = [ast.Import(names=[ast.alias(name=module_name, asname=handle if handle != module_name else None)])]
    reserved = {variable, handle}
    for argument in arguments:
        name = argument.arg
        suffix = 2
        while name in reserved:
            name = f'{argument.arg}_{suffix}'
            suffix += 1
        reserved.add(name)
        body.append(ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=argument.value))
        argument.value = ast.Name(id=name, ctx=ast.Load())
    call = ast.Call(func=ast.Attribute(value=ast.Name(id=handle, ctx=ast.Load()), attr=function, ctx=ast.Load()),
                    args=[], keywords=arguments)
    if reading:
        body.extend([ast.Assign(targets=[ast.Name(id=variable, ctx=ast.Store())], value=call),
                     ast.Expr(value=ast.Name(id=variable, ctx=ast.Load()))])
    else:
        body.append(ast.Expr(value=call))
    return ast.unparse(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))) + '\n'
