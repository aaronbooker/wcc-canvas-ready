# Changelog

Versions run v1.00, v1.01, v1.02 and so on. The skill's `name` stays `wcc-canvas-ready` in every version.

## v1.01 (November 16, 2026)

- Update check: at the start of a chat the skill asks GitHub (one read-only request for a version number) whether a newer version exists and tells you in one line. It cannot update itself; you download and replace it as before. If you are offline or the request is blocked, it stays silent.
- Added `VERSION` and `scripts/check_update.py`.

## v1.00 (November 15, 2026)

First release. Built on Chris Pasquini's `canvas-accessible-docx` (v1 November 6, v3 November 13) and rebuilt and tested against WCC's YuJa Panorama.

- Handles Word, PowerPoint, Excel, PDF (including scans) and HTML files.
- Includes `docx2pdf_ua.py`, which exports a Word file to a tagged PDF with the table summaries Panorama checks.
- `export_pdf.sh` warns when a Word file has tables.
- Rule added: PDFs the skill itself produces (reports, handouts) must pass the same checks as any other file.
