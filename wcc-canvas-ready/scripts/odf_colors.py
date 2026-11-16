"""Last step for OpenDocument files (.odt / .odp / .ods) written by LibreOffice: darken mid-tone text colors that
fail 4.5:1 on white, and raise font sizes under 12 pt. Usage: python3 odf_colors.py in.odp out.odp
Learned at WCC (Nov 2026): a deck that scored 100% as .odp fell to 0% after a round trip through .pptx, because
LibreOffice wrote the master's inherited gray (#808080, 3.95:1) onto every bullet as an explicit color, and
Panorama checks explicit colors (Severe). Light text (white, pale) is left alone: it sits on dark fills.
"""
import sys, re, zipfile
src, dst = sys.argv[1], sys.argv[2]
def lum(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
ratio = lambda h: 1.05 / (lum(h) + 0.05)
def darker(h):
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    for k in range(1, 100):
        n = '%02X%02X%02X' % (int(r * (1 - k / 100)), int(g * (1 - k / 100)), int(b * (1 - k / 100)))
        if ratio(n) >= 5.0: return n
    return '000000'
log = []
def fix(x):
    def col(m):
        h = m.group(2).upper()
        if 0.15 < lum(h) < 0.6 and ratio(h) < 4.5:      # mid-tones only: dark text is fine, light text sits on dark fills
            n = darker(h); log.append(f'#{h} ({ratio(h):.2f}:1) -> #{n} ({ratio(n):.2f}:1)'); return m.group(1) + n.lower()
        return m.group(0)
    x = re.sub(r'(fo:color="#)([0-9a-fA-F]{6})', col, x)
    def size(m):
        v = float(m.group(2))
        if v < 12: log.append(f'{v:g}pt -> 12pt'); return m.group(1) + '12pt'
        return m.group(0)
    return re.sub(r'((?:fo|style):font-size(?:-asian|-complex)?=")([\d.]+)pt', size, x)
z = zipfile.ZipFile(src)
with zipfile.ZipFile(dst, 'w') as o:
    for info in z.infolist():
        b = z.read(info.filename)
        if info.filename in ('content.xml', 'styles.xml'): b = fix(b.decode('utf-8')).encode('utf-8')
        # the mimetype entry must stay first and uncompressed
        o.writestr(info, b, compress_type=zipfile.ZIP_STORED if info.filename == 'mimetype' else zipfile.ZIP_DEFLATED)
print(sorted(set(log)) or 'nothing to change')
