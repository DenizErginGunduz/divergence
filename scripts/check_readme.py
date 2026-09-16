#!/usr/bin/env python3
"""Does the README still say what the findings file says?

WHY THIS EXISTS
Denetim 3 (D-090) compared every documented claim against the thing it
describes. The methodology documents were current. The interface was current --
it reads findings/latest.json and holds no number of its own. findings/ was, by
construction, itself. The stale surface was the README: "in 45 of 45
observations each" when the archive had grown to 55 and one of the three rungs
was 54, "0.2% arithmetic violations" when the last run wrote 0.4%, "94.9% above
the 2x bound" when it wrote 93%.

Nothing in the pipeline had failed. The numbers were copied into prose once, by
hand, and prose is not recomputed. The README meanwhile claimed that every
number traces to a script, enforced in CI -- true of the screen, not of the
README saying it.

So: the sentences in the README that carry a measured number are rebuilt here
from findings/latest.json and must appear in the file verbatim.

DELIBERATELY RIGID
Reword a sentence and this fails. That is the intended behaviour, the same
choice audit_semantics.py makes about the Kalshi rule text and for the same
reason: a checker that tolerates rewording tolerates the number changing
underneath it. Rewording then costs one edit here -- at the moment somebody is
looking at the current value anyway.

Usage:
    python scripts/check_readme.py
    python scripts/check_readme.py --self-test   # prove it can fail
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, 'README.md')
FINDINGS = os.path.join(ROOT, 'findings', 'latest.json')


def num(x):
    """9.0 -> 9, 10.3 -> 10.3. JSON gives us both; prose wants one."""
    if isinstance(x, float) and x == int(x):
        return str(int(x))
    return str(x)


def stability_threshold():
    """The share above which stability.py calls a rung always-exceeding.

    It is 0.9, not 1.0. Read from the source rather than hardcoded, so that
    changing the classifier forces the README sentence to change with it. This
    is the overclaim D-072 fixed on the interface card and could not enforce
    anywhere else.
    """
    path = os.path.join(ROOT, 'scripts', 'stability.py')
    try:
        with open(path, encoding='utf-8') as fh:
            m = re.search(r'always_above\s*=\s*([0-9.]+)', fh.read())
    except OSError:
        return None
    return float(m.group(1)) if m else None


def expectations(f):
    """The sentences the README must contain, built from the findings.

    Returns a list of (label, expected_substring). A measurement missing from
    the findings file produces no expectation rather than a crash: the README
    cannot be wrong about a number that was never written.
    """
    out = []
    m = f.get('measurements') or {}

    band = ((m.get('friction_band_kalshi') or {}).get('year_end') or {})
    st = band.get('stability') or {}
    if st.get('always_exceeds') is not None and st.get('distinct_rungs'):
        out.append(('kalshi rungs',
                    '%s of %s rungs' % (num(st['always_exceeds']),
                                        num(st['distinct_rungs']))))

    # "the weakest in 54 of 55" is the honest form. The list holds the rungs the
    # classifier calls always-exceeding; the weakest of them is the one the
    # sentence has to survive.
    counts = set()
    weakest = None
    for rung in (st.get('always_exceeding_list') or []):
        counts.add(rung.get('observations'))
        exc = rung.get('exceeding')
        if exc is not None and (weakest is None or exc < weakest):
            weakest = exc
    if len(counts) == 1 and weakest is not None:
        obs = counts.pop()
        out.append(('kalshi persistence',
                    'the weakest in %s of %s' % (num(weakest), num(obs))))

    threshold = stability_threshold()
    if threshold is not None:
        out.append(('stability rule',
                    'in over %s%% of their observations' % num(threshold * 100)))

    pm = m.get('polymarket_terminal') or {}
    if pm.get('percent') is not None:
        out.append(('polymarket share',
                    '%s%% of quotable rungs' % num(pm['percent'])))

    touch = m.get('long_horizon_touch') or {}
    if touch.get('violation_percent') is not None:
        out.append(('touch violations',
                    '%s%% arithmetic violations' % num(touch['violation_percent'])))
    if touch.get('ratio_over_two_percent') is not None:
        out.append(('touch bound',
                    '%s%% above the 2x bound' % num(touch['ratio_over_two_percent'])))

    a = f.get('archive') or {}
    if a.get('snapshot_count') and a.get('day_count'):
        out.append(('findings scope',
                    'over %s snapshots and %s days'
                    % (num(a['snapshot_count']), num(a['day_count']))))
    if a.get('last'):
        out.append(('findings stamp', 'last snapshot %s' % a['last']))
    return out


def check(readme_text, findings):
    return [(label, expected, expected in readme_text)
            for label, expected in expectations(findings)]


def report(rows):
    print('README vs findings/latest.json')
    print()
    for label, expected, ok in rows:
        print('  %-20s %-7s "%s"' % (label, 'ok' if ok else 'STALE', expected))
    print()
    if not rows:
        print('Nothing to check: findings/latest.json carried no measurements.')
        return 0
    bad = [r for r in rows if not r[2]]
    if bad:
        print('%d of %d claims in README.md no longer match the findings file.'
              % (len(bad), len(rows)))
        print('Update the README, or update the expected form in this script.')
        return 1
    print('All %d checked claims match.' % len(rows))
    return 0


def self_test():
    """A checker that cannot fail is a green light, not a check.

    The fixture is built from the same expectations() the real run uses, so the
    test stays honest when a claim is added: whatever the checker demands, the
    good fixture supplies, and the stale one breaks exactly one of them.
    """
    findings = {'archive': {'snapshot_count': 61, 'day_count': 16,
                            'last': '2026-08-30T1611Z'},
                'measurements': {'long_horizon_touch': {
                    'violation_percent': 0.4, 'ratio_over_two_percent': 93}}}
    exp = expectations(findings)
    good = ' // '.join(e for _, e in exp)
    stale = good.replace('0.4% arithmetic violations',
                         '0.2% arithmetic violations')
    if any(not ok for _, _, ok in check(good, findings)):
        print('SELF-TEST FAILED: a matching README was reported stale')
        return 1
    caught = [label for label, _, ok in check(stale, findings) if not ok]
    if caught != ['touch violations']:
        print('SELF-TEST FAILED: expected exactly the touch claim to break, '
              'got %s' % caught)
        return 1
    print('self-test ok: %d claims built, a changed number fails exactly one'
          % len(exp))
    return 0


def main():
    if '--self-test' in sys.argv[1:]:
        return self_test()
    if not os.path.exists(FINDINGS):
        print('findings/latest.json not found -- nothing to check against.')
        return 0
    with open(FINDINGS, encoding='utf-8') as fh:
        findings = json.load(fh)
    with open(README, encoding='utf-8') as fh:
        text = fh.read()
    return report(check(text, findings))


if __name__ == '__main__':
    sys.exit(main())
