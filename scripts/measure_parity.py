#!/usr/bin/env python3
"""Put-call cross-check — does the converted chain behave like a USD present value?

THE QUESTION THIS ANSWERS
Deribit BTC and ETH options are inverse: premium and settlement are in the
underlying. Every measurement in this project converts to USD by multiplying by
the index. Nobody had ever checked what that conversion actually yields. The fear
was that it produces a share-measure (BTC-numeraire) quantity rather than a USD
risk-neutral one — a reweighting by S_T that is smallest at the money and largest
in the tails, which is exactly where every finding in this project lives.

The exhaustiveness check cannot detect that error: a density under the wrong
measure still integrates to 1.

THE TEST
At a strike K the same digital can be built two ways from the same chain:

    call side:  [C(a) - C(b)] / (b - a)        ->  -dC/dK  =  D * Q(S > K)
    put side:   1 - [P(b) - P(a)] / (b - a)    ->  1 - D * Q(S < K)
                                                =  (1 - D) + D * Q(S > K)

So under a sound USD present-value interpretation the residual

    residual(K) = put_side(K) - call_side(K) = 1 - D

is a CONSTANT, independent of K, equal to one minus the discount factor.

That gives two falsifiable predictions at once:

  1. FLATNESS. If the residual varies with K — in particular if it drifts with
     moneyness — the two sides are not measuring the same object and the
     numeraire concern is real.
  2. ECONOMIC SENSE. The implied rate r = -ln(D) / T should be a plausible USD
     rate, and should be roughly consistent across expiries at one snapshot.

A constant residual with a sensible term structure is strong evidence that
mark x index behaves like a USD present value satisfying put-call parity. It is
evidence, not proof: it cannot rule out an error that happens to be affine in K.

WHAT IT ALSO EXPOSES
The two sides use INCONSISTENT discount conventions. The call side returns
D*Q(S>K); the put side returns (1-D) + D*Q(S>K). Wherever the pipeline mixes
them — a bucket whose lower bound sits below the forward and upper bound above
it — the result is inflated by exactly (1 - D). The sum-to-1 check is blind to
this too: the inflation on the straddling bucket exactly offsets the discounting
of all the others, so the total comes to 1 regardless of D.

Evaluation happens at the MIDPOINT of each consecutive strike pair, so the call
and put sides are guaranteed to use the identical bracket. Strikes listed on only
one side are skipped and counted.

Usage:
    python scripts/measure_parity.py
    python scripts/measure_parity.py --last 5
    python scripts/measure_parity.py --json
"""
import datetime
import json
import math
import sys

from archive import snapshot, stamps, summary, Missing
import measure_band

YEAR = 365.0
EXPIRY_HOUR = 8          # Deribit expiries settle at 08:00 UTC

# Only strike intervals whose midpoint sits in this moneyness band are used for
# the headline statistic. The wings are reported separately rather than dropped,
# because the wings are where a numeraire error would show up first.
CORE_LOW, CORE_HIGH = 0.70, 1.40


def expiry_utc(label):
    """'25DEC26' -> datetime(2026, 12, 25, 8, 0, tzinfo=utc)"""
    m = measure_band.EXPIRY.match(label)
    if not m:
        return None
    return datetime.datetime(2000 + int(m.group(3)), measure_band.MONTH[m.group(2)],
                             int(m.group(1)), EXPIRY_HOUR, 0,
                             tzinfo=datetime.timezone.utc)


def stamp_utc(stamp):
    """'2026-09-14T1435Z' -> datetime"""
    return datetime.datetime(int(stamp[0:4]), int(stamp[5:7]), int(stamp[8:10]),
                             int(stamp[11:13]), int(stamp[13:15]),
                             tzinfo=datetime.timezone.utc)


def residuals(ch, expiry, F):
    """One residual per consecutive strike interval that exists on both sides."""
    C, P = ch[expiry].get('C') or {}, ch[expiry].get('P') or {}
    shared = sorted(set(C) & set(P))
    out, only_one_side = [], (len(set(C) ^ set(P)))
    for a, b in zip(shared, shared[1:]):
        w = b - a
        if w <= 0:
            continue
        call = (C[a]['mark'] - C[b]['mark']) / w
        put = 1.0 - (P[b]['mark'] - P[a]['mark']) / w
        mid = (a + b) / 2.0
        out.append({'K': mid, 'moneyness': mid / F if F else None,
                    'call_side': call, 'put_side': put, 'residual': put - call})
    return out, only_one_side


def median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def slope(rows):
    """Least-squares slope of residual against log-moneyness.

    Under the USD present-value reading this is zero. A numeraire error would
    show up here first, because the reweighting is monotone in S_T.
    """
    pts = [(math.log(r['moneyness']), r['residual'])
           for r in rows if r['moneyness'] and r['moneyness'] > 0]
    n = len(pts)
    if n < 3:
        return None
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    num = sum((p[0] - mx) * (p[1] - my) for p in pts)
    den = sum((p[0] - mx) ** 2 for p in pts)
    return (num / den) if den else None


def run(stamp):
    g = snapshot(stamp)
    D = g.deribit
    t0 = stamp_utc(stamp)
    out = []
    for ccy in ('BTC', 'ETH'):
        try:
            ch, idx = measure_band.chain(D, ccy)
        except (KeyError, TypeError):
            continue
        for expiry in sorted(ch, key=lambda e: measure_band.expiry_ord(e) or 0):
            if not (ch[expiry].get('C') and ch[expiry].get('P')):
                continue
            exp_dt = expiry_utc(expiry)
            if not exp_dt:
                continue
            T = (exp_dt - t0).total_seconds() / 86400.0 / YEAR
            if T <= 0:
                continue
            F = measure_band.forward(ch, expiry, idx)
            if not F:
                continue
            rows, one_side = residuals(ch, expiry, F)
            core = [r for r in rows
                    if r['moneyness'] and CORE_LOW <= r['moneyness'] <= CORE_HIGH]
            wing = [r for r in rows if r not in core]
            if len(core) < 3:
                continue
            res = [r['residual'] for r in core]
            med = median(res)
            # 1 - D = median residual  ->  D = 1 - med  ->  r = -ln(D)/T
            disc = 1.0 - med
            rate = (-math.log(disc) / T) if 0 < disc < 1 else None
            out.append({
                'currency': ccy, 'expiry': expiry, 'days': round(T * YEAR, 2),
                'forward': round(F, 2), 'index': round(idx, 2),
                'intervals_core': len(core), 'intervals_wing': len(wing),
                'strikes_one_side_only': one_side,
                'residual_median': round(med, 6),
                'residual_min': round(min(res), 6),
                'residual_max': round(max(res), 6),
                'residual_spread': round(max(res) - min(res), 6),
                'slope_vs_log_moneyness': (round(slope(core), 6)
                                           if slope(core) is not None else None),
                'implied_discount': round(disc, 6),
                'implied_rate_pct': (round(100 * rate, 3) if rate is not None else None),
                'wing_residual_median': (round(median([r['residual'] for r in wing]), 6)
                                         if wing else None),
            })
    return {'stamp': stamp, 'chains': out}


def main():
    argv = sys.argv[1:]
    last = int(argv[argv.index('--last') + 1]) if '--last' in argv else None
    machine = '--json' in argv

    every = stamps('_meta')
    if last:
        every = every[-last:]

    results = []
    for d in every:
        try:
            results.append(run(d))
        except Missing:
            continue

    if machine:
        print(json.dumps({'archive': summary(), 'runs': results},
                         ensure_ascii=False, indent=1))
        return 0

    o = summary()
    print('PUT-CALL CROSS-CHECK')
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days' % o)
    print('scanned: %d runs' % len(results))
    print()
    print('The residual should be a constant equal to 1 - D. A slope against')
    print('log-moneyness that is materially non-zero is the numeraire warning.')
    print()
    print('%-18s %-4s %-9s %6s %5s %10s %10s %9s %8s'
          % ('snapshot', 'ccy', 'expiry', 'days', 'n', 'residual', 'spread',
             'slope', 'rate %'))
    print('-' * 96)

    all_rates, all_slopes, all_spreads = [], [], []
    for s in results:
        for c in s['chains']:
            print('%-18s %-4s %-9s %6.1f %5d %10.6f %10.6f %9s %8s'
                  % (s['stamp'], c['currency'], c['expiry'], c['days'],
                     c['intervals_core'], c['residual_median'], c['residual_spread'],
                     ('%.5f' % c['slope_vs_log_moneyness'])
                     if c['slope_vs_log_moneyness'] is not None else '-',
                     ('%.3f' % c['implied_rate_pct'])
                     if c['implied_rate_pct'] is not None else '-'))
            if c['implied_rate_pct'] is not None:
                all_rates.append(c['implied_rate_pct'])
            if c['slope_vs_log_moneyness'] is not None:
                all_slopes.append(abs(c['slope_vs_log_moneyness']))
            all_spreads.append(c['residual_spread'])

    print('-' * 96)
    print()
    if all_rates:
        print('implied rate   : median %.3f%%   range %.3f%% .. %.3f%%   (n=%d chains)'
              % (median(all_rates), min(all_rates), max(all_rates), len(all_rates)))
    if all_slopes:
        print('|slope|        : median %.6f   worst %.6f' % (median(all_slopes), max(all_slopes)))
    if all_spreads:
        print('spread         : median %.6f   worst %.6f' % (median(all_spreads), max(all_spreads)))
    print()
    print('HOW TO READ THIS')
    print('  A tight spread and a near-zero slope mean the two sides differ by a')
    print('  constant, which is what a USD present value with a single discount')
    print('  factor predicts. The numeraire concern would appear as a slope that')
    print('  grows with the tails, not as scatter.')
    print()
    print('  A plausible and expiry-consistent implied rate is the second leg of')
    print('  the evidence. A nonsensical or wildly varying rate means the residual')
    print('  is a constant for some other reason and the reading is wrong.')
    print()
    print('  This does NOT rule out an error that is itself affine in K.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
