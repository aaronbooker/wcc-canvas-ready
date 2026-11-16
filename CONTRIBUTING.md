# Contributing to WCC Canvas Ready

Thank you for helping. This skill is built by Whatcom Community College faculty for WCC faculty, and it gets better each time someone shows it a file it handled badly.

## Ways to contribute

- **Report a miss.** If YuJa Panorama flags something the skill did not fix, open an issue with the exact flag text, the file type, and what cleared it, if you found out.
- **Share a fix or a rule.** If you built your own skill or script for the same job, we would like to fold it in with credit to you.
- **Improve the guide.** Corrections to the README and the faculty guide are welcome.

## Never include student information

Do not put files with student names, grades, ID numbers or other student records in an issue, a pull request or a test file. Use your own course materials, and remove anything that identifies a student first. This repository is public.

## How changes get in

1. Open an issue first for anything larger than a typo, so we can agree on the approach.
2. Fork the repository, or create a branch if you have write access. Do not commit to `main` directly.
3. Make the change under `wcc-canvas-ready/` (the skill source). Do not edit `wcc-canvas-ready.zip` by hand. The zip is rebuilt from the source at release time.
4. Test it (see the next section).
5. Open a pull request that says what changed, which files you tested, and each file's Panorama score before and after.

Aaron Booker reviews and merges pull requests and publishes releases.

## Testing

A change is ready when all of these are true:

- Every Python script still compiles: `python3 -m compileall -q wcc-canvas-ready/scripts`
- The file that prompted the change scores 100% in WCC's Panorama after the skill runs on it. A predicted score is not enough. Upload the output to a Canvas course and read Panorama's report.
- A file of each other type you touched (Word, PowerPoint, Excel, PDF, HTML) still scores what it scored before.
- Nothing in the file was rewritten, summarized or lost.

Panorama is configured by each institution. A rule that passes at another college may not pass at WCC, and the reverse. This skill targets WCC's Panorama.

## Versions and releases

Versions run v1.00, v1.01, v1.02 and so on. A larger change, such as folding in another contributor's skill, moves to the next tenth (v1.10). Comparison is numeric for each part, so 1.10 is newer than 1.09.

Contributors do not need to bump the version. The maintainer does it at release time, in every one of these places:

- `VERSION`
- The title, the "Delivered by" line and the Version log in `wcc-canvas-ready/SKILL.md`
- `CHANGELOG.md`
- `README.md` (two places)
- `wcc-canvas-ready.zip`, rebuilt from `wcc-canvas-ready/`
- A GitHub release tagged `vX.YY` with the zip attached

## Licensing of contributions

The software and the written documents have separate licenses. The skill is licensed under the [Apache License 2.0](LICENSE). The README and everything under `docs/`, including the faculty guide, are licensed under [CC BY 4.0](docs/LICENSE).

By submitting a contribution you agree that it is licensed under the same terms as the part you changed (Apache License 2.0 for the skill, under section 5 of that license; CC BY 4.0 for the README and `docs/`), and you confirm that you have the right to contribute it. If you wrote it as part of your job, check that your employer allows you to release it.

If you contribute code or text that someone else wrote, say so in the pull request and include its license.

## Credit

Contributors are credited in the README and in `NOTICE`. Tell us in your pull request how you would like to be named, or if you would rather not be named.

## Accessibility of this repository

This project exists to make course files accessible, so its own documents meet WCAG 2.2 Level AA: headings in order with no skipped levels, link text that says where the link goes, alt text on images, and no meaning carried by color alone. PDFs in `docs/` must be tagged and must score 100% in WCC's Panorama themselves.
