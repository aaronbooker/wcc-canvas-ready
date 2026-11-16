# WCC Canvas Ready: notes for Claude Code sessions

This repository is the home of the `wcc-canvas-ready` skill. Work on the skill happens here, on branches, with Aaron Booker reviewing. Read this file, `README.md`, `CONTRIBUTING.md` and `CHANGELOG.md` before changing anything.

## What this is

A Claude skill for Whatcom Community College (WCC) faculty. It fixes Word, PowerPoint, Excel, PDF and HTML course files so they score 100% in WCC's YuJa Panorama in Canvas, without rewriting, summarizing or losing content. It began as Chris Pasquini's `canvas-accessible-docx` skill. Aaron Booker maintains it. Other WCC faculty contribute.

The audience is faculty, many of them new to Claude and on Free accounts. Anything a faculty member reads (README, guide, the skill's chat messages) must be plain, short and free of developer jargon.

## Layout

- `wcc-canvas-ready/`: the skill source (`SKILL.md` and `scripts/`). Edit here.
- `wcc-canvas-ready.zip`: the installable build of that folder. Never edit by hand. Rebuild at release time.
- `VERSION`: one line, read over the network by `scripts/check_update.py` in installed copies. Changing it on `main` tells every installed copy that an update exists.
- `docs/`: the faculty guide (CC BY 4.0).
- `CHANGELOG.md`, `README.md`, `NOTICE`, `LICENSE`, `CONTRIBUTING.md`.

## Current phase: before go-live (set November 16, 2026)

Aaron is the only person using the skill right now. Until he says it has been released to other faculty, changes to the skill, `VERSION` and the zip cannot affect anyone else, so they do not need the caution described below. He will say when that changes.

The plan: review a colleague's PDF and PowerPoint skill and likely merge it into this one, with the work recorded in the changelog under the current 1.0 series. Go-live to all faculty is the next tenth after that. Handout and README updates for faculty can wait for go-live.

Once Aaron says the skill is live, delete this section and follow the rules below in full.

## Rules for working here

- Aaron is the human in the loop and edits files himself. Re-read the current version of any file before changing it. Never overwrite his edits.
- Work on a branch and open a pull request. Do not commit to `main` unless Aaron says to in that session.
- Do not change `VERSION` on `main`, rebuild the zip, or describe something as released unless Aaron asked for a release. `VERSION` is live: installed copies read it.
- This repository is public. Do not commit student information, colleagues' names without their consent, colleagues' course files, Canvas course or file IDs, or email addresses beyond the one already in the README.
- Test files that belong to colleagues stay out of the repository.
- A predicted Panorama score is a prediction. Only say a file scores 100% when Panorama reported it. Say which results were verified and which were not.
- Never tell a user the skill is "up to date" unless the update check confirmed it.

## Accessibility

This is WCC work. Everything produced here meets WCAG 2.2 Level AA (WCAG 2.1 AA is WCC's floor): contrast 4.5:1 for body text and 3:1 for large text and interface parts, headings in order, data tables with a caption and scoped header cells, alt text on informative images, visible keyboard focus, no meaning by color alone, PDFs tagged to PDF/UA with title and language set. PDFs in `docs/` must score 100% in Panorama themselves. Build them with `wcc-canvas-ready/scripts/docx2pdf_ua.py`, because a plain LibreOffice export omits the table summaries Panorama checks.

Panorama is not a WCAG audit. Some Panorama checks go beyond WCAG (12 point minimum, visible table captions, text in cell A1, no justified text), and Panorama cannot judge some WCAG requirements. Keep that distinction in anything written for faculty.

## Versions and releases

Versions run v1.00, v1.01, v1.02 and so on; a larger change moves to the next tenth (v1.10). Comparison is numeric for each part. The skill's `name:` stays `wcc-canvas-ready` in every version.

A release changes all of these together:

1. `VERSION`
2. `wcc-canvas-ready/SKILL.md`: the title, the "Delivered by" line, and the Version log at the end
3. `CHANGELOG.md`
4. `README.md` (the "Current version" line and the "Folder layout" line)
5. `wcc-canvas-ready.zip`, rebuilt so that `wcc-canvas-ready/` is the single top-level folder, with `LICENSE` and `NOTICE` copied into it
6. A GitHub release tagged `vX.YY` with the zip attached. Cloud sessions cannot create releases through the API. Aaron publishes them in the browser at `releases/new?tag=vX.YY`.

Before a release, run `python3 -m compileall -q wcc-canvas-ready/scripts` and confirm the zip's `SKILL.md` matches the source.

## Folding in another contributor's skill

Get the contributor's permission and their preferred credit first. Record the credit in `NOTICE` and the README. Their contribution comes in under Apache 2.0 (see `CONTRIBUTING.md`). Bring it in on its own branch, compare rule by rule against the existing scripts, and test each adopted rule against Panorama before merging.

## Licensing

Software and documents are licensed separately, because Creative Commons licenses are not meant for software. Apache License 2.0 for the skill (`wcc-canvas-ready/`, the zip, and files not listed next). CC BY 4.0 for `README.md` and everything in `docs/`, including the faculty guide. CC BY requires named attribution and a note of any changes, so the guide must carry its own license line and credit when it is next rebuilt. Keep `NOTICE` accurate when contributors are added.
