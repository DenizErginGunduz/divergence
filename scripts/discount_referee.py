#!/usr/bin/env python3
"""Discount-factor referees — four estimates of D side by side, as rates.

WHY THIS EXISTS (D-093)
`measure_band.discount()` reads D off the put-call residual and every number
in the pipeline divides through it. It is identified and needs no forward, but
it has been the only estimate of itself. This script puts four next to each
other, each converted to an implied annual rate  r = -ln(D) / T  so they can
be read in one unit. No referee is declared right; the point is consistency.

  R1  the current estimator: median over shared brackets of the put-side
      minus call-side residual, 1 - D  (measure_band.discount)
  R2  the parity slope across the chain: C(K) - P(K) = D*F - D*K, so a
      least-squares slope of (C - P) against K near the forward is -D.
      NOT INDEPENDENT of R1 — it is the same identity, re-estimated
      (least squares over the chain instead of a median of per-bracket
      differences; mids as well as marks). Recorded as an
      ESTIMATOR-CONSISTENCY CHECK and labelled that way in the output.
  R3  the futures basis: every option row carries Deribit's
      `underlying_price` for its expiry — the listed future where one is
      listed, a synthetic otherwise. D3 = index_price / underlying_price.
      Whether a given expiry's underlying is listed or synthetic is not in
      the payload and is UNKNOWN per expiry (B-018 would settle it).
  R4  an external USD rate, entered by hand as a dated constant with its
      source next to it, because measure.yml has no network access. A
      sanity check, not the "correct" rate: crypto option pricing may embed
      collateral basis, cross-currency basis, funding and venue-specific
      financing. The only number in the measurement path that does not come
      from the archive, and it says so. UNKNOWN until a value is entered.

The three differences are reported separately because they mean three
different things: R1-R2 is estimator disagreement; R1-R3 is the
financing / collateral basis between the option chain and its future;
R1-R4 is the distance from an external money-market rate.

Usage:
    python scripts/discount_referee.py            # whole archive
    python scripts/discount_referee.py --last 5
"""
import json
import math
import os
import sys
from datetime import datetime, timezone

from archive import snapshot, stamps, summary, Missing
from measure_band import chain, discount, expiry_instant, MIN_BRACKETS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CURRENCIES = ('BTC', 'ETH')

# The external rate. Hand-entered, dated, sourced. Overnight SOFR as published
# by the New York Fed, read from FRED series SOFR. An OVERNIGHT rate used flat
# across the maturity: a term rate would be the better comparator and is not
# free; the label says which this is. Update the three fields together, and
# never silently. Set 'value' to None to make R4 print UNKNOWN.
EXTERNAL_RATE = {
    'name': 'SOFR (overnight), used flat',
    'value': 3.62,                      # percent per annum
    'as_of': '2026-09-14',
    'source': 'https://fred.stlouisfed.org/series/SOFR (NY Fed data)',
    'entered': '2026-09-16',
}

# Same strike window forward() uses: near the money, where both legs have
# time value and a mark is a price rather than an intrinsic.
NEAR_LO, NEAR_HI = 0.85, 1.2
MIN_POINTS = 3


def stamp_instant(stamp):
    """'2026-09-16T1302Z' -> datetime, UTC."""
    return datetime(int(stamp[0:4]), int(stamp[5:7]), int(stamp[8:10]),
                    int(stamp[11:13]), int(stamp[13:15]), tzinfo=timezone.utc)


def years_to(expiry, stamp):
    """Time to the 08:00 UTC settlement, in years. None if not in the future."""
    ts = expiry_instant(expiry)
    if ts is None:
        return None
    y = (ts - stamp_instant(stamp)).total_seconds() / (365.25 * 86400.0)
    return y if y > 0 else None


def implied_rate(D, T):
    """r = -ln(D) / T, in percent per annum. None where undefined."""
    if D is None or T is None or D <= 0 or T <= 0:
        return None
    return -100.0 * math.log(D) / T


def discount_from_rate(r_pct, T):
    """D = exp(-r T) for a percent rate. The inverse of implied_rate."""
    if r_pct is None or T is None or T <= 0:
        return None
    return math.exp(-r_pct / 100.0 * T)


def slope(xs, ys):
    """Ordinary least-squares slope of ys on xs. None below MIN_POINTS."""
    n = len(xs)
    if n < MIN_POINTS:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx


def parity_slope(ch, expiry, idx):
    """R2: -slope of (C - P) against K near the forward, on marks and on mids.

    Mids only where BOTH legs are two-sided; a one-sided leg is left out of
    the mid regression rather than filled from its mark."""
    C, P = ch[expiry].get('C'), ch[expiry].get('P')
    if not C or not P:
        return None
    ks = sorted(k for k in C if k in P and NEAR_LO * idx < k < NEAR_HI * idx)
    if len(ks) < MIN_POINTS:
        return None
    xm = ks
    ym = [C[k]['mark'] - P[k]['mark'] for k in ks]
    xd, yd = [], []
    for k in ks:
        c, p = C[k], P[k]
        if None in (c['bid'], c['ask'], p['bid'], p['ask']):
            continue
        xd.append(k)
        yd.append((c['bid'] + c['ask']) / 2.0 - (p['bid'] + p['ask']) / 2.0)
    sm = slope(xm, ym)
    sd = slope(xd, yd)
    return {'D_marks': (-sm if sm is not None else None),
            'D_mids': (-sd if sd is not None else None),
            'points_marks': len(xm), 'points_mids': len(xd)}


def underlying_by_expiry(D_raw, currency):
    """R3's input: the median `underlying_price` of the options on each expiry.
    Read from the raw book_summary because chain() does not carry it."""
    bs = D_raw[currency]['book_summary']
    bs = bs['result'] if isinstance(bs, dict) else bs
    per = {}
    for b in bs:
        q = b['instrument_name'].split('-')
        if len(q) != 4:
            continue
        u = b.get('underlying_price')
        if u:
            per.setdefault(q[1], []).append(float(u))
    out = {}
    for exp, vals in per.items():
        vals.sort()
        out[exp] = {'underlying_price': vals[len(vals) // 2], 'rows': len(vals)}
    return out


def run(stamp):
    """Every referee on every usable expiry of both currencies, one snapshot."""
    g = snapshot(stamp)
    D_raw = g.deribit
    out = {'stamp': stamp, 'chains': []}
    for cur in CURRENCIES:
        ch, idx = chain(D_raw, cur)
        und = underlying_by_expiry(D_raw, cur)
        for exp in sorted(ch, key=lambda v: expiry_instant(v) or datetime.max.replace(tzinfo=timezone.utc)):
            if not ch[exp].get('C') or not ch[exp].get('P'):
                continue
            T = years_to(exp, stamp)
            if T is None:
                continue
            r1 = discount(ch, exp)
            if r1 is None:
                # Below MIN_BRACKETS or outside the plausible range: the
                # production estimator refuses here, and so does this.
                out['chains'].append({'currency': cur, 'expiry': exp, 'T_years': round(T, 5),
                                      'skipped': 'R1 refused (thin chain or implausible D)'})
                continue
            r2 = parity_slope(ch, exp, idx)
            u = und.get(exp)
            D3 = (idx / u['underlying_price']) if u and u['underlying_price'] else None
            D4 = discount_from_rate(EXTERNAL_RATE['value'], T)
            row = {
                'currency': cur, 'expiry': exp, 'T_years': round(T, 5),
                'index': idx,
                'R1': {'D': r1['D'], 'rate': implied_rate(r1['D'], T),
                       'brackets': r1['brackets'], 'label': 'current estimator (median bracket residual)'},
                'R2': {'D_marks': r2['D_marks'] if r2 else None,
                       'D_mids': r2['D_mids'] if r2 else None,
                       'rate_marks': implied_rate(r2['D_marks'], T) if r2 else None,
                       'rate_mids': implied_rate(r2['D_mids'], T) if r2 else None,
                       'points': (r2['points_marks'], r2['points_mids']) if r2 else None,
                       'label': 'parity slope — estimator-consistency check, NOT independent of R1'},
                'R3': {'D': D3, 'rate': implied_rate(D3, T),
                       'underlying_price': u['underlying_price'] if u else None,
                       'listed_or_synthetic': 'UNKNOWN',
                       'label': 'futures basis from underlying_price'},
                'R4': {'D': D4, 'rate': EXTERNAL_RATE['value'],
                       'label': 'external rate, dated constant',
                       'as_of': EXTERNAL_RATE['as_of'], 'source': EXTERNAL_RATE['source']}
                      if EXTERNAL_RATE['value'] is not None else
                      {'D': None, 'rate': None, 'label': 'external rate: UNKNOWN (no value entered)'},
            }

            def bp(a, b):
                return None if a is None or b is None else round((a - b) * 100.0, 2)
            row['diff_bp'] = {
                'R1_minus_R2_marks (estimator disagreement)': bp(row['R1']['rate'], row['R2']['rate_marks']),
                'R1_minus_R2_mids (estimator disagreement)': bp(row['R1']['rate'], row['R2']['rate_mids']),
                'R1_minus_R3 (financing/collateral basis)': bp(row['R1']['rate'], row['R3']['rate']),
                'R1_minus_R4 (distance from external rate)': bp(row['R1']['rate'], row['R4']['rate']),
            }
            out['chains'].append(row)
    return out


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def aggregate(results):
    """Per (currency, expiry) medians across snapshots, and the three
    headline medians across everything."""
    per = {}
    for r in results:
        for c in r.get('chains', []):
            if 'skipped' in c:
                continue
            key = '%s %s' % (c['currency'], c['expiry'])
            p = per.setdefault(key, {'n': 0, 'r1': [], 'r2m': [], 'r2d': [], 'r3': [], 'r4': [],
                                     'd12': [], 'd13': [], 'd14': []})
            p['n'] += 1
            p['r1'].append(c['R1']['rate'])
            p['r2m'].append(c['R2']['rate_marks'])
            p['r2d'].append(c['R2']['rate_mids'])
            p['r3'].append(c['R3']['rate'])
            p['r4'].append(c['R4']['rate'])
            d = c['diff_bp']
            p['d12'].append(d['R1_minus_R2_marks (estimator disagreement)'])
            p['d13'].append(d['R1_minus_R3 (financing/collateral basis)'])
            p['d14'].append(d['R1_minus_R4 (distance from external rate)'])
    table = {}
    for key, p in per.items():
        table[key] = {'snapshots': p['n'],
                      'median_rate_pct': {'R1': median(p['r1']), 'R2_marks': median(p['r2m']),
                                          'R2_mids': median(p['r2d']), 'R3': median(p['r3']),
                                          'R4': median(p['r4'])},
                      'median_diff_bp': {'R1_minus_R2': median(p['d12']),
                                         'R1_minus_R3': median(p['d13']),
                                         'R1_minus_R4': median(p['d14'])}}
    alld12 = [abs(x) for p in per.values() for x in p['d12'] if x is not None]
    alld13 = [x for p in per.values() for x in p['d13'] if x is not None]
    alld14 = [x for p in per.values() for x in p['d14'] if x is not None]
    headline = {
        'chains_judged': sum(p['n'] for p in per.values()),
        'median_abs_R1_minus_R2_bp (estimator consistency)': median(alld12),
        'median_R1_minus_R3_bp (financing basis)': median(alld13),
        'median_R1_minus_R4_bp (vs external rate)': median(alld14),
    }
    return table, headline


def main():
    argv = sys.argv[1:]
    last = int(argv[argv.index('--last') + 1]) if '--last' in argv else None
    every = stamps('_meta')
    if last:
        every = every[-last:]
    o = summary()

    results = []
    for stamp in every:
        try:
            results.append(run(stamp))
        except Missing as e:
            results.append({'stamp': stamp, 'error': str(e)})
        except (KeyError, TypeError, ValueError) as e:
            results.append({'stamp': stamp, 'error': '%s: %s' % (type(e).__name__, e)})

    table, headline = aggregate(results)

    print('DISCOUNT-FACTOR REFEREES (D-093) — implied annual rates, percent')
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days' % o)
    print('external rate: %s = %s%% as of %s (%s)'
          % (EXTERNAL_RATE['name'], EXTERNAL_RATE['value'] if EXTERNAL_RATE['value'] is not None else 'UNKNOWN',
             EXTERNAL_RATE['as_of'], EXTERNAL_RATE['source']))
    print()
    newest = next((r for r in reversed(results) if 'chains' in r), None)
    if newest:
        print('newest snapshot %s' % newest['stamp'])
        print('%-4s %-8s %7s  %7s %7s %7s %7s %7s   %8s %8s %8s' % (
            '', 'expiry', 'T', 'R1', 'R2mark', 'R2mid', 'R3', 'R4', 'd12 bp', 'd13 bp', 'd14 bp'))
        print('-' * 100)
        for c in newest['chains']:
            if 'skipped' in c:
                print('%-4s %-8s %7.4f  %s' % (c['currency'], c['expiry'], c['T_years'], c['skipped']))
                continue
            f = lambda x: ('%7.2f' % x) if x is not None else '      -'
            d = c['diff_bp']
            print('%-4s %-8s %7.4f  %s %s %s %s %s   %8s %8s %8s' % (
                c['currency'], c['expiry'], c['T_years'],
                f(c['R1']['rate']), f(c['R2']['rate_marks']), f(c['R2']['rate_mids']),
                f(c['R3']['rate']), f(c['R4']['rate']),
                f(d['R1_minus_R2_marks (estimator disagreement)']),
                f(d['R1_minus_R3 (financing/collateral basis)']),
                f(d['R1_minus_R4 (distance from external rate)'])))
    print('-' * 100)
    print('across all judged chains: %s' % json.dumps(headline))
    print()
    print('Reading note: R2 is the SAME identity as R1 with a different estimator —')
    print('its disagreement with R1 is estimator noise, not independent evidence.')
    print('R3 and R4 are independent. R3 divides the index by the option rows\'')
    print('underlying_price, which is a listed future where one exists and a synthetic')
    print('otherwise; which one it is per expiry is UNKNOWN from the payload (B-018).')
    print('R4 is an overnight rate used flat, entered by hand with its date and source;')
    print('the objective is consistency, not forcing the chain onto it. No referee is')
    print('declared right.')

    record = {
        'archive': o,
        'produced_by': 'scripts/discount_referee.py',
        'decision': 'D-093',
        'external_rate': EXTERNAL_RATE,
        'headline': headline,
        'per_expiry': table,
        'newest': newest,
    }
    folder = os.path.join(ROOT, 'findings')
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, 'discount_referee.json'), 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
