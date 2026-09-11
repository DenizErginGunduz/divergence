# Divergence

Two markets price the same future event. This measures how far apart they are, and
how much of that distance survives contact with reality.

Prediction markets (Kalshi, Polymarket) quote a probability directly. Listed options
(Deribit) imply one through the price difference between neighbouring strikes. Same
question, two answers, no model required to compare them.

Not a betting app, not a trading bot, not a signal service.

---

## The catch that makes this non-trivial

**Touch is not terminal.** "Will Bitcoin hit $150k this year" asks whether the price
touches that level at any point. "Will Bitcoin be above $150k on December 31" asks
where it closes. Touch probability is always greater than or equal to terminal at the
same level. Options give terminal directly and touch not at all. Confusing the two
breaks every number downstream, and the two questions sit side by side on the same
exchange with almost identical wording.

**Settlement rarely lines up.** Polymarket daily ladders settle on a Binance candle at
16:00 UTC. Deribit options expire 08:00 UTC on Deribit's own index. Kalshi settles on
CF Benchmarks. Every comparison carries a time gap and a source mismatch, and the
honest move is to measure the gap rather than assume it away.

**A difference is not an opportunity.** Fees, spread, collateral cost, the variance
risk premium and measurement error all live inside the gap. Most of what looks like
mispricing is one of those.

---

## What has actually been measured

Archive: 13 days, 40 snapshots, three venues, collected three times daily since
2026-08-30. Every number below is regenerated from that archive by a script in this
repository — nothing is typed in by hand.

| setup | result | strength |
|---|---|---|
| Kalshi year-end buckets | 3 of 44 rungs beat the cost band, in 34 of 34 observations each | model-free |
| Polymarket dailies | 27.1% of rung-observations beat it, but 247 of 316 rungs are inconsistent | model-free, noisy |
| Long-horizon touch bound | 0.2% arithmetic violations; 94.9% above the 2x bound | model-dependent, weak |

The three Kalshi rungs that survive are all tails: BTC above $150k, ETH above $5k,
ETH above $1k. Nothing in the body of any distribution survives the cost band.

The touch result is worth reading carefully. A 0.2% violation rate is a pipeline
validation, not a finding — if the digital calculation were wrong, impossible values
would show up here in the hundreds. The 94.9% figure does not show mispricing; it
shows that the driftless reflection bound is the wrong tool for long-dated deep OTM
strikes. An earlier version of that script compared against a lognormal terminal and
reported 8.7% "arithmetic violations", which were the model's error, not the market's.

---

## Running it

Python 3.12. **No dependencies** — standard library only, nothing to install.

```bash
git clone https://github.com/DenizErginGunduz/divergence.git
cd divergence
python scripts/arsiv.py           # reads the archive, prints what it found
python scripts/write_findings.py  # runs every measurement, writes findings/latest.json
```

`scripts/README.md` lists what each script asks and how to run it.

Nothing needs network access to reproduce a measurement: the archive is in the
repository. Only the collector talks to the outside world.

---

## Repository map

```
collector/collect.py   the only thing that fetches from the internet; runs 3x daily in CI
raw/                   immutable snapshots, never rewritten  (docs/ARCHIVE_SCHEMA.md)
state/latest.json      pointer to the newest snapshot of each stream
scripts/               measurements; scripts/legacy/ does not run, by design
findings/latest.json   measurement output, written by CI
web/index.html         the terminal, reads the archive live
docs/                  methodology, data sources, product and design decisions
```

---

## How this project works

1. **Nothing is invented.** An endpoint, a price, a rule or a platform's coverage is
   either measured or written down as unknown.
2. **Raw data is kept unchanged.** The methodology will change; the ability to
   recompute from the original bytes must not.
3. **Settlement rules are quoted in full, never summarised.** The wording decides
   whether two contracts are comparable.
4. **Uncertainty is surfaced, not resolved.** A row we cannot measure stays visible
   and says why.
5. **Every number on screen traces to a script.** Enforced in CI: `ref_check.py` fails
   the build if a decision number is cited but never recorded.
6. **Retractions are recorded like results.** Decisions that turned out wrong stay in
   the log with the reason.

---

## Terminology

Avoided: fair value, true probability, AI probability, edge, signal, arbitrage,
insider, smart money.

Used: prediction-market-implied probability, options-implied risk-neutral probability,
cross-market probability gap, terminal and touch probability, measurable and not
measurable, settlement comparability.

We do not name something we cannot claim. "Edge" and "signal" promise something
actionable; as far as this has been measured, there isn't one.

---

## Status

Working: collector (25 of 25 recent runs clean), archive, three model-free
measurements, reference checker, terminal UI.

Known gaps, tracked openly:

- Eight decision records are marked `KAYIT KAYIP` in `docs/DECISIONS.md` — cited in
  the docs but never written down. They are placeholders, not silence.
- The archive grows about 4 MB a day. Git is the wrong home for it beyond roughly
  a year.
- 148 of 446 flow markets hit the fetch limit in the latest run with no gap flagged.
  Probably fine, not verified.
- Assets beyond BTC and ETH are collected but not measured.
- Documentation is being moved from Turkish to English; some files are still Turkish.
