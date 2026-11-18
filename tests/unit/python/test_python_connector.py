"""Verify generated Python execution with trusted synthetic scripts."""
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
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
        with self.assertRaises(ValueError):
            self.model.generate()
        with tempfile.TemporaryDirectory(prefix='zizai-python-test-') as folder:
            marker = Path(folder) / 'marker.txt'
            script = (
                'from pathlib import Path\n'
                'def main():\n'
                f'    Path({marker.as_posix()!r}).write_text("実行済み", encoding="utf-8")\n'
                '    print(\'__ZIZ_RESULT__={"unexpected": 1}\')\n'
                '    return {"結果": "成功", "一時ファイル": __file__}\n'
            )
            self.model.set_value('script', script)
            self.model.set_value('output_variable', '結果')
            code = self.model.generate()
            self.assertFalse(marker.exists())
            self.assertTrue(code.startswith('import python_connector\n'))
            namespace = {}
            with redirect_stdout(io.StringIO()) as stdout:
                exec(compile(code, '<generated-python>', 'exec'), namespace)
            self.assertEqual(marker.read_text(encoding='utf-8'), '実行済み')
            self.assertIn('__ZIZ_RESULT__', stdout.getvalue())
            row = namespace['結果'].iloc[0]
            self.assertEqual(row['結果'], '成功')
            self.assertFalse(Path(row['一時ファイル']).parent.exists())

    def test_selected_venv_scalar_result_and_failure_cleanup(self):
        from python_connector import execute_python
        with tempfile.TemporaryDirectory(prefix='zizai-python-env-') as folder:
            environment = Path(folder) / '選択環境'
            venv.EnvBuilder(with_pip=False).create(environment)
            script = 'import sys\ndef main():\n    return sys.prefix\n'
            self.model.set_value('script', script)
            self.model.set_value('env_path', environment.as_posix())
            namespace = {}
            exec(compile(self.model.generate(), '<generated-venv>', 'exec'), namespace)
            self.assertEqual(Path(namespace['result']), environment)

        with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaisesRegex(RuntimeError, 'Python実行に失敗.*終了コード'):
                execute_python('print(__file__)\nraise ValueError("架空エラー")\n')
        self.assertIn('架空エラー', stderr.getvalue())
        temp_script = Path(stdout.getvalue().strip())
        self.assertTrue(temp_script.is_absolute())
        self.assertFalse(temp_script.parent.exists())


if __name__ == '__main__':
    unittest.main()
