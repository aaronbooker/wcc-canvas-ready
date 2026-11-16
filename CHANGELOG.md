# Changelog

Versions run v1.00, v1.01, v1.02 and so on. The skill's `name` stays `wcc-canvas-ready` in every version.

## v1.00 (November 15, 2026)

First release. Built on Chris Pasquini's `canvas-accessible-docx` (v1 November 6, v3 November 13) and rebuilt and tested against WCC's YuJa Panorama.

- Handles Word, PowerPoint, Excel, PDF (including scans) and HTML files.
- Includes `docx2pdf_ua.py`, which exports a Word file to a tagged PDF with the table summaries Panorama checks.
- `export_pdf.sh` warns when a Word file has tables.
- Rule added: PDFs the skill itself produces (reports, handouts) must pass the same checks as any other file.
