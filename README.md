# WCC Canvas Ready

A skill for Claude that gets course files ready for Canvas, the learning management system (LMS) at Whatcom Community College. You give Claude a Word, PowerPoint, Excel, PDF or HTML file. The skill fixes what Panorama flags in Canvas, asks you before it makes any big change, and reports everything it did. The goal is a file that scores 100% in Panorama the first time you upload it, with nothing rewritten, summarized or lost.

**Current version: 1.1.0** (November 19, 2026). See the [changelog](CHANGELOG.md).

## Files it handles

| Type | Formats |
|---|---|
| Word | .docx, plus older .doc, .rtf, and OpenDocument .odt (LibreOffice) |
| PowerPoint | .pptx, plus older .ppt, and OpenDocument .odp |
| Excel | .xlsx, plus older .xls, and OpenDocument .ods |
| PDF | ordinary PDFs, scans, designed flyers, fillable forms, slide decks saved as PDF, and PDFs printed from a browser, Google Docs or Google Forms |
| HTML | web pages |

- **Google Docs, Sheets and Slides:** download the file first (File, then Download, then Word, Excel or PowerPoint) and give Claude that copy. Claude can't open Google Drive or Canvas links.
- **Older formats:** a fixed .doc comes back as .docx and a .ppt as .pptx, because saving them in the old format loses things Panorama checks. Claude asks first.

## Download

Open the [latest release](https://github.com/aaronbooker/wcc-canvas-ready/releases/latest) and, under **Assets**, select **wcc-canvas-ready.zip** (not "Source code"). Save it and do not unzip it. Updates come from the same page.

**[Install or update, step by step with pictures](docs/install-and-update.md).** A longer written guide for faculty is in [docs](docs/WCC_Canvas_Ready_Skill_Guide_2026-11-19_v11.pdf).

## Install in Claude

Works on Free and paid Claude accounts. Based on Anthropic's Help Center article "Use skills in Claude".

1. In Claude, open Settings, then Capabilities, and make sure "Create and edit files" is on.
2. Go to Customize, then Skills. (Claude is renaming Customize to Plugins, so you may see that name.)
3. Select + Add, then Upload skill. Drag in the ZIP or select browse to choose it, then select Upload. Do not unzip it first.
4. Open wcc-canvas-ready in your skills list and check that its switch is on.
5. If you installed Chris Pasquini's earlier `canvas-accessible-docx`, delete it so Claude does not choose between two similar skills.
6. Start a new chat, attach a file, and say you want it ready for Canvas.

## Check your version and update

**The skill tells you.** From version 1.01 on, at the start of a chat the skill asks GitHub for the current version number and, if a newer version exists, shows you a short message with the download link and three steps to install it. It cannot install the update for you. If the script can't reach GitHub (many accounts run scripts with no internet), it says so and Claude reads the version number with its web tool instead (the one-line `VERSION` file first, the releases page only if that fails). It never reports "up to date" for a check that could not run. The request is one read-only download of a one-line text file (`VERSION` in this repo). Nothing about you, your files or your chat is sent; GitHub sees it like any web visit. If you installed version 1.00, which has no check, reinstall once to get it. Versions before 1.0.5 used two-part numbers (1.00 to 1.04) and do not recognize the new three-part numbers, so reinstall those once as well.

**Ask it.** Start a new chat and type: Use the WCC Canvas Ready skill and tell me which version it is and whether there is an update. Claude should report the installed version and the latest one.

**Get notified by GitHub.** With a GitHub account, open this repository, choose Watch, then Custom, then Releases. Without one, add the [releases feed](https://github.com/aaronbooker/wcc-canvas-ready/releases.atom) to a feed reader.

**To update:**

1. Open the [latest release](https://github.com/aaronbooker/wcc-canvas-ready/releases/latest) and download wcc-canvas-ready.zip under Assets. Do not unzip it.
2. Upload it as in the install steps (Customize, then Skills, then + Add, then Upload skill). You do not need to delete the old version first.
3. If Claude asks whether to replace the WCC Canvas Ready you already have, say yes.
4. Start a new chat and check the version again.

The [step-by-step guide with pictures](docs/install-and-update.md) shows each of these screens. Only download the skill from this GitHub site.

## Limitations

### What Panorama's score does and doesn't tell you

- A 100% Panorama score is not proof of WCAG 2.2 AA. Panorama cannot judge whether alt text is accurate, whether reading order makes sense, or whether video captions are right.
- The score in the skill's report is a prediction. Panorama scores the file when you upload it. In testing, the prediction matched Panorama on 62 of 63 fixed files, but it was tuned on those same files, so expect it to be right a little less often on new ones.

### Files that may not reach 100%

- Not every file gets there. In a November 2026 test of 50 course files, 48 scored 100% in Panorama. Two stayed at 70%: an interactive web page whose program code Panorama counts as more than 3,000 words, and a designed PDF flyer whose small print can only be fixed in the original design file.
- A page over 3,000 words is flagged by Panorama and stays below 100% unless it is split. The skill asks before splitting anything.
- A fillable PDF form is rebuilt without its fill-in boxes, so students print it or type into a Word copy. Keeping the fillable original means it stays at 0%.
- An old .doc or .ppt is delivered as .docx or .pptx. Saved back in the old format, it scored 30% in testing.

### Things you still need to check or do yourself

- Read the alt text, captions and headings the skill adds. They are drafts.
- Proofread anything rebuilt from a scan. The words are read from a picture of the page, and names, numbers and quotes can come out wrong, especially in columns and side boxes.
- It does not caption or transcribe videos.
- It can't fix a photo of a page, a video file, or an Apple Pages, Keynote or Numbers file. Export those to Word, PowerPoint, Excel or PDF first.
- It can't open Canvas, Google Drive or OneDrive links. Download the file and attach it.
- On a Free Claude account, a long or picture-heavy file can use up your usage allowance quickly. Start with one small file.
- Claude can make mistakes. Read what changed before you post a file to students.
- Do not give Claude files that contain student names, grades or other student records.

## Folder layout

- `wcc-canvas-ready.zip`: the installable skill, version 1.1.0.
- `VERSION`: the current version number, read by the skill's update check.
- `wcc-canvas-ready/`: the same skill as plain files (`SKILL.md` and `scripts/`) so you can read what it does.
- `docs/`: the faculty guide, and `install-and-update.md`, the install and update steps with pictures (in `docs/images/`).
- `CHANGELOG.md`: what changed in each version.
- `LICENSE` and `NOTICE`: the license and the credit that must stay with any copy.
- `CONTRIBUTING.md`: how to suggest a fix or add your own work.

## Credit

Built on the work of Chris Pasquini (WCC), whose `canvas-accessible-docx` skill is the starting point. Rebuilt and tested against Panorama by Aaron Booker (WCC, Computer Information Systems), with test files contributed by WCC colleagues. Monica Riess is a collaborator: she shared her PDF and PowerPoint accessibility skills, and parts of them are being folded into this one. Developed for Whatcom Community College. Thank you, Chris and Monica.

- Chris Pasquini: [WCC staff directory](https://www.whatcom.edu/Home/Components/StaffDirectory/StaffDirectory/2304/), [LinkedIn](https://www.linkedin.com/in/chris-pasquini/)
- Aaron Booker: [WCC staff directory](https://www.whatcom.edu/Home/Components/StaffDirectory/StaffDirectory/4122/), [LinkedIn](https://www.linkedin.com/in/aaronbooker/)
- Monica Riess: [LinkedIn](https://www.linkedin.com/in/monica-riess-02301854/)

## License

You may use, copy, change and share this work, including at other colleges, as long as you keep the credit above with it. The software and the written documents have separate licenses.

- **The skill (software)** is licensed under the [Apache License 2.0](LICENSE). Keep the [NOTICE](NOTICE) file with any copy or adaptation.
- **This README and the faculty guide** (everything in `docs/`) are licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](docs/LICENSE). If you share or adapt them, name the authors, link to the license, and say whether you made changes.

Suggested credit for the documents: "WCC Canvas Ready" by Chris Pasquini, Aaron Booker and Monica Riess, Whatcom Community College, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). If you changed the document, add "Adapted from the original".

The skill comes with no warranty. This is not an official Whatcom Community College publication.

## Contributing

Fixes, new rules and other faculty members' skills are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). Do not include student information in anything you send.

## Feedback

The best help is your files. Email your original file, the one from before you used the skill, to abooker1@whatcom.edu. Nothing else is needed: Aaron runs it through the skill himself. Take out student names, grades and records first. Files are used only for testing and are not posted here.
