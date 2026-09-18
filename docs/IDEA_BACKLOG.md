# IDEA_BACKLOG.md — product and research ideas, kept with their reasoning

**Status:** current as of 2026-09-16 · **Decided in:** D-091 (nothing valuable
disappears), D-099, D-102
**Relationship to `BACKLOG.md`:** that file is the engineering and methodology
backlog (B-numbered: things the pipeline could do and does not). This file holds
product and research *hypotheses* — who would use a thing, why, and what would have to
be true to build it. An item that graduates from here into work usually acquires a
B-number there and a decision record.

Statuses: `ACTIVE` · `EXPERIMENT` · `WAITING_FOR_DATA` · `CUSTOMER_DISCOVERY` ·
`BACKLOG` · `REJECTED`. Rejected items stay, with the reason.

Every entry: STATUS · SOURCE / DATE · DESCRIPTION · WHY INTERESTING · WHY NOT ACTIVE ·
PROMOTION CONDITION, plus USER / PROBLEM / REUSE / MAIN RISK where they are known.

---

## Product ideas (Layer C)

### I-001 — Same-event payoff card
STATUS: ACTIVE (requirements only; build gated on G4) · SOURCE: external review synthesis, 2026-09-16
DESCRIPTION: see `PRODUCT_ROADMAP.md` V0. · WHY INTERESTING: ticket-adjacent, Polymarket-native, uses only what the pipeline computes. · WHY NOT ACTIVE: exact user, market family and repeated job are UNKNOWN. · PROMOTION CONDITION: G4.

### I-002 — Event / portfolio hedge tool
STATUS: BACKLOG · SOURCE: review synthesis, 2026-09-16
USER: a holder of a crypto position or an event exposure. · PROBLEM: which instrument hedges this exposure over this horizon under these constraints. · WHY INTERESTING: it is V1 of the product (`PRODUCT_ROADMAP.md`). · WHY NOT NOW: V0 unvalidated; funding ingest absent (B-019). · REUSE: the whole measurement pipeline; `EXPOSURE_ENGINE.md`. · MAIN RISK: becomes advice. · PROMOTION CONDITION: G6.

### I-003 — Binary ↔ call-spread translator
STATUS: BACKLOG · SOURCE: review synthesis, 2026-09-16
USER: anyone reading a prediction contract next to an option chain. · PROBLEM: what vertical spread replicates this binary, at what executable cost, and the reverse. · WHY INTERESTING: it is `digital()` and the envelope, exposed as a tool; the smallest real product in the list. · WHY NOT NOW: overlaps V0; ship inside V0 rather than beside it. · REUSE: total. · MAIN RISK: reads as an arbitrage tool; D-095 wording applies. · PROMOTION CONDITION: G4, as a V0 field.

### I-004 — Multi-leg prediction-market bracket / combo builder
STATUS: BACKLOG · SOURCE: review synthesis, 2026-09-16
PROBLEM: building a range or bucket exposure from several prediction contracts with fees per order. · WHY INTERESTING: exhaustive ladders sum to D (D-073); the fee round-up per order (D-077) makes multi-leg cost non-obvious. · WHY NOT NOW: no identified user. · PROMOTION CONDITION: a V0 user asks for it.

### I-005 — Settlement-rule linter
STATUS: BACKLOG · SOURCE: review synthesis, 2026-09-16
PROBLEM: does this contract's rule text parse, tile the outcome line, and name a settlement source that matches what the user thinks. · WHY INTERESTING: `scripts/audit_semantics.py` already does this for Kalshi crypto; it is the most reusable piece of the pipeline. · WHY NOT NOW: research use only so far; who pays is UNKNOWN. · REUSE: the audit script. · MAIN RISK: rule text changes venue by venue; a linter that tolerates rewording tolerates the wrong event. · PROMOTION CONDITION: an operator or a Builders user names the job.

### I-006 — Resolution-risk monitor
STATUS: BACKLOG · SOURCE: review synthesis, 2026-09-16
PROBLEM: which open contracts have a resolution source, window or instant that differs from the instrument a user would hedge with. · WHY INTERESTING: the settlement-basis measurement (D-075) found the index difference small and the averaging window and instant unmeasured; this is those two, watched. · WHY NOT NOW: needs the outcome pipeline first (roadmap step 4). · PROMOTION CONDITION: G3 exploratory stage.

### I-007 — Negative-risk / complete-set helper
STATUS: BACKLOG · SOURCE: review synthesis, 2026-09-16
PROBLEM: when a set of contracts is worth more or less than the certain payoff it sums to, after fees. · WHY INTERESTING: it is the exhaustiveness constraint (D-073) as a user tool. · WHY NOT NOW: Polymarket-specific mechanics not yet read verbatim. · PROMOTION CONDITION: rule text read and quoted; a user names the job.

### I-008 — Fee-aware position-size widget
STATUS: BACKLOG · SOURCE: review synthesis, 2026-09-16
PROBLEM: the smallest order at which the per-order fee round-up stops eating a given edge. · WHY INTERESTING: `fees.min_contracts()` already computes it. · WHY NOT NOW: a V0 field, not a product. · PROMOTION CONDITION: G4.

### I-009 — Cross-venue settlement and basis terminal
STATUS: BACKLOG · SOURCE: review synthesis, 2026-09-16
WHY INTERESTING: the reference and basis layers of `EXPOSURE_ENGINE.md` as a screen. · WHY NOT NOW: V2 territory; do not build a terminal (D-101). · PROMOTION CONDITION: G6 and G7.

### I-010 — Prediction-market-implied distribution API
STATUS: REJECTED for now · SOURCE: review synthesis, 2026-09-16
REASON: a broad API product is on the do-not list (D-101); data rights for redistributing derived data are unresolved (`DATA_SOURCES.md`). Kept because the ladder-to-density arithmetic exists (`METHODOLOGY.md` §1). · PROMOTION CONDITION: a data-rights answer and a paying user, in that order.

### I-011 — Post-trade settlement reconstruction
STATUS: BACKLOG · SOURCE: review synthesis, 2026-09-16
PROBLEM: after a contract settles, reconstruct from archived streams what the settlement value was, from which source, at which instant. · WHY INTERESTING: it is the outcome pipeline (roadmap step 4) seen from the user's side. · PROMOTION CONDITION: G3.

### I-012 — Builder attribution / economics analytics
STATUS: CUSTOMER_DISCOVERY · SOURCE: review synthesis, 2026-09-16
USER: Polymarket Builders. · PROBLEM: what attributed volume is worth and where it comes from. · WHY NOT NOW: no Builders product of our own yet. · PROMOTION CONDITION: G5.

### I-013 — Stablecoin depeg protection
STATUS: BACKLOG · SOURCE: review synthesis, 2026-09-16
WHY INTERESTING: a binary hedge with a clear reference and a clear event. · WHY NOT NOW: outside BTC/ETH (D-100); no data path. · PROMOTION CONDITION: G7 for the asset, then discovery.

### I-014 — Token-unlock hedge portal
STATUS: BACKLOG · SOURCE: review synthesis, 2026-09-16
WHY NOT NOW: outside the measured universe; event definitions not read. · PROMOTION CONDITION: G7 and discovery.

### I-015 — Macro event hedge mapping
STATUS: BACKLOG · SOURCE: review synthesis, 2026-09-16
WHY INTERESTING: prediction markets list macro events that listed derivatives price only indirectly; the reference-normalisation layer is the hard part. · WHY NOT NOW: cross-asset (D-100). · PROMOTION CONDITION: G7.

### I-016 — Oracle-resolution risk tooling
STATUS: BACKLOG · SOURCE: review synthesis, 2026-09-16
WHY INTERESTING: adjacent to I-005 and I-006 for on-chain resolution. · WHY NOT NOW: Polymarket resolution mechanics not yet read verbatim. · PROMOTION CONDITION: rule text quoted; an operator names the job.

---

## Research ideas (Layers A and B)

### I-101 — Cost of expressing a view (original §7.1 framing)
STATUS: superseded by `EXPOSURE_ENGINE.md` · SOURCE: the external review round, 2026-09-16 (D-091)
REASON: the review broadened it from a cost comparison to a frontier (D-091). Kept so the original framing and its reasoning are not lost.

### I-102 — Venue selection as the product (§7.3)
STATUS: BACKLOG · SOURCE: review package §7.3
DESCRIPTION: "given that you want this exposure, which venue should you use right now, after fees, spread and settlement differences?" · WHY INTERESTING: defensible on nine events; closer to a real decision than "is there an edge". · WHY NOT ACTIVE: absorbed into V1's constraint filter; as a standalone product it is a router, which is not built first (D-099). · PROMOTION CONDITION: G6.

### I-103 — Waiting (§7.4)
STATUS: ACTIVE, as policy · SOURCE: review package §7.4; D-101
DESCRIPTION: build nothing to close the expiry band or grow the validation sample; both improve on their own.

### I-104 — A volatility surface (SVI or other) to close the year-end gap
STATUS: REJECTED · SOURCE: review synthesis, 2026-09-16; D-094
REASON: replaces methodological uncertainty with model complexity; nearer expiries arrive in December and resolve the gap without a model. Kept so the rejection and its reason survive the next time it sounds quantitative.

### I-105 — Benjamini–Hochberg / p-values on the quoted-edge count
STATUS: REJECTED · SOURCE: review synthesis; D-096
REASON: the framework produces no valid independent p-values per rung; family freeze and forward holdout instead.

---

## Project 3 — customer discovery candidates (D-102)

No code before discovery. Each entry is a problem family and a buyer hypothesis, not a
product.

### I-201 — Post-alert crypto compliance / investigation workflow
STATUS: CUSTOMER_DISCOVERY · SOURCE: review synthesis, 2026-09-16
BUYER: small VASP; crypto platform; fintech compliance team; prediction-market operator. · JOB: alert → evidence gathering → transaction reconstruction → case notes → decision / escalation → closure evidence. · WHY INTERESTING: a repeated, regulated, documented job with a budget line. · MAIN RISK: incumbents; the buyer's real workflow is UNKNOWN until asked. · PROMOTION CONDITION: G8.

### I-202 — Settlement / integrity tooling for prediction-market operators
STATUS: CUSTOMER_DISCOVERY · REUSE: I-005, I-006, I-011. · PROMOTION CONDITION: G8.

### I-203 — Cross-venue TCA / execution-quality analysis
STATUS: CUSTOMER_DISCOVERY · REUSE: the execution layer of `EXPOSURE_ENGINE.md`. · PROMOTION CONDITION: G8.

### I-204 — Collateral / settlement optimisation
STATUS: CUSTOMER_DISCOVERY · PROMOTION CONDITION: G8.

### I-205 — Stablecoin reserve / compliance workflow
STATUS: CUSTOMER_DISCOVERY · PROMOTION CONDITION: G8.

### I-206 — Builder attribution / economics tooling
STATUS: CUSTOMER_DISCOVERY · same as I-012, seen as a Project 3 candidate. · PROMOTION CONDITION: G8.
