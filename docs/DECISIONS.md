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


## D-072 — The findings strip reads the record, and two overclaims it was hiding
**Date:** 2026-09-14 · **Produced by:** `scripts/write_findings.py` · `web/index.html`

DESIGN.md 5.0 says the strip's contents are "always computed, never hand-written"
and that a hand-written sentence turns it into a slogan board. Three of the four
cards were hand-written anyway. They have now been wired to
`findings/latest.json`, and wiring them exposed two things.

### The drift that prompted it
The costs card read "in every one of 34 observations", dated 2026-09-11. The live
measurement said 45 observations per rung. The number on screen had come loose
from the measurement three days earlier and nothing noticed, because nothing was
checking. Same failure mode as the "0/44" withdrawn in D-049 — a figure with no
path back to a record.

### Overclaim 1: "always" does not mean always
`stability.py` classifies a rung as always-exceeding when its share is
`> always_above`, and `always_above` defaults to **0.9**, not 1.0. The card said
"in every one of N observations". Today that happens to be true — all three rungs
are 45 of 45 — but the code would have said the same about 41 of 45. The card now
states the rule: "in over 90% of their observations".

### Overclaim 2: "the rest never clears the band"
False whenever `sometimes_exceeds` is above zero, which it is: 3 always, 3
sometimes, 38 never. The card now reports all three buckets. That is also the more
informative statement, since the split between structure and noise is the whole
point of the stability module.

### What changed structurally
- `write_findings.py` now records the exhaustiveness constraint as well. The 12.7%
  on the fourth card had no entry in `findings/latest.json` at all, so it could not
  be verified from the record even in principle. It now reads
  `exhaustiveness_constraint.naive_b.departure_percent` and comes out at 12.7,
  matching D-067 exactly.
- Each measurement block carries `model_free: true/false`. The "2 model-free
  setups" card counts those flags instead of asserting a number.
- A card whose source is missing renders a dash and "measurement unavailable".
  A number nobody can reproduce is worse than no number.

### What is still hand-written, on purpose
The interpretive sentences, and the decision numbers each card cites. The rule is
not that prose is forbidden; it is that every FIGURE derives from a measurement
and every claim carries its source. The date on each card is now the archive's own
last stamp rather than a typed one, so a stale strip is visible as a stale date.

## D-073 — The put-call cross-check closes the numeraire question and dates the discount bug
**Date:** 2026-09-15 · **Produced by:** `scripts/measure_parity.py` · workflow `measure`

The external review raised a possibility that would have invalidated every number
this project has produced: that the Deribit inverse contract, whose premium is
quoted in the underlying, makes the converted chain a share-measure price rather
than a USD present value. If that were true, the finite difference
`[C(K1) - C(K2)] / (K2 - K1)` is not `D · Q(S_T > K)` under the risk-neutral
measure but a quantity contaminated by a strike-dependent Radon-Nikodym factor,
and no amount of side selection or friction banding repairs it.

Testing this does not require theory. A share-measure error is moneyness-dependent;
a discount factor is not. So: compute both sides of the digital on the same bracket
and look at whether their difference moves with the strike.

### Construction
For each consecutive pair of shared strikes `(a, b)` the script evaluates
`call_side = [C(a) - C(b)] / (b - a)` and `put_side = 1 - [P(b) - P(a)] / (b - a)`
and records the residual `put_side - call_side` at the bracket **midpoint**, so both
sides are read off identical intervals and the discretisation error is common to
them. Restricted to moneyness 0.70-1.40 and to expiries beyond 7 days, where the
chain is populated.

### Result
28 chains across 6 snapshots and both currencies, 19 to 46 brackets each:

- absolute slope of residual against log-moneyness: median 2.9e-6, worst 1.8e-4
- residual spread across all brackets in a chain: median 5.0e-5, worst 4.7e-3
- that spread as a share of the residual itself: median 4.7e-3

The residual is flat. Across up to 46 strikes spanning 0.70-1.40 moneyness it varies
by roughly half a percent of its own magnitude, and its regression slope against
log-moneyness is zero to six decimal places. There is no strike dependence to find.

### Two conclusions, one of them uncomfortable
**The numeraire concern is empirically dead.** Not argued away, measured. A share
measure would have produced exactly the signature this test was built to detect, and
it is absent at every maturity in both currencies. The existing measurements are not
contaminated in the way the review feared.

**The residual is the discount factor, which confirms the convention bug.** Since
`call_side = D·Q(S>K)` and `put_side = (1-D) + D·Q(S>K)`, the residual is `1-D`. It
grows monotonically with maturity, 1.1e-4 at 1 day and 2.7e-2 at 207 days, and the
implied continuously compounded rate is a coherent term structure with median
**4.24%** and range 3.24-5.50%. A plausible USD funding curve is the strongest
available evidence that the residual is what it claims to be.

It also means the two sides of the digital have never been on the same footing, and
that the sum-to-1 exhaustiveness check cannot see this: `D·1 + (1-D) = 1` for any
`D`. The check that was supposed to catch inconsistency is structurally blind to
this particular one.

### What this licenses, and what it does not
Licensed: Week 1 items 2 to 4. Unify the put side to return `D·Q(S>K)`, carry `D`
explicitly, rename the output to `discounted_state_price`, and correct `forward()`
to `F = K + (C - P)/D`.

Not licensed: calling the corrected quantity a probability. `D·Q(S>K)` is a
discounted state price under the risk-neutral measure. Dividing by `D` gives `Q`,
not `P`. The distance between `Q` and any real-world probability is the volatility
risk premium, and nothing in this test measures it.

### Caveat
Expiries under two days are excluded from the statistics above. Their residuals are
noisy, and the 0.1-day chain returns -1.1e-4, the wrong sign, because `1-D` there is
smaller than the tick. That is a resolution limit rather than a contradiction, but it
means the discount cannot be estimated per-chain at the front end and has to be
interpolated from longer maturities.

## D-074 — The discount repair, and how little it moved
**Date:** 2026-09-15 · **Produced by:** `scripts/measure_band.py` · `scripts/measure_exhaustive.py` · `scripts/measure_touch.py` · `scripts/write_findings.py` · `web/index.html`

D-073 established that the put side of the digital returned `(1-D) + D*Q(S>K)`
while the call side returned `D*Q(S>K)`. This is the repair and, more usefully,
the measurement of what the bug was actually costing.

### What changed
- `digital()` takes D and the put side returns `D - D*Q(S<K)`. With D=1 the new
  expression is identical to the old one, which is why the bug survived review.
- `forward()` divides by D: parity is `C - P = D*(F - K)`, not `C - P = F - K`.
- `discount()` is new. It reads D off the residual, needs no forward, and refuses
  to answer on fewer than 8 brackets or outside 0.5 < D <= 1.
- The unbounded lower edge of a ladder is priced at D rather than 1. That single
  literal was what pinned the exhaustive sum at 1 for any D.
- The exhaustiveness check reports total/D. `web/index.html` got the same repair, so
  screen and record still agree (the standing rule from D-072).

### What it did to the numbers
| | before | after |
|---|---|---|
| exhaustive ladder sum, corrected rule | 0.9978 | 0.9978 as a ratio to D |
| naive_b departure | +12.7% | +12.9% |
| rung-observations clearing the band | 145 / 2068 | 145 / 2068 |
| stability: always / sometimes / never | 3 / 3 / 38 | 3 / 3 / 38 |

**No conclusion changed.** Not one rung moved across the friction band, and the
three that always clear it are the same three. Normalised by D, the corrected
boundary rule sits exactly where it sat before.

### Why the footprint was that small
Worth stating plainly, because "we found a systematic error in every put-side
number" would have been the exciting version and it is not true. A rung is a
DIFFERENCE of two digitals. Where both edges sit on the same side of the
forward the (1-D) offset appears twice and cancels. Where the lower edge is
unbounded it cancelled against the literal 1. What is left is exactly one rung
per ladder — the bucket straddling the forward — overstated by 1-D, about 1.3
cents. That rung was nowhere near its threshold in any of the 47 snapshots, so
nothing flipped.

So the bug was real, systematic, and almost entirely self-cancelling. It is
worth fixing because the next computation built on `digital()` might not be a
difference, not because it was distorting today's answers.

### The check that now works
The exhaustive ladder sum used to be pinned at 1 by construction, so it could
only ever measure discretisation noise. It now has to land on an independently
estimated D, and it does:

- ETH, 25DEC26: D 0.98991, ladder sum 0.98991 — agreement to five decimals.
- BTC, 25DEC26: D 0.98704, ladder sum 0.98163 — a ratio of 0.9945.

The BTC gap is the discretisation error on a 28-rung ladder whose tails reach
below $20k, where the option chain is thin. That is now a visible, measurable
quantity instead of something the constraint was arithmetically unable to see.

### Two things found on the way, neither of them about discounting
**The page threw on first load.** `buckets()` already had a parameter named D — the
Deribit payload — so declaring the discount factor as D was a redeclaration.
Syntax-checking the file passed, because it is a syntax error only in context.
Running the page found it in one load. This is the D-072 lesson landing a
second time: for `web/index.html`, a parse is not a test.

**A failing test suite exited green.** `tests.yml` piped unittest through `tee`, and
bash reports the status of the last command in a pipeline, so the only thing
standing between a red suite and a green tick was the test-count floor. Fixed
with `set -o pipefail`. The floor was also raised from 15 to the actual count,
33, because a floor far below the real number hides the deletion of everything
above it.

### Still open
The internal key is still `p` and the ladder row key is still `opt`. The
docstrings, the findings note and the page now all say "discounted state
price", but the identifiers have not been renamed, so the naming half of the
Week 1 item is done in prose and not in code. Recorded here rather than
claimed as finished.

## D-075 — The rules say what the fields say, and the real gap is somewhere else
**Date:** 2026-09-15 · **Produced by:** `scripts/audit_semantics.py` · workflow `measure`

Until now the event being priced came from three numeric fields — strike_type,
floor_strike, cap_strike — and Kalshi's own resolution text had never been read
by anything except a person. Rule 3 of this project says the wording of a
resolution rule is methodologically load-bearing and must be quoted rather than
summarised, so leaving it unparsed was a standing gap. It is now parsed.

### 1. The numbers agree, in all of them
2,070 rung-observations across 90 ladders and 45 snapshots:

- AGREE 2,070 (100.0%)
- MISMATCH 0
- UNKNOWN 0

A null result, and worth having. The parser is deliberately rigid — one exact
sentence shape, every variable part captured — so it would have reported
UNKNOWN rather than guessed if Kalshi had changed a single word. It did not
have to. The `less` / `greater` / `between` fields and the below / above / between
wording line up on every rung, and the thresholds match to the cent.

### 2. The ladders tile, so D-067 was a statement about contracts
No gaps, no overlaps. Adjacent buckets end at .99 and begin at .00, exactly one
tick apart.

**CORRECTED 2026-09-15 (D-078).** The first version of this paragraph justified
the claim with `price_level_structure`, saying it reports `deci_cent`. That field
is the CONTRACT PRICE tick, and says nothing about the settlement value. The
conclusion survives but the reason had to be replaced by a measurement: all
1,892 numeric `expiration_value` entries in the archive carry exactly two
decimals, so the 0.01 between adjacent buckets is not a reachable settlement
value. See D-078.

This matters more than it looks. The exhaustiveness constraint has been the
single most productive check in this project, and it rested on the assumption
that the ladder partitions the line. That assumption was never verified against
the contracts themselves, only against our own arithmetic. It holds. The
boundary rule `round(cap + 0.01)` is now justified by the rules, not only by the
fact that it makes the sum come out.

### 3. What actually settles these contracts, verbatim
Two distinct wordings in the entire archive:

> "If the simple average of the sixty seconds of CF Benchmarks' BRTI before
> 12 AM EST is above 149999.99 at 12 AM EST on Jan 1, 2027, then the market
> resolves to Yes."

and the same sentence with `CF Benchmarks' ETHUSD_RTI` for the ETH ladder.
1,260 BTC instances, 810 ETH.

So the Kalshi side is: **CF Benchmarks BRTI (or ETHUSD_RTI), a sixty-second
average, at 00:00 EST on 1 January 2027.** The option side is a different
reference rate, a different averaging convention and a different instant. Three
separate reasons for the two prices to differ with neither being wrong, and
none of them is inside the friction band.

### How large each one is
- **Instant.** 00:00 EST on 1 Jan 2027 is 05:00 UTC. The Deribit expiry the
  band uses is 25DEC26, which settles 08:00 UTC on 25 December. The gap is
  **6 days 21 hours** — about 7% of the remaining life of a 100-day contract.
  This is the material one. The page already shows it; nothing prices it.
- **Averaging window.** Sixty seconds against a horizon of roughly 100 days.
  The variance reduction from averaging one minute of a process with this much
  annual volatility is far below the tick. Negligible, and said here so it does
  not have to be re-argued.
- **Reference rate.** BRTI against the Deribit index: different constituent
  venues, different methodology. Size UNKNOWN. This one is measurable from data
  already in the archive — finalized Kalshi markets carry `expiration_value`,
  which is the realised BRTI, and Deribit index snapshots sit beside them — but
  it has not been measured, so it stays UNKNOWN rather than being called small.

### What this does not license
Nothing here says the two contracts are comparable. It says the two contracts
are what their fields claim, and it names the three ways they differ with a
number attached to two of them. The expiry gap in particular is a real economic
difference that the current friction band treats as zero.

### A bug found on the way
The first version crashed on 2026-08-31T0508Z. `snapshot()` succeeds even when a
stream is absent; `Missing` is raised when the stream is READ. The try block was
around `snapshot()` and not around `g.kalshi`. Two things follow: the archive
contains snapshots with no Kalshi file at all, which the audit now counts and
reports; and a lazily raised exception is not caught by a try around the thing
that looks like it does the work.

## D-076 — The band stops being a statistic and becomes a trade
**Date:** 2026-09-15 · **Produced by:** `scripts/measure_band.py` · `scripts/write_findings.py` · `web/index.html`

The friction band used to read
`|mid(prediction) - mid(option)| > 1.96*SE + fees + spread/2`. The 1.96*SE term
described how uncertain our ESTIMATE of the option mid was. That is a question
about our arithmetic, not about anything anyone can collect, and a rung could
clear it while no trade existed at any price on either venue.

### What replaced it
Two trades, each leg priced at a quote that is standing right now:

    sell the prediction at its BID, buy the bucket at its ASK side, pay the
    Deribit fees.  Anything left?
    buy the prediction at its ASK, sell the bucket at its BID side, pay the
    fees.  Anything left?

`edge = max(of the two)`, and a rung counts when `edge > 0`. The bucket's two
prices come from the option quotes directly: `opt_high = dL.high - dH.low` and
`opt_low = dL.low - dH.high`, because the bucket is long the lower digital and
short the upper one. No mid appears anywhere in the verdict.

The put branch inverts: the put spread is SUBTRACTED, so BUYING it (its ask
side) gives the LOW digital. Reversing that pair leaves every number plausible
— same sign, same magnitude, just inside out — so it is pinned by a test.

### What it did to the numbers
| | old rule | new rule |
|---|---|---|
| rungs with a verdict | 145 / 2068 | 136 / 1978 quotable |
| share | 7.0% | 6.9% |
| always / sometimes / never | 3 / 3 / 38 | 3 / 2 / 39 |

(The denominator moved because the archive window rolled from 47 snapshots to
45, and because rungs with a one-sided option quote are now excluded rather
than counted on the strength of a mid that nobody is showing. BTC: 26 of 28
rungs quotable. ETH: 18 of 18.)

### Why the count barely moved, which is worth knowing
It would be easy to describe this as a much harder test. It is not a much
harder test; it is a test that means something. With comparable spreads on the
four legs the two hurdles are almost the same size:

- new: `opt_high - opt` = half the envelope on each digital = `2s/w`
- old: `1.96 * SE` = `1.96 * sqrt(2) * (s*sqrt(2)/2) / w` = `1.96s/w`

Two percent apart. The prediction spread was charged at half from the mid
before and is charged at half from the mid now, so that part is identical too.
The change is in what the number refers to, not in how big it is. Anyone
reading this later should not claim the band was tightened.

### The three rungs that survive it, with their arithmetic
From the live page, 2026-09-15:

- **ETH above $5,000.** Prediction bid 3.00c. Bucket costs 1.31c to buy at its
  ask side, plus 0.37c of Deribit fees. Edge **1.32c**, by selling the
  prediction.
- **ETH below $1,000.** Bid 2.80c against 1.93c + 0.25c. Edge **0.62c**.
- **BTC above $150,000.** Bid 1.20c against 0.47c + 0.13c. Edge **0.60c**.

These are the same three rungs the old rule found, and they are the three
year-end tails. Their envelopes are narrow — BTC's bucket spans 0.12c to 0.47c
— because far out-of-the-money options are cheap in absolute terms even when
their relative spreads are wide.

### What is NOT in these numbers
Every one of them makes the edge smaller, and none is measured yet:

- **Kalshi's own fees.** UNKNOWN, not zero. An edge of 0.6c is small enough
  that a fee of a fraction of a cent decides it.
- **Margin on the option legs**, posted in crypto for three and a half months.
- **The expiry gap**, 6 days 21 hours (D-075), on a contract with about 100
  days to run.
- **BRTI against the Deribit index** (D-075), size UNKNOWN.

So `edge > 0` is a NECESSARY condition and nothing more. The page now says this
in the rung detail rather than leaving it to the reader.

### On the envelope width
The mean envelope across quotable rungs is 6.2c archive-wide, and 5.6c on the
current snapshot. That number is dominated by the mid-ladder buckets, where
the option legs are expensive and their spreads are wide in absolute terms. It
is not the right number to quote next to a tail edge of 0.6c, and it is
recorded here so nobody quotes it that way.

## D-077 — The prediction leg stops being free
**Date:** 2026-09-15 · **Produced by:** `scripts/fees.py` · `scripts/measure_band.py` · `web/index.html`

D-076 made the friction band a trade at quoted prices but charged only the
Deribit side. A trade with one free leg is not a trade. The Kalshi schedule
was read and implemented rather than estimated.

### Source, quoted
kalshi.com/docs/kalshi-fee-schedule.pdf, read 2026-09-15, the document dated
"Last updated and effective: July 1, 2025":

> "fees = round up(0.07 x C x P x (1-P))
>  P = the price of a contract in dollars (50 cents is 0.5)
>  C = the number of contracts being traded
>  round up = rounds to the next cent"

> "Trading fees are only charged for orders that are immediately matched with
>  orders sitting on the orderbook."

> "There is no settlement fee."

Three consequences, none of them a judgement call:

1. **Our trades are taker trades.** Both directions cross the spread on both
   venues, which is what makes them executable in the first place. The maker
   exemption does not apply, and neither does the 0.0175 maker rate — its
   series list is reproduced in `fees.py` and contains neither KXBTCY nor
   KXETHY.
2. **No settlement fee.** One unknown removed rather than bounded.
3. **The round-up is per ORDER.** One contract at 3 cents costs 0.2 cents in
   fee before rounding and a full cent after. So "is there an edge" has no
   answer until someone says at what size, and `fees.min_contracts()` now
   returns the smallest order at which the rounding stops eating it.

### The schedule tests itself
The PDF prints a worked table beside the formula — 21 price points, for one
contract and for a hundred. Those are the counterparty's own numbers, so
`tests/test_measurement.py` asserts against them rather than against anything
computed here. All 42 assertions pass, including the round-up cases where one
contract costs a cent at every price from 0.01 to 0.99.

### What it did to the measurement
| | before the Kalshi fee | after |
|---|---|---|
| rungs with a positive edge | 136 / 1978 | 134 / 1978 |
| always / sometimes / never | 3 / 2 / 39 | **3 / 0 / 41** |

The headline count barely moved. The STABILITY picture changed completely: the
marginal rungs are gone. Every rung that used to clear the band in some
snapshots and not others now fails in all of them, and what is left is binary
— three rungs clear it in essentially every observation, forty-one never do.
A fee of a fifth of a cent was the whole difference between "sometimes" and
"never" for two rungs, which says how thin those cases were.

### The three, with every cost named
From the live page, 2026-09-15, all in cents per contract:

| rung | pred. bid | bucket at ask | Deribit | Kalshi | gross | **net** | min size |
|---|---|---|---|---|---|---|---|
| ETH above $5,000 | 3.00 | 1.31 | 0.374 | 0.204 | 1.32 | **1.11** | 1 |
| BTC above $150,000 | 1.20 | 0.47 | 0.132 | 0.083 | 0.60 | **0.52** | 2 |
| ETH below $1,000 | 2.80 | 1.93 | 0.251 | 0.191 | 0.62 | **0.43** | 2 |

The minimum sizes are small because the gross edges are large relative to a
one-cent rounding. That was not obvious in advance: on a 1.2-cent contract a
one-cent minimum fee sounds fatal, and it would be at one contract. At two it
is already paid for.

### A note for the asset expansion
S&P 500 and Nasdaq-100 pay 0.035, half the general rate. The schedule
identifies them by RULEBOOK ticker — "whose Rulebook ticker begins with INX" —
and whether that string equals the API's series ticker is **UNKNOWN**.
Divergence prices neither asset yet. The coefficient and the open question are
both in `fees.py` so that the day it does, the general rate is not applied by
default.

### Still outside the number
- **Margin on the option legs**, posted in crypto for three and a half months.
- **The expiry gap**, 6 days 21 hours (D-075).
- **BRTI against the Deribit index** (D-075), size UNKNOWN.

An edge of 0.43 cents is not robust to any of these. `edge > 0` remains a
necessary condition.

### The tests earned their keep
Two older cases failed on the first run, and the size of each failure was
exactly the fee: 0.0175 on a 50-cent contract and 0.002037 on a 3-cent one.
Neither was a bug — they were assertions about a world in which the prediction
leg was free, and they broke the moment it stopped being. That is what a
regression test is supposed to do when the thing it pins is deliberately
changed.

## D-078 — What the edge is worth, and a field read wrong
**Date:** 2026-09-15 · **Produced by:** `scripts/measure_band.py` · `scripts/write_findings.py` · `web/index.html`

Week 2's last item was "read `price_level_structure` and `price_ranges`". Reading
them corrected an error in D-075 and, separately, produced the most deflating
number this project has yet measured.

### 1. The field I read wrong
D-075 justified the bucket-tiling claim by saying `price_level_structure` reports
`deci_cent`, and treating that as the granularity of the SETTLEMENT value. It is
not. It is the tick on the contract's own price. The two have nothing to do
with each other, and the mistake was mine, not the data's.

The conclusion happens to survive, but only because it can be measured
directly. Every finalized market in the archive carries `expiration_value`:

- 1,892 numeric entries, from KXBTC15M (946) and KXETH15M (946)
- **1,892 of 1,892 have exactly two decimals**
- a further 83 non-numeric entries ("No", "Yes") belong to series that settle
  on something other than a price, and 14 more are dollar-prefixed strings,
  also to the cent

So adjacent buckets ending at .99 and beginning at .00 really are touching.
D-075 is corrected in place with a pointer here rather than quietly edited.

### 2. What the field actually says
For the year-end ladders:

    price_level_structure: "deci_cent"
    price_ranges: [{start: 0.0000, end: 1.0000, step: 0.0010}]

One uniform tick of a tenth of a cent across the whole range. Not every Kalshi
market is like this — a multivariate market sampled the same day reports
`center_deci_edge_centi_cent` with three ranges, a finer 0.0001 tick below 0.01
and above 0.99 and 0.0010 in between. Our tails do NOT get the finer tick.
That is a fact about our markets that could only be learned by reading the
field.

`measure_band.on_grid()` now checks every quote against the published ranges.
Across the archive: **0 off-grid quotes**. The check earns its place anyway,
because the failure it guards against is a unit error, and a unit error is the
kind of thing that looks fine until it does not.

### 3. What `_fp` means, derived rather than assumed
`yes_bid_size_fp` and `yes_ask_size_fp` are quantities with two decimals, and
nothing in the payload says the unit. The archive settles it:

    yes_ask_dollars  = 0.0140,  yes_ask_size_fp = 698.86
    best NO bid      = 0.9860,  quantity        = 698.86

The ask on the YES side IS the bid on the NO side, and Kalshi reports the same
number for both. A dollar amount would not survive that flip — a no order at
0.986 commits 0.986 per contract while the same order shows as a yes offer
worth 0.014 — but a contract count does. **The unit is contracts**, fractional,
two decimals.

### 4. The number that matters
The edge now has a size behind it: how many contracts are resting at the quote
being hit, and therefore what the edge is worth in dollars.

Live, 2026-09-15:

| rung | net edge | resting | **worth** |
|---|---|---|---|
| ETH below $1,000 | 0.43c | 1,063.0 contracts | **$4.54** |
| ETH above $5,000 | 1.11c | 10.0 contracts | **$0.11** |
| BTC above $150,000 | 0.52c | 6.9 contracts | **$0.04** |

**$4.69 in total.** Across the whole archive, 134 rung-observations with a
positive edge: the median is worth **$0.63** and the largest seen in 45
snapshots is **$125.52**.

### What that means, stated plainly
The three persistent divergences are real as prices and negligible as money.
An edge of a cent on ten contracts is a price observation, not an opportunity,
and the distinction was invisible for as long as the pipeline reported only
cents per contract.

This does not retract anything. The rungs still clear a test built from quotes
that exist, and they have done so in essentially every snapshot for 45
consecutive observations, which is itself a fact worth having: a persistent,
reproducible price difference between two venues that nobody arbitrages away
because it is not worth the trouble. That is a finding about market structure.
It is not a trade.

It also reframes what remains unmeasured. Option margin, the 6d 21h expiry gap
and the BRTI basis were listed as reasons the edge might not survive. Against
$4.69 they no longer need to be measured to settle that question — they are
reasons to stop expecting a trade, not obstacles between here and one.

### Sum with care
`edge_value_total` reads $1,018.37 across the archive, and that number should
not be quoted. It sums the same three rungs over 45 snapshots of the same
standing orders. The median and the maximum are the honest summaries.

## D-079 — The expiry gap explains most of it
**Date:** 2026-09-15 · **Produced by:** `scripts/measure_sensitivity.py` · workflow `measure`

Two approximations have sat under every digital since the beginning and neither
had been measured: the strike grid the difference is taken across, and the fact
that no Deribit expiry falls on the Kalshi settlement date. Both are now
reported as a RANGE. A sensitivity test that returns a corrected point estimate
is not a sensitivity test.

### 1. The strike grid costs about 12%
The digital is recomputed on deliberately wider brackets — skipping one strike
each side, then two. Latest snapshot:

| rung | tight | skip 1 | skip 2 | spread |
|---|---|---|---|---|
| BTC above $150,000 | 0.00294 | 0.00282 | 0.00289 | 4.0% |
| ETH above $5,000 | 0.00932 | 0.00857 | 0.00814 | 12.6% |
| ETH below $1,000 | 0.01600 | — | — | — |

Across all observations the relative spread has a **median of 12.6%**, p90
18.8%, worst 23.9%. ETH below $1,000 has no wider bracket at all: the chain
runs out of strikes underneath it.

So roughly an eighth of every tail digital is a statement about how far apart
Deribit puts its strikes. That does not flip any sign and does not change an
order of magnitude, but it is not small either, and it is now a number rather
than an assumption.

### 2. The expiry band, and what it does to D-078
The Kalshi ladders settle 2027-01-01 05:00 UTC. Deribit's nearest expiries are
25DEC26 (seven days early) and 26MAR27 (84 days late). `measure_band` uses the
early one and has always admitted the bias. Here both are computed.

Latest snapshot:

| rung | pred bid | early (25DEC26) | late (26MAR27) | verdict |
|---|---|---|---|---|
| ETH above $5,000 | 3.00c | 0.93c | 2.59c | **above BOTH** |
| BTC above $150,000 | 1.20c | 0.29c | 1.21c | inside the band |
| ETH below $1,000 | 2.80c | 1.60c | 4.61c | inside the band |

Across all 135 rung-observations: **70 above both, 65 inside the band, 0 below
both.**

**Two of the three rungs from D-078 do not survive this.** BTC above $150,000
is quoted at 1.20 cents and the March chain implies 1.21 — the entire
difference is inside the seven-day gap, and it should not be reported as a
divergence. ETH below $1,000 is the same story with more room. Only ETH above
$5,000 clears both ends.

### What "inside the band" does and does not mean
It means the two contracts cannot be separated with a model-free comparison. It
does NOT mean the gap is explained, and the band is not symmetric: the early
chain misses the settlement date by 7 days and the late one by 84. The true
value sits roughly 8% of the way along, far nearer the early end, so a rung
sitting just under the late value is weaker evidence of "explained" than the
word band suggests. Saying more than this needs a model of how a tail
probability grows with maturity, and that model is exactly what D-025 refused.

### The test sharpens itself
Deribit lists weeklies about a month out. As 1 January 2027 approaches, expiries
will appear on both sides of the Kalshi close and the band will close on its own.
Nothing has to be built for that; the measurement simply gets stronger with time.
Re-running this in December is worth more than any modelling done today.

### A limitation this script does not cover
The grid sensitivity is computed on the EARLY chain only. For ETH above $5,000
the binding constraint is the LATE value, 2.59 cents against a 3.00-cent bid —
a margin of 0.41 cents, which is smaller than the 12.6% grid uncertainty would
be on that number (about 0.33 cents). The one rung that survives, survives by
about the width of an effect that has not been measured on the chain that
decides it. Stated here rather than resolved.

### Where this leaves the project
D-078 said the three divergences were real as prices and worth $4.69. D-079
says two of the three are not clearly divergences at all once the expiry gap is
admitted, and the third survives by a margin comparable to an unmeasured
uncertainty.

That is the fourth null result in two weeks, and it is the most consequential
one. It is also the correct output of a programme whose stated purpose was to
make the measurement defensible before making it larger.

### A bug found and fixed on the way
The first version of this script compared a 2.8-cent "ETH below $1,000" bid
against 0.97657 and reported "below both". The digital is always `D*Q(S > K)`; a
"below X" rung is worth `D` minus that. The number being compared was the chance
of ETH being ABOVE $1,000. Fixed, and the verdict now orders the two ends
rather than assuming early is the lower one — a "below X" rung loses value as
maturity grows while an "above X" rung gains it.

## D-080 — 88 pairs out of 4,657 resolutions, and the one-line reason
**Date:** 2026-09-15 · **Produced by:** `scripts/inventory_validation.py` · `collector/collect.py`

Before writing any scoring routine, count the sample. A Brier score over what
turns out to be a handful of draws is a decoration.

### The inventory
Over the 14-day public window, 46 snapshots:

| | |
|---|---|
| resolved markets seen | **4,657** |
| of those, with a quote taken while still live | **88** |
| scorable observations | 113 |
| independent events | 88 |
| observations per independent event | 1.3 |
| outcomes | 44 yes / 44 no |
| lead time, quote to close | median **0.23 h**, p75 0.27 h, max 719 h |

4,657 markets resolved and 88 of them were ever seen with a live price. The
median usable forecast was made **fourteen minutes** before settlement, on a
fifteen-minute market. Scoring that would measure how fast a price converges to
an outcome it can already see, not whether anyone forecasts well.

### The reason, and it is not the archive window
`collect.py` asked for each series with no status filter, deliberately, so that
resolution outcomes come too. But the request stopped at 5 pages of 200 —
1,000 rows — and for a busy series Kalshi filled those rows with markets that
are not tradable now. Measured on the 2026-09-14 snapshot:

- **KXBTCD: 1,000 rows, 1,000 of them `initialized`.** Not one live daily quote
  had ever been archived, in the entire history of this project.
- KXETHD, KXBTC, KXETH: identical.
- KXBTC15M: 946 `finalized`, 58 `initialized`, **1 `active`**.

One active 15-minute market per snapshot, 3 snapshots a day, 14 days = 42. The
inventory found 43. The arithmetic closes exactly, which is how a suspicion
becomes a diagnosis.

**This also retracts something I said earlier today.** The mirror was framed as
the thing standing between us and a validation sample. It is not. The mirror
holds more days of the same truncated pages; it would have multiplied 88 by the
extra days and by nothing else. The bottleneck was in the collector, in one
paging loop, and it had been there since the collector was written.

### The fix
When — and only when — a series fills the cap, one more call asks for its OPEN
markets explicitly and merges them by ticker. Truncated series pay for the extra
call and the rest do not.

Verified on the first run after the change (2026-09-15T1317Z):

- 8 series reported truncated: KXBTC15M, KXETH15M, KXBTC, KXETH, KXBTCD,
  KXETHD, KXINXU, KXNASDAQ100U
- **KXBTCD went from 0 active to 200 active.** KXETHD, KXBTC, KXETH the same.
- KXBTC15M still shows 1 active, which is correct: at any instant only one
  fifteen-minute market is open.
- open-pass errors: none
- sync window 0.77 s to **1.4 s**. It widened and that is a real cost on a
  measured quality number, but it is two orders of magnitude below the 8-minute
  gap that once moved a result by 33%.

### What the fix buys, and what it does not
It buys OBSERVATIONS, not independence. The 200 live daily rungs are the rungs
of one ladder that settles at one instant, so a day of daily markets is one
independent draw per asset however many rungs it has — the same clustering the
inventory already reports. What changes is the lead-time distribution: a daily
rung is observable three times across the day it lives, hours before
settlement, instead of once fourteen minutes before.

Two independent draws a day, from tomorrow. That is roughly 700 a year, which
is a sample. It is not a sample today, and no amount of reprocessing makes the
past fourteen days into one.

### What this means for scoring
Week 5's scoring work should not run on the present sample. The honest sequence
is: let the corrected collector accumulate, then score. The inventory script is
in the `measure` workflow and writes `findings/validation_inventory.json` on every
run, so the sample size is now a number on the record that grows visibly
instead of an assumption.

## D-081 — The measurements read the mirror, and nine events are the real sample
**Date:** 2026-09-15 · **Produced by:** `.github/workflows/measure.yml` · `scripts/archive.py`

The public repository keeps 14 days for data rights (docs/DATA_SOURCES.md). The
private mirror has held every snapshot since 2026-08-30. Until now the
measurements could only see the window. They can now read the mirror, and the
rights decision is untouched: nothing new is published, only findings come out.

### How it is wired
- `archive.RAW` honours `DIVERGENCE_RAW`. One constant, and every reader moves.
- `measure.yml` clones the mirror `--depth 1 --filter=blob:none --sparse` and takes
  only `raw/_meta`, `raw/kalshi`, `raw/deribit`, `raw/polymarket_events`. Measured
  2026-09-15: `events/`, `holders/` and `coverage/` are **55% of the archive** and no
  measurement reads any of them.
- A separate **read-only** token, `ARCHIVE_TOKEN_RO`. The read-write one stays in
  `collect` and nowhere else.
- `workflow_dispatch` only. `measure` also runs on pull_request and a same-repo PR
  can read secrets; a PR should prove the code, not be handed a credential.
- A missing or expired token is **not a failure**. The step exits, everything
  runs on the public window, and `findings/latest.json` records
  `archive_source` so a narrowed run is visible rather than silent.

### The danger, and what guards it
`DIVERGENCE_RAW` moves every READER. It must never move the DELETER: the mirror
is the only copy of everything older than fourteen days. `prune_archive.py`
computes its own `RAW` from `__file__` and does not import `archive.py`. That
duplication looks like something worth tidying away, so four tests now fail if
the pruner ever imports the reader, reads the environment, or disagrees with the
reader when no override is set.

Verified after the first mirror run: the public working tree is still 14 days,
2026-09-01 to 2026-09-15.

### What the longer series bought
Archive seen by the measurements: **16 days, 61 snapshots** (was 14 and 46).

| | window | mirror |
|---|---|---|
| observations per rung | 45 | **55** |
| rungs with an edge | 134 / 1978 | 165 / 2418 |
| share | 6.8% | 6.8% |
| always / sometimes / never | 3 / 0 / 41 | **3 / 1 / 40** |
| median edge value | $0.63 | $0.86 |

The share did not move. One rung moved from "never" to "sometimes", which is
exactly what ten more observations per rung are for: a rung that clears the test
occasionally is a different object from one that never does, and eleven days
could not tell them apart.

### Where it mattered: the validation inventory
| | window | mirror |
|---|---|---|
| resolved markets seen | 4,657 | 4,851 |
| with a prior live quote | 88 | **145** |
| scorable observations | 113 | **274** |
| independent events | 88 | **109** |
| median lead time | 0.23 h | **6.87 h** |

The lead time is the real gain, and the reason is specific: the mirror reaches
back to 2026-08-30, so it contains the **August month-end settlement**. Forty-two
monthly markets resolved there — KXBTCMAXMON 22, KXBTCMINMON 8, KXETHMAXMON 6,
KXETHMINMON 6 — with 149 observations taken days before they settled. That is a
different and far better kind of forecast than a fifteen-minute market quoted
fourteen minutes before expiry.

### But count the events, not the pairs
109 independent events = **100 fifteen-minute markets + 9 everything else**. The
forty-two monthly markets collapse to 9 events, because every rung of one
monthly ladder resolves from one reading of one price path.

So the informative sample is **nine events**, and the hundred short-dated ones
are forecasts made minutes before an outcome that was already visible. That is
the number to hold in mind when Week 5 arrives, not 145 and not 274.

### One more thing scoring will have to handle
The outcome balance moved from 44 yes / 44 no to **55 yes / 90 no**, because the
monthly markets are tails and tails mostly resolve no. A Brier score on an
unbalanced tail sample is not interpretable against 0.25; it needs a base-rate
comparison. Recorded now so it is not discovered after the number is computed.

Five of the 61 snapshots carry no Kalshi stream: Kalshi was added on 2026-08-31
and the mirror predates it. The inventory reports them rather than scoring them
as empty.

## D-082 — The intraday ladders, and why their first numbers mean nothing yet
**Date:** 2026-09-15 · **Produced by:** `scripts/measure_band.py` · `scripts/write_findings.py`

D-079 showed the year-end comparison losing two of its three findings to a
seven-day expiry gap. The obvious response is a contract whose expiry gap is
small. Kalshi's intraday BTC and ETH ladders settle the same day, and Deribit
lists daily expiries, so they were brought into the measurement.

### What was added
Four series beside the two year-end ones:

| label | series | shape |
|---|---|---|
| BTC / ETH intraday | KXBTC, KXETH | exhaustive buckets |
| BTC / ETH intraday cum | KXBTCD, KXETHD | **cumulative** |

The cumulative shape is new to this project. Every rung is `P(S > K)` at its own
threshold, so the rungs overlap and summing them is not a density.
`rungs()` now detects the shape and refuses to report `density_sum` for a
cumulative ladder rather than publishing a number that looks like the
exhaustiveness check and is not one.

### Two bugs the intraday contracts exposed
**Expiry selection compared DATES.** A Kalshi market closing 04:00 UTC would
have accepted that day's 08:00 Deribit expiry as "not past the close" — four
hours after it. Harmless on year-end ladders, wrong here. Now compared as
instants.

**There is no expiry before the close, ever.** Deribit's daily options settle
08:00 UTC and are delisted immediately. A 13:17 snapshot reading a market that
closes at 14:00 the same day finds that day's expiry already gone; the nearest
listed one is **the next morning, 18 hours after**. So the intraday comparison
cannot be two-sided, and `rungs()` now carries `expiry_side` rather than silently
picking whatever is nearest.

### The side matters more than the size
| | year-end | intraday |
|---|---|---|
| gap | +165 h | **−18 h** |
| side | option expires FIRST | option expires LATER |
| bias on an upside tail | understates — flatters us | overstates — works against us |

This is the part worth keeping. The year-end setup used an expiry seven days
EARLY, and a tail probability grows with maturity, so the option number was
systematically low and every gap we found was flattered by it. The intraday
setup has the opposite sign: the option is measured 18 hours PAST the
settlement and therefore overstates. A Kalshi price above it is evidence; a
price below it proves nothing.

Nine times closer, and on the conservative side.

### The first reading, and why it is not a result
| | year-end | intraday |
|---|---|---|
| rungs with an edge | 165 / 2418 quotable (6.8%) | 65 / 516 (12.6%) |
| mean envelope | 6.2c | 12.8c |
| median edge value | $0.86 | $18.53 |
| **observations per rung** | **55** | **1** |

**One.** Only the 2026-09-15T1317Z snapshot contains live intraday markets,
because the collector's paging cap hid them until it was fixed the same day
(D-080). "65 rungs always exceed" means 65 rungs exceeded in their single
observation, which is what the stability module exists to stop anyone from
saying. The 12.6% and the $18.53 are one reading of one moment.

They are recorded because the pipeline producing them is now correct, not
because they are findings. Nothing from the intraday block should be quoted
until the rungs have been seen enough times to separate a standing difference
from a snapshot.

### One caveat already visible
The intraday exhaustive ladders sum to 0.9904. For an option 18 hours out the
discount factor is essentially 1, so that is a **1% shortfall** against a
year-end shortfall of 0.2%. The strike grid is coarse relative to how far BTC
moves in a few hours, which is the same discretisation effect D-079 measured at
12.6% per digital — and it will be larger here, not smaller. Measuring it on
the intraday chains is the next thing this block needs.

## D-083 — There is no BRTI basis, and the expiry gap is the last one standing
**Date:** 2026-09-15 · **Produced by:** `scripts/measure_basis.py` · workflow `measure`

D-075 named three ways the Kalshi and Deribit contracts differ. Two were sized.
The third — Kalshi settles on CF Benchmarks' BRTI, Deribit on its own index —
was left **UNKNOWN** because it looked unmeasurable. It was not.

### Both halves were already archived
- A settled Kalshi market carries `expiration_value`, which IS the realised BRTI:
  the average of the sixty RTI prices before its close.
- The Deribit payload carries `usIn`, a **microsecond** timestamp of when the
  index was read. Not the snapshot time — the read time.

Fifteen-minute Kalshi markets settle four times an hour, so every snapshot has
a settlement within 450 seconds of its Deribit index read. Pair the nearest and
the difference is the basis plus whatever the price did in between.

### Separating the two, by the shape of the table
| bin | n | median | spread | se |
|---|---|---|---|---|
| within 60 s | 25 | **−0.20 bp** | 1.54 bp | 0.31 bp |
| within 180 s | 47 | −0.48 bp | 3.81 bp | 0.56 bp |
| within 450 s | 63 | −0.62 bp | 4.92 bp | 0.62 bp |

The test was stated before the numbers were seen: price movement has a median
of zero and a spread that GROWS with the gap; a real basis holds its median as
the bin tightens while the spread falls.

The spread grows exactly as predicted — 1.54, 3.81, 4.92 — so the wide bins are
measuring BTC, not CF Benchmarks. And the median does not survive the tightening:
it falls toward zero, and in the tightest bin it is **−0.20 bp against a
standard error of 0.31 bp**. Every one of the three bins is within about one
standard error of zero.

Per asset: BTC −1.08 bp (n 31, se 0.81), ETH −0.04 bp (n 32, se 0.87). Neither
is distinguishable from nothing.

### The answer
**There is no measurable basis.** A two-sigma bound from the tightest bin is
±0.62 bp, or **±0.006%**. On an 87,000 index that is about **six dollars**.
Deribit's strike interval is 5,000 dollars, so the basis is on the order of one
thousandth of one strike step. It cannot move a digital by an amount this
project can measure, and it should stop being listed as a caveat.

### What that leaves
| difference | status |
|---|---|
| settlement instant | **the only one that matters.** +165 h on the year-end ladders, and D-079 showed that swallowing two of three findings. −18 h intraday, on the conservative side (D-082). |
| averaging window | negligible: 60 seconds against a horizon of hours or months |
| reference rate | **closed, below 0.6 bp** |

Three named differences, and after three measurements exactly one is left. That
is worth saying plainly, because "the contracts do not settle on the same thing"
was a reasonable-sounding objection that could have been repeated indefinitely
without ever being tested. It has been tested. What remains is not the index —
it is the clock.

### A limit of the method
It cannot reach zero gap: Kalshi settles every fifteen minutes and the collector
runs three times a day, so 25 pairs inside a minute is what the archive happens
to offer. A larger sample would tighten the bound but cannot change its sign —
there is nothing there to find a sign for.

## D-084 — The two tenors fail in opposite directions
**Date:** 2026-09-15 · **Produced by:** `scripts/measure_sensitivity.py` · `findings/sensitivity.json`

D-082 brought the intraday ladders in because their expiry gap is small.
D-082's own closing line said the strike grid had to be measured on them next.
It has been, and the answer is that the intraday instrument trades one defect
for another.

| | year-end | intraday |
|---|---|---|
| expiry gap | **−165 h** | **+18 h** |
| bias on an upside tail | option expires FIRST, understates, flatters us | expires LATER, overstates, works against us |
| straddles the close | yes: −165 h and +2019 h | **no** — both neighbours are after |
| grid sensitivity, median | 11.5% | 5.2% |
| grid sensitivity, p90 / worst | 18.3% / 23.9% | 29.9% / **53.3%** |
| **rungs returning a duplicate digital** | **0.0%** | **67.4%** |
| verdicts | 84 above both, 81 inside the band | 66 above the bound, 250 under |

### The number that decides it
**67.4% of intraday rungs return a digital identical to another rung of the
same ladder in the same snapshot.**

Kalshi steps its intraday thresholds by 100 dollars. Deribit's strikes are far
wider, so runs of ten or more consecutive Kalshi rungs fall inside ONE option
bracket and come back with the same number. The log shows it plainly: nine
consecutive thresholds at 0.00554, then nine at 0.00373.

Two thirds of that ladder is one number repeated. Those rungs are not
independent measurements and the 66 that clear the bound are not 66 findings.

### So neither tenor is clean, and the defects are complementary
- **Year-end**: strikes fine enough that no two rungs collide, and an expiry
  gap of 165 hours that D-079 showed swallowing two of three findings.
- **Intraday**: an expiry gap of 18 hours on the conservative side, and an
  option chain that cannot resolve the ladder it is being compared against.

This is a structural statement about the comparison, not a bug to fix. The
option chain's strike spacing is set by Deribit for its own purposes and the
prediction ladder's step is set by Kalshi for theirs; where the two happen to
be compatible is not something this project controls.

### The question it raises
A middle tenor — a weekly or monthly TERMINAL ladder against a Deribit weekly —
could have both a small expiry gap and strikes fine enough to resolve it. That
is the obvious next place to look, and it is recorded rather than built:
Kalshi's monthly crypto series in the archive are MAX and MIN contracts, which
are touch-type and a different comparison entirely (D-031). Whether a terminal
weekly ladder exists at all is UNKNOWN and worth one inventory pass.

### A regression this run caught in my own work
The rewrite of `neighbours()` took "the two expiries nearest the close" by
absolute distance. For the year-end ladders 27NOV26 is closer to 1 January than
26MAR27 is, so both picks landed BEFORE the close and the band of D-079
silently became a one-sided bound — the finding disappeared without any error.
Fixed to take the nearest on EACH side, which restores −165 h and +2019 h.

It is worth naming how this was caught: not by a test, but because
`findings/sensitivity.json` printed `expiry_hours_by_tenor: {year_end: [-165]}`
with one entry where there should have been two. The file was added in the same
session for an unrelated reason — a virtualised CI log cannot be read past its
first screen — and it caught a silent regression within the hour. That is the
argument for D-070's rule holding generally: a number that only exists in a log
is a number nobody checks.

## D-085 — The Polymarket side had never been repaired, and it was half artefact
**Date:** 2026-09-15 · **Produced by:** `scripts/measure_polymarket.py` · `scripts/fees.py`

Everything from D-073 to D-084 was applied to `measure_band.py` and to the page.
None of it was applied to `measure_polymarket.py`. Its number sat in the same
`findings/latest.json` as the repaired one, formatted the same way, and nobody
looked — including me, for two weeks.

### What it was still doing
| | Kalshi side | Polymarket side, until today |
|---|---|---|
| discount convention (D-073) | repaired | **absent** — `digital()` called without `D`, so the put branch returned the old quantity |
| trade at quoted prices (D-076) | yes | **`1.96 * SE` around two mids** |
| both venues' fees (D-077) | yes | prediction leg **free** |
| expiry chosen by instant (D-082) | yes | day arithmetic with a hardcoded 8-hour offset |

### Polymarket charges a taker fee, and the schedule was in our own archive
The code carried this comment: *"Polymarket maker fee is treated as 0."* That
confuses a maker rebate with a taker fee. Every market in the archived payload
carries its own schedule, and has all along:

    feesEnabled: true
    feeType:     "crypto_fees_v2"
    feeSchedule: {"exponent": 1, "rate": 0.07, "takerOnly": true,
                  "rebateRate": 0.2}

    fee = C x rate x p x (1 - p)

Confirmed against Polymarket's published documentation. It is the **same
formula and the same 0.07 coefficient as Kalshi**, taker only — and our trades
cross the spread, so it applies. The measured average over the archive is
**0.65 cents per share**, against edges of the same order.

`fees.polymarket_rate()` reads the schedule from the market rather than hardcoding
it: Polymarket sets it per market and has already moved the crypto rate once
(0.072 to 0.07). It returns **None, not zero**, for a missing or unrecognised
schedule, and those rungs are skipped rather than scored.

### What the repair did to the number
| | before | after |
|---|---|---|
| rungs with a verdict | 5,927 | 4,561 quotable of 7,420 |
| exceeding | 1,432 | 470 |
| **share** | **24.2%** | **10.3%** |
| well-matched expiry (gap ≤ 12 h) | 26.3% | **8.3%** |
| always / sometimes / never | 9 / 298 / 92 | **3 / 173 / 214** |

More than half of it was method. The mass moved decisively from "sometimes" to
"never": 92 rungs never cleared the old band, 214 never clear the new one. The
three that always do have two to four observations each, which the stability
module reports and which is not enough to call anything.

### The sanity check that had been failing silently
Look at the well-matched subset. A tighter expiry match should REDUCE apparent
divergence — less of the gap can be the clock. Under the old method it went the
other way: 26.3% against 24.2% overall, so the better-matched contracts
disagreed *more*. That should have been read as a warning about the method.
Under the repaired test it points the right way, 8.3% against 10.3%.

Nobody noticed the sign because there was no reason to look at it. It is worth
recording as a class of error: a number can be wrong in a way that is only
visible in its relationship to another number, and neither one looks odd alone.

### What this does and does not settle
It does **not** say Polymarket and Kalshi are the same. 10.3% against the Kalshi
year-end 6.8% is not a like-for-like comparison — different tenor, different
ladder shape, different expiry alignment. Comparing them properly is a separate
measurement.

It does say that the Polymarket figure this project has been carrying was
roughly half method. And it removes the asymmetry that made any statement about
Polymarket unsafe: both venues are now measured by the same test, with both
fee schedules, at instants rather than dates.

### Why this was found at all
Only because the question "should we apply for a Polymarket grant" forced a look
at what the Polymarket measurement actually did. A repair programme that fixes
the code it is looking at and leaves its neighbour untouched produces exactly
this: one number that has survived scrutiny and one that has never been asked.
Both in the same file, both rendered to one decimal place.

## D-086 — The digital returns `dsp`, because `p` read as probability
**Date:** 2026-09-15 · **Produced by:** seven files, one rename

D-074 closed the discount repair with an open item: *"The internal key is still
`p` and the ladder row key is still `opt`. The docstrings, the findings note and the
page now all say 'discounted state price', but the identifiers have not been
renamed, so the naming half of the Week 1 item is done in prose and not in
code."* This closes it.

### What changed
`digital()` returns `dsp` instead of `p`, in Python and on the page. 35 call sites
across `measure_band`, `measure_exhaustive`, `measure_touch`, `measure_polymarket`,
`measure_sensitivity`, the tests and `web/index.html`.

The reason is narrow and worth stating: `p` reads as "probability". The quantity
is `D * Q(S > K)`, a discounted state price, and reading it as a probability is
**precisely the error D-073 was about**. A name that invites the mistake the
project has already made once is a bad name.

### What deliberately did NOT change
`opt`, `opt_low` and `opt_high` on the rung rows. They are discounted state prices
too, and a fully consistent rename would have made them `opt_dsp`,
`opt_dsp_low`, `opt_dsp_high`.

They were left alone on a judgement: `opt` reads as "the option side", which is
what it is and is not misleading, while `p` read as something the number is not.
Renaming them would have touched `write_findings` and the page's display layer for
no safety gain, and this project has already had a rename leak into markup once.
A comment on the row construction says so, so the asymmetry is a decision rather
than an oversight.

### How the citation was checked
The first push failed `ref-check`: the new comments cite D-086 and D-086 did not
exist yet. That is the workflow doing its job — every decision number cited
anywhere in the repository has to resolve to a real record, and a comment
referring forward to an unwritten one is exactly the dangling reference it was
built to catch.

The tests passed on the same push, which is the other half: 54 cases over the
renamed code, including the ones that pin the envelope direction and the
discount convention.

## D-087 — We were archiving strangers' profiles, and half the flow file was a repeat
**Date:** 2026-09-16 · **Produced by:** `collector/collect.py` · archive version 4

The 4-6 week plan had an item reading "stop or consume flow/holders". It was
framed as a storage question: `events/` and `holders/` are 48% of the archive and no
measurement reads either. Counting before deciding turned it into a different
question.

### What one flow file actually contains
7,081 trades, 5.4 MB, 958 distinct wallets in a single run. Per trade:

    proxyWallet, side, asset, conditionId, size, price, timestamp,
    outcome, outcomeIndex, transactionHash
    name, pseudonym, bio, profileImage, profileImageOptimized
    icon, title, slug, eventSlug

The second line is who the trader says they are. `name` was populated on **6,568
of 7,081** rows, `pseudonym` on 6,543. The third line is metadata repeated on every
single row that `raw/polymarket_events/` already stores once per run.

Together: **47.5% of the bytes.**

### The part that is not about storage
A rolling public archive of which named account bought which contract, at what
price, at what second, is a different category of thing from an archive of
prices. `docs/DATA_SOURCES.md` analysed the venues' terms for market data. It did
not consider that the trade tape carries third-party profile data, because
nobody had looked at a row.

Nothing in this project reads those fields. They were being published for
fourteen days at a time and accumulated in the mirror indefinitely, for no use.

### The decision
Nine fields are dropped before writing: `name`, `pseudonym`, `bio`, `profileImage`,
`profileImageOptimized`, `icon`, `title`, `slug`, `eventSlug`.

`proxyWallet` is **kept**. Concentration and large-trade work (B-007) needs an
actor key, a wallet is not a person's profile, and it is already public
on-chain. `transactionHash` is kept for the same reason: it is the on-chain
receipt and it is what makes a row verifiable by someone else.

Measured on the first run after the change: 415 bytes per trade against 790
before, and none of the nine fields present. The prediction was 47.5%; the
result is 47.5%.

### This bends rule 2, and says so
Rule 2 of this project is that raw data is stored **as it arrives**, because the
methodology will change and we must be able to recompute from the archive. This
is the first deliberate exception.

The justification is narrow: the rule exists so a future recomputation is
possible, and not one of the dropped fields can enter any recomputation of a
price, a probability or a fee. What is lost is the ability to ask "what is this
trader's display name", which is not a question this project has or wants.

Recorded as an exception rather than quietly done, so that the next person who
finds an archived field missing can see it was a decision and read the reason.

### Holders
`holders/` is untouched for now: it runs once a day, it is 7.8 MB of the archive,
and it has not been looked at row by row. Whatever this record says about
`events/` probably applies there too, and that inspection is the obvious next
thing rather than an assumption.

## D-088 — The holders file said who was holding which side, right now
**Date:** 2026-09-16 · **Produced by:** `collector/collect.py` · archive version 5

D-087 closed the `events/` half of the storage question and left this one open on
purpose: "whatever this record says about `events/` probably applies there too, and
that inspection is the obvious next thing rather than an assumption." This is the
inspection. Most of it confirms D-087. Two things in it do not.

### What one holders file actually contains
`raw/holders/2026-09-15/holders_2026-09-15T0505Z.json.gz`, the newest one at the
time of writing: 651,398 gzipped bytes, 3.70 MB plain, 80 conditions, 150 token
groups, **10,409 holder rows, 5,864 distinct wallets**. Per row:

    proxyWallet, amount, outcomeIndex
    name, pseudonym, bio, profileImage, profileImageOptimized,
    displayUsernamePublic, verified
    asset

`name` populated on 9,622 of 10,409 rows, `pseudonym` on 9,559, `bio` on 788.
`profileImageOptimized` populated on **0** rows: the key and its empty string were
stored 10,409 times a day for nothing. `verified` was true twice.

The first line is 26.5% of the field bytes. The other two are the rest.

### Why this stream is worse than the trade tape, not better
A trade is something that already happened. A holding is a position that is open
**now**. So each row named an account and said which side of a threshold it is
sitting on and how much of it — refreshed daily, published, and mirrored. D-087's
argument applies here with more force, not less.

### Two categories of removal, kept apart
**Profile — not recoverable, and not wanted.** `name`, `pseudonym`, `bio`,
`profileImage`, `profileImageOptimized`, `displayUsernamePublic`, `verified`.
48.4% of the field bytes. Nothing in this project reads any of them.

**Redundant — exactly recoverable.** `asset` is the token id, repeated on every
holder row, and it is already the key of the group the row sits inside. Checked:
equal on **10,409 of 10,409 rows, 0 mismatches**. Removing it loses nothing at all;
a reader can put it back from the key. 25.1% of the field bytes.

These are not the same act and the code does not pretend they are. The second is
compression. The first is a deliberate loss, and it is the one that needs the
justification below.

**Kept:** `proxyWallet`, `amount`, `outcomeIndex`. Same reasoning as D-087 — the
wallet is an actor key that B-007 needs, it is already on-chain public, and it is
not a profile.

### Measured effect
Applied to the real 2026-09-15T0505Z file: 3,696,191 plain bytes → 1,010,677
(**−72.7%**), 648,806 gzipped → 267,123 (**−58.8%**). Field-byte prediction was
−73.5%; the gap is the JSON structure outside the holder rows, which does not move.

The pipeline was verified by the next scheduled fetch, `2026-09-16T0504Z`, which
is the first holders file written under archive version 5:

    gzip        651,398 -> 275,704 bytes   (-57.7%, predicted -58.8%)
    per row     351 -> 97 bytes
    fields      proxyWallet, amount, outcomeIndex — and nothing else
    leaked      0 of 10,299 rows carried any dropped field

The counter worked on its first run too: `holders_unexpected: 1`, and reading the
file back finds exactly one condition whose payload is not a list. The hole that
was invisible is now a number in `_meta`.

(This paragraph replaces the one written a few hours earlier, which said the
change was not yet confirmed end-to-end. It said so rather than implying it was
fine; this is the confirmation it was waiting for.)

### The first thing the inspection found that is not about storage
**77 of the 150 token groups are at the `limit=100` cap.** The collector asks for
a hundred holders and a hundred is what it gets, so for more than half the tokens
this file is a *top-100 truncation*, not a holder set.

That matters for what the stream can ever answer. A concentration measure — a
Gini, an HHI, a true "share held by the largest wallets" — needs the tail or at
least the total. This file has neither. B-007 was written assuming holders data
would support it; on today's collector it supports "how much do the top 100 hold"
and nothing below that line.

Not fixed here, because raising the limit is a scope change and rule 5 applies.
Recorded in `docs/BACKLOG.md` against B-007 so the assumption is not carried
silently into whoever does that work.

### The second thing
One condition — `0x47914796a7…` — had a **JSON `null` body**. Not an exception, so
the `try/except` around the fetch never saw it, and `null` was archived
indistinguishably from "nobody holds this". One in eighty on the day it was
looked at; unknown on the other thirteen days, because nothing counted.

The payload is still written exactly as it arrived. What is new is a count:
`holders_unexpected` in `_meta`, `None` on runs where the stage was skipped rather
than `0`, so "not fetched" and "fetched, all fine" are different values. Rule 7 —
the hole is surfaced, not closed.

### What this does not undo
Fourteen days of holders files already published still carry the profile fields,
and so do the trade files written before D-087. Two separate horizons:

- The **working tree** heals itself. `scripts/prune_archive.py` deletes whole day
  folders older than 14 days across every stream, so the last file containing this
  data leaves `main` around 2026-09-29 without anyone doing anything.
- **Git history does not.** As `prune_archive.py` says in its own docstring, a
  deletion commit does not remove the blob. Anyone cloning the full history still
  gets it. Removing it there means rewriting published history, which breaks every
  existing clone and every commit SHA this project has cited.
- **The private mirror does not either.** It is append-only by design (`cp -rn`),
  which is what makes it safe to prune the public copy. So every holders and trade
  file since 2026-08-30 keeps its profile fields there, permanently. Private, not
  published, and not read by any measurement — the sparse checkout does not even
  fetch `holders/` — but it is there, and leaving it out of this list would have
  made the paragraph above read better than the truth.

That trade is not made here. It is a call for the repository owner, it is
destructive and irreversible, and the cost side of it is real. Written down so the
choice is visible rather than assumed away.

## D-089 — The archive window stays at fourteen days, and the reason changed
**Date:** 2026-09-16 · **Applies to:** `scripts/prune_archive.py` (`ARCHIVE_DAYS`)

Open since the sprint plan was written: keep the public `raw/` window at 14 days, or
extend it to roughly 90? Closing it, because the argument that opened it no longer
exists.

### Why extending was ever on the table
To give the measurements more to read. A friction band over 49 snapshots is a
different claim from one over three hundred, and at the time the only archive the
measurements could see was the public one.

### Why that argument is now void
`measure.yml` runs on `workflow_dispatch` and on `pull_request`. **There is no
schedule.** Every published number therefore comes from a manual run, and a manual
run clones the private mirror and sets `DIVERGENCE_RAW` to it — every snapshot since
2026-08-30, not fourteen days of them. Extending the public window would not add one
observation to any finding this project publishes. It would only publish more.

### What the window is actually for now
Two things, and they pull in opposite directions.

**Against a longer window.** `docs/DATA_SOURCES.md` quotes Kalshi's clause verbatim:
the named practice is "providing archived or cached data sets containing Kalshi Data
to another person or entity". A rolling sample is a weaker instance of that than a
growing feed. And since D-087 and D-088, a longer window also means the files written
before 2026-09-16 — the ones carrying strangers' profile fields — stay in the working
tree longer. Fourteen days is what makes that self-healing; ninety would have kept
them up for three months.

**For a longer window.** An outside reader can only re-derive what is public. The
findings report numbers computed over the full mirror; anyone checking them from the
public repository gets 14 days, currently 49 snapshots. That gap is the real cost of
this decision and it is not small — it is the difference between "reproducible" and
"reproducible in the small". `findings/` records the scope of each run so a reader can
at least see which one they are looking at.

### The decision
14 days. Not because the balance is comfortable, but because extending buys nothing
measurable and costs on both of the other two axes. If the reproducibility gap is to
be closed, the way to do it is to publish the mirror or hand out read access — a
different decision, with the data-rights question fully reopened — not to widen the
window a little and hope it covers both.

### What this decision does not claim
Unchanged from `docs/DATA_SOURCES.md` and repeated here so it is not lost: the window
bounds the **working tree**, not the repository. A full clone still reaches every
snapshot ever committed, and `.git` grows at the same rate either way. Bounding the
repository itself would take history rewriting or never committing raw payloads
publicly at all. Neither is done, and the claim is limited to what is measured.

## D-090 — Denetim 3: what the documents claim against what the code does
**Date:** 2026-09-16 · **Checked:** every `.md` in the repository against the code,
the workflows and `findings/latest.json`

The third audit. Denetim 1 asked whether the pipeline was healthy, Denetim 2 whether
every number on screen could be recomputed. This one asks a different question: does
the writing still describe the thing?

### What is clean, and it is most of it
- **The methodology documents are current.** Every mention of `1.96 · SE`, of mid
  prices, of an undiscounted digital, appears in the past tense explaining what it
  replaced. `METHODOLOGY.md`, `scripts/README.md` and `RESEARCH_NOTE_1.md` all match
  the code after weeks 1-4. This was the thing most likely to be wrong and it was not.
- **No document names a script that does not exist.** Zero phantom references.
- **The constants agree** where a document states one: `ARCHIVE_DAYS = 14`, the three
  crons at 05:00 / 13:00 / 21:00 UTC, `GENERAL = 0.07` and `INDEX = 0.035`,
  `always_above = 0.9`, `ARCHIVE_VERSION = 5`.
- **The interface cannot go stale.** `web/index.html` reads `findings/latest.json` and
  contains no percentage of its own. Checked by searching it for literal figures:
  none.
- **`RESEARCH_NOTE_1.md` matches the findings file exactly** — 61 snapshots, 16 days,
  $4.69.

### What was wrong
**The README's results table had drifted from the findings file it describes.**

| README said | findings say |
|---|---|
| "in 45 of 45 observations each" | 55 observations per rung, and the three are 55, 55 and **54** |
| "0.2% arithmetic violations" | 0.4% |
| "94.9% above the 2x bound" | 93% |
| "14 days, 46 snapshots" | the findings were computed over 61 snapshots and 16 days, from the mirror |
| "148 of 446 flow markets hit the fetch limit" | 149 of 460, in the run of 2026-09-16T0504Z |

Nothing in the pipeline had failed. The numbers were copied into prose once, by hand,
and prose is not recomputed. Two lines further down the same README said "every number
on screen traces to a script — enforced in CI", which was true of the screen and not
of the README saying it.

### The one that is worse than stale
"In 45 of 45 observations each" is not a number that went out of date. It is the
overclaim **D-072 already found and fixed** — `stability.py` calls a rung
always-exceeding when its share is above `always_above`, which is **0.9, not 1.0**, so
"every one of N" says something the classifier never checked. D-072 corrected the
interface card to "in over 90% of their observations" and left the identical sentence
standing in the README.

At the time it was accidentally true — all three rungs really were 45 of 45. It is not
true now: one of them is 54 of 55. A fix applied in one place and not the other stayed
invisible for as long as the wrong sentence happened to be right.

### The rest
- **`scripts/README.md` is the script index and was missing three scripts that CI runs
  on every measurement**: `measure_sensitivity.py`, `measure_basis.py`,
  `inventory_validation.py` — the three added in weeks 3 and 4. A reader taking that
  page at its word would think the pipeline has nine measurements. It runs eleven.
- **`DATA_SOURCES.md` said "about 42 snapshots"**; the window holds 47.
- **Four of the five workflows are named in no document at all**: `collect.yml`,
  `tests.yml`, `ref_check.yml`, `verify_index.yml`. The first three are described in
  prose without their filenames, which is survivable. `verify_index.yml` is not: it is
  an unlabelled experiment (can a GitHub runner pull an index option chain from
  Yahoo?) sitting in the repository with no record of why it is there or what it
  returned. Logged in `BACKLOG.md` rather than deleted.

### The pattern, which is the actual finding
Every stale claim was on a **hand-written** surface. Every **generated** surface was
correct — the interface, `findings/`, `state/latest.json`. The failure is not
carelessness, it is that copying a computed number into a sentence creates a second
copy with no owner.

### What was done about it
`scripts/check_readme.py` rebuilds the README's result sentences from
`findings/latest.json` and fails the build if they are not in the file verbatim. It
reads `always_above` out of `stability.py` too, so changing the classifier forces the
README's wording to change with it — the specific thing D-072 could not enforce.

It is deliberately rigid: reword a sentence and it fails. That is the same choice
`audit_semantics.py` makes about Kalshi's rule text, for the same reason — a checker
that tolerates rewording tolerates the number changing underneath it. Rewording then
costs one edit here, at the moment somebody is looking at the current value anyway.

Like `ref_check.py` it self-tests first: a checker that catches nothing also stays
green.

### What is still not checked, and is not pretended to be
Prose in `docs/` carries numbers that nothing verifies — the 6 days 21 hours in
`METHODOLOGY.md`, the coverage figures in `ARCHIVE_SCHEMA.md`, everything in this log.
Eight claims in one file are now machine-checked. The rest rests on audits like this
one, which is why they are numbered and repeated rather than treated as finished.

## D-091 — The external review is closed; the project becomes three layers, and the repository becomes its memory
**Date:** 2026-09-16 · **Source:** `the review package (kept outside the repository)` reviewed independently by three AI systems and synthesised by the owner · **Produces:** `docs/STRATEGY.md`, `docs/RESEARCH_ROADMAP.md`, `docs/PRODUCT_ROADMAP.md`, `docs/PRIOR_WORK.md`, `docs/EXPOSURE_ENGINE.md`, `docs/DECISION_GATES.md`, `docs/IDEA_BACKLOG.md`

The review loop that the package in `drafts/` was written for has run and ended. This
record and the eleven after it (D-092 … D-102) carry its conclusions into the log so
that nothing decided in it exists only in a chat transcript. The review is not reopened
by any of them; a broad strategic review is reopened only by a concrete factual or
mathematical contradiction, and none was found (the two technical corrections that
were found are recorded where they belong, in D-093 and D-094).

### The three layers
The project is from now on treated as three related but distinct layers.

**Layer A — Divergence research.** Cross-market research on prediction-market prices
against listed-derivative-implied state prices. Research-first, and unchanged in what
it is not: not a startup by itself, not an alpha engine, not a signal service, not an
arbitrage product, not a "true probability" engine. The same-state work is completed as
Research Note 1 (D-097) rather than expanded indefinitely as the commercial thesis.

**Layer B — exposure-design research.** A new branch. Its question: how should a market
view be expressed across instruments when capital, basis, carry, payoff shape,
liquidity and settlement differ? It is deliberately broader than the "cost of
expressing a view" idea in the review package (§7.1), and it is not "which instrument
is cheapest" — futures, perpetuals, vanilla options, spreads and binaries have different
payoff functions, so the research object is a cost × capital × payoff × basis × risk ×
execution frontier, not a single cost number. Defined in `docs/EXPOSURE_ENGINE.md`.

**Layer C — product spin-off.** Emerges in stages, each gated on evidence: a
same-event payoff card (V0), an event hedge studio (V1), a basis-aware exposure engine
(V2). No stage is built before the gate in front of it is passed (D-099).

### The methodology after the sprint
The measurement framework after D-073 … D-090 is considered fundamentally defensible.
What remains open is listed, not reopened: strike-grid discretisation, maturity
handling, size executability, quote quality, statistical dependence, validation sample
size, and data-rights constraints. The foundational repairs are not revisited unless
new evidence contradicts them.

### The governing principle
The repository is the project's long-term memory. Ideas, competitors, rejected paths,
open questions, methodological mistakes, negative results, product hypotheses and
promotion criteria are written down, dated, and kept. Rejected or delayed ideas keep
their reasoning rather than being deleted. A decision that supersedes an earlier one
says so and names it; the earlier one stays. The project may become smaller, more
negative, more research-oriented or more commercial; it may not become less honest.

### What this record does not do
It does not change a single measured number, script, or workflow. The documents it
produces link to the canonical files rather than restating them; where an existing
document already covers a topic (`docs/BACKLOG.md`, `docs/PRODUCT.md`,
`docs/METHODOLOGY.md`) it stays canonical and the new documents point at it.

## D-092 — ETH above $5,000 gets a pre-committed kill test, and its verdict rules are written before the number
**Date:** 2026-09-16 · **Produced by:** `scripts/kill_test_eth5k.py` (to be added; this record precedes it on purpose) · **Result:** recorded in a later decision, not here

### The status of the rung today
"ETH above $5k" is the one year-end rung that clears the option value at both
bracketing expiries (D-079), by about 0.4 cents, against a median grid sensitivity of
11.5% on the chain that decides it (`findings/sensitivity.json`). Until the test below
has run, its classification is **an interesting anomaly requiring confirmation**. It is
not to be called a finding, alpha, a mispricing, an artefact, or noise. Both directions
of overclaim are refused: the review package said "we would rather you attack it than we
defend it", and this is the attack, specified before its outcome is known.

### What the test computes
For every snapshot in the archive, and for **both** Deribit expiries that bracket the
Kalshi close (today 25DEC26 and 26MAR27), at K = 5,000:

1. the tight bracket the production code uses — note that `bracket()` in
   `scripts/measure_band.py` takes the strikes strictly below and above K, so a
   listed 5,000 strike is never itself used; the tight bracket is 4,800–5,200 on
   25DEC26 and 4,800–5,500 on 26MAR27;
2. the skip-1 and skip-2 brackets, as `scripts/measure_sensitivity.py` defines them;
3. because a 5,000 strike is listed on both expiries, the two one-sided quotients:
   lower strike → 5,000 and 5,000 → upper strike;
4. for each estimator: the mark discounted state price, the executable low and
   high (ask on the leg bought, bid on the leg sold — the same rule as `digital()`),
   the bracket width, and the Deribit fee computed on the **crossed** price of each
   leg rather than its mark;
5. the Kalshi side as `yes_bid − fees.rate(yes_bid, series)`, with `min_contracts`
   reported alongside because the per-order round-up makes the fee size-dependent;
6. a linear interpolant of the discounted state price to the settlement instant,
   `dsp(T*) = dsp(T1) + (T* − T1)/(T2 − T1) · [dsp(T2) − dsp(T1)]`, reported as a
   **sensitivity** and never as the settlement-date value (D-094).

Reported margins, all as `kalshi_net − (executable_high + option_fee)`:
`margin_vs_tight_late`, `margin_vs_skip1_late`, `margin_vs_skip2_late`,
`margin_vs_onesided_lower_late`, `margin_vs_onesided_upper_late`, the same five for
the early expiry, and `margin_vs_worst_local_executable`, which takes the largest
`executable_high + fee` across all estimators on both expiries. A one-sided quote on
any leg makes that estimator `None`, a refusal rather than a zero.

### The pre-committed verdict
Decided before the script exists and before any number has been seen:

- If any robust local-grid estimator removes the positive margin — that is, if
  `margin_vs_worst_local_executable` is positive in fewer than 90% of snapshots, the
  same `always_above` threshold `scripts/stability.py` uses — the rung is **not a
  surviving discrepancy**.
- If every estimator stays positive but the smallest margin is economically tiny —
  defined now as a minimum margin below **0.01** (one cent, the unit Kalshi rounds each
  order's fee up to) **or** margin × resting depth below **1 USD** — the rung is
  **indistinguishable from grid and quote noise**.
- If it survives materially, it is **a genuine anomaly requiring more observations**,
  and nothing stronger.

### What is deliberately not done
No volatility surface, no SVI, no interpolation in strike, is introduced to answer this
question. The test uses only prices on the chain, differenced. If the answer depends on
a model the answer is the model's.

## D-093 — The discount factor gets referees, and one of them is not as independent as it looks
**Date:** 2026-09-16 · **Produced by:** `scripts/discount_referee.py` (to be added) · **Applies to:** `discount()` in `scripts/measure_band.py`

`D` is read off the chain (D-073) and is the one number every other number divides
through. It is mathematically identified and needs no forward, so there is no
circularity with `forward()`. It should still not be the only estimate of itself. Four
referees are recorded side by side, each converted to an implied annual rate
`r = −ln(D)/T` so they can be read in one unit.

1. **The current estimator.** The median over shared brackets of the put-side minus
   call-side residual, `1 − D`.
2. **The parity slope across the chain.** `C(K) − P(K) = D·F − D·K`, so a least-squares
   slope of `C − P` against `K` over the strikes near the forward is `−D`. **This is
   not an independent referee.** The current estimator is the finite-difference form
   of the same identity: per bracket, `[C(a) − C(b)]/w + [P(b) − P(a)]/w` is exactly
   `−Δ(C − P)/ΔK`. Referee 2 re-estimates the same quantity with a different estimator
   (least squares instead of a median of brackets; mids as well as marks). It is
   recorded as an **estimator-consistency check** and is labelled that way in the
   output. The review synthesis called it independent; that is the one technical
   correction this record makes to it.
3. **The futures basis.** The archive holds no futures stream — the Deribit payload
   is options only — but every option row carries Deribit's `underlying_price` for its
   expiry, which is the listed future's price where one is listed and a synthetic
   otherwise. `D_fut = index_price / median(underlying_price)` is therefore computable
   from the existing archive, back to its first day. Whether a given expiry's
   underlying is a listed future or a synthetic is not stated in the payload and is
   recorded as **UNKNOWN** per expiry. Adding a futures stream to the collector would
   settle it and is logged in `docs/BACKLOG.md` rather than done here, because it
   changes the archive format.
4. **An external USD rate.** A sanity check, not the "correct" rate: crypto option
   pricing may embed collateral basis, cross-currency basis, funding and
   venue-specific financing, and the objective is consistency, not forcing Deribit
   into SOFR. `measure.yml` has no network access, so the external rate is a dated
   constant with its source URL written next to it, entered by hand — the only number
   in the measurement path that does not come from the archive, and it is marked as
   such. Until a value is entered it prints `UNKNOWN` and is skipped.

The differences are reported in basis points in three separate columns, because they
mean three different things: 1 − 2 is estimator disagreement; 1 − 3 is the
financing/collateral basis between the option chain and its future; 1 − 4 is the
distance from an external money-market rate. No referee is declared right.

## D-094 — The two-expiry test is a stress test, not a bound; an interpolant is reported as a sensitivity
**Date:** 2026-09-16 · **Supersedes in part:** the wording of D-079 and D-082 and the docstrings of `scripts/measure_sensitivity.py`, which describe the settlement-date value as lying "between" the two bracketing chains

D-079 introduced the requirement that a rung survive both Deribit expiries that
bracket the Kalshi close, and the sensitivity script's `judge()` reads a bid above both
as "cannot be explained by the gap". The argument behind that is monotonicity: a tail
probability grows with maturity, so the settlement-date value lies between the early
and the late chain.

That is not a theorem about a discounted state price. `D·Q(S_T > K)` is not monotone in
`T` in general — the discount factor falls with maturity, the risk-neutral drift and
the term structure of volatility can move the tail either way, and the two chains
carry different `D`, different forwards and different liquidity. Requiring survival at
both ends is a **conservative maturity stress test**: a rung that fails it has not
survived, and a rung that passes it has passed a stress test, not cleared a bound.

The wording is changed accordingly in `docs/METHODOLOGY.md`, in the docstrings and
the reading notes of `scripts/measure_sensitivity.py`, and in Research Note 1. The
arithmetic is not changed — the test remains as computed.

In addition, three numbers are shown together for each year-end rung: the early-expiry
DSP, the late-expiry DSP, and a linear-in-time interpolant to the settlement instant.
The interpolant is a **sensitivity** with a stated formula, not a "true target value",
and it is not a model of the term structure. On the current chains the band is
−165 hours and +2,019 hours, so the interpolant sits within 8% of the way from the
early chain to the late one; it will say little until nearer expiries exist. No
volatility surface is built to close the year-end gap; as Deribit lists weeklies that
straddle 1 January, real expiry convergence is preferred over model complexity.

## D-095 — "Quoted-executable discrepancy" and "size-executable opportunity" are two different claims, and only the first has been made
**Date:** 2026-09-16 · **Applies to:** every surface that describes an edge — `docs/METHODOLOGY.md`, `README.md`, `web/index.html`, `drafts/RESEARCH_NOTE_1.md`

The executable envelope (D-076) prices every leg at a quote that exists and pays both
venues' published fees (D-077). What it establishes is a **quoted-executable
discrepancy**: at top-of-book quotes, one of the two trades leaves something after
fees.

It does not establish a **size-executable opportunity**. That would require depth
beyond the best level, the option contract multiplier and minimum size, sizing the
option spread against the prediction contract, legging risk across two venues,
partial fills, quote staleness inside the sync window, fees at the executed rather than
the quoted price, and slippage. The `depth` and `value` fields in
`scripts/measure_band.py` describe the best level only and say so.

From here on the two phrases are used and not interchanged. A top-of-book discrepancy
is not described as a trade, an opportunity, or an edge that can be taken, without the
second standard being met — and no measurement in the repository meets it yet.

## D-096 — The year-end family is frozen at 44 rungs; no multiple-testing correction is applied; future data is a forward holdout
**Date:** 2026-09-16 · **Applies to:** the Kalshi year-end ladders (`KXBTCY`, `KXETHY`) as measured in `findings/latest.json`

### Why not Benjamini–Hochberg
The quoted-edge framework does not produce a p-value per rung. There is no null
distribution behind "bid minus executable high minus fees is positive", the rungs of
one ladder are read from one chain in one instant and are not independent, and the
snapshots of one rung are a time series of the same contract. Dressing the count in
false-discovery-rate arithmetic would manufacture the independence it lacks. It is not
done.

### What is done instead
1. The current year-end universe is frozen: **44 distinct rungs** across both assets,
   as the findings file records.
2. The family size is stated with every family-level result.
3. The test is pre-declared: the executable envelope with both venues' fees, survival
   at both bracketing expiries, and — for the one rung it applies to — the local-grid
   kill test of D-092.
4. Rungs discovered later are not added to this claim set. They begin a new family.
5. Results are reported at family level, in the form "n of 44 current year-end rungs
   survived the declared test".

Data collected after this date is a **forward holdout** for these 44 rungs. For new
hypotheses the sequence is now a stated methodological principle: **discovery →
hypothesis freeze → forward, untouched test.** A hypothesis formed on data that is then
scored on the same data is a description, not a result.

## D-097 — Research Note 1 is reframed around what survives the controls, and a mostly-null result is the result
**Date:** 2026-09-16 · **Supersedes:** the framing of `drafts/RESEARCH_NOTE_1.md` as written on 2026-09-15 ("Four dollars and sixty-nine cents") · **Depends on:** D-092, D-093, D-094, D-095, D-096

The same-state question is not the flagship commercial thesis (D-091) and it is not
expanded indefinitely. It is finished, as a defensible research note.

The question the note answers: **how much apparent prediction-market / options
divergence survives execution, maturity, settlement and strike-grid controls?** The
contribution is not "we also computed options-implied state prices" — several
products already do that (D-098). The contribution is that many apparently large
cross-market discrepancies shrink or disappear when the controls are applied
correctly, and the note shows each control doing its work: the Polymarket figure that
went from 24.2% to 10.3% under the same repairs (D-085); the two of three year-end
rungs that the maturity stress test removed (D-079); the one that remains, and what the
kill test of D-092 says about it.

The note contains: the inverse-option state-price derivation; the discount convention
(D-073) and its referees (D-093); executable envelopes (D-076); fee treatment (D-077);
maturity sensitivity as a stress test (D-094); settlement semantics
(`scripts/audit_semantics.py`, D-075); grid sensitivity; family-level persistence over
the frozen 44 (D-096); explicit retractions; and the final status of "ETH above $5k"
after D-092 has run. It does not contain a forecast-quality claim — the validation
sample is nine informative independent events, and no scoring is run on it. A
mostly-null result is acceptable and is expected.

## D-098 — Competitors exist, and the novelty claim is narrowed to the discipline, not the comparison
**Date:** 2026-09-16 · **Produces:** `docs/PRIOR_WORK.md`

"Prediction-market price versus Deribit option-implied probability" is not sufficient
differentiation. The review named at least four prior or parallel efforts on the same
comparison — Fabi et al. / Fair Odds, FairOdds, PolyGap and Block Scholes — and a
permanent register is created so they are not rediscovered in six months. Each entry
carries name, URL, category, what they do, method, target user, data, strengths,
weaknesses, overlap, differentiation and the date last checked; any field that could
not be verified from the source is written `UNKNOWN` rather than guessed (rule 1).

Where the project may differ — and this is a hypothesis about differentiation, not an
established one — is in the discipline rather than the comparison: model-light
reconstruction, explicit quote-side execution bounds, refusal where no two-sided quote
exists, settlement semantics read verbatim, maturity and grid controls, adversarial
methodology, and transparent retractions. Novelty is not overstated in any document;
the register is the check on that.

## D-099 — The product is staged V0 → V1 → V2 behind evidence gates, and the research is not the Builders submission
**Date:** 2026-09-16 · **Produces:** `docs/PRODUCT_ROADMAP.md`, gates in `docs/DECISION_GATES.md`

No full cross-venue router is built. The product emerges in three stages, each of
which needs evidence before the next:

- **V0 — same-event payoff card.** BTC/ETH Polymarket price markets only. A
  Polymarket-native, ticket-adjacent utility showing the Polymarket bid/ask and fee,
  the state-price / call-spread reference, the execution envelope, the clock mismatch,
  the settlement source, a simple scenario payoff, and basis/carry fields where
  available. If product testing reaches routing, only the Polymarket leg is routed
  through the Builders framework. The words BUY, SELL, EDGE, ALPHA and ARBITRAGE do not
  appear unless literally justified, and D-095 says when they are not.
- **V1 — event hedge studio.** Adds the user's view, target, horizon, capital and
  maximum loss; perpetual/future comparison with funding and basis; options and
  spreads; scenario analysis. Output: a small set of feasible exposure structures.
- **V2 — basis-aware exposure engine.** Only after demonstrated usage of V1.
  Potential expansion from crypto to equity indices and selected commodities, with
  basis normalisation, carry, multi-venue exposure and a deeper scenario/risk engine.

The current research is the credibility and methodology layer, not the product
submitted to the Polymarket Builders programme; the preferred V0 is the payoff/hedge
card, positioned as the first module of the event hedge studio. Success there is
measured by users, repeated sessions, attributed routed trades and volume, and
conversion from comparison to execution — not by methodological sophistication,
stars, screenshots or grant acceptance. The product is not built to satisfy a grant;
it continues without one only if users value it.

The "best fit" that V1 shows means best under the user's explicit, stated constraints.
It does not mean financial advice, highest expected return, true value, or the
objectively best trade, and the interface says so where it shows it.

## D-100 — BTC and ETH remain the only measured assets; indices are gated; WTI is a research case; ETF proxies are rejected
**Date:** 2026-09-16 · **Relates to:** B-001, B-002, B-017 in `docs/BACKLOG.md`

Research production stays on BTC and ETH. Nothing is broadened for presentation value.

**Equity indices (S&P 500, Nasdaq-100)** are the next feasibility target and only
that. They are not measured until a real option-chain data path exists, the licensing
implications are understood, and settlement comparability is verified. Yahoo-quality
data is not assumed sufficient; B-017 records that the one workflow that tests the
free route has no recorded result.

**WTI / oil** is valuable as a **research case** for exposure design (D-091, Layer B)
because it exhibits a futures / crypto-synthetic basis, carry and funding, a benchmark
mismatch, and event-market thresholds. The motivating example — an economic benchmark
near 105 while a crypto-venue synthetic trades near 99, so that a short opened on the
venue starts 5–6% away from the price the view is about — is recorded in
`docs/EXPOSURE_ENGINE.md` as an **illustration supplied by the owner, not a number
measured by this repository**, which collects no oil venue. No product-grade WTI
coverage is claimed until proper listed-derivatives data exists.

**Other assets.** Single stocks: low priority. Gold and silver: later, only with
correct listed-derivative data. Rates and FX: not near-term. **ETF proxies are
rejected** where tracking error, roll, fees, dividends, early exercise or basis add
more noise than information — which closes B-002 as rejected-with-reasoning rather
than deleting it.

## D-101 — Validation thresholds are heuristics, waiting is a strategy, and the do / wait / do-not lists are written down
**Date:** 2026-09-16 · **Applies to:** `docs/RESEARCH_ROADMAP.md`, `docs/DECISION_GATES.md`

### Validation sample
Nine informative independent events is too few for any forecast-quality claim, and it
stays that way until it is not. Planning thresholds, stated as heuristics and not as
statistical laws: **exploratory** around 30–50 independent events; **preliminary**
around 100–200; **stronger publication** around 300 or more, or a sufficiently narrow
uncertainty under a pre-specified evaluation design. More important than the count:
independence of events, useful lead time, horizon diversity, an untouched holdout, and
regime diversity. Many snapshots of one contract are never counted as many events —
`scripts/inventory_validation.py` already collapses them and that stays the rule.

### Waiting
Two of the project's weakest parts improve by themselves: the 165-hour expiry band
closes when Deribit lists the weeklies straddling 1 January (expected to appear from
late November), and the validation sample grows by roughly two informative independent
events a day since the collector defect fixed on 2026-09-15. No work is done to close
the band; waiting is free.

### The lists
**Do now:** the ETH > $5k kill test (D-092); the discount referees (D-093); the
Note 1 claim freeze (D-096, D-097); this documentation.
**Do while data accumulates:** the outcome pipeline and a validation schema; the
exposure-design methodology; a minimal futures / perpetual funding ingest (a collector
change, so it is planned and asked about before it is built); cross-asset data and
licensing feasibility; limited user discovery.
**Wait:** full calibration conclusions; broad cross-asset research; any large product
build.
**Do not:** generic dashboard expansion; alerts; a broad API product; an ML prediction
engine; an "AI probability" layer; cosmetic interface expansion as a goal; SVI or any
volatility surface adopted because it sounds quantitative; replacing methodological
uncertainty with model complexity.

## D-102 — Project 3 is customer discovery only, and the portfolio is written down
**Date:** 2026-09-16 · **Produces:** the Project 3 section of `docs/STRATEGY.md`, entries in `docs/IDEA_BACKLOG.md`

A commercial-first track (Project 3) is not coded now. What is kept is a
customer-discovery backlog. The most promising problem family identified in the review
is a post-alert crypto compliance / investigation workflow — alert → evidence
gathering → transaction reconstruction → case notes → decision or escalation →
closure evidence — with a small VASP, crypto platform, fintech compliance team or
prediction-market operator as the potential buyer. Other discovery candidates:
settlement and integrity tooling for prediction-market operators; cross-venue
execution-quality analysis; collateral and settlement optimisation; stablecoin reserve
and compliance workflow; Builder attribution and economics tooling. No revenue
projection enters any decision without real buyer evidence, and no Project 3 code is
written before customer discovery has been done.

The portfolio as a whole: Project 1, on-chain and prediction-market research (wallet
behaviour, integrity, measurement, datasets); Project 2A, Divergence research; Project
2B, exposure-design research; the Project 2 product spin-off (payoff card → event
hedge studio → basis-aware exposure engine); Project 3, customer discovery only. If
only three outputs may exist in six months they are: Research Note 1; the
resolved-event dataset with its validation specification; and the Polymarket-native
payoff / hedge card MVP only if discovery supports it, otherwise an exposure-design
research note in its place.

## D-103 — ETH above $5,000 is not a surviving discrepancy: the pre-committed kill test, run
**Date:** 2026-09-16 · **Produced by:** `scripts/kill_test_eth5k.py` on the full mirror (`measure` run #25, 68 snapshots / 17 days, 2026-08-30T1611Z … 2026-09-16T1314Z) · **Record:** `findings/kill_test_eth5k.json` · **Applies the rules of:** D-092 · **Closes gate:** G1 in `docs/DECISION_GATES.md`

### The verdict, in the words D-092 fixed before the number
**Not a surviving discrepancy.** The margin against the worst local executable
estimate is positive in **0 of 62** judged snapshots (six snapshots had no Kalshi
stream or no rung and were reported, not scored). Minimum margin −0.0523, median
−0.0298. Under D-092 the rung needed to clear that estimate in at least 90% of
snapshots; it clears it in none.

### The numbers behind it, so the verdict can be checked without the JSON
Kalshi `yes_bid` on the rung ranged 0.021–0.035 (mode 0.030); net of the taker fee,
0.019–0.033. Margins per estimator, `kalshi_net − (executable high + Deribit fee on the
crossed prices)`, over the 62 snapshots:

| chain | estimator | n | positive | min | median | max |
|---|---|---|---|---|---|---|
| early (25DEC26, −165 h) | tight 4,800–5,200 | 62 | 62 | +0.0041 | +0.0092 | +0.0176 |
| early | skip-1 | 62 | 62 | +0.0085 | +0.0140 | +0.0208 |
| early | skip-2 | 62 | 62 | +0.0116 | +0.0172 | +0.0238 |
| early | one-sided 4,800→5,000 | 62 | 33 | −0.0065 | +0.0005 | +0.0110 |
| early | one-sided 5,000→5,200 | 62 | 53 | −0.0073 | +0.0032 | +0.0110 |
| late (26MAR27, +2,019 h) | tight 4,800–5,500 | 62 | **3** | −0.0156 | −0.0053 | +0.0026 |
| late | skip-1 | 62 | 31 | −0.0073 | 0.0000 | +0.0075 |
| late | skip-2 | 10 | 10 | +0.0059 | +0.0066 | +0.0090 |
| late | one-sided 4,800→5,000 | 62 | **0** | −0.0523 | −0.0298 | −0.0170 |
| late | one-sided 5,000→5,500 | 62 | 5 | −0.0164 | −0.0060 | +0.0009 |

The worst estimator was the late chain's one-sided 4,800→5,000 quotient in all 62
snapshots — a 200-dollar-wide bracket where the two legs' bid-ask spread and the
per-leg fee, both divided by a narrow width, dominate. **The verdict does not rest
on it.** The late chain's own production bracket, tight 4,800–5,500, is positive in
3 of 62 snapshots (4.8%), which fails the persistence rule on its own. The rung
survives the early chain in every estimator and every snapshot; it does not survive
the late chain's executable prices. Skip-2 on the late chain is positive in the 10
snapshots where it was quotable — a bracket 4,500–7,000 wide, which says more about
the strike spacing than about the rung (the grid sensitivity of D-079).

### What changed since the review package said "survives by about 0.4 cents"
Nothing in the data; the comparison did. The 0.4 cents was `yes_bid` against the late
chain's **mark** discounted state price (`measure_sensitivity.judge()`), with no
executable side and no option fee. Pricing the late leg at the ask one would pay,
charging Deribit's fee on the crossed prices, and charging Kalshi's taker fee turns
+0.004 into −0.005 at the median. The stress test of D-079 was a mark test; D-092 made
it an executable one, and that is the whole difference.

### Two things the record has to say so nobody reads it wrong
1. **The early-chain edge is real at quoted prices and is not a trade.** Since
   2026-09-15T2104Z a resting bid of about 50,000 contracts sits at 0.025 on the rung
   (`yes_bid_size_fp`; it was 10 contracts a day earlier). Against the early chain
   the quoted edge times that depth reads as several hundred dollars, and
   `findings/latest.json` now carries `edge_value_total` and `edge_value_max`
   figures an order of magnitude larger than the $4.69 the README quoted. That is a
   **quoted-executable discrepancy** on a chain that expires a week before the
   contract settles (D-095), and the chain that expires after it prices the same
   payoff above the bid. Neither number is a size-executable opportunity, and the
   README's "$4.69" is retired with this record rather than replaced by a bigger one.
2. **The interpolant (D-094) is reported and decides nothing.** On the newest
   snapshot: early 0.00737, late 0.02072, linear-in-time at the close 0.00837 with
   weight 0.076 on the late chain. It sits near the early value because the band is
   asymmetric; it is a sensitivity, not the settlement-date value.

### Consequences
- Family-level statement for the frozen 44 (D-096): **0 of 44 current year-end rungs
  survive the declared test** — the executable envelope with both venues' fees,
  survival at both bracketing expiries, and the local-grid kill test.
- The rung is not called a finding, alpha, a mispricing, an artefact, or noise. It is
  "not a surviving discrepancy", and the verdict's exact words are used on every
  surface (G1).
- Research Note 1 is written to this result (D-097). The README's result sentences
  are rebuilt from the new findings in the same sitting, because `check_readme.py`
  now fails on six of eight claims — the measure run that produced this record also
  advanced the archive to 68 snapshots and 17 days.
- December's weeklies straddling 1 January will let the same test run with a band of
  days rather than weeks. Nothing is built for that; it is waited for (D-101).

## D-104 — The discount referees agree with the current estimator to a basis point; the external rate does not, and is not meant to
**Date:** 2026-09-16 · **Produced by:** `scripts/discount_referee.py` on the full mirror (68 snapshots / 17 days, 2026-08-30T1611Z … 2026-09-16T1314Z; automated commit `28e2373`) · **Record:** `findings/discount_referee.json` · **Applies the rules of:** D-093 · **Satisfies:** the referee condition of G2 in `docs/DECISION_GATES.md`

### What was measured
1,426 chain-snapshots (every expiry with a two-sided chain, both currencies, every
snapshot), each with the four estimates of D-093 converted to an annual rate:

| | median over all chains | on the 18 chains seen in 30+ snapshots |
|---|---|---|
| \|R1 − R2\| (estimator consistency, marks) | 0.2 bp | ≤ 1 bp on every one |
| R1 − R3 (option chain vs its `underlying_price`) | 0.22 bp | max \|median\| 4.6 bp; ≤ 0.5 bp on every chain dated a month or more out |
| R1 − R4 (vs SOFR 3.62% flat) | +47 bp | −30 bp (ETH 30OCT26) to +118 bp (BTC 25JUN27) |

The four chains the year-end work rests on: BTC 25DEC26 R1 4.76% / R3 4.74% /
26MAR27 4.68% / 4.69%; ETH 25DEC26 3.49% / 3.48%, 26MAR27 3.68% / 3.69%. In discount
terms on the newest snapshot, ETH 25DEC26 is D = 0.98987 (R1), 0.98986 (R3), 0.99016
(R4); ETH 26MAR27 is 0.98004, 0.98002, 0.98127.

### Reading, in the order D-093 fixed
- **R2 agrees, and that is not evidence.** It is the same identity re-estimated; the
  0.2 bp says the median-of-brackets and the least-squares slope see the same chain.
  On mids instead of marks the slope is unusable on short chains (a −42% "rate" on a
  two-day BTC chain), because a one-sided quote removes a point and the remaining
  spread dwarfs the time value; on the quarterly chains mids and marks agree within
  a few bp. R2 stays labelled an estimator-consistency check.
- **R3 agrees to within a basis point on every dated chain, and this is the referee
  that matters.** `underlying_price` is Deribit's own forward for the expiry — a
  listed future or a synthetic, which of the two is still **UNKNOWN** per expiry
  (B-018) — and it is produced by a different part of the venue than the option
  marks. The two coincide on the financing rate to ~1 bp for every chain a month or
  more out. The current estimator stands.
- **R4 differs by about a percentage point on BTC and by a fraction of one on ETH,
  in both directions, and no referee is declared right.** The gap is the basis
  D-093 said to expect — coin-collateralised financing on the venue against an
  unsecured overnight dollar rate — and it is a fact about the venue, not an error
  in the estimator. It is also not the number to use here: the digital's put side is
  `D − [P(b) − P(a)]/w`, so a D taken from outside the chain would make the put side
  and the call side of the same strike disagree by exactly that basis. Only a D read
  from the chain keeps the two sides on one footing. R4 is kept as the distance
  from a money-market rate and nothing else.
- **Short chains are noise, and are expected to be.** On the 37 chains seen in
  fewer than 30 snapshots — dailies and near-weeklies — \|R1 − R3\| reaches 511 bp
  and the rates themselves range from 2% to 10%. At T of a few days, 1 − D is
  smaller than a tick, which D-073 said: a 500 bp error in the rate at T = 0.005 y
  is 0.00025 in D. The intraday tenor's D is therefore effectively 1 whatever the
  referees say, and the year-end tenor's D is the one the referees confirm.

### What this changes
- Nothing in the numbers. The kill test of D-103 is on a call-side rung (ETH 5,000
  sits above the forward on both chains), whose discounted state price is a call
  spread over its width and contains no D at all. Put-side rungs move by
  (D_R4 − D_R1) ≈ 0.0003 on the December chain if R4 were used, and it is not.
- G2's referee condition is met: D has a referee that agrees, an external rate that
  disagrees for a stated reason, and a per-expiry UNKNOWN that a futures stream
  would settle. G2 itself stays open on the analytical freeze and the note.
- The external rate stays a dated constant (SOFR 3.62%, as of 2026-09-14, entered
  2026-09-16). It is refreshed by hand when it is refreshed, and its date travels
  with every number it touches.

## D-105 — The exhaustiveness check was summing things that are not partitions; one event per series, and only ladders that tile
**Date:** 2026-09-16 · **Produced by:** `scripts/measure_band.py` (`event_ladder()`, `ladder_shape()`), `scripts/measure_exhaustive.py`, `scripts/write_findings.py` · **Type:** pipeline defect, found and fixed; wrong numbers reached the screen · **Tests:** `LadderShapeAndEvents` in `tests/test_measurement.py`

### What was on the screen
From the automated findings of 2026-09-16, `exhaustiveness_constraint` read
`corrected` mean 2.479, max 76.1, departure **+147.9%**, and the intraday band block
read `mean_density` 1.1624 against a mean D of 0.9999. Both were wrong, and both
sat where `web/index.html` reads them. Rule 6: a wrong number on screen is the
worst kind, and this record exists so the reason is not lost.

### Why
On 2026-09-15 (commit `31a2eab`) the intraday series joined `SERIES`, including
the cumulative ladders KXBTCD / KXETHD. `rungs()` in `measure_band.py` knew they
were cumulative and refused to sum them. `measure_exhaustive.ladder_sum()` did not
know: it summed every active market of every series in `SERIES`, so ten ladders of
overlapping P(S > K) rungs contributed sums of 5 to 76.

Underneath that was a second defect that the first one hid. A series is not a
ladder. The collector's open pass returns one page of 200 open markets per series,
and for the intraday series that page spans **two events** — in the
2026-09-15T2104Z snapshot, 120 rungs of KXBTC closing at 22:00 and 80 of the event
closing 21:00 the next day. Both scripts took all 200 as one ladder under the first
market's close: `ladder_sum()` summed both events (ratio 1.78), and `rungs()` judged
the second event's rungs against an expiry and a gap chosen for the first.

And underneath that, a third: the 120 rungs of the first event are not the whole
event. The archived ladder runs `less` to 68,200, then `between` from 75,000 up to
86,800 and `greater` above it — the middle is missing, cut by the same 200-market
page. Its sum is 0.78 of D, not because the digitals are wrong but because the
archive holds a ladder with a hole in it. Summing that is not a check of anything.

### The fix
`event_ladder(KA, series)` returns the active markets of the earliest-closing event
and the number of events present; both scripts use it, and `rungs()` reports
`events_in_series`. `ladder_shape(M)` names the ladder `cumulative` (all `greater`),
`exhaustive` (one open end each side and every ceiling equal to the next floor under
the boundary rule of D-067), or `incomplete` with the number of breaks. Only an
exhaustive ladder is summed; the other two are counted in
`ladders_set_aside` and printed by name. On the public 14-day window the constraint
now reads `corrected` mean 0.9977, min 0.9945, max 1.0000, departure −0.2% over 97
ladders, with 10 cumulative and 7 incomplete set aside; the intraday block's
`mean_density` reads 0.9961. The year-end numbers did not move — one event per
series, complete ladders, under 200 markets — and neither did the kill test or the
referees, which never read a ladder sum.

### What is not fixed, and is written down instead
- Whether the open pass truncates a single intraday event is now visible
  (`incomplete`, with breaks) but not cured: curing it means the collector asking
  for more than one page of open markets, which changes what the archive holds and
  is the owner's call. Logged as B-022. Until then an intraday exhaustive ladder is
  summed only in the snapshots where the archive holds all of it (7 of 48 in the
  public window are incomplete; the rest were cumulative or complete).
- `ladder_sum()` still chooses its expiry by date, not by instant, unlike `rungs()`.
  For a partition test the expiry does not matter — a partition sums to D on any
  chain — so it is left as it is and noted.
- The intraday band block's `percent` changes by dropping the second event's rungs
  (17.3 on the mirror before the fix; 15.6 on the public 14-day window after it —
  two different bases, and the mirror's value follows at the next `measure` run);
  that block is not on the README and is not part of any claim. Its
  `expiry_gap_hours_median` now describes the event actually judged.

## D-106 — Resolved-event capture is reliable for the fifteen-minute series and structurally absent for the hourly ladders; the validation specification is opened
**Date:** 2026-09-16 · **Produced by:** `scripts/inventory_validation.py` and a count over the public window (`collector/collect.py` unchanged) · **Produces:** `docs/VALIDATION_SPEC.md` (DRAFT v0) · **Roadmap step:** 4 of D-091's order

### What was checked
Whether a market seen live with a two-sided quote is later seen resolved, so that
Note 2 could pair a price with an outcome. On the public 14-day window, for markets
whose close lies more than 24 hours before the last snapshot: KXBTC15M 40 of 40,
KXETH15M 39 of 39, KXBTCPRICE 1 of 2 (the other `closed`, pending settlement, not
lost). The archive-wide inventory reads 5,041 resolved markets, 157 with a prior
quote, 121 independent events, lead median 6.87 h.

### What was found
For the hourly ladders — KXBTC, KXETH and their cumulative twins KXBTCD, KXETHD —
every snapshot holds 1,000 rows `initialized` and 200 `active`, and **no resolved
row at all**. The main pass fetches 5 × 200 rows with no status filter and the API
fills them with not-yet-open hourly markets (200-plus rungs per future event, days
listed ahead); the settled ones are never reached, and the open pass adds live
quotes only. So the tenor with the tight expiry match — the natural Note 2 sample —
has prices in the archive and no outcomes. The fifteen-minute series escape this
only because their future rows are few (59) and their settled rows fill the page;
the row order that makes this work is not documented and is not relied on.

### Decisions
- Outcome capture is **reliable** for KXBTC15M / KXETH15M and the small monthly and
  yearly series, and **absent** for the hourly ladders. Both statements go in the
  specification with the numbers behind them.
- The cure is a collector change — an additional pass for the truncated series that
  asks for settled markets, whose exact parameters are `UNKNOWN` until Kalshi's
  documentation is read — and it is **asked for, not made**: B-023. The collector is
  not touched in this sprint, by the working rule.
- `docs/VALIDATION_SPEC.md` is opened as DRAFT v0: unit of analysis (independent
  event), the capture table above, six requirements R1–R6 with their measured
  status, and the list of design choices that will be frozen before any holdout is
  opened (scoring rules, the option-derived quantity, lead-time bins, independence,
  the holdout split, the D-101 thresholds). Nothing in it licenses a score; the
  freeze is a later record with a version number.
- The roadmap's "nine informative independent events" is retired: the inventory now
  counts 121 independent events on the public window, most of them fifteen-minute
  markets quoted a median of eleven minutes before settlement, and whether those
  are forecasts at all is a question for the frozen design, not a number to quote.

## D-107 — Note 1's analytical specification is frozen at v1
**Date:** 2026-09-16 · **Produces:** the "Frozen specification (v1)" table in `docs/RESEARCH_ROADMAP.md` · **Roadmap step:** 5 of D-091's order · **Gate:** G2's freeze condition

### What is frozen
The claim set (the 44 year-end rungs, D-096), the unit and the persistence rule, the
option-side quantity and its discount factor with referees, the five controls in
order — execution, maturity, settlement, grid, and the pre-committed kill test — the
second-venue and touch-bound treatment, the absence of a multiplicity correction, the
one-event-per-series exhaustiveness rule (D-105), the terminology (D-095), and the
two lists of what the note may and may not claim. Each row names the script and the
findings file that produce its number.

### What freezing means here
- Re-running the same lines on a longer archive — including December's weeklies
  straddling 1 January, which turn the maturity band from weeks into days — is a
  re-run of v1. The numbers may change; the specification does not.
- Changing any row is v2, under a new decision record that says what changed and
  why. A change made after looking at a result, to improve the result, is the thing
  this record exists to make visible.
- The draft at `drafts/RESEARCH_NOTE_1.md` is written to this specification. G2's
  remaining conditions are mechanical: green checkers and reproduced numbers.

### Why now and not earlier
The specification could not be frozen before the kill test ran (D-103) and the
referees reported (D-104), because both were open questions about which controls
belong in the list. With the verdict "not a surviving discrepancy" and a discount
factor its referees agree with, the list is complete for the question Note 1 asks.

## D-108 — The exposure engine's first worked example is specified before it is computed
**Date:** 2026-09-16 · **Produces:** `docs/EXPOSURE_ENGINE.md` §5 (methodology v0.1) · **Roadmap step:** 6 of D-091's order · **Gate:** the precondition of Note 4's gate and of G6

### What is fixed
One BTC view — "above K on 1 January 2027", K taken from the Kalshi year-end ladder
so that a binary at that threshold exists — expressed four ways: the Kalshi binary,
a Deribit call spread K / K+w on each of the two bracketing chains, the Polymarket
touch at K (present and flagged as a different payoff class, never compared as
equal), and a long perpetual (present and `UNKNOWN` in every field until B-019). The
eight layers are applied row by row with what the archive supplies today named and
every gap written as the word `UNKNOWN`. Scenarios are six named terminal prices;
the maturity gap of the chains is shown as two columns, not interpolated (D-094).

### Why specify before computing
The engine's risk, stated in the review, is that it reproduces the textbook answer
— binaries are cheap carry and expensive convexity — and dresses it up. Fixing the
instruments, the layers, the scenarios and the allowed conclusions before any number
exists is the only way to tell that outcome from a chosen one. If the example shows
nothing beyond the textbook answer, Note 4 says so and stops.

### What is not decided
No rate for the binary's collateral cost (a dated constant if entered, else
`UNKNOWN`); no perpetual venue; no engine code. The example reuses
`measure_band.rungs()`'s executable envelope and `fees.py` rather than re-deriving
either.

## D-109 — V0 requirements are defined in four groups, and two of them are not ours to answer
**Date:** 2026-09-16 · **Produces:** `docs/PRODUCT_ROADMAP.md` "V0 requirements" · **Roadmap step:** 7 of D-091's order, the last · **Gate:** G4's first condition

### What is defined
Six functional requirements the pipeline already satisfies (one card per market,
the state price with its envelope and expiry side, the market's own fee schedule,
touch markets get a bound not a reference, unresolvable rungs say so, every number
traces to a script and a stamp); six non-functional ones that hold whoever the user
is (freshness and staleness, no number without its envelope, `UNKNOWN` as a value,
the forbidden words, no arithmetic in the browser, no numbers in the interface);
five discovery questions (Q1–Q5) that need a named person; and three data-rights
questions (R1–R3) that need a reading of Deribit's, Polymarket's and — for anything
later than V0 — Kalshi's terms.

### What is decided
- The card is built against `findings/latest.json` in the pattern of `web/index.html`;
  it computes nothing (working rule 5). This makes group A true by construction and
  means the card cannot drift from the research.
- Group C (Q1–Q5) is not answered by hypothesis. The repeated-job hypothesis stays
  written as a hypothesis until a user says it in their words (D-099).
- Group D (R1–R3) is not answered by reading here: the Builders terms and the Kalshi
  Developer Agreement are unread, and the Deribit position in `DATA_SOURCES.md`
  says a product changes the analysis. Those readings are the owner's, and the card
  is not shown to anyone before them.

### What this closes
D-091's seven-step order. Steps 1–7 each have a record: D-103 (kill test), D-104
(referees), D-097 with the rewritten draft (findings language), D-106 (outcome
capture), D-107 (Note 1 frozen), D-108 (exposure example), D-109 (this). What
remains open is listed in `DECISION_GATES.md` and `BACKLOG.md`, not here.

## D-110 — The owner supplied the URLs; three of the four exist, and one of them states our premise in public
**Date:** 2026-09-16 · **Supersedes the NOT FOUND status of:** entries 1 and 3 in `docs/PRIOR_WORK.md` · **Narrows:** D-098 · **Closes:** B-021

D-098 narrowed the novelty claim to the discipline rather than the comparison, and
said so as a hypothesis with the register as its evidence. Three of the four names in
the review synthesis could not be found on 2026-09-16 and were recorded as NOT FOUND
rather than assumed (B-021). The owner then supplied the URLs. They exist. Reading
them costs us part of the hypothesis, and this record is where that is written down.

### What the pages say, read 2026-09-16
**The paper is real.** Fabi, Schönleber, Ruffo and Marfè, SSRN 6565258.

> **CORRECTED 2026-09-18.** This paragraph originally read "the synthesis had the
> title wrong" and named "Market Efficiency in Prediction Markets" as the real
> title. That was our error, not the synthesis's. The owner supplied the PDF on
> 2026-09-18 and its own first-page footnote settles it: *"This paper previously
> circulated as ‘Market Efficiency in Prediction Markets: A Comparison with
> Derivatives’."* The current title is **"Cross-Market Pricing in Prediction
> Markets: A Comparison with Derivatives"**, dated 31 August 2026 — exactly what the
> synthesis said. Both titles are real; we read the older one in a search listing
> and assumed the newer one was invented. Corrected in place rather than rewritten
> away, because the mistake is the same class the register exists to prevent:
> asserting from a second-hand source. The SSRN page was behind a bot check on 2026-09-16 and the entry was
written second-hand. **That is no longer the case:** the owner supplied the 95-page
PDF on 2026-09-18 and it has been read. It compares Polymarket BTC and ETH
prices against option-implied risk-neutral distributions across **nearly 5,000
contracts**, and reports that prices broadly track the benchmark while deviations
**concentrate in tail and barrier contracts** and vary with sentiment, volatility and
frictions.

That last clause is the uncomfortable one. Our own three persistent rungs were all
tails — BTC above $150k, ETH above $5k, ETH below $1k — and we reported that as an
observation. A published paper reports the same concentration on a sample two orders
of magnitude larger. Note 3 in `docs/RESEARCH_ROADMAP.md` ("do prediction markets
exhibit a persistent long-shot premium?") is therefore not an open question we are
first to ask; it is a question with prior work that we have not read in full.

**PolyGap is real and is a live paid product.** `polygap.io`, read at 18:57 UTC.
It prices every Polymarket crypto market against Deribit, refreshes every two
minutes, sells a $30/month tier in USDC with a REST API, Telegram alerts and two
bots that trade the user's own wallet. Its method is parametric and stated plainly on
the page: implied volatility by strike and expiry, **N(d₂)** for "above $X" and **a
barrier model** for "hit $X".

**Block Scholes' July report derives the binary from a call spread.** Entry 4 already
recorded the firm as parametric on the strength of its SVI surfaces. The report says
something else as well, in the plainest possible words: *binary option prices, and
therefore the prices of prediction markets on the same underlying, are uniquely
determined by the prices of vanilla call options*, and it then walks the reader
through building the binary out of a call spread. That is our Layer A premise,
published by an institutional analytics firm on 2 July 2026, months before this
record.

**And the executable framing has prior work too.** Not surfaced by the owner but
found while reading: Gebele, Mutzel and Matthes, **"Executable Arbitrage and Market
Efficiency in Prediction Markets"** (arXiv 2608.00666, 1 August 2026), which separates
payoff-space no-arbitrage from **protocol-executable** no-arbitrage and reconstructs
**depth-aware executable portfolio values**. Different comparison — Polymarket's own
negative-risk markets, not options — but the same instinct, named in the title, and
executed with depth rather than top of book.

**And the three-venue setup has been done as a thesis.** De Stefano, LUISS,
`btc-prediction-market-efficiency`: Polymarket, Kalshi **and** Deribit, 33,107
observations over March 2024 – June 2026, benchmark Φ(d₂) from DVOL. Parametric,
spot-based rather than chain-based, no fees and no executable side — but the venue
triple and the framing are ours.

### What this costs the differentiation hypothesis
D-098 listed seven things as the possible difference. After reading:

| claim | status after 2026-09-16 |
|---|---|
| model-free spread digitals | **weakened.** Block Scholes states and derives it publicly. What is left is that we *only* do this, where they also sell a surface. |
| | *(2026-09-18: unchanged by the paper — Fabi et al. do not use a spread digital at all. Their option side is a **Kou double-exponential jump-diffusion** calibrated to **fixed-delta implied-volatility surfaces bought from Amberdata**, not a chain. That is further from a spread digital than Block Scholes, not closer.)* |
| quote-side executable envelopes | **weakened, not removed.** Gebele et al. do depth-aware executable reconstruction on a different comparison. No entry in the register does it on the options-versus-prediction-market comparison. |
| | *(2026-09-18: **strengthened** by reading the paper and the product. Both say in their own words that the option side is not executable — the paper interprets wedges "rather than automatically as exploitable arbitrage profits", and fairodds.io states "The resulting OIP is a maturity-aligned benchmark price — not an executable option quote." The word "executable" is still not ours alone; the measurement on this comparison still is.)* |
| both venues' fee schedules, per-order rounding | **stands.** No entry evidences fee-schedule modelling. |
| expiry-gap and strike-grid sensitivity | **stands.** No entry evidences either. |
| verbatim settlement audits | **stands.** No entry evidences reading resolution text. |
| refusal where no two-sided quote exists | **stands.** |
| recorded retractions | **stands**, and is the one nobody can copy cheaply. |

Three of seven weakened; none of the seven is fraudulent; the honest summary is that
**the comparison is not ours and the controls may be.** Any sentence in this
repository that implies otherwise is to be changed on sight, including in Research
Note 1, whose related-work paragraph must now cite these entries rather than describe
an empty field.

### What is not concluded
That Divergence is redundant. PolyGap sells a signal built on N(d₂) and a barrier
model and calls the options side "the sharp read" that "is usually the one that's
right"; this project spent four weeks establishing that the same comparison, done at
executable prices with both fee schedules, produces **nothing** on the family it
declared. Those are different claims about the same data, and the second one is the
one we can defend. That is a smaller position than "we built the comparison" and it
is the true one.

### Consequences
- `docs/PRIOR_WORK.md` entries 1 and 3 are replaced with what the pages say;
  entry 2 records that the synthesis's "FairOdds" resolves to two different sites,
  one unrelated and one that did not respond; entries 4, 9 and 10 are added or
  extended. B-021 is closed.
- **2026-09-18: fairodds.io is up, and it is the same team.** The site is built by
  the paper's authors — the two contact addresses are Schönleber's company
  (ZoQuant Solutions UG) and Ruffo's — and it states that it "adapts the framework
  developed in" the paper. Register entries 1 and 2 describe one thing, not two,
  and are merged. Its live board carried its own staleness banner on the read date
  (last market update eight days earlier), and its comparison is struck against the
  **YES midpoint**. It publishes no fee treatment; the word does not appear on its
  methodology page.
- `fairodds.io` returned **504 Gateway Time-out** on two attempts at 19:0x UTC on
  2026-09-16. The domain is confirmed by the owner; the product is UNKNOWN. It stays
  in the register as unreachable rather than as absent, and is re-checked before Note
  1 publishes (G2).
- Note 1's related-work paragraph is a publication-gate item under G2, not a
  cosmetic edit.
- Reading the Fabi et al. paper in full is a prerequisite for Note 3, not for Note 1.
  Logged as B-025.

## D-111 — Perpetual funding is archived as an hourly history from Deribit, re-asked with overlap, after the synchronous reads
**Date:** 2026-09-18 · **Approves:** B-019 (owner's approval of 2026-09-18) · **Produced by:** `collector/collect.py` (`funding()`), `docs/DATA_SOURCES.md` §1a, `docs/ARCHIVE_SCHEMA.md` · **Archive version:** 5 → 6

### Scope
Ingest only: the funding rate of the BTC and ETH perpetuals into `raw/funding/`, and
its documentation. No carry computation, no exposure engine, no change to
`measure.yml`, nothing on the page. The measured universe is unchanged (D-100).

### Venue
Deribit. It is the venue whose option chain the whole comparison rests on, so its
perpetual's funding is the carry that an exposure comparison against that chain
would actually face; its premium is measured against the same Deribit index the
digital is priced on; it needs no key; and its terms are already quoted and taken a
position on (`DATA_SOURCES.md`, *Data rights*) — no new terms enter the project.
Other venues' perpetuals are a different basis and are not collected.

### Endpoint
`public/get_funding_rate_history`, per instrument, `BTC-PERPETUAL` and
`ETH-PERPETUAL`. Read in the documentation and tried on 2026-09-18 (quoted in
`DATA_SOURCES.md` §1a): hourly points with `timestamp, index_price,
prev_index_price, interest_1h, interest_8h`. The instantaneous fields in
`public/ticker` (`current_funding`, `funding_8h`) are not used: sampled three times a
day they are three points, not a history, and the three instants are not aligned
with anything. `public/get_funding_rate_value` returns one aggregate number for a
window and loses the hours. The history endpoint is per instrument and returns the
perpetual only — no dated future comes with it, so B-018 is untouched.

### Sampling — a history independent of the collector's cadence
Every run asks for the last **48 hours** ending at the run's instant. Points are
hourly, so a run returns about 48 rows per instrument and a run every eight hours
sees each hour about six times. The overlap is the point: a missed run leaves no
hole, and up to five consecutive missed runs (40 hours) leave none either. The cost
is a few kilobytes per run. Readers de-duplicate on `timestamp`; the archive does
not, because the archive stores what came back (rule 2).

The reason for 48 rather than the owner's example of 24: 24 hours survives one
missed run and not two, and the collector has missed runs before (the paging cap
of 2026-09-15 was a silent miss of a different kind). The difference in storage is
nil.

### Placement — after the synchronous reads
The stage runs **after** `kalshi`, in the same region as `flow` and `holders`.
`WINDOW = MARKS['polymarket_end']` — the Deribit-to-Polymarket drift the whole
comparison depends on, 0.66–2.04 s to date — is not touched and not redefined. The
stage gets its own mark, `funding_end`, so its latency is visible in
`source_marks_seconds`. After the first run under this version,
`sync_window_seconds` is compared with the previous runs; a visible widening is a
stop condition.

### What is stored
`raw/funding/YYYY-MM-DD/funding_<STAMP>.json.gz`, one file per run, gzipped JSON in
the layout of the other streams:

```
{ "BTC-PERPETUAL": { "request": { "method", "start_timestamp", "end_timestamp" },
                     "response": <the JSON-RPC envelope exactly as returned> },
  "ETH-PERPETUAL": { ... } }
```

The response is stored whole — envelope, `usIn`/`usOut`/`usDiff`, `testnet`, every
element with every field. No field is dropped, so the D-087/D-088 question does not
arise. `request` is ours: it records the window asked for, which the response does
not carry, so a reader can tell "no points" from "not asked".

`_meta` gains `funding_summary` (points returned per instrument, and the window
asked for) so a run that returned nothing is visible without opening the file.
`state/latest.json` gains `funding` in `paths`, because that block's stated purpose
is "the newest snapshot of each stream" and a reader should not have to list a
directory to find it; it is **not** added to the pointer's required-streams check,
because the page does not read it and a funding failure must not mark the pointer
broken.

### What stays UNKNOWN, on purpose
The unit and sign convention of `interest_8h` / `interest_1h` as returned; whether a
point's hour ends or begins at its `timestamp`; whether `start_timestamp` is
exclusive (one call suggests so); the endpoint's public rate limit. All four are
written in `DATA_SOURCES.md` §1a and none is assumed in code. The first consumer of
this stream (the exposure engine's worked example, D-108, layer D) has to state its
reading of them before it uses a number.

### Terms
The Deribit Terms of Service quoted in `DATA_SOURCES.md` restrict redistribution of
"market data and/or derived data" to personal use, and that clause already governs
the option chain in `raw/deribit/`. The funding stream is the same class of data
from the same venue under the same clause; the position recorded there (research
use, the rolling public window, the private mirror) is applied to it unchanged. The
owner's stop condition named "terms that restrict redistributing this data": the
restriction is not new and was already decided, which is why this record proceeds
and says so rather than stopping — if the owner reads it differently, the stream is
one commit to remove.

### Tests
`FundingStage` in `tests/test_measurement.py`: the window asked for is 48 hours
ending at the run instant and both instruments are requested; the response is
stored as received; the archive version is 6. The `tests.yml` floor rises with them.


### The stop condition fired on the first run, and it was the condition that was wrong
**Added 2026-09-18, after the 13:01Z run — the first under archive version 6.**

The funding stage itself is clean: `raw/funding/2026-09-18/funding_2026-09-18T1301Z.json.gz`,
48 hourly points per perpetual, both instruments, `funding_summary` as specified, no
errors, `version` 6, the pointer carrying `paths.funding`.

But `sync_window_seconds` came back **3.29 s**, outside the "0.66–2.04 s to date"
written above, so the run was stopped and reported.

**The mechanism rules the stage out, and the code is where that is settled.** In
`collect.py`, `WINDOW = MARKS['polymarket_end']` is assigned on line 277; `kalshi` runs on
278 and `funding` on 304. The window is closed before the funding stage is reached, so
nothing that stage does can widen it. On this run funding took 0.41 s and finished at
56.4 s — fifty-three seconds after the window had been measured.

**The archive says the same.** Across the 48 runs in the public window:
minimum 0.62 s, median 1.19 s, p90 1.93 s, maximum 3.29 s. The two widest share a
signature — Deribit normal, Polymarket slow:

| run | window | deribit | polymarket | version |
|---|---|---|---|---|
| 2026-09-18T1301Z | 3.29 | 0.95 | **2.34** | 6 |
| 2026-09-13T1311Z | 2.68 | 0.97 | **1.71** | 3 |

The second predates the funding stage by five days.

**So the rule was wrong, not the run.** "0.66–2.04 s to date" was already false when
it was written here: the 2.68 s run of 2026-09-13 was in the archive at the time. A
threshold that history has already crossed fires on ordinary noise, which is what
happened. The range in `docs/ARCHIVE_SCHEMA.md` carried the same error and is corrected
there as a dated distribution.

**The condition is restated, for this stage and any stage added after the window:**

1. A stage placed after `MARKS['polymarket_end']` cannot affect the window. The check
   is the placement, and it is a line number, not a measurement.
2. What is worth watching is whether the *distribution* of `polymarket_end` shifts, not
   whether one run exceeds a number. A single observation above a previous maximum,
   with the venue breakdown showing which side was slow, is a latency event and is
   recorded as one.
3. A stage inserted **before** that mark is a different matter and would need the
   window re-measured across several runs before it stayed.

D-111 is otherwise unchanged. No further run was scheduled to settle this, because
another observation cannot discriminate: a fast next run would not clear a stage the
placement had already cleared, and a slow one would be another Polymarket latency
event. Watching it would have been asking a question whose answer was already fixed.
## D-112 — The repository has two audiences, and only one of them should be reading the internal file
**Date:** 2026-09-18 · **Changes:** `README.md`, `docs/COMPETITORS.md` → `docs/PRIOR_WORK.md`, removal of `drafts/REVIEW_PACKAGE.md` · **Changes no number, no limitation and no claim**

### The problem
This repository is public and is shown to people deciding whether to work with the
author. It had been written for one audience — whoever picks the work up next, and
the reviewers the work was sent to — and it showed. Two documents in particular were
addressed to a reader who is not the one arriving:

- `drafts/REVIEW_PACKAGE.md` opens "For: independent reviewers (including other AI
  systems)", asks them to "be specific and adversarial", and contains a section
  headed "Known weaknesses, stated before you find them". It was written to be
  attacked. Handed to a reader who did not ask for it, it is a list of flaws with no
  question attached.
- `COMPETITORS.md` is, in substance, a prior-work survey. The filename says
  competitive intelligence, and two rows in it score points rather than record
  evidence.

### What was done
The review package is removed from the repository and kept outside it. It is still
sent to reviewers as a file; it is simply not the front page of a public project.
The register is renamed `docs/PRIOR_WORK.md` — which is what it is, and what the
academic convention calls it — and two evaluative rows are rewritten as observations.
The README gains a short reading order and its "Known gaps" heading becomes "Scope
and limitations", which is the ordinary name for that section in any research
repository.

### What was NOT done, and this is the part that matters
**Nothing about the result was softened and nothing about the limitations was
removed.** Specifically, all of the following stay exactly as they were:

- the verdict: 0 of 44 rungs in the declared family survive the full test (D-103)
- the validation sample: nine informative independent events, and no scoring
- the concession that the comparison is not ours — Block Scholes published the
  call-spread derivation, Fabi et al. measured it on 4,860 contracts, PolyGap sells
  it (D-110)
- "What else exists" in Research Note 1
- every retraction in this log, including D-090 and the correction inside D-110

The reasoning is not modesty. It is that the prior-work register is the *evidence*
that nothing here was taken from anyone, and a reader who cannot find it will ask
the question the register answers. And a project that claimed a surviving edge would
be making the claim everybody makes and nobody supports; the defensible claim is the
one this project can actually demonstrate — that the apparent edge did not survive a
test written before the result was known.

If a future edit removes a limitation in order to look better, this record is the
one it contradicts.

### Not changed
`drafts/` keeps its name. Note 1 is frozen at v1 (D-107) and G2 has not passed, so
the folder is accurate. Renaming it to `research/` while the publication gate is open
would be the first small overclaim, and the README says where the note stands
instead.

## D-113 — The terminal gets a plain URL; the README gets a picture of it, the badges, and nothing else
**Date:** 2026-09-18 · **Anchored to:** D-112 — nothing below changes a number, a limitation or a claim · **Changes:** `.github/workflows/pages.yml` (new), `README.md`, `web/terminal.png` (new), repository settings (Pages, homepage, Wiki and Projects tabs), one status line each in `docs/PRODUCT.md` and `docs/DESIGN.md`

### The publication decision
`web/index.html` has been reachable only through an htmlpreview link. GitHub Pages
is switched on, with the owner's approval, and serves the page at
`https://denizergingunduz.github.io/divergence/`. The repository is already public
and the page reads only files that are already public in it
(`raw.githubusercontent.com` and the contents API), so the site exposes nothing that
was not exposed before; what changes is that a visitor can open the terminal without
a workaround. That is still a publication decision, which is why it has a record.

### How it is served, and why that way
By a workflow (`pages.yml`) that uploads `web/` alone, not by serving the repository
root or `docs/`. Serving from the root would hand Jekyll the entire repository —
the decision log, the rolling `raw/` archive of gzipped vendor payloads, the tests —
and copy it to a public site as if it were meant to be browsed there. Uploading
`web/` publishes exactly one file. A redirecting `index.html` at the root would have
been one more file at the top of the tree that has nothing to do with the work. The
workflow runs only when `web/` or itself changes; the three daily archive commits do
not redeploy anything, because the page reads the archive live.

### What the README gains
A screenshot of the running terminal (`web/terminal.png`, taken 2026-09-18 from
snapshot 2026-09-18T0504Z, captioned with what it shows and nothing more), the CI
badges for `tests` and `ref-check` (they say the checks are real, and in this
repository the checks fail builds), and the site link. The count of `measure.yml`
steps in the status section is corrected from eleven to thirteen — two steps were
added on 2026-09-16 (D-103, D-104) and the sentence was not updated.

### What the two older documents gain
`docs/PRODUCT.md` and `docs/DESIGN.md` describe the research screen as it stood on
2026-09-14 and cite the numbers of their own decision records, some of which have
moved since (the "2 of 26" of D-066 is now "3 of 44 at quoted prices, 0 of 44 under
the full test", D-103). Each gets one status line at the top saying what it describes,
when, and where the current numbers live. Neither is rewritten and neither is
deleted: the design language and the screen's reasoning are still the ones in use.

### What was deliberately not done, per D-112
No number moved. No limitation was removed or softened: the nine informative
independent events, the 0 of 44, the prior-work concession and every retraction
stay as written. No section was added that praises the project; the picture, the
badges and the link are things a visitor can verify, not things they are asked to
believe. The empty Wiki and Projects tabs are switched off because an empty tab is a
promise of content that does not exist.

## D-114 — The buyer's comparison: for the same condition, which venue is cheaper to buy it on, and does the answer depend on the condition
**Date:** 2026-09-24 · **Asked by:** the owner, 2026-09-24 · **Produces:** `scripts/measure_payoff.py`, `findings/payoff_frontier.json`, the `payoff_frontier` block of `findings/latest.json` · **Gate:** an input to G4 (V0), nothing more · **Builds on:** D-108 (the worked example), D-092/D-103 (the kill test), D-095, D-096

### The question, and why it is not the kill test again
Every test so far asked an arbitrageur's question: sell one venue, buy the other, pay
both sides' costs — is anything left? D-103 answered it: nothing survives. The owner's
question on 2026-09-24 is a different one. Someone with a view does not trade both
venues; they buy the condition they believe in on ONE of them, and pay one side's
costs. For that person the question is not "is there a spread to capture" but "for
the payoff I want, which venue sells it cheaper". The arbitrage test cannot answer
that: a gap that is smaller than two sides' costs can still be larger than one.

So this record asks: **for each condition on the year-end BTC and ETH terminal price,
is buying it on Kalshi or buying the same payoff from the Deribit option chain
materially and persistently cheaper — and does the cheaper venue change from one
condition to another?** If it never changes, a product built on the comparison is a
one-line rule and not a product. If it does, the comparison carries information and
G4 has an input. That is the whole reach of the answer.

D-108 specified one row of this — one view, four instruments, every layer. This record
is the screen before it: across the whole ladder, on executable prices only, is there
any row where the choice of venue is not obvious in advance?

### The family
The two year-end ladders of D-096's family, `KXBTCY` and `KXETHY`, in every snapshot
where they are exhaustive (D-105). The conditions, each identified by asset, kind and
edges so that the same condition is followed across snapshots:
- every bucket as listed — "the terminal price is in [lo, hi)", including the two
  open-ended rungs;
- for every internal boundary K of the ladder, "above K" and "below K".

A condition on Kalshi is bought as the ladder sells it; the options side replicates
the same terminal payoff. Nothing outside these ladders is judged. The Polymarket
ladders, the intraday series and every other asset are not in the family (B-026).

### What a condition costs on each venue — per dollar of payoff, at the best level
**Kalshi.** The cheapest of the ways the ladder offers at the top of the book: the sum
of the YES asks of the buckets that make up the condition, each plus
`fees.rate(ask)`; or, when the condition is the complement of a single bucket, that
bucket's NO ask plus `fees.rate(no_ask)`. Depth is the smallest resting size among
the legs used. The taker fee's per-order round-up is not in the per-dollar cost; it
is in the reference ticket below, where an order size exists.

**Deribit.** The same payoff built from vertical spreads, priced at the side one would
actually hit — the ask on every leg bought, the bid on every leg sold — plus Deribit's
fee on those crossed prices (0.03% of the index, capped at 12.5% of the option
price), exactly as `kill_test_eth5k.estimate()` charges it:
- "above K": the call spread over the bracket around K when K is at or above the
  forward, otherwise the discount factor D held and the put spread over the bracket
  sold — the same side rule production uses (D-025, D-032);
- "below K": the mirror of that;
- a bucket: above its lower edge bought, above its upper edge sold, on the same
  estimator and the same chain.

### The band on the options side, and why a single number is refused
Two approximations sit under every option price here and both are measured, not
assumed away: the strike grid (D-079; a median sensitivity of 11.5% on the year-end chain, D-084)
and the expiry that is not the settlement date (the early chain is about 165 hours
before the Kalshi close, the late one months after). So the options cost is an
interval, not a point: the cheapest and the dearest of the tight and the one-skip
brackets (`measure_sensitivity.wide_bracket`, skip 0 and 1) on both bracketing chains
(`measure_sensitivity.neighbours`) — up to four estimates. The two-chain band is the
stress test of D-094, not a bound; it is used here as the conservative side of the
comparison, which is what it is for.

### When one venue counts as cheaper — the thresholds, fixed before any number
In one snapshot a condition is:
- **cheaper on Kalshi** when the Kalshi cost is below the CHEAPEST options estimate by
  at least 10% of the Kalshi cost and by at least 0.001;
- **cheaper on Deribit** when the DEAREST options estimate is below the Kalshi cost by
  at least 10% of that estimate and by at least 0.001;
- **indistinguishable** otherwise;
- **unquoted** when either side has no two-sided price, a leg is outside the strike
  range, or the chains do not straddle the close. Unquoted is a refusal, not a tie,
  and is not counted as judged.

Why these numbers. 0.001 is the price step the year-end ladders publish in
`price_ranges` (D-078's reading: one uniform 0.0010 step on these ladders), so a difference smaller
than one step is not a difference a buyer can act on. 10% because the options interval
already contains the grid and the maturity approximations, and what it does not
contain — the settlement basis (D-075, `measure_basis.py`), the drift inside the sync
window, the depth of the option book, which the archive does not record — could each
plausibly move a cost by a few percent; a difference of a tenth of the price is one
that none of them is on record as reaching. Both thresholds were chosen by the
assistant under the owner's delegation of 2026-09-24 ("do whatever is needed") and
written here before the script existed. They are not edited after the first run; a
different threshold is a new record that says it came after the evidence.

A condition is **stably** cheaper on a venue when it is so in more than 90% of its
judged snapshots — the `always_above` of `stability.py`, the same persistence rule as
D-092 — and it has at least 10 judged snapshots.

### The verdict — pre-committed, applied by the script, not by a reader
Over the whole family:
- at least one condition stably cheaper on Kalshi AND at least one stably cheaper on
  Deribit → **"the cheaper venue depends on the condition"**;
- stably cheaper conditions on one venue only → **"one venue is cheaper wherever
  either is"**, and the report names which;
- none → **"no condition is stably cheaper on either venue"**.

On every outcome: the result is a statement about the cost of buying a payoff at the
quotes that existed, not a recommendation, a signal or an edge, and it is not called
any of those in any file or on any screen. The first outcome passes nothing; it is an
input to G4, where discovery and the other open questions still stand. The second
reduces V0, if it is built, to a rule the report states in one line. The third says
the comparison cannot separate the venues at current quotes, and V0 would have to earn
its place on something other than cost.

### The reference ticket — an illustration, not a verdict
The owner's example — 1,000 USD, a target of +20% — is computed on the newest snapshot
only, for every condition and both venues: the stake needed for the target if the
condition pays, `stake = R · C · c / (1 − c)` with c the cost per dollar of payoff;
the payoff that stake buys; and whether Kalshi's resting depth at the best level
covers it, with the fee's per-order round-up applied (`fees.order_fee`). Beside them,
the two linear references: the move a spot long needs (+R) and the move a perpetual at
leverage L needs (+R/L, for L = 2 and 5). These rows are there so the next record can
put them on a screen; nothing in the verdict reads them.

### What stays UNKNOWN, by name
- **Perpetual funding in any number.** `raw/funding/` holds the history since
  2026-09-18, but the unit and sign of `interest_8h` as returned are `UNKNOWN`
  (`DATA_SOURCES.md` §1a) and D-111 requires the first consumer to state its reading
  before using a value. This record does not state one; the carry of the perpetual
  row is `UNKNOWN`, and so is its liquidation distance (the maintenance margin is not
  archived).
- **Dated futures** — B-018, not built, not asked for here.
- **The depth of the option book.** `book_summary` carries prices, not sizes. The
  options side has no depth figure at all, and a cheaper option price at a size
  nobody is showing is reported as the price, with this caveat, not as an amount.
- **The capital a long option spread ties up** under Deribit's margin, and Deribit's
  minimum order size. The comparison is premium against price; both are cash paid
  today for a dollar at (about) the same date.

### Set aside by the owner on 2026-09-24, and recorded so it is not forgotten
Three questions were raised and deliberately deferred by the owner until there are
users: which venues a given user may legally access (Deribit lists the United States
among its restricted jurisdictions; Kalshi's list is in its Member Agreement, unread);
whether ranking instruments against a person's risk profile is regulated advice; and
the data rights of showing either venue's prices in a product (`DATA_SOURCES.md`,
*Data rights*; the Kalshi Developer Agreement is unread). None of them is answered
here. All three stand in front of G4 unchanged.

## D-115 — Deribit discounts combo orders; the buyer's comparison gets a zero-fee sensitivity, added after a first look and labelled as such
**Date:** 2026-09-24 · **Amends:** D-114 (adds a sensitivity; changes no rule and no threshold) · **Produced by:** `scripts/measure_payoff.py` (`sensitivity_combo_fees`)

### What was found, and when
While `measure_payoff.py` was being checked against `measure_band.rungs()` on the
14-day public window — a debugging run, whose numbers are not published — the Deribit
fee turned out to be a large part of the options cost of a bucket — four crossed
legs, each charged 0.03% of the index divided by the bracket width, which on the
year-end BTC buckets is more than the Kalshi price of some of them. Checking the fee rule on that
account found a sentence the project had not read. Deribit's Combo Books page,
quoted:

> "The cheapest direction of a Combo has reduced fees, meaning less fees to pay
> compared to executing each leg individually."

The page lists call spreads, put spreads and butterflies among the combos. It does not
say how large the reduction is. Every spread in this project — the band, the kill
test, D-114 — is charged leg by leg, in full. For an arbitrageur that is the safe
direction for claiming an edge and the unsafe one for trusting a null (below). For
the buyer's comparison it is one-sided in the same way: it can only make the
options side look dearer than a buyer entering the spread as one combo would pay.

### What is done about it
D-114's fee model stays the verdict's fee model; changing it now, after a first look
at the data, would be the edited-after-the-evidence rule D-114 forbids. Beside the
verdict, the same rules are applied once more with every Deribit fee set to zero — the
most favourable case for Deribit the combo sentence could possibly mean — and reported
as `sensitivity_combo_fees`, which the verdict never reads. A condition that stays
cheaper on Kalshi with no Deribit fee at all does not depend on the combo rule; one
that flips does, and is reported as depending on a number that is `UNKNOWN`.

### What this record admits
The sensitivity was added after the assistant had seen D-114's rules applied to the
public window, and after seeing that the fee was large. It is added anyway because
it can only weaken a finding in Kalshi's favour, never strengthen one, and because
leaving a known unmodelled discount out of the report would be worse. Whether combo
books also quote tighter prices than the legs crossed separately is `UNKNOWN`: the
archive reads `book_summary` for single options only.

The same sentence bears on the arbitrage results, and not in a comfortable direction:
there, an overstated option fee makes a discrepancy harder to find, so it is the side
that could have manufactured D-103's null. A local check by the assistant on the public
window — a debugging run, not a published figure — found the kill test's verdict
unchanged with every Deribit fee set to zero. That is not the mirror and not the
workflow, so it settles nothing on the record; B-027 makes it a sensitivity the
workflow reports. Until then D-103 stands as written, with this caveat attached to it
here and not edited into it.

## D-116 — The buyer's comparison over the mirror: one venue is cheaper wherever either is, and it is Kalshi, on single buckets only
**Date:** 2026-09-24 · **Applies:** D-114's pre-committed verdict (with D-115's sensitivity beside it) · **Evidence:** `findings/payoff_frontier.json`, written by the `measure` workflow run #29 over the private mirror, 112 snapshots from 2026-08-30T1611Z to 2026-09-23T2117Z; six early snapshots are not judged — five have no Kalshi stream and one has no year-end ladder — so each condition is seen at most 106 times · **Gate:** an input to G4; nothing is promoted

### The verdict, in D-114's words
**"One venue is cheaper wherever either is"** — Kalshi. Of 130 conditions, 118 have at
least ten judged snapshots; 15 are stably cheaper on Kalshi and none is stably cheaper
on Deribit.

### Where the 15 are, and what that says in one line
All 15 are single bounded buckets. None is an "above K" or a "below K".
- **Buckets** (38 with enough judged snapshots): in no snapshot was any bucket cheaper
  on Deribit. 15 were cheaper on Kalshi in more than 90% of their snapshots — eight on
  BTC (50,000–70,000 and 90,000–110,000, in 5,000-dollar steps) and seven on ETH
  (1,000–2,250 and 4,000–4,500, in 250-dollar steps); the other 23 were
  cheaper on Kalshi in some snapshots and indistinguishable in the rest.
- **"Above K" and "below K"** (80 with enough judged snapshots): none is stable either
  way. Deribit was the cheaper venue in at least one snapshot for 35 of them, Kalshi
  for 8; the most persistent is ETH above 2,500, cheaper on Deribit in 75 of 106
  snapshots — 71%, under the 90% bar, so it is not a finding and is not reported as one.

The one line D-114 asked for: **for a single year-end bucket, Kalshi's ask plus its fee
was never dearer than the Deribit replication at executable prices, and was materially
cheaper in over 90% of snapshots for 15 of 38 buckets; for "above K" and "below K"
neither venue was persistently cheaper.**

### Why that shape, offered as a reading and not as a measurement
A bucket is one Kalshi contract and four Deribit legs — two vertical spreads, each
crossing two bid-ask spreads and paying two fees. "Above K" is two Deribit legs and,
on Kalshi, a sum of buckets, each with its own spread and fee. Each venue is cheapest
where its native contract matches the payoff. Nothing in the script tests this
explanation; it is consistent with the counts above and is written down so that the
next record can test it rather than assume it.

### The combo-fee sensitivity (D-115)
With every Deribit fee set to zero, 13 of the 15 stay stably cheaper on Kalshi; the
verdict is unchanged ("one venue is cheaper wherever either is", Kalshi, none on
Deribit). Two buckets — ETH 1,500–1,750 and ETH 4,250–4,500 — depend on the fee and
therefore on the unquantified combo discount. The combo books' own quotes are not in
the archive (B-027).

### What this does and does not change
It does not name a trade, a recommendation or an edge; it is what each venue charged
for the same payoff at the quotes that existed. Under D-114's second outcome, V0, if it
is ever built, reduces on cost to the line above, and its case would have to rest on
something else — the payoff shape, the size a user can actually get (Kalshi's depth is
in the reference ticket; Deribit's is not archived), or the view the user brings. G4's
other conditions — discovery, data rights, venue access — are untouched and still
open. The band's late end is the March chain, 2,019 hours after the Kalshi close;
December's Deribit weeklies will narrow it, and the same script re-run then is the
natural next test of whether any "above K" lean becomes persistent. Polymarket's
ladders are B-026.

## D-117 — The buyer's comparison becomes a template; Polymarket's daily ladders are its second family; every family also gets a narrow-band verdict
**Date:** 2026-09-24 · **Asked by:** the owner, 2026-09-24 ("there will be many comparisons like this"; B-026 and the December re-test approved) · **Extends:** D-114 (its rules are not changed) · **Produces:** `scripts/measure_payoff.py` (restructured), `findings/payoff_frontier.json` (one block per family) · **Closes:** B-026 (built here), B-027 (dropped by the owner)

### Why a template
The owner expects many comparisons of this kind. Each one so far would have had to
re-decide the same things — which conditions, which option chains, how each side is
costed, what counts as cheaper — and a comparison whose rules are re-decided each time
is a comparison whose rules can drift toward its result. So D-114's rules are lifted
out and applied to every family unchanged, and what varies between families is
declared, per family, in one place in the script:

| declared per family | Kalshi year-end (D-114) | Polymarket daily (this record) |
|---|---|---|
| assets | BTC, ETH | BTC, ETH |
| events | `KXBTCY`, `KXETHY` | "Bitcoin/Ethereum above ___ on DATE?" and "Bitcoin/Ethereum price on DATE?" |
| settlement | 1 January 2027, 05:00 UTC, the CF Benchmarks real-time index (D-075) | DATE 16:00 UTC, the Binance 1-minute close (quoted below) |
| how the prediction side is bought | YES asks of the buckets making up the interval, or the NO ask of a single bucket whose complement it is | the same, over both ladders of the date: a threshold market's YES ("above K") or NO ("below K"), a bucket's YES, or a sum of buckets |
| NO price | the payload's `no_ask_dollars` | 1 − the YES best bid (below) |
| prediction fee | `fees.rate`, Kalshi's schedule | `fees.polymarket_rate`, each market's own `feeSchedule` |
| price step (the ABS floor) | 0.001, the ladders' `price_ranges` step (D-078) | each market's `orderPriceMinTickSize` — 0.001 in the tails, 0.01 near the middle |
| depth at the best level | the payload's size fields | `UNKNOWN`: the event payload carries no sizes |

What is common and fixed is D-114 as written: the options side as a band of the tight
and one-skip brackets on both chains that straddle the close; crossed prices plus
Deribit's fee; cheaper on a venue only by at least 10% and at least one price step;
stably cheaper in more than 90% of at least 10 judged snapshots; the three verdicts in
D-114's words. The one generalisation: D-114's "0.001, one price step" becomes "the
price step the venue publishes for the markets bought" — the largest step among the
legs of a route. For the Kalshi ladders that is still 0.001, so D-116's verdict is
reproduced exactly; the script is checked against it before it runs on anything new.

Each family is judged on its own and gets its own verdict. Families are never pooled:
a year-end bucket and a noon-tomorrow threshold are not the same evidence.

### The second family: Polymarket's daily terminal ladders
B-026 held these back because "their nearest Deribit expiries usually do not straddle
the close (D-082)". That was carried over from the Kalshi intraday series and it is
wrong for these ladders. Polymarket's dailies close at 16:00 UTC; Deribit lists daily
options expiring at 08:00 UTC; so a ladder for a later date is straddled by that date's
08:00 chain, eight hours before, and the next day's, sixteen hours after — a band a
day wide, narrower than the Kalshi year-end band has ever been. A snapshot taken after
08:00 on the close date has lost the early chain and does not straddle; those
snapshots are unquoted, as D-114 already says. Ladders several days out straddle more
widely, when the dailies run out and the weeklies take over.

Settlement, quoted from the markets' own rule text: the "above" markets resolve "Yes" if
"the Binance 1 minute candle for BTC/USDT 12:00 in the ET timezone (noon) on the date
specified in the title has a final "Close" price higher than the price specified in the
title"; the bucket markets resolve on the same candle, and "If the reported value falls
exactly between two brackets, then this market will resolve to the higher range
bracket." So a bucket is [lo, hi) and "above K" is S > K, the intervals the script
already uses. The Binance close is not the Deribit index; that basis is not measured
for Polymarket and is not in any number (`UNKNOWN`, as it was in `measure_polymarket.py`).

The NO side. The event payload quotes the YES side only (`bestBid`, `bestAsk`). A NO is
priced as 1 − the YES best bid, on Polymarket's own description of its book, quoted:
"Someone places a limit order to buy Yes at a price (e.g., `$0.60`) [and] someone
places a limit order to buy No at the complementary price (e.g., `$0.40`). Since
`$0.60` + `$0.40` = `$1.00`, the orders match." A resting YES bid at p is therefore a NO
available at 1 − p.

Conditions, per asset and date: every interval either ladder sells directly — each
threshold's "above K" and "below K", each bucket — plus "above" and "below" every
bucket edge. A condition is followed across snapshots by asset, date and interval.

### A narrow-band verdict for every family — the December re-test, fixed now
D-116 left one question open: whether an "above K" lean toward Deribit becomes
persistent once the options band narrows. It narrows on its own — the year-end band's
late end is the March chain today, and 1 January 2027 is a Friday, the weekday Deribit's
weeklies expire on. Whether a 1 January expiry will be listed is `UNKNOWN`; if it is, it
will be three hours after the Kalshi close.

So every family reports, beside its verdict over all judged snapshots, the same verdict
over the judged snapshots whose band is narrow: **both straddling chains within 168
hours of the close** (one week, about the early year-end chain's own distance). The
rules inside are D-114's, unchanged. For the Kalshi family that sub-verdict is empty
until a chain within a week after 1 January is listed, and it fills by itself in every
`measure` run after that; nothing has to be decided in December. For the Polymarket
family nearly every judged snapshot is narrow already.

### B-027, dropped
The owner has set the combo-fee question aside. B-027 is closed without being done. The
zero-fee sensitivity of D-115 stays in the output, per family, because it costs nothing
and D-115 said it would be there; it never enters a verdict.

## D-118 — The template's first run: Kalshi's result stands, Polymarket's dailies can barely be told apart from the options, and the narrow band is still empty
**Date:** 2026-09-24 · **Applies:** D-114's verdict per family, D-117's narrow band beside it · **Evidence:** `findings/payoff_frontier.json`, `measure` workflow run #30 over the private mirror, 114 snapshots from 2026-08-30T1611Z to 2026-09-24T0515Z · **Gate:** an input to G4; nothing is promoted

### Kalshi year-end — D-116 stands
Unchanged in D-114's words: **"one venue is cheaper wherever either is"**, the
prediction market, on 15 single buckets, none on the options. The template reproduces
D-116 condition by condition (checked on the public window before this run). With two
more snapshots the zero-fee sensitivity now keeps 12 of the 15 rather than 13: BTC
90,000–95,000, ETH 1,500–1,750 and ETH 4,250–4,500 depend on the Deribit fee.

**Narrow band: empty** — 0 judged rows, because no Deribit chain within 168 hours after
the Kalshi close is listed yet. That is what D-117 expected. It fills without a new
decision once one is; a reminder to read it is set for 2026-12-21.

### Polymarket daily — technically the same verdict, resting on one condition
In D-114's words: **"one venue is cheaper wherever either is"** — the prediction
market. It rests on a single condition: 1,860 conditions were judged, 1,009 of them in
at least ten snapshots, and one — BTC in [68,000, 70,000) on 2026-09-18 — was cheaper
on Polymarket in all 21 of its judged snapshots. None was persistently cheaper on the
options. With every Deribit fee at zero, that one condition stops qualifying and the
sensitivity verdict is "no condition is stably cheaper on either venue". The narrow
band is the whole family here (21,514 judged rows, all within 168 hours) and gives the
same verdict.

Across every judged row of the family, 86.9% were indistinguishable, 9.8% cheaper on
Polymarket and 3.3% cheaper on the options. The most frequent lean either way stayed
far below the bar: a bucket cheaper on the options in 11 of 27 snapshots, a "below K"
cheaper on Polymarket in 25 of 29.

The verdict is reported as the rule produces it and is not softened here. Read with its
basis, it says that on the dailies the two venues are, with one fee-dependent
exception, not separable at the quotes that existed.

### Why the dailies separate so little — a reading, not a measurement
A daily options chain near expiry lists few strikes and many one-sided quotes, so
most conditions have no executable options price at all (in the newest snapshot, 2 of
31 per asset had one); where they do, the strikes are close together, each spread
crosses two bid-ask spreads and pays Deribit's fee divided by a narrow width, and the
band between the tight and one-skip brackets on two chains is wide. A Polymarket price
sits inside that band nearly every time. This is consistent with the counts; nothing
in the script tests it.

### What this changes
For G4, and for any Polymarket-facing product, the cost argument is now measured on
both families: it holds for single Kalshi year-end buckets and does not hold on
Polymarket's daily ladders, where the comparison mostly cannot say which venue is
cheaper. A Polymarket-first V0 would have to rest on something other than cost. The
README's checked sentences were brought to this run's findings (104 of 108, 92.8%,
114 snapshots and 25 days); nothing else in it moves.

## D-119 — Carry comes from Hyperliquid first and Polymarket's perpetuals second; Deribit's dated futures join the archive; Binance is parked
**Date:** 2026-09-24 · **Owner's decision of:** 2026-09-24 · **Supersedes:** D-111's venue clause ("Other venues' perpetuals are a different basis and are not collected"); nothing else in D-111 · **Builds:** B-018 · **Produced by:** `collector/collect.py` (`carry()`), `scripts/measure_carry.py`, `docs/ARCHIVE_SCHEMA.md` §`carry/` · **Archive version:** 6 → 7

### Why
The buyer's comparison (D-114) prices terminal payoffs. The owner's question is wider:
for one view ("WTI falls five dollars by the end of October"), what does $1,000 buy on
each venue, including a perpetual or a dated future, and what does holding it cost per
day and per week. That needs funding from the venues a buyer would use for a linear
position, and dated-futures prices. Deribit's own perpetual cannot supply it: its unit
is still unread (D-111), and the documentation page read again on 2026-09-24 still
says only "1hour interest rate" and "8hour interest rate", so that stays `UNKNOWN`.

### The owner's choice, and what the probe found
The owner preferred Binance and Hyperliquid, and said that the two converge within a
short time, so Hyperliquid can serve as the base. A one-off workflow
(`probe_sources.yml`, run 36034452391, runner in Iowa, US) asked each source once:

| source | answer from a GitHub runner |
|---|---|
| `fapi.binance.com` (funding, basis) | 451, "Service unavailable from a restricted location according to 'b. Eligibility' in https://www.binance.com/en/terms" |
| `data.binance.vision` (monthly funding files) | 200 |
| `api.hyperliquid.xyz/info` (funding history, both dexes) | 200 |
| `api.perpetuals.polymarket.com` (tickers, instruments) | 200 |
| Deribit `get_book_summary_by_currency`, `kind=future` | 200 |

A different Binance host answered the same funding request with 200. It is not used:
the refusal names Binance's eligibility terms, and reaching the same data through
another door would be working around that refusal, not an access method. The monthly
files are allowed but arrive weeks late, and the owner ruled that out for oil, which
moves within hours. Binance is parked (B-028), not rejected.

### Units, read before any number is shown
**Hyperliquid** (docs, *Trading → Funding*, read 2026-09-24):

> "The funding rate formula applies to 8 hour funding rate. However, funding is paid
> every hour at one eighth of the computed rate for each hour."

> "interest rate component is predetermined at 0.01% every 8 hours, which is 0.00125%
> every hour, or 11.6% APR paid to short."

> "If the contract's price is higher than the oracle price, the premium and hence the
> funding rate will be positive, and the long position will pay the short position."

> "Note that the funding payment at the end of the interval is position_size *
> oracle_price * funding_rate."

`fundingHistory` (docs, *Info endpoint → Perpetuals*): `startTime` "Start time in
milliseconds, inclusive", `endTime` "End time in milliseconds, inclusive". The value
returned is the **hourly** rate as a fraction: the probe's BTC rows read `0.0000125`,
which is the quoted 0.00125% per hour. HIP-3 dexes set a funding multiplier per asset
(`perpDexs` returns `assetToFundingMultiplier`); trade[XYZ]'s specification index,
read through a fetch tool, gives 0.5 for its markets, and the archived `perpDexs`
shows the value in force.

**Polymarket perpetuals.** docs.polymarket.com does not open from the owner's
connection, so the page was read through a fetch tool, which returned these as quotes;
they are recorded as such and are to be checked against the page:

> "Crypto markets use a 1.0 scale. Non-crypto markets use a 0.5 scale."

> "The charge window is 1 hour. Samples are averaged over the hour, and the hourly
> rate is applied once at the end."

> "Hourly rate > 0, perp rich vs Index | Longs Pay | Shorts Receive"

> "Funding is a direct transfer between longs and shorts. The protocol takes no cut."

The formula as returned: `F_8h = scale × (mean_P + clamp(0.0001 − mean_P, ±0.0005))`,
`FR_hour = clamp(F_8h / 8, ±0.04)`. The value in the API is the hourly rate as a
fraction: the probe's `SP500-USD` ticker read `funding_rate` `0.00000625`, which is
0.0001 / 8 × 0.5. The funding history endpoint returns "at most 100 funding-rate
entries per request" with a `more` flag; its entries carry `timestamp` in
milliseconds. The unit of its `start_timestamp` / `end_timestamp` parameters is not
stated; milliseconds are sent, and the first run shows whether the rows fall inside
the window asked for.

**The owner's observation, explained in part.** The owner has paid less funding on
Polymarket's perpetuals. The scale halves the whole rate — the interest leg and the
premium — on non-crypto markets, so both what a long pays and what a short receives
are halved there. Hyperliquid's trade[XYZ] markets use the same 0.5. On crypto both
venues use 1.0 and the same interest leg, so any difference there comes from the
premium and has to be measured, not assumed.

### What is collected
One new stream, `raw/carry/YYYY-MM-DD/carry_<STAMP>.json.gz`, written after `funding`,
so the Deribit–Polymarket window is untouched (D-111's placement argument applies
unchanged):

- **Hyperliquid:** `perpDexs`; `metaAndAssetCtxs` for the first dex and for `xyz`
  (current funding, mark, oracle, open interest, day notional volume); `fundingHistory`
  for BTC and ETH on the first dex and for CL, BRENTOIL, GOLD, SILVER, SP500 and
  XYZ100 on `xyz`. A coin that is not in that dex's universe is recorded as absent,
  not requested.
- **Polymarket perpetuals:** `tickers`, once a day `instruments`, and the funding
  history for BTC-USD, ETH-USD, WTIOIL-USD, BRENTOIL-USD, GOLD-USD, SILVER-USD and
  SP500-USD, found in the tickers by symbol, recorded as absent if not there.
- **Deribit dated futures (B-018):** `get_book_summary_by_currency` with
  `kind=future` and `get_instruments` with `kind=future` for BTC and ETH (the
  perpetual comes with them), and `get_index_price` for `btc_usd` and `eth_usd`.

The lookback is **eight days**, not D-111's 48 hours: a weekly average must exist
from the first run, and 192 hourly rows are a few kilobytes. Polymarket's history is
paged (at most four pages). Every vendor payload is stored exactly as returned, with
our `request` block beside it. A failed venue fails only its own block.

### What is derived
`scripts/measure_carry.py` writes `findings/carry.json`, run as a step of
`measure.yml`:

- per perpetual: hourly points de-duplicated on time; the mean hourly rate over the
  last 24 and 168 hours ending at the newest point, reported only when at least 90%
  of the window's hours have a point (the same 90% as D-114's persistence) and
  `UNKNOWN` otherwise; what a $1,000 long pays per day and per week at that mean,
  at constant notional (positive means the long pays, the short receives the same);
  the share of hours with a positive rate; the smallest and largest hour.
- per dated future: mark over index minus one at the newest snapshot, days to
  expiry from `expiration_timestamp`, and that premium in dollars per $1,000 and
  annualised.

These are descriptions of what was charged, not forecasts of what will be charged.

### Scope, and what this does not do
No R3 rule and no highlight is built from these numbers yet; the card only shows
them. Deribit's perpetual funding remains `UNKNOWN` (D-111). Kalshi's commodity
series are not added here. The data-rights order the owner set on 2026-09-24 —
raw data private and derived data public, evaluated at the end — is B-029; it does
not change what this record collects.
