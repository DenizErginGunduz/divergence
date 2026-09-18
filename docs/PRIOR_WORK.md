# PRIOR_WORK.md — prior work, adjacent research and live products

**Status:** seeded 2026-09-16 · **Decided in:** D-098
**Why this file exists.** A measurement project should know what has already been
measured, by whom, and with what method — before claiming anything. This register is
that survey. It is also the record that nothing here was taken from anyone: where a
result or a construction was published first by somebody else, it says so and names
them.

**Rule:** every field is either read from a page on the date given, or `UNKNOWN`. No
field is inferred. An entry whose name could not be found says so, with the searches
that were run, rather than being dropped — the point of the register is that nobody
rediscovers or re-invents these in six months.

**Why this file exists.** "Prediction-market price versus Deribit option-implied
probability" is not sufficient differentiation: at least one institutional analytics
firm, one academic paper and one paid retail product do the same comparison (entries 1, 3, 4, 5, 6, 7, 10).
Entry 4 publishes the call-spread derivation this project treats as its own starting
point, and entry 9 carries the executable framing further than we do (D-110). Where Divergence may differ is the discipline, not the comparison —
model-free spread digitals, quote-side executable envelopes, both venues' fee
schedules, maturity and grid sensitivity, verbatim settlement audits, refusal where
no two-sided quote exists, and recorded retractions. That is a hypothesis about
differentiation; the entries below are the evidence for and against it. Novelty is
not to be overstated in any document, and this register is the check.

**Categories.** `research paper` · `live product` · `analytics firm` · `open-source
code` · `commentary` · `NOT FOUND`. **Overlap** is with Divergence's Layer A
question; **differentiation** lists only what is evidenced on the page read.

---

## 1. Fabi, Marfè, Ruffo & Schönleber — and FairOdds, which is the same team — DIRECT

| field | value |
|---|---|
| NAME | "Cross-Market Pricing in Prediction Markets: A Comparison with Derivatives" — M. Fabi (Telecom Paris / ENSAE), R. Marfè (Collegio Carlo Alberto & Turin), V. Ruffo (Frankfurt School), L. Schönleber (Collegio Carlo Alberto & Turin), 31 August 2026 · and **FairOdds**, the live product built on it |
| URL | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6565258 · https://fairodds.io/ · https://fairodds.io/methodology · https://zoquantsolutions.com/ |
| CATEGORY | research paper + live product, one team |
| HOW READ | Paper **read in full 2026-09-18** from the 95-page PDF supplied by the owner (the SSRN page itself was behind a bot check on 2026-09-16 and the first version of this entry was second-hand; see the correction in D-110). Site read 2026-09-18. |
| TITLE HISTORY | The PDF's own first-page footnote: *"This paper previously circulated as ‘Market Efficiency in Prediction Markets: A Comparison with Derivatives’."* Both titles are real. Recorded because this register briefly asserted the opposite. |
| WHAT THEY DO | Compare Polymarket BTC and ETH contracts against option-implied benchmarks (OIP) from Deribit. Four contract types: **Above** and **Range** (terminal-value, European cash-or-nothing digitals) and **Reach** and **Dip** (upper/lower barrier, one-touch / first-passage). The object of study is the **CLOB−OIP wedge** and what explains it — payoff structure, maturity, directional demand, sentiment, announcements, volatility, cross-exchange fragmentation, wallet size — organised by a limits-to-arbitrage model with a specialist sector. |
| SAMPLE | **4,860 contracts** (2,550 BTC, 2,310 ETH), ~**4.4 million trades**, **927,450** hourly CLOB−OIP observations. Deribit surfaces January 2023 – December 2025; contract-level sample January 2024 – November 2025. |
| METHOD | Deribit data **bought from Amberdata** as hourly fixed-delta implied-volatility surfaces — not the option chain. Black pricing to recover strikes and forward prices, then the **Kou (2002) double-exponential jump-diffusion** calibrated at 7, 14, 30 and 60 days, which prices terminal and barrier payoffs in one framework. No-lookahead enforced at the CLOB timestamp. On the live site the comparison is struck against the Polymarket **YES midpoint**. |
| FEES AND EXECUTION | The paper has appendices measuring Polymarket bid-ask spreads (III.6) and on-chain gas fees (III.5), used as descriptive and regression variables. Neither is charged against the wedge, and the option leg has no executable side by construction. The word "fee" does not appear on the methodology page at all. |
| WHAT THEY SAY ABOUT EXPLOITABILITY, VERBATIM | Paper: wedges are interpreted "as cross-market pricing wedges relative to the stated benchmark, rather than automatically as exploitable arbitrage profits." Site: "The resulting OIP is a maturity-aligned benchmark price—not an executable option quote." |
| HEADLINE RESULTS | Contract-level time-series correlations 0.88 Above, 0.77 Range, 0.88 Reach, 0.86 Dip. 72.6% of contract-mean wedges positive; equal-contract mean +0.72 pp, median +0.63, mean absolute 2.25 pp. Reach wedge falls from 3.80 pp early in contract life to ~0 near expiry. Polymarket-implied Kou fit places more mass beyond the 5th/95th percentile cutoffs than Deribit: +0.85 / +0.82 pp for BTC, +0.21 / +0.48 pp for ETH. Larger wallets allocate more notional to larger absolute wedges. |
| STANDING | Presented at ~13 conferences (Moscow Finance, FC26 DeFi Workshop, Scuola Normale Pisa, Global AI Finance, D2, Frontiers in DeFi and others). Schönleber: Assistant Professor, Collegio Carlo Alberto & Turin; Professor of Practice at Frankfurt School from 2027; published in the Journal of Banking and Finance and BIS Bulletin No. 115; founder of the ToDeFi conference, co-organised with the Bank of Italy since 2024. |
| PRODUCT STATE (2026-09-18) | Reachable on 2026-09-18; returned 504 on two attempts on 2026-09-16. Tracks 502 markets. The dashboard shows an upstream-snapshot timestamp and a staleness notice when that timestamp is old; it did on the read date. No public repository, no linked social accounts and no pricing page were found. Recorded as what one visit saw, on one date. |
| OVERLAP | **The highest in this register.** Same two venues, same assets, same question, a sample two orders of magnitude larger than ours, and a published economic model of the wedge. |
| DIFFERENTIATION | Not "we do it better" — we do not. The difference is what is measured: they measure **how large the wedge is and what explains it**; Divergence measures **how much of it survives at the prices one could actually hit, after both venues' published fees**. Their own two sentences above say that second question is outside their scope. Concretely: chain rather than a bought surface, spread digital rather than Kou, executable sides rather than midpoint, both fee schedules, two bracketing expiries, strike-grid sensitivity, verbatim settlement audits, refusal on one-sided books, and Kalshi — which they do not cover at all. |
| WHAT IT COSTS US | Any claim of novelty for the comparison itself. Note 1 says so in "What else exists" and must keep saying so. |
| DATE LAST CHECKED | 2026-09-18 |

## 2. fairodds.app — a different site with the same name, not a competitor

| field | value |
|---|---|
| URL | https://fairodds.app/implied-probability |
| CATEGORY | live product — sports-betting calculators |
| WHAT THEY DO | Odds-format conversion, Kelly, EV, arbitrage and no-vig calculators. No options data, no crypto, no Polymarket. |
| WHY IT IS HERE | It surfaced first when "FairOdds" was searched on 2026-09-16 and was briefly mistaken for the product the review synthesis meant. Kept so the next person does not repeat the search. The real one is entry 1. |
| DATE LAST CHECKED | 2026-09-16 |

## 3. PolyGap — DIRECT (live, paid)

| field | value |
|---|---|
| NAME | PolyGap — "Polymarket Edge: Mispricings, LP Rewards & Bot API" |
| URL | https://polygap.io/ |
| CATEGORY | live product — free tier with locked fields, paid tier, REST API, packaged bots |
| WHAT THEY DO | "Prices every Polymarket crypto market against Deribit's options curve" and ranks funded Polymarket liquidity-reward pools. Terminal refreshes every 2 minutes; on the page as read the board showed **0** crypto markets clearing its **3-point gap threshold**, and 40 reward pools. Columns: MARKET / ASSET / **CROWD** / **FAIR** / CROWD to FAIR / GAP / **SIGNAL**. |
| METHOD | **Parametric, stated on the page:** "We pull Deribit's live options surface — implied volatility by strike and expiry — and convert it into the fair probability of each Polymarket question: **N(d2)** for 'above $X', **a barrier model** for 'hit $X'." No bid/ask side, no fee schedule, no expiry-gap treatment and no settlement-text audit are evidenced. The Polymarket side is described as "the crowd price". |
| TARGET USER | Retail Polymarket traders and bot operators |
| DATA | Deribit options surface; Polymarket CLOB; Polymarket LP reward pools |
| PRICING | Free tier shows which markets are in play; fair value, gap and reward-per-$ are locked. Pro **$30/month in USDC** (Polygon) or USDT (BEP20): fair value, gap, signal, reward rankings, Telegram alerts, JSON API (120 req/min), and "Autopilot" and "Autotrader" bots that run through the user's own wallet with dry-run, size caps and daily limits by default. |
| STRENGTHS | Live, shipped, priced and monetised; an API and two bots; a second product line (LP reward optimiser) with nothing to do with options; two-minute refresh |
| WEAKNESSES | Model-dependent on both contract types; a mid-style "crowd" price against a model "fair", so the gap is not an executable quantity; no fee treatment evidenced; the barrier model is exactly the path-dependent case this project refuses to model |
| OVERLAP | **Very high on the question, low on the method.** Same two venues, same asset class, same comparison. |
| DIFFERENTIATION | Divergence: model-free spread digitals rather than N(d2); executable bid/ask envelopes on both legs; both venues' published fee schedules; expiry-band and strike-grid sensitivity; verbatim settlement audits; refusal where no two-sided quote exists; Kalshi. PolyGap: shipped, paid, an API, bots, LP rewards, an audience — **none of which Divergence has**. |
| TERMINOLOGY, FOR CONTRAST | The page describes the option side as the sharper reference and presents a signal column. Divergence's own terminology rules are stricter by choice — "true probability" is not used, and a price difference is not called an opportunity — which is a difference in what each project is for, not a criticism of a product built for a different reader. |
| DATE LAST CHECKED | 2026-09-16, terminal timestamped 18:57 UTC on the page |

## 4. Block Scholes — DIRECT / ADJACENT

| field | value |
|---|---|
| NAME | Block Scholes |
| URL | https://www.blockscholes.com/use-cases/digital-options-prediction-markets · https://www.blockscholes.com/research/the-renaissance-of-onchain-options · https://www.blockscholes.com/research |
| CATEGORY | analytics firm — institutional crypto derivatives data and research |
| WHAT THEY DO | Sells implied-volatility and volatility-surface data (API, WebSocket feeds, self-serve plans) and publishes research. A dedicated use-case page pitches using the surface data to find prediction-market mispricings; a 2 July 2026 report co-authored with Castle Labs compares Polymarket BTC/ETH strike odds against probabilities from the Block Scholes composite surface, strike by strike at matched strike and expiry. |
| METHOD — CORRECTED 2026-09-16 (D-110) | **Both parametric and model-free.** The July report derives the binary from a **call spread** and states in plain words that *"binary option prices (and therefore the prices of prediction markets on the same underlying asset) are uniquely determined by the prices of vanilla call options"*, then walks the reader through removing the linear ramp. That is this project's Layer A premise, published 2 July 2026. The surface work alongside it is parametric: SVI-calibrated surfaces ("SVI-calibrated surfaces provide the complete smile across all strikes"); binary probabilities read from the calibrated surface. Composite surface synthesised from multiple venues. Mid vs bid/ask: UNKNOWN. Fees: "transaction costs" mentioned qualitatively; no fee-schedule modelling evidenced. Maturity handling between listed expiries and prediction-market resolution: UNKNOWN (page says "identical strikes and expiration times"). |
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

## 9. Gebele, Mutzel & Matthes, arXiv 2608.00666 — ADJACENT (academic)

| field | value |
|---|---|
| NAME | "Executable Arbitrage and Market Efficiency in Prediction Markets" — Jonas Gebele, Timm Mutzel, Florian Matthes; submitted 1 August 2026, cs.CE |
| URL | https://arxiv.org/abs/2608.00666 |
| CATEGORY | research paper |
| WHAT THEY DO | Separates **payoff-space** no-arbitrage (implied by terminal payoffs) from **protocol-executable** no-arbitrage (what the protocol lets a trader do before settlement), using Polymarket's negative-risk markets, where the NegRisk Adapter operationalises only the NO-to-YES direction. Reconstructs **depth-aware executable portfolio values**, combines them with actor-level transaction histories and on-chain conversion traces, and estimates **$1.12 m** of arbitrage profit ($1.086 m converter-enabled, $32 k settlement-based). Positive violations concentrate on the unsupported YES side. Implements a prototype bidirectional adapter. |
| METHOD | Depth-aware executable reconstruction; on-chain trace matching; no option model — the comparison is internal to Polymarket, not against derivatives |
| OVERLAP | **Low on the question, high on the instinct.** They do not compare against options at all. But "a bound violation is not an opportunity unless it is executable" is their thesis and ours, and they carry it further: depth-aware, not top of book. |
| DIFFERENTIATION | Divergence compares two venues with different settlement sources; they compare linked contracts inside one protocol. Ours is a cross-market pricing question, theirs a protocol-design question. |
| WHAT IT COSTS US | The word "executable" in our differentiation claim is not ours alone, and their execution standard is stricter than ours. D-095's distinction between quoted-executable and size-executable is the right one, and this paper is the reason to keep it visible: they measured the second, we have measured the first. |
| DATE LAST CHECKED | 2026-09-16 (abstract page read in full; PDF not read) |


## 10. De Stefano — btc-prediction-market-efficiency — DIRECT (academic, open source)

| field | value |
|---|---|
| NAME | "Cross-Market Mispricing in Bitcoin Prediction Markets: Evidence from Polymarket, Kalshi, and Deribit" — Giannandrea De Stefano, MSc Economics and Finance, LUISS Guido Carli |
| URL | https://github.com/giannandreadestefano/btc-prediction-market-efficiency |
| CATEGORY | open-source code and MSc thesis; MIT licence; 33 commits; 0 stars, 0 forks on the date checked |
| WHAT THEY DO | Asks whether Polymarket and Kalshi BTC prediction-market prices differ systematically from a Deribit-implied benchmark. **33,107 observations, 6,566 unique contracts, March 2024 to June 2026**: 19,649 Polymarket terminal, 10,323 Polymarket path-dependent, 3,135 Kalshi (first timestamped trade within 30 minutes of open). Six sequential notebooks from collection to regressions. |
| METHOD | **Parametric and spot-based, not chain-based.** Benchmark is Black-Scholes `P(S_T > K) = Phi(d2)` with matched BTC spot, strike, time to maturity and a **DVOL**-derived volatility input — Deribit's volatility *index*, not its option chain. Signed and absolute pricing-difference measures, bootstrap inference, OLS with robust and clustered errors, monthly and horizon robustness. Explicitly calls the benchmark "a risk-neutral-style probability proxy, rather than a physical probability forecast". |
| DATA | Polymarket, Kalshi `KXBTC`, BTC spot, Deribit DVOL. Full datasets deliberately **not redistributed**; one illustrative sample CSV is published, and the author states the repository is not a one-click reproduction package. |
| STRENGTHS | The same three venues as this project; a two-year sample against our seventeen days; separates terminal from path-dependent contracts; proper inference; states its own limits, including the data-rights one, in the README |
| WEAKNESSES | A single volatility number per observation (DVOL) rather than a strike-by-strike chain, so no smile and no per-strike digital; no bid/ask side; no fee schedules; no settlement-text audit; ETH not covered |
| OVERLAP | **High.** The closest published match to this project's venue triple. |
| DIFFERENTIATION | Chain-based model-free digitals against a DVOL Phi(d2) proxy; executable envelopes; both fee schedules; expiry-band and grid sensitivity; verbatim settlement rules; ETH. The sample-size comparison runs the other way and is to be stated that way. |
| DATE LAST CHECKED | 2026-09-16 |


## 11. Commentary and adjacent items (read, not competitors)

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
