"""Generate ordinary Python calls for the Vector connector."""
import ast
import math
from pathlib import Path

from .connector_codegen import _identifier, _integer, _text, module_name_for, render_call


BUILD = 'vector.embedding_vector_db'
SEARCH = 'vector.search_vector_db'
CORRECTION_FIELDS = {'enable_correction', 'regularization', 'density_k', 'penalty_weight'}
COMMON_FIELDS = {'db_folder', 'collection_name', 'output_variable'}
GENERATION_FIELDS = {
    BUILD: COMMON_FIELDS | CORRECTION_FIELDS | {'input_variable', 'id_column', 'text_column', 'model_name'},
    SEARCH: COMMON_FIELDS | {'query_text', 'top_k', 'search_mode'},
}
METRICS = {'コサイン類似度': 'cosine', 'ユークリッド距離': 'l2', 'マンハッタン距離': 'l1'}
SEARCH_MODES = {
    'コレクションに登録した検索方式': 'standard',
    'コサイン類似度（補正込み）': 'corrected',
    'コサイン類似度（補正前後を比較）': 'compare',
    # Shared folders can still carry a definition from the previous form.
    '通常検索': 'standard', '補正あり': 'corrected', '通常コサインと比較': 'compare',
}


def _correction_parameters(values):
    parameters = {'enable_correction': True} if values.get('enable_correction') else {}
    for name, label, convert, minimum in (
        ('regularization', '正則化係数', float, 0.0),
        ('density_k', '近傍件数', int, 1),
        ('penalty_weight', 'ペナルティ係数', float, 0.0),
    ):
        text = _text(values, name).strip()
        if not text:
            continue
        try:
            value = convert(text)
        except ValueError as error:
            raise ValueError(f'{label}は数値で指定してください。') from error
        if (convert is float and not math.isfinite(value)) or value < minimum or (name == 'regularization' and value == 0):
            raise ValueError(f'{label}が指定範囲外です。')
        parameters[name] = value
    return parameters


def generate_vector(kind, values, module_path):
    folder = Path(_text(values, 'db_folder', required=True))
    if not folder.is_absolute():
        raise ValueError('フォルダーは絶対パスで指定してください。')
    output = _identifier(values, 'output_variable')
    parameters = {'db_folder': folder.as_posix(),
                  'collection_name': _text(values, 'collection_name', required=True).strip()}
    if kind == BUILD:
        parameters.update(id_column=_text(values, 'id_column', required=True),
                          text_column=_text(values, 'text_column', required=True))
        # The registration form no longer sets a search metric. Accept older YAML definitions.
        metric = ({**METRICS, '内積': 'inner_product'}).get(values.get('metric'))
        if metric is not None:
            parameters['metric'] = metric
        model = _text(values, 'model_name').strip() if values.get('model_name') is not None else ''
        if model:
            parameters['model_name'] = model
        parameters.update(_correction_parameters(values))
    else:
        method = values.get('search_mode')
        metric = METRICS.get(method)
        mode = 'standard' if metric else SEARCH_MODES.get(method)
        if mode is None:
            raise ValueError('検索方法を確認してください。')
        parameters.update(query_text=_text(values, 'query_text', required=True),
                          top_k=_integer(values, 'top_k', 1),
                          search_mode=mode,
                          include_vector=True)
        if metric is not None:
            parameters['metric'] = metric
    arguments = [ast.keyword(arg=name, value=ast.Constant(value)) for name, value in parameters.items()]
    if kind == BUILD:
        arguments.insert(2, ast.keyword(arg='input_data', value=ast.Name(id=_identifier(values, 'input_variable'), ctx=ast.Load())))
    return render_call(module_name_for(module_path), kind.split('.', 1)[1], arguments, output, reading=True)
