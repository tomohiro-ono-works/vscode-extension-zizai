"""Rename table columns using the RENAME CSV contract from ZizAI."""
import csv
import re
import string

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
