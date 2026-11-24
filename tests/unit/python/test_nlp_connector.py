import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import pandas as pd

path = Path(__file__).resolve().parents[3] / "connectors/nlp/nlp_connector.py"
spec = importlib.util.spec_from_file_location("nlp_connector", path)
nlp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nlp)

class NLPTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(nlp.normalize_text("Ａ  Ｂ").normalized_text.tolist(), ["A B"])

    def test_duplicate_ids(self):
        with self.assertRaises(ValueError):
            nlp.normalize_text(pd.DataFrame({"id":[1,1],"text":["a","b"]}), id_column="id")

    def test_resolver(self):
        result = nlp.resolve_coreferences("田中。彼。", resolver=lambda t: [
            dict(mention="彼", antecedent="田中", antecedent_start=0, antecedent_end=2)])
        self.assertEqual(result.antecedent.tolist(), ["田中"])

    def test_japanese_model(self):
        try:
            nlp._model("ja_ginza")
        except (ImportError, OSError):
            self.skipTest("GiNZA not installed")
        text = "東京で売上を分析する。利益も確認する。"
        for action in (nlp.tokenize, nlp.parse_dependencies, nlp.extract_entities,
                       nlp.split_sentences, nlp.split_bunsetsu):
            with self.subTest(action=action.__name__):
                result = action(text)
                self.assertIsInstance(result, pd.DataFrame)
                for row in result.itertuples():
                    self.assertEqual(text[row.start:row.end], row.text)
        self.assertEqual(len(nlp.split_sentences(text)), 2)
        self.assertIsInstance(nlp.extract_keywords(text, method="textrank"), pd.DataFrame)
        self.assertIsInstance(nlp.extract_keywords(text, method="tfidf",
            corpus=[text,"利益を集計する。"]), pd.DataFrame)
