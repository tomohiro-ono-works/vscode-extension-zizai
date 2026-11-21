
"""Notebook connector magics exercise the real IPython dispatcher without network calls."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from IPython.core.interactiveshell import InteractiveShell
import pandas as pd
from traitlets.config import Config

from zizai.forms import create_form, load_ipython_extension


CONNECTORS = Path(__file__).resolve().parents[3] / 'connectors'


class ConnectorMagicTests(unittest.TestCase):
    def setUp(self):
        scratch = self.enterContext(TemporaryDirectory(prefix='zizai-sql-magic-'))
        self.root = Path(scratch)
        self.shell = InteractiveShell(
            ipython_dir=scratch, config=Config({'HistoryManager': {'hist_file': ':memory:'}}))
        self.addCleanup(self.shell.history_manager.end_session)
        load_ipython_extension(self.shell)
        self.frame = pd.DataFrame({'value': [1]})

    def test_form_shortcuts_select_the_requested_connector(self):
        for name, connector in (('zizai_bq', 'bigquery'), ('zizai_duck', 'duckdb'),
                                ('zizai_csv', 'csv'), ('zizai_excel', 'excel')):
            with self.subTest(name=name), patch('zizai.forms.show_form') as show:
                self.shell.run_line_magic(name, '')
                show.assert_called_once_with(connector=connector)
                form = create_form(CONNECTORS, connector=connector)
                try:
                    self.assertEqual(form.connector.value, connector)
                    self.assertIsNone(form.action.value)
                finally:
                    form.close()
        with patch('zizai.forms.show_form') as show:
            self.shell.run_cell_magic('zizai_excel', '', '# フォーム表示\n')
            show.assert_called_once_with(connector='excel')
        with self.assertRaisesRegex(ValueError, 'フォーム'):
            self.shell.run_cell_magic('zizai_csv', '', 'SELECT 1')

    def test_bigquery_displays_assigns_and_exports(self):
        query = 'SELECT 1 AS value\n'
        run = Mock(return_value=self.frame)
        self.shell.user_ns['zizai_bq_project'] = 'test-project'
        with patch.dict(sys.modules, bigquery_connector=SimpleNamespace(execute_sql=run)):
            self.assertIs(self.shell.run_cell_magic('zizai_bq', '', query), self.frame)
            self.shell.run_cell_magic('zizai_bq', '> df', query)
            self.assertIs(self.shell.user_ns['df'], self.frame)
            for extension, read in (('csv', pd.read_csv), ('xlsx', pd.read_excel)):
                path = self.root / f'結果 data.{extension}'
                self.shell.run_cell_magic('zizai_bq', f'> "{path}"', query)
                pd.testing.assert_frame_equal(read(path), self.frame)
            self.assertEqual(run.call_count, 4)
            run.assert_called_with('test-project', query)

    def test_rejects_bad_destinations_and_missing_connection_before_query(self):
        run = Mock(return_value=self.frame)
        with patch.dict(sys.modules, bigquery_connector=SimpleNamespace(execute_sql=run)):
            with self.assertRaisesRegex(ValueError, 'zizai_bq_project'):
                self.shell.run_cell_magic('zizai_bq', '', 'SELECT 1')
            self.shell.user_ns['zizai_bq_project'] = 'test-project'
            existing = self.root / 'existing.csv'
            existing.write_text('saved', encoding='utf-8')
            for target, error in (('file.txt', ValueError), ('class', ValueError), (existing, FileExistsError)):
                with self.subTest(target=target), self.assertRaises(error):
                    self.shell.run_cell_magic('zizai_bq', f'> {target}', 'SELECT 1')
            run.assert_not_called()
            self.assertEqual(existing.read_text(encoding='utf-8'), 'saved')

    def test_duckdb_uses_the_registered_database_connector(self):
        import duckdb
        import importlib.util

        path = self.root / 'source.duckdb'
        with duckdb.connect(str(path)) as connection:
            connection.execute('CREATE TABLE records AS SELECT 1 AS value')
        self.shell.user_ns['zizai_duck_db'] = path
        location = CONNECTORS / 'duckdb/duckdb_connector.py'
        spec = importlib.util.spec_from_file_location('duckdb_connector', location)
        connector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(connector)
        with patch.dict(sys.modules, duckdb_connector=connector):
            self.shell.run_cell_magic('zizai_duck', '> df', 'SELECT value FROM records')
        self.assertEqual(self.shell.user_ns['df']['value'].to_list(), [1])
