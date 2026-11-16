"""Turn Word footnotes/endnotes into in-flow note paragraphs (for PDF export).
Usage: python3 inline_notes.py in.docx out.docx
Each referenced note becomes a paragraph "Note N: <note text>" right after the paragraph that
cites it; the reference mark stays in the text as a Unicode superscript digit (¹, ², …) at the
baseline. Reason: in tagged PDFs a page-bottom footnote sits visually far from its tag position,
and WCC's Panorama flagged that page as "Check reading order" (Severe). Run fix_baseline.py first
or after; both are idempotent for marks.
"""
import re, sys, zipfile, shutil

SUP = str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')
src, dst = sys.argv[1:3]
z = zipfile.ZipFile(src)
files = {n: z.read(n) for n in z.namelist()}
X = lambda n: files[n].decode('utf-8')
doc = X('word/document.xml')
count = 0
for kind in ('footnote', 'endnote'):
    part = f'word/{kind}s.xml'
    if part not in files:
        continue
    notes = X(part)
    bodies = {}
    for m in re.finditer(rf'<w:{kind}\b[^>]*w:id="(\d+)"[^>]*>(.*?)</w:{kind}>', notes, re.S):
        paras = re.findall(r'<w:p\b[^>]*>.*?</w:p>', m.group(2), re.S)
        runs = []
        for p in paras:
            for r in re.findall(r'<w:r\b[^>]*>(?:(?!</w:r>).)*</w:r>', p, re.S):
                if f'<w:{kind}Ref/>' in r:
                    continue
                txt = ''.join(re.findall(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>', r))
                if re.fullmatch(r'\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*', txt):   # mark already converted to text
                    continue
                runs.append(r)
        bodies[m.group(1)] = ''.join(runs)
    order = []
    for m in re.finditer(rf'<w:{kind}Reference\b[^>]*w:id="(\d+)"', doc):
        if m.group(1) not in order:
            order.append(m.group(1))
    num = {i: k + 1 for k, i in enumerate(order)}

    def para(m):
        global count
        p = m.group(0)
        ids = re.findall(rf'<w:{kind}Reference\b[^>]*w:id="(\d+)"', p)
        if not ids:
            return p
        for i in ids:
            mark = str(num[i]).translate(SUP)
            # replace the reference run (and a following custom-mark run, if any) by plain text
            p = re.sub(rf'<w:r\b[^>]*>(?:(?!</w:r>).)*<w:{kind}Reference\b[^>]*w:id="{i}"[^>]*/>(?:(?!</w:r>).)*</w:r>'
                       rf'(?:\s*<w:r\b[^>]*>(?:(?!</w:r>).)*<w:t[^>]*>[⁰¹²³⁴⁵⁶⁷⁸⁹]+</w:t>(?:(?!</w:r>).)*</w:r>)?',
                       f'<w:r><w:t>{mark}</w:t></w:r>', p, count=1, flags=re.S)
        extra = ''
        for i in ids:
            count += 1
            label = 'Note' if kind == 'footnote' else 'Endnote'
            extra += (f'<w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr>'
                      f'<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">{label} {num[i]}: </w:t></w:r>{bodies.get(i, "")}</w:p>')
        return p + extra
    doc = re.sub(r'<w:p\b[^>]*>(?:(?!</w:p>).)*</w:p>', para, doc, flags=re.S)
    # drop the converted notes (keep separator notes with ids -1/0)
    notes = re.sub(rf'<w:{kind}\b[^>]*w:id="(\d+)"[^>]*>.*?</w:{kind}>',
                   lambda m: '' if m.group(1) in num else m.group(0), notes, flags=re.S)
    files[part] = notes.encode('utf-8')
files['word/document.xml'] = doc.encode('utf-8')
tmp = dst + '.tmp'
with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as out:
    for n, b in files.items():
        if not n.endswith('/'):
            out.writestr(n, b)
shutil.move(tmp, dst)
print('notes inlined:', count)
