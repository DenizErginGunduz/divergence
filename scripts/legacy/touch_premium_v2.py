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
touch_premium_v2.py — LAYER 3, WITH THE D-027 CORRECTION

Yesterday's `touch_premium_btc.py` produced the terminal probability with a naive
N(d2). `skew_correction_btc.py` measured that method deviating from the referee by
54.8% on average on the monthly chain, and by 334% in the wings. So yesterday's
"20/20 inside the band" result was computed with the WRONG denominator.

This script recomputes the same ladder with three denominators:
   A) naive       : N(d2)                         <- yesterday's denominator
   B) skew-adj    : N(d2) - vega * dsigma/dK      <- the corrected analytical form
   C) model-free  : -dC/dK, neighbouring strikes  <- PRIMARY (the D-027 decision)

The direction matters: the naive denominator INFLATES the terminal in the wings.
An inflated denominator SHRINKS the ratio. So the correction makes the ratios
LARGER.
  -> The hard lower bound (ratio >= 1) becomes impossible to violate; the D-018
     result stands.
  -> The upper bound (ratio <= 2) is SOFT and can be exceeded; a rung above it is a
     FLAG, not a violation.
The two are counted separately so that distinction is never lost.
"""
import json, csv, os, math, datetime, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DER = os.path.join(BASE, 'raw', 'deribit_btc_monthly_2026-08-05T2135Z.csv')
STORE = os.path.join(BASE, 'raw', '_store.json')

SNAP = datetime.datetime(2026, 8, 5, 21, 35, 12, tzinfo=datetime.timezone.utc)
PM_EXPIRY = datetime.datetime(2026, 9, 1, 3, 59, tzinfo=datetime.timezone.utc)
EXP = {'28AUG26': datetime.datetime(2026, 8, 28, 8, 0, tzinfo=datetime.timezone.utc),
       '25SEP26': datetime.datetime(2026, 9, 25, 8, 0, tzinfo=datetime.timezone.utc)}
FUT = {'28AUG26': 64794.96, '25SEP26': 65024.68}
YEAR = 365.0
N = lambda x: 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
PHI = lambda x: math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
yrs = lambda t: (t - SNAP).total_seconds() / 86400.0 / YEAR

chain = {}
for r in csv.DictReader(open(DER, encoding='utf-8')):
    chain.setdefault(r['expiry'], {})[int(r['strike'])] = {
        'mark': float(r['mark']), 'iv': float(r['iv']) / 100.0}

E1, E2 = '28AUG26', '25SEP26'
T1, T2, TP = yrs(EXP[E1]), yrs(EXP[E2]), yrs(PM_EXPIRY)
w = (TP - T1) / (T2 - T1)
F = FUT[E1] + (FUT[E2] - FUT[E1]) * (TP - T1) / (T2 - T1)


def _br(c, K):
    """The two strikes that bracket K."""
    ks = sorted(c)
    lo = [k for k in ks if k < K]
    hi = [k for k in ks if k > K]
    return (lo[-1], hi[0]) if (lo and hi) else (None, None)


def iv_at(e, K):
    c = chain[e]
    if K in c:
        return c[K]['iv']
    a, b = _br(c, K)
    if a is None:
        return None
    return c[a]['iv'] + (c[b]['iv'] - c[a]['iv']) * (K - a) / (b - a)


def dsig_at(e, K):
    c = chain[e]
    a, b = _br(c, K)
    if a is None:
        return None
    return (c[b]['iv'] - c[a]['iv']) / (b - a)


def dig_at(e, K):
    c = chain[e]
    a, b = _br(c, K)
    if a is None:
        return None
    return max(0.0, min(1.0, (c[a]['mark'] - c[b]['mark']) / (b - a)))


def terminals(K):
    """P(S_T > K) by all three methods, carried to the Polymarket expiry."""
    i1, i2 = iv_at(E1, K), iv_at(E2, K)
    if i1 is None or i2 is None:
        return None
    v = (i1 * i1 * T1) * (1 - w) + (i2 * i2 * T2) * w      # total variance interp.
    if v <= 0:
        return None
    d1 = (math.log(F / K) + 0.5 * v) / math.sqrt(v)
    d2 = d1 - math.sqrt(v)
    naive = N(d2)
    s1, s2 = dsig_at(E1, K), dsig_at(E2, K)
    skew = None
    if s1 is not None and s2 is not None:
        ds = s1 * (1 - w) + s2 * w                          # the skew is interpolated too
        skew = max(0.0, min(1.0, naive - F * PHI(d1) * math.sqrt(TP) * ds))
    g1, g2 = dig_at(E1, K), dig_at(E2, K)
    digi = None if (g1 is None or g2 is None) else g1 * (1 - w) + g2 * w
    return {'naive': naive, 'skew': skew, 'dig': digi}


# ---------- the Polymarket monthly touch ladder (same extraction as yesterday) ----------
store = json.load(open(STORE, encoding='utf-8'))
raw = []
for m in store['markets'].values():
    ql = (m.get('question') or '').lower()
    if 'bitcoin' not in ql or m.get('endDateIso') != '2026-09-01':
        continue
    if 'reach' not in ql and 'dip to' not in ql:
        continue
    n = re.findall(r'\$([\d,]+)', m.get('question') or '')
    bb, ba = m.get('bestBid'), m.get('bestAsk')
    if not n or not (isinstance(bb, (int, float)) and isinstance(ba, (int, float))):
        continue
    raw.append({'K': int(n[0].replace(',', '')), 'dir': 'up' if 'reach' in ql else 'down',
                'mid': (bb + ba) / 2, 'spread': ba - bb, 'vol': m.get('volumeNum') or 0})

seen, rows = {}, []
for r in sorted(raw, key=lambda x: -x['vol']):
    if (r['K'], r['dir']) not in seen:
        seen[(r['K'], r['dir'])] = r
        rows.append(r)

print('=' * 100)
print('LAYER 3 v2 — TOUCH PREMIUM, WITH THE SKEW CORRECTION (paying off the D-027 debt)')
print('=' * 100)
print('Forward %.2f   |   PM expiry T=%.4f years   |   interp w=%.4f' % (F, TP, w))
print('%-5s %-8s %-9s %-9s %-9s %-9s %-7s %-7s %-7s %s'
      % ('SIDE', 'THRESH', 'PM_touch', 'A naive', 'B skew', 'C free',
         'rA', 'rB', 'rC', 'STATUS (C is primary)'))
print('-' * 100)
out = []
cnt = {'violation': 0, 'in_band': 0, 'flag': 0}
changed = []
for r in sorted(rows, key=lambda x: (x['dir'], x['K'])):
    t = terminals(r['K'])
    if t is None or t['dig'] is None or t['skew'] is None:
        continue
    fix = lambda p: p if r['dir'] == 'up' else 1 - p
    tA, tB, tC = fix(t['naive']), fix(t['skew']), fix(t['dig'])
    if min(tA, tB, tC) <= 1e-6:
        continue
    oA, oB, oC = r['mid'] / tA, r['mid'] / tB, r['mid'] / tC
    if oC < 1:
        st = 'HARD VIOLATION'; cnt['violation'] += 1
    elif oC <= 2:
        st = 'in band'; cnt['in_band'] += 1
    else:
        st = 'flag (>2)'; cnt['flag'] += 1
    dA = 'in band' if 1 <= oA <= 2 else ('HARD VIOLATION' if oA < 1 else 'flag (>2)')
    if dA != st:
        changed.append((r['dir'], r['K'], dA, st, oA, oC))
    print('%-5s %-8d %-9.4f %-9.4f %-9.4f %-9.4f %-7.2f %-7.2f %-7.2f %s'
          % (r['dir'], r['K'], r['mid'], tA, tB, tC, oA, oB, oC, st))
    out.append({'dir': r['dir'], 'strike': r['K'], 'pm_touch': r['mid'],
                'pm_spread': r['spread'], 'term_naive': tA, 'term_skew': tB,
                'term_digital': tC, 'ratio_naive': oA, 'ratio_skew': oB,
                'ratio_digital': oC, 'status': st, 'volume': r['vol']})
print('-' * 100)
print('WITH THE MODEL-FREE DENOMINATOR (primary): in band %d  |  HARD VIOLATION %d'
      '  |  flag(>2) %d   [total %d]'
      % (cnt['in_band'], cnt['violation'], cnt['flag'], len(out)))
print()
if changed:
    print('RUNGS THAT CHANGED VERDICT (naive denominator -> model-free):')
    for d in changed:
        print('   %-5s %-7d  %-16s -> %-16s   (ratio %.2f -> %.2f)'
              % (d[0], d[1], d[2], d[3], d[4], d[5]))
else:
    print('No rung changed status — yesterday'
          "'s result turned out robust to the denominator.")
print()
print('READING')
print(' * The hard lower bound (ratio >= 1) is true BY DEFINITION; there is no model')
print('   to argue about.')
print(' * The upper bound (ratio <= 2) comes from a zero-drift assumption; exceeding')
print('   it is NOT a violation.')
print(' * The naive denominator inflated the terminal in the wings. The correction')
print('   makes the ratios LARGER, which makes the lower bound safer still and can')
print('   raise a flag at the upper one.')
json.dump({'snapshot': SNAP.isoformat(), 'w': w, 'F': F, 'TP': TP,
           'counts': cnt, 'rows': out},
          open(os.path.join(BASE, 'inventory', 'touch_premium_v2.json'), 'w',
               encoding='utf-8'), ensure_ascii=False, indent=1)
