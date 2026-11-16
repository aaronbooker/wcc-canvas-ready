"""Make floating pictures inline. D12 [WCAG 1.3.2 + Panorama "The Image is not inline with the text" (Major,
one instance per picture)]. Learned at WCC (Nov 2026): a 2011 Word 97 brochure converted to .docx kept 7 square-
wrapped pictures; with headings, alt text and title fixed it still scored 30% on this flag alone. Pictures in the
header or footer were not counted, and text boxes/shapes are left alone.

  python3 docx_inline.py in.docx            # list the floating pictures and the paragraph each is anchored to
  python3 docx_inline.py in.docx out.docx   # apply

Each floating picture (<wp:anchor> holding a picture) becomes an inline picture (<wp:inline>) in a paragraph of
its own, placed right after the paragraph it was anchored to, so a screen reader meets it where the text refers to
it. Size, alt text and the image itself are kept; wrapping and position are dropped. Render and look afterwards:
pictures that sat beside text now sit between paragraphs, so the document gets longer.
"""
import sys, re, zipfile, html

src = sys.argv[1]
z = zipfile.ZipFile(src); files = {n: z.read(n) for n in z.namelist()}
doc = files['word/document.xml'].decode()
txt = lambda x: html.unescape(''.join(re.findall(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>', x))).strip()

ANCHOR = re.compile(r'<wp:anchor\b[^>]*>.*?</wp:anchor>', re.S)
PARA = re.compile(r'<w:p\b(?:(?!<w:p\b).)*?</w:p>', re.S)   # innermost paragraph (no nested <w:p>)

def is_picture(a):
    return 'graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"' in a

def to_inline(a):
    keep = []
    for tag in ('wp:extent', 'wp:effectExtent', 'wp:docPr', 'wp:cNvGraphicFramePr', 'a:graphic'):
        m = re.search(r'<%s\b[^>]*?(?:/>|>.*?</%s>)' % (tag, tag), a, re.S)
        if m: keep.append(m.group(0))
    return '<wp:inline distT="0" distB="0" distL="0" distR="0">' + ''.join(keep) + '</wp:inline>'

def run_of(p, a_start, a_end):
    """the <w:r> that holds the anchor, as offsets in p"""
    rs = p.rfind('<w:r>', 0, a_start); rs2 = p.rfind('<w:r ', 0, a_start); rs = max(rs, rs2)
    re_ = p.find('</w:r>', a_end) + len('</w:r>')
    return rs, re_

found, out, pos = [], [], 0
for pm in PARA.finditer(doc):
    p = pm.group(0)
    anchors = [m for m in ANCHOR.finditer(p) if is_picture(m.group(0))]
    if not anchors: continue
    if 'mc:AlternateContent' in p[:anchors[0].start()] and '</mc:AlternateContent>' in p[anchors[0].end():]:
        continue   # picture inside an alternate-content wrapper: leave it
    spans = {}                       # one entry per run, even when a run holds several pictures
    for m in anchors:
        spans.setdefault(run_of(p, m.start(), m.end()), []).append(m)
    runs, new_p = [], p
    for (rs, re_), ms in sorted(spans.items(), reverse=True):
        run = p[rs:re_]
        for m in ms: run = run.replace(m.group(0), to_inline(m.group(0)))
        runs.insert(0, run)
        new_p = new_p[:rs] + new_p[re_:]
    for m in anchors:
        alt = re.search(r'descr="([^"]*)"', m.group(0))
        found.append((txt(p)[:60], alt.group(1)[:50] if alt else ''))
    pics = ''.join('<w:p><w:pPr><w:spacing w:before="120" w:after="120"/></w:pPr>' + r + '</w:p>' for r in runs)
    # an anchor-only paragraph (no text left) is replaced by the picture paragraphs
    rest = txt(new_p)
    out.append(doc[pos:pm.start()] + (new_p if rest or any(k in new_p for k in ('<w:drawing', '<w:pict', '<w:sectPr', '<w:bookmark', '<w:numPr')) else '') + pics)
    pos = pm.end()
out.append(doc[pos:])

for t, a in found:
    print(f'floating picture after: "{t}"  alt: "{a}"')
print(f'{len(found)} floating pictures')
if len(sys.argv) < 3: sys.exit()
files['word/document.xml'] = ''.join(out).encode()
with zipfile.ZipFile(sys.argv[2], 'w', zipfile.ZIP_DEFLATED) as o:
    for n in z.namelist(): o.writestr(n, files[n])
print('made inline:', len(found))
