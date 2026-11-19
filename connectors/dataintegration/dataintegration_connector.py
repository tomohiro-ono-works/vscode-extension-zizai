"""Independent DataFrame column operations and RENAME list processing."""
import csv
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
        key = change.get('column')
        if not isinstance(key, str) or key not in columns:
            raise ValueError(f'対象列が見つかりません: {key}')
        output = change.get('output')
        if 'output' in change and (not isinstance(output, str) or not output.strip()):
            raise ValueError('新しい列名を入力してください。')
        if output in columns:
            raise ValueError(f'同じ列名が既にあります: {output}')
        destination = columns[key] if output is None else output
        series = frame[columns[key]]
        op = change.get('op')
        if not isinstance(op, str):
            raise ValueError('値加工の操作を指定してください。')
        try:
            if op in _TEXT_METHODS or op in ('replace_exact', 'replace_part', 'concat', 'split', 'extract_regex'):
                result = _text_result(frame, columns, series, change, op)
            elif op in _ARITHMETIC or op in ('round', 'abs'):
                result = _numeric_result(frame, columns, series, change, op)
            elif op in ('to_null', 'fill_null'):
                value = change.get('value')
                if type(value) not in (str, int, float, bool) or (type(value) is float and not isfinite(value)):
                    raise ValueError('文字列、数値、真偽値のいずれかを指定してください。')
                result = (series.mask(series.eq(value).fillna(False), pd.NA) if op == 'to_null'
                          else series.fillna(value))
            else:
                raise ValueError('未対応の値加工です。')
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f'「{key}」列: {error}') from error
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
