"""Panorama pre-flight for PDFs. Usage: python3 preflight_pdf.py file.pdf
Want: every line OK."""
import sys, re, collections
import pikepdf, pdfplumber

path = sys.argv[1]
pdf = pikepdf.open(path)
root = pdf.Root
ok = lambda b: 'OK ' if b else 'FAIL'

info_title = str(pdf.docinfo.get('/Title', '')) if pdf.docinfo is not None else ''
vp = root.get('/ViewerPreferences')
print(ok(bool(info_title.strip())), 'F1 document title:', repr(info_title))
print(ok(vp is not None and bool(vp.get('/DisplayDocTitle'))), 'F1 DisplayDocTitle on')
print(ok(bool(str(root.get('/Lang', '')).strip())), 'F2 document language:', root.get('/Lang'))
tagged = '/StructTreeRoot' in root and bool(root.get('/MarkInfo', {}).get('/Marked', False))
print(ok(tagged), 'F3 tagged (structure tree + Marked)')
if not tagged:
    sys.exit()

tags = collections.Counter(); figs = []; tables = []
def walk(el):
    if isinstance(el, pikepdf.Dictionary):
        s = str(el.get('/S', ''))
        rm = root.StructTreeRoot.get('/RoleMap', {})
        tags[s] += 1
        if s == '/Figure': figs.append(el)
        if s == '/Table': tables.append(el)
        k = el.get('/K')
        if k is None: return
        for it in (list(k) if isinstance(k, pikepdf.Array) else [k]):
            if isinstance(it, pikepdf.Dictionary): walk(it)
walk(root.StructTreeRoot)
heads = [t for t in tags if re.fullmatch(r'/H\d', t)]
print(ok(bool(heads)), 'F4 headings tagged:', {h: tags[h] for h in sorted(heads)})
print(ok('/H1' in tags), 'F4 has an H1')
noalt = [f for f in figs if not str(f.get('/Alt', '')).strip() and not str(f.get('/ActualText', '')).strip()]
print(ok(not noalt), f'F5 figures with alt text: {len(figs) - len(noalt)}/{len(figs)}')
def has_summary(t):
    a = t.get('/A')
    items = list(a) if isinstance(a, pikepdf.Array) else ([a] if a is not None else [])
    return any(isinstance(x, pikepdf.Dictionary) and str(x.get('/Summary', '')).strip() for x in items)
print(ok(all(has_summary(t) for t in tables)), f'F6 tables with /Summary: {sum(has_summary(t) for t in tables)}/{len(tables)}')
print(ok(tags.get('/TH', 0) > 0 or not tables), f'F7 table header cells (TH): {tags.get("/TH", 0)}')

# untagged drawing (not inside marked content / artifacts)
untagged = 0
for page in pdf.pages:
    depth = 0
    for operands, op in pikepdf.parse_content_stream(page):
        o = str(op)
        if o in ('BDC', 'BMC'): depth += 1
        elif o == 'EMC': depth -= 1
        elif o in ('Tj', 'TJ', "'", '"') and depth == 0: untagged += 1
print(ok(untagged == 0), f'F8 untagged text operations: {untagged}')

# text size: WCC Panorama flags anything under 12 pt; shrunk sub/superscripts count too
pl = pdfplumber.open(path)
small = collections.defaultdict(set); sizes = collections.Counter()
for i, pg in enumerate(pl.pages, 1):
    for ch in pg.chars:
        s = round(ch['size'], 1); sizes[s] += 1
        if s < 12 and ch['text'].strip(): small[s].add(i)
print(ok(not small), 'F9 text under 12 pt:', {k: sorted(v)[:12] for k, v in small.items()} or 'none')
print('    sizes used:', sorted(sizes.items()))

# baseline shift: glyphs sitting off their line's baseline (raised/lowered text), any size.
# WCC Panorama flagged every page containing such glyphs as "Check reading order" (Severe).
shift = collections.defaultdict(list)
for i, pg in enumerate(pl.pages, 1):
    chars = [c for c in pg.chars if c['text'].strip()]
    for c in chars:
        nb = [o for o in chars if o is not c and 0 < abs(o['x0'] - c['x0']) < 25
              and min(o['bottom'], c['bottom']) - max(o['top'], c['top']) > 0.5 * min(o['size'], c['size'])]
        if len(nb) >= 2:
            base = sorted(o['bottom'] for o in nb)[len(nb) // 2]
            if 0.8 < abs(c['bottom'] - base) < 0.6 * c['size'] and sum(abs(o['bottom'] - base) < 0.3 for o in nb) >= 2:
                shift[i].append(c['text'])
print(ok(not shift), 'F10 text shifted off the baseline (sub/superscript):', {p: ''.join(v)[:20] for p, v in shift.items()} or 'none')
# F11 [WCC Panorama] real footnotes/endnotes (a /Note tag, page-bottom note text) also give "Check reading order"
# (Severe). Fix in the .docx with inline_notes.py before exporting.
print(ok(tags.get('/Note', 0) == 0), 'F11 footnote/endnote tags (/Note):', tags.get('/Note', 0))

# F20 [WCC Panorama "Check reading order" (Severe)]: on each page, the MCID numbers of text and pictures must go up in
# tag order. Seven one-page test PDFs (Nov 17, 2026): numbers out of tag order were flagged; the same tags renumbered
# scored 100%, whatever the page position or drawing order. Fix in place: pdf_tagfix.py (mcid_order, on by default).
# F21: does the tag order follow the page (top to bottom in a column, left to right on a line)? Panorama does not check
# this, but a screen reader reads the tags in order (WCAG 1.3.2). Fix: pdf_tagfix.py "tag_order": true, or by hand.
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdf_order
OB, OT = pdf_order.boxes(pl)
num = pdf_order.number_order(pdf, pdf_order.content(pl))
print(ok(not num), 'F20 MCID numbers go up in tag order (text and pictures):',
      {p + 1: v[0] for p, v in sorted(num.items())} or 'yes')
for p, (k, seq) in sorted(num.items())[:4]: print(f'    page {p + 1}: MCIDs in tag order start {seq}')
inv = pdf_order.inversions(pdf, OB, OT)
print(ok(not inv), 'F21 tag order follows the page (top to bottom in a column, left to right on a line):',
      {p + 1: len(v) for p, v in sorted(inv.items())} or 'yes')
ex = [(p, a, b) for p, v in sorted(inv.items()) for a, b in v[:2]]
for p, a, b in ex[:8]: print(f'    page {p + 1}: "{a}" is tagged before "{b}", which comes first on the page')
