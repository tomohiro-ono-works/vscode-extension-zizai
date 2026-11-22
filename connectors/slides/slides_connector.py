"""Convert Markdown files or strings using the bundled Zizai Slides engine."""

from pathlib import Path
from shutil import copyfileobj
from tempfile import TemporaryDirectory


def markdown_to_pptx(output_path, *, markdown_text=None, markdown_file=None, style_path=None):
    """Create a new editable PowerPoint and return its path."""
    if (markdown_text is None) == (markdown_file is None):
        raise ValueError('Markdown本文かファイルのどちらかを指定してください。')
    if markdown_text is not None and (not isinstance(markdown_text, str) or not markdown_text.strip()):
        raise ValueError('Markdown本文を入力してください。')
    target = Path(output_path).expanduser().absolute()
    if target.suffix.lower() != '.pptx':
        raise ValueError('出力先の拡張子は .pptx にしてください。')
    if target.exists() or target.is_symlink():
        raise FileExistsError(f'出力先が既にあります: {target}')
    if not target.parent.is_dir():
        raise FileNotFoundError(f'出力先フォルダーがありません: {target.parent}')
    from slides.zizai_slides import convert, convert_text

    with TemporaryDirectory(dir=target.parent, prefix='.zizai-pptx-') as folder:
        staged = Path(folder) / 'slides.pptx'
        if markdown_file is None:
            convert_text(markdown_text, staged, mode='editable', style_path=style_path)
        else:
            convert(markdown_file, staged, mode='editable', style_path=style_path)

        with staged.open('rb') as source:
            destination = target.open('xb')
            try:
                with destination:
                    copyfileobj(source, destination)
            except BaseException:
                target.unlink(missing_ok=True)
                raise
    return target.as_posix()
