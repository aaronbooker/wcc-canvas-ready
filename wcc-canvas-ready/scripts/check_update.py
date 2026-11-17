"""Tell the instructor when a newer WCC Canvas Ready exists. Notifies only; it cannot update the skill.

Usage:
  python3 -I check_update.py              one line of output at most (see below)
  python3 -I check_update.py --verbose    always says what it found, and how
  python3 -I check_update.py --compare 1.0.6 [--verbose]
        no network: compares the installed version with a version number Claude read with its
        own web tool (the raw VERSION file first, the releases page only if that fails)

Default output, exactly one of:
  UPDATE AVAILABLE: ...     GitHub lists a newer version. Prints the line plus three plain steps; show all of it to the instructor.
  (nothing)                 GitHub answered and this copy is current.
  UPDATE CHECK BLOCKED: ... this sandbox could not reach GitHub at all, or every answer was OLDER
                            than this copy (a cached page). That is NOT "up to date".
                            SKILL.md says what Claude does next (web fetch fallback).
A version older than this copy is never reported as a result: a releases page fetched by a web
tool was read as v1.01 when the real latest was v1.0.6 (a cached copy, Nov 17, 2026), and
"this copy is newer" hid that the check had failed.

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
    """Date of this copy, from its own Version log line: **v1.0.5** (Nov 16, 2026)"""
    m = re.search(r'\*\*v%s\*\* \(([A-Z][a-z]{2}) (\d{1,2}), (\d{4})\)' % re.escape(version), text)
    if not m:
        return None
    months = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
    try:
        return datetime.date(int(m.group(3)), months.index(m.group(1)) + 1, int(m.group(2)))
    except ValueError:
        return None


def key(v):
    """Comparable form of a version. Versions are major.minor.patch from 1.0.5 on. The first five releases
    were written with two parts and a two-digit second part (1.00 to 1.04); those mean 1.0.0 to 1.0.4."""
    p = v.split('.')
    if len(p) == 2 and len(p[1]) == 2:
        p = [p[0], p[1][0], p[1][1]]
    p = [int(x) for x in p]
    return tuple(p + [0] * (3 - len(p)))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def from_release_redirect():
    """github.com only: /releases/latest answers with a redirect to /releases/tag/v1.0.5."""
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


def latest(have):
    """Returns (version or None, source name or None, [why each failed]). An answer older than the installed
    copy is a cached or out-of-date source: noted, and the next source is tried."""
    start, why = time.time(), []
    for name, fn in SOURCES:
        if time.time() - start > BUDGET:
            why.append('%s: skipped, out of time' % name)
            continue
        try:
            v = fn()
            if v and key(v) < key(have):
                why.append('%s: said v%s, older than this copy (out of date?)' % (name, v))
                continue
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
              '3. In Claude, go to Customize, then Skills. Select + Add, then Upload skill, and choose that file.\n'
              '   When Claude asks whether to replace the WCC Canvas Ready you have, say yes.\n'
              'Your next new chat will use the new version.' % (new, have, DOWNLOAD_URL))
    elif verbose:
        print('Installed v%s. Latest release is v%s (%s). You are up to date.' % (have, new, how))


def blocked(text, have, why_line, next_step='Do the web fallback in SKILL.md.'):
    note, days = age_note(text, have)
    stale = ' STALE.' if days is not None and days >= STALE_DAYS else ''
    print('UPDATE CHECK BLOCKED: installed v%s%s.%s %s. This is NOT a "no update" result. %s Releases: %s'
          % (have, note, stale, why_line, next_step, DOWNLOAD_URL))


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
            print('Could not compare: "%s" is not a version number like 1.0.6.' % given)
            return
        if key(given) < key(have):
            # what was read is older than this copy: a stale page, not a result
            blocked(text, have, 'The version read (v%s) is older than this copy, so the page read was probably out of '
                    'date and the check could not be confirmed' % given,
                    'Go to step 3 of the web fallback in SKILL.md.')
            return
        report(have, given, 'read with the web tool', verbose)
        return
    new, how, why = latest(have)
    if new:
        report(have, new, how, verbose)
        return
    older = any('older than this copy' in w for w in why)
    blocked(text, have, 'GitHub answered only with a version older than this copy (an out-of-date copy)' if older
            else 'This sandbox could not reach GitHub')
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
