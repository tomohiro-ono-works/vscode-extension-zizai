"""Test-only tools for building and installing the actual Python package."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
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


class PackageArtifactTestCase(unittest.TestCase):
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
