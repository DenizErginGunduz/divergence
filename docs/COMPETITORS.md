# COMPETITORS.md — prior work and competitor register

**Status:** seeded 2026-09-16 · **Decided in:** D-098
**Rule:** every field is either read from a page on the date given, or `UNKNOWN`. No
field is inferred. An entry whose name could not be found says so, with the searches
that were run, rather than being dropped — the point of the register is that nobody
rediscovers or re-invents these in six months.

**Why this file exists.** "Prediction-market price versus Deribit option-implied
probability" is not sufficient differentiation: at least one institutional analytics
firm, one academic paper and one paid retail product do the same comparison (entries
4, 5, 7). Where Divergence may differ is the discipline, not the comparison —
model-free spread digitals, quote-side executable envelopes, both venues' fee
schedules, maturity and grid sensitivity, verbatim settlement audits, refusal where
no two-sided quote exists, and recorded retractions. That is a hypothesis about
differentiation; the entries below are the evidence for and against it. Novelty is
not to be overstated in any document, and this register is the check.

**Categories.** `research paper` · `live product` · `analytics firm` · `open-source
code` · `commentary` · `NOT FOUND`. **Overlap** is with Divergence's Layer A
question; **differentiation** lists only what is evidenced on the page read.

---

## 1. "Fabi et al." / "Fair Odds" — NOT FOUND

| field | value |
|---|---|
| NAME | "Fabi et al." / "Fair Odds", as named in the review synthesis |
| URL | UNKNOWN — no page found |
| CATEGORY | NOT FOUND |
| WHAT THEY DO | UNKNOWN. The synthesis describes research comparing Polymarket BTC/ETH contracts against Deribit option-implied benchmarks, with a live surface. |
| SEARCHES RUN (2026-09-16) | "Fabi" with Polymarket / Deribit / option-implied / arXiv / SSRN, five variants; no paper, author page or product surfaced. The nearest academic match (entry 5) cites no author named Fabi and nothing titled "Fair Odds". |
| NEAREST MATCHES | entry 5 (Portnaya, arXiv 2606.19517); entry 6 (Lee, Lee & Lee, SSRN 6748186); entry 7 (Bitcoin Edge) |
| ACTION | The owner is asked for a URL. Until one exists, no claim about this work is made anywhere in the repository. |
| DATE LAST CHECKED | 2026-09-16 |

## 2. FairOdds (fairodds.app) — exists, unrelated

| field | value |
|---|---|
| NAME | FairOdds |
| URL | https://fairodds.app/implied-probability |
| CATEGORY | live product — sports-betting calculators |
| WHAT THEY DO | Odds-format conversion (decimal / American / fractional ↔ implied probability), Kelly, EV, arbitrage and no-vig calculators |
| METHOD | Arithmetic odds conversion. No options data, no option model, no maturity handling, no bid/ask, no fees. |
| TARGET USER | Sports bettors |
| DATA | User-entered odds only |
| STRENGTHS | Simple, free |
| WEAKNESSES | Does not mention Polymarket, Deribit, crypto, BTC or options |
| OVERLAP | None |
| DIFFERENTIATION | Not a competitor. The synthesis's description ("live Polymarket-vs-options reference-pricing product") does not match the page read; whether a different "FairOdds" exists is UNKNOWN. |
| DATE LAST CHECKED | 2026-09-16 |

## 3. PolyGap — NOT FOUND

| field | value |
|---|---|
| NAME | PolyGap, as named in the review synthesis |
| URL | UNKNOWN — no page found |
| CATEGORY | NOT FOUND |
| WHAT THEY DO | UNKNOWN. The synthesis describes a crypto prediction-market vs Deribit comparison terminal. |
| SEARCHES RUN (2026-09-16) | "PolyGap" with Polymarket / Deribit / crypto / prediction market terminal; polygap.io / .xyz / .app; two tool directories read (Awesome-Prediction-Market-Tools on GitHub; launchpoly.com, 142 tools) list nothing by this name and nothing described as a Polymarket-vs-options comparison. |
| NEAREST MATCHES | entry 8 (djienne, open-source); `Romil10/gap369` on GitHub, described as a "prediction market comparison portal" — not read in depth, options use UNKNOWN |
| ACTION | The owner is asked for a URL. No claim about this work is made until one exists. |
| DATE LAST CHECKED | 2026-09-16 |

## 4. Block Scholes — DIRECT / ADJACENT

| field | value |
|---|---|
| NAME | Block Scholes |
| URL | https://www.blockscholes.com/use-cases/digital-options-prediction-markets · https://www.blockscholes.com/research/the-renaissance-of-onchain-options · https://www.blockscholes.com/research |
| CATEGORY | analytics firm — institutional crypto derivatives data and research |
| WHAT THEY DO | Sells implied-volatility and volatility-surface data (API, WebSocket feeds, self-serve plans) and publishes research. A dedicated use-case page pitches using the surface data to find prediction-market mispricings; a 2 July 2026 report co-authored with Castle Labs compares Polymarket BTC/ETH strike odds against probabilities from the Block Scholes composite surface, strike by strike at matched strike and expiry. |
| METHOD | Parametric: SVI-calibrated surfaces ("SVI-calibrated surfaces provide the complete smile across all strikes"); binary probabilities read from the calibrated surface. Composite surface synthesised from multiple venues. Mid vs bid/ask: UNKNOWN. Fees: "transaction costs" mentioned qualitatively; no fee-schedule modelling evidenced. Maturity handling between listed expiries and prediction-market resolution: UNKNOWN (page says "identical strikes and expiration times"). |
| TARGET USER | Hedge funds, systematic traders, institutions |
| DATA | Deribit (named as the surface source in the July report) plus a multi-venue composite; Polymarket. Kalshi: not mentioned on the pages read. |
| STRENGTHS | Institutional-grade surfaces; multi-venue composite; real-time feeds; brand; a published empirical observation that the gap is not uniform across strikes |
| WEAKNESSES | No live public comparison dashboard evidenced; model-dependent (SVI); paid; no evidence of executable bid/ask envelopes, venue fee modelling, or settlement-rule audits |
| OVERLAP | High on the core question — Polymarket vs Deribit-implied digital probabilities, BTC/ETH, matched strike and expiry |
| DIFFERENTIATION | Divergence: model-free vertical-spread digitals, bid/ask envelopes on both legs, both venues' fee schedules, expiry-gap and strike-grid sensitivity, Kalshi coverage, verbatim settlement audits — none evidenced at Block Scholes. Block Scholes: composite multi-venue surface, institutional data API, ongoing paid research — none in Divergence. |
| DATE LAST CHECKED | 2026-09-16 |

## 5. Portnaya, arXiv 2606.19517 — DIRECT (academic)

| field | value |
|---|---|
| NAME | "Do Prediction Markets Match Option Prices? Bitcoin Threshold Evidence from Binance and Polymarket" — Victoria Portnaya, Kyiv School of Economics, June 2026 |
| URL | https://arxiv.org/abs/2606.19517 |
| CATEGORY | research paper |
| WHAT THEY DO | Compares Polymarket BTC threshold contract YES prices against option-implied risk-neutral binary values. Reports a mean gap of 5.6 percentage points (September 2023 contract, 214 hourly observations), 6.3 pp pooled (287 observations, three markets), t = 6.46; an AR(1) half-life of about four hours; a Deribit extension with about an 11 pp gap; delta-hedged backtests. |
| METHOD | Black–Scholes binary value `e^(−rT)·Φ(d2)`, implied volatility inverted from listed call mid-prices; very short maturities excluded; a friction band combining both venues' fees and half-spreads. Not model-free; no strike-spread digital; no expiry or grid sensitivity evidenced. |
| TARGET USER | Academic and finance researchers |
| DATA | Binance options end-of-hour archive, Binance spot hourly bars, Polymarket trades and hourly prices; Deribit for the extension. Sample: mid-2023. Kalshi: not mentioned. |
| STRENGTHS | Econometric rigour (HAC intervals, block bootstrap), persistence analysis, an explicit fee-plus-spread friction band |
| WEAKNESSES | 2023 sample; single-IV Black–Scholes benchmark; mid prices only; no code or live implementation; no settlement-rule discussion |
| OVERLAP | High on the question; low on method and recency |
| DIFFERENTIATION | Divergence adds model-free spreads, executable bid/ask, Kalshi, settlement audits, sensitivity. The paper adds inference (t-statistics, half-life) that Divergence has not claimed and, per D-096, does not claim on the quoted-edge count. |
| DATE LAST CHECKED | 2026-09-16 |

## 6. Lee, Lee & Lee, SSRN 6748186 — ADJACENT (academic)

| field | value |
|---|---|
| NAME | "Cryptocurrency Prediction Markets through the Derivatives Lens: Evidence from Kalshi and Polymarket" — Seungju Lee, Yebon Lee, Jaewook Lee, Seoul National University; posted 2026-05-11, revised 2026-05-26 |
| URL | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6748186 |
| CATEGORY | research paper |
| WHAT THEY DO | Treats 113,338 Kalshi and Polymarket BTC/ETH contracts (September 2025 – February 2026) as cash-or-nothing digitals; extracts implied-volatility surfaces and risk-neutral densities from the prediction markets themselves; reports a symmetric smile, a positive variance risk premium, and a Polymarket VRP about 16× Kalshi's. |
| METHOD | Digital-option pricing applied to prediction-market prices. Whether Deribit is used as an external benchmark: UNKNOWN from the abstract. Mid / bid-ask, fees: UNKNOWN. |
| TARGET USER | Academic |
| DATA | Kalshi, Polymarket |
| OVERLAP | Same venues and assets; the opposite direction — surfaces derived from prediction markets rather than benchmarked against Deribit |
| DIFFERENTIATION | No code or live implementation evidenced. Relevant to Note 3 (long-shot premium) as prior work on the wings. |
| DATE LAST CHECKED | 2026-09-16 |

## 7. Bitcoin Edge (The 7 Oracles) — DIRECT (live, paid)

| field | value |
|---|---|
| NAME | Bitcoin Edge |
| URL | https://predictionmarketspicks.com/tools/bitcoin-edge |
| CATEGORY | live product — free headline, paid tier |
| WHAT THEY DO | Live options-vs-Kalshi comparison for hourly `KXBTCD` contracts; a signed edge `model_prob − kalshi_yes_price`; logs and grades every signal at settlement. Shows Polymarket reference prices but derives edges only from `KXBTCD` vs IBIT options. |
| METHOD | Black–Scholes `N(d2)`; implied volatility from IBIT (ETF) option mid-prices; a smile filter and IV clamps; a 4-week T-bill rate; a flat ~5 pp round-trip Kalshi slippage haircut; snapshots only during US options hours. Fees beyond the haircut: UNKNOWN. Not model-free; no Deribit. |
| TARGET USER | Active retail / semi-professional Kalshi traders |
| DATA | Kalshi `KXBTCD` (settles on CF Benchmarks BRTI); IBIT options; Polymarket, Coinbase and Robinhood reference prices |
| STRENGTHS | Live; graded track record; explicit liquidity guards; cheap |
| WEAKNESSES | IBIT proxy rather than BTC options (ETF hours only — no overnight or weekend coverage); parametric; Polymarket not benchmarked |
| OVERLAP | Medium — a live Kalshi BTC edge signal on the same hourly family Divergence measures as "intraday cum" |
| DIFFERENTIATION | Divergence: Deribit 24/7 chains, model-free digitals, envelopes, both venues' fees, both prediction venues, settlement audits. Bitcoin Edge: signal auto-grading and a paid product — which is also what Divergence is not (a signal service). |
| DATE LAST CHECKED | 2026-09-16 |

## 8. djienne / POLYMARKET_UP_DOWN_DERIBIT_STRATEGY — ADJACENT (open source)

| field | value |
|---|---|
| NAME | POLYMARKET_UP_DOWN_DERIBIT_STRATEGY |
| URL | https://github.com/djienne/POLYMARKET_UP_DOWN_DERIBIT_STRATEGY |
| CATEGORY | open-source code (Python, Docker); 27 stars, 4 forks on the date checked; licence UNKNOWN; last update UNKNOWN |
| WHAT THEY DO | Terminal probability calculator for BTC above/below a price at a future time; backtester and optimiser for Polymarket daily BTC up/down markets |
| METHOD | SSVI surface calibrated on Deribit BTC options; Breeden–Litzenberger density; Monte Carlo; Heston fallback. Mid vs bid/ask for the density: not specified. Fees: UNKNOWN. Polls the Deribit chain every 5 minutes, Polymarket prices every 5 minutes, CLOB bid/ask every minute. |
| TARGET USER | Self-hosting individual |
| DATA | Deribit, Polymarket. Kalshi: no. |
| OVERLAP | High on data; parametric rather than model-free; up/down rather than threshold contracts |
| DIFFERENTIATION | No public live surface; a strategy tool rather than a measurement. |
| DATE LAST CHECKED | 2026-09-16 |

## 9. Commentary and adjacent items (read, not competitors)

- Vertox, "How to Price Polymarket Up-Down Markets" (2025-11-16) — Deribit IV → SVI → Monte Carlo for touch-style markets; educational, paywalled, no tool. https://www.vertoxquant.com/p/how-to-price-touch-style-options
- dev.to, "Probability Arbitrage … Deribit Options" (2026-03-03) — Black–Scholes `d2` with Deribit IV vs Polymarket up/down; sells a bot; companion repo not read. https://dev.to/xniiinx/probability-arbitrage-how-to-beat-polymarket-using-deribit-options-ln1
- podshopguy, "polymarket overprices volatility" (2025-01-21) — IBIT call/put spreads vs Polymarket over/under, mid prices, no tool. https://podshopguy.substack.com/p/polymarket-overprices-volatility
- Investing.com, Jared Polites (2026-08-05) — Breeden–Litzenberger vertical-spread extraction for Fed / index markets; notes Kalshi vs Polymarket fee curves; no crypto, no tool. https://www.investing.com/analysis/when-markets-disagree-prediction-odds-and-optionsimplied-probabilities-200685270
- 1Token Research (2026-07-09) — Polymarket / Kalshi binaries vs Deribit vanillas, case studies; product is portfolio reconciliation. https://blog.1token.tech/trading-crypto-wisely-on-prediction-market/
- CryptoDaily (2026-07-16) — journalism summarising the arXiv result; names no tools. https://cryptodaily.co.uk/2026/07/prediction-markets-vs-options-pricing-gaps
- dev.to, Ayrat Murtazin (2026-04-20) — Black–Scholes `N(d2)` with equity IV vs Polymarket stock markets; not crypto. https://dev.to/ayratmurtazin/black-scholes-on-polymarket-finding-mispriced-binary-events-with-python-2m50
- Castle Labs, "Prediction markets as option-like instruments" — not read (HTTP 429 twice). https://research.castlelabs.io/p/prediction-markets-as-option-like
- Kaiko, "Prediction Markets Liquidity In Focus" — not read (redirect to app). 

---

## What the register says about differentiation, on this evidence

Nothing read combines, in one place: a model-free vertical-spread digital with
executable bid/ask on both legs; both venues' published fee schedules; expiry-gap and
strike-grid sensitivity; verbatim settlement-rule audits; and coverage of both Kalshi
and Polymarket against Deribit. That combination is the differentiation hypothesis
(D-098). Three named competitors from the review could not be verified (entries 1–3);
the strongest verified analogues are Block Scholes (institutional, SVI, paid) and
Portnaya (academic, Black–Scholes, 2023 data). The register is re-checked when any
document claims novelty, and at least quarterly.
