"""Exercise the actual package collection and hand-installed wheel boundary."""

import json
import shutil
import sys
import tarfile
import unittest
import zipfile
from email.parser import Parser

from package_test_support import PackageArtifactTestCase


class PackageDistributionTests(PackageArtifactTestCase):
    def test_new_connector_form_is_packaged_by_folder_name(self):
        self.wheel()
        source = self.root / 'extended-source'
        shutil.copytree(self.source, source, ignore=shutil.ignore_patterns('build', '*.egg-info'))
        support = source / 'connectors' / 'example' / 'form'
        support.mkdir(parents=True)
        (support / '__init__.py').write_text(
            "GENERATION_FIELDS = {'example.run': {'text'}}\n"
            "MAGIC_NAME = 'zizai_example'\n"
            "def generate(kind, values, module_path):\n"
            "    return 'import example_connector\\nresult = ' + repr(values['text'])\n",
            encoding='utf-8',
        )
        catalog = source / 'connectors'
        (catalog / 'example/example_connector.py').write_text(
            "raise AssertionError('connector executed while generating code')\n", encoding='utf-8')
        (catalog / 'example/example_definition.yaml').write_text('''version: 1
output_template: "{connector}.{action}"
connectors:
  example:
    label: Example
    module_file: example_connector.py
    actions:
      run:
        label: Run
        generation: example.run
        fields:
          text: {label: Text, type: text, default: sample}
''', encoding='utf-8')
        output = self.root / 'extended-wheel'
        self.build(source, 'build_wheel', output)
        with zipfile.ZipFile(next(output.glob('*.whl'))) as archive:
            self.assertIn('zizai/connector_forms/example/__init__.py', archive.namelist())
            name = next(name for name in archive.namelist() if name.endswith('.dist-info/entry_points.txt'))
            self.assertIn('example = zizai.connector_forms.example', archive.read(name).decode('utf-8'))
            installed = self.root / 'extended-install'
            archive.extractall(installed)
        result = self.run_process([sys.executable, '-I', '-B', '-c', '''
import json, os, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
from IPython.core.interactiveshell import InteractiveShell
from traitlets.config import Config
from zizai.connectors import configure_connectors
from zizai.forms import create_form, load_ipython_extension

site = Path(sys.argv[3])
settings = {'ZIZAI_CONFIG_FILE': str(site / 'zizai-connectors.json'), 'ZIZAI_CONNECTORS_DIR': ''}
with patch.dict(os.environ, settings), patch('zizai.core.connector_config._site_packages', return_value=site):
    configure_connectors(sys.argv[2], enabled_connectors=['example'])
    form = create_form(connector='example')
    form.action.value = 'run'
    form.generate_button.click()
    shell = InteractiveShell(ipython_dir=str(site), config=Config({'HistoryManager': {'hist_file': ':memory:'}}))
    try:
        load_ipython_extension(shell)
        print(json.dumps({'connectors': list(form.model.definition['connectors']), 'code': form.result,
                          'magic': shell.find_line_magic('zizai_example') is not None,
                          'executed': 'example_connector' in sys.modules}))
    finally:
        shell.history_manager.end_session()
        form.close()
''', str(installed), str(catalog), str(self.root / 'example-site')])
        self.assertEqual(json.loads(result), {
            'connectors': ['example'], 'code': "import example_connector\nresult = 'sample'",
            'magic': True, 'executed': False,
        })

    def test_form_dependencies_are_optional_and_default_install_does_not_load_ui(self):
        with zipfile.ZipFile(self.wheel()) as archive:
            name = next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))
            metadata = Parser().parsestr(archive.read(name).decode('utf-8'))
        requirements = metadata.get_all('Requires-Dist')
        self.assertEqual(len(requirements), 31)
        forms = [item for item in requirements if 'extra == "forms"' in item]
        csv = [item for item in requirements if 'extra == "csv"' in item]
        python_extra = [item for item in requirements if 'extra == "python"' in item]
        shell = [item for item in requirements if 'extra == "shell"' in item]
        windows = [item for item in requirements if 'extra == "windows"' in item]
        dataintegration = [item for item in requirements if 'extra == "dataintegration"' in item]
        bigquery = [item for item in requirements if 'extra == "bigquery"' in item]
        duckdb = [item for item in requirements if 'extra == "duckdb"' in item]
        excel = [item for item in requirements if 'extra == "excel"' in item]
        fulltext = [item for item in requirements if 'extra == "fulltext-search"' in item]
        vector = [item for item in requirements if 'extra == "vector"' in item]
        self.assertEqual(len(forms), 2)
        self.assertEqual(len(csv), 2)
        self.assertTrue(any(item.startswith('pandas==3.1.1') for item in csv))
        self.assertTrue(any(item.startswith('numpy==2.5.4') for item in csv))
        self.assertEqual({item.split(';')[0].strip() for item in python_extra}, {
            'pandas==3.1.1', 'numpy==2.5.4',
        })
        self.assertEqual({item.split(';')[0].strip() for item in shell}, {
            'pandas==3.1.1', 'numpy==2.5.4',
        })
        self.assertEqual({item.split(';')[0].strip() for item in windows}, {
            'pandas==3.1.1', 'numpy==2.5.4',
        })
        self.assertEqual({item.split(';')[0].strip() for item in dataintegration}, {
            'pandas==3.1.1', 'numpy==2.5.4',
        })
        self.assertEqual({item.split(';')[0].strip() for item in bigquery}, {
            'google-cloud-bigquery[pandas]==3.47.0', 'pandas==3.1.1', 'numpy==2.5.4', 'pyarrow==26.0.1',
        })
        self.assertEqual({item.split(';')[0].strip() for item in duckdb}, {
            'duckdb==2.0.0', 'pandas==3.1.1', 'numpy==2.5.4',
        })
        self.assertEqual({item.split(';')[0].strip() for item in excel}, {
            'pandas==3.1.1', 'numpy==2.5.4', 'openpyxl==3.1.5', 'defusedxml==0.7.1',
        })
        self.assertEqual({item.split(';')[0].strip() for item in fulltext}, {
            'pandas==3.1.1', 'numpy==2.5.4',
        })
        self.assertEqual({item.split(';')[0].strip() for item in vector}, {
            'duckdb==2.0.0', 'pandas==3.1.1', 'numpy==2.5.4', 'sentence-transformers==6.3.0',
            'torch==2.15.0', 'transformers==5.23.0',
        })
        python = self.fresh_python()
        self.install(python, self.wheel())
        result = self.probe(python, '''
import json, sys
import zizai, zizai.forms
print(json.dumps({'loaded': sorted(set(sys.modules) & {'ipywidgets', 'yaml', 'tkinter', 'pandas', 'numpy',
                                                      'openpyxl', 'defusedxml', 'duckdb', 'google', 'pyarrow',
                                                      'sentence_transformers', 'torch', 'transformers'})}))
''')
        self.assertEqual(result, {'loaded': []})

    def test_wheel_contains_the_runtime_without_unrelated_assets(self):
        # A missing connectors mapping or broad package discovery breaks this boundary.
        self.assert_package_contents(self.wheel())

    def test_hand_installation_enables_imports_without_source_paths(self):
        # Source-tree import tricks cannot satisfy this isolated before/after check.
        wheel = self.wheel()
        python = self.fresh_python()
        missing = self.probe(python, """
import json
try:
    import zizai
except ModuleNotFoundError as exc:
    print(json.dumps({"missing": exc.name}))
else:
    print(json.dumps({"missing": None}))
""")
        self.assertEqual(missing, {"missing": "zizai"})
        self.install(python, wheel)
        installed = self.probe(python, """
import importlib.metadata, json, pathlib, sys
import zizai, zizai.core, zizai.connectors
modules = (zizai, zizai.core, zizai.connectors)
widgets = pathlib.Path(sys.prefix) / 'share/jupyter/nbextensions/zizai-row-preview'
print(json.dumps({
    "names": [module.__name__ for module in modules],
    "installed": [pathlib.Path(module.__file__).is_relative_to(sys.prefix) for module in modules],
    "distribution": importlib.metadata.distribution("zizai-runtime").metadata["Name"],
    "widget_files": sorted(path.name for path in widgets.iterdir()),
}))
""")
        self.assertEqual(installed, {
            "names": ["zizai", "zizai.core", "zizai.connectors"],
            "installed": [True, True, True], "distribution": "zizai-runtime",
            "widget_files": ["extension.js", "index.js"],
        })

    def test_package_imports_do_not_require_optional_sdks(self):
        # Adding an eager SDK import or eager connector export must fail here.
        python = self.fresh_python()
        self.install(python, self.wheel())
        result = self.probe(python, """
import importlib.abc, json, sys
blocked = {"pandas", "numpy", "openpyxl", "duckdb", "google"}
class RejectSdk(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in blocked:
            raise AssertionError("Unexpected SDK import: " + fullname)
sys.meta_path.insert(0, RejectSdk())
import zizai, zizai.core, zizai.connectors
print(json.dumps({"eager_connectors": [name for name in sys.modules if name.startswith("zizai.connectors.")]}))
""")
        self.assertEqual(result, {"eager_connectors": []})

    def test_import_preserves_cwd_environment_and_search_path(self):
        # Import-time environment repair or path insertion is outside the contract.
        python = self.fresh_python()
        self.install(python, self.wheel())
        result = self.probe(python, """
import json, os, sys
before = (os.getcwd(), dict(os.environ), list(sys.path))
import zizai, zizai.core, zizai.connectors
after = (os.getcwd(), dict(os.environ), list(sys.path))
print(json.dumps({"unchanged": before == after}))
""")
        self.assertEqual(result, {"unchanged": True})

    def test_sdist_rebuild_preserves_split_package_imports(self):
        # A package omitted from SOURCES can work in checkout but fail after release build.
        self.wheel()
        output = self.root / "sdist"
        self.build(self.source, "build_sdist", output)
        archives = list(output.glob("*.tar.gz"))
        self.assertEqual(len(archives), 1)
        unpacked = self.root / "unpacked"
        unpacked.mkdir()
        with tarfile.open(archives[0]) as archive:
            archive.extractall(unpacked, filter="data")
        roots = list(unpacked.iterdir())
        self.assertEqual(len(roots), 1)
        rebuilt = self.root / "rebuilt"
        self.build(roots[0], "build_wheel", rebuilt)
        wheels = list(rebuilt.glob("*.whl"))
        self.assertEqual(len(wheels), 1)
        self.assert_package_contents(wheels[0])
        python = self.fresh_python()
        self.install(python, wheels[0])
        result = self.probe(python, """
import json, zizai, zizai.core, zizai.connectors
from zizai.arithmetic_formula import ArithmeticFormula
from zizai.connector_forms.csv.csv_codegen import generate_csv
print(json.dumps({
    "imports": [zizai.__name__, zizai.core.__name__, zizai.connectors.__name__],
    "codegen": generate_csv.__module__,
    "formula": ArithmeticFormula.__module__,
}))
""")
        self.assertEqual(result, {
            "imports": ["zizai", "zizai.core", "zizai.connectors"],
            "codegen": "zizai.connector_forms.csv.csv_codegen",
            "formula": "zizai.connector_forms.dataintegration.arithmetic_formula",
        })


if __name__ == "__main__":
    unittest.main()
