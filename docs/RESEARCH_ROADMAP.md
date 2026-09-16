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

**Status:** ANALYTICAL SPECIFICATION FROZEN — v1, 2026-09-16 (D-107). Draft at
`drafts/RESEARCH_NOTE_1.md`, written to D-097 and to the kill-test verdict of D-103.
What remains before publication is the G2 checklist, not more analysis.

**Question.** Of the gaps that appear when a prediction-market price is put next to
the option-implied discounted state price for the same threshold, how much is left
after: pricing every leg at a quote that exists (D-076); both venues' published fees
(D-077); survival at both bracketing expiries (D-079, reclassified as a stress test by
D-094); the settlement-source difference (D-075, measured); and the strike grid
(sensitivity, `findings/sensitivity.json`)?

**Frozen specification (v1).** Changing any line below is a new version under a new
decision record; re-running the same lines on a longer archive is not.

| element | fixed as | produced by |
|---|---|---|
| claim set | the 44 Kalshi year-end rungs of BTC and ETH, frozen by D-096; no rung is added or dropped after the fact | `scripts/measure_band.py`, `findings/latest.json` → `friction_band_kalshi.year_end` |
| unit | one rung-observation = one rung in one snapshot; persistence = positive edge in ≥ 90% of a rung's observations (`stability.py`) | same |
| option-side quantity | discounted state price `D·Q` from the vertical spread on the nearest chain; `D` from the put-call residual (D-073), with the referees of D-093 recorded beside it | `measure_band.digital()`, `discount()`; `scripts/discount_referee.py` |
| execution control | sell the prediction at its bid, buy the bucket at ask-on-long / bid-on-short, both venues' published fees (D-076, D-077); no mid in the verdict | `measure_band.rungs()`, `fees.py` |
| maturity control | both bracketing expiries, read as a stress test not a bound (D-094); the interpolant reported as a sensitivity only | `scripts/measure_sensitivity.py` |
| settlement control | BRTI-vs-index basis measured and reported, not corrected for (D-075) | `scripts/measure_basis.py` |
| grid control | the same digital at skip-1 and skip-2 brackets; the relative spread reported as an uncertainty, not a correction (D-079) | `scripts/measure_sensitivity.py` |
| kill test | the pre-committed test of D-092 on any rung that clears the maturity stress test; verdict words used as written (D-103) | `scripts/kill_test_eth5k.py`, `findings/kill_test_eth5k.json` |
| second venue | Polymarket daily terminal ladders under the identical test (D-085); not compared like-for-like with Kalshi | `scripts/measure_polymarket.py` |
| touch bound | model-dependent, reported as a pipeline validation and a statement about the bound, never as mispricing | `scripts/measure_touch.py` |
| multiplicity | no Benjamini–Hochberg or other correction; the claim is persistence of named rungs, tested by forward holdout (D-096) | — |
| exhaustiveness | one event per series, partitions only (D-105); a set-aside ladder is named, not summed | `scripts/measure_exhaustive.py` |
| terminology | D-095: quoted-executable discrepancy vs size-executable opportunity; no "edge", "signal", "arbitrage", "true probability" | every surface |
| what the note may claim | how much survives each control, with the numbers; the verdict of D-103 in its words; errors found in our own work | — |
| what it may not claim | forecast quality (Note 2); a dollar figure as a trade (D-095); anything about assets beyond BTC and ETH (D-100) | — |

**Required data.** Already in the archive; nothing new is collected for this note.

**Kill / continue gate (G2).** Published when: the kill test verdict is recorded
(D-103 — done); the discount referees have run and their spread is recorded (D-104 —
done); this specification is frozen (D-107 — done); every number in the note is
reproduced by a named script from `findings/` (the note cites them); `check_readme.py`
and `ref_check.py` are green; no forecast-quality claim appears. A mostly-null result
is publishable; a note that waits for a positive result is not this note.

**Dependencies.** None external. December's weeklies straddling 1 January will let
the same kill test re-run with a band of days; that is a re-run of v1, not a new
version, and it is waited for rather than built for.

---

## Note 2 — Do residual cross-market price differences contain incremental forecast information?

**Status:** WAITING_FOR_DATA.

**Question.** Given the prediction-market price, the option-derived `Q = DSP / D`, and
the realised outcome, does `PM − option` add predictive information beyond the
option-side quantity alone? This is the first place the project would say anything
about forecasting, and it is not said until the data allows it.

**Required data.** Resolved events paired with the prices that preceded them, with
lead time. `scripts/inventory_validation.py` counts what is available and collapses
snapshots of one contract into one event: 121 independent events on the public
window at 2026-09-16, most of them fifteen-minute markets quoted minutes before
settlement (`findings/validation_inventory.json`). Outcome capture is reliable for
those series and absent for the hourly ladders until the collector asks for settled
markets (D-106, B-023). The validation specification is open at
`docs/VALIDATION_SPEC.md` (DRAFT v0) and is frozen before any holdout is opened.

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
outcome pipeline being reliable — checked in roadmap step 4 (D-106): reliable for the
fifteen-minute and small series, not for the hourly ladders.

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

**Status:** ACTIVE — methodology only. No engine is built for it yet. The first
worked example is specified in `EXPOSURE_ENGINE.md` §5 (D-108) and not yet computed.

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
