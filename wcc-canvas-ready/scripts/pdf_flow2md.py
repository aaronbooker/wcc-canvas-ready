"""Untagged single-column PDF (a web article saved as PDF, a printed report) -> Markdown for md2docx.js.
Usage: python3 pdf_flow2md.py in.pdf out.md [--drop "regex"]...
Learned at WCC (Nov 2026): a browser "print to PDF" of an article with no tags scored 0%; there is no source file,
so it is rebuilt: text -> Markdown -> Word -> tagged PDF.
- body size = the most common font size; lines in a larger or bold-only-larger font become headings
  (largest size -> #, next -> ##, bold lines at body size that stand alone -> ###)
- lines are joined into paragraphs; a paragraph ends at a vertical gap bigger than the line spacing
- bold / italic runs inside a paragraph keep **bold** / *italic*
- lines that repeat on most pages (running heads, URLs, "3/11" page counters) and lone page numbers are dropped;
  pass --drop "regex" to drop more (e.g. site navigation like "Get updates")
- every page with images gets an "!img" line for the instructor (figures need alt text from a person)
Check the result against the page images before building: this is a draft, not a final file.
"""
import sys, re, collections, statistics
import pdfplumber
src, dst = sys.argv[1], sys.argv[2]
drops = [re.compile(sys.argv[i + 1]) for i, a in enumerate(sys.argv) if a == '--drop']
pl = pdfplumber.open(src)

def style(fn):
    fn = fn.split('+')[-1]
    return ('Bold' in fn or 'Black' in fn or 'Heavy' in fn, 'Italic' in fn or 'Oblique' in fn)

lines = []          # (page, top, bottom, size, allbold, text-with-markup, plain)
for pi, pg in enumerate(pl.pages):
    rows = collections.defaultdict(list)
    for ch in pg.chars:
        if ch['text'] == '\x00': continue
        rows[round(ch['top'] / 2)].append(ch)
    for k in sorted(rows):
        cs = sorted(rows[k], key=lambda c: c['x0'])
        out, plain, cur, bolds = '', '', None, []
        prev = None
        for c in cs:
            if prev is not None and c['x0'] - prev['x1'] > c['size'] * 0.25 and not plain.endswith(' '):
                out += ' '; plain += ' '
            b, it = style(c['fontname'])
            mk = ('**' if b else '') + ('*' if it else '')
            if mk != cur:
                if cur: out += cur[::-1]
                out += mk; cur = mk
            out += c['text']; plain += c['text']; bolds.append(b); prev = c
        if cur: out += cur[::-1]
        size = statistics.mode(round(c['size'], 1) for c in cs)
        lines.append([pi, min(c['top'] for c in cs), max(c['bottom'] for c in cs), size, all(bolds), out.strip(), plain.strip()])

# drop running heads / footers: same text (digits ignored) on more than half the pages
norm = lambda s: re.sub(r'\d+', '#', s.strip().lower())
pages_with = collections.defaultdict(set)
for l in lines: pages_with[norm(l[6])].add(l[0])
n = len(pl.pages)
keep = []
for l in lines:
    t = l[6]
    if n > 2 and len(pages_with[norm(t)]) > n / 2: continue
    if re.fullmatch(r'(page\s*)?\d+(\s*(/|of)\s*\d+)?', t, re.I): continue
    if any(d.search(t) for d in drops): continue
    keep.append(l)

body = statistics.mode(l[3] for l in keep)
bigger = sorted({l[3] for l in keep if l[3] > body + 0.5}, reverse=True)
lvl = {s: min(i + 1, 3) for i, s in enumerate(bigger)}
md, para, last = [], [], None
def flush():
    if para: md.append(' '.join(para).replace('** **', ' ').replace('* *', ' ') + '\n')
    para.clear()
for l in keep:
    pi, top, bot, size, allbold, txt, plain = l
    gap = (top - last[2]) if last and last[0] == pi else 99
    if size in lvl or (allbold and len(plain) < 120 and gap > size * 0.6 and not plain.endswith(('.', ','))):
        flush()
        h = lvl.get(size, 3 if not md or True else 3)
        md.append('#' * h + ' ' + plain + '\n'); last = l; continue
    if gap > size * 0.9: flush()
    if para and para[-1].endswith('-') and plain[:1].islower():
        para[-1] = para[-1][:-1] + txt
    else:
        para.append(txt)
    last = l
flush()
for pi, pg in enumerate(pl.pages):
    if pg.images:
        md.append(f'!img page {pi + 1}: {len(pg.images)} picture(s) -- crop, add, and write alt text (or mark decorative)\n')
open(dst, 'w').write('\n'.join(md))
print(f'{len(md)} blocks, body {body} pt, heading sizes {bigger}, dropped {len(lines) - len(keep)} repeated/page-number lines')
