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
    def test_generated_create_table_imports_csv_and_excel_and_requires_explicit_replace(self):
        import duckdb
        from openpyxl import Workbook

        shared = source_test_support.REPO / 'connectors'
        model = FormModel(load_definition(shared))
        data = {}

        def generate(connector, action, **values):
            model.set_connector(connector)
            model.set_action(action)
            for name, value in values.items():
                model.set_value(name, value)
            return model.generate()

        with tempfile.TemporaryDirectory(prefix='zizai-duckdb-table-') as scratch:
            folder = Path(scratch)
            database = folder / 'main.duckdb'
            (folder / '商品.csv').write_text('商品,数量\nりんご,3\n', encoding='utf-8')
            book = Workbook()
            book.active.title = 'シート1'
            book.active.append(['商品', '数量'])
            book.active.append(['りんご', 5])
            book.save(folder / '商品.xlsx')
            book.close()

            csv_code = generate('csv', 'import', folder=str(folder), filename='商品.csv', output_variable='注文')
            excel_code = generate('excel', 'read_excel', folder=str(folder), filename='商品.xlsx', output_variable='入荷')
            db_code = generate('duckdb', 'create_db_file', db_folder=str(folder), db_file_name=database.name)
            table_code = generate('duckdb', 'create_table', input_variable='注文', table_name='注文表',
                                  output_variable='結果')
            self.assertEqual(model.values['mode'], '新規作成')
            self.assertIn('replace = False', table_code)
            self.assertFalse(database.exists())

            with patch.object(sys, 'path', [str(shared / 'duckdb'), *sys.path]):
                for code in (csv_code, excel_code, db_code, table_code):
                    exec(compile(code, '<generated-data>', 'exec'), data)
                excel_table = generate('duckdb', 'create_table', input_variable='入荷', table_name='入荷表')
                exec(compile(excel_table, '<generated-excel-table>', 'exec'), data)
                sql = ('SELECT 注文表.商品, CAST(注文表.数量 AS INTEGER) AS 注文数, 入荷表.数量 AS 入荷数 '
                       'FROM 注文表 JOIN 入荷表 USING (商品)')
                (folder / 'join.sql').write_text(sql, encoding='utf-8')
                query = generate('duckdb', 'execute_sql_file', sql_folder=scratch,
                                 sql_file_name='join.sql', output_variable='集計')
                exec(compile(query, '<generated-query>', 'exec'), data)
                self.assertEqual(data['集計'].to_dict('records'), [{'商品': 'りんご', '注文数': 3, '入荷数': 5}])

                duplicate = generate('duckdb', 'create_table', input_variable='入荷', table_name='注文表', mode='新規作成')
                with self.assertRaises(duckdb.CatalogException):
                    exec(compile(duplicate, '<generated-duplicate>', 'exec'), data)
                exec(compile(query, '<generated-query>', 'exec'), data)
                self.assertEqual(data['集計']['注文数'].iat[0], 3)

                data['duckdb_connector'] = data['入荷']
                replace = generate('duckdb', 'create_table', mode='置換',
                                   input_variable='duckdb_connector', output_variable='db_file')
                self.assertIn('replace = True', replace)
                exec(compile(replace, '<generated-replace>', 'exec'), data)
                self.assertEqual(data['db_file'][['table_name', 'rows']].to_dict('records'),
                                 [{'table_name': '注文表', 'rows': 1}])
                exec(compile(query, '<generated-query>', 'exec'), data)
                self.assertEqual(data['集計'].to_dict('records'), [{'商品': 'りんご', '注文数': 5, '入荷数': 5}])

    def test_generated_cp932_script_runs_only_against_selected_database(self):
        import duckdb

        shared = source_test_support.REPO / 'connectors'
        model = FormModel(load_definition(shared))
        model.set_connector('duckdb')
        self.assertNotIn('execute_sql', model.actions)
        model.set_action('execute_sql_file')
        with tempfile.TemporaryDirectory(prefix='zizai-duckdb-sql-') as scratch:
            folder = Path(scratch)
            database = folder / '商品.duckdb'
            model.set_value('db_folder', str(folder))
            model.set_value('db_file_name', database.name)
            with self.assertRaises(ValueError):
                model.generate()
            self.assertFalse(database.exists())

            with duckdb.connect(str(database)) as connection:
                connection.execute("CREATE TABLE products AS SELECT 'りんご' AS 商品, 3 AS 数量")
            script = folder / '商品.sql'
            self.assertEqual(model.values['encoding'], 'utf8')
            model.set_value('sql_folder', str(folder))
            model.set_value('sql_file_name', script.name)
            model.set_value('encoding', 'cp932')
            script_code = model.generate()
            self.assertFalse(script.exists())
            script.write_text('SELECT 商品,\n数量 FROM products', encoding='cp932')
            result = {}
            with patch.object(sys, 'path', [str(shared / 'duckdb'), *sys.path]):
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
