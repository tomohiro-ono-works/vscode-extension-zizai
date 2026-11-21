"""One-time, Python-environment-scoped registration for ordinary imports."""
import json
import locale
import os
from pathlib import Path
import sys
import sysconfig
import tempfile

REGISTRATION_HEADER = '# Managed by ZizAI connector setup\n'


def _site_packages():
    return Path(sysconfig.get_path('purelib'))


def _settings_path():
    override = os.environ.get('ZIZAI_CONFIG_FILE')
    if override:
        return Path(override).expanduser()
    return _site_packages() / 'zizai-connectors.json'


def _settings():
    path = _settings_path()
    if not path.exists() and not os.environ.get('ZIZAI_CONFIG_FILE'):
        # Read the former user-scoped setting, but never overwrite it implicitly.
        base = Path(os.environ.get('APPDATA') or Path.home() / '.config')
        path = base / 'ZizAI' / 'settings.json'
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('ZizAI設定はJSONオブジェクトにしてください。')
    return value


def get_connector_directory():
    value = os.environ.get('ZIZAI_CONNECTORS_DIR') or _settings().get('connectors_directory')
    if value is None:
        return None
    if not isinstance(value, str) or not Path(value).expanduser().is_absolute():
        raise ValueError('コネクタ共通フォルダーは絶対パスで指定してください。')
    return Path(value).expanduser().resolve()


def configure_connectors(directory):
    """Register the shared source in this Python environment, without importing it.

    New kernels read the standard .pth file. Restart an existing kernel after
    changing registration or updating an already imported connector.
    """
    directory = Path(directory).expanduser()
    if not directory.is_absolute() or not directory.is_dir():
        raise ValueError('既存のコネクタ共通フォルダーを絶対パスで指定してください。')
    directory = directory.resolve()
    paths = [directory, *sorted(p.resolve() for p in directory.iterdir()
        if p.is_dir() and not p.name.startswith('.') and p.name != '__pycache__')]
    names = {}
    for folder in paths:
        if not folder.is_relative_to(directory) or any(c in str(folder) for c in '\r\n'):
            raise ValueError('検索先は共通フォルダー内の単一行のパスにしてください。')
        for module in folder.glob('*_connector.py'):
            if module.stem in names:
                raise ValueError('共通フォルダーに同名のコネクタがあります。')
            names[module.stem] = module
    registration = _site_packages() / 'zizai-connectors.pth'
    encoding = 'utf-8' if sys.version_info >= (3, 13) else locale.getencoding()
    if registration.exists() and not registration.read_text(encoding=encoding).startswith(REGISTRATION_HEADER):
        raise FileExistsError('既存のzizai-connectors.pthはZizAI管理ではないため変更しません。')
    cache = ascii(str(local_cache_directory().resolve()))
    text = (REGISTRATION_HEADER +
        f'import sys; sys.pycache_prefix = {cache} if sys.pycache_prefix is None else sys.pycache_prefix\n' +
        ''.join(str(folder) + '\n' for folder in paths))
    _atomic_write(registration, text, encoding=encoding)
    settings = _settings()
    settings['connectors_directory'] = str(directory)
    _atomic_write(_settings_path(), json.dumps(settings, ensure_ascii=False, indent=2))
    return directory


def _atomic_write(path, text, *, encoding='utf-8'):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding=encoding, dir=path.parent,
                                     prefix='settings-', suffix='.tmp', delete=False) as stream:
        stream.write(text)
        temporary = Path(stream.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def local_cache_directory():
    base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.cache')
    return base / 'ZizAI' / 'pycache'
