"""Independent DataFrame column operations and RENAME list processing."""
import csv
from itertools import groupby
from math import isfinite
import operator
import re
import string

import pandas as pd

from zizai.core.tabular import TabularOperations
from zizai.core.type_registry import build_dataframe_schema, resolve_pandas_type


PRE_CLEANING = {'remove_spaces', 'remove_newlines', 'to_halfwidth_alnum', 'symbols_to_snake'}
HALFWIDTH = str.maketrans(
    '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
    string.digits + string.ascii_uppercase + string.ascii_lowercase,
)
SYMBOLS = re.compile(f'[{re.escape(string.punctuation)}]+')
JAPANESE = re.compile(r'[\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]')


def _clean_column(name, options):
    if 'remove_spaces' in options:
        name = name.replace(' ', '').replace('　', '')
    if 'remove_newlines' in options:
        name = name.replace('\r', '').replace('\n', '')
    if 'to_halfwidth_alnum' in options:
        name = name.translate(HALFWIDTH)
    if 'symbols_to_snake' in options:
        name = SYMBOLS.sub('_', name).strip('_')
    return name.strip()


def _read_mappings(path, options):
    with open(path, encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        headers = {header.strip().lower(): header for header in (reader.fieldnames or ())}

        def find(*names):
            return next((headers[name] for name in names if name in headers), None)

        origin = find('origin_name', '元フィールド名')
        target = find('replaced_name', 'new_name', '新フィールド名')
        description = find('description', '説明', '日本語名')
        datatype = find('ziz_datatype', 'datatype', 'データ型')
        if not origin or not target:
            raise ValueError('RENAMEリストには origin_name と replaced_name（または new_name）が必要です。')
        mappings = {}
        for row in reader:
            old = _clean_column(row.get(origin) or '', options)
            new = (row.get(target) or '').strip()
            if not old or not new:
                continue
            entry = (new, (row.get(description) or '').strip(), (row.get(datatype) or '').strip().upper())
            if old in mappings and mappings[old] != entry:
                raise ValueError(f'RENAMEリストの定義が矛盾しています: {old}')
            mappings[old] = entry
        return mappings


def replace_fields_forrenamelist(data, rename_list_path, *, pre_rename_cleansing=(),
                                exclude_japanese_columns=False):
    """Return renamed columns and optional declared types without changing the input."""
    options = set(pre_rename_cleansing)
    if options - PRE_CLEANING:
        raise ValueError('リネーム前のクレンジング指定が不正です。')
    if type(exclude_japanese_columns) is not bool:
        raise TypeError('exclude_japanese_columnsには真偽値を指定してください。')

    frame = TabularOperations.to_dataframe(data)
    mappings = _read_mappings(rename_list_path, options)
    if not mappings:
        frame.attrs.setdefault('ziz_schema', build_dataframe_schema(frame))
        return frame

    original = list(frame.columns)
    cleaned = [_clean_column(str(column), options) or f'column_{index}'
               for index, column in enumerate(original, 1)] if options else original
    targets = [mappings[name][0] if name in mappings else name for name in cleaned]
    if frame.columns.has_duplicates or len(set(cleaned)) != len(cleaned) or len(set(targets)) != len(targets):
        raise ValueError('リネーム後またはクレンジング後に列名が重複します。')

    source_schema = {str(item.get('new_name') or item.get('origin_name')): item
                     for item in (frame.attrs.get('ziz_schema') or ()) if isinstance(item, dict)}
    frame.columns = targets
    kept = [(src, name, dest) for src, name, dest in zip(original, cleaned, targets)
            if not exclude_japanese_columns or not JAPANESE.search(str(dest))]
    result = frame.loc[:, [dest for _, _, dest in kept]].copy()
    schema = []
    for (src, name, dest), inferred in zip(kept, build_dataframe_schema(result)):
        item = {**source_schema.get(str(src), inferred), 'origin_name': str(dest), 'new_name': str(dest)}
        if name in mappings:
            _, description, datatype = mappings[name]
            if description:
                item['description'] = description
            if datatype:
                try:
                    resolve_pandas_type(datatype)
                except KeyError as error:
                    raise ValueError(f'RENAMEリストのデータ型が未対応です: {datatype}') from error
                item['ziz_datatype'] = datatype
                converted = TabularOperations.apply_schema_to_dataframe(result[[dest]], [item])
                result[dest] = converted[dest]
        schema.append(item)
    result.attrs['ziz_schema'] = schema
    return result


COLUMN_TYPES = {'text': 'STRING', 'integer': 'INT64', 'number': 'FLOAT64', 'date': 'DATE'}


def _convert_column(series, target):
    if target == 'text':
        return series.astype('string')
    if target == 'date':
        converted = pd.to_datetime(series.astype('string'), format='mixed').dt.normalize()
    else:
        dtype = 'Int64' if target == 'integer' else 'Float64'
        converted = pd.to_numeric(series).astype(dtype)
    if (series.notna() & converted.isna()).any():
        raise ValueError('変換できない値があります。')
    return converted


def _operation_frame(data, operations, label):
    if not isinstance(data, pd.DataFrame):
        raise TypeError('入力にはDataFrameを指定してください。')
    if not isinstance(operations, (list, tuple)):
        raise ValueError(f'{label}は操作の一覧で指定してください。')
    names = list(map(str, data.columns))
    if isinstance(data.columns, pd.MultiIndex) or len(set(names)) != len(names):
        raise ValueError(f'{label}には、重複のない1段の列名が必要です。')
    return data.copy()


def apply_column_operations(data, *, operations):
    """Apply ordered, name-based column operations to a separate DataFrame."""
    frame = _operation_frame(data, operations, '列操作')
    metadata = {str(item.get('new_name') or item.get('origin_name')): item.copy()
                for item in (frame.attrs.get('ziz_schema') or ()) if isinstance(item, dict)}

    for change in operations:
        if not isinstance(change, dict):
            raise ValueError('列操作の設定が不正です。')
        op = change.get('op')
        columns = dict(zip(map(str, frame.columns), frame.columns))
        if op in ('keep', 'drop'):
            selected = change.get('columns')
            if (not isinstance(selected, list) or not selected
                    or any(not isinstance(name, str) or name not in columns for name in selected)):
                raise ValueError('対象列が見つかりません。')
            selected = set(selected)
            labels = [label for key, label in columns.items() if (key in selected) == (op == 'keep')]
            frame = frame.loc[:, labels]
            metadata = {str(label): metadata[str(label)] for label in labels if str(label) in metadata}
            continue

        key = change.get('column')
        if not isinstance(key, str) or key not in columns:
            raise ValueError(f'対象列が見つかりません: {key}')
        label = columns[key]
        if op in ('rename', 'duplicate'):
            name = change.get('name')
            if not isinstance(name, str) or not name.strip():
                raise ValueError('新しい列名を入力してください。')
            if name in columns:
                raise ValueError(f'同じ列名が既にあります: {name}')
            if op == 'rename':
                frame = frame.rename(columns={label: name})
            else:
                frame.insert(frame.columns.get_loc(label) + 1, name, frame[label].copy())
            if key in metadata:
                metadata[name] = metadata[key].copy()
                if op == 'rename':
                    del metadata[key]
        elif op == 'move':
            position = change.get('position')
            if type(position) is not int or not 1 <= position <= len(columns):
                raise ValueError('移動先の位置を列数の範囲内で指定してください。')
            labels = [value for name, value in columns.items() if name != key]
            labels.insert(position - 1, label)
            frame = frame.loc[:, labels]
        elif op == 'convert':
            target = change.get('type')
            if not isinstance(target, str) or target not in COLUMN_TYPES:
                raise ValueError('変換後のデータ型を指定してください。')
            try:
                frame[label] = _convert_column(frame[label], target)
            except (ValueError, TypeError, OverflowError) as error:
                raise ValueError(f'「{key}」列に変換できない値があります。') from error
            if 'ziz_schema' in frame.attrs:
                metadata.setdefault(key, {})['ziz_datatype'] = COLUMN_TYPES[target]
        else:
            raise ValueError('未対応の列操作です。')

    if 'ziz_schema' in frame.attrs and operations:
        frame.attrs['ziz_schema'] = [
            {**inferred, **metadata.get(str(label), {}), 'origin_name': str(label), 'new_name': str(label)}
            for label, inferred in zip(frame.columns, build_dataframe_schema(frame))
        ]
    return frame


_TEXT_METHODS = {'trim': 'strip', 'upper': 'upper', 'lower': 'lower'}
_ARITHMETIC = {
    'add': operator.add, 'subtract': operator.sub,
    'multiply': operator.mul, 'divide': operator.truediv,
}


def _value_text(change, key, label, *, required=False):
    value = change.get(key)
    if not isinstance(value, str) or (required and not value):
        raise ValueError(f'{label}を入力してください。')
    return value


def _value_operand(frame, columns, change):
    key = change.get('other_column')
    if not isinstance(key, str) or key not in columns:
        raise ValueError(f'相手列が見つかりません: {key}')
    return frame[columns[key]]


def _text_result(frame, columns, series, change, op):
    text = series.astype('string')
    if op in _TEXT_METHODS:
        return getattr(text.str, _TEXT_METHODS[op])()
    if op in ('replace_exact', 'replace_part'):
        search = _value_text(change, 'search', '検索文字列', required=op == 'replace_part')
        replacement = _value_text(change, 'replacement', '置換後の文字列')
        if op == 'replace_exact':
            return text.mask(text.eq(search).fillna(False), replacement)
        return text.str.replace(search, replacement, regex=False)
    if op == 'concat':
        other = _value_operand(frame, columns, change).astype('string')
        return text.str.cat(other, sep=_value_text(change, 'separator', '区切り文字'))
    if op == 'split':
        separator = _value_text(change, 'separator', '区切り文字', required=True)
        position = change.get('position')
        if type(position) is not int or position < 1:
            raise ValueError('取り出す位置を1以上で指定してください。')
        return text.str.split(separator, regex=False).str.get(position - 1).astype('string')
    pattern = _value_text(change, 'pattern', '正規表現', required=True)
    try:
        expression = re.compile(pattern)
    except re.error as error:
        raise ValueError(f'正規表現が不正です: {error}') from error
    group = change.get('group', 0)
    if type(group) is not int or not 0 <= group <= expression.groups:
        raise ValueError('正規表現のグループ番号を確認してください。0は一致全体です。')

    def extract(value):
        match = expression.search(value)
        return match.group(group) if match else pd.NA

    return text.map(extract, na_action='ignore').astype('string')


def _numeric(series):
    numeric = pd.to_numeric(series)
    if (series.notna() & numeric.isna()).any():
        raise ValueError('数値に変換できない値があります。')
    return numeric


def _formula_result(frame, columns, expression):
    from zizai.arithmetic_formula import ArithmeticFormula
    from pandas.api.types import is_bool_dtype, is_complex_dtype, is_numeric_dtype

    def column(name):
        if name not in columns:
            raise ValueError(f'計算式の列が見つかりません: {name}')
        series = frame[columns[name]]
        if not is_numeric_dtype(series) or is_bool_dtype(series) or is_complex_dtype(series):
            raise ValueError(f'「{name}」は数値列ではありません。')
        return series

    return ArithmeticFormula(expression).evaluate(column)


def _timestamp(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('日付・日時を入力してください。')
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError('有効な日付・日時を入力してください。')
    return timestamp


def _numeric_result(frame, columns, series, change, op):
    left = _numeric(series)
    if op == 'abs':
        return left.abs()
    if op == 'round':
        digits = change.get('digits')
        if type(digits) is not int:
            raise ValueError('丸め桁数は整数で指定してください。')
        return left.round(digits)
    if 'other_column' in change:
        right = _numeric(_value_operand(frame, columns, change))
        zero = right.eq(0).any()
    else:
        right = change.get('number')
        if type(right) not in (int, float) or not isfinite(right):
            raise ValueError('固定値には有限の数値を指定してください。')
        zero = right == 0
    if op == 'divide' and zero:
        raise ValueError('0で割ることはできません。')
    return _ARITHMETIC[op](left, right)


def apply_value_operations(data, *, operations):
    """Apply ordered value changes into the selected or a new column in a copy."""
    frame = _operation_frame(data, operations, '値加工')
    changed = set()
    for change in operations:
        if not isinstance(change, dict):
            raise ValueError('値加工の設定が不正です。')
        columns = dict(zip(map(str, frame.columns), frame.columns))
        output = change.get('output')
        key = change.get('column')
        op = change.get('op')
        new_formula = op == 'formula' and 'output' in change and key is None
        if not new_formula and (not isinstance(key, str) or key not in columns):
            raise ValueError(f'対象列が見つかりません: {key}')
        if 'output' in change and (not isinstance(output, str) or not output.strip()):
            raise ValueError('新しい列名を入力してください。')
        if output in columns:
            raise ValueError(f'同じ列名が既にあります: {output}')
        destination = columns[key] if output is None else output
        series = None if new_formula else frame[columns[key]]
        if not isinstance(op, str):
            raise ValueError('値加工の操作を指定してください。')
        try:
            if op in _TEXT_METHODS or op in ('replace_exact', 'replace_part', 'concat', 'split', 'extract_regex'):
                result = _text_result(frame, columns, series, change, op)
            elif op in _ARITHMETIC or op in ('round', 'abs'):
                result = _numeric_result(frame, columns, series, change, op)
            elif op == 'formula':
                result = _formula_result(frame, columns, change.get('expression'))
            elif op in ('to_null', 'fill_null'):
                value = change.get('value')
                if type(value) not in (str, int, float, bool) or (type(value) is float and not isfinite(value)):
                    raise ValueError('文字列、数値、真偽値のいずれかを指定してください。')
                if change.get('value_type') == 'datetime':
                    value = _timestamp(value)
                result = (series.mask(series.eq(value).fillna(False), pd.NA) if op == 'to_null'
                          else series.fillna(value))
            else:
                raise ValueError('未対応の値加工です。')
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f'「{output if new_formula else key}」列: {error}') from error
        frame[destination] = result
        changed.add(str(destination))

    if changed and 'ziz_schema' in frame.attrs:
        metadata = {str(item.get('new_name') or item.get('origin_name')): item
                    for item in (frame.attrs.get('ziz_schema') or ()) if isinstance(item, dict)}
        schema = []
        for label, inferred in zip(frame.columns, build_dataframe_schema(frame)):
            name = str(label)
            item = {**inferred, **metadata.get(name, {}), 'origin_name': name, 'new_name': name}
            if name in changed:
                item['ziz_datatype'] = inferred['ziz_datatype']
            schema.append(item)
        frame.attrs['ziz_schema'] = schema
    return frame


_ROW_NUMERIC_COMPARISONS = {
    'number_equal': operator.eq, 'greater': operator.gt, 'greater_equal': operator.ge,
    'less': operator.lt, 'less_equal': operator.le,
}


def _row_bound(value):
    if type(value) not in (int, float) or (type(value) is float and not isfinite(value)):
        raise ValueError('比較値には有限の数値を指定してください。')
    return value


def _row_condition(frame, columns, condition):
    column = condition.get('column')
    if not isinstance(column, str) or column not in columns:
        raise ValueError('対象列を選択してください。')
    series = frame[columns[column]]
    comparison = condition.get('comparison')
    value = condition.get('value')
    if comparison == 'is_null':
        return series.isna()
    if comparison == 'not_null':
        return series.notna()
    if comparison == 'bool_equal':
        if type(value) is not bool:
            raise ValueError('比較する真偽値を選択してください。')
        return series.eq(value).fillna(False)
    if comparison in ('date_equal', 'date_before', 'date_after', 'date_between'):
        lower = _timestamp(value)
        if comparison == 'date_between':
            upper = _timestamp(condition.get('upper'))
            if upper < lower:
                raise ValueError('範囲の下限は上限以下にしてください。')
            return series.between(lower, upper).fillna(False)
        method = {'date_equal': 'eq', 'date_before': 'lt', 'date_after': 'gt'}[comparison]
        return getattr(series, method)(lower).fillna(False)
    if comparison in ('text_equal', 'contains'):
        if not isinstance(value, str) or (comparison == 'contains' and not value):
            raise ValueError('比較する文字列を入力してください。')
        text = series.astype('string')
        result = text.eq(value) if comparison == 'text_equal' else text.str.contains(value, regex=False, na=False)
        return result.fillna(False)
    if not isinstance(comparison, str) or (comparison != 'between' and comparison not in _ROW_NUMERIC_COMPARISONS):
        raise ValueError('比較方法を選択してください。')
    try:
        numeric = _numeric(series)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError(f'「{column}」列に数値として比較できない値があります。') from error
    lower = _row_bound(value)
    if comparison == 'between':
        upper = _row_bound(condition.get('upper'))
        if upper < lower:
            raise ValueError('範囲の下限は上限以下にしてください。')
        return numeric.between(lower, upper).fillna(False)
    return _ROW_NUMERIC_COMPARISONS[comparison](numeric, lower).fillna(False)


def _row_mask(frame, columns, conditions):
    if not isinstance(conditions, list) or not conditions or any(not isinstance(item, dict) for item in conditions):
        raise ValueError('条件を1件以上設定してください。')
    # Combine AND runs before folding them into the OR result.
    current = _row_condition(frame, columns, conditions[0])
    disjunction = None
    for condition in conditions[1:]:
        mask = _row_condition(frame, columns, condition)
        logic = condition.get('logic')
        if logic == 'and':
            current = current & mask
        elif logic == 'or':
            disjunction = current if disjunction is None else disjunction | current
            current = mask
        else:
            raise ValueError('条件の結合にはANDまたはORを指定してください。')
    return current if disjunction is None else disjunction | current


def _row_steps(operations):
    pending = None
    for change in operations:
        if not isinstance(change, dict):
            raise ValueError('行の条件の設定が不正です。')
        if change.get('op') != 'condition':
            if pending is not None:
                yield pending
                pending = None
            yield change
            continue
        mode, rule = change.get('mode'), change.get('condition')
        if not isinstance(rule, dict):
            raise ValueError('条件の設定を確認してください。')
        logic = rule.get('logic')
        if logic not in (None, 'and', 'or'):
            raise ValueError('条件の結合にはANDまたはORを指定してください。')
        if pending is not None and mode == pending['mode'] and logic is not None:
            pending['conditions'].append(rule)
        else:
            if pending is not None:
                yield pending
            first = {key: value for key, value in rule.items() if key != 'logic'}
            pending = {'op': 'filter', 'mode': mode, 'conditions': [first]}
    if pending is not None:
        yield pending


def filter_rows(data, *, operations):
    """Select and clean rows in order, preserving the original input and index."""
    frame = _operation_frame(data, operations, '行の条件')
    columns = dict(zip(map(str, frame.columns), frame.columns))
    for change in _row_steps(operations):
        op = change.get('op')
        if op == 'filter':
            mode = change.get('mode')
            if mode not in ('keep', 'exclude'):
                raise ValueError('抽出または除外を選択してください。')
            try:
                mask = _row_mask(frame, columns, change.get('conditions'))
            except (TypeError, OverflowError) as error:
                raise ValueError(f'条件の比較値を確認してください: {error}') from error
            frame = frame.loc[mask if mode == 'keep' else ~mask]
        elif op in ('drop_duplicates', 'drop_nulls'):
            selected = change.get('columns', [])
            if not isinstance(selected, list) or any(not isinstance(key, str) or key not in columns for key in selected):
                raise ValueError('判定する列を確認してください。')
            subset = [columns[key] for key in selected] or None
            frame = frame.drop_duplicates(subset=subset) if op == 'drop_duplicates' else frame.dropna(subset=subset)
        elif op in ('head', 'tail'):
            count = change.get('count')
            if type(count) is not int or count < 0:
                raise ValueError('行数は0以上の整数で指定してください。')
            frame = frame.head(count) if op == 'head' else frame.tail(count)
        else:
            raise ValueError('未対応の行操作です。')
    return frame


def apply_data_operations(data, *, operations):
    """Apply mixed value and row operations in the order supplied."""
    if not isinstance(operations, (list, tuple)):
        raise ValueError('処理は操作の一覧で指定してください。')
    if not operations:
        return _operation_frame(data, operations, 'データ加工')
    if any(not isinstance(step, dict) or not isinstance(step.get('operation'), dict) for step in operations):
        raise ValueError('処理の設定を確認してください。')
    functions = {'condition': filter_rows, 'value': apply_value_operations}
    result = data
    for category, steps in groupby(operations, key=lambda step: step.get('category')):
        if not isinstance(category, str) or category not in functions:
            raise ValueError('処理分類を確認してください。')
        result = functions[category](result, operations=[step['operation'] for step in steps])
    return result


def join_frames(left, right, *, keys, how='inner', match_policy='all'):
    """Join using AND-connected exact/contains/prefix/suffix keys.

    For textual keys, the left value is the text and the right value is
    the search term. First match means the earliest right row per left
    row, regardless of join type. Outer joins retain all unpaired rows.
    """
    if how not in ('inner', 'left', 'right', 'outer'):
        raise ValueError('結合方式を確認してください。')
    if match_policy not in ('all', 'first'):
        raise ValueError('マッチ方式を確認してください。')
    if not isinstance(keys, (list, tuple)) or not keys:
        raise ValueError('結合キーを指定してください。')
    modes = ('exact', 'contains', 'prefix', 'suffix')
    def labels(frame):
        if not isinstance(frame, pd.DataFrame) or frame.columns.nlevels != 1:
            raise ValueError('1段の列名を持つDataFrameを指定してください。')
        result = dict(zip(map(str, frame.columns), frame.columns))
        if len(result) != len(frame.columns):
            raise ValueError('列名は重複なく指定してください。')
        return result
    left_labels, right_labels = labels(left), labels(right)
    resolved = []
    for key in keys:
        if not isinstance(key, dict):
            raise ValueError('結合キーを確認してください。')
        l, r, mode = key.get('left'), key.get('right'), key.get('match', 'exact')
        if l not in left_labels or r not in right_labels or mode not in modes:
            raise ValueError('結合キー・一致方式を確認してください。')
        resolved.append((left_labels[l], right_labels[r], mode))
    if any(len(set(row[i] for row in resolved)) != len(resolved) for i in (0, 1)):
        raise ValueError('左右それぞれの結合キーを重複なく指定してください。')
    exact = [(l, r) for l, r, mode in resolved if mode == 'exact']
    textual = [(l, r, mode) for l, r, mode in resolved if mode != 'exact']
    if not textual and match_policy == 'all':
        return left.merge(right, how=how, left_on=[l for l, r in exact],
                          right_on=[r for l, r in exact], sort=False)

    # Match positional row IDs, never index labels (which may be duplicated).
    # Exact keys narrow the candidate set before any text matching.
    import numpy as np
    left_ids = np.arange(len(left), dtype='int64')
    right_ids = np.arange(len(right), dtype='int64')
    left_pos, right_pos = '__left_position', '__right_position'
    if exact:
        lk = pd.DataFrame({left_pos: left_ids})
        rk = pd.DataFrame({right_pos: right_ids})
        for i, (l, r) in enumerate(exact):
            lk[i] = left[l].reset_index(drop=True)
            rk[i] = right[r].reset_index(drop=True)
        exact_columns = list(range(len(exact)))
        if match_policy == 'first' and not textual:
            rk = rk.drop_duplicates(subset=exact_columns, keep='first')
        candidates = lk.merge(rk, on=exact_columns, how='inner', sort=False)
        candidates = candidates.sort_values([left_pos, right_pos], kind='stable')
        groups = ((int(i), group[right_pos].to_numpy())
                  for i, group in candidates.groupby(left_pos, sort=False))
    else:
        groups = ((int(i), right_ids) for i in left_ids)

    left_text = [left[l].astype('string').tolist() for l, _, _ in textual]
    right_text = [right[r].astype('string').tolist() for _, r, _ in textual]
    comparisons = [mode for _, _, mode in textual]
    def matches(i, j):
        for a, b, mode in zip(left_text, right_text, comparisons):
            value, term = a[i], b[j]
            if pd.isna(value) or pd.isna(term) or not term:
                return False
            if mode == 'contains' and term not in value:
                return False
            if mode == 'prefix' and not value.startswith(term):
                return False
            if mode == 'suffix' and not value.endswith(term):
                return False
        return True

    pairs = []
    used_left, used_right = set(), set()
    for i, candidates in groups:
        for j in candidates:
            j = int(j)
            if matches(i, j):
                pairs.append((i, j))
                used_left.add(i)
                used_right.add(j)
                if match_policy == 'first':
                    break
    if how in ('left', 'outer'):
        pairs.extend((int(i), -1) for i in left_ids if i not in used_left)
    if how in ('right', 'outer'):
        pairs.extend((-1, int(j)) for j in right_ids if j not in used_right)
    if how == 'right':
        pairs.sort(key=lambda p: (p[1], p[0]))
    else:
        pairs.sort(key=lambda p: (p[0] < 0, p[0], p[1]))

    # Preserve both non-exact key values. Same-name exact keys coalesce
    # like pandas.merge. Other overlapping labels receive _x/_y suffixes.
    shared_exact = {l for l, r in exact if l == r}
    overlap = (set(left.columns) & set(right.columns)) - shared_exact
    li = [i for i, _ in pairs]
    ri = [j for _, j in pairs]
    lout = left.reset_index(drop=True).reindex(li).reset_index(drop=True)
    rout = right.reset_index(drop=True).reindex(ri).reset_index(drop=True)
    for name in shared_exact:
        combined = pd.concat([left[name], right[name]], ignore_index=True)
        positions = [i if i >= 0 else len(left) + j for i, j in pairs]
        lout[name] = combined.iloc[positions].reset_index(drop=True)
    rout = rout.drop(columns=list(shared_exact))
    lout = lout.rename(columns={name: f'{name}_x' for name in overlap})
    rout = rout.rename(columns={name: f'{name}_y' for name in overlap})
    result = pd.concat([lout, rout], axis=1)
    labels(result)
    return result
