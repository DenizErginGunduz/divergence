# DATA_SOURCES.md — what data we can actually get

The constraint: **free**, no licence will be bought. Updated 2026-09-13.

## Evidence level — read this first

| Level | Meaning |
|---|---|
| `LIVE-VERIFIED` | A real call was made and data came back. |
| `DOCUMENTED` | The provider's documentation was read; no call could be made. |
| `UNREACHABLE` | A call was attempted and failed from that environment. Not a judgement about the source. |
| `FORBIDDEN` | The provider explicitly forbids automated collection. |

The distinction matters: failing to reach a source does not mean the source is
closed. Our development sandbox has an allowlisted network, so several endpoints
were unreachable from there; the same endpoints worked without trouble from the
GitHub Actions runner and from Colab.

---

## 1. BTC / ETH — Deribit · `LIVE-VERIFIED`

| What | Status |
|---|---|
| Option chain — **calls and puts** (strike, mark, bid/ask, IV, OI, volume) | no key |
| Index (spot reference) | no key |
| Futures and perpetual | no key |

Endpoints: `https://www.deribit.com/api/v2/public`
- `get_book_summary_by_currency?currency=BTC&kind=option` — the whole chain in one call
- `get_index_price?index_name=btc_usd`

**The put chain is critical (D-032, D-035).** Our first pull contained calls only
and derived the downside probability from deep ITM calls — results were off by up
to a factor of 2.09. The collector now fetches both with `kind=option`.

**Futures data turned out to be unnecessary (D-036).** Put-call parity,
`F = K + C − P`, gives the forward from the chain itself. Across 21 strikes on the
25SEP26 chain the dispersion was 113.75 USD (0.146%) — the chain is internally
consistent. One data dependency dropped.

**Deribit options are inverse:** USD price = BTC premium × index.

**There is no going back:** `get_book_summary` returns the current state only. A
missed day's chain is lost permanently. That is the reason the archive exists
(D-037).

### 1a. Perpetual funding · `LIVE-VERIFIED` 2026-09-18 (B-019, D-111)

Same venue, same public host, no key. Three endpoints were read in the
documentation and one was chosen; the reasons are in D-111.

| endpoint | what it returns | used |
|---|---|---|
| `public/get_funding_rate_history` | hourly history for one perpetual over a window | **yes** — the archived stream |
| `public/get_funding_rate_value` | one number for a window | no — loses the hourly detail |
| `public/ticker` (`current_funding`, `funding_8h`) | the instantaneous value | no — three samples a day are not a history |

**Documentation, quoted** ([public/get_funding_rate_history](https://docs.deribit.com/api-reference/market-data/public-get_funding_rate_history), read 2026-09-18):

> "Retrieves hourly historical funding rate (interest rate) data for a PERPETUAL
> instrument over a specified time period."

Parameters, as documented: `instrument_name` (required, string, "Instrument name");
`start_timestamp` (required, integer, "The earliest timestamp to return result from
(milliseconds since the UNIX epoch)"); `end_timestamp` (required, integer, "The most
recent timestamp to return result from (milliseconds since the UNIX epoch)").

Response fields, as documented: `timestamp` (integer, milliseconds since the Unix
epoch); `index_price` (number, "Price in base currency"); `prev_index_price` (number,
"Price in base currency"); `interest_1h` (number, "1hour interest rate");
`interest_8h` (number, "8hour interest rate").

**The call, tried** (2026-09-18T0657Z, `BTC-PERPETUAL`, window 2026-09-18T0000Z to
2026-09-19T0000Z): 6 elements, timestamps 01:00 to 06:00 UTC on the hour — the
point stamped at the window's start instant was not returned, and points after the
call's instant do not exist yet. Top-level keys `jsonrpc, result, usIn, usOut,
usDiff, testnet`; element keys exactly `timestamp, index_price, interest_8h,
interest_1h, prev_index_price`. `ETH-PERPETUAL` answers the same shape.

**How the venue defines the rate** ([Funding Specifications](https://support.deribit.com/hc/en-us/articles/31424939178397-Funding-Specifications), read 2026-09-18), quoted:

> "Premium Rate = ((Mark Price - Deribit Index) / Deribit Index) * 100%"
>
> "If the premium rate is within -0.025% and 0.025% range, the actual funding rate
> will be reduced to 0.00%."
>
> "Funding Rate = Minimum (Maximum_Cap, Maximum (Minimum_Cap, (Maximum (0.025%,
> Premium Rate) + Minimum (-0.025%, Premium Rate))))"
>
> "Time Fraction = Funding Rate Time Period / 8 hours"
>
> "Funding Payment = Funding Rate * Position Size * Time Fraction"
>
> "When the funding rate is positive, long position holders pay funding to the short
> position holders; when the funding rate is negative, short position holders pay
> funding to the long position holders."
>
> "funding is actually calculated and paid/received continuously and can be seen in
> real time in the realised session profit (RSPL)."

Caps on the same page: BTC −0.5% / +0.5%; ETH −1.0% / +1.0%; USDC and USDT −5.0% /
+5.0%.

**What is `UNKNOWN`.** The unit and sign of `interest_8h` / `interest_1h` as returned
(a fraction, a percentage, or something else; the documentation says "8hour interest
rate" and no more — the sampled values are of order 1e-6 to 1e-5). Whether a point's
`interest_1h` is the hour ending or the hour beginning at its `timestamp`. Whether
`start_timestamp` is exclusive (one observed call suggests so; not documented). The
public rate limit on this endpoint. None of these is assumed anywhere; the stream
stores the response as it came and a reader states its own reading.

**Terms.** The same Deribit Terms of Service quoted under *Data rights* below govern
this stream; there is no funding-specific clause. It is market data of the same class
as the option chain already archived, and the position taken there (research use, the
rolling public window, the private mirror) is not changed by it. That is our reading,
not the venue's ruling.

---

## 2. Polymarket · `LIVE-VERIFIED`

| Endpoint | Status | What it gives |
|---|---|---|
| `gamma-api` `/events?tag_slug=...` | 200 | ladders, rule text, bestBid/bestAsk |
| `data-api` `/trades?market=<conditionId>` | 200 | `proxyWallet, size, price, side, outcome, timestamp, transactionHash` |
| `data-api` `/holders?market=<conditionId>` | 200 | position holders |
| `clob` `/prices-history` | 200 but **empty** | parameters need another try (B-008) |
| `clob` `/book` | 404 | wrong path; not needed |
| `clob` `/trades` | 401 | wants credentials; `data-api` covers it |

**Flow data is the product's second leg (D-038, D-039).** In an options market you
cannot see who is on the other side; on a prediction market you can, because it is
on-chain. That is the structural advantage prediction markets have.

**Measured trade rate (2026-08-30, 106 markets):**

| | fastest | p10 | median | p90 |
|---|---|---|---|---|
| time span covered by 100 trades | 0.64 h | 34 h | **248 h** | 3,040 h |

Half the markets have been silent for 24 hours; the busiest does 156 trades an
hour. With `limit=100`, to miss nothing the fetch interval has to be shorter than
the busiest market's 100-trade window (38 minutes). Three runs a day lose nothing
on the median market and can lose something on the busiest — which is why the
collector detects a gap and flags it rather than assuming there is none.

**`offset` pagination support is unverified (D-042).** The script does not assume:
it tries, and writes the outcome into `pagination_worked`. No gap has occurred, so
it has never been triggered.

**Note — geographic block:** Polymarket is not accessible from Turkey. This does
not affect the pipeline; the collector runs on GitHub Actions in the US and
reaches every endpoint. That is the second benefit of the Actions architecture.

---

## 3. Commodities (gold, silver, oil)

**Price and option chain have to be treated separately.** They are nowhere near
equally hard.

### 3a. Futures / spot PRICE — easy
API Ninjas Commodity, CommodityPriceAPI, OilPriceAPI — all `DOCUMENTED`.
A 15-minute delay is not a problem for us.

### 3b. Option CHAIN — the real bottleneck
CME option data is licensed. None of the free commodity APIs provide a chain.

**The way out: ETF proxies (GLD, SLV, USO).** The cost should not be waved
through:
- **Carry difference** — GLD holds physical gold; the GC future includes carry.
- **Roll decay in USO** — it holds front-month CL and rolls; in contango it drifts
  systematically away from spot oil over long horizons. **USO is NOT a long-dated
  WTI proxy.**
- **Expense ratio** — the fund fee creates a slow drift.

### 3c. The mismatch on the Polymarket side
Our gold ladder settles on the `Gold (GC)` CME future. Comparing it with a GLD
option stacks two conversions on top of each other: GC→GLD and touch→terminal.
Each conversion is a source of error.

---

## 4. S&P 500

| What | Status |
|---|---|
| SPY option chain | `DOCUMENTED` — free through the equity-option channel |
| CBOE delayed quote pages | **`FORBIDDEN`** |
| ES future | `UNKNOWN` |

**CBOE warning:** automated collection is explicitly forbidden and they state that
they block IPs. It will not go into the pipeline. Looking by hand is fine.

**The good news:** the Polymarket market is already written on SPY (rule text:
Pyth, regular session, split-adjusted). So comparing against SPY options is the
more correct thing to do, and the index-versus-ETF question resolves itself
(D-012).

---

## 5. Equities (Mag7)

| Source | Free tier | Note |
|---|---|---|
| yfinance (Yahoo) | no key | Not an official API. Direct HTTP is blocked from data-centre IPs; the library worked from Colab. |
| Finnhub | 60 calls/min, 20 min delay | The most generous free tier |
| Polygon.io | 5 calls/min | Slow but it works |
| Alpha Vantage | **25 calls/day** | Not usable in practice |

### But the bottleneck is not on the option side (D-021)

I first said equities were the easy side. I had only looked at **data access**, not
at **liquidity**. Measured:

| Asset | Rungs | Median spread | Measurable |
|---|---|---|---|
| BTC | 22 | 0.002 | **20** |
| SPY | 14 | 0.024 | 2 |
| NVDA | 14 | 0.074 | **0** |
| META | 14 | 0.090 | 1 |
| TSLA | 14 | 0.099 | 1 |

Measurable = spread ≤ 0.02 **and** mid < 0.99. The reason for the threshold: the
gaps we measured on BTC were in the 0.006–0.026 range; if the spread is wider than
that, the number produced is the spread, not a market view.

**Equities are not dropped from the product:** they appear in the list, carrying a
reasoned "not measurable" label instead of a number.

---

## 6. Summary

| Asset | Prediction market | Option chain | Status |
|---|---|---|---|
| BTC | very deep | Deribit calls + puts | **working** |
| ETH | deep | Deribit calls + puts | **working** |
| SPY | 14 monthly touch | free channel | ladder liquidity is weak |
| TSLA/NVDA/META | 14 touch each | free channel | **not measurable** — spread |
| Gold/Silver/Oil | present | ETF proxy only | carries proxy error |

---

## Data rights — what we checked and where we stand

Checked 2026-09-11 by reading the current terms of all three venues. Not legal
advice; this is a record of what the documents say and what we decided.

### What the terms say

**Kalshi** — [Data Terms of Use](https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf)

> "You may access content only for your personal use for non-commercial purposes.
> Non-commercial use does not include the use of Kalshi Data without prior written
> consent from Kalshi in connection with: (1) the development of any software program...
> or (2) providing archived or cached data sets containing Kalshi Data to another
> person or entity."

That document governs the **website**. The API has a separate Developer Agreement at
kalshi.com/developer-agreement which we have not been able to read — the domain blocks
automated access. It may be more permissive. **Unread, therefore unresolved.**

**Polymarket** — [Terms of Use](https://polymarket.com/tos), effective 2026-08-11

Prohibits accessing Data "directly or through an API... whether in raw, derived,
aggregated, or anonymized form" **if you are** a Capital Market Client (broker, market
maker, prop trader, index calculator, fund) **or a market data distributor**, and
prohibits redistributing Data **to** those parties. The restriction is aimed at
institutional data resale, not at analytics tools.

Against that, Polymarket runs a [Builders Program](https://builders.polymarket.com/)
which says the protocol is "free and permissionless to use and access — just start
building", explicitly invites projects that "empower users with new analytics", and
lists 50+ third-party tools including data products.

**Deribit** — [Terms of Service](https://support.deribit.com/hc/en-us/articles/25944471089437-Terms-of-Service-DRB-Panama-Inc)

> "The use of market data and/or derived data is for personal use only. You are not
> allowed to aggregate, resell, publish, forward or in any other way process market
> data and/or derived data (except for personal use) without prior written approval."

Broadest wording of the three, and it reaches derived data. It also carves out personal
use explicitly. Deribit's public market-data endpoints need no key and allow
cross-origin requests from a browser, and a commercial analytics ecosystem exists on
top of them (Laevitas, Amberdata, Block Scholes).

### What we concluded

Building a tool on this data is normal and, on two of three venues, actively
encouraged. The thing that made us different from every other tool in the ecosystem
was not the analysis — it was that we published a continuously growing archive of raw
vendor payloads. Other tools display data; none redistribute it in bulk.

That is the specific practice the Kalshi clause names.

### The rolling window

`raw/` is a rolling window of 14 days (`ARCHIVE_DAYS` in
`scripts/prune_archive.py`). What remains is a research sample — fourteen days at
three runs a day — rather than an indefinite feed. Built and running as of
2026-09-14; the first prune removed 2026-08-30, eight day folders and 15.5 MB.

The exact count is deliberately not written here. It was, once — "about 42
snapshots" — and by the time Denetim 3 read the line it was 47 (D-090). A number
that changes three times a day does not belong in a sentence nobody recomputes;
`state/latest.json` carries it, and the interface reads it from there.

**Fourteen and not ninety — decided 2026-09-16, D-089.** Extending the window was
open until then. It was closed once it was clear that `measure.yml` has no schedule:
every published number comes from a manual run, and a manual run reads the private
mirror rather than this window, so a wider window would add nothing to any finding
and only publish more. The cost of the decision is named in D-089 — a reader
checking the findings from the public repository sees 14 days where the findings
were computed over the whole mirror.

**The ordering is the safety mechanism.** Pruning runs only after the private
mirror has been updated successfully. The mirror step exits 0 even when it is
skipped for a missing token, so "the previous step passed" proves nothing; the
workflow sets `MIRROR_OK=1` only on the real push path and the prune step is gated
on that. Skipped mirror, skipped prune. Otherwise the data leaves both places at
once.

**What the window does not do.** Deleting a file in a new commit does not remove
it from git history. The blob stays, so `.git` keeps growing at the same ~4 MB a
day and a full `git clone` still downloads everything ever committed. The window
bounds the WORKING TREE: what a visitor browses, and what a shallow clone
retrieves. It does not bound the repository.

So the size argument is weaker than it first looks, and the data-rights argument
is weaker than it first looks too — a determined full clone still reaches the
whole feed. Bounding the repository itself would take either periodic history
rewriting or never committing raw vendor data to the public repo at all. Neither
is done. The claim is limited to what is measured.

### Still open

- Kalshi's API Developer Agreement is unread. Until it is, the Kalshi position rests on
  website terms that may not be the governing document.
- The window bounds the working tree, not git history. A full clone still reaches
  every snapshot ever committed, so the bulk-archive practice the Kalshi clause
  names is reduced rather than removed.
- No written permission has been requested from any venue. All three have an
  "unless agreed in writing" carve-out; none has been exercised.
- Deribit's "derived data" wording arguably reaches `findings/latest.json`. We publish
  it because it is a research result rather than a data feed, but that is our reading,
  not their ruling.
- The current position suits a research and portfolio project. A commercial product or
  an investment round changes the analysis and would need proper legal review.
