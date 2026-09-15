#!/usr/bin/env python3
"""Event semantics — does the rule text describe the event we are pricing?

THE QUESTION
Everything else in this repository compares a Kalshi price with an option
price. That comparison is only meaningful if the two contracts pay out on the
same event. So far the event has been taken from three numeric fields —
strike_type, floor_strike, cap_strike — and the rule text has never been read
by anything but a human. This script reads it.

It answers three separate questions, and keeps them separate on purpose:

  1. Do the numbers in rules_primary agree with the numeric fields?
     A mismatch here would mean every digital on that rung is priced against
     the wrong threshold.

  2. Do the rules tile the outcome space?
     The exhaustiveness constraint assumes the ladder partitions the line. If
     the RULES leave a gap, the constraint is checking a computation against
     an assumption the contracts do not satisfy.

  3. What settles these contracts, in their own words?
     This one has no pass/fail. It is an inventory, printed verbatim, because
     the settlement source and instant are where the Kalshi and Deribit
     contracts differ most and that difference is not currently in any number
     the project produces.

WHAT COUNTS AS A FAILURE
A rule that does not parse is UNKNOWN, not "probably fine". The regex is
deliberately rigid: if Kalshi changes the sentence, the right outcome is that
this script stops recognising it and says so. Guessing the meaning of a
resolution rule is the one thing that must not happen quietly.

Usage:
    python scripts/audit_semantics.py
    python scripts/audit_semantics.py --last 5
    python scripts/audit_semantics.py --verbatim   # print every rule in full
"""
import re
import sys
from collections import Counter, OrderedDict

from archive import snapshot, stamps, summary, Missing
from measure_band import SERIES

# The rule sentence, as Kalshi writes it today. Example, quoted exactly:
#
#   "If the simple average of the sixty seconds of CF Benchmarks' BRTI before
#    12 AM EST is below 20000.00 at 12 AM EST on Jan 1, 2027, then the market
#    resolves to Yes."
#
# Every part that could change is captured rather than assumed, so a change
# shows up as a different inventory line instead of a silent pass.
RULE = re.compile(
    r"^If the simple average of the (?P<window>[a-z\- ]+?) seconds of "
    r"(?P<source>.+?) before (?P<observed_at>.+?) is "
    r"(?P<relation>above|below|between) (?P<numbers>[0-9,.\-]+) at "
    r"(?P<settles_at>.+?) on (?P<settles_on>.+?), then the market resolves "
    r"to Yes\.$")

# Kalshi quotes settlement values to two decimals (price_level_structure says
# "deci_cent"). Two adjacent buckets that end at .99 and start at .00 are
# therefore touching: the 0.01 between them is not a reachable value. This is
# the assumption D-067's boundary rule rests on, so it is named here instead
# of living in a comment.
TICK = 0.01


def number(s):
    """'39,999.99' -> 39999.99. Returns None rather than raising, because an
    unparseable number is a verdict, not a crash."""
    try:
        return float(s.replace(',', ''))
    except (ValueError, AttributeError):
        return None


def parse_rule(text):
    """rules_primary -> its parts, or None if the sentence is not the one we
    know. None is a result: the caller reports UNKNOWN."""
    if not text:
        return None
    m = RULE.match(text.strip())
    if not m:
        return None
    d = m.groupdict()
    raw = d['numbers']
    if d['relation'] == 'between':
        parts = raw.split('-')
        if len(parts) != 2:
            return None
        d['low'], d['high'] = number(parts[0]), number(parts[1])
        if d['low'] is None or d['high'] is None:
            return None
    else:
        d['low'] = d['high'] = number(raw)
        if d['low'] is None:
            return None
    return d


def check_numbers(m, rule):
    """Question 1: the rule's numbers against the numeric fields.

    'less' must pair with 'below' and the cap; 'greater' with 'above' and the
    floor; 'between' with both. Anything else is a MISMATCH — including a
    relation that does not match the strike_type, which would be the more
    dangerous error of the two because the number would still look right.
    """
    kind = m.get('strike_type')
    fl, cap = m.get('floor_strike'), m.get('cap_strike')
    rel = rule['relation']
    if kind == 'less':
        if rel != 'below':
            return 'MISMATCH', 'strike_type less, rule says %s' % rel
        if cap is None or abs(rule['low'] - cap) > 1e-9:
            return 'MISMATCH', 'cap_strike %s, rule threshold %s' % (cap, rule['low'])
        return 'AGREE', ''
    if kind == 'greater':
        if rel != 'above':
            return 'MISMATCH', 'strike_type greater, rule says %s' % rel
        if fl is None or abs(rule['low'] - fl) > 1e-9:
            return 'MISMATCH', 'floor_strike %s, rule threshold %s' % (fl, rule['low'])
        return 'AGREE', ''
    if kind == 'between':
        if rel != 'between':
            return 'MISMATCH', 'strike_type between, rule says %s' % rel
        if fl is None or cap is None:
            return 'MISMATCH', 'between market with a missing bound'
        if abs(rule['low'] - fl) > 1e-9 or abs(rule['high'] - cap) > 1e-9:
            return 'MISMATCH', ('fields [%s, %s], rule [%s, %s]'
                                % (fl, cap, rule['low'], rule['high']))
        return 'AGREE', ''
    return 'UNKNOWN', 'strike_type %r is not one this script knows' % kind


def tiling(rules):
    """Question 2: do the parsed intervals cover the line without gaps or
    overlaps, once a two-decimal settlement value is assumed?

    Takes the parsed rules of one ladder. The open-ended ends are the two
    sentinels: a 'below X' rung covers everything under X, an 'above Y' rung
    everything over it. Between them the 'between' rungs must chain, each one
    starting exactly one tick above where the last ended.
    """
    lows = sorted((r['low'], r['high'], r['relation']) for r in rules
                  if r['relation'] == 'between')
    problems = []
    for (lo1, hi1, _), (lo2, hi2, _) in zip(lows, lows[1:]):
        step = round(lo2 - hi1, 6)
        if abs(step - TICK) > 1e-9:
            problems.append('%.2f ends, %.2f starts: %.2f apart, not one tick'
                            % (hi1, lo2, step))
    below = [r for r in rules if r['relation'] == 'below']
    above = [r for r in rules if r['relation'] == 'above']
    if len(below) != 1 or len(above) != 1:
        problems.append('%d open-below and %d open-above rungs, expected one each'
                        % (len(below), len(above)))
    elif lows:
        if abs(round(lows[0][0] - below[0]['low'], 6)) > 1e-9:
            problems.append('lowest bucket starts at %.2f but the open-below '
                            'rung stops at %.2f' % (lows[0][0], below[0]['low']))
        if abs(round(above[0]['low'] - lows[-1][1], 6)) > 1e-9:
            problems.append('highest bucket ends at %.2f but the open-above '
                            'rung starts at %.2f' % (lows[-1][1], above[0]['low']))
    return problems


def audit(KA, series):
    """One ladder: verdict per rung, plus the parsed rules for the tiling
    check and the settlement inventory."""
    M = [m for m in (KA.get('markets', {}).get(series) or [])
         if m.get('status') == 'active']
    rows, parsed = [], []
    for m in M:
        rule = parse_rule(m.get('rules_primary'))
        if not rule:
            rows.append({'ticker': m.get('ticker'), 'verdict': 'UNKNOWN',
                         'detail': 'rules_primary did not parse',
                         'text': m.get('rules_primary')})
            continue
        v, detail = check_numbers(m, rule)
        rows.append({'ticker': m.get('ticker'), 'verdict': v, 'detail': detail,
                     'text': m.get('rules_primary')})
        parsed.append(rule)
    return rows, parsed


def main():
    argv = sys.argv[1:]
    last = int(argv[argv.index('--last') + 1]) if '--last' in argv else None
    verbatim = '--verbatim' in argv

    every = stamps('_meta')
    if last:
        every = every[-last:]
    o = summary()

    verdicts = Counter()
    bad = OrderedDict()          # ticker -> (verdict, detail, text)
    settlement = Counter()       # the inventory, one line per distinct wording
    tiling_problems = Counter()
    ladders = 0

    absent = 0
    for stamp in every:
        # snapshot() succeeds even when a stream is missing; Missing is raised
        # when the stream is actually READ. Touching g.kalshi inside the try is
        # therefore not optional — the first version of this loop crashed on
        # 2026-08-31T0508Z, a snapshot with no Kalshi file at all.
        try:
            g = snapshot(stamp)
            KA = g.kalshi
        except Missing:
            absent += 1
            continue
        for _asset, series, _ccy in SERIES:
            rows, parsed = audit(KA, series)
            if not rows:
                continue
            ladders += 1
            for r in rows:
                verdicts[r['verdict']] += 1
                if r['verdict'] != 'AGREE' and r['ticker'] not in bad:
                    bad[r['ticker']] = (r['verdict'], r['detail'], r['text'])
            for p in parsed:
                settlement['%s | %s-second average before %s | settles %s on %s'
                           % (p['source'], p['window'], p['observed_at'],
                              p['settles_at'], p['settles_on'])] += 1
            for problem in tiling(parsed):
                tiling_problems['%s: %s' % (series, problem)] += 1

    print('EVENT SEMANTICS — the rule text against the numeric fields')
    print('archive: %(snapshot_count)d snapshots / %(day_count)d days' % o)
    print('scanned: %d ladders' % ladders)
    if absent:
        print('skipped: %d snapshots with no Kalshi stream' % absent)
    print()

    total = sum(verdicts.values())
    print('1. NUMBERS')
    for v in ('AGREE', 'MISMATCH', 'UNKNOWN'):
        n = verdicts.get(v, 0)
        print('   %-9s %6d  %5.1f%%' % (v, n, 100.0 * n / total if total else 0))
    if bad:
        print()
        print('   Every rung that was not AGREE, once each, rule text verbatim:')
        for ticker, (v, detail, text) in bad.items():
            print('   %-32s %s  %s' % (ticker, v, detail))
            print('     "%s"' % (text or ''))
    print()

    print('2. TILING')
    if not tiling_problems:
        print('   No gaps and no overlaps. Adjacent buckets are exactly one')
        print('   tick (%.2f) apart, which is what makes the exhaustiveness' % TICK)
        print('   constraint a statement about the contracts and not just')
        print('   about our arithmetic. See D-067.')
    else:
        for problem, n in tiling_problems.most_common():
            print('   x%-5d %s' % (n, problem))
    print()

    print('3. SETTLEMENT — verbatim, no pass or fail')
    for line, n in settlement.most_common():
        print('   x%-6d %s' % (n, line))
    print()
    print('   Read this against the option side. Deribit settles on its own')
    print('   index at 08:00 UTC on the expiry date; nothing above says that.')
    print('   A different reference rate, a different averaging window and a')
    print('   different instant are three separate reasons the two prices can')
    print('   differ without either being wrong. None of them is inside the')
    print('   friction band today.')

    if verbatim:
        print()
        print('4. EVERY RULE, IN FULL')
        for stamp in reversed(every):
            try:
                g = snapshot(stamp)
                KA = g.kalshi
            except Missing:
                continue
            for _asset, series, _ccy in SERIES:
                rows, _ = audit(KA, series)
                for r in rows:
                    print('   %-32s %s' % (r['ticker'], r['verdict']))
                    print('     "%s"' % (r['text'] or ''))
            break

    # A mismatch is a reason to stop, not a line in a report. UNKNOWN is not:
    # it means this script does not recognise the sentence, which is a gap in
    # the script until someone reads the new wording and decides.
    return 1 if verdicts.get('MISMATCH') else 0


if __name__ == '__main__':
    sys.exit(main())
