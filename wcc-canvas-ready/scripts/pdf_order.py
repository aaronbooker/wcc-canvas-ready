"""Reading order of a tagged PDF. Shared by preflight_pdf.py (F20, F21) and pdf_tagfix.py ("mcid_order", "tag_order").

What WCC's Panorama checks [WCC Panorama "Check reading order" (Severe)], from seven one-page test PDFs (Nov 17, 2026):
on each page, the marked-content numbers (MCIDs) must go up in tag order. Tags whose MCIDs run 0, 1, 3, 2, 4 are
flagged; the same tags renumbered 0, 1, 2, 3, 4 scored 100%. Panorama does NOT compare the tags with where the content
sits on the page or with the order it is drawn: tags in drawing order but right picture before left scored 100%.
  - F20 / renumber(): MCID numbers in tag order. This is what Panorama scores; renumbering never changes how the page
    looks or what a screen reader reads.
  - F21 / page_order(): does the tag order follow the page? Panorama doesn't check it, but a screen reader reads the
    tags in order (WCAG 1.3.2). A tag is out of order when it comes after something clearly BELOW it in the same
    column (they share some width), or clearly to its RIGHT on the same line (they share most of a line's height).
    Row-first and column-first orders both pass, and so do two-column pages read column by column.
"""
import pikepdf

SLACK = 2.0          # points: boxes that touch or overlap this much still count as above / left of each other


def boxes(pl):
    """pdfplumber PDF -> ({(page index, MCID): (x0, top, x1, bottom)}, {(page index, MCID): text}).
    The box covers everything drawn inside that marked content: text, pictures and shapes."""
    B, T = {}, {}
    for pi, pg in enumerate(pl.pages):
        for o in pg.chars + pg.images + pg.rects + pg.curves + pg.lines:
            m = o.get('mcid')
            if m is None: continue
            if o['object_type'] == 'char':
                T[(pi, m)] = T.get((pi, m), '') + o['text']
                if not o['text'].strip(): continue
            k, b = (pi, m), (o['x0'], o['top'], o['x1'], o['bottom'])
            a = B.get(k)
            B[k] = b if a is None else (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
    return B, T


def content(pl):
    """{(page index, MCID)} that hold text or a picture: what Panorama's order check looks at. MCIDs that only hold
    shapes are left out: a test PDF with a shape-only MCID out of tag order scored 100% (Nov 17, 2026). Chrome draws
    table-cell backgrounds first, so their numbers come before the cell text's, and those prints score 100% too."""
    C = set()
    for pi, pg in enumerate(pl.pages):
        for o in pg.chars + pg.images:
            if o.get('mcid') is not None and (o['object_type'] != 'char' or o['text'].strip()): C.add((pi, o['mcid']))
    return C


def ahead(b, a):
    """True when box b clearly comes before box a on the page: above it in the same column, or left of it on the
    same line. (So a tag for a that comes before b's tag is out of page order.)"""
    w = min(a[2] - a[0], b[2] - b[0]); h = min(a[3] - a[1], b[3] - b[1])
    hov = min(a[2], b[2]) - max(a[0], b[0])          # shared width
    vov = min(a[3], b[3]) - max(a[1], b[1])          # shared height
    if b[3] <= a[1] + SLACK and hov > max(0.25 * w, 1): return True
    if b[2] <= a[0] + SLACK and vov > max(0.5 * h, 1): return True
    return False


def union(bs):
    bs = list(bs)
    return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))


def _kids(e):
    k = e.get('/K')
    return list(k) if isinstance(k, pikepdf.Array) else ([] if k is None else [k])


def mcids(e, pages, pg=None):
    """Every (page index, MCID) under a structure element (or one kid: an MCID number or an MCR), in tag order."""
    if isinstance(e, int): return [(pg, int(e))] if pg is not None else []
    if not isinstance(e, pikepdf.Dictionary): return []
    if e.get('/Type') == '/MCR':
        if '/Stm' in e: return []     # content inside a Form XObject: its MCIDs are numbered apart from the page's
        p = pages.get(e.Pg.objgen, pg) if '/Pg' in e else pg
        return [(p, int(e.MCID))] if p is not None else []
    if '/S' not in e and e.get('/Type') != '/StructTreeRoot': return []      # OBJR (links, form fields): no MCID
    if '/Pg' in e: pg = pages.get(e.Pg.objgen, pg)
    out = []
    for c in _kids(e): out += mcids(c, pages, pg)
    return out


def inversions(pdf, B, T):
    """Pages whose tag order runs against the page: {page index: [(earlier tag text, later tag text), ...]}."""
    pages = {p.objgen: i for i, p in enumerate(pdf.pages)}
    seq, seen = [], set()
    for k in mcids(pdf.Root.StructTreeRoot, pages):
        if k in B and k not in seen: seq.append(k); seen.add(k)
    per = {}
    for k in seq: per.setdefault(k[0], []).append(k)
    out = {}
    for pi, ks in per.items():
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                if ahead(B[ks[j]], B[ks[i]]):
                    name = lambda k: (T.get(k, '').strip()[:30] or f'MCID {k[1]} (picture or shape)')
                    out.setdefault(pi, []).append((name(ks[i]), name(ks[j])))
    return out


def footprint(kid, pages, pg, B):
    """{page index: box} of one kid's content."""
    f = {}
    for k in mcids(kid, pages, pg):
        if k in B: f.setdefault(k[0], []).append(B[k])
    return {p: union(bs) for p, bs in f.items()}


def must_precede(fi, fj):
    """Kid i must come before kid j (footprints from footprint())."""
    if not fi or not fj: return False
    shared = set(fi) & set(fj)
    if shared:
        return any(ahead(fi[p], fj[p]) for p in shared) and not any(ahead(fj[p], fi[p]) for p in shared)
    return max(fi) < min(fj)


def page_order(ks, fps):
    """Kids reordered into page order, moving only what must move: of the kids free to go next, the earliest in the
    original order goes first. Returns the new list of indexes, or None when the order is already fine or the
    constraints contradict each other."""
    import heapq
    n = len(ks)
    succ = [[] for _ in range(n)]; npred = [0] * n; bad = False
    for i in range(n):
        for j in range(n):
            if i != j and must_precede(fps[i], fps[j]):
                succ[i].append(j); npred[j] += 1
                if j < i: bad = True
    if not bad: return None
    h = [i for i in range(n) if npred[i] == 0]; heapq.heapify(h); out = []
    while h:
        i = heapq.heappop(h); out.append(i)
        for j in succ[i]:
            npred[j] -= 1
            if npred[j] == 0: heapq.heappush(h, j)
    return out if len(out) == n else None


def tag_order(pdf):
    """{page index: [MCIDs in tag order, each once]}."""
    pages = {p.objgen: i for i, p in enumerate(pdf.pages)}
    out = {}
    for pi, m in mcids(pdf.Root.StructTreeRoot, pages):
        seq = out.setdefault(pi, [])
        if m not in seq: seq.append(m)
    return out


def _lis(a):
    import bisect
    t = []
    for x in a:
        i = bisect.bisect_left(t, x)
        if i == len(t): t.append(x)
        else: t[i] = x
    return len(t)


def number_order(pdf, only=None):
    """Pages whose MCID numbers don't go up in tag order: {page index: (tags out of number order, first few MCIDs)}.
    only: the (page index, MCID) pairs to count, usually content(pl)."""
    out = {}
    for pi, seq in tag_order(pdf).items():
        if only is not None: seq = [m for m in seq if (pi, m) in only]
        k = len(seq) - _lis(seq)
        if k: out[pi] = (k, seq[:12])
    return out


def _nums(n):
    if n is None: return
    if '/Nums' in n:
        a = n.Nums
        for i in range(0, len(a), 2): yield a, i
    for kd in n.get('/Kids', []): yield from _nums(kd)


def renumber(pdf):
    """Renumber MCIDs on each page so they go up in tag order: the page's content stream, the structure tree and the
    ParentTree all change together. Returns {page index: number of tags renumbered} and a list of skipped pages."""
    pages = {p.objgen: i for i, p in enumerate(pdf.pages)}
    order = tag_order(pdf)
    st = pdf.Root.StructTreeRoot
    remap, done, skipped = {}, {}, []
    for pi, seq in order.items():
        if seq == sorted(seq): continue
        page = pdf.pages[pi]
        props = page.obj.get('/Resources', {}).get('/Properties', {})
        ops = pikepdf.parse_content_stream(page)
        drawn, named = [], False
        for operands, op in ops:
            if str(op) == 'BDC' and len(operands) > 1:
                d = operands[1]
                if isinstance(d, pikepdf.Name):
                    if '/MCID' in props.get(d, {}): named = True
                elif isinstance(d, pikepdf.Dictionary) and '/MCID' in d: drawn.append(int(d.MCID))
        if named or len(set(drawn)) != len(drawn):      # MCIDs in named property lists, or repeated: leave the page
            skipped.append(pi); continue
        rest = sorted(set(drawn) - set(seq))            # drawn but not tagged: numbered after the tagged ones
        new = {m: i for i, m in enumerate(seq + rest)}
        for operands, op in ops:
            if str(op) == 'BDC' and len(operands) > 1 and isinstance(operands[1], pikepdf.Dictionary) and '/MCID' in operands[1]:
                operands[1].MCID = new[int(operands[1].MCID)]
        page.Contents = pdf.make_stream(pikepdf.unparse_content_stream(ops))
        sp = page.obj.get('/StructParents')
        for a, i in _nums(st.get('/ParentTree')):
            if sp is not None and int(a[i]) == int(sp):
                old = a[i + 1]
                arr = [None] * len(new)
                for m, n in new.items():
                    if m < len(old): arr[n] = old[m]
                a[i + 1] = pikepdf.Array(arr)
        remap[pi] = new
        done[pi] = sum(1 for m, n in new.items() if m != n and m in seq)
    if not remap: return done, skipped
    def fix(e, pg=None):
        if '/Pg' in e: pg = pages.get(e.Pg.objgen, pg)
        k = e.get('/K')
        ks = list(k) if isinstance(k, pikepdf.Array) else ([] if k is None else [k])
        changed, out = False, []
        for c in ks:
            if isinstance(c, int) and pg in remap and int(c) in remap[pg]:
                out.append(remap[pg][int(c)]); changed = True; continue
            if isinstance(c, pikepdf.Dictionary):
                if c.get('/Type') == '/MCR' and '/Stm' not in c:
                    p = pages.get(c.Pg.objgen, pg) if '/Pg' in c else pg
                    if p in remap and int(c.MCID) in remap[p]: c.MCID = remap[p][int(c.MCID)]
                elif '/S' in c: fix(c, pg)
            out.append(c)
        if changed: e.K = pikepdf.Array(out) if isinstance(k, pikepdf.Array) else out[0]
    fix(st)
    return done, skipped
