#!/usr/bin/env python3
"""Kill test — ETH above $5,000, against the local strike grid, on both expiries.

WHY THIS EXISTS (D-092)
One Kalshi year-end rung survives the maturity stress test: ETH above $5,000,
by about 0.4 cents. The grid sensitivity on the chain that decides it is a
median 11.5%, measured across rungs but never on this rung. So the rung is
neither a finding nor an artefact until the following has been computed, and
D-092 wrote the verdict rules BEFORE this script existed so that the number
cannot choose its own interpretation.

WHAT IS COMPUTED, per snapshot, per bracketing expiry (early and late):
  tight            the bracket production uses: strikes strictly below and
                   above K. A listed 5,000 strike is never itself used by
                   measure_band.bracket(), so this is 4,800-5,200 on 25DEC26
                   and 4,800-5,500 on 26MAR27 today.
  skip1, skip2     the wider brackets of measure_sensitivity.wide_bracket()
  onesided_lower   lower strike -> 5,000, only if 5,000 is listed
  onesided_upper   5,000 -> upper strike, only if 5,000 is listed
For each: the mark discounted state price, the executable low and high (ask on
the leg bought, bid on the leg sold, the same rule as measure_band.digital),
the width, and the Deribit fee on the CROSSED price of each leg. A one-sided
quote on any leg makes the estimator None. That is a refusal, not a zero.

THE COMPARISON
  kalshi_net = yes_bid - fees.rate(yes_bid, series)
  margin_e   = kalshi_net - (high_e + fee_e)         for every estimator e
  margin_vs_worst_local_executable = kalshi_net - max_e (high_e + fee_e)
The rung is "above 5,000" (strike_type 'greater'), so its bucket is a single
digital with no upper leg: the executable high of the bucket is the high of
the digital itself. This matches measure_band, where an unbounded upper edge
contributes exactly zero.

THE INTERPOLANT (D-094)
  dsp(T*) = dsp(T1) + (T* - T1)/(T2 - T1) * (dsp(T2) - dsp(T1))
reported as a SENSITIVITY, never as the settlement-date value. With the band
at -165 h / +2,019 h the weight on the late chain is about 0.076.

THE PRE-COMMITTED VERDICT (D-092, DECISION_GATES.md G1) — not editable now:
  share of snapshots with margin_vs_worst_local_executable > 0
      < PERSISTENCE (0.9, the always_above of stability.py)
                       -> "not a surviving discrepancy"
  else, min margin < TINY_MARGIN (0.01) or min margin x depth < TINY_VALUE_USD (1.0)
                       -> "indistinguishable from grid and quote noise"
  else               -> "a genuine anomaly requiring more observations"

Nothing here fits a surface, interpolates in strike, or assumes a model.

Usage:
    python scripts/kill_test_eth5k.py            # whole archive
    python scripts/kill_test_eth5k.py --last 5
"""
import json
import os
import sys

import fees
from archive import snapshot, stamps, summary, Missing
from measure_band import chain, discount, forward, expiry_instant, iso_instant
from measure_sensitivity import neighbours, wide_bracket

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SERIES = 'KXETHY'
CURRENCY = 'ETH'
K = 5000.0
LABEL = 'ETH above 5000'

# The verdict constants. Written in D-092 before any number was seen. Changing
# them after the fact is the thing the pre-commitment exists to prevent, and
# tests/test_measurement.py pins PERSISTENCE to stability.py's threshold.
PERSISTENCE = 0.9
TINY_MARGIN = 0.01        # one cent: the unit Kalshi rounds each order's fee to
TINY_VALUE_USD = 1.0      # margin x resting depth, in dollars

VERDICT_NOT_SURVIVING = 'not a surviving discrepancy'
VERDICT_NOISE = 'indistinguishable from grid and quote noise'
VERDICT_ANOMALY = 'a genuine anomaly requiring more observations'

ESTIMATORS = ('tight', 'skip1', 'skip2', 'onesided_lower', 'onesided_upper')


def deribit_fee_usd(price_usd, idx):
    """Deribit's option fee per contract: 0.03% of the underlying, capped at
    12.5% of the option price. Same formula as measure_band.digital, applied
    here to the price actually crossed rather than the mark."""
    return min(0.0003 * idx, 0.125 * price_usd)


def brackets(o, K):
    """The five brackets of D-092 on one side of the chain. Each is a pair of
    strikes (a, b) with a < b, or None when the chain cannot supply it.

    The listed 5,000 strike is used ONLY by the one-sided pair: bracket() in
    production takes strictly-below and strictly-above, which is why the tight
    bracket here is 4,800-5,200 even though 5,000 exists.
    """
    out = {}
    for name, skip in (('tight', 0), ('skip1', 1), ('skip2', 2)):
        out[name] = wide_bracket(o, K, skip)
    ks = sorted(o)
    if K in o:
        below = [k for k in ks if k < K]
        above = [k for k in ks if k > K]
        out['onesided_lower'] = (below[-1], K) if below else None
        out['onesided_upper'] = (K, above[0]) if above else None
    else:
        out['onesided_lower'] = out['onesided_upper'] = None
    return out


def estimate(o, pair, idx):
    """One estimator on the CALL side: D*Q(S>K) as the difference quotient over
    the pair, with the executable envelope and the crossed-price fee.

    Long the lower strike, short the upper one. The buyer pays the lower leg's
    ASK and receives the upper leg's BID; that is the executable high. The fee
    is charged on those two crossed prices, per unit of digital (divided by
    the width), exactly as measure_band divides its fee by w.
    """
    if not pair:
        return None
    a, b = pair
    A, B = o[a], o[b]
    w = b - a
    if w <= 0:
        return None
    row = {'lower': a, 'upper': b, 'width': w,
           'dsp': (A['mark'] - B['mark']) / w,
           'low': None, 'high': None, 'fee': None, 'cost': None}
    if None in (A['bid'], A['ask'], B['bid'], B['ask']):
        row['refused'] = 'one-sided quote on a leg'
        return row
    row['low'] = (A['bid'] - B['ask']) / w
    row['high'] = (A['ask'] - B['bid']) / w
    row['fee'] = (deribit_fee_usd(A['ask'], idx) + deribit_fee_usd(B['bid'], idx)) / w
    row['cost'] = row['high'] + row['fee']
    return row


def find_rung(KA):
    """The 'ETH above 5000' market in a Kalshi snapshot, or None."""
    for m in (KA.get('markets', {}).get(SERIES) or []):
        if m.get('status') != 'active' or m.get('strike_type') != 'greater':
            continue
        if m.get('floor_strike') is None:
            continue
        if round(m['floor_strike'] + .01) == K:
            return m
    return None


def interpolant(dsp1, h1, dsp2, h2):
    """Linear in time between the two chains, to the close (hours = 0).
    h1 < 0 is the early chain, h2 > 0 the late one. Returns (value, weight on
    the late chain). A sensitivity, not a settlement-date value (D-094)."""
    if None in (dsp1, dsp2) or h2 == h1:
        return None, None
    wgt = (0.0 - h1) / (h2 - h1)
    return dsp1 + wgt * (dsp2 - dsp1), wgt


def run(stamp):
    """Everything D-092 asks for, on one snapshot. Never raises on a missing
    piece: the row says what was missing."""
    g = snapshot(stamp)
    row = {'stamp': stamp, 'window': g.sync_window}
    m = find_rung(g.kalshi)
    if not m:
        row['error'] = 'rung not in snapshot'
        return row
    bid = float(m['yes_bid_dollars'])
    ask = float(m['yes_ask_dollars'])
    try:
        depth = float(m.get('yes_bid_size_fp'))
    except (TypeError, ValueError):
        depth = None
    close_at = iso_instant(m.get('close_time', ''))
    if close_at is None:
        row['error'] = 'no close_time'
        return row
    kalshi_fee = fees.rate(bid, SERIES)
    net = bid - kalshi_fee
    row.update({'ticker': m.get('ticker'), 'bid': bid, 'ask': ask,
                'depth': depth, 'kalshi_fee': round(kalshi_fee, 6),
                'kalshi_net': round(net, 6)})

    ch, idx = chain(g.deribit, CURRENCY)
    near = neighbours(ch, close_at)
    sides = {n['side']: n for n in near}
    if 'before' not in sides or 'after' not in sides:
        row['error'] = 'expiries do not straddle the close'
        return row

    costs = []
    row['expiries'] = {}
    for side in ('before', 'after'):
        n = sides[side]
        exp = n['expiry']
        dis = discount(ch, exp)
        D = dis['D'] if dis else 1.0
        F = forward(ch, exp, idx, D)
        e = {'expiry': exp, 'hours': round(n['hours'], 2), 'D': round(D, 6),
             'D_estimated': dis is not None, 'F': F,
             'strike_5000_listed': K in (ch[exp].get('C') or {})}
        if not F or K <= F:
            # The call side is the one production uses above the forward. If
            # the forward ever sits above 5,000 this rung is no longer a tail
            # and the test as specified does not apply.
            e['error'] = 'K is not above the forward; call side not applicable'
            row['expiries'][side] = e
            continue
        o = ch[exp].get('C') or {}
        e['estimators'] = {}
        for name, pair in brackets(o, K).items():
            est = estimate(o, pair, idx)
            if est is None:
                e['estimators'][name] = None
                continue
            est['margin'] = None if est['cost'] is None else round(net - est['cost'], 6)
            e['estimators'][name] = est
            if est['cost'] is not None:
                costs.append(est['cost'])
        row['expiries'][side] = e

    # The one number the verdict reads: against the most expensive executable
    # estimate anywhere on either chain.
    if costs:
        worst = max(costs)
        row['worst_local_executable_cost'] = round(worst, 6)
        row['margin_vs_worst_local_executable'] = round(net - worst, 6)
        row['estimators_available'] = len(costs)
        row['value_at_depth_usd'] = (None if depth is None
                                     else round((net - worst) * depth, 2))
    else:
        row['margin_vs_worst_local_executable'] = None
        row['estimators_available'] = 0

    # The interpolant, on the tight estimator, as a sensitivity.
    b, a = row['expiries'].get('before', {}), row['expiries'].get('after', {})
    t1 = ((b.get('estimators') or {}).get('tight') or {}).get('dsp')
    t2 = ((a.get('estimators') or {}).get('tight') or {}).get('dsp')
    val, wgt = interpolant(t1, b.get('hours'), t2, a.get('hours'))
    row['interpolant'] = {'dsp_early': t1, 'dsp_late': t2,
                          'dsp_at_close_linear': val, 'weight_on_late': wgt,
                          'note': 'sensitivity, not a settlement-date value (D-094)'}
    return row


def verdict(rows):
    """The pre-committed rules of D-092 applied to the per-snapshot rows.
    Returns the verdict and the numbers it rested on."""
    judged = [r for r in rows if r.get('margin_vs_worst_local_executable') is not None]
    n = len(judged)
    if n == 0:
        return {'verdict': 'UNKNOWN', 'reason': 'no snapshot had an executable estimate',
                'snapshots_judged': 0}
    margins = [r['margin_vs_worst_local_executable'] for r in judged]
    positive = sum(1 for x in margins if x > 0)
    share = positive / float(n)
    values = [r['value_at_depth_usd'] for r in judged if r.get('value_at_depth_usd') is not None]
    out = {'snapshots_judged': n, 'snapshots_positive': positive,
           'share_positive': round(share, 4),
           'min_margin': round(min(margins), 6),
           'median_margin': round(sorted(margins)[n // 2], 6),
           'min_value_at_depth_usd': (round(min(values), 2) if values else None),
           'rules': {'persistence': PERSISTENCE, 'tiny_margin': TINY_MARGIN,
                     'tiny_value_usd': TINY_VALUE_USD}}
    if share < PERSISTENCE:
        out['verdict'] = VERDICT_NOT_SURVIVING
        out['reason'] = ('margin against the worst local executable estimate is '
                         'positive in %d of %d snapshots (%.1f%%), below %.0f%%'
                         % (positive, n, 100 * share, 100 * PERSISTENCE))
    elif min(margins) < TINY_MARGIN or (values and min(values) < TINY_VALUE_USD):
        out['verdict'] = VERDICT_NOISE
        out['reason'] = ('positive in %d of %d, but the smallest margin is %.4f '
                         '(rule: %.2f) and the smallest value at depth is %s USD (rule: %.0f)'
                         % (positive, n, min(margins), TINY_MARGIN,
                            ('%.2f' % min(values)) if values else 'UNKNOWN', TINY_VALUE_USD))
    else:
        out['verdict'] = VERDICT_ANOMALY
        out['reason'] = ('positive in %d of %d with a smallest margin of %.4f and a '
                         'smallest value at depth of %.2f USD'
                         % (positive, n, min(margins), min(values) if values else float('nan')))
    return out


def main():
    argv = sys.argv[1:]
    last = int(argv[argv.index('--last') + 1]) if '--last' in argv else None
    every = stamps('_meta')
    if last:
        every = every[-last:]
    o = summary()

    rows = []
    for stamp in every:
        try:
            rows.append(run(stamp))
        except Missing as e:
            rows.append({'stamp': stamp, 'error': str(e)})
        except (KeyError, TypeError, ValueError) as e:
            rows.append({'stamp': stamp, 'error': '%s: %s' % (type(e).__name__, e)})

    v = verdict(rows)

    print('KILL TEST — %s against the local strike grid (D-092)' % LABEL)
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days' % o)
    print('snapshots scanned: %d, judged: %d' % (len(rows), v.get('snapshots_judged', 0)))
    print()
    print('%-18s %7s %7s  %s' % ('snapshot', 'net', 'worst', 'margin per estimator (early | late)'))
    print('-' * 110)
    for r in rows:
        if 'error' in r:
            print('%-18s  %s' % (r['stamp'], r['error']))
            continue
        cells = []
        for side in ('before', 'after'):
            e = r['expiries'].get(side, {})
            ests = e.get('estimators') or {}
            cells.append(' '.join('%s=%s' % (name[:6],
                                           ('%+.4f' % ests[name]['margin'])
                                           if ests.get(name) and ests[name].get('margin') is not None
                                           else '-')
                                  for name in ESTIMATORS))
        print('%-18s %7.4f %7s  %s | %s' % (
            r['stamp'], r['kalshi_net'],
            ('%.4f' % r['worst_local_executable_cost'])
            if r.get('worst_local_executable_cost') is not None else '-',
            cells[0], cells[1]))
    print('-' * 110)
    print('VERDICT: %s' % v.get('verdict'))
    print('  %s' % v.get('reason'))
    if v.get('snapshots_judged'):
        print('  min margin %.4f, median %.4f, min value at depth %s USD'
              % (v['min_margin'], v['median_margin'],
                 v['min_value_at_depth_usd'] if v['min_value_at_depth_usd'] is not None else 'UNKNOWN'))
    last_row = next((r for r in reversed(rows) if 'error' not in r), None)
    if last_row:
        ip = last_row['interpolant']
        print()
        print('Interpolant on the newest snapshot (sensitivity, D-094): early %s, late %s,'
              % (('%.5f' % ip['dsp_early']) if ip['dsp_early'] is not None else '-',
                 ('%.5f' % ip['dsp_late']) if ip['dsp_late'] is not None else '-'))
        print('  linear-in-time at the close %s with weight %s on the late chain.'
              % (('%.5f' % ip['dsp_at_close_linear']) if ip['dsp_at_close_linear'] is not None else '-',
                 ('%.3f' % ip['weight_on_late']) if ip['weight_on_late'] is not None else '-'))
    print()
    print('Reading note: the verdict rules were written in D-092 before this script')
    print('existed. "margin" is kalshi_net minus (executable high + Deribit fee on the')
    print('crossed prices) of an estimator; "worst" is the most expensive estimator on')
    print('either chain. A one-sided leg makes an estimator None rather than zero.')
    print('The listed 5,000 strike is used only by the one-sided quotients; the')
    print('production bracket has always stepped over it.')

    record = {
        'archive': o,
        'produced_by': 'scripts/kill_test_eth5k.py',
        'decision': 'D-092',
        'rung': {'series': SERIES, 'label': LABEL, 'K': K},
        'verdict': v,
        'newest_interpolant': last_row['interpolant'] if last_row else None,
        'snapshots': rows,
    }
    folder = os.path.join(ROOT, 'findings')
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, 'kill_test_eth5k.json'), 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
