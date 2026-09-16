# DECISION_GATES.md — what has to be true before anything is promoted

**Status:** current as of 2026-09-16 · **Decided in:** D-092, D-097, D-099, D-100,
D-101, D-102

One list, so that the question "may we do X yet?" has one place to be answered. Each
gate names its inputs, its pass condition, and what happens on fail. A gate is passed
by a decision record that says so and cites the evidence; it is not passed by a
sentence in chat. Gates marked **pre-committed** were written before the evidence
existed and may not be edited after the evidence is in.

| # | gate | status |
|---|---|---|
| G1 | ETH > $5k anomaly kill test | CLOSED — verdict recorded in D-103: not a surviving discrepancy |
| G2 | Note 1 publish | OPEN — G1 verdict and referee spread (D-104) in; analytical freeze and the rewritten note outstanding |
| G3 | Note 2 sample / data | OPEN — waiting for data |
| G4 | Payoff card (V0) build | OPEN |
| G5 | Builders application | OPEN |
| G6 | Event hedge studio (V1) promotion | OPEN |
| G7 | Cross-asset expansion | OPEN |
| G8 | Project 3 coding | OPEN |

---

## G1 — ETH > $5k anomaly kill test (D-092) — pre-committed

**Inputs.** `findings/kill_test_eth5k.json`, produced by `scripts/kill_test_eth5k.py`
over the full mirror via the `measure` workflow.

**Verdict rules, fixed before the number:**
- `margin_vs_worst_local_executable` positive in fewer than 90% of snapshots (the
  `always_above` threshold of `scripts/stability.py`) → **not a surviving
  discrepancy**.
- All estimators positive but the smallest margin below 0.01, or margin × resting depth
  below 1 USD → **indistinguishable from grid and quote noise**.
- Otherwise → **a genuine anomaly requiring more observations**, and nothing stronger.

**On any outcome.** A decision record states the verdict with the numbers; Note 1,
`README.md` and the interface use the verdict's exact words; the rung is not called a
finding, alpha, mispricing, artefact or noise under any outcome.

**Outcome (2026-09-16).** Run on the full mirror, 68 snapshots: the margin against the
worst local executable estimate is positive in 0 of 62 judged snapshots → **not a
surviving discrepancy** (D-103). The gate is closed and this section is not edited
further.

## G2 — Note 1 publish (D-097)

**Pass when all of:** G1 has a recorded verdict; `findings/discount_referee.json`
exists and its spread is recorded in a decision; the analytical specification is
frozen (roadmap step 5) and the note's claim set is the frozen 44-rung family (D-096);
every number in the note is reproduced by a named script; `check_readme.py` and
`ref_check.py` are green; the note contains no forecast-quality claim.

**On fail.** The note is not published; the missing item is named in `BACKLOG.md`.

## G3 — Note 2 sample / data (D-101)

**Inputs.** `findings/validation_inventory.json` — informative independent events, not
snapshots and not markets.

**Pass conditions, by stage (heuristics, not laws):** exploratory ≥ ~30–50 independent
events; preliminary ≥ ~100–200; stronger publication ≥ ~300 or a sufficiently narrow
uncertainty under the pre-specified design. In every stage: the evaluation design is
frozen before the holdout is opened; lead time, horizon diversity and regime diversity
are reported alongside the count.

**On fail.** Wait. Nothing is built to accelerate the sample; the collector already
grows it.

## G4 — Payoff card (V0) build (D-099)

**Pass when all of:** the five V0 requirements in `PRODUCT_ROADMAP.md` have answers
that are not `UNKNOWN` (exact user, market family, repeated job, routing requirement,
data-rights-safe external information); G2's freeze is in place so the card's
reference number has a published method; at least one identified user has the
repeated job; the data-rights position for what the card displays is written in
`DATA_SOURCES.md`.

**On fail.** Not built. The third six-month output becomes the exposure-design
research note (D-102).

## G5 — Builders application (D-099)

**Pass when:** G4 has passed, and the submission is V0 as a product, positioned as the
first module of the event hedge studio. The research is not submitted as the product.

**On fail.** No application. The product is not built to satisfy a grant.

## G6 — Event hedge studio (V1) promotion (D-099)

**Pass when all of:** V0 shows demonstrated usage — users return, the repeated job is
confirmed by use, and where routing exists, attributed trades exist;
`EXPOSURE_ENGINE.md` has one end-to-end worked example computed from archived data;
the funding / futures ingest (B-019) exists — a collector change, asked about before
it is built.

**On fail.** V0 stays V0.

## G7 — Cross-asset expansion (D-100)

**Pass when all of, per asset class:** a real option-chain data path exists and has a
recorded result (B-017 records that the free index route has none); the licensing
implications of that path are understood and written in `DATA_SOURCES.md`; settlement
comparability between the prediction contract and the listed derivative is verified
the way `audit_semantics.py` verifies it for crypto. Yahoo-quality data is not
sufficient by assumption. ETF proxies are rejected where tracking error, roll, fees,
dividends, early exercise or basis add more noise than information (B-002).

**On fail.** BTC / ETH remain the measured universe. WTI stays a research case for
exposure design, not a covered asset.

## G8 — Project 3 coding (D-102)

**Pass when:** customer discovery has been conducted with the potential buyers named
in `STRATEGY.md` §5 and a repeated, paid-for job is documented in `IDEA_BACKLOG.md`
with the evidence attached. No revenue projection counts as evidence.

**On fail.** Discovery continues; no code.

---

## How a gate changes

A gate's pass condition may be tightened at any time by a decision record. It may be
loosened only by a decision record that explains what evidence showed the original
condition to be wrong — not by the wish to pass it. Pre-committed gates (G1) may not be
edited after their evidence exists.
