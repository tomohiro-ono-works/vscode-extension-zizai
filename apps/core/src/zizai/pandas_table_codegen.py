"""Generate standalone pandas code for sorting, aggregation and joins."""
from unicodedata import normalize

from .connector_codegen import _identifier


SORT_ROWS = 'dataintegration.sort_rows'
AGGREGATE_ROWS = 'dataintegration.aggregate_rows'
COMBINE_FRAMES = 'dataintegration.combine_frames'
TABLE_ACTIONS = {SORT_ROWS, AGGREGATE_ROWS, COMBINE_FRAMES}

AGGREGATIONS = {
    'sum': '合計', 'mean': '平均', 'min': '最小', 'max': '最大', 'count': 'カウント（非NULL）',
    'nunique': '重複なしカウント', 'median': '中央値', 'mode': '最頻値',
}
JOIN_TYPES = {'inner': '内部結合', 'left': '左結合', 'right': '右結合', 'outer': '完全外部結合'}
SET_OPERATIONS = {
    'union_all': '縦結合（すべての行）', 'union_distinct': '縦結合（重複を除く）',
    'except_distinct': 'EXCEPT DISTINCT（左側の行から右側と同じ行を除く）',
}


def column_names(frame):
    names = list(map(str, frame.columns))
    if frame.columns.nlevels != 1 or len(set(names)) != len(names):
        raise ValueError('重複のない1段の列名を使ってください。')
    return dict(zip(names, frame.columns))


def _columns(value, *, allow_empty=False):
    if (not isinstance(value, list) or (not value and not allow_empty)
            or any(not isinstance(column, str) for column in value) or len(set(value)) != len(value)):
        raise ValueError('列を重複なく指定してください。')
    return value


def _rows(settings, name):
    values = settings.get(name)
    if not isinstance(values, list) or not values or any(not isinstance(row, dict) for row in values):
        raise ValueError('設定を1行以上入力してください。')
    return values


def aggregate_specs(settings):
    groups = _columns(settings.get('groups', []), allow_empty=True)
    aggregations = []
    names = set(groups)
    for row in _rows(settings, 'aggregations'):
        column, method, output = row.get('column'), row.get('method'), row.get('output')
        if not isinstance(column, str) or not isinstance(method, str) or method not in AGGREGATIONS:
            raise ValueError('集計列と集計方法を指定してください。')
        if output is None or output == '':
            output = f'{column}_{method}'
        if not isinstance(output, str) or not output.strip() or output in names:
            raise ValueError('集計の出力列名を重複なく指定してください。')
        names.add(output)
        aggregations.append((column, method, output))
    return groups, aggregations


def _first_mode(series):
    return series.mode().reindex([0]).iloc[0]


def aggregate_sample(data, settings):
    """Apply the same aggregation as the generated code to the supplied sample."""
    from pandas import DataFrame

    groups, aggregations = aggregate_specs(settings)
    names = column_names(data)
    if groups:
        by = [names[name] for name in groups]
        fields = {output: (names[col], _first_mode if method == 'mode' else method)
                  for col, method, output in aggregations}
        return data.groupby(by, as_index=False, dropna=False, sort=False, observed=True).agg(**fields)
    return DataFrame([{
        output: _first_mode(data[names[col]]) if method == 'mode' else data[names[col]].agg(method)
        for col, method, output in aggregations
    }])


class TableCode:
    def __init__(self, incoming, output, right=None):
        self.incoming, self.output, self.right = incoming, output, right
        self.names = {normalize('NFKC', name) for name in (incoming, output, right) if name is not None}
        self.lines = []
        self.imports = []
        self.lookups = {}

    def unique(self, name):
        while name in self.names:
            name += '_'
        self.names.add(name)
        return name

    def label(self, frame, label, *, lookup):
        if not lookup:
            return repr(label)
        if frame not in self.lookups:
            name = self.unique('_column_names')
            self.lookups[frame] = name
            self.lines.append(f'{name} = {{f"{{column!s}}": column for column in {frame}.columns}}')
        return f'{self.lookups[frame]}[{label!r}]'

    def labels(self, frame, labels, *, lookup):
        return '[' + ', '.join(self.label(frame, label, lookup=lookup) for label in labels) + ']'

    def pandas(self):
        name = self.unique('pd')
        self.imports.append(f'import pandas as {name}')
        return name

    def sort(self, settings):
        rows = _rows(settings, 'keys')
        columns = _columns([row.get('column') for row in rows])
        ascending = [row.get('ascending') for row in rows]
        na_position, reset = settings.get('na_position', 'last'), settings.get('reset_index', True)
        if any(type(order) is not bool for order in ascending) or na_position not in ('first', 'last') or type(reset) is not bool:
            raise ValueError('並べ替えの順序を確認してください。')
        by = self.labels(self.incoming, columns, lookup=settings.get('lookup_labels') is True)
        self.lines.append(
            f'{self.output} = {self.incoming}.sort_values(by={by}, ascending={ascending}, '
            f'na_position={na_position!r}, ignore_index={reset}, kind="stable")'
        )

    def aggregate(self, settings):
        groups, aggregations = aggregate_specs(settings)
        lookup = settings.get('lookup_labels') is True
        if groups:
            by = self.labels(self.incoming, groups, lookup=lookup)
            fields = []
            for column, method, name in aggregations:
                label = self.label(self.incoming, column, lookup=lookup)
                function = '(lambda values: values.mode().reindex([0]).iloc[0])' if method == 'mode' else repr(method)
                fields.append(f'    {name!r}: ({label}, {function}),')
            self.lines.extend([
                f'{self.output} = {self.incoming}.groupby({by}, as_index=False, dropna=False, sort=False, observed=True).agg(**{{',
                *fields, '})',
            ])
            return
        pandas = self.pandas()
        fields = []
        for column, method, name in aggregations:
            label = self.label(self.incoming, column, lookup=lookup)
            series = f'{self.incoming}[{label}]'
            expression = f'{series}.mode().reindex([0]).iloc[0]' if method == 'mode' else f'{series}.{method}()'
            fields.append(f'    {name!r}: {expression},')
        self.lines.extend([f'{self.output} = {pandas}.DataFrame([{{', *fields, '}])'])

    def combine(self, settings):
        kind = settings.get('kind')
        left_lookup, right_lookup = settings.get('lookup_labels') is True, settings.get('right_lookup') is True
        if kind in JOIN_TYPES:
            keys = _rows(settings, 'keys')
            left = self.labels(self.incoming, _columns([key.get('left') for key in keys]), lookup=left_lookup)
            right = self.labels(self.right, _columns([key.get('right') for key in keys]), lookup=right_lookup)
            self.lines.append(f'{self.output} = {self.incoming}.merge({self.right}, how={kind!r}, '
                              f'left_on={left}, right_on={right})')
            return
        if kind not in SET_OPERATIONS:
            raise ValueError('結合方法を指定してください。')
        columns = _columns(settings.get('columns'))
        left = self.labels(self.incoming, columns, lookup=left_lookup)
        right = self.labels(self.right, columns, lookup=right_lookup)
        pandas = self.pandas()
        if left_lookup or right_lookup:
            self.lines.extend([f'if not {pandas}.Index({left}).equals({pandas}.Index({right})):',
                               '    raise ValueError("両方のDataFrameで対象列の列名を一致させてください。")'])
        if kind in ('union_all', 'union_distinct'):
            concat = f'{pandas}.concat([{self.incoming}.loc[:, {left}], {self.right}.loc[:, {right}]], ignore_index=True)'
            if kind == 'union_distinct':
                concat += '.drop_duplicates(ignore_index=True)'
            self.lines.append(f'{self.output} = {concat}')
            return
        left_rows, right_keys = self.unique('_left_rows'), self.unique('_right_keys')
        self.lines.extend([
            f'{left_rows} = {self.incoming}.loc[:, {left}].drop_duplicates()',
            f'{right_keys} = {pandas}.MultiIndex.from_frame({self.right}.loc[:, {right}].drop_duplicates())',
            f'{self.output} = {left_rows}.loc[~{pandas}.MultiIndex.from_frame({left_rows}).isin({right_keys})]'
            '.reset_index(drop=True)',
        ])

    def render(self):
        before = [*self.imports, ''] if self.imports else []
        return '\n'.join([*before, *self.lines, self.output])


def generate_table_action(kind, incoming, output, settings):
    right = _identifier(settings, 'right') if kind == COMBINE_FRAMES else None
    if any(normalize('NFKC', name) == normalize('NFKC', output) for name in (incoming, right) if name is not None):
        raise ValueError('入力と出力には別の変数名を指定してください。')
    code = TableCode(incoming, output, right)
    try:
        {SORT_ROWS: code.sort, AGGREGATE_ROWS: code.aggregate, COMBINE_FRAMES: code.combine}[kind](settings)
    except (KeyError, TypeError) as error:
        raise ValueError('処理の設定を確認してください。') from error
    return code.render()
