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


def band_block(rows, stab):
    """Aggregate one tenor's rung-observations into the shape the page reads."""
    exceeding = sum(v['exceeding'] for v in rows)
    measured = sum(v['measured'] for v in rows)
    quotable = sum(v['quotable'] for v in rows)
    envelopes = [v['mean_envelope'] for v in rows if v['mean_envelope'] is not None]
    values = [x for v in rows for x in v['edge_values']]
    # A cumulative ladder has no density sum; only the exhaustive ones do.
    density = [v['density_sum'] for v in rows if v['density_sum'] is not None]
    discounts = [v['discount_factor'] for v in rows]
    gaps = [v['expiry_gap_hours'] for v in rows]
    return {
        # The digital comes from a price difference, so no model is assumed.
        # The page counts this flag rather than a hand-typed number.
        'model_free': True,
        'exceeding': exceeding, 'measured': measured,
        # Since the friction band became a trade at quoted prices, the only
        # denominator that means anything is the number of rungs with a
        # two-sided option market. A rung nobody is quoting is not evidence
        # either way; it used to be counted because its mid existed.
        'quotable': quotable,
        'percent': round(100.0 * exceeding / quotable, 1) if quotable else None,
        'percent_of_all_rungs': round(100.0 * exceeding / measured, 1) if measured else None,
        'mean_envelope': round(sum(envelopes) / len(envelopes), 4) if envelopes else None,
        # What every positive edge is worth in DOLLARS at the top of book.
        # An edge with nothing resting behind it is a price observation, not
        # an opportunity, and this is the field that says which one it is.
        'edge_value_max': round(max(values), 2) if values else None,
        'edge_value_median': round(sorted(values)[len(values) // 2], 2) if values else None,
        'edge_value_total': round(sum(values), 2) if values else None,
        'off_grid_quotes': sum(v['off_grid'] for v in rows),
        # An exhaustive ladder sums to the DISCOUNT FACTOR, not to 1 (D-073).
        # Reporting it beside the mean D is the point: the two should agree.
        'mean_density': round(sum(density) / len(density), 4) if density else None,
        'mean_discount_factor': round(sum(discounts) / len(discounts), 6) if discounts else None,
        'discount_fallbacks': sum(1 for v in rows if not v['discount_estimated']),
        # The gap between the option expiry and the Kalshi close, in hours.
        # It is the reason this block is split by tenor at all: at 165 hours
        # it swallowed two of three findings (D-079); at about a day it does
        # not. A single pooled number would hide exactly that.
        'expiry_gap_hours_median': round(sorted(gaps)[len(gaps) // 2], 1) if gaps else None,
        'ladders': sorted(set(v['ladder'] for v in rows)),
        # Which side of the Kalshi close the option expiry falls on. 'before'
        # understates an upside tail and flatters the comparison; 'after'
        # overstates and works against it. A block mixing both would be
        # uninterpretable.
        'expiry_side': sorted(set(v['expiry_side'] for v in rows)),
        'series': sorted(set(v['label'] for v in rows)),
        'stability': stability_summary(stab),
    }


class TenorRouter(object):
    """One pass over the archive, one stability counter per tenor.

    measure_band.run() writes its stability keys as '<series label>:<rung>',
    and the label already carries the tenor, so routing on it avoids walking
    the archive twice. A rung's consistency only means something against rungs
    of the same kind: a year-end rung observed 61 times and an intraday rung
    that exists for four hours are not comparable evidence.
    """

    def __init__(self, stabs):
        self.stabs = stabs

    def add(self, key, flag):
        head = key.split(':', 1)[0]
        self.stabs['year_end' if 'year-end' in head else 'intraday'].add(key, flag)


def measure_band_all(all_stamps):
    """The friction band, SPLIT BY TENOR.

    Year-end and intraday ladders are the same measurement on contracts whose
    expiry gap differs by two orders of magnitude — about 165 hours against
    about a day. That gap swallowed two of three findings (D-079), so pooling
    the two would produce one number describing neither.
    """
    stabs = {'year_end': Stability(), 'intraday': Stability()}
    rows = {'year_end': [], 'intraday': []}
    router = TenorRouter(stabs)
    for d in all_stamps:
        try:
            s = measure_band.run(d, router)
        except Missing:
            continue
        for label, v in s['series'].items():
            if 'error' in v:
                continue
            tenor = 'year_end' if 'year-end' in label else 'intraday'
            rows[tenor].append(dict(v, label=label))
    return {t: band_block(rows[t], stabs[t]) for t in rows if rows[t]}

def measure_polymarket_all(all_stamps):
    """Polymarket terminal ladders, under the SAME test as Kalshi (D-085).

    Until 2026-09-15 this block was computed with the pre-repair method: the
    old discount convention, a 1.96*SE band around two mids, and no fee at all
    on the prediction leg. Its number sat in findings/latest.json beside the
    repaired Kalshi one as though the two were comparable. They were not.
    """
    stab = Stability()
    exceeding = quotable = seen = 0
    near_exceeding = near_quotable = 0
    touch_excluded = 0
    skipped = {}
    envelopes = []
    venue_fees = []
    for d in all_stamps:
        try:
            s = measure_polymarket.run(d)
        except Missing:
            continue
        touch_excluded += s['touch_excluded']
        for h in s['ladders']:
            seen += len(h['rows'])
            for r in h['rows']:
                if 'exceeds' not in r:
                    why = r.get('skipped', 'unknown')
                    skipped[why] = skipped.get(why, 0) + 1
                    continue
                quotable += 1
                envelopes.append(r['envelope'])
                venue_fees.append(r['venue_fee'])
                if r['exceeds']:
                    exceeding += 1
                if abs(h['gap_hours']) <= 12:
                    near_quotable += 1
                    if r['exceeds']:
                        near_exceeding += 1
                stab.add('%s:%s:%g' % (h['asset'], h['end'], r['K']), r['exceeds'])
    return {
        'model_free': True,
        # 'measured' is every rung the ladders offered; 'quotable' is the ones
        # that produced a verdict. A rung with a one-sided option quote or an
        # unrecognised fee schedule is neither evidence nor a zero.
        'measured': seen, 'quotable': quotable, 'exceeding': exceeding,
        'percent': round(100.0 * exceeding / quotable, 1) if quotable else None,
        'gap_12h_exceeding': near_exceeding, 'gap_12h_quotable': near_quotable,
        'gap_12h_percent': round(100.0 * near_exceeding / near_quotable, 1)
        if near_quotable else None,
        'mean_envelope': round(sum(envelopes) / len(envelopes), 4)
        if envelopes else None,
        'mean_venue_fee': round(sum(venue_fees) / len(venue_fees), 5)
        if venue_fees else None,
        'skipped': skipped,
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
    set_aside = {'cumulative': 0, 'incomplete': 0}
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
                if r and r['ratio'] is None:
                    # A cumulative or incomplete ladder has no sum to check
                    # (D-105). Counted, so the page can say what was set aside.
                    if rule == measure_exhaustive.RULES[0]:
                        set_aside[r['ladder']] = set_aside.get(r['ladder'], 0) + 1
                    continue
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
                   'the boundary rule and D-073 for the discount. Only a '
                   'ladder that is a partition is summed, one event per '
                   'series; cumulative ladders (every rung P(S > K) at its own '
                   'threshold) and incomplete ones (a hole in the archived '
                   'ladder) are counted in ladders_set_aside instead (D-105).')
    out['ladders_set_aside'] = set_aside
    return out


def kill_test_block():
    """The ETH 5,000 verdict, small enough for the page to carry.

    G1 in docs/DECISION_GATES.md requires Note 1, README.md AND THE INTERFACE to
    use the verdict's exact words. The interface reads one file, findings/
    latest.json, and holds no number of its own (D-090); the kill test writes its
    own 240 KB record with one row per snapshot, which is not a file to hand a
    browser. So the summary is copied here: the rung, the decision, and the
    verdict block WITHOUT the per-snapshot array.

    Copied rather than recomputed. kill_test_eth5k.py runs earlier in the same
    measure workflow and is the only thing that judges this; recomputing the
    verdict here would make two places able to disagree about it.

    Returns None when the file is absent — a run without the kill test is a
    smaller run, not a broken one, and the page shows the quoted-price claim
    alone rather than an error.
    """
    path = os.path.join(ROOT, 'findings', 'kill_test_eth5k.json')
    try:
        with open(path, encoding='utf-8') as f:
            k = json.load(f)
    except (OSError, ValueError):
        return None
    verdict = k.get('verdict')
    if not isinstance(verdict, dict):
        return None
    return {'rung': k.get('rung'), 'decision': k.get('decision'),
            'archive': k.get('archive'), 'verdict': verdict}


def payoff_frontier_block():
    """The buyer's comparison (D-114), small enough for the page to carry.

    Copied from findings/payoff_frontier.json, which measure_payoff.py writes
    earlier in the same workflow: the verdict, the conditions it rests on and
    the combo-fee sensitivity (D-115), WITHOUT the per-condition table and the
    reference ticket. Recomputing any of it here would make two places able to
    disagree. None when the file is absent.
    """
    path = os.path.join(ROOT, 'findings', 'payoff_frontier.json')
    try:
        with open(path, encoding='utf-8') as f:
            k = json.load(f)
    except (OSError, ValueError):
        return None
    verdict = k.get('verdict')
    if not isinstance(verdict, dict):
        return None
    return {'decision': k.get('decision'), 'family': k.get('family'),
            'archive': k.get('archive'), 'verdict': verdict,
            'stable_conditions': k.get('stable_conditions'),
            'sensitivity_combo_fees': k.get('sensitivity_combo_fees')}


def main():
    all_stamps = stamps('_meta')
    o = summary()
    print('measuring: %d snapshots' % len(all_stamps))

    result = {
        'archive': o,
        # Which archive produced these numbers. A run against the private
        # mirror covers everything since 2026-08-30; a run without it covers
        # the 14-day public window. The same figure computed over different
        # spans is not the same figure, so the span is on the record.
        'archive_source': ('private mirror' if os.environ.get('DIVERGENCE_RAW')
                           else '14-day public window'),
        'produced_by': 'scripts/write_findings.py',
        'measurements': {
            # Two blocks, one per tenor: 'year_end' and 'intraday'. The
            # numbers are not comparable across them and must not be pooled.
            'friction_band_kalshi': measure_band_all(all_stamps),
            'polymarket_terminal': measure_polymarket_all(all_stamps),
            'long_horizon_touch': measure_touch_all(all_stamps),
            'exhaustiveness_constraint': measure_exhaustive_all(all_stamps),
            # Not a measurement this script performs: the verdict recorded by
            # scripts/kill_test_eth5k.py earlier in the same workflow, carried
            # so the interface can print its exact words (G1). None if that
            # step did not run.
            'kill_test_eth5k': kill_test_block(),
            # The buyer's comparison of D-114, carried the same way: judged by
            # scripts/measure_payoff.py, copied here. None if that step did
            # not run.
            'payoff_frontier': payoff_frontier_block(),
        },
    }

    folder = os.path.join(ROOT, 'findings')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, 'latest.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print('written: findings/latest.json')
    for name, m in result['measurements'].items():
        if not isinstance(m, dict):
            print('  %-26s absent' % name)
            continue
        if name in ('kill_test_eth5k', 'payoff_frontier'):
            print('  %-26s %s' % (name, m['verdict'].get('verdict')))
            continue
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
