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
    def test_ordered_column_operations_generate_and_preserve_input(self):
        import json
        import pandas as pd

        shared = source_test_support.REPO / 'connectors'
        original = pd.DataFrame({'商品': ['りんご'], '数量': ['12'], '不要': ['x'], '省略': ['y']}, index=[9])
        original.attrs['ziz_schema'] = [{'new_name': '商品', 'description': '品名'}]
        before = original.copy(deep=True)
        operations = [
            {'op': 'rename', 'column': '商品', 'name': 'product'},
            {'op': 'duplicate', 'column': 'product', 'name': 'copy'},
            {'op': 'convert', 'column': '数量', 'type': 'integer'},
            {'op': 'drop', 'columns': ['不要']},
            {'op': 'keep', 'columns': ['product', '数量', 'copy']},
            {'op': 'move', 'column': 'copy', 'position': 1},
        ]
        form = FormModel(load_definition(shared))
        form.set_connector('dataintegration')
        form.set_action('apply_column_operations')
        form.set_value('input_variable', 'original')
        form.set_value('operations', json.dumps(operations, ensure_ascii=False))
        with patch.object(sys, 'path', [str(shared / 'dataintegration'), *sys.path]):
            namespace = {'original': original}
            exec(compile(form.generate(), '<generated-column-operations>', 'exec'), namespace)
        result = namespace['processed_df']
        self.assertEqual(result.to_dict('records'), [{'copy': 'りんご', 'product': 'りんご', '数量': 12}])
        self.assertEqual(list(result.columns), ['copy', 'product', '数量'])
        self.assertEqual(result.index.tolist(), [9])
        self.assertEqual(str(result['数量'].dtype), 'Int64')
        self.assertEqual([(item['new_name'], item.get('description')) for item in result.attrs['ziz_schema'][:2]],
                         [('copy', '品名'), ('product', '品名')])
        self.assertTrue(original.equals(before))
        self.assertEqual(original.attrs, before.attrs)

    def test_column_form_previews_only_thirty_rows_and_keeps_previous_valid_changes(self):
        import pandas as pd
        from zizai.forms import create_form

        shared = source_test_support.REPO / 'connectors'
        source = pd.DataFrame({'数量': ['12'] * 30 + ['未入力'], '注記': ['変換不可'] * 31})
        with patch.object(sys, 'path', [str(shared / 'dataintegration'), *sys.path]):
            form = create_form(shared, namespace={'df': source, 'scalar': 1})
            self.addCleanup(form.close)
            form.connector.value = 'dataintegration'
            form.action.value = 'apply_column_operations'
            self.assertEqual([key for _, key in form.field_widgets['input_variable'].options], ['', 'df'])
            form.field_widgets['input_variable'].value = 'df'
            editor = form._column_editor
            self.assertEqual(len(editor.preview), 30)
            self.assertTrue(editor.add_operation({'op': 'convert', 'column': '数量', 'type': 'integer'}))
            self.assertFalse(editor.add_operation({'op': 'convert', 'column': '注記', 'type': 'integer'}))
            self.assertIn('注記', editor.status.value)
            self.assertEqual(editor.preview['数量'].iloc[0], 12)
            self.assertEqual(source['数量'].iloc[0], '12')
            form.generate_button.click()
            self.assertIn('apply_column_operations', form.result)
            with self.assertRaisesRegex(ValueError, '数量'):
                exec(compile(form.result, '<whole-table>', 'exec'), {'df': source})
            editor.undo.click()
            self.assertTrue(form.generate_button.disabled)
            self.assertEqual(editor.preview['数量'].iloc[0], '12')

    def test_column_header_actions_keep_pending_deletion_visible_and_restore_it(self):
        import pandas as pd
        from zizai.forms import create_form

        shared = source_test_support.REPO / 'connectors'
        source = pd.DataFrame({'商品': ['りんご'], '数量': ['12'], '備考': ['メモ']})
        with patch.object(sys, 'path', [str(shared / 'dataintegration'), *sys.path]):
            form = create_form(shared, namespace={'df': source})
            self.addCleanup(form.close)
            form.connector.value = 'dataintegration'
            form.action.value = 'apply_column_operations'
            form.field_widgets['input_variable'].value = 'df'
            editor = form._column_editor

            def send(column, **message):
                header = next(header for header in editor._headers if header._column_name == column)
                editor._handle_header(header, column, message)

            send('商品', event='column-rename', name='product')
            send('数量', event='column-operation', role='drop')
            self.assertEqual(editor.preview.columns.tolist(), ['product', '数量', '備考'])
            self.assertIn('column-pending-delete', editor._body.value)
            send('product', event='column-move', source='備考', after=False)
            self.assertEqual(editor.preview.columns.tolist(), ['備考', 'product', '数量'])
            form.generate_button.click()
            dropped = {'df': source}
            exec(compile(form.result, '<drop-column>', 'exec'), dropped)
            self.assertEqual(dropped['processed_df'].columns.tolist(), ['備考', 'product'])

            send('数量', event='column-operation', role='restore')
            self.assertNotIn('column-pending-delete', editor._body.value)
            form.generate_button.click()
            restored = {'df': source}
            exec(compile(form.result, '<restore-column>', 'exec'), restored)
            self.assertEqual(restored['processed_df'].columns.tolist(), ['備考', 'product', '数量'])
            self.assertEqual(source.columns.tolist(), ['商品', '数量', '備考'])

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
