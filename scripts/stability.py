#!/usr/bin/env python3
"""Stability counter — stops a repeated observation from inflating N.

The problem: "1030 of 3795 rungs exceeded the band" reads as 3795 independent
observations. It is not. The same ladders are measured across 40 snapshots; on
the Kalshi side there are really 44 distinct rungs, each seen about 34 times.
Widening a denominator with a repeated sample buys confidence that was never
earned. This is the other face of the rule that a single snapshot cannot carry
significance: neither can the same snapshot counted many times.

The better question is not "what percentage exceeded" but "which rungs, and in
how many of their observations". A rung that clears the band in 34 of 34 is
structural. One that clears it in 18 of 35 is noise. Both feed the same
percentage; they are not the same finding.

This module tracks each rung by identity and reports the distribution.
"""
from collections import OrderedDict


class Stability(object):
    def __init__(self):
        # key -> [observations, times_exceeded]
        self._seen = OrderedDict()

    def add(self, key, exceeds):
        s = self._seen.setdefault(key, [0, 0])
        s[0] += 1
        if exceeds:
            s[1] += 1

    def __len__(self):
        return len(self._seen)

    def summary(self, always_above=0.9, never_at=0.0):
        """Split rungs by how they behave, not by how often in aggregate."""
        always, sometimes, never = [], [], []
        for key, (n, a) in self._seen.items():
            share = a / float(n) if n else 0.0
            if share > always_above:
                always.append((key, n, a))
            elif share <= never_at:
                never.append((key, n, a))
            else:
                sometimes.append((key, n, a))
        total_obs = sum(n for n, _ in self._seen.values())
        total_exc = sum(a for _, a in self._seen.values())
        return {
            'distinct_rungs': len(self._seen),
            'total_observations': total_obs,
            'total_exceeding': total_exc,
            'always': always, 'sometimes': sometimes, 'never': never,
            'observations_per_rung': (total_obs / float(len(self._seen)))
            if self._seen else 0,
        }

    def report(self, title='STABILITY'):
        o = self.summary()
        print()
        print(title)
        print('  distinct rungs      : %d' % o['distinct_rungs'])
        print('  total observations  : %d  (%.1f per rung)'
              % (o['total_observations'], o['observations_per_rung']))
        print('  ---')
        print('  ALWAYS exceeds      : %d rungs' % len(o['always']))
        print('  SOMETIMES exceeds   : %d rungs  <- suspect noise' % len(o['sometimes']))
        print('  NEVER exceeds       : %d rungs' % len(o['never']))
        if o['always']:
            print('  ---')
            print('  always exceeding (first 12):')
            for key, n, a in o['always'][:12]:
                print('    %-42s %d/%d observations' % (str(key)[:42], a, n))
        print()
        print('  Reading note: stability matters, not the ratio. A rung that clears')
        print('  the band in every observation is structural; one that clears it in')
        print('  half is noise. They contribute equally to a percentage and are not')
        print('  the same thing.')
        return o
