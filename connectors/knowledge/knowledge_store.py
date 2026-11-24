"""Local SQLite-backed RDFLib store."""
import sqlite3
from rdflib import URIRef, BNode, Literal
from rdflib.store import Store, VALID, NO_STORE
import json
from pathlib import Path

def encode(term):
    if isinstance(term, URIRef):
        return json.dumps(["u", str(term)], ensure_ascii=False)
    if isinstance(term, BNode):
        return json.dumps(["b", str(term)], ensure_ascii=False)
    if isinstance(term, Literal):
        return json.dumps(["l", str(term), term.language, str(term.datatype) if term.datatype else None], ensure_ascii=False)
    raise TypeError("Unsupported RDF term")

def decode(value):
    kind, *parts = json.loads(value)
    if kind == "u":
        return URIRef(parts[0])
    if kind == "b":
        return BNode(parts[0])
    return Literal(parts[0], lang=parts[1], datatype=URIRef(parts[2]) if parts[2] else None, normalize=False)

class SQLiteStore(Store):
    context_aware = True
    transaction_aware = True
    graph_aware = False

    def open(self, configuration, create=False):
        path = Path(configuration).resolve()
        if not create and not path.is_file():
            return NO_STORE
        if create:
            path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS triples (
          s TEXT NOT NULL, p TEXT NOT NULL, o TEXT NOT NULL, c TEXT NOT NULL,
          PRIMARY KEY(s,p,o,c));
        CREATE INDEX IF NOT EXISTS triples_pos ON triples(p,o,s,c);
        CREATE INDEX IF NOT EXISTS triples_osp ON triples(o,s,p,c);
        CREATE INDEX IF NOT EXISTS triples_context ON triples(c,s,p,o);
        CREATE TABLE IF NOT EXISTS namespaces(prefix TEXT PRIMARY KEY, uri TEXT UNIQUE);
        """)
        return VALID

    def _where(self, triple, context):
        clauses, args = [], []
        for column, term in zip(("s","p","o"), triple):
            if term is not None:
                clauses.append(column + "=?")
                args.append(encode(term))
        if context is not None:
            clauses.append("c=?")
            args.append(encode(context.identifier))
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), args

    def add(self, triple, context, quoted=False):
        if quoted:
            raise ValueError("Quoted graphs are not supported")
        super().add(triple, context, quoted)
        self.db.execute("INSERT OR IGNORE INTO triples VALUES (?,?,?,?)",
                        (*map(encode, triple), encode(context.identifier)))

    def remove(self, triple, context=None):
        super().remove(triple, context)
        where, args = self._where(triple, context)
        self.db.execute("DELETE FROM triples" + where, args)

    def triples(self, triple_pattern, context=None):
        where, args = self._where(triple_pattern, context)
        cursor = self.db.execute("SELECT DISTINCT s,p,o FROM triples" + where, args)
        try:
            for row in cursor:
                triple = tuple(map(decode, row))
                contexts = self.db.execute("SELECT c FROM triples WHERE s=? AND p=? AND o=?", row)
                yield triple, (decode(c[0]) for c in contexts)
        finally:
            cursor.close()

    def __len__(self, context=None):
        where, args = self._where((None,None,None), context)
        return self.db.execute("SELECT COUNT(*) FROM (SELECT DISTINCT s,p,o FROM triples" + where + ")", args).fetchone()[0]

    def contexts(self, triple=None):
        where, args = self._where(triple or (None,None,None), None)
        for (value,) in self.db.execute("SELECT DISTINCT c FROM triples" + where, args):
            yield decode(value)

    def bind(self, prefix, namespace, override=True):
        if override:
            self.db.execute("DELETE FROM namespaces WHERE prefix=? OR uri=?", (prefix,str(namespace)))
        self.db.execute("INSERT OR IGNORE INTO namespaces VALUES (?,?)", (prefix,str(namespace)))

    def namespace(self, prefix):
        row = self.db.execute("SELECT uri FROM namespaces WHERE prefix=?", (prefix,)).fetchone()
        return URIRef(row[0]) if row else None

    def prefix(self, namespace):
        row = self.db.execute("SELECT prefix FROM namespaces WHERE uri=?", (str(namespace),)).fetchone()
        return row[0] if row else None

    def namespaces(self):
        for prefix, uri in self.db.execute("SELECT prefix,uri FROM namespaces"):
            yield prefix, URIRef(uri)

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()

    def close(self, commit_pending_transaction=False):
        if commit_pending_transaction:
            self.commit()
        self.db.close()
