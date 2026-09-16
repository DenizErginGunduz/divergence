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

### V0 requirements — to be answered before anything is built (roadmap step 7)

| requirement | answer |
|---|---|
| exact user | UNKNOWN — to be found by discovery, not assumed |
| exact Polymarket market family | UNKNOWN — the daily BTC/ETH terminal ladders the pipeline already measures are the candidate; the intraday families are not, because the strike grid cannot resolve them (67.4% flat rungs, `findings/sensitivity.json`) |
| exact repeated job | UNKNOWN — the hypothesis is "before I buy this contract, what does the option chain say it is worth and what would it cost me to trade against that"; a hypothesis until a user says it |
| routing requirement | UNKNOWN — whether Builders attribution requires routing at all for V0 |
| minimum data-rights-safe external information | the option-side reference is derived data from Deribit's public endpoints; `DATA_SOURCES.md` quotes the terms; what may be shown to a third party from that derived data is unresolved and is asked before the card is built |

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
