"""Fix an already-tagged PDF in place (InDesign, Word, Acrobat exports) instead of rebuilding it.
Use when the layout must stay exactly as designed (flyers, posters, one-pagers).
Usage:
  python3 pdf_tagfix.py in.pdf --list            # numbered list of paragraph-level tags and figures with their text
  python3 pdf_tagfix.py in.pdf out.pdf fix.json  # apply
fix.json keys (all optional):
  "title": "..."                         F1 [WCAG+Panorama 2.4.2] dc:title + Info /Title + DisplayDocTitle
  "lang": "en-US"                        F2 [WCAG+Panorama 3.1.1]
  "alt": {"<n>": "alt text"}             F3 [WCAG+Panorama 1.1.1] /Alt on Figure n (from --list)
  "headings": {"<n>": "H1"}              F4 [WCAG+Panorama 1.3.1] retag element n as H1..H6 (no skipped levels)
  "colors": [["old op", "new op"]]       F5 [WCAG+Panorama 1.4.3] exact color operators in the page stream,
                                             e.g. ["0.73 0.34 0 0 k", "0.9 0.6 0 0.2 k"] (fills: lowercase rg/k/g)
  "actualtext": {"<n>": "text"}        spoken text for an element whose spaces were made Artifacts
  "fix_lists": true (default)            F13 [WCC Panorama "List item structure is missing" (Major)]: <LI> with
                                             no <LBody> (Chrome, Google Docs and Skia print-to-PDF) gets one
  "summary": {"<table #>": "text"}      F14 [Panorama "Table does not have a summary" (Minor)] /Summary on the
                                             nth <Table> (0-based, document order)
  "text_figures": true (default)         F15 a <Figure> whose content is only text becomes <P>
  "hoist_text": true (default)           F16 [Panorama "The tag is empty and contains no content" (Minor)]: a heading
                                             whose text sits only in plain <NonStruct>/<Span>
                                             children gets that text directly (Chrome prints every heading this
                                             way; WCC counted each one as an empty tag, 11 on a 3-page sheet)
  "link_refs": true (default)            F19 [Panorama "This link does not have a URL" (Minor)]: a <Link> tag with
                                             no annotation that goes anywhere (footnote numbers) becomes <Reference>
  "alt_from_caption": true | [n, ...]    F20 alt text from each figure's paired caption (+ the heading above it):
                                             --list prints the pairs and CHECKs alt text that drifted onto the wrong
                                             picture (InDesign). Explicit "alt" entries still win.
  "drop_empty": true                     F6 [Panorama] "The tag is empty and contains no content" (Minor):
                                             removes tags with no content and turns marked content that is only
                                             spaces into /Artifact; text drawn twice in the same spot (outline +
                                             fill layers) keeps one copy.
"""
import sys, re, json, pikepdf, pdfplumber
from collections import defaultdict

src = sys.argv[1]
pl = pdfplumber.open(src)
text = defaultdict(lambda: defaultdict(str))     # page index -> mcid -> text
sig = defaultdict(dict)                            # page index -> mcid -> (text, x, y) of its first glyph
for pi, pg in enumerate(pl.pages):
    for c in pg.chars:
        if c.get('mcid') is not None:
            text[pi][c['mcid']] += c['text']
            sig[pi].setdefault(c['mcid'], (round(c['x0'], 1), round(c['top'], 1)))
pdf = pikepdf.open(src, allow_overwriting_input=True)
pages = {p.objgen: i for i, p in enumerate(pdf.pages)}

def kids(e):
    k = e.get('/K')
    return list(k) if isinstance(k, pikepdf.Array) else ([] if k is None else [k])

def mcids(e, pg=None):
    out = []
    if '/Pg' in e: pg = pages.get(e.Pg.objgen, pg)
    for c in kids(e):
        if isinstance(c, int): out.append((pg, int(c)))
        elif isinstance(c, pikepdf.Dictionary):
            if c.get('/Type') == '/MCR': out.append((pages.get(c.Pg.objgen, pg) if '/Pg' in c else pg, int(c.MCID)))
            elif '/S' in c: out += mcids(c, pg)
    return out

rolemap = pdf.Root.StructTreeRoot.get('/RoleMap', {})
def role(e):
    s = str(e.S); return str(rolemap.get(s, s))
BLOCK = {'/P', '/H', '/H1', '/H2', '/H3', '/H4', '/H5', '/H6', '/Figure', '/LI', '/Caption', '/TD', '/TH'}
items = []
def walk(e, parent=None):
    if not isinstance(e, pikepdf.Dictionary) or '/S' not in e: return
    if role(e) in BLOCK:
        items.append((e, parent)); return
    for c in kids(e): walk(c, e)
for c in kids(pdf.Root.StructTreeRoot): walk(c)
desc = lambda e: ''.join(text[pg][m] for pg, m in mcids(e) if pg is not None).strip()

# ---- Figure captions (adapted from Monica Riess's pdf-accessibility-updater, Nov 2026). InDesign exports often list
# <Figure> tags in a different order from the page, so alt text written in page order lands on the wrong picture.
# The <Caption> tagged next to each figure (or inside it) stays paired with it, so use that pairing instead.
same = lambda a, b: a.objgen == b.objgen if a.objgen != (0, 0) else a == b
def is_struct(c): return isinstance(c, pikepdf.Dictionary) and '/S' in c
def as_caption(c):
    """c itself if it is a <Caption>, or the one <Caption> inside a wrapper (InDesign /Story) holding nothing else."""
    if not is_struct(c): return None
    if role(c) == '/Caption': return c
    if role(c) in BLOCK: return None
    found = []
    def f(x):
        for k in kids(x):
            if is_struct(k):
                if role(k) in BLOCK: found.append(k)
                else: f(k)
    f(c)
    return found[0] if len(found) == 1 and role(found[0]) == '/Caption' else None
boxes = defaultdict(dict)                          # page index -> mcid -> [x0, top, x1, bottom]
for pi, pg in enumerate(pl.pages):
    for o in pg.chars + pg.images:
        m = o.get('mcid')
        if m is None: continue
        b = boxes[pi].setdefault(m, [o['x0'], o['top'], o['x1'], o['bottom']])
        b[:] = [min(b[0], o['x0']), min(b[1], o['top']), max(b[2], o['x1']), max(b[3], o['bottom'])]
def centre(e):
    bs = [boxes[pg][m] for pg, m in mcids(e) if pg is not None and m in boxes[pg]]
    if not bs: return None
    return (sum(b[0] + b[2] for b in bs) / (2 * len(bs)), sum(b[1] + b[3] for b in bs) / (2 * len(bs)), mcids(e)[0][0])
def bbox(e):
    """(page, [x0, top, x1, bottom]) of everything e draws, or None when it draws on more than one page or nothing."""
    ms = [(pg, m) for pg, m in mcids(e) if pg is not None and m in boxes[pg]]
    if not ms or len({pg for pg, _ in ms}) != 1: return None
    bs = [boxes[pg][m] for pg, m in ms]
    return ms[0][0], [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]
def gap(a, b):
    """Distance between two boxes on the page (0 when they touch), plus a little for being off-centre."""
    gx = max(0, b[0] - a[2], a[0] - b[2]); gy = max(0, b[1] - a[3], a[1] - b[3])
    return (gx * gx + gy * gy) ** .5 + 0.1 * abs((a[0] + a[2]) / 2 - (b[0] + b[2]) / 2)
# Pair by position first: a figure and a caption that are each other's nearest on the page belong together. Tag order
# alone fails when an export lists "picture, picture, caption, caption" (tested on a two-picture grid, Nov 16, 2026).
_figs = [(i, bbox(e)) for i, (e, _) in enumerate(items) if role(e) == '/Figure']
_caps = [(j, bbox(e)) for j, (e, _) in enumerate(items) if role(e) == '/Caption' and desc(e)]
_figs = [(i, b) for i, b in _figs if b]; _caps = [(j, b) for j, b in _caps if b]
by_pos = {}
for i, fb in _figs:
    near = [(gap(fb[1], cb[1]), j) for j, cb in _caps if cb[0] == fb[0]]
    if not near: continue
    d, j = min(near)
    back = min((gap(fb2[1], dict(_caps)[j][1]), i2) for i2, fb2 in _figs if fb2[0] == fb[0])
    if back[1] == i: by_pos[i] = items[j][0]
def caption_of(e, parent):
    """(caption element or None, note). Looks inside the figure, then on the page, then at the tags beside it."""
    inner = [as_caption(c) for c in kids(e)]
    inner = [c for c in inner if c is not None]
    if inner: return inner[0], 'inside'
    n = next((k for k, (x, _) in enumerate(items) if same(x, e)), None)
    if n in by_pos: return by_pos[n], 'closest on the page'
    sib = kids(parent) if parent is not None else kids(pdf.Root.StructTreeRoot)
    idx = next((j for j, c in enumerate(sib) if is_struct(c) and same(c, e)), None)
    if idx is None: return None, ''
    cands = [as_caption(sib[j]) for j in (idx - 1, idx + 1) if 0 <= j < len(sib)]
    cands = [c for c in cands if c is not None and desc(c)]
    if len(cands) == 1: return cands[0], 'next to it'
    if len(cands) == 2:          # a grid of captioned pictures: take the caption that sits closest on the page
        fc, d = centre(e), []
        for c in cands:
            cc = centre(c)
            if fc and cc and fc[2] == cc[2]: d.append(((fc[0] - cc[0]) ** 2 + (fc[1] - cc[1]) ** 2, c))
        if len(d) == 2 and d[0][0] != d[1][0]: return min(d, key=lambda t: t[0])[1], 'closest on the page'
        return None, 'ambiguous: a caption on both sides'
    return None, ''
def heading_before(n):
    for e, _ in reversed(items[:n]):
        if re.fullmatch(r'/H\d?', role(e)) and desc(e): return desc(e)
    return ''
STOP = {'with', 'from', 'that', 'this', 'image', 'photo', 'picture', 'figure', 'showing', 'shows', 'graphic', 'logo'}
def words(s): return set(re.findall(r'[a-z]{4,}|\d+(?:\.\d+)?', (s or '').lower())) - STOP
def caption_alt(n, cap):
    h, c = heading_before(n), desc(cap)
    return f'{h}: {c}' if h and len(h) <= 40 and h.lower() not in c.lower() else c
fig_caps = {i: caption_of(e, p) for i, (e, p) in enumerate(items) if role(e) == '/Figure'}
def link_target(el):
    for it in kids(el):
        if isinstance(it, pikepdf.Dictionary) and it.get('/Type') == '/OBJR':
            a = it.get('/Obj')
            if isinstance(a, pikepdf.Dictionary) and ('/A' in a or '/Dest' in a): return True
    return '/A' in el and isinstance(el.A, pikepdf.Dictionary) and '/URI' in el.A
dead_links = []
def find_dead(e):
    if not is_struct(e): return
    if role(e) == '/Link' and not link_target(e): dead_links.append(e)
    for c in kids(e): find_dead(c)
for c in kids(pdf.Root.StructTreeRoot): find_dead(c)

if '--list' in sys.argv:
    for i, (e, _) in enumerate(items):
        print(i, role(e), str(e.S), 'Alt=' + str(e.get('/Alt')) if role(e) == '/Figure' else '', repr(desc(e)[:70]))
        if i in fig_caps:
            cap, how = fig_caps[i]
            if cap is None:
                if how: print(f'    caption: {how}')
                continue
            ct, alt = desc(cap), str(e.get('/Alt', ''))
            print(f'    caption ({how}): {ct[:90]!r}')
            if alt.strip() and words(ct) and not (words(ct) & words(alt)):
                other = [j for j, (c2, _) in fig_caps.items() if c2 is not None and j != i and words(desc(c2)) & words(alt)]
                print(f'    CHECK: alt text does not match this caption' + (f'; it matches the caption of figure {other[:3]}' if other else ''))
    for e in dead_links:
        print(f'link that goes nowhere (retagged as Reference unless "link_refs": false): {desc(e)[:40]!r}')
    tables = []
    def ft(e):
        if not isinstance(e, pikepdf.Dictionary) or '/S' not in e: return
        if role(e) == '/Table': tables.append(e)
        for c in kids(e): ft(c)
    for c in kids(pdf.Root.StructTreeRoot): ft(c)
    for i, t in enumerate(tables):    # header text of each table, for writing its summary
        print(f'table {i}:', repr(desc(t)[:110]))
    sys.exit()

dst, cfg = sys.argv[2], json.load(open(sys.argv[3]))
log = []
if cfg.get('title'):
    with pdf.open_metadata() as md: md['dc:title'] = cfg['title']
    pdf.docinfo['/Title'] = cfg['title']
    pdf.Root.ViewerPreferences = pdf.Root.get('/ViewerPreferences', pikepdf.Dictionary())
    pdf.Root.ViewerPreferences.DisplayDocTitle = True
    log.append('title set')
pdf.Root.Lang = cfg.get('lang', str(pdf.Root.get('/Lang', 'en-US')))
afc = cfg.get('alt_from_caption')
if afc:
    # F20 alt text from each figure's own caption (plus the heading above it), for figures listed by number or all
    # captioned figures with true. Fixes alt text that drifted onto the wrong picture. YOU read each one in the log.
    want = set(fig_caps) if afc is True else {int(n) for n in afc}
    for i in sorted(want):
        cap, how = fig_caps.get(i, (None, ''))
        if cap is None:
            if afc is not True or '/Alt' not in items[i][0]:
                log.append(f'figure {i}: no caption paired ({how or "none found"}); write its alt by hand')
            continue
        a = caption_alt(i, cap); items[i][0].Alt = a; log.append(f'alt on {i} from its caption: {a}')
def own_text(e):   # a figure's text, leaving out a <Caption> tagged inside it
    pg = pages.get(e.Pg.objgen) if '/Pg' in e else None
    out = []
    for k in kids(e):
        if is_struct(k):
            if as_caption(k) is None: out += mcids(k, pg)
        elif isinstance(k, int): out.append((pg, int(k)))
        elif isinstance(k, pikepdf.Dictionary) and k.get('/Type') == '/MCR':
            out.append((pages.get(k.Pg.objgen, pg) if '/Pg' in k else pg, int(k.MCID)))
    return ''.join(text[p][m] for p, m in out if p is not None).strip()
if cfg.get('text_figures', True):
    # F15: a <Figure> that holds only text (Google Forms / Sheets legends and labels exported as figures) is text,
    # not an image: retag it /P so it is read as text and needs no alt (WCC: "no alternative description", Severe)
    n_tf = 0
    for i, (e, _) in enumerate(items):
        if role(e) == '/Figure' and str(i) not in cfg.get('alt', {}) and '/Alt' not in e and own_text(e):
            e.S = pikepdf.Name('/P'); n_tf += 1
    if n_tf: log.append(f'figures that were only text retagged as paragraphs: {n_tf}')
for n, alt in cfg.get('alt', {}).items():
    items[int(n)][0].Alt = alt; log.append(f'alt on {n}')
for n, t in cfg.get('actualtext', {}).items():
    items[int(n)][0].ActualText = t; log.append(f'ActualText on {n}')
for n, h in cfg.get('headings', {}).items():
    items[int(n)][0].S = pikepdf.Name('/' + h); log.append(f'{n} -> {h}: {desc(items[int(n)][0])[:40]}')
if cfg.get('fix_lists', True):
    # F13 [WCC Panorama "List item structure is missing" (Major); WCAG 1.3.1]: Chrome / Google Docs / Skia print-to-PDF
    # tags <LI> as Lbl + loose content, with no <LBody>. Wrap everything after the label in an LBody.
    moved = {}                               # (page index, mcid) -> new LBody, for raw MCIDs that move
    def fix_li(e, pg=None):
        if '/Pg' in e: pg = pages.get(e.Pg.objgen, pg)
        for c in kids(e):
            if isinstance(c, pikepdf.Dictionary) and '/S' in c: fix_li(c, pg)
        if role(e) != '/LI': return
        ks = kids(e)
        if any(isinstance(c, pikepdf.Dictionary) and '/S' in c and role(c) == '/LBody' for c in ks):
            if not any(isinstance(c, pikepdf.Dictionary) and '/S' in c and role(c) == '/Lbl' for c in ks):
                # LBody but no Lbl (CSS lists with no visible marker): add a label that speaks as a bullet
                lb = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name('/StructElem'), S=pikepdf.Name('/Lbl'), P=e,
                                                       ActualText='•', K=pikepdf.Array([])))
                e.K = pikepdf.Array([lb] + ks); fixed_li.append(1)
            return
        lbl = [c for c in ks if isinstance(c, pikepdf.Dictionary) and '/S' in c and role(c) == '/Lbl']
        rest = [c for c in ks if not any(c is l for l in lbl)]
        if not rest: return
        body = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name('/StructElem'), S=pikepdf.Name('/LBody'), P=e,
                                                     K=pikepdf.Array(rest)))
        if '/Pg' in e: body.Pg = e.Pg
        for c in rest:
            if isinstance(c, pikepdf.Dictionary) and '/S' in c: c.P = body
            elif isinstance(c, int): moved[(pg, int(c))] = body
            elif isinstance(c, pikepdf.Dictionary) and c.get('/Type') == '/MCR':
                moved[(pages.get(c.Pg.objgen, pg) if '/Pg' in c else pg, int(c.MCID))] = body
        if not lbl:   # no marker tagged at all: a label that speaks as a bullet (WCC accepted this, Nov 2026)
            lbl = [pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name('/StructElem'), S=pikepdf.Name('/Lbl'), P=e,
                                                        ActualText='\u2022', K=pikepdf.Array([])))]
        e.K = pikepdf.Array(lbl + [body])
        fixed_li.append(1)
    fixed_li = []
    for c in kids(pdf.Root.StructTreeRoot):
        if isinstance(c, pikepdf.Dictionary) and '/S' in c: fix_li(c)
    if moved:    # point the ParentTree entries of moved MCIDs at their new LBody
        pt = pdf.Root.StructTreeRoot.get('/ParentTree')
        def nums(n):
            if '/Nums' in n:
                a = n.Nums
                for i in range(0, len(a), 2): yield int(a[i]), a[i + 1]
            for kd in n.get('/Kids', []): yield from nums(kd)
        for key, arr in nums(pt) if pt is not None else []:
            pi = next((i for i, p in enumerate(pdf.pages) if int(p.get('/StructParents', -1)) == key), None)
            if pi is None or not isinstance(arr, pikepdf.Array): continue
            for m in range(len(arr)):
                if (pi, m) in moved: arr[m] = moved[(pi, m)]
    if fixed_li: log.append(f'list items given an LBody: {len(fixed_li)}')
if cfg.get('hoist_text', True):
    # F16: Panorama reads a heading/paragraph as empty unless marked content hangs directly off it.
    HOIST = {'/H', '/H1', '/H2', '/H3', '/H4', '/H5', '/H6'}   # not P: lifting paragraphs (bare MCIDs) made
    # WCC flag "Check reading order" (Severe) at page breaks; Panorama only counted the headings as empty
    moved2, hoisted = {}, []
    def page_of(e, pg):
        return pages.get(e.Pg.objgen, pg) if '/Pg' in e else pg
    def hoist(e, pg=None):
        pg = page_of(e, pg)
        for c in kids(e):
            if isinstance(c, pikepdf.Dictionary) and '/S' in c: hoist(c, pg)
        if role(e) not in HOIST: return
        ks = kids(e)
        if any(isinstance(c, int) or (isinstance(c, pikepdf.Dictionary) and c.get('/Type') == '/MCR') for c in ks): return
        new, changed = [], False
        for c in ks:
            if isinstance(c, pikepdf.Dictionary) and '/S' in c and str(c.S) in ('/NonStruct', '/Span') and '/A' not in c \
                    and '/ActualText' not in c and '/Alt' not in c:
                cpg = page_of(c, pg); cks = kids(c)
                if cks and all(isinstance(x, int) or (isinstance(x, pikepdf.Dictionary) and x.get('/Type') == '/MCR') for x in cks):
                    for x in cks:
                        if isinstance(x, int):
                            mcr = pikepdf.Dictionary(Type=pikepdf.Name('/MCR'), MCID=x, Pg=pdf.pages[cpg].obj)
                            new.append(mcr); moved2[(cpg, int(x))] = e
                        else:
                            new.append(x); moved2[(page_of(x, cpg), int(x.MCID))] = e
                    changed = True; continue
            new.append(c)
        if changed:
            # Panorama only counts a bare MCID number as content, not an MCR dictionary: when every piece is on
            # one page, give the element that page and use plain numbers. A paragraph that runs onto the next
            # page is left as it was: lifting both pages' text into it made WCC flag "Check reading order"
            # (Severe) at the page break.
            pgs = {page_of(x, pg) for x in new if isinstance(x, pikepdf.Dictionary) and x.get('/Type') == '/MCR'}
            if len(pgs) != 1:
                for (pp, mm), el in list(moved2.items()):
                    if el is e: del moved2[(pp, mm)]
                return
            if True:
                only = pgs.pop()
                if '/Pg' not in e or pages.get(e.Pg.objgen) == only:
                    e.Pg = pdf.pages[only].obj
                    new = [pikepdf.Integer(int(x.MCID)) if isinstance(x, pikepdf.Dictionary) and x.get('/Type') == '/MCR' else x for x in new]
            e.K = pikepdf.Array(new) if len(new) != 1 else new[0]; hoisted.append(1)
    for c in kids(pdf.Root.StructTreeRoot):
        if isinstance(c, pikepdf.Dictionary) and '/S' in c: hoist(c)
    if moved2:
        pt = pdf.Root.StructTreeRoot.get('/ParentTree')
        def nums2(n):
            if '/Nums' in n:
                a = n.Nums
                for i in range(0, len(a), 2): yield int(a[i]), a[i + 1]
            for kd in n.get('/Kids', []): yield from nums2(kd)
        for key, arr in nums2(pt) if pt is not None else []:
            pi = next((i for i, p in enumerate(pdf.pages) if int(p.get('/StructParents', -1)) == key), None)
            if pi is None or not isinstance(arr, pikepdf.Array): continue
            for m in range(len(arr)):
                if (pi, m) in moved2: arr[m] = moved2[(pi, m)]
    if hoisted: log.append(f'headings/paragraphs given their text directly: {len(hoisted)}')
if cfg.get('summary'):
    tables = []
    def ft(e):
        if not isinstance(e, pikepdf.Dictionary) or '/S' not in e: return
        if role(e) == '/Table': tables.append(e)
        for c in kids(e): ft(c)
    for c in kids(pdf.Root.StructTreeRoot): ft(c)
    for n, t in cfg['summary'].items():
        e = tables[int(n)]
        a = e.get('/A')
        attr = pikepdf.Dictionary(O=pikepdf.Name('/Table'), Summary=t)
        if a is None: e.A = attr
        elif isinstance(a, pikepdf.Array): a.append(attr)
        else: e.A = pikepdf.Array([a, attr])
    log.append(f'table summaries: {len(cfg["summary"])} of {len(tables)} tables')
BLANK = {}
if cfg.get('colors') or cfg.get('drop_empty'):
    for pi, page in enumerate(pdf.pages):
        data = page.Contents.read_bytes() if not isinstance(page.Contents, pikepdf.Array) else b'\n'.join(x.read_bytes() for x in page.Contents)
        for old, new in cfg.get('colors', []):
            data, k = re.subn(rb'(?<![\d.])' + re.escape(old.encode()) + rb'(?=\s)', new.encode(), data)
            log.append(f'page {pi + 1}: {old} -> {new} x{k}')
        if cfg.get('drop_empty'):
            blank = {m for m, t in text[pi].items() if not t.strip()}
            # F6b: the same text drawn twice in the same place (an outline/shadow layer under the fill) is read twice
            # by screen readers and confuses Panorama's reading-order check: keep the first copy, artifact the rest
            seen = {}
            for m in sorted(text[pi], reverse=True):     # keep the LAST copy: the fill is drawn on top of its outline
                k = (text[pi][m].strip(), sig[pi].get(m))
                if k[0] and k in seen: blank.add(m); log.append(f'page {pi + 1}: MCID {m} repeats MCID {seen[k]} ("{k[0][:30]}") -> Artifact')
                else: seen.setdefault(k, m)
            for m in blank:
                data, k = re.subn(rb'/\w+\s*<<[^<>]*?/MCID ' + str(m).encode() + rb'\b[^<>]*>>\s*BDC', b'/Artifact BMC', data)
            if blank: log.append(f'page {pi + 1}: space-only content -> Artifact: MCIDs {sorted(blank)}')
            BLANK[pi] = blank
        page.Contents = pdf.make_stream(data)
if cfg.get('drop_empty'):
    blanks = {(i, m) for i, bs in BLANK.items() for m in bs}
    def prune(e, pg=None):
        if '/Pg' in e: pg = pages.get(e.Pg.objgen, pg)
        ks = kids(e); keep = []
        for c in ks:
            if isinstance(c, int):
                if (pg, int(c)) not in blanks: keep.append(c)
            elif isinstance(c, pikepdf.Dictionary) and c.get('/Type') == '/MCR':
                if (pages.get(c.Pg.objgen, pg) if '/Pg' in c else pg, int(c.MCID)) not in blanks: keep.append(c)
            elif isinstance(c, pikepdf.Dictionary) and '/S' in c:
                prune(c, pg)
                if kids(c) or role(c) == '/Figure': keep.append(c)
                else: log.append(f'dropped empty <{str(c.S)[1:]}>')
            else: keep.append(c)
        if len(keep) != len(ks):
            e.K = pikepdf.Array(keep) if len(keep) != 1 else keep[0]
    for c in kids(pdf.Root.StructTreeRoot):
        if isinstance(c, pikepdf.Dictionary): prune(c)
    # rebuild the ParentTree entries for removed MCIDs is not needed: orphaned entries only point at live elements
if cfg.get('link_refs', True) and dead_links:
    # F19 [Panorama "This link does not have a URL", Minor] a <Link> with no annotation that goes anywhere is a
    # footnote number or cross-reference (Word exports do this): retag it <Reference>. From Monica Riess's skill.
    for e in dead_links:
        e.S = pikepdf.Name('/Reference'); log.append(f'link that went nowhere retagged as Reference: {desc(e)[:40]!r}')
pdf.save(dst)
print('\n'.join(log))
