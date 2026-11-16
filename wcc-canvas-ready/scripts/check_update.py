"""Tell the instructor when a newer WCC Canvas Ready exists. Notifies only; it cannot update the skill.

Usage:
  python3 -I check_update.py              one line of output at most (see below)
  python3 -I check_update.py --verbose    always says what it found, and how
  python3 -I check_update.py --compare 1.03 [--verbose]
        no network: compares the installed version with a version number Claude read
        from the releases page with its own web tool

Default output, exactly one of:
  UPDATE AVAILABLE: ...     GitHub lists a newer version. Prints the line plus three plain steps; show all of it to the instructor.
  (nothing)                 GitHub answered and this copy is current.
  UPDATE CHECK BLOCKED: ... this sandbox could not reach GitHub at all. That is NOT "up to date".
                            SKILL.md says what Claude does next (web fetch fallback).

Many Claude accounts run scripts in a sandbox with no internet, or with a short allowlist, so the
script tries several GitHub hosts and gives up within a few seconds. Always exits 0.
Privacy: read-only requests for a version number. No file names, file contents, chat text or account
details are sent. GitHub sees the request like any web visit (IP address, this script's name as the agent).
Only the standard library is used."""
import datetime, json, os, re, sys, time, urllib.error, urllib.request

REPO = 'aaronbooker/wcc-canvas-ready'
DOWNLOAD_URL = 'https://github.com/%s/releases/latest' % REPO
AGENT = {'User-Agent': 'wcc-canvas-ready-update-check'}
TIMEOUT = 3          # seconds per host
BUDGET = 5           # seconds before it stops starting new attempts (worst case about 6)
STALE_DAYS = 30
VER = r'\d+(?:\.\d+)+'


def skill_text():
    here = os.path.dirname(os.path.abspath(__file__))
    return open(os.path.join(here, '..', 'SKILL.md'), encoding='utf8').read()


def installed(text):
    m = re.search(r'^# WCC Canvas Ready, v(%s)' % VER, text, re.M)
    return m.group(1) if m else None


def released(text, version):
    """Date of this copy, from its own Version log line: **v1.02** (Nov 16, 2026)"""
    m = re.search(r'\*\*v%s\*\* \(([A-Z][a-z]{2}) (\d{1,2}), (\d{4})\)' % re.escape(version), text)
    if not m:
        return None
    months = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
    try:
        return datetime.date(int(m.group(3)), months.index(m.group(1)) + 1, int(m.group(2)))
    except ValueError:
        return None


def key(v):
    return tuple(int(x) for x in v.split('.'))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def from_release_redirect():
    """github.com only: /releases/latest answers with a redirect to /releases/tag/v1.02."""
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        r = opener.open(urllib.request.Request(DOWNLOAD_URL, headers=AGENT, method='HEAD'), timeout=TIMEOUT)
        loc = r.headers.get('Location') or r.geturl()
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            raise
        loc = e.headers.get('Location', '')
    m = re.search(r'/releases/tag/v?(%s)$' % VER, loc or '')
    return m.group(1) if m else None


def from_api():
    req = urllib.request.Request('https://api.github.com/repos/%s/releases/latest' % REPO, headers=AGENT)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        tag = str(json.loads(r.read(200000).decode('utf8', 'replace')).get('tag_name', ''))
    m = re.fullmatch(r'v?(%s)' % VER, tag.strip())
    return m.group(1) if m else None


def _version_file(url):
    def get():
        with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=TIMEOUT) as r:
            raw = r.read(64).decode('utf8', 'replace').strip()
        return raw if re.fullmatch(VER, raw) else None
    return get


SOURCES = [
    ('github.com release page', from_release_redirect),
    ('api.github.com', from_api),
    ('raw.githubusercontent.com', _version_file('https://raw.githubusercontent.com/%s/main/VERSION' % REPO)),
    ('cdn.jsdelivr.net', _version_file('https://cdn.jsdelivr.net/gh/%s@main/VERSION' % REPO)),
]


def latest():
    """Returns (version or None, source name or None, [why each failed])."""
    start, why = time.time(), []
    for name, fn in SOURCES:
        if time.time() - start > BUDGET:
            why.append('%s: skipped, out of time' % name)
            continue
        try:
            v = fn()
            if v:
                return v, name, why
            why.append('%s: unexpected reply' % name)
        except Exception as e:
            why.append('%s: %s' % (name, type(e).__name__))
    return None, None, why


def age_note(text, have):
    d = released(text, have)
    if not d:
        return '', None
    days = (datetime.date.today() - d).days
    return ' dated %s (%d day%s old)' % (d.strftime('%b %d, %Y').replace(' 0', ' '), days, '' if days == 1 else 's'), days


def report(have, new, how, verbose):
    if key(new) > key(have):
        print('UPDATE AVAILABLE: WCC Canvas Ready v%s is out (you have v%s). It takes about a minute to update:\n'
              '1. Open this link and click wcc-canvas-ready.zip under Assets: %s\n'
              '2. Save the file. Do not unzip it.\n'
              '3. In Claude, go to Customize, then Skills, and replace WCC Canvas Ready with that file.\n'
              'Your next new chat will use the new version.' % (new, have, DOWNLOAD_URL))
    elif verbose:
        if key(new) == key(have):
            print('Installed v%s. Latest release is v%s (%s). You are up to date.' % (have, new, how))
        else:
            print('Installed v%s. Latest release is v%s (%s). This copy is newer than the latest release.' % (have, new, how))


def main():
    args = sys.argv[1:]
    verbose = '--verbose' in args
    text = skill_text()
    have = installed(text)
    if not have:
        print('UPDATE CHECK BLOCKED: could not read the installed version from SKILL.md. Releases: %s' % DOWNLOAD_URL)
        return
    if '--compare' in args:
        i = args.index('--compare')
        given = args[i + 1].strip().lstrip('vV') if i + 1 < len(args) else ''
        if not re.fullmatch(VER, given):
            print('Could not compare: "%s" is not a version number like 1.03.' % given)
            return
        report(have, given, 'read with the web tool', True)
        return
    new, how, why = latest()
    if new:
        report(have, new, how, verbose)
        return
    note, days = age_note(text, have)
    stale = ' STALE.' if days is not None and days >= STALE_DAYS else ''
    print('UPDATE CHECK BLOCKED: installed v%s%s.%s This sandbox could not reach GitHub, so this is NOT a '
          '"no update" result. Do the web fallback in SKILL.md. Releases: %s' % (have, note, stale, DOWNLOAD_URL))
    if verbose:
        print('Tried: ' + '; '.join(why))


if __name__ == '__main__':
    try:
        main()
    except BaseException as e:
        try:
            print('UPDATE CHECK BLOCKED: the check itself failed (%s). Releases: %s' % (type(e).__name__, DOWNLOAD_URL))
        except BaseException:
            pass
    sys.exit(0)
