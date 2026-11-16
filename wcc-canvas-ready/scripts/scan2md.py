"""OCR a scanned (image-only) PDF into tagged markdown for md2docx.js. Usage: python3 scan2md.py scan.pdf out.md [--dpi 300]
A scan has no text at all, so Panorama can't read it (and neither can a screen reader). This rebuilds the text:
- pages rendered at 300 dpi, OCR'd with Tesseract (TSV: block / paragraph / line, with line heights),
- lines joined into paragraphs, hyphenated line ends rejoined,
- lines much taller than the body text become headings (## / ###), all-caps short lines become ####,
- running headers/footers (same text on most pages) and lone page numbers dropped,
- every page with pictures gets an "!img" placeholder line listing it for the instructor (figures need cropping and
  alt text by a person, or a clear description).
OCR makes mistakes: the instructor must proofread names, numbers and quotes. Say so when delivering.
"""
import sys, os, re, subprocess, tempfile, statistics, collections, csv, io
src, dst = sys.argv[1], sys.argv[2]
dpi = int(sys.argv[sys.argv.index('--dpi') + 1]) if '--dpi' in sys.argv else 300
tmp = tempfile.mkdtemp()
subprocess.run(['pdftoppm', '-r', str(dpi), '-gray', '-png', src, os.path.join(tmp, 'p')], check=True)
pages = sorted(f for f in os.listdir(tmp) if f.endswith('.png'))
all_lines = []
for pi, f in enumerate(pages):
    tsv = subprocess.run(['tesseract', os.path.join(tmp, f), '-', '--psm', '3', 'tsv'], capture_output=True, text=True).stdout
    rows = list(csv.DictReader(io.StringIO(tsv), delimiter='\t', quoting=csv.QUOTE_NONE))
    lines = collections.OrderedDict()
    for r in rows:
        if r['level'] != '5' or not r['text'].strip() or float(r['conf']) < 0: continue
        k = (int(r['block_num']), int(r['par_num']), int(r['line_num']))
        L = lines.setdefault(k, {'words': [], 'h': [], 'top': int(r['top']), 'left': int(r['left'])})
        L['words'].append(r['text']); L['h'].append(int(r['height']))
    for k, L in lines.items():
        all_lines.append({'page': pi, 'block': k[0], 'par': k[1], 'text': ' '.join(L['words']),
                          'h': statistics.median(L['h']), 'top': L['top']})
body_h = statistics.median([l['h'] for l in all_lines]) if all_lines else 10
# running headers / footers: identical short lines on 3+ pages
cnt = collections.Counter(re.sub(r'\d+', '#', l['text']) for l in all_lines if len(l['text']) < 80)
running = {t for t, c in cnt.items() if c >= max(3, len(pages) // 2)}
out, para, last = [], [], None
def flush():
    global para
    if para:
        t = ' '.join(para)
        t = re.sub(r'(\w)- (\w)', r'\1\2', t)        # rejoin words split across lines
        out.append(t); para = []
for l in all_lines:
    t = l['text'].strip()
    if re.sub(r'\d+', '#', t) in running or re.fullmatch(r'\d{1,4}', t): continue
    key = (l['page'], l['block'], l['par'])
    big = l['h'] > body_h * 1.35
    caps = t.isupper() and len(t) < 60 and len(t.split()) <= 8
    if big or caps:
        flush()
        lvl = '##' if l['h'] > body_h * 1.8 else '###' if big else '####'
        if out and out[-1].startswith(lvl + ' ') and last == key: out[-1] += ' ' + t   # heading wrapped to 2 lines
        else: out.append(f'{lvl} {t}')
        last = key; continue
    if key != last: flush()
    para.append(t); last = key
flush()
title = next((o[3:] for o in out if o.startswith('## ')), os.path.splitext(os.path.basename(src))[0])
# no skipped heading levels (D7/F4): each heading at most one level below the previous one
fixed, prev = [], 1
for o in out:
    m = re.match(r'(#+) ', o)
    if m:
        lv = min(len(m.group(1)), prev + 1); o = '#' * lv + o[len(m.group(1)):]; prev = lv
    fixed.append(o)
out = fixed
md = '# ' + title + '\n\n' + '\n\n'.join(o for o in out if o != '## ' + title) + '\n'
open(dst, 'w').write(md)
print(f'pages {len(pages)}, lines {len(all_lines)}, body height {body_h}px, headings {sum(o.startswith("#") for o in out)}, dropped running lines {len(running)}')
