# Divergence — review package

**For:** independent reviewers (including other AI systems)
**Repository:** `github.com/DenizErginGunduz/divergence`
**State reviewed:** `main` as of 2026-09-16, after the four-week correctness sprint (decision records D-073 … D-090)
**Findings file:** `findings/latest.json`, computed over 61 snapshots / 16 days, last snapshot `2026-09-15T1317Z`

This document is self-contained. You do not need to open the repository to review it, though every number below names the script that produced it.

---

## 0. What we are asking you

Five questions, in the order we care about them. Sections 1–8 exist to let you answer them.

1. **Is the method wrong anywhere?** Section 2 and 3. We have repaired a discount-convention bug, a fee model, an inference-vs-execution confusion and an expiry-matching error in the last four weeks. We expect there is more.
2. **Is the result a result?** Section 4 and 5. Three persistent price gaps worth $4.69; two die to a 165-hour expiry mismatch; the survivor clears by about 0.4 cents against an unmeasured grid uncertainty on the same chain. Is this a finding about market structure, or a story told over noise?
3. **Should we change the question?** Section 7. We have three candidate directions. One of them — comparing the *cost of expressing a view* across futures, options and prediction markets — may be a better question than the one we started with.
4. **Which directions raise both portfolio value and commercial potential?** Section 7 again. This is an explicit constraint, not an afterthought: the project must remain a credible piece of research work *and* have a plausible path to being useful to somebody who would pay for it.
5. **Did we over-correct on presentation?** Section 8. Six things were removed for being methodologically loose. Several of them were what made the work legible. Were we right?

Please be specific and adversarial. "Looks solid" is not useful to us. If a number in this document is wrong, or a claim does not follow from the evidence given, say which one.

---

## 1. What the project is, and is not

Divergence compares the probabilities implied by prediction markets (Kalshi, Polymarket) against the probabilities implied by listed derivatives (Deribit options, futures) on the same underlying and, as far as possible, the same event.

It is **not** a betting product, a trading bot, or a signal service. It is a research terminal and a written record.

**Terminology discipline.** The project does not use the phrases "true probability", "correct probability", or "AI probability". It uses: prediction-market-implied probability, options-implied risk-neutral probability, cross-market probability gap, terminal probability, touch probability, settlement comparability.

**A probability gap is not automatically an arbitrage.** A gap can be produced by collateral cost, commission, spread, variance risk premium, a difference in resolution source, or model error. The project's job is to separate these, not to assume the residual is free money.

**Asset universe:** BTC and ETH are measured. Gold, silver, WTI, S&P 500 and Nasdaq-100 were inventoried in Phase 0 and are collected but not measured.

**Working rules that constrain everything below:**

1. Nothing is invented. An endpoint, a price, a rule text or a platform's coverage is either measured or written `UNKNOWN`.
2. Raw data is stored as it arrives. (Two deliberate exceptions, D-087 and D-088, both recorded — third-party profile fields in the Polymarket trade and holder streams.)
3. Settlement rules are quoted verbatim, never summarised.
4. Uncertainty is surfaced, not resolved.
5. Scope is not widened silently; new ideas go to `docs/BACKLOG.md`.
6. Every number that reaches a screen could affect somebody's financial decision. Where we are not sure, we emit a warning rather than a number.

---

## 2. The method

### 2.1 The option side is a discounted state price, not a probability

A digital payoff is recovered from a vertical spread on the listed chain:

```
D · Q(S_T > K)  ≈  −∂C/∂K  ≈  [C(K₁) − C(K₂)] / (K₂ − K₁)
```

This is **model-free**: no volatility model, no distributional assumption. What comes out is a *discounted state price* under the risk-neutral measure — the price today of a dollar paid on that event — not a probability. Dividing by `D` gives `Q`, which is a risk-neutral probability and still not a real-world one.

**D-073 (the bug this fixed).** The call side returned `D·Q(S>K)`. The put side returned `1 − D·Q(S<K)`, which equals `(1−D) + D·Q(S>K)`. The two sides were on different conventions and the difference was `(1−D)` — small, systematic, and invisible to the check that should have caught it: the exhaustiveness constraint summed buckets and compared to 1, and `D·1 + (1−D) = 1` for *any* D. The check was structurally blind to the error it existed to catch.

### 2.2 Where D comes from

`D` is recovered from the put-call parity residual rather than assumed:

```
residual = put_side − call_side = 1 − D
```

Measured, the residual is flat in strike — slope `2.9e-6` — which is what it must be if the conversion is producing a present value at all. The implied rate is 3.2–5.5%. Current mean discount factor in the findings: `0.988121`.

Forward, with the discount carried:

```
F = K + (C − P) / D
```

`forward()` previously assumed `D = 1`. Fixed in the same sprint.

### 2.3 The comparison is a trade, not a statistic

**What was removed (D-076).** The old test was `|mid − mid| > 1.96·SE + fees`. The standard-error term described how uncertain *our estimate of the option mid* was — a question about our arithmetic, not about whether anything could be executed. It is gone.

**What replaced it.** An executable envelope built from the sides you would actually hit:

```
opt_high = dL.high − dH.low
opt_low  = dL.low  − dH.high
```

(The put branch inverts: buying the put spread gives the LOW digital.)

Then a two-trade test:

```
sell_pm = bid − (opt_high + fee)
buy_pm  = (opt_low − fee) − ask
edge    = max(sell_pm, buy_pm)
```

**No mid price appears anywhere in the verdict.** On a thin ladder the mid is a number nobody trades at.

### 2.4 Fees, from the published schedules

**Kalshi:** `fee = roundup(0.07 × C × P × (1−P))`, taker only, rounded up to the cent **per order**, not per contract. No settlement fee. Index series (S&P, Nasdaq) use `0.035`.

**Polymarket:** `fee = C × rate × p × (1−p)`, with `rate: 0.07` for crypto, `takerOnly: true`, `exponent: 1`, `rebateRate: 0.2`. The schedule is read **per market from the archived payload**, not hardcoded; if the exponent is ever anything but 1, the script returns `None` rather than guessing.

Mean venue fee actually charged in the Polymarket measurement: `0.00646`.

### 2.5 Exhaustiveness, as a constraint rather than a number

Buying every bucket of an exhaustive ladder buys one dollar at expiry with certainty, so the ladder must be worth **D**, not 1. This is arithmetic, so a departure says the computation is wrong without saying which bucket is wrong.

Measured across 110 ladder-snapshots, as a ratio to D (target `1.0000`):

| boundary rule | mean | min | max | departure |
|---|---|---|---|---|
| corrected | 0.9977 | 0.9945 | 1.0000 | −0.2% |
| naive A | 0.9977 | 0.9945 | 1.0000 | −0.2% |
| naive B | 1.1292 | 1.0843 | 1.1914 | **+12.9%** |

Two of the three boundary rules are indistinguishable; the third is not. The constraint is what caught D-073, not any individual price.

### 2.6 Touch is not terminal

`P(max S_t ≥ K)` over the life of a contract is always ≥ `P(S_T > K)` at the same level. Conflating them breaks every comparison systematically and in one direction. Contract classification into `terminal` / `touch` / `range` / `relative` / `other` is the single most delicate part of the pipeline; touch ladders are excluded from the terminal comparison explicitly (1,035 excluded in the Polymarket run).

### 2.7 Do the two contracts even pay on the same event?

`scripts/audit_semantics.py` parses Kalshi's `rules_primary` text with a deliberately rigid regex and checks three separate things: (a) the numbers in the rule against `strike_type` / `floor_strike` / `cap_strike`; (b) whether the rules *tile* the outcome line with no gap — adjacent buckets must be exactly one tick apart, and settlement values are quoted to two decimals, verified as 1,892 of 1,892 numeric `expiration_value` entries; (c) an inventory of settlement wording, printed verbatim with no pass/fail.

A rule that does not parse is `UNKNOWN`, not "probably fine". A mismatch exits non-zero.

**What the inventory shows, and it is not small:** Kalshi settles on a **60-second average of CF Benchmarks' BRTI before a stated instant**. Deribit settles on **its own index at 08:00 UTC**. Different reference rate, different averaging window, different instant — three independent reasons two prices can differ with neither being wrong.

We measured one of the three. See 4.4.

---

## 3. What the correctness sprint changed

The sprint runs from D-073 to D-090. The records that changed a number:

| # | what it was | what it is |
|---|---|---|
| D-073 | put and call sides on different discount conventions | both sides return `D·Q(S>K)`; the exhaustiveness target is D |
| D-074 | `forward()` assumed `D = 1` | D carried through parity |
| D-075 | settlement-source difference logged as UNKNOWN | measured (see 4.4) |
| D-076 | `1.96·SE` band around two mids | executable envelope from the sides you hit |
| D-077 | no venue fees, or one venue's | both schedules, quoted verbatim, per-order rounding |
| D-078 | `price_level_structure` misread as settlement granularity | it is the contract price tick; settlement granularity measured separately |
| D-079 | one expiry per comparison | both bracketing expiries, and the verdict must survive each |
| D-085 | Polymarket side on the old conventions | same standard as Kalshi: 24.2% → 10.3% |
| D-086 | `p` used for a discounted state price | renamed `dsp` across 7 files / 35 call sites |
| D-087/088 | third-party profile fields archived publicly | dropped; the only two deliberate exceptions to rule 2 |
| D-089 | archive window open (14 vs 90 days) | 14, because measurement reads the private mirror anyway |
| D-090 | README numbers hand-copied and stale | rebuilt from `findings/latest.json` and checked in CI |

**Errors we found in our own work, recorded because a project that reports no mistakes is not reporting carefully:** a sum-to-1 check blind to the bug it was for; a stability classifier whose "always" meant ">90%" while two surfaces printed "in every one of N"; a neighbour-selection regression that silently destroyed the expiry band by picking two expiries on the same side of the close; a test pipeline that exited green on a failing suite because `tee` ate the status.

Test suite: 59 cases, each pinned to the decision record whose mistake it prevents.

---

## 4. Results

All figures from `findings/latest.json` unless stated. Sync window between reading the option chain and reading the prediction market: **0.66–2.04 seconds**, recorded per snapshot. A measured difference smaller than what the price can move inside that window is timing noise, not a market view.

### 4.1 Kalshi year-end ladders — the headline

- **165 of 2,418** quotable rung-observations show an edge at quoted prices after both venues' fees: **6.8%**
- Mean executable envelope width: **0.0615**
- Mean ladder density: **0.9859** (of D)
- **44 distinct rungs**, 55 observations each
- **3 always exceed** (classifier threshold >90%; the weakest is 54 of 55), 1 sometimes, 40 never
- Worth **$4.69 in total** at the resting size

The three are all tails: **BTC above $150k**, **ETH above $5k**, **ETH below $1k**. Nothing in the body of any distribution shows an edge.

### 4.2 The expiry band, which takes two of the three away

The Kalshi year-end contracts close at a stated instant; the nearest Deribit expiries sit **−165 hours** and **+2,019 hours** from it (median gap 165 hours, and the nearest available one falls *before* the close, which flatters us by understating an upside tail).

Tested against **both** bracketing expiries, **only 1 of the 3** clears the option value at either end. The surviving rung is **ETH above $5k**, and it survives by about **0.4 cents**.

Sensitivity of a digital to the strike grid it is differenced across, on the year-end chain: **median 11.5%**, p90 18.3%, worst 23.9%. The margin that decides the one surviving result is of the same order as an uncertainty we have not measured on the chain that decides it.

That is the central weakness of this project's headline number, and we would rather you attack it than we defend it.

### 4.3 Polymarket daily terminal ladders

- **470 of 4,561** quotable rung-observations: **10.3%** (was 24.2% before the same repairs reached this script — more than half of the original figure was method, D-085)
- Restricted to comparisons with an expiry gap ≤ 12 hours: **253 of 3,038 = 8.3%**
- Mean envelope 0.0462; skipped: 1,464 outside the strike range, 1,395 with no two-sided option quote; 1,035 touch ladders excluded
- 390 distinct rungs, 11.7 observations each: 3 always, 173 sometimes, 214 never

**The intraday problem.** On the intraday chains, **67.4%** of rungs are *flat* — the strike grid is coarse enough that neighbouring rungs return the same digital value. The ladder is finer than the chain that is supposed to price it. Grid sensitivity intraday: median 5.2% but p90 **29.9%** and worst **53.3%**.

### 4.4 Settlement basis — a null result, and a useful one

Kalshi settles on BRTI, Deribit on its own index. Measured directly from both archived streams using microsecond timestamps, 63 paired readings:

| bin | n | median | spread |
|---|---|---|---|
| within 60 s | 25 | **−0.20 bp** | 1.54 bp |
| within 180 s | 47 | −0.48 bp | 3.81 bp |
| within 450 s | 63 | −0.62 bp | 4.92 bp |

BTC median −1.08 bp, ETH median −0.04 bp.

**The index difference is not the explanation.** At well under a basis point it cannot account for gaps of several cents. One of the three settlement differences named in 2.7 is now measured and ruled out; the averaging window and the instant are not.

### 4.5 The touch bound — model-dependent, and we say so

The only measurement here that assumes a model. 1,397 observations, 55 distinct rungs.

- **5 arithmetic violations (0.4%)** — touch priced below terminal at the same level, which is impossible
- **93%** sit above the driftless reflection bound of 2× terminal

The 0.4% is a **pipeline validation, not a finding**: if the digital calculation were wrong, impossible values would appear in the hundreds, not in five. The 93% does not show mispricing; it shows the driftless reflection bound is the wrong tool for long-dated deep-OTM strikes. An earlier version of this script compared against a lognormal terminal and reported 8.7% "violations" which were the model's error, not the market's.

---

## 5. What cannot be said yet

Nothing above is a statement about whether either market *forecasts* well. That needs outcomes paired with the prices that preceded them.

Over 16 days: **4,851** Kalshi markets resolved; **145** of them had ever been seen with a live quote; those 145 collapse to **109 independent events** (every rung of one ladder resolves from one reading of one price); and **100 of those 109 are fifteen-minute markets quoted a median of fourteen minutes before settlement**, which measures how fast a price converges to an outcome already in view.

**Nine informative independent events.** That is the honest size of the validation sample. No scoring should be run on it, and none has been.

Lead time from quote to close: median 6.87 hours, p25 0.23, max 718. Outcomes seen: 90 no, 55 yes.

The sample grows by roughly two informative independent events a day, from 2026-09-15, when a collector defect that was hiding the daily ladders entirely was fixed.

**Things that would strengthen the work by waiting rather than building:** December, when Deribit lists weeklies that straddle 1 January and the 165-hour band closes on its own; and a middle tenor — a weekly prediction ladder against a Deribit weekly, which could have both a small expiry gap and strikes fine enough to resolve it. Whether such a ladder exists is currently `UNKNOWN`.

**Switching venue would not help.** Deribit is roughly 85% of crypto-native BTC options volume and over 90% of ETH; OKX and Bybit settle at 08:00 UTC as well. The clock is a property of crypto options, not of Deribit.

---

## 6. Known weaknesses, stated before you find them

1. **The surviving result is thin.** 0.4 cents against an 11.5% median grid uncertainty on the deciding chain. We have not measured that uncertainty *for that specific rung*.
2. **The validation sample is nine events.** Every forecast-quality claim is therefore unavailable.
3. **Kalshi's API Developer Agreement is unread** — the domain blocks automated access. The data-rights position rests on website terms that may not be the governing document.
4. **The public archive is a 14-day window while findings are computed over the full private mirror.** An outside reader can reproduce the findings only "in the small". This is a recorded, accepted cost (D-089), not an oversight.
5. **149 of 460 flow markets hit the fetch limit** in the latest run with no gap flagged. Probably fine; not verified.
6. **Five assets are collected and not measured.**
7. **Prose in `docs/` carries numbers that nothing verifies.** Eight claims in the README are machine-checked against the findings file as of D-090. The rest rests on periodic audits.

---

## 7. Directions we are considering — and the question we most want answered

The constraint: a direction should raise **both** the credibility of the research **and** the chance that the output is worth something to somebody. Please rank these, add what we have missed, and say plainly if one is a waste of time.

### 7.1 Cost of expressing a view: futures vs options vs prediction markets

**This is the one we think might be better than the question we started with.**

The concrete case that produced it: suppose you want to be short oil, building into the position as price rises. On a perpetual future the funding fee is a recurring carry cost that can consume most of the return over a multi-week horizon. On an option you pay theta. On a prediction contract you pay once for a fixed payoff and carry essentially nothing — your capital is locked, but nothing bleeds.

So the comparison is not "which venue is mispriced" but **"for a given directional view over a given horizon, what is the all-in cost of expressing it in each instrument?"** — funding, theta, spread, fees, collateral drag, and the payoff shape you end up with (linear vs convex vs binary).

Why this may be the better question:
- It does not require the two venues to price the *same event*, which is the constraint that has cost us most of the sprint.
- It produces something a person can act on without it being a signal service — a cost table, not a recommendation.
- It naturally extends past crypto, since funding-versus-binary is a general problem.
- The infrastructure is already three quarters built: the collector already reads Deribit and both prediction venues; perps/futures funding is an addition, not a rewrite.

What we do not know: whether the comparison is *interesting* once computed, or whether it just reproduces the textbook answer that binaries are cheap carry and expensive convexity.

### 7.2 Expanding beyond crypto — index, commodity, equity

Phase 0 inventoried seven assets. The blocker has been option-chain access: CME data is licensed, and the free routes (yfinance for `^SPX` / `^NDX`) have not been proven to work from a data-centre IP — a Colab attempt failed 5 of 5, and the workflow that tests this from GitHub Actions exists but has no recorded result (now logged as B-017).

Portfolio and commercial case: crypto-only reads as a crypto project. Index and commodity coverage reads as a markets project, and the audience that pays for research is larger there.

Cost: a second data source with its own licensing question, and the whole event-comparability problem again on contracts we have not read.

### 7.3 Venue selection as the product

Rather than "is there an edge", ask "given that you want this exposure, which venue should you use *right now*, after fees, spread and settlement differences?" This is a smaller claim, is defensible on nine events, and is closer to what a user actually decides.

### 7.4 Waiting

December closes the expiry band without any work. Accumulation grows the validation sample without any work. There is a real argument that the correct next move is to build nothing for six weeks and let the two weakest parts of the project strengthen themselves.

---

## 8. The presentation question

Six things were removed from the interface during the correctness sprint for being methodologically loose. They are kept recoverable on purpose in `docs/BACKLOG.md` (B-011 … B-016):

| | what it was | why it went |
|---|---|---|
| B-011 | the "×band" grammar | implied a statistical multiple that was not being computed |
| B-012 | the statistical framing (1.96·SE) | measured our arithmetic, not an executable trade |
| B-013 | the word "probability" on screen for the option side | it is a discounted state price |
| B-014 | a headline that summed to 1 | an exhaustive ladder is worth D, not 1 |
| B-015 | the single headline percentage | hid a stability distribution behind one number |
| B-016 | a "methodology under revision" banner | never actually added |

Each removal was correct in isolation. Together they removed most of what made the work quickly legible to somebody who is not going to read a 116 KB decision log.

**The question:** is there an honest version of any of these? A headline that is both true and graspable in five seconds? Or is the legibility cost simply the price of the accuracy, and the right move is to accept a smaller audience?

We are not asking for permission to overclaim. We are asking whether accuracy and legibility are actually in conflict here, or whether we mistook one for the other.

---

## 9. How to verify anything in this document

- `findings/latest.json`, `findings/sensitivity.json`, `findings/settlement_basis.json`, `findings/validation_inventory.json` — every number above
- `docs/METHODOLOGY.md` — the method in full
- `docs/DECISIONS.md` — the decision log, D-001 … D-090, including every retraction (numbers that carried no reasoning of their own were removed rather than renumbered, so there are gaps)
- `docs/ARCHIVE_SCHEMA.md` — what is stored and in what shape
- `docs/DATA_SOURCES.md` — the three venues' terms, quoted, and what we concluded
- `scripts/` — eleven measurement steps, standard library only, no dependencies
- `tests/test_measurement.py` — 59 cases, each naming the decision record it defends
- CI: `tests`, `ref-check` (dangling decision references, and the README against the findings file), `collect` (three times daily), `measure` (manual, reads the full mirror)

---

## 10. The five questions again

1. Where is the method still wrong?
2. Is the surviving result a finding or noise? (0.4 cents against an 11.5% median grid uncertainty; nine informative validation events.)
3. Is the cost-of-expression question (7.1) better than the mispricing question we started with?
4. Which direction raises research credibility *and* commercial potential together — and what have we not thought of?
5. Is there an honest, legible headline, or is that a contradiction here?
