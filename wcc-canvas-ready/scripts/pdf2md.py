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
  "symbol_map": {"MathematicalPi": {"j": ":"}},
  "runin": [["BellGothicStd-Black", 10]],             # run-in heads: become headings one level down
  "parity": "pdf",                                     # optional: trust the PDF page number for even/odd
  "media_site": "my[a-z]+lab\\.com"                    # optional: the online-lab notes in the margin
}
Draft "pages" and "manual_pages" with layout_draft.py, then check them against the page images.
Output markdown: '#'-headings, paragraphs, *italic*, **bold**, ^sup^,
'> [margin] text' margin notes, '<<MARKER>>' placeholders for hand-built blocks.
"""
import json, re, sys, unicodedata
import pdfplumber
from wordfreq import zipf_frequency as zf

L = {'symbol_map': {}, 'headings': [], 'body_size': 10}
HYPH = {}

def fontkind(fn):
    fn = fn.split('+')[-1]
    it = 'Italic' in fn or 'Oblique' in fn
    bd = any(k in fn for k in ('Bold', 'Black'))
    return it, bd

INVISIBLE = {}   # page index -> {char: [(x0, x1, top)]} drawn with text render mode 3 (invisible)

def load_invisible(path):
    """Acrobat Paper Capture writes its OCR guesses for icons and map art as invisible text (render mode 3), in
    ordinary font names (Times-Roman, Helvetica) as well as HiddenHorzOCR. Kept, they landed inside sentences as stray
    letters and symbols (a textbook chapter, Nov 18, 2026). pdfplumber can't see the render mode, so
    PyMuPDF lists those characters. Its positions are relative to the crop box and pdfplumber's are media-box points,
    so the crop box origin is added (a first try without it deleted real words next to the icons)."""
    try:
        import fitz
    except ImportError:
        print('note: PyMuPDF (fitz) not installed, so invisible OCR text is not filtered', file=sys.stderr)
        return
    for i, p in enumerate(fitz.open(path)):
        ox, oy = p.cropbox.x0, p.cropbox.y0
        for t in p.get_texttrace():
            if t['type'] == 3:
                for c in t['chars']:
                    INVISIBLE.setdefault(i, {}).setdefault(chr(c[0]), []).append((c[3][0] + ox, c[3][2] + ox, c[3][1] + oy))

def visible(pg):
    inv = INVISIBLE.get(pg.page_number - 1)
    if not inv:
        return pg
    def keep(o):
        if o.get('object_type') != 'char' or o['text'] not in inv:
            return True
        cx = (o['x0'] + o['x1']) / 2
        return not any(x0 - 1 <= cx <= x1 + 1 and abs(o['top'] - top) < 3 for x0, x1, top in inv[o['text']])
    return pg.filter(keep)

def get_words(pg):
    ws = visible(pg).extract_words(extra_attrs=['fontname', 'size'], x_tolerance=1.5)
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
    k, w = HYPH.get(keep.lower(), 0), HYPH.get(whole.lower(), 0)
    if k != w:                                  # the document's own spelling elsewhere decides
        return a + b if k > w else a[:-1] + b
    zw, zm, zn = zf(whole, 'en'), zf(m.group(1), 'en'), zf(n.group(1), 'en')
    # no evidence: keep the hyphen when the joined word is unknown, or rare while both halves are common words
    # ("so-called" became "socalled", Nov 18, 2026: wordfreq lists "socalled" at 1.7)
    if (zw == 0 and zm > 2 and zn > 2) or (zw < 2.0 and min(zm, zn) >= 4.5):
        return a + b
    return a[:-1] + b

def heading_level(ln):
    for f, s, lev in L['headings']:
        if f in ln['font'] and abs(ln['size'] - s) < 0.3:
            return lev
    return None

SPACING_MARKS = {'\u00b4': '\u0301', '\u02c7': '\u030c', '\u00a8': '\u0308', '\u02dc': '\u0303'}

def fix_accents(t):
    """A letter followed by a spacing accent ("c´") is one accented letter ("ć").
    Some typeset PDFs draw the accent as its own glyph after the letter (a textbook, Nov 18, 2026)."""
    return unicodedata.normalize('NFC', re.sub('([A-Za-z])([%s])' % ''.join(SPACING_MARKS),
                                               lambda m: m.group(1) + SPACING_MARKS[m.group(2)], t))

def page_sides(pdf):
    """'even'/'odd' layout for each page. The PDF page number's parity is only a guess: a chapter whose first PDF
    page is an odd book page has its left and right pages the other way round from one whose first page is even
    (two chapters of the same textbook, Nov 18, 2026). Body-font words that fit only one layout's body column
    decide each page; pages with too little body text (maps, photos, review pages) follow the chapter's majority.
    "parity": "pdf" in layout.json turns this off."""
    guess = lambda pno: 'even' if pno % 2 == 0 else 'odd'
    flip = lambda s: 'odd' if s == 'even' else 'even'
    if L.get('parity') == 'pdf':
        return {pno: guess(pno) for pno in range(1, len(pdf.pages) + 1)}
    inside = lambda w, s: L[s]['body'][0] <= w['x0'] and w['x1'] <= L[s]['body'][1] + 3
    sure, votes = {}, [0, 0]   # votes: [PDF parity right, PDF parity flipped]
    for pno, pg in enumerate(pdf.pages, 1):
        body = [w for w in get_words(pg) if L.get('body_font', '') in w['fontname'] and abs(w['size'] - L['body_size']) < 0.3
                and L['top'] <= w['top'] and w['bottom'] <= L['bottom']]
        g, o = guess(pno), flip(guess(pno))
        n_g = sum(1 for w in body if inside(w, g) and not inside(w, o))
        n_o = sum(1 for w in body if inside(w, o) and not inside(w, g))
        if max(n_g, n_o) >= 20 and max(n_g, n_o) > 2 * min(n_g, n_o):
            sure[pno] = g if n_g > n_o else o
            votes[sure[pno] != g] += 1
    flipped = votes[1] > votes[0]
    return {pno: sure.get(pno, flip(guess(pno)) if flipped else guess(pno)) for pno in range(1, len(pdf.pages) + 1)}

def clean(t):
    t = fix_accents(re.sub(r'\s+', ' ', t).strip())
    # era labels set in small caps come out lowercase or spaced ("b.c.e.", "B. C. E.")
    t = re.sub(r'\b[bB]\. ?[cC]\. ?[eE]\.?(?![a-z])', 'B.C.E.', t)
    t = re.sub(r'(?<![A-Za-z.] )(?<![A-Za-z.])\b[cC]\. ?[eE]\.(?![a-z])', 'C.E.', t)
    t = re.sub(r'\b[aA]\. ?[dD]\.(?= ?\d)', 'A.D.', t)
    t = t.replace('B.C.E. .', 'B.C.E.').replace('C.E. .', 'C.E.')
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

BLOCKS = []
RUNIN = [None]   # heading level of run-in heads since the last real heading

def runin_split(ln):
    """A run-in head: a phrase in the run-in font that opens a body line (a few words in bold sans, then the text).
    It is a heading in all but layout. Kept bold inside the paragraph it merged with a bold term after it, or, at
    the top of a page, with the paragraph before it (a textbook chapter, Nov 18, 2026).
    layout.json "runin": [[font, size], ...]. Returns (head words, rest of the line) or (None, None)."""
    w0 = ln['words'][0]
    if not any(f in w0['fontname'] and abs(w0['size'] - z) < 0.3 for f, z in L.get('runin', [])):
        return None, None
    n = 0
    while n < len(ln['words']) and ln['words'][n]['fontname'] == w0['fontname']:
        n += 1
    head = ln['words'][:n]
    if re.fullmatch(r'[\d.\s]+', ' '.join(w['text'] for w in head)):     # a learning-objective number, not a head
        return None, None
    return head, ln['words'][n:]

def last_level():
    """A run-in head goes one level under the heading before it, so heading levels stay nested."""
    for b in reversed(BLOCKS):
        if b[0] == 'h':
            return b[1]
    return 1

def main():
    global L, HYPH, para
    pdf_path, layout_path, out_path = sys.argv[1:4]
    L.update(json.load(open(layout_path)))
    pdf = pdfplumber.open(pdf_path)
    load_invisible(pdf_path)
    SIDES = page_sides(pdf)
    # Pass 1: collect all words for hyphenation evidence
    alltext = ' '.join(w['text'] for pg in pdf.pages for w in get_words(pg))
    HYPH = {}
    for tok in re.findall(r"[A-Za-z]+-?[A-Za-z]+", alltext):
        HYPH[tok.lower()] = HYPH.get(tok.lower(), 0) + 1

    blocks = BLOCKS      # ('h', level, text) | ('p', text) | ('m', text) | ('marker', name) | ('note', text)
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
        if (pg.rotation or 0) % 180:
            # a sideways page (a wide map or table): pdfplumber's text is unusable there (Nov 18, 2026, six pages of
            # one chapter). Build it by hand: region.py prints PyMuPDF's upright reading of the page.
            print('page %d is sideways (/Rotate %d): marked <<PAGE%d>>; build it by hand' % (pno, pg.rotation, pno), file=sys.stderr)
            flush(); blocks.append(('marker', f'PAGE{pno}')); continue
        ws = [w for w in get_words(pg) if L['top'] <= w['top'] and w['bottom'] <= L['bottom']]
        side = SIDES[pno]
        bx, mx = L[side]['body'], L[side]['margin']
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
                ln['lev'] = lev; prev = ln; RUNIN[0] = None; continue
            head, rest = runin_split(ln)
            if head:
                htxt = render(fmt_words(head, body_size)).strip('*').strip()
                if prev is not None and prev.get('runin') and blocks and blocks[-1][0] == 'h':   # a head on two lines
                    blocks[-1] = ('h', blocks[-1][1], blocks[-1][2] + ' ' + htxt)
                else:
                    flush(); RUNIN[0] = RUNIN[0] or min(4, last_level() + 1); blocks.append(('h', RUNIN[0], htxt))
                if rest:
                    para = render(fmt_words(rest, body_size)); para_kind[0] = 'p'
                else:
                    ln['runin'] = True
                prev = ln; continue
            if ln['size'] < body_size - 1.5 and ln['top'] > 540:          # footnote
                if para_kind[0] == 'note' and para is not None:
                    para = para + ' ' + s
                else:
                    flush(); para = s; para_kind[0] = 'note'
                prev = ln; continue
            if bullet:
                flush(); para = s; para_kind[0] = 'li'; para_kind[1] = words[0]['x0'] if words else ln['x0']
                prev = ln; continue
            # a typed number in bold ("1." then the item) is a numbered list item, its turned lines follow it
            if re.fullmatch(r'\d{1,2}\.', first['text']) and fontkind(first['fontname'])[1] and len(ln['words']) > 1:
                flush(); para = first['text'] + ' ' + render(fmt_words(ln['words'][1:], body_size))
                para_kind[0] = 'ol'; para_kind[1] = ln['words'][1]['x0']
                prev = ln; continue
            if para_kind[0] in ('li', 'ol') and para is not None and abs(ln['x0'] - para_kind[1]) < 4:
                para = join_hyphen(para, s) if para.endswith('-') else para + ' ' + s
                prev = ln; continue
            # an indented block quote, set a size smaller: one quote, not one paragraph per line
            if L.get('body_font', '') in first['fontname'] and body_size - 1.6 <= ln['size'] <= body_size - 0.4 and ln['x0'] - col_left > 8:
                if para_kind[0] == 'q' and para is not None and prev is not None and ln['top'] - prev['bottom'] <= 6:
                    para = join_hyphen(para, s) if para.endswith('-') else para + ' ' + s
                else:
                    flush(); para = s; para_kind[0] = 'q'
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

    out = []
    for b in blocks:
        if b[0] == 'h': out.append('#' * b[1] + ' ' + clean(b[2]))
        elif b[0] == 'p': out.append(clean(b[1]))
        elif b[0] == 'li': out.append('- ' + clean(b[1]))
        elif b[0] == 'ol': out.append('  ' + clean(b[1]))
        elif b[0] == 'q': out.append('> [quote] ' + clean(b[1]))
        elif b[0] == 'note': out.append('> [note] ' + clean(b[1]))
        elif b[0] == 'm': out.append('> [margin] ' + clean(b[1]))
        elif b[0] == 'marker': out.append(f'<<{b[1]}>>')
    with open(out_path, 'w') as f:
        f.write('\n\n'.join(sort_margins(out)) + '\n\n')
    print('blocks', len(blocks))


MEDIA = r'my[a-z]+lab\.com'   # a publisher's online-lab notes in the margin ("... at mylab.com"); L['media_site'] overrides

def sort_margins(out):
    """Margin notes come out of the page as one kind. In a textbook they are three (Nov 18, 2026, three chapters):
    learning-objective tabs, split in two by the number box ("Define" + "**1.2** and provide ..."), become one
    '> [lo] **1.2** Define and provide ...'; an online-lab note and the glossary term printed under it, read as one
    note ("... at **mylab.com term** —its definition ..."), are split into '[media]' and '[margin]';
    a note that is only a lab note is '[media]'. A chapter number set smaller ("**Chapter^1^**") is plain again, and a
    typed numbered line ("**1.** States") becomes a real list item, which Word would otherwise flag as
    "This element should be formatted as a list"."""
    site = L.get('media_site', MEDIA)
    res = []
    for b in out:
        b = re.sub(r'\b(Chapter|Figure|Table)\^(\d+)\^', r'\1 \2', b)
        m = re.match(r'> \[margin\] \*\*(\d+\.\d+)\*\* (.*)$', b, re.S)
        if m and res and re.match(r'> \[margin\] [^*]{1,40}$', res[-1]):
            res[-1] = '> [lo] **%s** %s %s' % (m.group(1), res[-1][len('> [margin] '):], m.group(2)); continue
        if b.startswith('> [margin] ') and re.search(site, b):
            t = b[len('> [margin] '):]
            t = re.sub(r'(%s) (?=[^*]+\*\*)' % site, '\\1**\0**', t)    # "**lab.com Study**": split inside the bold run
            t = re.sub(r'(%s)(\*\*)? (?=\S)' % site, '\\1\\2\0', t)      # "**lab.com** Study"
            for part in (x.strip() for x in t.split('\0')):
                if part and part != '****':
                    res.append(('> [media] ' if re.search(site, part) else '> [margin] ') + part)
            continue
        b = re.sub(r'^\*\*(\d{1,2})\.\*\* ', r'  \1. ', b)
        if b.startswith('> [note] '):
            res.extend(split_notes(b[len('> [note] '):])); continue
        res.append(b)
    return join_page_breaks(res)


def split_notes(t):
    """'1The six ...' -> 'Note 1: The six ...'; two footnotes on one page read as one are split at the next number."""
    m = re.match(r'(\d{1,2}) ?(?=\S)(.*)$', t, re.S)
    if not m:
        return ['> [note] ' + t]
    n, rest = int(m.group(1)), m.group(2)
    nxt = re.search(r' %d ?(?=[“"A-Z])' % (n + 1), rest)
    if nxt:
        return ['> [note] Note %d: %s' % (n, rest[:nxt.start()].strip())] + split_notes(rest[nxt.start():].strip())
    return ['> [note] Note %d: %s' % (n, rest.strip())]


def join_page_breaks(B):
    """A paragraph that runs onto the next page comes out in two when a footnote, margin note, box marker or picture
    sits between the halves (15 places in one 48-page chapter, Nov 18, 2026). A plain paragraph that doesn't end a sentence is joined with the next plain
    paragraph, and what was between them moves after the joined paragraph."""
    plain = lambda b: not re.match(r'(#|> |!|- |\s+\d+\. |\s+a\) |1\. |<<)', b)
    between = lambda b: b.startswith(('> ', '!', '<<'))
    k = 0
    while k < len(B):
        b = B[k]
        if (plain(b) or re.match(r'\s+\d+\. ', b)) and not re.search(r'[.?!:;”"’)\]]\**\s*$|\^\d+\^\s*$', b):
            j = k + 1
            while j < len(B) and between(B[j]):
                j += 1
            if j < len(B) and plain(B[j]) and (j > k + 1 or re.match(r'[a-z(]', B[j])):
                a, c = b.rstrip(), B[j]
                joined = a[:-1] + c if re.search(r'[a-z]-$', a) and zf(re.findall(r'[A-Za-z]+-$', a)[-1][:-1] + re.match(r'[A-Za-z]*', c).group(0), 'en') > 0 else a + ' ' + c
                B[k:j + 1] = [joined] + B[k + 1:j]
                continue
        k += 1
    return B


if __name__ == '__main__':
    main()
