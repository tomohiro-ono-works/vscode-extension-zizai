"""Slide-only CSS design tokens -> Python geometry and PowerPoint values.

Uses the Python standard library; VS Code UI styles are intentionally excluded.
This is a supported-token CSS bridge, not a general CSS rendering engine.
"""
from __future__ import annotations
from pathlib import Path
import re

BUILTIN_SLIDE_CSS = Path(__file__).resolve().parent / 'assets' / 'slide.css'
BUILTIN_PRINT_CSS = Path(__file__).resolve().parent / 'assets' / 'print.css'
TOKEN = re.compile(r'--zs-([a-z][a-z0-9-]*)\s*:\s*([^;}{]+)')
CSS_COMMENTS = re.compile(r'/\*.*?\*/', re.S)
HEX = re.compile(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\Z')

class SlideStyle:
    def __init__(self, override: str | Path | None = None):
        self.base_css = BUILTIN_SLIDE_CSS.read_text('utf-8')
        self.extra_css = ''
        if override is not None:
            path = Path(override).expanduser().resolve()
            if not path.is_file():
                raise ValueError(f'スライド用CSSが見つかりません: {path}')
            if path.stat().st_size > 500_000:
                raise ValueError('スライド用CSSは500KB以内にしてください')
            self.extra_css = path.read_text('utf-8')
        self.object_rules = self._read_object_rules(self.extra_css)
        self.values = {name: value.strip() for name, value in
                       TOKEN.findall(CSS_COMMENTS.sub('', self.base_css))}
        allowed = set(self.values)
        for name, value in TOKEN.findall(CSS_COMMENTS.sub('', self.extra_css)):
            value = value.strip()
            if name not in allowed:
                raise ValueError(f'未対応のCSSトークン --zs-{name} です')
            if not re.fullmatch(r'(?:#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?|[0-9]+(?:\.[0-9]+)?(?:px|%))', value):
                raise ValueError(f'CSSトークン --zs-{name} は #RRGGBB / px / % にしてください: {value[:60]}')
            self.values[name] = value

    @staticmethod
    def _read_object_rules(extra_css: str) -> dict[str, dict[str, str]]:
        """Read explicit per-object slide CSS. This is a constrained CSS subset.

        Example: .slide .zs-headline {left:40px;top:60px;width:1100px;height:45px;
                                      font-size:26px;font-weight:700;color:#111111}
        Unknown object properties fail instead of silently diverging from PPTX.
        """
        clean = CSS_COMMENTS.sub('', extra_css)
        allowed = {
            'position', 'left', 'top', 'width', 'height', 'background-color',
            'color', 'font-size', 'font-weight', 'font-family', 'text-align',
            'vertical-align', 'border-radius', 'border-color', 'border-width',
            'box-shadow',
        }
        found: dict[str, dict[str, str]] = {}
        for selector, properties in re.findall(r'([^{}]+)\{([^{}]*)\}', clean):
            selector = selector.strip()
            match = re.fullmatch(r'\.slide(?:\.freeform)?\s+\.zs-([a-z][a-z0-9-]{0,63})', selector)
            if not match:
                continue
            key = match.group(1)
            rule: dict[str, str] = {}
            for item in properties.split(';'):
                if not item.strip():
                    continue
                if ':' not in item:
                    raise ValueError(f'CSSクラス zs-{key} のプロパティの形式が不正です')
                prop, value = (v.strip() for v in item.split(':', 1))
                if prop not in allowed:
                    raise ValueError(f'CSSクラス zs-{key} のプロパティ {prop} は未対応です')
                if not value:
                    raise ValueError(f'CSSクラス zs-{key} のプロパティ {prop} が空です')
                rule[prop] = value
            found.setdefault(key, {}).update(rule)
        return found

    def absolute(self, name: str) -> dict:
        """Resolve validated CSS geometry/paint for one editable object."""
        if name not in self.object_rules:
            raise ValueError(f'スライドCSSに .slide .zs-{name} の定義がありません')
        raw = self.object_rules[name]
        def numeric(key, default=None):
            value = raw.get(key)
            if value is None:
                if default is None:
                    raise ValueError(f'.zs-{name} に {key} がありません')
                return default
            if not re.fullmatch(r'-?\d+(?:\.\d+)?px', value):
                raise ValueError(f'.zs-{name} の {key} はpxで指定してください: {value}')
            return float(value[:-2])
        def color(key, default=None):
            value = raw.get(key, default)
            if value is None or value == 'transparent':
                return None
            if not HEX.fullmatch(value):
                raise ValueError(f'.zs-{name} の {key} は#RGBまたは#RRGGBBにしてください: {value}')
            digits = value.lstrip('#').upper()
            return ''.join(x*2 for x in digits) if len(digits) == 3 else digits
        size = numeric('font-size', 18.0)
        weight = raw.get('font-weight', '400').lower()
        if weight not in ('400', '500', '600', '700', '800', '900', 'normal', 'bold'):
            raise ValueError(f'.zs-{name} のfont-weightは400〜900等で指定してください')
        align = raw.get('text-align', 'left')
        valign = raw.get('vertical-align', 'top')
        if align not in ('left', 'center', 'right') or valign not in ('top', 'middle', 'bottom'):
            raise ValueError(f'.zs-{name} の揃え設定が未対応です')
        if raw.get('position', 'absolute') != 'absolute':
            raise ValueError(f'.zs-{name} のpositionはabsoluteにしてください')
        shadow = raw.get('box-shadow', 'none').strip().lower() != 'none'
        family = raw.get('font-family', 'Yu Gothic')
        if not re.fullmatch(r'[\w\s,\"\'-]{1,90}', family, re.UNICODE):
            raise ValueError(f'.zs-{name} のfont-familyが不正です')
        return dict(
            x=numeric('left'), y=numeric('top'), w=numeric('width'), h=numeric('height'),
            bg=color('background-color'), color=color('color', '#111111'),
            border=color('border-color'), border_width=numeric('border-width', 0.0),
            radius=numeric('border-radius', 0.0), font_size=size,
            font_family=family,
            bold=weight in ('600', '700', '800', '900', 'bold'),
            center=align == 'center', valign=valign, shadow=shadow,
        )

    def color(self, name, default):
        raw = self.values.get(name, '#'+default).strip()
        if not HEX.fullmatch(raw):
            raise ValueError(f'CSSトークン --zs-{name} には #RRGGBB を指定してください: {raw}')
        code = raw[1:].upper()
        return ''.join(ch*2 for ch in code) if len(code) == 3 else code

    def px(self, name, default):
        raw = self.values.get(name, str(default)+'px').strip()
        if not re.fullmatch(r'\d+(?:\.\d+)?px', raw):
            raise ValueError(f'CSSトークン --zs-{name} はpx単位で指定してください: {raw}')
        return float(raw[:-2])

    def percent(self, name, default):
        raw = self.values.get(name, str(default)+'%').strip()
        if not re.fullmatch(r'\d+(?:\.\d+)?%', raw):
            raise ValueError(f'CSSトークン --zs-{name} は%単位で指定してください: {raw}')
        value = float(raw[:-1])
        if not 10 <= value <= 90:
            raise ValueError(f'CSSトークン --zs-{name} は10〜90%の範囲にしてください')
        return value / 100

    def pair(self, classes, kind='card'):
        for hue in ('turquoise', 'aqua', 'gray', 'coral', 'mono', 'yellow'):
            for shade in ('light', 'dark'):
                if 'tone-' + hue + '-' + shade in classes:
                    return (self.color(f'{kind}-{hue}-{shade}-bg','FFFFFF'),
                            self.color(f'{kind}-{hue}-{shade}-ink','111111'),
                            None if shade == 'light' else self.color(f'{kind}-{hue}-{shade}-bg','FFFFFF'))
        return ('FFFFFF', self.color('ink', '111111'), self.color('card-border', '242424'))

    def html_css(self):
        # Only supported slide tokens propagate to output. Non-token CSS is not
        # silently applied to HTML alone, as that would break PPTX consistency.
        overrides = dict(TOKEN.findall(CSS_COMMENTS.sub('', self.extra_css)))
        serialized = ';'.join(f'--zs-{key}:{self.values[key]}' for key in overrides)
        return self.base_css + ('\n.slide{' + serialized + '}\n' if overrides else '')
