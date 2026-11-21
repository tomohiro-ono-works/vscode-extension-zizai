"""Build ordinary Python calls for the Windows file actions."""
import ast
from pathlib import Path

from .connector_codegen import _identifier, absolute_file_path, module_name_for, render_call


SEARCH_FIELDS = {
    'root_folder', 'recursive', 'file_name_pattern', 'file_extension_pattern', 'max_elapsed_seconds',
}
GENERATION_FIELDS = {
    'windows.search_files_by_name': SEARCH_FIELDS | {'output_variable'},
    'windows.search_text_in_files': SEARCH_FIELDS | {'content_pattern', 'context_lines', 'output_variable'},
    'windows.create_markdown_file': {'folder', 'filename', 'write_mode', 'content', 'output_variable'},
    'windows.rename_and_move_file': {
        'source_file_path', 'destination_folder', 'destination_file_name', 'allow_missing_source', 'output_variable',
    },
}
WRITE_MODES = {'新規作成': 'create', '追記': 'append', '上書き': 'replace'}
PATH_FIELDS = {'root_folder', 'source_file_path', 'destination_folder'}


def generate_windows(kind, values, module_path):
    fields = GENERATION_FIELDS[kind] - {'output_variable'}
    module = module_name_for(module_path)
    output = _identifier(values, 'output_variable')
    if kind == 'windows.create_markdown_file':
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
