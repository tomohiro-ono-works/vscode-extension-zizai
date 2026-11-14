"""CSV processing against synthetic files; no GUI or external services."""
import json
from pathlib import Path
import tempfile
import unittest

import source_test_support


class CsvConnectorTests(unittest.TestCase):
    def setUp(self):
        from zizai.connectors.csv import read_csv, write_csv
        self.read_csv, self.write_csv = read_csv, write_csv
        self.temp = tempfile.TemporaryDirectory(prefix='zizai-csv-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def fixture(self, text, name='入力.csv', encoding='utf-8'):
        path = self.directory / name
        path.write_text(text, encoding=encoding)
        return path

    def test_utf8_read_preserves_values_and_dataframe_schema(self):
        path = self.fixture('名前,個数\nりんご,1\nみかん,2\n', name="日本語'入力.csv")
        frame = self.read_csv(path)
        self.assertEqual(frame['名前'].tolist(), ['りんご', 'みかん'])
        self.assertEqual(frame['個数'].astype(str).tolist(), ['1', '2'])
        self.assertEqual(frame.attrs['ziz_schema'][0]['origin_name'], '名前')

    def test_cp932_tsv_roundtrip_overwrites_and_keeps_input_unchanged(self):
        import pandas as pd
        path = self.fixture('名前\t値\n東京\t10\n大阪\t20\n', encoding='cp932')
        frame = self.read_csv(path, encoding='cp932', delimiter='\\t')
        original = frame.copy(deep=True)
        output = self.directory / '書出.tsv'
        output.write_text('replace me', encoding='cp932')
        result = self.write_csv(frame, output, encoding='cp932', delimiter='tab')
        self.assertEqual(result, f'CSV保存完了: {output.as_posix()}')
        self.assertTrue(output.read_text(encoding='cp932').startswith('名前\t値\n'))
        pd.testing.assert_frame_equal(self.read_csv(output, encoding='cp932', delimiter='TAB'), original)
        pd.testing.assert_frame_equal(frame, original)

    def test_header_data_rows_and_chunked_reads_match(self):
        import pandas as pd
        path = self.fixture('説明行\n名前,値\n除外,999\n一,1\n二,2\n三,3\n')
        whole = self.read_csv(path, header_row=2, data_start_row=4, chunk_size=0)
        chunks = self.read_csv(path, header_row=2, data_start_row=4, chunk_size=2)
        self.assertEqual(whole['名前'].tolist(), ['一', '二', '三'])
        pd.testing.assert_frame_equal(chunks, whole)

    def test_schema_selects_renames_and_converts_integer_and_dates(self):
        path = self.fixture('数量,日付,除外\n1,2026年11月15日,x\n2,45292,y\n')
        schema = [{'origin_name': '数量', 'new_name': 'count', 'ziz_datatype': 'INT64'},
                  {'origin_name': '日付', 'new_name': 'date', 'ziz_datatype': 'DATE'}]
        frame = self.read_csv(path, schema=json.dumps(schema, ensure_ascii=False))
        self.assertEqual(list(frame.columns), ['count', 'date'])
        self.assertEqual(str(frame['count'].dtype), 'Int64')
        self.assertEqual(frame['count'].tolist(), [1, 2])
        self.assertEqual(frame['date'].dt.year.tolist(), [2026, 2024])
        self.assertEqual(frame.attrs['ziz_date_parse_metrics']['serial_fallback_count'], 1)
        plain = self.read_csv(path, schema=schema, date_cleansing=False)
        self.assertTrue(plain['date'].isna().any())

    def test_empty_file_missing_path_and_invalid_rows_use_python_results(self):
        import pandas as pd
        self.assertTrue(self.read_csv(self.fixture('')).empty)
        with self.assertRaises(FileNotFoundError):
            self.read_csv(self.directory / '存在しない.csv')
        path = self.fixture('a\n1\n')
        for kwargs in ({'header_row': 0}, {'header_row': 3, 'data_start_row': 2}, {'chunk_size': -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.read_csv(path, **kwargs)
        with self.assertRaises(ValueError):
            self.write_csv(pd.DataFrame(), self.directory / 'empty.csv')
        self.assertFalse((self.directory / 'empty.csv').exists())

    def test_write_applies_schema_to_actual_objects_without_context_lookup(self):
        import pandas as pd
        source = pd.DataFrame({'元': ['1', '2'], '残さない': ['x', 'y']})
        original = source.copy(deep=True)
        schema = [{'origin_name': '元', 'new_name': 'new', 'ziz_datatype': 'INT64'}]
        target = self.directory / 'schema.csv'
        self.write_csv(source, target, schema=schema)
        self.assertEqual(target.read_text(encoding='utf-8-sig'), 'new\n1\n2\n')
        pd.testing.assert_frame_equal(source, original)
        self.write_csv([{'a': 1}], self.directory / 'list.csv')
        self.write_csv({'a': 2}, self.directory / 'dict.csv')
        with self.assertRaises(ValueError):
            self.read_csv(target, schema=[{'origin_name': 'missing', 'ziz_datatype': 'STRING'}])


if __name__ == '__main__':
    unittest.main()
