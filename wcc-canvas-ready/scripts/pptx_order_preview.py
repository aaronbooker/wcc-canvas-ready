"""Show the instructor the reading order before it's kept: renders slides with each content shape numbered in the
order a screen reader will read it, so they can say "yes" or "slide 3 should read title, chart, then notes".

  python3 pptx_order_preview.py fixed.pptx outdir [--original original.pptx] [--slides 3,5]

Writes outdir/slide_NN.png (numbered) and outdir/changed.png, a contact sheet of the slides whose order the fixer
changed (all slides if --original isn't given; only --slides if given). Prints, per slide, the order as
"1 Title 1: 'Virtual Machines'  2 Picture 5  3 Text 4: 'Choose boot device…'" so the instructor can answer with
names. Their answer goes back to pptx_fix.py as --keep-order 3,9 (leave as it was) or --order-file order.json.
Decorative shapes (backgrounds, lines) aren't numbered: a screen reader skips them.
Needs LibreOffice (soffice) and pdftoppm.
"""
import sys, os, subprocess, tempfile, glob
from pptx import Presentation
from PIL import Image, ImageDraw, ImageFont

args = sys.argv[1:]
deck, outdir = args[0], args[1]
orig = args[args.index('--original') + 1] if '--original' in args else None
only = {int(x) for x in args[args.index('--slides') + 1].split(',')} if '--slides' in args else None
os.makedirs(outdir, exist_ok=True)

def is_dec(el):
    # the shape's OWN mark only: a group holding one decorative outline is not itself decorative
    c = next(el.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr'), None)
    x = c.xml if c is not None and hasattr(c, 'xml') else ''
    return 'decorative' in x and 'val="1"' in x
def items(s):
    """shapes in reading order; the fixer's "Slide content" group is opened up (a screen reader reads into it)"""
    for sh in s.shapes:
        if is_dec(sh._element): continue
        if sh.shape_type == 6 and sh.name == 'Slide content':
            yield from (c for c in sh.shapes if not is_dec(c._element))
        else:
            yield sh
def order(p):
    return [[(sh.name, (sh.text_frame.text.strip().replace('\n', ' ')[:40] if sh.has_text_frame else '')) for sh in items(s)]
            for s in p.slides]

p = Presentation(deck)
new = order(p)
old = order(Presentation(orig)) if orig else None
changed = [i for i in range(1, len(new) + 1)
           if (only is None or i in only) and (old is None or i > len(old) or [n for n, _ in new[i - 1]] != [n for n, _ in old[i - 1]])]

tmp = tempfile.mkdtemp()
subprocess.run(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', tmp, deck], capture_output=True, timeout=300)
pdf = glob.glob(os.path.join(tmp, '*.pdf'))
if not pdf: sys.exit('could not render the deck (LibreOffice)')
subprocess.run(['pdftoppm', '-r', '60', '-png', pdf[0], os.path.join(tmp, 's')], check=True)
pngs = sorted(glob.glob(os.path.join(tmp, 's-*.png')))
try: font = ImageFont.truetype('DejaVuSans-Bold.ttf', 16)
except OSError: font = ImageFont.load_default()
SW, SH = p.slide_width, p.slide_height
tiles = []
for i in changed:
    if i - 1 >= len(pngs): continue
    s = p.slides[i - 1]
    im = Image.open(pngs[i - 1]).convert('RGB'); d = ImageDraw.Draw(im)
    sx, sy = im.width / SW, im.height / SH; n = 0
    for sh in items(s):
        n += 1
        try: X, Y = int(sh.left * sx), int(sh.top * sy)
        except TypeError: X, Y = 4, 4 + 22 * n
        d.rectangle([X, Y, X + 24, Y + 22], fill=(192, 0, 0)); d.text((X + 5, Y + 2), str(n), fill=(255, 255, 255), font=font)
    d.rectangle([0, 0, 110, 24], fill=(31, 78, 121)); d.text((6, 3), f'Slide {i}', fill=(255, 255, 255), font=font)
    f = os.path.join(outdir, f'slide_{i:02d}.png'); im.save(f); tiles.append(im)
    print(f'slide {i}: ' + '  '.join(f'{k} {nm}' + (f": '{t}'" if t else '') for k, (nm, t) in enumerate(new[i - 1], 1)))
if tiles:
    w, h = tiles[0].size; cols = 3; rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (w * cols, h * rows), 'white')
    for k, t in enumerate(tiles): sheet.paste(t.resize((w, h)), ((k % cols) * w, (k // cols) * h))
    sheet.save(os.path.join(outdir, 'changed.png'))
print(f'{len(tiles)} slides shown ({"order changed by the fixer" if old else "all slides"}); contact sheet: {os.path.join(outdir, "changed.png")}')
