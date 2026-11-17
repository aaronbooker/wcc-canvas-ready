"""Fix a .pptx for WCC Panorama. Usage: python3 pptx_fix.py in.pptx out.pptx [--title "Deck title"] [--report]
P2  every slide gets a real title placeholder: the slide's own heading text box (largest text in the
    top 40% of the slide) is converted to <p:ph type="title"/>; nothing is added or reworded.
    Slides with no heading-like text are reported, not invented.
P6  reading order: shapes with no text and no picture are marked decorative; content shapes are put in
    visual order (top-to-bottom rows, left-to-right), decorative shapes behind them in their old order.
P7  contrast: each text run is measured against what is really behind it (topmost filled shape under
    the text box, else slide/layout/master background); failing colors are moved toward black or white
    just far enough to pass (4.5:1, or 3:1 for >=18 pt / >=14 pt bold).
P8  pictures with no alt text are reported (alt text must be written by a person or with care).
P12 every run, paragraph default and list style raised to >= 12 pt on slides, layouts and masters.
P4/P5 document title, language en-US on every run and in core properties.
--report: only print what would change.
--keep-order 3,9: leave these slides in their current reading order (the instructor checked them).
--order-file order.json: {"3": ["Title 1", "Text 5", "Picture 2"]} sets a slide's content order by shape name
    (names as pptx_order_preview.py prints them); shapes not listed follow in the fixer's order.
Show the proposed order before keeping it: pptx_order_preview.py renders each slide with the order numbered.
"""
import sys, os, re, copy
from pptx import Presentation
from pptx.util import Emu
from lxml import etree
from pptx.oxml import parse_xml

NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
A = '{%s}' % NS['a']; P = '{%s}' % NS['p']
DEC_URI = '{C183D7F6-B498-43B3-948B-1728B52AA6E4}'
ADEC = 'http://schemas.microsoft.com/office/drawing/2017/decorative'

args = sys.argv[1:]
src, dst = args[0], args[1]
REPORT = '--report' in args
ORDER_MODE = args[args.index('--order') + 1] if '--order' in args else 'xycut'
NO_GROUP = '--no-group' in args
TITLE = args[args.index('--title') + 1] if '--title' in args else None
KEEP = {int(x) for x in args[args.index('--keep-order') + 1].split(',') if x.strip()} if '--keep-order' in args else set()
import json as _json
ORDER_FILE = {int(k): v for k, v in _json.load(open(args[args.index('--order-file') + 1])).items()} if '--order-file' in args else {}
# --titles titles.json: {"5": "Slide title", ...} for slides with no heading-like text (YOU write them, the instructor
# agrees). The title is added as a real title placeholder just above the slide's top edge: screen readers and Panorama
# read it, the slide looks the same. Used for slides that are one picture of text (a deck of pasted slide images,
# Nov 17, 2026: five such slides stayed "The document does not have slide titles", Major).
TITLES = {int(k): v for k, v in _json.load(open(args[args.index('--titles') + 1])).items()} if '--titles' in args else {}
prs = Presentation(src)
SW, SH = prs.slide_width, prs.slide_height
log = []

def lum(h):
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

def ratio(a, b):
    x, y = lum(a), lum(b)
    return (max(x, y) + .05) / (min(x, y) + .05)

def fix_color(fg, bg, need):
    """Move fg toward black or white (whichever direction can pass) until it meets need."""
    target = '000000' if lum(bg) > 0.18 else 'FFFFFF'
    if ratio(target, bg) < need:
        target = 'FFFFFF' if target == '000000' else '000000'
    r0 = [int(fg[i:i + 2], 16) for i in (0, 2, 4)]; r1 = [int(target[i:i + 2], 16) for i in (0, 2, 4)]
    for k in range(1, 101):
        t = k / 100
        c = ''.join('%02X' % round(a + (b - a) * t) for a, b in zip(r0, r1))
        if ratio(c, bg) >= need + 0.5:   # margin: checkers compute contrast slightly differently
            return c
    return target

def theme_colors():
    th = {}
    master = prs.slide_masters[0]
    for rel in master.part.rels.values():
        if rel.reltype.endswith('/theme'):
            x = etree.fromstring(rel.target_part.blob)
            for el in x.iter():
                if el.getparent() is not None and el.getparent().tag == A + 'clrScheme':
                    c = el.find(A + 'srgbClr'); s = el.find(A + 'sysClr')
                    th[etree.QName(el).localname] = c.get('val') if c is not None else (s.get('lastClr') if s is not None else None)
    th.update({'tx1': th.get('dk1'), 'bg1': th.get('lt1'), 'tx2': th.get('dk2'), 'bg2': th.get('lt2')})
    return th
THEME = theme_colors()

def color_of(el):
    if el is None: return None
    s = el.find(A + 'srgbClr')
    if s is not None: return s.get('val').upper()
    s = el.find(A + 'schemeClr')
    if s is not None: return (THEME.get(s.get('val')) or '').upper() or None
    return None

def bg_kinds():
    """fill kinds of the theme's background styles (bgRef idx 1001, 1002, 1003 -> solidFill / gradFill / blipFill)"""
    master = prs.slide_masters[0]
    for rel in master.part.rels.values():
        if rel.reltype.endswith('/theme'):
            x = etree.fromstring(rel.target_part.blob)
            lst = x.find('.//' + A + 'bgFillStyleLst')
            if lst is not None: return [etree.QName(k).localname for k in lst]
    return []
BGKINDS = bg_kinds()

def bg_color(slide):
    """the slide's solid background color, or None when it is a picture or gradient (contrast can't be computed:
    a theme-blue link on a teal photo background was darkened to near-invisible before this check existed)"""
    for part in (slide, slide.slide_layout, slide.slide_layout.slide_master):
        bg = part._element.find('.//' + P + 'bg')
        if bg is not None:
            if bg.find('.//' + A + 'blipFill') is not None or bg.find('.//' + A + 'gradFill') is not None: return None
            sf = bg.find('.//' + A + 'solidFill')
            c = color_of(sf)
            if c: return c
            ref = bg.find(P + 'bgRef')
            if ref is not None:
                idx = int(ref.get('idx', '0'))
                if idx > 1000 and idx - 1001 < len(BGKINDS) and BGKINDS[idx - 1001] != 'solidFill': return None
                c = color_of(ref)
                if c: return c
    return 'FFFFFF'

def box(sh):
    try:
        return (sh.left or 0, sh.top or 0, (sh.left or 0) + (sh.width or 0), (sh.top or 0) + (sh.height or 0))
    except Exception:
        return (0, 0, 0, 0)

def is_dec(el):
    return any(e.tag == '{%s}decorative' % ADEC for e in el.iter())

def mark_dec(el):
    cnv = el.find('.//' + P + 'cNvPr')
    if cnv is None or is_dec(cnv): return
    ext_lst = cnv.find(A + 'extLst')
    if ext_lst is None: ext_lst = etree.SubElement(cnv, A + 'extLst')
    ext = etree.SubElement(ext_lst, A + 'ext', uri=DEC_URI)
    etree.SubElement(ext, '{%s}decorative' % ADEC, nsmap={'adec': ADEC}, val='1')

def max_size(sh):
    sizes = [int(v) for v in re.findall(r'\bsz="(\d+)"', etree.tostring(sh._element).decode())]
    return max(sizes) if sizes else 1800

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pptx_bg import Backdrop, leaf_shapes
BACKDROP = Backdrop(prs, color_of, bg_color)
titles_text = []
for i, s in enumerate(prs.slides, 1):
    shapes = list(s.shapes)
    tree = s.shapes._spTree
    t = s.shapes.title
    # ---- P2: title placeholder
    if t is None or not t.text_frame.text.strip():
        def headlike(sh):
            if not sh.has_text_frame or sh.top is None: return False
            tx = sh.text_frame.text.strip()
            return bool(tx) and len(tx) < 120 and len(re.findall(r'[A-Za-z]', tx)) >= 3   # skip stat callouts like "85"
        cands = [sh for sh in shapes if headlike(sh)]
        # labels sitting on a photo ("ocean entry", "lava tube trace") are not the slide's heading: when two or more
        # text boxes lie inside the same picture, none of them is taken as the title (WCC, Nov 2026: a label made
        # the title of a labelled photo kept "Check reading order" in every order tried)
        def inside(a, b):
            return a.left >= b.left - 12700 and a.top >= b.top - 12700 and a.left + a.width <= b.left + b.width + 12700 \
                and a.top + a.height <= b.top + b.height + 12700
        pics = [x for x in shapes if x._element.tag == P + 'pic' and x.width]
        for pc in pics:
            on = [sh for sh in cands if sh.width and inside(sh, pc)]
            if len(on) >= 2: cands = [sh for sh in cands if sh not in on]
        top = [sh for sh in cands if sh.top < SH * 0.5]
        cands = top or cands
        if cands:
            # heading = topmost of the big text (>= 18 pt and >= 60% of the largest); a big pull-quote lower down is not the title
            big = max(max_size(sh) for sh in cands)
            pool = [sh for sh in cands if max_size(sh) >= max(1800, 0.6 * big)] or cands
            best = min(pool, key=lambda sh: (sh.top, -max_size(sh)))
            el = best._element
            nvpr = el.find('.//' + P + 'nvPr')
            if el.tag == P + 'sp' and nvpr is not None:
                cnvsp = el.find('.//' + P + 'cNvSpPr')
                if cnvsp is not None and cnvsp.get('txBox'): del cnvsp.attrib['txBox']
                for old in nvpr.findall(P + 'ph'): nvpr.remove(old)
                nvpr.insert(0, etree.Element(P + 'ph', type='title'))
                # wrap="none" boxes are often narrower than their text; some renderers wrap placeholders anyway, so widen to fit
                bp = el.find('.//' + A + 'bodyPr'); ext = el.find('./' + P + 'spPr/' + A + 'xfrm/' + A + 'ext'); off = el.find('./' + P + 'spPr/' + A + 'xfrm/' + A + 'off')
                if bp is not None and bp.get('wrap') == 'none' and ext is not None and off is not None:
                    longest = max(len(l) for l in best.text_frame.text.split('\n'))
                    need = int(longest * max_size(best) / 100 * 0.62 * 12700)
                    room = SW - int(off.get('x')) - 12700 * 18
                    if need > int(ext.get('cx')): ext.set('cx', str(min(need, room)))
                # freeze the text box's own look so the master title style (caps, gradient, 32 pt, major font) can't leak in
                for pp in el.iter(A + 'p'):
                    ppr = pp.find(A + 'pPr')
                    if ppr is None: ppr = etree.Element(A + 'pPr'); pp.insert(0, ppr)
                    if not ppr.get('algn'): ppr.set('algn', 'l')
                # also bold, line spacing, anchor, insets and autofit: the master title style is usually bold, centred
                # vertically and set at 90% line spacing, which made three headings bold and pushed one up into two
                # lines over a map (a test deck, Nov 15, 2026)
                lst_b = any(d.get('b') for d in el.iter(A + 'defRPr'))
                bp = el.find('.//' + A + 'bodyPr')
                if bp is not None:
                    if not bp.get('anchor'): bp.set('anchor', 't')
                    for k, v in (('lIns', '91440'), ('tIns', '45720'), ('rIns', '91440'), ('bIns', '45720')):
                        if not bp.get(k): bp.set(k, v)
                    if not any(etree.QName(c).localname in ('noAutofit', 'normAutofit', 'spAutoFit') for c in bp):
                        etree.SubElement(bp, A + 'noAutofit')
                for pp in el.iter(A + 'p'):
                    ppr = pp.find(A + 'pPr')
                    if ppr is not None:
                        order = ['lnSpc', 'spcBef', 'spcAft']
                        have = {etree.QName(c).localname for c in ppr}
                        if 'lnSpc' not in have:
                            ln = etree.Element(A + 'lnSpc'); etree.SubElement(ln, A + 'spcPct', val='100000'); ppr.insert(0, ln)
                        if 'spcBef' not in have:
                            sb = etree.Element(A + 'spcBef'); etree.SubElement(sb, A + 'spcPts', val='0')
                            ppr.find(A + 'lnSpc').addnext(sb)
                for rp in list(el.iter(A + 'rPr')) + list(el.iter(A + 'endParaRPr')):
                    if not rp.get('b') and not lst_b: rp.set('b', '0')
                    if not rp.get('cap'): rp.set('cap', 'none')
                    if not rp.get('sz'): rp.set('sz', '1800')
                    if rp.find(A + 'solidFill') is None and rp.find(A + 'gradFill') is None:
                        sf = etree.Element(A + 'solidFill'); etree.SubElement(sf, A + 'schemeClr', val='tx1')
                        kids = [k for k in rp if etree.QName(k).localname in ('ln',)]
                        (kids[-1].addnext(sf) if kids else rp.insert(0, sf))
                    if rp.find(A + 'latin') is None:
                        lat = etree.Element(A + 'latin', typeface='+mn-lt')
                        after = [k for k in rp if etree.QName(k).localname in ('ln','noFill','solidFill','gradFill','blipFill','pattFill','grpFill','effectLst','effectDag','highlight','uLnTx','uLn','uFillTx','uFill')]
                        (after[-1].addnext(lat) if after else rp.insert(0, lat))
                shown = best.text_frame.text.strip().replace(chr(10), ' ').replace(chr(11), ' ')[:50]
                log.append(f'slide {i}: title placeholder from "{shown}"')
                t = best
        elif i in TITLES:
            ids = [int(x) for x in s._element.xpath('.//p:cNvPr/@id')] or [1]
            from pptx.oxml import parse_xml   # python-pptx's own element classes, so s.shapes can read it
            new = parse_xml(
                f'<p:sp xmlns:p="{NS["p"]}" xmlns:a="{NS["a"]}"><p:nvSpPr><p:cNvPr id="{max(ids) + 1}" name="Title (added)"/>'
                '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>'
                f'<p:spPr><a:xfrm><a:off x="0" y="-{int(SH * 0.12)}"/><a:ext cx="{SW}" cy="{int(SH * 0.1)}"/></a:xfrm></p:spPr>'
                '<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="2800"/><a:t></a:t></a:r></a:p></p:txBody></p:sp>')
            new.find('.//' + A + 't').text = TITLES[i]
            tree_ = s.shapes._spTree
            first = [k for k in tree_ if etree.QName(k).localname not in ('nvGrpSpPr', 'grpSpPr')]
            (first[0].addprevious(new) if first else tree_.append(new))
            t = [sh for sh in s.shapes if sh._element is new][0]
            log.append(f'slide {i}: title added just above the slide (not visible): "{TITLES[i][:50]}"')
        else:
            log.append(f'slide {i}: NO heading-like text; needs a title written by the instructor')
    if t is not None:
        titles_text.append(t.text_frame.text.strip())
    # ---- P6: decorative marks + title first among content
    for sh in shapes:
        el = sh._element
        has_text = sh.has_text_frame and sh.text_frame.text.strip()
        if has_text and is_dec(el):
            # text marked decorative is skipped by screen readers (a textbook deck had every slide TITLE marked
            # decorative): text is content, so the mark comes off
            for e in list(el.iter()):
                if e.tag == '{%s}decorative' % ADEC:
                    ext = e.getparent(); lst = ext.getparent(); lst.remove(ext)
                    if len(lst) == 0: lst.getparent().remove(lst)
            shown = sh.text_frame.text.strip().replace(chr(10), ' ').replace(chr(11), ' ')[:30]
            log.append(f'slide {i}: "{shown}" was marked decorative; mark removed')
        if el.tag in (P + 'sp', P + 'cxnSp') and not has_text and not sh.is_placeholder:
            mark_dec(el);
    # Reading order = visual order. WCC Panorama flags "Check reading order of slide" (Major) when the
    # shape order in spTree differs from top-to-bottom, left-to-right position (even if the title is first).
    # Decorative shapes keep their relative order at the back, content shapes follow sorted by position,
    # so fills stay behind text. Slides where this would change the picture are checked by rendering (--verify).
    kids = [k for k in tree if k.tag in (P + 'sp', P + 'pic', P + 'grpSp', P + 'graphicFrame', P + 'cxnSp')]
    def xfrm(k):   # shapes use a:xfrm; tables, charts and SmartArt (graphicFrame) use p:xfrm
        return k.find('./' + P + 'xfrm') if k.tag == P + 'graphicFrame' else k.find('.//' + A + 'xfrm')
    # placeholders often carry no position of their own: they inherit it from the layout. python-pptx resolves that;
    # without it a title and body both read as (0, 0) and keep their XML order (body before title on a WCC-flagged slide)
    geo = {}
    for sh in s.shapes:
        try: geo[sh._element] = (int(sh.left), int(sh.top), int(sh.left) + int(sh.width), int(sh.top) + int(sh.height))
        except (TypeError, ValueError): pass
    def pos(k):
        xf = xfrm(k); off = xf.find(A + 'off') if xf is not None else None
        if off is not None: return (int(off.get('y')), int(off.get('x')))
        g = geo.get(k); return (g[1], g[0]) if g else (0, 0)
    dec = [k for k in kids if is_dec(k)]
    content = [k for k in kids if not is_dec(k)]
    ORDER = ORDER_MODE
    if ORDER == 'rows':
        tol = SH * 0.02
        rows = sorted(content, key=lambda k: pos(k))
        ordered, cur, cur_y = [], [], None
        for k in rows:
            y = pos(k)[0]
            if cur and y - cur_y > tol:
                ordered += sorted(cur, key=lambda k: pos(k)[1]); cur = []
            if not cur: cur_y = y
            cur.append(k)
        ordered += sorted(cur, key=lambda k: pos(k)[1])
    elif ORDER == 'xycut':
        # Recursive XY-cut (how layout-analysis tools read a page): split into horizontal bands wherever no shape
        # spans the gap, top to bottom; a band that can't be split is split into columns at vertical gaps,
        # left to right; recurse. Cards in a row read card by card; an eyebrow above the title reads first.
        def bb(k):
            xf = xfrm(k)                             # not './/a:ext': the decorative mark is an <a:ext uri=…>
            off = xf.find(A + 'off') if xf is not None else None; ext = xf.find(A + 'ext') if xf is not None else None
            if off is None or ext is None: return geo.get(k, (0, 0, 0, 0))
            x, y = int(off.get('x')), int(off.get('y'))
            return (x, y, x + int(ext.get('cx')), y + int(ext.get('cy')))
        slack = 12700 * 2
        def cut(items, axis):
            lo, hi = (1, 3) if axis == 'y' else (0, 2)
            # columns may overlap a little (a footer a bit wider than its column); rows may not
            tol = slack if axis == "y" else int(SW * 0.15)
            items = sorted(items, key=lambda k: bb(k)[lo])
            groups, end = [], None
            for k in items:
                b = bb(k)
                if groups and b[lo] < end - tol: groups[-1].append(k); end = max(end, b[hi])
                else: groups.append([k]); end = b[hi]
            return groups
        def leaf(items):   # shapes that overlap both ways: rows (tops within 8 pt), then left to right
            out, row, top = [], [], None
            for k in sorted(items, key=lambda k: bb(k)[1]):
                if row and bb(k)[1] - top > 12700 * 8: out += sorted(row, key=lambda k: bb(k)[0]); row = []
                if not row: top = bb(k)[1]
                row.append(k)
            return out + sorted(row, key=lambda k: bb(k)[0])
        def xy(items, depth=0):
            if len(items) <= 1 or depth > 12: return leaf(items)
            # columns first: WCC Panorama reads a left column before a right one (tested on 16 controlled slides).
            g = cut(items, 'x')
            if len(g) > 1: return [k for grp in g for k in xy(grp, depth + 1)]
            # no column split possible (something spans the width, like a title): peel off the top band only,
            # then look for columns again in everything below it
            g = cut(items, 'y')
            if len(g) > 1: return xy(g[0], depth + 1) + xy([k for grp in g[1:] for k in grp], depth + 1)
            return leaf(items)
        # decorative card/panel backgrounds take part in the cuts (they hold a card's title and body
        # together) but only content shapes are ordered; full-slide backgrounds are left out
        frames = [k for k in dec if not (bb(k)[2] - bb(k)[0] > SW * 0.9 and bb(k)[3] - bb(k)[1] > SH * 0.9)]
        cset = set(content)
        ordered = [k for k in xy(content + frames) if k in cset]
    else:
        # columns: group shapes whose left edges line up (within 2% of slide width), read each column
        # top to bottom, columns left to right
        tolx = SW * 0.02
        cols = []
        for k in sorted(content, key=lambda k: pos(k)[1]):
            x = pos(k)[1]
            if cols and x - cols[-1][0] <= tolx: cols[-1][1].append(k)
            else: cols.append([x, [k]])
        ordered = [k for _, ks in cols for k in sorted(ks, key=lambda k: pos(k)[0])]
    # (Tested and rejected at WCC, Nov 2026: forcing the title to the front of the content order DOUBLED the
    # reading-order flags on two decks (15 -> 30, 7 -> 14). Content stays in column-first visual order.)
    # (Tested and rejected at WCC, Nov 2026: moving decoration that overlaps nothing to after the content DOUBLED the
    # reading-order flags on two decks (7 -> 14, 15 -> 30). Decoration stays at the back, in its original order.)
    if i in ORDER_FILE:                      # the instructor's own order for this slide
        names = ORDER_FILE[i]
        nm = lambda k: (k.find('.//' + P + 'cNvPr').get('name') if k.find('.//' + P + 'cNvPr') is not None else '')
        listed = [next((k for k in ordered if nm(k) == n), None) for n in names]
        listed = [k for k in listed if k is not None]
        ordered = listed + [k for k in ordered if k not in listed]
        log.append(f'slide {i}: reading order set as the instructor gave it')
    keep = i in KEEP
    if keep: log.append(f'slide {i}: reading order kept as it was (the instructor checked it)')
    # Decoration goes to the back, EXCEPT decoration that was drawn on top of a content shape it overlaps (a red
    # outline marking a town on a map): sent to the back it disappears behind the map (seen on a test deck,
    # Nov 15, 2026). That kind stays just above the last content shape it covered.
    final = list(ordered)
    back = []
    def ov(a, b):
        A_, B_ = geo.get(a), geo.get(b)
        if not A_ or not B_: return False
        return A_[0] < B_[2] and B_[0] < A_[2] and A_[1] < B_[3] and B_[1] < A_[3]
    for d in dec:
        below = [c for c in ordered if kids.index(c) < kids.index(d) and ov(c, d)]
        if not below or (geo.get(d) and (geo[d][2] - geo[d][0]) > SW * 0.9 and (geo[d][3] - geo[d][1]) > SH * 0.9):
            back.append(d)
        else:
            at = max(final.index(c) for c in below)
            final.insert(at + 1, d)
    # P6b group into one unit. Tested at WCC (Nov 15, 2026): three slides (a labelled photo, two pictures under a
    # prompt box, a column of three photos beside a title) kept "Check reading order of slide" in EVERY order tried
    # (4 orders each, the author's own included); title first + the rest of the slide as ONE GROUP cleared all three
    # (deck 100%). Microsoft's advice for this warning is the same: group objects into logical units. Placeholders and
    # media can't be grouped safely, and a title that overlaps the content must stay where it is (z-order), so those
    # slides are left in visual order.
    anchor = kids[0].getprevious() if kids else None   # before anything moves (grpSpPr)
    t_el = t._element if t is not None and t._element in kids else None
    rest = [k for k in final if k is not t_el]
    content_rest = [k for k in rest if not is_dec(k)]
    def grp_ok():
        if NO_GROUP or keep or i in ORDER_FILE or len(content_rest) < 3: return False
        if any(k.find('.//' + P + 'nvPr/' + P + 'ph') is not None for k in rest): return False
        if any(re.search(r'videoFile|audioFile|p14:media', etree.tostring(k).decode()) for k in rest): return False
        if any(k.find('.//' + A + 'tbl') is not None for k in rest): return False   # PowerPoint can't group tables
        if t_el is not None and any(ov(t_el, k) for k in rest): return False
        return all(geo.get(k) for k in rest)
    grouped = None
    if grp_ok():
        bs = [geo[k] for k in rest]
        x0, y0, x1, y1 = min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)
        nid = max(int(e.get('id')) for e in tree.iter(P + 'cNvPr') if (e.get('id') or '').isdigit()) + 1
        grouped = parse_xml(
            f'<p:grpSp xmlns:p="{NS["p"]}" xmlns:a="{NS["a"]}"><p:nvGrpSpPr><p:cNvPr id="{nid}" name="Slide content"/>'
            f'<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="{x0}" y="{y0}"/><a:ext cx="{x1 - x0}" cy="{y1 - y0}"/>'
            f'<a:chOff x="{x0}" y="{y0}"/><a:chExt cx="{x1 - x0}" cy="{y1 - y0}"/></a:xfrm></p:grpSpPr></p:grpSp>')
        for k in rest: grouped.append(k)        # (moved out of kids below)
        final = ([t_el] if t_el is not None else []) + [grouped]
    if not keep and (grouped is not None or back + final != kids):
        for k in kids:
            if k.getparent() is tree: tree.remove(k)
        for k in reversed(back + final):
            anchor.addnext(k)
        if grouped is not None:
            log.append(f'slide {i}: title first, then the other {len(content_rest)} content shapes grouped as one unit, in visual order (looks the same)')
        else:
            log.append(f'slide {i}: reading order set to visual order ({len(ordered)} content shapes)')
    # ---- P11: tables get a header row (Panorama "Table does not have a header", Major; seen at WCC on a deck
    # that went through .ppt). Like Word's header flag: the first row is marked as the header row.
    for sh in shapes:
        if getattr(sh, 'has_table', False) and sh.has_table:
            tp = sh.table._tbl.tblPr
            if tp.get('firstRow') != '1':
                tp.set('firstRow', '1'); log.append(f'slide {i}: table "{sh.name}" first row marked as its header row (CHECK it is one)')
    # ---- P8: pictures without alt
    for sh in shapes:
        if sh._element.tag == P + 'pic':
            cnv = sh._element.find('.//' + P + 'cNvPr')
            if not (cnv.get('descr') or '').strip() and not is_dec(sh._element):
                log.append(f'slide {i}: picture "{cnv.get("name")}" has no alt text (write it, or mark decorative)')
    # ---- P7: contrast
    # Measured against what is really drawn behind each text box (pptx_bg.Backdrop: slide background, master and
    # layout artwork, and every picture and filled shape below the box). Before this, text on a PHOTO was measured
    # against the slide's plain background color: on a test deck (Nov 15, 2026) white labels on a dark photo
    # were "fixed" to dark gray and WCC's Panorama flagged all 8 (Severe, 0%). Panorama samples the picture.
    slide_bg = bg_color(s)
    ordered = list(leaf_shapes(s.shapes))
    for idx, sh in enumerate(ordered):
        if not sh.has_text_frame or not sh.text_frame.text.strip(): continue
        x0, y0, x1, y1 = box(sh); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        own_el = sh._element.find('./' + P + 'spPr/' + A + 'solidFill')
        own = color_of(own_el)
        under, under_el = own, (own_el if own else None)
        if not under:
            for prev in reversed(ordered[:idx]):
                a0, b0, a1, b1 = box(prev)
                pf_el = prev._element.find('./' + P + 'spPr/' + A + 'solidFill')
                pf = color_of(pf_el)
                if pf and a0 <= cx <= a1 and b0 <= cy <= b1:
                    under, under_el = pf, pf_el; break
        label = sh.text_frame.text.strip().replace(chr(10), ' ').replace(chr(11), ' ')[:30]
        # what is behind the text: a flat color, or a picture (many colors)
        px = [] if own else BACKDROP.pixels(s, sh)
        photo = None
        if px:
            ls = sorted(lum('%02X%02X%02X' % p) for p in px)
            lo, hi = ls[len(ls) // 20], ls[-1 - len(ls) // 20]
            if (hi + .05) / (lo + .05) > 1.15:
                photo = px                                   # varied: a photo, banner or gradient
            else:
                med = sorted(px, key=lambda p: lum('%02X%02X%02X' % p))[len(px) // 2]
                flat = '%02X%02X%02X' % med
                if not under or ratio(flat, under) > 1.05: under, under_el = flat, None
        bgc = under or slide_bg
        if photo is None and bgc is None:
            log.append(f'slide {i}: "{label}" sits on a picture/gradient background: check its contrast by eye')
            continue
        if photo is not None:
            # every run is judged by the worst 10% of the pixels behind the box: it passes if 90% of the
            # background gives 4.5:1. Passing text is left alone (no change to the design).
            def worst(c): 
                cs = sorted(ratio(c, '%02X%02X%02X' % p) for p in photo); return cs[len(cs) // 10]
            mean = '%02X%02X%02X' % tuple(round(sum(p[k] for p in photo) / len(photo)) for k in range(3))
            backed = False
            for p_ in sh.text_frame.paragraphs:
                for r in p_.runs:
                    if not r.text.strip(): continue
                    rpr = r._r.find(A + 'rPr')
                    fg = color_of(rpr.find(A + 'solidFill')) if rpr is not None else None
                    if not fg:
                        if worst(THEME.get('tx1') or '000000') < 4.5:
                            log.append(f'slide {i}: "{label}" (inherited color) sits on a picture: check its contrast by eye')
                        continue
                    if worst(fg) >= 4.5: continue
                    best = max(('FFFFFF', '000000'), key=worst)
                    sf = rpr.find(A + 'solidFill')
                    if worst(best) >= 4.8:
                        log.append(f'slide {i}: "{r.text.strip()[:30]}" {fg} on a picture (worst 10%: {worst(fg):.2f}:1) -> {best} ({worst(best):.2f}:1)')
                        for c in list(sf): sf.remove(c)
                        etree.SubElement(sf, A + 'srgbClr', val=best)
                    elif not backed and sh._element.tag == P + 'sp':
                        # neither white nor black passes over this busy picture: give the text box its own fill,
                        # the picture's average color pushed just far enough from the text color
                        fill = fix_color(mean, fg, 4.5)
                        spPr = sh._element.find('./' + P + 'spPr')
                        for old in spPr.findall(A + 'noFill'): spPr.remove(old)
                        nf = etree.Element(A + 'solidFill'); etree.SubElement(nf, A + 'srgbClr', val=fill)
                        geom = [k for k in spPr if etree.QName(k).localname in ('xfrm', 'custGeom', 'prstGeom')]
                        (geom[-1].addnext(nf) if geom else spPr.insert(0, nf))
                        backed = True
                        log.append(f'slide {i}: "{label}" on a busy picture: added a {fill} box behind the text ({ratio(fg, fill):.2f}:1); CHECK the look')
            if backed:
                # the box is now the background for EVERY run in the shape, not just the one it was chosen for: runs
                # that passed on the picture, or were skipped once the box existed, can fail on it (a title slide's
                # "By" line and two purple words stayed Severe, Nov 17, 2026). Recheck each run against the box.
                for p_ in sh.text_frame.paragraphs:
                    for r in p_.runs:
                        if not r.text.strip(): continue
                        rpr = r._r.get_or_add_rPr()
                        sf = rpr.find(A + 'solidFill')
                        fg = color_of(sf) or (THEME.get('tx1') or '000000')
                        if ratio(fg, fill) >= 4.5: continue
                        new = fix_color(fg, fill, 4.5)
                        if sf is None:
                            sf = etree.Element(A + 'solidFill')
                            after = [k for k in rpr if etree.QName(k).localname in ('ln',)]
                            (after[-1].addnext(sf) if after else rpr.insert(0, sf))
                        for c in list(sf): sf.remove(c)
                        etree.SubElement(sf, A + 'srgbClr', val=new)
                        log.append(f'slide {i}: "{r.text.strip()[:30]}" {fg} on the new {fill} box = {ratio(fg, fill):.2f}:1 -> {new} ({ratio(new, fill):.2f}:1)')
            continue
        for p in sh.text_frame.paragraphs:
            for r in p.runs:
                if not r.text.strip(): continue
                rpr = r._r.find(A + 'rPr')
                fg = color_of(rpr.find(A + 'solidFill')) if rpr is not None else None
                hl = rpr.find(A + 'hlinkClick') if rpr is not None else None
                HLX = '{A12FA001-AC4F-418D-AE19-62706E023703}'
                if hl is not None and not any(e.get('uri') == HLX for e in hl.iter(A + 'ext')):
                    # a link is drawn in the theme's hyperlink color, whatever the run's own color says (WCC flagged
                    # a theme-blue link on a navy slide, Severe). Give the run a passing color and tell PowerPoint
                    # to use it for the link (hlinkClr = tx, PowerPoint 2019+).
                    lc = (THEME.get('hlink') or '0563C1').upper()
                    if ratio(lc, bgc) < 4.5:
                        new = fg if fg and ratio(fg, bgc) >= 4.5 else fix_color(lc, bgc, 4.5)
                        sf = rpr.find(A + 'solidFill')
                        if sf is None:
                            sf = etree.Element(A + 'solidFill')
                            after = [k for k in rpr if etree.QName(k).localname in ('ln',)]
                            (after[-1].addnext(sf) if after else rpr.insert(0, sf))
                        for c in list(sf): sf.remove(c)
                        etree.SubElement(sf, A + 'srgbClr', val=new)
                        lst = hl.find(A + 'extLst')
                        if lst is None: lst = etree.SubElement(hl, A + 'extLst')
                        ext = etree.SubElement(lst, A + 'ext', uri=HLX)
                        AHYP = 'http://schemas.microsoft.com/office/drawing/2018/hyperlinkcolor'
                        etree.SubElement(ext, '{%s}hlinkClr' % AHYP, nsmap={'ahyp': AHYP}, val='tx')
                        log.append(f'slide {i}: link "{r.text.strip()[:30]}" theme color {lc} on {bgc} = {ratio(lc, bgc):.2f}:1 -> {new}')
                        continue
                if not fg: continue
                need = 4.5   # WCAG allows 3:1 for large text, but WCC's Panorama flagged large text at 3.5:1 (Severe)
                if ratio(fg, bgc) < need and under_el is not None and lum(fg) > 0.5 and lum(bgc) < 0.5:
                    # light text on a colored box (white on teal): keep the text white and darken the box instead,
                    # so the design keeps its look. Every run in this box is re-checked against the new fill.
                    nb = fix_color(bgc, fg, need)
                    log.append(f'slide {i}: box behind "{r.text.strip()[:30]}" {bgc} -> {nb} so {fg} text reaches {ratio(fg, nb):.2f}:1')
                    for c in list(under_el): under_el.remove(c)
                    etree.SubElement(under_el, A + 'srgbClr', val=nb); bgc = nb
                if ratio(fg, bgc) < need:
                    new = fix_color(fg, bgc, need)
                    log.append(f'slide {i}: "{r.text.strip()[:30]}" {fg} on {bgc} = {ratio(fg, bgc):.2f}:1 -> {new} ({ratio(new, bgc):.2f}:1)')
                    sf = rpr.find(A + 'solidFill')
                    for c in list(sf): sf.remove(c)
                    etree.SubElement(sf, A + 'srgbClr', val=new)
# ---- P10: link text that is just the URL (Panorama: "The hyperlink text is not descriptive", Major)
for i, s in enumerate(prs.slides, 1):
    for sh in s.shapes:
        if not sh.has_text_frame: continue
        for para in sh.text_frame.paragraphs:
            links = {}
            for r in para.runs:
                if r.hyperlink.address: links.setdefault(r.hyperlink.address, []).append(r.text)
            for url, parts in links.items():
                t = ''.join(parts).strip().rstrip('/')
                bare = re.sub(r'^https?://(www\.)?', '', url).rstrip('/')
                if re.sub(r'^https?://(www\.)?', '', t) == bare or re.fullmatch(r'(click here|here|link|more|read more)', t, re.I):
                    log.append(f'slide {i}: link text "{t}" is the URL; YOU: write descriptive text, e.g. "<Site name> ({bare})"')
# ---- P12 + P5: sizes and language everywhere
def floor_part(el):
    n = 0
    for e in el.iter(A + 'rPr', A + 'defRPr', A + 'endParaRPr'):
        if e.get('sz') and int(e.get('sz')) < 1200:
            e.set('sz', '1200'); n += 1
        if e.tag != A + 'defRPr':
            e.set('lang', 'en-US')
    return n
total = 0
for s in prs.slides: total += floor_part(s._element)
for m in prs.slide_masters:
    total += floor_part(m._element)
    for l in m.slide_layouts: total += floor_part(l._element)
if total: log.append(f'raised {total} font sizes to 12 pt')
for s in prs.slides:
    for r in s._element.iter(A + 'r'):
        if r.find(A + 'rPr') is None:
            r.insert(0, etree.Element(A + 'rPr', lang='en-US'))
cp = prs.core_properties
cand = TITLE or (cp.title if cp.title and cp.title.strip() and cp.title.strip() != 'PowerPoint Presentation' else (titles_text[0] if titles_text else 'Presentation'))
first, _, rest = cand.strip().partition('\n')
if re.fullmatch(r'(chapter|module|week|unit|part|lesson|session)\s+\d+[a-z]?', first.strip(), re.I) and rest.strip():
    cand = first.strip() + ': ' + rest          # "Chapter 12: Managing ..."
cp.title = re.sub(r'\s*[\r\n\v]+\s*', ' ', cand.strip())   # otherwise line breaks become spaces
cp.language = 'en-US'
log.append(f'document title: "{cp.title}"')
print('\n'.join(log))
if not REPORT:
    # tool names never stay in the author fields (python-pptx stamps "python-pptx" / "Steve Canny"); real names stay
    _tools = re.compile(r'^(python-pptx|python-docx|openpyxl|Steve Canny|Un-named)$', re.I)
    if _tools.match((cp.author or '').strip()): cp.author = ''
    if _tools.match((cp.last_modified_by or '').strip()): cp.last_modified_by = cp.author or ''
    prs.save(dst)
    # Files saved by LibreOffice name the core-properties relationship with a non-standard type, so python-pptx
    # adds a second docProps/core.xml. A zip with a duplicate part won't open in LibreOffice (and may not in
    # PowerPoint): keep python-pptx's copy (the last one) and a single core-properties relationship.
    import zipfile as _z
    zi = _z.ZipFile(dst); names = [i.filename for i in zi.infolist()]
    if len(names) != len(set(names)):
        last = {}
        for info in zi.infolist(): last[info.filename] = zi.read(info)     # later entries win
        rels = last.get('_rels/.rels', b'').decode()
        cores = re.findall(r'<Relationship [^>]*Target="/?docProps/core\.xml"[^>]*/>', rels)
        for extra in cores[:-1]: rels = rels.replace(extra, '', 1)
        last['_rels/.rels'] = rels.encode()
        zi.close()
        with _z.ZipFile(dst, 'w', _z.ZIP_DEFLATED) as zo:
            for n, b in last.items(): zo.writestr(n, b)
        log.append('removed a duplicate docProps/core.xml left by a LibreOffice-saved file')
