"""File actions for ZizAI notebooks, independent of desktop automation."""
from datetime import datetime, timezone
import errno
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


def _file_result(action, target, message, status='success'):
    return pd.DataFrame([{
        'status': status, 'executed_at': datetime.now(timezone.utc).isoformat(),
        'connector': 'WindowsConnector', 'action': action, 'target': target.as_posix(), 'message': message,
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
        return _file_result('rename_and_move_file', source, '対象ファイルが存在しないためスキップしました。', 'skipped')
    if not source.is_file():
        raise FileNotFoundError(f'対象ファイルが見つかりません: {source}')
    name = (destination_file_name or '').strip()
    if not destination_folder and not name:
        raise ValueError('移動先フォルダーか変更後のファイル名を指定してください。')
    folder = Path(destination_folder).expanduser().resolve() if destination_folder else source.parent.resolve()
    target = folder / _file_name(name or source.name)
    if folder == source.parent.resolve() and target.name == source.name:
        return _file_result('rename_and_move_file', target, 'ファイル名と保存先は同じです。', 'skipped')
    folder.mkdir(parents=True, exist_ok=True)
    _move_without_replacing(source, target)
    return _file_result('rename_and_move_file', target, 'ファイルを移動しました。')


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
    return _file_result('create_markdown_file', target, 'Markdownを保存しました。')


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
