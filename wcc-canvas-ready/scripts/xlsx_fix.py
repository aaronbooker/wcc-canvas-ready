"""Fix an .xlsx for WCC Panorama by editing the package XML (no openpyxl round-trip, so nothing is dropped).
Usage: python3 xlsx_fix.py in.xlsx out.xlsx --title "Workbook title" [--author "Name"] [--a1 "Sheet name::text" ...]
X1 [WCAG+Panorama 2.4.2] "The title is missing from the document's properties" (Major): sets dc:title.
X2 [WCC Panorama] "The font size is smaller than 11 points" (Minor, one per cell!): every <sz> in styles.xml
   raised to >= 12; column widths and custom row heights scaled by the largest raise so text still fits.
X3 [WCAG+Panorama 3.1.1] dc:language en-US.
X4 [Panorama] "Sheet does not have text in cell A1" (Minor at WCC, Nov 2026; only the first sheet was flagged):
   reported per sheet; YOU write a one-line sheet description and pass it with --a1 (an empty A1 gets it as text).
X5 [WCAG+Panorama 1.3.1] "Table does not have a header": Excel tables with headerRowCount="0" reported.
X6 [Metadata] tool names (openpyxl, python-docx...) removed from creator/lastModifiedBy.
"""
import sys, re, zipfile, html
args = sys.argv[1:]
src, dst = args[0], args[1]
title = args[args.index('--title') + 1] if '--title' in args else None
author = args[args.index('--author') + 1] if '--author' in args else None
A1TEXT = dict(args[i + 1].split('::', 1) for i, a in enumerate(args) if a == '--a1')
zin = zipfile.ZipFile(src)
files = {n: zin.read(n) for n in zin.namelist()}
log = []
TOOLS = re.compile(r'^(openpyxl|python-docx|python-pptx|xlsxwriter|Apache POI|Un-named|Steve Canny)$', re.I)

# X2 fonts
st = files['xl/styles.xml'].decode()
sizes = [float(v) for v in re.findall(r'<sz val="([\d.]+)"', st)]
low = [s for s in sizes if s < 12]
ratio = max([12 / s for s in low], default=1.0)
st = re.sub(r'<sz val="([\d.]+)"/>', lambda m: '<sz val="%s"/>' % (m.group(1) if float(m.group(1)) >= 12 else '12'), st)
files['xl/styles.xml'] = st.encode()
if low: log.append(f'raised {len(low)} font definitions to 12 pt (smallest was {min(low):g}); widths x{ratio:.2f}')

wb = files['xl/workbook.xml'].decode()
rels = files['xl/_rels/workbook.xml.rels'].decode()
sheets = re.findall(r'<sheet [^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wb)
ss = files.get('xl/sharedStrings.xml', b'').decode()
strings = [re.sub(r'<[^>]+>', '', si) for si in re.findall(r'<si>(.*?)</si>', ss, re.S)]
for name, rid in sheets:
    tgt = re.search(r'Id="%s"[^>]*Target="([^"]+)"' % rid, rels) or re.search(r'Target="([^"]+)"[^>]*Id="%s"' % rid, rels)
    path = 'xl/' + tgt.group(1).lstrip('/').replace('xl/', '')
    x = files[path].decode()
    if ratio > 1.0:
        x = re.sub(r'(<col\b[^>]*\bwidth=")([\d.]+)', lambda m: m.group(1) + '%.2f' % (float(m.group(2)) * ratio), x)
        x = re.sub(r'(<row\b[^>]*\bht=")([\d.]+)(")', lambda m: m.group(1) + '%.2f' % (float(m.group(2)) * ratio) + m.group(3), x)
        x = re.sub(r'(<sheetFormatPr\b[^>]*\bdefaultRowHeight=")([\d.]+)', lambda m: m.group(1) + '%.2f' % max(15.75, float(m.group(2))), x)
        files[path] = x.encode()
    a1 = re.search(r'<c r="A1"[^>]*?(?:/>|>(.*?)</c>)', x, re.S)
    has = False
    if a1 and a1.group(1):
        v = re.search(r'<v>(.*?)</v>', a1.group(1)); t = re.search(r'<t[^>]*>(.*?)</t>', a1.group(1), re.S)
        if 't="s"' in a1.group(0) and v: has = bool(strings[int(v.group(1))].strip())
        else: has = bool((v and v.group(1).strip()) or (t and t.group(1).strip()))
    if not has and name in A1TEXT:
        # write the instructor's sheet description into A1 as an inline string (keeps every other cell as is)
        cell = f'<c r="A1" t="inlineStr"><is><t xml:space="preserve">{html.escape(A1TEXT[name], quote=False)}</t></is></c>'
        if a1: x = x.replace(a1.group(0), cell.replace('<c r="A1"', '<c r="A1"' + (re.search(r' s="\d+"', a1.group(0)).group(0) if re.search(r' s="\d+"', a1.group(0)) else ''), 1), 1)
        elif re.search(r'<row r="1"[^>]*/>', x): x = re.sub(r'<row r="1"([^>]*)/>', r'<row r="1"\1>' + cell + '</row>', x, count=1)
        elif re.search(r'<row r="1"[^>]*>', x): x = re.sub(r'(<row r="1"[^>]*>)', r'\1' + cell, x, count=1)
        elif '<sheetData/>' in x: x = x.replace('<sheetData/>', f'<sheetData><row r="1">{cell}</row></sheetData>', 1)
        else: x = x.replace('<sheetData>', f'<sheetData><row r="1">{cell}</row>', 1)
        files[path] = x.encode(); has = True
        log.append(f'sheet "{name}": A1 set to "{A1TEXT[name]}"')
    if not has: log.append(f'sheet "{name}": cell A1 is empty - put a short description of the sheet there (instructor wording), then rerun with --a1 "{name}::text"')
for n in list(files):
    if n.startswith('xl/tables/') and n.endswith('.xml'):
        t = files[n].decode()
        if 'headerRowCount="0"' in t:
            log.append(f'{n}: table has no header row - turn on Header Row')

# X1 X3 X6 core properties
core = files.get('docProps/core.xml', b'').decode()
if not core:
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"></cp:coreProperties>')
    ct = files['[Content_Types].xml'].decode().replace('</Types>', '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>')
    files['[Content_Types].xml'] = ct.encode()
    r = files['_rels/.rels'].decode().replace('</Relationships>', '<Relationship Id="rIdCore1" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>')
    files['_rels/.rels'] = r.encode()
# an empty core-properties part can be one self-closing tag (<cp:coreProperties .../>): open it so fields can be added
core = re.sub(r'<cp:coreProperties\b([^>]*?)\s*/>', r'<cp:coreProperties\1></cp:coreProperties>', core)
# make sure dc/dcterms/xsi prefixes are declared on the root (openpyxl declares them per element)
root = re.search(r'<cp:coreProperties\b[^>]*>', core).group(0)
add = ''.join(f' xmlns:{p}="{u}"' for p, u in (('dc', 'http://purl.org/dc/elements/1.1/'), ('dcterms', 'http://purl.org/dc/terms/'),
              ('xsi', 'http://www.w3.org/2001/XMLSchema-instance')) if f'xmlns:{p}=' not in root)
if add: core = core.replace(root, root[:-1] + add + '>', 1)
def setp(xml, tag, val):
    val = html.escape(val, quote=False)
    if re.search(r'<%s\b[^>]*/>' % tag, xml): return re.sub(r'<%s\b[^>]*/>' % tag, f'<{tag}>{val}</{tag}>', xml)
    if re.search(r'<%s\b' % tag, xml): return re.sub(r'<%s\b([^>]*)>.*?</%s>' % (tag, tag), lambda m: f'<{tag}{m.group(1)}>{val}</{tag}>', xml, flags=re.S)
    return xml.replace('</cp:coreProperties>', f'<{tag}>{val}</{tag}></cp:coreProperties>')
cur = re.search(r'<dc:title>(.*?)</dc:title>', core, re.S)
if title or not (cur and cur.group(1).strip()):
    core = setp(core, 'dc:title', title or 'Workbook'); log.append(f'title: "{title}"')
core = setp(core, 'dc:language', 'en-US')
for tag in ('dc:creator', 'cp:lastModifiedBy'):
    m = re.search(r'<%s\b[^>]*>(.*?)</%s>' % (tag, tag), core)
    if m and TOOLS.match(m.group(1).strip()):
        core = setp(core, tag, author or ''); log.append(f'{tag}: "{m.group(1)}" -> "{author or ""}"')
files['docProps/core.xml'] = core.encode()
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as z:
    for n in dict.fromkeys(zin.namelist() + list(files)):   # each part once
        z.writestr(n, files[n])
print('\n'.join(log))
