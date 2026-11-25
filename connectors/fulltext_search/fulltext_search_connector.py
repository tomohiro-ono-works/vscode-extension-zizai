"""Local SQLite FTS5 index and BM25 retrieval; no NLP or network dependency."""
from contextlib import closing
from heapq import nsmallest
from numbers import Integral
from pathlib import Path
import json
import re
import sqlite3
import pandas as pd

_MODES = {"trigram": "trigram", "pretokenized": "unicode61"}
_RESULT_COLUMNS = ["id", "text", "score", "rank"]
_DISTANCE_COLUMNS = ["id", "text", "distance", "rank"]

def _path(db_folder, collection_name):
    folder = Path(db_folder)
    if not folder.is_absolute():
        raise ValueError("db_folder must be an absolute path")
    if not isinstance(collection_name,str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}",collection_name):
        raise ValueError("Invalid collection name")
    return folder / (collection_name + ".sqlite")

def _encode_id(value):
    if isinstance(value,str) and value.strip():
        return json.dumps(value,ensure_ascii=False)
    if isinstance(value,Integral) and not isinstance(value,bool):
        return json.dumps(int(value))
    raise ValueError("IDs must be nonempty strings or integers")

def _schema(db, mode):
    db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL)")
    current = db.execute("SELECT value FROM settings WHERE key='tokenizer'").fetchone()
    if current is not None and current[0] != mode:
        raise ValueError("Tokenizer differs from existing collection; use a new collection")
    if current is None:
        db.execute("INSERT INTO settings VALUES ('tokenizer',?)",(mode,))
    db.execute("CREATE TABLE IF NOT EXISTS documents (rowid INTEGER PRIMARY KEY,id TEXT UNIQUE NOT NULL,text TEXT NOT NULL,search_text TEXT NOT NULL)")
    try:
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(search_text, tokenize='"+_MODES[mode]+"')")
    except sqlite3.OperationalError as exc:
        raise RuntimeError("SQLite FTS5 with the requested tokenizer is required") from exc

def build_fulltext_db(db_folder, collection_name, input_data, *, id_column="id",
                      text_column="text", tokenizer="trigram", search_text_column=None):
    """Create or upsert by ID. Optionally store original text separately from indexed text.

    With tokenizer='pretokenized', supply whitespace-delimited tokens for indexing
    and queries, prepared by the caller. No linguistic model is loaded here.
    """
    if tokenizer not in _MODES:
        raise ValueError("Unknown tokenizer")
    if not isinstance(input_data,pd.DataFrame) or not input_data.columns.is_unique:
        raise TypeError("input_data must be a DataFrame with unique column names")
    if id_column in {text_column,search_text_column}:
        raise ValueError("ID and text columns must differ")
    ids = [_encode_id(v) for v in input_data[id_column]]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate IDs in input")
    originals = input_data[text_column].tolist()
    indexed = input_data[search_text_column or text_column].tolist()
    if any(not isinstance(v,str) or "\x00" in v for v in originals+indexed):
        raise ValueError("Text must be non-null strings without NUL characters")
    path = _path(db_folder,collection_name)
    path.parent.mkdir(parents=True,exist_ok=True)
    inserted = updated = 0
    with closing(sqlite3.connect(path)) as db:
        with db:
            db.execute("BEGIN IMMEDIATE")
            _schema(db,tokenizer)
            for key,original,search_text in zip(ids,originals,indexed):
                row = db.execute("SELECT rowid FROM documents WHERE id=?",(key,)).fetchone()
                if row is None:
                    cursor = db.execute("INSERT INTO documents(id,text,search_text) VALUES (?,?,?)",(key,original,search_text))
                    rowid = cursor.lastrowid
                    inserted += 1
                else:
                    rowid = row[0]
                    db.execute("UPDATE documents SET text=?,search_text=? WHERE rowid=?",(original,search_text,rowid))
                    db.execute("DELETE FROM search_index WHERE rowid=?",(rowid,))
                    updated += 1
                db.execute("INSERT INTO search_index(rowid,search_text) VALUES (?,?)",(rowid,search_text))
            total = db.execute("SELECT count(*) FROM documents").fetchone()[0]
    return pd.DataFrame([{"db_file":str(path),"collection_name":collection_name,
                          "tokenizer":tokenizer,"inserted":inserted,"updated":updated,"total":total}])

def _match_expression(query,mode):
    if not isinstance(query,str) or not query.strip() or "\x00" in query:
        raise ValueError("query_text must be a nonempty string without NUL")
    words = query.split()
    if mode == "trigram":
        terms = [word[i:i+3] for word in words for i in range(len(word)-2)]
        if not terms:
            raise ValueError("Trigram queries require at least one three-character term; use a pretokenized collection for shorter terms")
    elif mode == "pretokenized":
        terms = words
    else:
        raise ValueError("Unknown tokenizer")
    terms = list(dict.fromkeys(terms))
    if len(terms)>256:
        raise ValueError("Query exceeds 256 distinct search terms")
    # Literal tokens only; no user-supplied MATCH operators.
    return " OR ".join('"'+term.replace('"','""')+'"' for term in terms)

def search_fulltext_db(db_folder, collection_name, query_text, *, top_k=10):
    """Return BM25-ranked results. Larger score is better (negated FTS5 bm25)."""
    if not isinstance(top_k,Integral) or isinstance(top_k,bool) or top_k<1:
        raise ValueError("top_k must be a positive integer")
    path = _path(db_folder,collection_name)
    if not path.is_file():
        raise FileNotFoundError(path)
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)) as db:
        row = db.execute("SELECT value FROM settings WHERE key='tokenizer'").fetchone()
        if row is None:
            raise ValueError("Missing tokenizer settings")
        expression = _match_expression(query_text,row[0])
        rows = db.execute("""
            SELECT d.id,d.text,-bm25(search_index) AS score
            FROM search_index JOIN documents AS d ON d.rowid=search_index.rowid
            WHERE search_index MATCH ?
            ORDER BY score DESC,d.rowid ASC LIMIT ?
        """,(expression,int(top_k))).fetchall()
    return pd.DataFrame([(json.loads(key),text,score,rank)
                         for rank,(key,text,score) in enumerate(rows,1)],
                        columns=_RESULT_COLUMNS)


def _levenshtein_within(query, target, limit):
    """Return the edit distance when it is within the limit."""
    if abs(len(query) - len(target)) > limit:
        return None

    outside = limit + 1
    previous = {column: column for column in range(min(len(target), limit) + 1)}
    for row, character in enumerate(query, 1):
        current = {0: row} if row <= limit else {}
        start = max(1, row - limit)
        end = min(len(target), row + limit)
        for column in range(start, end + 1):
            current[column] = min(
                previous.get(column, outside) + 1,
                current.get(column - 1, outside) + 1,
                previous.get(column - 1, outside) + (character != target[column - 1]),
            )
        if min(current.values(), default=outside) > limit:
            return None
        previous = current
    distance = previous.get(len(target), outside)
    return distance if distance <= limit else None


def search_levenshtein(db_folder, collection_name, query_text, *, max_distance=2, top_k=10):
    """Rank complete stored search strings by their character edit distance."""
    if not isinstance(query_text, str) or not query_text.strip() or "\x00" in query_text:
        raise ValueError("query_text must be a nonempty string without NUL")
    if not isinstance(max_distance, Integral) or isinstance(max_distance, bool) or max_distance < 0:
        raise ValueError("max_distance must be a nonnegative integer")
    if not isinstance(top_k, Integral) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError("top_k must be a positive integer")

    path = _path(db_folder, collection_name)
    if not path.is_file():
        raise FileNotFoundError(path)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        documents = db.execute("SELECT rowid, id, text, search_text FROM documents")
        candidates = (
            (distance, rowid, key, text)
            for rowid, key, text, target in documents
            if (distance := _levenshtein_within(query_text, target, int(max_distance))) is not None
        )
        rows = nsmallest(int(top_k), candidates)
    return pd.DataFrame(
        [(json.loads(key), text, distance, rank)
         for rank, (distance, _, key, text) in enumerate(rows, 1)],
        columns=_DISTANCE_COLUMNS,
    )
