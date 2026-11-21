"""Exercise the Windows file actions through the normal form generator."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

import source_test_support
from zizai.form_definition import load_definition
from zizai.form_model import FormModel


class WindowsFileActionsTests(unittest.TestCase):
    def setUp(self):
        shared = source_test_support.REPO / 'connectors'
        self.model = FormModel(load_definition(shared))
        self.model.set_connector('windows')
        self.enterContext(patch.object(sys, 'path', [str(shared / 'windows'), *sys.path]))
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def generate(self, action, **values):
        self.model.set_action(action)
        for name, value in values.items():
            self.model.set_value(name, value)
        return self.model.generate()

    def execute(self, code, result_name):
        namespace = {}
        exec(compile(code, '<generated-windows>', 'exec'), namespace)
        return namespace[result_name]

    def test_name_and_content_search_return_matching_files_and_context(self):
        nested = self.root / 'sub'
        nested.mkdir()
        (nested / '売上_11.txt').write_text('前\n合計 120\n次\n', encoding='cp932')
        (self.root / '売上_11.csv').write_text('合計 900\n', encoding='utf-8')
        (self.root / '資料.txt').write_text('合計 100\n', encoding='utf-8')
        fields = dict(root_folder=str(self.root), file_name_pattern='^売上_', file_extension_pattern=r'^txt$')
        self.assertTrue(self.execute(self.generate('search_files_by_name', **fields), 'df').empty)
        fields['recursive'] = True
        names = self.execute(self.generate('search_files_by_name', **fields), 'df')
        self.assertEqual(names['file_name'].tolist(), ['売上_11.txt'])
        self.assertEqual(Path(names.iloc[0]['folder_path']), nested)
        code = self.generate('search_text_in_files', content_pattern=r'合計 \d+', context_lines=1, **fields)
        matches = self.execute(code, 'df')
        self.assertEqual(matches[['line_number', 'matched_line', 'context_excerpt']].values.tolist(),
                         [[2, '合計 120', '前\n合計 120\n次']])

    def test_markdown_generation_does_not_write_and_existing_files_are_protected(self):
        target = self.root / '試用.md'
        code = self.generate('create_markdown_file', folder=str(self.root), filename='試用', content='# はじめ\n')
        self.assertFalse(target.exists())
        self.assertEqual(self.execute(code, 'result').iloc[0]['target'], target.as_posix())
        with self.assertRaises(FileExistsError):
            self.execute(code, 'result')
        content = '追記\n'
        code = self.generate('create_markdown_file', write_mode='追記', content=content)
        self.execute(code, 'result')
        self.assertEqual(target.read_text(encoding='utf-8'), '# はじめ\n追記\n')
        code = self.generate('create_markdown_file', write_mode='上書き', content='置換')
        self.execute(code, 'result')
        self.assertEqual(target.read_text(encoding='utf-8'), '置換')

    def test_move_rejects_collisions_and_preserves_sources_until_execution(self):
        source = self.root / '元.txt'
        source.write_bytes(b'source')
        target = self.root / '先.txt'
        target.write_bytes(b'existing')
        code = self.generate('rename_and_move_file', source_file_path=str(source), destination_file_name=target.name)
        self.assertEqual(source.read_bytes(), b'source')
        with self.assertRaises(FileExistsError):
            self.execute(code, 'result')
        self.assertEqual(target.read_bytes(), b'existing')
        self.assertEqual(source.read_bytes(), b'source')
        destination = self.root / 'sub'
        code = self.generate('rename_and_move_file', destination_folder=str(destination))
        self.assertFalse(destination.exists())
        row = self.execute(code, 'result').iloc[0]
        self.assertEqual(Path(row['target']), destination / target.name)
        self.assertEqual((destination / target.name).read_bytes(), b'source')
        self.assertFalse(source.exists())
        code = self.generate('rename_and_move_file', allow_missing_source=True)
        self.assertEqual(self.execute(code, 'result').iloc[0]['status'], 'skipped')

    def test_action_switch_uses_new_default_but_keeps_a_user_entered_output_name(self):
        self.model.set_action('search_files_by_name')
        self.assertEqual(self.model.values['output_variable'], 'df')
        self.model.set_action('create_markdown_file')
        self.assertEqual(self.model.values['output_variable'], 'result')
        self.model.set_value('output_variable', 'my_result')
        self.model.set_action('search_text_in_files')
        self.assertEqual(self.model.values['output_variable'], 'my_result')
