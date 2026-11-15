"""Shared external connectors, local bytecode, and no generation-time import."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import source_test_support
from zizai.form_definition import load_definition
from zizai.form_model import FormModel


class ExternalConnectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='zizai-external-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.catalog = self.directory / 'shared'
        shutil.copytree(source_test_support.REPO / 'connectors', self.catalog)
        self.config = self.directory / 'user-settings.json'
        self.old_prefix = sys.pycache_prefix
        self.addCleanup(setattr, sys, 'pycache_prefix', self.old_prefix)
        sys.pycache_prefix = str(self.directory / 'local-cache')

    def test_yaml_and_generation_do_not_execute_connector(self):
        marker = self.directory / 'imported.txt'
        module = self.catalog / 'csv/csv_connector.py'
        module.write_text(f'from pathlib import Path\nPath({str(marker)!r}).touch()\n', encoding='utf-8')
        model = FormModel(load_definition(self.catalog))
        model.set_connector('csv')
        model.set_action('import')
        model.set_value('folder', str(self.directory))
        code = model.generate()
        self.assertIn('import csv_connector', code)
        self.assertNotIn(str(module), code)
        self.assertFalse(marker.exists())
        self.assertFalse(list(self.catalog.rglob('__pycache__')))

    def test_environment_can_override_persisted_directory(self):
        from zizai.core.connector_config import get_connector_directory
        self.config.write_text(json.dumps({'connectors_directory': str(self.catalog)}), encoding='utf-8')
        other = self.directory / 'another'
        other.mkdir()
        with patch.dict(os.environ, {'ZIZAI_CONFIG_FILE': str(self.config), 'ZIZAI_CONNECTORS_DIR': str(other)}):
            self.assertEqual(get_connector_directory(), other)

    def test_module_file_cannot_escape_definition_directory(self):
        definition = self.catalog / 'csv/csv_definition.yaml'
        original = definition.read_text(encoding='utf-8')
        for bad in ('../outside.py', '/outside.py', 'not_python.txt'):
            definition.write_text(original.replace('csv_connector.py', bad), encoding='utf-8')
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                load_definition(self.catalog)

    def test_no_configuration_keeps_preview_explicit(self):
        with patch.dict(os.environ, {'ZIZAI_CONFIG_FILE': str(self.config), 'ZIZAI_CONNECTORS_DIR': ''}):
            model = FormModel(load_definition())
            model.set_connector('csv')
            model.set_action('import')
            model.set_value('folder', str(self.directory))
            self.assertTrue(model.is_placeholder)
            self.assertEqual(model.generate(), '{csv.importのコードを生成}')
