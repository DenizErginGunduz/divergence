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
touch_bound_lognormal.py — is the "2" upper bound right, and is the downside measurable?

TWO QUESTIONS AT ONCE. In the first version I tried to back sigma out of the
terminal probability; the solver saturated (everything came out at 400%). The
reason: N(d2) is NOT MONOTONE in sigma, and at upper strikes there are two
solutions. The fix: instead of fitting sigma, use the chain's OWN IV and carry it
to the expiry with total variance.

QUESTION 1 — is the "2" upper bound wrong?
  Lognormal, a martingale on the forward: X_t = mu*t + sigma*W_t, mu = -sigma^2/2
    downside b = ln(B/F) < 0:
       terminal = N((b-mu*T)/rT)
       touch    = terminal + exp(-b) * N((b+mu*T)/rT)
    upside a = ln(A/F) > 0:
       terminal = N((-a+mu*T)/rT)
       touch    = terminal + exp(-a) * N((-a-mu*T)/rT)
  The constant "2" is exact only for driftless arithmetic BM. The full formula
  gives every rung ITS OWN upper bound; it is not a single number.

QUESTION 2 — is the downside terminal trustworthy?  (this may be D-025 again)
  The Deribit file we hold contains CALLS ONLY. The downside terminal comes out as
  1 - P(S>K), which means it comes from DEEP ITM calls.
  A deep ITM call's price is almost entirely intrinsic value; the time value is a
  few percent of the price. Taking a derivative off such a price means reading a
  small difference from the difference of two large numbers. D-025 was exactly
  this trap.
  This script measures and reports the TIME VALUE SHARE for every rung. Where the
  share is small, that row's number is FICTION; it is dropped without needing any
  theoretical argument.
"""
import json, csv, os, math

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = lambda x: 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
TIME_VALUE_LIMIT = 0.05      # time value under 5% of the price -> not measurable

d = json.load(open(os.path.join(BASE, 'inventory', 'touch_premium_v2.json'),
                   encoding='utf-8'))
F, TP, w = d['F'], d['TP'], d['w']

chain = {}
for r in csv.DictReader(open(os.path.join(
        BASE, 'raw', 'deribit_btc_monthly_2026-08-05T2135Z.csv'), encoding='utf-8')):
    chain.setdefault(r['expiry'], {})[int(r['strike'])] = {
        'mark': float(r['mark']), 'iv': float(r['iv']) / 100.0}
E1, E2 = '28AUG26', '25SEP26'
T1, T2 = 0.06146, 0.13804      # the same expiry definitions as skew_correction_btc.py
INDEX = 64638.85


def interp(c, K, field):
    ks = sorted(c)
    if K in c:
        return c[K][field]
    lo = [k for k in ks if k < K]
    hi = [k for k in ks if k > K]
    if not lo or not hi:
        return None
    a, b = lo[-1], hi[0]
    return c[a][field] + (c[b][field] - c[a][field]) * (K - a) / (b - a)


def sigma_TP(K):
    """Sigma at the Polymarket expiry, by interpolating total variance."""
    i1, i2 = interp(chain[E1], K, 'iv'), interp(chain[E2], K, 'iv')
    if i1 is None or i2 is None:
        return None
    v = (i1 * i1 * T1) * (1 - w) + (i2 * i2 * T2) * w
    return math.sqrt(v / TP) if v > 0 else None


def time_value_share(K):
    """The deep ITM call diagnostic: time value / option price. The D-025 detector."""
    mk = interp(chain[E1], K, 'mark')
    if mk is None or mk <= 0:
        return None
    intrinsic = max(0.0, INDEX - K)
    return (mk - intrinsic) / mk


def theoretical(K, direction, sigma):
    mu = -0.5 * sigma * sigma
    rT = sigma * math.sqrt(TP)
    x = math.log(K / F)
    if direction == 'down':
        term = N((x - mu * TP) / rT)
        touch = term + math.exp(-x) * N((x + mu * TP) / rT)
    else:
        term = N((-x + mu * TP) / rT)
        touch = term + math.exp(-x) * N((-x - mu * TP) / rT)
    return (touch / term) if term > 1e-12 else None


print('=' * 104)
print('UPPER BOUND + MEASURABILITY TEST')
print('=' * 104)
print('%-5s %-8s %-9s %-9s %-11s %-11s %-9s %s'
      % ('SIDE', 'THRESH', 'sigma', 'time val', 'OBSERVED', 'THEO max', 'obs/theo', 'STATUS'))
print('-' * 104)
res = []
for r in d['rows']:
    K, dr = r['strike'], r['dir']
    s = sigma_TP(K)
    if s is None:
        continue
    tv = time_value_share(K)
    to = theoretical(K, dr, s)
    obs = r['ratio_digital']
    if to is None:
        continue
    if dr == 'down' and tv is not None and tv < TIME_VALUE_LIMIT:
        st = 'NOT MEASURABLE — deep ITM call (D-025)'
        rel = None
    elif obs > to:
        st = 'above the theoretical max'
        rel = obs / to
    else:
        st = 'below the theoretical max'
        rel = obs / to
    print('%-5s %-8d %-9.1f %-9s %-11.2f %-11.2f %-9s %s'
          % (dr, K, s * 100, ('%.1f%%' % (100 * tv)) if tv is not None else '-',
             obs, to, ('%.2f' % rel) if rel else '-', st))
    res.append({'dir': dr, 'strike': K, 'sigma': s, 'time_value_share': tv,
                'observed': obs, 'theoretical_max': to, 'rel': rel, 'status': st})
print('-' * 104)
meas = [x for x in res if not x['status'].startswith('NOT MEASURABLE')]
dropped = [x for x in res if x['status'].startswith('NOT MEASURABLE')]
under = [x for x in meas if x['observed'] <= x['theoretical_max']]
print('Measurable rungs      : %d / %d   (dropped: %d, all downside deep ITM)'
      % (len(meas), len(res), len(dropped)))
print('Below the theoretical : %d / %d' % (len(under), len(meas)))
if meas:
    rr = [x['rel'] for x in meas]
    print('mean observed/theoretical = %.2f  (1.00 = sitting exactly on the bound)'
          % (sum(rr) / len(rr)))
print()
print('COMPARISON')
print('  with the old constant "2"        : 6 / 19 in the band')
print('  full lognormal bound + dropping  : %d / %d measurable below the theoretical'
      % (len(under), len(meas)))
print()
print('CONCLUSION')
print(' * "2" is NOT A CONSTANT. Every rung has its own upper bound; using the')
print('   constant produced a bound too loose on the upside and too tight on the downside.')
print(' * The downside rungs cannot be measured from a CALL chain. The fix is to fetch')
print('   PUT data; with no puts, no downside number should be produced. This is the')
print('   D-025 rule repeating itself verbatim.')
json.dump(res, open(os.path.join(BASE, 'inventory', 'touch_bound_lognormal.json'), 'w',
                    encoding='utf-8'), ensure_ascii=False, indent=1)
