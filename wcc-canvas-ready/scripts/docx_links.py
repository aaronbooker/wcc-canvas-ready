"""Replace Word link text that is just a URL with descriptive text. D18 [WCAG 2.4.4 + Panorama "The hyperlink text
is not descriptive" (Major in Word at WCC, Nov 2026: a syllabus with 9 bare-URL links stayed at 30%)].
  python3 docx_links.py in.docx                     # list every link: shown text -> address
  python3 docx_links.py in.docx out.docx links.json  # apply
links.json maps the text now shown to the new text, e.g.
  {"https://www.whatcom.edu/student-services/virtual-front-desk": "Virtual Front Desk (whatcom.edu)"}
Keep the domain in parentheses so print readers still see where the link goes. Formatting and address stay.
"""
import sys, re, json, zipfile, html
src = sys.argv[1]
z = zipfile.ZipFile(src); files = {n: z.read(n) for n in z.namelist()}
doc = files['word/document.xml'].decode()
rels = files['word/_rels/document.xml.rels'].decode()
tgt = {m.group(1): m.group(2) for m in re.finditer(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels)}
tgt.update({m.group(2): m.group(1) for m in re.finditer(r'Target="([^"]+)"[^>]*Id="([^"]+)"', rels)})
txt = lambda x: html.unescape(''.join(re.findall(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>', x)))
HL = re.compile(r'<w:hyperlink\b[^>]*>.*?</w:hyperlink>', re.S)
if len(sys.argv) < 4:
    for m in HL.finditer(doc):
        rid = re.search(r'r:id="([^"]+)"', m.group(0))
        print(f'"{txt(m.group(0)).strip()}" -> {tgt.get(rid.group(1), "(anchor)") if rid else "(anchor)"}')
    sys.exit()
dst, mp = sys.argv[2], json.load(open(sys.argv[3]))
n = 0
def fix(m):
    global n
    h = m.group(0); shown = txt(h).strip()
    if shown not in mp: return h
    first = [True]
    def t(mm):
        if first[0]:
            first[0] = False
            return f'<w:t xml:space="preserve">{html.escape(mp[shown], quote=False)}</w:t>'
        return '<w:t></w:t>'
    n += 1
    return re.sub(r'<w:t(?:\s[^>]*)?>[^<]*</w:t>', t, h)
doc = HL.sub(fix, doc)
files['word/document.xml'] = doc.encode()
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as o:
    for k in z.namelist(): o.writestr(k, files[k])
print(f'link texts replaced: {n}')
