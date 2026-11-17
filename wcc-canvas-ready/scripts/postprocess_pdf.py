"""Add Panorama-checked PDF accessibility attributes that LibreOffice doesn't export.
Usage: python3 postprocess_pdf.py in.pdf out.pdf tables.json
- /Summary attribute on every /Table structure element (Panorama PDF: "Table does not have a summary")
- /Lang, /MarkInfo, /DisplayDocTitle kept/forced
"""
import sys, json, pikepdf
src, dst, tj = sys.argv[1:4]
meta = json.load(open(tj))
pdf = pikepdf.open(src)
tables = []
def walk(el):
    if isinstance(el, pikepdf.Dictionary):
        if el.get('/S') == '/Table':
            tables.append(el)
        k = el.get('/K')
        if k is None: return
        for it in (list(k) if isinstance(k, pikepdf.Array) else [k]):
            if isinstance(it, pikepdf.Dictionary): walk(it)
walk(pdf.Root.StructTreeRoot)
for i, t in enumerate(tables):
    cap, desc = meta[i] if i < len(meta) else ('Table', '')
    summ = desc or cap
    a = pikepdf.Dictionary(O=pikepdf.Name('/Table'), Summary=pikepdf.String(summ))
    old = t.get('/A')
    if old is None:
        t.A = a
    elif isinstance(old, pikepdf.Array):
        old.append(a)
    else:
        t.A = pikepdf.Array([old, a])
pdf.Root.Lang = pikepdf.String('en-US')
pdf.Root.MarkInfo = pikepdf.Dictionary(Marked=True)
vp = pdf.Root.get('/ViewerPreferences') or pikepdf.Dictionary()
vp.DisplayDocTitle = True; pdf.Root.ViewerPreferences = vp
# A link that wraps onto a second line is exported by LibreOffice as two <Link> tags with the same address. WCC's Panorama
# flagged each split as "Check reading order" (Severe, 0%): a 6-page chart with 30 links, 7 flags; the same file without
# links scored 100% (Nov 17, 2026). Merge back-to-back <Link> siblings that go to the same address into one.
def _uri(link):
    k = link.get('/K')
    for it in (list(k) if isinstance(k, pikepdf.Array) else [k]):
        if isinstance(it, pikepdf.Dictionary) and it.get('/Type') == '/OBJR':
            a = it.get('/Obj', {}).get('/A')
            if isinstance(a, pikepdf.Dictionary): return str(a.get('/URI', a.get('/D', '')))
    return None
def _kids(e):
    k = e.get('/K'); return list(k) if isinstance(k, pikepdf.Array) else ([] if k is None else [k])
merged = {}
def merge(el):
    if not isinstance(el, pikepdf.Dictionary): return
    ks = _kids(el); out = []
    for it in ks:
        prev = out[-1] if out else None
        if (isinstance(it, pikepdf.Dictionary) and it.get('/S') == '/Link' and isinstance(prev, pikepdf.Dictionary)
                and prev.get('/S') == '/Link' and _uri(it) and _uri(it) == _uri(prev)):
            prev.K = pikepdf.Array(_kids(prev) + _kids(it)); merged[it.objgen] = prev; continue
        out.append(it)
        if isinstance(it, pikepdf.Dictionary) and '/S' in it: merge(it)
    if len(out) != len(ks): el.K = pikepdf.Array(out) if len(out) != 1 else out[0]
merge(pdf.Root.StructTreeRoot)
if merged:
    def fix_pt(node):
        nums = node.get('/Nums')
        if nums is not None:
            for i in range(1, len(nums), 2):
                v = nums[i]
                if isinstance(v, pikepdf.Dictionary) and v.objgen in merged: nums[i] = merged[v.objgen]
                elif isinstance(v, pikepdf.Array):
                    for j in range(len(v)):
                        if isinstance(v[j], pikepdf.Dictionary) and v[j].objgen in merged: v[j] = merged[v[j].objgen]
        for kid in node.get('/Kids', []): fix_pt(kid)
    pt = pdf.Root.StructTreeRoot.get('/ParentTree')
    if pt is not None: fix_pt(pt)
    print(f'merged {len(merged)} links split across lines')
# Each page's /Annots in the same order as their <Link> tags. LibreOffice writes them in another order (a link near the
# bottom of the page listed first), and WCC's Panorama flagged "Check reading order" once on every page with links
# (7 of 7 pages; the same file without links scored 100%), Nov 17, 2026.
_order = []
def _objrs(el):
    if not isinstance(el, pikepdf.Dictionary): return
    for it in _kids(el):
        if isinstance(it, pikepdf.Dictionary) and it.get('/Type') == '/OBJR' and '/Obj' in it: _order.append(it.Obj.objgen)
        elif isinstance(it, pikepdf.Dictionary) and '/S' in it: _objrs(it)
_objrs(pdf.Root.StructTreeRoot)
_rank = {og: i for i, og in enumerate(_order)}
_moved = 0
for pg in pdf.pages:
    an = pg.obj.get('/Annots')
    if not isinstance(an, pikepdf.Array) or len(an) < 2: continue
    items = list(an)
    new = sorted(items, key=lambda a: _rank.get(a.objgen, len(_rank) + items.index(a)))
    if [x.objgen for x in new] != [x.objgen for x in items]:
        pg.obj.Annots = pikepdf.Array(new); _moved += 1
if _moved: print(f'link annotations put in tag order on {_moved} page(s)')
pdf.save(dst)
print('tables with summary:', len(tables))
