"""Split a long HTML page (a Canvas page or syllabus) into parts under Panorama's 3000-word limit. H5 [Panorama
"The content is longer than 3000 words" (Minor)]. Learned at WCC (Nov 2026): a 3,839-word syllabus page held at
70% on this flag alone once everything else passed.

  python3 html_split.py page.html                 # word count per top-level block and the planned split
  python3 html_split.py page.html out_prefix      # writes out_prefix_part1.html, out_prefix_part2.html, ...
  [--max 2800]

Cuts only between top-level blocks, right before a Heading 2, so no section is broken. Each part repeats the page
banner (the first <header>) with "(Part N of M)" added to its Heading 1, keeps the skip link, and ends with a plain
line naming what the next part covers. Quick-navigation links to sections that moved to another part become plain
text (a link to a missing anchor goes nowhere). In Canvas, link the parts to each other as Canvas pages once they
exist; this tool doesn't guess their addresses. Ask the instructor before splitting: the page will be in two places.
"""
import sys, re, copy
from bs4 import BeautifulSoup

src = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
MAX = int(sys.argv[sys.argv.index('--max') + 1]) if '--max' in sys.argv else 2800
raw = open(src, encoding='utf-8').read()
soup = BeautifulSoup(raw, 'html.parser')
body = soup.body or soup
# the root: the single element that holds the page (Canvas pages are one wrapping <div>)
kids = [k for k in body.find_all(recursive=False)]
root = kids[0] if len(kids) == 1 else body
blocks = root.find_all(recursive=False)
words = lambda el: len(re.findall(r"[A-Za-z0-9’']+", el.get_text(' ')))
total = sum(words(b) for b in blocks)

# preamble: everything before the first top-level h2 (skip link, banner, quick navigation)
first_h2 = next((i for i, b in enumerate(blocks) if b.name == 'h2'), len(blocks))
pre, rest = blocks[:first_h2], blocks[first_h2:]
pre_w = sum(words(b) for b in pre)
# sections start at each top-level h2
sections, cur = [], []
for b in rest:
    if b.name == 'h2' and cur: sections.append(cur); cur = []
    cur.append(b)
if cur: sections.append(cur)
sw = [sum(words(b) for b in s) for s in sections]
n = max(1, -(-(total) // MAX))
while True:                                     # balanced greedy: aim for total/n per part
    target = sum(sw) / n; parts, acc = [[]], 0
    for s, w in zip(sections, sw):
        if parts[-1] and acc + w > target * 1.08 and len(parts) < n: parts.append([]); acc = 0
        parts[-1].append(s); acc += w
    sizes = [pre_w + sum(sw[sections.index(s)] for s in p) for p in parts]
    if max(sizes) <= MAX or n > 10: break
    n += 1
title = lambda s: s[0].get_text(' ', strip=True) if s[0].name == 'h2' else ''
print(f'{src}: {total} words; preamble {pre_w}; {len(sections)} sections; {len(parts)} parts:',
      ', '.join(f'part {i+1} {z} words (starts "{title(p[0])}")' for i, (p, z) in enumerate(zip(parts, sizes))))
if not out or len(parts) == 1: sys.exit()

for i, p in enumerate(parts, 1):
    new = BeautifulSoup('', 'html.parser')
    wrap = new.new_tag(root.name if root is not body else 'div', **({k: v for k, v in root.attrs.items()} if root is not body else {}))
    ids = set()
    for s in p:
        for b in s:
            for el in [b] + b.find_all(True):
                if el.get('id'): ids.add(el['id'])
    for b in pre:
        c = copy.copy(b); wrap.append(c)
    h1 = wrap.find('h1')
    if h1: h1.append(f' (Part {i} of {len(parts)})')
    for s in p:
        for b in s: wrap.append(copy.copy(b))
    for a in wrap.find_all('a', href=True):
        h = a['href']
        if h.startswith('#') and len(h) > 1 and h[1:] not in ids and h[1:] != 'main-content':
            a.name = 'span'; del a['href']
            if a.get('title'): del a['title']
    if i < len(parts):
        nxt = ', '.join(title(s) for s in parts[i] if title(s))
        note = new.new_tag('p', style='margin-top:24px;font-weight:bold;')
        note.string = f'Continued in Part {i + 1} of {len(parts)}: {nxt}.'
        wrap.append(note)
    new.append(wrap)
    open(f'{out}_part{i}.html', 'w', encoding='utf-8').write(str(new))
    print(f'wrote {out}_part{i}.html ({words(wrap)} words)')
