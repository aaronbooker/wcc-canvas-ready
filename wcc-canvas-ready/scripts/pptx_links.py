"""Replace link text that is just a URL with descriptive text. P10 [WCAG 2.4.4 + Panorama, Major].
  python3 pptx_links.py deck.pptx                    # list every link: slide, shown text, address
  python3 pptx_links.py deck.pptx out.pptx links.json  # apply
links.json maps the text now shown (usually the URL) to the new text, e.g.
  {"https://haveibeenpwned.com": "Have I Been Pwned (haveibeenpwned.com)"}
Keep the domain in parentheses so a live audience still sees where the link goes. Only the linked run's text
changes; its formatting and address stay.
"""
import sys, json
from pptx import Presentation
prs = Presentation(sys.argv[1])
apply = len(sys.argv) > 3
m = json.load(open(sys.argv[3])) if apply else {}
n = 0
for i, s in enumerate(prs.slides, 1):
    for sh in s.shapes:
        if not sh.has_text_frame: continue
        for p in sh.text_frame.paragraphs:
            # a link's text can be split across several runs ("https://a" + "aronbooker.com"): group them
            groups, cur = [], None
            for r in p.runs:
                addr = r.hyperlink.address
                if addr and cur and cur[0] == addr: cur[1].append(r)
                else:
                    cur = [addr, [r]] if addr else None
                    if cur: groups.append(cur)
            for addr, runs in groups:
                shown = ''.join(r.text for r in runs)
                if not apply: print(f'slide {i}: "{shown}" -> {addr}'); continue
                key = shown.strip()
                if key in m:
                    runs[0].text = shown.replace(key, m[key])
                    for r in runs[1:]: r.text = ''
                    n += 1
if apply:
    prs.save(sys.argv[2]); print(f'link texts replaced: {n}')
