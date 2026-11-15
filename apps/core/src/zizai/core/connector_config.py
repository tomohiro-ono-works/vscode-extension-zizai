"""User-scoped connector location; never require a per-project copy."""
import json
import os
from pathlib import Path
import tempfile


def _settings_path():
    override = os.environ.get('ZIZAI_CONFIG_FILE')
    if override:
        return Path(override).expanduser()
    base = Path(os.environ.get('APPDATA') or Path.home() / '.config')
    return base / 'ZizAI' / 'settings.json'


def _settings():
    path = _settings_path()
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
    """Explicitly save one shared directory; preserve other user settings."""
    directory = Path(directory).expanduser()
    if not directory.is_absolute() or not directory.is_dir():
        raise ValueError('既存のコネクタ共通フォルダーを絶対パスで指定してください。')
    settings = _settings()
    settings['connectors_directory'] = str(directory.resolve())
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix='settings-', suffix='.tmp', delete=False) as stream:
        json.dump(settings, stream, ensure_ascii=False, indent=2)
        temporary = Path(stream.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return directory.resolve()


def local_cache_directory():
    base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.cache')
    return base / 'ZizAI' / 'pycache'
