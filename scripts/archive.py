#!/usr/bin/env python3
"""Archive reader — the shared base for every measurement script.

Why it exists: the earlier measurement scripts read `raw/_store.json` and
`inventory/*.csv`. Neither is in the repository (404), so none of them ran.
The numbers they had produced were on screen with nothing able to reproduce
them. Found during an audit on 2026-09-11.

This module answers one question: how do we read a snapshot off disk.
Measurement scripts no longer fetch anything; they only compute. Raw data is
never rewritten, so the same snapshot always yields the same number.

Set DIVERGENCE_RAW to read a different archive root; see RAW below.

Usage:
    from archive import snapshot, stamps
    g = snapshot()                       # newest
    g = snapshot('2026-09-10T1312Z')     # a specific one
    g.kalshi, g.deribit, g.polymarket    # decompressed JSON
    g.stamp, g.day, g.meta, g.sync_window
"""
import gzip
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where the raw archive lives. Overridable so that a measurement can run against
# the private mirror, which holds every snapshot since 2026-08-30, instead of the
# 14-day rolling window the public repository keeps for data rights
# (docs/DATA_SOURCES.md). Everything in this module goes through RAW, so a single
# environment variable moves every measurement script at once.
#
# prune_archive.py deliberately does NOT import this. It computes its own RAW
# from its own location, so no environment variable can ever point the DELETER
# at the mirror. tests/test_measurement.py pins that separation.
RAW = os.environ.get('DIVERGENCE_RAW') or os.path.join(ROOT, 'raw')

STREAMS = {
    'kalshi': 'kalshi',
    'deribit': 'deribit',
    'polymarket': 'polymarket_events',
}


class Missing(Exception):
    """The requested snapshot or stream is not in the archive."""


def _gz(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def days(stream='_meta'):
    """Days present in the archive, oldest first."""
    p = os.path.join(RAW, STREAMS.get(stream, stream))
    if not os.path.isdir(p):
        return []
    return sorted(d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d)))


def stamps(stream='_meta'):
    """Every run stamp in the archive, oldest first."""
    root = os.path.join(RAW, STREAMS.get(stream, stream))
    out = []
    for d in days(stream):
        for name in sorted(os.listdir(os.path.join(root, d))):
            # meta_2026-09-13T0515Z.json / kalshi_2026-09-13T0515Z.json.gz
            stamp = name.split('_', 1)[-1].split('.')[0]
            if stamp:
                out.append(stamp)
    return sorted(set(out))


class Snapshot(object):
    """The three sources from a single run. Fields open on first access."""

    def __init__(self, stamp, day):
        self.stamp = stamp
        self.day = day
        self._cache = {}

    def _read(self, stream):
        if stream in self._cache:
            return self._cache[stream]
        folder = STREAMS[stream]
        path = os.path.join(RAW, folder, self.day,
                            '%s_%s.json.gz' % (folder, self.stamp))
        if not os.path.isfile(path):
            raise Missing('%s stream absent at %s: %s'
                          % (stream, self.stamp, os.path.relpath(path, ROOT)))
        self._cache[stream] = _gz(path)
        return self._cache[stream]

    @property
    def kalshi(self):
        return self._read('kalshi')

    @property
    def deribit(self):
        return self._read('deribit')

    @property
    def polymarket(self):
        return self._read('polymarket')

    @property
    def meta(self):
        if 'meta' not in self._cache:
            path = os.path.join(RAW, '_meta', self.day, 'meta_%s.json' % self.stamp)
            if not os.path.isfile(path):
                raise Missing('meta absent: %s' % self.stamp)
            with open(path, encoding='utf-8') as f:
                self._cache['meta'] = json.load(f)
        return self._cache['meta']

    @property
    def sync_window(self):
        """Seconds between reading the option chain and the prediction market.
        A difference smaller than what the price can move inside this window is
        timing noise, not a market view."""
        return self.meta.get('sync_window_seconds')

    def __repr__(self):
        return '<Snapshot %s>' % self.stamp


def snapshot(stamp=None):
    """Newest run if no stamp is given. Raises rather than guessing."""
    all_stamps = stamps('_meta')
    if not all_stamps:
        raise Missing('archive is empty: %s' % RAW)
    if stamp is None:
        stamp = all_stamps[-1]
    elif stamp not in all_stamps:
        raise Missing('%s not in archive. Newest is %s' % (stamp, all_stamps[-1]))
    return Snapshot(stamp, stamp.split('T')[0])


def summary():
    """State of the archive. Scripts print this so the reader can see which
    data produced the number."""
    s = stamps('_meta')
    return {
        'day_count': len(days('_meta')),
        'snapshot_count': len(s),
        'first': s[0] if s else None,
        'last': s[-1] if s else None,
    }


if __name__ == '__main__':
    # Smoke test: is the archive readable, do all three streams open?
    o = summary()
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days'
          '  (%(first)s .. %(last)s)' % o)
    g = snapshot()
    print('newest: %s' % g.stamp)
    for name in ('kalshi', 'deribit', 'polymarket'):
        try:
            v = getattr(g, name)
            info = ('%d top-level fields: %s' % (len(v), ', '.join(list(v)[:5]))
                    if isinstance(v, dict) else '%d records' % len(v))
            print('  %-12s OK   %s' % (name, info))
        except Exception as e:
            print('  %-12s FAIL %s' % (name, e))
            raise
    print('  sync window  %.2f s' % (g.sync_window or -1))
    print('\nthe archive read path works.')
