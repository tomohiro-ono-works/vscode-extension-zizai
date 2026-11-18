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

    def test_direct_and_file_sql_send_only_when_generated_code_runs(self):
        import pandas as pd
        from bigquery_connector import bigquery
        client = Mock()
        rows = client.query.return_value.result.return_value
        rows.schema = [bigquery.SchemaField('f0_', 'INTEGER')]
        rows.to_dataframe.return_value = pd.DataFrame({'f0_': [1]})

        with patch.object(bigquery, 'Client', return_value=client) as factory:
            self.model.set_action('execute_sql')
            with self.assertRaises(ValueError):
                self.model.generate()
            direct = self.generate('execute_sql', sql='SELECT 1', output_variable='集計')
            with tempfile.TemporaryDirectory(prefix='zizai-bq-') as scratch:
                script = Path(scratch) / '確認.sql'
                from_file = self.generate('execute_sql_file', sql_folder=scratch, sql_file_name=script.name,
                                          encoding='shift_jis', output_variable='集計')
                self.assertFalse(script.exists())
                factory.assert_not_called()
                script.write_text('SELECT 1 -- 確認', encoding='shift_jis')
                for code, expected in [(direct, 'SELECT 1'), (from_file, 'SELECT 1 -- 確認')]:
                    exec(compile(code, '<generated-bigquery>', 'exec'), self.namespace)
                    self.assertEqual(self.namespace['集計'].to_dict('records'), [{'f0_': 1}])
                    self.assertEqual(client.query.call_args.args, (expected,))
                    self.assertFalse(client.query.call_args.kwargs['job_config'].use_legacy_sql)
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
