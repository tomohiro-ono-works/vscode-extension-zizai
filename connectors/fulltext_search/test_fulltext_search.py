"""Tests for the separate Levenshtein search on a registered collection."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from fulltext_search_connector import build_fulltext_db, search_levenshtein


class LevenshteinSearchTests(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(TemporaryDirectory(prefix='zizai-lev-'))
        self.folder = Path(temporary) / '検索DB'
        entries = pd.DataFrame({
            'id': ['replace', 'delete', 'insert', 'exact', 'unrelated'],
            'text': ['りんごの原文', '短縮表記の原文', '追加表記の原文', '入力と同じ表記の原文', '別の原文'],
            'keywords': ['りんご', 'りこ', 'りんここ', 'りんこ', 'みかん'],
        })
        build_fulltext_db(self.folder, 'items', entries, search_text_column='keywords')

    def test_ranks_exact_and_one_edit_matches_on_search_column(self):
        result = search_levenshtein(self.folder, 'items', 'りんこ', max_distance=1)
        self.assertEqual(list(result.columns), ['id', 'text', 'distance', 'rank'])
        self.assertEqual(result['id'].tolist(), ['exact', 'replace', 'delete', 'insert'])
        self.assertEqual(result['distance'].tolist(), [0, 1, 1, 1])
        self.assertEqual(result['rank'].tolist(), [1, 2, 3, 4])
        self.assertEqual(result['text'].iloc[1], 'りんごの原文')

    def test_zero_threshold_and_top_k(self):
        exact = search_levenshtein(self.folder, 'items', 'りんこ', max_distance=0)
        self.assertEqual(exact['id'].tolist(), ['exact'])
        short = search_levenshtein(self.folder, 'items', 'りこ', max_distance=0)
        self.assertEqual(short['id'].tolist(), ['delete'])
        first_two = search_levenshtein(self.folder, 'items', 'りんこ', max_distance=1, top_k=2)
        self.assertEqual(first_two['id'].tolist(), ['exact', 'replace'])
        empty = search_levenshtein(self.folder, 'items', '別商品', max_distance=0)
        self.assertTrue(empty.empty)
        self.assertEqual(list(empty.columns), list(exact.columns))

    def test_rejects_invalid_limits_and_missing_collection(self):
        for distance in (-1, True, 1.5):
            with self.subTest(distance=distance), self.assertRaises(ValueError):
                search_levenshtein(self.folder, 'items', 'りんこ', max_distance=distance)
        with self.assertRaises(ValueError):
            search_levenshtein(self.folder, 'items', 'りんこ', top_k=0)
        with self.assertRaises(FileNotFoundError):
            search_levenshtein(self.folder, 'missing', 'りんこ')


if __name__ == '__main__':
    unittest.main()
