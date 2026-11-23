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
        if re.fullmatch(r'/H[1-6]', s): hseq.append(int(s[2]))
        if s == '/Figure': figs.append(el)
        if s == '/Table': tables.append(el)
        k = el.get('/K')
        if k is None: return
        for it in (list(k) if isinstance(k, pikepdf.Array) else [k]):
            if isinstance(it, pikepdf.Dictionary): walk(it)
hseq = []
walk(root.StructTreeRoot)
heads = [t for t in tags if re.fullmatch(r'/H\d', t)]
print(ok(bool(heads)), 'F4 headings tagged:', {h: tags[h] for h in sorted(heads)})
print(ok('/H1' in tags), 'F4 has an H1')
_skips = [(a, b) for a, b in zip(hseq, hseq[1:]) if b > a + 1]
print(ok(not _skips), 'F4b heading levels nested, no skips (Panorama "heading structure is not properly nested", Severe):', _skips[:6] or 'yes')
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

# The three checks below are adapted from Monica Riess's pdf-accessibility-updater skill (Nov 2026).
# F17 [WCAG 1.3.1; Panorama "The tag is empty and contains no content" (Minor) for a tag naming a missing MCID,
# WCC Nov 16, 2026] tags must point at real page content. A tree whose tags name marked-content
# IDs (MCIDs) that aren't on the page reads as "empty page" in Acrobat Read Aloud and screen readers, even when
# Panorama scores the file 100%. Form XObjects (/Stm) are checked too.
def bdc_mcids(ops, props):
    s = set()
    for operands, op in ops:
        if str(op) == 'BDC' and len(operands) == 2:
            d = operands[1]
            if isinstance(d, pikepdf.Name): d = props.get(d) if props is not None else None
            if isinstance(d, pikepdf.Dictionary) and '/MCID' in d: s.add(int(d.MCID))
    return s
def props_of(obj):
    r = obj.get('/Resources')
    return r.get('/Properties') if isinstance(r, pikepdf.Dictionary) else None
pg_index = {p.objgen: i for i, p in enumerate(pdf.pages)}
on_page = {}
for i, page in enumerate(pdf.pages):
    try: on_page[i] = bdc_mcids(pikepdf.parse_content_stream(page), props_of(page.obj))
    except Exception: on_page[i] = set()
in_stm = {}
missing, used = [], set()
def wire(el, pg=None):
    if not isinstance(el, pikepdf.Dictionary): return
    if '/Pg' in el: pg = pg_index.get(el.Pg.objgen, pg)
    k = el.get('/K')
    if k is None: return
    for it in (list(k) if isinstance(k, pikepdf.Array) else [k]):
        if isinstance(it, int):
            used.add((pg, int(it)))
            if pg is None or int(it) not in on_page.get(pg, set()): missing.append((pg, int(it)))
        elif isinstance(it, pikepdf.Dictionary) and it.get('/Type') == '/MCR':
            mpg = pg_index.get(it.Pg.objgen, pg) if '/Pg' in it else pg
            if '/Stm' in it:
                key = it.Stm.objgen
                if key not in in_stm:
                    try: in_stm[key] = bdc_mcids(pikepdf.parse_content_stream(it.Stm), props_of(it.Stm))
                    except Exception: in_stm[key] = set()
                if int(it.MCID) not in in_stm[key]: missing.append((mpg, int(it.MCID)))
            else:
                used.add((mpg, int(it.MCID)))
                if mpg is None or int(it.MCID) not in on_page.get(mpg, set()): missing.append((mpg, int(it.MCID)))
        elif isinstance(it, pikepdf.Dictionary) and '/S' in it: wire(it, pg)
wire(root.StructTreeRoot)
no_parents = [i + 1 for i, page in enumerate(pdf.pages) if on_page[i] and '/StructParents' not in page.obj]
orphans = {}
for i, ms in on_page.items():
    o = sorted(m for m in ms if (i, m) not in used)
    if o: orphans[i + 1] = o
pt = root.StructTreeRoot.get('/ParentTree')
empty_pt = any(on_page.values()) and (pt is None or (not len(pt.get('/Nums', [])) and '/Kids' not in pt))
wire_ok = not missing and not no_parents and not empty_pt and not orphans
print(ok(wire_ok), 'F17 tags point at real page content (a tag naming missing content = Panorama "The tag is empty", Minor):',
      'yes' if wire_ok else '; '.join(x for x in [
          f'{len(missing)} tag(s) point at content that is not on the page (pages {sorted({p + 1 for p, _ in missing if p is not None})[:12]})' if missing else '',
          f'pages with tagged content but no /StructParents: {no_parents[:12]}' if no_parents else '',
          'the ParentTree is missing or empty' if empty_pt else '',
          f'tagged content that no tag points at (page: MCIDs): {dict(list(orphans.items())[:6])}' if orphans else ''] if x))

# F18 [WCAG 1.4.3; Panorama "Insufficient contrast between foreground text and background", Severe] text color
# against what is behind it: the smallest filled shape under each character, or white. Uses the color space each
# character was drawn in, so gray, RGB and CMYK (k/K, what InDesign uses) are all read. WCC flagged 30 pt text at
# 3.5:1, so the target is 4.5:1 for every size. Text on a picture is listed for a check by eye.
def to_rgb(v, cs):
    if isinstance(v, (int, float)): v = (v,)        # pdfplumber gives a gray as a bare number on some pages
    v = tuple(float(x) for x in (v or ()) if isinstance(x, (int, float)))
    cs = str(cs or '')
    if any(s in cs for s in ('Separation', 'DeviceN', 'Indexed', 'Pattern')): return None   # spot inks: tint, not gray
    if len(v) == 1: return (v[0],) * 3
    if len(v) == 3 and ('RGB' in cs or 'ICC' in cs or 'Cal' in cs or not cs): return v
    if len(v) == 4: return cmyk_rgb(*v)
    return None
def cmyk_rgb(c, m, y, k):
    """CMYK as PDF.js draws it (a fit to US SWOP), not the naive (1-c)(1-k): tested at WCC, Nov 16, 2026, an orange
    darkened to 5.1:1 by the naive formula still failed in Panorama; this one gives 4.09:1 for it."""
    r = 255 + c * (-4.387332384609988 * c + 54.48615194189176 * m + 18.82290502165302 * y + 212.25662451639585 * k - 285.2331026137004) \
        + m * (1.7149763477362134 * m - 5.6096736904047315 * y - 17.873870861415444 * k - 5.497006427196366) \
        + y * (-2.5217340131683033 * y - 21.248923337353073 * k - 17.5119270841813) + k * (-21.86122147463605 * k - 189.48180835922747)
    g = 255 + c * (8.841041422036149 * c + 60.118027045597366 * m + 6.871425592049007 * y + 31.159100130055922 * k - 79.2970844816548) \
        + m * (-15.310361306967817 * m + 17.575251261109482 * y + 131.35250912493976 * k - 190.9453302588951) \
        + y * (4.444339102852739 * y + 9.8632861493405 * k - 24.86741582555878) + k * (-20.737325471181034 * k - 187.80453709719578)
    b = 255 + c * (0.8842522430003296 * c + 8.078677503112928 * m + 30.89978309703729 * y - 0.23883238689178934 * k - 14.183576799673286) \
        + m * (10.49593273432072 * m + 63.02378494754052 * y + 50.606957656360734 * k - 112.23884253719248) \
        + y * (0.03296041114873217 * y + 115.60384449646641 * k - 193.58209356861505) + k * (-22.33816807309886 * k - 180.12613974708367)
    return tuple(max(0.0, min(255.0, x)) / 255 for x in (r, g, b))
def lum(rgb):
    ch = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(rgb[0]) + 0.7152 * ch(rgb[1]) + 0.0722 * ch(rgb[2])
def ratio(a, b):
    la, lb = lum(a), lum(b); return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)
def literal_op(page, vals, cs):
    """The color operator exactly as written in the page stream, for pdf_tagfix.py "colors"."""
    ops = {1: b'g|sc|scn', 3: b'rg|sc|scn', 4: b'k|sc|scn'}.get(len(vals))
    if not ops: return None
    data = b''
    try:
        c = page.obj.get('/Contents')
        data = b'\n'.join(s.read_bytes() for s in (list(c) if isinstance(c, pikepdf.Array) else [c]))
    except Exception: pass
    num = rb'(-?\d*\.?\d+)'
    pat = re.compile(rb'(?<![\w.])' + rb'\s+'.join([num] * len(vals)) + rb'\s+(' + ops + rb')\b')
    for m in pat.finditer(data):
        if all(abs(float(m.group(i + 1)) - vals[i]) < 0.002 for i in range(len(vals))): return m.group(0).decode()
    return None
def darker(vals, bg):
    """A passing color close to the old one (aim 5:1 on its background), written as the same kind of operator."""
    vals = list(vals)
    for _ in range(200):
        rgb = to_rgb(vals, 'DeviceCMYK' if len(vals) == 4 else 'DeviceRGB')
        if ratio(rgb, bg) >= 5: return vals
        if len(vals) == 4: vals[3] = min(1, vals[3] + 0.01)
        else: vals = [max(0, x - 0.01) for x in vals]
    return vals
low, on_pic = {}, collections.Counter()
for i, pg in enumerate(pl.pages):
    fills = [r for r in pg.rects + pg.curves if r.get('fill') and to_rgb(r.get('non_stroking_color'), None) is not None]
    for ch in pg.chars:
        if not ch['text'].strip(): continue
        fg = to_rgb(ch.get('non_stroking_color'), ch.get('ncs'))
        if fg is None: continue
        cx, cy = (ch['x0'] + ch['x1']) / 2, (ch['top'] + ch['bottom']) / 2
        if any(im['x0'] <= cx <= im['x1'] and im['top'] <= cy <= im['bottom'] for im in pg.images):
            on_pic[i + 1] += 1; continue
        under = [r for r in fills if r['x0'] <= cx <= r['x1'] and r['top'] <= cy <= r['bottom']
                 and (r['x1'] - r['x0']) * (r['bottom'] - r['top']) < pg.width * pg.height * 0.98]
        bg = to_rgb(min(under, key=lambda r: (r['x1'] - r['x0']) * (r['bottom'] - r['top']))['non_stroking_color'], None) if under else (1, 1, 1)
        r = ratio(fg, bg)
        if r < 4.5:
            raw = tuple(round(float(x), 3) for x in ch['non_stroking_color'])
            key = (raw, tuple(round(x, 3) for x in bg))
            e = low.setdefault(key, {'ratio': r, 'pages': set(), 'chars': 0, 'sample': '', 'pi': i, 'cs': ch.get('ncs')})
            e['pages'].add(i + 1); e['chars'] += 1
            if len(e['sample']) < 30: e['sample'] += ch['text']
print(ok(not low), f'F18 text contrast under 4.5:1: {len(low)} color(s)' if low else 'F18 text contrast: all text 4.5:1 or better on what is behind it')
for (raw, bg), e in sorted(low.items(), key=lambda kv: kv[1]['ratio']):
    op = literal_op(pdf.pages[e['pi']], raw, e['cs'])
    # CMYK text is replaced with an RGB color (rg): at WCC an orange darkened in CMYK to 5:1 (by PDF.js's own
    # conversion) still failed in Panorama, Nov 16, 2026, so Panorama reads CMYK lighter than it draws it.
    cmyk = len(raw) == 4
    new = (darker(list(to_rgb(raw, e['cs'])), bg) if cmyk else darker(raw, bg)) if lum(bg) > 0.5 else None
    sug = ''
    if op and new is not None:
        newop = ' '.join(f'{x:.3f}'.rstrip('0').rstrip('.') or '0' for x in new) + ' ' + ('rg' if cmyk else op.split()[-1])
        sug = f'  fix: ["{op}", "{newop}"]'
    elif op: sug = f'  operator "{op}" (dark background: lighten the text or darken the shape)'
    print(f'    {e["ratio"]:.2f}:1  {e["cs"]} {raw} on {"white" if bg == (1, 1, 1) else bg}, pages {sorted(e["pages"])[:12]},'
          f' {e["chars"]} characters, e.g. "{e["sample"]}"{sug}')
# Panorama measures text on a picture against the picture's pixels (WCC flagged gray text on a dark photo, Nov 16)
print('CHECK' if on_pic else 'OK ', 'F18b text on a picture (Panorama measures the pixels; check by eye):', dict(on_pic) or 'none')

# F19 [Panorama "This link does not have a URL", Minor] a <Link> tag with no link annotation that goes anywhere.
# Word exports tag footnote numbers this way. pdf_tagfix.py retags them as <Reference> ("link_refs", on by default).
def link_target(el):
    k = el.get('/K')
    for it in (list(k) if isinstance(k, pikepdf.Array) else ([] if k is None else [k])):
        if isinstance(it, pikepdf.Dictionary) and it.get('/Type') == '/OBJR':
            a = it.get('/Obj')
            if isinstance(a, pikepdf.Dictionary) and ('/A' in a or '/Dest' in a): return True
    return '/A' in el and isinstance(el.A, pikepdf.Dictionary) and '/URI' in el.A
nolink = []
def find_links(el):
    if not isinstance(el, pikepdf.Dictionary): return
    s = str(el.get('/S', ''))
    if str(root.StructTreeRoot.get('/RoleMap', {}).get(s, s)) == '/Link' and not link_target(el): nolink.append(el)
    k = el.get('/K')
    for it in (list(k) if isinstance(k, pikepdf.Array) else ([] if k is None else [k])):
        if isinstance(it, pikepdf.Dictionary) and '/S' in it: find_links(it)
find_links(root.StructTreeRoot)
print(ok(not nolink), f'F19 link tags that go nowhere (footnote numbers tagged as links): {len(nolink)}')

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

# F22 [WCC Panorama "Check reading order" (Severe), one per page with a link]: links in a PDF that LibreOffice
# exported. Nov 19, 2026: 16 one-page tests changed the LibreOffice file in every way we could think of (links joined,
# reordered, /Contents, /F, the tag name and shape, the clip and underline) and all scored 0%; the same page without its
# link scored 100%, and the same links printed by Chrome scored 100%. Fix: docx2pdf_ua.py (it prints a PDF with links
# again through Chrome), or pdf_tag2html.py -> Chrome -> pdf_tagfix.py.
_meta = ' '.join(str(pdf.docinfo.get(k, '')) for k in ('/Producer', '/Creator')) if pdf.trailer.get('/Info') is not None else ''
try:
    with pdf.open_metadata() as _md: _meta += ' ' + str(_md.get('pdf:Producer', '')) + ' ' + str(_md.get('xmp:CreatorTool', ''))
except Exception: pass
_lo = 'libreoffice' in _meta.lower() or 'openoffice' in _meta.lower()
_lpages = [i + 1 for i, pg in enumerate(pdf.pages) if any(a.get('/Subtype') == '/Link' for a in pg.obj.get('/Annots', []))]
print(ok(not (_lo and _lpages)), 'F22 links in a PDF exported by LibreOffice (Panorama flags each of these pages):',
      _lpages[:12] if _lo and _lpages else 'none')

# F23 [Panorama "The hyperlink text is not descriptive", Minor, one per link]: link text that is only a web address.
# Nov 22, 2026: a guide's two links reading "claude.ai" were flagged (70%); "LinkedIn (Chris Pasquini)", "GitHub" and
# an email address were not. Same pattern pdf_tag2html.py uses for Canvas pages. Fix: name the page in the link text.
_BARE = re.compile(r'^\s*(https?://|www\.|[\w-]+(\.[\w-]+)*\.(com|org|edu|net|gov|us|io|ca|uk|ai)(/|\s*$))\S?')
_bare = []
for _i, _pg in enumerate(pl.pages):
    _by = collections.defaultdict(list)                       # a link that wraps is two annotations with one address
    for _h in (_pg.hyperlinks or []):
        _by[_h.get('uri')].append(_h)
    for _u, _hs in _by.items():
        if not _u or str(_u).startswith('mailto:'): continue
        for _h in _hs:
            _bb = (max(0, _h['x0']), max(0, _h['top']), min(_pg.width, _h['x1']), min(_pg.height, _h['bottom']))
            _t = (_pg.crop(_bb).extract_text() or '').strip() if _bb[2] > _bb[0] and _bb[3] > _bb[1] else ''
            _t = _t.rstrip('.,;:)”"\'')                  # the box can take in the period after the link
            if _t and _BARE.match(_t): _bare.append((_i + 1, _t))
print(ok(not _bare), 'F23 link text that is only a web address (Panorama: "The hyperlink text is not descriptive"):',
      _bare[:8] or 'none')
