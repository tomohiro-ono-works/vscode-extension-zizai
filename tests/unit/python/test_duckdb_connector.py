"""Run the generated DuckDB creation code against a temporary database."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import source_test_support
from zizai.form_definition import load_definition
from zizai.form_model import FormModel


class DuckDBConnectorTests(unittest.TestCase):
    def test_generated_create_opens_database_without_replacing_existing_tables(self):
        import duckdb

        shared = source_test_support.REPO / 'connectors'
        model = FormModel(load_definition(shared))
        model.set_connector('duckdb')
        model.set_action('create_db_file')
        self.assertEqual(model.values['db_file_name'], 'sample.duckdb')
        with self.assertRaises(ValueError):
            model.generate()

        with tempfile.TemporaryDirectory(prefix='zizai-duckdb-') as scratch:
            folder = Path(scratch) / 'データ'
            model.set_value('db_folder', str(folder))
            model.set_value('db_file_name', '商品DB')
            code = model.generate()
            self.assertTrue(code.startswith('import duckdb_connector\n'))
            self.assertIn(folder.as_posix(), code)
            self.assertFalse(folder.exists())

            result = {}
            with patch.object(sys, 'path', [str(shared / 'duckdb'), *sys.path]):
                exec(compile(code, '<generated-duckdb>', 'exec'), result)
                database = folder / '商品DB.duckdb'
                written_path = result['db_info']['file_path'].iat[0]
                self.assertEqual(Path(written_path), database)
                self.assertNotIn('\\', written_path)
                with duckdb.connect(str(database)) as connection:
                    connection.execute('CREATE TABLE items AS SELECT 7 AS id')
                exec(compile(code, '<generated-duckdb>', 'exec'), result)
                with duckdb.connect(str(database), read_only=True) as connection:
                    self.assertEqual(connection.execute('SELECT id FROM items').fetchall(), [(7,)])


if __name__ == '__main__':
    unittest.main()
