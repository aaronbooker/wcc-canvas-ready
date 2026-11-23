"""Compare words in the original PDF against the rebuild. Usage: content_check.py orig.pdf new.docx|new.html|new.pdf
Running headers/footers the original printed (page numbers, repeated titles) show up as "missing"; that is expected.
Pages of the original with no text (scans, pictures) are named, and the rebuild's extra words are then not called "added"."""
import re, sys, zipfile, collections, html, pdfplumber
pdf = pdfplumber.open(sys.argv[1])
ow, blank = [], []
for i, pg in enumerate(pdf.pages, 1):
    n = 0
    for w in pg.extract_words(extra_attrs=['fontname'], x_tolerance=1.5):
        if 'HiddenHorzOCR' in w['fontname'] or w['top'] < 45:
            continue
        ow.append(w['text']); n += 1
    if not n: blank.append(i)
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
# Pictures count too: a rebuild once dropped all 16 pictures of a guide while every word matched (Nov 22, 2026).
opics = sum(len(pg.images) for pg in pdf.pages)
if sys.argv[2].endswith('.docx'):
    npics = len(re.findall(r'<pic:pic\b', x))
elif sys.argv[2].endswith(('.html', '.htm')):
    npics = len(re.findall(r'<img\b', open(sys.argv[2]).read()))
else:
    npics = sum(len(pg.images) for pg in pdfplumber.open(sys.argv[2]).pages)
print('pictures in original:', opics, ' in rebuild:', npics)
if npics < opics:
    print('WARNING pictures: the rebuild has %d fewer picture(s) than the original. Find what is missing before '
          'you deliver it.' % (opics - npics))
norm = lambda t: [re.sub(r'[^a-z0-9]', '', w.lower()) for w in re.split(r'[\s—–/]+', t)]
O = collections.Counter(w for w in norm(otext) if w)
N = collections.Counter(w for w in norm(ntext) if w)
print('original words:', sum(O.values()), ' rebuilt words:', sum(N.values()))
miss = O - N
extra = N - O
print('in original, missing from rebuild (%d):' % sum(miss.values()), sorted(miss.items(), key=lambda kv: -kv[1])[:60])
for i in blank:   # a scanned or picture-only page: its words in the rebuild have nothing to match
    print('page %d has no text to compare (a scan or picture): check its words in the rebuild by eye' % i)
if blank:
    print('in rebuild, not in the original\'s text (%d; mostly from the page(s) above, so not counted as added):'
          % sum(extra.values()), sorted(extra.items(), key=lambda kv: -kv[1])[:40])
else:
    print('added in rebuild (%d):' % sum(extra.values()), sorted(extra.items(), key=lambda kv: -kv[1])[:40])
