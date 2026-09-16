# METHODOLOGY.md

Updated 2026-09-16. The previous version of this document was wrong in three
places; the corrections and their reasons are below and in `DECISIONS.md`. The
external review of 2026-09-16 added three clarifications without changing any
arithmetic — section 0b.

**Read this first.** Between 2026-09-14 and 2026-09-15 the measurement was taken
apart and rebuilt to be defensible (D-073 to D-080). Three things changed that
this document previously stated the other way round:

1. The option side is a **discounted state price**, not a probability (D-073).
2. The comparison is a **trade at quoted prices**, not a statistical test. The
   `1.96 * SE` band is gone (D-076), both venues' fees are charged (D-077), and
   an edge is reported with the size resting behind it (D-078).
3. Two of the three persistent divergences **cannot be separated from the
   seven-day expiry gap** (D-079).

| Layer | Status | Evidence |
|---|---|---|
| 1 — ladder to density | **verified** | ETH mean absolute error 0.0014 |
| 2 — futures consistency | **verified** | put-call parity, 21 strikes, 0.146% dispersion (D-036) |
| 3 — touch premium lower bound | **verified** | hard lower bound held 19/19 (D-018, D-030) |
| 4 — Breeden–Litzenberger | data ready | the strike grid is sparse in the wings |

---

## 0. The bridge — putting two instruments in the same unit

**Step 1 — put the prediction side into probability.**
A binary contract's price is already in probability units. But **the mid is not
used**: on a thin ladder the mid is an imaginary number nobody trades at. Bid and
ask are compared separately (D-024). On a one-sided book the answer is `UNKNOWN`,
not zero.

**Step 2 — put the option side into the same unit. It is not a probability.**
A call price is not a probability and neither is the difference quotient taken
from it. What comes out is a **discounted state price**:

    D · Q(S_T > K) ≈ −∂C/∂K ≈ [C(K₁) − C(K₂)] / (K₂ − K₁)

where `Q` is the risk-neutral measure and `D` the discount factor to expiry.
This is not a model, it is a numerical approximation of a derivative. **It is the
primary method** (D-027).

Both branches return the same quantity. Below the forward the PUT side is used
(D-025), and it reaches `D · Q(S>K)` as `D − D · Q(S<K)`. Until D-073 it returned
`1 − D · Q(S<K)`, which is a different number; with `D = 1` the two expressions
coincide, which is why the error survived review. The exhaustiveness check could
not see it either, because `D · 1 + (1 − D) = 1` for any `D`.

`D` is read off the put-call residual and carried explicitly (D-073, D-074).
Measured across 28 chains it is flat in strike to about 0.5% of its own size,
with an implied rate term structure of 3.2–5.5%.

**Both sides of the comparison are present values.** A Kalshi YES price is also
what one pays today for a dollar at settlement, so the two are on the same
footing without dividing anything. Dividing by `D` gives `Q`, which may be
reported as an options-implied risk-neutral probability, and which is still not
a real-world probability: the distance between `Q` and `P` is the volatility risk
premium and nothing here measures it.

**Step 3 — match the contract type.** Not skippable; see section 2.

**Step 4 — ask whether a trade exists, not whether a number differs.** (D-076)
Two trades, each leg priced at a quote standing right now:

    sell the prediction at its BID, buy the bucket at its ASK side, pay both
    venues' fees.  Anything left?
    buy the prediction at its ASK, sell the bucket at its BID side.  Anything left?

    edge = max(the two),  and a rung counts when edge > 0

The bucket's two prices come from the option quotes directly: `opt_high` pairs
the long leg's ask with the short leg's bid, `opt_low` the other way. The width
between them is the bid-ask cost of two option legs, **not a confidence
interval**. No mid appears anywhere in the verdict.

What this replaced: `1.96 * SE + fees + spread/2`. That term described how
uncertain our ESTIMATE of the option mid was — a question about our arithmetic
that nobody can trade on. Its size was almost identical (`2s/w` against
`1.96s/w` for comparable spreads), so the change was in meaning, not in
strictness.

**Step 5 — charge both venues, then ask what it is worth.** (D-077, D-078)
Kalshi's taker fee is `round up(0.07 · C · P · (1−P))`, quoted from their
schedule in `scripts/fees.py`; there is no settlement fee. The rounding is per
ORDER, so an edge has no meaning until a size is named. Then the resting size at
the quote being hit turns the edge into dollars. Live on 2026-09-15 the three
surviving rungs were worth **$4.69 between them**.

---

## 0b. Three clarifications from the external review (2026-09-16)

None of these changes a computed number. Each changes what a number is allowed to
be called.

**The two-expiry test is a stress test, not a bound** (D-094). Step 4 is run against
both Deribit expiries that bracket the prediction market's close, and a rung must
clear the option value at each. Earlier wording — here, in D-079 and in
`measure_sensitivity.py` — said the settlement-date value "lies between" the two
chains. That is a monotonicity argument about a tail probability, and `D·Q(S_T > K)`
is not monotone in maturity in general: the discount factor falls with `T`, the two
chains carry different `D`, forwards and liquidity, and the term structure can move a
tail either way. A rung that fails the test has not survived; a rung that passes has
passed a **conservative maturity stress test**, not cleared a bound. Alongside the
early and late values, a linear-in-time interpolant to the settlement instant,

    dsp(T*) = dsp(T1) + (T* − T1) / (T2 − T1) · [dsp(T2) − dsp(T1)]

is reported as a **sensitivity** with a stated formula — never as the settlement-date
value, and never as a model of the term structure. No volatility surface is built to
close the gap; nearer expiries close it (D-101).

**Quoted-executable is not size-executable** (D-095). Step 4 establishes a
**quoted-executable discrepancy**: at top-of-book quotes, after both venues' fees, one
of the two trades leaves something. It does not establish a **size-executable
opportunity**, which would need depth beyond the best level, the option multiplier and
minimum size, sizing the spread against the contract, legging across venues, partial
fills, quote staleness inside the sync window, fees at the executed price, and
slippage. No measurement in the repository meets the second standard, and no surface
describes the first as if it did.

**The claim set is frozen, and the count is a family-level statement** (D-096). The
44 year-end rungs measured in `findings/latest.json` are the declared family. No
p-value or false-discovery correction is applied to the quoted-edge count — the
framework produces no independent p-values per rung, and dressing it in one would
manufacture independence it lacks. Results are stated as "n of 44 in the declared
family"; rungs found later start a new family; data after 2026-09-16 is a forward
holdout. For every hypothesis from here on: discovery → hypothesis freeze → forward,
untouched test. The one rung that survives the stress test carries a pre-committed
kill test whose verdict rules were written before its number (D-092).

---

## 0a. Two traps — both of them measured in this project

### Trap 1: the wrong instrument (D-025, D-035)
Deriving a downside probability from a deep ITM call means reading a small
difference off the difference of two large numbers. Put-call parity says the two
routes **must give the same number**; any divergence is measurement error,
directly:

| time value / price | 86% | 35% | 12% | 4.8% | 1.2% | 0.4% |
|---|---|---|---|---|---|---|
| call route / put route | 1.01 | 1.01 | 1.02 | 1.04 | 1.28 | **2.09** |

**Rule:** upside from OTM calls, downside from OTM puts. If time value is under
5% of the price, that rung is `NOT MEASURABLE`. With no put chain, no downside
number is produced at all.

### Trap 2: ignoring skew (D-027, D-029)
`C` depends on `K` two ways — directly, and through the IV curve:

    dC/dK = (∂C/∂K)|σ + vega · (∂σ/∂K)

A naive `N(d2)` drops the second term. Measured cost on the BTC monthly chain:
**54.8%** mean deviation against a model-free referee, **334%** in the wings.
With the skew term added the deviation falls to **1.9%**. On the daily chain there
is no effect — 0.4 days to expiry, vega ≈ 0.

**Consequence:** the skew correction is mandatory at medium and long tenors. That
is the second independent reason for prioritising the medium tenor.

---

## 1. Layer 1 — ladder to discrete density

    P(S_T > K_j) = Σ_{i ≥ j} P(bucket_i)

| Asset | Snapshot spread | Mean absolute difference | Max |
|---|---|---|---|
| **ETH** | ~2 minutes | **0.0014** | 0.0040 |
| **BTC** | ~3.5 hours | 0.0123 | 0.0899 |

Two independent ladders read simultaneously confirm each other to within 0.14
points — evidence for both the conversion and the classification. A 3.5 hour drift
multiplies the error by nine; that is **measurement error**, not a market
inconsistency.

**Exhaustiveness condition:** the cumulative is only valid if the bucket set
covers the whole outcome space. With no lower-tail bucket, that region cannot be
read. The script warns automatically.

**The target is D, not 1** (D-073). Buying every bucket buys a dollar at expiry
with certainty, and a certain dollar is worth `D` today. `measure_exhaustive.py`
reports `total / D`, so 1.0000 is the target. Before the repair the sum landed on
1 whatever `D` was, which made the most productive check in this project blind to
the convention error sitting beside it.

**And the ladders really do tile** (D-075). The rule texts were parsed and the
parsed intervals chain without gap or overlap, one tick apart. Adjacent buckets
end at .99 and begin at .00, and all 1,892 numeric `expiration_value` entries in
the archive carry exactly two decimals, so the cent between them is not a
reachable settlement value. The constraint is therefore a statement about the
contracts and not only about our arithmetic.

---

## 2. Contract type matching

| Type | The question it asks | Option counterpart |
|---|---|---|
| `terminal` | `P(S_T > K)` | digital approximation, no model |
| `range` | `P(K₁ < S_T ≤ K₂)` | difference of two digitals, no model |
| `touch` | `P(max S_t ≥ K)` | no direct counterpart — a bound relation exists |

**The error in the previous version:** it said "touch will not be compared against
options". That was wrong. The terminal side can come from options, and this
relation is true **by definition**:

    P(touching K before expiry) ≥ P(closing beyond K at expiry)

This hard lower bound held on 19 of 19 rungs — independent evidence that the
classification is right.

**The rule text agrees with the numeric fields (D-075).** 2,070 rung-observations
were parsed out of `rules_primary` and compared against `strike_type`,
`floor_strike` and `cap_strike`: 100% agree, 0 mismatch, 0 unrecognised. The
parser is rigid on purpose — a changed sentence produces UNKNOWN rather than a
guess.

**But the contracts still are not the same event.** Kalshi settles on CF
Benchmarks' BRTI (ETHUSD_RTI for ETH), a sixty-second average, at 00:00 EST on
1 January 2027. Three differences from the option side, with sizes:

| | size |
|---|---|
| settlement instant | **6 days 21 hours** — the material one |
| averaging window | 60 seconds against ~100 days — negligible |
| reference rate | BRTI against the Deribit index — **UNKNOWN** |

**The expiry gap is not a caveat, it is a band (D-079).** Both bracketing Deribit
expiries are now computed, 25DEC26 and 26MAR27. Of 135 rung-observations, 70 sit
above both ends and 65 inside the band. On the latest snapshot only ETH above
$5,000 clears both; BTC above $150,000 and ETH below $1,000 cannot be separated
from the seven-day gap and should not be reported as divergences.

The band is asymmetric — 7 days early against 84 days late — so "inside the
band" means *cannot be separated*, not *explained*. Saying more needs a model of
how a tail probability grows with maturity, and that is what D-025 refused.

**The strike grid costs about 12%.** Recomputing each digital on wider brackets
moves it by a median of 12.6% (p90 18.8%, worst 23.9%). No sign flips, no order
of magnitude changes, but an eighth of every tail digital is a statement about
how far apart Deribit puts its strikes.

**The upper bound "2" is NOT a constant (D-031).** That number comes from
driftless arithmetic Brownian motion. Price is lognormal; even when the forward is
a martingale, the log-price drifts at −σ²/2. The full formula gives every rung its
own upper bound (measured range 1.94–2.07). Using the constant produced a bound
that was too loose on the upside and too tight on the downside.

---

## 3. What the gap is measured against

**NOT BUILT. Superseded in practice.** The scheme below was written on
2026-08-30 and no code has ever implemented it: there is no reference median, no
historical standard deviation, and nothing on screen has ever said "1.2 sigma
above usual". It is kept because the reasoning is still right — a gap against
zero is meaningless — and because the replacement solves the same problem a
different way.

**What is actually done now** (D-076 to D-078): the gap is not compared to its
own history at all. It is compared to what it costs to take it. A rung counts
when a trade priced at standing quotes, after both venues' fees, leaves
something — and the answer is reported in dollars at the resting size. That test
needs no accumulated reference and produces no indicator, which is why it could
be built immediately and this could not.

The historical-reference idea remains worth having for a different question:
whether today's gap is unusual FOR THIS PAIR. Recorded as future work rather
than pretended to be current.

### The original scheme, unbuilt


Even with perfect data the options-implied probability does not equal the realised
frequency: there is a **variance risk premium**. Rows reading "the prediction
market is cheap against options" are mostly structural, not an opportunity.

    gap_t     = P_prediction − P_derivative
    reference = the historical median of the gap for the same asset and a
                comparable tenor
    position  = (gap_t − reference) / the historical standard deviation of the gap

The screen does not say "gap 8%", it says "gap 8%, typical 6%, 1.2 sigma above
usual". Until the reference has accumulated, **no indicator is produced**.

---

## 4. Two views

**Hedge view** — touch ladder plus futures or spot. Needs no options. It reads the
contract not as a probability estimate but as the cost of a conditional order.
This works today.

**Pricing view** — terminal or range ladder plus the option chain. Layers 1, 2 and
4 live here. It is the only comparison that contains no model. BTC and ETH first.

---

## 5. Fields required on screen

`contract_type`, `underlying_reference`, `settlement_source`, `expiry`,
`snapshot_time` (separately for each side), `bid-ask spread`, `volume`.

Added 2026-09-15, each because its absence had already produced a wrong number:

- `discount_factor` and whether it was estimated or fell back to 1 (D-073)
- the executable envelope `opt_low`–`opt_high`, and the fees of BOTH venues
  charged separately (D-076, D-077)
- the **resting size** at the quote being hit, and the edge in dollars. An edge
  with nothing behind it is a price observation, not an opportunity (D-078)
- the minimum order size at which Kalshi's per-order fee rounding stops eating
  the edge (D-077)
- both bracketing expiries, not one (D-079)
- `price_ranges`, so quotes are checked against the grid the market publishes
  rather than an assumed cent (D-078)

A gap shown while any one of these is missing cannot be interpreted. The spread
especially: on thin ladders it can be larger than the gap being measured.

The collector writes `sync_window_seconds` on every run — the drift between the
two price sides. Measured range is 0.75 to 1.97 seconds; the eight-minute drift in
D-015 moved a result by 33%.

---

## 6. Terminology

Not used: "true probability", "correct probability", "AI probability",
"arbitrage opportunity", "insider", "smart money".

Used: prediction-market-implied probability, options-implied risk-neutral
probability, cross-market probability gap, terminal probability, touch probability,
large trade, concentrated position, historical settlement performance.

Added (D-073): **discounted state price** for `D · Q(S>K)`, which is what the
option side actually produces. "Options-implied risk-neutral probability" stays
permitted and means `Q`, i.e. the state price divided by `D` — it is the honest
name for the readable number, and the two must not be used interchangeably.

Added (D-076): **edge** is permitted, narrowly, and only for the result of the
two-trade test at quoted prices after fees. It is a necessary condition for a
trade and never a claim that one exists. "Arbitrage opportunity" remains banned.

Added (D-095): **quoted-executable discrepancy** — what the two-trade test
establishes at top-of-book quotes after fees; **size-executable opportunity** — the
standard that depth, multiplier, legging, fills, staleness and slippage would have to
meet, and that nothing here meets. The two are never interchanged.

Added (D-094): **maturity stress test** for the two-expiry requirement; "bound" is
not used for it. Added (D-096): **declared family** and **forward holdout**.

---

## 7. Still open

- **Validation has not started.** 4,657 markets resolved inside the 14-day window
  and only 88 were ever seen with a live quote, at a median of 14 minutes before
  settlement (D-080). The cause was a paging cap in the collector, fixed
  2026-09-15; daily ladders now arrive live for the first time. Scoring should
  wait for the corrected collector to accumulate rather than run on this.
- The one rung that survives the expiry band, ETH above $5,000, survives by about
  0.4 cents — a margin comparable to the strike-grid uncertainty on the chain that
  decides it (D-079). A pre-committed local-grid kill test is specified in D-092 and
  its verdict is pending.
- The discount factor has one estimator. Referees — the parity slope as an
  estimator-consistency check, the futures basis from `underlying_price`, an external
  rate as a dated constant — are specified in D-093 and pending.
- BRTI against the Deribit index: measured, 63 paired readings, median under a
  basis point (`findings/settlement_basis.json`, D-075). The averaging window and the instant
  remain unmeasured.
- ~~The internal identifiers are still `p` and `opt`~~ — renamed to `dsp` across the
  code in D-086; `opt` kept deliberately.
- ~~The measurement pipeline reads only the 14-day public window.~~ `measure.yml`
  reads the private mirror on a manual run and records which archive it read (D-089).
- Layer 4 (Breeden–Litzenberger) is not built; the data is ready.
- Reference accumulation started 2026-08-30 but is not yet long enough to produce
  a statistic, and section 3 was never implemented.
- `data-api` `offset` support is unverified — no gap has occurred, so it has never
  been triggered (D-042).
- The 5 August measurement is stale: BTC has moved 19.9% since, and that day's put
  chain cannot be recovered. The measurement has to be redone from scratch on
  simultaneous data (D-037).
