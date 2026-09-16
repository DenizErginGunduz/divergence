#!/usr/bin/env python3
"""Exhaustiveness constraint — what happens when the bucket boundary is wrong?

THE CONSTRAINT
If a bucket ladder partitions the whole outcome space, the bucket prices MUST
sum to the discount factor D. Buying every bucket buys a dollar at expiry with
certainty, and a certain dollar at expiry is worth D today. That is not a
preference, it is arithmetic. A sum that departs from D says the computation is
wrong — it does not say which bucket is wrong, but it does say one of them is.

WHY IT SAYS D AND NOT 1 (D-073)
It used to say 1, and that made the check partly blind. The call side of the
digital returns D*Q(S>K); the put side used to return 1 - D*Q(S<K), which is
(1-D) + D*Q(S>K). A ladder built from a mixture of the two summed to
D*1 + (1-D) = 1 for ANY D, so the constraint was satisfied by a computation
that was internally inconsistent. Once both sides return D*Q(S>K) the sum has
to land on D, and a convention slip finally shows up here.

The departure below is therefore reported on total/D, which is dimensionless
and comparable across chains with different maturities.

WHY IT MATTERS
Most of the errors caught in this project were caught by constraints, not by
numbers. In the bucket-boundary bug every individual digital looked plausible;
only the rule that the total must be exhaustive made the error visible.

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
counted twice and the total runs above the constraint.

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
from measure_band import (SERIES, chain, forward, digital, discount,
                          expiry_ord, event_ladder, ladder_shape)

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


def ladder_sum(KA, D_raw, series, currency, rule):
    """Sum of the bucket prices of one ladder under the given rule.

    One event only, and only if the ladder is a partition (D-105). A
    cumulative ladder (every rung P(S > K) at its own threshold) has
    overlapping rungs and no density; an incomplete one (the archive holds a
    ladder with a hole in it) has a sum that says nothing about the
    computation. Both come back with the shape named and no ratio, instead of
    a number that looks like the constraint and is not one.
    """
    M, events = event_ladder(KA, series)
    if not M:
        return None
    shape, breaks = ladder_shape(M)
    if shape != 'exhaustive':
        return {'ladder': shape, 'breaks': breaks, 'total': None, 'ratio': None,
                'buckets': len(M), 'events': events, 'D': None,
                'estimated': False}
    ch, idx = chain(D_raw, currency)
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

    dis = discount(ch, expiry)
    D = dis['D'] if dis else 1.0

    F = forward(ch, expiry, idx, D)
    if not F:
        return None

    t = 0.0
    n = 0
    for m in M:
        lo, hi = bounds(m, rule)
        # An unbounded lower edge is certainty, worth D today rather than 1.
        dL = digital(ch, expiry, lo, F, idx, D) if lo is not None else {'dsp': D}
        dH = digital(ch, expiry, hi, F, idx, D) if hi is not None else {'dsp': 0}
        if not dL or not dH:
            continue
        t += dL['dsp'] - dH['dsp']
        n += 1
    return {'ladder': 'exhaustive', 'breaks': 0, 'total': t, 'buckets': n,
            'events': events, 'D': D, 'estimated': dis is not None, 'ratio': t / D}


def main():
    argv = sys.argv[1:]
    last = int(argv[argv.index('--last') + 1]) if '--last' in argv else None
    every = stamps('_meta')
    if last:
        every = every[-last:]

    o = summary()
    print("EXHAUSTIVENESS CONSTRAINT — boundary rule and departure from D")
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days' % o)
    print()
    print('%-18s %-5s %9s %10s %10s %10s'
          % ('snapshot', 'series', 'D', 'corrected', 'naive_a', 'naive_b'))
    print('-' * 72)

    pooled = {k: [] for k in RULES}
    fallbacks = 0
    set_aside = {'cumulative': 0, 'incomplete': 0}
    for stamp in every:
        try:
            g = snapshot(stamp)
            KA, D_raw = g.kalshi, g.deribit
        except Missing:
            continue
        for asset, series, currency in SERIES:
            row = []
            shown = None
            for rule in RULES:
                try:
                    r = ladder_sum(KA, D_raw, series, currency, rule)
                except (KeyError, TypeError, ValueError):
                    r = None
                if r and r['ratio'] is None:
                    # Not a partition: named once, never summed (D-105).
                    if rule == RULES[0]:
                        set_aside[r['ladder']] += 1
                        print('%-18s %-5s %9s %10s' % (stamp, asset, '-', r['ladder']
                              + (' (%d breaks)' % r['breaks'] if r['breaks'] else '')))
                    r = None
                if r:
                    # Pool the RATIO, not the raw total: totals from chains with
                    # different maturities are not comparable, ratios are.
                    row.append(r['ratio'])
                    pooled[rule].append(r['ratio'])
                    if shown is None:
                        shown = '%.4f%s' % (r['D'], '' if r['estimated'] else '!')
                        if not r['estimated']:
                            fallbacks += 1
                else:
                    row.append(None)
            if any(x is not None for x in row):
                print('%-18s %-5s %9s %10s %10s %10s' % (
                    stamp, asset, shown or '-',
                    *['%.4f' % x if x is not None else '-' for x in row]))

    print('-' * 72)
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
        print('%-14s %8s departure from D: %+.1f%%'
              % ('', '', 100.0 * (mean - 1.0)))

    if any(set_aside.values()):
        print()
        print('Set aside, not summed (D-105): %d cumulative ladders (rungs overlap,'
              % set_aside['cumulative'])
        print('no density) and %d incomplete ones (a hole in the archived ladder,'
              % set_aside['incomplete'])
        print('so the sum says nothing about the computation).')
    if fallbacks:
        print()
        print('WARNING: %d ladders could not estimate D and fell back to D=1' % fallbacks)
        print('         (marked !). For those the ratio column is the old,')
        print('         convention-blind total and should not be compared')
        print('         against the rest.')

    print()
    print("Reading note: the three columns are total/D. The further from 1.0000,")
    print("the more wrong that boundary rule is. The constraint does not say")
    print("which bucket is broken — only THAT something is. That is exactly what")
    print("caught the bug: the digitals looked flawless one by one.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
