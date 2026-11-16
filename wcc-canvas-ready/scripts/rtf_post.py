"""Finish an .rtf exported by LibreOffice from a fixed .docx so Panorama reads it like the Word file.
Usage: python3 rtf_post.py in.rtf out.rtf
Panorama checks RTF with its Word rules (headings, title, font size, language...).
- [WCAG+Panorama 1.3.1] LibreOffice writes "Heading N" styles without \\outlinelevel; Word (and Panorama) need it
  to treat them as headings. Adds \\outlinelevel(N-1) to the style definitions and to every paragraph using them.
- [WCC Panorama] every \\fsN below 24 (12 pt) raised to 24, including unused code styles pandoc leaves behind.
- [WCAG+Panorama 3.1.1] \\deflang1033 and \\lang1033 default.
"""
import re, sys
s = open(sys.argv[1], encoding='latin-1').read()
heads = {}
for m in re.finditer(r'\{\\s(\d+)\\[^{}]*?Heading (\d);\}', s):
    heads[m.group(1)] = int(m.group(2)) - 1
def add_ol(m):
    sid = m.group(1)
    if sid in heads and '\\outlinelevel' not in m.group(0):
        return m.group(0) + '\\outlinelevel%d' % heads[sid]
    return m.group(0)
s = re.sub(r'\\s(\d+)(?=[\\ ])', add_ol, s)
s = re.sub(r'\\fs(\d+)', lambda m: '\\fs%d' % max(24, int(m.group(1))), s)
s = re.sub(r'\\afs(\d+)', lambda m: '\\afs%d' % max(24, int(m.group(1))), s)
if '\\deflang' not in s[:400]:
    s = s.replace('{\\rtf1', '{\\rtf1\\deflang1033', 1)
open(sys.argv[2], 'w', encoding='latin-1').write(s)
print('heading styles:', heads, '| outline marks:', s.count('\\outlinelevel'))
