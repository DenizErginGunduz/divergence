#!/usr/bin/env python3
"""The settlement basis — BRTI against the Deribit index.

THE LAST UNKNOWN OF THE THREE
D-075 named three ways the Kalshi and Deribit contracts differ and sized two of
them. The settlement instant is 6d 21h on the year-end ladders (D-079). The
sixty-second averaging window is negligible against a hundred-day horizon. The
third — Kalshi settles on CF Benchmarks' BRTI, Deribit on its own index — was
left UNKNOWN because it looked unmeasurable.

It is measurable. Both halves are already archived:

  * a settled Kalshi market carries expiration_value, which IS the realised
    BRTI: the average of the sixty RTI prices before its close.
  * the Deribit payload carries usIn, a MICROSECOND timestamp of the instant
    the index was read. Not the snapshot time, the read time.

So each snapshot gives a Deribit index at a known instant, and the archive
holds fifteen-minute Kalshi settlements around it. Pair the nearest ones and
the difference is the basis plus whatever the price did in between.

SEPARATING THE TWO
That is the whole difficulty, and it has a clean test. Bin the pairs by how far
apart the two instants are:

  * if the difference is PRICE MOVEMENT, its median sits at zero and its spread
    grows with the gap.
  * if there is a real BASIS, the median is displaced and stays displaced as
    the bin tightens, while the spread shrinks.

A median that survives the tightest bin is a basis. A median that collapses
toward zero as the bin tightens was never one. This script prints both so the
reader can see which happened rather than being told.

WHAT IT CANNOT DO
It cannot reach zero gap. Kalshi settles every fifteen minutes and the
collector runs three times a day, so the nearest settlement is up to 450
seconds away. The tightest bin is what the archive happens to offer, and the
standard error printed beside each median says how much to trust it.

Usage:
    python scripts/measure_basis.py
    python scripts/measure_basis.py --json
"""
import json
import os
import sys
from datetime import datetime, timezone

from archive import snapshot, stamps, summary, Missing

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (Deribit currency, Kalshi fifteen-minute series). These are the only series
# that settle often enough to land near a snapshot.
PAIRS = [('BTC', 'KXBTC15M'), ('ETH', 'KXETH15M')]

# Seconds. The last one is half of Kalshi's fifteen-minute cadence, so it is
# the widest gap that can ever occur.
BINS = (60, 180, 450)


def index_read_instant(obj):
    """Deribit stamps its own response in microseconds. usIn is when the
    request arrived, which is as close to the index read as we can get."""
    us = obj.get('usIn') or obj.get('usOut')
    return us / 1e6 if us else None


def iso_epoch(s):
    if not s or len(s) < 19:
        return None
    try:
        return datetime(int(s[0:4]), int(s[5:7]), int(s[8:10]),
                        int(s[11:13]), int(s[14:16]), int(s[17:19]),
                        tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def number(v):
    """expiration_value is usually a price, sometimes 'Yes'/'No', sometimes a
    dollar-prefixed string. Only the numbers are of any use here."""
    if v is None:
        return None
    s = str(v).replace(',', '').replace('$', '').strip()
    try:
        x = float(s)
    except ValueError:
        return None
    return x if x > 0 else None


def settlements(KA, series):
    """Every settled market of one series as (close epoch, realised BRTI).

    De-duplicated by close time: all rungs of one fifteen-minute event settle
    on the SAME reading, so keeping more than one would weight that reading by
    how many rungs the ladder happened to have.
    """
    out = {}
    for m in (KA.get('markets', {}).get(series) or []):
        v = number(m.get('expiration_value'))
        t = iso_epoch(m.get('close_time'))
        if v is None or t is None:
            continue
        out[t] = v
    return sorted(out.items())


def collect(every):
    rows = []
    for stamp in every:
        try:
            g = snapshot(stamp)
            KA, DE = g.kalshi, g.deribit
        except Missing:
            continue
        for ccy, series in PAIRS:
            try:
                idx_obj = DE[ccy]['index']
                price = idx_obj['result']['index_price']
            except (KeyError, TypeError):
                continue
            t_idx = index_read_instant(idx_obj)
            if not t_idx or not price:
                continue
            best = None
            for t_k, brti in settlements(KA, series):
                d = abs(t_k - t_idx)
                if best is None or d < best[0]:
                    best = (d, t_k, brti)
            if not best or best[0] > max(BINS):
                continue
            gap, t_k, brti = best
            rows.append({
                'stamp': stamp, 'ccy': ccy, 'gap_s': round(gap, 1),
                'signed_gap_s': round(t_k - t_idx, 1),
                'brti': brti, 'deribit': price,
                # Positive means BRTI printed ABOVE the Deribit index.
                'basis_bp': (brti / price - 1.0) * 10000.0,
            })
    return rows


def stats(vals):
    if not vals:
        return None
    v = sorted(vals)
    n = len(v)
    med = v[n // 2]
    # Median absolute deviation, scaled to a normal standard deviation. Robust
    # here because a mispaired settlement shows up as one enormous outlier.
    mad = sorted(abs(x - med) for x in v)[n // 2] * 1.4826
    return {'n': n, 'median_bp': round(med, 2), 'spread_bp': round(mad, 2),
            'se_bp': round(mad / (n ** 0.5), 2) if n else None,
            'min_bp': round(v[0], 2), 'max_bp': round(v[-1], 2)}


def main():
    machine = '--json' in sys.argv[1:]
    every = stamps('_meta')
    o = summary()
    rows = collect(every)

    result = {'archive': o, 'produced_by': 'scripts/measure_basis.py',
              'pairs': len(rows), 'by_currency': {}, 'by_bin': {}}
    for ccy, _s in PAIRS:
        result['by_currency'][ccy] = stats([r['basis_bp'] for r in rows
                                            if r['ccy'] == ccy])
    for b in BINS:
        result['by_bin']['within_%ds' % b] = stats(
            [r['basis_bp'] for r in rows if r['gap_s'] <= b])

    folder = os.path.join(ROOT, 'findings')
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, 'settlement_basis.json'), 'w',
              encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    if machine:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0

    print('SETTLEMENT BASIS — BRTI against the Deribit index')
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days' % o)
    print('pairs: %d' % len(rows))
    print()
    print('%-14s %5s %11s %11s %9s %9s %9s'
          % ('bin', 'n', 'median bp', 'spread bp', 'se bp', 'min', 'max'))
    print('-' * 76)
    for b in BINS:
        s = result['by_bin']['within_%ds' % b]
        if not s:
            print('%-14s %5s' % ('within %ds' % b, '-'))
            continue
        print('%-14s %5d %11.2f %11.2f %9.2f %9.1f %9.1f'
              % ('within %ds' % b, s['n'], s['median_bp'], s['spread_bp'],
                 s['se_bp'], s['min_bp'], s['max_bp']))
    print()
    for ccy, _s in PAIRS:
        s = result['by_currency'][ccy]
        if s:
            print('%-5s n %-4d median %+.2f bp   spread %.2f bp   se %.2f bp'
                  % (ccy, s['n'], s['median_bp'], s['spread_bp'], s['se_bp']))
    print()
    print('Reading note: one basis point is 0.01%. The test is the SHAPE of the')
    print('table, not one row. Price movement between the two instants has a')
    print('median of zero and a spread that grows with the gap; a real basis')
    print('holds its median as the bin tightens while the spread falls. If the')
    print('median collapses toward zero in the tightest bin, there is no basis')
    print('to report and the wider rows were measuring BTC, not CF Benchmarks.')
    print()
    print('Against a tail threshold this matters in proportion. A basis of 5 bp')
    print('on an 87,000 index is about 43 dollars, which is a fraction of one')
    print('Deribit strike interval, so it could not move a digital far. A basis')
    print('of 50 bp would be another matter.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
