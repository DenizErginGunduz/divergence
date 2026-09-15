# Research Note 1 — Four dollars and sixty-nine cents

**Divergence · 2026-09-15 · BTC and ETH, Kalshi and Polymarket against Deribit**

We went looking for places where two markets disagree about the same future
event. We found three. At the prices actually quoted, after both venues'
published fees, they were worth **four dollars and sixty-nine cents** between
them — and two of the three cannot be told apart from the fact that the
contracts settle a week apart.

This note is the short version of how that number was arrived at. Every figure
in it is regenerated from an archive of raw exchange payloads by a script in the
repository; none is typed in by hand.

---

## The question

A prediction market quotes a probability directly: "Bitcoin above $150,000 on
1 January 2027" trades at 1.2 cents. An option chain implies one indirectly,
through the price difference between neighbouring strikes. Same event, two
answers, and comparing them needs no model of how prices move.

The interesting case is where they disagree. The uninteresting and much more
common case is where they appear to disagree because something in the
comparison is wrong.

## Three things that have to be right first

**The option side is not a probability.** The difference quotient between two
strikes returns `D · Q(S > K)` — a *discounted state price* under the risk-neutral
measure. Dividing by the discount factor gives `Q`, which is still not a
real-world probability; the gap between them is the volatility risk premium.
Conveniently, a Kalshi price is also a present value — what you pay today for a
dollar at settlement — so the two sit on the same footing without adjustment.

For most of this project's life the put branch of that calculation returned
`1 − D · Q(S < K)` instead of `D − D · Q(S < K)`. With a discount factor of 1 the
two expressions are identical, which is why it survived review. The check that
should have caught it — the requirement that an exhaustive ladder's prices sum
to 1 — could not, because `D·1 + (1−D) = 1` for any `D` at all. The constraint was
arithmetically blind to the error sitting inside it.

**The contracts do not settle on the same thing.** Kalshi settles on a
sixty-second average of CF Benchmarks' BRTI at a stated instant. Deribit settles
on its own index at 08:00 UTC. Three differences follow, and all three have now
been measured:

| difference | size |
|---|---|
| reference rate, BRTI against the Deribit index | **below 0.6 bp** — about six dollars on an 87,000 index |
| averaging window, 60 seconds | negligible against a horizon of hours or months |
| settlement instant | **165 hours** on the year-end ladders |

The first two can be set aside. The third cannot, and it turns out to be the
whole story.

**A price difference is not an opportunity.** Both venues charge. Kalshi's
published taker fee is `round up(0.07 × C × P × (1−P))` per order, rounded to the
cent; Deribit charges 0.03% of the underlying capped at 12.5% of the premium,
on both legs. And a difference with nothing resting behind it is a price
observation, not a trade.

## What replaced the old test

The comparison used to be `|mid − mid| > 1.96 × SE + fees`. That standard-error term
described how uncertain *our estimate* of the option mid was — a question about
our own arithmetic that nobody can trade on.

It is now two trades, each leg priced at a quote that is standing:

    sell the prediction at its BID, buy the bucket at its ASK side, pay both
    venues' fees.  Anything left?
    ... or the mirror of that.

No mid appears anywhere in the verdict. The two hurdles turn out to be almost
the same size — about 2% apart for comparable spreads — so this was never a
tightening. It was a change in what the number refers to.

## What we found

**Three rungs, and they persist.** Across 61 snapshots and 16 days, 44 distinct
Kalshi year-end rungs were measured 55 times each. Three of them showed a
positive edge in essentially every observation; one showed it sometimes; forty
never did. The three are all tails: BTC above $150k, ETH above $5k, ETH below
$1k. Nothing in the body of any distribution came close.

A persistent, reproducible difference is worth something as an observation. The
question is what it is worth as money.

**It is worth $4.69.** Both size fields are archived, so the edge can be
multiplied by the contracts actually resting at the quote being hit:

| rung | net edge | resting | worth |
|---|---|---|---|
| ETH below $1,000 | 0.43c | 1,063 contracts | **$4.54** |
| ETH above $5,000 | 1.11c | 10 contracts | **$0.11** |
| BTC above $150,000 | 0.52c | 7 contracts | **$0.04** |

Across the whole archive the median positive edge is worth **86 cents** and the
largest ever seen is **$125.52**. An edge of a cent on ten contracts is a price
observation. It is not a business.

**And two of the three are the clock.** Kalshi's year-end contracts settle
1 January 2027. Deribit's nearest expiries are 25 December 2026 (165 hours
early) and 26 March 2027 (2,019 hours late). A tail probability grows with
maturity, so the settlement-date value lies between the two. Of 165
rung-observations, 84 sit above both ends and 81 sit inside the band. On the
most recent snapshot only **ETH above $5,000** clears both — and it clears by
about 0.4 cents, a margin comparable to an uncertainty that has not been
measured on the chain that decides it.

**The obvious fix does not work.** Kalshi lists intraday ladders that settle the
same day, which should shrink the expiry gap from 165 hours to about 18. It
does — and on the conservative side, since the option now expires *after* the
Kalshi close and therefore overstates an upside tail rather than understating
it. But the intraday ladder steps its thresholds by $100 and Deribit's strikes
are far wider, so **67% of intraday rungs return a digital identical to another
rung of the same ladder**. Runs of nine consecutive thresholds come back with
the same number. The option chain cannot see a hundred-dollar step.

The two tenors fail in opposite directions. Year-end has strikes fine enough
that no two rungs collide and an expiry gap wide enough to explain most of what
it finds. Intraday has an acceptable expiry gap and a chain that cannot resolve
the ladder. That is a structural property of comparing two venues whose contract
grids were designed for different purposes, not a bug with a fix.

## The second venue, and the number that was half method

Polymarket lists the same kind of ladder, and until this note was being written
its figures were computed by the **old** method: the pre-repair discount
convention, a 1.96·SE band around two mids, and — the worst of it — no fee at
all on the prediction leg. The number sat in the same results file as the
repaired Kalshi one, formatted the same way.

Polymarket does charge. Every market in our archive carries its own schedule
and always has:

    feeSchedule: {"exponent": 1, "rate": 0.07, "takerOnly": true, ...}
    fee = C × rate × p × (1 − p)

The same formula and the same coefficient as Kalshi, taker only, and our trades
cross. It averages **0.65 cents a share** — the same order as the edges being
measured. The code had called it a maker fee and set it to zero.

Under the same test as everything else:

| | old method | same test as Kalshi |
|---|---|---|
| share of quotable rungs with an edge | **24.2%** | **10.3%** |
| rungs where the expiry matched within 12 hours | 26.3% | **8.3%** |
| always / sometimes / never | 9 / 298 / 92 | 3 / 173 / 214 |

More than half of it was method, and the mass moved from "sometimes" to
"never".

**One detail is worth more than the headline.** A tighter expiry match should
*reduce* apparent divergence — less of the gap can be the clock. Under the old
method it did the opposite: the better-matched contracts disagreed *more*, 26.3%
against 24.2%. That inversion was visible in the results file for two weeks and
nobody read it, because neither number looks wrong on its own. Under the
repaired test the sign points the right way.

10.3% against Kalshi's 6.8% is **not** a like-for-like comparison — different
tenor, different ladder shape, different expiry alignment. What it does say is
that both venues are now measured by one test, with both fee schedules, at
instants rather than dates.

## What cannot be said yet

Nothing here is a statement about whether either market *forecasts* well. That
needs outcomes, and outcomes need to be paired with the prices that preceded
them. Over 16 days, 4,851 Kalshi markets resolved and 145 of them had ever been
seen with a live quote. Those 145 collapse to 109 independent events — every
rung of one ladder resolves from one reading of one price — and 100 of those are
fifteen-minute markets quoted a median of fourteen minutes before settlement,
which measures how fast a price converges to an outcome already in view.

**Nine informative independent events.** That is the honest size of the
validation sample, and no scoring should be run on it.

## What would change the answer

- **December.** Deribit lists weeklies about a month out, so expiries will
  appear on both sides of 1 January and the band will close on its own. Nothing
  has to be built; the test gets stronger by waiting.
- **A middle tenor.** A weekly terminal ladder against a Deribit weekly could
  have both a small expiry gap and strikes fine enough to resolve it. Whether
  one exists is currently unknown.
- **Accumulation.** A collector defect was hiding the daily ladders entirely
  until it was fixed on 2026-09-15; from that date the validation sample grows
  by roughly two independent events a day.

Switching to a larger venue would not help. Deribit is about 85% of
crypto-native BTC options volume and over 90% of ETH, and OKX and Bybit settle
at 08:00 UTC as well. The clock is a property of crypto options, not of Deribit.

## Errors found in our own work

Recorded because a project that reports no mistakes is not reporting carefully:

- the discount convention above, which had been wrong since the first digital
- an expiry selection that compared dates rather than instants, harmless on
  year-end ladders and wrong on intraday ones
- a rewrite that took "the two nearest expiries" by absolute distance and
  thereby picked two chains on the *same* side of the close, which silently
  turned a two-sided band into a one-sided bound and made a finding disappear
  with no error message
- a CI step that piped the test suite through `tee`, so a failing suite exited
  green and the only thing standing between a red run and a tick was a
  test-count floor
- and the largest of them: a whole second venue left on the old method for two
  weeks while its neighbour was repaired line by line, with a fee of zero where
  the counterparty's own published schedule sat inside data we had been
  archiving the entire time

The third was caught not by a test but because a summary file printed one
number where two belonged; the file had been added an hour earlier for an
unrelated reason. The last was caught only because someone asked an outside
question — whether the project was ready to be shown to Polymarket — and
answering it honestly required looking at what the Polymarket code actually
did. Internal review had not asked.

## How to check any of this

Every measurement runs from the raw archive. `python scripts/measure_band.py` and
its siblings regenerate the figures above from the stored exchange payloads;
the results are written to `findings/` rather than left in a log. Every claim in
this note cites a numbered decision record in `docs/DECISIONS.md` that gives the
measurement, the code that produced it, and what it does not license.

The relevant records for this note are D-073 through D-085.

---

*Divergence is a research terminal, not a betting application, a trading bot or
a signal service. A difference between two prices is not a trading opportunity,
and this note is an example of why.*
