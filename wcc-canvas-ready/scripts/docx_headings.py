"""Give a Word file real headings when it has none. D5 [WCAG 1.3.1 + Panorama "The document does not have any
headings" (Major)]. Learned at WCC (Nov 2026): forms, minutes, reports and readings typed with bold lines instead
of Heading styles all scored 30% on this flag; a bold "A. Section name" line was also flagged as an unformatted
list, which a Heading style clears too.

  python3 docx_headings.py in.docx                 # list the candidates and the levels it would give them
  python3 docx_headings.py in.docx out.docx        # apply
  python3 docx_headings.py in.docx out.docx --map map.json   # YOU override: {"paragraph text start": 1|2|3|0}

A candidate is a paragraph outside tables, 2-150 characters, not a list item or caption, that is all bold or
at least 14 pt, and doesn't end like a sentence (. , ;). The first candidate that is also the first text in the
document becomes H1; the rest become H2, or H3 when they are smaller than the H2s. If nothing qualifies, the
first short line of the document is used as H1 and reported, so YOU can check it.
Runs styled with a heading's *character* style ("Heading 2 Char", common in Word's minutes templates) look like
headings but aren't: they become real Heading N paragraphs, even in a file that has other headings.
A file that already has Heading styles is otherwise left alone (postprocess_docx.py fixes its levels).
"""
import sys, re, json, zipfile, html, collections
src = sys.argv[1]
dst = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
over = json.load(open(sys.argv[sys.argv.index('--map') + 1])) if '--map' in sys.argv else {}
z = zipfile.ZipFile(src); files = {n: z.read(n) for n in z.namelist()}
doc = files['word/document.xml'].decode(); sty = files['word/styles.xml'].decode()
txt = lambda p: html.unescape(''.join(re.findall(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>', p)))

FAKE = re.compile(r'<w:rStyle w:val="(?:Heading|heading)\s?([1-6])Char"')
has_real = re.search(r'<w:pStyle w:val="Heading[1-6]"', doc)   # a Title paragraph alone is not a heading (pandoc output)
if has_real and not FAKE.search(doc) and '--force' not in sys.argv:
    print('already has headings: nothing to do');
    if dst: open(dst, 'wb').write(open(src, 'rb').read())
    sys.exit()

# styles whose definition is bold or large count too
bold_styles = set(m.group(1) for m in re.finditer(r'<w:style [^>]*w:styleId="([^"]+)"[^>]*>(?:(?!</w:style>).)*?<w:b/>', sty, re.S))
def size(p):
    s = [int(x) for x in re.findall(r'<w:sz w:val="(\d+)"', p)]
    return max(s) if s else 0

# mark table spans so table paragraphs are skipped
spans, depth, start = [], 0, 0
for m in re.finditer(r'<w:tbl>|</w:tbl>', doc):
    if m.group(0) == '<w:tbl>':
        if depth == 0: start = m.start()
        depth += 1
    else:
        depth -= 1
        if depth == 0: spans.append((start, m.end()))
in_table = lambda i: any(a <= i < b for a, b in spans)

paras = [m for m in re.finditer(r'<w:p\b(?:(?!<w:p\b).)*?</w:p>', doc, re.S) if not in_table(m.start())]
first_text = next((m for m in paras if txt(m.group(0)).strip()), None)
cands = []
for m in paras:
    p = m.group(0); t = txt(p).strip()
    if not (2 <= len(t) <= 150) or '<w:numPr>' in p or re.search(r'w:val="Caption"', p): continue
    if re.search(r'[.,;]$', t) and not re.match(r'^[A-Z0-9]{1,3}\.\s', t): continue
    if t.startswith('<<') or t.startswith('['): continue          # template placeholders
    if t[0] in '“"‘\'' and m is not first_text: continue        # pull quotes are not headings
    runs = [r for r in re.findall(r'<w:r\b(?:(?!<w:r\b).)*?</w:r>', p, re.S) if re.search(r'<w:t[ >]', r) and txt(r).strip()]
    fk = [FAKE.search(r) for r in runs]
    if runs and all(fk) and not re.search(r'<w:pStyle w:val="Heading', p):
        # "Heading 2 Char" applied as a character style: looks like a heading, isn't one (Word minutes templates)
        cands.append([m, t, size(p), int(fk[0].group(1))]); continue
    if has_real: continue
    st = re.search(r'<w:pStyle w:val="([^"]+)"', p)
    if st and st.group(1) == 'Title':
        cands.append([m, t, size(p), 1]); continue
    # bold by direct formatting, or by a bold character style such as pandoc's "Strong"
    rb = lambda r: re.search(r'<w:b/>|<w:b w:val="(1|true)"/>', r) or (re.search(r'<w:rStyle w:val="([^"]+)"', r) and re.search(r'<w:rStyle w:val="([^"]+)"', r).group(1) in bold_styles)
    allbold = runs and all(rb(r) for r in runs)
    allbold = allbold or (st and st.group(1) in bold_styles)
    if allbold or size(p) >= 28:
        cands.append([m, t, size(p), 0])
ft = txt(first_text.group(0)).strip() if first_text is not None else ''
if cands and cands[0][0] is not first_text and ft and len(ft) <= 220 and not ft.startswith('<<'):
    cands.insert(0, [first_text, ft, size(first_text.group(0)), 1])   # the document's own first line is its title
    print('first line used as H1 (CHECK it is the title)')
if not cands and first_text is not None and len(txt(first_text.group(0)).strip()) <= 120 and not txt(first_text.group(0)).strip().startswith('<<'):
    cands.append([first_text, txt(first_text.group(0)).strip(), size(first_text.group(0)), 1])
    print('no bold or large lines: using the first line as H1 (CHECK)')

levels = {}
h2_sizes = []
for i, (m, t, s, fixed) in enumerate(cands):
    if fixed: levels[m.start()] = fixed
    elif i == 0 and m is first_text: levels[m.start()] = 1
    else: h2_sizes.append(s)
big = collections.Counter(h2_sizes).most_common(1)[0][0] if h2_sizes else 0
for i, (m, t, s, fixed) in enumerate(cands):
    if m.start() not in levels:
        levels[m.start()] = 2 if s >= big or not big else 3
    for k, v in over.items():
        if t.startswith(k): levels[m.start()] = v
for m, t, s, _ in cands:
    print(f'  H{levels[m.start()]}' if levels[m.start()] else '  --', repr(t[:80]))
print(f'{sum(1 for v in levels.values() if v)} headings')
if not dst: sys.exit()

out, pos = [], 0
for m, t, s, _ in cands:
    lv = levels[m.start()]
    if not lv: continue
    p = m.group(0)
    p = re.sub(r'<w:pStyle w:val="[^"]*"\s*/>', '', p, count=1)
    p = re.sub(r'<w:numPr>.*?</w:numPr>', '', p, flags=re.S)
    # drop "Heading N Char" run styles: Heading style + its Char style both set bold, and Word toggles it off
    p = re.sub(r'<w:rStyle w:val="(?:Heading|heading)\s?[1-6]Char"\s*/>', '', p)
    # a template whose Heading style is numbered ("I.", "A.") would number the new heading: switch that off
    hs = re.search(rf'<w:style [^>]*w:styleId="Heading{lv}"[^>]*>(?:(?!</w:style>).)*</w:style>', sty, re.S)
    nonum = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr>' if hs and '<w:numPr>' in hs.group(0) else ''
    if '<w:pPr>' in p: p = p.replace('<w:pPr>', f'<w:pPr><w:pStyle w:val="Heading{lv}"/>', 1)
    elif re.search(r'<w:pPr\s*/>', p): p = re.sub(r'<w:pPr\s*/>', f'<w:pPr><w:pStyle w:val="Heading{lv}"/></w:pPr>', p, count=1)
    else: p = re.sub(r'(<w:p\b[^>]*>)', lambda mm: mm.group(1) + f'<w:pPr><w:pStyle w:val="Heading{lv}"/></w:pPr>', p, count=1)
    if nonum:   # schema order: numPr comes after pStyle, keepNext, keepLines, pageBreakBefore, framePr, widowControl
        p = re.sub(r'(<w:pPr><w:pStyle w:val="Heading\d"/>(?:<w:(?:keepNext|keepLines|pageBreakBefore|widowControl)(?:\s[^>]*)?/>|<w:framePr\b[^>]*/>)*)',
                   lambda mm: mm.group(1) + nonum, p, count=1)
    out.append(doc[pos:m.start()] + p); pos = m.end()
out.append(doc[pos:]); doc = ''.join(out)
files['word/document.xml'] = doc.encode()

# make sure the Heading styles exist; keep the text's own look (runs keep their bold/size/color)
for lv in (1, 2, 3):
    if f'w:styleId="Heading{lv}"' not in sty:
        sty = sty.replace('</w:styles>', f'<w:style w:type="paragraph" w:styleId="Heading{lv}"><w:name w:val="heading {lv}"/>'
            f'<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="9"/><w:qFormat/><w:pPr><w:keepNext/>'
            f'<w:spacing w:before="240" w:after="80"/><w:outlineLvl w:val="{lv - 1}"/></w:pPr><w:rPr><w:b/><w:bCs/>'
            f'<w:sz w:val="{32 - 4 * lv}"/><w:szCs w:val="{32 - 4 * lv}"/></w:rPr></w:style></w:styles>')
files['word/styles.xml'] = sty.encode()
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as o:
    for n in z.namelist(): o.writestr(n, files[n])
