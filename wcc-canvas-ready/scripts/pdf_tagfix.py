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
  "mcid_order": true (default)           F20 [WCC Panorama "Check reading order" (Severe)]: renumbers each page's
                                             MCIDs so they go up in tag order (what Panorama checks). Changes
                                             nothing a reader sees or hears
  "tag_order": true                      F21 [WCAG 1.3.2; not checked by Panorama]: puts child tags in page order
                                             (top to bottom in a column, left to right on a line) where
                                             preflight_pdf.py F21 failed; only tags clearly out of order move
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

if '--list' in sys.argv:
    for i, (e, _) in enumerate(items):
        print(i, role(e), str(e.S), 'Alt=' + str(e.get('/Alt')) if role(e) == '/Figure' else '', repr(desc(e)[:70]))
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
if cfg.get('text_figures', True):
    # F15: a <Figure> that holds only text (Google Forms / Sheets legends and labels exported as figures) is text,
    # not an image: retag it /P so it is read as text and needs no alt (WCC: "no alternative description", Severe)
    n_tf = 0
    for i, (e, _) in enumerate(items):
        if role(e) == '/Figure' and str(i) not in cfg.get('alt', {}) and '/Alt' not in e and desc(e):
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
if cfg.get('tag_order'):
    # F21 [WCAG 1.3.2]: tags out of page order (InDesign lists a right-hand picture and its caption before the left-hand
    # ones). Inside each tag, its child tags are put in page order: top to bottom in a column, left to right on a line.
    # Only children that clearly sit in the wrong order move; the rest keep their order. The ParentTree needs no change
    # (no tag changes parent). Panorama doesn't check page order; mcid_order (below) is what clears its flag.
    sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
    import pdf_order
    OB, OT = pdf_order.boxes(pl)
    def name(c, pg):
        if isinstance(c, pikepdf.Dictionary) and '/S' in c:
            t = desc(c) or str(c.get('/Alt', '')).strip()
            return f'<{role(c)[1:]}>' + (f' "{t[:25]}"' if t else '')
        ks_ = pdf_order.mcids(c, pages, pg)
        return '"' + ''.join(OT.get(k, '') for k in ks_).strip()[:25] + '"'
    n_ord = []
    def reorder(e, pg=None):
        if '/Pg' in e: pg = pages.get(e.Pg.objgen, pg)
        ks = kids(e)
        for c in ks:
            if isinstance(c, pikepdf.Dictionary) and '/S' in c: reorder(c, pg)
        if len(ks) < 2: return
        fps = [pdf_order.footprint(c, pages, pg, OB) for c in ks]
        new = pdf_order.page_order(ks, fps)
        if new is None: return
        moved = [i for pos, i in enumerate(new) if i > pos]          # pulled ahead of where it was
        p = min((min(fps[i]) for i in moved if fps[i]), default=0)
        e.K = pikepdf.Array([ks[i] for i in new])
        n_ord.append(1)
        tag = f'<{role(e)[1:]}>' if '/S' in e else 'the top level'
        log.append(f'page {p + 1}: tags put in page order inside {tag}: ' + ', '.join(name(ks[i], pg) for i in moved[:4])
                   + ' moved earlier')
    reorder(pdf.Root.StructTreeRoot)
    if not n_ord: log.append('tag order: nothing to do')
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
if cfg.get('mcid_order', True):
    # F20 [WCC Panorama "Check reading order" (Severe)]: Panorama flags a page whose MCID numbers don't go up in tag
    # order (seven one-page test PDFs, Nov 17, 2026: renumbering alone took one from 0% to 100%). Runs last, after
    # every other change to the tags. The page looks the same and screen readers read the same order.
    sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
    import pdf_order
    done, skipped = pdf_order.renumber(pdf)
    for p_, n_ in sorted(done.items()):
        if n_: log.append(f'page {p_ + 1}: content renumbered to follow the tag order ({n_} tags)')
    for p_ in skipped: log.append(f'page {p_ + 1}: content numbers not changed (named or repeated MCIDs); check F20')
pdf.save(dst)
print('\n'.join(log))
