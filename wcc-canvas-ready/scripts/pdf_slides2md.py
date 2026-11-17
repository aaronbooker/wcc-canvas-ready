"""A slide deck saved as an untagged PDF (Keynote/PowerPoint "Save as PDF" on a Mac, Quartz) -> Markdown for md2docx.js.
One section per slide. Learned Nov 17, 2026: the one-column rebuild (pdf_flow2md.py) gave a 35-slide deck 12 heading levels
and no slide breaks.
Usage: python3 pdf_slides2md.py in.pdf out.md "Deck title" [imgs.json]
imgs.json: {"<page>": [["file.png", "alt text"], ...]} pictures to place after that slide's text (YOU choose and write alt).
Per page: the largest text is the slide title (## ), the rest is grouped into paragraphs by vertical gaps; a line that
starts with a bullet becomes a list item. Lines that repeat on more than half the pages (footers) are dropped.
"""
import sys, re, json, collections, statistics
import pdfplumber
src, dst, title = sys.argv[1:4]
imgs = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else {}
pl = pdfplumber.open(src)
pages = []
for pg in pl.pages:
    words = pg.extract_words(extra_attrs=['size'], keep_blank_chars=False, use_text_flow=True)
    rows = collections.defaultdict(list)
    for w in words: rows[round(w['top'] / 3)].append(w)
    lines = []
    for k in sorted(rows):
        ws = sorted(rows[k], key=lambda w: w['x0'])
        lines.append((min(w['top'] for w in ws), max(w['bottom'] for w in ws), max(w['size'] for w in ws), ' '.join(w['text'] for w in ws)))
    pages.append(lines)
norm = lambda s: re.sub(r'\d+', '#', s.strip().lower())
count = collections.Counter(norm(l[3]) for lines in pages for l in {x[3]: x for x in lines}.values())
md = [f'# {title}\n']
for i, lines in enumerate(pages):
    lines = [l for l in lines if count[norm(l[3])] <= len(pages) / 2 and not re.fullmatch(r'\d{1,3}', l[3].strip())]
    if not lines:
        head = f'Slide {i + 1}'
        md.append(f'## {head}\n')
    else:
        big = max(l[2] for l in lines)
        tl = [l for l in lines if l[2] >= big - 0.5]
        head = ' '.join(l[3] for l in tl)
        md.append(f'## {head}\n')
        rest = [l for l in lines if l not in tl]
        para, last = [], None
        def flush():
            if para: md.append(' '.join(para) + '\n'); para.clear()
        for l in rest:
            t = l[3].strip()
            if re.match(r'[•·▪◦‣–*-]\s', t): flush(); para.append('- ' + t[2:].strip()); last = l; continue
            if last is not None and l[0] - last[1] > l[2] * 0.8: flush()
            para.append(t); last = l
        flush()
    for f, alt in imgs.get(str(i + 1), []):
        md.append(f'!img {f} | {alt}\n')
open(dst, 'w').write('\n'.join(md))
print(f'{len(pages)} slides -> {dst}')
