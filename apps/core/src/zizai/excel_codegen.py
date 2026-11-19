"""Generate safe Python calls for the three Excel form actions."""
import ast
from pathlib import Path
from .connector_codegen import _identifier, _integer, _text, form_file_path, form_input_file_path, module_name_for, render_call


COMMON_FIELDS = {'folder', 'filename', 'sheet_name', 'schema'}
READ_FIELDS = COMMON_FIELDS | {'output_variable', 'header_row', 'data_start_row'}
GENERATION_FIELDS = {
    'excel.read_excel': READ_FIELDS | {'chunk_size'},
    'excel.read_excel_range': READ_FIELDS | {'cell_range'},
    'excel.write_excel': COMMON_FIELDS | {'input_variable', 'mode'},
}


def generate_excel(kind, values, module_path):
    module_name = module_name_for(module_path)
    reading = kind != 'excel.write_excel'
    path = form_input_file_path(values) if reading else form_file_path(values, default_extension='.xlsx')
    if Path(path).suffix.lower() != '.xlsx':
        raise ValueError('Excelファイルには .xlsx を指定してください。')

    sheet_name = _text(values, 'sheet_name', required=True)
    schema = _text(values, 'schema')
    options = {'sheet_name': sheet_name}
    if reading:
        variable = _identifier(values, 'output_variable')
        arguments = [ast.keyword(arg='file_path', value=ast.Constant(path))]
        header = _integer(values, 'header_row', 1)
        start = _integer(values, 'data_start_row', 1)
        if start < header:
            raise ValueError('データ開始行はヘッダー行以上にしてください。')
        if header != 1:
            options['header_row'] = header
        if start != 2:
            options['data_start_row'] = start
        if kind == 'excel.read_excel_range':
            options['cell_range'] = _text(values, 'cell_range', required=True).strip()
        else:
            chunk_size = _integer(values, 'chunk_size', 1)
            if chunk_size != 50000:
                options['chunk_size'] = chunk_size
    else:
        variable = _identifier(values, 'input_variable')
        arguments = [ast.keyword(arg='data', value=ast.Name(id=variable, ctx=ast.Load())),
                     ast.keyword(arg='output_path', value=ast.Constant(path))]
        mode = values.get('mode')
        if mode not in ('create_or_replace', 'create_or_insert'):
            raise ValueError('書き込みモードを選択してください。')
        options['mode'] = mode
    if schema.strip():
        options['schema'] = schema
    arguments.extend(ast.keyword(arg=name, value=ast.Constant(value)) for name, value in options.items())
    function = kind.split('.', 1)[1]
    return render_call(module_name, function, arguments, variable, reading=reading)
