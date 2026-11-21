"""Register and search text embeddings in a local DuckDB collection."""
import json
import math
import re
from functools import lru_cache
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd


DEFAULT_MODEL_NAME = 'cl-nagoya/ruri-v3-130m'
_DEFAULT_MODEL_REVISION = 'e3114c6ee10dbab8b4b235fbc6dcf9dd4d5ac1a6'
METRICS = {'cosine', 'l2', 'inner_product', 'l1'}
CORRECTION_DEFAULTS = {'regularization': 0.001, 'density_k': 10, 'penalty_weight': 0.25}
_DB_CONFIG = {
    'enable_external_access': 'false',
    'autoinstall_known_extensions': 'false',
    'autoload_known_extensions': 'false',
    'allow_community_extensions': 'false',
}


def _collection_path(db_folder, collection_name):
    if not isinstance(collection_name, str) or not re.fullmatch(r'[\w-]+', collection_name):
        raise ValueError('コレクション名には英数字・日本語・アンダースコア・ハイフンを使用してください。')
    if not db_folder:
        raise ValueError('ベクトルDBのフォルダーを指定してください。')
    return Path(db_folder).expanduser().resolve() / f'{collection_name}.vector.duckdb'


@lru_cache(maxsize=2)
def _model(model_name):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, device='cpu', trust_remote_code=False,
                               model_kwargs={'use_safetensors': True},
                               revision=_DEFAULT_MODEL_REVISION if model_name == DEFAULT_MODEL_NAME else None)


def _encode(model_name, texts, *, query):
    model = _model(model_name)
    encode = model.encode_query if query else model.encode_document
    options = {'convert_to_numpy': True, 'normalize_embeddings': False, 'show_progress_bar': False}
    if model_name.startswith('cl-nagoya/ruri-v3-'):
        options['prompt'] = '検索クエリ: ' if query else '検索文書: '
    return encode(texts, **options)


def _embeddings(model_name, texts, *, query):
    vectors = np.asarray(_encode(model_name, texts, query=query), dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[0] != len(texts) or not vectors.shape[1] or not np.isfinite(vectors).all():
        raise ValueError('埋め込みモデルが有効なベクトルを返しませんでした。')
    return vectors


def _source_rows(input_data, id_column, text_column):
    if not isinstance(input_data, pd.DataFrame) or input_data.empty:
        raise ValueError('1行以上のDataFrameを指定してください。')
    if not input_data.columns.is_unique or not {id_column, text_column} <= set(input_data.columns):
        raise ValueError('列名は一意で、指定したID列とテキスト列が必要です。')
    if id_column == text_column:
        raise ValueError('ID列とテキスト列は別の列を指定してください。')
    ids, texts = [], []
    for record_id, text in input_data[[id_column, text_column]].itertuples(index=False, name=None):
        if any(not pd.api.types.is_scalar(value) or pd.isna(value) or not str(value).strip()
               for value in (record_id, text)):
            raise ValueError('ID列とテキスト列に空の値や複合値は指定できません。')
        ids.append(str(record_id).strip())
        texts.append(str(text).strip())
    if len(set(ids)) != len(ids):
        raise ValueError('入力DataFrameのID列に重複があります。')
    metadata = input_data.drop(columns=[id_column, text_column])
    serialized = json.loads(metadata.to_json(orient='records', date_format='iso')) if len(metadata.columns) else (
        [{}] * len(ids))
    return ids, texts, [_as_json(row) for row in serialized]


def _as_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _positive_integer(value, label):
    if type(value) is not int or value < 1:
        raise ValueError(f'{label}は1以上の整数で指定してください。')
    return value


def _coefficient(value, label, *, allow_zero=False):
    if (type(value) not in {int, float} or not math.isfinite(value) or value < 0
            or (value == 0 and not allow_zero)):
        raise ValueError(f'{label}が指定範囲外です。')
    return float(value)


def _registration_settings(previous, model_name, metric, enable_correction, parameters):
    if model_name is not None and (not isinstance(model_name, str) or not model_name.strip()):
        raise ValueError('埋め込みモデル名を確認してください。')
    if metric is not None and metric not in METRICS:
        raise ValueError('検索方式を確認してください。')
    if previous and (model_name not in (None, previous['model_name']) or metric not in (None, previous['metric'])):
        raise ValueError('既存コレクションのモデルと検索方式は、新しいコレクションで変更してください。')
    settings = {
        'model_name': model_name or previous.get('model_name', DEFAULT_MODEL_NAME),
        'metric': metric or previous.get('metric', 'cosine'),
    }
    correction = previous.get('correction')
    if enable_correction or correction is not None or any(value is not None for value in parameters.values()):
        tuning = {**CORRECTION_DEFAULTS, **(correction or {})}
        tuning.update({name: value for name, value in parameters.items() if value is not None})
        settings['correction'] = {
            'regularization': _coefficient(tuning['regularization'], '正則化係数'),
            'density_k': _positive_integer(tuning['density_k'], '近傍件数'),
            'penalty_weight': _coefficient(tuning['penalty_weight'], 'ペナルティ係数', allow_zero=True),
        }
    return settings


def _initialize(connection):
    connection.execute('''
        CREATE TABLE IF NOT EXISTS vector_settings (
            singleton BOOLEAN PRIMARY KEY CHECK (singleton), settings JSON NOT NULL
        );
        CREATE TABLE IF NOT EXISTS vector_records (
            id VARCHAR PRIMARY KEY, text VARCHAR NOT NULL, metadata JSON NOT NULL,
            embedding FLOAT[] NOT NULL, whitened DOUBLE[], density DOUBLE
        );
    ''')


def _read_settings(connection):
    row = connection.execute('SELECT settings FROM vector_settings WHERE singleton').fetchone()
    return json.loads(row[0]) if row else {}


def _unit_rows(vectors):
    lengths = np.linalg.norm(vectors, axis=1, keepdims=True)
    return np.divide(vectors, lengths, out=np.zeros_like(vectors), where=lengths != 0)


def _fit_correction(vectors, regularization, density_k):
    center = vectors.mean(axis=0)
    centered = vectors - center
    covariance = centered.T @ centered / max(1, len(vectors) - 1)
    covariance.flat[::covariance.shape[0] + 1] += regularization
    factor = np.linalg.cholesky(covariance)
    transform = np.linalg.solve(factor, np.eye(factor.shape[0]))
    whitened = _unit_rows(centered @ transform.T)
    return center, transform, whitened, _neighborhood_density(whitened, density_k)


def _neighborhood_density(whitened, density_k):
    count = len(whitened)
    k = min(density_k, count - 1)
    density = np.zeros(count)
    if k == 0:
        return density
    # Block the pairwise products so the temporary matrix is bounded by block size × row count.
    for start in range(0, count, 128):
        end = min(start + 128, count)
        scores = whitened[start:end] @ whitened.T
        scores[np.arange(end - start), np.arange(start, end)] = -np.inf
        split = count - k
        scores.partition(split, axis=1)
        density[start:end] = scores[:, split:].mean(axis=1)
    return density


def _rebuild_correction(connection, correction):
    rows = connection.execute('SELECT id, embedding FROM vector_records ORDER BY id').fetchall()
    vectors = np.asarray([row[1] for row in rows], dtype=np.float64)
    center, transform, whitened, density = _fit_correction(vectors, correction['regularization'], correction['density_k'])
    connection.executemany('UPDATE vector_records SET whitened = ?, density = ? WHERE id = ?',
                           zip(whitened.tolist(), density.tolist(), (row[0] for row in rows)))
    correction.update(center=center.tolist(), transform=transform.tolist())


def embedding_vector_db(db_folder, collection_name, input_data, id_column='id', text_column='text', *,
                        model_name=None, metric=None, enable_correction=False,
                        regularization=None, density_k=None, penalty_weight=None):
    """Create a collection or upsert rows, refreshing any enabled correction."""
    path = _collection_path(db_folder, collection_name)
    ids, texts, metadata = _source_rows(input_data, id_column, text_column)
    parameters = {'regularization': regularization, 'density_k': density_k, 'penalty_weight': penalty_weight}
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path), config=_DB_CONFIG) as connection:
        connection.begin()
        _initialize(connection)
        previous = _read_settings(connection)
        settings = _registration_settings(previous, model_name, metric, enable_correction, parameters)
        vectors = _embeddings(settings['model_name'], texts, query=False)
        dimension = vectors.shape[1]
        if dimension != previous.get('dimension', dimension):
            raise ValueError('ベクトルの次元数が既存コレクションと一致しません。')
        settings['dimension'] = dimension
        connection.executemany('''
            INSERT INTO vector_records (id, text, metadata, embedding) VALUES (?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET text = excluded.text, metadata = excluded.metadata,
                embedding = excluded.embedding
        ''', zip(ids, texts, metadata, vectors.tolist()))
        if 'correction' in settings:
            _rebuild_correction(connection, settings['correction'])
        connection.execute('INSERT OR REPLACE INTO vector_settings VALUES (true, ?)', [_as_json(settings)])
        connection.commit()
    return pd.DataFrame([{
        'collection_name': collection_name, 'registered_records': len(ids), 'db_folder': path.parent.as_posix(),
        'database_path': path.as_posix(), 'model_name': settings['model_name'], 'dimension': dimension,
        'metric': settings['metric'], 'correction_enabled': 'correction' in settings,
    }])


def _metric_scores(vectors, query, metric):
    if metric == 'cosine':
        return _unit_rows(vectors) @ _unit_rows(query[None, :])[0]
    if metric == 'inner_product':
        return vectors @ query
    delta = vectors - query
    if metric == 'l1':
        return np.abs(delta).sum(axis=1)
    return np.linalg.norm(delta, axis=1)


def _corrected_scores(rows, query, correction):
    whitened = np.asarray([row[4] for row in rows], dtype=np.float64)
    density = np.asarray([row[5] for row in rows], dtype=np.float64)
    centered = query - np.asarray(correction['center'])
    transformed = _unit_rows((np.asarray(correction['transform']) @ centered)[None, :])[0]
    return whitened @ transformed - correction['penalty_weight'] * density


def _ranked_results(rows, scores, collection_name, top_k, include_vector, *, descending):
    ranking = np.argsort(-scores if descending else scores, kind='stable')[:top_k]
    results = []
    for index in ranking:
        record_id, text, metadata, vector = rows[index][:4]
        result = {'id': record_id, 'text': text, 'score': float(scores[index]),
                  'metadata': metadata, 'collection_name': collection_name}
        if include_vector:
            result['vector'] = _as_json(vector)
        results.append(result)
    return pd.DataFrame(results)


def search_vector_db(db_folder, collection_name, query_text, top_k=5, *,
                     include_vector=False, search_mode='standard'):
    """Return the highest ranked rows, or compare original cosine with correction."""
    path = _collection_path(db_folder, collection_name)
    if not isinstance(query_text, str) or not query_text.strip():
        raise ValueError('検索文を指定してください。')
    _positive_integer(top_k, '取得件数')
    if search_mode not in {'standard', 'corrected', 'compare'}:
        raise ValueError('検索モードを確認してください。')
    if not path.is_file():
        raise FileNotFoundError(f'コレクションが見つかりません: {path.as_posix()}')
    with duckdb.connect(str(path), read_only=True, config=_DB_CONFIG) as connection:
        connection.begin()
        settings = _read_settings(connection)
        correction = settings.get('correction')
        if search_mode != 'standard' and correction is None:
            raise ValueError('補正検索を使うには、登録時に補正検索を有効にしてください。')
        fields = 'id, text, metadata, embedding'
        if search_mode != 'standard':
            fields += ', whitened, density'
        rows = connection.execute(f'SELECT {fields} FROM vector_records ORDER BY id').fetchall()
        connection.commit()

    query = _embeddings(settings['model_name'], [query_text.strip()], query=True)[0].astype(np.float64)
    if len(query) != settings['dimension']:
        raise ValueError('検索ベクトルの次元数がコレクションと一致しません。')
    if search_mode != 'standard':
        corrected = _ranked_results(rows, _corrected_scores(rows, query, correction), collection_name,
                                    top_k, include_vector, descending=True)
        if search_mode == 'corrected':
            return corrected

    metric = 'cosine' if search_mode == 'compare' else settings['metric']
    vectors = np.asarray([row[3] for row in rows], dtype=np.float64)
    ranked = _ranked_results(rows, _metric_scores(vectors, query, metric), collection_name,
                             top_k, include_vector, descending=metric in {'cosine', 'inner_product'})
    if search_mode == 'compare':
        comparison = pd.concat([ranked.add_prefix('cosine_'), corrected.add_prefix('corrected_')], axis=1)
        comparison.insert(0, 'rank', np.arange(1, len(comparison) + 1))
        return comparison
    return ranked
