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
import ast
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
import kill_test_eth5k
import measure_payoff
import measure_carry
import horizons
import discount_referee
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
        self.assertAlmostEqual(d['dsp'], 0.4, places=6)

    def test_downside_uses_puts_and_matches_the_hand_computation(self):
        ch, idx = measure_band.chain(build(), 'BTC')
        d = measure_band.digital(ch, EXPIRY, 95000.0, 100000.0, idx)
        # 1 - (8000 - 5000) / 10000
        self.assertAlmostEqual(d['dsp'], 0.7, places=6)

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
        self.assertAlmostEqual(d['dsp'], 0.97, places=9)

    def test_the_old_put_expression_was_high_by_one_minus_d(self):
        """The bug, pinned. Passing D=1 reproduces it exactly, which is also
        why it survived so long: with D=1 the two expressions coincide."""
        ch, idx = measure_band.chain(parity_chain(), 'BTC')
        old = measure_band.digital(ch, EXPIRY, 92500.0, PARITY_F, idx, 1.0)
        self.assertAlmostEqual(old['dsp'] - 0.97, 1.0 - PARITY_D, places=9)

    def test_call_side_was_never_affected(self):
        """Above the forward the call side is used, and it was already
        returning D*Q. D must make no difference there."""
        ch, idx = measure_band.chain(parity_chain(), 'BTC')
        a = measure_band.digital(ch, EXPIRY, 107500.0, PARITY_F, idx, PARITY_D)
        b = measure_band.digital(ch, EXPIRY, 107500.0, PARITY_F, idx, 1.0)
        self.assertAlmostEqual(a['dsp'], b['dsp'], places=12)

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
                  if lo is not None else {'dsp': PARITY_D})
            dH = (measure_band.digital(ch, EXPIRY, hi, PARITY_F, idx, PARITY_D)
                  if hi is not None else {'dsp': 0.0})
            total += dL['dsp'] - dH['dsp']
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
        self.assertLess(d['low'], d['dsp'])
        self.assertGreater(d['high'], d['dsp'])
        self.assertAlmostEqual(d['dsp'], 0.02, places=9)

    def test_low_below_mid_and_high_above_on_the_put_side(self):
        """80,000 is under the forward, so this is the put branch — the one
        where the spread is SUBTRACTED and the bid/ask pairing inverts."""
        ch, idx = measure_band.chain(parity_chain(), 'BTC')
        d = measure_band.digital(ch, EXPIRY, 80000.0, PARITY_F, idx, PARITY_D)
        self.assertLess(d['low'], d['dsp'])
        self.assertGreater(d['high'], d['dsp'])
        self.assertAlmostEqual(d['dsp'], 0.97, places=9)

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
        self.assertIsNotNone(d['dsp'], 'the mid still exists')
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


COLLECTOR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'collector', 'collect.py')


def from_collector(*names):
    """Lift named definitions out of collect.py without running it.

    `collector/collect.py` IS the collector: its module level fetches from four
    APIs and writes files. Importing it from a test would run a collection. So
    the named top-level assignments and function definitions are taken out of
    its AST and only those are executed. Nothing else in the module is touched.

    A source-text assertion would have been simpler, but it would pass on code
    that reads right and behaves wrong, and the point of these tests is the
    behaviour.
    """
    wanted = set(names)
    with open(COLLECTOR, encoding='utf-8') as f:
        tree = ast.parse(f.read())
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            keep.append(node)
        elif isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id in wanted
                   for target in node.targets):
                keep.append(node)
    ns = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), COLLECTOR, 'exec'), ns)
    missing = wanted - set(ns)
    if missing:
        raise AssertionError('not found in collect.py: %s' % sorted(missing))
    return ns


def holder_row():
    """One row as the venue returns it, field for field."""
    return {'proxyWallet': '0x6dd4cbdd901d61124bef8e2afdb4c803cdf685aa',
            'bio': '', 'asset': 'T1', 'pseudonym': 'Parallel-Jalapeno',
            'amount': 153639.106938, 'displayUsernamePublic': True,
            'outcomeIndex': 0, 'name': 'geniusBacon521', 'profileImage': '',
            'profileImageOptimized': '', 'verified': False}


class CollectorFieldDrops(unittest.TestCase):
    """D-087 and D-088: the two deliberate exceptions to rule 2.

    Dropping a field from the archive is irreversible — the run that would have
    written it is gone. These tests pin which fields go and, more importantly,
    which ones must not: `proxyWallet` and `transactionHash` are what make a row
    attributable to an actor and verifiable by somebody else, and `amount`,
    `price`, `size` and `timestamp` are the measurement itself. Someone tidying
    the drop lists later should fail here rather than quietly lose them.
    """

    def setUp(self):
        self.ns = from_collector('strip_holders', 'HOLDER_DROP',
                                 'HOLDERS_UNEXPECTED', 'TRADE_DROP')

    def test_only_the_three_market_fields_survive(self):
        out = self.ns['strip_holders']([{'token': 'T1',
                                         'holders': [holder_row()]}])
        self.assertEqual(sorted(out[0]['holders'][0]),
                         ['amount', 'outcomeIndex', 'proxyWallet'])

    def test_asset_is_recoverable_from_the_key_it_sat_under(self):
        """Why dropping `asset` is lossless and dropping a name is not."""
        group = {'token': 'T1', 'holders': [holder_row()]}
        original = group['holders'][0]['asset']
        out = self.ns['strip_holders']([group])
        self.assertNotIn('asset', out[0]['holders'][0])
        self.assertEqual(out[0]['token'], original)

    def test_a_null_payload_is_returned_untouched_and_counted(self):
        """One condition really did come back as JSON null. It must stay in the
        file exactly as it arrived AND show up in the count."""
        before = len(self.ns['HOLDERS_UNEXPECTED'])
        self.assertIsNone(self.ns['strip_holders'](None))
        self.assertEqual(len(self.ns['HOLDERS_UNEXPECTED']), before + 1)

    def test_the_actor_key_is_never_dropped(self):
        self.assertNotIn('proxyWallet', self.ns['HOLDER_DROP'])
        self.assertNotIn('proxyWallet', self.ns['TRADE_DROP'])
        self.assertNotIn('transactionHash', self.ns['TRADE_DROP'])

    def test_the_numbers_are_never_dropped(self):
        for field in ('amount', 'outcomeIndex'):
            self.assertNotIn(field, self.ns['HOLDER_DROP'])
        for field in ('price', 'size', 'timestamp', 'conditionId'):
            self.assertNotIn(field, self.ns['TRADE_DROP'])


class KillTestEth5k(unittest.TestCase):
    """D-092: the ETH above $5,000 kill test, with its verdict rules written
    before the number. Synthetic call chain in USD, shaped like the one
    measure_band.chain() returns for one expiry and one side."""

    IDX = 2400.0

    def chain(self, one_sided=None):
        # strike -> (mark, bid, ask), USD. Monotone falling in strike.
        spec = {4500: (48, 46, 50), 4800: (38, 36, 40), 5000: (32, 31, 33),
                5200: (28, 27, 29), 5500: (23, 22, 24), 6000: (17, 16, 18)}
        o = {}
        for k, (m, b, a) in spec.items():
            o[float(k)] = {'mark': float(m), 'bid': float(b), 'ask': float(a)}
        if one_sided is not None:
            o[float(one_sided)]['bid'] = None
        return o

    def test_the_tight_bracket_steps_over_the_listed_strike(self):
        """Production's bracket() takes strictly below and above K, so a
        listed 5,000 is never used by the tight estimator; only the one-sided
        quotients touch it. D-092 records this because it is the reason the
        kill test can say something the band never could."""
        br = kill_test_eth5k.brackets(self.chain(), 5000.0)
        self.assertEqual(br['tight'], (4800.0, 5200.0))
        self.assertEqual(br['skip1'], (4500.0, 5500.0))
        self.assertIsNone(br['skip2'])           # no third strike below
        self.assertEqual(br['onesided_lower'], (4800.0, 5000.0))
        self.assertEqual(br['onesided_upper'], (5000.0, 5200.0))

    def test_no_onesided_quotients_without_a_listed_strike(self):
        o = self.chain()
        del o[5000.0]
        br = kill_test_eth5k.brackets(o, 5000.0)
        self.assertIsNone(br['onesided_lower'])
        self.assertIsNone(br['onesided_upper'])
        self.assertEqual(br['tight'], (4800.0, 5200.0))

    def test_the_estimator_crosses_the_spread_and_charges_the_crossed_price(self):
        """Long the lower leg at its ASK, short the upper leg at its BID: that
        is the executable high, and the Deribit fee is charged on those two
        prices, per unit of digital. Same rule as measure_band.digital."""
        o = self.chain()
        e = kill_test_eth5k.estimate(o, (4800.0, 5200.0), self.IDX)
        w = 400.0
        self.assertAlmostEqual(e['dsp'], (38 - 28) / w)
        self.assertAlmostEqual(e['high'], (40 - 27) / w)
        self.assertAlmostEqual(e['low'], (36 - 29) / w)
        fee = (min(0.0003 * self.IDX, 0.125 * 40) + min(0.0003 * self.IDX, 0.125 * 27)) / w
        self.assertAlmostEqual(e['fee'], fee)
        self.assertAlmostEqual(e['cost'], e['high'] + fee)
        self.assertLessEqual(e['low'], e['dsp'])
        self.assertLessEqual(e['dsp'], e['high'])

    def test_a_one_sided_leg_is_a_refusal_not_a_zero(self):
        o = self.chain(one_sided=5200)
        e = kill_test_eth5k.estimate(o, (4800.0, 5200.0), self.IDX)
        self.assertIsNotNone(e['dsp'])
        self.assertIsNone(e['high'])
        self.assertIsNone(e['cost'])
        self.assertIn('refused', e)

    def test_the_verdict_rules_are_the_ones_d092_wrote_down(self):
        """Three synthetic archives, one per branch. The thresholds are read
        from the module so that editing them there changes these numbers and
        not the branch they land in — the pre-commitment is the constants."""
        K = kill_test_eth5k

        def rows(margins, depth):
            return [{'margin_vs_worst_local_executable': m,
                     'value_at_depth_usd': m * depth} for m in margins]

        # 8 of 10 positive: persistence fails.
        v = K.verdict(rows([0.02] * 8 + [-0.01] * 2, 100))
        self.assertEqual(v['verdict'], K.VERDICT_NOT_SURVIVING)
        # All positive, smallest below one cent: noise.
        v = K.verdict(rows([0.02] * 9 + [0.005], 100))
        self.assertEqual(v['verdict'], K.VERDICT_NOISE)
        # All positive and material, but resting depth makes it worth < 1 USD.
        v = K.verdict(rows([0.02] * 10, 10))
        self.assertEqual(v['verdict'], K.VERDICT_NOISE)
        # All positive, material, and worth something: anomaly, nothing more.
        v = K.verdict(rows([0.02] * 10, 100))
        self.assertEqual(v['verdict'], K.VERDICT_ANOMALY)
        # Exactly 90% positive is not "fewer than 90%".
        v = K.verdict(rows([0.02] * 9 + [-0.01], 100))
        self.assertNotEqual(v['verdict'], K.VERDICT_NOT_SURVIVING)
        # No executable estimate anywhere: UNKNOWN, not a verdict.
        self.assertEqual(K.verdict([{'margin_vs_worst_local_executable': None}])['verdict'],
                         'UNKNOWN')

    def test_persistence_is_the_stability_threshold(self):
        """D-092 ties the 90% to stability.py's always_above so the two cannot
        drift apart silently, the way D-072's "always" once meant ">90%" on one
        surface and "every one of N" on another."""
        import inspect
        default = inspect.signature(Stability.summary).parameters['always_above'].default
        self.assertEqual(kill_test_eth5k.PERSISTENCE, default)

    def test_the_interpolant_is_linear_in_time_and_labelled(self):
        """-165 h early, +2019 h late: the weight on the late chain is
        165/2184, and a rung-observation with either end missing has no
        interpolant rather than a guessed one."""
        val, wgt = kill_test_eth5k.interpolant(0.010, -165.0, 0.020, 2019.0)
        self.assertAlmostEqual(wgt, 165.0 / 2184.0)
        self.assertAlmostEqual(val, 0.010 + wgt * 0.010)
        self.assertEqual(kill_test_eth5k.interpolant(None, -165.0, 0.02, 2019.0), (None, None))


class DiscountReferees(unittest.TestCase):
    """D-093: four estimates of D side by side. R2 is pinned as the same
    identity as R1 (it must agree exactly on an arbitrage-free chain), R3 is
    pinned to the futures basis arithmetic, and the external rate is pinned
    to being a dated, sourced constant rather than a bare number."""

    def test_the_parity_slope_recovers_d_on_marks_and_on_mids(self):
        """On the parity chain C - P = D*(F - K) exactly, so the least-squares
        slope is -D whether marks or mids are used (the mids ARE the marks:
        bid = 0.98 mark, ask = 1.02 mark). Agreement with R1 to machine
        precision is the point: this referee is not independent evidence."""
        ch, idx = measure_band.chain(parity_chain(), 'BTC')
        r2 = discount_referee.parity_slope(ch, EXPIRY, idx)
        self.assertAlmostEqual(r2['D_marks'], PARITY_D, places=9)
        self.assertAlmostEqual(r2['D_mids'], PARITY_D, places=9)
        r1 = measure_band.discount(ch, EXPIRY)
        self.assertAlmostEqual(r1['D'], r2['D_marks'], places=9)

    def test_a_one_sided_leg_leaves_the_mid_regression_not_the_mark_one(self):
        raw = parity_chain()
        for row in raw['BTC']['book_summary']['result']:
            if row['instrument_name'].endswith('-100000-C'):
                row['bid_price'] = None
        ch, idx = measure_band.chain(raw, 'BTC')
        r2 = discount_referee.parity_slope(ch, EXPIRY, idx)
        self.assertEqual(r2['points_marks'], r2['points_mids'] + 1)
        self.assertAlmostEqual(r2['D_marks'], PARITY_D, places=9)

    def test_the_futures_referee_is_index_over_underlying(self):
        """underlying_price = index / D on every row of the expiry, so R3
        returns D. The listed-or-synthetic question is UNKNOWN by construction
        and the script must say so rather than guess."""
        raw = parity_chain()
        for row in raw['BTC']['book_summary']['result']:
            row['underlying_price'] = INDEX / PARITY_D
        und = discount_referee.underlying_by_expiry(raw, 'BTC')
        self.assertIn(EXPIRY, und)
        self.assertAlmostEqual(INDEX / und[EXPIRY]['underlying_price'], PARITY_D, places=9)

    def test_rates_and_discounts_round_trip_and_refuse_nonsense(self):
        T = 0.5
        r = discount_referee.implied_rate(PARITY_D, T)
        self.assertAlmostEqual(discount_referee.discount_from_rate(r, T), PARITY_D, places=12)
        self.assertIsNone(discount_referee.implied_rate(PARITY_D, 0.0))
        self.assertIsNone(discount_referee.implied_rate(0.0, T))
        self.assertIsNone(discount_referee.implied_rate(None, T))

    def test_the_external_rate_is_dated_and_sourced(self):
        """Rule 1. The one number in the measurement path that is not read
        from the archive must carry where it came from and when, and must be
        either a number or None (UNKNOWN) — never a placeholder string."""
        e = discount_referee.EXTERNAL_RATE
        for field in ('name', 'value', 'as_of', 'source', 'entered'):
            self.assertIn(field, e)
        self.assertTrue(e['value'] is None or isinstance(e['value'], float))
        self.assertTrue(e['source'].startswith('http'))
        self.assertRegex(e['as_of'], r'^\d{4}-\d{2}-\d{2}$')

    def test_time_to_expiry_is_measured_from_the_snapshot(self):
        """25DEC26 08:00 UTC from a 2026-09-16 13:02 snapshot is a bit under
        100 days; a stamp after the expiry yields None, not a negative year."""
        T = discount_referee.years_to('25DEC26', '2026-09-16T1302Z')
        self.assertAlmostEqual(T * 365.25, 99.79, places=1)
        self.assertIsNone(discount_referee.years_to('25DEC26', '2027-01-05T0500Z'))


class LadderShapeAndEvents(unittest.TestCase):
    """D-105: a series is not a ladder, and not every ladder is a partition.

    The exhaustiveness constraint applies to one event's markets when they
    tile the outcome space. Summing two events, a cumulative ladder, or a
    ladder with a hole in it produced ratios of 1.8, 40 and 0.05 on the
    screen. These pin the three refusals and the event choice.
    """

    def test_the_fixture_ladder_is_a_partition(self):
        M = kalshi_ladder([(0.5, 0.52)] * 3)['markets']['KXBTCY']
        self.assertEqual(measure_band.ladder_shape(M), ('exhaustive', 0))

    def test_a_missing_middle_rung_is_a_break_not_a_sum(self):
        """68,200 'less' followed by a 'between' from 75,000 is what the
        archive holds for an intraday event cut by the 200-market page."""
        KA = kalshi_ladder([(0.5, 0.52)] * 3)
        KA['markets']['KXBTCY'] = [m for m in KA['markets']['KXBTCY']
                                   if m['strike_type'] != 'between']
        shape, breaks = measure_band.ladder_shape(KA['markets']['KXBTCY'])
        self.assertEqual(shape, 'incomplete')
        self.assertEqual(breaks, 1)
        r = measure_exhaustive.ladder_sum(KA, parity_chain(), 'KXBTCY', 'BTC', 'corrected')
        self.assertEqual(r['ladder'], 'incomplete')
        self.assertIsNone(r['ratio'])
        self.assertIsNone(r['total'])

    def test_an_all_greater_ladder_is_cumulative_and_never_summed(self):
        KA = kalshi_ladder([(0.5, 0.52)] * 3)
        for m in KA['markets']['KXBTCY']:
            m['strike_type'] = 'greater'
            m['floor_strike'] = m['floor_strike'] or 79999.99
            m['cap_strike'] = None
        self.assertEqual(measure_band.ladder_shape(KA['markets']['KXBTCY'])[0], 'cumulative')
        r = measure_exhaustive.ladder_sum(KA, parity_chain(), 'KXBTCY', 'BTC', 'corrected')
        self.assertEqual(r['ladder'], 'cumulative')
        self.assertIsNone(r['ratio'])

    def test_two_events_in_one_series_yield_the_earliest_closing_one(self):
        """Three rungs closing 2027-01-01 and three more of a later event: the
        ladder is the first three, and the caller is told there were two."""
        KA = kalshi_ladder([(0.5, 0.52)] * 3)
        first = KA['markets']['KXBTCY']
        for m in first:
            m['event_ticker'] = 'KXBTCY-27JAN01'
        later = [dict(m, event_ticker='KXBTCY-27JAN08', ticker=m['ticker'] + '-L',
                      close_time='2027-01-08T05:00:00Z') for m in first]
        KA['markets']['KXBTCY'] = later + first
        M, events = measure_band.event_ladder(KA, 'KXBTCY')
        self.assertEqual(events, 2)
        self.assertEqual([m['event_ticker'] for m in M], ['KXBTCY-27JAN01'] * 3)
        h = measure_band.rungs(KA, parity_chain(), 'KXBTCY', 'BTC')
        self.assertEqual(len(h['rows']), 3)
        self.assertEqual(h['events_in_series'], 2)
        self.assertEqual(h['ladder'], 'exhaustive')
        self.assertAlmostEqual(h['total'], PARITY_D, places=6)
        r = measure_exhaustive.ladder_sum(KA, parity_chain(), 'KXBTCY', 'BTC', 'corrected')
        self.assertEqual(r['events'], 2)
        self.assertEqual(r['buckets'], 3)
        self.assertAlmostEqual(r['ratio'], 1.0, places=6)


class FundingStage(unittest.TestCase):
    """D-111: the perpetuals' funding is archived as a HISTORY, re-asked with
    overlap, and stored as it came.

    The stage is lifted out of collect.py without running it (from_collector),
    and `get` is replaced so no network is touched. What is pinned: the window
    asked for, that both perpetuals are asked, that the response is not
    reshaped, and the archive version that says the stream exists.
    """

    def setUp(self):
        self.ns = from_collector('funding', 'FUNDING_INSTRUMENTS',
                                 'FUNDING_LOOKBACK_MS', 'DERIBIT', 'ARCHIVE_VERSION')
        self.calls = []
        payload = {'jsonrpc': '2.0', 'usIn': 1, 'usOut': 2, 'usDiff': 1, 'testnet': False,
                   'result': [{'timestamp': 1789693200000, 'index_price': 76529.69,
                               'interest_8h': 5.9e-06, 'interest_1h': 1.2e-06,
                               'prev_index_price': 76355.27}]}
        self.payload = payload

        def fake_get(url, timeout=30, attempts=3):
            self.calls.append(url)
            return payload
        self.ns['get'] = fake_get

    def test_the_window_is_the_lookback_ending_at_the_run_instant(self):
        """A run every eight hours re-asking for two days sees every hour about
        six times; that overlap is what makes a missed run leave no hole."""
        end = 1789714667000
        out = self.ns['funding'](end_ms=end)
        self.assertEqual(sorted(out), sorted(self.ns['FUNDING_INSTRUMENTS']))
        for name, v in out.items():
            r = v['request']
            self.assertEqual(r['end_timestamp'], end)
            self.assertEqual(r['start_timestamp'], end - self.ns['FUNDING_LOOKBACK_MS'])
            self.assertEqual(r['instrument_name'], name)
            self.assertEqual(r['method'], 'public/get_funding_rate_history')
        self.assertGreaterEqual(self.ns['FUNDING_LOOKBACK_MS'], 24 * 3600 * 1000)

    def test_both_perpetuals_are_asked_from_the_history_endpoint(self):
        self.ns['funding'](end_ms=1789714667000)
        self.assertEqual(len(self.calls), 2)
        for url, name in zip(self.calls, self.ns['FUNDING_INSTRUMENTS']):
            self.assertTrue(url.startswith(self.ns['DERIBIT'] + '/get_funding_rate_history?'))
            self.assertIn('instrument_name=%s' % name, url)
            self.assertIn('start_timestamp=', url)
            self.assertIn('end_timestamp=', url)

    def test_the_response_is_stored_as_it_came(self):
        """Rule 2. The JSON-RPC envelope, every field, untouched — the stage
        wraps it beside the request and does nothing else to it."""
        out = self.ns['funding'](end_ms=1789714667000)
        self.assertIs(out['BTC-PERPETUAL']['response'], self.payload)
        self.assertEqual(sorted(out['BTC-PERPETUAL']), ['request', 'response'])

    def test_the_archive_version_says_the_stream_exists(self):
        """A reader checks `_meta.version` before assuming raw/funding is there.
        Version 7 (D-119) added raw/carry and kept raw/funding."""
        self.assertGreaterEqual(self.ns['ARCHIVE_VERSION'], 6)


class PayoffBuyerComparison(unittest.TestCase):
    """D-114 and D-117: the buyer's comparison as a template. One venue, one
    side's costs, the options side as a band, the verdict rules written before
    the script, and the parts that vary declared per family. Chains here are in
    USD, shaped like measure_band.chain() output for one expiry."""

    IDX = 100000.0
    D = 0.98
    SCHED = {'exponent': 1, 'rate': 0.07, 'takerOnly': True, 'rebateRate': 0.2}

    def chain(self):
        # strike -> (mark, bid, ask) in USD, calls falling and puts rising in K.
        calls = {90000: (15000, 14800, 15200), 100000: (8000, 7900, 8100),
                 110000: (4000, 3900, 4100)}
        puts = {90000: (5000, 4900, 5100), 100000: (8000, 7900, 8100),
                110000: (14000, 13800, 14200)}
        mk = lambda d: {float(k): {'mark': float(m), 'bid': float(b), 'ask': float(a)}
                        for k, (m, b, a) in d.items()}
        return {'E': {'C': mk(calls), 'P': mk(puts)}}

    def fee(self, x):
        return kill_test_eth5k.deribit_fee_usd(x, self.IDX)

    def test_the_constants_are_the_ones_d114_and_d117_wrote_down(self):
        self.assertEqual(measure_payoff.REL, 0.10)
        self.assertEqual(measure_payoff.ABS, 0.001)
        self.assertEqual(measure_payoff.PERSISTENCE, 0.9)
        self.assertEqual(measure_payoff.PERSISTENCE, kill_test_eth5k.PERSISTENCE)
        self.assertEqual(measure_payoff.MIN_JUDGED, 10)
        self.assertEqual(tuple(measure_payoff.SKIPS), (0, 1))
        self.assertEqual(measure_payoff.NARROW_HOURS, 168.0)
        self.assertEqual([f[0] for f in measure_payoff.FAMILIES],
                         ['kalshi_year_end', 'polymarket_daily'])

    def test_the_prediction_market_is_cheaper_only_against_the_cheapest_option_estimate(self):
        c = measure_payoff.classify
        self.assertEqual(c(0.05, 0.06, 0.20), measure_payoff.PREDICTION)
        # 0.004 short of the 10% margin on 0.05: a tie, however dear the band's top.
        self.assertEqual(c(0.05, 0.054, 0.90), measure_payoff.TIE)

    def test_the_options_are_cheaper_only_when_their_dearest_estimate_is(self):
        c = measure_payoff.classify
        self.assertEqual(c(0.10, 0.02, 0.08), measure_payoff.OPTIONS)
        self.assertEqual(c(0.10, 0.02, 0.095), measure_payoff.TIE)

    def test_one_price_step_is_the_floor_on_a_tail(self):
        """On a 0.4-cent tail a 10% margin is 0.04 cents, below one step of
        the ladder's price grid; the step is what binds (D-078)."""
        self.assertEqual(measure_payoff.classify(0.004, 0.0048, 0.01), measure_payoff.TIE)
        self.assertEqual(measure_payoff.classify(0.004, 0.0051, 0.01), measure_payoff.PREDICTION)

    def test_the_floor_is_the_venues_own_step(self):
        """D-117: a Polymarket market quoted in whole cents cannot be cheaper by
        less than a cent, even where 10% would allow it."""
        c = measure_payoff.classify
        self.assertEqual(c(0.05, 0.056, 0.2, step=0.001), measure_payoff.PREDICTION)
        self.assertEqual(c(0.05, 0.056, 0.2, step=0.01), measure_payoff.TIE)

    def test_a_missing_side_is_unquoted_not_a_tie(self):
        c = measure_payoff.classify
        self.assertEqual(c(None, 0.1, 0.2), measure_payoff.UNQUOTED)
        self.assertEqual(c(0.1, None, None), measure_payoff.UNQUOTED)

    def test_the_call_side_buys_at_the_ask_and_pays_the_crossed_fee(self):
        """K above the forward: the bracket around 100,000 is 90,000 / 110,000,
        long the lower call at its ask, short the upper at its bid."""
        t = measure_payoff.digital_trade(self.chain(), 'E', 100000.0, 95000.0,
                                         self.D, self.IDX, 0)
        w = 20000.0
        self.assertEqual(t['side'], 'C')
        self.assertAlmostEqual(t['buy'], (15200 - 3900) / w + (self.fee(15200) + self.fee(3900)) / w)
        self.assertAlmostEqual(t['sell'], (14800 - 4100) / w - (self.fee(14800) + self.fee(4100)) / w)
        self.assertGreater(t['buy'], t['sell'])

    def test_the_put_side_holds_d_and_trades_the_put_spread(self):
        t = measure_payoff.digital_trade(self.chain(), 'E', 100000.0, 105000.0,
                                         self.D, self.IDX, 0)
        w = 20000.0
        self.assertEqual(t['side'], 'P')
        self.assertAlmostEqual(t['buy'], self.D - (13800 - 5100) / w
                               + (self.fee(5100) + self.fee(13800)) / w)
        self.assertAlmostEqual(t['sell'], self.D - (14200 - 4900) / w
                               - (self.fee(4900) + self.fee(14200)) / w)

    def test_below_is_d_less_the_digital_sold_and_both_sides_cost_at_least_d(self):
        ch, F = self.chain(), 95000.0
        t = measure_payoff.digital_trade(ch, 'E', 100000.0, F, self.D, self.IDX, 0)
        below = measure_payoff.option_cost(ch, 'E', None, 100000.0, F, self.D, self.IDX, 0)
        above = measure_payoff.option_cost(ch, 'E', 100000.0, None, F, self.D, self.IDX, 0)
        self.assertAlmostEqual(below, self.D - t['sell'])
        # Owning both halves is owning D for sure; crossing spreads cannot make it cheaper.
        self.assertGreaterEqual(above + below, self.D)

    def test_zero_fees_are_the_combo_sensitivity_and_only_lower_the_cost(self):
        ch, F = self.chain(), 95000.0
        full = measure_payoff.option_cost(ch, 'E', 100000.0, None, F, self.D, self.IDX, 0)
        free = measure_payoff.option_cost(ch, 'E', 100000.0, None, F, self.D, self.IDX, 0,
                                          fee_on=False)
        self.assertAlmostEqual(free, (15200 - 3900) / 20000.0)
        self.assertLess(free, full)

    def kalshi(self):
        mk = lambda kind, fl, cap, ask, bid, t: {
            'strike_type': kind, 'floor_strike': fl, 'cap_strike': cap, 'ticker': t,
            'yes_ask_dollars': '%.4f' % ask, 'yes_bid_dollars': '%.4f' % bid,
            'no_ask_dollars': '%.4f' % (1 - bid), 'yes_ask_size_fp': '100.00',
            'yes_bid_size_fp': '40.00',
            'price_ranges': [{'start': '0.0000', 'end': '1.0000', 'step': '0.0010'}]}
        return measure_payoff.kalshi_legs([
            mk('less', None, 100000, 0.30, 0.28, 'L'),
            mk('between', 100000, 109999.99, 0.40, 0.38, 'M'),
            mk('greater', 109999.99, None, 0.35, 0.33, 'G')], 'KXBTCY')

    def test_every_payoff_is_judged_once(self):
        """Above the top boundary is the 'greater' rung and below the bottom
        one is the 'less' rung; they collapse into the bucket they are."""
        conds = measure_payoff.conditions(self.kalshi())
        self.assertEqual(len(conds), 5)
        self.assertIn((None, 110000), conds)
        self.assertIn((100000, None), conds)

    def test_kalshi_takes_the_no_side_when_it_is_the_cheaper_way(self):
        legs = self.kalshi()
        k = measure_payoff.venue_cost(legs, None, 110000)
        yes = 0.30 + fees.rate(0.30) + 0.40 + fees.rate(0.40)
        no = 0.67 + fees.rate(0.67)
        self.assertLess(no, yes)
        self.assertEqual(k['route'], 'no')
        self.assertAlmostEqual(k['cost'], no)
        self.assertEqual(k['depth'], 40.0)       # the resting YES bid, seen as a NO ask
        self.assertEqual(k['step'], 0.001)       # the ladder's own price_ranges step

    def test_tiles_are_summed_only_when_they_cover_the_interval_exactly(self):
        legs = self.kalshi()
        k = measure_payoff.venue_cost(legs, 100000, None)   # middle + top bucket
        self.assertEqual(k['route'], 'no')                   # NO on 'less' is cheaper here
        self.assertTrue(measure_payoff.covers([(1, 2), (2, 3)], 1, 3))
        self.assertFalse(measure_payoff.covers([(1, 2), (2.5, 3)], 1, 3))

    def test_polymarket_bucket_titles_become_intervals(self):
        b = measure_payoff.poly_bucket
        self.assertEqual(b('<72,000'), (None, 72000.0))
        self.assertEqual(b('72,000-74,000'), (72000.0, 74000.0))
        self.assertEqual(b('>90,000'), (90000.0, None))
        self.assertIsNone(b('Other'))

    def test_polymarket_no_is_one_minus_the_yes_bid_and_the_fee_is_the_markets(self):
        """D-117: the payload quotes YES only; a resting YES bid at p is a NO at
        1 - p. The fee comes from the market's own feeSchedule."""
        m = {'slug': 'x', 'bestBid': 0.84, 'bestAsk': 0.86, 'feeSchedule': self.SCHED,
             'feesEnabled': True, 'orderPriceMinTickSize': 0.01}
        leg = measure_payoff.poly_leg(m, (84000.0, None), (None, 84000.0), False)
        k = measure_payoff.venue_cost([leg], None, 84000.0)
        self.assertEqual(k['route'], 'no')
        self.assertAlmostEqual(k['cost'], 0.16 + fees.polymarket_rate(0.16, self.SCHED))
        self.assertEqual(k['step'], 0.01)
        self.assertIsNone(k['depth'])            # not in the payload: UNKNOWN

    def test_a_polymarket_leg_with_an_unknown_fee_is_not_a_route(self):
        m = {'slug': 'x', 'bestBid': 0.2, 'bestAsk': 0.22, 'feeSchedule': None,
             'orderPriceMinTickSize': 0.001}
        leg = measure_payoff.poly_leg(m, (84000.0, None), (None, 84000.0), False)
        self.assertIsNone(measure_payoff.venue_cost([leg], 84000.0, None))

    def test_the_band_reaches_as_far_as_its_farther_chain(self):
        hb = measure_payoff.band_hours
        self.assertEqual(hb([{'hours': -8.0}, {'hours': 16.0}]), 16.0)
        self.assertEqual(hb([{'hours': -165.0}, {'hours': 2019.0}]), 2019.0)
        self.assertIsNone(hb(None))

    def test_the_verdict_has_three_outcomes_and_a_minimum_sample(self):
        mp = measure_payoff
        z = lambda k=0, d=0, t=0: {mp.PREDICTION: k, mp.OPTIONS: d, mp.TIE: t, mp.UNQUOTED: 0}
        v, _ = mp.verdict({'a': z(k=20), 'b': z(t=20)})
        self.assertEqual((v['verdict'], v['venue']), (mp.VERDICT_ONE, 'prediction market'))
        v, _ = mp.verdict({'a': z(k=20), 'b': z(d=19, t=1)})
        self.assertEqual(v['verdict'], mp.VERDICT_DEPENDS)
        v, _ = mp.verdict({'a': z(k=18, t=2), 'b': z(t=20)})   # 90% is not MORE than 90%
        self.assertEqual(v['verdict'], mp.VERDICT_NONE)
        v, _ = mp.verdict({'a': z(k=9)})                        # too few to classify
        self.assertEqual(v['verdict'], mp.VERDICT_NONE)

    def test_the_stake_for_a_target_and_the_round_up_on_kalshi(self):
        self.assertAlmostEqual(measure_payoff.stake_for_target(0.5), 200.0)
        self.assertAlmostEqual(measure_payoff.stake_for_target(0.2), 50.0)
        self.assertIsNone(measure_payoff.stake_for_target(1.02))
        legs = self.kalshi()
        k = measure_payoff.venue_cost(legs, 100000, 110000)
        t = measure_payoff.venue_ticket(k)
        n = t['contracts']
        self.assertAlmostEqual(t['stake_usd'], round(n * 0.40 + fees.order_fee(0.40, n, 'KXBTCY'), 2))
        self.assertAlmostEqual(t['profit_if_right_usd'], round(n - t['stake_usd'], 2), places=2)
        self.assertFalse(t['depth_covers'])      # 100 resting, more needed


class CarryStage(unittest.TestCase):
    """D-119: Hyperliquid and Polymarket's perpetuals, and Deribit's dated
    futures, lifted out of collect.py and run against fakes. Pinned: a coin the
    dex does not list is recorded as absent and never asked for; the window is
    the eight-day lookback ending at the run's instant; Polymarket's history is
    paged in the direction its own rows show, and no further than the cap; one
    venue failing leaves the others whole."""

    def setUp(self):
        import time as _time
        self.ns = from_collector('_try', '_hyperliquid', '_poly_perps', '_deribit_futures',
                                 'carry', 'CARRY_LOOKBACK_MS', 'CARRY_LOOKBACK_LONG_MS', 'HL_PAGE_ROWS',
                                 'HL_COINS', 'POLY_PERP_SYMBOLS',
                                 'POLY_PERP_MAX_PAGES', 'HYPERLIQUID', 'POLY_PERPS', 'DERIBIT',
                                 'DERIBIT_CURRENCIES', 'HOLDERS_HOUR', 'ARCHIVE_VERSION')
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        import datetime as _dt
        self.ns.update(os=os, time=_time, ROOT=self.tmp, DAY='2026-09-24',
                       now=_dt.datetime(2026, 9, 24, 13, tzinfo=_dt.timezone.utc))
        self.posts, self.gets = [], []

        def fake_post(url, body, timeout=30, attempts=3):
            self.posts.append(body)
            if body['type'] == 'metaAndAssetCtxs':
                names = ['xyz:CL', 'xyz:GOLD'] if body.get('dex') == 'xyz' else ['BTC', 'ETH']
                return [{'universe': [{'name': n} for n in names]}, [{} for _ in names]]
            if body['type'] == 'fundingHistory':
                return [{'coin': body['coin'], 'fundingRate': '0.0000125',
                         'premium': '0', 'time': body['startTime'] + 74}]
            return [None]

        def fake_get(url, timeout=30, attempts=3):
            self.gets.append(url)
            if url.endswith('/tickers'):
                return [{'symbol': 'WTIOIL-USD', 'instrument_id': 3}]
            if '/funding?' in url:
                # newest first, always "more": the stage must walk backwards and stop at the cap
                q = dict(x.split('=') for x in url.split('?')[1].split('&'))
                hi = int(q['end_timestamp'])
                rows = [{'funding_rate': '0.00000625', 'timestamp': hi - i * 3600000}
                        for i in range(100)]
                return {'data': rows, 'more': True}
            if 'deribit' in url or url.startswith(self.ns['DERIBIT']):
                raise RuntimeError('deribit down')
            return {}
        self.ns['post'], self.ns['get'] = fake_post, fake_get

    def test_absent_coins_are_recorded_and_not_asked(self):
        end = 1790270000000
        out = self.ns['carry'](end_ms=end, long_lookback=False)
        hl = out['hyperliquid']
        self.assertEqual(sorted(hl['funding']), ['BTC', 'ETH', 'xyz:CL', 'xyz:GOLD'])
        self.assertIn('xyz:SILVER', hl['absent'])
        asked = [b['coin'] for b in self.posts if b['type'] == 'fundingHistory']
        self.assertNotIn('xyz:SILVER', asked)
        for b in self.posts:
            if b['type'] == 'fundingHistory':
                self.assertEqual(b['endTime'], end)
                self.assertEqual(b['startTime'], end - self.ns['CARRY_LOOKBACK_MS'])
        self.assertGreaterEqual(self.ns['CARRY_LOOKBACK_MS'], 7 * 24 * 3600 * 1000)
        self.assertIn('BTC-USD', out['polymarket_perps']['absent'])

    def test_polymarket_pages_backwards_and_stops_at_the_cap(self):
        out = self.ns['carry'](end_ms=1790270000000, long_lookback=False)
        pages = out['polymarket_perps']['funding']['WTIOIL-USD']
        self.assertEqual(len(pages), 2)          # 192 hours: two pages of 100 cover it, then it stops
        self.ns['CARRY_LOOKBACK_MS'] = 60 * 24 * 3600 * 1000
        pages = self.ns['carry'](end_ms=1790270000000, long_lookback=False)['polymarket_perps']['funding']['WTIOIL-USD']
        self.assertEqual(len(pages), self.ns['POLY_PERP_MAX_PAGES'])
        his = [p['request']['end_timestamp'] for p in pages]
        self.assertEqual(his, sorted(his, reverse=True))
        self.assertTrue(all(p['request']['start_timestamp'] == pages[0]['request']['start_timestamp']
                            for p in pages))

    def test_one_venue_failing_leaves_the_others_whole(self):
        out = self.ns['carry'](end_ms=1790270000000)
        self.assertFalse(out['deribit_futures']['BTC']['book_summary']['ok'])
        self.assertIn('deribit down', out['deribit_futures']['BTC']['book_summary']['error'])
        self.assertTrue(out['hyperliquid']['funding']['BTC']['response']['ok'])

    def test_the_archive_version_says_the_carry_stream_exists(self):
        self.assertGreaterEqual(self.ns['ARCHIVE_VERSION'], 7)


class CarryMeasure(unittest.TestCase):
    """D-119's derived numbers: hourly rates as fractions, positive = long pays,
    a window below 90% coverage is UNKNOWN rather than a smaller average."""

    H = 3600 * 1000

    def test_hyperliquid_stamps_fall_into_their_hour_and_disagreements_are_counted(self):
        a = [(1790186400074, 0.0000125), (1790190000015, 0.0000125)]
        b = [(1790190000020, 0.0000130)]            # same hour, a later file, a different value
        series, disagree = measure_carry.merge_points([a, b])
        self.assertEqual(sorted(series), [1790186400000, 1790190000000])
        self.assertEqual(series[1790190000000], 0.0000130)
        self.assertEqual(disagree, 1)

    def test_a_window_below_ninety_percent_is_unknown(self):
        end = 1790190000000
        full = dict((end - i * self.H, 0.00001) for i in range(24))
        m, cov = measure_carry.window_mean(full, end, 24)
        self.assertAlmostEqual(m, 0.00001)
        self.assertEqual(cov, 1.0)
        for i in range(2):                       # 22 of 24 = 91.7%: still reported
            full.pop(end - i * self.H - 5 * self.H)
        self.assertIsNotNone(measure_carry.window_mean(full, end, 24)[0])
        full.pop(end - 10 * self.H)              # 21 of 24 = 87.5%: UNKNOWN
        m, cov = measure_carry.window_mean(full, end, 24)
        self.assertIsNone(m)
        self.assertAlmostEqual(cov, 21 / 24.0)

    def test_what_a_thousand_dollar_long_pays(self):
        """The documented interest leg, 0.00125% an hour, on $1,000 for a week."""
        self.assertAlmostEqual(measure_carry.long_pays(0.0000125, 168), 2.1)
        self.assertAlmostEqual(measure_carry.long_pays(-0.00001, 24), -0.24)
        self.assertIsNone(measure_carry.long_pays(None, 24))

    def test_the_dated_future_premium_and_an_expired_contract(self):
        now = 1790270000000
        p = measure_carry.futures_premium(101.0, 100.0, now + 73 * 24 * self.H, now)
        self.assertAlmostEqual(p['premium'], 0.01)
        self.assertAlmostEqual(p['per_1000'], 10.0)
        self.assertAlmostEqual(p['annualised'], 0.05)
        self.assertIsNone(measure_carry.futures_premium(101.0, 100.0, now - 1, now))
        self.assertIsNone(measure_carry.futures_premium(None, 100.0, now + 1, now))


class WaveTwoCollector(unittest.TestCase):
    """D-120, lifted out of collect.py and run against fakes: the commodity series
    Kalshi's catalogue is filtered to, a month of funding on the first run of the
    day with Hyperliquid paged when a reply is full, and the HIP-4 books asked only
    for threshold-at-a-time outcomes on our underlyings, in the future, under a cap."""

    def setUp(self):
        import re as _re, time as _time, datetime as _dt
        self.ns = from_collector('_try', '_hyperliquid', '_poly_perps', '_deribit_futures', 'carry',
                                 '_hip4_fields', 'hip4', 'CARRY_LOOKBACK_MS', 'CARRY_LOOKBACK_LONG_MS',
                                 'HL_PAGE_ROWS', 'HL_COINS', 'POLY_PERP_SYMBOLS', 'POLY_PERP_MAX_PAGES',
                                 'HYPERLIQUID', 'POLY_PERPS', 'DERIBIT', 'DERIBIT_CURRENCIES', 'HOLDERS_HOUR',
                                 'HIP4_UNDERLYINGS', 'HIP4_MAX_BOOKS', 'KALSHI_COMMODITY_RE', 'ARCHIVE_VERSION')
        self.re = _re
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.ns.update(os=os, time=_time, datetime=_dt, ROOT=self.tmp, DAY='2026-09-24',
                       now=_dt.datetime(2026, 9, 24, 13, tzinfo=_dt.timezone.utc))
        self.posts = []

    def test_the_commodity_series_filter(self):
        pat = self.ns['KALSHI_COMMODITY_RE']
        for t in ('KXWTI', 'KXWTIW', 'KXWTIMONTHLY', 'KXBRENTD', 'KXGOLDMON', 'KXSILVERW', 'KXWTIMAXM'):
            self.assertTrue(self.re.match(pat, t), t)
        for t in ('KXWTI15M', 'KXWTIH', 'KXGOLD15M', 'KXAAAGASD', 'KXGOLDVSSILVER', 'KXNATGASW', 'KXWTIEU'):
            self.assertFalse(self.re.match(pat, t), t)

    def test_a_month_on_the_first_run_of_the_day_and_hyperliquid_paged(self):
        H = 3600 * 1000

        def fake_post(url, body, timeout=30, attempts=3):
            self.posts.append(body)
            if body['type'] == 'metaAndAssetCtxs':
                return [{'universe': [{'name': 'BTC'}] if not body.get('dex') else []}, [{}]]
            if body['type'] == 'fundingHistory':
                n = min(500, int((body['endTime'] - body['startTime']) // H) + 1)
                return [{'coin': body['coin'], 'fundingRate': '0.0000125', 'time': body['startTime'] + i * H + 7}
                        for i in range(n)]
            return [None]
        self.ns['post'] = fake_post
        self.ns['get'] = lambda url, timeout=30, attempts=3: []
        end = 1790270000000
        out = self.ns['carry'](end_ms=end)                       # no raw/carry/DAY yet: first run of the day
        self.assertEqual(out['window']['start_ms'], end - self.ns['CARRY_LOOKBACK_LONG_MS'])
        btc = out['hyperliquid']['funding']['BTC']
        self.assertEqual(len(btc['response']['value']), 500)
        self.assertEqual(len(btc['more_pages']), 1)
        last = max(x['time'] for x in btc['response']['value'])
        self.assertEqual(btc['more_pages'][0]['request']['startTime'], last + 1)
        rows = measure_carry._hl_rows(btc)
        self.assertEqual(len(rows), 500 + len(btc['more_pages'][0]['response']['value']))
        os.makedirs(os.path.join(self.tmp, 'raw', 'carry', '2026-09-24'))
        out = self.ns['carry'](end_ms=end)                       # a later run the same day
        self.assertEqual(out['window']['start_ms'], end - self.ns['CARRY_LOOKBACK_MS'])

    def test_hip4_books_only_for_future_threshold_outcomes_on_our_underlyings(self):
        import datetime as _dt
        outcomes = [
            {'outcome': 1210, 'name': 'template:binaryPrice', 'description': 'perp:BTC|seconds:1|threshold:100000|time:20261001-0000'},
            {'outcome': 1230, 'name': 'template:binaryPrice', 'description': 'perp:xyz:CL|seconds:1|threshold:83.196|time:20260929-2100'},
            {'outcome': 1211, 'name': 'template:priceTouch', 'description': 'perp:BTC|seconds:1|target:100000|time:20261001-0000'},
            {'outcome': 1209, 'name': 'template:binaryPrice', 'description': 'perp:HYPE|seconds:1|threshold:50|time:20261001-0000'},
            {'outcome': 1100, 'name': 'template:binaryPrice', 'description': 'perp:BTC|seconds:1|threshold:90000|time:20260920-0000'},
        ]

        def fake_post(url, body, timeout=30, attempts=3):
            self.posts.append(body)
            if body['type'] == 'outcomeMeta':
                return {'outcomes': outcomes}
            if body['type'] == 'allMids':
                return {'#12100': '0.5'}
            return {'levels': [[], []]}
        self.ns['post'] = fake_post
        out = self.ns['hip4'](now_utc=_dt.datetime(2026, 9, 24, 13, tzinfo=_dt.timezone.utc))
        self.assertEqual(sorted(out['books']), ['#12100', '#12101', '#12300', '#12301'])
        self.assertEqual(self.ns['_hip4_fields']('perp:xyz:CL|threshold:83.196')['perp'], 'xyz:CL')
        self.ns['HIP4_MAX_BOOKS'] = 3
        out = self.ns['hip4'](now_utc=_dt.datetime(2026, 9, 24, 13, tzinfo=_dt.timezone.utc))
        self.assertEqual(len(out['books']), 3)
        self.assertEqual(out['skipped_for_cap'], 1)

    def test_the_archive_version(self):
        self.assertEqual(self.ns['ARCHIVE_VERSION'], 8)


class HorizonRule(unittest.TestCase):
    """D-120: a dated instrument is offered for a horizon only within
    max(1 day, 30% of the horizon), with its offset, nearest first."""

    D = 24 * 3600 * 1000

    def test_the_window(self):
        self.assertEqual(horizons.window_days(0.5), 1.0)
        self.assertEqual(horizons.window_days(2), 1.0)
        self.assertAlmostEqual(horizons.window_days(7), 2.1)
        self.assertAlmostEqual(horizons.window_days(100), 30.0)

    def test_a_week_finds_six_days_and_eight_but_not_three(self):
        now = 1790270000000
        target = now + 7 * self.D
        dates = [now + 3 * self.D, now + 6 * self.D, now + 8 * self.D, now + 10 * self.D, now - self.D]
        got = horizons.matches(dates, target, now)
        self.assertEqual([g['offset_days'] for g in got], [-1.0, 1.0])
        self.assertEqual(horizons.matches([now + 3 * self.D], target, now), [])

    def test_expiry_codes_and_stamps(self):
        import datetime as _dt
        ms = horizons.deribit_expiry_ms('2OCT26')
        self.assertEqual(_dt.datetime.fromtimestamp(ms / 1000, _dt.timezone.utc).isoformat(), '2026-10-02T08:00:00+00:00')
        self.assertIsNone(horizons.deribit_expiry_ms('PERPETUAL'))
        ms = horizons.hip4_time_ms('20260929-2100')
        self.assertEqual(_dt.datetime.fromtimestamp(ms / 1000, _dt.timezone.utc).isoformat(), '2026-09-29T21:00:00+00:00')
        self.assertIsNone(horizons.hip4_time_ms('soon'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
