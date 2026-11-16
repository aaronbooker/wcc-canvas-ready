---
name: wcc-canvas-ready
description: "Get WCC course files ready for Canvas: fixes accessibility so Word, PowerPoint, Excel, PDF and HTML files pass Whatcom Community College's YuJa Panorama. Asks before big changes and reports what changed and what Panorama may still flag. Use when a file is headed for WCC's Canvas, when someone asks to make a file accessible or Canvas ready, or when Panorama flagged it. Handles .docx/.doc/.rtf/.odt, .pptx/.ppt/.odp, .xlsx/.xls/.ods, PDFs (including scans and designed flyers) and HTML pages."
---

# WCC Canvas Ready, v1.02

**Goal:** a file that scores **100% in YuJa Panorama** at Whatcom Community College on its first upload, with
nothing in it rewritten, summarized or lost. This skill clears **Panorama**. It is **not** a WCAG audit:

- Many Panorama checks are also WCAG 2.2 AA (alt text, contrast, headings, language). Fixing them helps both.
- Some Panorama checks go beyond WCAG 2.2 AA (12 pt minimum, visible table captions, text in cell A1, no
  justified text). WCAG doesn't need them; Panorama scores them, so the skill fixes them.
- Panorama can't judge some WCAG requirements (is the alt text accurate, does the reading order make sense,
  are video captions right). **A 100% score is not proof of WCAG 2.2 AA.**

**WCC Canvas Ready v1.02** (Nov 16, 2026; first released as v1.00 on Nov 15), developed as `panorama-preflight-office` (internal drafts v4 and v5). Based on Chris Pasquini's (WCC) `canvas-accessible-docx` v1 (Nov 6) and v3 (Nov 13); rebuilt and tested by Aaron Booker against WCC's
Panorama in Nov 2026 on 59 files: 49 real course, college, committee, business and community files and 10 generated
ones that fill gaps (legacy and OpenDocument formats, a simulated scan, charts, tables and embedded video). A 29-slide
volcanoes deck then taught the PowerPoint picture-contrast and grouping rules (0% → 100%).

## Update check (first step of every chat)
Before anything else, run `python3 -I scripts/check_update.py` (the path is relative to this skill's folder). It asks GitHub for
the newest release number. Nothing about the instructor, their files or the chat is sent. It prints one of three things:
- **`UPDATE AVAILABLE` line:** show that line to the instructor in your first reply, then carry on with their request. Don't
  stop the work to update.
- **Nothing:** GitHub answered and this copy is current. Say nothing and carry on.
- **`UPDATE CHECK BLOCKED` line:** the sandbox that runs scripts has no route to GitHub. This is normal on many accounts
  (Free plans, and any account with code-execution network access off) and it does **not** mean the skill is current. Do the
  web fallback once, quietly:
  1. If you have a web fetch tool, fetch `https://github.com/aaronbooker/wcc-canvas-ready/releases/latest`. Your web tools run
     outside the sandbox, so this can work when the script can't. The page names the newest release, such as "v1.03".
  2. Run `python3 -I scripts/check_update.py --compare 1.03` with the number you read. It needs no network and compares
     correctly (v1.10 is newer than v1.09). If it prints `UPDATE AVAILABLE`, show that line; otherwise say nothing.
  3. If you have no web fetch tool, or the fetch is refused or shows no version: say nothing, **unless** the BLOCKED line says
     `STALE` (this copy is over 30 days old). Then add one line to your first reply: "I couldn't check for a newer version of
     this skill from here. Yours is vX.XX from <date>; the newest is always at
     https://github.com/aaronbooker/wcc-canvas-ready/releases/latest".
  Never retry, and never hold up the instructor's work for any of this.
- **Never say or imply the skill is up to date unless** the script printed nothing, or `--compare` or `--verbose` said so. "The
  check couldn't run" and "no update" are different facts. A recent date on this copy is not evidence either.
- **If the instructor asks** which version they have or whether an update exists: run it with `--verbose` and report what it
  says. If it says BLOCKED, do steps 1 and 2 above. If those fail too, tell them plainly that you can't check from this chat,
  give the installed version and the releases link, and suggest they paste that link into the chat (pasting it lets you fetch it).
- You can't update the skill yourself: they download the latest zip from the link and replace the skill (Customize, Skills).
- If the instructor says not to check for updates, skip it for the rest of the chat.

## No file in the chat? Show them how to add one
New users often ask for help before attaching anything, or paste a Canvas link, or paste the text of the document. **Look first:**
check the uploads folder and the conversation for a file. If there is one, start work. If there isn't, don't guess, don't work
from pasted text (pasting strips the headings, tables, images and alt text that Panorama scores), and don't just say "please
upload a file". Reply with these steps, in plain words, and leave out the lines that don't apply:
1. **Get the file onto your device.** If it lives in Canvas, open the course, go to **Files**, and download it. A Google Doc,
   Sheet or Slides file: File, Download, then Word, Excel or PowerPoint. I can't open Canvas, OneDrive or Google Drive links.
2. **Attach it to this chat.** Click the **+** button in the lower left corner of the message box, choose **Add files or
   photos**, pick the file, and click Open. On a computer you can also drag the file from its folder and drop it on the chat
   window. In the phone app, tap **+** and choose the file.
3. **Wait for the file to show** as a small card above your message, then send (a short note such as "make this Canvas ready"
   is enough).
- Attach the **original** file (.docx, .pptx, .xlsx, .pdf, .html), not a screenshot or a copy-paste of it.
- Up to 20 files fit in one chat. Start with one or two so the report stays readable.
- If Claude won't accept an Excel or PowerPoint file, **Code execution and file creation** is probably off: Settings, then
  Capabilities. The skill needs it for every file type, so turn it on. (Menu names can change; if these don't match what they
  see, say so and describe the control: the attach button is in the box where they type.)
Also say what happens next in one sentence: you will check the file, ask a few questions before big changes, and hand back a
fixed copy with a report. If they sent a file type the skill doesn't handle (a photo of a page, a video, a .pages file), say
which types it does handle and how to export to one.

## How Panorama scores (WCC)
Severe issues hold a file at **0%**, Major at **30%**, Minor-only files land at **70–100%**. One Severe flag in a
300-page file costs the same as 300. So: fix every Severe and Major; then the Minors.

## The workflow (every file)
1. **Copy first.** Never edit the original. Work on a copy in the working folder; name outputs `*_Accessible.*`.
   Start a `notes.json` for the report (see step 6) and save every script's output with `| tee -a fixlog.txt`.
2. **Identify the kind of file** (table below) and run its pre-flight to see what's wrong.
   **Then ask the instructor the up-front questions** (next section) before fixing anything.
3. **Fix with the scripts** in `scripts/` (Python 3 + LibreOffice; `pip install python-pptx pikepdf pdfplumber
   openpyxl playwright --break-system-packages` if missing). The scripts do the mechanical work the same way
   every time. **Run them; don't redo their work by hand.** Your judgment is only needed where marked **YOU**.
4. **Re-run the pre-flight** until it's clean, render the file to images and look at it, and run the
   content check (same words in, same words out).
5. **Show the big changes and ask** (next section): slide order, rewritten link text, added headings or
   captions. Apply what the instructor says.
6. **Deliver** the file **and its report, in full, in the chat**: run `fix_report.py ORIGINAL FIXED --notes notes.json
   --log fixlog.txt`. It prints the complete report as Markdown: the predicted Panorama score, what was fixed and
   changed, every piece of added text, the instructor's decisions, **what Panorama will most likely still flag**
   (and what it might flag), and what to check by hand. **Paste all of it into your reply, unedited and
   unshortened**, one report per delivered file. Then ask: **"Would you like this report as a PDF too?"** If yes,
   re-run with `--pdf` (an accessible, tagged PDF: headings, table header rows and summaries, 12 pt) and deliver
   it beside the file. *Default when nobody can answer: the chat report only.* Record decisions and anything left
   unfixed in `notes.json` as you go, and record **every text change in three lists**: `added` (captions, alt
   text, headings, titles), `removed` (printed page numbers, running heads, duplicates, Canvas link debris, and
   why), and `reworded` (link text and anything else a reader will see differently). The report states only what
   those lists say; it never claims nothing was removed, so an empty list must mean nothing was.
   In `not_fixed`, give Severe/Major/Minor only for what Panorama will surely flag, and "Possible" when you aren't
   sure; don't add slide reading order (the script judges it). Run it on **each** delivered file, including the
   old-format copy, since a .doc or .ppt saved by the tools loses things (it converts them back to check).
   Tested on 63 outputs (Nov 2026): the prediction matched Panorama on 56 of 63 before tuning and 62 of 63 after
   (the rules were tuned on those same files, so expect a little less on new ones). Say "predicted", never "will score".

## Ask the instructor (don't decide these alone)
The instructor owns the file. Ask before anything that changes its shape, wording or format, and give them
the trade-off in one or two sentences. Use the question tool when there is one; otherwise ask in plain text and
wait. If nobody can answer (a batch run), take the **default** below, keep going, and list the choice in the report.
Ask the up-front questions together, before fixing:
- **Output format** for a PDF with no source: "Word, PDF, or both?" Explain: the rebuild goes through Word
  anyway. In the tests both reached 100% in Panorama, so the difference isn't the score: the Word file is the
  one they can edit and re-export later, with real headings, lists and table headers; the PDF is what students
  usually download, and every later change means another rebuild (and a PDF export drops some structure, such
  as table summaries, that the skill has to put back). Offer both so they can compare. *Default: both.*
- **A page over 3,000 words** (a Minor flag in Panorama: the page can score 70–99% but not 100%): "Keep it as one page (Panorama
  will flag the length), or split it at section headings into N parts?" Never split without a yes.
  *Default: keep one page.*
- **Author** when it's empty or a tool name: "Whose name goes in Author?" *Default: leave it empty.*
- **Changing the file type** (.doc → .docx, .ppt → .pptx): "Keep the old format, or deliver the modern one?"
  Say why: a .doc saved by the tools loses its table-header marks (held at 30% in testing), and a .ppt saved
  by them loses its alt text, title and reading order (30%, 75 issues). *Default: deliver the modern file only
  (rule L1); the original stays untouched. If they still want the old format, deliver it too and say it will score lower.*
Ask during the fix, showing what you'd change:
- **Slide reading order:** after `pptx_fix.py`, run `pptx_order_preview.py fixed.pptx preview --original
  orig.pptx`, show `changed.png` (each shape numbered in reading order) and ask "Does each slide read in the
  right order?" Re-run `pptx_fix.py` with `--keep-order 3,9` (leave as it was) or `--order-file order.json`
  (their order, by the shape names the preview prints). *Default: the fixer's order, flagged in the report.*
- **Rewritten link text** (bare web addresses → names): show the old and new text and ask. *Default: apply.*
- **Added text**: headings, captions, alt text and placeholders that weren't there ("<<Enter subject here>>").
  Show them and ask for corrections. *Default: apply, and list each one in the report.*
- **Visible changes in a rebuilt PDF** (a dash in empty table cells, 12 pt text making the file longer,
  charts turned into pictures with alt text): say what will look different and ask. *Default: apply.*
- **"Verify Reading Order" in Panorama** is the instructor's step after upload: never tell them a slide is fine
  without having them look at the preview.

| File | Pre-flight | Fix with | YOU decide |
|---|---|---|---|
| .docx | `preflight_docx.py` | `docx_lists.py` → `docx_headings.py` → `docx_unbox.py` → `docx_alt.py` → `docx_inline.py` → `docx_captions.py` → `docx_links.py` → `postprocess_docx.py --title` | alt text, table captions, link text, title, headings to check |
| .doc, .rtf, .odt | convert to .docx (LibreOffice), then as .docx | then convert back: `.rtf` → `rtf_post.py`; `.odt` → `odf_colors.py`; `.doc` → **deliver .docx** (see L1) | same as .docx |
| .pptx | `preflight_pptx.py` | `pptx_alt.py` → `pptx_links.py` → `pptx_fix.py` (run the fixer **last**, so pictures marked decorative move behind the content) | alt text, link text, slides with no heading |
| .ppt, .odp | convert to .pptx, fix; `.ppt` → **deliver .pptx** (L1); `.odp` → convert back, then `odf_colors.py` | | |
| .xlsx, .xls, .ods | (the fixer reports) | `xlsx_fix.py --title --a1 "Sheet::text"` (convert .xls/.ods to .xlsx first, back after; `.ods` → then `odf_colors.py`) | title, text for an empty A1 |
| PDF made from Word/Docs | `preflight_pdf.py` | rebuild: fix the source .docx, then `docx2pdf_ua.py in.docx out.pdf` (= `export_pdf.sh` + `postprocess_pdf.py`) | |
| PDF with no source (textbook chapter) | `preflight_pdf.py` | rebuild: `pdf2md.py`/`region.py` → `md2docx.js` → `postprocess_docx.py` → `export_pdf.sh` → `postprocess_pdf.py` | layout.json, alt text |
| Untagged one-column PDF (web page saved as PDF, printed report) | `preflight_pdf.py` (F3 fails) | rebuild: `pdf_flow2md.py` → `md2docx.js` → as above | check the Markdown, alt text |
| Tagged PDF printed from a browser, Google Docs or Forms | `preflight_pdf.py` | fix in place: `pdf_tagfix.py` (lists, table summaries, heading text); small print → rebuild at 12 pt: `pdf_tag2html.py` → Chrome print → `pdf_tagfix.py`; Forms summary: `pdf_tag2html.py --cards` first | table summaries |
| **Scanned** PDF (no text) | `pdftotext` gives nothing | `scan2md.py` (OCR) → `md2docx.js` → … as above | **proofread OCR**, figures |
| Designed one-pager (InDesign flyer, poster) | `preflight_pdf.py` | fix in place: `pdf_tagfix.py --list`, then a JSON of fixes | headings, alt, colors |
| HTML page | `preflight_html.py` | `html_fix.py --fix` (rendered contrast + sizes), then hand edits | link text, alt |
| GIF | none needed (scored 100% at WCC) | | no flashing more than 3 times a second |

**Check the score before fixing.** 6 of the 59 test files already scored 100%. Don't round-trip a passing file:
an .odp that scored 100% fell to 0% after .odp → .pptx → .odp (LibreOffice wrote inherited grays as explicit colors).

Units: Word `w:sz` is half-points (12 pt = 24); PowerPoint `sz` is hundredths (12 pt = 1200); Excel `<sz val>` is points.

## WCC Panorama issues seen, and what fixes them
Severity is what WCC's Panorama showed (Nov 2026), which can differ from YuJa's published defaults.

| Panorama says | File | WCC severity | Fix | Label |
|---|---|---|---|---|
| The item does not have an alternative description | all | **Severe** | `docx_alt.py` / `pptx_alt.py` / `pdf_tagfix.py` alt | WCAG 1.1.1 |
| Insufficient contrast between foreground text and background | all | **Severe** (Major in Word) | postprocess/pptx_fix/html_fix/pdf_tagfix colors. **Text on a photo or banner is measured against the picture's pixels** (Panorama does; `pptx_bg.py`) | WCAG 1.4.3 |
| Check reading order (PDF) | PDF | **Severe** | see F10–F12 | Panorama |
| The document's heading structure is not properly nested | Word | **Severe** | `postprocess_docx.py` (levels) | Panorama (WCAG best practice) |
| Check reading order of slide | PowerPoint | Major | `pptx_fix.py`: title first, the rest of a busy slide (3+ other shapes) grouped as one unit; other slides in column-first order. Grouping cleared three slides that stayed flagged in every order tried (Nov 15, 2026). Left over: a person checks the flagged slides and ticks **Verify Reading Order** in Panorama. After the fixer it stayed only on decks with grid-like slides (rows of separate text boxes: exam-prep cards, a Jeopardy board, stat cards) and on two slides with staggered overlapping screenshots; `fix_report.py` predicts it from that | WCAG 1.3.2 |
| The document does not have slide titles | PowerPoint | Major | `pptx_fix.py` (title placeholders) | WCAG 2.4.2 |
| The title is missing from the document's properties | all | Major | `--title` / title in JSON | WCAG 2.4.2 |
| The document does not have any headings | Word, PDF | Major | `docx_headings.py` / `pdf_tagfix.py` headings | WCAG 1.3.1 |
| List item structure is missing | PDF | Major | `pdf_tagfix.py` (gives each <LI> an <Lbl> and <LBody>) | WCAG 1.3.1 |
| Table does not have a header | Word, Excel | Major | `docx_captions.py` (tblLook firstRow) | WCAG 1.3.1 |
| Table does not have a caption | Word, HTML | Major | `docx_captions.py` (visible caption) | WCC Panorama |
| This element should be formatted as a list | Word | Major | `docx_lists.py`; a heading typed "A. Title" is flagged too: `postprocess_docx.py` makes the "A." real heading numbering. A line that **starts with an initial** ("R. Borgstrom") is flagged as well: ask the instructor how to word it ("Recipe from R. Borgstrom"). Typed numbers alone in table cells were not flagged: leave them | WCAG 1.3.1 |
| This link should have a descriptive title | HTML | Major | link text by hand | WCAG 2.4.4 |
| This link is missing a text description | HTML | Major | empty `<a>`: restore its text | WCAG 2.4.4 |
| The link is broken | HTML | Major | real broken links: fix; **429 = false positive** | Panorama |
| Sheet does not have text in cell A1 | Excel | **Minor** (first sheet only was flagged) | **YOU** write a one-line sheet description; `xlsx_fix.py --a1` | Panorama |
| The font size is smaller than 11 points | all | Minor (counted per cell/run) | raise everything to **12 pt** | WCC Panorama |
| The tag is empty and contains no content | PDF | Minor | headings whose text sits only in child tags: `pdf_tagfix.py` (hoist_text, default); empty table cells: `pdf_tag2html.py` fills them; leftovers: `pdf_tagfix.py drop_empty` | Panorama |
| Table does not have a summary | PDF | Minor | `pdf_tagfix.py` "summary" / `postprocess_pdf.py` | Panorama |
| The hyperlink text is not descriptive | Word | **Major** | `docx_links.py` | WCAG 2.4.4 |
| The Image is not inline with the text | Word | **Major** ×picture | `docx_inline.py` | WCAG 1.3.2 |
| The hyperlink text is not descriptive | PDF | Minor | fix in the source; can't be fixed in place | WCAG 2.4.4 |
| The content is longer than 3000 words | HTML | Minor | `html_split.py` (ask first: the page becomes two) | Panorama |
| The font size is smaller than 11 points | PDF | Minor ×runs | browser prints: `pdf_tag2html.py` rebuild at 12 pt; designed PDFs: the design file | Panorama |

Label key: **WCAG x.x.x** = also a WCAG 2.2 AA requirement. **Panorama** = Panorama check, not WCAG AA.
**WCC Panorama** = stricter at WCC than YuJa's defaults (11 pt flags at WCC; this skill uses 12 pt).

## Golden rules
- **Never replace, summarize or delete real content to pass a checker.** No placeholder text, no invented
  "accessibility statements". If something can't be fixed as-is (a picture you can't describe), keep it and flag it.
- **Never overwrite the original.** **Work from the user's latest saved copy.** Never regenerate over their edits.
- **Same words in, same words out.** Run the content check. Added text is limited to captions, alt text, titles
  and headings Panorama requires; list every addition in the report. A rebuild may drop print furniture (page
  numbers, running heads) or printing defects: list each removal in the report too, with the reason.
- **Fix the file, not Panorama.** Panorama's fixes change only the copy stored in Canvas: the instructor's own file
  keeps every problem, and the next upload of it brings them all back. Tested at WCC (Nov 15, 2026, on two Word
  files and two decks): the earlier warning that Panorama's fix button "scrambles reading order and strips table
  headers" did **not** hold up. Paragraph order, slide shape order and table header rows were unchanged. What it
  does do, and what to tell an instructor who uses it:
  - its AI **rewrites visible text** ("Join Zoom Meeting https://…" became "Join Zoom Meeting Join the Zoom
    meeting"; links became "YouTube video" and "NTP.org"), writes **captions with stray Markdown**
    ("\*Virtualization Essentials\*") and literal alt text ("A black outlined play button…"). Read every
    generated line before accepting it.
  - for slide **reading order** it only offers a "Verify Reading Order" box with "apply to all instances": ticking
    it clears every flag at once, and nothing checks the order for you. The guided fixes include nothing for
    **missing slide titles**.
  - it **recolors** text to pass (white on teal became near-black #121212), which can change a design.
  - before saving it offers to apply the same fixes to **identical copies elsewhere in Canvas**, with those copies
    already ticked and "Apply To Selected Files" as the main button. Choose "Apply To This File Only" unless you
    mean it.
  (Ticking "Verify Reading Order" after a person has checked the order is YuJa's own instruction for that flag;
  the instructor does it, not the skill.)
- **Never stamp someone else's name on a file.** Keep the original author. Remove only tool names
  (`python-docx`, `openpyxl`, `Un-named`, `Steve Canny`). Ask whose name goes in Author if it's empty.
- **Ask before changing format.** Deliver the same format unless a rule below says otherwise (L1), and say why.

---

# Word (.docx) rules
Run `python3 scripts/preflight_docx.py file.docx`. Then, in this order:

1. **Typed structure → real structure** — `docx_lists.py in.docx out.docx`
   [WCAG 1.3.1] Turns typed `- `, `• `, `1. `, `a) ` lines into real Word lists, typed Markdown `## Heading`
   into Heading styles and `**bold**` into bold, and splits a one-paragraph list written with line breaks.
   **Watch for whole files of pasted Markdown or HTML** (lines like `# Title`, `<p><strong>`): AI-drafted
   handouts often are. For a file that is entirely markup, rebuild instead: recover the text, then
   `md2docx.js` (Markdown) or pandoc (HTML). Tell the instructor the markup characters are gone.
2. **Headings** — `docx_headings.py in.docx` lists what it would do; `docx_headings.py in.docx out.docx` applies.
   [WCAG 1.3.1, "The document does not have any headings" Major] Forms, minutes, reports and readings typed with
   bold lines instead of Heading styles all scored 30% at WCC. It promotes all-bold / large standalone lines (the
   first line becomes H1), skips pull quotes and placeholders, and turns runs styled with a heading's
   *character* style ("Heading 2 Char", common in Word's minutes template) into real headings. **YOU** check the
   list; `--map` overrides levels. A letter or template with no heading at all: ask before adding one (a
   "<<Enter subject here>>" Heading 1 placeholder cleared a letterhead template at WCC).
3. **One-cell layout tables → boxed paragraphs** — `docx_unbox.py` [WCAG 1.3.1]. Callout boxes built as 1×1
   tables are announced as tables and flagged for header and caption. Keeps the fill and adds a border.
4. **Pictures** — `docx_alt.py in.docx --list imgs/`, then **YOU** look at each extracted image and its
   nearby text and fill `alt_draft.json` ("" or "decorative" for decoration), then `docx_alt.py in.docx out.docx alt.json`.
   Counts per distinct image, so a logo used 200 times is decided once. Bars or icons that repeat the
   number or words next to them are decorative. Pictures inside text boxes, headers and footers are handled.
   [WCAG 1.1.1, Severe]
   Then **floating pictures → inline** — `docx_inline.py in.docx out.docx` [WCAG 1.3.2, "The Image is not inline
   with the text", **Major**, one per picture]. Each square- or tight-wrapped picture moves into its own
   paragraph right after the text it was anchored to. A converted 2011 brochure held at 30% on this flag alone
   (7 pictures) and scored 100% after it. Header/footer logos weren't counted; text boxes are left alone.
   Render and look: pictures that sat beside text now sit between paragraphs.
5. **Data tables** — `docx_captions.py in.docx /dev/null` prints draft titles from the text above each table;
   **YOU** write `[{"title","summary"}]` and run it for real. Adds a visible 12 pt bold "Table N: title" caption
   (WCC flags a missing visible caption, Major), hidden caption/summary, and `tblLook firstRow="1"` plus a
   repeating header row (Panorama checks tblLook, not just the repeat flag).
6. **Links** — `docx_links.py in.docx` lists every link; **YOU** write `{"shown text": "Name (domain)"}` for
   links whose text is a bare URL and apply. [WCAG 2.4.4, "The hyperlink text is not descriptive", **Major** in
   Word at WCC: a syllabus with 9 bare-URL links held at 30%]. E-mail addresses as link text weren't flagged.
7. **Everything else** — `postprocess_docx.py in.docx out.docx [tables.json] --title "…"`:
   - every font size to ≥ 12 pt in every part (styles, numbering, headers/footers, notes), and a 12 pt default;
   - language en-US everywhere; title (creates the properties part if a generator left it out);
   - **heading levels:** outline-level-only headings get Heading styles, a document that starts at H2 is
     shifted up, no level is skipped (WCC: improper nesting is **Severe** for Word);
   - mid-tone text colors under 4.5:1 on white darkened to ≥ 5:1 (theme colors like pandoc/Word's accent blue
     `4F81BD` fail); justified → left; Word's `[trash]` leftovers removed; schema gaps (`pgMar gutter`) fixed;
   - a heading typed as "A. Course outcomes" / "1. Purpose" gets real heading numbering (the typed marker is
     removed, Word draws the same "A."): WCC flagged those headings as unformatted lists (Major);
   - a properties part that is one self-closing tag gets opened, so the title actually lands (a workbook stayed
     at 30% for "title missing" until this was fixed);
   - tool names removed from author fields, real names kept.
8. Validate (`docx` skill's `validate.py`), render to PDF and look, run the pre-flight again.

Kept from the original skill: real heading styles (D5), H1 first (D6), images inline (D12, now done by `docx_inline.py`), no ASCII art (D13),
descriptive link text (D18, [WCAG 2.4.4]), no empty spacer paragraphs (D22, best practice), list leftover
placeholders like `[instructor]` for the instructor (D23).

**L1. Legacy .doc:** LibreOffice's .doc export drops the table header flag Panorama checks (a fixed .doc stayed
at 30%: "Table does not have a header" ×6, while the same fix as .docx scored 100%). Deliver **.docx** and say why.
**.ppt is worse:** a fixed deck saved back to .ppt by LibreOffice scored 30% with 75 issues (all 52 alt texts,
the document title and the reading order lost), while the same deck as .pptx lost only one table-header mark.
Deliver **.pptx** for a .ppt and say why. .xls round-trips fine (scored 100%). Converting a .doc to .docx also writes numbering levels in an
order Word's schema rejects; `postprocess_docx.py` puts them back in order. A Word 97 brochure went 0% → 100% as
.docx. A .doc that neither Word nor LibreOffice can open is corrupted: ask the owner for another copy.

# PowerPoint (.pptx) rules
Pictures first: `pptx_alt.py deck.pptx --list imgs/`, **YOU** write the JSON, apply (charts and SmartArt are listed
as `chart:<slide>:<name>`). Logos repeated on every slide by the template are **decorative**. Then link text with
`pptx_links.py` (list, write `{"shown text": "Site name (domain)"}`, apply). Then
`python3 scripts/pptx_fix.py in.pptx out.pptx [--title "…"]` **last**, `preflight_pptx.py out.pptx`, and
render every slide before and after: the pictures must be identical apart from the changes you meant.

What `pptx_fix.py` does, and why:
- **P2 Slide titles** [WCAG 2.4.2, Major ×slides]: each slide's heading text box becomes the title placeholder
  (topmost text ≥ 18 pt and ≥ 60% of the largest; never a stat like "85"; never a label on a photo: when two
  or more text boxes sit inside the same picture, none is the title). The box keeps its own look (caps, size,
  color, font, bold, line spacing, anchor, insets and autofit frozen so the master title style can't leak in:
  an earlier draft left bold and spacing open, and three headings turned bold, one moving up over a map). Slides with no heading-like
  text are listed: **YOU** write a title (it may sit off-slide if the design needs it; say so).
- **P6b Group busy slides** [WCAG 1.3.2, Major]: on a slide with the title plus 3 or more other content shapes,
  the title goes first and everything else becomes **one group** in visual order (the picture doesn't change;
  the group is named "Slide content"). Tested at WCC, Nov 15, 2026: a labelled photo, two pictures under a prompt
  box, and a column of three photos beside the title kept "Check reading order" in **every** order tried (4 each,
  the author's own included) and all cleared once grouped; the 29-slide deck then scored 100%. Microsoft's advice
  for this warning is the same ("group objects into logical units"). Not grouped (listed in the report as possible
  flags): slides with body placeholders or media, and slides whose title overlaps the content. `--no-group` turns
  it off. Tell the instructor: the slide looks the same, but its pieces now move together when edited (ungroup in
  PowerPoint to change one). Run `pptx_order_preview.py` before grouping is final if the order matters.
- **P6 Reading order** [WCAG 1.3.2, Major]: content shapes are put in **column-first order** — after any
  full-width band at the top (the title), left column top-to-bottom, then the next column — with decorative
  shapes behind them in their old order (nothing visible moves), **except** decoration drawn on top of a content
  shape it overlaps (a red outline marking a town on a map), which stays just above it (an earlier draft hid one behind a map). This rule was learned from 16 controlled
  test slides at WCC: Panorama flags left-to-right *row* order on multi-column slides, a footer read last when
  it sits under the left column, and a title that isn't first. Card backgrounds hold each card's title and
  body together. Pixel-compare the render before and after: it must be identical.
  Panorama may still ask to "check reading order" on some layouts (a header row with two items above a wide
  body). It is the same test as PowerPoint's own "Check reading order" warning: the order doesn't match one of
  the common spatial patterns. **Tested (Nov 15):** after a person checked the flagged slides, ticking
  **Verify Reading Order** → *Add change to all instances* → *Apply fixes* in Panorama took two decks to 100%
  (2 and 15 flagged slides). Panorama then saves a new version of the file in Canvas (modified by "YuJa
  Panorama API"). **Don't tick it unchecked:** render the slides with the order numbered and look. A slide
  laid out as a table of text boxes (rows of label · points · percent) came out column-by-column, which is
  wrong; fix those by hand in the Reading Order pane first. Strict row order (`--order rows`) was tested
  instead and flagged more slides (8 → 10).
- **P7 Contrast** [WCAG 1.4.3, Severe]: each run is measured against what is actually drawn behind it
  (`pptx_bg.py` paints the slide background, the master's and layout's own artwork, and every picture and filled
  shape below the text box, groups included). **On a photo or banner** a run passes if 90% of the pixels behind
  it give 4.5:1; passing text is left alone; failing text becomes white or black, whichever passes; if neither
  does, the text box gets a fill (the picture's average color, pushed until the text passes) and the report says
  so. *Why:* an earlier draft measured photo labels against the plain slide color, turned white labels on a dark photo gray, and
  WCC's Panorama flagged all 8 (Severe, 0%). Panorama samples the picture. White text on a
  colored box: the **box** is darkened so the text stays white. Otherwise the text color moves just far
  enough to pass. Target **4.5:1 for every size**: WCC flagged 30 pt text at 3.5:1 even though WCAG allows 3:1.
- **P12** all sizes ≥ 12 pt on slides, layouts and masters. **P4/P5** title on one line (line breaks become
  spaces; "Chapter 12" + subtitle becomes "Chapter 12: …"), language en-US.
- Shapes with no text are marked decorative. Pictures with filename alt text ("preencoded.png") count as missing.
  **Text marked decorative** (a textbook deck had every slide title marked decorative) has the mark removed.
- Tables and charts are placed by their own position (`p:xfrm`); before this fix they sorted to the top of the
  order and a table slide was flagged (that deck then reached 100%).
- With template logos marked decorative and the stray decorative marks removed from titles, a 31-slide textbook
  deck went from 28 reading-order flags to 2.
- Placeholders that inherit their position from the layout (no position of their own) are placed where the layout
  puts them. Before this, a title and body both read as top-left and kept their file order, body first.
- **Tested and rejected** (A/B uploads, Nov 15): forcing the title to the front of the order doubled the flags on
  two decks (15 → 30, 7 → 14), and moving decoration after the content didn't help. Keep the column-first visual
  order and decoration at the back.
- **Links** are drawn in the theme's hyperlink color, not the run's: a theme-blue link on a navy slide was
  Severe. Failing links get a passing run color plus PowerPoint's "use the text color for this link" flag.
- A slide whose background is a **picture or gradient** isn't recolored (its real contrast can't be computed);
  those slides are listed for a check by eye.
- Files saved by LibreOffice: the duplicate core-properties part python-pptx creates is removed (otherwise the
  deck won't open).
- **P10 Link text that is just the URL** (Major) is listed: **YOU** write "Site name (domain)" so the audience
  still sees the address.
- **P13 media:** embedded audio/video is listed; captions or a transcript are the instructor's job.

# Excel rules
`python3 scripts/xlsx_fix.py in.xlsx out.xlsx --title "…" [--author "…"]`. Edits the package XML (never
re-saves with openpyxl, which drops charts and validation).
- X1 title (Major). X2 every font ≥ 12 pt; column widths and row heights scaled so numbers don't become `####`
  (Panorama counts small fonts **per cell**: 343 issues in one workbook). X3 language.
- X4 **cell A1** must hold text (Minor at WCC; only the first sheet was flagged): reported; **YOU** write a short
  sheet description and pass it with `--a1 "Sheet name::text"`.
- Charts, merged cells and embedded charts were **not** flagged by WCC's Panorama in Excel or PowerPoint, and
  neither were PowerPoint tables or embedded video (captions are still the instructor's job).
- X5 Excel tables need a header row. X6 tool names out of author fields.

# PDF rules
**Decide the route first:**
- **There's a source file** (Word, PowerPoint): fix the source, export again. Don't patch the PDF.
- **No source, long text document:** rebuild through Word (pipeline below).
- **Scanned** (no text layer): OCR rebuild (`scan2md.py`). Tested: a scanned chapter went 0% → 100%.
  OCR mangles multi-column layouts and side boxes: the instructor **must proofread** names, numbers and quotes.
  For a few pages you may read the page images yourself and type the Markdown instead; it's more accurate.
- **Designed one-pager** (InDesign flyer, poster) that is already tagged: fix **in place** with `pdf_tagfix.py`
  so the design survives. Tested on two InDesign flyers: 0% → 70% (only Minor small print left), and 0% → 0%
  with contrast, alt, headings and title cleared but one Severe "Check reading order" whose trigger isn't
  known yet (two-column layout with list bullets tagged apart from their text). Report it; the design file is
  the real fix.

**Printed from a browser, Google Docs or Google Forms** (Skia/Chrome PDFs, already tagged): `pdf_tagfix.py` fixes
in place. **F13** "List item structure is missing" (Major, every Chrome-printed list): each <LI> gets an <Lbl> and
an <LBody> (a label that speaks as a bullet if the page drew none); this took three printed reports from 30% to
70%. **F14** table summaries with `"summary"`. **F16** headings: Chrome tags every heading's text inside a plain
child tag, and WCC counted each heading as "The tag is empty" (Minor, 11 on a 3-page sheet); `pdf_tagfix.py` now
gives headings their text directly (`hoist_text`, default). Only headings: doing the same to paragraphs made WCC
flag "Check reading order" (Severe, 0%) at page breaks.
**Small print** (7.5–10 pt; Minor, one flag per run of text) can't be enlarged inside the PDF without breaking
the layout. Rebuild from the tags instead (Nov 15: three Chrome prints, 30–70% → 100%):
`pdf_tag2html.py in.pdf out.html [--landscape] [--describe-links]` → `google-chrome --headless=new
--no-pdf-header-footer --print-to-pdf=raw.pdf out.html` → `pdf_tagfix.py raw.pdf fixed.pdf fix.json` (table
summaries) → `content_check.py in.pdf out.html` (only the page footers and repeated table headers may be
missing). The rebuild reads the structure tree (headings, tables with header scopes, lists, links, bold and
italic), prints everything at 12 pt or more, writes bullets as text (a drawn disc leaves an empty list label),
puts "—" in empty table cells (an empty cell is an empty tag), and turns bare-address link text into labels like
"Facebook post (facebook.com)" with `--describe-links` (**YOU** read the printed list). Use `--landscape` for
wide tables. It does **not** fix a PDF whose tag order is itself wrong (a 14-page InDesign guide came out with
lists run together and pictures misplaced): that needs the design file.
**Google Forms summary prints** (charts are untagged drawings with their labels loose): `pdf_tag2html.py in.pdf
out.html --cards alts.json` cuts each chart out as a picture under its question heading, drops the "Copy chart"
buttons and lists typed answers (a 20-question survey print: 0% → 100%). **YOU** look at each chart and write `{"start of question": "Pie chart, 32
responses: No 59.4%, Yes 31.3%, Part-time 9.4%."}`; use the PDF's own percentages, not your reading of the slices.
Google Forms "print summary": every legend entry is a <Figure> made of letter outlines, so 40 alt texts were
missing (0%). `pdf_ocr_alt.py` reads each one with OCR and uses the words as its alt; proofread them.
**Untagged** browser prints score 0%: rebuild with `pdf_flow2md.py` (one-column text → Markdown → Word → tagged
PDF); a 4,900-word essay went 0% → 100%. Put a blank line between list items in the Markdown for `md2docx.js`.

**PDF checks** (`preflight_pdf.py`): F1 title + DisplayDocTitle; F2 language; F3 tagged; F4 headings from H1;
F5 figure alt; F6 table /Summary; F7 header cells; F8 no untagged text; F9 nothing under 12 pt;
**F10 no glyph off the baseline** and **F11 no footnote tags**: at WCC a tagged PDF with *any* sub/superscript
or real footnote gets **"Check reading order" (Severe → 0%)**. Fix in the .docx before export:
`fix_baseline.py` (sub/superscripts → Unicode ₀–₉ ⁰–⁹, raised/lowered runs too) and `inline_notes.py`
(footnotes → "Note N:" paragraphs after the citing paragraph). **F12** text drawn twice in the same place
(an outline layer under a fill) is read twice: `pdf_tagfix.py drop_empty` keeps the top copy.

**Rebuild pipeline** (textbook chapter, 0% → 100% at WCC):
`pdf2md.py in.pdf layout.json out.md` (or `region.py` per area) → check the Markdown against the page images →
`node md2docx.js out.md out.docx "Title" "Description"` → `postprocess_docx.py out.docx fixed.docx out.docx.tables.json`
→ `fix_baseline.py` / `inline_notes.py` if needed → `export_pdf.sh fixed.docx` (LibreOffice, tagged PDF/UA) →
`postprocess_pdf.py fixed.pdf final.pdf tables.json` (adds table /Summary LibreOffice doesn't write; for a .docx you wrote yourself,
`docx2pdf_ua.py in.docx out.pdf` does both and reads each table's description from the .docx) →
`preflight_pdf.py final.pdf` → `content_check.py original.pdf fixed.docx`.

**In-place fix** (`pdf_tagfix.py in.pdf --list` numbers every paragraph-level tag and figure with its text):
JSON keys `title`, `lang`, `alt` {n: text}, `headings` {n: "H1"}, `actualtext` {n: text},
`colors` [["old op","new op"]] (exact operators from the page stream, fills lowercase `rg`/`k`, outlines
uppercase `RG`/`K`), `drop_empty`. QR codes: decode them (OpenCV `QRCodeDetector`) and say where they go.

# HTML rules
`preflight_html.py page.html` (links, alt, captions, headings, length, pasted report markup), then
`html_fix.py page.html out.html --fix` which renders the page in headless Chrome and fixes what Panorama
measures on the rendered page:
- **Contrast** (Severe): rewrites failing `color:` values in the page's own CSS; adds a solid
  `background-color` under every CSS gradient (checkers treat gradients as white, so light text on a dark
  gradient "fails" even when it doesn't); text that is `transparent` until a script shows it is reported —
  move it into CSS `::before` on the active state or set it in the script.
- **Font size** (Minor ×elements): every px/pt/rem size below 16px raised to 16px (12 pt).
- **YOU**, by hand: link text ("Read", bare domains like `dl.acm.org`, filenames, "click here" were flagged),
  empty links, alt text. Canvas pages may start at H2 (Canvas supplies the H1); that passed.
- **Remove pasted Panorama report markup** (`panorama-html…`, `MuiList…`): copying from Panorama's preview
  can paste its overlay into a page.

# Can't be fixed in the file (report these)
- **Instagram / sites that block checkers:** Panorama gets HTTP 429 and calls the link broken (Major). It comes
  and goes: the same unchanged page re-uploaded on Nov 15 had no broken-link flag. Re-scan before changing
  anything; if it stays, keep it and accept the flag, have the instructor dismiss it, or remove the link.
  Rewriting the address doesn't help (an `http://` form scored worse).
- **"Check reading order of slide" that remains** after `pptx_fix.py`: the instructor checks the order (fixing
  any slide that is wrong) and ticks Verify Reading Order in Panorama; that clears it (tested, 100%).
- **Small print in a designed PDF** (8–11 pt legal lines): needs the InDesign/Canva source.
- **"Check reading order" (Severe) on designed PDFs** (a 14-page brand guide, two-column flyers): fix the design
  file's reading order and export again. (Google Forms prints are now rebuilt with `--cards`.)
- **Files the tools can't open** (a password-protected or damaged .doc): Panorama may still score them; ask the
  owner for an unprotected copy.
- **Pages over 3000 words** (Minor): `html_split.py page.html out` splits at section headings into parts under
  3000 words (a 3,839-word syllabus page: two parts, both 100%). **Only if the instructor says yes**; keeping one
  long page is a fine answer, and the report then lists the length flag. If split, link the parts in Canvas.
- **Accuracy:** alt text, OCR text and captions must be checked by a person. Media captions are out of scope.

# Delivering
Send the fixed file(s) and put the **complete report from `fix_report.py`** (one per output file) in the chat,
as it prints it: the predicted Panorama score, what was fixed and changed, added text, the instructor's decisions,
what Panorama will most likely still flag and why, and what to check by hand. Then ask whether they want the
report as a PDF too (`--pdf`). The predicted score is a prediction from the skill's checks:
say so, and say that Panorama scores the file on upload. Never claim WCAG 2.2 AA compliance from a Panorama score.

**Your own PDFs count too.** A report or handout you generate for the instructor (a `fix_report.py --pdf`, a guide, a comparison)
is a file headed for Canvas like any other. Nov 15: two PDFs built with a plain LibreOffice export scored **70%** ("Table does not
have a summary", Minor) while their preflight looked fine except F6 (0/2). Rebuilt with `docx2pdf_ua.py` (F6 2/2) they scored 100%.
Run `preflight_pdf.py` on every PDF you deliver and treat an F6 miss as a stop.

# Testing in Canvas (optional)
Upload to an **unpublished, hidden** folder only, log each upload with its rollback (delete the file), and
read the score from the file list (the Panorama icon's label reads "Score: N%"). Scans take 1–15 minutes.
- **Upload from the page with Canvas's own files API** (`POST /api/v1/folders/<id>/files`, then the returned
  upload URL, with the page's `_csrf_token` cookie as `X-CSRF-Token`): putting a file into the page's hidden
  file input did not start an upload. Browser tools cap a file at about 3.8 MB: split a bigger file
  (`split -b 3500000`), load the parts one at a time, join them in the page (`new File(parts, name)`) and
  check the uploaded size matches.
- **Test one hypothesis per slide in small decks:** copy the slides in question into a deck of their own
  (images shrunk, layout unchanged) so each flag can be traced. In the report, the issue navigator ("9 / 12")
  steps through flags in slide order and scrolls the preview to each one.
- Leaving the report while a guided fix is open asks about "unsaved accessibility changes": Confirm only
  discards the guided fix you didn't make.

# Scripts (in `scripts/`)
| Script | Does |
|---|---|
| preflight_docx.py / preflight_pptx.py / preflight_pdf.py / preflight_html.py | report problems; change nothing |
| docx_lists.py | typed bullets/numbers/Markdown → real lists, headings, bold; splits one-paragraph lists |
| docx_unbox.py | 1×1 layout tables → shaded, bordered paragraphs |
| docx_alt.py | alt text / decorative per distinct image, headers and footers too (`--list` to extract) |
| docx_inline.py | floating pictures → inline, each in its own paragraph after its anchor text |
| docx_captions.py | visible captions + table caption/summary + header-row flags |
| postprocess_docx.py | sizes, language, title, heading levels, contrast, author, schema fixes |
| fix_baseline.py / inline_notes.py | before PDF export: sub/superscripts and footnotes that make WCC's PDF check Severe |
| pptx_fix.py / pptx_alt.py | slide titles, title-first + grouped busy slides, column-first reading order, contrast, sizes, title / picture alt text |
| pptx_bg.py | what is really behind a slide's text (background, master art, pictures, fills): used by the fixer and the pre-flight's contrast check (P7) |
| xlsx_fix.py | workbook title, 12 pt fonts + widths, A1 and header checks |
| rtf_post.py | heading outline levels and 12 pt in RTF exported by LibreOffice |
| pdf2md.py, region.py, layout.json, md2docx.js, export_pdf.sh, postprocess_pdf.py, content_check.py | PDF rebuild pipeline |
| docx2pdf_ua.py | one step: .docx → tagged PDF/UA with table /Summary. **Use it for every PDF you build from a .docx that has tables, including your own reports and handouts** |
| scan2md.py | OCR a scanned PDF to Markdown for the rebuild |
| fix_report.py | the report that goes with every output: changes, decisions, what to check, predicted Panorama flags and score; printed in full for the chat, `--pdf` for an accessible PDF copy |
| pptx_order_preview.py | slides rendered with the reading order numbered, to ask the instructor; answers go back as `pptx_fix.py --keep-order` / `--order-file` |
| pdf_tagfix.py | fix a tagged PDF in place (flyers, posters, browser prints): title, headings, alt, colors, lists, table summaries |
| pdf_flow2md.py | untagged one-column PDF (saved web page) → Markdown for the rebuild |
| pdf_tag2html.py | tagged browser/Google print → clean 12 pt HTML from its structure tree (then print and `pdf_tagfix.py`); `--cards` for Forms summaries, `--describe-links` for bare-address links |
| html_split.py | split an HTML page over 3000 words at section headings |
| pdf_ocr_alt.py | alt text for figures that are text drawn as shapes (Google Forms charts) |
| docx_headings.py | real Heading styles for bold lines, first lines and heading character styles |
| pptx_links.py / docx_links.py | descriptive text for links that show a bare URL |
| odf_colors.py | last step for .odt/.odp/.ods: darken mid-tone colors, 12 pt minimum |
| html_fix.py | rendered contrast and font-size fixes for HTML (Playwright + Chrome) |

## Add to this list
When WCC's Panorama flags something not covered here, add the exact flag text, its severity at WCC, the file
type, and the fix that cleared it — tested by re-uploading — to the issue table above.

# Version log
Versions run v1.00, v1.01, v1.02 and so on. The skill's `name:` stays `wcc-canvas-ready` in every version; the number
lives in the title above and in this log. Bump it for each change that goes out, and say in the report what changed.
- **v1.00** (Nov 15, 2026): first release. Includes `docx2pdf_ua.py` (table /Summary in one step), the `export_pdf.sh`
  table warning, and the "your own PDFs count too" rule, added after two plain-export PDFs scored 70%.
- **v1.01** (Nov 16, 2026): update check. `scripts/check_update.py` reads `VERSION` on GitHub and tells the instructor in one line
  when a newer version exists (notify only; silent if offline or blocked). Added the "Update check" step above.
- **v1.02** (Nov 16, 2026): update check now works when the script sandbox has no internet (first seen on a Free account).
  `check_update.py` tries four GitHub hosts, prints `UPDATE CHECK BLOCKED` when none answers, and takes `--compare` so Claude can
  read the releases page with its web tool instead. Rule added: a check that could not run is never reported as "up to date".
  Also new: "No file in the chat?" section, so a new user who hasn't attached anything gets step-by-step help adding the file.
