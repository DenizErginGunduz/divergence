#!/usr/bin/env python3
"""Long-horizon touch bound — the third setup, and the only one that ASSUMES A
MODEL.

WHAT TOUCH IS, AND WHY IT IS HARD
"What price will Bitcoin hit in 2026?" asks about touching the level at ANY
moment before expiry. The option chain has NO direct counterpart for that. The
terminal probability P(S_T > K) falls out of prices model-free; touch does not.

So this measurement differs from the others and is labelled as such: the other
two setups are MODEL-FREE, this one ASSUMES A MODEL.

THE BOUND
For driftless arithmetic Brownian motion the reflection principle gives
touch = 2 * terminal. In the real world none of the three assumptions hold:
drift is not zero, monitoring is not continuous, volatility is not a single
number. So "2" is NOT a constant (D-031).

Under lognormal dynamics in the risk-neutral measure, with a = ln(A/F) and
mu = -sigma^2/2:

    terminal = N((-a + mu*T) / (sigma*sqrt(T)))
    touch    = terminal + exp(-a) * N((-a - mu*T) / (sigma*sqrt(T)))

That gives a BOUND, not a point estimate. The ratio should theoretically sit
between 1 and 2. A ratio BELOW 1 is a no-arbitrage violation: the probability
of touching a level before expiry cannot be smaller than the probability of
CLOSING above it at expiry. Counting those violations is the most valuable
output of this script — because a violation contradicts arithmetic, not a
model.

WHERE sigma COMES FROM
From the chain's own implied volatility, linearly interpolated between the two
strikes nearest the threshold. Solving for sigma by bisection was TRIED and
rejected: N(d2) is not monotone in sigma at upper strikes, and the solver
saturated at 400%.

Usage:
    python scripts/measure_touch.py
    python scripts/measure_touch.py --last 5
"""
import math
import re
import sys

from archive import snapshot, stamps, summary, Missing
from measure_band import forward, digital, discount, MONTH
from stability import Stability

ASSETS = [('BTC', 'bitcoin', 'BTC'), ('ETH', 'ethereum', 'ETH')]
TOUCH_TITLE = re.compile(r'What price will (Bitcoin|Ethereum) hit', re.I)
EXPIRY_LABEL = re.compile(r'^(\d+)([A-Z]{3})(\d{2})$')


def _norm(x):
    """Standard normal CDF — no scipy, erf is enough."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def chain_iv(D, currency):
    """Deribit chain plus each strike's implied volatility.
    measure_band.chain does not carry mark_iv; touch needs sigma."""
    idx = D[currency]['index']['result']['index_price']
    bs = D[currency]['book_summary']
    bs = bs['result'] if isinstance(bs, dict) else bs
    ch = {}
    for b in bs:
        q = b['instrument_name'].split('-')
        if len(q) != 4:
            continue
        expiry, strike, kind = q[1], float(q[2]), q[3]
        ch.setdefault(expiry, {}).setdefault(kind, {})[strike] = {
            'mark': (b.get('mark_price') or 0) * idx,
            'bid': b['bid_price'] * idx if b.get('bid_price') else None,
            'ask': b['ask_price'] * idx if b.get('ask_price') else None,
            'iv': (b.get('mark_iv') or 0) / 100.0,
        }
    return ch, idx


def expiry_day(label):
    m = EXPIRY_LABEL.match(label)
    if not m:
        return None
    return (2000 + int(m.group(3))) * 372 + MONTH[m.group(2)] * 31 + int(m.group(1))


def sigma_at(o, K):
    """Linear interpolation between the IVs of the two strikes bracketing K."""
    ks = sorted(k for k in o if o[k].get('iv'))
    if not ks:
        return None
    below = [k for k in ks if k <= K]
    above = [k for k in ks if k >= K]
    if not below or not above:
        # the threshold is outside the chain: use the nearest end, invent nothing
        return o[ks[0]]['iv'] if K < ks[0] else o[ks[-1]]['iv']
    a, b = below[-1], above[0]
    if a == b:
        return o[a]['iv']
    w = (K - a) / (b - a)
    return o[a]['iv'] * (1 - w) + o[b]['iv'] * w


def touch_bound(A, F, sigma, T):
    """Terminal and touch under lognormal. A: threshold, F: forward."""
    if sigma <= 0 or T <= 0 or F <= 0 or A <= 0:
        return None
    a = math.log(A / F)
    mu = -0.5 * sigma * sigma
    root = sigma * math.sqrt(T)
    terminal = _norm((-a + mu * T) / root)
    touch = terminal + math.exp(-a) * _norm((-a - mu * T) / root)
    return {'terminal': terminal, 'touch': min(touch, 1.0)}


def run(stamp, stab):
    g = snapshot(stamp)
    PM, D = g.polymarket, g.deribit
    out = {'stamp': stamp, 'measured': 0, 'violations': 0, 'over_two': 0}
    for asset, key, currency in ASSETS:
        try:
            ch, idx = chain_iv(D, currency)
        except (KeyError, TypeError):
            continue
        for event in (PM.get(key) or []):
            title = event.get('title') or ''
            if not TOUCH_TITLE.search(title):
                continue
            end = (event.get('endDate') or '')[:10]
            if len(end) < 10:
                continue
            target = int(end[:4]) * 372 + int(end[5:7]) * 31 + int(end[8:10])

            usable = [(abs(expiry_day(v) - target), v) for v in ch
                      if ch[v].get('C') and ch[v].get('P') and expiry_day(v)]
            if not usable:
                continue
            usable.sort()
            day_gap, expiry = usable[0]
            # Discount first (D-073): forward() and digital() both need it.
            # The touch ratio itself is a price over a price, so D cancels;
            # what D fixes here is the forward, and with it the A <= F cutoff
            # that decides which contracts are in scope at all.
            dis = discount(ch, expiry)
            D = dis['D'] if dis else 1.0
            F = forward(ch, expiry, idx, D)
            if not F:
                continue
            # time to expiry: target day - measurement day
            today = int(stamp[:4]) * 372 + int(stamp[5:7]) * 31 + int(stamp[8:10])
            T = max((target - today), 1) / 365.0

            for m in (event.get('markets') or []):
                if not (m.get('active') and not m.get('closed')):
                    continue
                raw = (m.get('groupItemTitle') or '').replace(',', '').replace('$', '')
                mm = re.search(r'\d+(?:\.\d+)?', raw)
                bid, ask = m.get('bestBid'), m.get('bestAsk')
                if not mm or bid is None or ask is None:
                    continue
                A = float(mm.group(0))
                if A <= F:        # downside touch is a separate computation, out of scope
                    continue
                # The TERMINAL side must be MODEL-FREE. An earlier version used a
                # lognormal terminal and labelled the result an "arithmetic
                # violation"; that was wrong. Lognormal is a model, and a
                # contradiction with it refutes the model, not arithmetic. For a
                # real violation the terminal has to come straight from option
                # prices (the D-025 digital approach).
                d = digital(ch, expiry, A, F, idx, D)
                if not d or d['p'] <= 0:
                    continue
                pm = (float(bid) + float(ask)) / 2
                if pm <= 0:
                    continue
                terminal = d['p']
                ratio = pm / terminal
                out['measured'] += 1
                # VIOLATION: the probability of touching before expiry cannot be
                # smaller than the probability of closing above at expiry. Since
                # the terminal is model-free, this really is arithmetic.
                if ratio < 1.0:
                    out['violations'] += 1
                # The driftless bound is 2, but "2" is NOT a constant (D-031).
                if ratio > 2.0:
                    out['over_two'] += 1
                stab.add('%s:%s:%g' % (asset, end, A), ratio > 2.0)
    return out


def main():
    argv = sys.argv[1:]
    last = int(argv[argv.index('--last') + 1]) if '--last' in argv else None
    every = stamps('_meta')
    if last:
        every = every[-last:]

    o = summary()
    stab = Stability()
    print('LONG-HORIZON TOUCH BOUND — a MODEL-ASSUMING measurement')
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days' % o)
    print()
    print('%-18s %8s %8s %10s' % ('snapshot', 'measured', 'violate', 'ratio>2'))
    print('-' * 48)

    t_measured = t_violations = t_over = 0
    for stamp in every:
        try:
            s = run(stamp, stab)
        except Missing:
            continue
        if not s['measured']:
            continue
        print('%-18s %8d %8d %10d'
              % (stamp, s['measured'], s['violations'], s['over_two']))
        t_measured += s['measured']
        t_violations += s['violations']
        t_over += s['over_two']

    print('-' * 48)
    print('TOTAL  %8d measurements, %d arithmetic violations, %d with ratio>2'
          % (t_measured, t_violations, t_over))
    if t_measured:
        print('       violation rate %.1f%%  (touch < terminal: IMPOSSIBLE)'
              % (100.0 * t_violations / t_measured))
        print('       ratio>2        %.1f%%  (above the lognormal bound)'
              % (100.0 * t_over / t_measured))
    stab.report('STABILITY — thresholds with ratio>2')

    print()
    print('RATIO = prediction-market touch price / MODEL-FREE terminal digital.')
    print('The terminal comes straight from option prices; no model is assumed.')
    print('')
    print('ratio < 1 : ARITHMETIC violation. Touching before expiry cannot be')
    print('            rarer than closing above at expiry. Contradicts logic,')
    print('            not a model.')
    print('ratio > 2 : above the driftless Brownian bound. This is a WEAKER')
    print('            claim, because "2" is not a constant (D-031).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
