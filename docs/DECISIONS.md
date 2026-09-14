# DECISIONS — Phase 0

This file records the decisions made while producing the inventory that affected
the result. None of them was made silently; each one sits here with its reason and
each one can be reversed.

## D-001 — Data source: the Gamma API, from the schema rather than from memory
Endpoints and field names were confirmed against the official OpenAPI schema at
`https://docs.polymarket.com/api-reference/markets/list-markets`. Endpoints used:
`GET /markets`, `GET /events`, `GET /tags/slug/{slug}`. No key required.

## D-002 — Network restriction (an implementation detail that affects methodology)
The sandbox I run code in has an allowlisted network; `polymarket.com` domains
cannot be reached directly with `curl` or Python. Every call went through the
permitted fetch tool, which has a limit of about 82 KB per response. Consequence:
every page was kept small and **whether the response closed as complete JSON was
verified programmatically every time**; on truncated pages only fully parseable
objects were taken, and pages were fetched with overlapping offsets of 10 so that
no gap could open. The `fetches` section of `raw/_store.json` records how many
objects each call returned and whether it was complete.

## D-003 — Expired markets are excluded
Filter: `closed=false` **and** `end_date_min = today`.
Reason: Polymarket carries records that are `closed=false` while their expiry passed
months ago (example: December 2025 five-minute "Up or Down" markets, with zero
volume and zero liquidity). They carry no live price and inflate the inventory.
**Risk:** this filter can miss a market expiring today. Accepted for Phase 0.

## D-004 — Classification comes only from the rule text
`contract_type` is derived from the `description` field, not from the title. If the
title and the rule text disagree, both are recorded and `ambiguity_flags` is set. No
disagreement was found in this scan. Unrecognised rule text was **not forced into
a class**; it was left as `other`.

## D-005 — The scope column: no row was deleted
Markets that relate to the seven assets but carry no price or level threshold
(e.g. "US national Bitcoin reserve", "NYSE circuit breaker", "Venezuelan crude
output") were not dropped from the inventory; they were marked
`scope = OUT_OF_SCOPE_non_price_or_unresolved`.
Reason: no loss of count — the call is yours.

## D-006 — Records with no event group get a synthetic ladder label
Some markets came back from the API without an `events` object. For those a
`ladder_group` of the form `SYNTHETIC::asset|expiry|type|direction` was derived and
the rows flagged with `ambiguity_flags`. **This is an assumption**, not a grouping
that came from the API.

## D-007 — Two BTC ladders were injected by hand
`bitcoin-above-on-august-6-2026` (11 rungs) and `bitcoin-price-on-august-6-2026`
(11 buckets) did not come back from the tag query; they were fetched separately
with `GET /events?slug=...` and written into the store with the values from the API
response. Nothing was invented, but the `conditionId` field of these two groups
reads `"see_raw"` — if the full identity is needed they have to be re-fetched.
**Also:** the two groups have different snapshot times (`above` 17:11 UTC, `price`
06:19 UTC). They must be re-fetched simultaneously before being compared.

## D-008 — Price fields
`yes_bid` / `yes_ask` are Gamma's `bestBid` / `bestAsk`; `yes_mid` is their average.
On a one-sided book, with no counterparty, `UNKNOWN` was written rather than
assuming zero. `snapshot_timestamp_utc` gives the moment of the fetch,
`market_updated_at` gives the last time Gamma updated the record. They are kept
separate because some markets have not been updated for hours.

## D-009 — The product's purpose was widened (user-approved, 2026-08-05)
The "not a signal service" rule in the project brief still holds, but the product
will no longer only show the gap — it will also show **where that gap sits in its
own history**. So not "gap 8%", but "gap 8%, typical 6%, 1.2 sigma above usual".

Why it is needed: the options-implied probability carries a variance risk premium.
Showing the raw gap against zero pushes the user in the same structural direction
every time, and that direction is not an opportunity.

The limit: it will never be reduced to a single green or red score. Four things
stand separately on screen — the prediction price, the derivative counterpart, the
gap, and the typical level of the gap. Reducing them crosses the line.

The cost: no indicator can be produced until the reference has accumulated. The
first weeks only collect data.

## D-010 — Short tenors are not in the product, they are in the calibration
Daily and weekly ladders are out of product scope (user's decision) but they are
**used to validate the engine**. That is how the layer 1 test was done without any
external data. Use for calibration does not count as scope expansion.

## D-011 — Gold: CME GC chosen, XAUUSD on hold
Volume and liquidity point to the GC future (total 1,158,013 vs 184,006; liquidity
400,962 vs 55,869). The 24-hour volume points the other way (80,784 vs 12,539) but
that comes from expiry proximity (XAUUSD 27 days, GC 148 days). Second reason: GC
is the only underlying directly comparable with a derivative listed on CME.
Reversible.

## D-012 — SPY does not count as the SPX index
The Polymarket market is written on the SPY ETF (rule text: Pyth, regular session,
split-adjusted). A SPY option goes opposite it, not an index option. That way no
dividend or scale adjustment is needed. `asset=SPX` remains, but the
`underlying_reference` field reads "ETF: SPY (NOT THE S&P 500 INDEX)" and the
contradiction is flagged.

## D-013 — CBOE will not be used programmatically
CBOE explicitly forbids automated collection of its delayed quote tables and
states that it blocks IPs. It will not go into the pipeline. Looking by hand is
fine.

## D-014 — ATH contracts on hold
The threshold of the oil ATH contract is written out verbatim in the rule text
($147.27), so it can be treated as an ordinary touch at the 147.27 level. User's
decision: hold for now.

## D-015 — The measured gap is hypersensitive to timing (2026-08-05, with evidence)
There are **8 minutes** between two Deribit snapshots (21:14 and 21:22). The
Polymarket side did not change at all (frozen at 17:11). Even so the measured gap:

| | mean \|gap\| | largest |
|---|---|---|
| Deribit 21:14 | 0.0094 | 0.0424 |
| Deribit 21:22 | 0.0063 | 0.0264 |

The BTC index moved 64,728 → 64,665 (−64 USD) in those 8 minutes and the measured
gap **shrank by 33%**. So most of what we were seeing as a "gap" was not a market
view, it was timing.

**Rule:** no number is shown in this table unless the simultaneity window is on the
order of minutes. Both sides' snapshot times and the difference between them are
required fields on screen.

## D-016 — On Gamma, the query path changes the freshness of the data
For the same market, `/events?slug=...` and `/events?tag_slug=...&end_date_min=...`
returned different `updatedAt` values and different prices (the 62,000–64,000
bucket: 0.13/0.14 @20:50 on the direct query, 0.23/0.24 @17:14 on the tagged one).
Probably a cache layer.

**Consequence:** in production, markets are fetched **directly by slug or id**; the
tagged list query is used for discovery only. The pipeline should not be written
before this is confirmed.

## D-017 — The `bitcoin-above-on-august-6-2026` ladder is stale
All three query paths returned `updatedAt = 17:11:01`. So the ladder has not been
updated for 4+ hours. Either move to a more liquid ladder for the comparison, or,
if the measurement is not going to be made on this one, show it with a "stale"
label. This is the concrete reason the "last updated" field on screen is required.

## D-018 — Layer 3 is NOT blocked: I am correcting my earlier assessment
I had said "there is no touch + terminal pair at the same expiry, so layer 3 cannot
be measured". That was wrong. The terminal side **does not have to come from
Polymarket** — it can come from the option chain. The relation used is not an
assumption, it is true by definition:
`P(touching K before expiry) ≥ P(closing beyond K at expiry)`.

**Measurement (2026-08-05, monthly BTC touch ladder, 20 rungs):**
20 of 20 rungs inside the theoretical [1, 2] band. No hard violation. The ratio
peaks near the money (1.93–1.97) and falls toward 1.0 in the wings — exactly the
shape the reflection principle predicts, and it came out of the data rather than
being imposed.

This is also **independent evidence that my touch/terminal classification is
right**: had I mixed up the labels, the ratios would have come out meaningless.

## D-019 — A long horizon is robust to the simultaneity problem
On a daily ladder an 8-minute drift moved the measurement by 33% (D-015).
On a monthly ladder, despite a drift of **4.4 hours**, 20 of 20 rungs stayed in the
band. The reason: the ratio is a relative quantity and four hours is negligible
over a 26-day horizon.

**Consequence:** prioritising the medium and long tenor is not only a product
preference, it is a **measurement-robustness argument**. Short tenors do not work
without simultaneity infrastructure; the medium tenor works today.

## D-020 — A duplicated market record was found
"Will Bitcoin dip to $62,500 in August?" appears three times; two at mid=0.9995
(impossible with BTC at 64,639), one at 0.695. The inventory de-duplicates on the
(threshold, direction) key, keeps the highest-volume record and reports the others.
This step is mandatory in the pipeline — skip it and that rung of the ladder comes
out broken.

## D-021 — Equity ladders are unmeasurable because of LIQUIDITY (2026-08-06)
Yesterday I said equities were the easy side. That was an incomplete assessment: I
had looked only at **data access**, not at **liquidity**. Measured:

| Asset | Rungs | Median spread | Measurable rungs |
|---|---|---|---|
| BTC | 22 | 0.002 | **20** |
| SPY | 14 | 0.024 | 2 |
| NVDA | 14 | 0.074 | **0** |
| META | 14 | 0.090 | 1 |
| TSLA | 14 | 0.099 | 1 |

Measurable = spread ≤ 0.02 **and** mid < 0.99.
Reason for the threshold: the gaps we measured on BTC were in the 0.006–0.026
range. If the spread is wider than that, the number produced is the spread itself,
not a market view.

**Consequence:** there is no point fetching an equity option chain right now. The
bottleneck is not on the option side, it is on the Polymarket side. Task #11
(yfinance/Finnhub) is **suspended**.

**Equities are not dropped from the product:** they appear in the list with a
"spread too wide — not measurable" label instead of a number. This is the first
real application of the METHODOLOGY rule: do not produce a number you are unsure
of, produce a warning.

## D-022 — Resolved-market detection: the user's hypothesis was confirmed
The hypothesis in D-020 was confirmed across five assets at once. The 13 rungs with
mid ≥ 0.99:
- SPY ↑740 ↑750 ↑760 ↑770 · META ↓560 ↓580 ↑600 · NVDA ↓200 ↑208 ↑216
- TSLA ↑315 · BTC ↓62,500 (two duplicated records)

All consistent: on NVDA both ↓200 and ↑216 are full, so it travelled inside that
band during August. The `closed` flag never came back, but the market is finished
in practice. The rule lives in `ladder_health.py` and filters automatically on every
run.

## D-023 — A monotonicity check was added to the pipeline
Within the same ladder, touch probability **must** fall as the threshold moves
further away. This needs no model. One violation on TSLA: `↓240 = 0.020` but
`↓225 = 0.105`. That rung has zero volume and a spread of 0.190 — not a real
arbitrage, just an untraded wide quote. A free and effective broken-quote detector.
In `ladder_health.py`.

## D-024 — Fair value band design (user's idea, adopted)
Instead of making the Polymarket mid an input to the measurement, **anchor on the
option and publish a fair price band to the prediction side.** What an illiquid
market needs is a reference price anyway.

The refinement I added: on a wide spread, compare against **bid and ask separately,
not the mid**. The mid is an imaginary number nobody trades at.
- `ask < band_low` → buyable
- `bid > band_high` → sellable
- otherwise → the band sits inside the spread, there is nothing to say

Where the band comes from: the terminal probability from options, and the
touch/terminal ratio in [1, 2]. No model is invented; the ratio band was confirmed
20 of 20 on BTC yesterday.

## D-025 — THE FIRST MEASUREMENT IS INVALID: the deep ITM call IV trap
On its first run `fair_band_equity.py` marked 11 of 34 rungs "tradable".
**Nine were spurious.** The cause: for downside rungs I used the implied volatility
of deep ITM calls.

A deep ITM call's price is almost entirely intrinsic value; the IV comes out of the
crumb that is left:

| SPY strike | mid | intrinsic | time value | share | IV |
|---|---|---|---|---|---|
| 670 | 101.83 | 98.93 | 2.90 | **2.8%** | 0.4034 |
| 700 | 72.32 | 68.93 | 3.39 | 4.7% | 0.3168 |
| 730 | 43.17 | 38.93 | 4.24 | 9.8% | 0.2234 |
| 770 (ATM) | 10.47 | 0 | 10.47 | 100% | 0.1347 |

The result **flips completely** depending on which IV is chosen. SPY ↓670, PM ask
0.029:

| IV assumption | terminal | band | where 0.029 falls |
|---|---|---|---|
| deep ITM call (0.4034) | 0.1063 | 0.106–0.213 | BUYABLE |
| reasonable skew (0.26) | 0.0238 | 0.024–0.048 | inside the band |
| reasonable skew (0.22) | 0.0093 | 0.009–0.019 | EXPENSIVE |
| ATM (0.1347) | 0.0001 | ~0 | VERY EXPENSIVE |

**Rule:** no IV is derived from an option whose time value is under 20% of its
price.

**Correction:** PUTS will be fetched for the downside. A deep OTM put's price is
100% time value. Better still, the digital approximation can be built directly
from puts (`P(S_T<K) ≈ ∂P/∂K`) — that uses no IV at all and carries no model.

**What survives:** TSLA ↑345 and ↑375 (OTM calls, IV trustworthy). The gap at ↑345
is 0.003 — inside rounding, meaningless. The gap at ↑375 is 0.031 — the only
serious candidate, but because the upper bound (2×) is a soft limit this is a
**flag, not evidence**.

## D-026 — yfinance works (part of D-021 corrected)
From Colab, the `yfinance` library succeeded on 5 of 5 symbols and returned real
bids and asks. Direct HTTP is blocked but the library works. Equity option chains
are **reachable**. The liquidity problem (D-021) is separate and still stands — but
the D-024 design supersedes it.

## D-027 — Naive N(d2) is WRONG when skew is present; the model-free digital becomes primary
After correcting D-025 (OTM calls upside, OTM puts downside) two independent
methods disagreed on 17 of 32 rungs. I looked into why: the error is not in the
data, it is in **my analytical method**.

The naive method computes `N(d2)` with each strike's own IV. But a call price is
`C(K, σ(K))` and the correct derivative is:

    dC/dK = (∂C/∂K)|σ fixed  +  vega · (∂σ/∂K)

The second term is large when skew is present. The slope measured on the SPY put
curve is `∂σ/∂K = −0.0015` (IV rises as K falls). Dropping that term:

| strike | naive N(−d2) | model-free digital | ratio |
|---|---|---|---|
| 670 | 0.0193 | 0.0091 | **2.12×** |
| 700 | 0.0428 | 0.0229 | 1.87× |
| 720 | 0.0804 | 0.0488 | 1.65× |

The naive method **inflates** the left tail systematically — in exactly the
direction being measured.

**Decision:** the model-free digital is the **primary** method. The analytical
method is used only to correct an expiry mismatch, and only **with the skew
correction term added**. No comparison is made before that correction.

Note: the BTC/ETH measurements (`bridge_btc.py`, `touch_premium_btc.py`) used the same
naive method. On Deribit the skew is flatter near the money so the effect is
smaller, but it is **not zero**. Those two scripts have to be re-run with the skew
term.

## D-028 — The disagreement check is a permanent part of the product
If two independent methods disagree, **no number is produced**. This check caught
all nine of the spurious signals in D-025 and additionally exposed the
methodological error above. It lives in `fair_band_v2.py`, with a threshold of 35%.

**The v2 result:** 32 rungs, 17 rejected for disagreement, 14 "band inside the
spread", and **1 outside the band**: TSLA ↑375, PM bid 0.200, model-free band top
0.141. Volume 2,189 USD. This is still a **flag**, not evidence — the upper bound
(2×) assumes zero drift.

## D-029 — The measured effect of the skew correction on BTC (2026-08-28)
`skew_correction_btc.py` computed the same ladder three ways, using the model-free
digital as the referee, to measure what D-027 costs on the BTC side:

| Chain | naive N(d2) deviation | with skew |
|---|---|---|
| monthly 28AUG26 | mean **54.8%**, max **334%** | mean **1.9%**, max 9.3% |
| daily 6AUG26 | mean 10.5% | mean 10.3% |

On the monthly chain the correction is decisive. On the daily it makes almost no
difference — 0.4 days to expiry, vega ≈ 0, so the skew term has nothing to
multiply. The residual 10.5% on the daily comes not from skew but from **wing data
quality** (the 66,000 and 67,000 marks are 12.49 and 0.58; effectively tick
quotes).

**Consequence:** the skew term is mandatory at medium and long tenors and
negligible at short ones. This is the second independent reason for our medium-tenor
priority (D-019).

## D-030 — The "20/20 in the band" result in D-018 is WITHDRAWN
Yesterday's result was computed with a naive denominator. Re-run with the
model-free denominator (`touch_premium_v2.py`): **6 of 19 rungs in the [1,2] band**,
13 above 2.

**But the CORE claim of D-018 stands:** the hard lower bound (ratio ≥ 1) holds
19 of 19, and since the correction made the ratios larger it is now safer. So the
evidence that the touch/terminal classification is right is intact. What broke was
the "comfortably inside the band" framing. Two separate claims; they have to be
kept separate.

## D-031 — "2" is not a constant; replaced with the full lognormal bound
The upper bound of 2 is derived for **driftless arithmetic** Brownian motion. Price
is lognormal, and even when the forward is a martingale the log-price drifts at
−σ²/2. The full formula (`touch_bound_lognormal.py`) gives every rung **its own**
upper bound; the measured range is 1.94–2.07.

Using the constant produced a bound that was too loose on the upside and too tight
on the downside. The pipeline uses the full formula instead of the constant.

## D-032 — D-025 REPEATED ITSELF: the downside terminal comes from deep ITM calls
The Deribit monthly file we had **contains calls only**. Computing the downside
terminal as `1 − P(S>K)` makes the source a deep ITM call. Time value as a share of
price:

| Threshold | 42,500 | 45,000 | 47,500 | 50,000 | 52,500 | 55,000 | 57,500 | 60,000 | 62,500 |
|---|---|---|---|---|---|---|---|---|---|
| time value / price | 0.8% | 0.9% | 1.1% | 1.5% | 2.1% | 3.4% | 6.3% | 14.0% | 37.8% |

On the first six rungs, 99% of the price is intrinsic. Taking a derivative there
means reading a small difference off the difference of two large numbers. **Exactly
the same trap as D-025.**

**Rule (permanent):** a PUT chain is required for the downside. With no puts, no
downside number is produced. Threshold: time value share < 5% → `NOT MEASURABLE`.
The automatic detector lives in `touch_bound_lognormal.py` and flags on every run.

**To do:** fetch the Deribit put chain (same endpoint — `kind=option` already returns
puts; yesterday's pull filtered them out).

## D-033 — A tick-resolution floor will be added
On the `up 100,000` rung the PM price is 0.0025, the terminal 0.0004, the ratio
6.42. Both numbers are on the order of the quote tick; the ratio is rounding noise,
not a market view. This is the small-price counterpart of the spread rule (D-021):
**if the PM price is less than a few ticks, no ratio is produced.**

## D-034 — Product decisions (user-approved, 2026-08-28)
- **Audience:** the priority is a personal research tool; the site also carries
  portfolio and brand value. There is no contradiction — to a reader who knows
  derivatives, a tool that goes quiet when it cannot measure looks **more**
  competent than one that invents a number. Silence will not be hidden, it will be
  designed well.
- **Collector:** GitHub Actions. Free cron, reaches Deribit and Polymarket, commits
  snapshots to the repository. A public repository also makes the methodology
  visible.
- **Band:** a wide model-free band. Transferred calibration will not be used for
  now.
- **V1 scope:** BTC and ETH measured; equities and commodities appear in the list
  carrying a reasoned "not measurable" label instead of a number.
- **Screen architecture:** the four-screen structure from the GPT suggestion
  (Overview / Event detail / Scanner / Research) is taken as a shell; the engine and
  the measurement discipline stay ours.
- **The archive moved from V2 to V1.** The time series, the "typical gap" reference
  and the Brier score all depend on the archive; if it does not start today it never
  starts.
- **Lead/lag analysis deferred to V3.** It needs minute resolution; an 8-minute
  drift moved a measurement by 33% (D-015).

## D-035 — D-032 is no longer a diagnosis, it is a MEASUREMENT (2026-08-28)
We now hold both the call and the put chain for the same expiry. The same quantity
was computed two ways; by put-call parity they **must be the same number**, so any
divergence is error, directly.

| time value share | 86% | 35% | 12% | 4.8% | 1.2% | 0.4% |
|---|---|---|---|---|---|---|
| call route / put route | 1.01 | 1.01 | 1.02 | 1.04 | 1.28 | **2.09** |

The error is a **monotone** function of the time value share. In the sound region
it is 1.01–1.03; in deep ITM it blows up to 2.09. The 5% threshold was confirmed
from the data, not invented.

**The rule is settled:** a PUT chain is required for the downside. With no puts, no
number.

## D-036 — LAYER 2 came for free: the forward from put-call parity
`F = K + C − P` gives a forward estimate at every strike. Across 21 strikes on the
25SEP26 chain the dispersion is **113.75 USD (0.146%)** — the chain is internally
consistent. Median F = 77,704.64, index 77,478.56, basis **+0.292%** (about +3.9%
annualised carry).

**Consequence:** there is no need to fetch futures data; the option chain carries
the forward inside itself. One data dependency disappeared. Layer 2 verified.

## D-037 — OUR MEASUREMENT BASE IS STALE; there is no going back
Between the 5 August snapshot and today, BTC went
**64,638.85 → 77,478.56 (+19.9%)**. The 28AUG26 expiry also expired today and fell
off the list.

**The critical consequence:** Deribit's `get_book_summary` returns the CURRENT state
only. The 5 August put chain **cannot be recovered.** So the D-032 correction
cannot be applied to the old measurement; the measurement has to be redone from
scratch on **simultaneous** data.

This is the hardest justification for the archive decision (D-034): a day we miss
is permanently lost. The collector is not a side task, it is a PRECONDITION for
correct measurement.

## D-038 — Flow / whale data is LIVE-VERIFIED, terminology fixed
`data-api.polymarket.com` works without a key:
- `/trades` → `proxyWallet, size, price, side, outcome, timestamp, transactionHash,
  conditionId, pseudonym, name, bio` — flow per wallet, per trade. **200 OK**
- `/holders?market=<conditionId>` → position holders. **200 OK**
- `clob/prices-history` → **200 but empty** (`{"history": []}`). Parameters need
  another try; if it works, Polymarket history arrives ready-made and we do not
  wait months for accumulation.
- `clob/book` 404, `clob/trades` 401 (wants credentials) — neither is needed.

**Terminology (permanent, same discipline as D-034):**
Not used: "insider", "insider wallet", "smart money", "whale signal".
Used: **large trade**, **concentrated position**, **historical settlement record**,
**wallet flow**. We do not name what we cannot claim.

## D-039 — The flow layer goes at the TOP of the list, the pricing thesis goes DEEP
I am reversing my earlier advice. The pricing number is absent on most rows (7 of
14 on TSLA); flow data is present on every market. So:
- **list layer** = flow (always full, changes every day)
- **depth layer** = the pricing thesis (surfaces where it has been earned)

They are also a cross-check on each other: if the model says "expensive against
derivatives" while a large address is buying that side, that address disagrees with
the derivatives. Agreement strengthens the observation; disagreement raises a
research question.

**Note:** the liquidity gate applies to flow too. On a 10.7k USD ladder a "large
trade" is 500 USD; the threshold has to scale with volume rather than being fixed.

## D-040 — Collector v2: event-based storage (2026-08-30)
v1 re-stored the last 100 trades of every market on every run; almost the whole
file was a copy. v2 changed three things, and all three were done now because they
are expensive to add later:

1. **De-duplication by `transactionHash` plus a watermark.** However fast we poll, we
   write to the same store. When a live watcher is added later, the format will not
   have to change.
2. **A coverage record.** Every fetch writes down "this is the range over which I
   saw this market". Without it, "no trades" and "we were not looking" cannot be
   told apart — and in an alerting product that distinction is everything.
3. **A gap flag plus pagination.** If the watermark cannot be reached, `GAP` is set.

**Measured gain:** the trade file per run went **24.9 MB → 94 KB**. gzip on top:
Deribit 816→69 KB (11.8×), ladders 3,251→350 KB (9.3×). Run time 4m05 → 2m36.
Price window 1.28 s.

## D-041 — My scope mistake, and the fix
The first v2 run fetched **770 markets**. v1 had a `[:120]` limit; I removed it
without thinking while writing v2. That was a violation of project rule 5 (scope is
not widened silently) and I reported it as soon as I noticed.

The fix: markets carrying a price threshold (`\$\s?\d[\d.,]{2,}`) are filtered.
Result: **524 ladder markets, 248 out of scope.**

**An important limit:** this is a COLLECTION filter, not a classification. Contract
type (terminal / touch / range) is still determined only from the rule text.

## D-042 — The pagination question is still OPEN, and that is the right behaviour
We could not verify `offset` support on `data-api`: an hour passed between the two
runs, so no market had a gap (`WITH_GAP: 0`) and pagination was therefore never
triggered (`pagination_tried: 0`).

That is not a shortfall: the mechanism is in place and it did not run
unnecessarily. The answer will arrive by itself when a gap appears on the busiest
market during the scheduled 8-hourly runs, and it will be written into
`pagination_worked`.

## D-043 — The repository is live, but only the pipeline is uploaded
`github.com/DenizErginGunduz/divergence` — public, three successful runs.
Uploaded: `.github/`, `collector/`, `raw/`, `state/`.
**Missing: `README.md`, `docs/`, `scripts/`, `.gitignore`.**
On the first upload attempt the files arrived flat and were never committed. The
portfolio value lives in the README and the docs, so this gap has to be closed.

## D-069 — The strip became a grid; full width survives only in the dateline
**Date:** 2026-09-10

We had built the screen with horizontal strips running to the edge of the screen.
The user's decision: it read worse. Reverted, but not completely:

- **The dateline rule** stays full width. A rule costs nothing in readability.
- **The findings strip** went back to a grid (4 columns → 2 on a narrow screen →
  1). No scrolling. Six findings dropped to four; the two removed are in
  `BACKLOG.md` B-010.
- **Notable** stayed a slider but inside the 1200px content width. The arrows sit
  in the gutter beside the content, not at the edge of the screen.

### Two measured defects

**1. `scrollLeft` reads stale during a smooth scroll.**
On a long strip an arrow click could not see the "I am at the end" state and the
wrap to the start was missed. The target is kept in a separate variable and
refreshed from the real position 140ms after scrolling stops. Measured: on a
2702px strip the position one second after a click still read 489; waiting for the
animation to finish gave 2702.

**2. A viewport change may fire no notification at all.**
When `--vw` (usable width excluding the scrollbar) went stale, the dateline strip was
drawn at the wrong width — in a mobile test the labels sat at x=24 and the cards at
x=32. It was then measured that `resize`, ResizeObserver on `html` **and** on `body`,
and `visualViewport.resize` — all four stayed silent while clientWidth fell from
1385 to 885. No single notification mechanism can be relied on.

The fix: all four listeners are kept and a 500ms safety pass was added on top; if
the value has not changed, the style is never touched. The pure-CSS alternative
(`100vw` + `overflow-x:clip`) was tried and **rejected**: 100vw counts the scrollbar,
so the dateline content shifts by half a scrollbar — bringing back exactly the bug
we were fixing.

## D-070 — The page was cut loose from the GitHub contents API
**Date:** 2026-09-10

The site was showing "archive unavailable" to visitors. I first blamed my own
verification requests; that was an incomplete diagnosis. Measured:

The page found the newest snapshot by **listing directories**, because
`raw.githubusercontent.com` cannot list a directory. The cost:

| call | count |
|---|---|
| `newestPath('raw/kalshi')` | 2 |
| `newestPath('raw/deribit')` | 2 |
| `raw/_meta` + day list | 2 |
| **NO. counter: one listing per archive day** | **as many as there are days** |

On a 12-day archive that is **~18 calls per page load**. GitHub's unauthenticated
limit is 60 an hour → **about 3 page opens per visitor**. Worse: because the counter
added one call per day, **the cost grew every day**. This was not a quota accident,
it was a design defect.

### The decision
The collector writes `state/latest.json` on every run: the newest file path for each
of the three streams, the sync window, the snapshot time, and the archive counters
(day count, total snapshots, per-day distribution — all counted from disk). The page
reads that one file.

**Measured:** 18 calls → **0**. The page makes 3 raw requests (the pointer plus
kalshi.gz plus deribit.gz). The dateline is correct:
`NO. 038 · 2026-09-10 13:12Z · SYNC 0.85s · ARCHIVE 12d`.
`raw.githubusercontent.com` has no such limit; only a ~5 minute CDN cache, and the
collector runs three times a day (05:00 / 13:00 / 21:00 UTC, eight hours apart) —
so it is fine.

**Correction (2026-09-11):** when this record was first written the run interval was
stated as "3 hours"; that was assumed, not measured. The real interval is 8 hours.
Caught during an audit and corrected — the record is subject to measurement too.

The old API path **remains as a fallback**: if the pointer is missing or its version
is unrecognised, the page falls back to the old behaviour. So it also works before
the collector has run.

The first version of `state/latest.json` was produced by hand (so that D-070 could
take effect without waiting for the next run); everything after that is overwritten
by the collector. The collector also writes into the `errors` list if the kalshi or
deribit path fails to appear in the pointer — so it never produces a silently
incomplete pointer.

### Why it matters
This defect was exactly the kind that damages the portfolio value: whoever opened
the site saw an empty screen rather than measurement rigour. And it was getting
worse on its own.

---

# Re-measured records

Everything below was re-derived from the raw archive; each record carries the
script that produced it and which snapshots it ran on.


## D-045 — Polymarket short-dated terminal ladders measured
**Date:** 2026-09-11 · **Produced by:** `scripts/measure_polymarket.py` · 40 snapshots / 13 days

Polymarket's daily "X above ___ on [date]" ladders were compared against Deribit
digitals. In raw form the result looks strong:

| measurement | value |
|---|---|
| rung-observations clearing the band | 1030 / 3795 (**27.1%**) |
| those with an expiry gap ≤ 12 hours | 787 / 2711 (**29.0%**) |
| touch ladders excluded | 677 |

The ratio does **not** fall when the expiry gap narrows. So the gap is not what
drives this result — the suspicion was measured and rejected.

**But the stability breakdown undoes the table:** of 316 distinct rungs, **247 are
"sometimes exceeding"**. Only 16 rungs clear the band in every observation. So most
of the 27.1% is noise, not structure. Because the daily ladders are replaced every
day there are about 12 observations per rung, which weakens any stability judgement
further.

**Conclusion:** this setup supports the thesis, but far more weakly than the raw
ratio implies.

### Caveat
Polymarket settles at 16:00 UTC on the Binance BTC/USDT close, Deribit at 08:00 UTC
on its own index. Both the time and the settlement source differ.


## D-046 — The long-horizon touch bound measured; the test came out weak
**Date:** 2026-09-11 · **Produced by:** `scripts/measure_touch.py` · 40 snapshots

Polymarket's "What price will X hit in 2026?" touch ladders were compared against
the **model-free** terminal digital from options.

| measurement | value |
|---|---|
| total measurements | 1812 |
| arithmetic violations (ratio < 1) | 3 (**0.2%**) |
| ratio > 2 | 1720 (**94.9%**) |
| distinct thresholds / always exceeding | 89 / 65 |

**0.2% violations is good news.** Touch probability cannot be smaller than
terminal; had our pipeline been broken, hundreds of impossible values would have
appeared here. This is an independent validation of the measurement chain.

**94.9%, though, does not support the thesis — it shows the bound is the wrong
bound.** The coefficient "2" comes from driftless arithmetic Brownian motion and is
loose at long-dated deep OTM thresholds. D-031 said "2 is not a constant"; the
measurement confirms that and at the same time leaves the test useless.

**Conclusion:** this setup is **weak evidence** for the thesis and strong validation
for the pipeline.

### The error that was corrected
The first version took the terminal from a lognormal model and labelled the result
an "arithmetic violation"; that was wrong. Lognormal is a model, and a contradiction
with it refutes the model. With a model terminal the violation rate came out at
8.7% — entirely the model's own error. Switching to the model-free digital dropped
it to 0.2%.


## D-049 — The friction band: how many rungs clear the cost of trading
**Date:** 2026-09-11 · **Produced by:** `scripts/measure_band.py` · 40 snapshots / 13 days

threshold = 1.96·SE + friction. Friction has three parts: the Deribit option fee
(0.03% of the underlying, capped at 12.5% of the option price, for both legs), half
the prediction spread, and the measurement uncertainty coming from the digital's
two legs. The Polymarket maker fee is treated as 0.

On the Kalshi year-end buckets:

| measurement | value |
|---|---|
| rung-observations clearing the band | 105 / 1496 (**7.0%**) |
| distinct rungs | 44 (34 observations per rung) |
| **always exceeding** | **3** |
| sometimes exceeding | 3 |
| never exceeding | 38 |

The three that always exceed, at 34 of 34 observations: `BTC > $150k`, `ETH > $5k`,
`ETH > $1k`. All three are **tails**. Nothing in the body clears the band.

**This is a stronger finding than the raw ratio suggests.** 7.0% looks small, but
almost all of it is structural: the same three rungs, on every run, without
exception.

### The old "0/44" record is withdrawn
The screen said "0/44 survives costs". Nothing in the repository produced that
number and it could not be reproduced (audit, 2026-09-11). This measurement
replaced it.

### Clearing the band does not mean tradable
Margin cost, the expiry gap and the difference in settlement source are not in this
computation.


## D-066 — Kalshi year-end buckets give a terminal measurement at a long horizon
**Date:** 2026-09-11 · **Produced by:** `scripts/measure_band.py`

At long horizons Polymarket only asked touch, and touch cannot be extracted from
options model-free (D-046). Kalshi's `KXBTCY` / `KXETHY` year-end bucket ladders
remove that constraint: they ask terminal directly, so they can be compared
model-free.

Across 40 snapshots, 44 distinct rungs were measurable without a break. The
exhaustiveness check holds on every run (mean density sum **0.9979**).

**Why it matters:** this is the project's only model-free long-horizon measurement.
Its results are in D-049.

### Caveat
Kalshi settles on CF Benchmarks BRTI, Deribit on its own index. Also, the nearest
option expiry that does not run past the Kalshi close is chosen; the remaining gap
can bias the result in our favour.


## D-067 — The bucket boundary error, and the constraint that caught it
**Date:** 2026-09-11 · **Produced by:** `scripts/measure_exhaustive.py` · 68 ladder-moments

If a bucket ladder partitions the whole outcome space, the probabilities must sum
to 1. That is arithmetic, not a preference. Three boundary rules were compared on
the same data:

| rule | mean total | departure from 1 |
|---|---|---|
| `round(cap + 0.01)` (in use today) | 0.9979 | −0.2% |
| `round(cap)` (no epsilon) | 0.9979 | −0.2% |
| `round(cap) + 0.01` (epsilon outside) | 1.1271 | **+12.7%** |

Range: 1.0835 – 1.1839.

**The measurement says something sharper than the record did.** The bug was not
"the epsilon was forgotten". Having no epsilon at all is harmless; the bug is the
epsilon sitting **outside the rounding**. `round(24999.99)+0.01 = 25000.01` does not
coincide with the next bucket's floor of `25000`, the digital picks different strike
pairs under strict inequality, and one region gets counted twice.

**The real lesson:** each digital looked flawless on its own. The error was caught
by a **constraint**, not by a number. Most of the errors caught in this project were
caught that way.


## D-071 — The archive becomes a rolling window, and what that does not buy
**Date:** 2026-09-14 · **Built:** `scripts/prune_archive.py` · `collect.yml`

`raw/` now keeps 14 days. The first prune removed 2026-08-30: eight day folders,
15.5 MB, including two orphan streams (`polymarket_flow`, `polymarket_holders`) left
behind by a collector version that no longer exists.

**The ordering is the whole safety mechanism.** Pruning runs only after the
private mirror has been pushed successfully. The subtlety that makes this
non-obvious: the mirror step exits 0 when it is SKIPPED for a missing token, so
"the previous step passed" is not evidence the mirror was updated. The step now
writes `MIRROR_OK=1` only on the real push path, and the prune step is gated on
that variable. Skipped mirror, skipped prune. Without this the archive could
leave both places in the same run.

### What the window does not do
Deleting a file in a new commit does not remove it from git history. The blob
stays, so `.git` keeps growing at the same rate and a full `git clone` still
downloads every snapshot ever committed.

So both arguments for the window are weaker than they first look:
- **Size.** It bounds the working tree, not the repository.
- **Data rights.** It bounds what a visitor browses or a shallow clone fetches,
  not what a determined full clone reaches.

Bounding the repository itself would take periodic history rewriting, or never
committing raw vendor data to the public repo at all. Neither is done. This is
recorded rather than smoothed over because the earlier version of
`DATA_SOURCES.md` claimed the window "caps repository growth", and that claim was
wrong in a way nobody would have caught by reading it.

### A bug the first run exposed
The collector computes the archive counters from disk during the snapshot step,
which happens BEFORE pruning. After the first prune the repository held 14 days
while `state/latest.json` still said 15, and the page's dateline read `ARCHIVE 15d`
with no files behind the number. `prune_archive.py` now recomputes that block after
deleting. Measured before the fix: day_count 15, actual 14.

### Cost
The measured sample is capped at about 42 snapshots. The long series that D-009
needs — where today's gap sits in its own history — cannot come from the public
repository any more; it has to be read from the mirror. That is a real
restriction on the reference metric and it is not solved here.
