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
layer1_consistency.py — LAYER 1 INTERNAL CONSISTENCY TEST

The question: does the cumulative of the discrete density we extract from a
bucket (range) ladder reproduce the prices of the terminal threshold ladder at
THE SAME EXPIRY?

Two ladders price the same event in two different ways:
  - range    : P(K_i < S_T <= K_{i+1})     -> the density, directly
  - terminal : P(S_T > K)                  -> the cumulative survival function
The identity:  P(S_T > K_j) = sum over i >= j of P(bucket_i)

If it holds: the ladder-to-density engine works and the classification is right.
If it does not: either the classification is wrong, or the market is
inconsistent, or the data is stale. The SIZE and the SIGN of the deviation are
what tell the three apart.

Needs NO external data source. It uses raw/_store.json only.
"""
import json, os, sys, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(BASE, 'raw', '_store.json')


def mid(m):
    """Mid price. On a one-sided book with no counterparty it falls back to
    outcomePrices."""
    bb, ba = m.get('bestBid'), m.get('bestAsk')
    if isinstance(bb, (int, float)) and isinstance(ba, (int, float)):
        return (bb + ba) / 2.0, 'bid/ask mid'
    try:
        return float(json.loads(m['outcomePrices'])[0]), 'outcomePrices (one-sided book)'
    except Exception:
        return None, 'NONE'


def num(s):
    return float(str(s).replace(',', '').replace('$', '').strip())


def collect(store, above_pat, range_pat, expiry):
    above, rng = {}, []
    for m in store['markets'].values():
        sl = m.get('slug') or ''
        if m.get('endDateIso') != expiry:
            continue
        gt = (m.get('groupItemTitle') or '').strip()
        p, src = mid(m)
        if p is None:
            continue
        if above_pat in sl:
            above[num(gt)] = (p, src, (m.get('updatedAt') or '')[11:19])
        elif range_pat in sl:
            if gt.startswith('>'):
                lo, hi = num(gt[1:]), float('inf')
            elif gt.startswith('<'):
                lo, hi = 0.0, num(gt[1:])
            elif '-' in gt:
                a, b = gt.split('-'); lo, hi = num(a), num(b)
            else:
                continue
            rng.append({'lo': lo, 'hi': hi, 'p': p, 'src': src,
                        'upd': (m.get('updatedAt') or '')[11:19], 'label': gt})
    rng.sort(key=lambda x: x['lo'])
    return above, rng


def run(asset, above_pat, range_pat, expiry):
    store = json.load(open(STORE, encoding='utf-8'))
    above, rng = collect(store, above_pat, range_pat, expiry)
    if not above or not rng:
        print('%s: no data (above=%d, range=%d)' % (asset, len(above), len(rng)))
        return None

    print('\n' + '=' * 76)
    print('LAYER 1 — %s, expiry %s' % (asset, expiry))
    print('=' * 76)

    ts = sorted({v[2] for v in above.values()} | {r['upd'] for r in rng})
    print('Snapshot stamps: %s  (the spread between them is part of this test'
          "'s error budget)" % ', '.join(ts))

    tot = sum(r['p'] for r in rng)
    print('\nBucket total = %.4f   (no-arbitrage: should be 1.0; the excess is'
          ' spread and rounding)' % tot)
    covered_lo = min(r['lo'] for r in rng)
    has_low_tail = any(r['lo'] == 0.0 for r in rng)
    if not has_low_tail:
        print('WARNING: there is no lower-tail bucket (<%g). The ladder is NOT'
              ' EXHAUSTIVE.' % covered_lo)
        print('         The cumulative is meaningless below that level.')

    # Cumulative: P(S_T > K) = the sum of the buckets at and above K
    print('\n%-9s %-12s %-12s %-10s %-10s %s' %
          ('THRESHOLD', 'BUCKET->CUM', 'TERMINAL', 'DIFF', 'NORM.DIFF', 'NOTE'))
    print('-' * 76)
    rows = []
    for K in sorted(above.keys(), reverse=True):
        cum = sum(r['p'] for r in rng if r['lo'] >= K - 1e-9)
        term, src, _ = above[K]
        d = cum - term
        dn = (cum / tot) - term          # if the bucket set is normalised to 1
        flag = ''
        if abs(d) > 0.05:
            flag = 'LARGE DEVIATION'
        elif abs(d) > 0.02:
            flag = 'watch'
        if not has_low_tail and K <= covered_lo:
            flag = (flag + ' | lower tail missing').strip(' |')
        print('%-9g %-12.4f %-12.4f %-+10.4f %-+10.4f %s' % (K, cum, term, d, dn, flag))
        rows.append({'strike': K, 'bucket_cumulative': round(cum, 6),
                     'terminal': round(term, 6), 'diff': round(d, 6),
                     'normalised_diff': round(dn, 6), 'terminal_source': src})

    va = [abs(r['diff']) for r in rows]
    vn = [abs(r['normalised_diff']) for r in rows]
    print('-' * 76)
    print('Mean |diff| = %.4f   |  after normalising = %.4f' %
          (sum(va) / len(va), sum(vn) / len(vn)))
    print('Max  |diff| = %.4f   |  after normalising = %.4f' % (max(va), max(vn)))
    return {'asset': asset, 'expiry': expiry, 'bucket_total': round(tot, 6),
            'has_lower_tail': has_low_tail, 'snapshot_stamps': ts,
            'mean_absolute_diff': round(sum(va) / len(va), 6),
            'normalised_mean_absolute_diff': round(sum(vn) / len(vn), 6),
            'rows': rows}


if __name__ == '__main__':
    out = []
    for args in [('ETH', 'ethereum-above-', 'the-price-of-ethereum-be', '2026-08-06'),
                 ('BTC', 'bitcoin-above-', 'the-price-of-bitcoin-be', '2026-08-06')]:
        r = run(*args)
        if r:
            out.append(r)
    p = os.path.join(BASE, 'inventory', 'layer1_results.json')
    json.dump({'produced_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'results': out}, open(p, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\nWritten: %s' % p)
    print("""
HOW TO READ THIS
  diff ~ 0                 -> the engine works and the classification is right.
  diff always POSITIVE     -> the bucket set sums above 1; spread and rounding.
                              The "normalised diff" column corrects for that.
  a large deviation on one -> read that contract's rule text first. A
  single threshold            classification error is likelier than a market
                              inconsistency.
  lower tail missing       -> the cumulative below that level is MEANINGLESS.
                              Do not read it.
""")
