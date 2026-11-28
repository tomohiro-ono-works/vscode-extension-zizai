"""Form support for descriptive statistics."""
from ...connector_forms.analytics_controls import AnalyticsControls, columns_argument, generate_call

KIND = 'statistics.describe'
GENERATION_FIELDS = {KIND: {'input_variable', 'columns', 'group_columns', 'output_variable'}}
RESET_DEFAULTS_ON_ACTION_CHANGE = ('output_variable',)


class Controls(AnalyticsControls):
    multi_fields = ('columns', 'group_columns')


def form_controls(form):
    return Controls(form)


def generate(kind, values, module_path):
    if kind != KIND:
        raise ValueError('未対応の統計分析アクションです。')
    columns = columns_argument(values, 'columns', required=True)
    groups = columns_argument(values, 'group_columns')
    if set(columns) & set(groups):
        raise ValueError('分析対象列とグループ列を分けてください。')
    return generate_call(values, module_path, 'describe',
                         {'columns': columns, 'group_columns': groups})
