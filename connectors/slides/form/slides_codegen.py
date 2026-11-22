"""Generate explicit editable-PPTX conversion calls."""

import ast
from pathlib import Path

from ...connector_codegen import _text, absolute_file_path, module_name_for, render_call


CONVERSION = 'slides.markdown_to_pptx'
GENERATION_FIELDS = {
    CONVERSION: {'input_mode', 'markdown_text', 'markdown_file', 'style_path', 'output_folder', 'filename'},
}


def generate_slides(kind, values, module_path):
    if kind != CONVERSION:
        raise ValueError('未対応のスライド生成種別です。')
    params = {}
    mode = values['input_mode']
    if mode == 'text':
        params['markdown_text'] = _text(values, 'markdown_text', required=True)
    elif mode == 'file':
        params['markdown_file'] = absolute_file_path(values, 'markdown_file')
    else:
        raise ValueError('Markdownの入力方法を選択してください。')
    style = _text(values, 'style_path')
    if style.strip():
        params['style_path'] = absolute_file_path(values, 'style_path')

    folder = Path(_text(values, 'output_folder', required=True))
    if not folder.is_absolute():
        raise ValueError('保存先フォルダーは絶対パスで指定してください。')
    filename = _text(values, 'filename', required=True).strip()
    if filename in {'.', '..'} or any(char in filename for char in '/\\:'):
        raise ValueError('PPTXファイル名にはファイル名だけを指定してください。')
    extension = Path(filename).suffix.lower()
    if extension and extension != '.pptx':
        raise ValueError('出力先の拡張子は .pptx にしてください。')
    if not extension:
        filename += '.pptx'
    params['output_path'] = (folder / filename).as_posix()
    arguments = [ast.keyword(arg=key, value=ast.Constant(value)) for key, value in params.items()]
    return render_call(module_name_for(module_path), 'markdown_to_pptx', arguments, 'result', reading=True)
