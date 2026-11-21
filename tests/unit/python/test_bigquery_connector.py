"""Check generated BigQuery actions without communicating with Google Cloud."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import source_test_support
from zizai.form_definition import load_definition
from zizai.form_model import FormModel


class BigQueryConnectorTests(unittest.TestCase):
    def setUp(self):
        shared = source_test_support.REPO / 'connectors'
        self.model = FormModel(load_definition(shared))
        self.model.set_connector('bigquery')
        self.namespace = {}
        modules = patch.object(sys, 'path', [str(shared / 'bigquery'), *sys.path])
        modules.start()
        self.addCleanup(modules.stop)

    def generate(self, action, **settings):
        self.model.set_action(action)
        self.model.set_value('project_id', 'fixture-project')
        for name, value in settings.items():
            self.model.set_value(name, value)
        return self.model.generate()

    def test_file_sql_sends_only_when_generated_code_runs_and_applies_output_schema(self):
        import pandas as pd
        from bigquery_connector import bigquery, execute_sql_file
        client = Mock()
        rows = client.query.return_value.result.return_value
        rows.schema = [bigquery.SchemaField('f0_', 'INTEGER')]
        rows.to_dataframe.return_value = pd.DataFrame({'f0_': [1]})

        with patch.object(bigquery, 'Client', return_value=client) as factory:
            self.assertEqual(set(self.model.actions), {'execute_sql', 'execute_sql_file', 'load_data'})
            self.model.set_action('execute_sql_file')
            self.model.set_value('project_id', 'fixture-project')
            self.assertEqual(self.model.values['output_variable'], 'result')
            with self.assertRaises(ValueError):
                self.model.generate()
            with tempfile.TemporaryDirectory(prefix='zizai-bq-') as scratch:
                script = Path(scratch) / '確認.sql'
                from_file = self.generate('execute_sql_file', sql_file=str(script), encoding='shift_jis',
                                          output_schema='[{"origin_name":"f0_","new_name":"answer"}]')
                self.assertFalse(script.exists())
                factory.assert_not_called()
                script.write_text('SELECT 1 -- 確認', encoding='shift_jis')
                exec(compile(from_file, '<generated-bigquery>', 'exec'), self.namespace)
                self.assertEqual(self.namespace['result'].to_dict('records'), [{'answer': 1}])
                self.assertEqual(client.query.call_args.args, ('SELECT 1 -- 確認',))
                self.assertFalse(client.query.call_args.kwargs['job_config'].use_legacy_sql)
                raw = execute_sql_file('fixture-project', script, encoding='shift_jis', maximum_bytes_billed=1)
                self.assertEqual(raw.to_dict('records'), [{'f0_': 1}])
                self.assertEqual(client.query.call_args.kwargs['job_config'].maximum_bytes_billed, 1)
            factory.assert_called_with(project='fixture-project')
            self.assertEqual(client.close.call_count, 2)

    def test_load_modes_and_schema_reach_the_mock_client(self):
        import pandas as pd
        from bigquery_connector import bigquery
        frame = pd.DataFrame({'商品': ['りんご']})
        self.namespace['bigquery_connector'] = frame
        client = Mock()
        job = client.load_table_from_dataframe.return_value
        job.job_id = 'fixture-job'
        job.output_rows = 1
        with patch.object(bigquery, 'Client', return_value=client) as factory:
            self.model.set_action('load_data')
            self.assertEqual(self.model.values['output_variable'], 'result')
            for mode, disposition in [('新規／空テーブル', 'WRITE_EMPTY'),
                                      ('追記', 'WRITE_APPEND'), ('置換', 'WRITE_TRUNCATE')]:
                code = self.generate('load_data', dataset_id='fixture_data', table_id='items',
                                     input_variable='bigquery_connector', output_variable='load_info',
                                     schema='[{"name": "商品", "type": "STRING"}]')
                if mode == '新規／空テーブル':
                    self.assertEqual(self.model.values['mode'], mode)
                    factory.assert_not_called()
                else:
                    self.model.set_value('mode', mode)
                    code = self.model.generate()
                exec(compile(code, '<generated-bigquery-load>', 'exec'), self.namespace)
                call = client.load_table_from_dataframe.call_args
                self.assertEqual(call.args[0].to_dict('records'), [{'商品': 'りんご'}])
                self.assertEqual(str(call.args[1]), 'fixture-project.fixture_data.items')
                config = call.kwargs['job_config']
                self.assertEqual(config.write_disposition, disposition)
                self.assertEqual(config.schema[0].name, '商品')
                self.assertEqual(self.namespace['load_info']['rows'].iat[0], 1)
            self.assertEqual(job.result.call_count, 3)
            self.assertEqual(client.close.call_count, 3)


if __name__ == '__main__':
    unittest.main()
