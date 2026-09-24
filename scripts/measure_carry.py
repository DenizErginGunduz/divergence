#!/usr/bin/env python3
"""measure_carry.py — what holding a linear position has cost, per venue (D-119).

Reads raw/carry/ (archive version 7+) and writes findings/carry.json:

  perpetuals  Hyperliquid (first dex and trade[XYZ]) and Polymarket's perpetuals.
              Hourly funding points, de-duplicated on time across every file, then
              the mean hourly rate over the last 24 and 168 hours ending at the
              newest point, and what a $1,000 long pays at that mean per day and per
              week. A window with fewer than 90% of its hours present is UNKNOWN.
  futures     Deribit's dated futures at the newest snapshot: mark over index minus
              one, days to expiry, that premium per $1,000 and annualised.

Units, as read in D-119: both venues return the HOURLY rate as a fraction; a
positive rate means the long pays and the short receives. Deribit's own perpetual
funding is not read here: its unit is still UNKNOWN (D-111).

These describe what was charged. They are not forecasts of what will be charged.
"""
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import archive  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'findings', 'carry.json')

HOUR_MS = 3600 * 1000
WINDOWS = (24, 168)
MIN_COVERAGE = 0.9          # the same 90% as D-114's persistence
NOTIONAL = 1000.0

# Which instrument tracks which underlying, for the card. Venue names are ours.
UNDERLYING = {
    ('hyperliquid', 'BTC'): 'BTC', ('hyperliquid', 'ETH'): 'ETH',
    ('hyperliquid', 'xyz:CL'): 'WTI', ('hyperliquid', 'xyz:BRENTOIL'): 'BRENT',
    ('hyperliquid', 'xyz:GOLD'): 'GOLD', ('hyperliquid', 'xyz:SILVER'): 'SILVER',
    ('hyperliquid', 'xyz:SP500'): 'SPX', ('hyperliquid', 'xyz:XYZ100'): 'NDX-like',
    ('polymarket', 'BTC-USD'): 'BTC', ('polymarket', 'ETH-USD'): 'ETH',
    ('polymarket', 'WTIOIL-USD'): 'WTI', ('polymarket', 'BRENTOIL-USD'): 'BRENT',
    ('polymarket', 'GOLD-USD'): 'GOLD', ('polymarket', 'SILVER-USD'): 'SILVER',
    ('polymarket', 'SP500-USD'): 'SPX',
}


# ---------------- pure functions (tested) ----------------
def hour_of(ms):
    """Floor a millisecond instant to its hour. Hyperliquid stamps land a few
    milliseconds after the hour (1790186400074), so equality on raw ms would split
    one hour into two."""
    return int(ms) // HOUR_MS * HOUR_MS


def merge_points(batches):
    """batches: lists of (ms, rate) in file order, oldest file first. Returns
    ({hour: rate}, disagreements). A later file wins, and every hour two files
    report differently is counted, because the archive never says a venue revised
    a value — the counter does."""
    series, disagree = {}, 0
    for batch in batches:
        for ms, rate in batch:
            h = hour_of(ms)
            if h in series and series[h] != rate:
                disagree += 1
            series[h] = rate
    return series, disagree


def window_mean(series, end_hour, hours, min_coverage=MIN_COVERAGE):
    """Mean hourly rate over the `hours` hours ending at end_hour (inclusive), or
    None when fewer than min_coverage of them are present."""
    want = [end_hour - i * HOUR_MS for i in range(hours)]
    got = [series[h] for h in want if h in series]
    coverage = len(got) / float(hours)
    if not got or coverage < min_coverage:
        return None, coverage
    return sum(got) / len(got), coverage


def long_pays(mean_hourly, hours, notional=NOTIONAL):
    """What a long of `notional` pays over `hours` at a constant notional. Negative
    means the long receives."""
    if mean_hourly is None:
        return None
    return notional * mean_hourly * hours


def futures_premium(mark, index, expiry_ms, now_ms, notional=NOTIONAL):
    """Premium of a dated future over the index: as a fraction, per `notional`,
    and annualised over the days left. None where an input is missing or the
    contract has expired."""
    if not mark or not index or not expiry_ms:
        return None
    days = (expiry_ms - now_ms) / (24.0 * HOUR_MS)
    if days <= 0:
        return None
    prem = mark / float(index) - 1.0
    return {'premium': prem, 'per_1000': notional * prem, 'days': days,
            'annualised': prem * 365.0 / days}


# ---------------- reading the archive ----------------
def _gz(p):
    with gzip.open(p, 'rt', encoding='utf-8') as f:
        return json.load(f)


def carry_files():
    base = os.path.join(archive.RAW, 'carry')
    out = []
    if not os.path.isdir(base):
        return out
    for d in sorted(os.listdir(base)):
        dp = os.path.join(base, d)
        if os.path.isdir(dp):
            out += [os.path.join(dp, f) for f in sorted(os.listdir(dp)) if f.endswith('.json.gz')]
    return out


def _hl_rows(block):
    r = block.get('response') or {}
    if not r.get('ok') or not isinstance(r.get('value'), list):
        return []
    return [(int(x['time']), float(x['fundingRate'])) for x in r['value']
            if x.get('time') is not None and x.get('fundingRate') is not None]


def _poly_rows(pages):
    rows = []
    for p in pages:
        r = p.get('response') or {}
        v = r.get('value') if r.get('ok') else None
        for x in ((v or {}).get('data') or []) if isinstance(v, dict) else []:
            if x.get('timestamp') is not None and x.get('funding_rate') is not None:
                rows.append((int(x['timestamp']), float(x['funding_rate'])))
    return rows


def _hl_context(doc):
    """Newest context per coin: mark, oracle, open interest, day notional volume."""
    out = {}
    for dex, blk in ((doc.get('hyperliquid') or {}).get('ctx') or {}).items():
        r = blk.get('response') or {}
        v = r.get('value') if r.get('ok') else None
        if not (isinstance(v, list) and len(v) == 2):
            continue
        for u, c in zip((v[0] or {}).get('universe') or [], v[1] or []):
            out[u.get('name')] = {k: c.get(k) for k in
                                  ('markPx', 'oraclePx', 'openInterest', 'dayNtlVlm', 'funding')}
    return out


def _poly_context(doc):
    t = ((doc.get('polymarket_perps') or {}).get('tickers') or {})
    v = t.get('value') if t.get('ok') else None
    return dict((x.get('symbol'), {k: x.get(k) for k in
                                   ('index_price', 'mark_price', 'open_interest', 'funding_rate')})
                for x in (v or []) if isinstance(x, dict))


def _futures(doc, now_ms):
    out = {}
    for cur, blk in (doc.get('deribit_futures') or {}).items():
        bs, ins, idx = blk.get('book_summary') or {}, blk.get('instruments') or {}, blk.get('index') or {}
        if not (bs.get('ok') and ins.get('ok') and idx.get('ok')):
            out[cur] = {'error': 'a Deribit call failed in the newest snapshot'}
            continue
        index = ((idx['value'] or {}).get('result') or {}).get('index_price')
        expiry = dict((i.get('instrument_name'), i.get('expiration_timestamp'))
                      for i in (ins['value'] or {}).get('result') or [])
        for row in (bs['value'] or {}).get('result') or []:
            name = row.get('instrument_name')
            if not name or name.endswith('PERPETUAL'):
                continue
            p = futures_premium(row.get('mark_price'), index, expiry.get(name), now_ms)
            out[name] = {'underlying': cur, 'mark': row.get('mark_price'), 'index': index,
                         'expiry_ms': expiry.get(name), 'volume_usd': row.get('volume_usd'),
                         'open_interest': row.get('open_interest'), 'premium': p}
    return out


def run(files):
    batches = {}
    newest = None
    for f in files:
        try:
            doc = _gz(f)
        except Exception:
            continue
        newest = (f, doc)
        for coin, blk in ((doc.get('hyperliquid') or {}).get('funding') or {}).items():
            batches.setdefault(('hyperliquid', coin), []).append(_hl_rows(blk))
        for sym, pages in ((doc.get('polymarket_perps') or {}).get('funding') or {}).items():
            batches.setdefault(('polymarket', sym), []).append(_poly_rows(pages))
    perps = {}
    for key, bs in sorted(batches.items()):
        series, disagree = merge_points(bs)
        if not series:
            perps['%s:%s' % key] = {'venue': key[0], 'instrument': key[1], 'points': 0}
            continue
        end = max(series)
        rec = {'venue': key[0], 'instrument': key[1],
               'underlying': UNDERLYING.get(key, 'UNKNOWN'),
               'rate_unit': 'fraction per hour; positive = long pays (D-119)',
               'points': len(series), 'first_hour_ms': min(series), 'last_hour_ms': end,
               'disagreements': disagree, 'last_rate': series[end], 'windows': {}}
        for w in WINDOWS:
            m, cov = window_mean(series, end, w)
            rec['windows']['%dh' % w] = {
                'mean_hourly': m, 'coverage': round(cov, 4),
                'long_pays_per_1000_per_day': long_pays(m, 24),
                'long_pays_per_1000_per_week': long_pays(m, 168),
            }
        last = [series[h] for h in series if h > end - 168 * HOUR_MS]
        rec['share_positive_168h'] = sum(1 for x in last if x > 0) / float(len(last))
        rec['min_hourly_168h'], rec['max_hourly_168h'] = min(last), max(last)
        perps['%s:%s' % key] = rec
    ctx = {}
    futures = {}
    stamp = None
    if newest:
        f, doc = newest
        stamp = os.path.basename(f)[len('carry_'):-len('.json.gz')]
        now_ms = (doc.get('window') or {}).get('end_ms')
        hl, pc = _hl_context(doc), _poly_context(doc)
        for k, rec in perps.items():
            src = hl if rec['venue'] == 'hyperliquid' else pc
            ctx[k] = src.get(rec['instrument'])
        futures = _futures(doc, now_ms) if now_ms else {}
    for k, c in ctx.items():
        perps[k]['context_newest_snapshot'] = c
    return {'produced_by': 'scripts/measure_carry.py', 'decision': 'D-119',
            'archive': archive.RAW, 'files_read': len(files), 'newest_stamp': stamp,
            'perpetuals': perps, 'futures': futures,
            'not_measured': {'deribit_perpetual_funding': 'UNKNOWN unit (D-111)',
                             'binance': 'parked (B-028)'}}


def main():
    res = run(carry_files())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print('carry: %d files, newest %s, %d perpetuals, %d futures'
          % (res['files_read'], res['newest_stamp'], len(res['perpetuals']), len(res['futures'])))
    for k, r in res['perpetuals'].items():
        w = (r.get('windows') or {}).get('168h') or {}
        print('  %-28s points %4s  week/$1000 long pays %s'
              % (k, r.get('points'), w.get('long_pays_per_1000_per_week')))


if __name__ == '__main__':
    main()
