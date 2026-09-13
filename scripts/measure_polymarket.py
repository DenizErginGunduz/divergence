#!/usr/bin/env python3
"""Polymarket short-dated terminal ladders — the third independent setup.

WHY A SEPARATE MEASUREMENT
Seeing the same shape (the prediction market pricing the unlikely outcome
richer than the option chain) in three different setups is far stronger than
seeing it in one. The Kalshi year-end buckets and the long-horizon touch bound
are already measured; this script measures the third, Polymarket's daily
threshold ladders.

TOUCH / TERMINAL — THE MOST DELICATE POINT IN THIS SCRIPT
Two different question types sit side by side on Polymarket:

  "What price will Bitcoin hit in September?"     -> TOUCH  (path dependent)
  "Bitcoin above ___ on September 11?"            -> TERMINAL
  "Bitcoin price on September 11?"                -> TERMINAL (bucket)

The word "hit" asks about touching the level at ANY moment before expiry.
Touch probability is always greater than or equal to terminal probability at
the same level. Conflating them breaks the whole computation systematically.
This script EXCLUDES touch ladders explicitly and reports how many it dropped.

EXPIRY AND SETTLEMENT GAP — NOT HIDDEN
Polymarket daily ladders resolve at 16:00 UTC on the Binance BTC/USDT
one-minute candle close. Deribit options expire at 08:00 UTC on the Deribit
index. So:

  - time gap   : the option expiry is typically 8 hours EARLIER
  - source gap : Binance spot vs the Deribit index

Because the option expires earlier its implied distribution is NARROWER; the
digitals come out closer to 0 and 1 than they should. That is a bias which can
inflate the gap in our favour. So every row carries the gap in hours, and the
summary is split by how large the gap is.

Usage:
    python scripts/measure_polymarket.py
    python scripts/measure_polymarket.py --last 5
"""
import re
import sys

from archive import snapshot, stamps, summary, Missing
from measure_band import chain, forward, digital, MONTH
from stability import Stability

ASSETS = [('BTC', 'bitcoin', 'BTC'), ('ETH', 'ethereum', 'ETH')]

# "Bitcoin above ___ on September 11?" -> terminal threshold ladder
TERMINAL = re.compile(r'^(Bitcoin|Ethereum) above ___ on ', re.I)
# "What price will Bitcoin hit in 2026?" -> TOUCH, not comparable
TOUCH = re.compile(r'\bhit\b', re.I)

EXPIRY_LABEL = re.compile(r'^(\d+)([A-Z]{3})(\d{2})$')


def expiry_date(label):
    """Deribit expiry label -> (year, month, day). Expiries settle 08:00 UTC."""
    m = EXPIRY_LABEL.match(label)
    if not m:
        return None
    return (2000 + int(m.group(3)), MONTH[m.group(2)], int(m.group(1)))


def _day_number(y, mo, d):
    """Coarse day counter — only ever used for DIFFERENCES, so calendar
    accuracy is not required."""
    return y * 372 + mo * 31 + d


def parse_threshold(market):
    """Numeric threshold from groupItemTitle. '70,000' -> 70000.0"""
    raw = (market.get('groupItemTitle') or '').replace(',', '').replace('$', '').strip()
    m = re.search(r'\d+(?:\.\d+)?', raw)
    if not m:
        return None
    return float(m.group(0))


def ladder(event, ch, idx):
    """Every rung of one Polymarket terminal ladder."""
    M = [m for m in (event.get('markets') or []) if m.get('active') and not m.get('closed')]
    if len(M) < 3:
        return None

    end = (event.get('endDate') or '')[:10]
    if len(end) < 10:
        return None
    target = _day_number(int(end[:4]), int(end[5:7]), int(end[8:10]))

    # The expiry with the SMALLEST gap is chosen; its direction and size are
    # both reported.
    usable = []
    for v in ch:
        if not (ch[v].get('C') and ch[v].get('P')):
            continue
        ed = expiry_date(v)
        if not ed:
            continue
        usable.append((abs(_day_number(*ed) - target), _day_number(*ed) - target, v))
    if not usable:
        return None
    usable.sort()
    _, day_gap, expiry = usable[0]
    # Polymarket 16:00 UTC, Deribit 08:00 UTC -> same day means 8 hours earlier
    gap_hours = day_gap * 24 - 8

    F = forward(ch, expiry, idx)
    if not F:
        return None

    rows = []
    for m in M:
        K = parse_threshold(m)
        if K is None:
            continue
        bid, ask = m.get('bestBid'), m.get('bestAsk')
        if bid is None or ask is None:
            continue
        d = digital(ch, expiry, K, F, idx)
        if not d:
            rows.append({'K': K, 'skipped': 'outside the strike range'})
            continue
        pm = (float(bid) + float(ask)) / 2
        spread = float(ask) - float(bid)
        # Polymarket maker fee is treated as 0 (user's decision).
        friction = d['fee'] + spread / 2
        threshold = (0 if d['se'] is None else 1.96 * d['se']) + friction
        rows.append({'K': K, 'pm': pm, 'opt': d['p'], 'gap': pm - d['p'],
                     'threshold': threshold, 'spread': spread,
                     'exceeds': abs(pm - d['p']) > threshold})
    if not rows:
        return None
    return {'rows': rows, 'expiry': expiry, 'gap_hours': gap_hours,
            'title': event.get('title'), 'end': end}


def run(stamp):
    g = snapshot(stamp)
    PM, D = g.polymarket, g.deribit
    out = {'stamp': stamp, 'ladders': [], 'touch_excluded': 0}
    for asset, key, currency in ASSETS:
        try:
            ch, idx = chain(D, currency)
        except (KeyError, TypeError):
            continue
        for event in (PM.get(key) or []):
            title = event.get('title') or ''
            if TOUCH.search(title):
                out['touch_excluded'] += 1
                continue
            if not TERMINAL.match(title):
                continue
            try:
                h = ladder(event, ch, idx)
            except (KeyError, TypeError, ValueError):
                continue
            if h:
                h['asset'] = asset
                out['ladders'].append(h)
    return out


def main():
    argv = sys.argv[1:]
    last = int(argv[argv.index('--last') + 1]) if '--last' in argv else None
    every = stamps('_meta')
    if last:
        every = every[-last:]

    o = summary()
    stab = Stability()
    print('POLYMARKET TERMINAL LADDERS — third independent setup')
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days' % o)
    print()
    print('%-18s %-4s %-30s %5s %6s %s' %
          ('snapshot', 'ast', 'ladder', 'gap', 'over', '(over/measured)'))
    print('-' * 86)

    tot_over = tot_measured = 0
    near_over = near_measured = 0      # ladders with a gap of 12h or less
    touch_excluded = 0
    shown = 0

    for stamp in every:
        try:
            s = run(stamp)
        except Missing:
            continue
        touch_excluded += s['touch_excluded']
        for h in s['ladders']:
            measured = [r for r in h['rows'] if 'opt' in r]
            if not measured:
                continue
            over = sum(1 for r in measured if r['exceeds'])
            for r in measured:
                # identity: asset + ladder expiry + threshold. Daily ladders are
                # replaced every day, so most rungs are observed only a few
                # times; the stability summary shows that as it is.
                stab.add('%s:%s:%g' % (h['asset'], h['end'], r['K']), r['exceeds'])
            tot_over += over
            tot_measured += len(measured)
            if abs(h['gap_hours']) <= 12:
                near_over += over
                near_measured += len(measured)
            if shown < 24:      # a sample, without flooding the log
                print('%-18s %-4s %-30s %+5dh %6s %d/%d' %
                      (stamp, h['asset'], (h['title'] or '')[:30],
                       h['gap_hours'], '', over, len(measured)))
                shown += 1

    print('-' * 86)
    print()
    print('TOTAL      : %d / %d rung-observations cleared the band'
          % (tot_over, tot_measured))
    if tot_measured:
        print('             %.1f%%' % (100.0 * tot_over / tot_measured))
    print('GAP <= 12h : %d / %d' % (near_over, near_measured))
    if near_measured:
        print('             %.1f%%  <- still the same with a small expiry gap?'
              % (100.0 * near_over / near_measured))
    stab.report('STABILITY — Polymarket daily thresholds')
    print()
    print('touch ladders excluded: %d  ("hit" questions are NOT terminal)'
          % touch_excluded)
    print()
    print('CAVEAT: Polymarket settles at 16:00 UTC on the Binance BTC-USDT')
    print('close, Deribit at 08:00 UTC on its own index. Both the time and the')
    print('source differ. The option expires earlier, so its distribution comes')
    print('out narrower and the gap can inflate IN OUR FAVOUR. This number is')
    print('a measure of comparability, not a count of opportunities.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
