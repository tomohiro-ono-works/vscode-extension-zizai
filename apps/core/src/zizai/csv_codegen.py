"""Pure CSV call generation. Never import a connector, evaluate input, or do IO."""
import ast
import keyword
from pathlib import Path

GENERATION_KINDS = frozenset({'csv.read_csv', 'csv.write_csv'})


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


def generate_csv(kind, values, module_path):
    """Return ordinary Python code; filesystem checks belong to execution."""
    if not isinstance(kind, str) or kind not in GENERATION_KINDS:
        raise ValueError('未対応のCSV生成種別です。')
    if not isinstance(module_path, str) or not Path(module_path).is_absolute() or Path(module_path).suffix.lower() != '.py':
        raise ValueError('コネクタモジュールの絶対パスが必要です。')
    module_name = Path(module_path).stem
    if not module_name.isidentifier() or keyword.iskeyword(module_name):
        raise ValueError('コネクタのファイル名はPythonのモジュール名にしてください。')
    folder = _text(values, 'folder', required=True)
    if not Path(folder).is_absolute():
        raise ValueError('フォルダーは絶対パスで指定してください。')
    filename = _text(values, 'filename', required=True)
    reading = kind == 'csv.read_csv'
    if not reading and not Path(filename).suffix:
        filename += '.csv'
    path = str(Path(folder) / filename)
    schema = _text(values, 'schema')
    options = {'encoding': _text(values, 'encoding'), 'delimiter': _text(values, 'delimiter'),
               'schema': schema if schema.strip() else None}
    defaults = {'encoding': 'utf-8' if reading else 'utf-8-sig', 'delimiter': ',', 'schema': None}
    function = 'read_csv' if reading else 'write_csv'
    if reading:
        variable = _identifier(values, 'output_variable')
        header = _integer(values, 'header_row', 1)
        start = _integer(values, 'data_start_row', 1)
        if start < header:
            raise ValueError('データ開始行はヘッダー行以上にしてください。')
        cleansing = values.get('date_cleansing')
        if cleansing not in ('有効', '無効'):
            raise ValueError('日付処理を選択してください。')
        options.update(header_row=header, data_start_row=start,
                       chunk_size=_integer(values, 'chunk_size', 0), date_cleansing=cleansing == '有効')
        defaults.update(header_row=1, data_start_row=2, chunk_size=50000, date_cleansing=True)
        arguments = [ast.keyword(arg='file_path', value=ast.Constant(path))]
    else:
        variable = _identifier(values, 'input_variable')
        arguments = [ast.keyword(arg='data', value=ast.Name(id=variable, ctx=ast.Load())),
                     ast.keyword(arg='output_path', value=ast.Constant(path))]
    # Omit unchanged defaults to keep generated Notebook cells short.
    arguments.extend(ast.keyword(arg=name, value=ast.Constant(value))
                     for name, value in options.items() if value != defaults[name])
    handle = '_zizai_' + module_name if variable == module_name else module_name
    call = ast.Call(func=ast.Attribute(value=ast.Name(id=handle, ctx=ast.Load()), attr=function, ctx=ast.Load()),
                    args=[], keywords=arguments)
    body = [ast.Import(names=[ast.alias(name=module_name, asname=handle if handle != module_name else None)])]
    if reading:
        body.extend([ast.Assign(targets=[ast.Name(id=variable, ctx=ast.Store())], value=call),
                     ast.Expr(value=ast.Name(id=variable, ctx=ast.Load()))])
    else:
        body.append(ast.Expr(value=call))
    return ast.unparse(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))) + '\n'
