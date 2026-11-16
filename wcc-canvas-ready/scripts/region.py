"""Extract one rectangular region of a PDF page as clean paragraphs.

Usage: python3 region.py input.pdf PAGE x0 top x1 bottom [--gap N] [--lines] [--layout layout.json]
Prints paragraphs (blank-line separated). Lines whose font is bold/black and
all-caps are printed as '#### Heading'. --lines prints raw lines instead.
"""
import sys, re, json
import pdfplumber
sys.path.insert(0, __import__('os').path.dirname(__file__))
import pdf2md as P

def region_paras(pdf, page, bbox, gap=4.5, size=9):
    pg = pdf.pages[page - 1]
    ws = [w for w in P.get_words(pg) if P.in_box(w, bbox)]
    lines = P.group_lines(ws)
    if not lines:
        return []
    left = min(l['x0'] for l in lines)
    right = max(l['x1'] for l in lines)
    out, cur, prev = [], None, None
    for ln in lines:
        s = P.render(P.fmt_words(ln['words'], size))
        plain = re.sub(r'[*^]', '', s)
        is_head = P.fontkind(ln['words'][0]['fontname'])[1] and plain.isupper() and len(plain) < 40
        if is_head:
            if cur: out.append(cur)
            out.append('#### ' + plain.title()); cur = None; prev = ln; continue
        new = (cur is None or (prev is not None and ln['top'] - prev['bottom'] > gap)
               or (prev is not None and prev['x1'] < right - 25 and ln['x0'] <= left + 2 and re.match(r'[\W_]*[A-Z0-9]', plain))
               or 6 < ln['x0'] - left < 20 and prev is not None and prev['x1'] < right - 25)
        if new:
            if cur: out.append(cur)
            cur = s
        else:
            cur = P.join_hyphen(cur, s) if cur.endswith('-') else cur + ' ' + s
        prev = ln
    if cur: out.append(cur)
    return [P.clean(o) for o in out]

if __name__ == '__main__':
    a = sys.argv
    pdf = pdfplumber.open(a[1]); page = int(a[2]); bbox = tuple(map(float, a[3:7]))
    if '--layout' in a:
        P.L.update(json.load(open(a[a.index('--layout') + 1])))
    gap = float(a[a.index('--gap') + 1]) if '--gap' in a else 4.5
    alltext = ' '.join(w['text'] for pg in pdf.pages for w in P.get_words(pg))
    for tok in re.findall(r"[A-Za-z]+-?[A-Za-z]+", alltext):
        P.HYPH[tok.lower()] = P.HYPH.get(tok.lower(), 0) + 1
    if '--lines' in a:
        for l in P.group_lines([w for w in P.get_words(pdf.pages[page-1]) if P.in_box(w, bbox)]):
            print(round(l['top'],1), round(l['x0'],1), P.clean(P.render(P.fmt_words(l['words'], 9))))
    else:
        print('\n\n'.join(region_paras(pdf, page, bbox, gap)))
