"""Export Zizai slides to PowerPoint using only Python's standard library.

Two export modes:
- image: browser-rendered PNG occupies each slide (pixel fidelity; content uneditable).
- editable: Python-computed geometry produces native editable PowerPoint
  shapes and text (one geometry source shared with the preview HTML).

No third-party Python package, COM, network service or PowerPoint installation required.
For image mode, an installed Microsoft Edge or Chrome is needed to take screenshots.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

try:
    from .export_pdf import browser_candidates
except ImportError:  # Direct invocation by VS Code
    from export_pdf import browser_candidates

EMU = 9525  # PowerPoint 1280 × 720 at 96 CSS px per inch.
SW, SH = 1280, 720
NS_P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
NS_A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
NS_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_PR = 'http://schemas.openxmlformats.org/package/2006/relationships'
NS_CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
for prefix, namespace in [('p', NS_P), ('a', NS_A), ('r', NS_R)]:
    ET.register_namespace(prefix, namespace)

def q(ns: str, name: str) -> str:
    return '{' + ns + '}' + name

def element(ns: str, name: str, attrs=None, parent=None):
    el = ET.Element(q(ns, name), attrs or {})
    if parent is not None:
        parent.append(el)
    return el

def sub(parent, ns: str, tag: str, attributes=None, **attrs):
    combined = dict(attributes or {})
    combined.update({k: str(v) for k, v in attrs.items()})
    return element(ns, tag, combined, parent)

def xml(value) -> bytes:
    return ET.tostring(value, encoding='utf-8', xml_declaration=True)

def bound(n, a, b): return max(a, min(b, n))
def cx(x): return str(int(round(max(0, x) * EMU)))
def normalize_hex(color: str):
    color = color.lstrip('#').upper()
    return color if re.fullmatch(r'[0-9A-F]{6}', color) else '111111'

def fill(parent, color):
    f = sub(parent, NS_A, 'solidFill')
    sub(f, NS_A, 'srgbClr', val=normalize_hex(color))

def geometry(parent, x, y, w, h, kind='rect'):
    transform = sub(parent, NS_A, 'xfrm')
    sub(transform, NS_A, 'off', x=cx(x), y=cx(y))
    sub(transform, NS_A, 'ext', cx=cx(max(0.1, w)), cy=cx(max(0.1, h)))
    prst = sub(parent, NS_A, 'prstGeom', prst=kind)
    sub(prst, NS_A, 'avLst')

class SlideDrawing:
    def __init__(self, title='Slide'):
        self.title = title
        self.root = element(NS_P, 'sld')
        csld = sub(self.root, NS_P, 'cSld', name=title[:100])
        tree = sub(csld, NS_P, 'spTree')
        grp = sub(tree, NS_P, 'nvGrpSpPr')
        sub(grp, NS_P, 'cNvPr', id=1, name='')
        sub(grp, NS_P, 'cNvGrpSpPr')
        sub(grp, NS_P, 'nvPr')
        grppr = sub(tree, NS_P, 'grpSpPr')
        tf = sub(grppr, NS_A, 'xfrm')
        for nm in ('off', 'ext', 'chOff', 'chExt'):
            sub(tf, NS_A, nm, **({'x': 0, 'y': 0} if nm in ('off', 'chOff') else {'cx': 0, 'cy': 0}))
        self.tree = tree
        self.next_id = 2
        self.images: list[tuple[str, bytes, str]] = []
        over = sub(self.root, NS_P, 'clrMapOvr')
        sub(over, NS_A, 'masterClrMapping')

    def rect(self, x, y, w, h, color='FFFFFF', line=None, radius=0, name='Rectangle'):
        if w <= 0 or h <= 0:
            return
        sp = sub(self.tree, NS_P, 'sp')
        nv = sub(sp, NS_P, 'nvSpPr')
        sub(nv, NS_P, 'cNvPr', id=self.next_id, name=f'{name} {self.next_id}')
        self.next_id += 1
        sub(nv, NS_P, 'cNvSpPr')
        sub(nv, NS_P, 'nvPr')
        props = sub(sp, NS_P, 'spPr')
        geometry(props, x, y, w, h, 'roundRect' if radius else 'rect')
        fill(props, color)
        if line:
            ln = sub(props, NS_A, 'ln', w='9000')
            fill(ln, line)
        else:
            sub(props, NS_A, 'ln')
            sub(props[-1], NS_A, 'noFill')
        return sp

    def textbox(self, x, y, w, h, runs, size=20, color='111111', bold=False, valign='top', name='Text'):
        if w <= 0 or h <= 0:
            return
        sp = sub(self.tree, NS_P, 'sp')
        nv = sub(sp, NS_P, 'nvSpPr')
        sub(nv, NS_P, 'cNvPr', id=self.next_id, name=f'{name} {self.next_id}')
        self.next_id += 1
        sub(nv, NS_P, 'cNvSpPr', txBox='1')
        sub(nv, NS_P, 'nvPr')
        props = sub(sp, NS_P, 'spPr')
        geometry(props, x, y, w, h)
        sub(props, NS_A, 'noFill')
        tx = sub(sp, NS_P, 'txBody')
        sub(tx, NS_A, 'bodyPr', wrap='square', anchor='ctr' if valign == 'middle' else 't', lIns='0', rIns='0', tIns='0', bIns='0')
        sub(tx, NS_A, 'lstStyle')
        paragraph = sub(tx, NS_A, 'p')
        for chunk in runs if isinstance(runs, list) else [{'text': str(runs)}]:
            text = chunk.get('text', '')
            if not text: continue
            for i, part in enumerate(text.split('\n')):
                if i: sub(paragraph, NS_A, 'br')
                if not part: continue
                run = sub(paragraph, NS_A, 'r')
                rp = sub(run, NS_A, 'rPr', lang='ja-JP', sz=int(chunk.get('size', size) * 75), b='1' if chunk.get('bold', bold) else '0')
                fc = sub(rp, NS_A, 'solidFill')
                sub(fc, NS_A, 'srgbClr', val=normalize_hex(chunk.get('color', color)))
                sub(rp, NS_A, 'latin', typeface='Yu Gothic')
                sub(rp, NS_A, 'ea', typeface='Yu Gothic')
                elem = sub(run, NS_A, 't')
                elem.text = part
                elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        sub(paragraph, NS_A, 'endParaRPr', lang='ja-JP')
        return sp

    def picture(self, x, y, w, h, data: bytes, ext: str):
        if ext not in ('png', 'jpg', 'jpeg', 'gif'):
            return
        if not data or len(data) > 12_000_000:
            return
        n = len(self.images) + 1
        r_id = f'rId{n+1}'
        name = f'Image {self.next_id}'
        pic = sub(self.tree, NS_P, 'pic')
        nv = sub(pic, NS_P, 'nvPicPr')
        sub(nv, NS_P, 'cNvPr', id=self.next_id, name=name)
        self.next_id += 1
        sub(nv, NS_P, 'cNvPicPr')
        sub(nv, NS_P, 'nvPr')
        blip_fill = sub(pic, NS_P, 'blipFill')
        sub(blip_fill, NS_A, 'blip', {q(NS_R, 'embed'): r_id})
        stretch = sub(blip_fill, NS_A, 'stretch')
        sub(stretch, NS_A, 'fillRect')
        props = sub(pic, NS_P, 'spPr')
        geometry(props, x, y, w, h)
        self.images.append((f'image{n}.{ext}', data, r_id))

    def done(self) -> bytes:
        return xml(self.root)


# ------- Open XML Presentation package ------------------------------------

def relationship_list(entries):
    ET.register_namespace('', NS_PR)
    root=ET.Element(q(NS_PR,'Relationships'))
    for idx,(type_name,target) in enumerate(entries,1):
        prefix = ('http://schemas.openxmlformats.org/package/2006/relationships/'
                  if type_name == 'metadata/core-properties' else
                  'http://schemas.openxmlformats.org/officeDocument/2006/relationships/')
        ET.SubElement(root,q(NS_PR,'Relationship'),{'Id':f'rId{idx}','Type':prefix+type_name,'Target':target})
    return xml(root)

def shape_tree(parent):
    tree=sub(parent,NS_P,'spTree')
    n=sub(tree,NS_P,'nvGrpSpPr')
    sub(n,NS_P,'cNvPr',id=1,name='')
    sub(n,NS_P,'cNvGrpSpPr')
    sub(n,NS_P,'nvPr')
    gp=sub(tree,NS_P,'grpSpPr'); x=sub(gp,NS_A,'xfrm')
    for nm in ('off', 'ext', 'chOff', 'chExt'):
        sub(x, NS_A, nm, **({'x': 0, 'y': 0} if nm in ('off', 'chOff') else {'cx': 0, 'cy': 0}))
    return tree

def slide_master():
    root=element(NS_P,'sldMaster')
    cs=sub(root,NS_P,'cSld',name='Zizai Master');shape_tree(cs)
    cmap={'accent1':'accent1','accent2':'accent2','accent3':'accent3','accent4':'accent4','accent5':'accent5','accent6':'accent6','bg1':'lt1','bg2':'lt2','tx1':'dk1','tx2':'dk2','folHlink':'folHlink','hlink':'hlink'}
    sub(root,NS_P,'clrMap',**cmap)
    lst=sub(root,NS_P,'sldLayoutIdLst')
    sub(lst,NS_P,'sldLayoutId',{'id':'2147483649',q(NS_R,'id'):'rId1'})
    tx=sub(root,NS_P,'txStyles')
    for name in ('titleStyle','bodyStyle','otherStyle'):
        sub(tx,NS_P,name)
    return xml(root)

def slide_layout():
    root=element(NS_P,'sldLayout',{'type':'blank','preserve':'1'})
    cs=sub(root,NS_P,'cSld',name='Blank');shape_tree(cs)
    co=sub(root,NS_P,'clrMapOvr');sub(co,NS_A,'masterClrMapping')
    return xml(root)

def theme_xml():
    root=element(NS_A,'theme',{'name':'Zizai Slide Studio'})
    elems=sub(root,NS_A,'themeElements')
    color=sub(elems,NS_A,'clrScheme',name='Zizai')
    mapping=[('dk1','000000'),('lt1','FFFFFF'),('dk2','1B2B45'),('lt2','F6F6F6'),('accent1','009287'),('accent2','44B3BA'),('accent3','DE5251'),('accent4','EAE68C'),('accent5','95999A'),('accent6','171717'),('hlink','167D86'),('folHlink','75721F')]
    for name, code in mapping:
        e=sub(color,NS_A,name);sub(e,NS_A,'srgbClr',val=code)
    font=sub(elems,NS_A,'fontScheme',name='Zizai Fonts')
    for kind in ('majorFont','minorFont'):
        f=sub(font,NS_A,kind);sub(f,NS_A,'latin',typeface='Yu Gothic');sub(f,NS_A,'ea',typeface='Yu Gothic');sub(f,NS_A,'cs',typeface='Arial')
    effect=sub(elems,NS_A,'fmtScheme',name='Zizai')
    fills=sub(effect,NS_A,'fillStyleLst')
    for c in ('FFFFFF','F6F6F6','EDFDFC'):
        sub(sub(fills,NS_A,'solidFill'),NS_A,'srgbClr',val=c)
    lines=sub(effect,NS_A,'lnStyleLst')
    for width in (9525,25400,38100):
        ln=sub(lines,NS_A,'ln',w=width)
        sub(sub(ln,NS_A,'solidFill'),NS_A,'srgbClr',val='242424')
        sub(ln,NS_A,'prstDash',val='solid')
    effects=sub(effect,NS_A,'effectStyleLst')
    for _ in range(3): sub(sub(effects,NS_A,'effectStyle'),NS_A,'effectLst')
    bgfills=sub(effect,NS_A,'bgFillStyleLst')
    for c in ('FFFFFF','FBFBFB','F2F2F2'):
        sub(sub(bgfills,NS_A,'solidFill'),NS_A,'srgbClr',val=c)
    return xml(root)

def core_properties():
    ns='http://schemas.openxmlformats.org/package/2006/metadata/core-properties'
    dc='http://purl.org/dc/elements/1.1/'
    root=ET.Element(q(ns,'coreProperties'))
    sub(root,dc,'creator').text='Zizai Slide Studio'
    sub(root,dc,'title').text='Zizai Slides'
    return xml(root)

def app_properties(count):
    root=ET.Element('Properties',{'xmlns':'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'})
    ET.SubElement(root,'Application').text='Zizai Slide Studio'
    ET.SubElement(root,'Slides').text=str(count)
    return xml(root)

def content_types():
    ET.register_namespace('', NS_CT)
    root=ET.Element(q(NS_CT,'Types'))
    for ext,ct in [('rels','application/vnd.openxmlformats-package.relationships+xml'),('xml','application/xml'),('png','image/png'),('jpg','image/jpeg'),('jpeg','image/jpeg'),('gif','image/gif')]:
        ET.SubElement(root,q(NS_CT,'Default'),{'Extension':ext,'ContentType':ct})
    for name,ct in [
        ('/ppt/presentation.xml','application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'),
        ('/ppt/slideMasters/slideMaster1.xml','application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml'),
        ('/ppt/slideLayouts/slideLayout1.xml','application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml'),
        ('/ppt/theme/theme1.xml','application/vnd.openxmlformats-officedocument.theme+xml'),
        ('/docProps/core.xml','application/vnd.openxmlformats-package.core-properties+xml'),
        ('/docProps/app.xml','application/vnd.openxmlformats-officedocument.extended-properties+xml')]:
        ET.SubElement(root,q(NS_CT,'Override'),{'PartName':name,'ContentType':ct})
    return root

def package_pptx(slides: list[SlideDrawing], output: Path):
    content=content_types()
    for i in range(len(slides)):
        ET.SubElement(content,q(NS_CT,'Override'),{'PartName':f'/ppt/slides/slide{i+1}.xml', 'ContentType':'application/vnd.openxmlformats-officedocument.presentationml.slide+xml'})
    presentation=element(NS_P,'presentation')
    masterlist=sub(presentation,NS_P,'sldMasterIdLst')
    sub(masterlist,NS_P,'sldMasterId',{'id':'2147483648',q(NS_R,'id'):'rId1'})
    slideids=sub(presentation,NS_P,'sldIdLst')
    for i in range(len(slides)):
        sub(slideids,NS_P,'sldId',{'id':str(256+i),q(NS_R,'id'):f'rId{i+2}'})
    sub(presentation,NS_P,'sldSz',cx=SW*EMU,cy=SH*EMU,type='screen16x9')
    sub(presentation,NS_P,'notesSz',cx=6858000,cy=9144000)
    with ZipFile(output,'w',compression=ZIP_DEFLATED) as z:
        ET.register_namespace('', NS_CT)
        z.writestr('[Content_Types].xml',xml(content))
        z.writestr('_rels/.rels',relationship_list([('officeDocument','ppt/presentation.xml'),('metadata/core-properties','docProps/core.xml'),('extended-properties','docProps/app.xml')]))
        z.writestr('docProps/core.xml',core_properties())
        z.writestr('docProps/app.xml',app_properties(len(slides)))
        z.writestr('ppt/presentation.xml',xml(presentation))
        z.writestr('ppt/_rels/presentation.xml.rels',relationship_list([('slideMaster','slideMasters/slideMaster1.xml')]+[('slide',f'slides/slide{i+1}.xml') for i in range(len(slides))]))
        z.writestr('ppt/slideMasters/slideMaster1.xml',slide_master())
        z.writestr('ppt/slideMasters/_rels/slideMaster1.xml.rels',relationship_list([('slideLayout','../slideLayouts/slideLayout1.xml'),('theme','../theme/theme1.xml')]))
        z.writestr('ppt/slideLayouts/slideLayout1.xml',slide_layout())
        z.writestr('ppt/slideLayouts/_rels/slideLayout1.xml.rels',relationship_list([('slideMaster','../slideMasters/slideMaster1.xml')]))
        z.writestr('ppt/theme/theme1.xml',theme_xml())
        for i,slide in enumerate(slides):
            z.writestr(f'ppt/slides/slide{i+1}.xml',slide.done())
            relations=[('slideLayout','../slideLayouts/slideLayout1.xml')]
            for j,(filename,bytes_,rid) in enumerate(slide.images):
                key=f'slide{i+1}_image{j+1}.'+filename.rsplit('.',1)[-1]
                z.writestr('ppt/media/'+key,bytes_)
                relations.append(('image','../media/'+key))
            z.writestr(f'ppt/slides/_rels/slide{i+1}.xml.rels',relationship_list(relations))
    with ZipFile(output) as z:
        issue=z.testzip()
        if issue: raise RuntimeError('PPTX ZIP CRCエラー: '+issue)
        for name in z.namelist():
            if name.endswith('.xml') or name.endswith('.rels'):
                ET.fromstring(z.read(name))
    return str(output)

# ------- Browser-measured native editable PowerPoint -----------------------


def _safe_dimension(value, maximum=1400):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('レイアウトに数値でない位置情報があります。')
    if not math.isfinite(value) or abs(value) > maximum * 100:
        raise ValueError('レイアウト座標が不正です。')
    return float(value)


def _rgb(value, fallback='111111'):
    return normalize_hex(value) if isinstance(value, str) else fallback


def _text_shape(slide: SlideDrawing, measured):
    """A single editable text run at Chromium's actual Range.getClientRects coordinates.

    One shape per rendered line/style is intentional: it prevents the PowerPoint
    layout engine from re-wrapping an entire paragraph differently than Chromium.
    The text and its font attributes remain fully editable after export.
    """
    content = measured.get('text', '')
    if not isinstance(content, str) or not content.strip():
        return
    if len(content) > 20_000:
        raise ValueError('文字列が長すぎます。')
    x = _safe_dimension(measured['x'])
    y = _safe_dimension(measured['y'])
    w = _safe_dimension(measured['w'])
    h = _safe_dimension(measured['h'])
    size = bound(_safe_dimension(measured.get('fontSize', 20)), 6, 140)
    if w < .2 or h < .2:
        return
    # CSS px to PowerPoint hundredths-of-points: 96px == 72pt.
    pt100 = int(round(size * 75))
    # The five-pixel horizontal safety margin absorbs font-substitution variance.
    # No wrap means the browser-decided line breaks remain authoritative.
    sp = sub(slide.tree, NS_P, 'sp')
    nv = sub(sp, NS_P, 'nvSpPr')
    sub(nv, NS_P, 'cNvPr', id=slide.next_id,
        name=str(measured.get('name', 'Editable text'))[:70] + f' {slide.next_id}')
    slide.next_id += 1
    sub(nv, NS_P, 'cNvSpPr', txBox='1')
    sub(nv, NS_P, 'nvPr')
    props = sub(sp, NS_P, 'spPr')
    geometry(props, x, y, w + 7, max(h + 5, size * 1.27))
    sub(props, NS_A, 'noFill')
    body = sub(sp, NS_P, 'txBody')
    bodypr = sub(body, NS_A, 'bodyPr', wrap='none', anchor='t',
                 lIns='0', rIns='0', tIns='0', bIns='0',
                 spcFirstLastPara='0')
    sub(bodypr, NS_A, 'noAutofit')
    sub(body, NS_A, 'lstStyle')
    para = sub(body, NS_A, 'p')
    if measured.get('center'):
        sub(para, NS_A, 'pPr', algn='ctr')
    run = sub(para, NS_A, 'r')
    rp = sub(run, NS_A, 'rPr', lang='ja-JP', sz=str(pt100),
             b='1' if measured.get('bold') else '0')
    fill(rp, _rgb(measured.get('color')))
    family = measured.get('fontFamily', 'Yu Gothic')
    if not isinstance(family, str):
        family = 'Yu Gothic'
    family = family.split(',')[0].strip(' \"\'')[:90] or 'Yu Gothic'
    sub(rp, NS_A, 'latin', typeface=family)
    sub(rp, NS_A, 'ea', typeface=family)
    word = sub(run, NS_A, 't')
    word.text = content
    word.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    sub(para, NS_A, 'endParaRPr', lang='ja-JP')


def _draw_measured_shape(slide: SlideDrawing, item):
    x, y, w, h = [_safe_dimension(item.get(k, 0)) for k in ('x', 'y', 'w', 'h')]
    if w <= 0 or h <= 0:
        return
    paint = item.get('fill')
    stroke = item.get('border')
    if not paint and not stroke:
        return
    shape = sub(slide.tree, NS_P, 'sp')
    nv = sub(shape, NS_P, 'nvSpPr')
    sub(nv, NS_P, 'cNvPr', id=slide.next_id,
        name=str(item.get('name', 'Editable shape'))[:70] + f' {slide.next_id}')
    slide.next_id += 1
    sub(nv, NS_P, 'cNvSpPr')
    sub(nv, NS_P, 'nvPr')
    sppr = sub(shape, NS_P, 'spPr')
    radius = _safe_dimension(item.get('radius', 0))
    geometry(sppr, x, y, w, h,
             'ellipse' if item.get('kind') == 'ellipse' else 'roundRect' if radius > 1 else 'rect')
    if radius > 1 and item.get('kind') != 'ellipse':
        geom = sppr.find(q(NS_A, 'prstGeom'))
        values = geom.find(q(NS_A, 'avLst'))
        # OOXML preset roundRect uses adjustable corner radius. Its default
        # scales with shape height, producing huge curves on large cards.
        # Preserve the exact CSS px radius instead.
        adjust = int(bound(radius / min(w, h) * 100000, 0, 50000))
        sub(values, NS_A, 'gd', name='adj', fmla=f'val {adjust}')
    rotate = _safe_dimension(item.get('rotate', 0))
    if rotate:
        sppr.find(q(NS_A, 'xfrm')).set('rot', str(int(rotate * 60000)))
    if paint:
        fill(sppr, _rgb(paint))
    else:
        sub(sppr, NS_A, 'noFill')
    if stroke and _safe_dimension(item.get('borderWidth', 0)) > 0:
        ln = sub(sppr, NS_A, 'ln', w=cx(_safe_dimension(item['borderWidth'])))
        fill(ln, _rgb(stroke))
    else:
        sub(sub(sppr, NS_A, 'ln'), NS_A, 'noFill')
    if item.get('shadow'):
        effect = sub(sppr, NS_A, 'effectLst')
        shade = sub(effect, NS_A, 'outerShdw', blurRad=str(8 * EMU),
                    dist=str(3 * EMU), dir=str(5400000), algn='ctr', rotWithShape='0')
        c = sub(shade, NS_A, 'srgbClr', val='1B2B45')
        sub(c, NS_A, 'alpha', val='19000')


def _draw_measured_image(slide: SlideDrawing, item, source_dir: str):
    if not source_dir:
        return
    rel = item.get('path', '')
    if not isinstance(rel, str) or not rel or '\x00' in rel or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', rel):
        return
    base = Path(source_dir).resolve()
    path = (base / rel).resolve()
    try:
        path.relative_to(base)
    except ValueError:
        return
    if not path.is_file():
        raise ValueError(f'画像が見つかりません: {rel}')
    if path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.gif'):
        raise ValueError(f'編集可能PPTXが対応していない画像形式です: {rel}。PNGまたはJPEGに変換してください。')
    if path.stat().st_size > 12_000_000:
        raise ValueError(f'画像が12MBを超えています: {rel}')
    coords = [_safe_dimension(item.get(k, 0)) for k in ('x', 'y', 'w', 'h')]
    slide.picture(*coords, path.read_bytes(), path.suffix.lower().lstrip('.'))


def export_measured_editable(deck: dict, layouts: list, output: Path, source_dir=''):
    """Generate native PPTX from canonical Python geometry (no Webview)."""
    slides = deck.get('slides', [])
    if not slides or not isinstance(layouts, list) or len(slides) != len(layouts):
        raise ValueError('スライド数と実測レイアウトが一致しません。再プレビューしてから出力してください。')
    drawings = []
    for index, (src, layout) in enumerate(zip(slides, layouts)):
        if not isinstance(layout, dict) or abs(layout.get('width', 0) - SW) > 1 or abs(layout.get('height', 0) - SH) > 1:
            raise ValueError(f'{index + 1}枚目のレイアウトサイズが不正です。')
        shapes, texts, images = (layout.get('shapes'), layout.get('texts'), layout.get('images'))
        if not all(isinstance(x, list) for x in (shapes, texts, images)):
            raise ValueError(f'{index + 1}枚目のレイアウト情報が不足しています。')
        if len(shapes) + len(texts) + len(images) > 6000:
            raise ValueError(f'{index + 1}枚目のオブジェクト数が多すぎます。')
        if src.get('html', '').strip() and not texts and not images:
            raise ValueError(f'{index + 1}枚目に描画可能なテキスト／画像がありません。')
        # Refuse silent truncation. An export where browser-clipped characters
        # reappear in PowerPoint would look broken despite identical geometry.
        if layout.get('warnings'):
            raise ValueError(f'{index + 1}枚目のスライドでテキストのはみ出しを検出しました。'
                             '文字量またはカードの高さを調整してください。'
                             + ', '.join(map(str, layout['warnings']))[:140])
        drawing = SlideDrawing(src.get('title', f'Slide {index + 1}'))
        # Shapes → pictures → text. Every object remains native and selectable.
        for element in shapes:
            _draw_measured_shape(drawing, element)
        for element in images:
            _draw_measured_image(drawing, element, source_dir)
        for element in texts:
            _text_shape(drawing, element)
        drawings.append(drawing)
    return package_pptx(drawings, output)


# ------- Screenshot-to-PPTX mode ------------------------------------------

def screenshot(browser, html_file, png_file):
    cmd=[browser,'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
         '--disable-background-networking','--disable-extensions','--hide-scrollbars',
         '--force-device-scale-factor=1','--window-size=1280,720',f'--screenshot={png_file}',html_file.as_uri()]
    if os.name!='nt':cmd.insert(1,'--no-sandbox')
    completed=subprocess.run(cmd,capture_output=True,text=True,timeout=45,check=False)
    if completed.returncode!=0 or not png_file.exists() or png_file.stat().st_size<150:
        raise RuntimeError('ブラウザからPNGを取得できません: '+(completed.stderr or '')[-250:])
    data=png_file.read_bytes()
    if data[:8]!=b'\x89PNG\r\n\x1a\n':raise RuntimeError('生成した画像がPNGではありません。')
    return data

def export_image(pages, output: Path):
    browsers=browser_candidates()
    if not browsers:
        raise RuntimeError('画像ベースPPTXにはインストール済みのMicrosoft EdgeまたはGoogle Chromeが必要です。')
    drawings=[]
    with tempfile.TemporaryDirectory(prefix='zizai-pptx-') as tmp:
        for i,page in enumerate(pages):
            html_file=Path(tmp)/f'slide{i+1}.html'
            png=Path(tmp)/f'slide{i+1}.png'
            html_file.write_text(page,encoding='utf-8')
            errors=[]
            data=None
            for browser in browsers:
                try:
                    data=screenshot(browser,html_file,png)
                    break
                except (OSError,subprocess.TimeoutExpired,RuntimeError) as err:
                    errors.append(str(err)[:300])
            if data is None:
                raise RuntimeError(f'{i+1}枚目のスクリーンショットに失敗しました。'+ '; '.join(errors)[:250])
            slide=SlideDrawing(f'Slide {i+1}')
            slide.picture(0,0,SW,SH,data,'png')
            drawings.append(slide)
    return package_pptx(drawings,output)

def export_editable(deck, output, source_dir='', layout=None):
    if layout is None:
        from .layout import layout_deck
        layout = layout_deck(deck)
    return export_measured_editable(deck, layout, output, source_dir)


def main():
    try:
        req=json.load(sys.stdin)
        target=Path(req.get('output','')).expanduser().resolve()
        if target.suffix.lower()!='.pptx':raise ValueError('出力先は.pptxにしてください。')
        mode=req.get('mode')
        if mode=='image':
            pages=req.get('pages')
            if not isinstance(pages,list) or not 0<len(pages)<=100 or any(not isinstance(x,str) or len(x)>12_000_000 for x in pages):
                raise ValueError('画像モードのスライドデータが不正です。')
            result=export_image(pages,target)
        elif mode=='editable':
            if not isinstance(req.get('deck'),dict):raise ValueError('編集モードにはdeckを指定してください。')
            result=export_editable(req['deck'],target,req.get('sourceDir',''),req.get('layout'))
        else:raise ValueError('modeには image / editable を指定してください。')
        print(json.dumps({'ok':True,'path':result,'mode':mode},ensure_ascii=False))
    except (OSError,RuntimeError,ValueError,TypeError) as err:
        print(json.dumps({'ok':False,'error':str(err)},ensure_ascii=False))
    return 0

if __name__=='__main__':sys.exit(main())
