"""Form support for multiple linear regression."""
from ...connector_codegen import _text
from ...connector_forms.analytics_controls import AnalyticsControls, columns_argument, generate_call

KIND = 'machine_learning.fit_linear_regression'
GENERATION_FIELDS = {KIND: {'input_variable', 'features', 'target', 'categories',
                            'interactions', 'scale', 'output_variable'}}
RESET_DEFAULTS_ON_ACTION_CHANGE = ('output_variable',)


class Controls(AnalyticsControls):
    multi_fields = ('features', 'categories')
    single_fields = ('target',)


def form_controls(form):
    return Controls(form)


def generate(kind, values, module_path):
    if kind != KIND:
        raise ValueError('未対応の機械学習アクションです。')
    features = columns_argument(values, 'features', required=True)
    categories = columns_argument(values, 'categories')
    target = _text(values, 'target', required=True)
    if len(set([*features, *categories, target])) != len(features) + len(categories) + 1:
        raise ValueError('目的変数・数値説明変数・カテゴリ説明変数を重複なく指定してください。')
    if values.get('interactions') and not categories:
        raise ValueError('交互作用を含める場合はカテゴリ説明変数を指定してください。')
    return generate_call(values, module_path, 'fit_linear_regression',
                         {'features': features, 'target': target, 'categories': categories,
                          'interactions': bool(values.get('interactions')),
                          'scale': bool(values.get('scale'))})
