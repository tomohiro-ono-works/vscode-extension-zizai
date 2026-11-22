"""Pure-standard-library Markdown slide compiler for Zizai Slide Studio.

Protocol: one JSON request on stdin, one JSON response on stdout.
No network, no Python package dependencies, no user code execution.
"""
from __future__ import annotations

import html
import json
import re
import sys
from typing import Any

COLORS = {
    f'{hue}-{shade}'
    for hue in ('turquoise', 'aqua', 'gray', 'coral', 'mono', 'yellow')
    for shade in ('dark', 'light')
}
CONTAINERS = {
    'h': ('layout', 'h'), 'horizontal': ('layout', 'h'),
    'v': ('layout', 'v'), 'vertical': ('layout', 'v'),
    'card': ('card',), 'paper': ('paper',), 'blank': ('blank',),
    'header': ('header',), 'body': ('body',),
    'hero': ('hero',), 'hero-media': ('hero-media',), 'hero-copy': ('hero-copy',),
    'text': ('abs-text',), 'box': ('abs-box',), 'shape': ('abs-shape',),
}
MODIFIERS = {'hover', 'medium', 'tall', 'center', 'equal', 'flow'}
FENCE = re.compile(r'^\s{0,3}(:{3,})(?:\s+([^\s].*?))?\s*$')
CODE_FENCE = re.compile(r'^\s{0,3}(`{3,}|~{3,})(.*)$')
DIRECTIVE = re.compile(r'^\s*<!--\s*_class:\s*([\w\s-]+?)\s*-->\s*$')
COLOR_TOKEN = re.compile(r'\[([^\]\n]+)\]\{\.([a-z]+-(?:dark|light))\}')
INLINE = re.compile(
    r'!\[([^\]\n]*)\]\(([^)\n]+)\)'
    r'|\[([^\]\n]+)\]\{\.([a-z]+-(?:dark|light))\}'
    r'|\[([^\]\n]+)\]\((https?://[^)\s]+|mailto:[^)\s]+)\)'
    r'|(`+)(.+?)\7'
    r'|(\*\*|__)(.+?)\9'
    r'|(?<!\*)\*([^*\n]+)\*(?!\*)',
)


class SlideSyntaxError(ValueError):
    pass


def escape(text: str) -> str:
    return html.escape(text, quote=True)


def render_inline(value: str) -> str:
    """Render inline Markdown without allowing arbitrary HTML or JS."""
    pieces: list[str] = []
    cursor = 0
    for found in INLINE.finditer(value):
        pieces.append(escape(value[cursor:found.start()]))
        img_alt, img_path, chip_label, chip_color, link_label, link_url, ticks, code, bold_mark, bold_text, italic = found.groups()
        if img_alt is not None:
            # Remote and active content is deliberately excluded from document images.
            if (not re.match(r'(?i)^[a-z][a-z0-9+.-]*:', img_path)
                    and not img_path.startswith(('/', '\\', '//'))
                    and not img_path.lower().endswith('.svg')
                    and not img_path.startswith('#')):
                pieces.append(f'<img data-local-path="{escape(img_path)}" alt="{escape(img_alt)}">')
            else:
                pieces.append(escape(img_alt))
        elif chip_label is not None:
            if chip_color in COLORS:
                pieces.append(f'<span class="slide-chip tone-{chip_color}">{escape(chip_label)}</span>')
            else:
                pieces.append(escape(found.group()))
        elif link_label is not None:
            pieces.append(f'<a href="{escape(link_url)}" class="slide-link">{escape(link_label)}</a>')
        elif ticks is not None:
            pieces.append(f'<code>{escape(code)}</code>')
        elif bold_mark is not None:
            pieces.append(f'<strong>{escape(bold_text)}</strong>')
        else:
            pieces.append(f'<em>{escape(italic)}</em>')
        cursor = found.end()
    pieces.append(escape(value[cursor:]))
    return ''.join(pieces)


def read_frontmatter(text: str) -> tuple[dict[str, str], list[str]]:
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    if not lines or lines[0].strip() != '---':
        return {}, lines
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == '---'), None)
    if end is None:
        raise SlideSyntaxError('フロントマターの終端 --- がありません。')
    metadata: dict[str, str] = {}
    for row in lines[1:end]:
        match = re.match(r'^([a-zA-Z][\w-]*):\s*(.*?)\s*$', row)
        if match:
            key, value = match.groups()
            metadata[key] = value.strip('"\'')
    return metadata, lines[end + 1:]


def split_slides(lines: list[str]) -> list[list[str]]:
    slides: list[list[str]] = []
    current: list[str] = []
    fence: tuple[str, int] | None = None
    container_depth = 0
    for line in lines:
        code_match = CODE_FENCE.match(line)
        if code_match:
            symbol = code_match[1][0]
            if fence is None:
                fence = (symbol, len(code_match[1]))
            elif symbol == fence[0] and len(code_match[1]) >= fence[1] and not code_match[2].strip():
                fence = None
        if fence is None:
            container = FENCE.match(line)
            if container:
                container_depth += 1 if container[2] else -1
            if line.strip() == '---' and container_depth == 0:
                if any(row.strip() for row in current):
                    slides.append(current)
                current = []
                continue
        current.append(line)
    if any(row.strip() for row in current):
        slides.append(current)
    return slides or [[]]


def parse_container(spec: str, line: int) -> str:
    parts = spec.split()
    name, mods = parts[0], parts[1:]
    if name not in CONTAINERS:
        raise SlideSyntaxError(f'{line}行: 不明なコンテナ「{name}」です。')
    if name in ('text', 'box', 'shape'):
        if len(mods) != 1 or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', mods[0]):
            raise SlideSyntaxError(f'{line}行: {name} コンテナにはCSSクラス名を1つ指定してください。')
        return '<div class="slide-absolute slide-abs-' + name + ' zs-' + mods[0] + '">'
    classes = ['slide-' + CONTAINERS[name][0]]
    classes.extend('slide-' + p for p in CONTAINERS[name][1:])
    colors = [part for part in mods if part in COLORS]
    if len(colors) > 1:
        raise SlideSyntaxError(f'{line}行: カードに複数の色を指定できません。')
    if colors and name != 'card':
        raise SlideSyntaxError(f'{line}行: 色指定はカードのみで使用できます。')
    for mod in mods:
        if mod in COLORS:
            classes.append('tone-' + mod)
        elif mod in MODIFIERS:
            classes.append('mod-' + mod)
        else:
            raise SlideSyntaxError(f'{line}行: 不明な修飾子「{mod}」です。')
    if name == 'blank':
        return '<div class="slide-blank" aria-hidden="true"></div>'
    return '<div class="' + ' '.join(classes) + '">'


def parse_table(row_lines: list[str]) -> str:
    cells = lambda x: [c.strip() for c in x.strip().strip('|').split('|')]
    header = cells(row_lines[0])
    body = row_lines[2:]
    out = ['<table class="slide-table"><thead><tr>']
    out += [f'<th>{render_inline(cell)}</th>' for cell in header]
    out.append('</tr></thead><tbody>')
    for row in body:
        out.append('<tr>')
        out += [f'<td>{render_inline(cell)}</td>' for cell in cells(row)]
        out.append('</tr>')
    out.append('</tbody></table>')
    return ''.join(out)


def render_blocks(lines: list[str], offset: int = 1) -> str:
    """Small deterministic block parser. Containers may nest using 6>5>4>3 fences."""
    output: list[str] = []
    pos = 0

    def skip_empty() -> None:
        nonlocal pos
        while pos < len(lines) and not lines[pos].strip():
            pos += 1

    while pos < len(lines):
        skip_empty()
        if pos >= len(lines):
            break
        line = lines[pos]
        line_no = offset + pos
        match = FENCE.match(line)
        if match:
            length, spec = len(match[1]), match[2]
            if not spec:
                raise SlideSyntaxError(f'{line_no}行: 対応する開始コンテナがありません。')
            opening = parse_container(spec, line_no)
            content: list[str] = []
            pos += 1
            found_close = False
            nested: list[int] = []
            code_fence: tuple[str, int] | None = None
            while pos < len(lines):
                raw = lines[pos]
                code = CODE_FENCE.match(raw)
                if code:
                    sym = code[1][0]
                    if code_fence is None:
                        code_fence = (sym, len(code[1]))
                    elif sym == code_fence[0] and len(code[1]) >= code_fence[1] and not code[2].strip():
                        code_fence = None
                inner = FENCE.match(raw) if code_fence is None else None
                if inner:
                    inner_length = len(inner[1])
                    if inner[2]:
                        if inner_length >= (nested[-1] if nested else length):
                            raise SlideSyntaxError(f'{offset + pos}行: 子コンテナのコロン数は親より少なくしてください。')
                        nested.append(inner_length)
                    else:
                        if nested:
                            if inner_length != nested[-1]:
                                raise SlideSyntaxError(f'{offset + pos}行: 子コンテナの閉じ記号が一致しません。')
                            nested.pop()
                        else:
                            if inner_length != length:
                                raise SlideSyntaxError(f'{offset + pos}行: コンテナの閉じ記号が一致しません。')
                            found_close = True
                            break
                content.append(raw)
                pos += 1
            if not found_close:
                raise SlideSyntaxError(f'{line_no}行: コンテナを閉じてください（{":" * length}）。')
            pos += 1
            if 'class="slide-blank"' in opening:
                if any(item.strip() for item in content):
                    raise SlideSyntaxError(f'{line_no}行: blankコンテナに内容を入れられません。')
                output.append(opening)
            else:
                output.append(opening + render_blocks(content, line_no + 1) + '</div>')
            continue
        if DIRECTIVE.match(line):
            pos += 1
            continue
        if line.startswith('<!--') and line.strip().endswith('-->'):
            pos += 1
            continue
        heading = re.match(r'^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$', line)
        if heading:
            depth = len(heading[1])
            output.append(f'<h{depth}>{render_inline(heading[2])}</h{depth}>')
            pos += 1
            continue
        code = CODE_FENCE.match(line)
        if code:
            lang = re.match(r'^[\w+-]+', code[2].strip())
            language = lang[0] if lang else ''
            pos += 1
            rows = []
            while pos < len(lines):
                end = CODE_FENCE.match(lines[pos])
                if end and end[1][0] == code[1][0] and len(end[1]) >= len(code[1]) and not end[2].strip():
                    pos += 1
                    break
                rows.append(lines[pos])
                pos += 1
            output.append(f'<pre><code class="lang-{escape(language)}">{escape(chr(10).join(rows))}</code></pre>')
            continue
        if (line.strip().startswith('|') and pos + 1 < len(lines)
                and re.match(r'^\s*\|?[\s:|-]+\|?\s*$', lines[pos + 1])
                and '-' in lines[pos + 1]):
            rows = [line, lines[pos + 1]]
            pos += 2
            while pos < len(lines) and lines[pos].strip().startswith('|'):
                rows.append(lines[pos])
                pos += 1
            output.append(parse_table(rows))
            continue
        if re.match(r'^\s{0,3}>\s?', line):
            quotes: list[str] = []
            while pos < len(lines) and re.match(r'^\s{0,3}>\s?', lines[pos]):
                quotes.append(re.sub(r'^\s{0,3}>\s?', '', lines[pos]))
                pos += 1
            output.append('<blockquote>' + render_blocks(quotes, line_no) + '</blockquote>')
            continue
        listing = re.match(r'^\s{0,3}([-+*])\s+(.+)$', line)
        ordered = re.match(r'^\s{0,3}(\d+)[.)]\s+(.+)$', line)
        if listing or ordered:
            ordered_mode = bool(ordered)
            tag = 'ol' if ordered_mode else 'ul'
            items: list[str] = []
            while pos < len(lines):
                item = re.match(r'^\s{0,3}\d+[.)]\s+(.+)$' if ordered_mode else r'^\s{0,3}[-+*]\s+(.+)$', lines[pos])
                if not item:
                    break
                items.append('<li>' + render_inline(item[1]) + '</li>')
                pos += 1
            output.append('<' + tag + '>' + ''.join(items) + '</' + tag + '>')
            continue
        paragraph = [line.strip()]
        pos += 1
        while pos < len(lines):
            nxt = lines[pos]
            if (not nxt.strip() or FENCE.match(nxt) or DIRECTIVE.match(nxt) or CODE_FENCE.match(nxt)
                    or re.match(r'^\s{0,3}(?:#{1,6}\s+|[-+*]\s+|\d+[.)]\s+|>\s?)', nxt)
                    or nxt.strip().startswith('|')):
                break
            paragraph.append(nxt.strip())
            pos += 1
        output.append('<p>' + render_inline(' '.join(paragraph)) + '</p>')
    return '\n'.join(output)


def compile_deck(text: str) -> dict[str, Any]:
    meta, rows = read_frontmatter(text)
    slide_rows = split_slides(rows)
    slides = []
    for i, lines in enumerate(slide_rows):
        classes = []
        for line in lines:
            directive = DIRECTIVE.match(line)
            if directive:
                classes.extend(directive[1].split())
        # Untrusted attributes are never emitted directly.
        safe_classes = [x for x in classes if re.fullmatch(r'[a-zA-Z][a-zA-Z0-9-]*', x)]
        rendered = render_blocks(lines)
        title_match = re.search(r'<h1>(.*?)</h1>', rendered, flags=re.S)
        title = re.sub(r'<[^>]+>', '', html.unescape(title_match[1])) if title_match else meta.get('title', f'Slide {i + 1}')
        slides.append({'html': rendered, 'classes': safe_classes, 'title': title, 'index': i + 1})
    return {'slides': slides, 'meta': meta, 'count': len(slides)}


def main() -> int:
    try:
        request = json.load(sys.stdin)
        text = request.get('text', '')
        if not isinstance(text, str):
            raise SlideSyntaxError('textは文字列で指定してください。')
        if len(text) > 2_000_000:
            raise SlideSyntaxError('Markdownは2MB以内にしてください。')
        print(json.dumps({'ok': True, 'deck': compile_deck(text)}, ensure_ascii=False))
        return 0
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        return 0


if __name__ == '__main__':
    sys.exit(main())
