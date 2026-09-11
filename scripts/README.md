# scripts/

Measurement code. Not product code — each script tests one claim and writes the
number into `findings/latest.json` or prints it in CI.

No third-party packages. Everything here is Python 3.12 standard library, so there
is nothing to install and no dependency that can rot.

---

## Running

From the repository root:

```bash
python scripts/arsiv.py                 # smoke test: can the archive be read?
python scripts/measure_band.py          # friction band, Kalshi year-end ladders
python scripts/measure_exhaustive.py    # do bucket probabilities sum to 1?
python scripts/measure_polymarket.py    # Polymarket daily terminal ladders
python scripts/measure_touch.py         # long-horizon touch bound
python scripts/write_findings.py        # run all three, write findings/latest.json
python scripts/ref_check.py --liste     # every D-XXX reference resolves?
```

Most accept `--son N` to limit the scan to the last N snapshots, which is useful
while iterating.

All of them also run in CI: the `measure` workflow (manual trigger) and `ref-check`
(every push). If you want to see a number regenerate without a local checkout, run
the workflow from the Actions tab.

---

## What each one does

| script | question | data |
|---|---|---|
| `arsiv.py` | Can we read a snapshot? Shared loader for everything else. | `raw/` |
| `kararlilik.py` | Helper. Tracks whether the *same* rung behaves the same way across runs. | — |
| `measure_band.py` | Does the gap beat fees, spread and measurement error? | Kalshi + Deribit |
| `measure_exhaustive.py` | Does a bucket ladder's probabilities sum to 1 under three different boundary rules? | Kalshi + Deribit |
| `measure_polymarket.py` | Same band question on Polymarket daily terminal ladders. Excludes touch ladders. | Polymarket + Deribit |
| `measure_touch.py` | Is the touch price inside the theoretical bound above terminal? | Polymarket + Deribit |
| `write_findings.py` | Calls the three measurements, writes `findings/latest.json`. | — |
| `ref_check.py` | Does every decision number cited anywhere actually exist? | repo text |

`kararlilik.py` exists because a ratio over repeated observations is misleading.
The same 44 Kalshi rungs are measured 34 times each; reporting "105 of 1496" implies
1496 independent samples. What matters is whether a rung behaves consistently, and
that is what this module reports.

---

## `legacy/` — does not run

Six scripts from the first weeks of the project. They read `raw/_store.json` and
`inventory/*.csv`, a local layout that no longer exists in the repository. They are
kept for the reasoning, not the code, and each carries a header saying so.

They were found broken during an audit on 2026-09-11: the numbers they had produced
were on screen, but nothing in the repository could reproduce them. That is what the
`measure_*.py` scripts above were written to fix.

Do not repair them. Write a new measurement on top of `arsiv.py` instead.

---

## Adding a measurement

1. Read snapshots through `arsiv.py`. Never parse paths by hand.
2. If a stream is missing, let `Eksik` propagate. Do not score it as zero.
3. Count distinct items with `kararlilik.py`, not just observations.
4. State the caveat in the output itself. A number that travels without its
   limitation will be quoted without it.
5. Cite a decision number only if it exists — `ref_check.py` enforces this in CI.
