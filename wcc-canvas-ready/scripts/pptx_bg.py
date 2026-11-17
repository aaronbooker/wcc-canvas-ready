"""What is really behind a text box on a slide: a low-resolution composite of the slide background, the master's
and layout's own pictures and filled shapes, and every slide shape drawn before the text box (pictures, filled
shapes, groups). Used by pptx_fix.py (P7) to measure contrast against photos and banners, not just solid fills.

  from pptx_bg import Backdrop
  bd = Backdrop(prs)                       # once per deck
  img = bd.behind(slide, shape)            # PIL RGB image of the slide with everything under `shape` painted
  px  = bd.pixels(slide, shape)            # list of (r,g,b) under the shape's text area
"""
import io
from PIL import Image, ImageDraw
from lxml import etree

NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
A = '{%s}' % NS['a']; P = '{%s}' % NS['p']; R = '{%s}' % NS['r']
DRAW = (P + 'sp', P + 'pic', P + 'grpSp', P + 'graphicFrame', P + 'cxnSp')


class Backdrop:
    def __init__(self, prs, color_of, slide_bg, width_px=960):
        self.prs = prs
        self.color_of = color_of          # pptx_fix's resolver: <a:solidFill> element -> 'RRGGBB' (theme-aware)
        self.slide_bg = slide_bg          # pptx_fix's bg_color(slide): 'RRGGBB' or None (picture/gradient)
        self.k = width_px / prs.slide_width
        self.W = width_px
        self.H = max(1, round(prs.slide_height * self.k))
        self._img = {}

    # ---------- painting ----------
    def _image(self, part, rid):
        key = (id(part), rid)
        if key not in self._img:
            try:
                ip = part.related_part(rid)
                im = Image.open(io.BytesIO(ip.blob))
                im.load()
                self._img[key] = im.convert('RGBA')
            except Exception:
                self._img[key] = None
        return self._img[key]

    def _bg_fill(self, slide):
        """background color, or a picture for a picture background"""
        for part in (slide, slide.slide_layout, slide.slide_layout.slide_master):
            bg = part._element.find('.//' + P + 'bg')
            if bg is None: continue
            blip = bg.find('.//' + A + 'blip')
            if blip is not None and blip.get(R + 'embed'):
                im = self._image(part.part, blip.get(R + 'embed'))
                if im is not None: return im
            g = bg.find('.//' + A + 'gradFill')
            if g is not None:   # average of the stops: rough, but better than white
                cs = [self.color_of(gs) for gs in g.iter(A + 'gs')]
                cs = [c for c in cs if c]
                if cs:
                    rgb = [sum(int(c[i:i + 2], 16) for c in cs) // len(cs) for i in (0, 2, 4)]
                    return '%02X%02X%02X' % tuple(rgb)
            break
        return self.slide_bg(slide) or 'FFFFFF'

    def _xf(self, el, tr):
        """box of el in slide EMU, through the group transforms in tr"""
        xf = el.find('./' + P + 'xfrm') if el.tag == P + 'graphicFrame' else el.find('./*/' + A + 'xfrm')
        if xf is None: return None
        off, ext = xf.find(A + 'off'), xf.find(A + 'ext')
        if off is None or ext is None: return None
        x, y, w, h = int(off.get('x')), int(off.get('y')), int(ext.get('cx')), int(ext.get('cy'))
        for (ox, oy, sx, sy, cx, cy) in reversed(tr):
            x, y, w, h = ox + (x - cx) * sx, oy + (y - cy) * sy, w * sx, h * sy
        return x, y, w, h

    def _paint(self, canvas, part, el, tr):
        if el.tag == P + 'grpSp':
            g = el.find('./' + P + 'grpSpPr/' + A + 'xfrm')
            t = list(tr)
            if g is not None:
                off, ext, co, ce = (g.find(A + k) for k in ('off', 'ext', 'chOff', 'chExt'))
                if None not in (off, ext, co, ce) and int(ce.get('cx')) and int(ce.get('cy')):
                    t.append((int(off.get('x')), int(off.get('y')),
                              int(ext.get('cx')) / int(ce.get('cx')), int(ext.get('cy')) / int(ce.get('cy')),
                              int(co.get('x')), int(co.get('y'))))
            for k in el:
                if k.tag in DRAW: self._paint(canvas, part, k, t)
            return
        b = self._xf(el, tr)
        if b is None: return
        x, y, w, h = [v * self.k for v in b]
        if w < 1 or h < 1: return
        box = (round(x), round(y), round(x + w), round(y + h))
        if el.tag == P + 'pic' or (el.tag == P + 'sp' and el.find('./' + P + 'spPr/' + A + 'blipFill') is not None):
            blip = el.find('.//' + A + 'blip')
            rid = blip.get(R + 'embed') if blip is not None else None
            im = self._image(part, rid) if rid else None
            if im is None: return
            src = el.find('.//' + A + 'srcRect')
            if src is not None:
                W0, H0 = im.size
                l, t_, r, bo = (int(src.get(k, '0')) / 100000 for k in ('l', 't', 'r', 'b'))
                cb = (round(W0 * l), round(H0 * t_), round(W0 * (1 - r)), round(H0 * (1 - bo)))
                if cb[2] > cb[0] and cb[3] > cb[1]: im = im.crop(cb)
            im = im.resize((max(1, box[2] - box[0]), max(1, box[3] - box[1])))
            canvas.alpha_composite(im, (box[0], box[1])) if box[0] >= 0 and box[1] >= 0 else \
                canvas.paste(im, (box[0], box[1]), im)
            return
        if el.tag == P + 'sp' and el.find('./' + P + 'spPr/' + A + 'gradFill') is not None:
            # gradient fills (Google Slides boxes: one dark color going from half to fully opaque) were skipped, so text on
            # them was measured against the photo underneath and recolored black on a near-black box (Severe, Nov 17, 2026)
            gf = el.find('./' + P + 'spPr/' + A + 'gradFill'); stops = []
            for gs in gf.iter(A + 'gs'):
                kid = next((k for k in gs if k.tag in (A + 'srgbClr', A + 'schemeClr', A + 'sysClr', A + 'prstClr')), None)
                c = self.color_of(gs) if kid is not None else None
                if not c: continue
                al = kid.find(A + 'alpha'); a_ = round(255 * int(al.get('val')) / 100000) if al is not None else 255
                stops.append((int(gs.get('pos', '0')) / 100000, tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)), a_))
            if not stops: return
            stops.sort()
            lin = gf.find(A + 'lin'); ang = int(lin.get('ang', '0')) if lin is not None else 0
            vertical = 2700000 <= ang % 10800000 <= 8100000
            W_, H_ = max(1, box[2] - box[0]), max(1, box[3] - box[1]); n = H_ if vertical else W_
            ov = Image.new('RGBA', canvas.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
            for i in range(n):
                t = i / max(1, n - 1)
                lo = max([st for st in stops if st[0] <= t] or [stops[0]]); hi = min([st for st in stops if st[0] >= t] or [stops[-1]])
                f = 0 if hi[0] == lo[0] else (t - lo[0]) / (hi[0] - lo[0])
                col = tuple(round(lo[1][j] + (hi[1][j] - lo[1][j]) * f) for j in range(3)) + (round(lo[2] + (hi[2] - lo[2]) * f),)
                if vertical: d.line([(box[0], box[1] + i), (box[2], box[1] + i)], fill=col)
                else: d.line([(box[0] + i, box[1]), (box[0] + i, box[3])], fill=col)
            canvas.alpha_composite(ov)
            return
        if el.tag == P + 'sp':
            sp = el.find('./' + P + 'spPr')
            sf = sp.find(A + 'solidFill') if sp is not None else None
            c = self.color_of(sf) if sf is not None else None
            if not c:   # style fill (fillRef) on shapes with no spPr fill
                st = el.find('./' + P + 'style/' + A + 'fillRef')
                if st is not None and sp is not None and sp.find(A + 'noFill') is None and int(st.get('idx', '0')) > 0:
                    c = self.color_of(st)
            if not c: return
            alpha = 255
            a_el = sf.find('.//' + A + 'alpha') if sf is not None else None
            if a_el is not None: alpha = round(255 * int(a_el.get('val')) / 100000)
            ov = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            ImageDraw.Draw(ov).rectangle(box, fill=tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,))
            canvas.alpha_composite(ov)

    def behind(self, slide, shape_el):
        """the slide as drawn up to (not including) shape_el"""
        bg = self._bg_fill(slide)
        if isinstance(bg, str):
            canvas = Image.new('RGBA', (self.W, self.H), tuple(int(bg[i:i + 2], 16) for i in (0, 2, 4)) + (255,))
        else:
            canvas = Image.new('RGBA', (self.W, self.H), (255, 255, 255, 255))
            canvas.alpha_composite(bg.resize((self.W, self.H)))
        lay, mas = slide.slide_layout, slide.slide_layout.slide_master
        show = lambda e: e.get('showMasterSp', '1') not in ('0', 'false')
        layers = []
        if show(slide._element) and show(lay._element): layers.append(mas)
        if show(slide._element): layers.append(lay)
        for part in layers:   # master/layout artwork (not placeholders)
            for el in part.shapes._spTree:
                if el.tag in DRAW and el.find('.//' + P + 'nvPr/' + P + 'ph') is None:
                    self._paint(canvas, part.part, el, [])
        self._upto(canvas, slide.part, slide.shapes._spTree, shape_el, [])
        return canvas.convert('RGB')

    def _upto(self, canvas, part, parent, target, tr):
        """paint parent's children up to target; returns True once target is reached (inside groups too)"""
        for el in parent:
            if el.tag not in DRAW: continue
            if el is target: return True
            if el.tag == P + 'grpSp' and any(d is target for d in el.iter()):
                g = el.find('./' + P + 'grpSpPr/' + A + 'xfrm'); t = list(tr)
                if g is not None:
                    off, ext, co, ce = (g.find(A + k) for k in ('off', 'ext', 'chOff', 'chExt'))
                    if None not in (off, ext, co, ce) and int(ce.get('cx')) and int(ce.get('cy')):
                        t.append((int(off.get('x')), int(off.get('y')),
                                  int(ext.get('cx')) / int(ce.get('cx')), int(ext.get('cy')) / int(ce.get('cy')),
                                  int(co.get('x')), int(co.get('y'))))
                return self._upto(canvas, part, el, target, t)
            self._paint(canvas, part, el, tr)
        return False

    def pixels(self, slide, shape, box=None):
        """pixels under the shape's text area (box minus the text insets)"""
        img = self.behind(slide, shape._element)
        if box is None:
            bp = shape._element.find('.//' + A + 'bodyPr')
            ins = lambda k, d: int(bp.get(k)) if bp is not None and bp.get(k) else d
            x0 = shape.left + ins('lIns', 91440); x1 = shape.left + shape.width - ins('rIns', 91440)
            y0 = shape.top + ins('tIns', 45720); y1 = shape.top + shape.height - ins('bIns', 45720)
            box = (x0, y0, x1, y1)
        b = [round(v * self.k) for v in box]
        b = (max(0, b[0]), max(0, b[1]), min(self.W, max(b[2], b[0] + 1)), min(self.H, max(b[3], b[1] + 1)))
        if b[2] <= b[0] or b[3] <= b[1]: return []
        return list(img.crop(b).getdata())


def deck_colors(prs):
    """(color_of, bg_color) for decks checked outside pptx_fix.py (pre-flight): theme-aware color resolver and the
    slide's flat background color (None for a picture or gradient background)."""
    def theme_of(master):
        t = {}
        for rel in master.part.rels.values():
            if rel.reltype.endswith('/theme'):
                x = etree.fromstring(rel.target_part.blob)
                for el in x.iter():
                    if el.getparent() is not None and el.getparent().tag == A + 'clrScheme':
                        c = el.find(A + 'srgbClr'); s_ = el.find(A + 'sysClr')
                        t[etree.QName(el).localname] = c.get('val') if c is not None else (s_.get('lastClr') if s_ is not None else None)
        cm = master._element.find(P + 'clrMap')
        mp = dict(cm.attrib) if cm is not None else {}
        for k, d in (('tx1', 'dk1'), ('bg1', 'lt1'), ('tx2', 'dk2'), ('bg2', 'lt2')): t[k] = t.get(mp.get(k, d))
        return t
    # one theme per slide master (a Google Slides deck had two with opposite light/dark colors, Nov 17, 2026);
    # bg_color(slide) switches to the slide's own master, so call it first for each slide
    themes = {id(m._element): theme_of(m) for m in prs.slide_masters}
    th = dict(themes[id(prs.slide_masters[0]._element)])

    def color_of(el):
        if el is None: return None
        s = el.find(A + 'srgbClr')
        if s is not None: return s.get('val').upper()
        s = el.find(A + 'schemeClr')
        if s is not None: return (th.get(s.get('val')) or '').upper() or None
        return None

    def bg_color(slide):
        th.clear(); th.update(themes.get(id(slide.slide_layout.slide_master._element), {}))
        for part in (slide, slide.slide_layout, slide.slide_layout.slide_master):
            bg = part._element.find('.//' + P + 'bg')
            if bg is None: continue
            if bg.find('.//' + A + 'blipFill') is not None or bg.find('.//' + A + 'gradFill') is not None: return None
            c = color_of(bg.find('.//' + A + 'solidFill')) or color_of(bg.find(P + 'bgRef'))
            if c: return c
        return 'FFFFFF'
    return color_of, bg_color


def _lum(rgb):
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = [v / 255 for v in rgb]
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def worst_contrast(fg_hex, pixels, share=10):
    """contrast that (100 - share)% of the background pixels reach against fg_hex"""
    fl = _lum(tuple(int(fg_hex[i:i + 2], 16) for i in (0, 2, 4)))
    cs = sorted((max(fl, l) + .05) / (min(fl, l) + .05) for l in (_lum(p) for p in pixels))
    return cs[len(cs) * share // 100] if cs else 21.0


def leaf_shapes(shapes):
    """every shape in drawing order, with group children in place of their groups"""
    for sh in shapes:
        if sh.shape_type == 6:      # MSO_SHAPE_TYPE.GROUP
            yield from leaf_shapes(sh.shapes)
        else:
            yield sh
