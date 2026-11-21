"""Pure CSV call generation. Never import a connector, evaluate input, or do IO."""
import ast
from .connector_codegen import _text, _identifier, _integer, form_file_path, form_input_file_path, module_name_for, render_call

GENERATION_KINDS = frozenset({'csv.read_csv', 'csv.write_csv'})


def generate_csv(kind, values, module_path):
    """Return ordinary Python code; filesystem checks belong to execution."""
    if not isinstance(kind, str) or kind not in GENERATION_KINDS:
        raise ValueError('未対応のCSV生成種別です。')
    module_name = module_name_for(module_path)
    reading = kind == 'csv.read_csv'
    path = form_input_file_path(values) if reading else form_file_path(values, default_extension='.csv')
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
        # Older custom definitions can still expose this option.
        cleansing = values.get('date_cleansing', '有効')
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
    return render_call(module_name, function, arguments, variable, reading=reading)
