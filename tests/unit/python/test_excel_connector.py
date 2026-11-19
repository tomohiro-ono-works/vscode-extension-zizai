"""Run the actual Excel and CSV code generated from their form definitions."""
import ast
from pathlib import Path
import tempfile
import unittest

import source_test_support
from zizai.form_definition import load_definition
from zizai.form_model import FormModel


class ExcelConnectorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='zizai-excel-')
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)
        self.form = FormModel(load_definition(source_test_support.REPO / 'connectors'))
        self.namespace = {}

    def run_generated(self, connector, action, **settings):
        self.form.set_connector(connector)
        self.form.set_action(action)
        if 'folder' in self.form.fields:
            self.form.set_value('folder', str(self.folder))
        for name, value in settings.items():
            self.form.set_value(name, value)
        self.assertFalse(self.form.is_placeholder)
        code = self.form.generate()
        self.assertNotIn('\\\\', code)
        exec(compile(code, '<generated-connector>', 'exec'), self.namespace)
        return code

    def test_generated_excel_reads_csv_joins_and_writes_both_formats(self):
        from openpyxl import Workbook, load_workbook
        source = self.folder / '商品表.xlsx'
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'シート1'
        for row in (['説明'], ['商品', '単価'], ['除外', 999], ['りんご', 120], ['なし', 200]):
            sheet.append(row)
        workbook.save(source)
        workbook.close()
        original = source.read_bytes()
        (self.folder / '注文.csv').write_text('商品,数量\nなし,3\nりんご,2\n', encoding='utf-8')

        self.form.set_connector('excel')
        self.form.set_action('read_excel')
        self.assertEqual(self.form.values['file_path'], '')
        with self.assertRaises(ValueError):
            self.form.generate()
        self.run_generated('excel', 'read_excel', file_path=str(source), header_row=2,
                           data_start_row=4, chunk_size=1, output_variable='商品表')
        self.run_generated('excel', 'read_excel_range', file_path=str(source), cell_range='A2:B5',
                           header_row=1, data_start_row=3, output_variable='指定範囲')
        self.assertTrue(self.namespace['商品表'].equals(self.namespace['指定範囲']))
        self.run_generated('csv', 'import', file_path=str(self.folder / '注文.csv'), output_variable='注文')
        exec("明細 = 注文.merge(指定範囲, on='商品', validate='many_to_one')\n"
             "明細['数量'] = 明細['数量'].astype(int)\n"
             "明細['金額'] = 明細['数量'] * 明細['単価'].astype(int)", self.namespace)
        self.run_generated('csv', 'export', filename='集計.csv', input_variable='明細')
        code = self.run_generated('excel', 'export', filename='集計.xlsx', input_variable='明細')
        self.assertIn("mode = 'create_or_replace'", code)
        self.assertIn("sheet_name = 'シート1'", code)
        expression = next(node for node in ast.walk(ast.parse(code)) if isinstance(node, ast.Call))
        self.assertIn('mode', {keyword.arg for keyword in expression.keywords})
        self.assertEqual((self.folder / '集計.csv').read_text(encoding='utf-8-sig').splitlines(),
                         ['商品,数量,単価,金額', 'なし,3,200,600', 'りんご,2,120,240'])
        workbook = load_workbook(self.folder / '集計.xlsx', read_only=True)
        try:
            self.assertEqual(list(workbook['シート1'].values),
                             [('商品', '数量', '単価', '金額'), ('なし', 3, 200, 600), ('りんご', 2, 120, 240)])
        finally:
            workbook.close()
        self.assertEqual(source.read_bytes(), original)

    def test_generated_replace_and_append_preserve_other_sheet_and_failed_write(self):
        from openpyxl import Workbook, load_workbook
        from openpyxl.utils.exceptions import IllegalCharacterError
        path = self.folder / '出力.xlsx'
        workbook = Workbook()
        workbook.active.title = 'シート1'
        workbook.active.append(['旧列', '既存データ'])
        preserved = workbook.create_sheet('保持')
        preserved.append(['別シート', '=1+1'])
        workbook.save(path)
        workbook.close()
        self.namespace.update(df=[{'品名': 'りんご'}], more=[{'品名': '=みかん'}])
        self.run_generated('excel', 'export', filename=path.name, input_variable='df')
        self.run_generated('excel', 'export', filename=path.name, input_variable='more', mode='create_or_insert')
        self.run_generated('excel', 'export', filename=path.name, input_variable='df', sheet_name='追加',
                           mode='create_or_insert')
        workbook = load_workbook(path)
        try:
            self.assertEqual(list(workbook['シート1'].values), [('品名',), ('りんご',), ('=みかん',)])
            self.assertEqual(workbook['シート1']['A3'].data_type, 's')
            self.assertEqual(list(workbook['追加'].values), [('品名',), ('りんご',)])
            self.assertEqual(list(workbook['保持'].values), [('別シート', '=1+1')])
        finally:
            workbook.close()
        original = path.read_bytes()
        from excel_connector import write_excel
        with self.assertRaises(IllegalCharacterError):
            write_excel([{'品名': '保存\x00不可'}], path)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(self.folder.glob('*.xlsx')), [path])
