#!/usr/bin/env python3
"""The buyer's comparison (D-114), as a template over families (D-117): for the
same terminal payoff, is it cheaper to buy on the prediction market or from the
Deribit option chain, and does the answer depend on the condition?

WHY THIS IS NOT THE KILL TEST AGAIN
Every earlier test asked an arbitrageur's question: sell one venue, buy the
other, pay BOTH sides' costs. D-103 answered it: nothing survives. A buyer with
a view trades ONE venue and pays one side's costs, so a gap too small to
arbitrage can still decide where the buyer should pay less. This script asks
that question and nothing more. It never says which condition anyone should
buy; it says, for a given condition, what each venue charged for it.

THE TEMPLATE (D-117)
What is fixed, for every family, is D-114 as written (the RULES below). What
varies is declared per family, in FAMILIES and in that family's reader:
  - which events, and so which conditions (intervals of the terminal price);
  - how the prediction side is bought: every market is a LEG with a YES interval,
    optionally a NO interval, its asks, its fee and its published price step;
    'tile' legs partition the line and can be summed into a wider interval;
  - the close instant, which picks the two option chains that straddle it.
Each family gets its own verdict. Families are never pooled.

  kalshi_year_end    KXBTCY, KXETHY; buckets tile the line; a NO exists for the
                     two open-ended buckets, whose complements are intervals
                     (D-114).
  polymarket_daily   "Bitcoin/Ethereum above ___ on DATE?" (threshold legs: YES
                     is above K, NO is below K) and "... price on DATE?" (bucket
                     legs that tile the line). NO ask = 1 - YES best bid, from
                     Polymarket's own description of its book (D-117). Depth is
                     not in the payload: UNKNOWN.

WHAT EACH SIDE COSTS, per dollar of payoff, at the best level
  prediction  the cheapest route: one leg whose YES (or NO) interval is the
              condition, or a sum of tile legs covering it exactly; each leg's
              ask plus that venue's per-contract taker fee.
  options     the same payoff from vertical spreads, ask on every leg bought and
              bid on every leg sold, plus Deribit's fee on those crossed prices
              (kill_test_eth5k.deribit_fee_usd). Call spread at or above the
              forward; below it, D held and the put spread traded (D-025, D-032,
              D-073).

THE BAND
The options cost is an interval, not a point: the cheapest and the dearest of
the tight and one-skip brackets (measure_sensitivity.wide_bracket, skip 0 and 1)
on both chains that straddle the close (measure_sensitivity.neighbours). A band
needs both ends, so a condition with no estimate on one of the chains is
'unquoted' in that snapshot, and so is every condition of a snapshot whose
chains do not straddle.

THE RULES — D-114, not editable here
  cheaper on the prediction market   opt_min - pred >= max(REL * pred, step)
  cheaper on the options             pred - opt_max >= max(REL * opt_max, step)
  indistinguishable                  otherwise
  unquoted                           no executable price on a side; not judged
step is the price step the venue publishes for the markets bought — the largest
among a route's legs (D-117; 0.001 on the Kalshi year-end ladders, D-078).
A condition is STABLY cheaper on a side when it is so in more than PERSISTENCE
of its judged snapshots and it has at least MIN_JUDGED of them. Verdict per
family: stable conditions on both sides -> VERDICT_DEPENDS; on one side only ->
VERDICT_ONE; none -> VERDICT_NONE.

THE NARROW BAND (D-117)
Beside the verdict over every judged snapshot, the same verdict over the
snapshots whose two chains are both within NARROW_HOURS of the close. For the
year-end family it is empty until a chain within a week after 1 January 2027 is
listed; for the dailies nearly every judged snapshot is narrow.

COMBO FEES (D-115) — reported, never in a verdict
Deribit says combo orders carry reduced fees and does not say by how much; every
spread here is charged leg by leg. The same rules with every Deribit fee at zero
are reported per family as a sensitivity. The owner set the question aside
(D-117); the sensitivity stays because it costs nothing.

WHAT IS NOT IN ANY NUMBER HERE
Perpetual funding (unit and sign UNKNOWN, D-111), dated futures (B-018), the
depth of the option book (book_summary has no sizes), Polymarket's depth (not in
the payload), the margin a long spread ties up, Deribit's minimum order size,
the settlement basis (BRTI or Binance against the Deribit index).

Usage:
    python scripts/measure_payoff.py            # whole archive
    python scripts/measure_payoff.py --last 5
"""
import json
import math
import os
import re
import sys

import fees
from archive import snapshot, stamps, summary, Missing
from measure_band import chain, discount, forward, event_ladder, ladder_shape, \
    iso_instant, size_fp
from measure_sensitivity import neighbours, wide_bracket
from kill_test_eth5k import deribit_fee_usd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# The rules of D-114. Written there before the first version of this script;
# changing them here without a new record is what the pre-commitment forbids,
# and tests/test_measurement.py pins them.
REL = 0.10            # the dearer side must cost at least 10% more
ABS = 0.001           # the Kalshi year-end ladders' price step (D-078); the default step
PERSISTENCE = 0.9     # stability.py's always_above, the same rule as D-092
MIN_JUDGED = 10       # fewer judged snapshots and a condition is not classified
SKIPS = (0, 1)        # tight and one-skip brackets
NARROW_HOURS = 168.0  # D-117: both chains within a week of the close

VERDICT_DEPENDS = 'the cheaper venue depends on the condition'
VERDICT_ONE = 'one venue is cheaper wherever either is'
VERDICT_NONE = 'no condition is stably cheaper on either venue'

PREDICTION, OPTIONS, TIE, UNQUOTED = 'prediction', 'options', 'indistinguishable', 'unquoted'

# The owner's example (D-114, reference ticket). Illustration only: nothing in
# any verdict reads it.
TICKET_CAPITAL = 1000.0
TICKET_TARGET = 0.20
LEVERAGES = (2, 5)

# (family, prediction venue, what it is) — the declared part of the template.
FAMILIES = [
    ('kalshi_year_end', 'Kalshi', 'KXBTCY and KXETHY year-end buckets (D-114)'),
    ('polymarket_daily', 'Polymarket',
     'daily "above ___ on DATE" thresholds and "price on DATE" buckets (D-117)'),
]
KALSHI_SERIES = [('BTC', 'KXBTCY', 'BTC'), ('ETH', 'KXETHY', 'ETH')]
POLY_ASSETS = [('BTC', 'bitcoin', 'BTC', 'Bitcoin'), ('ETH', 'ethereum', 'ETH', 'Ethereum')]
POLY_ABOVE = re.compile(r'^(Bitcoin|Ethereum) above ___ on ', re.I)
POLY_BUCKETS = re.compile(r'^(Bitcoin|Ethereum) price on ', re.I)


# ---------------------------------------------------------------------------
# Legs: the prediction side, whatever the venue

def price(value):
    """A dollar price, or None when it is not a live quote. 0 and 1 are what an
    empty side of the book reads as, and neither can be bought at."""
    try:
        p = float(value)
    except (TypeError, ValueError):
        return None
    return p if 0.0 < p < 1.0 else None


def complement(iv):
    """The complement of an interval when it is itself an interval (only for
    the open-ended ones); None otherwise."""
    lo, hi = iv
    if lo is None and hi is not None:
        return (hi, None)
    if hi is None and lo is not None:
        return (None, lo)
    return None


def inside(iv, lo, hi):
    """Is interval iv wholly inside [lo, hi)? None is open-ended."""
    b_lo = -math.inf if iv[0] is None else iv[0]
    b_hi = math.inf if iv[1] is None else iv[1]
    c_lo = -math.inf if lo is None else lo
    c_hi = math.inf if hi is None else hi
    return c_lo <= b_lo and b_hi <= c_hi


def covers(ivs, lo, hi):
    """Do these intervals, sorted, cover [lo, hi) exactly and without gaps?"""
    if not ivs:
        return False
    key = lambda iv: -math.inf if iv[0] is None else iv[0]
    s = sorted(ivs, key=key)
    if s[0][0] != lo or s[-1][1] != hi:
        return False
    return all(a[1] is not None and a[1] == b[0] for a, b in zip(s, s[1:]))


def venue_cost(legs, lo, hi):
    """Cheapest way the venue sells [lo, hi) at the top of the book, per dollar
    of payoff, taker fee in. Returns {cost, route, depth, step, legs} or None.
    A leg whose fee is UNKNOWN is not a route: a fee that quietly becomes zero
    is the error fees.py exists to prevent."""
    routes = []

    def add(parts, route):
        total, depth, step = 0.0, [], []
        for leg, side, p in parts:
            if p is None:
                return
            r = leg['rate'](p)
            if r is None:
                return
            total += p + r
            depth.append(leg['yes_depth'] if side == 'yes' else leg['no_depth'])
            step.append(leg['step'])
        routes.append({'cost': total, 'route': route,
                       'depth': None if (not depth or None in depth) else min(depth),
                       'step': max(step),
                       'legs': [(leg['id'], side, p) for leg, side, p in parts],
                       '_legs': parts})

    for leg in legs:
        if leg['yes'] == (lo, hi):
            add([(leg, 'yes', leg['yes_ask'])], 'yes')
        if leg['no'] == (lo, hi):
            add([(leg, 'no', leg['no_ask'])], 'no')
    tiles = [leg for leg in legs if leg['tile'] and inside(leg['yes'], lo, hi)]
    if len(tiles) > 1 and covers([t['yes'] for t in tiles], lo, hi):
        add([(t, 'yes', t['yes_ask']) for t in tiles], 'yes, summed')
    if not routes:
        return None
    return min(routes, key=lambda r: r['cost'])


def conditions(legs):
    """Every interval the family judges, once each: what the legs sell directly
    (YES and NO intervals), plus above and below every tile edge. Keyed by
    (lo, hi), so the same payoff reached two ways is one condition."""
    seen = {}
    for leg in legs:
        seen[leg['yes']] = None
        if leg['no']:
            seen[leg['no']] = None
    for leg in legs:
        if leg['tile']:
            for K in leg['yes']:
                if K is not None:
                    seen[(K, None)] = None
                    seen[(None, K)] = None
    return list(seen)


# ---------------------------------------------------------------------------
# Family readers

def kalshi_step(m):
    """The price step the market publishes. The year-end ladders publish one
    uniform 0.0010 band (D-078); a market that publishes nothing gets D-114's
    ABS, which is that same step."""
    steps = []
    for r in (m.get('price_ranges') or []):
        try:
            steps.append(float(r['step']))
        except (KeyError, TypeError, ValueError):
            pass
    return max(steps) if steps else ABS


def kalshi_legs(M, series):
    """One leg per bucket. Edges as measure_band reads them (D-067): a
    'between' cap of 24,999.99 is an upper edge of 25,000, a 'greater' floor
    of 149,999.99 a lower edge of 150,000. The quantity at the best NO ask is
    the quantity at the best YES bid (measure_band.size_fp)."""
    out = []
    for m in M:
        kind = m.get('strike_type')
        if kind == 'less':
            iv = (None, round(m['cap_strike']))
        elif kind == 'greater':
            iv = (round(m['floor_strike'] + .01), None)
        else:
            iv = (round(m['floor_strike']), round(m['cap_strike'] + .01))
        out.append({'id': m.get('ticker'), 'yes': iv, 'no': complement(iv),
                    'yes_ask': price(m.get('yes_ask_dollars')),
                    'no_ask': price(m.get('no_ask_dollars')),
                    'yes_depth': size_fp(m.get('yes_ask_size_fp')),
                    'no_depth': size_fp(m.get('yes_bid_size_fp')),
                    'step': kalshi_step(m), 'tile': True,
                    'rate': (lambda p, s=series: fees.rate(p, s)),
                    'order_fee': (lambda p, n, s=series: fees.order_fee(p, n, s))})
    out.sort(key=lambda leg: -1 if leg['yes'][0] is None else leg['yes'][0])
    return out


def poly_number(s):
    """'72,000' -> 72000.0; None when there is no number."""
    m = re.search(r'\d+(?:\.\d+)?', (s or '').replace(',', '').replace('$', ''))
    return float(m.group(0)) if m else None


def poly_bucket(title):
    """A bucket title -> its interval. '<72,000' -> (None, 72000);
    '72,000-74,000' -> (72000, 74000); '>90,000' -> (90000, None). Ties go to
    the higher bracket, so the interval is [lo, hi) (the markets' rule text,
    quoted in D-117)."""
    t = (title or '').replace(',', '').replace('$', '').strip()
    if t.startswith('<'):
        v = poly_number(t)
        return None if v is None else (None, v)
    if t.startswith('>'):
        v = poly_number(t)
        return None if v is None else (v, None)
    parts = re.findall(r'\d+(?:\.\d+)?', t)
    if len(parts) == 2:
        return (float(parts[0]), float(parts[1]))
    return None


def poly_leg(m, yes_iv, no_iv, tile):
    """One Polymarket market as a leg. The payload quotes the YES side; a
    resting YES bid at p is a NO at 1 - p (D-117). The fee comes from the
    market's own feeSchedule and is None — the leg unusable — when that
    schedule is missing or unfamiliar."""
    bid, ask = price(m.get('bestBid')), price(m.get('bestAsk'))
    sched, enabled = m.get('feeSchedule'), m.get('feesEnabled', True)
    try:
        step = float(m.get('orderPriceMinTickSize'))
    except (TypeError, ValueError):
        step = None
    return {'id': m.get('slug') or m.get('id'), 'yes': yes_iv, 'no': no_iv,
            'yes_ask': ask, 'no_ask': None if bid is None else price(1.0 - bid),
            'yes_depth': None, 'no_depth': None,
            'step': step if step and step > 0 else ABS, 'tile': tile,
            'rate': (lambda p, s=sched, e=enabled: fees.polymarket_rate(p, s, e)),
            'order_fee': (lambda p, n, s=sched, e=enabled:
                          None if fees.polymarket_rate(p, s, e) is None
                          else n * fees.polymarket_rate(p, s, e))}


def poly_legs(events, name):
    """Group the day's two ladders by close date. Returns
    {date: {'close': iso, 'legs': [...]}} for one asset."""
    out = {}
    for e in events or []:
        title = e.get('title') or ''
        if not title.lower().startswith(name.lower()):
            continue
        above, bucket = POLY_ABOVE.match(title), POLY_BUCKETS.match(title)
        if not (above or bucket):
            continue
        close = e.get('endDate') or ''
        if len(close) < 19:
            continue
        day = out.setdefault(close[:10], {'close': close, 'legs': []})
        for m in e.get('markets') or []:
            if not m.get('active') or m.get('closed'):
                continue
            if above:
                K = poly_number(m.get('groupItemTitle'))
                if K is None:
                    continue
                day['legs'].append(poly_leg(m, (K, None), (None, K), False))
            else:
                iv = poly_bucket(m.get('groupItemTitle'))
                if iv is None:
                    continue
                day['legs'].append(poly_leg(m, iv, complement(iv), True))
    return out


# ---------------------------------------------------------------------------
# The options side

def digital_trade(ch, expiry, K, F, D, idx, skip, fee_on=True):
    """What it costs to BUY and what selling pays for the digital D*Q(S>K),
    per dollar, on one bracket, fees on the crossed prices included.

    Call side (K >= F): long the lower strike, short the upper.
        buy  = (A.ask - B.bid)/w + fee(A.ask, B.bid)/w
        sell = (A.bid - B.ask)/w - fee(A.bid, B.ask)/w
    Put side (K < F): the digital is D - (P_b - P_a)/w, so buying it is holding
    D and selling the put spread, and selling it is the mirror.
        buy  = D - (B.bid - A.ask)/w + fee(A.ask, B.bid)/w
        sell = D - (B.ask - A.bid)/w - fee(A.bid, B.ask)/w
    Returns None when the bracket does not exist or any leg is one-sided — a
    refusal, not a zero.
    """
    kind = 'C' if K >= F else 'P'
    o = (ch.get(expiry) or {}).get(kind)
    if not o:
        return None
    br = wide_bracket(o, K, skip)
    if not br:
        return None
    a, b = br
    w = b - a
    A, Bq = o[a], o[b]
    if w <= 0 or None in (A['bid'], A['ask'], Bq['bid'], Bq['ask']):
        return None
    fee_buy = (deribit_fee_usd(A['ask'], idx) + deribit_fee_usd(Bq['bid'], idx)) / w
    fee_sell = (deribit_fee_usd(A['bid'], idx) + deribit_fee_usd(Bq['ask'], idx)) / w
    if not fee_on:
        fee_buy = fee_sell = 0.0
    if kind == 'C':
        buy = (A['ask'] - Bq['bid']) / w + fee_buy
        sell = (A['bid'] - Bq['ask']) / w - fee_sell
    else:
        buy = D - (Bq['bid'] - A['ask']) / w + fee_buy
        sell = D - (Bq['ask'] - A['bid']) / w - fee_sell
    return {'buy': buy, 'sell': sell, 'side': kind, 'bracket': (a, b)}


def option_cost(ch, expiry, lo, hi, F, D, idx, skip, fee_on=True):
    """Cost of buying the interval's payoff on one chain and one bracket.
        (K, None)   buy the digital at K
        (None, K)   hold D and sell the digital at K
        (lo, hi)    buy the digital at lo, sell the one at hi
    Both legs of a bucket use the same chain and the same skip."""
    if hi is None:
        t = digital_trade(ch, expiry, lo, F, D, idx, skip, fee_on)
        return None if t is None else t['buy']
    if lo is None:
        t = digital_trade(ch, expiry, hi, F, D, idx, skip, fee_on)
        return None if t is None else D - t['sell']
    a = digital_trade(ch, expiry, lo, F, D, idx, skip, fee_on)
    b = digital_trade(ch, expiry, hi, F, D, idx, skip, fee_on)
    if a is None or b is None:
        return None
    return a['buy'] - b['sell']


def chains(ch, idx, close_at):
    """The two chains that straddle the close, each with its D and forward.
    Returns None when they do not straddle: the band has only one end."""
    near = neighbours(ch, close_at)
    sides = {n['side']: n for n in near}
    if 'before' not in sides or 'after' not in sides:
        return None
    out = []
    for side in ('before', 'after'):
        exp = sides[side]['expiry']
        dis = discount(ch, exp)
        D = dis['D'] if dis else 1.0
        F = forward(ch, exp, idx, D)
        if not F:
            return None
        out.append({'side': side, 'expiry': exp, 'D': D, 'D_estimated': dis is not None,
                    'F': F, 'hours': sides[side]['hours']})
    return out


def band_hours(legs):
    """How far the band reaches: the larger distance of the two chains from
    the close, in hours."""
    return max(abs(c['hours']) for c in legs) if legs else None


def option_band(ch, idx, legs, lo, hi, fee_on=True):
    """Cheapest and dearest estimate over both chains and both brackets.
    None unless each chain supplies at least one estimate (a band needs both
    ends)."""
    per_chain = []
    for c in legs:
        vals = [option_cost(ch, c['expiry'], lo, hi, c['F'], c['D'], idx, s, fee_on)
                for s in SKIPS]
        vals = [v for v in vals if v is not None]
        if not vals:
            return None
        per_chain.append(vals)
    every = [v for vals in per_chain for v in vals]
    return {'min': min(every), 'max': max(every), 'estimates': len(every)}


# ---------------------------------------------------------------------------
# The rules

def classify(pred, opt_min, opt_max, step=ABS):
    """D-114's per-snapshot rule. Costs per dollar of payoff; step is the
    venue's published price step for the legs bought (D-117)."""
    if pred is None or opt_min is None or opt_max is None:
        return UNQUOTED
    if opt_min - pred >= max(REL * pred, step):
        return PREDICTION
    if pred - opt_max >= max(REL * opt_max, step):
        return OPTIONS
    return TIE


def blank():
    return {PREDICTION: 0, OPTIONS: 0, TIE: 0, UNQUOTED: 0}


def stable_class(t):
    """A condition's class across snapshots, or None when it has none: more
    than PERSISTENCE of its judged snapshots on one side, with at least
    MIN_JUDGED judged."""
    judged = t[PREDICTION] + t[OPTIONS] + t[TIE]
    if judged < MIN_JUDGED:
        return None
    if t[PREDICTION] / float(judged) > PERSISTENCE:
        return PREDICTION
    if t[OPTIONS] / float(judged) > PERSISTENCE:
        return OPTIONS
    return None


def verdict(tally):
    """The pre-committed verdict of D-114 over one family."""
    stable = {PREDICTION: [], OPTIONS: []}
    classified = 0
    for key, t in tally.items():
        if t[PREDICTION] + t[OPTIONS] + t[TIE] >= MIN_JUDGED:
            classified += 1
        s = stable_class(t)
        if s:
            stable[s].append(key)
    out = {'conditions': len(tally),
           'conditions_with_enough_judged_snapshots': classified,
           'stably_cheaper_on_prediction_market': len(stable[PREDICTION]),
           'stably_cheaper_on_options': len(stable[OPTIONS]),
           'rules': {'rel': REL, 'abs_default': ABS, 'step': 'venue price step (D-117)',
                     'persistence': PERSISTENCE, 'min_judged': MIN_JUDGED,
                     'skips': list(SKIPS)}}
    if stable[PREDICTION] and stable[OPTIONS]:
        out['verdict'] = VERDICT_DEPENDS
    elif stable[PREDICTION] or stable[OPTIONS]:
        out['verdict'] = VERDICT_ONE
        out['venue'] = 'prediction market' if stable[PREDICTION] else 'options'
    else:
        out['verdict'] = VERDICT_NONE
    return out, stable


# ---------------------------------------------------------------------------
# The reference ticket (illustration, not verdict)

def stake_for_target(cost, capital=TICKET_CAPITAL, target=TICKET_TARGET):
    """Stake that earns target*capital if the condition pays, at a cost per
    dollar of payoff. profit = stake*(1-c)/c, so stake = R*C*c/(1-c).
    None when the cost is not strictly between 0 and 1."""
    if cost is None or not (0.0 < cost < 1.0):
        return None
    return target * capital * cost / (1.0 - cost)


def venue_ticket(route, capital=TICKET_CAPITAL, target=TICKET_TARGET):
    """The same target with whole contracts and each venue's order fee
    (Kalshi's per-order round-up; Polymarket's rate times size, its rounding
    UNKNOWN): contracts, exact stake, profit if right, and whether the resting
    depth at the best level covers it (None when depth is not published)."""
    stake = stake_for_target(route['cost'], capital, target)
    if stake is None:
        return None
    n = int(math.ceil(stake / route['cost']))
    exact = 0.0
    for leg, _side, p in route['_legs']:
        f = leg['order_fee'](p, n)
        if f is None:
            return None
        exact += n * p + f
    return {'contracts': n, 'stake_usd': round(exact, 2),
            'profit_if_right_usd': round(n - exact, 2),
            'max_loss_usd': round(exact, 2),
            'depth_at_best': route['depth'],
            'depth_covers': None if route['depth'] is None else n <= route['depth']}


def linear_references(idx, target=TICKET_TARGET):
    """What a spot long and a perpetual need to move for the same target.
    Carry and liquidation are UNKNOWN (D-114): the funding unit is unread and
    the maintenance margin is not archived."""
    rows = [{'instrument': 'spot long', 'leverage': 1,
             'required_move': target, 'required_level': round(idx * (1 + target), 2),
             'max_loss': 'the stake, linearly', 'carry': None}]
    for L in LEVERAGES:
        rows.append({'instrument': 'perpetual long', 'leverage': L,
                     'required_move': round(target / L, 6),
                     'required_level': round(idx * (1 + target / L), 2),
                     'liquidation_distance': 'UNKNOWN',
                     'carry': 'UNKNOWN (funding unit unread, D-111)'})
    return rows


# ---------------------------------------------------------------------------
# One snapshot

def fmt(x):
    return format(int(x), ',') if float(x) == int(x) else format(x, ',')


def describe(asset, lo, hi):
    if lo is None:
        return '%s below %s' % (asset, fmt(hi))
    if hi is None:
        return '%s above %s' % (asset, fmt(lo))
    return '%s in [%s, %s)' % (asset, fmt(lo), fmt(hi))


def judge(legs, ch, idx, close_at):
    """Every condition of one ladder set, in one snapshot."""
    opt = chains(ch, idx, close_at)
    hours = band_hours(opt)
    rows = []
    for lo, hi in conditions(legs):
        k = venue_cost(legs, lo, hi)
        band = option_band(ch, idx, opt, lo, hi) if opt else None
        step = k['step'] if k else ABS
        cls = classify(k['cost'] if k else None, band['min'] if band else None,
                       band['max'] if band else None, step)
        free = option_band(ch, idx, opt, lo, hi, fee_on=False) if opt else None
        cls_free = classify(k['cost'] if k else None, free['min'] if free else None,
                            free['max'] if free else None, step)
        rows.append({'lo': lo, 'hi': hi, 'pred': k, 'options': band, 'class': cls,
                     'class_without_deribit_fees': cls_free, 'band_hours': hours})
    chains_out = opt and [{x: c[x] for x in ('side', 'expiry', 'D', 'D_estimated', 'hours')}
                          for c in opt]
    return rows, chains_out


def run(stamp):
    """Every family in one snapshot. Returns {family: [group, ...]} where a
    group is one ladder set (an asset's year-end ladder, or an asset's day)
    with its rows. Never raises on a missing piece; the group says what was
    missing."""
    g = snapshot(stamp)
    out = {'kalshi_year_end': [], 'polymarket_daily': []}
    for asset, series, currency in KALSHI_SERIES:
        grp = {'asset': asset, 'event': series}
        M, _events = event_ladder(g.kalshi, series)
        if not M:
            grp['error'] = 'no ladder'
        elif ladder_shape(M)[0] != 'exhaustive':
            grp['error'] = 'ladder not exhaustive'
        else:
            close_at = iso_instant(M[0].get('close_time', ''))
            if close_at is None:
                grp['error'] = 'no close_time'
            else:
                ch, idx = chain(g.deribit, currency)
                grp['legs'] = kalshi_legs(M, series)
                grp['rows'], grp['chains'] = judge(grp['legs'], ch, idx, close_at)
                grp['index'] = idx
        out['kalshi_year_end'].append(grp)
    for asset, key, currency, name in POLY_ASSETS:
        try:
            ch, idx = chain(g.deribit, currency)
        except (KeyError, TypeError):
            continue
        for day, d in sorted(poly_legs((g.polymarket or {}).get(key), name).items()):
            grp = {'asset': asset, 'event': day}
            close_at = iso_instant(d['close'])
            if close_at is None or not d['legs']:
                grp['error'] = 'no close or no legs'
            else:
                grp['legs'] = d['legs']
                grp['rows'], grp['chains'] = judge(d['legs'], ch, idx, close_at)
                grp['index'] = idx
            out['polymarket_daily'].append(grp)
    return out


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def r6(x):
    return None if x is None else round(x, 6)


def main():
    argv = sys.argv[1:]
    last = int(argv[argv.index('--last') + 1]) if '--last' in argv else None
    every = stamps('_meta')
    if last:
        every = every[-last:]
    o = summary()

    fam = {name: {'all': {}, 'narrow': {}, 'free': {}, 'track': {}, 'newest': {},
                  'narrow_rows': 0, 'errors': 0}
           for name, _v, _d in FAMILIES}
    errors = []
    for stamp in every:
        try:
            r = run(stamp)
        except Missing as e:
            errors.append({'stamp': stamp, 'error': str(e)})
            continue
        except (KeyError, TypeError, ValueError) as e:
            errors.append({'stamp': stamp, 'error': '%s: %s' % (type(e).__name__, e)})
            continue
        for name, groups in r.items():
            F = fam[name]
            for grp in groups:
                if 'error' in grp:
                    F['errors'] += 1
                    if name == 'kalshi_year_end':
                        errors.append({'stamp': stamp, 'family': name,
                                       'asset': grp['asset'], 'error': grp['error']})
                    continue
                if name == 'kalshi_year_end' or grp['chains']:
                    prev = F['newest'].get(grp['asset'])
                    if prev is None or prev[0] < stamp or \
                            (prev[0] == stamp and grp['event'] < prev[1]['event']):
                        F['newest'][grp['asset']] = (stamp, grp)
                for row in grp['rows']:
                    key = '%s:%s:%s:%s' % (grp['asset'], grp['event'], row['lo'], row['hi'])
                    F['all'].setdefault(key, blank())[row['class']] += 1
                    F['free'].setdefault(key, blank())[row['class_without_deribit_fees']] += 1
                    narrow = row['band_hours'] is not None and row['band_hours'] <= NARROW_HOURS
                    if narrow:
                        F['narrow'].setdefault(key, blank())[row['class']] += 1
                        if row['class'] != UNQUOTED:
                            F['narrow_rows'] += 1
                    tr = F['track'].setdefault(key, {'asset': grp['asset'], 'event': grp['event'],
                                                     'lo': row['lo'], 'hi': row['hi'],
                                                     'pred': [], 'opt_min': [], 'opt_max': []})
                    if row['class'] != UNQUOTED:
                        tr['pred'].append(row['pred']['cost'])
                        tr['opt_min'].append(row['options']['min'])
                        tr['opt_max'].append(row['options']['max'])

    families = {}
    for name, venue, what in FAMILIES:
        F = fam[name]
        v, stable = verdict(F['all'])
        vn, stable_n = verdict(F['narrow'])
        vf, stable_f = verdict(F['free'])
        per_condition = []
        for key, t in F['all'].items():
            if t[PREDICTION] + t[OPTIONS] + t[TIE] == 0:
                continue
            tr = F['track'][key]
            per_condition.append({
                'condition': describe(tr['asset'], tr['lo'], tr['hi']),
                'asset': tr['asset'], 'event': tr['event'], 'lo': tr['lo'], 'hi': tr['hi'],
                'judged': t[PREDICTION] + t[OPTIONS] + t[TIE], 'unquoted': t[UNQUOTED],
                'cheaper_on_prediction_market': t[PREDICTION],
                'cheaper_on_options': t[OPTIONS], 'indistinguishable': t[TIE],
                'stable': stable_class(t),
                'stable_in_narrow_band': stable_class(F['narrow'][key]) if key in F['narrow'] else None,
                'stable_without_deribit_fees': stable_class(F['free'][key]),
                'median_prediction_cost': r6(median(tr['pred'])),
                'median_options_min': r6(median(tr['opt_min'])),
                'median_options_max': r6(median(tr['opt_max']))})
        per_condition.sort(key=lambda c: (c['asset'], str(c['event']),
                                          -1 if c['lo'] is None else c['lo'],
                                          math.inf if c['hi'] is None else c['hi']))
        ticket = {}
        for asset, (stamp, grp) in sorted(F['newest'].items()):
            rows = []
            for row in grp['rows']:
                k, band = row['pred'], row['options']
                rows.append({
                    'condition': describe(asset, row['lo'], row['hi']),
                    'prediction_cost': None if not k else r6(k['cost']),
                    'prediction_route': None if not k else k['route'],
                    'prediction': None if not k else venue_ticket(k),
                    'options_cost_min': None if not band else r6(band['min']),
                    'options_cost_max': None if not band else r6(band['max']),
                    'options_stake_range_usd': None if not band else [
                        None if stake_for_target(band['min']) is None else round(stake_for_target(band['min']), 2),
                        None if stake_for_target(band['max']) is None else round(stake_for_target(band['max']), 2)],
                    'options_depth': 'UNKNOWN (book_summary carries no sizes)',
                    'class_in_this_snapshot': row['class']})
            ticket[asset] = {'stamp': stamp, 'event': grp['event'], 'index': grp['index'],
                             'chains': grp['chains'], 'band_hours': rows and grp['rows'][0]['band_hours'],
                             'rows': rows, 'linear_references': linear_references(grp['index'])}
        families[name] = {
            'prediction_venue': venue, 'what': what,
            'verdict': v,
            'stable_conditions': {PREDICTION: sorted(stable[PREDICTION]),
                                  OPTIONS: sorted(stable[OPTIONS])},
            'narrow_band': {'hours': NARROW_HOURS, 'judged_rows': F['narrow_rows'],
                            'verdict': vn,
                            'stable_conditions': {PREDICTION: sorted(stable_n[PREDICTION]),
                                                  OPTIONS: sorted(stable_n[OPTIONS])}},
            'sensitivity_combo_fees': {
                'what': 'the same rules with every Deribit fee set to zero (D-115)',
                'reads_into_verdict': False,
                'verdict_if_deribit_fees_were_zero': vf['verdict'],
                'stably_cheaper_on_prediction_market': vf['stably_cheaper_on_prediction_market'],
                'stably_cheaper_on_options': vf['stably_cheaper_on_options']},
            'ladder_sets_skipped': F['errors'],
            'conditions': per_condition,
            'reference_ticket': {'capital_usd': TICKET_CAPITAL, 'target': TICKET_TARGET,
                                 'note': 'illustration of D-114; nothing in any verdict reads it',
                                 'assets': ticket},
        }

    print("THE BUYER'S COMPARISON (D-114, D-117)")
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days' % o)
    for name, venue, what in FAMILIES:
        f = families[name]
        v = f['verdict']
        print()
        print('== %s — %s' % (name, what))
        print('conditions judged: %d, with >= %d judged snapshots: %d'
              % (len(f['conditions']), MIN_JUDGED, v['conditions_with_enough_judged_snapshots']))
        stab = [c for c in f['conditions'] if c['stable']]
        for c in stab[:40]:
            print('  %-36s %-10s judged %3d  pred %8.4f  opt %8.4f-%8.4f'
                  % ((c['condition'] + ' ' + str(c['event']))[:36], c['stable'], c['judged'],
                     c['median_prediction_cost'], c['median_options_min'], c['median_options_max']))
        print('VERDICT (%s vs options): %s%s' % (venue, v['verdict'],
                                                (' (%s)' % v['venue']) if v.get('venue') else ''))
        print('  stably cheaper on %s: %d, on the options: %d'
              % (venue, v['stably_cheaper_on_prediction_market'], v['stably_cheaper_on_options']))
        nb = f['narrow_band']
        print('NARROW BAND (both chains within %d h): %d judged rows -> %s'
              % (NARROW_HOURS, nb['judged_rows'], nb['verdict']['verdict']))
        s = f['sensitivity_combo_fees']
        print('SENSITIVITY (not a verdict), Deribit fees at zero: %s'
              % s['verdict_if_deribit_fees_were_zero'])
    print()
    print('Reading note: costs are per dollar of payoff at the best level, fees in.')
    print('The options side is a band over two brackets and both chains that straddle')
    print('the close; a condition is cheaper on a venue only against the whole band.')
    print('This is what each venue charged for a payoff, not a recommendation, a')
    print('signal or an edge (D-114). Families are judged separately (D-117).')

    record = {
        'archive': o,
        'archive_source': ('private mirror' if os.environ.get('DIVERGENCE_RAW')
                           else '14-day public window'),
        'produced_by': 'scripts/measure_payoff.py',
        'decision': 'D-114, D-117',
        'families': families,
        'errors': errors,
    }
    folder = os.path.join(ROOT, 'findings')
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, 'payoff_frontier.json'), 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
