"""Standard Python imports after one-time environment registration."""
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from unittest.mock import patch

import source_test_support
from zizai.connectors import configure_connectors
from zizai.form_definition import load_definition
from zizai.form_model import FormModel


class ConnectorImportRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='zizai-import-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.shared=self.root/'shared'
        shutil.copytree(source_test_support.REPO/'connectors',self.shared)
        self.site=self.root/'site-packages'
        self.site.mkdir()
        self.env={'ZIZAI_CONFIG_FILE':str(self.root/'settings.json'),
                  'ZIZAI_CONNECTORS_DIR':'','LOCALAPPDATA':str(self.root/'local')}

    def register(self):
        with patch.dict(os.environ,self.env), patch('zizai.core.connector_config._site_packages',return_value=self.site,create=True):
            configure_connectors(self.shared)

    def test_generated_code_uses_ordinary_import_without_module_path(self):
        model=FormModel(load_definition(self.shared))
        model.set_connector('csv');model.set_action('import')
        model.set_value('file_path',str(self.root / 'input.csv'))
        code=model.generate()
        self.assertIsInstance(ast.parse(code).body[0],ast.Import)
        self.assertIn('import csv_connector',code)
        self.assertNotIn('load_connector',code)
        self.assertNotIn(str(self.shared),code)

    def test_registered_import_works_in_two_projects_without_tool_bootstrap(self):
        self.register()
        pth=self.site/'zizai-connectors.pth'
        self.assertTrue(pth.is_file())
        # Isolate this fake site directory from an already registered real env.
        # Dependencies still come from the interpreter's installed site-packages.
        source='''import site,sys,json
sys.path.append(sys.argv[3])
site.addsitedir(sys.argv[1])
sys.path.insert(0,sys.argv[2])
import csv_connector
print(json.dumps({'file':csv_connector.__file__,'cache':sys.pycache_prefix}))
'''
        for project_name in ('analysis-a','analysis-b'):
            project=self.root/project_name;project.mkdir()
            proc=subprocess.run([sys.executable,'-S','-X','utf8','-c',source,str(self.site),
                str(source_test_support.REPO/'apps/core/src'),sysconfig.get_path('purelib')],cwd=project,
                env={**os.environ,**self.env},capture_output=True,text=True,encoding='utf-8',check=True)
            data=json.loads(proc.stdout)
            self.assertEqual(Path(data['file']).resolve(),(self.shared/'csv/csv_connector.py').resolve())
            self.assertTrue(Path(data['cache']).is_relative_to(self.root/'local'))
            self.assertEqual(list(project.iterdir()),[])
        self.assertFalse(list(self.shared.rglob('__pycache__')))
        self.assertTrue(list((self.root/'local').rglob('csv_connector*.pyc')))

    def test_registration_does_not_execute_connector_and_preserves_unowned_pth(self):
        marker=self.root/'executed'
        (self.shared/'csv/csv_connector.py').write_text(f'from pathlib import Path\nPath({str(marker)!r}).touch()\n',encoding='utf-8')
        (self.root/'settings.json').write_text('{"other":"keep"}',encoding='utf-8')
        self.register()
        self.assertEqual(json.loads((self.root/'settings.json').read_text(encoding='utf-8'))['other'],'keep')
        self.assertFalse(marker.exists())
        other=self.site/'zizai-connectors.pth'
        other.write_text('# user owned\n',encoding='utf-8')
        with self.assertRaises(FileExistsError):
            self.register()
        self.assertEqual(other.read_text(encoding='utf-8'),'# user owned\n')

    def test_registration_move_replaces_search_paths_and_default_settings_are_environment_scoped(self):
        self.register()
        moved=self.root/'moved';shutil.move(self.shared,moved)
        with patch.dict(os.environ,self.env),patch('zizai.core.connector_config._site_packages',return_value=self.site,create=True):
            configure_connectors(moved)
        text=(self.site/'zizai-connectors.pth').read_text(encoding='utf-8')
        self.assertNotIn(str(self.shared),text)
        self.assertIn(str((moved/'csv').resolve()),text)
        from zizai.core.connector_config import _settings_path
        with patch.dict(os.environ,{'ZIZAI_CONFIG_FILE':''}),patch('zizai.core.connector_config._site_packages',return_value=self.site,create=True):
            self.assertEqual(_settings_path(),self.site/'zizai-connectors.json')
