#!/usr/bin/env python3
"""Friction band — how many rungs clear the cost of trading them?

THE QUESTION
Is the gap between a prediction-market price and the digital implied by the
option chain LARGER than what it would cost to trade that gap?

WHAT THE TEST IS NOW (was: 1.96*SE + friction)
Every price here is a quote someone is standing behind, so the question is
asked as a trade rather than as a statistic:

  sell the prediction at its BID, buy the option bucket at its ASK side, pay
  the option fees. Is there anything left?
  or the mirror: buy the prediction at its ASK, sell the bucket at its BID
  side, pay the fees. Is there anything left?

The bucket's two executable prices come from the option quotes directly:
  opt_high — what buying the spread costs: ask on the long leg, bid on the
             short one.
  opt_low  — what selling it pays: the other way round.
The width between them is a cost, not a confidence interval, which is the
whole reason for the change. 1.96*SE was a statement about how uncertain our
ESTIMATE of the mid was; it answered a question nobody can trade on. The
standard error is still computed and reported, but it no longer decides
anything.

WHAT THE OPTION NUMBER IS (D-073)
It is a DISCOUNTED STATE PRICE, D*Q(lo < S_T < hi), not a probability. Q is
the risk-neutral measure and D the discount factor to expiry. Both are read
off prices, so both sides of the comparison are present values: the Kalshi
YES price is also what one pays today for a dollar at settlement. Dividing
by D would give Q, which is still not a real-world probability — the gap
between Q and P is the volatility risk premium and nothing here measures it.

Until D-073 the two sides of the digital used DIFFERENT conventions: the
call side returned D*Q(S>K) while the put side returned 1 - D*Q(S<K), which
is (1-D) + D*Q(S>K). The sum-to-1 exhaustiveness check could not see this,
because D*1 + (1-D) = 1 for any D. D-073 measured the residual across 28
chains and found it flat in strike to ~0.5% of its own size, with an implied
rate term structure of 3.2-5.5%, which is what licensed the repair below.

WHY THIS SCRIPT EXISTS
The page showed "0/44" while nothing in the repository produced it; the old
scripts read a file layout that no longer existed (audit, 2026-09-11). This
script computes from the raw archive, so the result can be checked.

ONE SNAPSHOT IS NOT ENOUGH
No claim of statistical significance can rest on a single snapshot. So the
whole archive is scanned and the distribution reported. A rung that clears
the band in one run may not in the next; what matters is stability, not the
ratio.

Usage:
    python scripts/measure_band.py              # whole archive
    python scripts/measure_band.py --last 5     # only the last 5 runs
    python scripts/measure_band.py --json       # machine-readable output
"""
import json
import math
import re
import sys

from archive import snapshot, stamps, summary, Missing
from stability import Stability

SERIES = [('BTC', 'KXBTCY', 'BTC'), ('ETH', 'KXETHY', 'ETH')]

MONTH = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
         'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
EXPIRY = re.compile(r'^(\d+)([A-Z]{3})(\d{2})$')

# Fewer brackets than this and the median residual is not a measurement.
MIN_BRACKETS = 8
# A discount factor outside this range is not a funding curve. Short-dated
# chains land here because 1-D is smaller than the tick (D-073 caveat); the
# caller then falls back to D=1 and records that it did.
D_FLOOR, D_CEIL = 0.5, 1.0


def expiry_ord(label):
    """Deribit expiry label -> sortable number. '26DEC25' -> 20251226"""
    m = EXPIRY.match(label)
    if not m:
        return None
    return (2000 + int(m.group(3))) * 10000 + MONTH[m.group(2)] * 100 + int(m.group(1))


def chain(D, currency):
    """Deribit book_summary -> ch[expiry]['C'/'P'][strike] = {mark,bid,ask}
    Inverse contracts quote prices in units of the underlying; multiply by
    the index to get dollars."""
    idx = D[currency]['index']['result']['index_price']
    bs = D[currency]['book_summary']
    bs = bs['result'] if isinstance(bs, dict) else bs
    ch = {}
    for b in bs:
        q = b['instrument_name'].split('-')
        if len(q) != 4:
            continue
        expiry, strike, kind = q[1], float(q[2]), q[3]
        ch.setdefault(expiry, {}).setdefault(kind, {})[strike] = {
            'mark': (b.get('mark_price') or 0) * idx,
            'bid': b['bid_price'] * idx if b.get('bid_price') else None,
            'ask': b['ask_price'] * idx if b.get('ask_price') else None,
        }
    return ch, idx


def discount(ch, expiry):
    """Discount factor read off the put-call residual (D-073).

    On the same bracket the call side gives D*Q(S>K) and the put side gives
    1 - D*Q(S<K) = (1-D) + D*Q(S>K), so their difference is 1-D and carries
    no Q at all. The median over every shared bracket is taken so one broken
    quote cannot move it. Needs no forward, so there is no circularity with
    forward() below.

    Returns None when the chain is too thin or the estimate is implausible.
    """
    C, P = ch[expiry].get('C'), ch[expiry].get('P')
    if not C or not P:
        return None
    shared = sorted(set(C) & set(P))
    res = []
    for a, b in zip(shared, shared[1:]):
        w = b - a
        if w <= 0:
            continue
        call_side = (C[a]['mark'] - C[b]['mark']) / w
        put_side = 1.0 - (P[b]['mark'] - P[a]['mark']) / w
        res.append(put_side - call_side)
    if len(res) < MIN_BRACKETS:
        return None
    res.sort()
    d = 1.0 - res[len(res) // 2]
    if not (D_FLOOR < d <= D_CEIL):
        return None
    return {'D': d, 'brackets': len(res), 'spread': res[-1] - res[0]}


def forward(ch, expiry, idx, D=1.0):
    """Forward from put-call parity. Parity is C - P = D*(F - K), so
    F = K + (C - P)/D. Before D-073 this divided by nothing, i.e. assumed
    D=1, which biases F by -(1-D)*(F-K) — about 21 USD on a December chain,
    a fifth of the observed cross-strike dispersion. Small, but there is now
    no reason to carry it. The median is taken so a single broken quote
    cannot drag the result. Needs no futures data.
    """
    C, P = ch[expiry].get('C'), ch[expiry].get('P')
    if not C or not P:
        return None
    v = [k + (C[k]['mark'] - P[k]['mark']) / D
         for k in C if k in P and 0.85 * idx < k < 1.2 * idx]
    if not v:
        return None
    v.sort()
    return v[len(v) // 2]


def bracket(o, K):
    """The two neighbouring strikes that bracket K."""
    ks = sorted(o)
    below = [k for k in ks if k < K]
    above = [k for k in ks if k > K]
    return (below[-1], above[0]) if below and above else None


def digital(ch, expiry, K, F, idx, D=1.0):
    """D*Q(S_T > K) = -dC/dK, as the difference quotient of two neighbouring
    strikes.

    NO model: no lognormal assumption, no implied vol. Price differences only.

    Side selection matters: below the forward the PUT side is used, because in
    a deep ITM call the time value is a tiny part of the price and the
    difference quotient drowns in noise (D-025 / D-032).

    Both sides return the SAME quantity, D*Q(S>K). The put side reaches it as
    D - D*Q(S<K) rather than 1 - D*Q(S<K); with D=1 the two coincide, which is
    why the old expression looked right (D-073).

    Three numbers come back:
      p    — from the marks. The midpoint estimate. Reported, not traded on.
      high — what it costs to BUY the spread: ask on the leg you are long,
             bid on the leg you are short.
      low  — what selling it pays. low <= p <= high, and the width between
             them is the bid-ask cost of two option legs.
    low and high are None when either leg is quoted on one side only. That is
    a refusal, not a zero: a bucket with no two-sided market has no executable
    price and must not be given one.
    """
    kind = 'P' if K < F else 'C'
    o = ch[expiry].get(kind)
    if not o:
        return None
    br = bracket(o, K)
    if not br:
        return None
    a, b = br
    w = b - a
    A, B = o[a], o[b]
    p = (A['mark'] - B['mark']) / w if kind == 'C' else D - (B['mark'] - A['mark']) / w
    if None in (A['bid'], A['ask'], B['bid'], B['ask']):
        se = low = high = None
    else:
        # Kept as a diagnostic only. It no longer enters any verdict.
        se = math.sqrt(((A['ask'] - A['bid']) / 2) ** 2 +
                       ((B['ask'] - B['bid']) / 2) ** 2) / w
        if kind == 'C':
            # Long the low strike, short the high one.
            low = (A['bid'] - B['ask']) / w
            high = (A['ask'] - B['bid']) / w
        else:
            # The put spread is SUBTRACTED, so buying it (its ask side) gives
            # the LOW digital. Getting this pair the wrong way round inverts
            # the envelope while leaving every number plausible, which is why
            # tests/test_measurement.py pins it.
            low = D - (B['ask'] - A['bid']) / w
            high = D - (B['bid'] - A['ask']) / w
    # Deribit: 0.03% of the underlying, capped at 12.5% of the option price
    fee = lambda x: min(0.0003 * idx, 0.125 * x)
    return {'p': p, 'se': se, 'low': low, 'high': high,
            'fee': (fee(A['mark']) + fee(B['mark'])) / w}


def rungs(KA, D_raw, series, currency):
    """Band arithmetic for every rung of one Kalshi bucket ladder."""
    M = [m for m in (KA.get('markets', {}).get(series) or [])
         if m.get('status') == 'active']
    if not M:
        return None
    ch, idx = chain(D_raw, currency)
    close = M[0].get('close_time', '')

    usable = sorted((v for v in ch if ch[v].get('C') and ch[v].get('P')),
                    key=expiry_ord)
    usable = [v for v in usable if expiry_ord(v)]
    if not usable:
        return None
    # Nearest option expiry that does NOT run past the Kalshi close. Not equal:
    # any remaining expiry gap biases the result in our favour, and that
    # caveat is reported rather than hidden.
    target = int(close[:4] + close[5:7] + close[8:10]) if len(close) >= 10 else None
    ok = [v for v in usable if target is None or expiry_ord(v) <= target]
    if not ok:
        return None
    expiry = ok[-1]

    # Discount first: forward() and digital() both need it.
    dis = discount(ch, expiry)
    D = dis['D'] if dis else 1.0

    F = forward(ch, expiry, idx, D)
    if not F:
        return None

    S = sorted(M, key=lambda m: (m.get('floor_strike') if m.get('floor_strike')
                                 is not None else m.get('cap_strike')) or 0)
    rows = []
    for m in S:
        kind = m.get('strike_type')
        lo = hi = None
        if kind == 'less':
            hi = round(m['cap_strike'])
        elif kind == 'greater':
            lo = round(m['floor_strike'] + .01)
        else:
            lo = round(m['floor_strike'])
            hi = round(m['cap_strike'] + .01)   # bucket boundary: D-067 fix

        label = m.get('ticker') or ('%s-%s' % (lo, hi))
        # An unbounded lower edge is a certainty, and a certainty is worth D
        # today, not 1. An unbounded upper edge is worth nothing either way.
        # Both are exact, so their envelope has zero width.
        edge_L = {'p': D, 'se': 0, 'low': D, 'high': D, 'fee': 0}
        edge_H = {'p': 0, 'se': 0, 'low': 0, 'high': 0, 'fee': 0}
        dL = digital(ch, expiry, lo, F, idx, D) if lo is not None else edge_L
        dH = digital(ch, expiry, hi, F, idx, D) if hi is not None else edge_H
        bid = float(m['yes_bid_dollars'])
        ask = float(m['yes_ask_dollars'])
        pm = (bid + ask) / 2          # reported, never traded on
        spread = ask - bid
        if not dL or not dH:
            rows.append({'label': label, 'skipped': 'outside the strike range',
                         'pm': pm, 'spread': spread})
            continue
        opt = dL['p'] - dH['p']
        se = None if (dL['se'] is None or dH['se'] is None) else \
            math.sqrt(dL['se'] ** 2 + dH['se'] ** 2)
        fee = dL['fee'] + dH['fee']

        # The bucket is LONG the lower digital and SHORT the upper one, so its
        # cheapest executable value pairs the lower leg's bid side with the
        # upper leg's ask side, and vice versa.
        if None in (dL['low'], dL['high'], dH['low'], dH['high']):
            opt_low = opt_high = edge = None
            direction = 'no two-sided option quote'
            exceeds = False
        else:
            opt_low = dL['low'] - dH['high']
            opt_high = dL['high'] - dH['low']
            # Two trades, both priced at quotes that exist right now.
            sell_pm = bid - (opt_high + fee)     # sell the prediction, buy the bucket
            buy_pm = (opt_low - fee) - ask       # buy the prediction, sell the bucket
            edge = max(sell_pm, buy_pm)
            direction = 'sell prediction' if sell_pm >= buy_pm else 'buy prediction'
            exceeds = edge > 0
        rows.append({'label': label, 'pm': pm, 'pm_bid': bid, 'pm_ask': ask,
                     'opt': opt, 'opt_low': opt_low, 'opt_high': opt_high,
                     'gap': pm - opt, 'se': se, 'fee': fee,
                     'envelope': None if opt_low is None else opt_high - opt_low,
                     'edge': edge, 'direction': direction,
                     'spread': spread, 'exceeds': exceeds})
    return {'rows': rows, 'expiry': expiry, 'F': F, 'idx': idx,
            'discount': dis, 'D': D,
            'total': sum(r['opt'] for r in rows if 'opt' in r)}


def run(stamp, stab=None):
    """Band result for both series in a single snapshot.
    stab: Stability counter — tracks how the same rung behaves across runs."""
    g = snapshot(stamp)
    out = {'stamp': stamp, 'window': g.sync_window, 'series': {}}
    for asset, series, currency in SERIES:
        try:
            h = rungs(g.kalshi, g.deribit, series, currency)
        except (KeyError, TypeError, ValueError) as e:
            out['series'][asset] = {'error': '%s: %s' % (type(e).__name__, e)}
            continue
        if not h:
            out['series'][asset] = {'error': 'no ladder'}
            continue
        measured = [r for r in h['rows'] if 'opt' in r]
        quotable = [r for r in measured if r['edge'] is not None]
        if stab is not None:
            for r in measured:
                stab.add('%s:%s' % (asset, r.get('label')), r['exceeds'])
        out['series'][asset] = {
            'rungs': len(h['rows']),
            'measured': len(measured),
            'exceeding': sum(1 for r in measured if r['exceeds']),
            'expiry': h['expiry'],
            # The ladder is exhaustive, so this sums to D, not to 1. Before
            # D-073 it summed to 1 whatever D was, which is why the check
            # never caught the convention split.
            'density_sum': round(h['total'], 4),
            'discount_factor': round(h['D'], 6),
            'discount_estimated': h['discount'] is not None,
            'discount_brackets': h['discount']['brackets'] if h['discount'] else 0,
            'discount_spread': round(h['discount']['spread'], 8) if h['discount'] else None,
            # How many rungs even have a two-sided option market. A rung
            # without one is not evidence of anything; it is a rung nobody is
            # quoting, and it used to be counted as measured because the mid
            # existed.
            'quotable': len(quotable),
            'mean_envelope': round(sum(r['envelope'] for r in quotable) / len(quotable), 4)
            if quotable else None,
            'best_edge': round(max(r['edge'] for r in quotable), 4)
            if quotable else None,
        }
    return out


def main():
    argv = sys.argv[1:]
    last = None
    if '--last' in argv:
        last = int(argv[argv.index('--last') + 1])
    machine = '--json' in argv

    every = stamps('_meta')
    if last:
        every = every[-last:]

    o = summary()
    stab = Stability()
    results = []
    for d in every:
        try:
            results.append(run(d, stab))
        except Missing as e:
            results.append({'stamp': d, 'error': str(e)})

    if machine:
        print(json.dumps({'archive': o, 'runs': results},
                         ensure_ascii=False, indent=1))
        return 0

    print('FRICTION BAND')
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days' % o)
    print('scanned: %d runs' % len(results))
    print()
    print('%-18s %6s  %-30s %-30s'
          % ('snapshot', 'window', 'BTC (edge/quotable/rungs)',
             'ETH (edge/quotable/rungs)'))
    print('-' * 90)

    tot_over = tot_measured = 0
    fallbacks = 0
    for s in results:
        if 'error' in s:
            print('%-18s  %s' % (s['stamp'], s['error']))
            continue
        cells = []
        for v in ('BTC', 'ETH'):
            d = s['series'].get(v, {})
            if 'error' in d:
                cells.append('%-30s' % d['error'][:30])
            else:
                mark = '' if d['discount_estimated'] else '!'
                if not d['discount_estimated']:
                    fallbacks += 1
                cells.append('%-30s' % ('%d/%d/%d  (D %.4f%s  env %.3f)'
                                        % (d['exceeding'], d['quotable'], d['measured'],
                                           d['discount_factor'], mark,
                                           d['mean_envelope'] or 0)))
                tot_over += d['exceeding']
                tot_measured += d['measured']
        print('%-18s %6s  %s %s' % (s['stamp'], s['window'], cells[0], cells[1]))

    print('-' * 90)
    print('TOTAL: %d / %d rung-observations show a positive edge at quoted prices'
          % (tot_over, tot_measured))
    if tot_measured:
        print('       %.1f%% — this is a ratio, NOT a count of opportunities.' %
              (100.0 * tot_over / tot_measured))
    if fallbacks:
        print('WARNING: %d series-observations could not estimate D and fell back' % fallbacks)
        print('         to D=1 (marked !). Their sum column will read ~1.000 and')
        print('         their two digital sides are on different footings.')
    stab.report('STABILITY — Kalshi bucket rungs')
    print()
    print('Reading note: a rung counts when ONE of the two trades leaves')
    print('something after the option fees, with every leg priced at a quote')
    print('that exists: prediction sold at its bid against the bucket bought')
    print('at its ask side, or the mirror of that. No mid is used anywhere in')
    print('the verdict, and 1.96*SE no longer appears in it.')
    print()
    print('STILL NOT IN THIS NUMBER, and each one only makes it worse:')
    print('  - Kalshi\'s own trading and settlement fees. UNKNOWN, not zero.')
    print('  - Margin on the option legs, which is posted for months.')
    print('  - The expiry gap between the two contracts (D-075: 6d 21h).')
    print('  - BRTI against the Deribit index (D-075: size UNKNOWN).')
    print('So a positive edge here is a NECESSARY condition for a trade and')
    print('nothing more. The option column is a discounted state price')
    print('D*Q(lo<S<hi), not a probability, and the sum column is the')
    print('exhaustive ladder total, which should sit near D rather than 1.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
