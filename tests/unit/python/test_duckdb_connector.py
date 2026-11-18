"""Run generated DuckDB code against a temporary database."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import source_test_support
from zizai.form_definition import load_definition
from zizai.form_model import FormModel


class DuckDBConnectorTests(unittest.TestCase):
    def test_generated_sql_and_cp932_script_run_only_against_selected_database(self):
        import duckdb

        shared = source_test_support.REPO / 'connectors'
        model = FormModel(load_definition(shared))
        model.set_connector('duckdb')
        model.set_action('execute_sql')
        with tempfile.TemporaryDirectory(prefix='zizai-duckdb-sql-') as scratch:
            folder = Path(scratch)
            database = folder / '商品.duckdb'
            model.set_value('db_folder', str(folder))
            model.set_value('db_file_name', database.name)
            with self.assertRaises(ValueError):
                model.generate()
            model.set_value('sql', "CREATE TABLE products AS SELECT 'りんご' AS 商品, 3 AS 数量")
            create_code = model.generate()
            self.assertFalse(database.exists())

            with duckdb.connect(str(database)):
                pass
            script = folder / '商品.sql'
            script.write_text('SELECT 商品,\n数量 FROM products', encoding='cp932')
            model.set_action('execute_sql_file')
            self.assertEqual(model.values['encoding'], 'utf8')
            model.set_value('sql_folder', str(folder))
            model.set_value('sql_file_name', script.name)
            model.set_value('encoding', 'cp932')
            script_code = model.generate()
            result = {}
            with patch.object(sys, 'path', [str(shared / 'duckdb'), *sys.path]):
                exec(compile(create_code, '<generated-sql>', 'exec'), result)
                exec(compile(script_code, '<generated-script>', 'exec'), result)
                self.assertEqual(result['df'].to_dict('records'), [{'商品': 'りんご', '数量': 3}])
                from duckdb_connector import execute_sql
                with self.assertRaises(FileNotFoundError):
                    execute_sql(folder / 'missing.duckdb', 'SELECT 1')
                self.assertFalse((folder / 'missing.duckdb').exists())
                csv = folder / 'inputs.csv'
                csv.write_text('id\n1\n', encoding='utf-8')
                with self.assertRaises(duckdb.PermissionException):
                    execute_sql(database, f"SELECT * FROM read_csv_auto('{csv.as_posix()}')")

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
