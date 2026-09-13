# METHODOLOGY.md

Updated 2026-08-30. The previous version of this document was wrong in three
places; the corrections and their reasons are below and in `DECISIONS.md`.

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

**Step 2 — put the option side into probability.**
A call price is not a probability. The terminal probability comes out of the
digital approximation:

    P(S_T > K) ≈ −∂C/∂K ≈ [C(K₁) − C(K₂)] / (K₂ − K₁)

This is not a model, it is a numerical approximation of a derivative. **It is the
primary method** (D-027).

**Step 3 — match the contract type.** Not skippable; see section 2.

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

**The upper bound "2" is NOT a constant (D-031).** That number comes from
driftless arithmetic Brownian motion. Price is lognormal; even when the forward is
a martingale, the log-price drifts at −σ²/2. The full formula gives every rung its
own upper bound (measured range 1.94–2.07). Using the constant produced a bound
that was too loose on the upside and too tight on the downside.

---

## 3. What the gap is measured against — not zero, its own history

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

---

## 7. Still open

- Layer 4 (Breeden–Litzenberger) is not built; the data is ready.
- Reference accumulation started 2026-08-30 but is not yet long enough to produce
  a statistic.
- `data-api` `offset` support is unverified — no gap has occurred, so it has never
  been triggered (D-042).
- The 5 August measurement is stale: BTC has moved 19.9% since, and that day's put
  chain cannot be recovered. The measurement has to be redone from scratch on
  simultaneous data (D-037).
