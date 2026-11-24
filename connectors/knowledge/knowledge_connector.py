"""DataFrame interface for local RDF graphs."""
from contextlib import contextmanager
from pathlib import Path
import pandas as pd
from rdflib import Graph, URIRef
from rdflib.util import from_n3
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue
from pyparsing import ParseResults
from knowledge_store import SQLiteStore

@contextmanager
def open_graph(db_file, graph_uri="urn:zizai:knowledge", create=False):
    if not create and not Path(db_file).is_file():
        raise FileNotFoundError(db_file)
    store = SQLiteStore()
    store.open(db_file, create=create)
    try:
        graph = Graph(store=store, identifier=URIRef(graph_uri))
        yield graph
        store.commit()
    except BaseException:
        store.rollback()
        raise
    finally:
        store.close()

def create_graph(db_file, graph_uri="urn:zizai:knowledge"):
    with open_graph(db_file, graph_uri, create=True):
        pass
    return pd.DataFrame([{"db_file": str(db_file), "graph_uri": graph_uri}])

def _term(value):
    from rdflib import URIRef, BNode, Literal
    if isinstance(value, (URIRef, BNode, Literal)):
        return value
    if not isinstance(value, str) or not value.startswith(("<", "_:", '"')):
        raise ValueError("Use N3 terms: <URI>, _:node or quoted literal")
    term = from_n3(value)
    if not isinstance(term, (URIRef, BNode, Literal)):
        raise ValueError("Invalid RDF term")
    return term

def add_triples(db_file, df, graph_uri="urn:zizai:knowledge"):
    from rdflib import BNode
    with open_graph(db_file, graph_uri, create=True) as graph:
        for row in df[["subject","predicate","object"]].itertuples(index=False, name=None):
            s,p,o = map(_term,row)
            if not isinstance(s,(URIRef,BNode)) or not isinstance(p,URIRef):
                raise ValueError("Invalid RDF subject or predicate")
            graph.add((s,p,o))
    return pd.DataFrame([{"input_rows":len(df)}])

def remove_triples(db_file, df, graph_uri="urn:zizai:knowledge"):
    with open_graph(db_file, graph_uri) as graph:
        for row in df[["subject","predicate","object"]].itertuples(index=False,name=None):
            graph.remove(tuple(map(_term,row)))
    return pd.DataFrame([{"input_rows":len(df)}])

def _check_query(node):
    if isinstance(node, CompValue):
        if node.name in {"ServiceGraphPattern","DatasetClause"}:
            raise ValueError("External SPARQL access is prohibited")
        for value in node.values():
            _check_query(value)
    elif isinstance(node,(list,tuple,ParseResults)):
        for value in node:
            _check_query(value)

def search_graph(db_file, sparql, graph_uri="urn:zizai:knowledge"):
    parsed = parseQuery(sparql)
    _check_query(parsed)
    if parsed[1].name not in {"SelectQuery","AskQuery"}:
        raise ValueError("Only SELECT and ASK are supported")
    with open_graph(db_file, graph_uri) as graph:
        result = graph.query(sparql, use_store_provided=False)
        if result.type == "ASK":
            return pd.DataFrame([{"ask":bool(result.askAnswer)}])
        return pd.DataFrame.from_records(
            ([term.n3() if term is not None else None for term in row] for row in result),
            columns=[str(v) for v in result.vars])

def define_class(db_file, class_uri, label=None, parent_uri=None):
    from ontology import define_class as action
    return action(db_file, class_uri, label, parent_uri)

def define_property(db_file, property_uri, domain_uri=None, range_uri=None, property_type="object", label=None):
    from ontology import define_property as action
    return action(db_file, property_uri, domain_uri, range_uri, property_type, label)

def search_ontology(db_file, sparql):
    from ontology import search_ontology as action
    return action(db_file, sparql)

def list_ancestors(db_file, class_uri):
    from ontology import list_ancestors as action
    return action(db_file, class_uri)

def infer_types(db_file):
    from ontology import infer_types as action
    return action(db_file)

def validate_ontology(db_file):
    from ontology import validate_ontology as action
    return action(db_file)
