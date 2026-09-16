# RESEARCH_ROADMAP.md — the research programme

**Status:** current as of 2026-09-16 · **Decided in:** D-091, D-096, D-097, D-101
**Companion:** `DECISION_GATES.md` holds the pass / fail conditions in one place;
this file holds the questions, the data and the method.

Four notes, in order. Cross-asset generalisation comes after them, not before
(D-100). Each note is written so that a mostly-null result is a result.

A principle that applies to every note from Note 2 on (D-096): **discovery →
hypothesis freeze → forward, untouched test.** A hypothesis formed on data that is then
scored on the same data is a description, not a result.

---

## Note 1 — How much apparent prediction-market / options divergence survives execution, maturity, settlement and strike-grid controls?

**Status:** ACTIVE — being finished, not expanded. Draft at `drafts/RESEARCH_NOTE_1.md`
(its 2026-09-15 framing is superseded by D-097 and is being rewritten).

**Question.** Of the gaps that appear when a prediction-market price is put next to
the option-implied discounted state price for the same threshold, how much is left
after: pricing every leg at a quote that exists (D-076); both venues' published fees
(D-077); survival at both bracketing expiries (D-079, reclassified as a stress test by
D-094); the settlement-source difference (D-075, measured); and the strike grid
(sensitivity, `findings/sensitivity.json`)?

**Required data.** Already in the archive: Kalshi year-end and intraday ladders,
Polymarket daily terminal ladders, Deribit chains, all with microsecond timestamps and
a recorded sync window. Nothing new is collected for this note.

**Method.** `METHODOLOGY.md` in full. The claim set is the frozen family of 44
year-end rungs (D-096); the one rung that survives the maturity stress test is subject
to the pre-committed kill test of D-092; the discount factor carries the referees of
D-093. Terminology per D-095.

**Kill / continue gate.** The note is published when: the kill test has run and its
verdict is recorded (D-092 → a later decision); the discount referees have run and
their spread is recorded; `check_readme.py` and `ref_check.py` are green; and every
number in the note is reproduced by a named script from `findings/`. No forecast-
quality claim appears in it. A mostly-null result is publishable; a note that waits
for a positive result is not this note.

**Dependencies.** None external. December closes the expiry band on its own and is
not waited for — the note reports the band as it is.

---

## Note 2 — Do residual cross-market price differences contain incremental forecast information?

**Status:** WAITING_FOR_DATA.

**Question.** Given the prediction-market price, the option-derived `Q = DSP / D`, and
the realised outcome, does `PM − option` add predictive information beyond the
option-side quantity alone? This is the first place the project would say anything
about forecasting, and it is not said until the data allows it.

**Required data.** Resolved events paired with the prices that preceded them, with
lead time. `scripts/inventory_validation.py` counts what is available and collapses
snapshots of one contract into one event; today that is nine informative independent
events (`findings/validation_inventory.json`), growing by roughly two a day since the
collector fix of 2026-09-15. The validation specification (the second of the three
six-month outputs, D-102) is written while the sample accumulates.

**Method.** Pre-specified before the holdout is opened. Evaluation design, scoring
rule, and the definition of "independent event" are frozen in the specification, not
chosen after looking. Many snapshots of one contract are never many events.

**Kill / continue gate.** Planning thresholds, stated as heuristics (D-101):
exploratory around 30–50 independent events; preliminary around 100–200; stronger
publication around 300 or more or a sufficiently narrow uncertainty under the
pre-specified design. More important than the count: independence, lead time, horizon
diversity, an untouched holdout, regime diversity. The note is not started before the
exploratory threshold and is not called more than exploratory before the preliminary
one.

**Dependencies.** Note 1's controls (the residual is only meaningful after them); the
outcome pipeline being reliable (roadmap step 4).

---

## Note 3 — Do prediction markets exhibit a persistent long-shot premium?

**Status:** WAITING_FOR_DATA.

**Question.** Whether prediction-market prices at the wings are systematically above
or below the option-implied state price, across many events, many wings and multiple
tenors — not across three cherry-picked rungs. The three year-end tails that show an
edge today (D-078) are the motivation, not the evidence.

**Required data.** The frozen year-end family as a forward holdout; the intraday and
Polymarket daily ladders across tenors; enough distinct events that a wing effect can
be separated from a handful of contracts.

**Method.** Family-level, pre-declared, with the tenor and wing definitions frozen
before scoring. No multiple-testing correction is dressed onto a framework that does
not produce p-values (D-096); the report is "n of N in the declared family".

**Kill / continue gate.** Same thresholds as Note 2, applied to distinct events in the
wings. A result that holds only on the year-end tails is not a result about long shots.

**Dependencies.** Note 2's outcome pipeline; nearer Deribit expiries (December) to
reduce the maturity stress on the year-end wing.

---

## Note 4 — The cost–capital–basis–payoff frontier of expressing market views across instruments

**Status:** ACTIVE — methodology only. No engine is built for it yet.

**Question.** For a given directional or event view over a given horizon, what does it
cost, in every dimension that matters, to express it in a perpetual, a dated future, a
vanilla option, an option spread, and a prediction-market binary — where "cost" is a
frontier over capital, basis to the reference the view is about, carry, payoff shape,
liquidation exposure and execution, not a scalar?

**Required data.** What the archive holds today: Deribit chains, Polymarket and Kalshi
ladders. What it does not: perpetual funding, dated futures, and any non-crypto
reference. A minimal futures / perpetual funding ingest is a collector change and is
planned and asked about before it is built (D-101); it is B-019 in `BACKLOG.md`.

**Method.** `EXPOSURE_ENGINE.md` — reference normalisation, basis, carry, execution,
payoff, scenario, constraints, output. The motivating WTI case is an illustration
supplied by the owner, not a measurement (D-100).

**Kill / continue gate.** The methodology is complete when a worked example can be
computed end-to-end from archived data for one BTC or ETH view, with every UNKNOWN
named. The open risk, stated in the review package: the comparison may reproduce the
textbook answer that binaries are cheap carry and expensive convexity. If a first
worked example shows nothing beyond that, the note says so and stops.

**Dependencies.** None on Notes 2–3. It shares the archive with Note 1 and shares the
product's V1 with `PRODUCT_ROADMAP.md`.

---

## What is not on this roadmap

- Cross-asset generalisation (indices, commodities, equities): after these notes, and
  gated in `DECISION_GATES.md` on a real option-chain data path, licensing, and
  settlement comparability (D-100).
- A volatility surface (SVI or any other) adopted to close the year-end gap (D-094).
- Any "AI probability" or ML prediction layer (D-101).
- Anything that appears in `BACKLOG.md` or `IDEA_BACKLOG.md` without a promotion.
