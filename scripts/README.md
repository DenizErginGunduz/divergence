# scripts/

Measurement code. Not product code — each script tests one claim and writes the
number into `findings/latest.json` or prints it in CI.

No third-party packages. Everything here is Python 3.12 standard library, so there
is nothing to install and no dependency that can rot.

---

## Running

From the repository root:

```bash
python scripts/archive.py               # smoke test: can the archive be read?
python scripts/audit_semantics.py       # do the rule texts match the fields?
python scripts/measure_parity.py        # put-call cross-check, discount factor
python scripts/measure_band.py          # is there an edge at quoted prices?
python scripts/measure_exhaustive.py    # does a bucket ladder sum to D?
python scripts/measure_polymarket.py    # Polymarket daily terminal ladders
python scripts/measure_touch.py         # long-horizon touch bound
python scripts/measure_sensitivity.py   # strike grid and expiry band, as a range
python scripts/kill_test_eth5k.py       # the pre-committed ETH above $5,000 kill test (D-092)
python scripts/measure_payoff.py        # the buyer's comparison, per family: which venue sells the same payoff for less (D-114, D-117)
python scripts/measure_carry.py         # funding per venue per day, week and month on $1,000, and the dated futures' premium (D-119, D-120)
python scripts/horizons.py              # what settles when, per asset and family, and the horizon rule (D-120)
python scripts/discount_referee.py      # four estimates of D as implied rates (D-093)
python scripts/measure_basis.py         # BRTI against the Deribit index
python scripts/inventory_validation.py  # how much could ever be scored, and how much is independent
python scripts/write_findings.py        # run them all, write findings/latest.json
python scripts/ref_check.py --list      # every D-XXX reference resolves?
python scripts/check_readme.py          # does the README still match findings/?
python scripts/prune_archive.py         # dry run: what would leave the window?
```

Most accept `--last N` to limit the scan to the last N snapshots, which is
useful while iterating.

All of them also run in CI: the `measure` workflow (manual trigger) and
`ref-check` (every push). If you want to see a number regenerate without a
local checkout, run the workflow from the Actions tab.

---

## What each one does

| script | question | data |
|---|---|---|
| `archive.py` | Can we read a snapshot? Shared loader for everything else. | `raw/` |
| `stability.py` | Helper. Tracks whether the *same* rung behaves the same way across runs. | — |
| `audit_semantics.py` | Do Kalshi's own rule texts describe the event the numeric fields describe? Do the rules tile the line? What settles these contracts, verbatim? (D-075) | Kalshi |
| `measure_parity.py` | Does the converted option chain behave like a USD present value, and what discount factor does it imply? (D-073) | Deribit |
| `fees.py` | Kalshi's published taker fee, quoted from their schedule. Helper, not a measurement. (D-077) | — |
| `measure_band.py` | Sell the prediction at its bid against the bucket at its ask side, pay both venues' fees — is anything left, and what is it worth at the resting size? (D-076, D-077, D-078) | Kalshi + Deribit |
| `measure_exhaustive.py` | Does a bucket ladder sum to the discount factor D under three different boundary rules? (D-067, D-073) | Kalshi + Deribit |
| `measure_polymarket.py` | Same band question on Polymarket daily terminal ladders. Excludes touch ladders. | Polymarket + Deribit |
| `measure_touch.py` | Is the touch price inside the theoretical bound above terminal? | Polymarket + Deribit |
| `measure_sensitivity.py` | Two approximations under every digital: the strike grid it is differenced across, and the expiry that is not the settlement date. Reported as a band, never as a correction. (D-079) | Kalshi + Deribit |
| `measure_basis.py` | The third settlement difference, measured rather than left UNKNOWN: Kalshi settles on BRTI, Deribit on its own index. (D-075) | Kalshi + Deribit |
| `kill_test_eth5k.py` | The pre-committed local-grid kill test for the one rung that survives the maturity stress test. | Kalshi + Deribit |
| `measure_payoff.py` | For the same terminal payoff, is it cheaper to buy on the prediction market or from the option chain, one side's costs only — and does the answer depend on the condition? D-114's rules as a template over families, each judged separately, with a narrow-band verdict beside each (D-117): the Kalshi year-end ladders and Polymarket's daily ladders. A zero-fee sensitivity for Deribit's combo rule rides along (D-115). | Kalshi + Polymarket + Deribit |
| `measure_carry.py` | What holding a linear position has cost: Hyperliquid's and Polymarket's hourly funding de-duplicated across runs, the mean over the last 24, 168 and 720 hours (UNKNOWN below 90% coverage) and what a $1,000 long paid at it per day, week and month (D-120); Deribit's dated futures as a premium over the index, per $1,000 and annualised. Deribit's own perpetual stays UNKNOWN (D-111). (D-119) | `raw/carry/` |
| `horizons.py` | On which dates something settles, per asset (BTC, ETH, WTI, Brent, gold, silver, S&P 500) and family (terminal prediction ladders, touch markets, options), from the newest snapshot of each stream; perpetuals match every horizon. Carries the horizon rule: within max(1 day, 30% of the horizon), offset always shown. Lists, prices nothing. (D-120) | Kalshi + Polymarket + Deribit + Hyperliquid |
| `discount_referee.py` | Four estimates of the discount factor side by side, as implied rates; one is an estimator-consistency check, two are independent, one is an external dated constant. | Deribit |
| `inventory_validation.py` | How many observations could ever be scored against an outcome, and how many of those are independent events. Counting before scoring. | `raw/` |
| `write_findings.py` | Calls every measurement, writes `findings/latest.json`. | — |
| `ref_check.py` | Does every decision number cited anywhere actually exist? | repo text |
| `check_readme.py` | Does the README's results table still say what `findings/latest.json` says? Rebuilds the sentences and demands them verbatim. (D-090) | `findings/` |
| `prune_archive.py` | Bounds `raw/` to a rolling 14-day window. Runs in CI only after the private mirror is confirmed. | `raw/` |

`stability.py` exists because a ratio over repeated observations is
misleading. The same 44 Kalshi rungs are measured in every snapshot; reporting
"134 of 1978" implies 1978 independent samples. What matters is whether a rung
behaves consistently, and that is what this module reports: how many rungs clear
the test in over 90% of their observations, how many sometimes, how many never
(D-072, D-077). The current split is in `findings/latest.json`, not here.

---

## What the numbers mean now

Three things changed in the two weeks to 2026-09-15, and code written before
them will read wrong:

- **The option side is a discounted state price, not a probability.** Both the
  call and the put branch of `measure_band.digital()` return `D*Q(S>K)`. Until
  D-073 the put branch returned `1 - D*Q(S<K)`, which is a different quantity,
  and the exhaustiveness check could not see the difference. Dividing by `D`
  gives `Q`, which is still not a real-world probability.
- **The band is a trade, not a statistic.** `1.96*SE` is gone (D-076). A rung
  counts when one of two trades — priced at quotes that exist, after Deribit's
  fees and Kalshi's taker fee — leaves something. No mid is used in the verdict.
- **An edge has a size, and a size is not a trade.** `measure_band` reads the
  contracts resting at the quote being hit and reports what the quoted edge is
  worth in dollars (D-078). That is a quoted-executable discrepancy, not a
  size-executable opportunity (D-095); the one rung that cleared the maturity
  stress test did not survive executable prices on the later chain (D-103).

---

## `legacy/` — does not run

Six scripts from the first weeks of the project. They read `raw/_store.json` and
`inventory/*.csv`, a local layout that no longer exists in the repository. They
are kept for the reasoning, not the code, and each carries a header saying so.

They were found broken during an audit on 2026-09-11: the numbers they had produced
were on screen, but nothing in the repository could reproduce them. That is what the
`measure_*.py` scripts above were written to fix.

Do not repair them. Write a new measurement on top of `archive.py` instead.

---

## Adding a measurement

1. Read snapshots through `archive.py`. Never parse paths by hand.
2. If a stream is absent, let `Missing` propagate. Do not score it as zero.
3. Count distinct items with `stability.py`, not just observations.
4. State the caveat in the output itself. A number that travels without its
   limitation will be quoted without it.
5. Cite a decision number only if it exists — `ref_check.py` enforces this in CI.
