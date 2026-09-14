#!/usr/bin/env python3
"""Regression tests. Every case here pins a bug that actually happened.

The tests are not invented from the code's shape; each one names the decision
record whose mistake it prevents from coming back. If a test fails, read that
record first — it explains what the wrong answer looked like and why it was
convincing at the time.

Standard library only (unittest), like everything else in this repository.
Synthetic chains throughout: no test reads the archive, so they are fast and
give the same answer on an empty checkout.

    python -m unittest discover -s tests -v
"""
import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

import measure_band
import measure_exhaustive
import measure_touch
import prune_archive
from stability import Stability


# --------------------------------------------------------------------------
# A synthetic Deribit chain where put-call parity holds exactly, so the forward
# is 100,000 at every strike and the digitals can be worked out by hand.
#
#   K=90,000   C=0.15 BTC  P=0.05 BTC   ->  F = 90,000 + 15,000 -  5,000
#   K=100,000  C=0.08 BTC  P=0.08 BTC   ->  F = 100,000 + 8,000 -  8,000
#   K=110,000  C=0.04 BTC  P=0.14 BTC   ->  F = 110,000 + 4,000 - 14,000
#
# Prices are quoted in units of the underlying because Deribit options on BTC
# and ETH are inverse contracts. That is the trap ARCHIVE_SCHEMA.md calls "the
# one thing that will bite you": skip the multiplication and every number is
# wrong by a factor of about 100,000 while still looking plausible in a ratio.
INDEX = 100000.0
EXPIRY = '25DEC26'


def quote(name, mark, bid, ask):
    return {'instrument_name': name, 'mark_price': mark,
            'bid_price': bid, 'ask_price': ask}


def build(calls=True, puts=True):
    rows = []
    spec = {90000: (0.15, 0.05), 100000: (0.08, 0.08), 110000: (0.04, 0.14)}
    for k, (c, p) in spec.items():
        if calls:
            rows.append(quote('BTC-%s-%d-C' % (EXPIRY, k), c, c * 0.98, c * 1.02))
        if puts:
            rows.append(quote('BTC-%s-%d-P' % (EXPIRY, k), p, p * 0.98, p * 1.02))
    return {'BTC': {'book_summary': {'result': rows},
                    'index': {'result': {'index_price': INDEX}}}}


class InverseContracts(unittest.TestCase):
    """ARCHIVE_SCHEMA.md — prices are in units of the underlying."""

    def test_marks_are_converted_to_dollars(self):
        ch, idx = measure_band.chain(build(), 'BTC')
        self.assertEqual(idx, INDEX)
        # 0.08 BTC at an index of 100,000 is 8,000 dollars, not 0.08.
        self.assertAlmostEqual(ch[EXPIRY]['C'][100000.0]['mark'], 8000.0, places=6)
        self.assertAlmostEqual(ch[EXPIRY]['P'][90000.0]['mark'], 5000.0, places=6)


class ForwardFromParity(unittest.TestCase):
    """D-036 — the forward comes out of the chain, no futures feed needed."""

    def test_forward_is_the_median_of_the_parity_estimates(self):
        ch, idx = measure_band.chain(build(), 'BTC')
        self.assertAlmostEqual(measure_band.forward(ch, EXPIRY, idx), 100000.0, places=6)

    def test_a_single_broken_quote_does_not_move_it(self):
        d = build()
        # One absurd call mark. The median must ignore it; a mean would not.
        d['BTC']['book_summary']['result'].append(
            quote('BTC-%s-95000-C' % EXPIRY, 99.0, 98.0, 100.0))
        d['BTC']['book_summary']['result'].append(
            quote('BTC-%s-95000-P' % EXPIRY, 0.01, 0.009, 0.011))
        ch, idx = measure_band.chain(d, 'BTC')
        self.assertAlmostEqual(measure_band.forward(ch, EXPIRY, idx), 100000.0, places=6)


class DigitalSideSelection(unittest.TestCase):
    """D-025, D-032, D-035 — the deep ITM call trap, twice.

    Below the forward the digital must come from PUTS. Reading it off deep ITM
    calls means taking a small difference between two large numbers; the
    measured error reached a factor of 2.09.
    """

    def test_upside_uses_calls_and_matches_the_hand_computation(self):
        ch, idx = measure_band.chain(build(), 'BTC')
        d = measure_band.digital(ch, EXPIRY, 105000.0, 100000.0, idx)
        # (8000 - 4000) / 10000
        self.assertAlmostEqual(d['p'], 0.4, places=6)

    def test_downside_uses_puts_and_matches_the_hand_computation(self):
        ch, idx = measure_band.chain(build(), 'BTC')
        d = measure_band.digital(ch, EXPIRY, 95000.0, 100000.0, idx)
        # 1 - (8000 - 5000) / 10000
        self.assertAlmostEqual(d['p'], 0.7, places=6)

    def test_no_put_chain_means_no_downside_number(self):
        """The rule from D-032: with no puts, produce nothing. Not a fallback
        to calls, which is what made the first measurement invalid."""
        ch, idx = measure_band.chain(build(puts=False), 'BTC')
        self.assertIsNone(measure_band.digital(ch, EXPIRY, 95000.0, 100000.0, idx))
        # The upside still works, so this is a targeted refusal and not an outage.
        self.assertIsNotNone(measure_band.digital(ch, EXPIRY, 105000.0, 100000.0, idx))


class ExpiryParsing(unittest.TestCase):
    def test_label_becomes_a_sortable_number(self):
        self.assertEqual(measure_band.expiry_ord('26DEC25'), 20251226)
        self.assertEqual(measure_band.expiry_ord('1JAN26'), 20260101)

    def test_nonsense_is_rejected_rather_than_guessed(self):
        self.assertIsNone(measure_band.expiry_ord('PERPETUAL'))
        self.assertIsNone(measure_band.expiry_ord(''))


class BucketBoundary(unittest.TestCase):
    """D-067 — one cent in the wrong place inflated the density by 12.7%.

    A Kalshi cap of 24999.99 must round to the next bucket's floor of 25000.
    The bug was not a missing epsilon; it was an epsilon applied OUTSIDE the
    rounding, which lands on 25000.01 and makes the digital pick a different
    strike pair on each side of the same boundary.
    """

    BUCKET = {'strike_type': 'range', 'floor_strike': 20000.0, 'cap_strike': 24999.99}
    NEXT_FLOOR = 25000

    def test_corrected_rule_meets_the_next_floor(self):
        _lo, hi = measure_exhaustive.bounds(self.BUCKET, 'corrected')
        self.assertEqual(hi, self.NEXT_FLOOR)

    def test_naive_b_overshoots_by_a_cent(self):
        _lo, hi = measure_exhaustive.bounds(self.BUCKET, 'naive_b')
        self.assertNotEqual(hi, self.NEXT_FLOOR)
        self.assertAlmostEqual(hi - self.NEXT_FLOOR, 0.01, places=6)

    def test_all_three_rules_are_still_present(self):
        """The comparison is the evidence in D-067. Dropping a rule would make
        the record unreproducible."""
        self.assertEqual(set(measure_exhaustive.RULES),
                         {'corrected', 'naive_a', 'naive_b'})


class TouchBound(unittest.TestCase):
    """D-018, D-030, D-031 — touch is never rarer than terminal, and "2" is not
    a constant."""

    def test_touch_is_never_below_terminal(self):
        for A in (105000.0, 120000.0, 200000.0):
            for sigma in (0.4, 0.8, 1.5):
                for T in (0.05, 0.5, 1.0):
                    r = measure_touch.touch_bound(A, 100000.0, sigma, T)
                    self.assertIsNotNone(r)
                    self.assertGreaterEqual(
                        r['touch'] + 1e-12, r['terminal'],
                        'touch < terminal at A=%s sigma=%s T=%s' % (A, sigma, T))

    def test_the_ratio_is_not_pinned_at_two(self):
        """If this ever returns exactly 2 everywhere, the lognormal formula has
        been replaced by the constant again."""
        ratios = []
        for A in (110000.0, 150000.0, 300000.0):
            r = measure_touch.touch_bound(A, 100000.0, 0.7, 0.5)
            ratios.append(r['touch'] / r['terminal'])
        self.assertGreater(max(ratios) - min(ratios), 1e-6)

    def test_degenerate_inputs_return_nothing(self):
        self.assertIsNone(measure_touch.touch_bound(105000.0, 100000.0, 0.0, 0.5))
        self.assertIsNone(measure_touch.touch_bound(105000.0, 100000.0, 0.5, 0.0))


class StabilityClassifier(unittest.TestCase):
    """D-072 — "always" means more than 90% of a rung's observations, not 100%.

    The strip card claimed "in every one of N observations" for two days. These
    cases pin the actual rule so the wording cannot drift away from it again.
    """

    def _rung(self, s, key, hits, total):
        for i in range(total):
            s.add(key, i < hits)

    def test_the_threshold_is_above_ninety_percent_not_a_hundred(self):
        s = Stability()
        self._rung(s, 'perfect', 45, 45)     # 100%
        self._rung(s, 'over90', 41, 45)      # 91.1%
        self._rung(s, 'under90', 40, 45)     # 88.9%
        self._rung(s, 'none', 0, 45)         # 0%
        o = s.summary()
        self.assertEqual(len(o['always']), 2, 'over90 must count as always')
        self.assertEqual(len(o['sometimes']), 1)
        self.assertEqual(len(o['never']), 1)

    def test_repeated_observations_do_not_inflate_the_rung_count(self):
        """The reason this module exists: 44 rungs seen 45 times each are 44
        rungs, not 1980 independent samples."""
        s = Stability()
        for k in range(44):
            self._rung(s, 'rung%d' % k, 45, 45)
        o = s.summary()
        self.assertEqual(o['distinct_rungs'], 44)
        self.assertEqual(o['total_observations'], 44 * 45)
        self.assertAlmostEqual(o['observations_per_rung'], 45.0, places=6)


class PruneWindow(unittest.TestCase):
    """D-071 — the rolling window, and the guard that stops a date bug from
    wiping the archive."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._raw = prune_archive.RAW
        self._ptr = prune_archive.POINTER
        self._days = prune_archive.ARCHIVE_DAYS
        prune_archive.RAW = os.path.join(self.tmp, 'raw')
        prune_archive.POINTER = os.path.join(self.tmp, 'state', 'latest.json')

    def tearDown(self):
        prune_archive.RAW = self._raw
        prune_archive.POINTER = self._ptr
        prune_archive.ARCHIVE_DAYS = self._days
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make(self, n_days):
        for i in range(n_days):
            day = '2026-09-%02d' % (i + 1)
            for stream in ('_meta', 'kalshi', 'events/trades'):
                d = os.path.join(prune_archive.RAW, stream, day)
                os.makedirs(d)
                with open(os.path.join(d, 'x.json'), 'w') as f:
                    f.write('{}')

    def test_day_folders_are_found_at_every_depth(self):
        """events/trades sits one level deeper than the other streams. Matching
        on path shape instead of folder name would silently miss it."""
        self._make(3)
        found = prune_archive.day_dirs()
        self.assertEqual(len(found), 9)
        self.assertTrue(any('events' in p and 'trades' in p for p in found))

    def test_a_short_archive_is_left_alone(self):
        self._make(5)
        prune_archive.ARCHIVE_DAYS = 14
        sys.argv = ['prune_archive.py', '--apply']
        self.assertEqual(prune_archive.main(), 0)
        self.assertEqual(len(prune_archive.day_dirs()), 15)

    def test_the_window_keeps_exactly_the_newest_days(self):
        self._make(20)
        prune_archive.ARCHIVE_DAYS = 14
        sys.argv = ['prune_archive.py', '--apply']
        self.assertEqual(prune_archive.main(), 0)
        left = sorted({os.path.basename(p) for p in prune_archive.day_dirs()})
        self.assertEqual(len(left), 14)
        self.assertEqual(left[0], '2026-09-07')
        self.assertEqual(left[-1], '2026-09-20')

    def test_a_dry_run_deletes_nothing(self):
        self._make(20)
        prune_archive.ARCHIVE_DAYS = 14
        sys.argv = ['prune_archive.py']
        prune_archive.main()
        self.assertEqual(len(prune_archive.day_dirs()), 60)

    def test_it_refuses_to_delete_most_of_the_archive(self):
        """If a date bug ever asked for a mass deletion, stop. One day per run
        is the steady state."""
        self._make(20)
        prune_archive.ARCHIVE_DAYS = 2
        sys.argv = ['prune_archive.py', '--apply']
        self.assertEqual(prune_archive.main(), 1)
        self.assertEqual(len(prune_archive.day_dirs()), 60, 'nothing may be deleted')


if __name__ == '__main__':
    unittest.main(verbosity=2)
