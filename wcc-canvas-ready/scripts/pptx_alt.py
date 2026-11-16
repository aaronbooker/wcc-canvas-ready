"""Alt text for pictures in a .pptx, decided once per distinct image. P8 [WCAG 1.1.1 + Panorama, Severe/Major].
  python3 pptx_alt.py deck.pptx --list outdir/     # extract each distinct picture + alt_draft.json (slides, slide text)
  python3 pptx_alt.py deck.pptx out.pptx alt.json   # apply
alt.json maps the image file name (e.g. "image3.png") to alt text, or to "decorative"; charts and SmartArt
are keyed "chart:<slide>:<shape name>" (say what the chart shows: its point, then the key numbers).
Open each extracted image and read its slide text before writing alt text. QR codes: decode them and say where
they go. Logos: "<Name> logo". Pictures that only decorate: "decorative".
"""
import sys, os, json, re
from pptx import Presentation
from lxml import etree
P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
ADEC = 'http://schemas.microsoft.com/office/drawing/2017/decorative'
prs = Presentation(sys.argv[1])

def pics():
    """pictures (keyed by image file), plus charts and SmartArt (keyed "chart:<slide>:<name>"), which Panorama also
    treats as images that need alt text. A video is a picture whose image is its poster frame."""
    for i, s in enumerate(prs.slides, 1):
        for el in s.shapes._spTree.iter(P + 'pic'):
            blip = el.find('.//' + A + 'blip')
            rid = blip.get(R + 'embed') if blip is not None else None
            part = s.part.related_part(rid) if rid else None
            key = os.path.basename(part.partname) if part is not None else 'unknown'
            yield i, s, el, key, part
        for el in s.shapes._spTree.iter(P + 'graphicFrame'):
            uri = el.find('.//' + A + 'graphicData')
            uri = uri.get('uri', '') if uri is not None else ''
            if 'chart' in uri or 'diagram' in uri:
                cnv = el.find('.//' + P + 'cNvPr')
                yield i, s, el, f'chart:{i}:{cnv.get("name")}', None

if '--list' in sys.argv:
    out = sys.argv[sys.argv.index('--list') + 1]; os.makedirs(out, exist_ok=True)
    info = {}
    for i, s, el, key, part in pics():
        cnv = el.find('.//' + P + 'cNvPr')
        d = info.setdefault(key, {'alt': '', 'current_alt': cnv.get('descr') or '', 'slides': [], 'slide_text': ''})
        d['slides'].append(i)
        if not d['slide_text']:
            d['slide_text'] = ' | '.join(sh.text_frame.text.replace('\n', ' ')[:80] for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip())[:300]
        if part is not None: open(os.path.join(out, key), 'wb').write(part.blob)
    json.dump(info, open(os.path.join(out, 'alt_draft.json'), 'w'), indent=1, ensure_ascii=False)
    print(f'{sum(len(v["slides"]) for v in info.values())} pictures, {len(info)} distinct -> {out}/alt_draft.json')
    sys.exit()

dst, alts = sys.argv[2], json.load(open(sys.argv[3]))
alts = {k: (v['alt'] if isinstance(v, dict) else v) for k, v in alts.items()}
n, missing = 0, set()
for i, s, el, key, part in pics():
    a = alts.get(key)
    if a is None: missing.add(key); continue
    cnv = el.find('.//' + P + 'cNvPr')
    for k in ('descr', 'title'):
        if k in cnv.attrib: del cnv.attrib[k]
    old = cnv.find(A + 'extLst')
    if old is not None:
        for e in list(old):
            if e.get('uri') == '{C183D7F6-B498-43B3-948B-1728B52AA6E4}': old.remove(e)
    if a.strip().lower() in ('', 'decorative'):
        lst = cnv.find(A + 'extLst')
        if lst is None: lst = etree.SubElement(cnv, A + 'extLst')
        ext = etree.SubElement(lst, A + 'ext', uri='{C183D7F6-B498-43B3-948B-1728B52AA6E4}')
        etree.SubElement(ext, '{%s}decorative' % ADEC, nsmap={'adec': ADEC}, val='1')
    else:
        cnv.set('descr', a.strip())
    n += 1
prs.save(dst)
print(f'alt/decorative set on {n} pictures; not in JSON: {sorted(missing)}')
