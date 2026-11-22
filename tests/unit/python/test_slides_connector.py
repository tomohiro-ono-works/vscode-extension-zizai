"""Form and connector boundaries for Markdown slide conversion."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

from zizai.forms import create_form


CONNECTORS = Path(__file__).resolve().parents[3] / 'connectors'


class SlidesConnectorTests(unittest.TestCase):
    def test_toggle_keeps_drafts_and_generates_only_the_chosen_input(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        form = create_form(CONNECTORS, connector='slides')
        self.addCleanup(form.close)
        form.action.value = 'markdown_to_pptx'
        fields = form.field_widgets
        fields['output_folder'].value = str(root)
        fields['markdown_text'].value = '# Draft\n'
        fields['markdown_file'].value = 'relative.md'
        self.assertFalse(form.generate_button.disabled)
        form.generate_button.click()
        self.assertIn('markdown_text =', form.result)
        self.assertNotIn('markdown_file =', form.result)

        fields['input_mode'].value = 'file'
        self.assertEqual(fields['markdown_text'].layout.display, 'none')
        self.assertTrue(form.generate_button.disabled)
        fields['markdown_file'].value = str(root / 'slides.md')
        fields['style_path'].value = str(root / 'custom.css')
        form.generate_button.click()
        self.assertIn('markdown_file =', form.result)
        self.assertNotIn('markdown_text =', form.result)
        self.assertIn('custom.css', form.result)
        compile(form.result, '<generated>', 'exec')
        fields['input_mode'].value = 'text'
        self.assertEqual(fields['markdown_text'].value, '# Draft\n')

    def test_calls_upstream_editable_engine_and_protects_existing_file(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch.object(sys, 'path', [str(CONNECTORS / 'slides'), *sys.path]))
        from slides_connector import markdown_to_pptx

        def output(source, destination, **kwargs):
            Path(destination).write_bytes(b'pptx fixture')

        file_convert = Mock(side_effect=output)
        text_convert = Mock(side_effect=output)
        engine = SimpleNamespace(convert=file_convert, convert_text=text_convert)
        with patch.dict(sys.modules, zizai_slides=engine):
            first = root / 'from text.pptx'
            self.assertEqual(markdown_to_pptx(first, markdown_text='# Text'), first.as_posix())
            self.assertEqual(text_convert.call_args.kwargs, {'mode': 'editable', 'style_path': None})
            second = root / 'from file.pptx'
            file_input = root / 'deck.md'
            style = root / 'deck custom.css'
            markdown_to_pptx(second, markdown_file=file_input, style_path=style)
            self.assertEqual(file_convert.call_args.args[0], file_input)
            self.assertEqual(file_convert.call_args.kwargs, {'mode': 'editable', 'style_path': style})
            with self.assertRaises(FileExistsError):
                markdown_to_pptx(first, markdown_text='# Replace')
            self.assertEqual(first.read_bytes(), b'pptx fixture')
            file_convert.assert_called_once()
            text_convert.assert_called_once()
