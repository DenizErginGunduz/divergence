#!/usr/bin/env python3
"""Validation inventory — how much can actually be scored, and how much of that
is independent?

THE QUESTION BEHIND IT
Everything measured so far compares two PRICES. None of it says whether either
price was any good, and nothing here will until contracts resolve and the
forecasts are scored against outcomes. Before writing a scoring routine the
honest first step is to count the sample: a Brier score over a sample that
turns out to be one independent draw is a decoration.

THREE COUNTS, AND THE GAP BETWEEN THEM IS THE POINT
  observations  — every (market, snapshot) pair with a live two-sided quote
                  whose market later resolved. The number a naive script would
                  report, and the largest.
  markets       — distinct resolved markets with at least one such quote.
  events        — distinct Kalshi events. Every rung of one event resolves from
                  ONE reading of ONE price, so a 44-rung ladder is one draw and
                  not 44. This is the number that governs a standard error.

WHAT THIS SCRIPT DOES NOT DO
It does not score anything. It counts, and it prints the lead time between the
last quote and settlement, because a forecast made a minute before expiry and
one made a month before are not the same forecast and should not be pooled.

A BOUND WORTH STATING
The public archive is a 14-day rolling window, kept that way for data rights
(docs/DATA_SOURCES.md). The private mirror holds everything since 2026-08-30
and is not read here. So every number below is a LOWER BOUND on what exists,
and the ratio between this window and the mirror is roughly the factor by which
the real sample is larger.

Usage:
    python scripts/inventory_validation.py
    python scripts/inventory_validation.py --json
"""
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

from archive import snapshot, stamps, summary, Missing

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The seven-asset universe is BTC and ETH for now. Counting series we do not
# price would inflate the sample with markets nothing in this repository
# forecasts.
PREFIXES = ('KXBTC', 'KXETH', 'BTC', 'ETH')

RESOLVED = ('yes', 'no')


def stamp_dt(stamp):
    """'2026-09-15T0505Z' -> datetime. The archive's own stamp format."""
    try:
        return datetime(int(stamp[0:4]), int(stamp[5:7]), int(stamp[8:10]),
                        int(stamp[11:13]), int(stamp[13:15]), tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None


def iso_dt(s):
    if not s or len(s) < 19:
        return None
    try:
        return datetime(int(s[0:4]), int(s[5:7]), int(s[8:10]),
                        int(s[11:13]), int(s[14:16]), int(s[17:19]),
                        tzinfo=timezone.utc)
    except ValueError:
        return None


def collect(every):
    """One pass over the archive. ticker -> quotes seen while live, plus the
    outcome if the market resolved inside the window."""
    seen = {}
    absent = 0
    for stamp in every:
        try:
            g = snapshot(stamp)
            KA = g.kalshi
        except Missing:
            absent += 1
            continue
        for series, markets in (KA.get('markets') or {}).items():
            if not series.startswith(PREFIXES):
                continue
            for m in (markets or []):
                ticker = m.get('ticker')
                if not ticker:
                    continue
                rec = seen.get(ticker)
                if rec is None:
                    rec = seen[ticker] = {
                        'series': series, 'event': m.get('event_ticker'),
                        'close': m.get('close_time'), 'obs': [],
                        'result': '', 'resolved_at': None,
                        'value': m.get('expiration_value'),
                    }
                result = (m.get('result') or '').strip().lower()
                if result in RESOLVED:
                    if not rec['result']:
                        rec['result'] = result
                        rec['resolved_at'] = stamp
                        rec['value'] = m.get('expiration_value')
                    continue
                if m.get('status') not in ('active', 'open'):
                    continue
                try:
                    bid = float(m['yes_bid_dollars'])
                    ask = float(m['yes_ask_dollars'])
                except (KeyError, TypeError, ValueError):
                    continue
                # No offer means nobody would sell it to you. That is not a
                # forecast and must not be scored as one.
                if ask <= 0:
                    continue
                rec['obs'].append((stamp, bid, ask))
    return seen, absent


def main():
    argv = sys.argv[1:]
    machine = '--json' in argv
    every = stamps('_meta')
    o = summary()
    seen, absent = collect(every)

    pairs = []          # (ticker, rec) with an outcome AND at least one quote
    for ticker, rec in seen.items():
        if rec['result'] in RESOLVED and rec['obs']:
            pairs.append((ticker, rec))

    observations = sum(len(r['obs']) for _t, r in pairs)
    events = {r['event'] for _t, r in pairs if r['event']}
    by_series = Counter(r['series'] for _t, r in pairs)
    obs_by_series = Counter()
    for _t, r in pairs:
        obs_by_series[r['series']] += len(r['obs'])
    outcomes = Counter(r['result'] for _t, r in pairs)

    # Lead time from each quote to the market's close, in hours.
    leads = []
    for _t, r in pairs:
        close = iso_dt(r['close'])
        if not close:
            continue
        for stamp, _b, _a in r['obs']:
            d = stamp_dt(stamp)
            if d:
                leads.append((close - d).total_seconds() / 3600.0)
    leads.sort()

    def q(p):
        return leads[int(p * (len(leads) - 1))] if leads else None

    result = {
        'archive': o,
        'produced_by': 'scripts/inventory_validation.py',
        'bound': ('The public archive is a 14-day rolling window. These are '
                  'LOWER BOUNDS; the private mirror holds everything since '
                  '2026-08-30 and is not read here.'),
        'resolved_markets_seen': sum(1 for r in seen.values() if r['result'] in RESOLVED),
        'markets_with_a_prior_quote': len(pairs),
        'scorable_observations': observations,
        'independent_events': len(events),
        'observations_per_independent_event':
            round(observations / len(events), 1) if events else None,
        'outcomes': dict(outcomes),
        'by_series': dict(by_series.most_common()),
        'observations_by_series': dict(obs_by_series.most_common()),
        'lead_hours': {
            'min': round(leads[0], 2) if leads else None,
            'p25': round(q(.25), 2) if leads else None,
            'median': round(q(.5), 2) if leads else None,
            'p75': round(q(.75), 2) if leads else None,
            'max': round(leads[-1], 2) if leads else None,
        },
        'snapshots_without_kalshi': absent,
    }

    folder = os.path.join(ROOT, 'findings')
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, 'validation_inventory.json'), 'w',
              encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    if machine:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0

    print('VALIDATION INVENTORY — what could be scored, and how much is independent')
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days' % o)
    if absent:
        print('skipped: %d snapshots with no Kalshi stream' % absent)
    print()
    print('resolved markets seen            %8d' % result['resolved_markets_seen'])
    print('  of those, with a prior quote   %8d' % result['markets_with_a_prior_quote'])
    print('scorable observations            %8d' % observations)
    print('INDEPENDENT events               %8d' % len(events))
    if events:
        print('  observations per event         %8.1f' %
              result['observations_per_independent_event'])
    print()
    print('outcomes: %s' % ', '.join('%s %d' % kv for kv in outcomes.most_common()))
    print()
    print('%-16s %10s %14s' % ('series', 'markets', 'observations'))
    print('-' * 44)
    for s, n in by_series.most_common(12):
        print('%-16s %10d %14d' % (s, n, obs_by_series[s]))
    print()
    if leads:
        print('lead time from quote to close, hours:')
        print('  min %.2f   p25 %.2f   median %.2f   p75 %.2f   max %.2f' % (
            leads[0], q(.25), q(.5), q(.75), leads[-1]))
        print('  A quote taken minutes before settlement and one taken days')
        print('  before are not the same forecast. Scoring must not pool them.')
    print()
    print('Reading note: the three counts fall away fast, and that fall IS the')
    print('finding. Every rung of one event resolves from ONE reading of ONE')
    print('price, so the event count is what governs a standard error. A Brier')
    print('score quoted over the observation count would overstate its own')
    print('precision by the ratio printed above.')
    print()
    print('These are LOWER BOUNDS. The public window is 14 days by a data-rights')
    print('decision (docs/DATA_SOURCES.md); the private mirror has held every')
    print('snapshot since 2026-08-30 and is not read here.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
