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
pdf.save(dst)
print('tables with summary:', len(tables))
