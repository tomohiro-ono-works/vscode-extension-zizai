import json
import unittest

import source_test_support
from zizai.form_definition import load_definition
from zizai.form_model import FormModel


class DataFrameTableActionsTests(unittest.TestCase):
    def open_form(self, action, **namespace):
        from zizai.forms import create_form

        form = create_form(source_test_support.REPO / 'connectors', namespace=namespace)
        self.addCleanup(form.close)
        form.connector.value = 'dataintegration'
        form.action.value = action
        form.field_widgets['input_variable'].value = 'left'
        return form, form._dataframe_editor

    def generate(self, action, settings, **namespace):
        form = FormModel(load_definition(source_test_support.REPO / 'connectors'))
        form.set_connector('dataintegration')
        form.set_action(action)
        form.set_value('input_variable', 'left')
        form.set_value('output_variable', 'result')
        form.set_value('operations', json.dumps(settings, ensure_ascii=False))
        source = form.generate()
        self.assertNotIn('dataintegration_connector', source)
        exec(compile(source, '<generated-table-action>', 'exec'), namespace)
        return namespace['result']

    def test_sort_uses_key_order_directions_and_resets_index(self):
        import pandas as pd

        data = pd.DataFrame({'部署': ['B', 'A', 'A', 'B', None], '数量': [3, 2, 8, 6, 1]}, index=[20, 21, 22, 23, 24])
        keys = [{'column': '部署', 'ascending': True}, {'column': '数量', 'ascending': False}]
        spec = {'keys': keys, 'na_position': 'last', 'reset_index': True}
        result = self.generate('sort_rows', spec, left=data)
        self.assertEqual(result['数量'].tolist(), [8, 2, 6, 3, 1])
        self.assertEqual(result.index.tolist(), [0, 1, 2, 3, 4])
        result = self.generate('sort_rows', {**spec, 'na_position': 'first', 'reset_index': False}, left=data)
        self.assertEqual(result.index.tolist(), [24, 22, 21, 23, 20])
        self.assertEqual(data.index.tolist(), [20, 21, 22, 23, 24])

    def test_aggregate_supports_several_methods_and_no_group(self):
        import pandas as pd

        data = pd.DataFrame({'部署': ['A', 'A', 'A', 'A', None], '数量': [2, 4, 2, None, 8]})
        methods = [{'column': '数量', 'method': method, 'output': method}
                   for method in ('sum', 'mean', 'min', 'max', 'count', 'nunique', 'median', 'mode')]
        grouped = self.generate('aggregate_rows', {'groups': ['部署'], 'aggregations': methods}, left=data)
        self.assertEqual(grouped.iloc[0].drop('部署').tolist(), [8.0, 8 / 3, 2.0, 4.0, 3, 2, 2.0, 2.0])
        self.assertTrue(pd.isna(grouped.iloc[1]['部署']))
        total = self.generate('aggregate_rows', {'groups': [], 'aggregations': methods}, left=data)
        self.assertEqual(total.iloc[0].tolist(), [16.0, 4.0, 2.0, 8.0, 4, 3, 3.0, 2.0])

    def test_join_supports_differently_named_composite_keys(self):
        import pandas as pd

        left = pd.DataFrame({'ID': [1, 1, 2], '組': ['甲', '乙', '甲']})
        right = pd.DataFrame({'番号': [1, 1], '区分': ['乙', '甲'], '得点': [30, 40]})
        settings = {'right': 'right', 'kind': 'left', 'keys': [
            {'left': 'ID', 'right': '番号'}, {'left': '組', 'right': '区分'}]}
        result = self.generate('combine_frames', settings, left=left, right=right)
        self.assertEqual(result['得点'].fillna(-1).tolist(), [40, 30, -1])

    def test_union_aligns_columns_by_name_and_except_distinct_handles_nulls(self):
        import pandas as pd

        left = pd.DataFrame({'ID': [1, 1, 2, 3, None], '区分': ['a', 'a', 'b', 'c', 'n']})
        right = pd.DataFrame({'区分': ['b', 'd', 'n'], 'ID': [2, 4, None]})
        settings = {'right': 'right', 'columns': ['ID', '区分']}
        all_rows = self.generate('combine_frames', {**settings, 'kind': 'union_all'}, left=left, right=right)
        self.assertEqual(all_rows.columns.tolist(), ['ID', '区分'])
        self.assertEqual(len(all_rows), 8)
        distinct = self.generate('combine_frames', {**settings, 'kind': 'union_distinct'}, left=left, right=right)
        self.assertEqual(distinct['区分'].tolist(), ['a', 'b', 'c', 'n', 'd'])
        difference = self.generate('combine_frames', {**settings, 'kind': 'except_distinct'}, left=left, right=right)
        self.assertEqual(difference.to_dict('records'), [{'ID': 1.0, '区分': 'a'}, {'ID': 3.0, '区分': 'c'}])

    def test_sort_form_reorders_sort_keys(self):
        import pandas as pd

        data = pd.DataFrame({'部署': ['B', 'A', 'B'], '数量': [3, 1, 2]}, index=[9, 7, 5])
        form, editor = self.open_form('sort_rows', left=data)
        first = editor.rules.rows.children[0]
        first.children[0].value = '部署'
        editor.rules.add.click()
        second = editor.rules.rows.children[1]
        second.children[0].value = '数量'
        second.children[1].value = False
        first.children[-2].click()
        editor.reset_index.value = False
        form.generate_button.click()
        namespace = {'left': data}
        exec(form.result, namespace)
        self.assertEqual(namespace['sorted_df'].index.tolist(), [9, 5, 7])
        self.assertIn("by=['数量', '部署']", form.result)

    def test_aggregate_form_displays_sample_but_generated_code_uses_all_rows(self):
        import pandas as pd

        data = pd.DataFrame({'部署': ['A'] * 35, '数量': [1] * 30 + [10] * 5})
        form, editor = self.open_form('aggregate_rows', left=data)
        editor.groups.value = ('部署',)
        row = editor.rules.rows.children[0]
        row.children[0].value = '数量'
        row.children[1].value = 'sum'
        self.assertIn('先頭30行', editor.preview.value)
        self.assertIn('<td>30</td>', editor.preview.value)
        form.generate_button.click()
        namespace = {'left': data}
        exec(form.result, namespace)
        self.assertEqual(namespace['aggregated_df']['数量_sum'].tolist(), [80])

    def test_union_form_requires_explicit_common_columns_for_different_schemas(self):
        import pandas as pd

        left = pd.DataFrame({'ID': [1], '左の値': ['左']})
        right = pd.DataFrame({'右の値': ['右'], 'ID': [2]})
        form, editor = self.open_form('combine_frames', left=left, right=right)
        editor.right.value = 'right'
        editor.kind.value = 'union_all'
        self.assertTrue(form.generate_button.disabled)
        self.assertEqual(editor.columns_used.options, ('ID',))
        editor.columns_used.value = ('ID',)
        form.generate_button.click()
        self.assertNotIn('table', editor.status.value)
        namespace = {'left': left, 'right': right}
        exec(form.result, namespace)
        self.assertEqual(namespace['combined_df'].to_dict('records'), [{'ID': 1}, {'ID': 2}])
