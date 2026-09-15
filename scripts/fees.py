#!/usr/bin/env python3
"""Kalshi trading fees, from Kalshi's own schedule.

SOURCE
https://kalshi.com/docs/kalshi-fee-schedule.pdf, read 2026-09-15, the document
dated "Last updated and effective: July 1, 2025". Quoted rather than
paraphrased, because a fee formula is exactly the kind of text that loses its
meaning in a summary.

    "Trading fees are only charged for orders that are immediately matched
     with orders sitting on the orderbook. Trading fees are not charged for
     orders placed that are not immediately matched and are instead left as
     resting orders on the orderbook unless they are included in our 'Maker
     Fees' section."

    "fees = round up(0.07 x C x P x (1-P))
     P = the price of a contract in dollars (50 cents is 0.5)
     C = the number of contracts being traded
     round up = rounds to the next cent"

    "There is no settlement fee."

WHY THIS MATTERS HERE
The friction band became a trade at quoted prices (D-076), and that trade
CROSSES the spread on both venues. Crossing is what makes it a taker order, so
0.07 applies and the maker exemption does not. Until this file existed the
Kalshi side of the trade was free, which is not a conservative assumption, it
is a wrong one.

TWO THINGS THE FORMULA DOES THAT A FLAT RATE WOULD NOT
1. P*(1-P) is symmetric, so selling YES at 0.03 costs the same as buying it at
   0.97. Our trades sell cheap tails, and the fee is computed on the traded
   contract's own price either way.
2. The round-up is per ORDER, not per contract, and it rounds to a whole cent.
   On a 3-cent contract one contract costs 0.2 cents in fee before rounding
   and a full cent after. So the fee per contract falls with size, and the
   question "is there an edge" cannot be answered without saying at what size.
   That is why min_contracts() exists.

WHAT IS DELIBERATELY NOT MODELLED
Maker fees. They apply to a fixed list of series tickers, none of which is
KXBTCY or KXETHY, and in any case a resting order is not the trade being
measured. The list is kept below so that a later asset expansion trips over it
instead of assuming it away.
"""
import math

# "fees = round up(0.07 x C x P x (1-P))" — the general trading fee.
GENERAL = 0.07

# "The INX and NASDAQ100 market fees are given by the following formula:
#  fees = round up(0.035 x C x P x (1-P))"
# The schedule identifies these by RULEBOOK ticker ("whose Rulebook ticker
# begins with INX" / "NASDAQ100"). The API's series ticker is not obviously
# the same string, and the mapping between them is UNKNOWN. This matters the
# day Divergence prices S&P 500 or Nasdaq-100 — the coefficient halves — so it
# is written down rather than discovered later.
INDEX = 0.035
INDEX_RULEBOOK_PREFIXES = ('INX', 'NASDAQ100')

# Series subject to ADDITIONAL maker fees of 0.0175. Reproduced so that the
# membership test is a fact rather than a memory. Taker fees on these series
# are still the general 0.07.
MAKER_SERIES = frozenset("""
KXAAAGASM KXGDP KXPAYROLLS KXU3 KXEGGS KXCPI KXCPIYOY KXFEDDECISION KXFED
KXNBA KXNBAEAST KXNBAWEST KXNBASERIES KXNBAGAME KXNHL KXNHLEAST KXNHLWEST
KXNHLSERIES KXNHLGAME KXINDY500 KXPGA KXUSOPEN KXPGARYDER KXTHEOPEN
KXPGASOLHEIM KXFOMENSINGLES KXFOWOMENSINGLES KXWMENSINGLES KXWWOMENSINGLES
KXUSOMENSINGLES KXUSOWOMENSINGLES KXAOMENSINGLES KXAOWOMENSINGLES KXNFLGAME
KXUEFACL KXNBAFINALSMVP KXCONNSMYTHE KXFOMEN KXFOWOMEN KXNATHANSHD
KXNATHANDOGS KXCLUBWC KXTOURDEFRANCE KXNASCARRACE
""".split())
MAKER = 0.0175

SETTLEMENT = 0.0          # "There is no settlement fee."


def coefficient(series=None):
    """The multiplier in front of C*P*(1-P) for a taker order on this series.

    An unknown or absent series falls back to the general rate, which is the
    higher of the two and therefore the safe direction to be wrong in.
    """
    if series:
        s = series.upper()
        for prefix in INDEX_RULEBOOK_PREFIXES:
            if s.startswith(prefix):
                return INDEX
    return GENERAL


def round_up_cent(x):
    """"round up = rounds to the next cent". The round() guards against a
    product like 0.07*100*0.03*0.97 arriving as 0.20370000000000002 and being
    pushed up a whole cent by floating point rather than by the schedule."""
    return math.ceil(round(x * 100, 9)) / 100.0


def order_fee(price, contracts=1, series=None):
    """Total fee in DOLLARS for one order of that many contracts at that price.

    price is in dollars, so 3 cents is 0.03. Returns 0.0 at either boundary,
    where P*(1-P) is zero and nothing is being risked.
    """
    p = float(price)
    if not (0.0 < p < 1.0) or contracts <= 0:
        return 0.0
    return round_up_cent(coefficient(series) * contracts * p * (1.0 - p))


def rate(price, series=None):
    """Fee per contract in the limit of large orders, i.e. before the round-up.

    This is the number to subtract from a per-contract edge. It understates the
    cost of a small order and states the cost of a large one exactly; the gap
    between the two is what min_contracts() answers.
    """
    p = float(price)
    if not (0.0 < p < 1.0):
        return 0.0
    return coefficient(series) * p * (1.0 - p)


def min_contracts(price, edge, series=None, cap=10000):
    """Smallest order size at which the round-up no longer eats the edge.

    edge is the per-contract profit BEFORE the Kalshi fee, in dollars. Returns
    None when no size up to the cap works — which is the answer for a rung
    whose gross edge is already below the asymptotic fee rate.

    Searched rather than solved: the round-up makes the condition a step
    function, and a closed form would be a place to be quietly wrong.
    """
    if edge is None or edge <= 0:
        return None
    for c in range(1, cap + 1):
        if order_fee(price, c, series) <= c * edge:
            return c
    return None
