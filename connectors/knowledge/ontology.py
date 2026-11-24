"""Ontology operations sharing the local RDF store."""
import pandas as pd
from rdflib import URIRef, Literal, RDF, RDFS, OWL
from knowledge_connector import open_graph, search_graph

ONTOLOGY_GRAPH = "urn:zizai:ontology"

def define_class(db_file, class_uri, label=None, parent_uri=None):
    subject = URIRef(class_uri)
    with open_graph(db_file, ONTOLOGY_GRAPH, create=True) as graph:
        graph.add((subject, RDF.type, OWL.Class))
        if label is not None:
            graph.add((subject, RDFS.label, Literal(label)))
        if parent_uri is not None:
            graph.add((subject, RDFS.subClassOf, URIRef(parent_uri)))
    return pd.DataFrame([{"class_uri":class_uri}])

def define_property(db_file, property_uri, domain_uri=None, range_uri=None,
                    property_type="object", label=None):
    types = {"object":OWL.ObjectProperty,"datatype":OWL.DatatypeProperty}
    if property_type not in types:
        raise ValueError("property_type must be object or datatype")
    subject = URIRef(property_uri)
    with open_graph(db_file, ONTOLOGY_GRAPH, create=True) as graph:
        graph.add((subject,RDF.type,types[property_type]))
        for predicate,value in ((RDFS.domain,domain_uri),(RDFS.range,range_uri)):
            if value is not None:
                graph.add((subject,predicate,URIRef(value)))
        if label is not None:
            graph.add((subject,RDFS.label,Literal(label)))
    return pd.DataFrame([{"property_uri":property_uri}])

def search_ontology(db_file, sparql):
    return search_graph(db_file, sparql, ONTOLOGY_GRAPH)

def list_ancestors(db_file, class_uri):
    with open_graph(db_file, ONTOLOGY_GRAPH) as graph:
        result = graph.query("SELECT DISTINCT ?ancestor WHERE { ?cls <http://www.w3.org/2000/01/rdf-schema#subClassOf>+ ?ancestor }",
                             initBindings={"cls":URIRef(class_uri)})
        return pd.DataFrame.from_records(((str(row[0]),) for row in result),columns=["ancestor"])

def validate_ontology(db_file):
    """Check explicit object/datatype property usage and declared datatype ranges."""
    rows = []
    with open_graph(db_file, ONTOLOGY_GRAPH) as schema, open_graph(db_file) as data:
        for s,p,o in data:
            types = set(schema.objects(p,RDF.type))
            issues = []
            if OWL.ObjectProperty in types and isinstance(o,Literal):
                issues.append("object_property_requires_resource")
            if OWL.DatatypeProperty in types:
                if not isinstance(o,Literal):
                    issues.append("datatype_property_requires_literal")
                else:
                    from rdflib.namespace import XSD
                    actual = o.datatype or (RDF.langString if o.language else XSD.string)
                    for expected in schema.objects(p,RDFS.range):
                        if actual != expected:
                            issues.append("datatype_range_mismatch")
            for issue in issues:
                rows.append((s.n3(),p.n3(),o.n3(),issue))
    return pd.DataFrame(rows,columns=["subject","predicate","object","issue"])
