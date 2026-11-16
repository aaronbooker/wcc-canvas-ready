"""Remove every baseline shift from a .docx (Panorama "Check reading order" trigger).
Usage: python3 fix_baseline.py in.docx out.docx
- runs with w:vertAlign sub/superscript or a non-zero w:position: digits (and + - = ( )) become
  Unicode sub/superscript characters at full size; other characters stay as normal text; the
  vertAlign/position are removed
- footnote/endnote reference marks become Word custom marks written as Unicode superscript
  digits (¹ ² ³ …) at the baseline, in the body and inside the notes
- FootnoteReference/EndnoteReference styles lose vertAlign/position
"""
import re, sys, zipfile, shutil

SUP = str.maketrans('0123456789+-=()', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾')
SUB = str.maketrans('0123456789+-=()', '₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎')

src, dst = sys.argv[1:3]
z = zipfile.ZipFile(src)
files = {n: z.read(n) for n in z.namelist()}
X = lambda n: files[n].decode('utf-8')
put = lambda n, s: files.__setitem__(n, s.encode('utf-8'))
stats = {'shifted_runs': 0, 'note_marks': 0}

def fix_runs(xml):
    def run(m):
        r = m.group(0)
        if '<w:footnoteReference' in r or '<w:endnoteReference' in r or '<w:footnoteRef' in r or '<w:endnoteRef' in r:
            return r
        va = re.search(r'<w:vertAlign w:val="(superscript|subscript)"/>', r)
        pos = re.search(r'<w:position w:val="(-?\d+)"/>', r)
        p = int(pos.group(1)) if pos else 0
        if not va and p == 0:
            return re.sub(r'<w:position w:val="0"/>', '', r)
        kind = (va.group(1) == 'superscript') if va else (p > 0)
        table = SUP if kind else SUB
        r = re.sub(r'<w:vertAlign w:val="(?:superscript|subscript)"/>|<w:position w:val="-?\d+"/>', '', r)
        r = re.sub(r'(<w:t(?:\s[^>]*)?>)([^<]*)(</w:t>)', lambda t: t.group(1) + t.group(2).translate(table) + t.group(3), r)
        stats['shifted_runs'] += 1
        return r
    return re.sub(r'<w:r\b[^>]*>(?:(?!</w:r>).)*</w:r>', run, xml, flags=re.S)

def sup_num(n):
    return str(n).translate(SUP)

for kind in ('footnote', 'endnote'):
    part = f'word/{kind}s.xml'
    doc = X('word/document.xml')
    ids = []
    for m in re.finditer(rf'<w:{kind}Reference\b[^>]*w:id="(\d+)"', doc):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    num = {i: k + 1 for k, i in enumerate(ids)}
    def ref(m):
        r = m.group(0)
        i = re.search(rf'<w:{kind}Reference\b[^>]*w:id="(\d+)"', r).group(1)
        r = re.sub(r'<w:vertAlign w:val="(?:superscript|subscript)"/>|<w:position w:val="-?\d+"/>', '', r)
        r = re.sub(rf'<w:{kind}Reference\b([^>]*?)\s*w:customMarkFollows="[^"]*"', rf'<w:{kind}Reference\1', r)
        r = re.sub(rf'<w:{kind}Reference\b', f'<w:{kind}Reference w:customMarkFollows="1"', r, count=1)
        rpr = re.search(r'<w:rPr>.*?</w:rPr>', r, re.S)
        stats['note_marks'] += 1
        return r + f'<w:r>{rpr.group(0) if rpr else ""}<w:t>{sup_num(num.get(i, 1))}</w:t></w:r>'
    doc = re.sub(rf'<w:r\b[^>]*>(?:(?!</w:r>).)*<w:{kind}Reference\b(?:(?!</w:r>).)*</w:r>', ref, doc, flags=re.S)
    put('word/document.xml', doc)
    if part in files:
        notes = X(part)
        def note(m):
            body = m.group(0)
            i = m.group(1)
            def mark(r):
                rr = r.group(0)
                rr = re.sub(r'<w:vertAlign w:val="(?:superscript|subscript)"/>|<w:position w:val="-?\d+"/>', '', rr)
                return re.sub(rf'<w:{kind}Ref/>', f'<w:t>{sup_num(num.get(i, 1))}</w:t>', rr)
            return re.sub(rf'<w:r\b[^>]*>(?:(?!</w:r>).)*<w:{kind}Ref/>(?:(?!</w:r>).)*</w:r>', mark, body, flags=re.S)
        notes = re.sub(rf'<w:{kind}\b[^>]*w:id="(\d+)"[^>]*>.*?</w:{kind}>', note, notes, flags=re.S)
        put(part, notes)

for n in list(files):
    if re.match(r'word/(document|footnotes|endnotes|header\d*|footer\d*)\.xml$', n):
        put(n, fix_runs(X(n)))
sty = X('word/styles.xml')
sty = re.sub(r'(<w:style\b[^>]*w:styleId="(?:FootnoteReference|EndnoteReference)"[^>]*>.*?</w:style>)',
             lambda m: re.sub(r'<w:vertAlign w:val="(?:superscript|subscript)"/>|<w:position w:val="-?\d+"/>', '', m.group(1)), sty, flags=re.S)
put('word/styles.xml', sty)

tmp = dst + '.tmp'
with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as out:
    for n, b in files.items():
        if not n.endswith('/'):
            out.writestr(n, b)
shutil.move(tmp, dst)
print(stats)
