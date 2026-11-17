"""Excel cell colors as WCC's Panorama judges them. Used by xlsx_fix.py (fixes) and fix_report.py (prediction).

Book(files) reads an unzipped .xlsx ({part name: bytes}) and resolves every text cell's font color and solid fill
(theme colors with tints, indexed colors, rgb). audit() lists:
  ('contrast', sheet, ref, ratio, fg, bg)  text under 4.5:1 against its fill (4.5 for every size: Panorama's
                                           Excel threshold isn't known, and 4.5 always passes)
  ('rich', sheet, ref, bg)                 rich text (words formatted differently inside one cell) on a solid fill.
                                           WCC Panorama, Nov 16 2026: 4 such legend cells were flagged "Insufficient
                                           contrast" (Major) with black text on light fills; giving the runs explicit
                                           colors, dropping their colors, or rewriting the fills did not clear them,
                                           making them plain text did (5 -> 1 instance).
  ('colored', sheet, ref, ratio, fg, bg)   colored text that passes 4.5:1 on a colored fill but is well short of
                                           black/white. WCC Panorama, Nov 16 2026: dark teal on light peach at
                                           7.97:1 was flagged in 1 of 11 identical cells; black passed. A risk, not a
                                           certainty.
links() lists hyperlinked cells (sheet, part, ref, shown text, address); bare_url(text) says whether the shown
text is just a web address (WCC Panorama, Nov 16 2026: "The hyperlink text is not descriptive", Major, for three
cells showing their URL).
"""
import re, colorsys

INDEXED = ['000000', 'FFFFFF', 'FF0000', '00FF00', '0000FF', 'FFFF00', 'FF00FF', '00FFFF',
           '000000', 'FFFFFF', 'FF0000', '00FF00', '0000FF', 'FFFF00', 'FF00FF', '00FFFF',
           '800000', '008000', '000080', '808000', '800080', '008080', 'C0C0C0', '808080',
           '9999FF', '993366', 'FFFFCC', 'CCFFFF', '660066', 'FF8080', '0066CC', 'CCCCFF',
           '000080', 'FF00FF', 'FFFF00', '00FFFF', '800080', '800000', '008080', '0000FF',
           '00CCFF', 'CCFFFF', 'CCFFCC', 'FFFF99', '99CCFF', 'FF99CC', 'CC99FF', 'FFCC99',
           '3366FF', '33CCCC', '99CC00', 'FFCC00', 'FF9900', 'FF6600', '666699', '969696',
           '003366', '339966', '003300', '333300', '993300', '993366', '333399', '333333']
# SpreadsheetML theme indexes swap the first two pairs of the theme's color scheme (0 = lt1, 1 = dk1)
THEME_ORDER = ('lt1', 'dk1', 'lt2', 'dk2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6', 'hlink', 'folHlink')
NEED = 4.5


def lum(h):
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a, b):
    x, y = lum(a), lum(b)
    return (max(x, y) + .05) / (min(x, y) + .05)


def tint(h, t):
    if not t:
        return h
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    l = l * (1 + t) if t < 0 else l * (1 - t) + t
    return '%02X%02X%02X' % tuple(round(c * 255) for c in colorsys.hls_to_rgb(hh, l, s))


def fix_color(fg, bg, need=NEED):
    """Move fg toward black or white (whichever can pass) just far enough to clear need, with a small margin."""
    target = '000000' if ratio('000000', bg) >= ratio('FFFFFF', bg) else 'FFFFFF'
    a = [int(fg[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(target[i:i + 2], 16) for i in (0, 2, 4)]
    for k in range(1, 101):
        c = ''.join('%02X' % round(x + (y - x) * k / 100) for x, y in zip(a, b))
        if ratio(c, bg) >= need + 0.3:
            return c
    return target


def _items(xml, tag):
    sect = re.search(r'<%ss\b[^>]*?(?:/>|>.*?</%ss>)' % (tag, tag), xml, re.S)
    return re.findall(r'<%s\b[^>]*?(?:/>|>.*?</%s>)' % (tag, tag), sect.group(0), re.S) if sect else []


class Book:
    def __init__(self, files):
        self.files = files
        th = files.get('xl/theme/theme1.xml', b'').decode()
        scheme = re.search(r'<a:clrScheme\b.*?</a:clrScheme>', th, re.S)
        slots = {}
        for n in THEME_ORDER:
            m = scheme and re.search(r'<a:%s>(.*?)</a:%s>' % (n, n), scheme.group(0), re.S)
            v = m and (re.search(r'srgbClr val="([0-9A-Fa-f]{6})"', m.group(1)) or re.search(r'lastClr="([0-9A-Fa-f]{6})"', m.group(1)))
            slots[n] = v.group(1).upper() if v else ('000000' if n.startswith('dk') else 'FFFFFF')
        self.theme = [slots[n] for n in THEME_ORDER]
        self.styles = files['xl/styles.xml'].decode()
        custom = re.search(r'<indexedColors>(.*?)</indexedColors>', self.styles, re.S)
        self.indexed = [c[-6:].upper() for c in re.findall(r'rgb="([0-9A-Fa-f]{6,8})"', custom.group(1))] if custom else INDEXED
        self.fonts = _items(self.styles, 'font')
        self.fills = _items(self.styles, 'fill')
        cx = re.search(r'<cellXfs\b.*?</cellXfs>', self.styles, re.S)
        self.xfs = re.findall(r'<xf\b[^>]*?(?:/>|>.*?</xf>)', cx.group(0), re.S) if cx else []
        ss = files.get('xl/sharedStrings.xml', b'').decode()
        self.sis = re.findall(r'<si>(.*?)</si>', ss, re.S)
        wb = files['xl/workbook.xml'].decode()
        rels = files['xl/_rels/workbook.xml.rels'].decode()
        self.sheets = []
        for name, rid in re.findall(r'<sheet [^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wb):
            t = re.search(r'Id="%s"[^>]*Target="([^"]+)"' % rid, rels) or re.search(r'Target="([^"]+)"[^>]*Id="%s"' % rid, rels)
            if t:
                self.sheets.append((name, 'xl/' + t.group(1).lstrip('/').replace('xl/', '')))

    def color(self, attrs, default):
        if attrs is None:
            return default
        a = dict(re.findall(r'(\w+)="([^"]*)"', attrs))
        if 'rgb' in a:
            base = a['rgb'][-6:].upper()
        elif 'theme' in a and int(a['theme']) < len(self.theme):
            base = self.theme[int(a['theme'])]
        elif 'indexed' in a:
            i = int(a['indexed'])
            base = self.indexed[i] if i < len(self.indexed) else ('000000' if i == 64 else 'FFFFFF')
        else:
            base = default
        return tint(base, float(a.get('tint', 0)))

    def xf(self, s):
        x = self.xfs[s] if s < len(self.xfs) else ''
        fo = re.search(r'fontId="(\d+)"', x); fi = re.search(r'fillId="(\d+)"', x)
        return int(fo.group(1)) if fo else 0, int(fi.group(1)) if fi else 0

    def font_color(self, fo):
        c = re.search(r'<color\b([^>]*?)/?>', self.fonts[fo]) if fo < len(self.fonts) else None
        return self.color(c.group(1) if c else None, '000000')

    def fill_color(self, fi):
        """The color of a solid fill, or None (no fill, patterns, gradients)."""
        f = self.fills[fi] if fi < len(self.fills) else ''
        if 'patternType="solid"' not in f:
            return None
        fg = re.search(r'<fgColor\b([^>]*?)/?>', f)
        return self.color(fg.group(1) if fg else None, 'FFFFFF')

    def cells(self):
        """(sheet name, part, ref, style index, text, rich text?, shared-string index or None) for every text cell."""
        for name, part in self.sheets:
            x = self.files[part].decode()
            for m in re.finditer(r'<c r="([A-Z]+\d+)"([^>]*?)(?:/>|>(.*?)</c>)', x, re.S):
                ref, attrs, body = m.group(1), m.group(2), m.group(3) or ''
                s = re.search(r'\bs="(\d+)"', attrs)
                s = int(s.group(1)) if s else 0
                si, rich = None, False
                if 't="s"' in attrs:
                    v = re.search(r'<v>(\d+)</v>', body)
                    if not v or int(v.group(1)) >= len(self.sis):
                        continue
                    si = int(v.group(1))
                    raw = self.sis[si]
                elif 't="inlineStr"' in attrs:
                    raw = body
                else:
                    v = re.search(r'<v>(.*?)</v>', body)
                    raw = v.group(1) if v else ''
                rich = '<r>' in raw
                text = re.sub(r'<[^>]+>', '', raw)
                if text.strip():
                    yield name, part, ref, s, text, rich, si

    def audit(self):
        out = []
        for name, part, ref, s, text, rich, si in self.cells():
            fo, fi = self.xf(s)
            bg = self.fill_color(fi)
            if rich and bg:
                out.append(('rich', name, ref, bg))
            fg = self.font_color(fo)
            r = ratio(fg, bg or 'FFFFFF')
            if r < NEED:
                out.append(('contrast', name, ref, round(r, 2), fg, bg or 'FFFFFF'))
            elif bg and bg not in ('000000', 'FFFFFF') and r < 0.85 * max(ratio('000000', bg), ratio('FFFFFF', bg)):
                out.append(('colored', name, ref, round(r, 2), fg, bg))
        return out


BARE = re.compile(r'^(?:(?:https?|ftp)://\S+|www\.\S+|[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}(?:[/?#]\S*)?)$')

def bare_url(text):
    """True when link text is only an address (https://..., www..., example.com/page). E-mail addresses are not:
    Panorama didn't flag them in Word."""
    t = (text or '').strip()
    return bool(t) and '@' not in t and bool(BARE.match(t))

def _refs(rng):
    """'B4' -> ['B4']; 'B4:C5' -> every cell in the block."""
    if ':' not in rng: return [rng]
    (c1, r1), (c2, r2) = [re.match(r'([A-Z]+)(\d+)', x).groups() for x in rng.split(':')]
    num = lambda c: sum((ord(ch) - 64) * 26 ** i for i, ch in enumerate(reversed(c)))
    col = lambda n: (col((n - 1) // 26) if n > 26 else '') + chr(65 + (n - 1) % 26)
    return [f'{col(c)}{r}' for c in range(num(c1), num(c2) + 1) for r in range(int(r1), int(r2) + 1)]

def links(book):
    """(sheet, part, ref, shown text, address) for every cell under a <hyperlink>."""
    text = {(p, r): t for _, p, r, _, t, _, _ in book.cells()}
    out = []
    for name, part in book.sheets:
        x = book.files[part].decode()
        rels_part = re.sub(r'([^/]+)$', r'_rels/\1.rels', part)
        rels = book.files.get(rels_part, b'').decode()
        for h in re.findall(r'<hyperlink\b[^>]*>', x):
            rng = re.search(r'\bref="([^"]+)"', h)
            if not rng: continue
            rid = re.search(r'\br:id="([^"]+)"', h)
            addr = ''
            if rid:
                t = re.search(r'<Relationship\b[^>]*Id="%s"[^>]*>' % re.escape(rid.group(1)), rels)
                t = t and re.search(r'Target="([^"]*)"', t.group(0))
                addr = t.group(1) if t else ''
            loc = re.search(r'\blocation="([^"]*)"', h)
            addr = addr or (loc.group(1) if loc else '')
            for ref in _refs(rng.group(1)):
                if (part, ref) in text:
                    out.append((name, part, ref, text[(part, ref)], addr))
    return out
