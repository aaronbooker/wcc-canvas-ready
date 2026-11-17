"""docx -> tagged PDF/UA WITH the table /Summary attribute Panorama checks (one step: export_pdf.sh + postprocess_pdf.py).
Use this for any .docx you BUILD or REBUILD that has tables; export_pdf.sh alone leaves "Table does not have a summary" (file scores 70%).
Usage: python3 -I docx2pdf_ua.py in.docx out.pdf
Reads each table's caption and description from the .docx (w:tblCaption / w:tblDescription), exports with LibreOffice,
then runs the skill's postprocess_pdf.py to write /Summary on every /Table tag."""
import sys, os, re, json, zipfile, subprocess, tempfile, shutil

SKILL = os.path.dirname(os.path.abspath(__file__))
OPTS = ('pdf:writer_pdf_Export:{"UseTaggedPDF":{"type":"boolean","value":"true"},"PDFUACompliance":{"type":"boolean","value":"true"},'
        '"DisplayPDFDocumentTitle":{"type":"boolean","value":"true"},"ExportBookmarks":{"type":"boolean","value":"true"}}')
src, dst = sys.argv[1:3]
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
subprocess.run([sys.executable, '-I', os.path.join(SKILL, 'postprocess_pdf.py'), os.path.join(tmp, 'in.pdf'), dst,
                os.path.join(tmp, 'tables.json')], check=True)
shutil.rmtree(tmp)
print('wrote', dst, '| table summaries from docx:', len(tables))
