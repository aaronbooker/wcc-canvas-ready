import sys, re
from pptx import Presentation
from pptx.util import Pt
P='{http://schemas.openxmlformats.org/presentationml/2006/main}'
A='{http://schemas.openxmlformats.org/drawingml/2006/main}'
prs=Presentation(sys.argv[1]); cp=prs.core_properties
print('P4 title:',repr(cp.title),' P5 lang:',repr(cp.language),' P16 author:',cp.author,'/',cp.last_modified_by)
def real_alt(cnv):
    d=(cnv.get('descr') or '').strip()
    return bool(d) and not re.search(r'\.(png|jpe?g|gif|emf|wmf|svg)$',d,re.I)
def decorative(cnv):
    return any(el.tag.endswith('}decorative') and el.get('val') in ('1','true') for el in cnv.iter())
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pptx_bg import Backdrop, deck_colors, worst_contrast, leaf_shapes
_co, _bg = deck_colors(prs)
BD = Backdrop(prs, _co, _bg)
titles=[]
for i,s in enumerate(prs.slides,1):
    _bg(s)   # switch to this slide's master theme
    t=s.shapes.title
    if t is None or not t.text_frame.text.strip(): print(f'P2 slide {i}: no title placeholder text')
    else: titles.append(t.text_frame.text.strip())
    # (P6 'title first' check removed in v5: forcing the title first doubled WCC's reading-order flags; the fixer keeps column-first visual order)
    tree=s._element
    # Check each graphic on its own: pictures, charts/SmartArt/tables frames (not tables), and groups.
    for el in tree.iter(P+'pic',P+'graphicFrame',P+'grpSp'):
        if el.tag==P+'graphicFrame' and el.find('.//'+A+'tbl') is not None: continue
        cnv=next(el.iter(P+'cNvPr'))
        if el.tag==P+'grpSp' and el.find('.//'+P+'pic') is None and el.find('.//'+P+'graphicFrame') is None:
            continue  # group of plain shapes/text: check by eye
        if el.tag==P+'grpSp' and all(real_alt(next(c.iter(P+'cNvPr'))) or decorative(next(c.iter(P+'cNvPr'))) for c in el.iter(P+'pic',P+'graphicFrame') if not (c.tag==P+'graphicFrame' and c.find('.//'+A+'tbl') is not None)):
            continue  # every picture inside has its own alt: Panorama asks nothing of the group (3 of 3, Nov 2026)
        if not real_alt(cnv) and not decorative(cnv):
            print(f'P8 slide {i}: no alt / not decorative: {el.tag.split("}")[1]} "{cnv.get("name")}"')
    x=tree.xml
    small=[int(v) for v in re.findall(r'<a:(?:rPr|defRPr|endParaRPr)\b[^>]*\bsz="(\d+)"',x) if int(v)<1200]
    if small: print(f'P12 slide {i}: runs <12pt:', sorted(set(small)))
    langs=set(re.findall(r'\blang="([^"]+)"',x))-{'en-US'}
    if langs: print(f'P5 slide {i}: other lang tags', langs)
    if re.search(r'videoFile|audioFile|<p14:media',x): print(f'P13 slide {i}: embedded media, flag for captions')
    # P7 contrast against what is really behind the text (fills, pictures, master banners): 90% of the
    # background must give 4.5:1 (WCC's Panorama flags text on photos, Severe)
    for sh in leaf_shapes(s.shapes):
        if not sh.has_text_frame or not sh.text_frame.text.strip(): continue
        own = _co(sh._element.find('./'+P+'spPr/'+A+'solidFill'))
        px = [tuple(int(own[k:k+2],16) for k in (0,2,4))] if own else BD.pixels(s, sh)
        if not px: continue
        seen = set()
        for p in sh.text_frame.paragraphs:
            for r in p.runs:
                rp = r._r.find(A+'rPr')
                fg = _co(rp.find(A+'solidFill')) if rp is not None else None
                if not r.text.strip() or not fg or fg in seen: continue
                seen.add(fg); w = worst_contrast(fg, px)
                if w < 4.5: print(f'P7 slide {i}: low contrast {fg} on what is behind it ({w:.2f}:1): {r.text.strip()[:30]!r}')
    for sh in s.shapes:
        if sh.has_table and sh.table._tbl.tblPr.get('firstRow')!='1': print(f'P11 slide {i}: table w/o header row')
        if sh.has_text_frame:
            for p in sh.text_frame.paragraphs:
                for r in p.runs:
                    if r.hyperlink.address and re.match(r'\s*(click here|here|link|read more|https?://|www\.)',r.text,re.I):
                        print(f'P10 slide {i}: weak link text', repr(r.text))
# Sizes inherited from the layouts and masters this deck actually uses
used={}
for s in prs.slides:
    for part in (s.slide_layout.slide_master, s.slide_layout):
        used.setdefault(str(part.part.partname), part)
for name,part in used.items():
    small=sorted({int(v) for v in re.findall(r'\bsz="(\d+)"',part._element.xml) if int(v)<1200})
    if small: print(f'P12 {name}: inherited sizes <12pt', small)
dups={t for t in titles if titles.count(t)>1}
print('P3 duplicate titles:', dups or 'none')
