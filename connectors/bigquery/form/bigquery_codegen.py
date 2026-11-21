"""Generate normal Python calls from the BigQuery form."""
import ast

from ...connector_codegen import _identifier, _text, absolute_file_path, module_name_for, render_call


COMMON_FIELDS = {'project_id', 'output_variable'}
GENERATION_FIELDS = {
    'bigquery.execute_sql_file': COMMON_FIELDS | {'sql_file', 'encoding'},
    'bigquery.load_data': COMMON_FIELDS | {'dataset_id', 'table_id', 'input_variable', 'mode', 'schema'},
}
WRITE_MODES = {
    '新規／空テーブル': 'WRITE_EMPTY',
    '追記': 'WRITE_APPEND',
    '置換': 'WRITE_TRUNCATE',
}


def generate_bigquery(kind, values, module_path):
    if kind not in GENERATION_FIELDS:
        raise ValueError('未対応のBigQuery生成種別です。')
    module_name = module_name_for(module_path)
    output = _identifier(values, 'output_variable')
    function = kind.split('.', 1)[1]
    parameters = {'project_id': _text(values, 'project_id', required=True).strip()}
    if function == 'execute_sql_file':
        parameters['sql_file'] = absolute_file_path(values, 'sql_file')
        parameters['encoding'] = _text(values, 'encoding', required=True)
        schema = values.get('output_schema')
    else:
        for name in ('dataset_id', 'table_id'):
            parameters[name] = _text(values, name, required=True).strip()
        disposition = WRITE_MODES.get(values.get('mode'))
        if disposition is None:
            raise ValueError('書き込みモードを選択してください。')
        parameters['write_disposition'] = disposition
        schema = values.get('schema')
    if schema and schema.strip():
        parameters['schema'] = schema
    arguments = [ast.keyword(arg=name, value=ast.Constant(value)) for name, value in parameters.items()]
    if function == 'load_data':
        variable = _identifier(values, 'input_variable')
        arguments.append(ast.keyword(arg='data', value=ast.Name(id=variable, ctx=ast.Load())))
    return render_call(module_name, function, arguments, output, reading=True)
