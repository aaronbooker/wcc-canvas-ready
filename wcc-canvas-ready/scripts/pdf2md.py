"""Extract a multi-column textbook PDF into a simple tagged markdown file.

Usage: python3 pdf2md.py input.pdf layout.json out.md

layout.json:
{
  "even": {"body": [x0,x1], "margin": [x0,x1]},      # column x-ranges for even PDF pages
  "odd":  {"body": [x0,x1], "margin": [x0,x1]},
  "top": 45, "bottom": 640,                            # drop running heads / footers
  "headings": [[font_substring, size, level], ...],    # e.g. ["BellGothicStd-Black",13,2]
  "body_font": "Sabon", "body_size": 10,
  "pages": {"5": {"skip": [[x0,top,x1,bottom], ...], "marker_after": "FIG2_1"}, ...},
  "manual_pages": [1, 22, 23],                         # pages handled by hand
  "symbol_map": {"MathematicalPi": {"j": ":"}}
}
Output markdown: '#'-headings, paragraphs, *italic*, **bold**, ^sup^,
'> [margin] text' margin notes, '<<MARKER>>' placeholders for hand-built blocks.
"""
import json, re, sys
import pdfplumber
from wordfreq import zipf_frequency as zf

L = {'symbol_map': {}, 'headings': [], 'body_size': 10}
HYPH = {}

def fontkind(fn):
    fn = fn.split('+')[-1]
    it = 'Italic' in fn or 'Oblique' in fn
    bd = any(k in fn for k in ('Bold', 'Black'))
    return it, bd

def get_words(pg):
    ws = pg.extract_words(extra_attrs=['fontname', 'size'], x_tolerance=1.5)
    out = []
    for w in ws:
        fn = w['fontname']
        if 'HiddenHorzOCR' in fn:
            continue
        for k, mp in L.get('symbol_map', {}).items():
            if k in fn:
                w['text'] = ''.join(mp.get(c, c) for c in w['text'])
        out.append(w)
    return out

def in_box(w, b):
    return w['x0'] >= b[0] - 1 and w['x1'] <= b[2] + 1 and w['top'] >= b[1] - 1 and w['bottom'] <= b[3] + 1

def group_lines(ws):
    ws = sorted(ws, key=lambda w: (w['top'], w['x0']))
    lines = []
    for w in ws:
        # same line if vertically overlapping the line's baseline zone
        for ln in lines[-3:]:
            dropcap = w['size'] > 25 and len(w['text']) <= 2 and abs(ln['top'] - w['top']) < 15
            sup = w['size'] < 7 and ln['top'] - 5 <= w['top'] and w['bottom'] <= ln['bottom'] + 1
            if abs(ln['bottom'] - w['bottom']) < 3.5 or sup or dropcap:
                ln['words'].append(w)
                break
        else:
            lines.append({'top': w['top'], 'bottom': w['bottom'], 'words': [w]})
    # merge lines made only of a drop cap or superscripts into the line they belong to
    merged = []
    for ln in lines:
        only_big = all(w['size'] > 25 for w in ln['words'])
        only_sup = all(w['size'] < 7 for w in ln['words'])
        if only_big or only_sup:
            tgt = [o for o in lines if o is not ln and not all(w['size'] > 25 or w['size'] < 7 for w in o['words'])
                   and 0 <= o['top'] - ln['top'] < (15 if only_big else 6) + 0.1 * 0
                   and o['words'][0]['x0'] <= ln['words'][-1]['x1'] + 400]
            tgt = [o for o in tgt if (only_big and o['words'][0]['x0'] > ln['words'][0]['x0']) or
                   (only_sup and o['words'][0]['x0'] - 5 <= ln['words'][0]['x0'] <= o['words'][-1]['x1'] + 5)]
            if tgt:
                tgt[0]['words'].extend(ln['words']); continue
        merged.append(ln)
    lines = merged
    for ln in lines:
        ln['words'].sort(key=lambda w: w['x0'])
        ln['x0'] = ln['words'][0]['x0']; ln['x1'] = ln['words'][-1]['x1']
        big = [w for w in ln['words'] if 7 <= w['size'] <= 25]
        ln['size'] = max((w['size'] for w in big), default=ln['words'][0]['size'])
        ln['font'] = (big or ln['words'])[0]['fontname'].split('+')[-1]
    return lines

def fmt_words(words, body_size):
    """Render words with inline markup; merge drop caps and split ligatures."""
    toks = []
    normal = sorted(w['bottom'] for w in words if w['size'] >= body_size * 0.75)
    ref = normal[len(normal) // 2] if normal else None
    for w in words:
        t = w['text']
        it, bd = fontkind(w['fontname'])
        small = w['size'] < body_size * 0.75 and re.fullmatch(r'[\d*†‡]+', t)
        sub = bool(small) and ref is not None and w['bottom'] >= ref - 0.5
        toks.append({'t': t, 'it': it, 'bd': bd, 'sup': bool(small), 'sub': sub, 'size': w['size'], 'x0': w['x0'], 'x1': w['x1']})
    merged = []
    for tk in toks:
        if merged:
            prev = merged[-1]
            dropcap = prev['size'] > body_size * 2.5 and len(prev['t']) == 1
            lig = re.fullmatch(r'(Th|th|f|ff|fi|fl|ffi|ffl)', prev['t']) and re.match(r'[a-z]', tk['t']) \
                and zf(prev['t'] + tk['t'].strip('.,;:!?)”’'), 'en') > zf(tk['t'].strip('.,;:!?)”’'), 'en')
            touching = tk['x0'] - prev['x1'] < 0.8 and not re.search(r'[,;:.)!?”]$', prev['t'])
            if dropcap or lig or tk['sup'] or (touching and prev['it'] == tk['it'] and prev['bd'] == tk['bd']):
                if tk['sup']:
                    mark = '~' if tk['sub'] else '^'
                    prev['t'] += mark + tk['t'] + mark
                else:
                    prev['t'] += tk['t']
                prev['size'] = tk['size'] if dropcap else prev['size']
                prev['x1'] = tk['x1']
                continue
        merged.append(dict(tk))
    return merged

def render(toks):
    out = []
    i = 0
    gaps = []
    while i < len(toks):
        tk = toks[i]
        j = i
        while j + 1 < len(toks) and toks[j + 1]['it'] == tk['it'] and toks[j + 1]['bd'] == tk['bd']:
            j += 1
        s = ' '.join(t['t'] for t in toks[i:j + 1])
        if tk['bd'] and tk['it']:
            s = f'***{s}***'
        elif tk['bd']:
            s = f'**{s}**'
        elif tk['it']:
            s = f'*{s}*'
        out.append(s)
        gaps.append(i > 0 and toks[i]['x0'] - toks[i - 1]['x1'] < 1.0)
        i = j + 1
    r = ''
    for k, (o, tight) in enumerate(zip(out, gaps)):
        r += ('' if k == 0 or tight else ' ') + o
    return r

def join_hyphen(a, b):
    """Join line a ending in a hyphen with line b."""
    m = re.search(r'([A-Za-z]+)-$', a)
    n = re.match(r'([A-Za-z]+)', b)
    if not m or not n:
        return a + ' ' + b
    whole = m.group(1) + n.group(1)
    keep = m.group(1) + '-' + n.group(1)
    if HYPH.get(keep.lower(), 0) > HYPH.get(whole.lower(), 0) or (zf(whole, 'en') == 0 and zf(m.group(1), 'en') > 2 and zf(n.group(1), 'en') > 2):
        return a + b
    return a[:-1] + b

def heading_level(ln):
    for f, s, lev in L['headings']:
        if f in ln['font'] and abs(ln['size'] - s) < 0.3:
            return lev
    return None

def clean(t):
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'(?<!\*)\* \*(?!\*)', ' ', t)          # *a* *b* -> *a b*
    t = re.sub(r'\*\* \*\*', ' ', t)                    # **a** **b** -> **a b**
    t = re.sub(r'^\S*-\[\s*', '', t)                      # icon debris like <i>-[
    t = re.sub(r'\s+([.,;:])', r'\1', t)
    t = re.sub(r'([—–]) (?=[a-z])', r'\1', t)
    def dehy(m):
        whole = m.group(1) + m.group(2)
        return whole if zf(re.sub(r'\W', '', whole), 'en') > 0 else m.group(0)
    t = re.sub(r'([A-Za-z]+)- ([a-z]+)', dehy, t)
    t = re.sub(r'([A-Za-z]+)-(\*+) (\*+)([a-z]+)', lambda m: m.group(1) + m.group(4) + m.group(2) if zf(m.group(1)+m.group(4),'en')>0 else m.group(0), t)
    return t

def main():
    global L, HYPH, para
    pdf_path, layout_path, out_path = sys.argv[1:4]
    L.update(json.load(open(layout_path)))
    pdf = pdfplumber.open(pdf_path)
    # Pass 1: collect all words for hyphenation evidence
    alltext = ' '.join(w['text'] for pg in pdf.pages for w in get_words(pg))
    HYPH = {}
    for tok in re.findall(r"[A-Za-z]+-?[A-Za-z]+", alltext):
        HYPH[tok.lower()] = HYPH.get(tok.lower(), 0) + 1

    blocks = []          # ('h', level, text) | ('p', text) | ('m', text) | ('marker', name) | ('note', text)
    para = None          # current paragraph text
    pending = []         # floats to emit at next paragraph boundary
    body_size = L['body_size']

    para_kind = ['p', 0]

    def flush():
        global para
        if para is not None:
            blocks.append((para_kind[0], para)); para = None; para_kind[0] = 'p'
        while pending:
            blocks.append(pending.pop(0))

    for pno, pg in enumerate(pdf.pages, 1):
        pc = L.get('pages', {}).get(str(pno), {})
        if pno in L.get('manual_pages', []):
            flush(); blocks.append(('marker', f'PAGE{pno}')); continue
        side = 'even' if pno % 2 == 0 else 'odd'
        bx, mx = L[side]['body'], L[side]['margin']
        ws = [w for w in get_words(pg) if L['top'] <= w['top'] and w['bottom'] <= L['bottom']]
        ws = [w for w in ws if not any(in_box(w, b) for b in pc.get('skip', []))]
        body = [w for w in ws if bx[0] <= w['x0'] and w['x1'] <= bx[1] + 3]
        marg = [w for w in ws if mx[0] <= w['x0'] and w['x1'] <= mx[1] + 3 and w not in body]
        if pc.get('marker_before'):
            flush(); blocks.append(('marker', pc['marker_before']))
        # margin notes: split on vertical gaps, or where a bold term starts after plain text
        mlines = group_lines(marg)
        notes, cur, last = [], [], None
        for ln in mlines:
            starts_term = fontkind(ln['words'][0]['fontname'])[1] and ln['words'][0]['size'] >= 7.5 and cur and not fontkind(cur[-1]['words'][-1]['fontname'])[1]
            icon = re.match(r'[<✓]', ln['words'][0]['text'])
            if last is not None and (ln['top'] - last > 16 or starts_term or icon):
                notes.append(cur); cur = []
            cur.append(ln); last = ln['bottom']
        if cur: notes.append(cur)
        margin_blocks = []
        for nt in notes:
            txt = ''
            for ln in nt:
                s = render(fmt_words(ln['words'], body_size))
                txt = join_hyphen(txt, s) if txt.endswith('-') else (txt + ' ' + s if txt else s)
            margin_blocks.append((nt[0]['top'], ('m', txt.strip())))
        blines = group_lines(body)
        if not blines:
            flush(); blocks.extend(b for _, b in margin_blocks); margin_blocks = []
        col_left = min((ln['x0'] for ln in blines if ln['size'] == body_size), default=bx[0])
        col_right = max((ln['x1'] for ln in blines if ln['size'] == body_size), default=bx[1])
        prev = None
        mi = 0
        for ln in blines:
            while mi < len(margin_blocks) and margin_blocks[mi][0] <= ln['top']:
                pending.append(margin_blocks[mi][1]); mi += 1
            first = ln['words'][0]
            bullet = 'MathematicalPi' in first['fontname'] or first['text'] in ('■', '•')
            words = ln['words'][1:] if bullet else ln['words']
            s = render(fmt_words(words, body_size))
            lev = heading_level(ln)
            if lev:
                if prev is not None and prev.get('lev') == lev and ln['top'] - prev['bottom'] < 6:
                    h = blocks[-1]; blocks[-1] = ('h', lev, h[2] + ' ' + s.strip('*'))
                else:
                    flush(); blocks.append(('h', lev, s.strip('*')))
                ln['lev'] = lev; prev = ln; continue
            if ln['size'] < body_size - 1.5 and ln['top'] > 540:          # footnote
                if para_kind[0] == 'note' and para is not None:
                    para = para + ' ' + s
                else:
                    flush(); para = s; para_kind[0] = 'note'
                prev = ln; continue
            if bullet:
                flush(); para = s; para_kind[0] = 'li'; para_kind[1] = words[0]['x0'] if words else ln['x0']
                prev = ln; continue
            if para_kind[0] == 'li' and para is not None and abs(ln['x0'] - para_kind[1]) < 4:
                para = join_hyphen(para, s) if para.endswith('-') else para + ' ' + s
                prev = ln; continue
            indent = ln['x0'] - col_left
            prev_short = prev is not None and prev['x1'] < col_right - 15
            new = (para is None or para_kind[0] != 'p' or 10 < indent < 25 or prev_short
                   or (prev is not None and ln['top'] - prev['bottom'] > 9))
            cont_page = para is not None and prev is None and ln['x0'] - col_left <= 10 and para_kind[0] == 'p'
            if new and not cont_page:
                flush(); para = s; para_kind[0] = 'p'
            else:
                para = join_hyphen(para, s) if para.endswith('-') else para + ' ' + s
            prev = ln
        for _, b in margin_blocks[mi:]:
            pending.append(b)
        if pc.get('marker_after'):
            pending.append(('marker', pc['marker_after']))
    flush()

    with open(out_path, 'w') as f:
        for b in blocks:
            if b[0] == 'h': f.write('#' * b[1] + ' ' + clean(b[2]) + '\n\n')
            elif b[0] == 'p': f.write(clean(b[1]) + '\n\n')
            elif b[0] == 'li': f.write('- ' + clean(b[1]) + '\n\n')
            elif b[0] == 'note': f.write('> [note] ' + clean(b[1]) + '\n\n')
            elif b[0] == 'm': f.write('> [margin] ' + clean(b[1]) + '\n\n')
            elif b[0] == 'marker': f.write(f'<<{b[1]}>>\n\n')
    print('blocks', len(blocks))


if __name__ == '__main__':
    main()
