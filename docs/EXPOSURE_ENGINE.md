# EXPOSURE_ENGINE.md — basis-aware exposure design

**Status:** methodology, version 0.1 (2026-09-16; §5 added by D-108). No code
exists for it yet; this document is the specification that code would be written
against.
**Decided in:** D-091 (Layer B), D-100 (WTI as a research case), D-101 (what is not
built yet) · **Research note:** Note 4 in `RESEARCH_ROADMAP.md` · **Product:** V1 and
V2 in `PRODUCT_ROADMAP.md`

---

## 0. The question, and the wrong version of it

**The question.** A person has a market view — directional or event-shaped — over a
horizon, with a given amount of capital and a given tolerance for loss and
liquidation. How should that view be expressed across the instruments available, when
the instruments differ in the reference price they start from, what they cost to
carry, what shape of payoff they deliver, how much capital they lock, how they settle,
and what it costs to get in and out?

**The wrong version.** "Which instrument is cheapest?" A perpetual, a dated future, a
vanilla option, an option spread and a prediction-market binary have different payoff
functions. A cost comparison between them is a comparison between different things
unless the payoff is held fixed or the difference in payoff is priced. So the object of
study is not a cost number but a **frontier**: cost × capital × payoff × basis × risk ×
execution. The engine's job is to compute that frontier honestly and let the user's
stated constraints select from it. Nothing it produces is advice.

This question does not require two venues to price the same event — the constraint
that consumed most of Layer A's sprint (`STRATEGY.md`). It requires each venue to be
priced on its own terms and then put on a common footing.

---

## 1. The motivating case — an illustration, not a measurement

Recorded per D-100. **The figures below were supplied by the project owner as an
illustration. This repository collects no oil venue and has measured none of them.**

A trader wants to be short oil. The economic benchmark they have a view on — a
CME-like WTI reference — trades near 105. A crypto-native venue lists a synthetic oil
perpetual near 99. Opening the short on the synthetic starts the position roughly 5–6%
away from the price the view is about: an adverse entry basis before anything has
happened. If funding on the short side is also strongly negative, the basis
disadvantage plus a recurring funding cost can consume a large part of the return the
view would have earned on the benchmark.

A prediction-market contract — "oil reaches 120?", "oil reaches 130?" — with a NO
position has no liquidation, no recurring funding, a binary capped payoff, locked
collateral, and a settlement definition that may or may not match the benchmark. It
is a different economic decision, not a cheaper version of the same one.

The case is kept because it exhibits every layer below at once: reference mismatch,
basis, carry, payoff shape, capital lock, settlement definition. It is not a claim
about oil markets.

---

## 2. Architecture — eight layers, in order

The order matters: a cost comparison that skips the basis layer compares positions on
different underlyings and calls them the same.

### A. User objective
Inputs, all explicit: view (bullish / bearish / event thesis), target level or event,
horizon, capital, maximum loss, liquidation tolerance (none / some / any), optional
target payoff. The engine never infers a view.

### B. Reference normalisation
Identify what the user actually has a view on: WTI / CL, Brent, BTC spot reference,
a CME index, SPX, NDX. Every venue's quoted underlying is mapped to a reference, or
marked `UNKNOWN`. No venue's underlying is treated as economically identical to
another's without that mapping being written down. This is the same discipline as
`scripts/audit_semantics.py` applied one level up: the reference is read, not assumed.

### C. Basis layer
For each instrument / venue: venue price, reference price, percentage basis, the
settlement reference the instrument actually pays on, and current or historical basis
where the archive has it. Basis is computed **before** any cost is compared. Where the
reference is `UNKNOWN`, the basis is `UNKNOWN` and the instrument is shown with that
gap, not dropped and not filled.

### D. Carry layer
Perpetual funding (signed, per period, over the horizon); dated-futures basis and
roll; option theta / premium; prediction-market collateral opportunity cost; borrow
where relevant. Each is a measured or quoted number with its source, or `UNKNOWN`.

### E. Execution layer
Bid / ask on every leg, fees from the published schedules (`scripts/fees.py` for the
prediction venues; Deribit's schedule as in `measure_band.py`), depth at the best
level, slippage beyond it (`UNKNOWN` until measured), minimum size, legging across
venues. The executable envelope of D-076 is the template: price every leg at the side
one would hit.

### F. Payoff layer
Classify and, where possible, compute: linear (future, perpetual), convex (option),
capped (spread), binary (prediction contract), path-dependent (touch contracts,
funding accrual), liquidation-dependent (leveraged perpetual). The payoff class is a
field on every instrument; comparisons across classes say so.

### G. Scenario layer
Outcomes under named scenarios, at minimum: `S_T` below target, at target, moderately
above, extreme tail; and where relevant: basis converges, basis widens, funding
persists, funding reverses. Scenarios are named and their assumptions are printed
with the result. No scenario is called "expected".

### H. Constraint filter
Apply the user's constraints from A: maximum loss, capital ceiling, no liquidation,
capped payoff acceptable or not, minimum target payoff. Instruments that fail a
constraint are shown as failing it, not removed silently.

### I. Output
Internally the full frontier is preserved — every instrument, every layer, every
`UNKNOWN`. The first interface shows **best fit for your stated constraints**, then
**why**, then **alternatives**, then the **full comparison**. "Best fit" is best under
explicit user-specified constraints. It does not mean financial advice, highest
expected return, true value, or objectively best trade, and the screen says so.

---

## 3. Quantities, stated once

For an instrument `i` held over horizon `[0, T]` against reference `R`:

- **entry basis** `b_i = (P_i(0) − R(0)) / R(0)` — signed; adverse when it moves the
  entry away from the view.
- **carry** `c_i` = the sum over the horizon of the instrument's periodic costs
  (funding, roll, theta), each as measured; `UNKNOWN` components make `c_i`
  `UNKNOWN`, not zero.
- **execution** `e_i` = fees plus half-spreads on every leg at the sizes stated, plus
  slippage where measured.
- **capital** `k_i` = margin or collateral locked, including maintenance where the
  venue publishes it.
- **payoff** `Π_i(S_T; scenario)` — the class from F and the value under each
  scenario from G; for a leveraged perpetual, the liquidation boundary is a scenario
  outcome, not a footnote.
- **settlement** — what `S_T` means for this instrument: the reference, the averaging
  window, the instant; quoted verbatim (rule 3).

The frontier is the set of `(e_i + c_i, k_i, Π_i, b_i, risk_i)` tuples. There is no
scalar ranking of it; the constraint filter H selects, the user's constraints do the
ranking.

---

## 4. What the archive can and cannot feed today

| layer | BTC / ETH today | gap |
|---|---|---|
| B reference | Deribit index; Kalshi BRTI; Polymarket resolution source (verbatim) | mapping table not yet written |
| C basis | index vs `underlying_price` per Deribit expiry (D-093, referee 3) | listed vs synthetic UNKNOWN; no perpetual stream |
| D carry | option premium from the chain | perpetual funding, dated-futures roll: not collected (B-019) |
| E execution | bid / ask, both fee schedules, best-level depth | slippage beyond best level |
| F payoff | option, spread, binary | perpetual and its liquidation boundary |
| G scenarios | computable from the chain for option / binary | perpetual funding paths need the funding stream |

The first worked example (Note 4's gate) is therefore an option-spread versus binary
comparison for one BTC or ETH view, with the perpetual column present and marked
`UNKNOWN` until B-019 exists. That is deliberate: the engine is specified in full and
computed only where the archive supports it.

---

## 5. The first worked example — specified, not computed

Note 4's kill / continue gate (`RESEARCH_ROADMAP.md`) and G6 in `DECISION_GATES.md`
both ask for one worked example computed end-to-end from archived data before any
engine is built. This section fixes what that example is, so that when it is computed
the choices were made before the numbers.

**The view.** "BTC finishes above K on 1 January 2027", for one K taken from the
Kalshi year-end ladder so that a binary with that exact threshold exists. The
horizon is the contract's close. Capital, maximum loss and liquidation tolerance
are inputs and are varied in the scenario table rather than fixed here.

**The instruments compared.**

| instrument | venue | payoff class | what the archive supplies today | `UNKNOWN` |
|---|---|---|---|---|
| binary YES at K | Kalshi year-end | binary, pays 1 | bid, ask, sizes, taker fee (`fees.py`), settlement rule text | maker economics; collateral opportunity cost (a rate) |
| call spread K / K+w | Deribit 25DEC26 and 26MAR27 | capped, pays up to `w` | marks, bids, asks, per-leg fee, `D`, the digital and its executable envelope | slippage beyond best level; margin for the short leg |
| touch YES at K | Polymarket year-end | binary on a path event | bid, ask, taker fee, resolution source text | comparability to the terminal view: **different payoff class**, shown as such and not compared as equal |
| long perpetual, size chosen to match the spread's delta | (none collected) | linear, liquidation-dependent | — | everything: price, funding, liquidation rule (B-019) |

**The layers, applied.**
- **B.** Reference for all four is a BTC dollar price; the three collected venues
  settle on three sources (BRTI, the Deribit index, Polymarket's stated source) and
  the mapping row for each is its quoted rule text (rule 3). The perpetual's row
  is `UNKNOWN`.
- **C.** Entry basis per instrument: the binary and the touch have none in price
  terms (they are priced in probability units) but carry a **settlement basis**,
  which is the BRTI-vs-index difference already measured (`findings/settlement_basis.json`);
  the spread's basis is the chain's own forward against the index (referee 3 of
  D-093); the perpetual's is `UNKNOWN`.
- **D.** Carry: the spread's is its premium's time decay between now and expiry,
  read off the two chains rather than modelled; the binary's is the collateral
  locked until 1 January at a rate marked `UNKNOWN` (no rate is assumed); the
  perpetual's funding is `UNKNOWN`.
- **E.** Execution at the sides one would hit, both fee schedules, best-level depth;
  this is `measure_band.rungs()`'s envelope reused, not re-derived.
- **F.** Payoff at settlement for the binary (0 or 1), the spread (0, linear, then
  `w`), the touch (0 or 1 on the path, which the terminal price does not determine —
  the row is present and flagged), the perpetual (`UNKNOWN`).
- **G.** Scenarios: `S_T` = K − 10%, K − 1%, K, K + 1%, K + 10%, and a tail at K + 50%;
  for each, the executable P&L per unit of capital for each instrument, with the
  maturity gap of the option chains shown as two columns (25DEC26 and 26MAR27) rather
  than interpolated (D-094).
- **H.** Constraints applied in the table: no liquidation (removes the perpetual by
  construction), maximum loss = capital (the binary and the long spread satisfy it),
  capped payoff acceptable (yes for this view).
- **I.** Output is the table itself, every `UNKNOWN` printed as the word.

**What the example is allowed to conclude.** Only which rows are computable from
the archive and what each costs and pays under each named scenario. Not that one is
"better": that is the constraint filter's job on a stated user input, and not a
statement this repository makes.

**What it needs before it runs.** Nothing new from the collector for the three
collected rows; B-019 for the perpetual column to become anything but `UNKNOWN`. The
rate for the binary's collateral cost is a dated, sourced constant if one is entered
(the pattern of `discount_referee.EXTERNAL_RATE`), or `UNKNOWN`.

---

## 6. What this is not

Not a router, not an execution system, not a recommendation engine. Not a claim that
any instrument is mispriced — that is Layer A's question and it has its own controls.
Not a model of expected returns: no drift is assumed anywhere in the scenario layer.
And not a reason to build a volatility surface (D-094): the option column uses chain
prices, differenced, exactly as the measurements do.
