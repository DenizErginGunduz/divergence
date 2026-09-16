# Research Note 1 — What survives

**Divergence · 2026-09-16 · BTC and ETH, Kalshi and Polymarket against Deribit**

Two markets price the same future event. How much of the difference between
them survives contact with execution, maturity, settlement and the strike grid?

Over 68 snapshots and 17 days, three of 44 Kalshi year-end rungs showed a
difference at quoted prices, after both venues' published fees, in essentially
every observation. Two of the three cannot be told apart from the fact that the
contracts settle a week apart from the options. The third — ETH above $5,000 —
cleared the mark-price maturity test by about 0.4 cents and was then put through
a kill test whose verdict rules were written down before it ran. **It is not a
surviving discrepancy.** Priced at the quotes one would actually hit on the chain
that expires after the contract settles, with both venues' fees, its margin is
negative in every one of 62 snapshots.

That is the result: **0 of 44 rungs in the declared family survive the full set
of controls.** What remains is a fact about market structure — price differences
that persist at the top of the book and that the executable side of the same
book removes — not a trade. Every figure in this note is regenerated from an
archive of raw exchange payloads by a script in the repository; none is typed in
by hand.

---

## The question

A prediction market quotes a probability directly: "Bitcoin above $150,000 on
1 January 2027" trades at a few cents. An option chain implies one indirectly,
through the price difference between neighbouring strikes. Same event, two
answers, and comparing them needs no model of how prices move.

The interesting case is where they disagree. The uninteresting and much more
common case is where they appear to disagree because something in the
comparison is wrong. This note is about telling the two apart, control by
control, and about what is left at the end.

## What else exists

This comparison is not new, and the register that says so is part of the work
(`docs/COMPETITORS.md`, D-098 and D-110). Four entries in it bear directly on what
follows.

**The construction is published.** Block Scholes, in a report dated 2 July 2026,
states that binary option prices — and therefore the prices of prediction markets
on the same underlying — are uniquely determined by the prices of vanilla calls,
and walks the reader through building the binary out of a call spread. That is
the starting point of this note, in print, by an institutional analytics firm,
before this note existed. Nothing here claims the derivation.

**The empirical question has a larger answer already.** Fabi, Schönleber, Ruffo
and Marfè compare Polymarket BTC and ETH prices against option-implied
risk-neutral distributions across nearly 5,000 contracts, and report that prices
broadly track the benchmark while deviations concentrate in tail and barrier
contracts. Their sample is two orders of magnitude larger than the 68 snapshots
here. That description is second-hand — the paper was behind a bot check on
2026-09-16 and has not been read in full — which is recorded rather than glossed,
and reading it is a prerequisite for the note that would follow this one.

**A paid product already ships the comparison.** PolyGap prices every Polymarket
crypto market against Deribit’s options curve, refreshes every two minutes, and
sells the fair value, the gap and an execution signal for thirty dollars a month.
Its method is stated on its own page: implied volatility by strike and expiry,
N(d2) for a threshold and a barrier model for a touch. The difference from this
note is not the question and not the data. It is that this note prices the option
leg at the side one would have to hit, charges both venues’ published fees, tests
both bracketing expiries, and refuses a rung where either book is one-sided.

**And the executable framing has a stricter version.** Gebele, Mutzel and Matthes
separate payoff-space no-arbitrage from protocol-executable no-arbitrage inside
Polymarket’s own linked markets, and reconstruct depth-aware executable portfolio
values. They measure at depth; this note measures at the top of the book, which
is the weaker of the two standards and is labelled as such throughout (D-095).

A fourth entry, De Stefano’s thesis, uses the same three venues as this project
over two years rather than seventeen days, with a DVOL-based benchmark instead of
a strike-by-strike chain.

What is left, stated narrowly: the controls. A model-free digital from the spread
rather than a fitted surface; the executable side rather than the mark; both fee
schedules as published; the maturity band as a stress test; the strike grid as a
measured sensitivity; the settlement text quoted rather than assumed; and a
refusal where the data does not support an answer. Whether that set of controls
changes the conclusion is what this note asks, and the answer is that it removes
everything the quoted prices appeared to show.

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
to 1 — could not, because `D·1 + (1−D) = 1` for any `D` at all (D-073). The ladder
now has to sum to `D`, and it does: the year-end ladders' mean density is 0.9858
against a mean discount factor of 0.9881.

`D` itself is read off the chain, and it now has referees (D-093, D-104). Across
1,426 chain-snapshots the current estimator and Deribit's own forward for each
expiry agree on the implied financing rate to within a basis point on every
chain a month or more out; a least-squares re-estimate of the same identity
agrees by construction, and is labelled that way rather than counted as
evidence. An external overnight dollar rate (SOFR, 3.62% on 2026-09-14) sits
about a percentage point below the BTC chains and within a fraction of one of
the ETH chains. That gap is the venue's coin-collateralised financing basis, not
an estimator error, and the external rate is not used — a `D` from outside the
chain would put the call side and the put side of the same strike on different
footings.

**The contracts do not settle on the same thing.** Kalshi settles on a
sixty-second average of CF Benchmarks' BRTI at a stated instant. Deribit settles
on its own index at 08:00 UTC. Three differences follow, and all three are
measured:

| difference | size |
|---|---|
| reference rate, BRTI against the Deribit index | median about a basis point (BTC −0.9, ETH +1.2); spread 1.5 bp between readings taken within 60 s, about 5 bp across all 75 pairs |
| averaging window, 60 seconds | negligible against a horizon of hours or months |
| settlement instant | **165 hours** early on one side of the year-end ladders, **2,019 hours** late on the other |

The first two can be set aside. The third cannot, and it does most of the work
in what follows.

**A price difference is not an opportunity.** Both venues charge. Kalshi's
published taker fee is `round up(0.07 × C × P × (1−P))` per order, rounded to the
cent; Deribit charges 0.03% of the underlying capped at 12.5% of the premium,
on both legs. And a difference with nothing resting behind it is a price
observation, not a trade. The vocabulary for that distinction is fixed in D-095:
a **quoted-executable discrepancy** is one that clears fees at the top of the
book; a **size-executable opportunity** is one that also survives the depth and
the slippage of a fill. Nothing in this note is the second kind.

## The test

The comparison used to be `|mid − mid| > 1.96 × SE + fees`. That standard-error term
described how uncertain *our estimate* of the option mid was — a question about
our own arithmetic that nobody can trade on.

It is now two trades, each leg priced at a quote that is standing:

    sell the prediction at its BID, buy the bucket at its ASK side, pay both
    venues' fees.  Anything left?
    ... or the mirror of that.

No mid appears anywhere in the verdict. The family of rungs the test is run on
is frozen — the 44 Kalshi year-end rungs of BTC and ETH — and a rung is counted
as showing a difference only if it does so in at least 90% of its observations
(D-096). No multiple-comparison correction is applied, because the claim is not
"at least one of 44 is significant" but "these particular rungs persist", and
persistence across snapshots is the test.

## What survives each control

**At quoted prices: three rungs.** 44 distinct year-end rungs were measured 62
times each. Three showed a positive edge in essentially every observation — BTC
above $150,000 in 62 of 62, ETH above $5,000 in 62 of 62, ETH below $1,000 in 61
of 62. One showed it sometimes; forty never did. Over all 2,726 quotable
rung-observations the share with an edge is 6.8%. The three are all tails;
nothing in the body of any distribution came close.

**At size: small numbers, and one large one that is not what it looks like.**
Both size fields are archived, so an edge can be multiplied by the contracts
resting at the quote being hit. The median positive edge is worth $1.21; the
largest single observation is $569.51. The large one is recent: since
2026-09-15 a bid of about 50,000 contracts has rested at 0.025 on ETH above
$5,000, where a day earlier there were ten. Against the chain that expires a
week *before* the contract settles, that depth times the quoted edge reads as
several hundred dollars. It is a quoted-executable discrepancy on the wrong
chain, and the next control removes it.

**Against the clock: one rung, by 0.4 cents, on marks.** Kalshi's year-end
contracts settle 1 January 2027. Deribit's nearest expiries are 25 December 2026
(165 hours early) and 26 March 2027 (2,019 hours late). A tail probability grows
with maturity, so the two chains bracket the settlement date from either side.
This is a stress test, not a bound (D-094): a bid above both chains has survived
the gap, not been shown to sit between them. Two of the three persistent rungs
sit inside the band and cannot be separated from it (D-079). On the newest
snapshot only **ETH above $5,000** clears both chains — by about 0.4 cents, on
mark prices, with no executable side and no option fee on the far chain. A
linear-in-time interpolant between the two chains is reported as a sensitivity
only; with the band this asymmetric it puts 0.076 of its weight on the late
chain and decides nothing.

**Against executable prices on the far chain: nothing.** The kill test was
specified before it ran (D-092): five local estimates of the digital at $5,000
on each chain — the production bracket, two wider ones, and the two one-sided
quotients — each priced at the ask one would pay and the bid one would receive,
with Deribit's fee on the crossed prices and Kalshi's on the bid. The rung had to
beat the *worst* of them in at least 90% of snapshots. It beat it in **0 of 62**.
It does not rest on the worst estimator either: the late chain's own production
bracket, 4,800–5,500, is positive in 3 of 62 snapshots. The rung survives the
early chain in every estimator and every snapshot, and does not survive the late
chain's executable prices in any. The difference between "survives by 0.4
cents" and "negative at the median" is entirely the difference between a mark
and a quote one can hit (D-103).

**Against the strike grid: a stated uncertainty, not a rescue.** The same
digital read from a bracket one strike wider on each side moves by a median of
11.5% of itself on the year-end ladders (p90 18.3%, worst 23.9%). That is the
size of the statement "this number depends on Deribit's strike spacing", and it
is the reason the kill test used five brackets rather than one. On the intraday
ladders the grid is the whole problem: Kalshi steps its thresholds by $100 and
the chain cannot resolve that, so **70.3% of intraday rungs return a digital
identical to another rung of the same ladder.** The two tenors fail in opposite
directions — year-end has strikes fine enough that no two rungs collide and an
expiry gap wide enough to explain most of what it finds; intraday has an
acceptable expiry gap and a chain that cannot resolve the ladder. That is a
structural property of comparing two venues whose contract grids were designed
for different purposes, not a bug with a fix.

## The second venue, and the number that was half method

Polymarket lists the same kind of ladder, and until 2026-09-15 its figures were
computed by the **old** method: the pre-repair discount convention, a 1.96·SE
band around two mids, and — the worst of it — no fee at all on the prediction
leg. The number sat in the same results file as the repaired Kalshi one,
formatted the same way.

Polymarket does charge. Every market in the archive carries its own schedule
and always has:

    feeSchedule: {"exponent": 1, "rate": 0.07, "takerOnly": true, ...}
    fee = C × rate × p × (1 − p)

The same formula and the same coefficient as Kalshi, taker only, and our trades
cross. It averages **0.65 cents a share** — the same order as the edges being
measured. The code had called it a maker fee and set it to zero (D-085).

Under the same test as everything else, over 5,117 quotable rung-observations:

| | old method | same test as Kalshi |
|---|---|---|
| share of quotable rungs with an edge | **24.2%** | **9.9%** |
| rungs where the expiry matched within 12 hours | 26.3% | **7.9%** |
| always / sometimes / never | 9 / 298 / 92 | 3 / 185 / 217 |

More than half of it was method. The three "always" rungs were each seen two to
four times, which is not persistence. And a tighter expiry match now *reduces*
apparent divergence, as it should — less of the gap can be the clock. Under the
old method it did the opposite, and that inversion was visible in the results
file for two weeks without anyone reading it, because neither number looks wrong
on its own.

9.9% against Kalshi's 6.8% is **not** a like-for-like comparison — different
tenor, different ladder shape, different expiry alignment. What it does say is
that both venues are now measured by one test, with both fee schedules, at
instants rather than dates.

## The long-dated touch bound

Polymarket's year-end markets ask whether a level is *touched*, not where the
price closes, and options give terminal probabilities only. The one model-free
statement is that touch is at least terminal; the driftless reflection bound
says at most twice terminal. Over 1,572 rung-observations, 0.3% violate the
first (five observations) and 93.3% exceed the second. The first number is a
pipeline validation: if the digital were wrong, impossible values would appear
in the hundreds. The second is not mispricing; it says the
reflection bound is the wrong tool for long-dated deep out-of-the-money strikes,
and nothing here uses it for more than that.

## What cannot be said yet

Nothing here is a statement about whether either market *forecasts* well. That
needs outcomes paired with the prices that preceded them. In the public 14-day
window 5,041 Kalshi markets resolved and 157 had ever been seen with a live
quote; 112 of those are fifteen-minute markets. They collapse to **121
independent events** — every rung of one ladder resolves from one reading of one
price — quoted a median of 6.9 hours before settlement, a quarter of them within
14 minutes. These are lower bounds from the public window; the private mirror
holds more. No scoring is run on them, and the gate that would allow it (G3)
asks for the evaluation design to be frozen before any holdout is opened.

## What would change the answer

- **December.** Deribit lists weeklies about a month out, so expiries will
  appear on both sides of 1 January and the band will close from weeks to days.
  Nothing has to be built; the same kill test runs again by waiting.
- **A complete intraday ladder.** The archive's open-market pass returns one
  page of 200 markets, which spans two intraday events and cuts the first one's
  middle out; such ladders are now named `incomplete` and set aside rather than
  summed (D-105). Fetching the whole event is a collector change and is logged,
  not made (B-022).
- **A futures stream.** Whether an expiry's `underlying_price` is a listed
  future or a synthetic is unknown per expiry; a futures stream would settle it
  and give the basis that the exposure work needs (B-018).

Switching venues would not help. Deribit carries most crypto-native BTC and ETH
options volume (the share is not measured here), and the other venues settle at
08:00 UTC as well. The clock is a property of crypto options, not of Deribit.

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
- a whole second venue left on the old method for two weeks while its
  neighbour was repaired line by line, with a fee of zero where the
  counterparty's own published schedule sat inside data we had been archiving
  the entire time
- the exhaustiveness check summing things that are not partitions — cumulative
  ladders whose rungs overlap, two events of one series, and ladders with a hole
  cut by a fetch cap — which put a departure of +147.9% on the screen for a day
  (D-105)
- a review that called the parity-slope referee independent of the current
  estimator; it is the same identity re-estimated, and is now labelled so (D-093)
- and the sentence "survives by about 0.4 cents", which was true of mark prices
  and was read, for a while, as if it were true of a trade (D-103)

Most were caught by constraints rather than by numbers, and the last three by
writing the verdict rules down before the number existed.

## How to check any of this

Every measurement runs from the raw archive. `python scripts/write_findings.py`
regenerates the figures above from the stored exchange payloads into
`findings/latest.json`; `scripts/kill_test_eth5k.py`, `scripts/measure_sensitivity.py`
and `scripts/discount_referee.py` write their own records beside it. Every claim
in this note cites a numbered decision record in `docs/DECISIONS.md` that gives
the measurement, the code that produced it, and what it does not license. The
relevant records are D-073 through D-085 for the repairs and D-092 through D-105
for the controls.

---

*Divergence is a research terminal, not a betting application, a trading bot or
a signal service. A difference between two prices is not a trading opportunity,
and this note is a worked example of why.*
