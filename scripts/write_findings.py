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

from archive import snapshot, stamps, summary, Missing
import measure_band
import measure_exhaustive
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
    discounts = []
    fallbacks = 0
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
            discounts.append(v['discount_factor'])
            if not v['discount_estimated']:
                fallbacks += 1
    return {
        # The digital comes from a price difference, so no model is assumed.
        # The page counts this flag rather than a hand-typed number.
        'model_free': True,
        'exceeding': exceeding, 'measured': measured,
        'percent': round(100.0 * exceeding / measured, 1) if measured else None,
        # The ladder is exhaustive, so this sums to the DISCOUNT FACTOR, not
        # to 1 (D-073). Reporting it beside the mean D is the point: the two
        # should agree, and a gap between them is a measurement error rather
        # than a fact about the market.
        'mean_density': round(sum(density) / len(density), 4) if density else None,
        'mean_discount_factor': round(sum(discounts) / len(discounts), 6) if discounts else None,
        'discount_fallbacks': fallbacks,
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
        'model_free': True,
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
        # The bound comes from lognormal dynamics, so this one DOES assume a
        # model. Kept separate from the two above on purpose (D-046).
        'model_free': False,
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


def measure_exhaustive_all(all_stamps):
    """The three boundary rules, pooled over the archive.

    This one has no stability block because it is not a per-rung question. It
    asks whether a bucket set sums to 1, which is a property of the whole
    ladder, and the answer is the same shape on every snapshot.
    """
    pooled = {rule: [] for rule in measure_exhaustive.RULES}
    for d in all_stamps:
        try:
            g = snapshot(d)
            KA, D = g.kalshi, g.deribit
        except Missing:
            continue
        for _asset, series, currency in measure_band.SERIES:
            for rule in measure_exhaustive.RULES:
                try:
                    r = measure_exhaustive.ladder_sum(KA, D, series, currency, rule)
                except (KeyError, TypeError, ValueError):
                    r = None
                if r:
                    # The ratio, not the raw total: after D-073 an exhaustive
                    # ladder is worth D rather than 1, and D differs between
                    # chains, so raw totals from different maturities are not
                    # comparable while ratios are.
                    pooled[rule].append(r['ratio'])

    out = {}
    for rule, v in pooled.items():
        if not v:
            out[rule] = None
            continue
        mean = sum(v) / len(v)
        out[rule] = {
            'measured': len(v),
            'mean_ratio_to_discount': round(mean, 4),
            'min_ratio_to_discount': round(min(v), 4),
            'max_ratio_to_discount': round(max(v), 4),
            'departure_percent': round(100.0 * (mean - 1.0), 1),
        }
    out['note'] = ('An exhaustive bucket set is worth the discount factor D '
                   'today, because buying every bucket buys a dollar at expiry '
                   'with certainty. That is arithmetic, not a preference, so a '
                   'departure from D says the computation is wrong without '
                   'saying which bucket is wrong. The figures below are '
                   'total/D, so 1.0000 is the target. Until D-073 the target '
                   'was written as 1 and the sum landed on 1 for any D, which '
                   'made the check blind to the convention bug. See D-067 for '
                   'the boundary rule and D-073 for the discount.')
    return out


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
            'exhaustiveness_constraint': measure_exhaustive_all(all_stamps),
        },
    }

    folder = os.path.join(ROOT, 'findings')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, 'latest.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print('written: findings/latest.json')
    for name, m in result['measurements'].items():
        k = m.get('stability') or {}
        if k:
            print('  %-26s distinct rungs %-4s always exceeding %-4s'
                  % (name, k.get('distinct_rungs'), k.get('always_exceeds')))
        else:
            worst = max((v for v in m.values() if isinstance(v, dict)),
                        key=lambda x: abs(x.get('departure_percent') or 0), default=None)
            print('  %-26s worst departure from 1: %s%%'
                  % (name, worst.get('departure_percent') if worst else '-'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
