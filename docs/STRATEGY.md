# STRATEGY.md — what Divergence is now, and what it is not

**Status:** current as of 2026-09-16 · **Decided in:** D-091 (structure), D-097 (Note 1),
D-099 (product), D-100 (assets), D-101 (waiting), D-102 (Project 3)
**Read next:** `RESEARCH_ROADMAP.md` for the research programme,
`PRODUCT_ROADMAP.md` for the staged product, `DECISION_GATES.md` for what has to be
true before anything is promoted.

This document exists so that the shape of the project does not live only in a chat
transcript. It states the shape; the reasoning behind each piece is in the decision
record it names. Where another document is canonical for a topic, this one links and
does not restate: the method is `METHODOLOGY.md`, the numbers are `findings/`, the
screen is `PRODUCT.md`, ideas not built are `BACKLOG.md` and `IDEA_BACKLOG.md`.

---

## 1. Three layers

The project is three related but distinct layers. Work in one must not be described as
work in another.

### Layer A — Divergence research (Project 2A)

Cross-market research on prediction-market prices against listed-derivative-implied
state prices, on the same underlying and — as far as the contracts allow — the same
event. The method after the correctness sprint (D-073 … D-090) is treated as a
defensible measurement framework; what remains open is listed in
`RESEARCH_ROADMAP.md` and is not the same thing as reopening the repairs.

The same-state work is being **finished** as Research Note 1 (D-097): how much
apparent divergence survives execution, maturity, settlement and strike-grid controls.
It is not expanded indefinitely and it is not the commercial thesis.

### Layer B — exposure-design research (Project 2B)

A new branch with its own question: **how should a market view be expressed across
instruments when capital, basis, carry, payoff shape, liquidity and settlement
differ?** It is deliberately not "which instrument is cheapest": futures, perpetuals,
vanilla options, spreads and binaries have different payoff functions, so the research
object is a frontier — cost × capital × payoff × basis × risk × execution — rather than
a single number. It is defined in `EXPOSURE_ENGINE.md` and it does not require two
venues to price the same event, which is the constraint that cost Layer A most of its
sprint.

### Layer C — product spin-off

A product that emerges in stages, each gated on evidence (D-099): a same-event payoff
card (V0), an event hedge studio (V1), a basis-aware exposure engine (V2). The research
is the credibility and methodology layer under it, not the product itself. See
`PRODUCT_ROADMAP.md`.

---

## 2. What the project is not

Unchanged from the review package and restated because every reader arrives at a
different document first. Divergence is not a betting product, a trading bot, a signal
service, an alpha engine, an arbitrage product, or a "true probability" engine. It does
not use the phrases "true probability", "correct probability" or "AI probability". A
probability gap is not automatically an arbitrage; it can be collateral cost,
commission, spread, variance risk premium, a difference in resolution source, or model
error, and the project's job is to separate these.

Two distinctions the review added and the project now keeps (D-095): a
**quoted-executable discrepancy** — one of the two trades leaves something after fees
at top-of-book quotes — is what the measurements establish; a **size-executable
opportunity** — depth, multiplier, legging, fills, staleness, slippage — is a second
standard that no measurement here has met. The first is never described as the second.

---

## 3. Research-first, and what that means in practice

Research comes first in the sense that a number reaches a screen only from a script
that reads the archive, that uncertainty is surfaced rather than resolved, and that a
mostly-null result is an acceptable result. It does not mean research is the only
output. The constraint the review set — a direction must raise both the credibility of
the research and the chance that the output is worth something to somebody — stays. The
staged product is how that constraint is met without turning the research into a
signal service.

Two things improve by waiting and are not built around (D-101): the 165-hour expiry
band closes when Deribit lists the weeklies straddling 1 January, and the validation
sample grows on its own. The do / wait / do-not lists are in D-101 and are binding.

---

## 4. The product's relationship to the research

- The research decides what a number means; the product decides what a user sees.
  `PRODUCT.md` records the constants that come from measurement and may not be changed
  without a new measurement.
- V0 uses only what the research already produces for BTC/ETH Polymarket price markets:
  the bid/ask and fee, the state-price reference and its executable envelope, the clock
  mismatch, the settlement source. Nothing in V0 is a recommendation.
- If the product is submitted to the Polymarket Builders programme, the submission is
  the product, not the research. Success is measured by users, repeated sessions,
  attributed routed trades and volume — not by methodology, stars or grant acceptance.
  The product is not built to satisfy a grant.
- "Best fit" in V1 means best under the user's stated constraints. It is not advice.

---

## 5. Project 3 — a separate, commercial-first track (D-102)

Not coded. A customer-discovery backlog is kept in `IDEA_BACKLOG.md`. The most
promising problem family identified so far is a post-alert crypto compliance and
investigation workflow (alert → evidence → transaction reconstruction → case notes →
decision → closure evidence) for a small VASP, crypto platform, fintech compliance
team or prediction-market operator. Other candidates are listed there. No revenue
projection enters a decision without buyer evidence; no code before discovery.

Project 3 shares nothing with Layers A–C except the people working on it. It is kept
in this repository's documents only so that the portfolio is written down in one place.

---

## 6. The portfolio, in one place

| track | what | state |
|---|---|---|
| Project 1 | on-chain / prediction-market research — wallet behaviour, integrity, measurement, datasets | separate; not in this repository |
| Project 2A | Divergence research — same-state pricing, methodology, validation | active; finishing Note 1 |
| Project 2B | exposure-design research — basis, carry, payoff, capital, execution | starting; methodology first |
| Project 2 product | payoff card → event hedge studio → basis-aware exposure engine | gated; V0 requirements only |
| Project 3 | commercial-first | customer discovery only |

**If only three outputs may exist in six months:** Research Note 1; the resolved-event
dataset with its validation specification; the Polymarket-native payoff / hedge card
MVP if discovery supports it — otherwise an exposure-design research note in its place.

---

## 7. How this document is kept true

It is prose, and prose is not recomputed (D-090). Every claim here that could go stale
names a decision record or a canonical file; when one of those changes, this document
is edited in the same commit or the next. A change of strategy is a new decision
record first and an edit here second, never the reverse.
