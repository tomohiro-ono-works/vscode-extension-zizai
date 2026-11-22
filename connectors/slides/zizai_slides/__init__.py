"""Zizai Slides: dependency-free Python Markdown slide engine.

Public API: convert(input, output, mode='editable')
No VS Code, npm, pip, Marp, or network requirement for native PPTX.
"""
from __future__ import annotations

__version__ = "0.6.1"
from pathlib import Path
from base64 import b64encode
import copy

from .slide_engine import compile_deck, SlideSyntaxError
from .layout import layout_deck, document_html, slide_to_html
from .style import SlideStyle
from .export_pptx import export_measured_editable, export_image
from .export_pdf import export_pdf

__all__ = ['compile', 'convert', 'SlideSyntaxError', 'render_html']


def compile(text: str, style_path: str | Path | None = None) -> dict:
    deck = compile_deck(text)
    layouts = layout_deck(deck, SlideStyle(style_path))
    for slide, layout in zip(deck['slides'], layouts):
        slide['layout'] = layout
    return deck


def _with_images(deck: dict, source_dir: Path) -> dict:
    """Embed only local raster images, bounded and confined to document directory."""
    from html import unescape
    result = copy.deepcopy(deck)
    base = source_dir.resolve()
    for slide in result['slides']:
        for item in slide['layout'].get('images', []):
            rel = unescape(item.get('path', ''))
            if not rel or '\0' in rel or '://' in rel or rel.startswith(('/', '\\')):
                continue
            candidate = (base / rel).resolve()
            if not candidate.is_relative_to(base):
                continue
            if not candidate.is_file() or candidate.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.gif'):
                continue
            if candidate.stat().st_size > 12_000_000:
                continue
            kind = 'jpeg' if candidate.suffix.lower() in ('.jpg', '.jpeg') else candidate.suffix.lower()[1:]
            item['src'] = 'data:image/' + kind + ';base64,' + b64encode(candidate.read_bytes()).decode('ascii')
    return result


def render_html(text: str, source_dir: str | Path = '.', style_path: str | Path | None = None) -> str:
    deck = _with_images(compile(text, style_path=style_path), Path(source_dir))
    return document_html(deck, [s['layout'] for s in deck['slides']], SlideStyle(style_path))


def convert(input: str | Path, output: str | Path, mode: str = 'editable',
            style_path: str | Path | None = None) -> Path:
    """Convert a Markdown file to editable PPTX, image PPTX, HTML or PDF.

    Image mode and PDF use installed Edge/Chrome; editable PPTX is pure stdlib.
    Returns the destination path; raises ValueError for unsupported/overflow.
    """
    source = Path(input).expanduser().resolve()
    target = Path(output).expanduser().resolve()
    text = source.read_text(encoding='utf-8-sig')
    # Prefer a slide-local CSS of the same name, unless the caller explicitly
    # chose another stylesheet. This is only a discovery rule, not a new dependency.
    if style_path is None:
        adjacent_css = source.with_suffix('.css')
        if adjacent_css.is_file():
            style_path = adjacent_css
    return convert_text(text, target, mode=mode, source_dir=source.parent, style_path=style_path)


def convert_text(text: str, output: str | Path, mode='editable', source_dir: str | Path = '.',
                 style_path: str | Path | None = None) -> Path:
    target = Path(output).expanduser().resolve()
    if not target.parent.is_dir():
        raise ValueError('出力先のフォルダが存在しません。')
    deck = compile(text, style_path=style_path)
    style = SlideStyle(style_path)
    layouts = [s['layout'] for s in deck['slides']]
    if len(layouts) > 100:
        raise ValueError('スライドは100枚以内にしてください。')
    if mode == 'editable':
        if target.suffix.lower() != '.pptx':
            raise ValueError('編集可能モードの出力先は.pptxにしてください。')
        for i, page in enumerate(layouts, 1):
            if page['warnings']:
                raise ValueError(f'{i}枚目にレイアウトのはみ出しがあります: ' + '; '.join(page['warnings']))
        export_measured_editable(deck, layouts, target, str(Path(source_dir).resolve()))
    elif mode in ('image', 'html', 'pdf'):
        illustrated = _with_images(deck, Path(source_dir))
        if mode == 'image':
            if target.suffix.lower() != '.pptx':
                raise ValueError('画像モードの出力先は.pptxにしてください。')
            pages = []
            for slide in illustrated['slides']:
                html = document_html({'slides':[slide]},[slide['layout']],style)
                pages.append(html)
            export_image(pages, target)
        elif mode == 'html':
            if target.suffix.lower() not in ('.html', '.htm'):
                raise ValueError('HTMLモードは.htmlに出力してください。')
            target.write_text(document_html(illustrated,[s['layout'] for s in illustrated['slides']],style),encoding='utf-8')
        else:
            if target.suffix.lower() != '.pdf':
                raise ValueError('PDFモードは.pdfに出力してください。')
            export_pdf(document_html(illustrated,[s['layout'] for s in illustrated['slides']],style), str(target))
    else:
        raise ValueError('modeはeditable / image / html / pdfのいずれかにしてください。')
    return target
