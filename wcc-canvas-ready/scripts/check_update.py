"""Tell the instructor when a newer WCC Canvas Ready exists. Notifies only; it cannot update the skill.
Usage: python3 -I check_update.py [--verbose]
Default: prints ONE line only if GitHub lists a newer version; prints nothing in every other case
(up to date, offline, blocked, slow, odd reply). Always exits 0 and gives up after a few seconds.
--verbose: prints the installed version, the latest version, or why the check could not finish.
Privacy: one read-only GET of a tiny text file. No file names, file contents, chat text or account
details are sent. GitHub sees the request like any web visit (IP address, this script's name as the agent).
Only the standard library is used."""
import os, re, sys, urllib.request

REPO = 'aaronbooker/wcc-canvas-ready'
VERSION_URL = 'https://raw.githubusercontent.com/%s/main/VERSION' % REPO
DOWNLOAD_URL = 'https://github.com/%s/releases/latest' % REPO
TIMEOUT = 4

def installed():
    here = os.path.dirname(os.path.abspath(__file__))
    text = open(os.path.join(here, '..', 'SKILL.md'), encoding='utf8').read(4000)
    m = re.search(r'^# WCC Canvas Ready, v(\d+(?:\.\d+)+)', text, re.M)
    return m.group(1) if m else None

def latest():
    req = urllib.request.Request(VERSION_URL, headers={'User-Agent': 'wcc-canvas-ready-update-check'})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read(64).decode('utf8', 'replace').strip()
    return raw if re.fullmatch(r'\d+(?:\.\d+)+', raw) else None

def key(v):
    return tuple(int(x) for x in v.split('.'))

def main():
    verbose = '--verbose' in sys.argv
    try:
        have = installed()
        if not have:
            if verbose: print('Could not read the installed version from SKILL.md.')
            return
        try:
            new = latest()
        except Exception as e:
            if verbose: print('Installed v%s. Could not reach GitHub (%s). Check again later or see %s' % (have, type(e).__name__, DOWNLOAD_URL))
            return
        if not new:
            if verbose: print('Installed v%s. GitHub returned an unexpected reply.' % have)
            return
        if key(new) > key(have):
            print('UPDATE AVAILABLE: WCC Canvas Ready v%s is out (you have v%s). Download: %s' % (new, have, DOWNLOAD_URL))
        elif verbose:
            print('Installed v%s. Latest is v%s. You are up to date.' % (have, new))
    except Exception as e:
        if verbose: print('Update check failed (%s).' % type(e).__name__)

if __name__ == '__main__':
    try:
        main()
    except BaseException:
        pass
    sys.exit(0)
