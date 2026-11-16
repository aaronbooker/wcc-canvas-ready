"""Alt text for every picture in a .docx, decided once per distinct image. D11 [WCAG 1.1.1 + Panorama, Severe at WCC].
  python3 docx_alt.py in.docx --list outdir/     # extract each distinct image + a JSON draft (count, nearby text)
  python3 docx_alt.py in.docx out.docx alt.json   # apply
A document may place the same image hundreds of times (icons, logos repeated per row): Panorama counts every
placement. alt.json maps the image file name (e.g. "image12.png") to alt text, or to "" / "decorative" to mark it
decorative. Look at each extracted image (open it) and read the nearby text before writing alt text: a logo
is "<Name> logo"; a chart needs its point in a sentence; icons that repeat the text next to them are decorative.
Images that are not in the JSON are left unchanged and listed. Headers and footers are covered too (a logo in
the header is a picture Panorama can flag); their "near" text says HEADER/FOOTER.
Text boxes and shapes (wps) count as "items" too: they get the alt from the "shape:<name>" key, or
"decorative" by default when they only hold text that is already in the document flow.
"""
import sys, re, json, zipfile, html, os, collections
src = sys.argv[1]
z = zipfile.ZipFile(src); files = {n: z.read(n) for n in z.namelist()}
PARTS = ['word/document.xml'] + sorted(n for n in files if re.fullmatch(r'word/(header|footer)\d*\.xml', n))
def relmap(part):
    rp = part.replace('word/', 'word/_rels/') + '.rels'
    rels = files.get(rp, b'').decode()
    m = dict((a.group(1), a.group(2)) for a in re.finditer(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    m.update((a.group(2), a.group(1)) for a in re.finditer(r'Target="([^"]+)"[^>]*Id="([^"]+)"', rels))
    return m
txt = lambda x: html.unescape(' '.join(re.findall(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>', x))).strip()
DEC = ('<a:extLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:ext uri="{C183D7F6-B498-43B3-948B-1728B52AA6E4}">'
       '<adec:decorative xmlns:adec="http://schemas.microsoft.com/office/drawing/2017/decorative" val="1"/></a:ext></a:extLst>')

DOCPR = re.compile(r'<wp:docPr\b[^>]*?(?:/>|>.*?</wp:docPr>)', re.S)
def keyed(doc, rid2t):
    """every <wp:docPr> with the image it labels: the first r:embed after it, before the next docPr or the end of
    its drawing. Works for pictures nested inside text boxes (a drawing inside a drawing)."""
    ms = list(DOCPR.finditer(doc))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(doc)
        seg = doc[m.end():end]
        cut = seg.find('</w:drawing>'); seg = seg if cut < 0 else seg[:cut]
        emb = re.search(r'r:embed="([^"]+)"', seg)
        name = re.search(r'name="([^"]*)"', m.group(0))
        key = os.path.basename(rid2t.get(emb.group(1), '')) if emb else 'shape:' + (name.group(1) if name else '?')
        yield m, key
if '--list' in sys.argv:
    out = sys.argv[sys.argv.index('--list') + 1]; os.makedirs(out, exist_ok=True)
    info = collections.OrderedDict()
    for part in PARTS:
      doc = files[part].decode(); where = '' if part.endswith('document.xml') else ('HEADER ' if 'header' in part else 'FOOTER ')
      for m, key in keyed(doc, relmap(part)):
        d = m.group(0)
        cur = re.search(r'descr="([^"]*)"', d)
        i = info.setdefault(key, {'count': 0, 'current_alt': cur.group(1) if cur else '', 'near': ''})
        i['count'] += 1
        if not i['near']:
            i['near'] = where + txt(doc[max(0, m.start() - 1500):m.start()])[-120:] + ' [IMAGE] ' + txt(doc[m.end():m.end() + 1500])[:120]
            if key.startswith('shape:'): i['near'] = where + 'TEXT INSIDE: ' + txt(doc[m.end():m.end() + 3000])[:200]
    for key in info:
        if not key.startswith('shape:'):
            p = 'word/media/' + key
            if p in files: open(os.path.join(out, key), 'wb').write(files[p])
    json.dump({k: {'alt': '', **v} for k, v in info.items()}, open(os.path.join(out, 'alt_draft.json'), 'w'), indent=1, ensure_ascii=False)
    print(f'{sum(v["count"] for v in info.values())} placements of {len(info)} distinct images/shapes -> {out}/alt_draft.json')
    sys.exit()

dst, alts = sys.argv[2], json.load(open(sys.argv[3]))
alts = {k: (v['alt'] if isinstance(v, dict) else v) for k, v in alts.items()}
done, missing = collections.Counter(), set()
for part in PARTS:
    doc = files[part].decode(); out, pos = [], 0
    for m, key in list(keyed(doc, relmap(part))):
        dp = m.group(0)
        a = alts.get(key)
        if a is None and key.startswith('shape:'): a = 'decorative'
        if a is None:
            missing.add(key); continue
        head = re.sub(r'\s(descr|title)="[^"]*"', '', re.match(r'<wp:docPr\b[^>]*?(?=/?>)', dp).group(0))
        new = head + '>' + DEC + '</wp:docPr>' if a.strip().lower() in ('', 'decorative') else head + f' descr="{html.escape(a.strip(), quote=True)}"/>'
        out.append(doc[pos:m.start()] + new); pos = m.end(); done[key] += 1
    out.append(doc[pos:]); files[part] = ''.join(out).encode()
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as o:
    for n in z.namelist(): o.writestr(n, files[n])
print(f'alt/decorative set on {sum(done.values())} placements of {len(done)} images/shapes; not in JSON: {sorted(missing)[:20]}')
