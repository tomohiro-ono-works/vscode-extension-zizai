"""Exercise RENAME lists with generated CSV and Excel workflows."""
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import source_test_support
from zizai.form_definition import load_definition
from zizai.form_model import FormModel


def operation_label(row):
    return re.sub(r'<[^>]+>', '', row.children[1].value)


class DataIntegrationConnectorTests(unittest.TestCase):
    def test_unified_form_edits_and_reorders_steps_in_generated_code(self):
        import pandas as pd
        from zizai.forms import create_form

        shared = source_test_support.REPO / 'connectors'
        source = pd.DataFrame({'数量': [1, 2]}, index=[7, 9])
        with patch.object(sys, 'path', [str(shared / 'dataintegration'), *sys.path]):
            form = create_form(shared, namespace={'df': source})
            self.addCleanup(form.close)
            form.connector.value = 'dataintegration'
            form.action.value = 'apply_data_operations'
            form.field_widgets['input_variable'].value = 'df'
            editor = form._dataframe_editor
            self.assertEqual(editor._inputs.children[0].description, '対象列')
            editor._inputs.children[0].value = '数量'
            editor.category.value = 'value'
            value = editor.value_fields
            value.column.value = '数量'
            self.assertEqual([field.description for field in editor._inputs.children[:3]],
                             ['対象列', '処理分類', '操作'])
            value.action.value = 'formula'
            value.fields['expression'].value = '数量 + 10'
            editor.apply.click()
            editor.category.value = 'condition'
            row = editor.row_fields
            row.column.value = '数量'
            row.action.value = 'keep'
            row.comparison.value = 'greater'
            row.value.value = '11'
            editor.apply.click()

            def result():
                form.generate_button.click()
                self.assertNotIn('dataintegration_connector', form.result)
                scope = {'df': source}
                exec(compile(form.result, '<mixed-operations>', 'exec'), scope)
                return scope['processed_df']

            self.assertEqual(result()['数量'].tolist(), [12])
            entry = editor.entries.items[0]
            self.assertEqual(operation_label(entry), '数量 値加工 計算式 数量 + 10')
            self.assertIn('<strong class="zizai-operation-target">数量</strong>', entry.children[1].value)
            self.assertIn('data-category="value">値加工</span>', entry.children[1].value)
            self.assertEqual(operation_label(editor.entries.items[1]), '数量 条件 条件に合う行だけ残す より大きい 11')
            self.assertEqual([btn.description for btn in entry.children[-2:]], ['編集', '削除'])
            entry.children[-2].click()
            self.assertEqual([btn.description for btn in entry.children[-2].children],
                             ['編集をキャンセル', '編集を保存'])
            self.assertEqual(editor._settings_row.children, (editor._inputs,))
            self.assertIn('zizai-operation-delete', entry.children[-1]._dom_classes)
            self.assertEqual(value.fields['expression'].value, '数量 + 10')
            value.fields['expression'].value = '数量 + 20'
            editor.apply.click()
            self.assertEqual(result()['数量'].tolist(), [21, 22])
            self.assertEqual(editor.entries.items[0].children[-2].description, '編集')
            self.assertNotIn('zizai-operation-editor-inline', editor.settings._dom_classes)
            editor._move(1, 0, after=False)
            self.assertTrue(result().empty)
            self.assertEqual(source['数量'].tolist(), [1, 2])

    def test_row_operations_generate_mixed_conditions_then_apply_row_cleanup(self):
        import json
        import pandas as pd

        shared = source_test_support.REPO / 'connectors'
        source = pd.DataFrame({
            '商品': ['A-1', 'B-1', 'A-2', None, 'OTHER', 'A-2'],
            '数量': [1, 7, 10, 1, 12, 10],
            '注記': ['x', 'y', 'ok', None, 'z', 'extra'],
        }, index=[30, 31, 32, 33, 34, 35])
        before = source.copy(deep=True)
        operations = [
            {'op': 'filter', 'mode': 'keep', 'conditions': [
                {'column': '商品', 'comparison': 'contains', 'value': 'A-'},
                {'logic': 'and', 'column': '数量', 'comparison': 'between', 'value': 5, 'upper': 10},
                {'logic': 'or', 'column': '商品', 'comparison': 'is_null'},
            ]},
            {'op': 'drop_duplicates', 'columns': ['商品', '数量']},
        ]
        form = FormModel(load_definition(shared))
        form.set_connector('dataintegration')
        form.set_action('apply_data_operations')
        form.set_value('input_variable', 'source')
        form.set_value('operations', json.dumps([
            {'category': 'condition', 'operation': operation} for operation in operations
        ], ensure_ascii=False))
        with patch.object(sys, 'path', [str(shared / 'dataintegration'), *sys.path]):
            namespace = {'source': source}
            exec(compile(form.generate(), '<generated-row-operations>', 'exec'), namespace)
            from dataintegration_connector import filter_rows
        self.assertEqual(namespace['processed_df'].index.tolist(), [32, 33])
        preceding_or = filter_rows(source, operations=[{'op': 'filter', 'mode': 'keep', 'conditions': [
            {'column': '商品', 'comparison': 'contains', 'value': 'B-'},
            {'logic': 'or', 'column': '商品', 'comparison': 'is_null'},
            {'logic': 'and', 'column': '数量', 'comparison': 'greater_equal', 'value': 10},
        ]}])
        self.assertEqual(preceding_or.index.tolist(), [31])
        result = filter_rows(source, operations=[
            {'op': 'filter', 'mode': 'exclude', 'conditions': [
                {'column': '商品', 'comparison': 'text_equal', 'value': 'OTHER'},
            ]},
            {'op': 'drop_nulls', 'columns': ['注記']},
            {'op': 'head', 'count': 4}, {'op': 'tail', 'count': 2},
        ])
        self.assertEqual(result.index.tolist(), [32, 35])
        self.assertTrue(source.equals(before))

    def test_row_form_adds_and_deletes_individual_conditions_and_generates_for_all_rows(self):
        import pandas as pd
        from zizai.forms import create_form

        shared = source_test_support.REPO / 'connectors'
        source = pd.DataFrame({'数量': range(40)})
        with patch.object(sys, 'path', [str(shared / 'dataintegration'), *sys.path]):
            form = create_form(shared, namespace={'df': source})
            self.addCleanup(form.close)
            form.connector.value = 'dataintegration'
            form.action.value = 'apply_data_operations'
            form.field_widgets['input_variable'].value = 'df'
            editor = form._dataframe_editor
            self.assertFalse(hasattr(editor, 'grid'))
            self.assertIs(editor._settings_row.children[-1], editor.apply)
            editor.category.value = 'condition'
            row = editor.row_fields
            row.column.value = '数量'
            row.action.value = 'keep'
            row.comparison.value = 'greater_equal'
            row.value.value = '10'
            editor.apply.click()
            row.logic.value = 'or'
            row.comparison.value = 'less'
            row.value.value = '3'
            editor.apply.click()
            self.assertEqual(len(editor.entries.items), 2)
            editor.entries.items[0].children[-1].click()
            form.generate_button.click()
            namespace = {'df': source}
            exec(compile(form.result, '<generated-remaining-condition>', 'exec'), namespace)
            self.assertEqual(namespace['processed_df']['数量'].tolist(), [0, 1, 2])
            editor.entries.items[0].children[-1].click()
            self.assertTrue(form.generate_button.disabled)
            row.column.value = False
            row.action.value = 'tail'
            row.count.value = 2
            editor.apply.click()
            self.assertEqual(operation_label(editor.entries.items[0]), '表全体 条件 末尾から指定行数を残す 2行')
            form.generate_button.click()
            namespace = {'df': source}
            exec(compile(form.result, '<generated-tail>', 'exec'), namespace)
            self.assertEqual(namespace['processed_df']['数量'].tolist(), [38, 39])
            editor.entries.items[0].children[-1].click()
            self.assertTrue(form.generate_button.disabled)

    def test_value_operations_generated_code_preserves_input_and_applies_steps(self):
        import json
        import pandas as pd

        shared = source_test_support.REPO / 'connectors'
        source = pd.DataFrame({
            '商品': ['東京-001', '大阪-020', None, '対象外'],
            '数量': [12, 3, 8, 0], '単価': [2.5, 4.0, 1.5, 2.0],
        }, index=[9, 6, 4, 2])
        before = source.copy(deep=True)
        operations = [
            {'op': 'extract_regex', 'column': '商品', 'pattern': r'-(\d+)$', 'group': 1, 'output': '番号'},
            {'op': 'fill_null', 'column': '番号', 'value': '未登録'},
            {'op': 'replace_exact', 'column': '番号', 'search': '未登録', 'replacement': 'NA'},
            {'op': 'split', 'column': '商品', 'separator': '-', 'position': 1, 'output': '地域'},
            {'op': 'replace_part', 'column': '地域', 'search': '東京', 'replacement': '首都'},
            {'op': 'multiply', 'column': '数量', 'other_column': '単価', 'output': '金額'},
            {'op': 'add', 'column': '金額', 'number': 0.49},
            {'op': 'round', 'column': '金額', 'digits': 0},
            {'op': 'to_null', 'column': '数量', 'value': 0},
        ]
        form = FormModel(load_definition(shared))
        form.set_connector('dataintegration')
        form.set_action('apply_data_operations')
        form.set_value('input_variable', 'source')
        form.set_value('operations', json.dumps([
            {'category': 'value', 'operation': operation} for operation in operations
        ], ensure_ascii=False))
        with patch.object(sys, 'path', [str(shared / 'dataintegration'), *sys.path]):
            scope = {'source': source}
            exec(compile(form.generate(), '<generated-value-operations>', 'exec'), scope)
        result = scope['processed_df']
        self.assertEqual(result['番号'].tolist(), ['001', '020', 'NA', 'NA'])
        self.assertEqual(result['地域'].fillna('_').tolist(), ['首都', '大阪', '_', '対象外'])
        self.assertEqual(result['金額'].tolist(), [30.0, 12.0, 12.0, 0.0])
        self.assertTrue(pd.isna(result.loc[2, '数量']))
        self.assertEqual(result.index.tolist(), [9, 6, 4, 2])
        self.assertTrue(source.equals(before))

    def test_value_form_adds_settings_in_one_row_and_guards_dependent_deletion(self):
        import pandas as pd
        from zizai.forms import create_form

        shared = source_test_support.REPO / 'connectors'
        source = pd.DataFrame({'商品': ['東京-001'] * 31, '数量': [12] * 31})
        with patch.object(sys, 'path', [str(shared / 'dataintegration'), *sys.path]):
            form = create_form(shared, namespace={'df': source})
            self.addCleanup(form.close)
            form.connector.value = 'dataintegration'
            form.action.value = 'apply_data_operations'
            form.field_widgets['input_variable'].value = 'df'
            editor = form._dataframe_editor
            self.assertFalse(hasattr(editor, 'grid'))
            self.assertIs(editor._settings_row.children[-1], editor.apply)
            editor.category.value = 'value'
            value = editor.value_fields
            self.assertTrue(value.action.disabled)
            value.column.value = editor.column.options[0][1]
            value.action.value = 'extract_regex'
            value.source.value = '商品'
            value.new_column.value = '番号'
            value.fields['pattern'].value = '('
            editor.apply.click()
            self.assertIn('正規表現', editor.status.value)
            self.assertTrue(form.generate_button.disabled)
            value.fields['pattern'].value = r'-(\d+)$'
            value.fields['group'].value = 1
            editor.apply.click()
            self.assertNotIn('番号', source.columns)
            self.assertIn('番号（新規） 値加工 正規表現で抽出 入力列 商品', operation_label(editor.entries.items[0]))
            self.assertIn('番号', dict(value.column.options).values())
            value.column.value = '番号'
            value.action.value = 'trim'
            editor.apply.click()
            self.assertEqual(len(editor.entries.items), 2)
            editor.entries.items[0].children[-1].click()
            self.assertIn('削除できません', editor.status.value)
            self.assertEqual(len(editor.operations), 2)
            form.generate_button.click()
            self.assertIn('.str.strip()', form.result)
            editor.entries.items[1].children[-1].click()
            editor.entries.items[0].children[-1].click()
            self.assertTrue(form.generate_button.disabled)

    def test_unified_form_keeps_numeric_looking_codes_as_text(self):
        import pandas as pd
        from zizai.forms import create_form

        source = pd.DataFrame({'コード': ['001', '002'], '数量': [1, 2],
                               '有効': pd.array([True, None], dtype='boolean'),
                               '日付': pd.to_datetime(['2026-11-20', '2026-11-21'])})
        shared = source_test_support.REPO / 'connectors'
        with patch.object(sys, 'path', [str(shared / 'dataintegration'), *sys.path]):
            form = create_form(shared, namespace={'df': source})
            self.addCleanup(form.close)
            form.connector.value = 'dataintegration'
            form.action.value = 'apply_data_operations'
            form.field_widgets['input_variable'].value = 'df'
            editor = form._dataframe_editor
            value, row = editor.value_fields, editor.row_fields
            value.column.value = 'コード'
            editor.category.value = 'value'
            self.assertIn('extract_regex', dict(value.action.options).values())
            self.assertNotIn('formula', dict(value.action.options).values())
            value.column.value = '数量'
            self.assertIn('formula', dict(value.action.options).values())
            self.assertIn('fill_null', dict(value.action.options).values())
            self.assertNotIn('add', dict(value.action.options).values())
            row.column.value = '有効'
            editor.category.value = 'condition'
            row.action.value = 'keep'
            self.assertIn('bool_equal', dict(row.comparison.options).values())
            row.comparison.value = 'bool_equal'
            row.value.value = 'true'
            editor.apply.click()
            row.column.value = '日付'
            self.assertIn('date_between', dict(row.comparison.options).values())
            self.assertNotIn('greater', dict(row.comparison.options).values())
            row.comparison.value = 'date_equal'
            row.value.value = '2026-11-20'
            editor.apply.click()
            form.generate_button.click()
            scope = {'df': source}
            exec(compile(form.result, '<typed-conditions>', 'exec'), scope)
            self.assertEqual(scope['processed_df']['コード'].tolist(), ['001'])

    def test_new_column_accepts_multiline_formula_below_list_and_edits_inline(self):
        import pandas as pd
        from ipywidgets import Textarea
        from zizai.forms import create_form

        data = pd.DataFrame({'数量': [2, 3], '税抜 単価': [50, 80], 'コード': ['001', '002']}, index=[4, 7])
        shared = source_test_support.REPO / 'connectors'
        with patch.object(sys, 'path', [str(shared / 'dataintegration'), *sys.path]):
            form = create_form(shared, namespace={'df': data})
            self.addCleanup(form.close)
            form.connector.value = 'dataintegration'
            form.action.value = 'apply_data_operations'
            form.field_widgets['input_variable'].value = 'df'
            editor = form._dataframe_editor
            value = editor.value_fields
            self.assertIs(editor.entries.rows.children[-1], editor.settings)
            self.assertEqual(editor.column.options[0][0], '新しく作る')
            editor.column.value = editor.column.options[0][1]
            value.action.value = 'formula'
            entry = value.fields['expression']
            self.assertIsInstance(entry, Textarea)
            self.assertIs(editor.settings.children[1], entry)
            entry.value = '(数量 + 1) *\n    `税抜 単価`'
            value.new_column.value = '金額'
            editor.apply.click()
            form.generate_button.click()
            self.assertIn("processed_df['金額'] = (processed_df['数量'] + 1) * processed_df['税抜 単価']", form.result)
            scope = {'df': data}
            exec(compile(form.result, '<generated-formula>', 'exec'), scope)
            self.assertEqual(scope['processed_df']['金額'].to_dict(), {4: 150, 7: 320})
            self.assertNotIn('金額', data.columns)
            total = form.result

            for expression in ('数量.sum()', '数量 / 0', '不明列 + 1', '数量 + コード'):
                entry.value = expression
                value.new_column.value = '別の列'
                editor.apply.click()
                self.assertIn('role="alert"', editor.status.value)
                self.assertEqual(len(editor.operations), 1)
                form.generate_button.click()
                self.assertEqual(form.result, total)
            editor.column.value = '数量'
            value.action.value = 'formula'
            value.fields['expression'].value = '数量 + 1'
            editor.apply.click()
            first, second = editor.entries.items
            first.children[-2].click()
            self.assertEqual(editor.entries.rows.children, (first, editor.settings, second))
            self.assertEqual(value.new_column.value, '金額')
            self.assertEqual(value.fields['expression'].value, '(数量 + 1) *\n    `税抜 単価`')
            editor.cancel.click()
            self.assertEqual(editor.entries.rows.children, (first, second, editor.settings))
            self.assertEqual(first.children[-2].description, '編集')

    def test_value_operations_join_text_and_reject_zero_division_without_changing_input(self):
        import pandas as pd

        shared = source_test_support.REPO / 'connectors/dataintegration'
        with patch.object(sys, 'path', [str(shared), *sys.path]):
            from dataintegration_connector import apply_value_operations
        source = pd.DataFrame({'地域': [' 東京 ', None], 'コード': ['AbC', 'XYZ'], '差': [-3, 0]})
        operations = [
            {'op': 'trim', 'column': '地域'},
            {'op': 'lower', 'column': 'コード'},
            {'op': 'concat', 'column': '地域', 'other_column': 'コード', 'separator': ' / ', 'output': '表示'},
            {'op': 'abs', 'column': '差', 'output': '絶対値'},
        ]
        result = apply_value_operations(source, operations=operations)
        self.assertEqual(result['表示'].fillna('-').tolist(), ['東京 / abc', '-'])
        self.assertEqual(result['絶対値'].tolist(), [3, 0])
        with self.assertRaisesRegex(ValueError, '0で割る'):
            apply_value_operations(source, operations=[*operations, {'op': 'divide', 'column': '差', 'number': 0}])
        self.assertEqual(source['地域'].iloc[0], ' 東京 ')
        self.assertNotIn('表示', source.columns)

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
            editor = form._dataframe_editor
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
            editor = form._dataframe_editor

            def send(column, **message):
                header = next(header for header in editor._headers if header._column_name == column)
                editor._handle_header(header, column, message)

            send('数量', event='column-operation', role='convert')
            self.assertLess(editor.root.children.index(editor._type_controls), editor.root.children.index(editor.grid))
            self.assertTrue(editor._type_controls.children)
            self.assertFalse(editor._controls.children)

            def marker(index):
                return editor._heading.children[index].children[0]

            other_marker = marker(0)
            self.assertEqual(marker(1).description, 'ABC')
            editor._handle_type(marker(1), '数量', {'event': 'column-type', 'role': 'integer'})
            self.assertEqual(marker(1).description, '123')
            self.assertIs(marker(0), other_marker)
            self.assertEqual(editor.preview['数量'].iloc[0], 12)
            self.assertFalse(editor._type_controls.children)
            self.assertEqual(source['数量'].iloc[0], '12')

            send('商品', event='column-rename', name='product')
            self.assertFalse(editor._type_controls.children)
            send('数量', event='column-operation', role='drop')
            self.assertEqual(editor.preview.columns.tolist(), ['product', '数量', '備考'])
            self.assertTrue(marker(1).disabled)
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
