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
ladder_health.py — LADDER HEALTH CHECK (needs no external data)

The check to run BEFORE touching option data. It asks three questions:

1) SPREAD VS THE QUANTITY BEING MEASURED
   The gap we are measuring is a few points. If the bid-ask spread is wider than
   that, the number produced is the spread itself, not a market view.
   Threshold: spread > 0.02 means "not measurable".

2) MONOTONICITY  (a model-free data quality test)
   Within one ladder, touch probability MUST fall as the threshold rises (upside)
   and MUST fall as the threshold falls (downside). A violation means either the
   quote is broken or the record is wrong.

3) POSSIBLY ALREADY RESOLVED
   A touch contract with mid >= 0.99 has probably already happened; the `closed`
   flag may simply not have come back. These have to come out of the ladder, or
   the rung stays broken. (The user's BTC 62,500 hypothesis — D-020.)
"""
import json, os, re, statistics

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
store = json.load(open(os.path.join(BASE, 'raw', '_store.json'), encoding='utf-8'))

SPREAD_LIMIT = 0.02     # above this the gap is not measurable
RESOLVED_LIMIT = 0.99   # above this it has probably already happened

TICK = {'tsla': 'TSLA', 'nvda': 'NVDA', 'meta': 'META', 'spy': 'SPY',
        'aapl': 'AAPL', 'bitcoin': 'BTC'}


def ladders():
    out = {}
    for ev in store['events'].values():
        m = re.match(r'what-price-will-(\w+)-hit-in-august-2026', ev.get('slug') or '')
        if not m:
            continue
        t = TICK.get(m.group(1), m.group(1).upper())
        rungs = []
        for x in (ev.get('markets') or []):
            gt = x.get('groupItemTitle') or ''
            n = re.findall(r'([\d,\.]+)', gt.replace('$', ''))
            if not n:
                continue
            bb, ba = x.get('bestBid'), x.get('bestAsk')
            if not (isinstance(bb, (int, float)) and isinstance(ba, (int, float))):
                continue
            rungs.append({'K': float(n[0].replace(',', '')),
                          'dir': 'up' if '↑' in gt else 'down',
                          'mid': (bb + ba) / 2, 'spread': ba - bb,
                          'vol': x.get('volumeNum') or 0})
        if rungs:
            out[t] = rungs
    return out


print('=' * 94)
print('LADDER HEALTH CHECK — before moving on to option data')
print('=' * 94)
print('%-6s %5s %9s %9s %9s %8s %9s %s'
      % ('ASSET', 'rungs', 'median', 'mean', 'widest', 'measur', 'possibly', 'monotone'))
print('%-6s %5s %9s %9s %9s %8s %9s %s'
      % ('', '', 'spread', 'spread', 'spread', 'able', 'resolved', 'violations'))
print('-' * 94)

report = {}
for t, R in sorted(ladders().items()):
    sp = [r['spread'] for r in R]
    usable = [r for r in R if r['spread'] <= SPREAD_LIMIT and r['mid'] < RESOLVED_LIMIT]
    resolved = [r for r in R if r['mid'] >= RESOLVED_LIMIT]

    # monotonicity: upside, mid must fall as K rises; downside, mid must fall as K falls
    viol = []
    for d, keyf in (('up', lambda r: r['K']), ('down', lambda r: -r['K'])):
        seq = sorted([r for r in R if r['dir'] == d and r['mid'] < RESOLVED_LIMIT], key=keyf)
        for a, b in zip(seq, seq[1:]):
            if b['mid'] > a['mid'] + 1e-9:
                viol.append((d, a['K'], a['mid'], b['K'], b['mid']))

    print('%-6s %5d %9.3f %9.3f %9.3f %8d %9d %s'
          % (t, len(R), statistics.median(sp), statistics.mean(sp), max(sp),
             len(usable), len(resolved), len(viol) if viol else '-'))
    report[t] = {'rungs': len(R), 'median_spread': round(statistics.median(sp), 4),
                 'widest_spread': round(max(sp), 4), 'measurable': len(usable),
                 'possibly_resolved': len(resolved),
                 'monotonicity_violations': [{'direction': v[0], 'K1': v[1], 'mid1': v[2],
                                              'K2': v[3], 'mid2': v[4]} for v in viol]}

print('-' * 94)
print('"measurable" = rungs with spread <= %.2f AND mid < %.2f'
      % (SPREAD_LIMIT, RESOLVED_LIMIT))
print()

for t, r in sorted(report.items()):
    if r['monotonicity_violations']:
        print('MONOTONICITY VIOLATION — %s:' % t)
        for v in r['monotonicity_violations']:
            print('   %s side: K=%g mid=%.4f  ->  K=%g mid=%.4f  (probability ROSE, impossible)'
                  % (v['direction'], v['K1'], v['mid1'], v['K2'], v['mid2']))

print('\nPOSSIBLY RESOLVED (mid >= %.2f) — should come out of the ladder:' % RESOLVED_LIMIT)
for t, R in sorted(ladders().items()):
    res = [r for r in R if r['mid'] >= RESOLVED_LIMIT]
    if res:
        print('   %-6s %s' % (t, ', '.join('%s%g' % ('↑' if r['dir'] == 'up' else '↓', r['K'])
                                           for r in sorted(res, key=lambda x: x['K']))))

json.dump(report, open(os.path.join(BASE, 'inventory', 'ladder_health.json'), 'w',
                       encoding='utf-8'), ensure_ascii=False, indent=1)
print('\nWritten: inventory/ladder_health.json')
