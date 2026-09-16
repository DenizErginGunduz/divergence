# Validation specification — what would be scored, on what, and what stands in the way

**Status:** DRAFT v0, 2026-09-16 (D-106). This is the second of the three six-month
outputs (D-102) and the document that Note 2 (`docs/RESEARCH_ROADMAP.md`) may not be
started without. It is written while the sample accumulates and is frozen — by a
decision record, with a version number — before any holdout is opened. Until that
record exists nothing here licenses a score.

Rule 1 applies throughout: a parameter, an endpoint or a count that has not been
measured is written `UNKNOWN`, not guessed.

---

## 1. The question this validates

Note 2 asks whether `PM − option` — the prediction-market price minus the
option-derived risk-neutral quantity for the same threshold — carries forecast
information beyond the option quantity alone. Three things are therefore needed for
every scorable unit: the prediction-market price at a stated lead, the option-derived
quantity at the same instant (with its sync window), and the realised outcome. The
first two the archive has since 2026-08-30. This document is mostly about the third.

Nothing in it is a claim that either market forecasts well. It is the plan for
finding out.

## 2. Unit of analysis

- **An observation** is one (market, snapshot) pair with a live two-sided quote
  whose market later resolved.
- **A market** is one Kalshi ticker (one rung).
- **An independent event** is one Kalshi `event_ticker`: every rung of one ladder
  resolves from one reading of one price, so a 44-rung ladder is one draw. **The
  count that governs a standard error is the number of independent events**, and
  every threshold in §6 is stated in those units. Many snapshots of one contract
  are never many events.
- **Lead time** is `close_time − snapshot instant`, in hours, per observation. A
  quote fourteen minutes before settlement and one a month before are not the same
  forecast and are never pooled; lead-time bins are part of the frozen design.

`scripts/inventory_validation.py` produces all four counts and the lead-time
quartiles in `findings/validation_inventory.json`. It scores nothing.

## 3. What the archive captures today — measured

Outcomes reach the archive through the collector's main pass, which fetches up to
5 × 200 rows per series with **no status filter**, so resolved markets come back with
`result` set to `yes` or `no`. On the public 14-day window, for every market that was
seen live with a two-sided quote and whose close lies more than 24 hours before the
last snapshot:

| series | seen live, closed > 24 h | outcome captured | note |
|---|---|---|---|
| KXBTC15M | 40 | 40 | fifteen-minute markets |
| KXETH15M | 39 | 39 | fifteen-minute markets |
| KXBTCPRICE | 2 | 1 | the other is `closed`, not yet `finalized` — pending, not lost |
| KXBTC, KXETH (hourly ladders) | — | **none possible** | see §4 |
| KXBTCD, KXETHD (hourly cumulative ladders) | — | **none possible** | see §4 |

Public-window inventory at the last snapshot (2026-09-16T1314Z): 5,041 resolved
markets seen, 157 with a prior live quote, 286 scorable observations, **121
independent events**, lead median 6.87 h (p25 0.23 h, p75 17.25 h). 112 of the 157
markets are fifteen-minute markets. These are lower bounds; the private mirror holds
everything since 2026-08-30 and is not read by the script.

## 4. The capture defect, and why it is structural

For the hourly ladders — KXBTC, KXETH, KXBTCD, KXETHD — every snapshot holds exactly
**1,000 rows with status `initialized` and 200 with status `active`, and not one
resolved row**. The main pass's 1,000 rows are filled by not-yet-open hourly markets
(each future event lists 200 or more rungs, and days of events are listed ahead), so
the settled ones are never reached; the open pass adds live quotes and nothing else.
The tenor with the tight expiry match — the one Note 2 would most want — therefore
has live prices in the archive and **no outcomes**, and cannot be scored from the
archive as collected.

The fifteen-minute series do not have this problem only because their future rows
are few (59 `initialized` in the last snapshot) and their settled rows fill the rest
of the 1,000; the API's row order does the right thing there by accident, not by
design. That order is `UNKNOWN` and is not relied on.

Curing this is a collector change: an additional pass for the truncated series
asking explicitly for settled markets (Kalshi's `/markets` takes a `status` filter —
the open pass already uses `status=open`; whether it also takes close-time bounds,
and which values return the settled hourly markets of the last day, is `UNKNOWN`
until the documentation is read and the call is tried). It changes what the
archive holds and adds calls to the sync window, so it is asked for, not made:
**B-023**. Until it lands, Note 2's sample is the fifteen-minute series plus the
small monthly and yearly series, and the hourly ladders are priced but unscored.

## 5. Requirements for a reliable outcome pipeline

| # | requirement | status |
|---|---|---|
| R1 | Every market seen live is later seen with `result ∈ {yes, no}`, or with a status that says why not (`closed` pending settlement; `voided`) | met for 15M and the small series (79 of 81 on the public window); **not met** for hourly ladders (§4) |
| R2 | The outcome is captured with the settlement value (`expiration_value`) so the rung's truth can be re-derived from the ladder's own thresholds | field archived when present; coverage per series `UNKNOWN` |
| R3 | The resolution source and its rule text are quoted, not summarised (working rule 3) | Kalshi rule text: per-market `rules_primary` archived; CF Benchmarks reference quoted in `docs/DATA_SOURCES.md`; Polymarket resolution capture `UNKNOWN` — not inventoried |
| R4 | No observation enters the sample from a snapshot whose sync window exceeds the bound in use for prices (`METHODOLOGY.md`) | enforced by the same window field; threshold to be fixed in the frozen design |
| R5 | The count is by independent event and by lead-time bin, before any score is computed | `inventory_validation.py` counts events; lead-time bins not yet fixed |
| R6 | Polymarket outcomes | `UNKNOWN` — the inventory reads Kalshi only; Polymarket resolution fields are archived but not yet inventoried |

## 6. What will be frozen before the holdout opens (not yet frozen)

The following are listed so the choices are visible now and are not made after
looking at outcomes. Each is `TO FREEZE` until the freezing decision record names
it.

- **Scoring rules.** Brier score and log score of the prediction-market price and of
  the option-derived quantity against the outcome; the incremental question is put
  as a pre-specified comparison of the two, and of a stated combination of them, on
  the same events. Which combination: `TO FREEZE`.
- **The option-derived quantity.** `Q = DSP / D` at the nearest chain, with the
  expiry side recorded (`before` understates an upside tail, `after` overstates it,
  D-082) and the strike-grid sensitivity carried as an uncertainty, not a correction.
- **Lead-time bins.** `TO FREEZE`; candidates are the quartiles the inventory
  reports, so that a bin is not chosen to flatter a result.
- **Independence.** One event, one draw. Rungs of one ladder are never pooled as
  independent. Events of the same series on the same day: `TO FREEZE` whether they
  count as one regime draw.
- **Holdout.** The forward-test split of D-096: everything up to the freeze date is
  discovery; everything after is holdout and is not read until the design is frozen.
- **Thresholds (D-101, heuristics not laws).** Exploratory around 30–50 independent
  events; preliminary around 100–200; stronger publication around 300 or a
  sufficiently narrow uncertainty under the frozen design. The note is not started
  before the exploratory threshold and is not called more than exploratory before
  the preliminary one. Count, independence, lead time, horizon diversity and regime
  diversity all have to hold, not the count alone.

## 7. What this document does not do

It does not score. It does not read the private mirror. It does not decide whether
the fifteen-minute series — quoted a median of eleven minutes before settlement on
the public window — are a forecast at all rather than a measurement of how fast a price converges to an
outcome already in view; that question is part of the frozen design and is asked
there, not here.
