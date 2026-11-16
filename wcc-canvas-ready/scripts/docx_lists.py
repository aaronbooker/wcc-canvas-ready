"""Turn typed Markdown/typed structure into real Word structure: typed "## Heading" lines become Heading styles
(D5), "**bold**" inside one run becomes bold, and typed bullets and numbers become real Word lists. D17 [WCAG 1.3.1 + Panorama "This element should be
formatted as a list"]. Usage: python3 docx_lists.py in.docx out.docx
A paragraph that starts with "- ", "* ", "• ", "◦ ", "▪ " becomes a bulleted list item; "1. " / "1) " / "a. "
a numbered item (runs of consecutive items share one list; numbering restarts after any other paragraph).
The typed marker (and a tab after it) is removed from the text. Headings are left alone: a heading that starts
with "1." is a numbered heading, not a list. Indented markers (leading spaces/tabs, or w:ind) become level 2.
"""
import sys, re, zipfile, html
src, dst = sys.argv[1], sys.argv[2]
z = zipfile.ZipFile(src); files = {n: z.read(n) for n in z.namelist()}
doc = files['word/document.xml'].decode()
BUL = re.compile(r'^(\s*)([-*•◦▪‣·])[\s ]+')
NUM = re.compile(r'^(\s*)(\d{1,2}|[a-z])[.)][\s ]+')
txt = lambda p: html.unescape(''.join(re.findall(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>', p)))

num = files.get('word/numbering.xml', b'').decode()
if not num:
    num = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:numbering xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main"></w:numbering>')
    files['[Content_Types].xml'] = files['[Content_Types].xml'].decode().replace('</Types>',
        '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/></Types>').encode()
    r = files['word/_rels/document.xml.rels'].decode()
    files['word/_rels/document.xml.rels'] = r.replace('</Relationships>', '<Relationship Id="rIdNumTyped" Type="http://schemas.'
        'openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/></Relationships>').encode()
aid = max([int(x) for x in re.findall(r'w:abstractNumId="(\d+)"', num)] + [100]) + 1
nid = max([int(x) for x in re.findall(r'<w:num w:numId="(\d+)"', num)] + [100]) + 1
def lvl(i, fmt, text):
    return (f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="{fmt}"/><w:lvlText w:val="{text}"/><w:lvlJc w:val="left"/>'
            f'<w:pPr><w:ind w:left="{720 * (i + 1)}" w:hanging="360"/></w:pPr>'
            + ('<w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr>' if fmt == 'bullet' else '') + '</w:lvl>')
abs_b, abs_n = aid, aid + 1
abstract = (f'<w:abstractNum w:abstractNumId="{abs_b}"><w:multiLevelType w:val="hybridMultilevel"/>'
            + lvl(0, 'bullet', '') + lvl(1, 'bullet', 'o').replace('Symbol', 'Courier New') + '</w:abstractNum>'
            f'<w:abstractNum w:abstractNumId="{abs_n}"><w:multiLevelType w:val="hybridMultilevel"/>'
            + lvl(0, 'decimal', '%1.') + lvl(1, 'lowerLetter', '%2.') + '</w:abstractNum>')
new_nums = []
def new_num(abs_id):
    global nid
    nid += 1; new_nums.append(f'<w:num w:numId="{nid}"><w:abstractNumId w:val="{abs_id}"/>'
                              f'<w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>')
    return nid

def strip_marker(p, n):
    """remove the first n characters of visible text (the typed marker), across runs"""
    def cut(m):
        nonlocal n
        if n <= 0: return m.group(0)
        t = html.unescape(m.group(2)); k = min(n, len(t)); n -= k; t = t[k:]
        if n == 0: t = t.lstrip('\t')
        return m.group(1) + html.escape(t, quote=False) + m.group(3)
    p = re.sub(r'(<w:t(?:\s[^>]*)?>)([^<]*)(</w:t>)', cut, p)
    return re.sub(r'(<w:r\b[^>]*>(?:<w:rPr>(?:(?!</w:rPr>).)*</w:rPr>)?)<w:tab/>', r'\1', p, count=1, flags=re.S)

# typed Markdown headings: "## Text" -> Heading2 (D5). Pasted Markdown is common in AI-drafted handouts.
HN = 0
def _mdh(m):
    global HN
    p = m.group(0); t = txt(p)
    h = re.match(r'^(#{1,6})\s+\S', t)
    if not h or re.search(r'<w:pStyle w:val="Heading', p): return p
    HN += 1
    q = strip_marker(p, len(h.group(1)) + 1)
    q = re.sub(r'<w:pStyle w:val="[^"]*"\s*/>', '', q, count=1)
    if '<w:pPr>' in q: return q.replace('<w:pPr>', f'<w:pPr><w:pStyle w:val="Heading{len(h.group(1))}"/>', 1)
    return re.sub(r'(<w:p\b[^>]*>)', rf'\1<w:pPr><w:pStyle w:val="Heading{len(h.group(1))}"/></w:pPr>', q, count=1)
doc = re.sub(r'<w:p\b(?:(?!<w:p\b).)*?</w:p>', _mdh, doc, flags=re.S)
# "**bold**" typed inside a single text run -> a bold run
def _bold(m):
    run = m.group(0)
    t = re.search(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>', run)
    if not t or '**' not in t.group(1): return run
    rpr = (re.search(r'<w:rPr>.*?</w:rPr>', run, re.S) or [''])[0] if re.search(r'<w:rPr>', run) else ''
    parts = re.split(r'\*\*(.+?)\*\*', t.group(1))
    if len(parts) == 1: return run
    out = ''
    for i, ptxt in enumerate(parts):
        if not ptxt: continue
        r = rpr
        if i % 2:
            r = r.replace('<w:rPr>', '<w:rPr><w:b/>', 1) if r else '<w:rPr><w:b/></w:rPr>'
        out += f'<w:r>{r}<w:t xml:space="preserve">{ptxt}</w:t></w:r>'
    return out
doc = re.sub(r'<w:r\b(?:(?!<w:r\b).)*?</w:r>', _bold, doc, flags=re.S)

# a typed list written as ONE paragraph with line breaks ("• a<br/>• b") is split into one paragraph per line first
SPLIT = 0
def _split(m):
    global SPLIT
    p = m.group(0); t = txt(p)
    if '<w:br/>' not in p or not (BUL.match(t) or NUM.match(t)): return p
    head = re.match(r'<w:p\b[^>]*>(?:<w:pPr>.*?</w:pPr>|<w:pPr/>)?', p, re.S).group(0)
    body = p[len(head):-len('</w:p>')]
    def run(rm):
        r = rm.group(0)
        if '<w:br/>' not in r: return r
        open_tag = re.match(r'<w:r\b[^>]*>', r).group(0)
        rpr = (re.search(r'<w:rPr>.*?</w:rPr>', r, re.S) or [''])[0] if '<w:rPr>' in r else ''
        return r.replace('<w:br/>', '</w:r>\u00a7' + open_tag + rpr)
    body = re.sub(r'<w:r\b(?:(?!<w:r\b).)*?</w:r>', run, body, flags=re.S)
    segs = [sgm for sgm in body.split('\u00a7')]
    segs = [re.sub(r'<w:r\b[^>]*>(?:<w:rPr>(?:(?!</w:rPr>).)*</w:rPr>)?</w:r>', '', sgm, flags=re.S) for sgm in segs]   # empty runs only
    segs = [sgm for sgm in segs if txt(sgm).strip()]
    if len(segs) < 2: return p
    SPLIT += len(segs) - 1
    return ''.join(head + sgm + '</w:p>' for sgm in segs)
doc = re.sub(r'<w:p\b(?:(?!<w:p\b).)*?</w:p>', _split, doc, flags=re.S)

# a typed number alone in a table cell ("1." in an outcomes table, one per row) is the row's own label, not a
# list: converting each one made separate lists that all restart at 1 (WCC syllabus, Nov 2026). Keep those typed.
cells = [(c.start(), c.end()) for c in re.finditer(r'<w:tc>(?:(?!<w:tc>).)*?</w:tc>', doc, re.S)]
def cell_of(i):
    for a, b2 in cells:
        if a <= i < b2: return (a, b2)
lone = set()
for a, b2 in cells:
    nums = [q for q in re.finditer(r'<w:p\b(?:(?!<w:p\b).)*?</w:p>', doc[a:b2], re.S) if NUM.match(txt(q.group(0)))]
    if len(nums) == 1: lone.add((a, b2))
out, pos, cur, count = [], 0, None, 0
for m in re.finditer(r'<w:p\b(?:(?!<w:p\b).)*?</w:p>', doc, re.S):
    p = m.group(0); t = txt(p)
    is_head = re.search(r'<w:pStyle w:val="(Heading\d|Title)"', p)
    b, nm = BUL.match(t), NUM.match(t)
    if nm and not b and cell_of(m.start()) in lone: nm = None
    if is_head or '<w:numPr>' in p or not (b or nm) or len(t) < 3:
        cur = None if t.strip() else cur
        continue
    kind = 'b' if b else 'n'
    mk = b or nm
    level = 1 if (mk.group(1) or re.search(r'<w:ind w:left="(?:[7-9]\d\d|[1-9]\d{3})"', p)) else 0
    if cur is None or cur[0] != kind: cur = (kind, new_num(abs_b if kind == 'b' else abs_n))
    q = strip_marker(p, len(mk.group(0)))
    numpr = f'<w:numPr><w:ilvl w:val="{level}"/><w:numId w:val="{cur[1]}"/></w:numPr>'
    if '<w:pPr>' in q:
        q = re.sub(r'<w:ind\b[^>]*/>', '', q, count=1)
        q = re.sub(r'(<w:pPr>(?:<w:pStyle [^>]*/>)?(?:<w:keepNext/>)?(?:<w:keepLines/>)?(?:<w:pageBreakBefore/>)?)', r'\1' + numpr, q, count=1)
    else:
        q = re.sub(r'(<w:p\b[^>]*>)', r'\1<w:pPr><w:pStyle w:val="ListParagraph"/>' + numpr + '</w:pPr>', q, count=1)
    out.append(doc[pos:m.start()] + q); pos = m.end(); count += 1
out.append(doc[pos:])
files['word/document.xml'] = ''.join(out).encode()
if count:
    first_num = re.search(r'<w:num\b', num)
    ins = num.find('<w:num ') if first_num else num.find('</w:numbering>')
    num = num[:ins] + abstract + num[ins:]
    num = num.replace('</w:numbering>', ''.join(new_nums) + '</w:numbering>')
    files['word/numbering.xml'] = num.encode()
    sty = files['word/styles.xml'].decode()
    if 'w:styleId="ListParagraph"' not in sty:
        sty = sty.replace('</w:styles>', '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
                          '<w:basedOn w:val="Normal"/><w:uiPriority w:val="34"/><w:qFormat/><w:pPr><w:ind w:left="720"/>'
                          '<w:contextualSpacing/></w:pPr></w:style></w:styles>')
        files['word/styles.xml'] = sty.encode()
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as o:
    for n in dict.fromkeys(list(z.namelist()) + list(files)): o.writestr(n, files[n])
print(f'split one-paragraph lists: +{SPLIT} paragraphs; typed headings -> Heading styles: {HN}; typed list items -> real lists: {count} ({len(new_nums)} lists)')
