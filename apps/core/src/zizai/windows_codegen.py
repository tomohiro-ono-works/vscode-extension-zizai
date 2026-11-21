"""Build ordinary Python calls for Windows connector actions."""
import ast
from pathlib import Path

from .connector_codegen import _identifier, absolute_file_path, module_name_for, render_call


SEARCH_FIELDS = {
    'root_folder', 'recursive', 'file_name_pattern', 'file_extension_pattern', 'max_elapsed_seconds',
}
WAIT_FIELDS = {'wait_before_seconds', 'wait_after_seconds', 'output_variable'}
GENERATION_FIELDS = {
    'windows.search_files_by_name': SEARCH_FIELDS | {'output_variable'},
    'windows.search_text_in_files': SEARCH_FIELDS | {'content_pattern', 'context_lines', 'output_variable'},
    'windows.create_markdown_file': {'folder', 'filename', 'write_mode', 'content', 'output_variable'},
    'windows.rename_and_move_file': {
        'source_file_path', 'destination_folder', 'destination_file_name', 'allow_missing_source', 'output_variable',
    },
    'windows.mouse_click': WAIT_FIELDS | {'coordinate_mode', 'x', 'y', 'button', 'click_count'},
    'windows.input_text': WAIT_FIELDS | {'text', 'input_mode'},
    'windows.send_keys': WAIT_FIELDS | {'key', 'ctrl', 'shift', 'alt'},
}
WRITE_MODES = {'新規作成': 'create', '追記': 'append', '上書き': 'replace'}
PATH_FIELDS = {'root_folder', 'source_file_path', 'destination_folder'}


def _screen_parameters(kind, values):
    if kind == 'windows.mouse_click':
        parameters = {
            'button': {'左': 'left', '右': 'right'}[values['button']],
            'click_count': {'シングルクリック': 1, 'ダブルクリック': 2}[values['click_count']],
        }
        if values['coordinate_mode'] == '座標指定':
            try:
                parameters.update(x=int(values['x']), y=int(values['y']))
            except ValueError as error:
                raise ValueError('X座標とY座標には整数を指定してください。') from error
    elif kind == 'windows.input_text':
        parameters = {'text': values['text'], 'replace': values['input_mode'] == '全選択して置換'}
    else:
        parameters = {'key': values['key'], **{key: values[key] for key in ('ctrl', 'shift', 'alt')}}
    return {
        **parameters,
        'wait_before_seconds': values['wait_before_seconds'],
        'wait_after_seconds': values['wait_after_seconds'],
    }


def generate_windows(kind, values, module_path):
    fields = GENERATION_FIELDS[kind] - {'output_variable'}
    module = module_name_for(module_path)
    output = _identifier(values, 'output_variable')
    if 'wait_before_seconds' in fields:
        parameters = _screen_parameters(kind, values)
    elif kind == 'windows.create_markdown_file':
        folder = absolute_file_path(values, 'folder')
        filename = values['filename'].strip()
        if not filename or any(character in filename for character in '/\\:') or filename in {'.', '..'}:
            raise ValueError('ファイル名にはフォルダーを含めないでください。')
        parameters = {
            'target_file_path': (Path(folder) / filename).as_posix(),
            'content': values['content'],
            'write_mode': WRITE_MODES[values['write_mode']],
        }
    else:
        parameters = {
            name: absolute_file_path(values, name) if name in PATH_FIELDS else value
            for name, value in values.items() if name in fields and value not in ('', None)
        }
        if kind == 'windows.rename_and_move_file' and not (
            parameters.get('destination_folder') or values['destination_file_name'].strip()
        ):
            raise ValueError('移動先フォルダーか変更後のファイル名を指定してください。')
    arguments = [ast.keyword(arg=name, value=ast.Constant(value)) for name, value in parameters.items()]
    return render_call(module, kind.split('.', 1)[1], arguments, output, reading=True)
