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

import archive
import fees
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


# --------------------------------------------------------------------------
# A wider synthetic chain in which put-call parity holds at a discount factor
# other than 1. Parity is C(K) - P(K) = D*(F - K); everything below is derived
# from that identity, so the chain is arbitrage-free by construction and the
# right answers are known exactly.
#
# The time-value shape is deliberately arbitrary (a plain tent function). It
# has to be: the put-call residual is 1 - D whatever the call prices are, and
# a test that only passed for one particular smile would be testing the smile.
PARITY_D = 0.99
PARITY_F = 100000.0


def parity_chain(D=PARITY_D, F=PARITY_F):
    """17 strikes from 60k to 140k, priced so that parity holds exactly at D."""
    rows = []
    k = 60000
    while k <= 140000:
        tv = 4000.0 - 0.02 * abs(k - F)          # positive across the range
        c_usd = D * max(F - k, 0.0) + tv
        p_usd = c_usd - D * (F - k)
        rows.append(quote('BTC-%s-%d-C' % (EXPIRY, k),
                          c_usd / INDEX, c_usd * 0.98 / INDEX, c_usd * 1.02 / INDEX))
        rows.append(quote('BTC-%s-%d-P' % (EXPIRY, k),
                          p_usd / INDEX, p_usd * 0.98 / INDEX, p_usd * 1.02 / INDEX))
        k += 5000
    return {'BTC': {'book_summary': {'result': rows},
                    'index': {'result': {'index_price': INDEX}}}}


class DiscountConvention(unittest.TestCase):
    """D-073 — the two sides of the digital were on different footings.

    The call side returned D*Q(S>K); the put side returned 1 - D*Q(S<K), which
    is (1-D) + D*Q(S>K). Every put-side rung was therefore (1-D) too high. The
    exhaustiveness check could not see it, because D*1 + (1-D) = 1 for any D,
    which is why this needs a test of its own rather than a constraint.
    """

    def test_discount_is_recovered_from_the_residual(self):
        ch, _idx = measure_band.chain(parity_chain(), 'BTC')
        d = measure_band.discount(ch, EXPIRY)
        self.assertIsNotNone(d)
        self.assertAlmostEqual(d['D'], PARITY_D, places=9)
        self.assertEqual(d['brackets'], 16)

    def test_residual_is_flat_in_strike(self):
        """The whole numeraire argument turns on this. A share-measure error
        would be moneyness-dependent; a discount factor is not."""
        ch, _idx = measure_band.chain(parity_chain(), 'BTC')
        d = measure_band.discount(ch, EXPIRY)
        self.assertLess(d['spread'], 1e-9)

    def test_both_sides_of_the_digital_now_agree(self):
        """92,500 sits below the forward, so digital() takes the put side. On
        the same bracket the call side is (C(90k) - C(95k))/5,000 = 0.97."""
        ch, idx = measure_band.chain(parity_chain(), 'BTC')
        d = measure_band.digital(ch, EXPIRY, 92500.0, PARITY_F, idx, PARITY_D)
        self.assertAlmostEqual(d['p'], 0.97, places=9)

    def test_the_old_put_expression_was_high_by_one_minus_d(self):
        """The bug, pinned. Passing D=1 reproduces it exactly, which is also
        why it survived so long: with D=1 the two expressions coincide."""
        ch, idx = measure_band.chain(parity_chain(), 'BTC')
        old = measure_band.digital(ch, EXPIRY, 92500.0, PARITY_F, idx, 1.0)
        self.assertAlmostEqual(old['p'] - 0.97, 1.0 - PARITY_D, places=9)

    def test_call_side_was_never_affected(self):
        """Above the forward the call side is used, and it was already
        returning D*Q. D must make no difference there."""
        ch, idx = measure_band.chain(parity_chain(), 'BTC')
        a = measure_band.digital(ch, EXPIRY, 107500.0, PARITY_F, idx, PARITY_D)
        b = measure_band.digital(ch, EXPIRY, 107500.0, PARITY_F, idx, 1.0)
        self.assertAlmostEqual(a['p'], b['p'], places=12)

    def test_forward_is_exact_once_d_is_carried(self):
        ch, idx = measure_band.chain(parity_chain(), 'BTC')
        F = measure_band.forward(ch, EXPIRY, idx, PARITY_D)
        self.assertAlmostEqual(F, PARITY_F, places=6)

    def test_forward_with_d_equal_one_is_biased(self):
        """F_hat = K + D*(F-K), so each strike gives a different answer and the
        median lands off the true forward. Small — a few tens of dollars — but
        there is no longer any reason to carry it."""
        ch, idx = measure_band.chain(parity_chain(), 'BTC')
        biased = measure_band.forward(ch, EXPIRY, idx, 1.0)
        self.assertNotAlmostEqual(biased, PARITY_F, places=2)
        self.assertGreater(biased, PARITY_F)

    def test_thin_chain_yields_no_discount(self):
        """Three strikes is two brackets. A median of two numbers is not a
        measurement, and the caller must be told so rather than handed one."""
        ch, _idx = measure_band.chain(build(), 'BTC')
        self.assertIsNone(measure_band.discount(ch, EXPIRY))

    def test_implausible_discount_is_refused(self):
        """0.4 is not a funding curve over any maturity this project touches.
        Refusing is the point: short-dated chains where 1-D is below the tick
        must fall back visibly, not quietly."""
        ch, _idx = measure_band.chain(parity_chain(D=0.4), 'BTC')
        self.assertIsNone(measure_band.discount(ch, EXPIRY))

    def test_guard_constants_are_what_the_record_says(self):
        """Loosening these silently would turn the refusal above into a
        plausible-looking number."""
        self.assertEqual(measure_band.MIN_BRACKETS, 8)
        self.assertEqual((measure_band.D_FLOOR, measure_band.D_CEIL), (0.5, 1.0))


class ExhaustivenessTargetsD(unittest.TestCase):
    """D-073 — an exhaustive ladder is worth D today, not 1.

    Buying every bucket buys a dollar at expiry with certainty, and a certain
    dollar at expiry is worth D now. Before the repair the sum came out at 1
    whatever D was, so the constraint that caught the bucket-boundary bug was
    blind to the convention bug sitting next to it.
    """

    def test_a_partition_sums_to_d_not_to_one(self):
        ch, idx = measure_band.chain(parity_chain(), 'BTC')
        edges = [None, 80000.0, 95000.0, 105000.0, 120000.0, None]
        total = 0.0
        for lo, hi in zip(edges[:-1], edges[1:]):
            dL = (measure_band.digital(ch, EXPIRY, lo, PARITY_F, idx, PARITY_D)
                  if lo is not None else {'p': PARITY_D})
            dH = (measure_band.digital(ch, EXPIRY, hi, PARITY_F, idx, PARITY_D)
                  if hi is not None else {'p': 0.0})
            total += dL['p'] - dH['p']
        self.assertAlmostEqual(total, PARITY_D, places=9)

    def test_the_unbounded_edge_is_worth_d(self):
        """The old code wrote 1 here. That single literal is what made the sum
        land on 1 regardless of everything else in the ladder."""
        self.assertNotEqual(PARITY_D, 1.0)


def kalshi_ladder(quotes):
    """A three-rung Kalshi ladder over the parity chain: below 80k, the middle,
    above 120k. quotes is a list of (bid, ask) in dollars, one per rung.

    The close time is after the option expiry so that rungs() will select
    25DEC26 — the same "nearest expiry not past the close" rule as production.
    """
    fields = [
        ('KXBTCY-TEST-T80000.00', 'less', None, 80000.0),
        ('KXBTCY-TEST-B100000', 'between', 80000.0, 119999.99),
        ('KXBTCY-TEST-T119999.99', 'greater', 119999.99, None),
    ]
    M = []
    for (ticker, kind, fl, cap), (bid, ask) in zip(fields, quotes):
        M.append({'ticker': ticker, 'status': 'active',
                  'close_time': '2027-01-01T05:00:00Z',
                  'strike_type': kind, 'floor_strike': fl, 'cap_strike': cap,
                  'yes_bid_dollars': bid, 'yes_ask_dollars': ask})
    return {'markets': {'KXBTCY': M}}


class TradeAtQuotedPrices(unittest.TestCase):
    """The friction band stopped being a statistic and became a trade.

    1.96*SE measured how uncertain our estimate of the mid was — a question
    nobody can trade on. What replaced it is two trades priced at quotes that
    exist. These tests pin the direction of the envelope, because a reversed
    bid/ask pairing leaves every number plausible: still positive, still the
    right size, just inside out.

    On the numbers below: the top rung's bucket costs at most 0.0344 to buy
    and the two option legs cost 0.006 in fees, so a prediction bid of 0.50 is
    an edge and a bid of 0.01 against an ask of 0.03 is not.
    """

    def test_low_below_mid_and_high_above_on_the_call_side(self):
        ch, idx = measure_band.chain(parity_chain(), 'BTC')
        d = measure_band.digital(ch, EXPIRY, 120000.0, PARITY_F, idx, PARITY_D)
        self.assertLess(d['low'], d['p'])
        self.assertGreater(d['high'], d['p'])
        self.assertAlmostEqual(d['p'], 0.02, places=9)

    def test_low_below_mid_and_high_above_on_the_put_side(self):
        """80,000 is under the forward, so this is the put branch — the one
        where the spread is SUBTRACTED and the bid/ask pairing inverts."""
        ch, idx = measure_band.chain(parity_chain(), 'BTC')
        d = measure_band.digital(ch, EXPIRY, 80000.0, PARITY_F, idx, PARITY_D)
        self.assertLess(d['low'], d['p'])
        self.assertGreater(d['high'], d['p'])
        self.assertAlmostEqual(d['p'], 0.97, places=9)

    def test_the_envelope_is_the_cost_of_the_two_legs(self):
        """Width = (spread of leg A + spread of leg B) / w. Not 1.96 of
        anything, and not a confidence interval."""
        ch, idx = measure_band.chain(parity_chain(), 'BTC')
        d = measure_band.digital(ch, EXPIRY, 120000.0, PARITY_F, idx, PARITY_D)
        C = ch[EXPIRY]['C']
        a, b = 115000.0, 125000.0
        expected = ((C[a]['ask'] - C[a]['bid']) + (C[b]['ask'] - C[b]['bid'])) / (b - a)
        self.assertAlmostEqual(d['high'] - d['low'], expected, places=9)

    def test_one_sided_quotes_produce_no_envelope(self):
        """A leg quoted on one side only has no executable price. The answer
        is None — a refusal — not a zero-width envelope."""
        raw = parity_chain()
        for row in raw['BTC']['book_summary']['result']:
            if row['instrument_name'].endswith('-115000-C'):
                row['bid_price'] = None
        ch, idx = measure_band.chain(raw, 'BTC')
        d = measure_band.digital(ch, EXPIRY, 120000.0, PARITY_F, idx, PARITY_D)
        self.assertIsNotNone(d['p'], 'the mid still exists')
        self.assertIsNone(d['low'])
        self.assertIsNone(d['high'])

    def test_a_rich_prediction_bid_is_an_edge_on_the_sell_side(self):
        KA = kalshi_ladder([(0.01, 0.03), (0.90, 0.95), (0.50, 0.52)])
        h = measure_band.rungs(KA, parity_chain(), 'KXBTCY', 'BTC')
        top = h['rows'][-1]
        self.assertTrue(top['exceeds'])
        self.assertEqual(top['direction'], 'sell prediction')
        # Gross first: prediction bid, minus the bucket bought at its ask side,
        # minus the two Deribit legs.
        self.assertAlmostEqual(top['gross_edge'], 0.50 - (0.0344 + 0.006), places=9)
        # Then Kalshi's taker fee on the contract actually traded, at its own
        # price. 0.07 * 0.50 * 0.50 = 0.0175, the most expensive point on the
        # whole schedule.
        self.assertAlmostEqual(top['kalshi_fee'], 0.0175, places=9)
        self.assertAlmostEqual(top['edge'], top['gross_edge'] - 0.0175, places=9)
        # A 44-cent edge does not need size to survive a one-cent round-up.
        self.assertEqual(top['min_size'], 1)

    def test_a_fair_prediction_quote_is_not_an_edge(self):
        """The bucket's mid is 0.02 and the prediction is quoted 0.01/0.03
        around it. Under the old rule this was a coin toss decided by 1.96*SE;
        under the new one neither trade survives its own spread."""
        KA = kalshi_ladder([(0.01, 0.03), (0.90, 0.95), (0.50, 0.52)])
        h = measure_band.rungs(KA, parity_chain(), 'KXBTCY', 'BTC')
        bottom = h['rows'][0]
        self.assertFalse(bottom['exceeds'])
        self.assertLess(bottom['edge'], 0)

    def test_no_mid_is_used_in_the_verdict(self):
        """Moving the prediction mid without moving either quote must not
        change anything, because the verdict never reads it."""
        KA = kalshi_ladder([(0.01, 0.03), (0.90, 0.95), (0.50, 0.52)])
        h = measure_band.rungs(KA, parity_chain(), 'KXBTCY', 'BTC')
        for r in h['rows']:
            recomputed = max(r['pm_bid'] - (r['opt_high'] + r['fee']),
                             (r['opt_low'] - r['fee']) - r['pm_ask'])
            self.assertAlmostEqual(r['gross_edge'], recomputed, places=12)
            # The Kalshi fee is charged at the quote actually hit, never at
            # the mid — that is the other half of "no mid in the verdict".
            price = r['pm_bid'] if r['direction'] == 'sell prediction' else r['pm_ask']
            self.assertAlmostEqual(r['kalshi_fee'], fees.rate(price, 'KXBTCY'), places=12)
            self.assertAlmostEqual(r['edge'], r['gross_edge'] - r['kalshi_fee'], places=12)

    def test_the_synthetic_ladder_still_sums_to_d(self):
        """The ladder partitions the line, so D-073 applies here too. If this
        breaks, the fixture is wrong and the two tests above mean nothing."""
        KA = kalshi_ladder([(0.01, 0.03), (0.90, 0.95), (0.50, 0.52)])
        h = measure_band.rungs(KA, parity_chain(), 'KXBTCY', 'BTC')
        self.assertAlmostEqual(h['total'], PARITY_D, places=9)


class KalshiFees(unittest.TestCase):
    """scripts/fees.py against Kalshi's own published table.

    The schedule prints a worked table beside the formula, which makes this a
    rare case where the right answers come from the counterparty rather than
    from us. Every number below is copied from the PDF, not computed here.
    """

    # "General Trading Fees Table", price -> fee for 100 contracts, in dollars.
    HUNDRED = [(0.01, 0.07), (0.05, 0.34), (0.10, 0.63), (0.15, 0.90),
               (0.20, 1.12), (0.25, 1.32), (0.30, 1.47), (0.35, 1.60),
               (0.40, 1.68), (0.45, 1.74), (0.50, 1.75), (0.55, 1.74),
               (0.60, 1.68), (0.65, 1.60), (0.70, 1.47), (0.75, 1.32),
               (0.80, 1.12), (0.85, 0.90), (0.90, 0.63), (0.95, 0.34),
               (0.99, 0.07)]

    # Same table, fee for ONE contract. Every entry is a cent or two, which is
    # the round-up doing the work.
    ONE = [(0.01, 0.01), (0.05, 0.01), (0.10, 0.01), (0.15, 0.01),
           (0.20, 0.02), (0.25, 0.02), (0.30, 0.02), (0.35, 0.02),
           (0.40, 0.02), (0.45, 0.02), (0.50, 0.02), (0.55, 0.02),
           (0.60, 0.02), (0.65, 0.02), (0.70, 0.02), (0.75, 0.02),
           (0.80, 0.02), (0.85, 0.01), (0.90, 0.01), (0.95, 0.01),
           (0.99, 0.01)]

    def test_matches_the_published_table_for_one_hundred_contracts(self):
        for price, expected in self.HUNDRED:
            self.assertAlmostEqual(fees.order_fee(price, 100), expected, places=9,
                                   msg='price %.2f' % price)

    def test_matches_the_published_table_for_one_contract(self):
        for price, expected in self.ONE:
            self.assertAlmostEqual(fees.order_fee(price, 1), expected, places=9,
                                   msg='price %.2f' % price)

    def test_the_fee_is_symmetric_in_the_price(self):
        """P*(1-P), so selling a 3-cent YES costs what buying it at 97 does.
        Our trades sell cheap tails; if this were asymmetric the direction of
        the trade would change the answer."""
        self.assertAlmostEqual(fees.rate(0.03), fees.rate(0.97), places=12)

    def test_the_round_up_is_per_order_not_per_contract(self):
        """One contract at 3 cents costs a full cent; a hundred cost 21 cents,
        not a dollar. This is the whole reason an edge needs a size."""
        self.assertAlmostEqual(fees.order_fee(0.03, 1), 0.01, places=9)
        self.assertAlmostEqual(fees.order_fee(0.03, 100), 0.21, places=9)

    def test_the_index_coefficient_is_half(self):
        """S&P 500 and Nasdaq-100 pay 0.035. Divergence does not price them
        yet; this is here so the day it does, the coefficient is not the
        general one by default."""
        self.assertAlmostEqual(fees.order_fee(0.50, 100, 'INXD'), 0.88, places=9)
        self.assertAlmostEqual(fees.order_fee(0.50, 100, 'NASDAQ100W'), 0.88, places=9)

    def test_our_series_pay_the_general_rate(self):
        self.assertEqual(fees.coefficient('KXBTCY'), fees.GENERAL)
        self.assertEqual(fees.coefficient('KXETHY'), fees.GENERAL)
        self.assertNotIn('KXBTCY', fees.MAKER_SERIES)
        self.assertNotIn('KXETHY', fees.MAKER_SERIES)

    def test_no_fee_at_the_boundaries(self):
        """P*(1-P) is zero at 0 and 1, and a contract at either is not a bet."""
        self.assertEqual(fees.order_fee(0.0, 100), 0.0)
        self.assertEqual(fees.order_fee(1.0, 100), 0.0)

    def test_min_contracts_answers_the_round_up(self):
        """A gross edge of 0.6 cents on a 1.2-cent contract cannot pay a
        one-cent fee alone, so one contract is not enough — but two are."""
        self.assertIsNone(fees.min_contracts(0.012, 0.0))
        self.assertEqual(fees.min_contracts(0.012, 0.006), 2)

    def test_min_contracts_refuses_when_the_edge_is_below_the_rate(self):
        """No order size rescues an edge smaller than the asymptotic fee."""
        rate = fees.rate(0.50)
        self.assertIsNone(fees.min_contracts(0.50, rate * 0.5))


class MirrorIsolation(unittest.TestCase):
    """DIVERGENCE_RAW moves every READER to the private mirror. It must never
    move the DELETER.

    prune_archive.py computes its own RAW from its own file location and does
    not import archive.py. If someone ever "tidies" that duplication away, an
    environment variable set to point at the mirror would point the pruner at
    it too, and the mirror is the only copy of everything older than fourteen
    days. These tests exist so that tidying fails loudly.
    """

    def test_the_reader_honours_the_environment(self):
        self.assertTrue(hasattr(archive, 'RAW'))
        self.assertIn('DIVERGENCE_RAW', open(archive.__file__, encoding='utf-8').read(),
                      'archive.RAW must be overridable')

    def test_the_pruner_does_not_import_the_reader(self):
        src = open(prune_archive.__file__, encoding='utf-8').read()
        self.assertNotIn('from archive import', src)
        self.assertNotIn('import archive', src)

    def test_the_pruner_never_reads_the_environment(self):
        """Its RAW is derived from __file__ and nothing else."""
        src = open(prune_archive.__file__, encoding='utf-8').read()
        self.assertNotIn('DIVERGENCE_RAW', src)
        self.assertNotIn('environ', src)

    def test_the_two_roots_are_the_same_when_unset(self):
        """With no override the pruner and the reader must agree, or the
        window would be bounded somewhere the measurements are not reading."""
        if os.environ.get('DIVERGENCE_RAW'):
            self.skipTest('override is set; the roots are meant to differ')
        self.assertEqual(os.path.abspath(archive.RAW),
                         os.path.abspath(prune_archive.RAW))


if __name__ == '__main__':
    unittest.main(verbosity=2)
