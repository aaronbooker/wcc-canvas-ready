#!/bin/bash
# Export a tagged PDF (PDF/UA) from a .docx with LibreOffice. Usage: bash export_pdf.sh file.docx  -> file.pdf beside it
set -e
cd "$(dirname "$1")"
SOFFICE=$(command -v soffice || command -v libreoffice)
timeout 300 "$SOFFICE" --headless --convert-to 'pdf:writer_pdf_Export:{"UseTaggedPDF":{"type":"boolean","value":"true"},"PDFUACompliance":{"type":"boolean","value":"true"},"ExportBookmarks":{"type":"boolean","value":"true"}}' "$(basename "$1")" >/dev/null 2>&1
ls -1 "${1%.*}.pdf"
if unzip -p "$1" word/document.xml 2>/dev/null | grep -q "<w:tbl>"; then echo "WARNING: this .docx has tables. LibreOffice does not write table /Summary, so the PDF will score 70% (Table does not have a summary) until you run postprocess_pdf.py (or use docx2pdf_ua.py instead of this script)." >&2; fi
