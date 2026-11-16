"""Panorama pre-flight for an HTML page (Canvas page body or uploaded .html). Usage: python3 preflight_html.py page.html
Checks what WCC Panorama flagged plus YuJa's published HTML checklist. Reports; changes nothing.
"""
import sys, re, html
from html.parser import HTMLParser
src = open(sys.argv[1], encoding='utf-8', errors='replace').read()
ok = lambda b: 'OK  ' if b else 'FAIL'
body = re.sub(r'<(script|style)\b.*?</\1>', '', src, flags=re.S | re.I)
text = html.unescape(re.sub(r'<[^>]+>', ' ', body))
words = len(re.findall(r'\w+', text))
full = bool(re.search(r'<html\b', src, re.I))
if full:
    print(ok(re.search(r'<html\b[^>]*\blang="[^"]+"', src, re.I)), 'H0 <html lang> set')
    print(ok(re.search(r'<title>\s*\S', src, re.I)), 'H0 <title> present')

class P(HTMLParser):
    def __init__(s):
        super().__init__(); s.links = []; s.cur = None; s.heads = []; s.imgs = []; s.tables = []; s.tbl = None
        s.hcur = None
    def handle_starttag(s, t, a):
        a = dict(a)
        if t == 'a' and a.get('href') is not None: s.cur = [a.get('href'), '', a.get('aria-label') or '', a.get('title') or '']
        if re.fullmatch(r'h[1-6]', t): s.heads.append(int(t[1])); s.hcur = ''
        if t == 'img':
            s.imgs.append((a.get('src', ''), a.get('alt'), a.get('role')))
            if s.cur is not None: s.cur[1] += a.get('alt') or ''
        if t == 'table': s.tbl = {'caption': False, 'th': 0, 'cells': 0, 'text': ''}
        if s.tbl is not None:
            if t == 'caption': s.tbl['caption'] = True
            if t == 'th': s.tbl['th'] += 1
            if t in ('td', 'th'): s.tbl['cells'] += 1
    def handle_endtag(s, t):
        if t == 'a' and s.cur is not None: s.links.append(tuple(s.cur)); s.cur = None
        if t == 'table' and s.tbl is not None: s.tables.append(s.tbl); s.tbl = None
    def handle_data(s, d):
        if s.cur is not None: s.cur[1] += d
        if s.tbl is not None: s.tbl['text'] += d
p = P(); p.feed(body)

WEAK = re.compile(r'^(click here|here|link|read|read more|more|learn more|this|this link|go|download|info|details)$', re.I)
weak, empty, dup = [], [], []
prev = None
for href, t, aria, title in p.links:
    t2 = ' '.join(t.split())
    if not t2 and not aria.strip(): empty.append(href)
    elif WEAK.match(t2) or re.fullmatch(r'(https?://|www\.)\S+', t2) or re.fullmatch(r'[\w.-]+\.(com|org|edu|net|gov|io|us)(/\S*)?', t2) \
            or re.search(r'\.(pdf|docx?|pptx?|xlsx?)$', t2, re.I):
        weak.append(t2)
    if prev and prev == href and not href.startswith('#'): dup.append(href)
    prev = href
print(ok(not weak), 'H1 link text not descriptive (Major):', weak[:10])
print(ok(not empty), 'H2 empty links (Major):', empty[:10])
print(ok(not dup), 'H6 adjacent links to the same URL (Minor):', dup[:5])
ext = [h for h, *_ in p.links if re.match(r'https?://(www\.)?(instagram|facebook|linkedin|x|twitter|tiktok)\.com', h or '')]
print('NOTE', 'H3 links Panorama may call broken (sites that block checkers, 429):', ext[:5])
print(ok(words <= 3000), f'H4 page length {words} words (Minor over 3000)')
print(ok(not re.search(r'panorama-html|MuiList', src)), 'H5 no pasted Panorama report markup')
noalt = [s for s, alt, role in p.imgs if alt is None and role != 'presentation']
badalt = [alt for s, alt, role in p.imgs if alt and (len(alt) > 120 or re.search(r'\.(png|jpe?g|gif|svg|webp)$', alt, re.I)
          or re.fullmatch(r'(image|picture|photo|graphic|img)\s*\d*', alt, re.I))]
print(ok(not noalt), 'H7 images without alt (Major):', noalt[:5])
print(ok(not badalt), 'H8 alt text that is a filename, a placeholder or over 120 characters (Major):', [a[:40] for a in badalt[:5]])
print(ok(all(t['caption'] for t in p.tables)), f'H9 tables with a <caption>: {sum(t["caption"] for t in p.tables)}/{len(p.tables)}')
print(ok(all(t['th'] for t in p.tables)), f'H10 tables with header cells <th>: {sum(bool(t["th"]) for t in p.tables)}/{len(p.tables)}')
print(ok(all(t['text'].strip() for t in p.tables)), 'H11 no empty tables')
skips = [(a, b) for a, b in zip(p.heads, p.heads[1:]) if b > a + 1]
print(ok(not skips), 'H12 heading levels nested, no skips (Minor):', skips[:5], '| sequence starts at', p.heads[:1])
# color contrast of inline styles on white (only the simple case: color set, no background)
def lum(h):
    h = h.lstrip('#'); h = ''.join(c * 2 for c in h) if len(h) == 3 else h
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
bad = set()
for st in re.findall(r'style="([^"]*)"', body):
    c = re.search(r'(?<![-\w])color:\s*(#[0-9a-fA-F]{3,6})\b', st); bg = re.search(r'background(?:-color)?:\s*(#[0-9a-fA-F]{3,6})\b', st)
    if c:
        r = (max(lum(c.group(1)), lum(bg.group(1) if bg else '#ffffff')) + .05) / (min(lum(c.group(1)), lum(bg.group(1) if bg else '#ffffff')) + .05)
        if r < 4.5: bad.add(f'{c.group(1)} on {bg.group(1) if bg else "#fff (assumed)"} = {r:.2f}')
print(ok(not bad), 'H13 inline text colors under 4.5:1 (check large text and the real background):', sorted(bad)[:8])
