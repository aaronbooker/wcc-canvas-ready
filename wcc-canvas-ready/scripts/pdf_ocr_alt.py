"""Alt text for <Figure> tags that are really text drawn as shapes. F5 [WCAG 1.1.1 + Panorama, Severe].
Usage: python3 pdf_ocr_alt.py in.pdf out.pdf [--min-chars 3] [--list]
Learned at WCC (Nov 2026): a Google Forms "print summary" PDF tags every chart legend entry and label as a
<Figure> whose content is vector outlines of letters, not text, so Panorama reports 40 missing alt texts (0%).
For each Figure with no /Alt, its area is rendered at 300 dpi and OCR'd (Tesseract); if it reads as text, that
text becomes the alt (it is what the image says). Figures that don't read as text (real pictures, chart
drawings) are listed for YOU to describe with pdf_tagfix.py "alt". Proofread the OCR'd alt text.
"""
import sys, subprocess, tempfile, os, re
import pikepdf, pdfplumber
src, dst = sys.argv[1], sys.argv[2]
LIST = '--list' in sys.argv
minc = int(sys.argv[sys.argv.index('--min-chars') + 1]) if '--min-chars' in sys.argv else 3
pdf = pikepdf.open(src)
pl = pdfplumber.open(src)
pages = {p.objgen: i for i, p in enumerate(pdf.pages)}
def kids(e):
    k = e.get('/K'); return list(k) if isinstance(k, pikepdf.Array) else ([] if k is None else [k])
figs = []
def walk(e, pg=None):
    if not isinstance(e, pikepdf.Dictionary) or '/S' not in e: return
    if '/Pg' in e: pg = pages.get(e.Pg.objgen, pg)
    if str(e.S) == '/Figure' and '/Alt' not in e:
        ms = []
        def mc(x, pg):
            if isinstance(x, int): ms.append((pg, int(x)))
            elif isinstance(x, pikepdf.Dictionary):
                if x.get('/Type') == '/MCR': ms.append((pages.get(x.Pg.objgen, pg) if '/Pg' in x else pg, int(x.MCID)))
                elif '/S' in x:
                    for y in kids(x): mc(y, pages.get(x.Pg.objgen, pg) if '/Pg' in x else pg)
        for x in kids(e): mc(x, pg)
        figs.append((e, ms)); return
    for c in kids(e): walk(c, pg)
for c in kids(pdf.Root.StructTreeRoot): walk(c)
tmp = tempfile.mkdtemp(); done = todo = 0
for n, (e, ms) in enumerate(figs):
    boxes = []
    for pg, m in ms:
        if pg is None: continue
        P = pl.pages[pg]
        for o in P.objects.get('curve', []) + P.objects.get('rect', []) + P.objects.get('line', []) + P.images + P.chars:
            if o.get('mcid') == m: boxes.append((pg, o['x0'], o['top'], o['x1'], o['bottom']))
    if not boxes:
        print(f'figure {n}: no drawable content found (YOU: alt or decorative)'); todo += 1; continue
    pg = boxes[0][0]
    x0 = max(0, min(b[1] for b in boxes) - 2); t = max(0, min(b[2] for b in boxes) - 2)
    x1 = max(b[3] for b in boxes) + 2; b_ = max(b[4] for b in boxes) + 2
    img = pl.pages[pg].crop((x0, t, min(x1, pl.pages[pg].width), min(b_, pl.pages[pg].height))).to_image(resolution=300)
    f = os.path.join(tmp, f'{n}.png'); img.save(f)
    txt = subprocess.run(['tesseract', f, '-', '--psm', '7' if b_ - t < 20 else '6'], capture_output=True, text=True).stdout
    txt = re.sub(r'\s+', ' ', txt).strip()
    # common Tesseract slips on UI fonts: a lone "|" is "I", "ld"/"lm" at a word start are "I'd"/"I'm"
    txt = re.sub(r'(^|\s)\|(\s)', r'\1I\2', txt); txt = re.sub(r'\bl([dm])\b', r"I'\1", txt)
    txt = re.sub(r'(\.\.\.?|_|-)$', '...', txt) if re.search(r'[._-]$', txt) else txt
    if len(re.sub(r'\W', '', txt)) >= minc and (x1 - x0) * (b_ - t) < 60000:
        e.Alt = txt; done += 1
        if LIST: print(f'figure {n} (page {pg + 1}): "{txt}"')
    else:
        print(f'figure {n} (page {pg + 1}, {round(x1 - x0)}x{round(b_ - t)} pt): not text (YOU: describe it). OCR saw: {txt[:60]!r}'); todo += 1
pdf.save(dst)
print(f'alt from OCR: {done}; left for YOU: {todo}')
