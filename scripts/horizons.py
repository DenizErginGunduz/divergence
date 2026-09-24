#!/usr/bin/env python3
"""horizons.py — on which dates does something settle, per asset and per family (D-120).

Reads the newest snapshot of each stream and writes findings/horizons.json:

  for each asset (BTC, ETH, WTI, BRENT, GOLD, SILVER, SPX) and each family
  (terminal prediction ladders, touch markets, options, perpetuals), the dates on
  which an instrument settles, with where it was found and how many markets.

It also carries the horizon rule, so a reader never re-implements it: for a view
h days away, a dated instrument qualifies if it settles within
max(1 day, 30% of h) of the horizon, and its offset is always shown. Perpetuals
have no date and match every horizon, carried by the funding means (D-119).

This script lists what exists. It prices nothing and judges nothing.
"""
import datetime
import gzip
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import archive  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'findings', 'horizons.json')

DAY_MS = 24 * 3600 * 1000
MIN_WINDOW_DAYS = 1.0
WINDOW_SHARE = 0.30
ASSETS = ('BTC', 'ETH', 'WTI', 'BRENT', 'GOLD', 'SILVER', 'SPX')

# Kalshi series by asset and kind. Terminal: a price at a time. Touch: a high or low
# reached before a time. Anything not listed here is not a price ladder on our assets.
KALSHI_TERMINAL = {
    'BTC': r'^KXBTC(D|Y)?$', 'ETH': r'^KXETH(D|Y)?$',
    'WTI': r'^KXWTI(W|MONTHLY)?$', 'BRENT': r'^KXBRENT(D|W|MON)$',
    'GOLD': r'^KXGOLD(D|W|MON)$', 'SILVER': r'^KXSILVER(D|W|MON)$',
    'SPX': r'^KXINX(U)?$',
}
KALSHI_TOUCH = {
    'BTC': r'^KXBTC(MAX|MIN)(W|MON|Y)$', 'ETH': r'^KXETH(MAX|MIN)(W|MON|Y)$',
    'WTI': r'^KXWTI(MAX|MIN)M?$', 'BRENT': r'^$', 'GOLD': r'^$', 'SILVER': r'^$',
    'SPX': r'^KXINXMAXY$',
}
# Polymarket titles -> asset. Terminal: "above ___ on", "price on", "closes above",
# "close at end of". Touch: "hit". Up/Down is neither and is left out.
POLY_ASSET = [('BTC', r'\bBitcoin\b'), ('ETH', r'\bEthereum\b'), ('WTI', r'\bWTI\b|Crude Oil \(CL\)'),
              ('GOLD', r'\bGold\b'), ('SILVER', r'\bSilver\b'), ('SPX', r'S&P 500|\bSPX\b')]
POLY_TERMINAL = r'above ___ on|price on|closes? above|close at end of'
POLY_NOT_A_PRICE = r'Volatility|Dominance|ETF|\bvs\.?\b|\bgas\b|reserves|all time high'
POLY_TOUCH = r'\bhit\b'
HIP4_ASSET = {'BTC': 'BTC', 'ETH': 'ETH', 'xyz:CL': 'WTI', 'xyz:BRENTOIL': 'BRENT',
              'xyz:GOLD': 'GOLD', 'xyz:SILVER': 'SILVER', 'xyz:SP500': 'SPX'}
MONTHS = dict((m, i + 1) for i, m in enumerate(
    ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']))


# ---------------- the rule (tested) ----------------
def window_days(horizon_days):
    """How far from the horizon a dated instrument may settle and still be offered."""
    return max(MIN_WINDOW_DAYS, WINDOW_SHARE * max(0.0, horizon_days))


def matches(dates_ms, target_ms, now_ms):
    """Dated instruments within the window of a horizon, nearest first, each with its
    offset in days (negative = settles before the horizon). Nothing outside the
    window is returned, and nothing is substituted."""
    h = (target_ms - now_ms) / float(DAY_MS)
    w = window_days(h)
    out = []
    for d in sorted(set(dates_ms)):
        if d <= now_ms:
            continue
        off = (d - target_ms) / float(DAY_MS)
        if abs(off) <= w + 1e-9:
            out.append({'settles_ms': d, 'offset_days': round(off, 3)})
    return sorted(out, key=lambda x: (abs(x['offset_days']), x['offset_days']))


def deribit_expiry_ms(code):
    """'2OCT26' -> 08:00 UTC that day, the hour D-117 uses for Deribit expiries."""
    m = re.match(r'^(\d{1,2})([A-Z]{3})(\d{2})$', code or '')
    if not m or m.group(2) not in MONTHS:
        return None
    d = datetime.datetime(2000 + int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)), 8,
                          tzinfo=datetime.timezone.utc)
    return int(d.timestamp() * 1000)


def iso_ms(s):
    if not s:
        return None
    try:
        return int(datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp() * 1000)
    except ValueError:
        return None


def hip4_time_ms(t):
    """'20261001-0000' -> ms, read as UTC (the stamp carries no zone; D-120 reads it
    as UTC until the HIP-4 documentation says otherwise)."""
    try:
        d = datetime.datetime.strptime(t, '%Y%m%d-%H%M').replace(tzinfo=datetime.timezone.utc)
    except (TypeError, ValueError):
        return None
    return int(d.timestamp() * 1000)


# ---------------- reading the newest snapshot of each stream ----------------
def newest(stream):
    base = os.path.join(archive.RAW, stream)
    if not os.path.isdir(base):
        return None, None
    for d in sorted(os.listdir(base), reverse=True):
        dp = os.path.join(base, d)
        files = sorted(f for f in os.listdir(dp) if f.endswith('.json.gz')) if os.path.isdir(dp) else []
        if files:
            p = os.path.join(dp, files[-1])
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                return json.load(f), files[-1]
    return None, None


def add(table, asset, family, ms, source, what):
    if asset not in table or ms is None:
        return
    key = (ms, source, what)
    fam = table[asset].setdefault(family, {})
    fam[key] = fam.get(key, 0) + 1


def collect(now_ms):
    table = dict((a, {}) for a in ASSETS)
    stamps = {}
    der, stamps['deribit'] = newest('deribit')
    for cur in ('BTC', 'ETH'):
        rows = ((der or {}).get(cur) or {}).get('book_summary')
        rows = rows.get('result', rows) if isinstance(rows, dict) else rows
        for r in rows or []:
            parts = (r.get('instrument_name') or '').split('-')
            if len(parts) == 4:
                add(table, cur, 'options', deribit_expiry_ms(parts[1]), 'Deribit', 'option chain ' + parts[1])
    kal, stamps['kalshi'] = newest('kalshi')
    for grp in ('markets', 'observed', 'commodities'):
        for series, ms in ((kal or {}).get(grp) or {}).items():
            if not isinstance(ms, list):
                continue
            for a in ASSETS:
                fam = ('prediction_terminal' if re.match(KALSHI_TERMINAL[a], series)
                       else ('touch' if re.match(KALSHI_TOUCH[a], series) else None))
                if not fam:
                    continue
                for m in ms:
                    t = iso_ms(m.get('close_time'))
                    if t and t > now_ms and m.get('status') in ('active', 'open'):
                        add(table, a, fam, t, 'Kalshi', series)
    for stream in ('polymarket_events', 'polymarket_other'):
        doc, stamps[stream] = newest(stream)
        for key, evs in (doc or {}).items():
            if isinstance(evs, dict):                   # polymarket_other wraps as ok/value
                evs = evs.get('value') if evs.get('ok') else None
            for e in evs or []:
                if e.get('closed'):
                    continue
                title = e.get('title') or ''
                a = next((x for x, pat in POLY_ASSET if re.search(pat, title)), None)
                fam = ('prediction_terminal' if re.search(POLY_TERMINAL, title, re.I)
                       else ('touch' if re.search(POLY_TOUCH, title, re.I) else None))
                t = iso_ms(e.get('endDate'))
                if re.search(POLY_NOT_A_PRICE, title, re.I):
                    continue
                if a and fam and t and t > now_ms:
                    add(table, a, fam, t, 'Polymarket', title[:60])
    hl, stamps['hip4'] = newest('hip4')
    meta = ((hl or {}).get('outcomeMeta') or {})
    meta = meta.get('value') if meta.get('ok') else None
    for o in ((meta or {}).get('outcomes') or []) if isinstance(meta, dict) else []:
        f = dict(p.partition(':')[::2] for p in (o.get('description') or '').split('|') if p)
        a = HIP4_ASSET.get(f.get('perp'))
        t = hip4_time_ms(f.get('time'))
        if not a or not t or t <= now_ms:
            continue
        fam = {'template:binaryPrice': 'prediction_terminal', 'template:priceTouch': 'touch'}.get(o.get('name'))
        if fam:
            add(table, a, fam, t, 'Hyperliquid HIP-4', o.get('name').split(':')[-1])
    out = {}
    for a, fams in table.items():
        out[a] = {}
        for fam, rows in fams.items():
            out[a][fam] = [{'settles_ms': ms, 'source': src, 'what': what, 'markets': n}
                           for (ms, src, what), n in sorted(rows.items())]
        out[a]['perpetual'] = 'every horizon (funding means, D-119)'
    return out, stamps


def main():
    now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    table, stamps = collect(now_ms)
    res = {'produced_by': 'scripts/horizons.py', 'decision': 'D-120', 'archive': archive.RAW,
           'computed_at_ms': now_ms, 'newest_files': stamps,
           'rule': {'min_window_days': MIN_WINDOW_DAYS, 'window_share': WINDOW_SHARE,
                    'text': 'a dated instrument qualifies if it settles within max(1 day, 30% of the '
                            'horizon) of it; the offset is always shown; nothing outside is offered'},
           'assets': table}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for a, fams in table.items():
        print('%-7s %s' % (a, ', '.join('%s %d dates' % (k, len(v)) for k, v in fams.items() if isinstance(v, list))))


if __name__ == '__main__':
    main()
