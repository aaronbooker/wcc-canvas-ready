"""The report that goes with every fixed file: what changed and why, what the instructor decided, what still needs
a person, and what Panorama will most likely still flag, with the score that predicts. Written before the file goes
to Canvas, so the instructor isn't surprised by Panorama's score.

  python3 fix_report.py ORIGINAL FIXED [--notes notes.json] [--log fixlog.txt] [--pdf] [--docx] [--out "report.docx"]

ORIGINAL may be in another format (a .pdf rebuilt as .docx, a .doc converted); it is checked only when its type has
a pre-flight. FIXED is what the instructor gets. notes.json (all keys optional, YOU fill it in as you work):
  {"changed":   ["Raised 648 runs to 12 pt", ...],           # anything the scripts' logs don't already say
   "added":     ["Caption 'Table 1: Test results'", ...],    # every piece of text you added
   "removed":   ["Printed page numbers and running heads", ...],   # every piece of text you took out, and why
   "reworded":  ["Link 'https://zoom.us/j/…' now reads 'Office hours Zoom'", ...],   # every visible text you changed
               # The report never claims "nothing was removed": it lists exactly what these three keys record.
   "decisions": [["Split the 3,800-word page?", "No, keep one page"], ...],
   "check":     ["Alt text on slide 4 (diagram)", ...],      # what a person must check
   "not_fixed": [["The font size is smaller than 11 points", "Minor", "Needs the InDesign file"], ...]}
               # severity Severe/Major/Minor counts toward the predicted score; use "Possible" when you aren't sure
               # Panorama will flag it. Slide reading order is judged by this script; don't add it here.
--log: the fixers' printed output, saved as you go (`python3 x.py ... | tee -a fixlog.txt`); its lines are listed.
Prints the COMPLETE report as Markdown for the chat (paste it unedited). Files only on request: --pdf writes
"<fixed> - accessibility report.pdf" (tagged: title, language, headings, table header rows and summaries, 12 pt),
--docx keeps the Word version. Fixer output from --log is tidied: tool noise and zero results dropped, repeats
folded into one line with their slide or page numbers. Predicted score: any Severe -> 0%, any Major -> 30%, Minor only -> 70-99%,
nothing -> 100% (the bands WCC's Panorama used in Nov 2026). It is a prediction: say so.
"""
import sys, os, re, json, subprocess, zipfile, html as H

args = sys.argv[1:]
orig, fixed = args[0], args[1]
opt = lambda k: args[args.index(k) + 1] if k in args else None
notes = json.load(open(opt('--notes'))) if opt('--notes') else {}
def _scrub(x):   # control characters (a vertical tab in a slide title) make python-docx refuse the text
    if isinstance(x, str): return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', x)
    if isinstance(x, list): return [_scrub(v) for v in x]
    if isinstance(x, dict): return {k: _scrub(v) for k, v in x.items()}
    return x
notes = _scrub(notes)
out = opt('--out') or os.path.splitext(fixed)[0] + ' - accessibility report.docx'
logf = opt('--log')
HERE = os.path.dirname(os.path.abspath(__file__))
SEV = {'Severe': 3, 'Major': 2, 'Minor': 1, 'Possible': 0}

def run(script, f):
    try:
        return subprocess.run([sys.executable, os.path.join(HERE, script), f], capture_output=True, text=True,
                               timeout=300).stdout
    except Exception as e:
        return f'(check failed: {e})'

def num(pat, t, d=0):
    m = re.search(pat, t)
    return int(m.group(1)) if m else d

def lst(pat, t):
    m = re.search(pat, t)
    if not m: return []
    try: return eval(m.group(1), {}, {})
    except Exception: return [m.group(1)]

def issues_docx(t):
    I = []
    if re.search(r"D2 title: (False|None|''|\"\")", t): I.append(('The title is missing from the document\'s properties', 'Major', 1))
    if re.search(r'D3 lang core/styles/settings: .*False', t): I.append(('The document language is not set', 'Major', 1))
    if num(r'D5 headings: (\d+)', t, 1) == 0: I.append(('The document does not have any headings', 'Major', 1))
    if lst(r'D7 skips: (\[.*?\])', t): I.append(('The document\'s heading structure is not properly nested', 'Severe', len(lst(r'D7 skips: (\[.*?\])', t))))
    n = num(r'D11 images w/o real alt: (\d+)', t);  n and I.append(('The item does not have an alternative description', 'Severe', n))
    n = num(r'D12 floating images \(wp:anchor\): (\d+)', t);  n and I.append(('The Image is not inline with the text', 'Major', n))
    n = num(r'w/o Header Row flag \(tblLook firstRow\): (\d+)', t);  n and I.append(('Table does not have a header', 'Major', n))
    n = num(r'D15 tables w/o visible caption: (\d+)', t);  n and I.append(('Table does not have a caption', 'Major', n))
    b = lst(r'D17 typed bullets: (\[.*?\])', t);  b and I.append(('This element should be formatted as a list', 'Major', len(b)))
    w = lst(r'D18 weak link text: (\[.*?\])', t);  w and I.append(('The hyperlink text is not descriptive', 'Major', len(w)))
    m = re.search(r'D21 sizes <12pt by part: (\{.*?\})', t)
    if m:
        try: n = sum(eval(m.group(1)).values())
        except Exception: n = 1
        n and I.append(('The font size is smaller than 11 points (this skill uses 12 pt)', 'Minor', n))
    n = num(r'Known failing colors: (\d+)', t);  n and I.append(('Insufficient contrast between foreground text and background', 'Major', n))
    n = num(r'D20 justified: (\d+)', t);  n and I.append(('Justified text', 'Minor', n))
    return I

def issues_pptx(t):
    I = []
    if re.search(r"P4 title: (None|''|\"\")", t): I.append(('The title is missing from the document\'s properties', 'Major', 1))
    if re.search(r"P5 lang: (None|''|\"\")", t): I.append(('The document language is not set', 'Major', 1))
    n = len(re.findall(r'^P2 slide', t, re.M));  n and I.append(('The document does not have slide titles', 'Major', n))
    n = len(re.findall(r'^P8 slide', t, re.M));  n and I.append(('The item does not have an alternative description', 'Severe', n))
    n = len(re.findall(r'^P7 slide', t, re.M));  n and I.append(('Insufficient contrast between foreground text and background', 'Severe', n))
    n = len(re.findall(r'^P12 ', t, re.M));  n and I.append(('The font size is smaller than 11 points (this skill uses 12 pt)', 'Minor', n))
    n = len(re.findall(r'^P11 slide', t, re.M));  n and I.append(('Table does not have a header', 'Major', n))
    n = len(re.findall(r'^P10 slide', t, re.M));  n and I.append(('The hyperlink text is not descriptive', 'Major', n))
    n = len(re.findall(r'^P13 slide', t, re.M));  n and I.append(('Embedded media: captions must be checked by a person', 'Possible', n))
    return I

PDF_MAP = {'F1': ('The title is missing from the document\'s properties', 'Major'), 'F2': ('The document language is not set', 'Major'),
           'F3': ('The document is not tagged', 'Severe'), 'F4': ('The document does not have any headings', 'Major'),
           'F5': ('The item does not have an alternative description', 'Severe'), 'F6': ('Table does not have a summary', 'Minor'),
           'F7': ('Table does not have a header', 'Major'), 'F9': ('The font size is smaller than 11 points', 'Minor'),
           'F10': ('Check reading order (text off the baseline: sub/superscripts)', 'Severe'),
           'F11': ('Check reading order (footnote tags)', 'Severe'), 'F13': ('List item structure is missing', 'Major')}
def issues_pdf(t):
    I = []
    for m in re.finditer(r'^FAIL\s+(F\d+)\s+(.*)$', t, re.M):
        name, sev = PDF_MAP.get(m.group(1), (m.group(2)[:70], 'Minor'))
        if m.group(1) == 'F8': continue                       # untagged drawing: not a Panorama issue by itself
        I.append((name, sev, 1))
    return I

def issues_html(t):
    I = []
    for m in re.finditer(r'^FAIL\s+H\d+\s+(.*?)(?:\((Severe|Major|Minor)[^)]*\))?:?\s*(.*)$', t, re.M):
        name = m.group(1).strip(' :'); sev = m.group(2) or 'Minor'
        I.append((name, sev, 1))
    for m in re.finditer(r'^NOTE\s+H3\s+links Panorama may call broken.*?:\s*(\[.*\])', t, re.M):
        I.append(('The link is broken (sites that block checkers, such as Instagram, can be reported this way)', 'Possible', len(lst(r'(\[.*\])', m.group(1)))))
    return I

def issues_xlsx(f):
    I = []
    try: z = zipfile.ZipFile(f); n = z.namelist()
    except Exception: return I
    core = z.read('docProps/core.xml').decode() if 'docProps/core.xml' in n else ''
    if not re.search(r'<dc:title>[^<]+</dc:title>', core): I.append(('The title is missing from the document\'s properties', 'Major', 1))
    st = z.read('xl/styles.xml').decode() if 'xl/styles.xml' in n else ''
    small = [s for s in re.findall(r'<sz val="([\d.]+)"', st) if float(s) < 12]
    if small: I.append(('The font size is smaller than 11 points (this skill uses 12 pt)', 'Minor', len(small)))
    sh = sorted(x for x in n if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', x))
    if sh and not re.search(r'<c r="A1"[^>]*>\s*<(v|is)>', z.read(sh[0]).decode()):
        I.append(('Sheet does not have text in cell A1', 'Minor', 1))
    for x in n:
        if x.startswith('xl/tables/') and 'headerRowCount="0"' in z.read(x).decode():
            I.append(('Table does not have a header', 'Major', 1))
    for x in n:
        if x.startswith('xl/drawings/drawing') and x.endswith('.xml'):
            k = len(re.findall(r'<xdr:cNvPr\b(?![^>]*descr=)[^>]*>', z.read(x).decode()))
            k and I.append(('The item does not have an alternative description', 'Severe', k))
    return I

def ro_risk(f):
    """Slide reading-order risk. WCC Panorama, Nov 2026: decks with a slide laid out as a grid of separate text boxes
    kept "Check reading order of slide" after column-first ordering (3 of 3). Nov 15, 2026: slides that kept the flag in
    EVERY order (a labelled photo, pictures under a prompt box, a column of photos) cleared when pptx_fix.py put the
    title first and grouped the rest as one unit (3 of 3; whole 29-slide deck 100%). So: busy slides the fixer could
    NOT group (body placeholders, media, a title overlapping the content) are the risk; grouped grids are untested."""
    try:
        from pptx import Presentation
        p = Presentation(f); SH = p.slide_height
    except Exception:
        return []
    dec = lambda x: 'adec:decorative' in x._element.xml and 'val="1"' in x._element.xml
    ungrouped, grids = [], []
    for i, s in enumerate(p.slides, 1):
        t = s.shapes.title
        top = [x for x in s.shapes if not dec(x) and (t is None or x.shape_id != t.shape_id)]
        if len(top) >= 3: ungrouped.append(i)
        leaves = []
        def walk(shs):
            for x in shs:
                if x.shape_type == 6: walk(x.shapes)
                elif not dec(x) and x.top is not None: leaves.append(x)
        walk(s.shapes)
        rows = []
        for x in sorted(leaves, key=lambda x: x.top):
            if rows and abs(x.top - rows[-1][0]) < SH * 0.03: rows[-1][1] += 1
            else: rows.append([x.top, 1])
        if (sum(1 for r in rows if r[1] >= 2) >= 4 or len(leaves) >= 12) and i not in ungrouped: grids.append(i)
    out = []
    if ungrouped:
        out.append(('Check reading order of slide (busy slides the fixer could not group: ' + ', '.join(map(str, ungrouped[:12])) +
                    ('…' if len(ungrouped) > 12 else '') + '; if flagged, a person checks the order, then ticks Verify Reading Order)', 'Possible', len(ungrouped)))
    if grids:
        out.append(('Check reading order of slide (grid-like slides, grouped; grouping a grid is untested: ' + ', '.join(map(str, grids[:12])) + ')', 'Possible', len(grids)))
    return out or [('Check reading order of slide (unlikely: busy slides are grouped as one unit)', 'Possible', 0)]

def convert(f, ext):
    import tempfile
    d = tempfile.mkdtemp()
    subprocess.run(['soffice', '--headless', '--convert-to', ext, '--outdir', d, f], capture_output=True, timeout=300)
    out = os.path.join(d, os.path.splitext(os.path.basename(f))[0] + '.' + ext)
    return out if os.path.exists(out) else None

def check(f):
    e = os.path.splitext(f)[1].lower()
    # older and OpenDocument formats: read back the way Panorama would see the content, plus known format losses
    # (a converted copy loses the language setting, so that check is skipped for these formats)
    nolang = lambda I: None if I is None else [a for a in I if 'language is not set' not in a[0]]
    if e in ('.doc', '.rtf', '.odt'):
        c = convert(f, 'docx'); I = nolang(check(c)) if c else None
        if I is not None and e == '.doc' and '<w:tbl>' in zipfile.ZipFile(c).read('word/document.xml').decode():
            I.append(('Table does not have a header (the .doc format loses the header mark; deliver .docx)', 'Major', 1))
        return I
    if e in ('.ppt', '.odp'):
        c = convert(f, 'pptx'); I = nolang(check(c)) if c else None
        # Panorama rates missing alt text in a .ppt as Major, not Severe (WCC, Nov 2026)
        return None if I is None else [((n, 'Major', k) if e == '.ppt' and 'alternative description' in n else (n, sv, k)) for n, sv, k in I]
    if e in ('.xls', '.ods'):
        c = convert(f, 'xlsx'); I = nolang(check(c)) if c else None
        # converting back to .xlsx adds LibreOffice's 10 pt default style; the .xls/.ods itself scored 100% (3 of 3)
        return None if I is None else [a for a in I if 'font size' not in a[0]]
    if e == '.docx': return issues_docx(run('preflight_docx.py', f))
    if e == '.pptx': return issues_pptx(run('preflight_pptx.py', f)) + ro_risk(f)
    if e == '.pdf': return issues_pdf(run('preflight_pdf.py', f))
    if e in ('.html', '.htm'): return issues_html(run('preflight_html.py', f))
    if e == '.xlsx': return issues_xlsx(f)
    return None

before = check(orig) if os.path.exists(orig) else None
after = check(fixed) or []
for item in notes.get('not_fixed', []):
    name, sev = item[0], (item[1] if len(item) > 1 else 'Major')
    if 'reading order of slide' in name.lower() and any('reading order of slide' in a[0].lower() for a in after):
        continue                       # the deck check above already judged slide order; don't count it twice
    if not any(name.lower()[:30] in a[0].lower() for a in after): after.append((name, sev, None))
worst = max((SEV.get(s, 0) for _, s, _ in after), default=0)
score = {3: '0%', 2: '30%', 1: '70-99%', 0: '100%'}[worst]
fixed_names = []
if before is not None:
    bn = {a[0]: a for a in before}
    an = {a[0] for a in after}
    fixed_names = [(n, s, c) for n, s, c in before if n not in an and s != 'Possible']
_cc = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')   # control characters break the .docx (titles with a vertical tab)
logl = [_cc.sub(' ', l).strip() for l in open(logf, errors='replace') if l.strip()] if logf and os.path.exists(logf) else []
# the fixers' to-do notes ("has no alt text", "needs a title") that the final check shows were done afterwards are
# dropped: left in, a reader sees "no alt text" next to "wrote alt text for 11 pictures"
_open = ' '.join(a[0].lower() for a in after)
if 'alternative description' not in _open:
    logl = [l for l in logl if not re.search(r'has no alt text|no alt / not decorative', l)]
if 'slide titles' not in _open:
    logl = [l for l in logl if not re.search(r'needs a title written by the instructor', l)]

# ---------- the full report, in Markdown, for the chat ----------
base = os.path.basename(fixed)
likely = [a for a in after if a[1] != 'Possible']; maybe = [a for a in after if a[1] == 'Possible']
why = {x[0]: (x[2] if len(x) > 2 else '') for x in notes.get('not_fixed', [])}
md = lambda x: str(x).replace('|', '\\|').replace('\n', ' ')
def mtable(head, rows):
    o = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    o += ['| ' + ' | '.join(md(v) for v in r) + ' |' for r in rows]
    return '\n'.join(o)
M = [f'## Accessibility report: {base}', '',
     f'**Predicted Panorama score: {score}.** This is a prediction from the skill\'s own checks, made before the file '
     'goes to Canvas; Panorama scores it when you upload it. A 100% Panorama score is not proof of WCAG 2.2 AA.', '',
     '### What was fixed', '']
if fixed_names: M += [mtable(['Panorama issue', 'Severity', 'Count'], fixed_names), '']
elif before is None: M += ['The original is a different file type, so it was not checked the same way; the changes are listed below.', '']
else: M += ['The checks found nothing to fix in the original.', '']
def tidy(lines):
    """Fixer output -> readable change list: drop tool noise, and fold per-slide/per-page repeats into one line."""
    noise = re.compile(r'Warning|Traceback|^\s*File "|^/usr/|^return self\.|^\s*\^|^\(|not in JSON: \[\]$')
    keep, groups, order, orig1 = [], {}, [], {}
    merged = []
    for l in lines:                   # a quoted slide text with a line break was printed over two lines: rejoin
        if merged and merged[-1].count('"') % 2 == 1: merged[-1] += ' ' + l.strip()
        else: merged.append(l)
    for l in merged:
        l = l.strip()
        if not l or noise.search(l): continue
        if re.match(r'^(?:[DPFHX]\d+[a-z]? |OK |FAIL |PASS |Known failing|Colors used|Fills used|\s*sizes used)', l): continue  # pre-flight output
        nums = re.findall(r'(?<![\w.])[+-]?\d+(?:\.\d+)?', l)
        if re.search(r'nothing to do|already (?:has|passes)', l) or (nums and all(float(x) == 0 for x in nums)): continue   # nothing happened
        c = re.search(r"Counter\(\{(.*)\}\)", l)
        if c:
            parts = re.findall(r"'((?:[^'\\]|\\.)*)': (\d+)", c.group(1))
            l = l[:c.start()] + '; '.join(f'{a} (×{n})' if int(n) > 1 else a for a, n in parts)
        m = re.match(r'^(slide|page) (\d+): (.*)$', l)
        if not m: keep.append(l); continue
        t = re.sub(r'"[^"]*"', '"…"', m.group(3)); t = re.sub(r'\(\d+ content shapes\)', '', t).strip()
        k = (m.group(1), t)
        if k not in groups: groups[k] = []; order.append(k); orig1[k] = m.group(3)
        groups[k].append(int(m.group(2)))
    def rng(ns):
        ns = sorted(set(ns)); out, a = [], ns[0]
        for x, y in zip(ns, ns[1:] + [None]):
            if y != x + 1: out.append(f'{a}' if a == x else f'{a}–{x}'); a = y
        return ', '.join(out)
    for k in order:
        ns = groups[k]; what = k[1].replace('"…" ', 'text ').replace('"…"', 'text')
        keep.append(f'{k[0].capitalize()} {ns[0]}: ' + orig1[k] if len(ns) == 1 else
                    f'{what[0].upper() + what[1:]} ({k[0]}s {rng(ns)}' + (f'; {len(ns)} times' if len(ns) > len(set(ns)) else '') + ')')
    return keep
ch = notes.get('changed', []) + tidy(logl)
if ch: M += ['Changes made:', ''] + [f'- {x}' for x in ch] + ['']
def text_changes():
    """(heading, intro, items) for the added / removed / reworded sections, from what notes.json records."""
    out = []
    if notes.get('added'): out.append(('Text that was added', 'Added to the file:', notes['added']))
    if notes.get('removed'): out.append(('Text that was removed', 'Taken out of the file, and why:', notes['removed']))
    if notes.get('reworded'): out.append(('Text that was reworded', 'Changed wording that readers will see:', notes['reworded']))
    return out
for h, intro, items in text_changes():
    M += [f'### {h}', '', intro, ''] + [f'- {x}' for x in items] + ['']
if (notes.get('added') or notes.get('removed') or notes.get('reworded')) and not (notes.get('removed') and notes.get('reworded')):
    none = [k for k in ('removed', 'reworded') if not notes.get(k)]
    M += ['No text was recorded as ' + ' or '.join(none) + '.', '']
if notes.get('decisions'):
    M += ['### Your decisions', '', mtable(['Question', 'Your answer'], [tuple(x) if isinstance(x, list) else (x, '') for x in notes['decisions']]), '']
M += ['### What Panorama will likely still flag', '']
if likely:
    M += [mtable(['Panorama issue', 'Severity', 'Count', 'Why it is left'],
                 [(n, s_, c if c else '', why.get(n, 'Found by the final check')) for n, s_, c in likely]), '',
          'Panorama scores a file by its worst issue: any Severe issue gives 0%, any Major issue 30%, and Minor issues only 70% or more.', '']
else: M += ['Nothing expected. The file should score 100% in Panorama.', '']
if maybe:
    M += ['### Panorama might also flag', '', 'Not counted in the predicted score. If Panorama does flag one, here is why and what to do:', '']
    M += [f'- {n}' + (f': {why[n]}' if why.get(n) else '') for n, s_, c in maybe] + ['']
if notes.get('check'):
    M += ['### Check these yourself', '', 'Panorama can\'t judge these, so a person needs to look:', ''] + [f'- {x}' for x in notes['check']] + ['']
print('\n'.join(_scrub(l) for l in M))
want_pdf, want_docx = '--pdf' in args, '--docx' in args
if not (want_pdf or want_docx):
    print('(Report shown above only. Ask the instructor whether they want it as a PDF too: re-run with --pdf.)')
    sys.exit()
final_pdf = os.path.splitext(fixed)[0] + ' - accessibility report.pdf'
if want_pdf and not want_docx:      # the Word file is only a step to the PDF: build it in a scratch folder, never over a real file
    import tempfile
    out = os.path.join(tempfile.mkdtemp(), os.path.basename(os.path.splitext(fixed)[0]) + ' - accessibility report.docx')

# ---------- .docx report ----------
try:
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError:
    print('(python-docx not installed: report printed above only)'); sys.exit()
d = Document()
st = d.styles['Normal']; st.font.name = 'Calibri'; st.font.size = Pt(12)
for s in ('Heading 1', 'Heading 2', 'Title'):
    try:
        d.styles[s].font.color.rgb = RGBColor(0x1F, 0x4E, 0x79); d.styles[s].font.size = Pt(18 if s != 'Heading 2' else 14)
    except KeyError: pass
rpr = d.styles.element.find(qn('w:docDefaults'))
d.core_properties.title = f'Accessibility report: {base}'
d.core_properties.language = 'en-US'
d.core_properties.author = d.core_properties.last_modified_by = ''
_ap = d.add_paragraph
d.add_paragraph = lambda t='', style=None: _ap(_scrub(t), style)
d.add_heading(f'Accessibility report: {_scrub(base)}', level=1)
p = d.add_paragraph(); r = p.add_run('Predicted Panorama score: '); r.bold = True
p.add_run(f'{score}. This is a prediction from the skill\'s own checks, made before the file goes to Canvas; '
          'Panorama scores it when you upload it. A 100% Panorama score is not proof of WCAG 2.2 AA.')
def table(caption, head, rows):
    cp = d.add_paragraph(caption); cp.style = d.styles['Caption'] if 'Caption' in [s.name for s in d.styles] else st
    for rr in cp.runs: rr.font.size = Pt(12); rr.bold = True; rr.font.color.rgb = RGBColor(0x26, 0x26, 0x26)
    t = d.add_table(rows=1, cols=len(head)); t.style = 'Table Grid'
    for i, h in enumerate(head):
        c = t.rows[0].cells[i]; c.text = h; c.paragraphs[0].runs[0].bold = True
    trPr = t.rows[0]._tr.get_or_add_trPr(); th = OxmlElement('w:tblHeader'); th.set(qn('w:val'), 'true'); trPr.append(th)
    tblPr = t._tbl.tblPr; look = tblPr.find(qn('w:tblLook'))
    if look is None: look = OxmlElement('w:tblLook'); tblPr.append(look)
    look.set(qn('w:firstRow'), '1'); look.set(qn('w:val'), '0020')
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row): cells[i].text = _scrub(str(v))
n_t = [0]
def tcap(text):
    n_t[0] += 1; return f'Table {n_t[0]}: {text}'
d.add_heading('What was fixed', level=2)
if fixed_names:
    table(tcap('Panorama issues found in the original and fixed'), ['Panorama issue', 'Severity', 'Count'],
          [(n, s, c) for n, s, c in fixed_names])
elif before is None:
    d.add_paragraph('The original is a different file type, so it was not checked the same way; the changes are listed below.')
else:
    d.add_paragraph('The checks found nothing to fix in the original.')
if ch:
    d.add_paragraph('Changes made:')
    for x in ch: d.add_paragraph(x, style='List Bullet')
for h, intro, items in text_changes():
    d.add_heading(h, level=2)
    d.add_paragraph(intro)
    for x in items: d.add_paragraph(x, style='List Bullet')
if (notes.get('added') or notes.get('removed') or notes.get('reworded')) and not (notes.get('removed') and notes.get('reworded')):
    none = [k for k in ('removed', 'reworded') if not notes.get(k)]
    d.add_paragraph('No text was recorded as ' + ' or '.join(none) + '.')
if notes.get('decisions'):
    d.add_heading('Your decisions', level=2)
    table(tcap('Questions asked while fixing, and your answers'), ['Question', 'Your answer'],
          [tuple(x) if isinstance(x, list) else (x, '') for x in notes['decisions']])
d.add_heading('What Panorama will likely still flag', level=2)
why = {x[0]: (x[2] if len(x) > 2 else '') for x in notes.get('not_fixed', [])}
if likely:
    table(tcap('Issues expected in Panorama after upload'), ['Panorama issue', 'Severity', 'Count', 'Why it is left'],
          [(n, s, c if c else '', why.get(n, 'Found by the final check')) for n, s, c in likely])
    d.add_paragraph('Panorama scores a file by its worst issue: any Severe issue gives 0%, any Major issue 30%, and '
                    'Minor issues only 70% or more.')
else:
    d.add_paragraph('Nothing expected. The file should score 100% in Panorama.')
if maybe:
    d.add_heading('Panorama might also flag', level=2)
    d.add_paragraph('These are not counted in the predicted score. If Panorama does flag one, here is why and what to do:')
    for n, s, c in maybe: d.add_paragraph(n + (f': {why[n]}' if why.get(n) else ''), style='List Bullet')
if notes.get('check'):
    d.add_heading('Check these yourself', level=2)
    d.add_paragraph('Panorama can\'t judge these, so a person needs to look:')
    for x in notes['check']: d.add_paragraph(x, style='List Bullet')
d.save(out)
# language, no blank author, list numbering are set; make the package title/lang complete
z = zipfile.ZipFile(out); files = {n: z.read(n) for n in z.namelist()}; z.close()
s = files['word/styles.xml'].decode()
if '<w:lang ' not in s:
    s = s.replace('<w:rPrDefault><w:rPr>', '<w:rPrDefault><w:rPr><w:lang w:val="en-US"/>', 1)
s = re.sub(r'<w:sz w:val="(\d+)"/>', lambda m: f'<w:sz w:val="{max(24, int(m.group(1)))}"/>', s)
s = re.sub(r'<w:szCs w:val="(\d+)"/>', lambda m: f'<w:szCs w:val="{max(24, int(m.group(1)))}"/>', s)
# the default template's unused styles carry light grays (Subtle Emphasis 808080): darken them to 595959 (7:1 on white)
s = re.sub(r'(<w:color w:val=")(?:999999|808080|A6A6A6|BFBFBF)("[^>]*?)(?: w:themeColor="[^"]*")?(?: w:themeTint="[^"]*")?(/>)', r'\g<1>595959\2\3', s)
files['word/styles.xml'] = s.encode()
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as o:
    for n, b in files.items(): o.writestr(n, b)
if want_pdf:
    r = subprocess.run(['bash', os.path.join(HERE, 'export_pdf.sh'), os.path.abspath(out)], capture_output=True, text=True)
    pdf = os.path.splitext(out)[0] + '.pdf'
    if os.path.exists(pdf) and os.path.abspath(pdf) != os.path.abspath(final_pdf):
        import shutil; shutil.move(pdf, final_pdf); pdf = final_pdf
    if os.path.exists(pdf):
        paras = [H.unescape(''.join(re.findall(r'<w:t[^>]*>([^<]*)', q))) for q in re.findall(r'<w:p\b.*?</w:p>', files['word/document.xml'].decode(), re.S)]
        caps = [q.split(': ', 1)[1] for q in paras if re.match(r'Table \d+: ', q)]   # each table's caption doubles as its summary
        tj = pdf + '.tables.json'; json.dump([[c, c] for c in caps], open(tj, 'w'))
        tmp = pdf + '.raw.pdf'; os.replace(pdf, tmp)
        subprocess.run([sys.executable, os.path.join(HERE, 'postprocess_pdf.py'), tmp, pdf, tj], capture_output=True)
        if not os.path.exists(pdf): os.replace(tmp, pdf)
        for f_ in (tj, tmp):
            if os.path.exists(f_): os.remove(f_)
        chk = subprocess.run([sys.executable, os.path.join(HERE, 'preflight_pdf.py'), pdf], capture_output=True, text=True).stdout
        fails = [l for l in chk.splitlines() if l.startswith('FAIL')]
        print(f'Report saved as PDF: {pdf}' + ('' if not fails else '  (pre-flight: ' + '; '.join(fails) + ')'))
    else:
        print('PDF export failed (LibreOffice):', r.stderr[-300:])
    if not want_docx: os.remove(out)
if want_docx: print(f'Report saved: {out}')
