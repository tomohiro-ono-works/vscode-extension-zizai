"""Explicit external module import at execution time, using local bytecode."""
import hashlib
import importlib.util
from pathlib import Path
import sys

from .connector_config import local_cache_directory


def load_connector(module_path):
    """Import a trusted .py by absolute path, without changing sys.path."""
    path = Path(module_path).expanduser()
    if not path.is_absolute() or path.suffix.lower() != '.py':
        raise ValueError('コネクタは.pyの絶対パスで指定してください。')
    path = path.resolve(strict=True)
    # Respect an existing Python cache-prefix setting. The local default also
    # protects the shared folder when a kernel was started without that setting.
    if sys.pycache_prefix is None:
        sys.pycache_prefix = str(local_cache_directory())
    name = '_zizai_connector_' + hashlib.sha256(str(path).encode('utf-8')).hexdigest()
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module
