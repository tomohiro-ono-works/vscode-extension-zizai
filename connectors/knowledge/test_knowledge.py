import tempfile
import unittest
from pathlib import Path
import pandas as pd
from knowledge_connector import create_graph, add_triples, remove_triples, search_graph
from ontology import define_class, define_property, list_ancestors, search_ontology

class KnowledgeTests(unittest.TestCase):
    def test_persistence(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "catalog.sqlite"
            create_graph(db)
            df = pd.DataFrame([["<urn:sales>", "<urn:column>", '"売上"@ja']], columns=["subject","predicate","object"])
            add_triples(db, df)
            add_triples(db, df)
            result = search_graph(db, "SELECT ?o WHERE { <urn:sales> <urn:column> ?o }")
            self.assertEqual(result["o"].tolist(), ['"売上"@ja'])
            remove_triples(db, df)
            self.assertFalse(search_graph(db, "ASK { ?s ?p ?o }").iloc[0,0])

    def test_ontology(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "catalog.sqlite"
            define_class(db, "urn:Table")
            define_class(db, "urn:Sales", parent_uri="urn:Table")
            define_property(db, "urn:column", domain_uri="urn:Table")
            self.assertEqual(list_ancestors(db, "urn:Sales")["ancestor"].tolist(), ["urn:Table"])
            self.assertTrue(search_ontology(db, "ASK { <urn:Table> a <http://www.w3.org/2002/07/owl#Class> }").iloc[0,0])
            self.assertFalse(search_graph(db, "ASK { ?s ?p ?o }").iloc[0,0])

    def test_external_query_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "catalog.sqlite"
            create_graph(db)
            for query in ["SELECT * WHERE { SERVICE <https://example.invalid/> { ?s ?p ?o } }",
                          "SELECT * FROM <https://example.invalid/> WHERE { ?s ?p ?o }"]:
                with self.assertRaises(ValueError):
                    search_graph(db, query)

if __name__ == "__main__":
    unittest.main()
