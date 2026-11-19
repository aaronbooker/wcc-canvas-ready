"""Find words that are in a PDF page's IMAGE but not in its text layer (and text-layer words that look misread).

Usage: python3 -I ocr_gaps.py in.pdf [pages like 1,3-5] [--dpi 300] [--conf 70]

Why: a PDF run through OCR (Acrobat "Paper Capture" and the like) can leave a word it could not recognize as a
picture of that word, with no text behind it. The page looks complete, but the text layer, and so any rebuild made
from it, silently lacks the word, and content_check.py can't see it, because it compares against the same text layer.
(Nov 18, 2026, three textbook chapters: no such gap was found; the hits were map labels and italic first capitals.) This OCRs each page with
Tesseract and, by POSITION, lists OCR words that no text-layer word covers ([[word]]), and text-layer words that
look misread ({{ocr ≠ layer "text"}}). Text inside photos and maps shows up too; skip those by eye.
Needs pdfplumber, Pillow, wordfreq and the tesseract program. Uses PyMuPDF and pytesseract when they are there, and
falls back to pdfplumber's renderer and the tesseract command line when they aren't (Claude's sandbox may lack them).
"""
import sys, re, io, csv, shutil, subprocess
import pdfplumber
from PIL import Image
from wordfreq import zipf_frequency as zf
try:
    import fitz
except ImportError:
    fitz = None
try:
    import pytesseract
except ImportError:
    pytesseract = None
if not pytesseract and not shutil.which('tesseract'):
    print('ocr_gaps: the tesseract program is not installed here, so the page images could not be checked. '
          'Look at the pages yourself, or install it (apt-get install tesseract-ocr).')
    sys.exit(0)


def render(pno):
    if fitz:
        pix = DOC[pno - 1].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
        return Image.open(io.BytesIO(pix.tobytes('png')))
    return pdf.pages[pno - 1].to_image(resolution=DPI).original.convert('L')   # offset is measured below


def ocr(img):
    if pytesseract:
        return pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config='--psm 3')
    buf = io.BytesIO(); img.save(buf, 'PNG')
    tsv = subprocess.run(['tesseract', 'stdin', 'stdout', '--psm', '3', 'tsv'], input=buf.getvalue(),
                         capture_output=True).stdout.decode('utf8', 'replace')
    d = {k: [] for k in ('text', 'conf', 'left', 'top', 'width', 'height', 'block_num', 'par_num', 'line_num')}
    for r in csv.DictReader(io.StringIO(tsv), delimiter='\t', quoting=csv.QUOTE_NONE):
        for k in d:
            v = r.get(k, '')
            d[k].append(v if k == 'text' else float(v) if k == 'conf' else int(v))
    return d

args = [a for a in sys.argv[1:] if not a.startswith('--')]
opt = lambda k, d: type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
DPI, CONF = opt('--dpi', 300), opt('--conf', 70)
src = args[0]
pdf = pdfplumber.open(src)
DOC = fitz.open(src) if fitz else None
pages = list(range(1, len(pdf.pages) + 1))
if len(args) > 1 and re.fullmatch(r'[\d,-]+', args[1]):
    pages = []
    for part in args[1].split(','):
        a, _, b = part.partition('-')
        pages += range(int(a), int(b or a) + 1)
norm = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
total = 0
for pno in pages:
    pg = pdf.pages[pno - 1]
    tw = pg.extract_words(x_tolerance=1.5)
    d = ocr(render(pno))
    k = 72.0 / DPI
    # The rendered page and the text layer can disagree by an offset (crop box vs media box, scan shift):
    # measure it from words that appear once in both and agree, and move the OCR boxes by the median.
    once = {}
    for w in tw:
        once.setdefault(norm(w['text']), []).append(w)
    dxs, dys = [], []
    ocr_n = [norm(t) for t in d['text']]
    for i, n in enumerate(ocr_n):
        if len(n) >= 5 and ocr_n.count(n) == 1 and len(once.get(n, [])) == 1:
            w = once[n][0]
            dxs.append(w['x0'] - d['left'][i] * k); dys.append(w['top'] - d['top'][i] * k)
    med = lambda v: sorted(v)[len(v) // 2] if v else 0.0
    DX, DY = med(dxs), med(dys)
    lines = {}
    for i, t in enumerate(d['text']):
        t = (t or '').strip()
        if not t or float(d['conf'][i]) < 0:
            continue
        x0, y0 = d['left'][i] * k + DX, d['top'][i] * k + DY
        x1, y1 = x0 + d['width'][i] * k, y0 + d['height'][i] * k
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        hit = [w for w in tw if w['x0'] - 1 <= cx <= w['x1'] + 1 and w['top'] - 2 <= cy <= w['bottom'] + 2]
        key = (d['block_num'][i], d['par_num'][i], d['line_num'][i])
        L = lines.setdefault(key, {'y': y0, 'x': x0, 'toks': []})
        flag, n = None, norm(t)
        if not hit and len(n) >= 2 and float(d['conf'][i]) >= CONF and (zf(n, 'en') > 0 or n.isdigit() or t[:1].isupper()):
            flag = 'gap'
        elif hit and len(n) >= 4 and float(d['conf'][i]) >= 85:
            have = norm(' '.join(w['text'] for w in hit))
            # a bold, colored or italic first capital is often its own word in the text layer ("I" + "nternational");
            # the rebuild joins them, so it isn't a misread when that letter sits just left of the rest
            split_cap = n.endswith(have) and len(n) - len(have) == 1 and any(
                norm(w['text']) == n[0] and -1 <= hit[0]['x0'] - w['x1'] < 6 and abs(w['bottom'] - hit[0]['bottom']) < 4 for w in tw)
            if n not in have and zf(n, 'en') > 2 and zf(have, 'en') == 0 and not split_cap:
                flag = 'diff:' + ' '.join(w['text'] for w in hit)
        L['toks'].append((t, flag))
    for key, L in sorted(lines.items(), key=lambda kv: (kv[1]['y'], kv[1]['x'])):
        if not any(f for _, f in L['toks']):
            continue
        s = ' '.join(('[[%s]]' % t if f == 'gap' else '{{%s ≠ layer "%s"}}' % (t, f[5:]) if f else t)
                     for t, f in L['toks'])
        total += sum(1 for _, f in L['toks'] if f)
        print('p%d y=%d x=%d: %s' % (pno, L['y'], L['x'], s))
print('flagged words:', total, file=sys.stderr)
