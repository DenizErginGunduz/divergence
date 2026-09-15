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

from archive import snapshot, stamps, summary, Missing
from measure_band import (SERIES, chain, discount, forward,
                          expiry_instant, iso_instant, EXPIRY)

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


def neighbours(ch, close_at):
    """The two usable expiries nearest the Kalshi close, nearest first.

    Compared as INSTANTS, not dates. A Kalshi intraday market closing 14:00 UTC
    and a Deribit expiry at 08:00 the same day are not the same moment, and the
    date comparison this replaced called the later one "before".

    The two do not always straddle. Deribit's daily options settle 08:00 UTC
    and are delisted at once, so by the time a snapshot reads an intraday
    market that closes the same afternoon, that morning's expiry is gone and
    BOTH neighbours fall after the close (D-082). The caller is told which,
    because a pair that straddles is a band and a pair that does not is a
    one-sided bound, and they do not mean the same thing.
    """
    dated = sorted((expiry_instant(v), v) for v in ch
                   if ch[v].get('C') and ch[v].get('P') and expiry_instant(v))
    if not dated:
        return []
    dated.sort(key=lambda p: abs((p[0] - close_at).total_seconds()))
    out = []
    for ts, v in dated[:2]:
        hours = (ts - close_at).total_seconds() / 3600.0
        out.append({'expiry': v, 'hours': hours,
                    'side': 'after' if hours > 0 else 'before'})
    return out


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
        close_at = iso_instant(M[0].get('close_time', ''))
        if close_at is None:
            continue
        near = neighbours(ch, close_at)
        if not near:
            continue

        # Each chain carries its own discount and its own forward. Borrowing
        # the near chain's would import the very error being measured.
        for n in near:
            dis = discount(ch, n['expiry'])
            n['D'] = dis['D'] if dis else 1.0
            n['F'] = forward(ch, n['expiry'], idx, n['D'])
        near = [n for n in near if n['F']]
        if not near:
            continue
        first = near[0]

        for K, label, kind, bid in thresholds(M):
            # The grid test runs on the NEAREST chain, which is the one the
            # friction band actually prices against.
            grid = []
            for s in SKIPS:
                d = digital_at(ch, first['expiry'], K, first['F'], first['D'], s)
                if d:
                    d['v'] = rung_value(d['p'], first['D'], kind)
                grid.append(d)
            if not grid[0]:
                continue
            others = []
            for n in near:
                d = digital_at(ch, n['expiry'], K, n['F'], n['D'])
                if not d:
                    continue
                others.append({'expiry': n['expiry'], 'hours': n['hours'],
                               'side': n['side'],
                               'v': rung_value(d['p'], n['D'], kind)})
            rows.append({
                'asset': asset, 'label': label, 'kind': kind, 'bid': bid,
                'K': K, 'grid': grid, 'chains': others,
                'straddles': len(set(o['side'] for o in others)) == 2,
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
    print('2. EXPIRY — the two nearest chains, and which side they fall on')
    print()
    print('%-18s %-16s %8s %9s %9s %10s  %s' %
          ('', 'rung', 'pred bid', 'near', 'far', 'hours', 'verdict'))
    print('-' * 100)

    def judge(r):
        """Two cases, and they are not the same statement.

        STRADDLES — one chain each side of the close. The settlement-date value
        lies between them, so a bid above both cannot be explained by the gap.

        ONE-SIDED — both chains expire after the close, which is every intraday
        ladder (D-082). A later expiry OVERSTATES an upside tail, so the
        NEAREST chain is the binding upper bound and the far one adds nothing.
        A bid above the nearest is evidence; a bid below it proves nothing,
        because the true value is lower still.
        """
        vals = [o['v'] for o in r['chains']]
        if not vals:
            return 'no chain'
        if r['straddles']:
            lo, hi = min(vals), max(vals)
            if r['bid'] > hi:
                return 'above BOTH'
            if r['bid'] < lo:
                return 'below both'
            return 'inside the band'
        # One-sided. Compare against the nearest chain only.
        near_v = r['chains'][0]['v']
        side = r['chains'][0]['side']
        if side == 'after':
            return 'above the bound' if r['bid'] > near_v else 'under the bound'
        return 'above the nearest' if r['bid'] > near_v else 'below the nearest'

    tally = {}
    latest = {}
    for r in all_rows:
        v = judge(r)
        tally[v] = tally.get(v, 0) + 1
        latest[(r['asset'], r['label'])] = r
    for r in latest.values():
        ch = r['chains']
        near_v = ch[0]['v'] if ch else None
        far_v = ch[1]['v'] if len(ch) > 1 else None
        print('%-18s %-16s %8.4f %9s %9s %10s  %s' % (
            r['asset'][:18], r['label'][:16], r['bid'],
            '%.5f' % near_v if near_v is not None else '-',
            '%.5f' % far_v if far_v is not None else '-',
            '%+.0f/%+.0f' % (ch[0]['hours'], ch[1]['hours'])
            if len(ch) > 1 else ('%+.0f' % ch[0]['hours'] if ch else '-'),
            judge(r)))
    if tally:
        print('-' * 100)
        print('across all %d observations: %s'
              % (sum(tally.values()),
                 ', '.join('%d %s' % (n, k) for k, n in
                           sorted(tally.items(), key=lambda kv: -kv[1]))))
    print()
    print('Reading note: the hours column is SIGNED and it decides how to read')
    print('the row. Negative means the option expires BEFORE the Kalshi close,')
    print('so for an upside tail it understates and flatters the comparison;')
    print('positive means it expires later and overstates, which does not.')
    print()
    print('Year-end ladders straddle: -165h and +2000h, so the settlement-date')
    print('value sits between the two and "inside the band" means the rung')
    print('cannot be separated from the gap at all.')
    print()
    print('Intraday ladders never straddle. Deribit delists a daily option the')
    print('moment it settles, so both neighbours are AFTER the close and both')
    print('overstate. The nearest is the binding bound: "above the bound" is')
    print('real evidence, "under the bound" is no evidence either way.')
    print()
    print('No interpolation is done anywhere. That would need a model of how a')
    print('tail probability grows with maturity, and this measurement has none.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
