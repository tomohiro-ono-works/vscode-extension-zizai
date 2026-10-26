"""Check the manual notebook's diagnostic code against an installed real wheel."""

import hashlib
import json
import unittest
import zipfile

from package_test_support import PackageArtifactTestCase, REPO


class NotebookHandoffTests(PackageArtifactTestCase):
    def notebook(self):
        path = REPO / "tests" / "manual" / "TASK-003-05-python.ipynb"
        self.assertTrue(path.is_file(), "Kernel handoff notebook is missing")
        return json.loads(path.read_text(encoding="utf-8"))

    def execution_script(self, *cell_ids):
        cells = {cell["id"]: cell for cell in self.notebook()["cells"]}
        sources = ["".join(cells[cell_id]["source"]) for cell_id in cell_ids]
        return (
            "import contextlib, io, json\nnamespace = {}\n"
            "with contextlib.redirect_stdout(io.StringIO()):\n"
            f"    for source in {sources!r}:\n"
            "        exec(compile(source, '<manual notebook>', 'exec'), namespace)\n"
            "print(json.dumps({key: namespace.get(key) for key in "
            "('report_before_restart', 'report_after_restart')}))\n"
        )

    def test_notebook_is_unexecuted_and_uses_a_standard_kernel(self):
        notebook = self.notebook()
        self.assertEqual(notebook["nbformat"], 4)
        self.assertEqual(notebook["metadata"]["kernelspec"]["name"], "python3")
        ids = [cell["id"] for cell in notebook["cells"]]
        self.assertEqual(len(ids), len(set(ids)))
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                self.assertEqual(cell["outputs"], [])
                self.assertIsNone(cell["execution_count"])
                compile("".join(cell["source"]), "<manual notebook>", "exec")

    def test_diagnostic_matches_the_wheel_without_exposing_local_paths(self):
        # Wrong package resolution or accidental raw path reporting breaks this handoff.
        script = self.execution_script("report-helper", "before-restart")
        python = self.fresh_python()
        wheel = self.wheel()
        self.install(python, wheel)
        report = self.probe(python, script)["report_before_restart"]
        self.assertEqual(report["scope"], "minimal_package_import")
        self.assertEqual(report["phase"], "before_restart")
        self.assertEqual(report["distribution"]["name"], "zizai-runtime")
        self.assertEqual(report["distribution"]["version"], "0.0.0.dev0")
        self.assertEqual(report["distribution"]["runtime_dependency_count"], 0)
        self.assertTrue(report["checks"]["imports_match_distribution"])
        self.assertTrue(report["checks"]["import_preserved_process_state"])
        with zipfile.ZipFile(wheel) as archive:
            expected = {
                name: hashlib.sha256(archive.read(path)).hexdigest()
                for name, path in [
                    ("zizai", "zizai/__init__.py"),
                    ("zizai.core", "zizai/core/__init__.py"),
                    ("zizai.connectors", "zizai/connectors/__init__.py"),
                ]
            }
        self.assertEqual({item["module"]: item["sha256"] for item in report["files"]}, expected)
        self.assertNotIn(str(self.root), json.dumps(report))

    def test_restart_check_distinguishes_current_and_fresh_processes(self):
        # Re-running in the same session must not be reported as a fresh kernel session.
        same_session = self.execution_script("report-helper", "before-restart", "after-restart")
        fresh_session = self.execution_script("report-helper", "after-restart")
        python = self.fresh_python()
        self.install(python, self.wheel())
        same = self.probe(python, same_session)["report_after_restart"]
        fresh = self.probe(python, fresh_session)["report_after_restart"]
        self.assertFalse(same["checks"]["previous_session_marker_absent"])
        self.assertTrue(fresh["checks"]["previous_session_marker_absent"])
        self.assertTrue(fresh["checks"]["imports_match_distribution"])

    def test_diagnostic_detects_packages_shadowed_by_notebook_cwd(self):
        # A same-named source tree must not masquerade as the hand-installed wheel.
        script = self.execution_script("report-helper", "before-restart")
        python = self.fresh_python()
        wheel = self.wheel()
        self.install(python, wheel)
        shadow = self.root / "shadow"
        shadow.mkdir()
        with zipfile.ZipFile(wheel) as archive:
            for name in ["zizai/__init__.py", "zizai/core/__init__.py", "zizai/connectors/__init__.py"]:
                path = shadow / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.read(name))
        result = json.loads(self.run_process([str(python), "-c", script], cwd=shadow))
        self.assertFalse(result["report_before_restart"]["checks"]["imports_match_distribution"])


if __name__ == "__main__":
    unittest.main()
