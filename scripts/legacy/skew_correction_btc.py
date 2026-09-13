# LEGACY — this script does not run.
#
# It reads `raw/_store.json` or `inventory/*.csv`: a local layout from the first
# weeks of the project. Neither exists in the repository. The archive moved to
# per-run gzipped snapshots under `raw/<stream>/<date>/`, documented in
# docs/ARCHIVE_SCHEMA.md.
#
# Kept for the reasoning, not the code. What these scripts measured has been
# re-measured against the archive by the measure_*.py scripts one directory up.
#
# Do not repair this file. If you need what it did, write a new measurement on
# top of scripts/archive.py.

#!/usr/bin/env python3
"""
skew_correction_btc.py — THE D-027 DEBT: redo the BTC measurements with the skew term

THE PROBLEM (caught on SPY in D-027):
The digital probability is the derivative of the call price with respect to strike:
        P(S_T > K) = -dC/dK
But C depends on K TWO ways: directly, and through the IV curve.
        C = C_BS(K, sigma(K))
        dC/dK = (dC_BS/dK)|sigma  +  vega * (dsigma/dK)
                 \_____________/     \________________/
                    -N(d2)               THE SKEW TERM

A naive N(d2) drops the second term ENTIRELY. When skew is present — and on BTC it
always is — that is a systematic error; on SPY we measured a 2.12x deviation in the
left wing.

This script computes the same ladders THREE ways and puts them side by side:
   A) naive      : N(d2)                        <- yesterday's faulty method
   B) skew-adj   : N(d2) - vega * dsigma/dK     <- the corrected analytical form
   C) model-free : [C(a) - C(b)] / (b - a)      <- carries no assumption, the REFEREE

C is the referee. If B lands closer to C than A does, the correction is working.

Black-76 (on the forward, discounting ignored — all expiries <= 51 days):
   d1 = (ln(F/K) + v/2) / sqrt(v),  d2 = d1 - sqrt(v),   v = sigma^2 * T
   dC/dK|sigma = -N(d2)
   vega        = F * phi(d1) * sqrt(T)
"""
import csv, os, math, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = lambda x: 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
PHI = lambda x: math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
YEAR = 365.0


def load(path):
    """Turn the CSV into expiry -> strike -> {mark, iv}. IV from percent to decimal."""
    ch = {}
    for r in csv.DictReader(open(path, encoding='utf-8')):
        ch.setdefault(r['expiry'], {})[int(r['strike'])] = {
            'mark': float(r['mark']), 'iv': float(r['iv']) / 100.0}
    return ch


def iv_at(c, K):
    """IV at a strike; if the exact strike is absent, interpolate linearly between
    its neighbours."""
    if K in c:
        return c[K]['iv']
    ks = sorted(c)
    lo = [k for k in ks if k < K]
    hi = [k for k in ks if k > K]
    if not lo or not hi:
        return None
    a, b = lo[-1], hi[0]
    return c[a]['iv'] + (c[b]['iv'] - c[a]['iv']) * (K - a) / (b - a)


def dsigma_dK(c, K):
    """The IV slope by central difference. This is the quantity D-027 was missing."""
    ks = sorted(c)
    lo = [k for k in ks if k < K]
    hi = [k for k in ks if k > K]
    if not lo or not hi:
        return None
    a, b = lo[-1], hi[0]
    return (c[b]['iv'] - c[a]['iv']) / (b - a)


def probs(c, K, F, T):
    """Naive and skew-adjusted probability for one strike, plus the intermediates."""
    s = iv_at(c, K)
    sk = dsigma_dK(c, K)
    if s is None or s <= 0 or T <= 0:
        return None
    v = s * s * T
    d1 = (math.log(F / K) + 0.5 * v) / math.sqrt(v)
    d2 = d1 - math.sqrt(v)
    naive = N(d2)
    vega = F * PHI(d1) * math.sqrt(T)          # USD per unit of vol
    corr = vega * sk if sk is not None else 0.0
    return {'naive': naive, 'skew_adj': max(0.0, min(1.0, naive - corr)),
            'vega': vega, 'dsig': sk, 'corr': corr, 'iv': s}


def digital(c, K):
    """The model-free referee: the call price difference of the two strikes that
    bracket K."""
    ks = sorted(c)
    lo = [k for k in ks if k < K]
    hi = [k for k in ks if k > K]
    if not lo or not hi:
        return None
    a, b = lo[-1], hi[0]
    return max(0.0, min(1.0, (c[a]['mark'] - c[b]['mark']) / (b - a)))


def report(title, c, F, T, strikes):
    print('\n' + '=' * 96)
    print(title)
    print('=' * 96)
    print('Forward %.2f   |   T = %.5f years (%.1f days)' % (F, T, T * YEAR))
    print('%-8s %-7s %-11s %-9s %-10s %-10s %-10s %s'
          % ('K', 'IV', 'dsig/dK', 'vega', 'A naive', 'B skew-adj', 'C model-free',
             'naive/free'))
    print('-' * 96)
    sa, sb = [], []
    for K in strikes:
        p = probs(c, K, F, T)
        d = digital(c, K)
        if p is None or d is None or d < 1e-4:
            continue
        ra, rb = p['naive'] / d, p['skew_adj'] / d
        sa.append(abs(ra - 1)); sb.append(abs(rb - 1))
        print('%-8d %-7.1f %-11.2e %-9.0f %-10.4f %-10.4f %-10.4f %.2fx'
              % (K, p['iv'] * 100, p['dsig'], p['vega'],
                 p['naive'], p['skew_adj'], d, ra))
    print('-' * 96)
    if sa:
        print('Mean deviation from the referee:  A naive = %.1f%%   ->   B skew-adj = %.1f%%'
              % (100 * sum(sa) / len(sa), 100 * sum(sb) / len(sb)))
        print('Largest deviation              :  A naive = %.1f%%   ->   B skew-adj = %.1f%%'
              % (100 * max(sa), 100 * max(sb)))
    return sa, sb


# ---------------- 1) DAILY chain: the data bridge_btc.py rests on ----------------
g = load(os.path.join(BASE, 'raw', 'deribit_btc_2026-08-05T2123Z.csv'))
SNAP_D = datetime.datetime(2026, 8, 5, 21, 22, 55, tzinfo=datetime.timezone.utc)
T_6AUG = (datetime.datetime(2026, 8, 6, 8, 0, tzinfo=datetime.timezone.utc)
          - SNAP_D).total_seconds() / 86400.0 / YEAR
ks_d = [k for k in sorted(g['6AUG26']) if 60000 <= k <= 67000]
a1, b1 = report('DAILY CHAIN — 6AUG26 (the data bridge_btc.py uses)',
                g['6AUG26'], 64673.90, T_6AUG, ks_d)

# ---------------- 2) MONTHLY chain: the data touch_premium_btc.py rests on -------
m = load(os.path.join(BASE, 'raw', 'deribit_btc_monthly_2026-08-05T2135Z.csv'))
SNAP_M = datetime.datetime(2026, 8, 5, 21, 35, 12, tzinfo=datetime.timezone.utc)
T_28AUG = (datetime.datetime(2026, 8, 28, 8, 0, tzinfo=datetime.timezone.utc)
           - SNAP_M).total_seconds() / 86400.0 / YEAR
ks_m = [k for k in sorted(m['28AUG26']) if 52000 <= k <= 85000]
a2, b2 = report('MONTHLY CHAIN — 28AUG26 (the data touch_premium_btc.py uses)',
                m['28AUG26'], 64794.96, T_28AUG, ks_m)

print('\n' + '=' * 96)
print('CONCLUSION — what the D-027 correction does on the BTC side')
print('=' * 96)
for name, A, B in (('daily 6AUG26', a1, b1), ('monthly 28AUG26', a2, b2)):
    if not A:
        continue
    ia, ib = sum(A) / len(A), sum(B) / len(B)
    print('%-18s mean deviation %.1f%% -> %.1f%%   (%s)'
          % (name, 100 * ia, 100 * ib,
             'IMPROVED' if ib < ia else 'NOT IMPROVED — needs a look'))
