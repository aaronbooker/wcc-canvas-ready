"""Apply the wcc-canvas-ready post-processing rules to a .docx.
Usage: python3 postprocess_docx.py in.docx out.docx [tables.json] [--title TITLE] [--last-modified-by NAME] [--creator NAME]
- w:lang en-US in styles rPrDefault, settings themeFontLang, core dc:language (D3, D4)
- every w:sz/w:szCs floored to 24 in document/styles/numbering/headers/footers/notes (D21)
- rPrDefault size 24 (D21); justified -> left (D20)
- w:tblCaption / w:tblDescription per table from tables.json (D15, D16)
- dc:title kept, tool-generated author names removed (D24)
"""
import re, sys, json, zipfile, shutil, os, tempfile, collections

src, dst = sys.argv[1], sys.argv[2]
meta = json.load(open(sys.argv[3])) if len(sys.argv) > 3 and sys.argv[3].endswith('.json') else []
arg = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else ''
lastmod, creator = arg('--last-modified-by'), arg('--creator')

z = zipfile.ZipFile(src)
files = {n: z.read(n) for n in z.namelist() if not n.startswith('[trash]/')}   # Word leftovers fail validation
X = lambda n: files[n].decode('utf-8')

def put(n, s): files[n] = s.encode('utf-8')

def floor(x):
    return re.sub(r'<w:(sz|szCs) w:val="(\d+)"\s*/>', lambda m: f'<w:{m.group(1)} w:val="{max(int(m.group(2)), 24)}"/>', x)

def _lum(h):
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
def _ratio(h): return 1.05 / (_lum(h) + 0.05)          # against white
def _darken(h):
    for k in range(1, 101):
        c = ''.join('%02X' % round(int(h[i:i + 2], 16) * (1 - k / 100)) for i in (0, 2, 4))
        if _ratio(c) >= 5.0: return c   # margin: checkers round and convert differently
    return '000000'
COLOR_LOG = []
def fix_colors(x):
    """D9: mid-tone text colors that fail 4.5:1 on white (2:1 to 4.5:1, e.g. pandoc/Word accent blue 4F81BD,
    gray 808080, red FF0000) are darkened just enough to pass. Theme attributes are dropped because Word
    uses w:themeColor over w:val. Very light colors (likely white text on a dark fill) are left alone."""
    def rep(m):
        tag = m.group(0); v = re.search(r'w:val="([0-9A-Fa-f]{6})"', tag)
        if not v: return tag
        h = v.group(1).upper(); r = _ratio(h)
        if 2.0 <= r < 4.5:
            n = _darken(h); COLOR_LOG.append(f'{h} ({r:.2f}:1) -> {n} ({_ratio(n):.2f}:1)')
            return f'<w:color w:val="{n}"/>'
        return tag
    return re.sub(r'<w:color\b[^>]*/>', rep, x)

def _r2(a, b):
    la, lb = _lum(a), _lum(b); return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)
def _toward(h, target, bg):
    """move color h toward target (FFFFFF or 000000) just far enough for 5:1 against bg"""
    t = [int(target[i:i + 2], 16) for i in (0, 2, 4)]
    for k in range(0, 101):
        c = ''.join('%02X' % round(int(h[i:i + 2], 16) + (t[i // 2] - int(h[i:i + 2], 16)) * k / 100) for i in (0, 2, 4))
        if _r2(c, bg) >= 5.0: return c
    return target
def shade_fix(s):
    """D9b: text against the shading behind it (run, paragraph or table-cell fill), not just white. WCC, Nov 17, 2026: a
    project plan with white text on teal and green status cells and gray on a navy banner scored 30% (27 instances,
    Major); D9 had even darkened the banner's light text against white. Text on a dark fill is lightened; white text on
    a mid-tone fill keeps its color and the fill is darkened; other text is darkened."""
    reps = []; cell_fill = {}
    cells = [(m.start(), m.end()) for m in re.finditer(r'<w:tc>(?:(?!<w:tc>).)*?</w:tc>', s, re.S)]
    def fill_of(span):
        x = s[span[0]:span[1]]
        f = re.search(r'<w:tcPr>(?:(?!</w:tcPr>).)*?<w:shd [^>]*w:fill="([0-9A-Fa-f]{6})"', x, re.S)
        return f.group(1).upper() if f else None
    for pm in re.finditer(r'<w:p[ >](?:(?!<w:p[ >]).)*?</w:p>', s, re.S):
        cell = min((c for c in cells if c[0] <= pm.start() and pm.end() <= c[1]), key=lambda c: c[1] - c[0], default=None)
        cf = cell_fill.get(cell) or (fill_of(cell) if cell else None)
        ppr = re.search(r'<w:pPr>.*?</w:pPr>', pm.group(0), re.S)
        pf = re.search(r'<w:shd [^>]*w:fill="([0-9A-Fa-f]{6})"', ppr.group(0)) if ppr else None
        for rm in re.finditer(r'<w:r[ >](?:(?!<w:r[ >]).)*?</w:r>', pm.group(0), re.S):
            r = rm.group(0)
            if not re.search(r'<w:t[ >][^<]*\S', r): continue
            rs = re.search(r'<w:rPr>.*?<w:shd [^>]*w:fill="([0-9A-Fa-f]{6})"', r, re.S)
            bg = (rs.group(1) if rs else pf.group(1) if pf else cf or 'FFFFFF').upper()
            cm = re.search(r'<w:color w:val="([0-9A-Fa-f]{6})"[^>]*/>', r)
            fg = cm.group(1).upper() if cm else '000000'
            if _r2(fg, bg) >= 4.5: continue
            if not rs and not pf and cell and _lum(fg) > 0.8 and _lum(bg) > 0.1:
                nf = _toward(bg, '000000', fg); cell_fill[cell] = nf
                COLOR_LOG.append(f'cell fill {bg} under {fg} text ({_r2(fg, bg):.2f}:1) -> {nf} ({_r2(fg, nf):.2f}:1)')
                continue
            nc = _toward(fg, 'FFFFFF' if _lum(bg) < 0.18 else '000000', bg)
            COLOR_LOG.append(f'{fg} on {bg} ({_r2(fg, bg):.2f}:1) -> {nc} ({_r2(nc, bg):.2f}:1)')
            if cm: nr = r.replace(cm.group(0), f'<w:color w:val="{nc}"/>', 1)
            elif '<w:rPr>' in r: nr = r.replace('<w:rPr>', f'<w:rPr><w:color w:val="{nc}"/>', 1)
            else: nr = re.sub(r'(<w:r[ >][^>]*>|<w:r>)', r'\1' + f'<w:rPr><w:color w:val="{nc}"/></w:rPr>', r, count=1)
            reps.append((pm.start() + rm.start(), pm.start() + rm.end(), nr))
    for cell, nf in cell_fill.items():
        x = s[cell[0]:cell[1]]
        m = re.search(r'(<w:tcPr>(?:(?!</w:tcPr>).)*?<w:shd )([^>]*?)(/>)', x, re.S)
        attrs = re.sub(r'\s*w:themeFill\w*="[^"]*"', '', m.group(2)); attrs = re.sub(r'w:fill="[0-9A-Fa-f]{6}"', f'w:fill="{nf}"', attrs)
        reps.append((cell[0] + m.start(), cell[0] + m.end(), m.group(1) + attrs + m.group(3)))
    for a_, b_, t_ in sorted(reps, key=lambda z: -z[0]): s = s[:a_] + t_ + s[b_:]
    return s

for n in list(files):
    if re.match(r'word/(document|styles|numbering|header\d*|footer\d*|footnotes|endnotes)\.xml$', n):
        s = floor(X(n))
        s = re.sub(r'<w:jc w:val="(?:both|distribute)"\s*/>', '<w:jc w:val="left"/>', s)
        s = fix_colors(s)
        if re.match(r'word/(document|header\d*|footer\d*)\.xml$', n): s = shade_fix(s)
        # schema: w:pgMar needs w:gutter (some generators leave it out; Word calls the file damaged)
        s = re.sub(r'<w:pgMar\b(?![^>]*w:gutter)([^>]*?)(/?)>', r'<w:pgMar\1 w:gutter="0"\2>', s)
        # normalize stray languages to en-US
        s = re.sub(r'<w:lang w:val="(?!en-US)[^"]*"', '<w:lang w:val="en-US"', s)
        put(n, s)

# D6/D7 [WCC Panorama: "heading structure is not properly nested" is SEVERE for Word files at WCC]
# each heading at most one level below the one before it; the first heading is level 1
doc = X('word/document.xml'); prev = 0; HEADFIX = []
# paragraphs that are headings only by outline level (no Heading style): Word's navigation shows them, Panorama
# doesn't count them. Give them the matching Heading style.
def _ol(m):
    p = m.group(0)
    if re.search(r'<w:pStyle w:val="Heading\d"', p): return p
    lv = int(re.search(r'<w:outlineLvl w:val="(\d)"', p).group(1))
    if lv > 5: return p
    HEADFIX.append(f'outline->H{lv + 1}')
    p = re.sub(r'<w:pStyle w:val="[^"]*"\s*/>', '', p, count=1)
    return re.sub(r'<w:pPr>', f'<w:pPr><w:pStyle w:val="Heading{lv + 1}"/>', p, count=1)
doc = re.sub(r'<w:p\b(?:(?!<w:p\b).)*?<w:outlineLvl w:val="\d"/>(?:(?!<w:p\b).)*?</w:p>', _ol, doc, flags=re.S)
# a document whose headings start at H2 (or lower) is shifted up so its top level is H1 (D6)
levels = [int(x) for x in re.findall(r'<w:pStyle w:val="Heading([1-6])"', doc)]
shift = (min(levels) - 1) if levels and 1 not in levels else 0
if shift:
    doc = re.sub(r'(<w:pStyle w:val="Heading)([1-6])"', lambda m: f'{m.group(1)}{int(m.group(2)) - shift}"', doc)
    HEADFIX.append(f'all headings up {shift}')
def _h(m):
    global prev
    lv = int(m.group(2)); new = min(lv, prev + 1) if prev else 1
    if new != lv: HEADFIX.append(f'H{lv}->H{new}')
    prev = new
    return f'{m.group(1)}Heading{new}"'
doc = re.sub(r'(<w:pStyle w:val=")Heading([1-6])"', _h, doc)

# D17b [WCC Panorama "This element should be formatted as a list" (Major)]: a heading that starts with a typed
# "A. " / "1. " / "IV. " is still flagged as an unformatted list, even with a Heading style (WCC, Nov 2026).
# Turn the typed marker into real heading numbering: same look, marker made by Word.
import html as _h2
NUMHEAD = re.compile(r'^\s*((?:[A-Z]|\d{1,2}|[IVX]{1,4}))[.)]\s+')
def _ptxt(p): return _h2.unescape(''.join(re.findall(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>', p)))
heads = [m for m in re.finditer(r'<w:p\b(?:(?!<w:p\b).)*?</w:p>', doc, re.S)
         if re.search(r'<w:pStyle w:val="Heading[1-6]"', m.group(0)) and '<w:numPr>' not in m.group(0) and NUMHEAD.match(_ptxt(m.group(0)))]
if heads:
    num = X('word/numbering.xml') if 'word/numbering.xml' in files else ''
    if not num:
        num = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:numbering xmlns:w="http://schemas.openxmlformats.org/'
               'wordprocessingml/2006/main"></w:numbering>')
        put('[Content_Types].xml', X('[Content_Types].xml').replace('</Types>', '<Override PartName="/word/numbering.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/></Types>'))
        put('word/_rels/document.xml.rels', X('word/_rels/document.xml.rels').replace('</Relationships>', '<Relationship '
            'Id="rIdNumHead" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/></Relationships>'))
    aid = max([int(x) for x in re.findall(r'w:abstractNumId="(\d+)"', num)] + [200]) + 1
    nid = max([int(x) for x in re.findall(r'<w:num w:numId="(\d+)"', num)] + [200]) + 1
    abstracts, nums, out, pos = '', '', [], 0
    for m in heads:
        p = m.group(0); mk = NUMHEAD.match(_ptxt(p)).group(1)
        fmt, start = (('decimal', int(mk)) if mk.isdigit() else ('upperRoman', 'IVX'.index(mk[0]) + 1) if set(mk) <= set('IVX') and len(mk) > 1
                      else ('upperLetter', ord(mk) - 64))
        abstracts += (f'<w:abstractNum w:abstractNumId="{aid}"><w:multiLevelType w:val="singleLevel"/><w:lvl w:ilvl="0"><w:start w:val="{start}"/>'
                      f'<w:numFmt w:val="{fmt}"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="0" w:firstLine="0"/></w:pPr></w:lvl></w:abstractNum>')
        nums += f'<w:num w:numId="{nid}"><w:abstractNumId w:val="{aid}"/></w:num>'
        # strip the typed marker from the first text run(s)
        n = len(NUMHEAD.match(_ptxt(p)).group(0))
        def cut(mm):
            global n
            if n <= 0: return mm.group(0)
            t = _h2.unescape(mm.group(2)); k = min(n, len(t)); n -= k
            return mm.group(1) + _h2.escape(t[k:], quote=False) + mm.group(3)
        q = re.sub(r'(<w:t(?:\s[^>]*)?>)([^<]*)(</w:t>)', cut, p)
        # numPr goes after pStyle/keepNext/keepLines/pageBreakBefore/framePr/widowControl (schema order)
        q = re.sub(r'(<w:pStyle w:val="Heading[1-6]"/>(?:<w:keepNext/>|<w:keepLines/>|<w:pageBreakBefore/>|<w:framePr\b[^>]*/>|<w:widowControl(?: [^>]*)?/>)*)',
                   rf'\1<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{nid}"/></w:numPr>', q, count=1)
        out.append(doc[pos:m.start()] + q); pos = m.end(); aid += 1; nid += 1
        HEADFIX.append(f'typed "{mk}." -> numbered heading')
    out.append(doc[pos:]); doc = ''.join(out)
    first = re.search(r'<w:num\b', num)
    ins = first.start() if first else num.find('</w:numbering>')
    num = num[:ins] + abstracts + num[ins:]
    num = num.replace('</w:numbering>', nums + '</w:numbering>')
    put('word/numbering.xml', num)
put('word/document.xml', doc)

sty = X('word/styles.xml')
m = re.search(r'<w:rPrDefault>(.*?)</w:rPrDefault>', sty, re.S)
block = m.group(1) if m else ''
rpr = re.search(r'<w:rPr>(.*?)</w:rPr>', block, re.S)
inner = rpr.group(1) if rpr else ''
inner = re.sub(r'<w:lang\b[^>]*/>', '', inner)
inner = re.sub(r'<w:sz w:val="\d+"/>', '', inner); inner = re.sub(r'<w:szCs w:val="\d+"/>', '', inner)
inner += '<w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="en-US" w:eastAsia="en-US" w:bidi="ar-SA"/>'
# schema order inside rPr: keep fonts first; sz/szCs/lang after them is acceptable for Word and LibreOffice
newdef = f'<w:rPrDefault><w:rPr>{inner}</w:rPr></w:rPrDefault>'
if m:
    sty = sty.replace(m.group(0), newdef)
else:
    sty = sty.replace('<w:docDefaults>', '<w:docDefaults>' + newdef, 1)
put('word/styles.xml', sty)

sett = X('word/settings.xml')
sett = re.sub(r'<w:themeFontLang\b[^>]*/>', '', sett)
# schema order: themeFontLang comes right before clrSchemeMapping (or near the end)
anchor = next((a for a in ('<w:clrSchemeMapping', '<w:doNotIncludeSubdocsInStats', '<w:doNotAutoCompressPictures', '<w:forceUpgrade',
                           '<w:captions', '<w:readModeInkLockDown', '<w:smartTagType', '<w:schemaLibrary', '<w:shapeDefaults',
                           '<w:doNotEmbedSmartTags', '<w:decimalSymbol', '<w:listSeparator', '</w:settings>') if a in sett))
sett = sett.replace(anchor, '<w:themeFontLang w:val="en-US"/>' + anchor, 1)
put('word/settings.xml', sett)

doc = X('word/document.xml')
i = 0
def tblpr(m):
    global i
    cap, desc = meta[i] if i < len(meta) else ('Table', '')
    i += 1
    esc = lambda t: t.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')
    body = m.group(1)
    body = re.sub(r'<w:tblCaption\b[^>]*/>|<w:tblDescription\b[^>]*/>|<w:tblLook\b[^>]*/>', '', body)
    # Word's "Header Row" table-style option; Panorama's DOCX header check reads this, not just w:tblHeader
    look = '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/>'
    return f'<w:tblPr>{body}{look}<w:tblCaption w:val="{esc(cap)}"/><w:tblDescription w:val="{esc(desc)}"/></w:tblPr>'
doc = re.sub(r'<w:tblPr>(.*?)</w:tblPr>', tblpr, doc, flags=re.S)
doc = doc.replace('<w:tblHeader w:val="off"/>', '').replace('<w:trPr></w:trPr>', '')
put('word/document.xml', doc)

if 'docProps/core.xml' not in files:   # some generators write no document properties at all (D2 then can't pass)
    put('docProps/core.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties '
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"></cp:coreProperties>')
    put('[Content_Types].xml', X('[Content_Types].xml').replace('</Types>', '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>'))
    put('_rels/.rels', X('_rels/.rels').replace('</Relationships>', '<Relationship Id="rIdCoreProps" '
        'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>'))
# D18b: a link whose target is a bare email address (no mailto:) shows text identical to its URL: WCC flagged it as "The
# hyperlink text is not descriptive" (Major, a syllabus rendered from HTML, Nov 17, 2026). Give the target its mailto:.
for n in [k for k in files if re.match(r'word/_rels/.*\.rels$', k)]:
    put(n, re.sub(r'Target="(?!mailto:)([\w.+-]+@[\w-]+(?:\.[\w-]+)+)"', r'Target="mailto:\1"', X(n)))
core = X('docProps/core.xml').lstrip('\ufeff')
# Some generators (.NET tools, online form builders) write the core-properties root in the default namespace,
# <coreProperties xmlns="...core-properties">, with no cp: prefix. Every edit below looks for </cp:coreProperties>,
# so the title and language were silently not written (an order form, Nov 17, 2026: both still flagged). Rename
# the root and its unprefixed children to the cp: prefix first.
if not re.search(r'<cp:coreProperties\b', core) and re.search(r'<coreProperties\b', core):
    CP = 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties'
    core = re.sub(r'\sxmlns="' + re.escape(CP) + '"', f' xmlns:cp="{CP}"', core, count=1)
    core = re.sub(r'<(/?)(coreProperties|keywords|lastModifiedBy|revision|category|contentStatus|lastPrinted|version)\b',
                  r'<\1cp:\2', core)
core = re.sub(r'<cp:coreProperties\b([^>]*?)\s*/>', r'<cp:coreProperties\1></cp:coreProperties>', core)   # self-closing root: open it
title = arg('--title')
if title:   # D2: dc:title (an explicit --title replaces whatever is there)
    import html as _html
    core = re.sub(r'<dc:title>.*?</dc:title>|<dc:title\s*/>', '', core, flags=re.S)
    core = core.replace('</cp:coreProperties>', f'<dc:title>{_html.escape(title, quote=False)}</dc:title></cp:coreProperties>')
core = re.sub(r'<dc:language>[^<]*</dc:language>', '', core)
core = core.replace('</cp:coreProperties>', '<dc:language>en-US</dc:language></cp:coreProperties>')
TOOLNAMES = re.compile(r'^\s*(python-docx|python-pptx|openpyxl|docx|Un-named|Steve Canny|pandoc|LibreOffice)?\s*$', re.I)
def setname(core, tag, val):
    m = re.search(r'<%s\b[^>]*>([^<]*)</%s>|<%s\s*/>' % (tag, tag, tag), core)
    cur = (m.group(1) or '') if m else None
    if val: new = val                                  # explicit name from the user
    elif cur is not None and TOOLNAMES.match(cur): new = ''   # strip tool names only
    else: return core                                  # keep a real person's name (D24)
    if m: return core.replace(m.group(0), f'<{tag}>{new}</{tag}>', 1)
    return core.replace('</cp:coreProperties>', f'<{tag}>{new}</{tag}></cp:coreProperties>')
core = setname(core, 'dc:creator', creator)
core = setname(core, 'cp:lastModifiedBy', lastmod)
put('docProps/core.xml', core)

# Numbering levels in schema order: LibreOffice's .doc conversion writes <w:pStyle> before <w:numFmt>, which
# fails Word's schema check (seen on a converted Word 97 file, Nov 2026).
LVL_ORDER = ['start', 'numFmt', 'lvlRestart', 'pStyle', 'isLgl', 'suff', 'lvlText', 'lvlPicBulletId', 'legacy',
             'lvlJc', 'pPr', 'rPr']
def _lvl(m):
    head, body, tail = m.group(1), m.group(2), m.group(3)
    kids = re.findall(r'<w:(\w+)\b[^>]*?(?:/>|>.*?</w:\1>)', body, re.S)
    parts = [k.group(0) for k in re.finditer(r'<w:(\w+)\b[^>]*?(?:/>|>.*?</w:\1>)', body, re.S)]
    if ''.join(parts) != body.strip() or any(k not in LVL_ORDER for k in kids): return m.group(0)
    return head + ''.join(sorted(parts, key=lambda x: LVL_ORDER.index(re.match(r'<w:(\w+)', x).group(1)))) + tail
if 'word/numbering.xml' in files:
    put('word/numbering.xml', re.sub(r'(<w:lvl\b[^>]*>)(.*?)(</w:lvl>)', _lvl, X('word/numbering.xml'), flags=re.S))

tmp = dst + '.tmp'
with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as out:
    for n, b in files.items():
        if n.endswith('/'):
            continue
        out.writestr(n, b)
shutil.move(tmp, dst)
print('tables tagged:', i)
if COLOR_LOG: print('colors darkened:', sorted(set(COLOR_LOG)))
if HEADFIX: print('heading levels fixed:', collections.Counter(HEADFIX) if 'collections' in globals() else HEADFIX[:20])
