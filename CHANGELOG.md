# Changelog

From v1.0.5 on, versions have three parts: major.minor.patch. A fix moves the last number (v1.0.6), a new feature moves the middle number (v1.1.0), and a change that breaks how the skill is used moves the first (v2.0.0). The first five releases were numbered v1.00 to v1.04, which are the same as v1.0.0 to v1.0.4. The skill's `name` stays `wcc-canvas-ready` in every version.

## Next release (not released yet)

- Fix: a Word file with both pictures and links lost every picture when the skill made it into a PDF. Since v1.1.0, a PDF with links is printed again through Chrome so that Panorama doesn't flag "Check reading order". On the way, `pdf_tag2html.py` dropped any paragraph with no text, which is where LibreOffice puts a Word picture. It now keeps pictures. Found on the faculty guide: all 16 screenshots were missing, and nothing warned about it.
- Fix: in the same Chrome route, body paragraphs ran together into one block. `pdf_tag2html.py` looked up a tag's role without the leading slash that PDF role maps use, so LibreOffice's "Standard is a paragraph" mapping was never found. It now finds it, and each paragraph prints as its own paragraph.
- `content_check.py` now counts pictures as well as words, and prints a WARNING when the rebuilt file has fewer pictures than the original.
- The faculty guide PDF in `docs/` is now version 15, written for WCC faculty outside the AI in Action workshop. Its web addresses are links you can select. The privacy section warns that a new Free account had "Help improve our AI models" already on, and it was checked against Anthropic's Privacy Center on November 22, 2026. It also fixes the count of test files (59) and says that Team plans have skills on unless an owner turns them off.
- `docs/install-and-update.md` has new pictures of Claude from November 21, 2026, taken during the v1.1.1 test installs. It now says what Claude shows after each upload ("added and ready to use", "Replaced Wcc canvas ready"), that the plugin page's Version counts uploads rather than naming the skill's version, that Add, then Upload plugin also updates an installed copy (Claude asks to replace it), and what the version check looks like in a new chat. The skill itself is unchanged.
- The faculty guide PDF in `docs/` is now version 14, for v1.1.1. Its pictures of Claude were retaken on November 21, 2026, with four new ones (the upload preview, the version check, the message after an update, and Replace existing plugin). Its steps now mention the Preview box, the New label, what Claude says after an install or update, that the plugin page's Version counts uploads, that Upload plugin can also replace an installed copy, and that the skill can't check for updates by itself when "Use the internet while making files" is off.

## v1.1.1 (November 21, 2026)

The last number moves: the skill now comes as a .skill file and its update steps match Claude's new Plugins screens. Nothing about how files are fixed changed.

- The skill now comes as `wcc-canvas-ready.skill` instead of `wcc-canvas-ready.zip`. A .skill file is the same ZIP archive with a different name. Claude moved skills under Plugins on November 20, 2026, and its new **Upload new version** button accepts only a .skill file (or a single SKILL.md), so a ZIP can no longer be used to update. A first install still takes either, through Plugins, then Add, then Upload plugin. The v1.1.0 release had `wcc-canvas-ready.skill` added beside its ZIP on November 20, and its download note now names the .skill file.
- The update notice now says to download `wcc-canvas-ready.skill` and upload it with Plugins, the skill's three dots (…), then Upload new version. Copies at v1.1.0 or earlier still show the old notice, which names the ZIP and the old Customize menu, so the release keeps the ZIP for now.
- The README and `docs/install-and-update.md` describe Claude's new screens: Plugins in the sidebar, Add, then Upload plugin for a first install, an "Added" label instead of an on/off switch, and Upload new version for updates. Seven screenshots were replaced or added, including the GitHub release page with the .skill file outlined.
- The faculty guide PDF in `docs/` is now version 11, for v1.1.0: its version numbers and timeline are up to date, and its update section shows a screenshot of the update notice. The step-by-step page `docs/install-and-update.md` shows the same screenshot. The skill itself is unchanged.
- The faculty guide PDF in `docs/` is now version 13. Its setup steps match the Canvas setup page in six parts, including making a Claude account and keeping chats out of AI training. It downloads `wcc-canvas-ready.skill`, installs through Plugins, updates with Upload new version, and shows Claude's screens as of November 19 and 20, 2026. It scored 100% in Panorama.

## v1.1.0 (November 19, 2026)

The middle number moves because PDFs with links are now made a new way (through Chrome). Nothing about how you install or use the skill changed.

- PDFs with links now pass Panorama. When the skill made a PDF from a Word file, any clickable link left the page flagged "Check reading order" (Severe), so the PDF scored 0% while the skill's report predicted 100%. In tests on November 19, nothing changed inside such a PDF cleared the flag, but the same pages printed through Chrome passed. The skill now does that by itself whenever the PDF has links, and keeps the links. An 8-page guide with 7 links went from 0% to 100% in Panorama this way. The page layout comes from Chrome afterwards, so Claude checks every page.
- The skill's report now predicts this flag, so it no longer promises 100% for a PDF like that.
- A word with a hyphen that wrapped at the end of a line ("well-" then "known") came out with a space added ("well- known") when a PDF was printed again through Chrome. It is now joined back together.
- Web pages: the link check now flags a link whose text is a bare `.ai` address, such as "claude.ai". Panorama flagged one as "This link should have a descriptive title" (Major) on November 19, and the check had missed it because it only knew `.com`, `.org`, `.edu`, `.net`, `.gov`, `.io` and `.us`. It now also knows `.ca` and `.uk`, and ignores capital letters. The PDF rebuild's list of addresses gains `.ai` too.
- The skill's list of Panorama issues has a row for "Alternative description longer than 120 characters" (Major, web pages). The check already existed; the list didn't say how to fix it. An alt text of exactly 120 characters passed in Panorama.
- Web pages: the link check now flags a bare address with any ending, not only a list of known ones. A side effect: link text like "Node.js" is flagged too, so read the list before changing anything.
- Web pages: the alt text check lists every image whose alt is too long, with its length. It used to stop at five, so a sixth long alt text went unlisted.
- The report for a web page now predicts the right score. It had ignored the severity the check printed, so a page with Major problems was predicted at 70–99% instead of 30%, and its issues were listed without names. Each link and each image with long alt text now counts as one instance, as Panorama counts them.
- Web pages: two links in a row to the same address are now listed under "Panorama might also flag" and no longer lower the predicted score. Panorama did not flag two email links to the same address.
- The report for a web page no longer lists "The link is broken" when the page has no links to sites that block checkers.
- New note in the skill: for a Canvas page, check the page's HTML with the scripts, not the page in the browser. A page checked in the browser was predicted at 100% and scored 30%.
- The faculty guide PDF in `docs/` is now version 10, still for v1.0.11. The install steps now show a screenshot for each part, the same seven pictures as `docs/install-and-update.md`, each with alt text. It scored 100% in Panorama.
- Before that, the same day, version 9: its "What it does not do" section is now "Limitations", matching the README: what Panorama's score does and doesn't tell you, which files may not reach 100% (with the 50-file test results and older Office files), and what you still need to check yourself. It also says that signing up for Claude needs a cell phone that can get texts. Web addresses are still written as text, not links.

## v1.0.11 (November 19, 2026)

- The update notice no longer says only a new chat will use the update. In a test, a chat that had last run v1.0.5 reported v1.0.9 when it was reopened, so an existing chat can pick up the new version. How that happens isn't known, so the notice now recommends a new chat as the route that is sure to work, and says an existing chat may pick it up too but that isn't guaranteed. The skill's instructions tell Claude not to promise either way, and not to say whether relaunching the browser or app refreshes the skill.
- The update steps say "If Claude asks whether to replace" instead of "When", since that question may not appear every time.
- The README lists every file type the skill handles (older Office formats, OpenDocument, RTF, scans, flyers, fillable forms and slide decks saved as PDF), how to give it a Google file, and what it can't fix.
- The README's "What it does not do" section is now "Limitations": which files may not reach 100% and why, and what you still need to check or do yourself.
- The skill's description, README, NOTICE and CONTRIBUTING call it simply "Panorama", the name faculty know it by in Canvas, without the vendor's name. The README's first line also says that Canvas is WCC's learning management system (LMS).
- The README's Credit section thanks Chris and Monica and links to each person's WCC staff directory entry and LinkedIn page.
- Monica Riess is now named in the copyright line in `NOTICE` and in the suggested credit for anyone who shares or adapts the README or guide.
- Textbook chapters rebuilt from scanned-and-recognized PDFs (Acrobat "Paper Capture"): three more chapters of one textbook went from 0% to 100% in Panorama, for the Word file and the PDF of each (Nov 18). Fixes found along the way:
  - The layout settings file is now a blank template. It still held another chapter's settings, which made the next chapter silently lose its first lines.
  - Each page's left- or right-hand layout is worked out from where the text sits. Two chapters of the same book start on opposite sides, and the old rule read every page of one of them with the wrong columns.
  - Invisible OCR guesses that Acrobat hides in the page (for icons and maps) are dropped; they had landed in the middle of sentences.
  - Accents drawn apart from their letter are joined again ("ć", not "c´").
  - Margin notes are sorted into learning objectives, online-lab notes and glossary terms. Typed numbered lines become real lists, which Word's checker expects.
  - A paragraph split by a page break with a footnote, box or picture in between is joined again. Footnotes read "Note 1:", and two footnotes run together are split.
  - Era labels set in small capitals read "B.C.E." and "C.E.". "So-called" keeps its hyphen at a line break.
  - New `ocr_gaps.py` reads every page image with OCR and lists words the text layer lacks or seems to misread. It works without the optional PyMuPDF and pytesseract libraries.
  - New `layout_draft.py` drafts a chapter's layout from the page images: boxes, figures and photos to set aside, and the pages to build by hand. On the three chapters its pages matched the hand-made layouts, apart from one gray chart, which it flags for a person to mark. This was the longest step done by hand.
  - Run-in heads (a phrase in the heading font that opens a paragraph) become headings, one level under the heading before them. Typed numbered lists become real numbered items with their turned lines, and indented block quotes become one quote.
  - Sideways pages are marked for building by hand, and `region.py` prints a readable version of them.
  - The skill tells the instructor that a long chapter takes a while, and offers to do it a few sections at a time.
- New guide with pictures, `docs/install-and-update.md`: each install and update step with a screenshot of Claude and of the GitHub release page, including which download to pick under Assets. The update notice ends with a link to it, says Customize may now be called Plugins, and Claude is told to point instructors to the guide if they get stuck. Updates always come from GitHub.
- The README's download and update steps now go through the release page (Assets, then wcc-canvas-ready.zip), as the update notice does. Its install steps match Claude's current Upload a skill screen and say to check that the skill's switch is on.
- The README asks faculty to help by emailing their original file, before the skill, with student information taken out. Nothing else is needed.
- After the release, the same day: the faculty guide PDF in `docs/` is now version 8, for v1.0.11. The skill is downloaded only from GitHub, and the guide's install and update steps, file types, limits, timeline and request for original files are up to date. Web addresses are written out as text, not as clickable links: in Panorama tests the same day, every clickable link in a PDF exported by LibreOffice was flagged "Check reading order" (Severe), and the guide with links scored 0%. With the addresses as text it scored 100%.

## v1.0.10 (November 17, 2026)

- Test release to check the v1.0.9 update notice end to end. Nothing about how the skill works changed.

## v1.0.9 (November 17, 2026)

- The update notice can no longer get lost. In a test on claude.ai with v1.0.6, the check correctly found v1.0.8, but Claude wrote the notice just before asking a question, and in that kind of chat text written between steps is summarized, not shown. The instructor never saw it. Now the notice goes where it will be seen: sent with a message tool if Claude has one, otherwise at the top of the first question (inside the question itself when Claude asks with a question box), otherwise at the top of the final reply. It is repeated as one line with the download link after the report. The "couldn't check" line for an out-of-date copy is placed the same way.
- The report no longer lists the rebuild's progress line ("wrote … blocks … tables …") under "Changes made".
- The word check for a rebuilt PDF names the original's pages that have no text (scanned pages) instead of counting the words read from them as "added". In the same test, a scan's 588 words were all counted as added.
- The faculty guide in `docs/` now describes v1.0.8: the install and update steps use **+ Add**, then **Upload skill**, and the update no longer asks you to delete the old copy first (Claude offers to replace it). Version numbers, the update notice and the timeline are brought up to date. The guide's license note lists these changes.

## v1.0.8 (November 17, 2026)

- The update steps now match claude.ai: go to Customize, then Skills, select **+ Add**, then **Upload skill**, and choose the file. The old steps named a menu path that no longer exists, and following them led to "Create a skill" instead. Fixed in the update message, in the skill's own instructions and in the README.
- The update check no longer misses an update when Claude's web tool reads an old copy of the releases page. On Nov 17 that page was read as v1.01 while the latest was v1.0.6, and the check then said this copy was "newer than the latest release" and stayed quiet. Now Claude first reads the one-line `VERSION` file, which has nothing to misread, and uses the releases page only if that fails. If the number it reads is older than the installed copy, the check says it couldn't be confirmed instead of treating it as a result. The script's own check also skips a source that answers with an older number and tries the next one.

## v1.0.7 (November 17, 2026)

- Fillable PDF forms (made in InDesign or Acrobat, with boxes to type in) now have their own steps. These forms usually have no accessibility tags, so Panorama scores them 0%, and the tags can't be added to the form as it is. The skill rebuilds the form as a printable PDF with real headings, write-in lines, check boxes and tables for the rating grids. Because the rebuilt PDF has no boxes to type in, the skill asks first whether you want Word, PDF or both. A seven-page bilingual student information form went from 0% to 100% in Panorama.
- An asterisk inside a word (the German gender star, as in "Schüler*innen") is no longer dropped when a PDF is rebuilt.
- Tables in rebuilt PDFs get column widths that fit their words. Before, every column was the same width, and long words were split in the middle ("Sportveranstaltung" on one line, "en" on the next), which changes what a screen reader reads.
- The report lists a missing PDF title once instead of twice.
- PDF rebuilds work on a Mac without extra setup.
- Monica Riess is credited as a collaborator in `NOTICE` and the README. She shared her `pdf-accessibility-updater` and `pptx-accessibility-updater` skills and gave permission to use anything in them. Each rule adopted from them will be listed here with credit to her, after it is tested against WCC's Panorama.
- Four PDF rules adapted from Monica Riess's `pdf-accessibility-updater`, tested on a one-page test PDF in WCC's Panorama (Nov 16):
  - `preflight_pdf.py` F17: checks that the tags point at real page content. A tag that points at content missing from the page is what Panorama reports as "The tag is empty" (Minor). Screen readers can also find such pages empty. The report counts it and lists it under "Check these yourself".
  - `preflight_pdf.py` F18: text contrast, read in each character's own color space (gray, RGB and the CMYK colors InDesign uses), against the shape behind it. It prints the exact color operator and a passing replacement for `pdf_tagfix.py`; a gray fix made this way passed in Panorama. CMYK text gets an RGB replacement, because Panorama still failed an orange that was darkened in CMYK; with the RGB replacement the test PDF scored 100%. F18b lists text on a picture for a check by eye, since Panorama measures the picture's pixels.
  - `pdf_tagfix.py`: `--list` pairs each figure with the caption nearest it on the page and flags alt text that drifted onto the wrong picture (InDesign). The new `alt_from_caption` key writes alt text from the caption.
  - `pdf_tagfix.py` `link_refs` (on by default) retags link tags that go nowhere (footnote numbers) as `<Reference>`. WCC's Panorama did not flag these ("This link does not have a URL"), so the report lists F19 as Possible only.
- `pdf_tagfix.py`: a figure whose only text is a caption tagged inside it is no longer turned into a paragraph.
- Student records: when a file looks like it holds student records (a roster, grades next to names, student IDs or emails), Claude stops and asks the instructor for a copy without them before fixing anything.
- Notes in the skill and the faculty guide now describe past test files only by kind, without naming their topics or the colleagues' departments.
- PDF: Panorama's "Check reading order" (Severe, 0%) on tagged PDFs, the kind InDesign exports, is now predicted and fixed. Seven one-page test PDFs showed what Panorama checks: on each page, the numbers that tie the text and pictures to their tags must go up in tag order. Where things sit on the page, and the order they are drawn, made no difference. `preflight_pdf.py` checks this as F20. `pdf_tagfix.py` now renumbers the content to follow the tags by default (`mcid_order`). This changes nothing a reader sees or hears. A test PDF went from 0% to 100% with that default alone (Panorama, Nov 17). On a 68-page InDesign file the check cleared every flagged page, and each page looks the same (checked on this computer, not in Panorama).
- PDF: a new check, F21, asks whether the tag order follows the page: top to bottom in a column, left to right on a line. Panorama doesn't check this, but a screen reader reads the tags in that order. The report lists it as something for a person to check, not as part of the score. `pdf_tagfix.py` `"tag_order": true` moves only the tags that are clearly out of place. It changes what a screen reader reads first, so the instructor is asked before it is used.
- `pdf_order.py` is new and holds both checks. It found no problem in the faculty guide or in PDFs the skill rebuilt.
- Tested on 50 course files of every type in WCC's Panorama (Nov 17). 48 now score 100%. The other two score 70%: an interactive game page whose built-in text is over 3,000 words, and a designed flyer whose small print needs the original design file. Fixes found by the round:
  - Word: text on shaded table cells, paragraphs and banners is checked against the shading; email links get `mailto:`; quiz choices typed "A. … B. …" become a lettered list; document properties written without the usual prefix are read.
  - PowerPoint: logos repeated on every slide are drafted as decorative; slides are grouped in more cases to clear "Check reading order of slide" (placeholders first, then the rest grouped; a photo edge touching the title box no longer blocks it); each slide uses its own slide master's colors; a text box turned into a slide title keeps the color it had.
  - PDF: heading levels are closed up so none is skipped; a rebuilt PDF that has links goes through Chrome, because LibreOffice's links were flagged on every page; slide decks saved as untagged PDFs have their own rebuild script (`pdf_slides2md.py`).
  - HTML: hidden slides and panels are measured too; text inside a colored box takes the box's own text color; text on a color gradient is checked against every color in it; a page that is really RTF is converted first.

## v1.0.6 (November 16, 2026)

- Excel: text contrast is now fixed and predicted. A workbook the skill predicted at 100% scored 30% in Panorama ("Insufficient contrast between foreground text and background", Major). Tests in Panorama showed two causes: words formatted differently inside one colored cell (a bold label followed by plain text) are flagged whatever their colors, and colored text on a colored fill can be flagged even when it passes on paper. The skill now makes those cells plain text and turns colored text on colored fills black or white. The same workbook then scored 100%.
- Excel: links whose visible text is just the web address are now found and renamed (for example "WCC Library (library.whatcom.edu)"), the same way as in Word and PowerPoint. Panorama flags them as "The hyperlink text is not descriptive" (Major). A test workbook went from 30% to 100%. The report now predicts this too.
- Excel: font sizes under 12 points are now raised in every workbook. Workbooks saved by some programs write font sizes in a slightly different form, which the skill skipped while reporting that it had raised them (found with test workbooks, November 16). Panorama flags fonts under 11 points, so those files could still lose points.
- Updating is simpler: upload the new ZIP and say yes when Claude asks whether to replace the version you have. You no longer need to delete the old one first. The update message and the README say so.
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

First release. Built on Chris Pasquini's `canvas-accessible-docx` (v1 November 6, v3 November 13) and rebuilt and tested against WCC's Panorama.

- Handles Word, PowerPoint, Excel, PDF (including scans) and HTML files.
- Includes `docx2pdf_ua.py`, which exports a Word file to a tagged PDF with the table summaries Panorama checks.
- `export_pdf.sh` warns when a Word file has tables.
- Rule added: PDFs the skill itself produces (reports, handouts) must pass the same checks as any other file.
