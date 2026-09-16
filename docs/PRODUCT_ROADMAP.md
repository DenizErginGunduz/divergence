# PRODUCT_ROADMAP.md — the staged product, and the gates between stages

**Status:** current as of 2026-09-16 · **Decided in:** D-099 (staging, Builders),
D-095 (terminology), D-100 (assets)
**Companion:** `PRODUCT.md` records what the existing research screen says and why;
this file records what the product *becomes*, in what order, and what has to be true
first. `DECISION_GATES.md` carries the gates in one list.

Nothing here is built ahead of its gate. The research is the credibility layer under
the product, not the product (D-099).

---

## V0 — Same-event payoff card

**Scope.** BTC / ETH Polymarket price markets only. Polymarket-native, ticket-adjacent:
it sits next to the market a user is already looking at and tells them what the
contract is, priced against the option chain, without telling them what to do.

**Displays** (every field comes from something the pipeline already computes):

| field | source |
|---|---|
| Polymarket bid / ask | archived market payload |
| Polymarket fee at that price | `scripts/fees.py`, schedule read per market |
| state-price / call-spread reference | `digital()` — a discounted state price, labelled as such (never "probability", B-013) |
| execution envelope | `opt_low` … `opt_high` from the sides one would hit |
| clock mismatch | signed expiry gap in hours, as `measure_band.py` reports it |
| settlement source | the market's resolution text, quoted verbatim (rule 3) |
| simple scenario payoff | binary payoff at settlement for YES / NO at the quoted price |
| basis / carry fields | where available — today, none; shown as UNKNOWN, not omitted |

**Does not display:** BUY, SELL, EDGE, ALPHA, ARBITRAGE — unless literally justified,
and D-095 says when they are not. A quoted-executable discrepancy may be shown as a
number with its envelope; it is not shown as an opportunity.

**Routing.** If product testing ever reaches execution, only the Polymarket leg is
routed, through the Builders framework. The option leg is never routed by this
product.

**Build gate** (from `DECISION_GATES.md`): the V0 requirements below are answered;
Note 1 is frozen (D-096, D-097) so that the card's reference number has a published
method behind it; the data-rights position for what the card shows is written down;
and there is at least one identified user who has the repeated job the card serves.
Without the last, the card is not built to see whether users appear.

### V0 requirements (roadmap step 7, D-109)

Defined 2026-09-16. Four groups: what the pipeline can already answer, what the
card must do regardless of who uses it, what only discovery can answer, and what
only a reading of the venues' terms can answer. Nothing is built until the last two
groups have answers; the first two are written so that the answers have something
to attach to.

**A. Functional — answerable from the pipeline today**

| # | requirement | source and status |
|---|---|---|
| F1 | One card per Polymarket BTC / ETH terminal price market, keyed by the market's condition id, showing the eight displays in the table above | every field is computed today by `measure_polymarket.py` / `measure_band.py`; nothing new is derived |
| F2 | The option-side number is labelled a **discounted state price** and carries its envelope (`opt_low` … `opt_high`), its expiry, its expiry side (`before` / `after`) and its gap in hours | as `findings/latest.json` reports them (D-082, D-094) |
| F3 | The card's fee line uses the market's own archived `feeSchedule`, not a constant | `fees.py`, per market (D-085) |
| F4 | A market whose ladder is a **touch** market gets no state-price reference — only the model-free bound "touch ≥ terminal", with the words | `measure_touch.py`; the terminal/touch distinction is the first thing `README.md` explains |
| F5 | A rung the grid cannot resolve (identical digital to a neighbouring rung, `findings/sensitivity.json` flat share) says so on the card | sensitivity output; the intraday families are excluded for this reason |
| F6 | Every number on the card traces to a script and a snapshot stamp shown on the card (working rule 5) | `findings/latest.json` carries `archive.last`; the card shows it |

**B. Non-functional — required regardless of user**

| # | requirement |
|---|---|
| N1 | **Freshness.** The card states the snapshot instant it was computed from and the sync window; a card older than the collector's cadence (three runs a day) says "stale" rather than showing a number as if current (rule 6). |
| N2 | **No number without its envelope.** A state price is never shown without `opt_low` … `opt_high`; a quoted difference is never shown without both fees; a size is never shown without the level it rests at. |
| N3 | **UNKNOWN is a value.** Basis, carry and any field the archive does not hold are displayed as the word, in the same place a number would be. Nothing is omitted to make the card look complete. |
| N4 | **Forbidden words.** BUY, SELL, EDGE, ALPHA, ARBITRAGE, SIGNAL, TRUE / FAIR / AI PROBABILITY do not appear (D-095, `METHODOLOGY.md` terminology). "Quoted-executable discrepancy" is the strongest phrase the card uses, and only when the number is one. |
| N5 | **The card does not compute in the browser.** It reads a findings file the pipeline wrote (the pattern of `web/index.html`); the arithmetic lives in `scripts/`, once (working rule 5). |
| N6 | **Interface holds no numbers of its own.** Thresholds, fees and rules come from the archive and the scripts; a change to any of them is a commit to `scripts/`, not to the card. |

**C. Discovery — to be answered by the owner, with a named person, before the build gate**

| # | question | status |
|---|---|---|
| Q1 | Who is the user — one identified person with the repeated job, not a persona | `UNKNOWN` |
| Q2 | What is the repeated job, in their words | `UNKNOWN`; the hypothesis remains "before I buy this contract, what does the option chain say it is worth and what would it cost me to trade against that" |
| Q3 | Which market family they actually look at (daily terminal ladders are the candidate; year-end touch markets are not comparable; intraday families are unresolvable by the grid) | `UNKNOWN` |
| Q4 | Whether they would act on a card that shows an `UNKNOWN` carry field, or whether the card is useless until B-019 | `UNKNOWN` |
| Q5 | Whether Builders attribution requires routing for V0 at all, and what the attribution mechanism is | `UNKNOWN` — the Builders documentation has not been read here |

**D. Data rights — to be answered by reading, before the build gate**

| # | question | status |
|---|---|---|
| R1 | Whether a card shown to a third party, derived from Deribit's public endpoints, is "personal use" under Deribit's terms as quoted in `DATA_SOURCES.md` | **unresolved**; `DATA_SOURCES.md` records that the current position suits a research project and that a product changes the analysis |
| R2 | Whether the Polymarket Builders terms permit or require anything about how the reference number is presented | `UNKNOWN` — not read |
| R3 | Kalshi is not on the card (V0 is Polymarket-only), so the unread Kalshi Developer Agreement does not gate V0; it gates any later card that shows Kalshi data | noted, not resolved |

**Build gate, restated.** A and B are met by construction once the card reads the
findings file. Q1–Q3 need a named person; R1–R2 need a reading. Without the first
the card is not built to see whether users appear (D-099); without the second it is
not shown to anyone.

---

## V1 — Event hedge studio

**Adds.** The user's view (bullish / bearish / event), target, horizon, capital,
maximum loss, liquidation tolerance, optional target payoff; a perpetual / dated
future comparison with funding and basis; options and spreads; scenario analysis.

**Output.** A small set of feasible exposure structures under the user's constraints,
each with its cost, capital, payoff shape, basis and execution fields shown — and a
"best fit for your stated constraints", followed by why, alternatives, and the full
comparison. "Best fit" means best under explicit user constraints; it is not financial
advice, highest expected return, true value, or the objectively best trade, and the
interface says so where it shows it.

**Requires.** The exposure-design methodology (`EXPOSURE_ENGINE.md`) complete to the
point of one end-to-end worked example; a funding / futures ingest (B-019), which is a
collector change and is asked about first; and V0 having shown demonstrated usage.

**Promotion gate.** V0 users return; the repeated job is confirmed; the methodology
has a worked example; the ingest exists. Not before.

---

## V2 — Basis-aware exposure engine

**Adds.** Expansion from crypto to equity indices and selected commodities, with
reference normalisation, basis, carry, multi-venue exposure and a deeper scenario /
risk engine.

**Requires.** Everything V1 requires, plus the cross-asset gate in
`DECISION_GATES.md` — a real option-chain data path, licensing understood, settlement
comparability verified (D-100). Yahoo-quality data is not assumed sufficient; B-017
records that the free route has no recorded result.

**Promotion gate.** Demonstrated V1 usage. No commitment to V2 before V0 and V1 have
been validated; a roadmap is not a promise to build its last stage.

---

## The Polymarket Builders programme

- The submission, if made, is V0 positioned as the first module of the event hedge
  studio — a real product, not the research.
- Success is measured by users, repeated sessions, attributed routed trades,
  attributed volume, and conversion from comparison to Polymarket execution. It is not
  measured by methodological sophistication, GitHub stars, screenshots, or grant
  acceptance.
- The product is not built solely to satisfy a grant. It continues without one only if
  users actually value it; if they do not, the third six-month output becomes the
  exposure-design research note instead (D-102).

---

## What is explicitly not built (D-101)

Generic dashboard expansion; alerts (B-007 stays in the backlog); a broad API
product; an ML prediction engine; an "AI probability" layer; cosmetic interface
expansion as a project goal; a full cross-venue router before V0 and V1 have earned
it.
