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
        form = create_form(Path(__file__).resolve().parents[3] / 'connectors', folder_picker=picker)
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
        self.assertIn('import csv_connector', form.result)
        self.assertIn('生成コード', form.generated.value)
        self.assertNotIn('仮表示', form.generated.value)
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
        self.assertIn('変更.csv', form.result)
        self.assertIn('data = df', form.result)
        self.assertIn('write_csv(data=data', form.result)

    def test_sql_and_python_use_only_files_in_the_form(self):
        for connector, action, folder, filename, call in (
            ('duckdb', 'execute_sql_file', 'sql_folder', 'sql_file_name', 'execute_sql_file'),
            ('bigquery', 'execute_sql_file', 'sql_folder', 'sql_file_name', 'execute_sql_file'),
            ('python', 'execute_python', 'folder', 'filename', 'execute_python_file'),
        ):
            with self.subTest(connector=connector):
                form = self.make_form()
                form.connector.value = connector
                form.action.value = action
                self.assertNotIn('sql', form.field_widgets)
                self.assertNotIn('script', form.field_widgets)
                self.assertNotIn('execute_sql', form.model.actions)
                if connector == 'duckdb':
                    form.folder_buttons['db_folder'].click()
                    form.field_widgets['db_file_name'].value = '商品.duckdb'
                if connector == 'bigquery':
                    form.field_widgets['project_id'].value = 'fixture-project'
                form.folder_buttons[folder].click()
                self.assertTrue(form.generate_button.disabled)
                form.field_widgets[filename].value = '試用.py' if connector == 'python' else '試用.sql'
                form.generate_button.click()
                self.assertIn(call + '(', form.result)

    def test_csv_encoding_and_delimiter_share_a_horizontal_row(self):
        import ipywidgets as widgets
        form = self.make_form()
        for action in ('import', 'export'):
            with self.subTest(action=action):
                self.select(form, action)
                row = next((child for child in form.details.children
                            if isinstance(child, widgets.HBox) and form.field_widgets['encoding'] in child.children), None)
                self.assertIsNotNone(row)
                self.assertEqual(row.children, (form.field_widgets['encoding'], form.field_widgets['delimiter']))

    def test_browse_button_is_beside_its_folder_field_and_keeps_picker_behavior(self):
        import ipywidgets as widgets
        from unittest.mock import Mock
        picker = Mock(return_value='C:/選択先')
        form = self.make_form(picker)
        for connector, action in (('csv', 'import'), ('csv', 'export'), ('excel', 'export')):
            with self.subTest(connector=connector, action=action):
                form.connector.value = connector
                form.action.value = action
                field = form.field_widgets['folder']
                field.value = 'C:/現在'
                button = form.folder_buttons['folder']
                self.assertEqual(button.description, '参照…')
                self.assertNotIn(button, form.toolbar.children)
                self.assertTrue(any(isinstance(row, widgets.HBox) and row.children == (field, button)
                                    for row in form.details.children))
                picker.reset_mock()
                button.click()
                picker.assert_called_once_with('C:/現在')
                self.assertEqual(field.value, 'C:/選択先')

    def test_csv_read_form_pairs_row_and_chunk_settings_without_date_control(self):
        import ipywidgets as widgets
        repo = Path(__file__).resolve().parents[3]
        definitions = (repo / 'connectors', repo / 'apps/core/src/zizai/forms.yaml')
        for definition in definitions:
            with self.subTest(definition=definition.name):
                form = create_form(definition, folder_picker=lambda current: 'C:/選択先')
                self.addCleanup(form.close)
                self.select(form, 'import')
                fields = form.field_widgets
                rows = [row.children for row in form.details.children if isinstance(row, widgets.HBox)]
                self.assertIn((fields['header_row'], fields['data_start_row']), rows)
                self.assertIn((fields['output_variable'], fields['chunk_size']), rows)
                self.assertNotIn('date_cleansing', fields)
                form.folder_buttons['folder'].click()
                fields['header_row'].value = 2
                fields['data_start_row'].value = 4
                fields['chunk_size'].value = 0
                self.assertFalse(form.generate_button.disabled)
                form.generate_button.click()
                if definition.is_dir():
                    for name, value in (('header_row', 2), ('data_start_row', 4), ('chunk_size', 0)):
                        self.assertIn(f'{name} = {value}', form.result)
                        self.assertIn(f'{name}={name}', form.result)
                    self.assertNotIn('date_cleansing', form.result)

    def test_native_folder_picker_sets_parent_topmost_before_opening_and_cleans_up(self):
        from unittest.mock import Mock, call
        from zizai.forms import _select_folder
        root = Mock()
        events = Mock()
        events.attach_mock(root, 'root')
        with patch('tkinter.Tk', return_value=root), patch('tkinter.filedialog.askdirectory', return_value='') as choose:
            events.attach_mock(choose, 'choose')
            self.assertEqual(_select_folder('C:/現在'), '')
        self.assertEqual(events.mock_calls, [call.root.withdraw(), call.root.attributes('-topmost', True),
                         call.root.update_idletasks(), call.choose(parent=root, title='フォルダーを選択', initialdir='C:/現在'),
                         call.root.destroy()])
        root.reset_mock()
        with patch('tkinter.Tk', return_value=root), patch('tkinter.filedialog.askdirectory', side_effect=RuntimeError('dialog failed')):
            with self.assertRaises(RuntimeError):
                _select_folder('C:/現在')
        root.destroy.assert_called_once_with()

    def test_sjis_can_be_selected_and_passed_to_generated_csv_calls(self):
        form = self.make_form()
        for action in ('import', 'export'):
            with self.subTest(action=action):
                self.select(form, action)
                form.folder_buttons['folder'].click()
                form.field_widgets['encoding'].value = 'sjis'
                form.generate_button.click()
                self.assertIn("encoding = 'sjis'", form.result)
                self.assertIn('encoding=encoding', form.result)
                if action == 'import':
                    self.assertIn('df = csv_connector.read_csv(', form.result)

    def test_copy_uses_exact_code_only_after_explicit_click_and_clears_on_edit(self):
        from unittest.mock import Mock
        from zizai.forms import NotebookForm
        from zizai.form_definition import load_definition
        copy = Mock()
        form = NotebookForm(load_definition(Path(__file__).resolve().parents[3] / 'connectors'),
                            folder_picker=lambda current: 'C:/選択先', clipboard_writer=copy)
        self.addCleanup(form.close)
        self.assertEqual(form.code_actions.children, (form.generate_button, form.copy_button))
        self.assertNotIn(form.generate_button, form.toolbar.children)
        self.assertTrue(form.copy_button.disabled)
        self.select(form, 'import')
        form.folder_buttons['folder'].click()
        form.generate_button.click()
        self.assertIn('<code', form.generated.value)
        self.assertFalse(form.copy_button.disabled)
        copy.assert_not_called()
        form.copy_button.click()
        copy.assert_called_once_with(form.result)
        form.field_widgets['filename'].value = '変更.csv'
        self.assertTrue(form.copy_button.disabled)
        form.copy_button.click()
        self.assertEqual(copy.call_count, 1)
        form.generate_button.click()
        copy.side_effect = RuntimeError('clipboard unavailable')
        form.copy_button.click()
        self.assertIn('コピーできません', form.message.value)
        self.assertNotIn('コードをコピーしました', form.message.value)

    def test_windows_copy_passes_code_as_data_to_persistent_system_clipboard(self):
        from zizai.forms import _copy_to_clipboard
        text = '日本語 = "$(not_a_command)"\n# 引用符と改行\n'
        with patch('sys.platform', 'win32'), patch('subprocess.run') as run, patch('tkinter.Tk') as tk:
            _copy_to_clipboard(text)
        run.assert_called_once()
        arguments, options = run.call_args
        self.assertNotIn(text, ' '.join(arguments[0]))
        self.assertEqual(options['input'], text)
        self.assertEqual(options['encoding'], 'utf-8')
        self.assertTrue(options['check'])
        self.assertFalse(options['shell'])
        tk.assert_not_called()

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

    def test_delayed_old_action_selection_cannot_error_or_select_new_action(self):
        from comm import get_comm_manager
        # A frontend selection can already be queued when the connector changes
        # (for example while the native folder chooser blocks the kernel).
        # An index from CSV can refer to an unrelated action in Excel.
        for old_index in (1, 2):
            with self.subTest(old_index=old_index):
                form = self.make_form()
                form.connector.value = 'csv'
                old_comm_id = form.action.comm.comm_id
                form.connector.value = 'excel'
                with self.assertNoLogs(form.action.log, level='WARNING'):
                    get_comm_manager().comm_msg(None, None, {
                        'content': {'comm_id': old_comm_id, 'data': {
                            'method': 'update', 'state': {'index': old_index},
                            'buffer_paths': []}}, 'buffers': []})
                self.assertIsNone(form.model.action)
                self.assertTrue(form.generate_button.disabled)
                # A fresh selection on the current form still works.
                export_index = next(index for index, (_, value) in enumerate(form.action.options) if value == 'export')
                get_comm_manager().comm_msg(None, None, {
                    'content': {'comm_id': form.action.comm.comm_id, 'data': {
                        'method': 'update', 'state': {'index': export_index},
                        'buffer_paths': []}}, 'buffers': []})
                self.assertEqual(form.model.action, 'export')

    def test_output_is_escaped_text_not_executable_html(self):
        from importlib.resources import files
        from zizai.form_definition import parse_definition
        from zizai.forms import NotebookForm
        config = parse_definition(files('zizai').joinpath('forms.yaml').read_text(encoding='utf-8'))
        config['output_template'] = '<img src=x onerror=bad()> {connector}.{action}'
        form = NotebookForm(config)
        self.addCleanup(form.close)
        form.connector.value = 'excel'
        form.action.value = 'export'
        form.field_widgets['folder'].value = 'C:/valid'
        form.generate_button.click()
        self.assertNotIn('<img', form.generated.value)
        self.assertIn('&lt;img', form.generated.value)

    def test_real_csv_code_escapes_html_in_path_and_blocks_bad_variable(self):
        form = self.make_form()
        self.select(form)
        form.field_widgets['folder'].value = 'C:/valid'
        form.field_widgets['filename'].value = '<img src=x onerror=bad()>.csv'
        form.generate_button.click()
        self.assertNotIn('<img', form.generated.value)
        self.assertIn('&lt;img', form.generated.value)
        form.field_widgets['input_variable'].value = 'df; injected()'
        self.assertTrue(form.generate_button.disabled)
        self.assertEqual(form.generated.value, '')
        self.assertIn('変数名', form.message.value)

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
