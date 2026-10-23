"""Exercise the actual package collection and hand-installed wheel boundary."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile


REPO = Path(__file__).resolve().parents[3]
RUNTIME = os.environ.get("ZIZAI_TEST_PYTHON", sys.executable)
PACKAGE_FILES = {
    "zizai/__init__.py",
    "zizai/core/__init__.py",
    "zizai/connectors/__init__.py",
}


class PackageDistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory(prefix="zizai-003 ")
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.root = Path(cls.scratch.name)
        cls.source = cls.root / "source"
        cls.outside = cls.root / "Notebook 別 cwd"
        cls.outside.mkdir()
        cls.built_wheel = None

    def run_process(self, arguments, *, cwd=None):
        result = subprocess.run(
            arguments, cwd=cwd or self.outside,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])
        return result.stdout

    def build(self, source, hook, output):
        output.mkdir(exist_ok=True)
        self.run_process(
            [sys.executable, "-I", "-c",
             "import sys; from setuptools import build_meta; "
             "getattr(build_meta, sys.argv[1])(sys.argv[2])",
             hook, str(output)],
            cwd=source,
        )

    def wheel(self):
        self.assertTrue((REPO / "pyproject.toml").is_file(), "Python package declaration is missing")
        cls = type(self)
        if cls.built_wheel is None:
            self.source.mkdir()
            shutil.copy2(REPO / "pyproject.toml", self.source)
            shutil.copy2(REPO / "README.md", self.source)
            shutil.copytree(
                REPO / "apps", self.source / "apps",
                ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"),
            )
            unrelated = self.source / "apps" / "extension" / "unrelated.py"
            unrelated.parent.mkdir(parents=True, exist_ok=True)
            unrelated.write_text("raise RuntimeError('not a Python package asset')\n")
            (self.source / "private-input.csv").write_text("private fixture\n")
            output = self.root / "wheel"
            self.build(self.source, "build_wheel", output)
            wheels = list(output.glob("*.whl"))
            self.assertEqual(len(wheels), 1)
            cls.built_wheel = wheels[0]
        return cls.built_wheel

    def fresh_python(self):
        target = Path(tempfile.mkdtemp(prefix="導入先 空白 ", dir=self.root)) / "venv"
        self.run_process([RUNTIME, "-I", "-m", "venv", "--without-pip", str(target)])
        return target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    def install(self, python, wheel):
        self.run_process([
            sys.executable, "-I", "-m", "pip", "--isolated",
            "--disable-pip-version-check", "--no-cache-dir", "--python", str(python),
            "install", "--no-index", "--no-deps", "--no-compile", str(wheel),
        ])

    def probe(self, python, code):
        return json.loads(self.run_process([str(python), "-I", "-c", code]))

    def assert_package_contents(self, wheel):
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
        payload = {name for name in names if ".dist-info/" not in name}
        self.assertEqual(payload, PACKAGE_FILES)
        self.assertEqual(len([n for n in names if n.endswith(".dist-info/METADATA")]), 1)

    def test_wheel_contains_both_source_roots_without_unrelated_assets(self):
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
print(json.dumps({
    "names": [module.__name__ for module in modules],
    "installed": [pathlib.Path(module.__file__).is_relative_to(sys.prefix) for module in modules],
    "distribution": importlib.metadata.distribution("zizai-runtime").metadata["Name"],
}))
""")
        self.assertEqual(installed, {
            "names": ["zizai", "zizai.core", "zizai.connectors"],
            "installed": [True, True, True], "distribution": "zizai-runtime",
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
print(json.dumps({"imports": [zizai.__name__, zizai.core.__name__, zizai.connectors.__name__]}))
""")
        self.assertEqual(result, {"imports": ["zizai", "zizai.core", "zizai.connectors"]})


if __name__ == "__main__":
    unittest.main()
