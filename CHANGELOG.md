# Changelog

From v1.0.5 on, versions have three parts: major.minor.patch. A fix moves the last number (v1.0.6), a new feature moves the middle number (v1.1.0), and a change that breaks how the skill is used moves the first (v2.0.0). The first five releases were numbered v1.00 to v1.04, which are the same as v1.0.0 to v1.0.4. The skill's `name` stays `wcc-canvas-ready` in every version.

## v1.0.6 (November 16, 2026)

- When you ask about the skill itself (which version, whether there is an update, what it does), Claude answers and does not ask you for a file.
- When you ask Claude to use the skill without attaching a file, it shows the steps for adding one in general terms. It no longer names a document it remembers from earlier chats.
- Three lines in `pptx_fix.py` and `pdf_tag2html.py` were rewritten so the scripts also run on Python versions older than 3.12. They work the same way.

## v1.0.5 (November 16, 2026)

- Version numbers now have three parts. This is the release after v1.04. The update check reads the old two-part numbers as v1.0.0 to v1.0.4. Copies at v1.04 or earlier do not recognize three-part numbers and will not show an update notice, so reinstall them once.
- The skill is licensed under the Apache License 2.0. The README and the faculty guide are licensed under CC BY 4.0. `LICENSE` and `NOTICE` are now inside the skill folder and the zip.
- Added `CONTRIBUTING.md` for colleagues who want to add fixes or their own skills.
- Nothing about how the skill fixes files changed.

## v1.04 (November 16, 2026)

- Test release to check the update flow end to end. Nothing about how the skill works changed.

## v1.03 (November 16, 2026)

- The update message is written for new users: what is out, the download link, and three plain steps (download, do not unzip, replace the skill under Customize, then Skills).

## v1.02 (November 16, 2026)

- The update check now works when the sandbox that runs scripts has no internet (first seen on a Free account). `check_update.py` tries four GitHub hosts, prints `UPDATE CHECK BLOCKED` when none answers, and takes `--compare` so Claude can read the releases page with its web tool instead.
- A check that could not run is never reported as "up to date".
- New "No file in the chat?" section: a new user who has not attached a file gets step-by-step help adding one.

## v1.01 (November 16, 2026)

- Update check: at the start of a chat the skill asks GitHub (one read-only request for a version number) whether a newer version exists and tells you in one line. It cannot update itself; you download and replace it as before. If you are offline or the request is blocked, it stays silent.
- Added `VERSION` and `scripts/check_update.py`.

## v1.00 (November 15, 2026)

First release. Built on Chris Pasquini's `canvas-accessible-docx` (v1 November 6, v3 November 13) and rebuilt and tested against WCC's YuJa Panorama.

- Handles Word, PowerPoint, Excel, PDF (including scans) and HTML files.
- Includes `docx2pdf_ua.py`, which exports a Word file to a tagged PDF with the table summaries Panorama checks.
- `export_pdf.sh` warns when a Word file has tables.
- Rule added: PDFs the skill itself produces (reports, handouts) must pass the same checks as any other file.
