#!/usr/bin/env python3
"""Sensitivity — how much of the number is the grid, and how much is the date?

Two approximations sit under every digital this project produces, and neither
has been measured. Both are reported here as a RANGE rather than a correction,
because the honest output of a sensitivity test is a band, not a better point.

1. THE STRIKE GRID
   The digital is a finite difference between two neighbouring strikes. That
   quotient is not the derivative at K; it is the average of the survival
   function over the bracket. Deribit's strikes are 5,000 apart on BTC, so the
   bracket is wide and the averaging is real.

   Measured by recomputing each digital on deliberately WIDER brackets —
   skipping one strike on each side, then two. If the answer barely moves, the
   grid is not driving it. If it moves a lot, the tail numbers are a statement
   about Deribit's strike spacing as much as about the market.

2. THE EXPIRY DATE
   The Kalshi ladders settle 2027-01-01 05:00 UTC. Deribit has no expiry on
   that date. measure_band picks the nearest expiry NOT PAST the close, which
   is 25DEC26 — seven days early — and the docstring has always admitted that
   this biases the comparison in our favour, because a tail probability grows
   with maturity.

   Here both bracketing expiries are computed: the one before the close and the
   one after. For a tail whose probability is monotone in maturity the true
   value for the settlement date lies between them. That turns "we used the
   early one" into a bound, and the bound is what decides whether the three
   surviving rungs (D-078) survive the expiry gap at all.

WHAT THIS SCRIPT DOES NOT DO
It does not choose. It does not interpolate between expiries, which would need
a model of how the probability grows with maturity, and a model is the thing
this measurement has avoided from the start (D-025). It prints both ends.

Usage:
    python scripts/measure_sensitivity.py
    python scripts/measure_sensitivity.py --last 5
"""
import sys
from datetime import date

from archive import snapshot, stamps, summary, Missing
from measure_band import (SERIES, chain, discount, forward, expiry_ord, MONTH,
                          EXPIRY)

# Skip levels tried on each side of the threshold. 0 is what production uses.
SKIPS = (0, 1, 2)


def wide_bracket(o, K, skip=0):
    """The (skip+1)-th strike below and above K. skip=0 is the tight bracket."""
    ks = sorted(o)
    below = [k for k in ks if k < K]
    above = [k for k in ks if k > K]
    if len(below) <= skip or len(above) <= skip:
        return None
    return below[-1 - skip], above[skip]


def digital_at(ch, expiry, K, F, D, skip=0):
    """Same arithmetic as measure_band.digital, on a chosen bracket width.

    Marks only: this is about the grid and the date, not about the spread, and
    mixing the bid-ask envelope in here would hide the effect being measured.
    """
    kind = 'P' if K < F else 'C'
    o = (ch.get(expiry) or {}).get(kind)
    if not o:
        return None
    br = wide_bracket(o, K, skip)
    if not br:
        return None
    a, b = br
    w = b - a
    if w <= 0:
        return None
    p = ((o[a]['mark'] - o[b]['mark']) / w if kind == 'C'
         else D - (o[b]['mark'] - o[a]['mark']) / w)
    return {'p': p, 'width': w, 'low': a, 'high': b, 'side': kind}


def to_date(ord_yyyymmdd):
    s = str(ord_yyyymmdd)
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def bracketing(ch, close_ord):
    """The usable expiry before the Kalshi close, and the one after it."""
    usable = [v for v in ch
              if ch[v].get('C') and ch[v].get('P') and expiry_ord(v)]
    usable.sort(key=expiry_ord)
    before = [v for v in usable if expiry_ord(v) <= close_ord]
    after = [v for v in usable if expiry_ord(v) > close_ord]
    return (before[-1] if before else None, after[0] if after else None)


def thresholds(M):
    """One threshold per rung, with a readable label. Only the single-sided
    rungs — 'above X' and 'below X' — because a between-bucket is a difference
    of two digitals and its sensitivity is the sum of two effects, which would
    read as one."""
    out = []
    for m in M:
        kind = m.get('strike_type')
        if kind == 'greater':
            out.append((round(m['floor_strike'] + .01), 'above %s' % m['floor_strike'],
                        kind, float(m['yes_bid_dollars'])))
        elif kind == 'less':
            out.append((round(m['cap_strike']), 'below %s' % m['cap_strike'],
                        kind, float(m['yes_bid_dollars'])))
    return out


def rung_value(p, D, kind):
    """The digital is always D*Q(S > K). A 'below X' rung pays on the OTHER
    side, so its value is D - that.

    Getting this wrong is not subtle once you look: the first version of this
    script compared a 2.8-cent 'ETH below $1,000' bid against 0.97657 and
    called it "below both". The number was the chance of being ABOVE.
    """
    if p is None:
        return None
    return p if kind == 'greater' else D - p


def run(stamp):
    g = snapshot(stamp)
    KA, D_raw = g.kalshi, g.deribit
    rows = []
    for asset, series, currency in SERIES:
        M = [m for m in (KA.get('markets', {}).get(series) or [])
             if m.get('status') == 'active']
        if not M:
            continue
        ch, idx = chain(D_raw, currency)
        close = M[0].get('close_time', '')
        if len(close) < 10:
            continue
        close_ord = int(close[:4] + close[5:7] + close[8:10])
        early, late = bracketing(ch, close_ord)
        if not early:
            continue

        dis = discount(ch, early)
        D = dis['D'] if dis else 1.0
        F = forward(ch, early, idx, D)
        if not F:
            continue
        # The late chain has its own discount and its own forward; using the
        # early one's would import a seven-day error into the very number
        # meant to measure a seven-day error.
        D_late = F_late = None
        if late:
            dl = discount(ch, late)
            D_late = dl['D'] if dl else 1.0
            F_late = forward(ch, late, idx, D_late)

        for K, label, kind, bid in thresholds(M):
            grid = []
            for s in SKIPS:
                d = digital_at(ch, early, K, F, D, s)
                if d:
                    d['v'] = rung_value(d['p'], D, kind)
                grid.append(d)
            if not grid[0]:
                continue
            late_d = (digital_at(ch, late, K, F_late, D_late)
                      if (late and F_late) else None)
            late_v = (rung_value(late_d['p'], D_late, kind) if late_d else None)
            rows.append({
                'asset': asset, 'label': label, 'kind': kind, 'bid': bid,
                'late_v': late_v,
                'K': K, 'early': early, 'late': late,
                'early_days': (to_date(close_ord) - to_date(expiry_ord(early))).days,
                'late_days': ((to_date(expiry_ord(late)) - to_date(close_ord)).days
                              if late else None),
                'grid': grid,
            })
    return rows


def main():
    argv = sys.argv[1:]
    last = int(argv[argv.index('--last') + 1]) if '--last' in argv else None
    every = stamps('_meta')
    if last:
        every = every[-last:]
    o = summary()

    all_rows = []
    for stamp in every:
        try:
            all_rows.extend(run(stamp))
        except (Missing, KeyError, TypeError, ValueError):
            continue

    print('SENSITIVITY — the strike grid and the expiry date')
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days' % o)
    print('rung-observations: %d' % len(all_rows))
    print()

    # ---- 1. the grid -----------------------------------------------------
    print('1. STRIKE GRID — the same digital on wider brackets')
    print()
    print('%-5s %-18s %10s %10s %10s %9s' %
          ('', 'rung', 'tight', 'skip 1', 'skip 2', 'spread'))
    print('-' * 68)
    grid_spreads = []
    latest = {}
    for r in all_rows:
        vals = [d['v'] if d else None for d in r['grid']]
        have = [v for v in vals if v is not None]
        if len(have) > 1 and have[0]:
            grid_spreads.append((max(have) - min(have)) / abs(have[0]))
        # Keep the LAST observation of each rung. stamps() is chronological,
        # so this is the newest snapshot rather than the oldest.
        latest[(r['asset'], r['label'])] = r
    for r in latest.values():
        vals = [d['v'] if d else None for d in r['grid']]
        have = [v for v in vals if v is not None]
        print('%-5s %-18s %10s %10s %10s %9s' % (
            r['asset'], r['label'][:18],
            *['%.5f' % v if v is not None else '-' for v in vals],
            '%.1f%%' % (100.0 * (max(have) - min(have)) / abs(have[0]))
            if len(have) > 1 and have[0] else '-'))
    if grid_spreads:
        grid_spreads.sort()
        print('-' * 68)
        print('relative spread across bracket widths, all observations:')
        print('  median %.2f%%   p90 %.2f%%   worst %.2f%%' % (
            100 * grid_spreads[len(grid_spreads) // 2],
            100 * grid_spreads[int(.9 * (len(grid_spreads) - 1))],
            100 * grid_spreads[-1]))
        print('  A digital that moves this much when the bracket is widened is')
        print('  partly a statement about Deribit strike spacing.')
    print()

    # ---- 2. the expiry ---------------------------------------------------
    print('2. EXPIRY BAND — both chains that bracket the Kalshi close')
    print()
    print('%-5s %-18s %8s %9s %9s %9s  %s' %
          ('', 'rung', 'pred bid', 'early', 'late', 'band', 'verdict'))
    print('-' * 86)
    def judge(r):
        """A 'below X' rung loses value as maturity grows while an 'above X'
        rung gains it, so the band is not always early-then-late. Order the
        two ends and compare against the pair."""
        early_v = r['grid'][0]['v']
        late_v = r['late_v']
        if late_v is None:
            return None, None, 'no later chain'
        lo, hi = min(early_v, late_v), max(early_v, late_v)
        if r['bid'] > hi:
            return lo, hi, 'above BOTH'
        if r['bid'] < lo:
            return lo, hi, 'below both'
        return lo, hi, 'inside the band'

    survive = clipped = nolate = below = 0
    latest = {}
    for r in all_rows:
        _lo, _hi, v = judge(r)
        if v == 'above BOTH':
            survive += 1
        elif v == 'inside the band':
            clipped += 1
        elif v == 'below both':
            below += 1
        else:
            nolate += 1
        latest[(r['asset'], r['label'])] = r
    for r in latest.values():
        early_v = r['grid'][0]['v']
        late_v = r['late_v']
        _lo, _hi, verdict = judge(r)
        print('%-5s %-18s %8.4f %9.5f %9s %9s  %s' % (
            r['asset'], r['label'][:18], r['bid'], early_v,
            '%.5f' % late_v if late_v is not None else '-',
            '%.5f' % abs(late_v - early_v) if late_v is not None else '-',
            verdict))
    total = survive + clipped + nolate + below
    if total:
        print('-' * 86)
        print('across all %d observations: %d above both, %d inside the band, '
              '%d below both, %d with no later chain'
              % (total, survive, clipped, below, nolate))
    print()
    print('Reading note: the early chain expires BEFORE the Kalshi contract')
    print('settles and the late one after it, so for a tail whose probability')
    print('grows with maturity the settlement-date value sits between them.')
    print('"above BOTH" means the prediction price exceeds the option-implied')
    print('value at either end, and the seven-day gap cannot explain it.')
    print('"inside the band" means it cannot be separated from the gap, and')
    print('the rung should not be reported as a divergence at all.')
    print('No interpolation is done: that would need a model of how the')
    print('probability grows with maturity, and this measurement has no model.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
