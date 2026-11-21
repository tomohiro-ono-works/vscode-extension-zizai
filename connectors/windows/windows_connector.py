"""Windows file and explicit screen actions for ZizAI notebooks."""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import errno
from functools import lru_cache
import ntpath
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
from tempfile import NamedTemporaryFile
import time
import warnings

import pandas as pd


def _file_name(value):
    name = PureWindowsPath(value)
    is_reserved = getattr(ntpath, 'isreserved', None)
    reserved = is_reserved(value) if is_reserved else name.is_reserved()
    if (not value or name.name != value or value in {'.', '..'} or reserved
            or any(character in value for character in '<>:"/\\|?*') or value.endswith((' ', '.'))):
        raise ValueError('ファイル名にはフォルダーやWindowsで使えない文字を含めないでください。')
    return value


def _action_result(action, target, message, status='success'):
    if isinstance(target, Path):
        target = target.as_posix()
    return pd.DataFrame([{
        'status': status, 'executed_at': datetime.now(timezone.utc).isoformat(),
        'connector': 'WindowsConnector', 'action': action, 'target': target, 'message': message,
    }])


def _move_on_same_volume(source, target):
    if os.name == 'nt':
        source.rename(target)
    else:
        os.link(source, target)
        source.unlink()


def _move_without_replacing(source, target):
    try:
        _move_on_same_volume(source, target)
        return
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise

    with NamedTemporaryFile(dir=target.parent, prefix='.zizai-move-', delete=False) as temporary:
        staged = Path(temporary.name)
    try:
        shutil.copy2(source, staged)
        _move_on_same_volume(staged, target)
    finally:
        staged.unlink(missing_ok=True)
    source.unlink()


def rename_and_move_file(source_file_path, *, destination_folder=None, destination_file_name=None,
                         allow_missing_source=False):
    """Rename a file, move it, or do both. Raise if the destination already exists."""
    source = Path(source_file_path).expanduser().absolute()
    if source.is_symlink() or source.is_junction():
        raise ValueError('リンクは移動できません。')
    if not source.exists() and allow_missing_source:
        return _action_result('rename_and_move_file', source, '対象ファイルが存在しないためスキップしました。', 'skipped')
    if not source.is_file():
        raise FileNotFoundError(f'対象ファイルが見つかりません: {source}')
    name = (destination_file_name or '').strip()
    if not destination_folder and not name:
        raise ValueError('移動先フォルダーか変更後のファイル名を指定してください。')
    folder = Path(destination_folder).expanduser().resolve() if destination_folder else source.parent.resolve()
    target = folder / _file_name(name or source.name)
    if folder == source.parent.resolve() and target.name == source.name:
        return _action_result('rename_and_move_file', target, 'ファイル名と保存先は同じです。', 'skipped')
    folder.mkdir(parents=True, exist_ok=True)
    _move_without_replacing(source, target)
    return _action_result('rename_and_move_file', target, 'ファイルを移動しました。')


def create_markdown_file(target_file_path, content, *, write_mode='create'):
    """Save UTF-8 Markdown using the selected write mode."""
    modes = {'create': 'x', 'append': 'a', 'replace': 'w'}
    if write_mode not in modes:
        raise ValueError('書き込み方法を確認してください。')
    target = Path(target_file_path).expanduser().absolute()
    _file_name(target.name)
    if not target.suffix:
        target = target.with_suffix('.md')
    if target.suffix.lower() not in {'.md', '.markdown', '.txt'}:
        raise ValueError('拡張子は .md、.markdown、.txt のいずれかを指定してください。')
    if target.is_symlink() or target.is_junction():
        raise ValueError('リンクには書き込めません。')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open(modes[write_mode], encoding='utf-8', newline='') as handle:
        handle.write(content)
    return _action_result('create_markdown_file', target, 'Markdownを保存しました。')


def _checked_integer(value, minimum, maximum, label):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'{label}は{minimum}〜{maximum}の整数を指定してください。')


def _search_pattern(pattern, label):
    if not pattern:
        return None
    try:
        return re.compile(pattern)
    except re.error as error:
        raise ValueError(f'{label}の正規表現が不正です: {error}') from error


def _candidate_paths(root, recursive):
    for directory, folders, filenames in os.walk(root):
        parent = Path(directory)
        folders[:] = sorted(
            name for name in folders
            if recursive and not (parent / name).is_symlink() and not (parent / name).is_junction()
        )
        for name in sorted(filenames):
            yield parent / name


def _matching_files(root_folder, recursive, file_name_pattern, file_extension_pattern, max_elapsed_seconds):
    _checked_integer(max_elapsed_seconds, 30, 480, '検索時間の目安')
    name_filter = _search_pattern(file_name_pattern, 'ファイル名')
    extension_filter = _search_pattern(file_extension_pattern, '拡張子')
    root = Path(root_folder).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)
    deadline = time.monotonic() + max_elapsed_seconds
    for path in _candidate_paths(root, recursive):
        if time.monotonic() >= deadline:
            warnings.warn('検索時間に達したため、ここまでの結果を返します。', RuntimeWarning, stacklevel=2)
            break
        if name_filter and not name_filter.search(path.stem):
            continue
        if extension_filter and not (extension_filter.search(path.suffix)
                                     or extension_filter.search(path.suffix.lstrip('.'))):
            continue
        if not path.is_symlink() and path.is_file():
            yield path


def _file_columns(path):
    return {'folder_path': path.parent.as_posix(), 'file_name': path.name}


def search_files_by_name(root_folder, *, recursive=False, file_name_pattern='', file_extension_pattern='',
                         max_elapsed_seconds=120):
    """Find files by a regular expression on their name stem and extension."""
    paths = _matching_files(root_folder, recursive, file_name_pattern, file_extension_pattern, max_elapsed_seconds)
    return pd.DataFrame((_file_columns(path) for path in paths), columns=['folder_path', 'file_name'])


def _text_lines(path):
    data = path.read_bytes()
    if b'\0' in data:
        return []
    for encoding in ('utf-8-sig', 'cp932', 'shift_jis'):
        try:
            return data.decode(encoding).splitlines()
        except UnicodeDecodeError:
            continue
    return []


def search_text_in_files(root_folder, content_pattern, *, recursive=False, file_name_pattern='',
                         file_extension_pattern='', context_lines=0, max_elapsed_seconds=120):
    """Return matching lines and surrounding text from UTF-8 and Japanese text files."""
    _checked_integer(context_lines, 0, 200, '前後行数')
    matcher = _search_pattern(content_pattern, '検索する文字列')
    if matcher is None:
        raise ValueError('検索する文字列を入力してください。')
    paths = _matching_files(root_folder, recursive, file_name_pattern, file_extension_pattern, max_elapsed_seconds)
    rows = []
    for path in paths:
        lines = _text_lines(path)
        for index, line in enumerate(lines):
            if matcher.search(line):
                rows.append({
                    **_file_columns(path), 'line_number': index + 1, 'matched_line': line,
                    'context_excerpt': '\n'.join(lines[max(0, index - context_lines):index + context_lines + 1]),
                })
    return pd.DataFrame(rows, columns=['folder_path', 'file_name', 'line_number', 'matched_line', 'context_excerpt'])


class _MouseInput(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('data', wintypes.DWORD),
                ('flags', wintypes.DWORD), ('time', wintypes.DWORD), ('extra_info', ctypes.c_size_t)]


class _KeyboardInput(ctypes.Structure):
    _fields_ = [('key', wintypes.WORD), ('scan', wintypes.WORD), ('flags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('extra_info', ctypes.c_size_t)]


class _InputData(ctypes.Union):
    _fields_ = [('mouse', _MouseInput), ('keyboard', _KeyboardInput)]


class _Input(ctypes.Structure):
    _fields_ = [('kind', wintypes.DWORD), ('data', _InputData)]


_KEY_UP = 0x02
_KEY_UNICODE = 0x04
_KEY_EXTENDED = 0x01
_KEYS = {
    'BACKSPACE': 0x08, 'TAB': 0x09, 'ENTER': 0x0D, 'ESC': 0x1B, 'SPACE': 0x20,
    'PAGEUP': 0x21, 'PAGEDOWN': 0x22, 'END': 0x23, 'HOME': 0x24, 'LEFT': 0x25, 'UP': 0x26,
    'RIGHT': 0x27, 'DOWN': 0x28, 'INSERT': 0x2D, 'DELETE': 0x2E,
    **{f'F{number}': 0x6F + number for number in range(1, 25)},
}
_EXTENDED_KEYS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E}
_MODIFIERS = {'ctrl': 0x11, 'shift': 0x10, 'alt': 0x12}
_BUTTON_EVENTS = {'left': (0x02, 0x04), 'right': (0x08, 0x10)}


@lru_cache(maxsize=1)
def _user32():
    if os.name != 'nt':
        raise OSError('画面操作にはWindowsのローカルカーネルが必要です。')
    api = ctypes.WinDLL('user32.dll', use_last_error=True)
    api.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_Input), ctypes.c_int)
    api.SendInput.restype = wintypes.UINT
    api.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
    api.SetCursorPos.restype = wintypes.BOOL
    api.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
    api.GetCursorPos.restype = wintypes.BOOL
    return api


def _send_inputs(events):
    batch = (_Input * len(events))(*events)
    api = _user32()
    ctypes.set_last_error(0)
    sent = api.SendInput(len(batch), batch, ctypes.sizeof(_Input))
    if sent != len(batch):
        raise OSError(ctypes.get_last_error(), f'Windowsが画面入力を受け付けませんでした（{sent}/{len(batch)}）。')


def _set_coordinates(x, y):
    api = _user32()
    point = wintypes.POINT()
    if not api.SetCursorPos(x, y) or not api.GetCursorPos(ctypes.byref(point)):
        raise OSError(ctypes.get_last_error(), '指定座標にカーソルを移動できませんでした。')
    if (point.x, point.y) != (x, y):
        raise ValueError('指定座標に移動できません。画面の座標を確認してください。')


def _screen_action(action, target, events, before, after, coordinates=None):
    for seconds in (before, after):
        if type(seconds) is not int or seconds < 0:
            raise ValueError('操作前後の待機は0以上の整数秒にしてください。')
    _user32()
    if before:
        time.sleep(before)
    if coordinates is not None:
        _set_coordinates(*coordinates)
    _send_inputs(events)
    if after:
        time.sleep(after)
    return _action_result(action, target, 'Windowsに画面入力を送信しました。')


def _keyboard_event(key=0, scan=0, flags=0):
    return _Input(1, _InputData(keyboard=_KeyboardInput(key, scan, flags)))


def _key_chord(key, modifiers=()):
    flags = _KEY_EXTENDED if key in _EXTENDED_KEYS else 0
    return [
        *(_keyboard_event(key=modifier) for modifier in modifiers),
        _keyboard_event(key=key, flags=flags),
        _keyboard_event(key=key, flags=flags | _KEY_UP),
        *(_keyboard_event(key=modifier, flags=_KEY_UP) for modifier in reversed(modifiers)),
    ]


def mouse_click(*, x=None, y=None, button='left', click_count=1, wait_before_seconds=0, wait_after_seconds=0):
    """Click at the current or specified screen coordinates."""
    coordinates = None
    if x is not None or y is not None:
        if any(type(value) is not int or not -(2**31) <= value < 2**31 for value in (x, y)):
            raise ValueError('X座標とY座標には画面座標の整数を指定してください。')
        coordinates = (x, y)
    if button not in _BUTTON_EVENTS or type(click_count) is not int or click_count not in (1, 2):
        raise ValueError('マウスボタンかクリック回数を確認してください。')
    events = [_Input(0, _InputData(mouse=_MouseInput(flags=flag))) for flag in _BUTTON_EVENTS[button]]
    target = 'cursor' if coordinates is None else f'screen:({x}, {y})'
    return _screen_action('mouse_click', target, events * click_count,
                          wait_before_seconds, wait_after_seconds, coordinates)


def input_text(text, *, replace=False, wait_before_seconds=0, wait_after_seconds=0):
    """Send Unicode text to the focused control without using the clipboard."""
    if not isinstance(text, str) or not text or '\0' in text:
        raise ValueError('入力する文字を確認してください。')
    utf16 = text.encode('utf-16-le')
    events = _key_chord(ord('A'), (_MODIFIERS['ctrl'],)) if replace else []
    for offset in range(0, len(utf16), 2):
        code_unit = int.from_bytes(utf16[offset:offset + 2], 'little')
        events.append(_keyboard_event(scan=code_unit, flags=_KEY_UNICODE))
        events.append(_keyboard_event(scan=code_unit, flags=_KEY_UNICODE | _KEY_UP))
    return _screen_action('input_text', 'active_window', events, wait_before_seconds, wait_after_seconds)


def send_keys(key, *, ctrl=False, shift=False, alt=False, wait_before_seconds=0, wait_after_seconds=0):
    """Send a single key with optional Ctrl, Shift and Alt modifiers."""
    key = key.strip().upper()
    if key in _KEYS:
        key_code = _KEYS[key]
    elif len(key) == 1 and key.isascii() and key.isalnum():
        key_code = ord(key)
    else:
        raise ValueError('英数字、F1〜F24、またはEnterなどのキー名を指定してください。')
    modifiers = tuple(_MODIFIERS[modifier] for modifier, enabled in (('ctrl', ctrl), ('shift', shift), ('alt', alt))
                      if enabled)
    return _screen_action('send_keys', 'active_window', _key_chord(key_code, modifiers),
                          wait_before_seconds, wait_after_seconds)
