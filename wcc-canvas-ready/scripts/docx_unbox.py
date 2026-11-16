"""Turn one-cell layout tables (callout boxes) into shaded, bordered paragraphs. D14 [WCAG 1.3.1 + Panorama].
Usage: python3 docx_unbox.py in.docx out.docx
A 1-row, 1-column table is a box drawn around text, not data. Screen readers announce it as "table, 1 row,
1 column" and Panorama asks for a header row and caption. Each paragraph inside keeps its own formatting and
gets the cell's fill (w:shd) and a border (w:pBdr) so the box looks the same. Nested content other than
paragraphs (an inner table, an image) is kept as-is.
"""
import sys, re, zipfile
src, dst = sys.argv[1], sys.argv[2]
z = zipfile.ZipFile(src); files = {n: z.read(n) for n in z.namelist()}
doc = files['word/document.xml'].decode()

def top_tables(x):
    out, depth, start = [], 0, 0
    for m in re.finditer(r'<w:tbl>|</w:tbl>', x):
        if m.group(0) == '<w:tbl>':
            if depth == 0: start = m.start()
            depth += 1
        else:
            depth -= 1
            if depth == 0: out.append((start, m.end()))
    return out

def border_xml(tbl):
    # use the table/cell border color if there is one, else a mid-gray that meets 3:1 for UI (WCAG 1.4.11)
    c = re.search(r'<w:(?:top|left|start)\b[^>]*w:color="([0-9A-Fa-f]{6})"', tbl)
    col = c.group(1) if c else '767676'
    side = lambda s: f'<w:{s} w:val="single" w:sz="8" w:space="4" w:color="{col}"/>'
    return '<w:pBdr>' + ''.join(side(s) for s in ('top', 'left', 'bottom', 'right')) + '</w:pBdr>'

PPR_ORDER = ['pStyle', 'keepNext', 'keepLines', 'pageBreakBefore', 'framePr', 'widowControl', 'numPr',
             'suppressLineNumbers', 'pBdr', 'shd', 'tabs', 'suppressAutoHyphens', 'kinsoku', 'wordWrap',
             'overflowPunct', 'topLinePunct', 'autoSpaceDE', 'autoSpaceDN', 'bidi', 'adjustRightInd', 'snapToGrid',
             'spacing', 'ind', 'contextualSpacing', 'mirrorIndents', 'suppressOverlap', 'jc', 'textDirection',
             'textAlignment', 'textboxTightWrap', 'outlineLvl', 'divId', 'cnfStyle', 'rPr', 'sectPr', 'pPrChange']

def add_ppr(p, extra):
    """insert pBdr/shd into the paragraph's pPr in schema order"""
    m = re.search(r'<w:pPr>(.*?)</w:pPr>', p, re.S)
    inner = m.group(1) if m else ''
    inner = re.sub(r'<w:pBdr>.*?</w:pBdr>|<w:pBdr/>|<w:shd [^>]*/>', '', inner, flags=re.S)
    kids = re.findall(r'<w:(\w+)\b(?:[^>]*/>|[^>]*>.*?</w:\1>)', inner, re.S)
    parts = re.findall(r'(<w:(\w+)\b(?:[^>]*/>|[^>]*>.*?</w:\2>))', inner, re.S)
    allp = [(t, name) for t, name in parts] + [(e, re.match(r'<w:(\w+)', e).group(1)) for e in extra]
    allp.sort(key=lambda t: PPR_ORDER.index(t[1]) if t[1] in PPR_ORDER else 99)
    new = '<w:pPr>' + ''.join(t for t, _ in allp) + '</w:pPr>'
    if m: return p[:m.start()] + new + p[m.end():]
    i = re.match(r'<w:p\b[^>]*>', p).end()
    return p[:i] + new + p[i:]

out, pos, n = [], 0, 0
for a, b in top_tables(doc):
    tbl = doc[a:b]
    rows = re.findall(r'<w:tr\b.*?</w:tr>', tbl, re.S)
    cells = re.findall(r'<w:tc>.*?</w:tc>', tbl, re.S) if len(rows) == 1 else []
    if len(rows) != 1 or len(cells) != 1 or '<w:tbl>' in tbl[6:]:
        continue
    cell = cells[0]
    fill = re.search(r'<w:tcPr>.*?<w:shd [^>]*w:fill="([0-9A-Fa-f]{6})"', cell, re.S) or \
           re.search(r'<w:tblPr>.*?<w:shd [^>]*w:fill="([0-9A-Fa-f]{6})"', tbl, re.S)
    extra = [border_xml(tbl)]
    if fill: extra.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{fill.group(1)}"/>')
    body = re.sub(r'^<w:tc>\s*(?:<w:tcPr>.*?</w:tcPr>)?', '', cell, flags=re.S)[:-len('</w:tc>')]
    body = re.sub(r'<w:p\b(?:(?!<w:p\b).)*?</w:p>|<w:p\b[^>]*/>', lambda m: add_ppr(m.group(0), extra), body, flags=re.S)
    out.append(doc[pos:a] + body); pos = b; n += 1
out.append(doc[pos:])
files['word/document.xml'] = ''.join(out).encode()
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as o:
    for name in z.namelist(): o.writestr(name, files[name])
print(f'one-cell tables turned into bordered paragraphs: {n}')
