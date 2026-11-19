"""Verify generated Python execution with trusted synthetic scripts."""
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import venv

import source_test_support
from zizai.form_definition import load_definition
from zizai.form_model import FormModel


class PythonConnectorTests(unittest.TestCase):
    def setUp(self):
        shared = source_test_support.REPO / 'connectors'
        module_path = patch.object(sys, 'path', [str(shared / 'python'), *sys.path])
        module_path.start()
        self.addCleanup(module_path.stop)
        self.model = FormModel(load_definition(shared))
        self.model.set_connector('python')
        self.model.set_action('execute_python')

    def test_generated_code_only_runs_after_user_executes_and_returns_table(self):
        self.assertEqual(set(self.model.fields), {'file_path', 'output_variable'})
        self.assertEqual(self.model.values['output_variable'], 'result')
        with self.assertRaises(ValueError):
            self.model.generate()
        with tempfile.TemporaryDirectory(prefix='zizai-python-test-') as folder:
            marker = Path(folder) / 'marker.txt'
            script = (
                'from pathlib import Path\n'
                'import sys\n'
                'def main():\n'
                f'    Path({marker.as_posix()!r}).write_text("実行済み", encoding="utf-8")\n'
                '    print(\'__ZIZ_RESULT__={"unexpected": 1}\')\n'
                '    return {"結果": "成功", "ファイル": __file__, "python": sys.executable, "環境": sys.prefix}\n'
            )
            path = Path(folder) / '試用.py'
            self.model.set_value('file_path', str(path))
            self.model.set_value('output_variable', '結果')
            code = self.model.generate()
            self.assertFalse(marker.exists())
            self.assertFalse(path.exists())
            self.assertTrue(code.startswith('import python_connector\n'))
            self.assertIn('python_connector.execute_python_file(script_file=script_file)', code)
            self.assertNotIn('env_path', code)
            path.write_text(script, encoding='utf-8')
            namespace = {}
            with redirect_stdout(io.StringIO()) as stdout:
                exec(compile(code, '<generated-python>', 'exec'), namespace)
            self.assertEqual(marker.read_text(encoding='utf-8'), '実行済み')
            self.assertIn('__ZIZ_RESULT__', stdout.getvalue())
            row = namespace['結果'].iloc[0]
            self.assertEqual(row['結果'], '成功')
            self.assertEqual(Path(row['ファイル']), path)
            self.assertTrue(Path(row['python']).samefile(sys.executable))
            self.assertTrue(Path(row['環境']).samefile(sys.prefix))
            self.assertEqual(path.read_text(encoding='utf-8'), script)

    def test_selected_venv_scalar_result_and_failure_cleanup(self):
        from python_connector import execute_python, execute_python_file
        with tempfile.TemporaryDirectory(prefix='zizai-python-env-') as folder:
            environment = Path(folder) / '選択環境'
            venv.EnvBuilder(with_pip=False).create(environment)
            script = 'import sys\ndef main():\n    return sys.prefix\n'
            path = Path(folder) / 'environment.py'
            path.write_text(script, encoding='utf-8')
            self.assertEqual(Path(execute_python_file(path, env_path=environment.as_posix())), environment)
            self.assertEqual(Path(execute_python(script, env_path=environment.as_posix())), environment)

        with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaisesRegex(RuntimeError, 'Python実行に失敗.*終了コード'):
                execute_python('print(__file__)\nraise ValueError("架空エラー")\n')
        self.assertIn('架空エラー', stderr.getvalue())
        temp_script = Path(stdout.getvalue().strip())
        self.assertTrue(temp_script.is_absolute())
        self.assertFalse(temp_script.parent.exists())

    def test_form_browses_for_python_file_and_only_generates_a_file_call(self):
        from zizai.forms import create_form

        form = create_form(source_test_support.REPO / 'connectors')
        self.addCleanup(form.close)
        form.connector.value = 'python'
        form.action.value = 'execute_python'
        self.assertEqual(set(form.field_widgets), {'file_path', 'output_variable'})
        self.assertTrue(form.generate_button.disabled)
        path = 'C:/選択先/試用.py'
        with patch('tkinter.Tk', return_value=Mock()), \
                patch('tkinter.filedialog.askopenfilename', return_value=path) as file:
            form.browse_buttons['file_path'].click()
            self.assertEqual(file.call_args.kwargs['filetypes'][0][1], '*.py')
        self.assertEqual(form.field_widgets['file_path'].value, path)
        form.generate_button.click()
        self.assertIn("script_file = 'C:/選択先/試用.py'", form.result)
        self.assertIn('result = python_connector.execute_python_file(script_file=script_file)', form.result)


if __name__ == '__main__':
    unittest.main()
