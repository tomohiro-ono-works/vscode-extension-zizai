"""Generated CSV code is data-safe and only performs IO when executed."""
import ast
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import source_test_support
from zizai.form_definition import load_definition, parse_definition
from zizai.form_model import FormModel


class CsvCodegenTests(unittest.TestCase):
    def setUp(self):
        from zizai.csv_codegen import generate_csv
        self.generate = generate_csv
        self.temp = tempfile.TemporaryDirectory(prefix='zizai-code-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.values = dict(folder=str(self.directory), filename='入力.csv', encoding='utf-8',
            delimiter=',', header_row=1, data_start_row=2, chunk_size=50000,
            schema='', date_cleansing='有効', output_variable='df', input_variable='df')

    def test_read_code_compiles_and_reads_only_when_executed(self):
        source = self.directory / '入力.csv'
        source.write_text('名前,数\n東京,1\n', encoding='utf-8')
        before = source.read_bytes()
        with patch('pandas.read_csv', side_effect=AssertionError('generation must not read')):
            code = self.generate('csv.read_csv', self.values)
        namespace = {}
        exec(compile(code, '<generated-csv>', 'exec'), namespace)
        self.assertEqual(namespace['df']['名前'].tolist(), ['東京'])
        self.assertEqual(source.read_bytes(), before)
        self.assertIsInstance(ast.parse(code).body[-1], ast.Expr)

    def test_write_code_uses_actual_variable_and_appends_extension(self):
        import pandas as pd
        self.values.update(filename='出力', encoding='cp932', delimiter='\\t')
        output = self.directory / '出力.csv'
        self.assertFalse(output.exists())
        frame = pd.DataFrame({'名前': ['東京'], '数': [1]})
        for variable in ('売上', 'write_csv'):
            with self.subTest(variable=variable):
                self.values['input_variable'] = variable
                code = self.generate('csv.write_csv', self.values)
                exec(compile(code, '<generated-csv>', 'exec'), {variable: frame})
                self.assertEqual(output.read_text(encoding='cp932'), '名前\t数\n東京\t1\n')

    def test_quotes_newlines_and_schema_text_stay_literals(self):
        self.values.update(folder=str(self.directory / "日本語'\"; injected() #"),
                           filename="値'\n.csv", schema='[]\n# not code')
        code = self.generate('csv.read_csv', self.values)
        with patch('zizai.connectors.csv.read_csv', return_value='safe') as read:
            namespace = {}
            exec(compile(code, '<generated-csv>', 'exec'), namespace)
        self.assertEqual(namespace['df'], 'safe')
        self.assertEqual(read.call_args.kwargs['file_path'], str(Path(self.values['folder']) / self.values['filename']))
        self.assertEqual(read.call_args.kwargs['schema'], self.values['schema'])

    def test_invalid_identifiers_missing_inputs_and_rows_do_not_generate(self):
        for bad in ('df.value', 'class', 'df; injected()', '', 'has space'):
            for kind, role in [('csv.read_csv', 'output_variable'), ('csv.write_csv', 'input_variable')]:
                with self.subTest(kind=kind, bad=bad), self.assertRaises(ValueError):
                    self.generate(kind, {**self.values, role: bad})
        for values in ({**self.values, 'folder': ''}, {**self.values, 'filename': ''},
                       {**self.values, 'data_start_row': 0}, {**self.values, 'chunk_size': -1}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.generate('csv.read_csv', values)

    def test_yaml_routes_csv_to_real_code_and_leaves_other_actions_as_placeholder(self):
        definition = load_definition()
        form = FormModel(definition)
        form.set_connector('csv')
        form.set_action('import')
        form.set_value('folder', str(self.directory))
        form.set_value('filename', '入力.csv')
        self.assertIn('from zizai.connectors.csv import read_csv', form.generate())
        self.assertFalse(form.is_placeholder)
        form.set_action('export')
        self.assertIn('write_csv', form.generate())
        form.set_connector('excel')
        self.assertTrue(form.is_placeholder)
        self.assertEqual(form.generate(), '{excel.exportのコードを生成}')

    def test_yaml_cannot_choose_arbitrary_python_generator(self):
        import yaml
        definition = copy.deepcopy(load_definition())
        for invalid in ('os.system', ['csv.read_csv'], None):
            definition['connectors']['csv']['actions']['import']['generation'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_definition(yaml.safe_dump(definition))


if __name__ == '__main__':
    unittest.main()
