#!/usr/bin/env python3
"""Exhaustiveness constraint — what happens when the bucket boundary is wrong?

THE CONSTRAINT
If a bucket ladder partitions the whole outcome space, the bucket
probabilities MUST sum to 1. That is not a preference, it is arithmetic. So a
sum that departs from 1 says the computation is wrong — it does not say which
bucket is wrong, but it does say one of them is.

WHY IT MATTERS
Most of the errors caught in this project were caught by constraints, not by
numbers. In the bucket-boundary bug every individual digital looked plausible;
only the rule that the total must be 1 made the error visible.

WHAT THIS SCRIPT DOES
It computes the same data under three different boundary rules and reports each
total. It does not assert which rule is right — the totals say so.

  corrected : hi = round(cap + 0.01)     <- the one in use today
  naive_a   : hi = round(cap)            <- no epsilon at all
  naive_b   : hi = round(cap) + 0.01     <- epsilon OUTSIDE the rounding

Why the difference matters: with cap 24999.99, round(24999.99 + 0.01) = 25000,
but round(24999.99) + 0.01 = 25000.01. The next bucket's floor is 25000. The
digital picks bracketing strikes by strict inequality, so 25000.01 and 25000
can select DIFFERENT strike pairs for the same boundary. One region then gets
counted twice and the total runs above 1.

HONESTY NOTE
The historical shape of the bug was reconstructed from a summary. This script
does not claim "the total was such and such"; it measures all three rules and
shows the result. Whatever the measurement says is what gets written.

Usage:
    python scripts/measure_exhaustive.py
    python scripts/measure_exhaustive.py --last 5
"""
import sys

from archive import snapshot, stamps, summary, Missing
from measure_band import SERIES, chain, forward, digital, expiry_ord

RULES = ('corrected', 'naive_a', 'naive_b')


def bounds(m, rule):
    """Lower/upper threshold of a Kalshi bucket under the chosen rule."""
    kind = m.get('strike_type')
    if kind == 'less':
        cap = m['cap_strike']
        if rule == 'corrected':
            return None, round(cap)
        if rule == 'naive_a':
            return None, round(cap)
        return None, round(cap)
    if kind == 'greater':
        fl = m['floor_strike']
        if rule == 'corrected':
            return round(fl + .01), None
        if rule == 'naive_a':
            return round(fl), None
        return round(fl) + .01, None
    fl, cap = m['floor_strike'], m['cap_strike']
    if rule == 'corrected':
        return round(fl), round(cap + .01)
    if rule == 'naive_a':
        return round(fl), round(cap)
    return round(fl), round(cap) + .01


def ladder_sum(KA, D, series, currency, rule):
    """Sum of the bucket probabilities of one ladder under the given rule."""
    M = [m for m in (KA.get('markets', {}).get(series) or [])
         if m.get('status') == 'active']
    if not M:
        return None
    ch, idx = chain(D, currency)
    close = M[0].get('close_time', '')
    usable = [v for v in ch if ch[v].get('C') and ch[v].get('P') and expiry_ord(v)]
    if not usable:
        return None
    usable.sort(key=expiry_ord)
    target = int(close[:4] + close[5:7] + close[8:10]) if len(close) >= 10 else None
    ok = [v for v in usable if target is None or expiry_ord(v) <= target]
    if not ok:
        return None
    expiry = ok[-1]
    F = forward(ch, expiry, idx)
    if not F:
        return None

    t = 0.0
    n = 0
    for m in M:
        lo, hi = bounds(m, rule)
        dL = digital(ch, expiry, lo, F, idx) if lo is not None else {'p': 1}
        dH = digital(ch, expiry, hi, F, idx) if hi is not None else {'p': 0}
        if not dL or not dH:
            continue
        t += dL['p'] - dH['p']
        n += 1
    return {'total': t, 'buckets': n}


def main():
    argv = sys.argv[1:]
    last = int(argv[argv.index('--last') + 1]) if '--last' in argv else None
    every = stamps('_meta')
    if last:
        every = every[-last:]

    o = summary()
    print("EXHAUSTIVENESS CONSTRAINT — boundary rule and departure from 1")
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days' % o)
    print()
    print('%-18s %-5s %10s %10s %10s'
          % ('snapshot', 'series', 'corrected', 'naive_a', 'naive_b'))
    print('-' * 60)

    pooled = {k: [] for k in RULES}
    for stamp in every:
        try:
            g = snapshot(stamp)
            KA, D = g.kalshi, g.deribit
        except Missing:
            continue
        for asset, series, currency in SERIES:
            row = []
            for rule in RULES:
                try:
                    r = ladder_sum(KA, D, series, currency, rule)
                except (KeyError, TypeError, ValueError):
                    r = None
                if r:
                    row.append(r['total'])
                    pooled[rule].append(r['total'])
                else:
                    row.append(None)
            if any(x is not None for x in row):
                print('%-18s %-5s %10s %10s %10s' % (
                    stamp, asset,
                    *['%.4f' % x if x is not None else '-' for x in row]))

    print('-' * 60)
    print()
    print('%-14s %8s %10s %10s %10s'
          % ('rule', 'measured', 'mean', 'min', 'max'))
    for rule in RULES:
        v = pooled[rule]
        if not v:
            print('%-14s %8s' % (rule, 'none'))
            continue
        mean = sum(v) / len(v)
        print('%-14s %8d %10.4f %10.4f %10.4f'
              % (rule, len(v), mean, min(v), max(v)))
        print('%-14s %8s departure from 1: %+.1f%%'
              % ('', '', 100.0 * (mean - 1.0)))

    print()
    print("Reading note: the further the total is from 1, the more wrong that")
    print("boundary rule is. The constraint does not say which bucket is broken")
    print("— only THAT something is. That is exactly what caught the bug: the")
    print("digitals looked flawless one by one.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
