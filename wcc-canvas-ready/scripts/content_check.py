"""Compare words in the original PDF against the rebuild. Usage: content_check.py orig.pdf new.docx|new.html|new.pdf
Running headers/footers the original printed (page numbers, repeated titles) show up as "missing"; that is expected."""
import re, sys, zipfile, collections, html, pdfplumber
pdf = pdfplumber.open(sys.argv[1])
ow = []
for pg in pdf.pages:
    for w in pg.extract_words(extra_attrs=['fontname'], x_tolerance=1.5):
        if 'HiddenHorzOCR' in w['fontname'] or w['top'] < 45:
            continue
        ow.append(w['text'])
otext = ' '.join(ow)
otext = re.sub(r'(\w)- (\w)', r'\1\2', otext)          # line-end hyphens
if sys.argv[2].endswith('.docx'):
    x = zipfile.ZipFile(sys.argv[2]).read('word/document.xml').decode()
    ntext = html.unescape(' '.join(re.findall(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>', x)))
elif sys.argv[2].endswith(('.html', '.htm')):
    x = open(sys.argv[2]).read()
    x = re.sub(r'<(style|script)\b.*?</\1>|<img\b[^>]*>', ' ', x, flags=re.S)
    ntext = html.unescape(re.sub(r'<[^>]+>', ' ', x[x.find('<body'):]))
else:
    ntext = ' '.join(pg.extract_text() or '' for pg in pdfplumber.open(sys.argv[2]).pages)
norm = lambda t: [re.sub(r'[^a-z0-9]', '', w.lower()) for w in re.split(r'[\s—–/]+', t)]
O = collections.Counter(w for w in norm(otext) if w)
N = collections.Counter(w for w in norm(ntext) if w)
print('original words:', sum(O.values()), ' rebuilt words:', sum(N.values()))
miss = O - N
extra = N - O
print('in original, missing from rebuild (%d):' % sum(miss.values()), sorted(miss.items(), key=lambda kv: -kv[1])[:60])
print('added in rebuild (%d):' % sum(extra.values()), sorted(extra.items(), key=lambda kv: -kv[1])[:40])
