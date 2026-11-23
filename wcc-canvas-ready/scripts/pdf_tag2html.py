"""Rebuild a tagged browser-printed PDF (Chrome/Edge "Save as PDF", Google Docs/Forms prints) as clean HTML, so it
can be printed again at a readable size. F9 [Panorama "The font size is smaller than 11 points" (Minor, one per text
run)] and "The tag is empty" (Minor). Learned at WCC (Nov 2026): three Chrome prints (a 3-page guidance sheet, an
8-page statement, an 11-page analytics report full of tables) were stuck at 70% on small print (7.5-10 pt) and empty
tags after every tag fix; the text can't be enlarged inside the PDF without breaking the layout.

  python3 pdf_tag2html.py in.pdf out.html [--landscape] [--drop REGEX]
  google-chrome --headless=new --no-pdf-header-footer --print-to-pdf=out_raw.pdf out.html
  python3 pdf_tagfix.py out_raw.pdf out.pdf fix.json     # list structure + table summaries (see SKILL.md)

The structure tree is the source: H1-H6, P, BlockQuote, L/LI (numbered when the labels are numbers), Table with
THead/TBody/TR/TH/TD (scope, colspan, rowspan kept), Caption, Strong/Em, Link (its address comes from the link
annotation it covers), Figure (alt text kept, picture cropped from the page). Text comes from the marked content each
tag owns, so nothing is retyped. Empty tags are dropped. Every font size is 12 pt or more (headings larger).
--describe-links replaces link text that is a bare web address (Panorama: "The hyperlink text is not descriptive",
Minor in PDF) with a label drafted from the address and, inside a table, the row's next cell (usually a date):
"Facebook post, May 29 (facebook.com)". --links map.json overrides any label {"address": "text"}. The labels are
printed: YOU read them. The address stays the link target.
Bullets are printed as text ("•"), not drawn discs: Chrome tags each marker as a list label (Lbl), and a drawn disc
leaves that label without content, which Panorama counts as an empty tag (11 on a 3-page sheet).
--cards [alts.json] is for form/survey summaries printed from the browser (Google Forms "Summary" prints): each
question is a Heading 2, a chart drawn as untagged vector art, and its labels as loose text. The chart is cut from
the page (heading to next heading) as a picture; its alt text comes from alts.json {"start of question": "alt"}
or, if missing, a draft from the chart's labels (printed, so YOU can write the real one after looking at it).
Typed answers become a bulleted list; buttons ("Copy chart") and other form controls are dropped.
Empty table cells get "—" (--empty-cell TEXT to change it): Panorama counts an empty cell as an empty tag.
--landscape prints on letter landscape (use it for wide tables). --drop removes paragraphs matching a regex
(e.g. a running footer that the print tagged as text). Run the content check afterwards and look at every page.
"""
import sys, re, html, os, base64, io, collections
import pdfplumber, pikepdf
from pdfplumber.page import PDFPageAggregatorWithMarkedContent as _Agg

# pdfplumber forgets the tag ID when a tag is nested inside another (browsers wrap ligatures like "fi" in a
# /Span with ActualText inside the paragraph's tag): every character after the ligature lost its ID and was
# dropped. Keep a stack: a nested tag without an ID inherits its parent's, and closing it restores the parent.
def _begin(self, tag, props=None):
    st = self.__dict__.setdefault('_mcstack', [])
    mc = props['MCID'] if isinstance(props, dict) and 'MCID' in props else (st[-1][1] if st else None)
    nm = tag.name.decode("latin-1") if isinstance(tag.name, bytes) else str(tag.name)
    st.append((nm, mc)); self.cur_tag, self.cur_mcid = st[-1]
def _end(self):
    st = self.__dict__.setdefault('_mcstack', [])
    if st: st.pop()
    self.cur_tag, self.cur_mcid = st[-1] if st else (None, None)
_Agg.begin_tag, _Agg.end_tag = _begin, _end

src, dst = sys.argv[1], sys.argv[2]
LANDSCAPE = '--landscape' in sys.argv
DROP = re.compile(sys.argv[sys.argv.index('--drop') + 1]) if '--drop' in sys.argv else None
import json
DESCRIBE = '--describe-links' in sys.argv
CARDS = '--cards' in sys.argv
EMPTY_CELL = sys.argv[sys.argv.index('--empty-cell') + 1] if '--empty-cell' in sys.argv else '\u2014'
_ci = sys.argv.index('--cards') + 1 if CARDS else 0
CARD_ALTS = json.load(open(sys.argv[_ci])) if CARDS and _ci < len(sys.argv) and sys.argv[_ci].endswith('.json') else {}
import json
LINKMAP = json.load(open(sys.argv[sys.argv.index('--links') + 1])) if '--links' in sys.argv else {}

pdf = pdfplumber.open(src)
# (page index, mcid) -> list of chars
chars = collections.defaultdict(list)
boxes = collections.defaultdict(list)    # (page, mcid) -> bboxes of images and drawn shapes (for Figures)
for i, pg in enumerate(pdf.pages):
    for c in pg.chars:
        if c.get('mcid') is not None:
            chars[(i, c['mcid'])].append(c)
    for o in list(pg.images) + list(pg.rects) + list(pg.curves) + list(pg.lines):
        if o.get('mcid') is not None:
            boxes[(i, o['mcid'])].append((o['x0'], o['top'], o['x1'], o['bottom']))
links = [(i, h) for i, pg in enumerate(pdf.pages) for h in (pg.hyperlinks or [])]
title = (pdf.metadata or {}).get('Title') or ''
if isinstance(title, bytes): title = title.decode('utf-8', 'ignore')

LIG = {'\ufb00': 'ff', '\ufb01': 'fi', '\ufb02': 'fl', '\ufb03': 'ffi', '\ufb04': 'ffl', '\ufb05': 'st', '\ufb06': 'st'}
state = {'last': None, 'plain': False, 'tail': ''}
def _style(c):
    f = c.get('fontname', '')
    return ('Bold' in f or 'Black' in f or 'Heavy' in f, 'Italic' in f or 'Oblique' in f)
def text_of_mcid(pi, mcid, raw=False):
    """HTML for one marked-content sequence: spaces where the print left gaps or broke lines; bold and italic
    runs (from the font names) become <strong>/<em> unless the element is already bold (headings, TH)"""
    segs = []                                    # [(style, text)]
    for c in chars.get((pi, mcid), []):
        last = state['last']; sp = ''
        if last is not None:
            same_pg = last[0] == pi
            newline = (not same_pg) or abs(c['top'] - last[1]['top']) > c['size'] * 0.5
            gap = c['x0'] - last[1]['x1']
            prev = segs[-1][1] if segs else ''
            if (newline or gap > c['size'] * 0.18) and not prev.endswith((' ', '\u00a0')) and c['text'] not in ' \u00a0':
                sp = ' '
            if newline and same_pg and re.search(r'[^\W_]-$', state['tail']):   # "canvas-" + "accessible-docx":
                sp = ''                                    # a word with a hyphen, wrapped at the hyphen
        st = (False, False) if (raw or state['plain']) else _style(c)
        ch = LIG.get(c['text'], c['text'])
        if segs and segs[-1][1].endswith('\u2010') and sp:     # the browser's own hyphen at a line break: rejoin
            segs[-1] = (segs[-1][0], segs[-1][1][:-1].rstrip(' ')); sp = ''
        if ch == '\u2010': sp = ''
        if sp: segs.append(((False, False), sp))
        if segs and segs[-1][0] == st: segs[-1] = (st, segs[-1][1] + ch)
        else: segs.append((st, ch))
        state['last'] = (pi, c)
        state['tail'] = (state['tail'] + sp + ch)[-2:]
    if raw: return ''.join(t for _, t in segs)
    out = []
    for (b, i), t in segs:
        t = html.escape(t)
        if i and t.strip(): t = f'<em>{t}</em>'
        if b and t.strip(): t = f'<strong>{t}</strong>'
        out.append(t)
    return re.sub(r'</strong>(\s*)<strong>', r'\1', re.sub(r'</em>(\s*)<em>', r'\1', ''.join(out)))

class Node:
    """one structure element: type (role-mapped), alt, attributes, kids = Node | ('mc', page, mcid) | ('uri', str)"""
    def __init__(self, t, alt, a, kids): self.type, self.alt_text, self.attributes, self.kids = t, alt, a, kids

pk = pikepdf.open(src)
pg_index = {p.obj.objgen: i for i, p in enumerate(pk.pages)}
root = pk.Root.get('/StructTreeRoot')
# Keys without the slash: tags are looked up as 'Standard', and LibreOffice's map says '/Standard' -> '/P'. With the
# slash kept, a Word file's body paragraphs never became <p> and ran together in the Chrome PDF (Nov 22, 2026).
rolemap = {str(k).lstrip('/'): str(v) for k, v in (root.get('/RoleMap') or {}).items()} if root is not None else {}
def role(t):
    seen = 0
    while t in rolemap and seen < 10: t = rolemap[t].lstrip('/'); seen += 1
    return t
def build(el, page):
    if '/Pg' in el: page = pg_index.get(el.Pg.objgen, page)
    t = role(str(el.get('/S', '/Span')).lstrip('/'))
    a = {}
    A = el.get('/A')
    for d in (list(A) if isinstance(A, pikepdf.Array) else [A] if A is not None else []):
        if isinstance(d, pikepdf.Dictionary):
            for k, v in d.items():
                if k != '/O': a[k.lstrip('/')] = str(v).lstrip('/') if isinstance(v, pikepdf.Name) else (int(v) if isinstance(v, int) else str(v))
    alt = str(el.get('/Alt')) if '/Alt' in el else ''
    K = el.get('/K')
    items = list(K) if isinstance(K, pikepdf.Array) else ([] if K is None else [K])
    kids = []
    for k in items:
        if isinstance(k, int): kids.append(('mc', page, int(k)))
        elif isinstance(k, pikepdf.Dictionary):
            ty = k.get('/Type')
            if ty == '/MCR':
                pp = pg_index.get(k.Pg.objgen, page) if '/Pg' in k else page
                kids.append(('mc', pp, int(k.MCID)))
            elif ty == '/OBJR':
                ob = k.get('/Obj'); act = ob.get('/A') if ob is not None else None
                if act is not None and '/URI' in act: kids.append(('uri', str(act.URI)))
            elif '/S' in k: kids.append(build(k, page))
    return Node(t, alt, a, kids)
tree = []
if root is not None:
    K = root.get('/K')
    for k in (list(K) if isinstance(K, pikepdf.Array) else [K]):
        if isinstance(k, pikepdf.Dictionary): tree.append(build(k, None))

def mcs(e):
    out = []
    for k in e.kids:
        if isinstance(k, Node): out.extend(mcs(k))
        elif k[0] == 'mc': out.append((k[1], k[2]))
    return out
def bbox_of(e):
    pts = [(p, c) for p, m in mcs(e) if p is not None for c in chars.get((p, m), [])]
    if not pts:
        bx = [(p, b) for p, m in mcs(e) if p is not None for b in boxes.get((p, m), [])]
        if not bx: return None
        pi = bx[0][0]; bs = [b for p, b in bx if p == pi]
        return pi, (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))
    pi = pts[0][0]; cs = [c for p, c in pts if p == pi]
    return pi, (min(c['x0'] for c in cs), min(c['top'] for c in cs), max(c['x1'] for c in cs), max(c['bottom'] for c in cs))

def uri_for(e):
    for k in e.kids:
        if not isinstance(k, Node) and k[0] == 'uri': return k[1]
    b = bbox_of(e)
    if not b: return None
    pi, (x0, t, x1, bt) = b
    best = None
    for p, h in links:
        if p != pi: continue
        ix = min(x1, h['x1']) - max(x0, h['x0']); iy = min(bt, h['bottom']) - max(t, h['top'])
        if ix > 0 and iy > 0 and (best is None or ix * iy > best[0]): best = (ix * iy, h.get('uri'))
    return best[1] if best else None

def figure_img(e):
    b = bbox_of(e)
    if not b:
        return ''
    pi, bb = b
    pg = pdf.pages[pi]
    bb = (max(0, bb[0]), max(0, bb[1]), min(pg.width, bb[2]), min(pg.height, bb[3]))   # clip to the page
    if bb[2] - bb[0] < 2 or bb[3] - bb[1] < 2: return ''
    im = pg.crop(bb).to_image(resolution=150).original
    buf = io.BytesIO(); im.save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()

INLINE = {'Span', 'NonStruct', 'LBody', 'Reference', 'Note', 'Quote', 'Code', 'Sect', 'Art', 'Part', 'Document', 'Private'}
BLOCK = {'P': 'p', 'H1': 'h1', 'H2': 'h2', 'H3': 'h3', 'H4': 'h4', 'H5': 'h5', 'H6': 'h6', 'BlockQuote': 'blockquote',
         'Div': 'div', 'Caption': 'caption', 'TR': 'tr', 'THead': 'thead', 'TBody': 'tbody', 'TFoot': 'tfoot', 'Strong': 'strong', 'Em': 'em'}

def attrs(e):
    a = {}
    for k, v in (e.attributes or {}).items():
        a[k] = v.decode() if isinstance(v, bytes) else v
    return a

def render(e):
    t = e.type
    inner = []
    was = state['plain']
    if t in ('H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'TH', 'Strong', 'Caption'): state['plain'] = True
    pf = state.get('page_only')
    if t == 'TH' and pf is None:        # a header row repeated after a page break is tagged into the same cell:
        m0 = mcs(e)                     # keep only the copy on the first page
        if m0: state['page_only'] = m0[0][0]
    for k in e.kids:
        if isinstance(k, Node): inner.append(render(k))
        elif k[0] == 'mc' and k[1] is not None and (state.get('page_only') is None or k[1] == state['page_only']):
            inner.append(text_of_mcid(k[1], k[2]))
    state['page_only'] = pf
    state['plain'] = was
    body = ''.join(inner)
    plain = re.sub(r'<[^>]+>', '', body).strip()
    if t == 'Figure':
        alt = e.alt_text or ''
        src_ = figure_img(e)
        return f'<div class="fig"><img src="{src_}" alt="{html.escape(alt)}"></div>' if src_ else ''
    if t == 'Lbl':
        return ''                      # the browser draws the bullet or number again
    if not plain and '<img' in body:
        return body                    # a picture with no text around it: LibreOffice tags a Word picture as a Figure
                                       # inside a P, and the text-only test below dropped all 16 pictures of a guide
                                       # (Nov 22, 2026). The bare <div class="fig"> keeps it; a <p> can't hold a <div>.
    if not plain and t not in ('TD', 'TH'):
        return ''                      # empty tags are dropped (Panorama: "The tag is empty")
    if t in INLINE:
        return body
    if t == 'Link':
        u = uri_for(e)
        return f'<a href="{html.escape(u)}">{body}</a>' if u else body
    if t == 'L':
        lbls = [re.sub(r'\s', '', ''.join(text_of_mcid(p, m, raw=True) for p, m in mcs(x)))
                for li in e.kids if isinstance(li, Node) for x in li.kids if isinstance(x, Node) and x.type == 'Lbl']
        state_save = state['last']
        num = attrs(e).get('ListNumbering', '')
        ordered = str(num).lstrip('/') in ('Decimal', 'UpperRoman', 'LowerRoman', 'UpperAlpha', 'LowerAlpha') or \
            (lbls and all(re.fullmatch(r'\(?\w{1,3}[.)]', l) for l in lbls))
        state['last'] = state_save
        tag = 'ol' if ordered else 'ul'
        return f'<{tag}>{body}</{tag}>'
    if t == 'LI':
        return f'<li>{body}</li>'
    if t == 'Table':
        return f'<table>{body}</table>'
    if t in ('TH', 'TD'):
        a = attrs(e); extra = ''
        if t == 'TH':
            sc = str(a.get('Scope', '')).lstrip('/').lower()
            extra += f' scope="{sc if sc in ("row", "col") else "col"}"'
        for k, h in (('ColSpan', 'colspan'), ('RowSpan', 'rowspan')):
            if int(a.get(k, 1) or 1) > 1: extra += f' {h}="{int(a[k])}"'
        return f'<{t.lower()}{extra}>{body}</{t.lower()}>'
    if t in BLOCK:
        if t in ('P', 'Div') and DROP and DROP.search(plain): return ''
        return f'<{BLOCK[t]}>{body}</{BLOCK[t]}>'
    return body

CARD_LOG = []
def crop_img(pi, bb):
    im = pdf.pages[pi].crop(bb).to_image(resolution=150).original.convert('RGB')
    from PIL import ImageChops, Image
    diff = ImageChops.difference(im, Image.new('RGB', im.size, (255, 255, 255))).convert('L').point(lambda v: 255 if v > 12 else 0)
    box = diff.getbbox()                               # trim the blank margin around the card
    if box: im = im.crop((max(0, box[0] - 8), max(0, box[1] - 8), min(im.width, box[2] + 8), min(im.height, box[3] + 8)))
    buf = io.BytesIO(); im.save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
def render_cards(doc):
    """questions as H2, charts as cropped pictures, typed answers as lists"""
    kids = [k for k in doc.kids if isinstance(k, Node)]
    seq = []                                           # flatten one wrapper level (Chrome's NonStruct around the header)
    for k in kids:
        if k.type == 'NonStruct' and any(isinstance(x, Node) and x.type in ('H1', 'H2') for x in k.kids):
            seq += [x for x in k.kids if isinstance(x, Node)]
        else: seq.append(k)
    heads = [(i, bbox_of(k)) for i, k in enumerate(seq) if k.type == 'H2']
    out, cur = [], None
    for i, k in enumerate(seq):
        if k.type == 'Form': continue
        sub = [x for x in k.kids if isinstance(x, Node)]
        if sub and all(x.type == 'Form' for x in sub) and not any(not isinstance(x, Node) for x in k.kids): continue
        if k.type == 'H2':
            cur = i; out.append(render(k)); continue
        if cur is not None and k.type == 'NonStruct' and len(sub) >= 2 and all(x.type in ('NonStruct', 'P', 'Span') for x in sub):
            out.append('<ul>' + ''.join(f'<li>{r}</li>' for r in (render(x) for x in sub) if re.sub(r'<[^>]+>|\s', '', r)) + '</ul>')
            cur = None; continue
        if cur is not None and k.type == 'NonStruct':
            hb = dict(heads)[cur]; kb = bbox_of(k)
            if hb:
                pi, (x0, t, x1, b) = hb
                cpi = kb[0] if kb else pi                    # the chart may start on the next page
                pg = pdf.pages[cpi]
                top = b + 2 if cpi == pi else 30
                nxt = next((bb for j, bb in heads if j > cur and bb and bb[0] == cpi and bb[1][1] > top), None)
                bottom = nxt[1][1] - 6 if nxt else pg.height - 30
                if bottom - top < 20: bottom = min(pg.height, top + 200)
                region = (max(0, x0 - 20), top, pg.width - max(0, x0 - 20), bottom)
                pi = cpi
                q = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', render(seq[cur])))).strip()
                labels = re.sub(r'\s+', ' ', ''.join(text_of_mcid(p_, m_, raw=True) for p_, m_ in mcs(k))).strip()
                alt = next((v for kk, v in CARD_ALTS.items() if q.startswith(kk)), None)
                if alt is None: alt = f'Chart of answers. Labels shown: {labels}'
                CARD_LOG.append((q, alt == f'Chart of answers. Labels shown: {labels}', labels))
                out.append(f'<div class="fig"><img src="{crop_img(pi, region)}" alt="{html.escape(alt)}"></div>')
                cur = None; continue
        out.append(render(k))
    return out
parts = render_cards(tree[0]) if CARDS and tree else [render(e) for e in tree]
body = '\n'.join(p for p in parts if p)
# tables whose first row is all TH and that have no THead: wrap that row
def thead(m):
    t = m.group(0)
    if '<thead>' in t: return t
    first = re.search(r'<tr>(?:(?!</tr>).)*</tr>', t, re.S)
    if first and '<td' not in first.group(0):
        t = t.replace(first.group(0), '<thead>' + first.group(0) + '</thead>', 1)
    return t
body = re.sub(r'<table>.*?</table>', thead, body, flags=re.S)
def pad(m):                            # rows the print left short (an empty cell that wasn't tagged) get it back
    t = m.group(0)
    rows = re.findall(r'<tr>.*?</tr>', t, re.S)
    width = lambda r: sum(int(x or 1) for x in re.findall(r'<t[dh](?: scope="\w+")?(?: colspan="(\d+)")?', r))
    n = max((width(r) for r in rows), default=0)
    if any(re.search(r'rowspan=', r) for r in rows): return t
    for r in rows:
        if 0 < width(r) < n: t = t.replace(r, r[:-5] + '<td></td>' * (n - width(r)) + '</tr>', 1)
    return t
body = re.sub(r'<table>.*?</table>', pad, body, flags=re.S)
# a bare host with a path counts too ("whatcom-edu.zoom.us/my/name": WCC flagged it, Minor, Nov 17, 2026)
BARE = re.compile(r'^\s*(https?://|www\.|[\w-]+(\.[\w-]+)*\.(com|org|edu|net|gov|us|io|ca|uk|ai)(/|\s*$))\S?')
def draft_label(u):
    from urllib.parse import urlparse, parse_qs, unquote
    pu = urlparse(u); host = pu.netloc.lower().removeprefix('www.'); path = [x for x in pu.path.split('/') if x]
    site = host.split('.')[-2] if host.count('.') >= 1 else host
    if 'facebook.com' in host:
        if 'reel' in path: return 'Facebook reel'
        if 'posts' in path: return 'Facebook post'
        if 'live_videos' in path: return 'Facebook live videos'
        if host.startswith('business.'): return 'Meta Business Suite insights'
        return 'Facebook page' + (f' {path[0]}' if path else '')
    if 'instagram.com' in host:
        if path[:1] == ['reel']: return 'Instagram reel'
        if path[:1] == ['p']: return 'Instagram post'
        return 'Instagram profile' + (f' @{path[0]}' if path else '')
    if host in ('x.com', 'twitter.com'):
        return 'X post' if 'status' in path else 'X profile' + (f' @{path[0]}' if path else '')
    if 'tiktok.com' in host: return 'TikTok profile' + (f' {path[0]}' if path else '')
    if 'linkedin.com' in host: return 'LinkedIn page'
    if host == 'studio.youtube.com':
        tab = next((x[4:].replace('_', ' ') for x in path if x.startswith('tab-')), '')
        if 'videos' in path: return 'YouTube Studio ' + ('live videos' if 'live' in path else 'uploads') + ' list'
        return 'YouTube Studio analytics' + (f', {tab} tab' if tab else '')
    if 'youtube.com' in host or host == 'youtu.be': return 'YouTube video'
    if host.startswith('help.'): return f'{site.capitalize()} help article'
    if 'vimeo.com' in host:
        if path[:1] == ['analytics']:
            kind = path[1] if len(path) > 1 else ''
            return 'Vimeo analytics' + (f' by {kind}' if kind and kind != 'video' else (', video' if kind else ''))
        if 'analytics' in path: return 'Vimeo video analytics'
        if 'folder' in path: return 'Vimeo folder'
        return 'Vimeo video'
    return host
LABELS = []
def describe(m):
    href, text = m.group(1), m.group(2)
    plain = html.unescape(re.sub(r'<[^>]+>', '', text))
    if not BARE.match(plain): return m.group(0)
    u = html.unescape(href)
    if not DESCRIBE and u not in LINKMAP:
        shown = html.escape(re.sub(r"\s+", "", plain))
        return f'<a href="{href}">{shown}</a>'
    host = re.sub(r'^https?://(www\.)?', '', u).split('/')[0]
    lab = LINKMAP.get(u) or f'{draft_label(u)}{{CTX}} ({host})'
    LABELS.append((u, lab))
    return f'<a href="{href}">{html.escape(lab)}</a>'
body = re.sub(r'(\w) ?\u2010\s+(\w)', r'\1\2', body)
# no space just inside a block: Chrome tags a lone leading/trailing space as its own (empty) tag
# an empty table cell is an empty tag to Panorama (Minor, one per cell): fill it with a dash meaning "nothing here"
body = re.sub(r'<td((?: (?:colspan|rowspan)="\d+")*)>\s*</td>', lambda m: f'<td{m.group(1)}>{html.escape(EMPTY_CELL)}</td>', body)
for tg in ('em', 'strong'):              # "</em> <em>" leaves a lone tagged space between the two runs
    body = re.sub(r'</%s>(\s*)<%s>' % (tg, tg), r'\1', body)
BL = r'h[1-6]|p|li|td|th|caption|blockquote|div|figure'
body = re.sub(r'(<(?:%s)\b[^>]*>)\s+' % BL, r'\1', body)
body = re.sub(r'\s+(</(?:%s)>)' % BL, r'\1', body)      # browser hyphen at a line break, split across tags
body = re.sub(r'<a href="([^"]+)">(.*?)</a>', describe, body, flags=re.S)
def row_ctx(m):                       # in a table row, add the next cell's text to tell same-kind links apart
    r = m.group(0)
    cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S)
    for i, c in enumerate(cells):
        if '{CTX}' in c and re.sub(r'<a href="[^"]+">.*?</a>|<[^>]+>|\s', '', c):
            r = r.replace(c, c.replace('{CTX}', ''), 1); continue      # the cell's own text already says what it is
        if '{CTX}' in c:
            nxt = next((html.unescape(re.sub(r'<[^>]+>', '', x)).strip() for x in cells[i + 1:] if re.sub(r'<[^>]+>', '', x).strip()), '')
            nxt = re.split(r'\s{2,}|,', nxt)[0][:40].strip()
            r = r.replace(c, c.replace('{CTX}', html.escape(f', {nxt}') if nxt else '', 1), 1)
    return r
body = re.sub(r'<tr>.*?</tr>', row_ctx, body, flags=re.S)
body = body.replace('{CTX}', '')
LABELS = [(u, l.replace('{CTX}', '')) for u, l in LABELS]
# No H1 in the tags: a bold first line becomes the H1, or the first H2 does (Panorama: "The document does not have any
# headings" / no H1. Nov 17, 2026: a one-page checklist whose title was only bold, and a browser syllabus print that
# started at H2, both rebuilt without an H1).
if not re.search(r'<h1[\s>]', body):
    m_ = re.search(r'<p><strong>([^<]{2,150}?)\s*</strong></p>', body)
    first_h = re.search(r'<h([2-6])[\s>]', body)
    if m_ and (not first_h or m_.start() < first_h.start()):
        body = body[:m_.start()] + f'<h1>{m_.group(1).strip()}</h1>' + body[m_.end():]
    elif first_h:
        n_ = first_h.group(1); i_ = first_h.start(); j_ = body.find(f'</h{n_}>', i_)
        body = body[:i_] + '<h1' + body[i_ + 3:j_] + '</h1>' + body[j_ + 5:]
# Headings must not skip levels (H1 then H3): WCC flagged "The document's heading structure is not properly nested"
# (Severe, 0%) on a browser print rebuilt this way, Nov 17, 2026. Each heading may go at most one level deeper.
_prev = [0]
def _nest(m):
    lv = int(m.group(2)); new = min(lv, _prev[0] + 1) if _prev[0] else lv
    _prev[0] = new
    return f'<{m.group(1)}h{new}'
body = re.sub(r'<(/?)h([1-6])(?=[\s>])', lambda m: m.group(0) if m.group(1) else _nest(m), body)
# closing tags follow their opening tag's new level
_lv = []
def _close(m):
    if m.group(1) == '': _lv.append(m.group(2)); return m.group(0)
    return f'</h{_lv.pop() if _lv else m.group(2)}'
body = re.sub(r'<(/?)h([1-6])(?=[\s>])', _close, body)
if not title:
    h1 = re.search(r'<h1>(.*?)</h1>', body, re.S)
    title = re.sub(r'<[^>]+>', '', h1.group(1)).strip() if h1 else os.path.basename(src)

css = f'''@page {{ size: letter{' landscape' if LANDSCAPE else ''}; margin: 0.6in; }}
body {{ font-family: "Liberation Sans", Arial, sans-serif; font-size: 12pt; line-height: 1.4; color: #1a1a1a; }}
h1 {{ font-size: 20pt; }} h2 {{ font-size: 16pt; margin-top: 1.2em; break-after: avoid; }} h3, h4 {{ break-after: avoid; }} h1, h2, h3, h4, h5, h6 {{ break-inside: avoid; }} h3 {{ font-size: 14pt; }} h4, h5, h6 {{ font-size: 12pt; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.6em 0 1em; font-size: 12pt; }}
th, td {{ border: 1px solid #767676; padding: 4px 6px; vertical-align: top; text-align: left; overflow-wrap: break-word; }}
thead th {{ background: #f0f0f0; }}
caption {{ text-align: left; font-weight: bold; padding: 4px 0; caption-side: top; }}
a {{ color: #0b57a4; overflow-wrap: anywhere; }} blockquote {{ margin-left: 1.2em; padding-left: 0.8em; border-left: 3px solid #767676; }}
img {{ max-width: 100%; }} .fig {{ margin: 0.6em 0; break-inside: avoid; }}
ul {{ list-style-type: "•  "; }} ul ul {{ list-style-type: "–  "; }} li::marker {{ font-family: inherit; }}
* {{ font-size: max(12pt, 1em); }}'''
out = f'''<!DOCTYPE html>
<html lang="en-US"><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>{css}</style></head>
<body><main>
{body}
</main></body></html>'''
open(dst, 'w').write(out)
cnt = collections.Counter(re.findall(r'<(h[1-6]|p|table|ul|ol|li|a|img|blockquote)\b', body))
print(f'{dst}: title "{title}"; ' + ', '.join(f'{k} {v}' for k, v in sorted(cnt.items())))
if CARD_LOG:
    print(f'charts cut as pictures: {len(CARD_LOG)}; alt text still drafted from labels (write real ones): {sum(1 for _, d, _ in CARD_LOG if d)}')
    for q, d, lab in CARD_LOG:
        if d: print(f'    "{q[:60]}": labels: {lab[:120]}')
if LABELS:
    print(f'link text written for {len(LABELS)} bare-address links (check them):')
    for txt_ in re.findall(r'<a href="[^"]+">([^<]*)</a>', body):
        if any(txt_ == html.escape(l) for _, l in LABELS): print('   ', html.unescape(txt_))
