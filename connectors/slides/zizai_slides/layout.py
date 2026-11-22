"""Canonical pure-Python slide layout; preview and editable PPTX share geometry.

All dimensions are in logical CSS pixels on a 1280x720 canvas.  Objects are
independent, with explicitly wrapped text lines and native PowerPoint shapes.
Python standard library only; no browser or VS Code in this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from html import escape
import unicodedata
from typing import Any
from .style import SlideStyle, BUILTIN_PRINT_CSS

W, H = 1280, 720


@dataclass
class Node:
    tag: str
    text: str = ''
    attrs: dict[str, str] = field(default_factory=dict)
    children: list['Node'] = field(default_factory=list)

    def classes(self) -> set[str]:
        return set(self.attrs.get('class', '').split())


class TreeParser(HTMLParser):
    VOID = {'img', 'br', 'hr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('root')
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        node = Node(tag, attrs={k: v or '' for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.stack.pop()

    def handle_endtag(self, tag: str):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str):
        self.stack[-1].children.append(Node('#text', text=data))


def as_tree(markup: str) -> Node:
    parser = TreeParser()
    parser.feed(markup)
    parser.close()
    return parser.root


def plain(node: Node) -> str:
    if node.tag == '#text':
        return node.text
    if node.tag == 'br':
        return '\n'
    return ''.join(plain(c) for c in node.children)


def glyph_width(char: str, size: float, bold=False) -> float:
    """Conservative font-width estimator; one shared wrap for PPTX and preview.

    Fallback is deterministic across platforms. Width is intentionally reserved
    per glyph to reduce clipping on other Office font substitution engines.
    """
    if char == '\t':
        return size * 1.25
    if char.isspace():
        return size * .32
    east = unicodedata.east_asian_width(char)
    if east in ('W', 'F'):
        return size * 1.03
    if east == 'A':
        return size * .86
    if char in 'ilI|.,;:!\'`':
        return size * .32
    if char in 'MW@%#&':
        return size * .85
    if char.isupper():
        return size * .68
    return size * (.58 if bold else .55)


class Layout:
    def __init__(self, slide: dict, index: int, total: int, footer: str, theme: SlideStyle):
        self.slide = slide
        self.theme = theme
        self.ink = theme.color('ink', '111111')
        self.body_size = theme.px('body-font-size', 23)
        self.pad_x = theme.px('canvas-padding-x', 42)
        self.pad_top = theme.px('canvas-padding-top', 36)
        self.gap = theme.px('layout-gap', 18)
        self.index = index
        self.total = total
        self.footer = footer
        self.shapes: list[dict] = []
        self.texts: list[dict] = []
        self.images: list[dict] = []
        self.warnings: list[str] = []
        classes = set(slide.get('classes', []))
        self.bg = theme.color('background-gray', 'FBFBFB') if 'gray' in classes else theme.color('background', 'FFFFFF')
        self.hero = 'cover' in classes or 'chapter' in classes
        self.chapter = 'chapter' in classes
        self.message = 'message' in classes
        self.freeform = 'freeform' in classes
        self.page_start = int(slide.get('page_start', 1))
        self.add_rect(0, 0, W, H, self.bg, 'Background')
        # Freeform slides do not inherit the ordinary corner marks or progress bar.
        if not self.freeform:
            self.add_rect(1233, 29, 2, 20, theme.color('line', '242424'), 'Corner mark')
            self.add_rect(1233, 29, 19, 2, theme.color('line', '242424'), 'Corner mark')
            self.add_rect(0, 713, W, 7, theme.color('track', 'D9DDE4'), 'Progress track')
            self.add_rect(0, 713, W * index / max(1, total), 7, theme.color('navy', '1B2B45'), 'Progress')
        if footer:
            self.draw_text(footer, self.pad_x, 681, 950, 12, theme.color('muted', '777777'), name='Footer')

    def add_rect(self, x, y, w, h, fill, name, radius=0, border=None, shadow=False, border_width=1.5):
        if w <= 0 or h <= 0:
            return
        self.shapes.append({'kind': 'rect', 'x': round(x, 2), 'y': round(y, 2),
                            'w': round(w, 2), 'h': round(h, 2), 'fill': fill,
                            'radius': radius, 'borderColor': border,
                            'borderWidth': border_width if border else 0, 'shadow': shadow, 'name': name})

    def draw_text(self, text, x, y, w, size, color='111111', bold=False,
                  name='Text', center=False):
        if not text or w < 1:
            return 0
        size = float(size)
        line_height = size * 1.37
        lines: list[str] = []
        current = ''
        width = 0.0
        for char in str(text):
            if char == '\n':
                lines.append(current)
                current, width = '', 0
                continue
            add = glyph_width(char, size, bold)
            if width + add > w - 2 and current:
                lines.append(current.rstrip())
                current, width = char.lstrip(), add
            else:
                current += char
                width += add
        if current or not lines:
            lines.append(current)
        for n, line in enumerate(lines):
            if not line:
                continue
            self.texts.append({'x': round(x, 2), 'y': round(y + n * line_height, 2),
                               'w': round(w, 2), 'h': round(line_height + 2, 2),
                               'fontSize': size, 'text': line, 'bold': bool(bold),
                               'color': color, 'name': name, 'center': center})
        return len(lines) * line_height

    def inline_tokens(self, node: Node, size: float, color: str, bold=False):
        """Extract text, bold and independently colored inline pill tokens."""
        if node.tag == '#text':
            return [{'text': node.text, 'size': size, 'bold': bold, 'color': color}]
        if node.tag == 'br':
            return [{'text': '\n', 'size': size, 'bold': bold, 'color': color}]
        cls = node.classes()
        if 'slide-chip' in cls:
            fill, ink, _ = self.theme.pair(cls, 'chip')
            return [{'chip': True, 'text': plain(node), 'size': 18, 'bold': True, 'color': ink, 'fill': fill}]
        if node.tag == 'img':
            return [{'image': node.attrs.get('data-local-path', ''), 'alt': node.attrs.get('alt', '')}]
        child_size = size * .86 if node.tag == 'code' else size
        child_color = self.theme.color('link', '167D86') if node.tag == 'a' else color
        return [t for child in node.children for t in self.inline_tokens(child, child_size, child_color, bold or node.tag in ('strong', 'b'))]

    def inline(self, node: Node, x: float, y: float, w: float, size: float, color='111111', bold=False,
               line_height=None, name='Text', center=False) -> float:
        tokens = self.inline_tokens(node, size, color, bold)
        lh = line_height or size * 1.40
        cx = 0.0
        cy = 0.0
        items = []
        def flush():
            nonlocal items
            if center:
                total_width = sum(k['w'] for k in items)
                shift = max(0, (w - total_width) / 2)
            else:
                shift = 0
            for data in items:
                dx = x + data['pos'] + shift
                if data.get('chip'):
                    self.add_rect(dx, y + cy + 2, data['w'], max(20, lh - 4), data['fill'], 'Label', radius=self.theme.px('chip-radius', 11))
                    self.texts.append({'x': round(dx + 8, 2), 'y': round(y + cy + 2, 2),
                        'w': round(data['w'] - 16, 2), 'h': round(max(20, lh - 2), 2),
                        'text': data['text'], 'fontSize': self.theme.px('chip-font-size', 16), 'bold': True, 'color': data['color'], 'name': 'Label text'})
                else:
                    self.texts.append({'x': round(dx, 2), 'y': round(y + cy, 2),
                        'w': round(data['w'] + 5, 2), 'h': round(lh + 3, 2),
                        'text': data['text'], 'fontSize': data['size'],
                        'bold': data['bold'], 'color': data['color'], 'name': name})
            items = []
        # Text groups are grouped by style and wrap at explicit glyph positions.
        for token in tokens:
            if 'image' in token:
                flush()
                if cx > 0:
                    cy += lh; cx = 0
                self.images.append({'x': round(x, 2), 'y': round(y + cy, 2),
                    'w': min(w, 460), 'h': 220, 'path': token['image']})
                cy += 220
                continue
            if token.get('chip'):
                text = token['text']
                chip_w = sum(glyph_width(ch, 16, True) for ch in text) + 18
                if cx > 0 and cx + chip_w > w:
                    flush(); cy += lh; cx = 0
                items.append(dict(token, w=chip_w, pos=cx))
                cx += chip_w + 5
                continue
            text = token['text']
            if not text:
                continue
            group = ''
            group_start = cx
            for ch in text:
                if ch == '\n':
                    if group:
                        items.append(dict(token, text=group, w=cx - group_start, pos=group_start))
                    group = ''
                    flush(); cy += lh; cx = 0; group_start = 0
                    continue
                g = glyph_width(ch, token['size'], token['bold'])
                if cx > 0 and cx + g > w:
                    if group:
                        items.append(dict(token, text=group, w=cx - group_start, pos=group_start))
                        group = ''
                    flush(); cy += lh; cx = 0; group_start = 0
                    if ch.isspace():
                        continue
                if not group:
                    group_start = cx
                group += ch
                cx += g
            if group:
                items.append(dict(token, text=group, w=cx - group_start, pos=group_start))
        flush()
        return cy + lh if tokens else 0

    def absolute_item(self, node: Node) -> float:
        """Place one named Markdown object using only its slide CSS rule."""
        c = node.classes()
        names = [name[3:] for name in c if name.startswith('zs-')]
        if len(names) != 1:
            raise ValueError('絶対配置オブジェクトにはCSS名が1つ必要です')
        name = names[0]
        rule = self.theme.absolute(name)
        x, y, w, h = (rule[k] for k in ('x', 'y', 'w', 'h'))
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > W + .01 or y + h > H + .01:
            self.warnings.append(f'オブジェクト {name} がスライドの外にはみ出しています')
        if len(self.shapes) + len(self.texts) > 500:
            raise ValueError('1枚のスライドのオブジェクトは500個以内にしてください')
        label = plain(node).strip()
        if 'slide-abs-box' in c or 'slide-abs-shape' in c:
            fill = rule['bg']
            if fill is not None:
                self.add_rect(x, y, w, h, fill, name, radius=rule['radius'],
                              border=rule['border'], border_width=rule['border_width'],
                              shadow=rule['shadow'])
        if label and 'slide-abs-shape' not in c:
            font = rule['font_size']
            estimated = self.estimate_text_height(label, w - 8, font)
            if estimated > h + 5:
                self.warnings.append(f'テキスト {name} の高さがCSSの範囲を超えています')
            dy = 0
            if rule['valign'] == 'middle':
                dy = max(0, (h - estimated) / 2)
            elif rule['valign'] == 'bottom':
                dy = max(0, h - estimated)
            prior = len(self.texts)
            self.draw_text(label, x + 3, y + dy, max(5,w - 6), font,
                           color=rule['color'], bold=rule['bold'],
                           name=name, center=rule['center'])
            for text_item in self.texts[prior:]:
                text_item['fontFamily'] = rule['font_family']
        return 0

    def item(self, node: Node, x: float, y: float, w: float,
             ink='111111', font=23, top=False, parent_h=None) -> float:
        c = node.classes()
        if 'slide-absolute' in c:
            return self.absolute_item(node)
        if node.tag == '#text':
            if not node.text.strip():
                return 0
            return self.draw_text(node.text.strip(), x, y, w, font, ink)
        if node.tag in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'):
            if node.tag == 'h1':
                size, bold, before, after = self.theme.px('title-font-size', 36), True, 4, 17
                mark = self.theme.px('title-mark-width', 10)
                # A hero has no headline marker; panels own their title styling.
                if not self.hero:
                    self.add_rect(x, y + 8, mark, 37, self.ink, 'Title bar')
                    x += 20; w -= 20
            elif node.tag == 'h2':
                size, bold, before, after = self.theme.px('h2-font-size', 27), True, 16, 9
            elif node.tag in ('h3', 'h4', 'h5', 'h6'):
                size, bold, before, after = self.theme.px('h3-font-size', 23), True, 8, 7
            else:
                size, bold, before, after = (21 if top else font), False, 6, 7
            if node.tag == 'li':
                x += 26; w -= 26
            if node.tag == 'p' and any(ch.tag == 'strong' for ch in node.children) and font <= 20:
                size = self.theme.px('h3-font-size', 23)
            hh = self.inline(node, x, y + before, w, size, ink, bold, name=node.tag)
            return hh + before + after
        if node.tag in ('ul', 'ol'):
            pos = y + 6
            for i, ch in enumerate(node.children):
                if ch.tag == 'li':
                    self.draw_text(f'{i + 1}.' if node.tag == 'ol' else '•', x + 8, pos + 3, 25, font, ink, True, 'List marker')
                    pos += self.item(ch, x + 16, pos, w - 16, ink, font)
            return pos - y + 6
        if node.tag == 'pre':
            code = plain(node).strip('\n')
            width = w
            lines = code.split('\n')
            size = 17
            required = max(56, 26 + len(lines) * size * 1.42)
            self.add_rect(x, y + 5, width, required, self.theme.color('code-background', 'F2F4F6'), 'Code block', radius=8)
            for j, line in enumerate(lines):
                self.draw_text(line, x + 16, y + 16 + j * size * 1.42, width - 32, size, '1B2B45', name='Code')
            return required + 12
        if node.tag == 'table':
            rows = [c for part in node.children for c in (part.children if part.tag in ('thead', 'tbody') else [part]) if c.tag == 'tr']
            if not rows:
                return 0
            count = max(1, max(sum(1 for x in row.children if x.tag in ('th', 'td')) for row in rows))
            cw = w / count
            pos = y + 6
            for row_num, row in enumerate(rows):
                cells = [z for z in row.children if z.tag in ('th', 'td')]
                row_heights = [max(39, self.estimate_text_height(plain(z), cw - 22, 18) + 16) for z in cells]
                rh = max(row_heights or [39])
                for j, cell in enumerate(cells):
                    bg = self.theme.color('table-header-background', 'F2F2F2') if row_num == 0 or j == 0 else self.theme.color('background', 'FFFFFF')
                    self.add_rect(x + j * cw, pos, cw, rh, bg, 'Table cell', border=self.theme.color('table-border', 'A9ADB0'))
                    self.inline(cell, x + j * cw + 10, pos + 7, cw - 20, 18, '111111', row_num == 0 or j == 0, name='Table text')
                pos += rh
            return pos - y + 8
        if node.tag == 'blockquote' or 'slide-card' in c or 'slide-paper' in c:
            card = 'slide-card' in c or node.tag == 'blockquote'
            pad = (self.theme.px('card-padding-x', 21), self.theme.px('card-padding-y', 18)) if card else (self.theme.px('paper-padding', 32), self.theme.px('paper-padding', 32))
            ix, iy = pad
            bg, fg, border = self.theme.pair(c, 'card') if card else (self.theme.color('background','FFFFFF'), self.ink, self.theme.color('track','D9DDE4'))
            if node.tag == 'blockquote' or 'slide-paper' in c:
                pass
            inner_w = max(20, w - 2 * ix)
            needed = self.estimate_children(node.children, inner_w, fg, self.theme.px('card-font-size', 20) if card else font)
            h = max((needed + 2 * iy), 64 if card else 120)
            if parent_h is not None:
                h = max(h, parent_h)
            if y + h > 705:
                self.warnings.append('カードがスライド範囲を超えています')
            self.add_rect(x, y, w, h, bg, 'Card' if card else 'Paper', radius=self.theme.px('card-radius', 9), border=border,
                          shadow=('mod-hover' in c))
            self.children(node.children, x + ix, y + iy, inner_w, fg, self.theme.px('card-font-size', 20) if card else font)
            return h
        if 'slide-blank' in c:
            return parent_h or 1
        if 'slide-layout' in c or 'slide-hero' in c:
            children = [ch for ch in node.children if ch.tag != '#text' or ch.text.strip()]
            horizontal = 'slide-h' in c or 'slide-hero' in c
            gap = 0 if self.hero and horizontal else self.gap
            start = y + (5 if not self.hero else 0)
            if horizontal:
                ratio = self.theme.percent('hero-left-percent', 40)
                weights = [ratio, 1-ratio] if 'slide-hero' in c else [1 / len(children)] * len(children) if children else []
                usable = w - gap * max(0, len(children) - 1)
                widths = [usable * z / sum(weights) for z in weights] if weights else []
                heights = [self.estimate(ch, max(10, widths[i])) for i, ch in enumerate(children)]
                height = max([*heights, 183 if 'mod-medium' in c else 0, 355 if 'mod-tall' in c else 0, 1])
                xx = x
                for i, ch in enumerate(children):
                    stretch = height if ('slide-card' in ch.classes() or 'slide-blank' in ch.classes()) else None
                    if self.hero and 'slide-hero-media' in ch.classes():
                        color = self.theme.color('chapter-left-background','1B2B45') if self.chapter else self.theme.color('cover-left-background','F1F1F1')
                        self.add_rect(xx, start, widths[i], H, color, 'Hero media panel')
                    self.item(ch, xx, start, widths[i], ink, font, parent_h=stretch)
                    xx += widths[i] + gap
                if 'mod-flow' in c:
                    xx = x
                    for aw in widths[:-1]:
                        xx += aw
                        self.draw_text('→', xx + 3, start + height / 2 - 15, gap - 4, 25, self.theme.color('navy','1B2B45'), True, 'Flow arrow')
                        xx += gap
                return height + (10 if not self.hero else 0)
            else:
                pos = start
                heights = [self.estimate(ch, w) for ch in children]
                minheight = 183 if 'mod-medium' in c else 355 if 'mod-tall' in c else 0
                extra = max(0, minheight - sum(heights) - gap * max(0, len(heights)-1))
                for i, ch in enumerate(children):
                    h = heights[i] + (extra / len(heights) if 'mod-equal' in c and heights else 0)
                    self.item(ch, x, pos, w, ink, font, parent_h=h if 'slide-card' in ch.classes() else None)
                    pos += h + gap
                return pos - y - (gap if children else 0) + 5
        if node.tag == 'div' and ('slide-hero-copy' in c or 'slide-hero-media' in c):
            if 'slide-hero-media' in c and self.chapter:
                ink = 'FFFFFF'
            children = [ch for ch in node.children if ch.tag != '#text' or ch.text.strip()]
            inside_w = max(1, w - 80)
            required = self.estimate_children(children, inside_w, ink, self.body_size)
            yy = max(0, (H - required) / 2)
            return self.children(children, x + 40, yy, inside_w, ink, self.body_size)
        if node.tag == 'div':
            return self.children(node.children, x, y, w, ink, font)
        if node.tag == 'img':
            p = node.attrs.get('data-local-path', '')
            self.images.append({'path': p, 'x': x, 'y': y, 'w': min(w, 480), 'h': 240})
            return 246
        return self.children(node.children, x, y, w, ink, font)

    def estimate_text_height(self, text, width, size):
        lines = 1
        current = 0
        for ch in text:
            if ch == '\n':
                lines += 1; current = 0
            else:
                add = glyph_width(ch, size)
                if current > 0 and current + add > max(20, width):
                    lines += 1; current = 0
                current += add
        return lines * size * 1.4

    def estimate_children(self, nodes, w, ink, font):
        # Match the block spacings used by item(); all layout is computed here,
        # never in the VS Code Webview or browser.
        return sum(self.estimate(n, w, ink, font) for n in nodes)

    def estimate(self, node: Node, w, ink='111111', font=23):
        c = node.classes()
        if 'slide-absolute' in c:
            return 0
        if node.tag == '#text':
            return self.estimate_text_height(node.text.strip(), w, font) if node.text.strip() else 0
        if node.tag in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'):
            if node.tag == 'h1': size, pre, post = self.theme.px('title-font-size',36), 4, 17; w -= (0 if self.hero else 20)
            elif node.tag == 'h2': size, pre, post = self.theme.px('h2-font-size',27), 16, 9
            elif node.tag in ('h3','h4','h5','h6'): size, pre, post = self.theme.px('h3-font-size',23), 8, 7
            else: size, pre, post = (23 if any(x.tag == 'strong' for x in node.children) and font<=20 else font), 6, 7
            return pre + self.estimate_text_height(plain(node), w, size) + post
        if node.tag in ('ul', 'ol'):
            return 12 + sum(self.estimate(child, w - 42, ink, font) for child in node.children)
        if node.tag == 'pre':
            return max(56, 26 + len(plain(node).strip('\n').split('\n')) * 17 * 1.42) + 12
        if node.tag == 'table':
            rows = [c for part in node.children for c in (part.children if part.tag in ('thead','tbody') else [part]) if c.tag == 'tr']
            columns = max(1,max((len(r.children) for r in rows),default=1))
            return 14 + sum(max([max(39,self.estimate_text_height(plain(z), w/columns-22,18)+16) for z in row.children] or [39]) for row in rows)
        if node.tag == 'blockquote' or 'slide-card' in c or 'slide-paper' in c:
            pad = self.theme.px('card-padding-x',21) if node.tag == 'blockquote' or 'slide-card' in c else self.theme.px('paper-padding',32)
            py = self.theme.px('card-padding-y',18) if node.tag == 'blockquote' or 'slide-card' in c else self.theme.px('paper-padding',32)
            is_card = node.tag == 'blockquote' or 'slide-card' in c
            return max(64 if is_card else 120, self.estimate_children(node.children, max(20,w-2*pad), ink, self.theme.px('card-font-size',20) if is_card else font)+2*py)
        if 'slide-blank' in c:
            return 1
        if 'slide-layout' in c or 'slide-hero' in c:
            nodes = [ch for ch in node.children if ch.tag != '#text' or ch.text.strip()]
            if 'slide-h' in c or 'slide-hero' in c:
                if not nodes:return 0
                ratio=self.theme.percent('hero-left-percent',40)
                weights=[ratio,1-ratio] if 'slide-hero' in c else [1/len(nodes)]*len(nodes)
                usable=w-(0 if self.hero else self.gap)*(len(nodes)-1)
                ww=[usable*z/sum(weights) for z in weights]
                return max([self.estimate(ch,ww[i],ink,font) for i,ch in enumerate(nodes)]+[183 if 'mod-medium' in c else 355 if 'mod-tall' in c else 1])+10
            return sum(self.estimate(ch,w,ink,font) for ch in nodes)+self.gap*max(0,len(nodes)-1)+10
        if 'slide-hero-copy' in c or 'slide-hero-media' in c:
            return self.estimate_children(node.children,max(20,w-80),ink,font)
        if node.tag == 'img':return 246
        return self.estimate_children(node.children,w,ink,font)

    def children(self, nodes, x, y, w, ink='111111', font=23):
        pos = y
        nodes = [n for n in nodes if n.tag != '#text' or n.text.strip()]
        for i, child in enumerate(nodes):
            is_lead = i == 1 and nodes[0].tag == 'h1' and child.tag == 'p'
            if is_lead:
                consumed = self.item(child, x+10, pos, w-10, ink, 21, top=True) + 16
            else:
                consumed = self.item(child, x, pos, w, ink, font)
            pos += consumed
        return pos-y

    def compose(self) -> dict[str, Any]:
        root = as_tree(self.slide.get('html',''))
        nodes = [n for n in root.children if n.tag != '#text' or n.text.strip()]
        headers = [n for n in nodes if 'slide-header' in n.classes()]
        bodies = [n for n in nodes if 'slide-body' in n.classes()]
        if headers or bodies:
            # A sectioned slide reserves a dedicated header band, then places
            # the body below it. Both HTML and editable PPTX use this geometry.
            if len(headers) > 1 or len(bodies) > 1:
                raise ValueError('1枚のスライドにheader/bodyはそれぞれ1つまで指定できます')
            if len(headers) + len(bodies) != len(nodes):
                raise ValueError('header/bodyを使用する場合は、スライド直下の内容を各コンテナ内に記述してください')
            region_width = W - 2 * self.pad_x
            if headers:
                head_height = self.item(headers[0], self.pad_x, self.pad_top,
                                        region_width, self.ink, self.body_size)
                allowed = self.theme.px('header-height', 140)
                if head_height > allowed + 1:
                    self.warnings.append(f'headerの内容が指定高さを超えています（{int(head_height)}px > {int(allowed)}px）')
            if bodies:
                body_top = (self.pad_top + self.theme.px('header-height', 140)
                            + self.theme.px('header-body-gap', 14))
                body_height = self.item(bodies[0], self.pad_x, body_top,
                                        region_width, self.ink, self.body_size)
                if body_top + body_height > 675:
                    self.warnings.append(f'bodyが下端を超えています（下端 {int(body_top + body_height)}px）')
        elif self.freeform:
            self.children(root.children, 0, 0, W, self.ink, self.body_size)
        elif self.hero:
            self.children(root.children, 0, 0, W, self.ink, self.body_size)
        else:
            height = self.children(root.children, self.pad_x, self.pad_top, W - 2*self.pad_x, self.ink, self.body_size)
            if self.pad_top + height > 675:
                self.warnings.append(f'本文が下端を超えています（高さ {int(height)}px）')
        # Pagination is part of the slide, not the VS Code UI. Use the same
        # canonical coordinates for browser preview and editable PowerPoint.
        if self.slide.get('show_page_number', True):
            size = self.theme.px('page-number-font-size', 12)
            right = self.theme.px('page-number-right', 42)
            bottom = self.theme.px('page-number-bottom', 17)
            color = self.theme.color('page-number-color', '777777')
            number = str(self.index + self.page_start - 1)
            width = sum(glyph_width(ch, size) for ch in number) + 7
            x = W - right - width
            y = H - bottom - size * 1.37 - 3
            if x < W / 2 or y < 0:
                self.warnings.append('ページ番号のCSS指定がキャンバス範囲を超えています')
            else:
                self.draw_text(number, x, y, width, size, color, name='Page number')

        # All colors and coordinates are stable and serializable; no browser measurement.
        return {'width': W, 'height': H, 'shapes': self.shapes,
                'texts': self.texts, 'images': self.images, 'warnings': list(dict.fromkeys(self.warnings))}


def layout_deck(deck: dict, style: SlideStyle | None = None) -> list[dict]:
    slides = deck.get('slides', [])
    footer = str(deck.get('meta', {}).get('footer', ''))
    style = style or SlideStyle()
    # Match the existing Markdown front matter. Missing paginate enables the
    # default page-number footer; explicit false/off/0 disables it.
    paginate = str(deck.get('meta', {}).get('paginate', 'true')).strip().lower()
    if paginate not in ('true', 'false', 'yes', 'no', '1', '0', 'on', 'off'):
        raise ValueError('paginateにはtrueまたはfalseを指定してください')
    show_numbers = paginate in ('true', 'yes', '1', 'on')
    first = str(deck.get('meta', {}).get('page_start', '1')).strip()
    if not first.isdigit() or not 1 <= int(first) <= 9999:
        raise ValueError('page_startは1〜9999の整数にしてください')
    return [Layout({**slide, 'show_page_number': show_numbers, 'page_start': int(first)}, i+1, len(slides), footer, style).compose()
            for i, slide in enumerate(slides)]


def slide_to_html(layout: dict, title='Slide') -> str:
    """Self-contained HTML rendering from the same object coordinates as PPTX."""
    pieces = [f'<section class="slide" aria-label="{escape(title,quote=True)}">']
    for item in layout['shapes']:
        style = (f'position:absolute;left:{item["x"]}px;top:{item["y"]}px;'
                 f'width:{item["w"]}px;height:{item["h"]}px;background:#{item["fill"]};'
                 f'border-radius:{item.get("radius",0)}px;'
                 + (f'border:{item.get("borderWidth",0)}px solid #{item["borderColor"]};' if item.get('borderColor') else '')
                 + ('box-shadow:0 7px 10px -5px #1B2B4533;' if item.get('shadow') else ''))
        pieces.append(f'<div style="{style}"></div>')
    for item in layout['texts']:
        style=(f'position:absolute;left:{item["x"]}px;top:{item["y"]}px;'
               f'width:{item["w"]}px;height:{item["h"]}px;overflow:visible;white-space:pre;'
               f'font-size:{item["fontSize"]}px;line-height:1.37;color:#{item["color"]};'
               f'font-weight:{700 if item.get("bold") else 400};'
               f'font-family:{escape(item.get("fontFamily", "Yu Gothic"), quote=True)};'
               f'text-align:{"center" if item.get("center") else "left"};')
        pieces.append(f'<div style="{style}">{escape(item["text"])}</div>')
    for item in layout['images']:
        src = escape(item.get('src', ''),quote=True)
        if src:
            pieces.append(f'<img src="{src}" style="position:absolute;object-fit:contain;left:{item["x"]}px;top:{item["y"]}px;width:{item["w"]}px;height:{item["h"]}px">')
    pieces.append('</section>')
    return ''.join(pieces)


def document_html(deck: dict, layouts: list[dict], style: SlideStyle | None = None) -> str:
    slides = '\n'.join(slide_to_html(layout,slide.get('title','Slide')) for layout,slide in zip(layouts,deck['slides']))
    style = style or SlideStyle()
    from html import escape as html_escape
    slide_css = style.html_css().replace('</style', '<\\/style')
    print_css = BUILTIN_PRINT_CSS.read_text('utf-8')
    return ('<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">'
            '<title>Zizai Slides</title><style>'
            '@page{size:13.333333in 7.5in;margin:0}'
            'html,body{margin:0;background:#ddd}'
            '.slide{width:1280px;height:720px;position:relative;box-sizing:border-box;'
            'font-family:"Yu Gothic","Meiryo",sans-serif;overflow:hidden;'
            'background:#fff;break-after:page;page-break-after:always;}'
            '@media print{html,body{background:#fff}}'
            '</style><style>' + slide_css + '</style><style>' + print_css + '</style></head><body>'+slides+'</body></html>')
