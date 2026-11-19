"""Run generated batch calls only against harmless temporary fixtures."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import source_test_support
from zizai.form_definition import load_definition
from zizai.form_model import FormModel


@unittest.skipUnless(os.name == 'nt', 'Windows batch execution')
class ShellConnectorTests(unittest.TestCase):
    def setUp(self):
        shared = source_test_support.REPO / 'connectors'
        self.model = FormModel(load_definition(shared))
        self.model.set_connector('shell')
        self.model.set_action('execute_bat')
        modules = patch.object(sys, 'path', [str(shared / 'shell'), *sys.path])
        modules.start()
        self.addCleanup(modules.stop)

    def test_generated_code_runs_only_the_selected_batch_with_literal_arguments(self):
        with tempfile.TemporaryDirectory(prefix='zizai-batch-') as scratch:
            with self.assertRaises(ValueError):
                self.model.generate()
            path = Path(scratch) / '試用 & %TEMP% !.bat'
            self.model.set_value('file_path', str(path))
            self.model.set_value('args', '["2 words", "A&B!%TEMP%"]')
            code = self.model.generate()
            self.assertFalse(path.exists())
            path.write_text('@echo off\necho "%~1"\necho "%~2"\necho done 1>&2\nexit /b 0\n',
                            encoding='ascii')
            namespace = {}
            exec(compile(code, '<generated-batch>', 'exec'), namespace)
            row = namespace['result'].iloc[0]
            self.assertEqual(row['stdout'].splitlines(), ['"2 words"', '"A&B!%TEMP%"'])
            self.assertEqual(row['stderr'], 'done')
            self.assertEqual(row['returncode'], 0)

    def test_nonzero_exit_reports_stdout_stderr_and_unsafe_arguments_are_rejected(self):
        from shell_connector import execute_bat

        with tempfile.TemporaryDirectory(prefix='zizai-batch-error-') as scratch:
            path = Path(scratch) / 'error.bat'
            path.write_text('@echo off\necho expected-out\necho expected-error 1>&2\nexit /b 7\n',
                            encoding='ascii')
            with self.assertRaises(ValueError):
                execute_bat(path, args=['broken"argument'])
            with self.assertRaisesRegex(RuntimeError, r'終了コード 7[\s\S]*expected-out[\s\S]*expected-error'):
                execute_bat(path)
