# WCC Canvas Ready

A skill for Claude that gets course files ready for Canvas at Whatcom Community College. You give Claude a Word, PowerPoint, Excel, PDF or HTML file. The skill fixes what YuJa Panorama flags, asks you before it makes any big change, and reports everything it did. The goal is a file that scores 100% in Panorama the first time you upload it, with nothing rewritten, summarized or lost.

**Current version: 1.04** (November 16, 2026). See the [changelog](CHANGELOG.md).

## Download

[Download wcc-canvas-ready.zip](https://github.com/aaronbooker/wcc-canvas-ready/releases/latest/download/wcc-canvas-ready.zip) (the latest release, version 1.04). Save it and do not unzip it.

A written guide for faculty is in [docs](docs/WCC_Canvas_Ready_Skill_Guide_2026-11-15_v5.pdf).

## Install in Claude

Works on Free and paid Claude accounts. Based on Anthropic's Help Center article "Use skills in Claude".

1. In Claude, open Settings, then Capabilities, and make sure "Create and edit files" is on.
2. Go to Customize, then Skills.
3. Select +, then Create skill, then Upload a skill, and choose the ZIP.
4. If you installed Chris Pasquini's earlier `canvas-accessible-docx`, delete it first so Claude does not choose between two similar skills.
5. Start a new chat, attach a file, and say you want it ready for Canvas.

## Check your version and update

**The skill tells you.** From version 1.01 on, at the start of a chat the skill asks GitHub for the current version number and, if a newer version exists, shows you a short message with the download link and three steps to install it. It cannot install the update for you. If the script can't reach GitHub (many accounts run scripts with no internet), it says so and Claude reads the releases page with its web tool instead. It never reports "up to date" for a check that could not run. The request is one read-only download of a one-line text file (`VERSION` in this repo). Nothing about you, your files or your chat is sent; GitHub sees it like any web visit. If you installed version 1.00, which has no check, reinstall once to get it.

**Ask it.** Start a new chat and type: Use the WCC Canvas Ready skill and tell me which version it is and whether there is an update. Claude should report the installed version and the latest one.

**Get notified by GitHub.** With a GitHub account, open this repository, choose Watch, then Custom, then Releases. Without one, add the [releases feed](https://github.com/aaronbooker/wcc-canvas-ready/releases.atom) to a feed reader.

**To update:**

1. Download the latest ZIP from the link above.
2. In Customize, then Skills, open WCC Canvas Ready, turn it off, select the three-dot button, choose Delete, and confirm.
3. Upload the new ZIP as in the install steps, then check the version again.

## What it does not do

- A 100% Panorama score is not proof of WCAG 2.2 AA. Panorama cannot judge whether alt text is accurate, whether reading order makes sense, or whether video captions are right.
- The predicted score in the skill's report is a prediction. Panorama scores the file when you upload it.
- Claude can make mistakes. Read what changed before you post a file to students.
- Do not give Claude files that contain student names, grades or other student records.

## Folder layout

- `wcc-canvas-ready.zip`: the installable skill, version 1.04.
- `VERSION`: the current version number, read by the skill's update check.
- `wcc-canvas-ready/`: the same skill as plain files (`SKILL.md` and `scripts/`) so you can read what it does.
- `docs/`: the faculty guide.
- `CHANGELOG.md`: what changed in each version.

## Credit

Built on the work of Chris Pasquini (WCC), whose `canvas-accessible-docx` skill is the starting point. Rebuilt and tested against Panorama by Aaron Booker (WCC, Computer Information Systems), with test files contributed by WCC colleagues.

## Feedback

If Panorama flags something the skill missed, open an issue here or email abooker1@whatcom.edu with the exact flag text, the file type, and what cleared it.
