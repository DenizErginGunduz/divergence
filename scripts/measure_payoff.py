#!/usr/bin/env python3
"""The buyer's comparison (D-114): for the same terminal payoff, is it cheaper
to buy on Kalshi or from the Deribit option chain, and does the answer depend
on the condition?

WHY THIS IS NOT THE KILL TEST AGAIN
Every earlier test asked an arbitrageur's question: sell one venue, buy the
other, pay BOTH sides' costs. D-103 answered it: nothing survives. A buyer with
a view trades ONE venue and pays one side's costs, so a gap too small to
arbitrage can still decide where the buyer should pay less. This script asks
that question and nothing more. It never says which condition anyone should
buy; it says, for a given condition, what each venue charged for it.

THE FAMILY (D-114)
The year-end ladders KXBTCY and KXETHY, in every snapshot where they are
exhaustive (D-105). Every condition is an interval of the terminal price:
  - each listed bucket [lo, hi), including the two open-ended rungs;
  - "above K" and "below K" for every internal boundary K.
A condition is identified by its interval, so "above the top boundary" and the
top 'greater' bucket are the same condition and are judged once.

WHAT EACH SIDE COSTS, per dollar of payoff, at the best level
  Kalshi   the cheaper of: the sum of the YES asks of the buckets that make up
           the interval, each plus fees.rate(ask); or, when the interval is the
           complement of a single bucket, that bucket's NO ask plus
           fees.rate(no_ask). The per-order round-up is not in this number; it
           is applied in the reference ticket, where an order size exists.
  Deribit  the same payoff from vertical spreads, ask on every leg bought and
           bid on every leg sold, plus Deribit's fee on those crossed prices
           (kill_test_eth5k.deribit_fee_usd). Side rule as in production: the
           call spread at or above the forward, the discount factor D held and
           the put spread traded below it (D-025, D-032, D-073).

THE BAND
The options cost is an interval, not a point: the cheapest and the dearest of
the tight and one-skip brackets (measure_sensitivity.wide_bracket, skip 0 and
1) on both chains that straddle the Kalshi close (measure_sensitivity.
neighbours). A band needs both ends, so a condition with no estimate on one of
the two chains is 'unquoted' in that snapshot. That is this script's reading
of D-114's "on both bracketing chains"; it can only make a verdict harder to
reach, never easier.

THE RULES — written in D-114 before this file existed; not editable here
  cheaper on Kalshi    opt_min - kalshi >= max(REL * kalshi, ABS)
  cheaper on Deribit   kalshi - opt_max >= max(REL * opt_max, ABS)
  indistinguishable    otherwise
  unquoted             either side has no executable price; not judged
A condition is STABLY cheaper on a venue when it is so in more than
PERSISTENCE of its judged snapshots and it has at least MIN_JUDGED of them.
Verdict over the family: stable conditions on both venues -> VERDICT_DEPENDS;
on one venue only -> VERDICT_ONE; none -> VERDICT_NONE.

COMBO FEES — found after D-114 was written, reported as a sensitivity only
Deribit's Combo Books page says "The cheapest direction of a Combo has reduced
fees, meaning less fees to pay compared to executing each leg individually."
The reduction is not quantified there, and every spread here is charged leg by
leg, as the kill test charges it. So the options cost may be overstated for a
buyer who enters the spread as one combo. The verdict keeps D-114's fee model;
beside it the same rules are applied with every Deribit fee set to zero, the
most favourable case for Deribit, and reported as a sensitivity (D-115).

WHAT IS NOT IN ANY NUMBER HERE (D-114, "What stays UNKNOWN")
Perpetual funding (unit and sign of interest_8h UNKNOWN, D-111), dated futures
(B-018), the depth of the option book (book_summary has no sizes), the margin
a long spread ties up, Deribit's minimum order size, the settlement basis.

Usage:
    python scripts/measure_payoff.py            # whole archive
    python scripts/measure_payoff.py --last 5
"""
import json
import math
import os
import sys

import fees
from archive import snapshot, stamps, summary, Missing
from measure_band import chain, discount, forward, event_ladder, ladder_shape, \
    iso_instant, size_fp
from measure_sensitivity import neighbours, wide_bracket
from kill_test_eth5k import deribit_fee_usd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (asset label, Kalshi series, Deribit currency) — D-096's year-end family.
FAMILY = [
    ('BTC', 'KXBTCY', 'BTC'),
    ('ETH', 'KXETHY', 'ETH'),
]

# The constants of D-114. Written there before this script existed; changing
# them here without a new record is exactly what the pre-commitment forbids,
# and tests/test_measurement.py pins them.
REL = 0.10            # the dearer side must cost at least 10% more
ABS = 0.001           # and at least one price step of the year-end ladders (D-078)
PERSISTENCE = 0.9     # stability.py's always_above, the same rule as D-092
MIN_JUDGED = 10       # fewer judged snapshots and a condition is not classified
SKIPS = (0, 1)        # tight and one-skip brackets

VERDICT_DEPENDS = 'the cheaper venue depends on the condition'
VERDICT_ONE = 'one venue is cheaper wherever either is'
VERDICT_NONE = 'no condition is stably cheaper on either venue'

KALSHI, DERIBIT, TIE, UNQUOTED = 'kalshi', 'deribit', 'indistinguishable', 'unquoted'

# The owner's example (D-114, reference ticket). Illustration only: nothing in
# the verdict reads it.
TICKET_CAPITAL = 1000.0
TICKET_TARGET = 0.20
LEVERAGES = (2, 5)


# ---------------------------------------------------------------------------
# Kalshi side

def price(value):
    """A Kalshi dollar price, or None when it is not a live quote. 0 and 1 are
    what an empty side of the book reads as, and neither can be bought at."""
    try:
        p = float(value)
    except (TypeError, ValueError):
        return None
    return p if 0.0 < p < 1.0 else None


def buckets(M):
    """The ladder's buckets as intervals, lowest first. Edges as measure_band
    reads them (D-067): a 'between' cap of 24,999.99 is an upper edge of
    25,000, and a 'greater' floor of 149,999.99 a lower edge of 150,000."""
    out = []
    for m in M:
        kind = m.get('strike_type')
        if kind == 'less':
            lo, hi = None, round(m['cap_strike'])
        elif kind == 'greater':
            lo, hi = round(m['floor_strike'] + .01), None
        else:
            lo, hi = round(m['floor_strike']), round(m['cap_strike'] + .01)
        out.append({'lo': lo, 'hi': hi, 'ticker': m.get('ticker'),
                    'yes_ask': price(m.get('yes_ask_dollars')),
                    'no_ask': price(m.get('no_ask_dollars')),
                    # The quantity at the best NO ask is the quantity at the
                    # best YES bid: the same resting order seen from the
                    # other side (measure_band.size_fp).
                    'yes_ask_size': size_fp(m.get('yes_ask_size_fp')),
                    'no_ask_size': size_fp(m.get('yes_bid_size_fp'))})
    out.sort(key=lambda b: -1 if b['lo'] is None else b['lo'])
    return out


def conditions(B):
    """Every interval D-114 judges, once each: the buckets, then 'above K' and
    'below K' for every internal boundary. Keyed by (lo, hi) so a duplicate
    payoff collapses into one condition."""
    seen = {}
    for b in B:
        seen[(b['lo'], b['hi'])] = None
    for K in [b['lo'] for b in B if b['lo'] is not None]:
        seen[(K, None)] = None
        seen[(None, K)] = None
    return list(seen)


def inside(b, lo, hi):
    """Is bucket b wholly inside the interval [lo, hi)? None is open-ended."""
    b_lo = -math.inf if b['lo'] is None else b['lo']
    b_hi = math.inf if b['hi'] is None else b['hi']
    c_lo = -math.inf if lo is None else lo
    c_hi = math.inf if hi is None else hi
    return c_lo <= b_lo and b_hi <= c_hi


def kalshi_cost(B, lo, hi, series):
    """Cheapest way the ladder sells the interval at the top of the book, per
    dollar of payoff, taker fee at its per-contract rate. Returns
    {cost, route, depth, legs} or None when no route has a live quote."""
    legs = [b for b in B if inside(b, lo, hi)]
    rest = [b for b in B if not inside(b, lo, hi)]
    routes = []
    if legs and all(b['yes_ask'] is not None for b in legs):
        cost = sum(b['yes_ask'] + fees.rate(b['yes_ask'], series) for b in legs)
        sizes = [b['yes_ask_size'] for b in legs]
        routes.append({'cost': cost, 'route': 'yes',
                       'depth': None if None in sizes else min(sizes),
                       'legs': [(b['ticker'], 'yes', b['yes_ask']) for b in legs]})
    if len(rest) == 1 and rest[0]['no_ask'] is not None:
        b = rest[0]
        routes.append({'cost': b['no_ask'] + fees.rate(b['no_ask'], series),
                       'route': 'no', 'depth': b['no_ask_size'],
                       'legs': [(b['ticker'], 'no', b['no_ask'])]})
    if not routes:
        return None
    return min(routes, key=lambda r: r['cost'])


# ---------------------------------------------------------------------------
# Deribit side

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

def classify(kalshi, opt_min, opt_max):
    """D-114's per-snapshot rule. Arguments are costs per dollar of payoff."""
    if kalshi is None or opt_min is None or opt_max is None:
        return UNQUOTED
    if opt_min - kalshi >= max(REL * kalshi, ABS):
        return KALSHI
    if kalshi - opt_max >= max(REL * opt_max, ABS):
        return DERIBIT
    return TIE


def stable_class(t):
    """A condition's class across snapshots, or None when it has none: more
    than PERSISTENCE of its judged snapshots on one venue, with at least
    MIN_JUDGED judged."""
    judged = t[KALSHI] + t[DERIBIT] + t[TIE]
    if judged < MIN_JUDGED:
        return None
    if t[KALSHI] / float(judged) > PERSISTENCE:
        return KALSHI
    if t[DERIBIT] / float(judged) > PERSISTENCE:
        return DERIBIT
    return None


def verdict(tally):
    """The pre-committed verdict of D-114 over the whole family."""
    stable = {KALSHI: [], DERIBIT: []}
    classified = 0
    for key, t in tally.items():
        judged = t[KALSHI] + t[DERIBIT] + t[TIE]
        if judged >= MIN_JUDGED:
            classified += 1
        s = stable_class(t)
        if s:
            stable[s].append(key)
    out = {'conditions': len(tally),
           'conditions_with_enough_judged_snapshots': classified,
           'stably_cheaper_on_kalshi': len(stable[KALSHI]),
           'stably_cheaper_on_deribit': len(stable[DERIBIT]),
           'rules': {'rel': REL, 'abs': ABS, 'persistence': PERSISTENCE,
                     'min_judged': MIN_JUDGED, 'skips': list(SKIPS)}}
    if stable[KALSHI] and stable[DERIBIT]:
        out['verdict'] = VERDICT_DEPENDS
    elif stable[KALSHI] or stable[DERIBIT]:
        out['verdict'] = VERDICT_ONE
        out['venue'] = KALSHI if stable[KALSHI] else DERIBIT
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


def kalshi_ticket(k, series, capital=TICKET_CAPITAL, target=TICKET_TARGET):
    """The same target on Kalshi with whole contracts and the fee's per-order
    round-up (fees.order_fee): contracts, exact stake, profit if right, and
    whether the resting depth at the best level covers it."""
    stake = stake_for_target(k['cost'], capital, target)
    if stake is None:
        return None
    n = int(math.ceil(stake / k['cost']))
    exact = sum(n * p + fees.order_fee(p, n, series) for _t, _s, p in k['legs'])
    return {'contracts': n, 'stake_usd': round(exact, 2),
            'profit_if_right_usd': round(n - exact, 2),
            'max_loss_usd': round(exact, 2),
            'depth_at_best': k['depth'],
            'depth_covers': None if k['depth'] is None else n <= k['depth']}


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

def describe(asset, lo, hi):
    if lo is None:
        return '%s below %s' % (asset, format(hi, ','))
    if hi is None:
        return '%s above %s' % (asset, format(lo, ','))
    return '%s in [%s, %s)' % (asset, format(lo, ','), format(hi, ','))


def run(stamp):
    """Every condition of the family in one snapshot. Never raises on a
    missing piece; the row says what was missing."""
    g = snapshot(stamp)
    out = {'stamp': stamp, 'assets': {}}
    for asset, series, currency in FAMILY:
        M, _events = event_ladder(g.kalshi, series)
        if not M:
            out['assets'][asset] = {'error': 'no ladder'}
            continue
        shape, _breaks = ladder_shape(M)
        if shape != 'exhaustive':
            out['assets'][asset] = {'error': 'ladder not exhaustive (%s)' % shape}
            continue
        close_at = iso_instant(M[0].get('close_time', ''))
        if close_at is None:
            out['assets'][asset] = {'error': 'no close_time'}
            continue
        ch, idx = chain(g.deribit, currency)
        legs = chains(ch, idx, close_at)
        B = buckets(M)
        rows = []
        for lo, hi in conditions(B):
            k = kalshi_cost(B, lo, hi, series)
            band = option_band(ch, idx, legs, lo, hi) if legs else None
            cls = classify(k['cost'] if k else None,
                           band['min'] if band else None,
                           band['max'] if band else None)
            # The sensitivity to Deribit's combo fee rule, which is not
            # modelled (see COMBO FEES in the header). Never read by the
            # verdict.
            free = option_band(ch, idx, legs, lo, hi, fee_on=False) if legs else None
            cls_free = classify(k['cost'] if k else None,
                                free['min'] if free else None,
                                free['max'] if free else None)
            rows.append({'lo': lo, 'hi': hi, 'kalshi': k, 'options': band,
                         'class': cls, 'class_without_deribit_fees': cls_free})
        out['assets'][asset] = {
            'series': series, 'index': idx, 'rows': rows,
            'chains': legs and [{k2: c[k2] for k2 in ('side', 'expiry', 'D',
                                                     'D_estimated', 'hours')}
                                for c in legs]}
    return out


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def main():
    argv = sys.argv[1:]
    last = int(argv[argv.index('--last') + 1]) if '--last' in argv else None
    every = stamps('_meta')
    if last:
        every = every[-last:]
    o = summary()

    tally, track, errors = {}, {}, []
    tally_free = {}
    newest = {}
    for stamp in every:
        try:
            r = run(stamp)
        except Missing as e:
            errors.append({'stamp': stamp, 'error': str(e)})
            continue
        except (KeyError, TypeError, ValueError) as e:
            errors.append({'stamp': stamp, 'error': '%s: %s' % (type(e).__name__, e)})
            continue
        for asset, a in r['assets'].items():
            if 'error' in a:
                errors.append({'stamp': stamp, 'asset': asset, 'error': a['error']})
                continue
            newest[asset] = (stamp, a)
            for row in a['rows']:
                key = '%s:%s:%s' % (asset, row['lo'], row['hi'])
                t = tally.setdefault(key, {KALSHI: 0, DERIBIT: 0, TIE: 0, UNQUOTED: 0})
                t[row['class']] += 1
                tf = tally_free.setdefault(key, {KALSHI: 0, DERIBIT: 0, TIE: 0, UNQUOTED: 0})
                tf[row['class_without_deribit_fees']] += 1
                tr = track.setdefault(key, {'asset': asset, 'lo': row['lo'],
                                            'hi': row['hi'], 'kalshi': [],
                                            'opt_min': [], 'opt_max': []})
                if row['class'] != UNQUOTED:
                    tr['kalshi'].append(row['kalshi']['cost'])
                    tr['opt_min'].append(row['options']['min'])
                    tr['opt_max'].append(row['options']['max'])

    v, stable = verdict(tally)
    v_free, stable_free = verdict(tally_free)
    sensitivity = {
        'what': 'the same rules with every Deribit fee set to zero',
        'why': ("Deribit states that combo orders carry reduced fees; the size of the "
                "reduction is UNKNOWN and this script charges every leg in full. Zero "
                "is the most favourable case for Deribit, so a condition that stays "
                "cheaper on Kalshi here does not depend on the combo rule."),
        'reads_into_verdict': False,
        'verdict_if_deribit_fees_were_zero': v_free['verdict'],
        'stably_cheaper_on_kalshi': v_free['stably_cheaper_on_kalshi'],
        'stably_cheaper_on_deribit': v_free['stably_cheaper_on_deribit'],
        'stable_conditions': {KALSHI: sorted(stable_free[KALSHI]),
                              DERIBIT: sorted(stable_free[DERIBIT])},
    }

    per_condition = []
    for key, t in tally.items():
        tr = track[key]
        per_condition.append({
            'condition': describe(tr['asset'], tr['lo'], tr['hi']),
            'asset': tr['asset'], 'lo': tr['lo'], 'hi': tr['hi'],
            'judged': t[KALSHI] + t[DERIBIT] + t[TIE], 'unquoted': t[UNQUOTED],
            'cheaper_on_kalshi': t[KALSHI], 'cheaper_on_deribit': t[DERIBIT],
            'indistinguishable': t[TIE], 'stable': stable_class(t),
            'stable_without_deribit_fees': stable_class(tally_free[key]),
            'median_kalshi_cost': median(tr['kalshi']),
            'median_options_min': median(tr['opt_min']),
            'median_options_max': median(tr['opt_max'])})
    per_condition.sort(key=lambda c: (c['asset'],
                                      -1 if c['lo'] is None else c['lo'],
                                      math.inf if c['hi'] is None else c['hi']))

    # The reference ticket, on the newest snapshot of each asset.
    ticket = {'capital_usd': TICKET_CAPITAL, 'target': TICKET_TARGET,
              'note': 'illustration of D-114; nothing in the verdict reads it',
              'assets': {}}
    for asset, series, _cur in FAMILY:
        if asset not in newest:
            continue
        stamp, a = newest[asset]
        rows = []
        for row in a['rows']:
            k, band = row['kalshi'], row['options']
            rows.append({
                'condition': describe(asset, row['lo'], row['hi']),
                'kalshi_cost': None if not k else round(k['cost'], 6),
                'kalshi_route': None if not k else k['route'],
                'kalshi': None if not k else kalshi_ticket(k, series),
                'options_cost_min': None if not band else round(band['min'], 6),
                'options_cost_max': None if not band else round(band['max'], 6),
                'options_stake_range_usd': None if not band else [
                    None if stake_for_target(band['min']) is None else round(stake_for_target(band['min']), 2),
                    None if stake_for_target(band['max']) is None else round(stake_for_target(band['max']), 2)],
                'options_depth': 'UNKNOWN (book_summary carries no sizes)',
                'class_in_this_snapshot': row['class']})
        ticket['assets'][asset] = {'stamp': stamp, 'index': a['index'],
                                   'chains': a['chains'], 'rows': rows,
                                   'linear_references': linear_references(a['index'])}

    print("THE BUYER'S COMPARISON (D-114)")
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days' % o)
    print('conditions: %d, with >= %d judged snapshots: %d'
          % (v['conditions'], MIN_JUDGED, v['conditions_with_enough_judged_snapshots']))
    print()
    print('%-34s %6s %5s %5s %5s  %-8s %8s %8s %8s'
          % ('condition', 'judged', 'K', 'D', 'tie', 'stable', 'kalshi', 'opt_min', 'opt_max'))
    print('-' * 104)
    for c in per_condition:
        fmt = lambda x: '-' if x is None else '%.4f' % x
        print('%-34s %6d %5d %5d %5d  %-8s %8s %8s %8s'
              % (c['condition'][:34], c['judged'], c['cheaper_on_kalshi'],
                 c['cheaper_on_deribit'], c['indistinguishable'], c['stable'] or '-',
                 fmt(c['median_kalshi_cost']), fmt(c['median_options_min']),
                 fmt(c['median_options_max'])))
    print('-' * 104)
    print('VERDICT: %s%s' % (v['verdict'], (' (%s)' % v['venue']) if v.get('venue') else ''))
    print('  stably cheaper on Kalshi: %d, on Deribit: %d'
          % (v['stably_cheaper_on_kalshi'], v['stably_cheaper_on_deribit']))
    print('SENSITIVITY (not the verdict): with every Deribit fee set to zero,')
    print('  stably cheaper on Kalshi: %d, on Deribit: %d -> %s'
          % (v_free['stably_cheaper_on_kalshi'], v_free['stably_cheaper_on_deribit'],
             v_free['verdict']))
    print()
    print('Reading note: costs are per dollar of payoff at the best level, fees in.')
    print('The options side is a band over two brackets and both chains that straddle')
    print('the close; a condition is cheaper on a venue only against the whole band.')
    print('This is what each venue charged for a payoff, not a recommendation, a')
    print('signal or an edge (D-114). Option depth, spread margin, perpetual carry and')
    print('the settlement basis are not in any number here.')

    record = {
        'archive': o,
        'archive_source': ('private mirror' if os.environ.get('DIVERGENCE_RAW')
                           else '14-day public window'),
        'produced_by': 'scripts/measure_payoff.py',
        'decision': 'D-114',
        'family': [s for _a, s, _c in FAMILY],
        'verdict': v,
        'stable_conditions': {KALSHI: sorted(stable[KALSHI]), DERIBIT: sorted(stable[DERIBIT])},
        'sensitivity_combo_fees': sensitivity,
        'conditions': per_condition,
        'reference_ticket': ticket,
        'errors': errors,
    }
    folder = os.path.join(ROOT, 'findings')
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, 'payoff_frontier.json'), 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
