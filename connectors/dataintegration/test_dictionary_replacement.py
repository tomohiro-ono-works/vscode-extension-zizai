"""Dictionary replacement regression tests (run with zizai-runtime installed)."""
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from dataintegration_connector import replace_dictionary, apply_data_operations


class DictionaryReplacementTests(unittest.TestCase):
    def setUp(self):
        self.dictionary = pd.DataFrame({'before': ['売上高', '売上金額'],
                                        'after': ['売上金額', 'sales_amount']})
        self.series = pd.Series(['売上高', '売上金額', '不明', None], index=[7, 3, 7, 2],
                                dtype='string')

    def replace(self, **kwargs):
        return replace_dictionary(self.series, self.dictionary,
                                  source_column='before', target_column='after', **kwargs)

    def test_exact_no_cascade_and_nulls(self):
        expected = pd.Series(['売上金額', 'sales_amount', '不明', None],
                             index=self.series.index, dtype='string')
        pd.testing.assert_series_equal(self.replace(), expected)

    def test_cascade(self):
        expected = pd.Series(['sales_amount', 'sales_amount', '不明', None],
                             index=self.series.index, dtype='string')
        pd.testing.assert_series_equal(self.replace(cascade=True), expected)

    def test_unmatched_null(self):
        self.assertTrue(self.replace(unmatched='null').iloc[2:].isna().all())

    def test_overlapping_partial_priority(self):
        rules = pd.DataFrame({'before': ['売上高', '売上', '店舗'],
                              'after': ['sales', 'amount', 'store']})
        actual = replace_dictionary(pd.Series(['店舗の売上高と売上']), rules,
                                    source_column='before', target_column='after',
                                    match_mode='partial')
        self.assertEqual(actual.iloc[0], 'storeのsalesとamount')

    def test_regex_literal_replacement(self):
        rules = pd.DataFrame({'before': [r'商品[0-9]+'], 'after': [r'\1']})
        actual = replace_dictionary(pd.Series(['商品123']), rules,
                                    source_column='before', target_column='after',
                                    match_mode='regex')
        self.assertEqual(actual.iloc[0], r'\1')

    def test_invalid_regex(self):
        rules = pd.DataFrame({'before': ['['], 'after': ['x']})
        with self.assertRaises(ValueError):
            replace_dictionary(self.series, rules, source_column='before',
                               target_column='after', match_mode='regex')

    def test_csv_and_new_column(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'dictionary.csv'
            self.dictionary.to_csv(path, index=False, encoding='utf-8-sig')
            frame = self.series.to_frame('original')
            change = {'op': 'replace_dictionary', 'column': 'original', 'output': 'converted',
                      'dictionary_source': 'csv', 'dictionary_reference': str(path),
                      'source_column': 'before', 'target_column': 'after',
                      'match_mode': 'exact', 'unmatched': 'keep', 'cascade': False}
            result = apply_data_operations(frame, operations=[{'category': 'value', 'operation': change}])
            pd.testing.assert_series_equal(result['converted'], self.replace().rename('converted'))
            self.assertEqual(list(frame.columns), ['original'])

    def test_dataframe_reference(self):
        frame = self.series.to_frame('original')
        change = {'op': 'replace_dictionary', 'column': 'original',
                  'dictionary_source': 'dataframe', 'dictionary_reference': 'rules',
                  'source_column': 'before', 'target_column': 'after'}
        result = apply_data_operations(frame, operations=[{'category': 'value', 'operation': change}],
                                       dictionaries={'rules': self.dictionary})
        pd.testing.assert_series_equal(result['original'], self.replace().rename('original'))


if __name__ == '__main__':
    unittest.main()
