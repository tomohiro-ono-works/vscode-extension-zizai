"""Exercise analytics column selectors and generated Python calls."""
import sys
import unittest
from unittest.mock import patch

import source_test_support
import pandas as pd
from zizai.forms import create_form


class AnalyticsFormTests(unittest.TestCase):
    def make_form(self, connector, action):
        shared = source_test_support.REPO / 'connectors'
        data = pd.DataFrame({'売上': [3, 5, 9, 11], '数量': [1, 2, 3, 4],
                             '区分': ['A', 'A', 'B', 'B']})
        form = create_form(shared, namespace={'df': data, 'other': pd.DataFrame({'別列': [1]})})
        self.addCleanup(form.close)
        form.connector.value = connector
        form.action.value = action
        self.assertTrue(form.generate_button.disabled)
        form.field_widgets['input_variable'].value = 'df'
        return shared, data, form

    def test_statistics_multiple_selection_and_execution(self):
        shared, data, form = self.make_form('statistics', 'describe')
        fields = form.field_widgets
        self.assertEqual(fields['columns'].options, ('売上', '数量', '区分'))
        fields['columns'].value = ('売上', '数量')
        fields['group_columns'].value = ('区分',)
        self.assertFalse(form.generate_button.disabled)
        form.generate_button.click()
        scope = {'df': data}
        with patch.object(sys, 'path', [str(shared / 'statistics'), *sys.path]):
            exec(compile(form.result, '<statistics>', 'exec'), scope)
        self.assertEqual(len(scope['statistics_df']), 4)
        self.assertEqual(set(scope['statistics_df']['column']), {'売上', '数量'})

    def test_regression_selection_and_execution(self):
        shared, data, form = self.make_form('machine_learning', 'fit_linear_regression')
        fields = form.field_widgets
        fields['target'].value = '売上'
        fields['features'].value = ('数量',)
        fields['categories'].value = ('区分',)
        self.assertFalse(form.generate_button.disabled)
        fields['features'].value = ('売上',)
        self.assertTrue(form.generate_button.disabled)
        fields['features'].value = ('数量',)
        form.generate_button.click()
        scope = {'df': data}
        with patch.object(sys, 'path', [str(shared / 'machine_learning'), *sys.path]):
            exec(compile(form.result, '<regression>', 'exec'), scope)
        self.assertEqual(len(scope['model'].score(data)), len(data))

    def test_dataframe_switch_clears_old_selection(self):
        _, _, form = self.make_form('machine_learning', 'fit_linear_regression')
        fields = form.field_widgets
        fields['target'].value = '売上'
        fields['features'].value = ('数量',)
        old = fields['features']
        fields['input_variable'].value = 'other'
        self.assertIsNot(old, fields['features'])
        self.assertEqual(fields['features'].options, ('別列',))
        self.assertEqual(fields['features'].value, ())
        self.assertEqual(fields['target'].value, '')
        self.assertTrue(form.generate_button.disabled)
