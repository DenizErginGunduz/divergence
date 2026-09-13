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

## `kalshi/` — catalogue and markets

```json
{
  "catalogue": { "Crypto": { "series": [...] }, "Financials": { "series": [...] } },
  "selection": { "crypto": [...62 series tickers...], "observed": [...30...] },
  "markets":   { "<SERIES_TICKER>": [ ...market objects... ] },
  "observed":  { "<SERIES_TICKER>": [ ... ] }
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

A market object carries 41 fields. The ones the measurements use:

| field | meaning |
|---|---|
| `ticker` | unique and stable. Use it as the identity of a rung across runs. |
| `strike_type` | `less`, `greater` or a range type |
| `floor_strike`, `cap_strike` | bucket bounds |
| `yes_bid_dollars`, `yes_ask_dollars` | prices as **decimal strings**, `"0.9900"` |
| `status` | only `active` markets are measured |
| `close_time` | resolution time, ISO 8601 |
| `open_interest_fp`, `volume_fp` | size |
| `rules_primary`, `rules_secondary` | settlement rules **in full text** |

Keep `rules_primary` verbatim. The wording decides whether a contract is terminal or
touch, and that distinction decides whether a comparison is valid at all.

Bucket boundaries need care. `cap_strike` can be `24999.99` while the next bucket's
`floor_strike` is `25000`. Rounding the two independently makes them disagree, the
digital picks different bracketing strikes on each side of the same boundary, one
region gets counted twice, and the densities sum to about 1.13 instead of 1. The
correct form is `round(cap + 0.01)`. `measure_exhaustive.py` demonstrates all three
variants against the archive.

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
  "conditionId": "0x02deb9...",
  "size": 99.5,
  "price": 0.019861809,
  "timestamp": 1789084519,
  "title": "Will Bitcoin hit $150k by December 31, 2026?",
  "outcome": "Yes",
  "transactionHash": "0x..."
}
```

Per-run files rather than one appended file: git stores whole blobs, so appending to a
growing file would re-store the entire history on every commit.

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
errors, and a Kalshi summary.

The field that governs whether a comparison is meaningful:

```json
"sync_window_seconds": 0.85
```

This is the elapsed time between reading the option chain and reading the prediction
market. Observed range so far is 0.66 to 2.04 seconds. A measured difference smaller
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
  "paths": { "kalshi": "raw/kalshi/...", "deribit": "...", "polymarket_events": "..." },
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

An absent stream raises `Missing` rather than returning empty. Kalshi was added on
2026-08-31, so the first five snapshots have no Kalshi file; measurements report those
as unmeasurable instead of silently scoring zero.
