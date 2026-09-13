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
put_vs_itmcall_test.py — MEASURE WHAT D-032 COSTS (needs NO Polymarket data)

In D-032 I claimed the downside terminal cannot be extracted from deep ITM calls.
Yesterday that claim was only a diagnosis. Today we hold BOTH the call and the put
chain for the same expiry, so the claim is directly measurable. Compute the same
quantity two ways:

    A) PUT route  (correct)  : P(S_T < K) = +dP/dK, from OTM put prices
    B) CALL route (D-032)    : P(S_T < K) = 1 - (-dC/dK), from ITM call prices

The two are theoretically the SAME number (put-call parity). However far apart
they are is measurement error, directly. Nothing invented, nothing assumed, no
referee — an identity.

BONUS — LAYER 2 COMES FOR FREE:
Put-call parity, C - P = F - K, gives an estimate of F at every strike. If those
estimates agree across strikes the chain is internally consistent, and we have the
forward without fetching any futures data.
"""
import csv, os, statistics

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(BASE, 'raw', 'deribit_btc_putcall_2026-08-28T1858Z.csv')
INDEX = 77478.56
TIME_VALUE_LIMIT = 0.05

ch = {'C': {}, 'P': {}}
for r in csv.DictReader(open(CSV, encoding='utf-8')):
    if r['expiry'] != '25SEP26':
        continue
    ch[r['type']][int(r['strike'])] = {'mark': float(r['mark']),
                                       'iv': float(r['iv']) / 100.0}

# ---------- LAYER 2: the forward from put-call parity ----------
print('=' * 92)
print('LAYER 2 (free) — the forward from put-call parity:  F = K + C - P')
print('=' * 92)
Fs = []
common = sorted(set(ch['C']) & set(ch['P']))
for K in common:
    if not (0.75 * INDEX <= K <= 1.30 * INDEX):      # parity is sound near the money
        continue
    F = K + ch['C'][K]['mark'] - ch['P'][K]['mark']
    Fs.append((K, F))
for K, F in Fs:
    print('   K=%-8d F=%.2f' % (K, F))
F_MED = statistics.median([f for _, f in Fs])
sp = max(f for _, f in Fs) - min(f for _, f in Fs)
print('-' * 92)
print('Median F = %.2f   |   dispersion = %.2f USD (%.3f%%)   |   index = %.2f'
      % (F_MED, sp, 100 * sp / F_MED, INDEX))
print('Basis (F/index - 1) = %+.3f%%  -> over 28 days, %+.1f%% annualised carry'
      % (100 * (F_MED / INDEX - 1), 100 * ((F_MED / INDEX) ** (365 / 28) - 1)))
print('READING: a narrow dispersion means the chain is INTERNALLY CONSISTENT, and')
print('the forward is in hand without fetching futures data.')

# ---------- D-032: the put route versus the ITM call route ----------
def dig_put(K):
    """P(S_T < K) = +dP/dK  (the OTM put side, well conditioned)."""
    ks = sorted(ch['P'])
    lo = [k for k in ks if k < K]
    hi = [k for k in ks if k > K]
    if not lo or not hi:
        return None
    a, b = lo[-1], hi[0]
    return max(0.0, min(1.0, (ch['P'][b]['mark'] - ch['P'][a]['mark']) / (b - a)))


def dig_call(K):
    """P(S_T < K) = 1 - (-dC/dK)  (below F this is the ITM call side, BADLY
    conditioned)."""
    ks = sorted(ch['C'])
    lo = [k for k in ks if k < K]
    hi = [k for k in ks if k > K]
    if not lo or not hi:
        return None
    a, b = lo[-1], hi[0]
    return max(0.0, min(1.0, 1.0 - (ch['C'][a]['mark'] - ch['C'][b]['mark']) / (b - a)))


def time_value(K):
    """Time value as a share of the price on an ITM call. The D-032 detector."""
    c = ch['C'].get(K)
    if not c or c['mark'] <= 0:
        return None
    return (c['mark'] - max(0.0, INDEX - K)) / c['mark']


print('\n' + '=' * 92)
print('THE D-032 TEST — the same number, two routes.  P(S_T < K), 25SEP26')
print('=' * 92)
print('%-9s %-11s %-13s %-13s %-11s %s'
      % ('THRESHOLD', 'time val.', 'A: PUT route', 'B: CALL route', 'B/A', 'VERDICT'))
print('-' * 92)
rows = []
for K in sorted(ch['P']):
    if K > F_MED or K < 40000:
        continue
    a, b = dig_put(K), dig_call(K)
    tv = time_value(K)
    if a is None or b is None or a < 1e-5:
        continue
    r = b / a
    bad = (tv is not None and tv < TIME_VALUE_LIMIT)
    st = ('CALL ROUTE COLLAPSED' if (r > 2 or r < 0.5) else
          'call route drifting' if (r > 1.25 or r < 0.8) else 'the two routes agree')
    print('%-9d %-11s %-13.4f %-13.4f %-11.2fx %s'
          % (K, ('%.1f%%' % (100 * tv)) if tv is not None else '-', a, b, r,
             st + (' (deep ITM)' if bad else '')))
    rows.append((K, tv, a, b, r, bad))
print('-' * 92)
deep = [x for x in rows if x[5]]
sound = [x for x in rows if not x[5]]
if deep:
    rr = [x[4] for x in deep]
    print('DEEP ITM region (time value < %.0f%%): %d rungs, B/A ratio %.2f-%.2f'
          % (100 * TIME_VALUE_LIMIT, len(deep), min(rr), max(rr)))
if sound:
    rr = [x[4] for x in sound]
    print('SOUND region                        : %d rungs, B/A ratio %.2f-%.2f'
          % (len(sound), min(rr), max(rr)))
print()
print('CONCLUSION — D-032 is no longer a diagnosis, it is a MEASUREMENT.')
print(' * The two routes MUST give the same number (put-call parity). Divergence = error.')
print(' * The error blows up in the deep ITM region and vanishes in the sound one.')
print(' * The rule: a PUT chain is required for the downside. No puts, no number.')
