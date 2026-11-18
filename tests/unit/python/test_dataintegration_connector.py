"""Exercise RENAME lists with generated CSV and Excel workflows."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import source_test_support
from zizai.form_definition import load_definition
from zizai.form_model import FormModel


class DataIntegrationConnectorTests(unittest.TestCase):
    def test_csv_and_excel_tables_are_renamed_without_mutating_input(self):
        from openpyxl import Workbook

        shared = source_test_support.REPO / 'connectors'
        form = FormModel(load_definition(shared))
        namespace = {}

        def generate(connector, action, **values):
            form.set_connector(connector)
            form.set_action(action)
            for name, value in values.items():
                form.set_value(name, value)
            return form.generate()

        with tempfile.TemporaryDirectory(prefix='zizai-rename-') as scratch:
            folder = Path(scratch)
            headers = ['商品名', '数量', '英語_備考', 'Ａ - Ｂ']
            (folder / 'input.csv').write_text(','.join(headers) + '\nりんご,2,メモ,code\n', encoding='utf-8')
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.title = 'シート1'
            worksheet.append(headers)
            worksheet.append(['りんご', '2', 'メモ', 'code'])
            workbook.save(folder / 'input.xlsx')
            workbook.close()

            with patch.object(sys, 'path', [str(shared / 'dataintegration'), *sys.path]):
                for connector, action, filename, output in (
                    ('csv', 'import', 'input.csv', 'csv_input'), ('excel', 'read_excel', 'input.xlsx', 'excel_input'),
                ):
                    code = generate(connector, action, folder=scratch, filename=filename, output_variable=output)
                    exec(compile(code, '<generated-import>', 'exec'), namespace)
                first = generate('dataintegration', 'replace_fields_forrenamelist', folder=scratch,
                                 filename='rename.csv', input_variable='csv_input', output_variable='renamed')
                self.assertTrue(first.startswith('import dataintegration_connector\n'))
                self.assertFalse((folder / 'rename.csv').exists())
                (folder / 'rename.csv').write_text('元フィールド名,新フィールド名,説明,データ型\n'
                                                   '商品名,product,商品名の説明,\n数量,amount,,INT64\n'
                                                   'A_B,code,,\n', encoding='utf-8-sig')
                for source in ('csv_input', 'excel_input'):
                    with self.subTest(source=source):
                        original = namespace[source].copy(deep=True)
                        code = generate('dataintegration', 'replace_fields_forrenamelist', input_variable=source,
                                        remove_spaces=True, to_halfwidth_alnum=True, symbols_to_snake=True,
                                        exclude_japanese_columns=True)
                        exec(compile(code, '<generated-rename>', 'exec'), namespace)
                        result = namespace['renamed']
                        self.assertEqual(result.to_dict('records'), [{'product': 'りんご', 'amount': 2, 'code': 'code'}])
                        self.assertEqual(result.attrs['ziz_schema'][0]['description'], '商品名の説明')
                        self.assertTrue(namespace[source].equals(original))

    def test_existing_column_and_ambiguous_mapping_are_preserved_on_error(self):
        import pandas as pd
        shared = source_test_support.REPO / 'connectors/dataintegration'
        with patch.object(sys, 'path', [str(shared), *sys.path]):
            from dataintegration_connector import replace_fields_forrenamelist
        original = pd.DataFrame({'a': [1], 'b': [2]})
        with tempfile.TemporaryDirectory(prefix='zizai-rename-collision-') as scratch:
            rename_file = Path(scratch) / 'rename.csv'
            for content in ('origin_name,replaced_name\na,b\n', 'origin_name,new_name\na,c\na,d\n'):
                rename_file.write_text(content, encoding='utf-8')
                with self.subTest(rename=content), self.assertRaisesRegex(ValueError, '重複|矛盾'):
                    replace_fields_forrenamelist(original, rename_file)
        self.assertEqual(original.to_dict('records'), [{'a': 1, 'b': 2}])

    def test_cleaning_checkbox_is_off_initially_and_only_affects_generated_code_when_selected(self):
        from ipywidgets import Checkbox
        from zizai.forms import create_form
        form = create_form(source_test_support.REPO / 'connectors')
        self.addCleanup(form.close)
        form.connector.value = 'dataintegration'
        form.action.value = 'replace_fields_forrenamelist'
        form.field_widgets['folder'].value = str(source_test_support.REPO)
        form.field_widgets['filename'].value = 'rename.csv'
        form.field_widgets['input_variable'].value = 'df'
        checkbox = form.field_widgets['remove_newlines']
        self.assertIsInstance(checkbox, Checkbox)
        self.assertFalse(checkbox.value)
        form.generate_button.click()
        self.assertNotIn('pre_rename_cleansing', form.result)
        checkbox.value = True
        form.generate_button.click()
        self.assertIn("pre_rename_cleansing = ('remove_newlines',)", form.result)


if __name__ == '__main__':
    unittest.main()
