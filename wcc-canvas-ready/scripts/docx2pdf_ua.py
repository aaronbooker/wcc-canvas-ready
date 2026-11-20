"""docx -> tagged PDF/UA WITH the table /Summary attribute Panorama checks (one step: export_pdf.sh + postprocess_pdf.py).
Use this for any .docx you BUILD or REBUILD that has tables; export_pdf.sh alone leaves "Table does not have a summary" (file scores 70%).
Usage: python3 -I docx2pdf_ua.py in.docx out.pdf [--no-chrome]
Reads each table's caption and description from the .docx (w:tblCaption / w:tblDescription), exports with LibreOffice,
then runs the skill's postprocess_pdf.py to write /Summary on every /Table tag.
A PDF with links is then printed again through Chrome (pdf_tag2html.py -> Chrome -> pdf_tagfix.py): WCC's Panorama
flags every page that has a LibreOffice link "Check reading order" (Severe, 0%). Nov 19, 2026: 16 one-page link tests
changed the LibreOffice file in every way we could think of and all scored 0%; the same page without its link scored
100%, and the same link printed by Chrome had no reading-order flag. --no-chrome keeps the LibreOffice PDF anyway."""
import sys, os, re, json, zipfile, subprocess, tempfile, shutil

SKILL = os.path.dirname(os.path.abspath(__file__))
OPTS = ('pdf:writer_pdf_Export:{"UseTaggedPDF":{"type":"boolean","value":"true"},"PDFUACompliance":{"type":"boolean","value":"true"},'
        '"DisplayPDFDocumentTitle":{"type":"boolean","value":"true"},"ExportBookmarks":{"type":"boolean","value":"true"}}')
src, dst = sys.argv[1:3]
NO_CHROME = '--no-chrome' in sys.argv
xml = zipfile.ZipFile(src).read('word/document.xml').decode('utf8')
tables = []
for t in re.findall(r'<w:tbl>.*?</w:tbl>', xml, re.S):
    cap = re.search(r'<w:tblCaption w:val="([^"]*)"', t)
    desc = re.search(r'<w:tblDescription w:val="([^"]*)"', t)
    unesc = lambda s: s.replace('&amp;', '&').replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>').replace('&apos;', "'")
    tables.append([unesc(cap.group(1)) if cap else 'Table', unesc(desc.group(1)) if desc else ''])
tmp = tempfile.mkdtemp()
shutil.copy(src, os.path.join(tmp, 'in.docx'))
subprocess.run(['soffice', '--headless', '--convert-to', OPTS, 'in.docx', '--outdir', tmp], cwd=tmp, check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
json.dump(tables, open(os.path.join(tmp, 'tables.json'), 'w'))
lo_pdf = os.path.join(tmp, 'lo.pdf')
subprocess.run([sys.executable, '-I', os.path.join(SKILL, 'postprocess_pdf.py'), os.path.join(tmp, 'in.pdf'), lo_pdf,
                os.path.join(tmp, 'tables.json')], check=True, env={**os.environ, 'WCC_DOCX2PDF': '1'})


def find_chrome():
    for p in ('/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser',
              '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'):
        if os.path.exists(p): return p
    try:                                   # the Chromium that `python3 -m playwright install chromium` downloads
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            p = pw.chromium.executable_path
        return p if p and os.path.exists(p) else None
    except Exception:
        return None


import pikepdf
with pikepdf.open(lo_pdf) as pdf:
    links = sum(1 for pg in pdf.pages for a in pg.obj.get('/Annots', []) if a.get('/Subtype') == '/Link')
    title = str(pdf.docinfo.get('/Title', '')) if pdf.docinfo is not None else ''
    lang = str(pdf.Root.get('/Lang', 'en-US'))
    box = [float(x) for x in pdf.pages[0].obj.get('/MediaBox', [0, 0, 612, 792])]
chrome = find_chrome() if links and not NO_CHROME else None
if chrome:
    page = os.path.join(tmp, 'page.html'); raw = os.path.join(tmp, 'chrome.pdf')
    wide = ['--landscape'] if box[2] - box[0] > box[3] - box[1] else []
    subprocess.run([sys.executable, '-I', os.path.join(SKILL, 'pdf_tag2html.py'), lo_pdf, page] + wide, check=True)
    subprocess.run([chrome, '--headless=new', '--no-sandbox', '--disable-gpu', '--no-pdf-header-footer',
                    '--print-to-pdf=' + raw, 'file://' + page], check=True, timeout=300,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fix = {'title': title, 'lang': lang, 'summary': {str(i): d or c for i, (c, d) in enumerate(tables)}}
    json.dump(fix, open(os.path.join(tmp, 'fix.json'), 'w'))
    subprocess.run([sys.executable, '-I', os.path.join(SKILL, 'pdf_tagfix.py'), raw, dst, os.path.join(tmp, 'fix.json')],
                   check=True)
    subprocess.run([sys.executable, '-I', os.path.join(SKILL, 'content_check.py'), lo_pdf, page])
    print(f'links: {links}, so the PDF was printed again through Chrome (a LibreOffice link gets Panorama '
          f'"Check reading order", Severe). The page layout is Chrome\'s now: render the pages and look at every one.')
else:
    shutil.copy(lo_pdf, dst)
    if links:
        print(f'WARNING links: {links} link(s) kept in a LibreOffice PDF. WCC\'s Panorama flags every page that has '
              f'one "Check reading order" (Severe, 0%). ' + ('(--no-chrome was given.)' if NO_CHROME else
              'No Chrome was found: run `python3 -m playwright install chromium` and run this again. If that fails, '
              'deliver the .docx, or ask the instructor whether to write the addresses out as text.'))
shutil.rmtree(tmp)
print('wrote', dst, '| table summaries from docx:', len(tables), '| links:', links)
