#!/usr/bin/env python3
"""Writes the measurement results to findings/latest.json.

WHY TO A FILE
1. Nobody reads logs. Pulling GitHub workflow logs from the API needs admin
   rights, and the log view in the UI is virtualised. The result exists but
   cannot be reached — which in practice means it does not exist.
2. The page will be fed from here. The "recorded measurement" cards on the site
   were hand-written until now and none of them could be reproduced. From here
   on the record and the screen read the same file; the two cannot drift apart
   structurally.
3. History accumulates. If every run overwrote the previous result, when a
   number was produced and against which archive would be lost. The file
   carries that.

IMPORTANT: this script does not MEASURE, it CALLS the measurement modules. The
arithmetic lives in one place; here there is only collection and writing.
"""
import json
import os
import sys

from archive import stamps, summary, Missing
import measure_band
import measure_polymarket
import measure_touch
from stability import Stability

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def stability_summary(stab):
    o = stab.summary()
    return {
        'distinct_rungs': o['distinct_rungs'],
        'total_observations': o['total_observations'],
        'observations_per_rung': round(o['observations_per_rung'], 1),
        'always_exceeds': len(o['always']),
        'sometimes_exceeds': len(o['sometimes']),
        'never_exceeds': len(o['never']),
        'always_exceeding_list': [{'rung': str(a), 'observations': n, 'exceeding': x}
                                  for a, n, x in o['always'][:20]],
    }


def measure_band_all(all_stamps):
    stab = Stability()
    exceeding = measured = 0
    density = []
    for d in all_stamps:
        try:
            s = measure_band.run(d, stab)
        except Missing:
            continue
        for v in s['series'].values():
            if 'error' in v:
                continue
            exceeding += v['exceeding']
            measured += v['measured']
            density.append(v['density_sum'])
    return {
        'exceeding': exceeding, 'measured': measured,
        'percent': round(100.0 * exceeding / measured, 1) if measured else None,
        'mean_density': round(sum(density) / len(density), 4) if density else None,
        'stability': stability_summary(stab),
    }


def measure_polymarket_all(all_stamps):
    stab = Stability()
    exceeding = measured = 0
    near_exceeding = near_measured = 0
    touch_excluded = 0
    for d in all_stamps:
        try:
            s = measure_polymarket.run(d)
        except Missing:
            continue
        touch_excluded += s['touch_excluded']
        for h in s['ladders']:
            rows = [r for r in h['rows'] if 'opt' in r]
            if not rows:
                continue
            a = sum(1 for r in rows if r['exceeds'])
            exceeding += a
            measured += len(rows)
            if abs(h['gap_hours']) <= 12:
                near_exceeding += a
                near_measured += len(rows)
            for r in rows:
                stab.add('%s:%s:%g' % (h['asset'], h['end'], r['K']), r['exceeds'])
    return {
        'exceeding': exceeding, 'measured': measured,
        'percent': round(100.0 * exceeding / measured, 1) if measured else None,
        'gap_12h_exceeding': near_exceeding, 'gap_12h_measured': near_measured,
        'gap_12h_percent': round(100.0 * near_exceeding / near_measured, 1)
        if near_measured else None,
        'touch_ladders_excluded': touch_excluded,
        'stability': stability_summary(stab),
    }


def measure_touch_all(all_stamps):
    stab = Stability()
    measured = violations = over_two = 0
    for d in all_stamps:
        try:
            s = measure_touch.run(d, stab)
        except Missing:
            continue
        measured += s['measured']
        violations += s['violations']
        over_two += s['over_two']
    return {
        'measured': measured, 'arithmetic_violations': violations,
        'ratio_over_two': over_two,
        'violation_percent': round(100.0 * violations / measured, 1) if measured else None,
        'ratio_over_two_percent': round(100.0 * over_two / measured, 1) if measured else None,
        'stability': stability_summary(stab),
        'note': ('The terminal comes from a MODEL-FREE digital. "ratio>2" means '
                 'above the driftless Brownian bound; "2" is not a constant '
                 '(D-031), so that is a weak claim. "ratio<1" is an arithmetic '
                 'violation.'),
    }


def main():
    all_stamps = stamps('_meta')
    o = summary()
    print('measuring: %d snapshots' % len(all_stamps))

    result = {
        'archive': o,
        'produced_by': 'scripts/write_findings.py',
        'measurements': {
            'friction_band_kalshi': measure_band_all(all_stamps),
            'polymarket_terminal': measure_polymarket_all(all_stamps),
            'long_horizon_touch': measure_touch_all(all_stamps),
        },
    }

    folder = os.path.join(ROOT, 'findings')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, 'latest.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print('written: findings/latest.json')
    for name, m in result['measurements'].items():
        k = m.get('stability', {})
        print('  %-26s distinct rungs %-4s always exceeding %-4s'
              % (name, k.get('distinct_rungs'), k.get('always_exceeds')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
