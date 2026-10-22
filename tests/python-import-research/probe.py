"""TASK-003-01 PROTOTYPE: ordinary Python imports, not a Jupyter/VS Code test."""

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile


FIXTURES = {
    "root_a": {
        "zizai_import_probe_00301/__init__.py": "origin = 'source-a'\n",
        "zizai_import_probe_00301/dependency.py": "import zizai_missing_dependency_00301\n",
        "zizai_import_probe_00301/operation.py": "def fail():\n    raise ValueError('prototype failure')\n",
    },
    "root_b": {"zizai_import_probe_00301/__init__.py": "origin = 'source-b'\n"},
}

CASES = [
    ("I1", "no search path", "import zizai_import_probe_00301", None, 1, "ModuleNotFoundError", "zizai_import_probe_00301"),
    ("I2", "absolute sys.path from another cwd", "import sys; sys.path.insert(0, {root_a!r}); import zizai_import_probe_00301 as p; print(p.origin)", None, 0, None, "source-a\n"),
    ("I3", "PYTHONPATH before process start", "import zizai_import_probe_00301 as p; print(p.origin)", "root_a", 0, None, "source-a\n"),
    ("I4", "PYTHONPATH changed after process start", "import os; os.environ['PYTHONPATH'] = {root_a!r}; import zizai_import_probe_00301", None, 1, "ModuleNotFoundError", "zizai_import_probe_00301"),
    ("I5", "cached module survives search path change", "import sys; sys.path.insert(0, {root_a!r}); import zizai_import_probe_00301 as p; sys.path.insert(0, {root_b!r}); import zizai_import_probe_00301 as q; print(q.origin); print(p is q)", None, 0, None, "source-a\nTrue\n"),
    ("I6", "fresh process loads the other root", "import zizai_import_probe_00301 as p; print(p.origin)", "root_b", 0, None, "source-b\n"),
    ("I7", "dependency missing", "import sys; sys.path.insert(0, {root_a!r}); import zizai_import_probe_00301.dependency", None, 1, "ModuleNotFoundError", "zizai_missing_dependency_00301"),
    ("I8", "operation raises ordinary Python error", "import sys; sys.path.insert(0, {root_a!r}); from zizai_import_probe_00301.operation import fail; fail()", None, 1, "ValueError", "prototype failure"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    results = []
    with tempfile.TemporaryDirectory(prefix="zizai-import-research-") as tmp:
        base = Path(tmp)
        roots = {"root_a": str(base / "任意 展開先 A" / "lib"), "root_b": str(base / "別の 展開先 B" / "lib")}
        cwd = base / "Notebook 側"
        cwd.mkdir()
        for root, files in FIXTURES.items():
            for name, source in files.items():
                file = Path(roots[root]) / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(source, encoding="utf-8")
        for case_id, label, template, env_root, expected_exit, error_type, expected_text in CASES:
            env = os.environ.copy()
            if env_root:
                env["PYTHONPATH"] = roots[env_root] + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
            run = subprocess.run(
                [sys.executable, "-B", "-c", template.format(**roots)],
                cwd=cwd, env=env, text=True, capture_output=True, timeout=10,
            )
            passed = run.returncode == expected_exit and (
                error_type in run.stderr and expected_text in run.stderr
                if error_type else run.stdout == expected_text
            )
            results.append({
                "id": case_id, "case": label, "codeTemplate": template,
                "startupPythonPathRoot": env_root,
                "expected": {"exitCode": expected_exit, "errorType": error_type, "text": expected_text},
                "observed": {"exitCode": run.returncode, "stdout": run.stdout, "error": run.stderr.strip().splitlines()[-1] if run.stderr.strip() else None},
                "passed": passed,
            })
    report = {
        "checkedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "Temporary fixture imports in ordinary Python subprocesses only",
        "prototype": True, "vscodeRun": False, "jupyterKernelRun": False,
        "python": platform.python_version(), "platform": platform.system(),
        "pythonTargetAssumption": "3.12.13 (not tested)",
        "probeSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "jupyterClientAvailable": importlib.util.find_spec("jupyter_client") is not None,
        "ipykernelAvailable": importlib.util.find_spec("ipykernel") is not None,
        "persistentEnvironmentModified": False, "packagesInstalled": False,
        "fixtures": FIXTURES, "cases": results,
        "limitations": ["Windows and Jupyter not run", "No real library, dependency installation or ZIP tested", "No formal package name or import method adopted"],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    count = sum(row["passed"] for row in results)
    print(f"Ordinary Python import research: {count}/{len(results)} passed. Jupyter and VS Code NOT tested.")
    return 0 if count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
