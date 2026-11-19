"""Exercise RENAME lists with generated CSV and Excel workflows."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

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
                csv_code = generate('csv', 'import', file_path=str(folder / 'input.csv'), output_variable='csv_input')
                excel_code = generate('excel', 'read_excel', file_path=str(folder / 'input.xlsx'),
                                      output_variable='excel_input')
                for code in (csv_code, excel_code):
                    exec(compile(code, '<generated-import>', 'exec'), namespace)
                first = generate('dataintegration', 'replace_fields_forrenamelist',
                                 file_path=str(folder / 'rename.csv'), input_variable='csv_input',
                                 output_variable='renamed')
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
        form.field_widgets['input_variable'].value = 'df'
        self.assertTrue(form.generate_button.disabled)
        with patch('tkinter.Tk', return_value=Mock()), patch('tkinter.filedialog.askdirectory') as folder, \
                patch('tkinter.filedialog.askopenfilename', return_value='C:/選択先/RENAME.csv') as file:
            form.browse_buttons['file_path'].click()
            self.assertEqual(file.call_args.kwargs['filetypes'][0][1], '*.csv')
            folder.assert_not_called()
        checkbox = form.field_widgets['remove_newlines']
        self.assertIsInstance(checkbox, Checkbox)
        self.assertTrue(all(not widget.value for widget in form.field_widgets.values() if isinstance(widget, Checkbox)))
        form.generate_button.click()
        self.assertIn("rename_list_path = 'C:/選択先/RENAME.csv'", form.result)
        self.assertNotIn('pre_rename_cleansing', form.result)
        checkbox.value = True
        form.generate_button.click()
        self.assertIn("pre_rename_cleansing = ('remove_newlines',)", form.result)


if __name__ == '__main__':
    unittest.main()
