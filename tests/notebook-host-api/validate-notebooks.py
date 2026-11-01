"""Validate explicitly selected diagnostic notebooks without conversion or writes."""

import argparse
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import warnings

import nbformat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebooks", nargs="+", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    # Keep previous results: never overwrite an existing report.
    with args.report.open("x", encoding="utf-8") as report_file:
        results = []
        for path in args.notebooks:
            result = {"file": path.name, "status": "FAIL"}
            try:
                original = path.read_bytes()
                before = hashlib.sha256(original).hexdigest()
                notebook = json.loads(original)
                candidate = copy.deepcopy(notebook)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    nbformat.validate(
                        candidate,
                        version=notebook["nbformat"],
                        version_minor=notebook["nbformat_minor"],
                        relax_add_props=False,
                    )
                result["warnings"] = [str(item.message) for item in caught]
                result["data_unchanged"] = candidate == notebook
                result["file_unchanged"] = (
                    hashlib.sha256(path.read_bytes()).hexdigest() == before
                )
                result["sha256"] = before
                result["nbformat"] = [
                    notebook["nbformat"], notebook["nbformat_minor"]
                ]
                if not result["data_unchanged"] or not result["file_unchanged"]:
                    raise ValueError("Notebook changed during validation")
                if caught:
                    raise ValueError("Validation emitted warnings; inspect report")
                result["status"] = "PASS"
            except Exception as error:
                result["error_type"] = type(error).__name__
                result["error"] = str(error).splitlines()[0]
            results.append(result)
        passed = sum(item["status"] == "PASS" for item in results)
        report = {
            "scope": "explicit diagnostic notebooks; schema validation only",
            "python": platform.python_version(),
            "packages": {
                dist.metadata["Name"]: dist.version
                for dist in importlib.metadata.distributions()
            },
            "conversion_or_normalization_requested": False,
            "kernel_or_GUI_execution": False,
            "passed": passed,
            "failed": len(results) - passed,
            "results": results,
        }
        json.dump(report, report_file, ensure_ascii=False, indent=2)
        report_file.write("\n")
    print(json.dumps({"passed": passed, "failed": len(results) - passed}))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
