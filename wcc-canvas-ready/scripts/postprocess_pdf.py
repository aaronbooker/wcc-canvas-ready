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
# A link that wraps onto a second line is exported by LibreOffice as two <Link> tags with the same address. Merge
# back-to-back <Link> siblings that go to the same address into one, so a screen reader announces one link.
# This was written (Nov 17, 2026) to clear Panorama's "Check reading order" on pages with links. It does NOT: Nov 19
# one-page tests scored 0% with the halves joined or not. Any LibreOffice link is flagged; see the end of this file.
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
# Each page's /Annots in the same order as their <Link> tags (LibreOffice writes them in another order), so Tab moves
# through the links in reading order. Also written for "Check reading order" (Nov 17, 2026); it does not clear it either.
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
# WCC's Panorama flags every page with a LibreOffice link "Check reading order" (Severe, 0%): 16 one-page tests,
# Nov 19, 2026, nothing changed in the file cleared it. docx2pdf_ua.py prints such a PDF again through Chrome.
_lp = sum(1 for pg in pdf.pages if any(a.get('/Subtype') == '/Link' for a in pg.obj.get('/Annots', [])))
import os
if _lp and not os.environ.get('WCC_DOCX2PDF'):     # docx2pdf_ua.py handles it itself
    print(f'WARNING links on {_lp} page(s): Panorama will flag each "Check reading order" (Severe). Use docx2pdf_ua.py '
          'on the .docx instead (it prints a PDF with links through Chrome), or pdf_tag2html.py -> Chrome -> pdf_tagfix.py.')
