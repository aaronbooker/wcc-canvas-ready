"""Draft a chapter's layout.json for pdf2md.py: skip boxes and markers for feature boxes, figures and photos, and
the pages to build by hand. A draft for YOU to check against the page images, not a final answer.

Usage: python3 -I layout_draft.py chapter.pdf layout.json out_layout.json [--min-area 3000] [--full 0.55]

Why: mapping each chapter's boxes and photos by hand was the longest step of a textbook rebuild (three chapters,
Nov 18, 2026). Scanned pages often have no vector boxes at all (the page is one picture with text laid over it),
so this looks at the page image: tinted areas (shaded boxes, photos, colored figures) become skip boxes, and pages
that are mostly picture, sideways (/Rotate), the first page, or nearly without body text become manual pages.
Coordinates are written in pdfplumber's media-box points (the render's crop-box origin is added back).
Gray-only figures and boxes with no tint are not found: look for them. It prints one line per region with its
first words, so each marker can be named and written by hand (region.py, the page image).
Needs pdfplumber, Pillow and numpy; uses PyMuPDF to render when it is there.
"""
import sys, json, re, io
import pdfplumber
import numpy as np
from PIL import Image
try:
    import fitz
except ImportError:
    fitz = None

args = [a for a in sys.argv[1:] if not a.startswith('--')]
opt = lambda k, d: type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
src, base, dst = args[:3]
MIN_AREA, FULL = opt('--min-area', 3000.0), opt('--full', 0.55)
L = json.load(open(base))
DPI = 36                      # 2 points per pixel: coarse on purpose, boxes and photos are large
pdf = pdfplumber.open(src)
doc = fitz.open(src) if fitz else None
sys.path.insert(0, __import__('os').path.dirname(__file__))
import pdf2md as P                      # the same left/right page decision pdf2md.py will make
P.L.update(L)
SIDES = P.page_sides(pdf)


def render(i):
    """RGB array of the visible page (crop box) and the crop box's origin in media-box points."""
    pg = pdf.pages[i]
    if doc:
        p = doc[i]
        pix = p.get_pixmap(dpi=DPI)
        im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        return np.asarray(im).astype(int), p.cropbox.x0, p.cropbox.y0
    im = pg.to_image(resolution=DPI).original.convert('RGB')
    cb = pg.cropbox or pg.bbox
    return np.asarray(im).astype(int), cb[0], cb[1]


def regions(rgb):
    """Bounding boxes (pixels) of connected tinted areas, after a small closing so a box's text doesn't split it."""
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    m = sat > 12                                   # tinted: boxes, photos, colored figures (black text is not)
    h, w = m.shape
    g = m.copy()                                   # close gaps of up to 2 px (4 pt): text lines inside a box
    for dy in (-2, -1, 1, 2):
        g |= np.roll(m, dy, axis=0)
    for dx in (-2, -1, 1, 2):
        g |= np.roll(m, dx, axis=1)
    seen = np.zeros_like(g)
    out = []
    for y in range(h):
        for x in range(w):
            if g[y, x] and not seen[y, x]:
                stack, x0, y0, x1, y1, n = [(y, x)], x, y, x, y, 0
                seen[y, x] = True
                while stack:
                    cy, cx = stack.pop(); n += 1
                    x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
                    for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                        if 0 <= ny < h and 0 <= nx < w and g[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True; stack.append((ny, nx))
                out.append((x0, y0, x1 + 1, y1 + 1, n))
    return out


pages, manual, report = {}, [], []
body_font, body_size = L.get('body_font', ''), L.get('body_size', 10)
for i, pg in enumerate(pdf.pages):
    pno = i + 1
    words = pg.extract_words(extra_attrs=['fontname', 'size'], x_tolerance=1.5)
    body = [w for w in words if body_font in w['fontname'] and abs(w['size'] - body_size) < 0.3 and w.get('upright', True)]
    upright = sum(1 for c in pg.chars if c.get('upright', True)) / max(1, len(pg.chars))
    rgb, ox, oy = render(i)
    k = 72.0 / DPI
    page_area = rgb.shape[0] * rgb.shape[1] * k * k
    why = None
    if pno == 1:
        why = 'first page (chapter opener)'
    elif (pg.rotation or 0) % 180 or upright < 0.6:
        why = 'sideways page (/Rotate %s): read it with PyMuPDF or type it' % (pg.rotation or 0)
    elif len(body) < 40:
        why = 'little body text (%d words): photos, maps or review pages' % len(body)
    side = SIDES[pno]
    mx = L[side]['margin']
    is_body = lambda w: body_font in w['fontname'] and abs(w['size'] - body_size) < 0.3
    found = []
    for x0, y0, x1, y1, n in regions(rgb):
        bb = [round(x0 * k + ox, 1), round(y0 * k + oy, 1), round(x1 * k + ox, 1), round(y1 * k + oy, 1)]
        area = (bb[2] - bb[0]) * (bb[3] - bb[1])
        fill = n / max(1, (x1 - x0 + 1) * (y1 - y0 + 1))
        # not a box: colored text (a heading, a glossary term: short or sparse), or a margin note (pdf2md reads those)
        if area < MIN_AREA or bb[3] - bb[1] < 26 or fill < 0.55 or (bb[0] >= mx[0] - 4 and bb[2] <= mx[1] + 4):
            continue
        inside = lambda b: [w for w in words if b[0] - 1 <= w['x0'] and w['x1'] <= b[2] + 1 and b[1] - 1 <= w['top'] and w['bottom'] <= b[3] + 1]
        # a figure's labels and caption sit around the picture in another font: take them in (within 40 pt)
        # never past a body-text word, a running head or a drop cap: growing must not swallow the text
        n_body = lambda b: sum(1 for w in inside(b) if is_body(w))
        grow = True
        while grow:
            grow = False
            for w in words:
                if is_body(w) or w['size'] > 25 or w['top'] < L.get('top', 45) or w in inside(bb):
                    continue
                if bb[0] - 40 <= w['x1'] and w['x0'] <= bb[2] + 40 and bb[1] - 40 <= w['bottom'] and w['top'] <= bb[3] + 40 \
                        and not (mx[0] - 4 <= w['x0'] and w['x1'] <= mx[1] + 4):
                    nb = [min(bb[0], w['x0'] - 2), min(bb[1], w['top'] - 2), max(bb[2], w['x1'] + 2), max(bb[3], w['bottom'] + 2)]
                    if n_body(nb) > n_body(bb):
                        continue
                    bb, grow = nb, True
        bb = [round(v, 1) for v in bb]
        ins = inside(bb)
        # a colored heading over body text is not a figure: an area that holds body-text words but is short is text
        nb = sum(1 for w in ins if is_body(w))
        if nb and (bb[3] - bb[1] < 80 or nb > 0.5 * len(ins)):
            continue
        # a colored heading on two lines: its words are in a heading font from layout.json
        head = lambda w: any(f in w['fontname'] and abs(w['size'] - z) < 0.3 for f, z, _ in L.get('headings', []))
        if ins and sum(1 for w in ins if head(w)) >= 0.8 * len(ins):
            continue
        found.append((bb, area, ins))
    if not why and any(a > FULL * page_area for _, a, _ in found):
        why = 'mostly one box or picture'
    if why:
        manual.append(pno)
        report.append('p%-3d MANUAL  %s' % (pno, why))
        continue
    skips = []
    for j, (bb, area, inside) in enumerate(sorted(found, key=lambda f: (f[0][1], f[0][0]))):
        kind = 'BOX' if len(inside) >= 25 else 'FIG'
        name = '%s_p%d_%d' % (kind, pno, j + 1)
        skips.append((bb, name))
        report.append('p%-3d %-6s %-26s %3d words: %s' % (pno, kind, bb, len(inside), ' '.join(w['text'] for w in inside[:12])[:70]))
    if skips:
        pages[str(pno)] = {'skip': [bb for bb, _ in skips], 'marker_after': '+'.join(n for _, n in skips)}
    # a printed caption with nothing found around it: a gray chart or an untinted box (Figure 4.1 in a test chapter)
    lines = {}
    for w in words:
        lines.setdefault(round(w['top']), []).append(w)
    for top, ws in lines.items():
        t = ' '.join(x['text'] for x in sorted(ws, key=lambda x: x['x0']))
        m = re.match(r'(FIGURE|TABLE|MAP)\s+\d+[.\d]*', t)
        if m and not any(b[0] - 2 <= ws[0]['x0'] <= b[2] + 2 and b[1] - 2 <= top <= b[3] + 2 for b, _ in skips):
            report.append('p%-3d CHECK  caption "%s" at y=%d has no box around it: mark its figure or table by hand' % (pno, m.group(0), top))

L['pages'], L['manual_pages'] = pages, manual
json.dump(L, open(dst, 'w'), indent=1)
open(dst, 'a').write('\n')
print('\n'.join(report))
print('wrote %s: %d pages with skip boxes, %d manual pages. Check every line against the page images; '
      'a marker joined with + stands for several blocks (rename it, or split it with marker_before).'
      % (dst, len(pages), len(manual)))
