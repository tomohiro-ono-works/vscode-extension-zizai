"""Real widget backend and magic wiring; not browser/native-dialog UI tests."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'apps/core/src'))
from zizai.forms import create_form, load_ipython_extension


class FormWidgetTests(unittest.TestCase):
    def make_form(self, picker=lambda current: 'C:/選択先'):
        form = create_form(folder_picker=picker)
        self.addCleanup(form.close)
        return form

    def select(self, form, action='export'):
        form.connector.value = 'csv'
        form.action.value = action

    def test_horizontal_form_passes_selection_and_folder_result_to_python(self):
        import ipywidgets as widgets
        form = self.make_form()
        self.assertIsInstance(form.toolbar, widgets.HBox)
        self.select(form, 'import')
        form.folder_buttons['folder'].click()
        form.generate_button.click()
        self.assertEqual(form.model.values['folder'], 'C:/選択先')
        self.assertEqual(form.result, '{csv.importのコードを生成}')
        self.assertIn('csv.import', form.generated.value)
        self.assertEqual(form.field_widgets['encoding'].value, 'utf-8')

    def test_regeneration_preserves_form_and_replaces_only_output(self):
        form = self.make_form()
        self.select(form)
        form.folder_buttons['folder'].click()
        form.generate_button.click()
        root, controls = form.root, form.details.children
        form.field_widgets['filename'].value = '変更.csv'
        self.assertEqual(form.generated.value, '')
        form.generate_button.click()
        self.assertIs(form.root, root)
        self.assertEqual(form.details.children, controls)
        self.assertEqual(form.result, '{csv.exportのコードを生成}')

    def test_cancel_keeps_folder_and_parent_changes_keep_or_clear_action(self):
        form = self.make_form(lambda current: '')
        self.select(form)
        form.field_widgets['folder'].value = 'C:/keep'
        form.folder_buttons['folder'].click()
        self.assertEqual(form.model.values['folder'], 'C:/keep')
        form.connector.value = 'excel'
        self.assertEqual(form.action.value, 'export')
        self.assertEqual(form.model.values['folder'], 'C:/keep')
        form.connector.value = 'csv'
        form.action.value = 'import'
        form.connector.value = 'excel'
        self.assertIsNone(form.action.value)
        self.assertTrue(form.generate_button.disabled)

    def test_invalid_visible_input_cannot_generate_using_previous_valid_value(self):
        form = self.make_form()
        self.select(form)
        form.field_widgets['folder'].value = 'C:/valid'
        form.generate_button.click()
        form.field_widgets['folder'].value = 'relative/path'
        self.assertTrue(form.generate_button.disabled)
        form.generate_button.click()
        self.assertEqual(form.generated.value, '')
        self.assertEqual(form.result, '')

    def test_output_is_escaped_text_not_executable_html(self):
        from zizai.form_definition import load_definition
        from zizai.forms import NotebookForm
        config = load_definition()
        config['output_template'] = '<img src=x onerror=bad()> {connector}.{action}'
        form = NotebookForm(config)
        self.addCleanup(form.close)
        self.select(form)
        form.field_widgets['folder'].value = 'C:/valid'
        form.generate_button.click()
        self.assertNotIn('<img', form.generated.value)
        self.assertIn('&lt;img', form.generated.value)

    def test_magic_registers_explicitly_and_does_not_replace_foreign_magic(self):
        from IPython.core.interactiveshell import InteractiveShell
        from traitlets.config import Config
        with tempfile.TemporaryDirectory(prefix='zizai-magic-') as directory:
            shell = InteractiveShell(ipython_dir=directory, config=Config({'HistoryManager': {'hist_file': ':memory:'}}))
            try:
                load_ipython_extension(shell)
                load_ipython_extension(shell)
                with patch('zizai.forms.show_form') as show:
                    shell.run_line_magic('form', '')
                    show.assert_called_once_with(None)
                    show.reset_mock()
                    shell.run_line_magic('form', '"C:/設定/form.yaml"')
                    show.assert_called_once_with('C:/設定/form.yaml')
                shell.register_magic_function(lambda line: None, magic_kind='line', magic_name='form')
                with self.assertRaises(ValueError):
                    load_ipython_extension(shell)
            finally:
                shell.history_manager.end_session()


if __name__ == '__main__':
    unittest.main()
