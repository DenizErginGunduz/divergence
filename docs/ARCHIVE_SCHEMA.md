# Archive schema

What is stored under `raw/`, in what shape, and which fields matter.

Every file here is written once and never modified. The methodology will change;
the ability to recompute from the original bytes must not. If you find yourself
wanting to "fix" an archived file, write a new measurement instead.

---

## Layout

```
raw/
  kalshi/            YYYY-MM-DD/ kalshi_<STAMP>.json.gz
  deribit/           YYYY-MM-DD/ deribit_<STAMP>.json.gz
  polymarket_events/ YYYY-MM-DD/ polymarket_events_<STAMP>.json.gz
  funding/           YYYY-MM-DD/ funding_<STAMP>.json.gz      (archive version 6+)
  carry/             YYYY-MM-DD/ carry_<STAMP>.json.gz        (archive version 7+)
  polymarket_other/  YYYY-MM-DD/ polymarket_other_<STAMP>.json.gz (archive version 8+)
  hip4/              YYYY-MM-DD/ hip4_<STAMP>.json.gz         (archive version 8+)
  events/trades/     YYYY-MM-DD/ trades_<STAMP>.ndjson.gz
  holders/           YYYY-MM-DD/ holders_<STAMP>.json.gz
  coverage/          YYYY-MM-DD/ coverage_<STAMP>.json
  _meta/             YYYY-MM-DD/ meta_<STAMP>.json
state/
  latest.json        pointer to the newest snapshot of each stream
  watermark.json     per-market high-water mark for trade de-duplication
findings/
  latest.json        measurement output, written by CI
```

`<STAMP>` is `YYYY-MM-DDTHHMMZ`, for example `2026-09-11T0515Z`. Every stream in a
single collector run shares the same stamp. That is what makes cross-venue comparison
possible: a Kalshi price and a Deribit price with the same stamp were read seconds
apart, and `_meta` records exactly how many.

Three runs per day at 05:00, 13:00 and 21:00 UTC.

Most files are gzipped JSON. `coverage` and `_meta` are plain JSON because they are
small and meant to be read by eye. Trades are NDJSON — one JSON object per line —
because they are appended per run and line-oriented data survives partial reads.

Field names inside our own files (the `kalshi` wrapper, `coverage`, `_meta`,
`findings`) are ours. Vendor payloads keep the field names the venue returned, because
those are not ours to relabel — which is why a Kalshi market object and a Deribit quote
look exactly as they arrived.

The schema our own files use is versioned: `_meta` carries a `version` field and
`state/latest.json` carries its own. Read it before assuming a field is there.

---

## `deribit/` — option chain and index

```json
{
  "BTC": { "book_summary": { "result": [ ... ] }, "index": { "result": { ... } } },
  "ETH": { ... }
}
```

`index.result.index_price` is the spot index in USD.

`book_summary.result` is an array of roughly 950 quotes per currency. One entry:

```json
{
  "instrument_name": "BTC-25SEP26-155000-P",
  "bid_price": 1.0025,
  "ask_price": 1.0135,
  "mark_price": 1.00777056,
  "mark_iv": 84.02,
  "open_interest": 0.1,
  "underlying_price": 77191.88,
  "underlying_index": "BTC-25SEP26"
}
```

**The one thing that will bite you.** Deribit options on BTC and ETH are inverse
contracts: `bid_price`, `ask_price` and `mark_price` are quoted in units of the
underlying, not dollars. A mark of `1.0077` on that put means 1.0077 BTC. To get
dollars, multiply by `index_price`. Every script does this in `chain()`; if you write
a new one and skip it, your numbers will be wrong by a factor of about 77,000 and will
still look plausible in a ratio.

`instrument_name` parses as `CURRENCY-EXPIRY-STRIKE-TYPE`, where expiry is Deribit's
`DDMMMYY` label (`25SEP26`) and type is `C` or `P`. Expiries settle at 08:00 UTC.

`mark_iv` is a percentage (84.02 means 84%). Only `measure_touch.py` uses it.

---

## `funding/` — the perpetuals' hourly funding history

Written every run since archive version 6 (D-111, 2026-09-18). One gzipped JSON file
per run, one key per perpetual:

```json
{
  "BTC-PERPETUAL": {
    "request":  { "method": "public/get_funding_rate_history",
                  "instrument_name": "BTC-PERPETUAL",
                  "start_timestamp": 1789541867000, "end_timestamp": 1789714667000 },
    "response": { "jsonrpc": "2.0",
                  "result": [ { "timestamp": 1789693200000,
                                "index_price": 76529.69,
                                "prev_index_price": 76355.27,
                                "interest_8h": 5.91821175553615e-06,
                                "interest_1h": 1.257606590607552e-06 }, ... ],
                  "usIn": 1789714667179301, "usOut": 1789714667185192,
                  "usDiff": 5891, "testnet": false }
  },
  "ETH-PERPETUAL": { ... }
}
```

`request` is ours: the window the run asked for, in milliseconds since the Unix
epoch. It is recorded because the response does not carry it, and without it "no
points" and "not asked" look the same. `response` is Deribit's JSON-RPC envelope
exactly as returned; nothing in it is renamed or removed.

Fields inside `result`, with the venue's own descriptions
(`docs/DATA_SOURCES.md` §1a quotes the documentation):

| field | venue's description | note |
|---|---|---|
| `timestamp` | milliseconds since the Unix epoch | on the hour; whether the point describes the hour ending or beginning there is `UNKNOWN` |
| `index_price` | "Price in base currency" | the Deribit index at the point |
| `prev_index_price` | "Price in base currency" | the index one point earlier |
| `interest_1h` | "1hour interest rate" | unit and sign convention as returned are `UNKNOWN`; sampled values are of order 1e-6 |
| `interest_8h` | "8hour interest rate" | same |

**How often, and why it overlaps.** Every run asks for the last **48 hours**, so
with three runs a day each hour appears in about six consecutive files. That is
deliberate: the series is meant to be independent of the collector's cadence, and up
to five consecutive missed runs leave no hole in it. A reader that wants one row per
hour de-duplicates on `timestamp` (the values for a given hour are identical across
files when the venue has not revised them; whether it ever revises them is
`UNKNOWN` and would show up as a disagreement between files). The archive itself
never de-duplicates, because it stores what came back.

**What this stream is not.** It is not a dated-futures stream (B-018, not
approved): the endpoint is per instrument and returns the perpetual only. It is not
a carry computation: nothing in the repository reads this stream yet, and the first
reader (the exposure engine's worked example, D-108) has to state its reading of
the `UNKNOWN`s above before it uses a number.

`_meta.funding_summary` carries the points returned per instrument and the window
asked for, so an empty run is visible without opening the file. `state/latest.json`
lists the newest funding file under `paths.funding`; it is not one of the streams
whose absence marks the pointer incomplete.

---

## `carry/` — other venues' perpetuals and Deribit's dated futures

Written every run since archive version 7 (D-119, 2026-09-24). One gzipped JSON file
per run. Every vendor payload sits under `response` exactly as returned, wrapped as
`{"ok": true, "value": <payload>}` or `{"ok": false, "error": "<message>"}` so one
failed call is visible without failing the stage. `request` blocks are ours.

```json
{
  "window": { "start_ms": ..., "end_ms": ... },            // eight days ending at the run
  "hyperliquid": {
    "perpDexs": { "ok": true, "value": [ null, { "name": "xyz", ... } ] },
    "ctx": { "main": { "request": {"type": "metaAndAssetCtxs"}, "response": {...} },
             "xyz":  { "request": {"type": "metaAndAssetCtxs", "dex": "xyz"}, "response": {...} } },
    "funding": { "BTC":    { "request": {"type": "fundingHistory", "coin": "BTC",
                                         "startTime": ..., "endTime": ...},
                             "response": { "ok": true, "value": [ { "coin", "fundingRate",
                                                                    "premium", "time" } ] } },
                 "xyz:CL": { ... } },
    "absent": [ "xyz:SILVER" ]                              // not in that dex's universe, not asked
  },
  "polymarket_perps": {
    "tickers": { "ok": true, "value": [ { "instrument_id", "symbol", "index_price",
                                          "mark_price", "funding_rate", "next_funding", ... } ] },
    "instruments": { ... },                                 // first run of the day only
    "funding": { "WTIOIL-USD": [ { "request": { "instrument_id", "start_timestamp",
                                                "end_timestamp" },
                                   "response": { "ok": true, "value": { "data": [ { "funding_rate",
                                                                                    "timestamp" } ],
                                                                        "more": false } } } ] },
    "absent": [ ... ]
  },
  "deribit_futures": {
    "BTC": { "book_summary": {...}, "instruments": {...}, "index": {...} },  // kind=future; btc_usd
    "ETH": { ... }
  }
}
```

**Units (D-119).** Hyperliquid `fundingRate` and Polymarket `funding_rate` are the
hourly rate as a fraction; positive means the long pays. Hyperliquid's `time` lands
a few milliseconds after the hour; readers floor to the hour before de-duplicating.
HIP-3 funding multipliers are in `perpDexs` (`assetToFundingMultiplier`).
Polymarket's history is paged, at most four pages, toward whichever end its rows
show; each page is stored. The unit of its `start_timestamp` parameter is not stated
by the venue; milliseconds are sent and the rows show whether they fell inside.

**A month once a day (version 8, D-120).** The first carry run of each UTC day asks
for 31 days, the others for eight; `window.start_ms` says which. A Hyperliquid reply
of 500 rows is followed by up to three more requests starting just after its newest
row, stored under `more_pages` beside the first `request`/`response`. Polymarket's
paging cap is nine pages.

**Overlap.** Eight days asked every run, so each hour appears in about 24 files.
Readers de-duplicate; `measure_carry.py` counts hours two files report differently.

`_meta.carry_summary` carries rows per coin and per symbol, the absent lists, and
whether each Deribit block came back. `state/latest.json` lists the newest file under
`paths.carry`; like `funding`, it is not a required stream.

---

## `polymarket_other/` — commodity and index events

Written every run since archive version 8 (D-120). The Gamma `events` reply for each
tag in `POLY_OTHER_TAGS` (`commodities`, `sp-500`), open events only, wrapped as
`{"ok": true, "value": [ <event>, ... ]}` or `{"ok": false, "error": ...}` per tag.
Events have the same shape as in `polymarket_events/`. A separate stream so the
trade-flow stage, which walks every event of `polymarket_events/`, is unchanged. The
tags carry terminal ladders ("WTI Crude Oil (WTI) closes above ___ on <date>",
"What will S&P 500 (SPX) close at end of 2026?"), touch events ("hit") and Up/Down
markets; `scripts/horizons.py` tells them apart by title.

---

## `hip4/` — Hyperliquid outcome markets

Written every run since archive version 8 (D-120).

```json
{
  "outcomeMeta": { "ok": true, "value": { "outcomes": [ { "outcome": 1210,
                     "name": "template:binaryPrice",
                     "description": "perp:BTC|priceDescription:BTC-USDC mark|seconds:1|threshold:100000|time:20261001-0000",
                     "sideSpecs": [ {"name": "template:Yes"}, {"name": "template:No"} ],
                     "quoteToken": "USDC", ... } ] } },
  "allMids": { "ok": true, "value": { "#12100": "0.5", ..., "BTC": "...", ... } },
  "books": { "#12100": { "ok": true, "value": <l2Book reply> }, "#12101": { ... } },
  "skipped_for_cap": 0
}
```

`#<10 × outcome + side>` names one side of an outcome (0 = Yes, 1 = No, from a
third-party guide; to be read in Hyperliquid's documentation). Books are asked for
both sides of every `template:binaryPrice` outcome on BTC, ETH, xyz:CL, xyz:BRENTOIL,
xyz:GOLD, xyz:SILVER and xyz:SP500 whose `time` is after the run, at most 80 a run.
`template:priceTouch` outcomes are in `outcomeMeta` and get no book. The `time` field
carries no zone; it is read as UTC until the documentation says otherwise.
**No number from this stream is shown** until settlement, fees and the relation
between the two sides' books are read and written down (D-120).

---

## `kalshi/` — catalogue and markets

```json
{
  "catalogue": { "Crypto": { "series": [...] }, "Financials": { "series": [...] },
                 "Commodities": { "series": [...] } },            // Commodities since version 8
  "selection": { "crypto": [...62 series tickers...], "observed": [...30...],
                 "commodities": [...], "truncated": [...], "open_pass_errors": {...} },
  "markets":   { "<SERIES_TICKER>": [ ...market objects... ] },
  "observed":  { "<SERIES_TICKER>": [ ... ] },
  "commodities": { "<SERIES_TICKER>": [ ... ] }                  // since version 8 (D-120)
}
```

- `catalogue` — the raw series catalogue, as returned. Kept because the series list is
  derived from it at run time rather than hardcoded. A truncated catalogue response
  once caused 42 of 62 crypto series to be missed, including the annual ladders the
  whole long-horizon measurement depends on.
- `selection` — which series this run decided to fetch.
- `markets` — the measured universe: crypto series.
- `observed` — an observation-only universe (indices, metals, oil). Collected but not
  yet measured.
- `commodities` — since version 8 (D-120): the Commodities-category series whose ticker
  matches `KALSHI_COMMODITY_RE` (WTI, Brent, gold, silver; daily, weekly, monthly and
  their high/low series). Same market objects, same passes. Since version 8 the OPEN
  pass of a truncated series pages up to five pages instead of one.

A market object carries 41 fields. The ones the measurements use:

| field | meaning |
|---|---|
| `ticker` | unique and stable. Use it as the identity of a rung across runs. |
| `strike_type` | `less`, `greater` or a range type |
| `floor_strike`, `cap_strike` | bucket bounds |
| `yes_bid_dollars`, `yes_ask_dollars` | prices as **decimal strings**, `"0.9900"` |
| `status` | only `active` markets are measured |
| `close_time` | resolution time, ISO 8601 |
| `open_interest_fp`, `volume_fp` | size, in CONTRACTS — see below |
| `yes_bid_size_fp`, `yes_ask_size_fp` | contracts resting at the BEST level only |
| `price_level_structure`, `price_ranges` | the tick grid this market trades on |
| `expiration_value` | the settlement reading, once known |
| `result` | `yes` / `no` once resolved, empty before |
| `rules_primary`, `rules_secondary` | settlement rules **in full text** |

Keep `rules_primary` verbatim. The wording decides whether a contract is terminal or
touch, and that distinction decides whether a comparison is valid at all.
`scripts/audit_semantics.py` parses it and checks it against the numeric fields;
across 2,070 rung-observations they agree 100% of the time (D-075).

### `_fp` is CONTRACTS, and that was derived rather than assumed

Nothing in the payload says the unit, and the values are not integers —
`"30263.99"`, `"9.73"`. The archive settles it. On 2026-09-15 one market reported
`yes_ask_dollars = 0.0140` with `yes_ask_size_fp = 698.86`, and its order book
showed the best NO bid at `0.9860` with a quantity of **698.86** — the same
number. The ask on the YES side IS the bid on the NO side. A dollar amount would
not survive that flip: a no order at 0.986 commits 0.986 per contract while the
same order appears as a yes offer worth 0.014. A contract count does.

So: **contracts, fractional, two decimals.** Both size fields describe the BEST
level only, so they bound a trade that does not walk the book and nothing more
(D-078).

### The price grid is per-market, and not always a cent

    price_level_structure: "deci_cent"
    price_ranges: [{start: "0.0000", end: "1.0000", step: "0.0010"}]

That is the year-end crypto ladders: one uniform tenth-of-a-cent tick across the
whole range. Other markets differ — a multivariate market sampled the same day
reported `center_deci_edge_centi_cent` with three ranges and a finer 0.0001 tick
below 0.01 and above 0.99. Our tails do NOT get the finer tick. Read the field,
do not assume a cent; `measure_band.on_grid()` checks every quote against it and
has found 0 violations so far.

**`price_level_structure` is the CONTRACT PRICE tick.** It says nothing about the
granularity of the settlement value, and D-075 originally cited it as if it did.
The settlement value's granularity is a separate, measurable fact: all 1,892
numeric `expiration_value` entries in the archive carry exactly two decimals.

### `expiration_value` is not always a number

Most series report a price. Some report `"Yes"` / `"No"`, and a few a
dollar-prefixed string like `"$2511.18"`. Parse defensively; a series that
settles on something other than a price is not a bug.

Bucket boundaries need care. `cap_strike` can be `24999.99` while the next bucket's
`floor_strike` is `25000`. Rounding the two independently makes them disagree, the
digital picks different bracketing strikes on each side of the same boundary, one
region gets counted twice, and the total runs about 13% over. The correct form is
`round(cap + 0.01)`. `measure_exhaustive.py` demonstrates all three variants
against the archive.

The target of that sum is the **discount factor D**, not 1 (D-073): buying every
bucket buys a dollar at expiry with certainty, and a certain dollar is worth D
today. The script reports `total / D`, so 1.0000 is the target.

---

## `polymarket_events/` — events and their markets

```json
{ "bitcoin": [ ...100 events... ], "ethereum": [ ...100 events... ] }
```

An event holds a ladder; the rungs are in `event.markets`. Fields used:

| field | meaning |
|---|---|
| `title` | **how contract type is decided** (see below) |
| `endDate` | resolution timestamp |
| `markets[].groupItemTitle` | the threshold, as a display string: `"70,000"` |
| `markets[].bestBid`, `bestAsk` | probabilities, numbers in 0–1 |
| `markets[].active`, `closed` | both must be checked; `active` alone is not enough |
| `markets[].description` | contains the settlement rule |

**Contract type comes from the title, and getting it wrong invalidates everything:**

| title pattern | type |
|---|---|
| `What price will Bitcoin hit in 2026?` | **touch** — any time before expiry |
| `Bitcoin above ___ on September 11?` | terminal threshold |
| `Bitcoin price on September 11?` | terminal bucket |

Touch probability is always greater than or equal to terminal probability at the same
level. Options give terminal directly and touch not at all. `measure_polymarket.py`
excludes touch ladders explicitly and reports how many it dropped, so the exclusion
stays visible instead of becoming a silent filter.

Settlement differs from Deribit on both axes. Polymarket daily ladders resolve on the
Binance BTC/USDT one-minute candle close at 16:00 UTC; Deribit expires 08:00 UTC on
its own index. That is an eight-hour gap and a different price source. The measurement
reports the gap per ladder and splits results by gap size rather than assuming it away.

---

## `events/trades/` — trade flow

NDJSON, one trade per line, roughly 2,200 lines per run. Only trades new since the
previous run are written; `state/watermark.json` holds the per-market high-water mark
and `transactionHash` de-duplicates.

```json
{
  "proxyWallet": "0xece7...",
  "side": "SELL",
  "asset": "1014920563...",
  "conditionId": "0x02deb9...",
  "size": 99.5,
  "price": 0.019861809,
  "timestamp": 1789084519,
  "outcome": "Yes",
  "outcomeIndex": 1,
  "transactionHash": "0x..."
}
```

Ten fields, and that is the whole row. **From archive version 4 (2026-09-16) nine
vendor fields are dropped before writing** (D-087):

| dropped | why |
|---|---|
| `name`, `pseudonym`, `bio`, `profileImage`, `profileImageOptimized` | somebody's profile, not market data. `name` was populated on 6,568 of 7,081 rows in one run. Nothing here reads them. |
| `icon`, `title`, `slug`, `eventSlug` | repeated on every row and already stored once per run in `polymarket_events/`. `conditionId` resolves them. |

Together they were 47.5% of the bytes; measured after the change, 415 bytes a
trade against 790.

`proxyWallet` and `transactionHash` are KEPT. A wallet is an actor key, which
concentration work needs, and both are already public on-chain — the hash is
also what lets somebody else verify a row.

This is one of **two** deliberate exceptions to rule 2 (raw data stored as it
arrives); `holders/` below is the other. It is allowed because the rule exists so that a changed methodology
can be recomputed from the archive, and none of the dropped fields can enter a
recomputation of a price, a probability or a fee. Files written before
2026-09-16 still contain them.

Per-run files rather than one appended file: git stores whole blobs, so appending to a
growing file would re-store the entire history on every commit.

---

## `holders/` — who is on each side

Gzipped JSON, fetched **once a day** at 05:00 UTC (three runs a day write every other
stream; this one writes on the first). An object keyed by `conditionId`, each value a
list of token groups, each group a list of holders. Up to 80 conditions, `limit=100`
holders per token.

```json
{
  "0xa1b2...": [
    {
      "token": "45438797913102633064...",
      "holders": [
        { "proxyWallet": "0x6dd4...", "amount": 153639.106938, "outcomeIndex": 0 }
      ]
    }
  ]
}
```

Three fields, and that is the whole row. **From archive version 5 (2026-09-16) eight
vendor fields are dropped before writing** (D-088):

| dropped | why |
|---|---|
| `name`, `pseudonym`, `bio`, `profileImage`, `profileImageOptimized`, `displayUsernamePublic`, `verified` | somebody's profile, not market data. `name` was populated on 9,622 of 10,409 rows in one file; `profileImageOptimized` on 0 of them. Nothing here reads any of them. 48.4% of the field bytes. |
| `asset` | the token id, repeated on every holder row, and already the key of the group the row sits in. Equal on 10,409 of 10,409 rows, 0 mismatches — so this removal is **lossless**, unlike the one above. 25.1% of the field bytes. |

Measured on the real 2026-09-15T0505Z file: 3,696,191 plain bytes → 1,010,677
(−72.7%), 648,806 gzipped → 267,123 (−58.8%).

`proxyWallet` is KEPT, for the reason given under `events/trades/`.

This is the second deliberate exception to rule 2, on the same narrow grounds: a
holder's display name cannot enter a recomputation of a price, a probability or a
fee. Files written before 2026-09-16 still contain all of it.

### Two things a reader must know before using this stream

**It is a top-100 truncation, not a holder set.** 77 of 150 token groups in the file
measured were at the `limit=100` cap. There is no tail and no total, so a Gini, an
HHI or a true largest-holder share cannot be computed from it — only "how much do
the top 100 hold". B-007 assumed otherwise.

**A `null` value is not an empty market.** One condition returned a JSON `null` body
rather than a list. It is stored exactly as it arrived, so `null` and "nobody holds
this" look alike in the file. `_meta.holders_unexpected` counts these per run:
`null` means the stage did not run, `0` means it ran and every payload was a list.

---

## `coverage/` — did we actually get everything?

An array with one entry per market fetched, written so that gaps are auditable instead
of assumed away.

| field | meaning |
|---|---|
| `fetched_utc` | fetch time |
| `returned` | rows returned |
| `new` | new after de-duplication |
| `pages` | pages fetched |
| `oldest_ts` / `newest_ts` | trade timestamp range seen |
| `previous_watermark` | where the last run stopped |
| `limit_hit` | hit the fetch limit |
| `pagination_worked` | pagination returned new rows |
| `first_time` | first time this market was seen |
| `GAP` | gap detected |

`limit_hit` is the field to watch. In the run of 2026-09-11, 148 of 446 markets hit
the limit while `GAP` was false everywhere. Pagination reported success, so there is
probably no gap — but "probably" is not a measurement, and this has not been verified.

---

## `_meta/` — what the run did

Plain JSON. Carries `snapshot_utc`, per-stage timings, the list of files written, any
errors, a Kalshi summary and, from version 6, a funding summary (points returned
per perpetual and the window asked for). `version` says which archive version wrote
the run: 6 is the first with `raw/funding/`.

The field that governs whether a comparison is meaningful:

```json
"sync_window_seconds": 0.85
```

This is the elapsed time between reading the option chain and reading the prediction
market. **Measured over the 48 runs in the public window on 2026-09-18:** minimum 0.62 s,
median 1.19 s, p90 1.93 s, maximum 3.29 s.

A range is written here as a distribution and with its date, because the earlier
wording — "0.66 to 2.04 seconds" — was a range taken once and left standing. It was
already wrong when it was written (a 2.68 s run of 2026-09-13 was in the archive),
and a stop condition keyed on it fired on an ordinary slow response (D-111).

The two widest runs on record share one signature: the Deribit read is normal and
the Polymarket read is slow. The window is `polymarket_end`, so it is bounded by
whichever of the two venues answers last; nothing added to the collector after that
mark can move it. A measured difference smaller
than what the price can move inside that window is not a market view, it is timing
noise. An early experiment with an eight-minute gap moved a result by 33%.

---

## `state/latest.json` — the pointer

Written every run so that a reader can find the newest snapshot with one request:

```json
{
  "version": 2,
  "stamp": "2026-09-11T0515Z",
  "sync_window_seconds": 0.85,
  "paths": { "kalshi": "raw/kalshi/...", "deribit": "...", "polymarket_events": "...",
             "funding": "raw/funding/..." },
  "archive": { "day_count": 13, "snapshot_count": 40 }
}
```

Before this file existed, the web page listed directories through the GitHub contents
API. That cost about 18 API calls per page load and grew by one call per archive day.
The unauthenticated limit is 60 per hour, so a visitor could open the page roughly
three times before it broke, and it got worse daily.

---

## Reading the archive from Python

Do not parse paths by hand. `scripts/archive.py` does it:

```python
from archive import snapshot, stamps

g = snapshot()                         # newest snapshot
g = snapshot('2026-09-10T1312Z')       # a specific one

g.kalshi, g.deribit, g.polymarket      # decompressed JSON
g.meta, g.sync_window, g.stamp, g.day

stamps('_meta')                        # every stamp, oldest first
```

`Missing` is raised when a stream is READ, not when `snapshot()` is called. A try
block around `snapshot()` alone does not catch it — that mistake crashed
`audit_semantics.py` on its first CI run (D-075).

An absent stream raises `Missing` rather than returning empty. Kalshi was added on
2026-08-31, so the first five snapshots have no Kalshi file; measurements report those
as unmeasurable instead of silently scoring zero.
