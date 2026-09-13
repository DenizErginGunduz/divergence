#!/usr/bin/env python3
"""Decision reference checker.

Why it exists: the finding cards in the interface printed decision numbers like
"D-049" and "D-045 . D-046 . D-066", but those decisions had never been written
into DECISIONS.md. The screen was citing records that did not exist. A human
noticed, not the code. In a project that claims measurement rigour that is the
worst kind of hole.

What it does:
  1. Scans the text files in the repository and collects every D-\d{3} citation.
  2. Treats the "## D-XXX" headings in DECISIONS.md as definitions.
  3. FAILS (exit 1) if any citation has no definition.

Usage:
    python scripts/ref_check.py              # check
    python scripts/ref_check.py --list       # also print where each one occurs
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISIONS_FILE = os.path.join('docs', 'DECISIONS.md')

# The raw archive is not scanned: it holds no citations, and the files are large
# and immutable.
SKIP_DIRS = {'.git', 'raw', 'state', '__pycache__', 'node_modules'}
SCAN_EXT = {'.md', '.py', '.html', '.yml', '.yaml', '.json', '.txt', '.js', '.css'}

CITATION = re.compile(r'\bD-(\d{3})\b')
DEFINITION = re.compile(r'^##\s+(D-\d{3})', re.MULTILINE)


def files():
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            if os.path.splitext(name)[1].lower() in SCAN_EXT:
                full = os.path.join(base, name)
                yield full, os.path.relpath(full, ROOT).replace(os.sep, '/')


def self_test():
    """Proves the checker can actually FAIL.

    A checker that stays green while catching nothing is not a checker. This runs
    first in CI: until the ability to catch is proven, the real check means
    nothing.
    """
    # The sample numbers are built PIECEWISE: had a plain number been written in
    # the source, the checker would read its own test data as a real citation and
    # break itself. That is exactly what happened — the first version failed in
    # CI. Proof that the tool works, but test data must not resemble production
    # data.
    P = 'D-'
    sample_decisions = ('## %s001 - a real decision\n'
                        '## %s002 - a second decision\n'
                        'body text\n') % (P, P)
    sample_text = 'mentions %s001, %s002 and the undefined %s999\n' % (P, P, P)

    defined = set(DEFINITION.findall(sample_decisions))
    cited = {P + m.group(1) for m in CITATION.finditer(sample_text)}
    dangling = sorted(c for c in cited if c not in defined)

    problems = []
    if defined != {P + '001', P + '002'}:
        problems.append('definitions not recognised: %s' % sorted(defined))
    if cited != {P + '001', P + '002', P + '999'}:
        problems.append('citations not scanned: %s' % sorted(cited))
    if dangling != [P + '999']:
        problems.append('dangling reference NOT CAUGHT: %s' % dangling)

    if problems:
        print('SELF-TEST FAILED:')
        for p in problems:
            print('  - %s' % p)
        return 1
    print('self-test: passed - a dangling reference is caught')
    return 0


def main():
    verbose = '--list' in sys.argv
    if '--self-test' in sys.argv:
        return self_test()

    dp = os.path.join(ROOT, DECISIONS_FILE)
    if not os.path.isfile(dp):
        print('ERROR: %s not found' % DECISIONS_FILE)
        return 1
    decisions = open(dp, encoding='utf-8').read()
    defined = set(DEFINITION.findall(decisions))

    where = {}
    for full, rel in files():
        try:
            text = open(full, encoding='utf-8').read()
        except (UnicodeDecodeError, OSError):
            continue
        for m in CITATION.finditer(text):
            num = 'D-' + m.group(1)
            where.setdefault(num, set()).add(rel)

    dangling = sorted(n for n in where if n not in defined)

    scanned = sum(1 for _ in files())
    print('files scanned     : %d' % scanned)
    print('decisions defined : %d' % len(defined))
    print('decisions cited   : %d' % len(where))

    # An empty scan must not pass quietly: if the path is wrong the check is
    # saying nothing at all.
    if scanned < 5 or not defined:
        print('\nERROR: the scan came back empty (files=%d, definitions=%d). '
              'ROOT may be wrong: %s' % (scanned, len(defined), ROOT))
        return 1

    if verbose:
        for num in sorted(where):
            print('  %s  <- %s' % (num, ', '.join(sorted(where[num]))))

    if dangling:
        print('\nDANGLING REFERENCE (%d) - no definition:' % len(dangling))
        for num in dangling:
            print('  %-7s <- %s' % (num, ', '.join(sorted(where[num]))))
        print('\nA number is not cited before the decision is written. Either the')
        print('record gets written or the citation goes. A number that carries no')
        print('information was never a citation to begin with.')
        return 1

    print('\nno dangling references.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
