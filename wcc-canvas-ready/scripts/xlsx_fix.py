"""Fix an .xlsx for WCC Panorama by editing the package XML (no openpyxl round-trip, so nothing is dropped).
Usage: python3 xlsx_fix.py in.xlsx out.xlsx --title "Workbook title" [--author "Name"] [--a1 "Sheet name::text" ...]
       [--link "shown text::new text" ...]
X1 [WCAG+Panorama 2.4.2] "The title is missing from the document's properties" (Major): sets dc:title.
X2 [WCC Panorama] "The font size is smaller than 11 points" (Minor, one per cell!): every <sz> in styles.xml
   raised to >= 12; column widths and custom row heights scaled by the largest raise so text still fits.
X3 [WCAG+Panorama 3.1.1] dc:language en-US.
X4 [Panorama] "Sheet does not have text in cell A1" (Minor at WCC, Nov 2026; only the first sheet was flagged):
   reported per sheet; YOU write a one-line sheet description and pass it with --a1 (an empty A1 gets it as text).
X5 [WCAG+Panorama 1.3.1] "Table does not have a header": Excel tables with headerRowCount="0" reported.
X6 [Metadata] tool names (openpyxl, python-docx...) removed from creator/lastModifiedBy.
X7 [WCC Panorama] "Insufficient contrast between foreground text and background" (Major in Excel, Nov 16 2026) on
   rich text (words formatted differently inside one cell) on a colored fill, even black on light peach: such cells
   become plain text in the cell's own font. Explicit run colors, no run colors and rewritten fills did not clear
   it; plain text did (4 of 4 legend cells).
X8 [WCAG 1.4.3 + WCC Panorama] same flag for colored text on a colored fill: Panorama flagged dark teal link text
   on light peach at 7.97:1 in one cell and passed it in the cells around it; black passed. So text on a solid fill
   that isn't already black or white becomes whichever of the two contrasts more, and text with no fill under
   4.5:1 is darkened just enough (+0.3). Only the cell formats involved get a new font; nothing else changes.
X9 [WCAG 2.4.4 + Panorama] "The hyperlink text is not descriptive" (Major in Excel, Nov 16 2026: 3 cells showing
   their own URL held a workbook at 30%): linked cells whose text is just an address are listed; YOU write
   "Site name (domain)" and pass --link "https://site.org/page::Site name (site.org)". The cell's text changes;
   its link, format and position stay.
"""
import sys, os, re, zipfile, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xlsx_colors as XC
args = sys.argv[1:]
src, dst = args[0], args[1]
title = args[args.index('--title') + 1] if '--title' in args else None
author = args[args.index('--author') + 1] if '--author' in args else None
A1TEXT = dict(args[i + 1].split('::', 1) for i, a in enumerate(args) if a == '--a1')
LINKTEXT = dict(args[i + 1].split('::', 1) for i, a in enumerate(args) if a == '--link')
zin = zipfile.ZipFile(src)
files = {n: zin.read(n) for n in zin.namelist()}
log = []
TOOLS = re.compile(r'^(openpyxl|python-docx|python-pptx|xlsxwriter|Apache POI|Un-named|Steve Canny)$', re.I)

# X2 fonts
st = files['xl/styles.xml'].decode()
sizes = [float(v) for v in re.findall(r'<sz val="([\d.]+)"', st)]
low = [s for s in sizes if s < 12]
ratio = max([12 / s for s in low], default=1.0)
st = re.sub(r'<sz val="([\d.]+)"\s*/>', lambda m: '<sz val="%s"/>' % (m.group(1) if float(m.group(1)) >= 12 else '12'), st)
files['xl/styles.xml'] = st.encode()
if low: log.append(f'raised {len(low)} font definitions to 12 pt (smallest was {min(low):g}); widths x{ratio:.2f}')

# X7 X8 colors
book = XC.Book(files)
flat_si, flat_inline, recolor = set(), {}, {}
for sname, part, ref, s, text, rich, si in book.cells():
    fo, fi = book.xf(s)
    bg = book.fill_color(fi)
    if rich and bg:
        if si is not None: flat_si.add(si)
        else: flat_inline.setdefault(part, set()).add(ref)
        log.append(f'sheet "{sname}" {ref}: mixed formatting inside the cell on a colored fill made plain (Panorama flags it as low contrast)')
    fg = book.font_color(fo)
    if bg and bg not in ('000000', 'FFFFFF'):
        best = '000000' if XC.ratio('000000', bg) >= XC.ratio('FFFFFF', bg) else 'FFFFFF'
        new = best if XC.ratio(fg, bg) < 0.85 * XC.ratio(best, bg) else None   # near-black stays as is
    else:
        new = XC.fix_color(fg, bg or 'FFFFFF') if XC.ratio(fg, bg or 'FFFFFF') < XC.NEED else None
    if new: recolor.setdefault(s, (fo, fg, new, bg or 'FFFFFF', []))[4].append(f'{sname}!{ref}')

def plain(xml):   # rich-text runs -> one plain run, same characters
    txt = ''.join(re.findall(r'<t(?:\s[^>]*)?>(.*?)</t>', xml, re.S))
    return '<t xml:space="preserve">%s</t>' % txt
if flat_si:
    k = iter(range(len(book.sis)))
    ss_x = re.sub(r'<si>(.*?)</si>', lambda m: '<si>%s</si>' % plain(m.group(1)) if next(k) in flat_si else m.group(0),
                  files['xl/sharedStrings.xml'].decode(), flags=re.S)
    files['xl/sharedStrings.xml'] = ss_x.encode()
for part, refs in flat_inline.items():
    x = files[part].decode()
    for ref in refs:
        x = re.sub(r'(<c r="%s"[^>]*>)(.*?)(</c>)' % ref, lambda m: m.group(1) + re.sub(r'<is>.*?</is>', lambda i: '<is>%s</is>' % plain(i.group(0)), m.group(2), flags=re.S) + m.group(3), x, count=1, flags=re.S)
    files[part] = x.encode()

if recolor:
    st = files['xl/styles.xml'].decode()
    fonts_sect = re.search(r'<fonts\b[^>]*>.*?</fonts>', st, re.S).group(0)
    xfs_sect = re.search(r'<cellXfs\b[^>]*>.*?</cellXfs>', st, re.S).group(0)
    xf_list = re.findall(r'<xf\b[^>]*?(?:/>|>.*?</xf>)', xfs_sect, re.S)
    added, made = [], {}
    for s, (fo, fg, new, bg, refs) in sorted(recolor.items()):
        if (fo, new) not in made:
            f = book.fonts[fo]
            f = re.sub(r'<color\b[^>]*/>', f'<color rgb="FF{new}"/>', f) if '<color' in f else \
                (f.replace('</font>', f'<color rgb="FF{new}"/></font>') if f.endswith('</font>') else f'<font><color rgb="FF{new}"/></font>')
            made[(fo, new)] = len(book.fonts) + len(added); added.append(f)
        x = xf_list[s]
        x = re.sub(r'fontId="\d+"', 'fontId="%d"' % made[(fo, new)], x) if 'fontId=' in x else x.replace('<xf ', '<xf fontId="%d" ' % made[(fo, new)], 1)
        x = x if 'applyFont=' in x else x.replace('<xf ', '<xf applyFont="1" ', 1)
        xf_list[s] = re.sub(r'applyFont="0"', 'applyFont="1"', x)
        shown = ', '.join(refs[:6]) + (f' and {len(refs) - 6} more' if len(refs) > 6 else '')
        log.append(f'text #{fg} on #{bg} ({XC.ratio(fg, bg):.2f}:1) -> #{new} ({XC.ratio(new, bg):.2f}:1) in {len(refs)} cells: {shown}')
    fonts_new = re.sub(r'(<fonts\b[^>]*?count=")\d+', lambda m: m.group(1) + str(len(book.fonts) + len(added)), fonts_sect).replace('</fonts>', ''.join(added) + '</fonts>')
    xfs_new = re.match(r'<cellXfs\b[^>]*>', xfs_sect).group(0) + ''.join(xf_list) + '</cellXfs>'
    files['xl/styles.xml'] = st.replace(fonts_sect, fonts_new).replace(xfs_sect, xfs_new).encode()

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

# X9 link text that is just the address
for sname, part, ref, text, addr in XC.links(XC.Book(files)):
    if not XC.bare_url(text): continue
    new = LINKTEXT.get(text.strip())
    if not new:
        log.append(f'sheet "{sname}" {ref}: link text is the address "{text.strip()}" - write "Site name (domain)" and rerun with --link "{text.strip()}::new text"')
        continue
    x = files[part].decode()
    m = re.search(r'<c r="%s"([^>]*?)(?:/>|>.*?</c>)' % ref, x, re.S)
    attrs = re.sub(r'\s+t="[^"]*"', '', m.group(1))
    x = x[:m.start()] + f'<c r="{ref}"{attrs} t="inlineStr"><is><t xml:space="preserve">{html.escape(new, quote=False)}</t></is></c>' + x[m.end():]
    files[part] = x.encode()
    log.append(f'sheet "{sname}" {ref}: link text "{text.strip()}" -> "{new}"')

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
