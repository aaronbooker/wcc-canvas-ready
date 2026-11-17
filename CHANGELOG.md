# Changelog

From v1.0.5 on, versions have three parts: major.minor.patch. A fix moves the last number (v1.0.6), a new feature moves the middle number (v1.1.0), and a change that breaks how the skill is used moves the first (v2.0.0). The first five releases were numbered v1.00 to v1.04, which are the same as v1.0.0 to v1.0.4. The skill's `name` stays `wcc-canvas-ready` in every version.

## Unreleased

- Monica Riess is credited as a collaborator in `NOTICE` and the README. She shared her `pdf-accessibility-updater` and `pptx-accessibility-updater` skills and gave permission to use anything in them. Each rule adopted from them will be listed here with credit to her, after it is tested against WCC's Panorama.
- Four PDF rules adapted from Monica Riess's `pdf-accessibility-updater`, tested on a one-page test PDF in WCC's Panorama (Nov 16):
  - `preflight_pdf.py` F17: checks that the tags point at real page content. A tag that points at content missing from the page is what Panorama reports as "The tag is empty" (Minor). Screen readers can also find such pages empty. The report counts it and lists it under "Check these yourself".
  - `preflight_pdf.py` F18: text contrast, read in each character's own color space (gray, RGB and the CMYK colors InDesign uses), against the shape behind it. It prints the exact color operator and a passing replacement for `pdf_tagfix.py`; a gray fix made this way passed in Panorama. CMYK text gets an RGB replacement, because Panorama still failed an orange that was darkened in CMYK; with the RGB replacement the test PDF scored 100%. F18b lists text on a picture for a check by eye, since Panorama measures the picture's pixels.
  - `pdf_tagfix.py`: `--list` pairs each figure with the caption nearest it on the page and flags alt text that drifted onto the wrong picture (InDesign). The new `alt_from_caption` key writes alt text from the caption.
  - `pdf_tagfix.py` `link_refs` (on by default) retags link tags that go nowhere (footnote numbers) as `<Reference>`. WCC's Panorama did not flag these ("This link does not have a URL"), so the report lists F19 as Possible only.
- `pdf_tagfix.py`: a figure whose only text is a caption tagged inside it is no longer turned into a paragraph.

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
