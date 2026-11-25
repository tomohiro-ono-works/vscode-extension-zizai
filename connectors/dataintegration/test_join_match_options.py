"""Regression tests for the extended join conditions."""
import unittest
import pandas as pd
from dataintegration_connector import join_frames


class JoinMatchTests(unittest.TestCase):
    def setUp(self):
        self.left = pd.DataFrame({'text': ['店舗別売上高', '売上高前年比', '売上高', '粗利', None],
                                  'lid': [0, 1, 2, 3, 4]}, index=[2, 2, 4, 5, 6])
        self.right = pd.DataFrame({'term': ['売上', '売上高', '前年比', '', None],
                                   'rid': [10, 11, 12, 13, 14]})

    def join(self, mode, how='inner', policy='all'):
        return join_frames(self.left, self.right,
                           keys=[{'left': 'text', 'right': 'term', 'match': mode}],
                           how=how, match_policy=policy)

    def test_exact_all_keeps_pandas_semantics(self):
        expected = self.left.merge(self.right, left_on='text', right_on='term', how='outer')
        pd.testing.assert_frame_equal(self.join('exact', 'outer'), expected)

    def test_contains(self):
        self.assertEqual(list(zip(self.join('contains').lid, self.join('contains').rid)),
                         [(0, 10), (0, 11), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11)])

    def test_prefix(self):
        result = self.join('prefix')
        self.assertEqual(list(zip(result.lid, result.rid)), [(1, 10), (1, 11), (2, 10), (2, 11)])

    def test_suffix(self):
        result = self.join('suffix')
        self.assertEqual(list(zip(result.lid, result.rid)), [(0, 11), (1, 12), (2, 11)])

    def test_first_right_row(self):
        result = self.join('contains', 'left', 'first')
        self.assertEqual(result.lid.tolist(), [0, 1, 2, 3, 4])
        self.assertEqual(result.rid.iloc[:3].tolist(), [10, 10, 10])
        self.assertTrue(result.rid.iloc[3:].isna().all())

    def test_outer_and_right_first(self):
        for how in ('outer', 'right'):
            result = self.join('contains', how, 'first')
            self.assertEqual(set(result.loc[result.lid.isna(), 'rid']), {11, 12, 13, 14})
            self.assertEqual(result.lid.notna().sum(), 5 if how == 'outer' else 3)

    def test_multiple_keys_and_first(self):
        left = pd.DataFrame({'group': ['A', 'B'], 'text': ['abc', 'abc']})
        right = pd.DataFrame({'group': ['B', 'A', 'A'], 'term': ['a', 'ab', 'a']})
        result = join_frames(left, right,
                             keys=[{'left': 'group', 'right': 'group'},
                                   {'left': 'text', 'right': 'term', 'match': 'prefix'}],
                             match_policy='first')
        self.assertEqual(result.term.tolist(), ['ab', 'a'])
        self.assertEqual(result.group.tolist(), ['A', 'B'])

    def test_exact_first_outer(self):
        left = pd.DataFrame({'k': [1, 2], 'a': ['L1', 'L2']})
        right = pd.DataFrame({'k': [1, 1, 3], 'b': ['R1', 'R2', 'R3']})
        result = join_frames(left, right, keys=[{'left': 'k', 'right': 'k'}],
                             how='outer', match_policy='first')
        self.assertEqual(result.k.tolist(), [1, 2, 1, 3])
        self.assertEqual(result.b.dropna().tolist(), ['R1', 'R2', 'R3'])
        self.assertTrue(result.a.iloc[2:].isna().all())

    def test_same_name_text_keys_and_empty(self):
        left = pd.DataFrame({'k': ['abc']})
        right = pd.DataFrame({'k': ['a']})
        keys = [{'left': 'k', 'right': 'k', 'match': 'prefix'}]
        result = join_frames(left, right, keys=keys)
        self.assertEqual(result.to_dict('records'), [{'k_x': 'abc', 'k_y': 'a'}])
        self.assertTrue(join_frames(left.iloc[:0], right, keys=keys).empty)
        self.assertEqual(len(join_frames(left, right.iloc[:0], keys=keys, how='left')), 1)


if __name__ == '__main__':
    unittest.main()
