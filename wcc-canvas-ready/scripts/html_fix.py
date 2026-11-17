"""Measure and fix rendered contrast and font size in an HTML page (CSS included) the way Panorama does.
  python3 html_fix.py page.html                 # audit only: every text element with its computed color,
                                                # background, size and contrast ratio
  python3 html_fix.py page.html out.html --fix  # rewrite the CSS values that fail, re-render, repeat (max 4 passes)
Needs Playwright + Chrome (python -m playwright install chromium if no Chrome is found).
[WCAG + Panorama 1.4.3] contrast (Severe at WCC for HTML): 4.5:1, or 3:1 for >= 24px (18pt) / >= 18.66px bold.
[WCC Panorama] "The font size is smaller than 11 points" (Minor): every text size raised to >= 16px (12pt).
Fixes change values in the page's own CSS (<style> blocks and style="" attributes), so scripts keep working.
A color used on several backgrounds is darkened/lightened until it passes on all of them.
"""
import sys, re, os, json, shutil
from playwright.sync_api import sync_playwright
src = os.path.abspath(sys.argv[1])
FIX = '--fix' in sys.argv
dst = os.path.abspath(sys.argv[2]) if FIX else None
CHROME = next((p for p in ('/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
                           '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome') if os.path.exists(p)), None)   # Mac too

JS = r"""
() => {
  const out = [];
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x)); return {r:p[0], g:p[1], b:p[2], a: p.length > 3 ? p[3] : 1}; };
  const bgOf = el => { let e = el; const layers = [];
    while (e && e.nodeType === 1) { const cs = getComputedStyle(e); const c = parse(cs.backgroundColor);
      if (cs.backgroundImage && cs.backgroundImage !== 'none' && /gradient/.test(cs.backgroundImage)) {
        const m = cs.backgroundImage.match(/rgba?\([^)]+\)/g); if (m) { const g = parse(m[0]); if (g && g.a > 0) layers.push(g); if (g && g.a >= 1) break; } }
      if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; }
      e = e.parentElement; }
    let base = {r:255, g:255, b:255};
    for (let i = layers.length - 1; i >= 0; i--) { const l = layers[i];
      base = {r: l.r*l.a + base.r*(1-l.a), g: l.g*l.a + base.g*(1-l.a), b: l.b*l.a + base.b*(1-l.a)}; }
    return base; };
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode; if (!t.textContent.trim()) continue;
    const el = t.parentElement; if (!el || seen.has(el)) continue; seen.add(el);
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || el.closest('script,style,noscript')) continue;
    const r = el.getBoundingClientRect(); if (r.width === 0 && r.height === 0) continue;
    const fg = parse(cs.color); if (!fg) continue;
    out.push({tag: el.tagName.toLowerCase(), cls: el.className && el.className.baseVal === undefined ? el.className : '',
      id: el.id, text: t.textContent.trim().slice(0, 40), fg, bg: bgOf(el), size: parseFloat(cs.fontSize),
      weight: parseInt(cs.fontWeight) || 400, opacity: parseFloat(cs.opacity)});
  }
  return out;
}"""

def lum(c):
    f = lambda v: (v / 255) / 12.92 if v / 255 <= 0.03928 else ((v / 255 + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c['r']) + 0.7152 * f(c['g']) + 0.0722 * f(c['b'])
def ratio(a, b):
    x, y = lum(a), lum(b); return (max(x, y) + .05) / (min(x, y) + .05)
hexc = lambda c: '#%02x%02x%02x' % (round(c['r']), round(c['g']), round(c['b']))
def need(e): return 3.0 if e['size'] >= 24 or (e['size'] >= 18.66 and e['weight'] >= 700) else 4.5

def audit(path):
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=['--no-sandbox']) if CHROME else p.chromium.launch()
        pg = b.new_page(viewport={'width': 1280, 'height': 900})
        pg.goto('file://' + path); pg.wait_for_timeout(400)
        els = pg.evaluate(JS); b.close()
    bad_c = [e for e in els if ratio(e['fg'], e['bg']) < need(e)]
    bad_s = [e for e in els if e['size'] < 15.99]
    return els, bad_c, bad_s

def mix(c, t, k): return {x: c[x] + (t[x] - c[x]) * k for x in 'rgb'}
def passing(fg, bgs, need_):
    """move fg toward black or white until it passes on every background it sits on"""
    for target in ({'r': 0, 'g': 0, 'b': 0}, {'r': 255, 'g': 255, 'b': 255}):
        for k in range(1, 101):
            c = mix(fg, target, k / 100)
            if all(ratio(c, b) >= n + 0.3 for b, n in zip(bgs, need_)): return c
    return None

def color_variants(h):
    """the ways one color can be written in CSS: #abc / #aabbcc / rgb(...)"""
    r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
    v = [h, h.upper()]
    if h[1] == h[2] and h[3] == h[4] and h[5] == h[6]: v += ['#' + h[1] + h[3] + h[5], ('#' + h[1] + h[3] + h[5]).upper()]
    v += [f'rgb({r}, {g}, {b})', f'rgb({r},{g},{b})']
    return v

def solid_behind_gradients(s):
    """Checkers (Panorama included) can't measure text on a CSS gradient and treat the background as white, so
    light text on a dark gradient fails. After every gradient background, add background-color set to the
    gradient's darkest stop (var() resolved from :root). It paints under the gradient: nothing visible changes."""
    roots = dict(re.findall(r'(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})', s))
    def hx(v):
        v = roots.get(v[4:-1].strip(), v) if v.startswith('var(') else v
        return v if re.fullmatch(r'#[0-9a-fA-F]{6}', v or '') else ('#' + ''.join(c * 2 for c in v[1:4]) if re.fullmatch(r'#[0-9a-fA-F]{3}', v or '') else None)
    def L(h): return lum({'r': int(h[1:3], 16), 'g': int(h[3:5], 16), 'b': int(h[5:7], 16)})
    n = 0
    def rep(m):
        nonlocal n
        decl, rest = m.group(0), m.string[m.end():m.end() + 200]
        if re.match(r'\s*;?\s*background-color\s*:', rest): return decl
        cols = [h for h in (hx(c) for c in re.findall(r'#[0-9a-fA-F]{3,6}\b|var\(--[\w-]+\)', decl)) if h]
        if not cols: return decl
        dark = min(cols, key=L); n += 1
        return decl + f';background-color:{dark}'
    s = re.sub(r'background(?:-image)?\s*:\s*[^;{}"]*?(?:linear|radial|conic)-gradient\((?:[^()]|\([^()]*\))*\)[^;{}"]*', rep, s)
    # A plain color given with the `background` shorthand ("background: white" on a slide card) is not read as the text's
    # background by Panorama, which then measures against the next ancestor's background-color (a dark page body):
    # 49 Severe contrast flags on a slide-viewer page, Nov 17, 2026. Repeat the color as background-color.
    COLOR = r'(?:#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|[a-zA-Z]+)'
    s = re.sub(r'(?<![-\w])background\s*:\s*(' + COLOR + r')\s*(;|(?=}))(?!\s*background-color)',
               lambda m: f'background: {m.group(1)}; background-color: {m.group(1)}' + (';' if m.group(2) == ';' else ''), s)
    return s, n

html_src = open(src, encoding='utf-8').read()
work = dst if FIX else src
if FIX: shutil.copy(src, dst)
for rnd in range(4 if FIX else 1):
    els, bad_c, bad_s = audit(work)
    print(f'pass {rnd + 1}: {len(els)} text elements, contrast failures {len(bad_c)}, under 12 pt {len(bad_s)}')
    for e in bad_c[:12]:
        print(f'   contrast {hexc(e["fg"])} on {hexc(e["bg"])} = {ratio(e["fg"], e["bg"]):.2f} ({e["size"]:.0f}px) <{e["tag"]} class="{e["cls"]}"> {e["text"]!r}')
    for e in bad_s[:6]:
        print(f'   size {e["size"]:.1f}px <{e["tag"]} class="{e["cls"]}"> {e["text"]!r}')
    if not FIX or (not bad_c and not bad_s): break
    s = open(work, encoding='utf-8').read()
    if rnd == 0:
        s, ng = solid_behind_gradients(s)
        if ng: print(f'   solid background-color added under {ng} gradient backgrounds')
    for e in bad_c:
        if e['fg'].get('a', 1) == 0 or e.get('transparent'):
            print(f'   hidden-until-active text <{e["tag"]} class="{e["cls"]}"> {e["text"]!r}: color is transparent;'
                  ' show it with CSS ::before or set its text in the script instead (fix by hand)')
    bad_c = [e for e in bad_c if e['fg'].get('a', 1) != 0]
    # contrast: group failures by text color; choose one replacement that passes on all its backgrounds
    groups = {}
    for e in els:
        groups.setdefault(hexc(e['fg']), []).append(e)
    for e in bad_c:
        h = hexc(e['fg']); members = groups[h]
        new = passing(e['fg'], [m['bg'] for m in members], [need(m) for m in members])
        if not new:
            # light text (white on colored buttons) can't get lighter and is used on many backgrounds: darken the
            # failing elements' own background colors instead (a slide-viewer page's three buttons, Nov 17, 2026)
            done_bg = 0
            for m in [x for x in bad_c if hexc(x['fg']) == h]:
                bh = hexc(m['bg']); k = 0.0; nb = m['bg']
                while ratio(m['fg'], nb) < need(m) + 0.3 and k < 1: k += 0.02; nb = mix(m['bg'], {'r': 0, 'g': 0, 'b': 0}, k)
                nbh = hexc(nb)
                for v in color_variants(bh):
                    s, c_ = re.subn(r'((?<![-\w])background(?:-color)?\s*:\s*(?:[^;{}"]*?\s)?)' + re.escape(v) + r'(?![0-9a-fA-F])', r'\g<1>' + nbh, s); done_bg += c_
                print(f'   {h} text on {bh}: background darkened to {nbh} ({ratio(m["fg"], nb):.2f}:1)')
            if not done_bg: print('   no single color passes for', h)
            continue
        nh = hexc(new); hit = 0
        for v in color_variants(h):
            # only in color declarations, never in background
            s, k = re.subn(r'((?<![-\w])color\s*:\s*)' + re.escape(v) + r'(?![0-9a-fA-F])', r'\g<1>' + nh, s); hit += k
        if hit: print(f'   {h} -> {nh} in {hit} color declarations')
        else: print(f'   {h}: not found as a plain color declaration (variable or inherited); fix by hand')
        groups[nh] = groups.pop(h)
        for m in members: m['fg'] = new
    # sizes: raise px / pt / rem values in font-size and font shorthand
    def up(m):
        n, u = float(m.group(2)), m.group(3)
        px = n * (16 if u == 'rem' else 1.3333 if u == 'pt' else 1)
        if px >= 15.99: return m.group(0)
        nv = {'px': '16px', 'pt': '12pt', 'rem': '1rem'}[u]
        return m.group(1) + nv
    if bad_s:
        s = re.sub(r'(font-size\s*:\s*)([\d.]+)(px|pt|rem)\b', up, s)
        s = re.sub(r'(font\s*:[^;{}"]*?\s)([\d.]+)(px|pt|rem)(?=[\s/])', up, s)
    open(work, 'w', encoding='utf-8').write(s)
