import re, sys, zipfile
z=zipfile.ZipFile(sys.argv[1]); names=z.namelist()
R=lambda n: z.read(n).decode('utf-8') if n in names else ''
doc,sty,core,sett=R('word/document.xml'),R('word/styles.xml'),R('docProps/core.xml'),R('word/settings.xml')
txt=lambda x: ''.join(re.findall(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>',x))
parts=[n for n in names if re.match(r'word/(document|styles|numbering|header\d*|footer\d*|footnotes|endnotes)\.xml$',n)]
print('D2 title:', bool(re.search(r'<dc:title>[^<]+',core)))
print('D3 lang core/styles/settings:', '<dc:language>' in core, 'w:lang' in sty, 'w:themeFontLang' in sett)
print('D4 other lang tags:', sorted(set(re.findall(r'<w:lang\b[^>]*w:val="([^"]*)"',doc+sty))-{'en-US'}))
h=[int(x) for x in re.findall(r'<w:pStyle w:val="Heading(\d)"',doc)]
print('D5 headings:',len(h),' D6 starts at H1:',h[:1]==[1],' D7 skips:',[(a,b) for a,b in zip(h,h[1:]) if b>a+1])
docpr=re.findall(r'<wp:docPr\b[^>]*?(?:/>|>.*?</wp:docPr>)',doc,re.S)
noalt=[d for d in docpr if 'decorative' not in d and not re.search(r'descr="(?![^"]*\.(?:png|jpe?g|gif|emf|wmf|svg)")[^"]+"',d)]
print('D11 images w/o real alt:',len(noalt),' decorative marks:',len(re.findall(r'decorative\b[^>]*val="1"',doc)))
# only anchored *pictures* count: a drawn line or empty shape that floats was not flagged at WCC (Nov 2026, 100%)
_anch = re.findall(r'<wp:anchor\b.*?</wp:anchor>', doc, re.S)
print('D12 floating images (wp:anchor):', sum(1 for a in _anch if '<pic:pic' in a or '<a:blip' in a),
      f'(+{sum(1 for a in _anch if not ("<pic:pic" in a or "<a:blip" in a))} floating shapes without a picture, not counted)')
tbls=list(re.finditer(r'<w:tbl>.*?</w:tbl>',doc,re.S))
print('D14 tables:',len(tbls),' w/o header row:',sum('w:tblHeader' not in t.group(0) for t in tbls),
      ' w/o Header Row flag (tblLook firstRow):',sum(not re.search(r'<w:tblLook\b[^>]*w:firstRow="(1|true)"',t.group(0)) for t in tbls))
print('D21 shrunk sub/superscripts (vertAlign):', len(re.findall(r'<w:vertAlign w:val="(?:sub|super)script"',doc)))
# F10 (only matters if this .docx will also be exported to PDF): WCC Panorama gives a tagged PDF a Severe
# "Check reading order" for any glyph off the baseline and for real footnotes. Fix with fix_baseline.py / inline_notes.py.
print('F10 raised/lowered runs (w:position):', len(re.findall(r'<w:position w:val="-?[1-9]\d*"',doc)),
      '| footnote/endnote refs:', len(re.findall(r'<w:(?:footnote|endnote)Reference\b',doc)))
def cap_above(m):
    prev=re.findall(r'<w:p[ >].*?</w:p>',doc[max(0,m.start()-3000):m.start()],re.S)
    return bool(prev) and 'w:val="Caption"' in prev[-1]
print('D15 tables w/o visible caption:', sum(not cap_above(t) for t in tbls))
print('D16 tables w/o summary (tblDescription):', sum('w:tblDescription' not in t.group(0) for t in tbls))
body=re.sub(r'<w:tbl>.*?</w:tbl>','',doc,flags=re.S)
paras=re.findall(r'<w:p(?:\s[^>]*)?/>|<w:p[ >].*?</w:p>',body,re.S)
# typed list markers outside tables. WCC Panorama (Nov 2026): a line starting with an initial ("R. Borgstrom") was flagged
# "should be formatted as a list" (Major); typed numbers alone in table cells were NOT flagged.
_tb = [(m.start(), m.end()) for m in re.finditer(r'<w:tbl>.*?</w:tbl>', doc, re.S)]
_intb = lambda p: any(a <= doc.find(p) < b for a, b in _tb)
print('D17 typed bullets:', [txt(p)[:40] for p in paras if re.match(r'\s*(?:[-–•*·]|\d+[.)]|[A-Za-z][.)])\s',txt(p)) and '<w:numPr>' not in p and not re.search(r'w:pStyle w:val="(Heading|Title)',p) and not _intb(p)][:10])
links=re.findall(r'<w:hyperlink\b[^>]*>.*?</w:hyperlink>',doc,re.S)
_rel = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', R('word/_rels/document.xml.rels')))
_same = [txt(l) for l in links if re.search(r'r:id="([^"]+)"', l) and _rel.get(re.search(r'r:id="([^"]+)"', l).group(1), '').strip() == txt(l).strip()]
print('D18 weak link text:', [txt(l) for l in links if re.match(r'\s*(click here|here|link|read more|more|https?://|www\.)',txt(l),re.I)] + _same)
print('D19 links w/o ScreenTip:', sum('w:tooltip' not in l.split('>',1)[0] for l in links))
print('D20 justified:', len(re.findall(r'<w:jc w:val="(?:both|distribute)"',doc+sty)))
print('D21 sizes <12pt by part:', {n:c for n in parts if (c:=sum(int(v)<24 for v in re.findall(r'<w:(?:sz|szCs) w:val="(\d+)"',R(n))))})
# Read the size from inside rPrDefault only (the old regex could match a later style's size).
d=re.search(r'<w:rPrDefault>(.*?)</w:rPrDefault>',sty,re.S); ds=re.search(r'<w:sz w:val="(\d+)"',d.group(1)) if d else None
print('D21 rPrDefault size >=24:', bool(ds) and int(ds.group(1))>=24, '(missing = Word default 10/11 pt, FAIL)' if not ds else '')
empty=[p for p in paras if not txt(p).strip() and not re.search(r'<w:drawing|<w:pict|<w:object|w:type="page"|<w:sectPr|<w:fldChar',p)]
print('D22 empty spacer paragraphs:', len(empty))
print('D23 placeholders:', sorted(set(re.findall(r'\[[^\]\n]{2,40}\]',txt(doc))))[:15])
print('D24 author:', re.findall(r'<dc:creator>([^<]*)',core), re.findall(r'<cp:lastModifiedBy>([^<]*)',core))
# D25: the text is HTML or XML source code, not a document (an .rtf and a .doc holding a syllabus's HTML, an .rtf holding
# a quiz's XML; Nov 17, 2026). Ask the instructor: render it as the page it describes, or keep the code.
_paras = [__import__('html').unescape(txt(p_)).strip() for p_ in re.findall(r'<w:p[ >].*?</w:p>', doc, re.S)]
_paras = [p_ for p_ in _paras if p_]
_code = sum(1 for p_ in _paras if re.match(r'</?[a-zA-Z!?][\w:-]*[\s>/]|[.#]?[\w-]+\s*\{|[\w-]+:\s*[^;]+;$', p_))
print('D25 text that is HTML/XML/CSS source:', f'{_code} of {len(_paras)} paragraphs' + (' -> ASK: render it or keep the code' if _paras and _code / len(_paras) > 0.3 else ''))
# D9b: text against the shading behind it (run, paragraph or table-cell fill), as Panorama measures it (27 of 27 instances
# matched on a project plan, Nov 17, 2026)
def _L(h):
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
def _R(a, b): la, lb = _L(a), _L(b); return (max(la, lb) + .05) / (min(la, lb) + .05)
_low = []
_cells = [(m.start(), m.end(), (re.search(r'<w:tcPr>(?:(?!</w:tcPr>).)*?<w:shd [^>]*w:fill="([0-9A-Fa-f]{6})"', m.group(0), re.S) or [0, None])[1])
          for m in re.finditer(r'<w:tc>(?:(?!<w:tc>).)*?</w:tc>', doc, re.S)]
for _pm in re.finditer(r'<w:p[ >](?:(?!<w:p[ >]).)*?</w:p>', doc, re.S):
    _c = min((c for c in _cells if c[0] <= _pm.start() and _pm.end() <= c[1]), key=lambda c: c[1] - c[0], default=None)
    _pp = re.search(r'<w:pPr>.*?</w:pPr>', _pm.group(0), re.S)
    _pf = re.search(r'<w:shd [^>]*w:fill="([0-9A-Fa-f]{6})"', _pp.group(0)) if _pp else None
    for _r in re.findall(r'<w:r[ >](?:(?!<w:r[ >]).)*?</w:r>', _pm.group(0), re.S):
        if not re.search(r'<w:t[ >][^<]*\S', _r): continue
        _rs = re.search(r'<w:rPr>.*?<w:shd [^>]*w:fill="([0-9A-Fa-f]{6})"', _r, re.S)
        _bg = _rs.group(1) if _rs else _pf.group(1) if _pf else (_c[2] if _c and _c[2] else 'FFFFFF')
        _fg = (re.search(r'<w:color w:val="([0-9A-Fa-f]{6})"', _r) or [0, '000000'])[1]
        if _R(_fg, _bg) < 4.5: _low.append(f'{_fg.upper()} on {_bg.upper()} {_R(_fg, _bg):.2f}')
print('D9b text under 4.5:1 on its shading:', len(_low), sorted(set(_low))[:6])
print('Known failing colors:', len(re.findall(r'w:val="(?:999999|808080|A6A6A6|BFBFBF|FF0000)"',doc+sty)))
print('Colors used (check each vs its real background):', sorted(set(re.findall(r'<w:color w:val="([0-9A-Fa-f]{6})"',doc+sty))))
print('Fills used:', sorted(set(re.findall(r'w:fill="([0-9A-Fa-f]{6})"',doc+sty))))
