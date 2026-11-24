"""Package the form modules shipped with each connector."""
from pathlib import Path
from keyword import iskeyword

from setuptools import find_packages, setup


root = Path(__file__).resolve().parent
packages = ["zizai", *(f"zizai.{name}" for name in find_packages(root / "src"))]
package_dir = {"zizai": "src"}
connector_forms = []
for initializer in sorted((root / "connectors").glob("*/form/__init__.py")):
    identifier = initializer.parent.parent.name
    if not identifier.isidentifier() or iskeyword(identifier):
        raise ValueError(f"Invalid connector folder name: {identifier}")
    name = f"zizai.connector_forms.{identifier}"
    connector_forms.append(f"{identifier} = {name}")
    package_dir[name] = initializer.parent.relative_to(root).as_posix()
    packages.extend([name, *(f"{name}.{child}" for child in find_packages(initializer.parent))])

setup(packages=packages, package_dir=package_dir,
      entry_points={"zizai.connector_forms": connector_forms})
