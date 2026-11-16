"""Give every table in an existing .docx a visible caption, hidden caption/summary and a Header Row flag.
Usage: python3 docx_captions.py in.docx out.docx captions.json
captions.json: [{"title": "...", "summary": "..."}, ...] one per table in document order
               (leave it out to get a draft list printed: titles from the bold label/paragraph just above each table).
D15 [WCC Panorama] "Table does not have a caption" (Major): visible "Table N: title" paragraph, style Caption
    (12 pt, bold, #262626, keepNext) directly above the table, with a SEQ field so Word renumbers it.
D16 [Best practice] w:tblCaption + w:tblDescription in w:tblPr.
D14 [WCAG+Panorama 1.3.1] w:tblLook firstRow="1" and w:tblHeader on row 1 (Panorama checks tblLook).
A table that already has a Caption-style paragraph directly above it is left alone.
"""
import sys, re, json, zipfile, html
src, dst = sys.argv[1], sys.argv[2]
caps = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None
z = zipfile.ZipFile(src); files = {n: z.read(n) for n in z.namelist()}
doc = files['word/document.xml'].decode(); sty = files['word/styles.xml'].decode()
txt = lambda x: html.unescape(''.join(re.findall(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>', x))).strip()
esc = lambda s: html.escape(s, quote=True)

if 'w:styleId="Caption"' not in sty:
    sty = sty.replace('</w:styles>',
        '<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
        '<w:uiPriority w:val="35"/><w:unhideWhenUsed/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="120" w:after="120"/></w:pPr>'
        '<w:rPr><w:b/><w:bCs/><w:color w:val="262626"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:style></w:styles>')
else:  # Word's built-in Caption is 9 pt italic blue: override
    sty = re.sub(r'(<w:style [^>]*w:styleId="Caption"[^>]*>)(.*?)(</w:style>)',
        lambda m: m.group(1) + re.sub(r'<w:rPr>.*?</w:rPr>', '', m.group(2), flags=re.S).replace('</w:pPr>', '</w:pPr>') +
        '<w:rPr><w:b/><w:bCs/><w:i w:val="0"/><w:color w:val="262626"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>' + m.group(3), sty, flags=re.S)
files['word/styles.xml'] = sty.encode()

# only top-level tables (nested tables keep their parent's caption)
out, pos, n, drafts = [], 0, 0, []
for m in re.finditer(r'<w:tbl>(?:(?!<w:tbl>).)*?</w:tbl>|<w:tbl>.*?</w:tbl>', doc, re.S):
    pass
depth_tbls, i = [], 0
for m in re.finditer(r'<w:tbl>|</w:tbl>', doc):
    if m.group(0) == '<w:tbl>':
        if i == 0: start = m.start()
        i += 1
    else:
        i -= 1
        if i == 0: depth_tbls.append((start, m.end()))
for k, (a, b) in enumerate(depth_tbls):
    tbl = doc[a:b]
    before = doc[pos:a]
    paras = re.findall(r'<w:p\b(?:(?!<w:p\b).)*?</w:p>', before, re.S)
    prev = paras[-1] if paras else ''
    has_cap = 'w:val="Caption"' in prev
    label = txt(prev)
    c = caps[k] if caps and k < len(caps) else {'title': label[:80] or f'Table {k + 1}', 'summary': ''}
    drafts.append({'title': c['title'], 'summary': c.get('summary', ''), 'above': label[:90]})
    # tblPr: caption, description, tblLook firstRow
    tp = re.search(r'<w:tblPr>.*?</w:tblPr>', tbl, re.S).group(0)
    tp2 = re.sub(r'<w:tblCaption [^>]*/>|<w:tblDescription [^>]*/>', '', tp)
    if re.search(r'<w:tblLook\b', tp2):
        tp2 = re.sub(r'<w:tblLook\b([^>]*?)/>', lambda mm: '<w:tblLook' + re.sub(r'\sw:firstRow="\d"', '', mm.group(1)) + ' w:firstRow="1"/>', tp2)
    else:
        tp2 = tp2.replace('</w:tblPr>', '<w:tblLook w:val="0420" w:firstRow="1" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>')
    tp2 = tp2.replace('</w:tblPr>', f'<w:tblCaption w:val="{esc(c["title"])}"/><w:tblDescription w:val="{esc(c.get("summary") or c["title"])}"/></w:tblPr>')
    tbl = tbl.replace(tp, tp2, 1)
    r1 = re.search(r'<w:tr\b[^>]*>', tbl)
    first_row = tbl[r1.end():]
    if '<w:tblHeader' not in first_row.split('</w:trPr>')[0][:400]:
        if first_row.startswith('<w:trPr>'): tbl = tbl[:r1.end()] + '<w:trPr><w:tblHeader/>' + first_row[len('<w:trPr>'):]
        else: tbl = tbl[:r1.end()] + '<w:trPr><w:tblHeader/></w:trPr>' + first_row
    cap = ''
    if not has_cap:
        n += 1
        cap = ('<w:p><w:pPr><w:pStyle w:val="Caption"/><w:keepNext/></w:pPr>'
               '<w:r><w:t xml:space="preserve">Table </w:t></w:r>'
               '<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> SEQ Table \\* ARABIC </w:instrText></w:r>'
               f'<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>{k + 1}</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>'
               f'<w:r><w:t xml:space="preserve">: {html.escape(c["title"])}</w:t></w:r></w:p>')
    out.append(before + cap + tbl); pos = b
out.append(doc[pos:])
files['word/document.xml'] = ''.join(out).encode()
if caps is None:
    print(json.dumps(drafts, indent=1, ensure_ascii=False))
else:
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as o:
        for name in z.namelist(): o.writestr(name, files[name])
    print(f'captions added: {n} of {len(depth_tbls)} tables')
