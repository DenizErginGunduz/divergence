# BACKLOG — ideas recorded, not built

The scope rule says a new idea does not get built, it gets written down here.

## B-001 — Extending the asset universe to equities
Reason: US equities are where free option data is most plentiful; commodities are
the hardest place. Polymarket already lists ladders (all monthly, all touch,
Pyth / regular session): TSLA 14, NVDA 14, META 14, SPY 14, AAPL 10, MSFT 7,
AMZN 7, GOOGL 6 rungs.
Warning: MSFT / AMZN / GOOGL volumes are very thin (827 / 1,185 / 2,740 USD in
total). At those volumes the spread can be larger than the gap being measured.

## B-002 — ETF proxies for commodities (GLD / SLV / USO)
CME option data is licensed. ETF options come through a free channel.
The cost: carry differences, expense ratio, and roll decay in USO.
**USO is NOT a long-dated WTI proxy** — in contango it drifts systematically.

## B-003 — Historical accumulation pipeline
Needed for the reference metric in D-009. Daily and weekly markets are born and
die; they cannot be fetched retroactively. Every snapshot has to be kept. Free,
but it needs design.
**DONE 2026-08-30** — see D-034, D-040. The collector runs in GitHub Actions.

## B-004 — Kalshi inventory (second venue)
Purpose: fill the SPX/NDX gap and find a touch + terminal pair at the same expiry.
Coverage unknown, the API may require a key.

## B-005 — A model layer for the touch premium
The reflection principle and its variants. It opens layer 3 but brings model risk.
Should not be started before layer 4 works.
**Partly addressed in D-031** — the constant "2" was replaced with the full
lognormal formula.

## B-006 — A bid-ask spread threshold
Above which spread do we say "do not show this"? If the measured gap is smaller
than the spread, the number misleads.
**Decided in D-021** — spread ≤ 0.02 and mid < 0.99. Also D-033: the tick floor.

## B-007 — Live watcher and alerts (2026-08-30)
Alerts on large trades and on concentrated position moves. It will be a separate
process, writing to the SAME event format as the archive (D-039, D-040). Actions
cron cannot run more often than every 5 minutes and can be late, so real live
watching needs a continuously running process. Measured: the busiest market sees
156 trades an hour and the rest are far slower — there is no hurry.

**Caveat added 2026-09-16 (D-088):** the "concentrated position moves" half of this
item assumed `raw/holders/` describes the holder set. It does not. The collector asks
for `limit=100` and 77 of 150 token groups came back at the cap, so for most tokens the
file is the top 100 by size with no tail and no total. A Gini, an HHI or a true
largest-holder share is not computable from what is archived today; "what share do the
top 100 hold" is. Raising the limit is a collector change and a scope decision, so it
is named here rather than made.

## B-008 — Polymarket price history via clob/prices-history
The first attempt returned 200 but empty (`{"history": []}`). The parameters need
another try. If it works we get a historical series without waiting months for
accumulation, which pulls the time-series chart and the "typical gap" reference
far forward.

## B-009 — COT data
Mentioned in conversation, never written up as an item. Left as a placeholder so
the numbering does not collide; whoever picks it up should fill it in.

## B-010 — The two cards removed from the findings strip
While the strip was a slider it carried six findings. An infinitely scrolling
strip read worse, so it became a grid and dropped to four cards (D-069). The two
that were removed:

**Sync window** (`id:'sync'`, live)
> Time between reading the option chain and the prediction market.
> An 8-minute gap once moved a result by 33%.

Removed as a card because the value is already visible in the dateline as
`SYNC 0.81s`; it took up space on screen a second time. The measurement was not
lost, the card was.

**Markets tracked** (`id:'mkts'`, live, the total of `S.KA.markets`)
> Across three venues, captured in one synchronised run and archived unchanged.

Removed because it is a scope count, not a finding. It says "look how much we
track", not "here is what we measured". The four remaining cards tell a story:
what we found → does it beat the cost → is it stable → how do we know we are not
fooling ourselves.

If the strip ever becomes a single-card auto-rotating slider, both come back; the
live branch code inside `strip()` has to come back with them.

---

## B-017 — verify_index.yml: an experiment with no record (2026-09-16)
Found by Denetim 3 (D-090). `.github/workflows/verify_index.yml` asks one
question — can a GitHub Actions runner pull an index option chain from Yahoo via
yfinance, given that Colab failed 5 of 5 — and it is named in no document, no
decision record and no backlog item. Its own header comment is the only account
of why it exists.

It is `workflow_dispatch` only and touches nothing else, so it is harmless where
it sits. What is missing is the answer: whether it has ever been run, and what it
returned. That answer decides whether the index arm (`^SPX`, `^NDX`) can be built
on Actions at all, or needs a keyed source or a collector on the user machine —
which is the gate on the whole index / commodity / equity direction, and on B-001
and B-002 with it.

Not deleted, because the question is live. Logged so the next person does not have
to reconstruct the intent from a comment.

## B-018 — A Deribit futures stream in the collector (2026-09-16)
The archive holds no futures. Every Deribit option row carries `underlying_price`
for its expiry — the listed future where one exists, a synthetic otherwise — and
the discount-factor referee (D-093) reads it, but the payload does not say which
of the two it is, so that field is `UNKNOWN` per expiry in `findings/`. A
`get_book_summary_by_currency` call with `kind=future` would settle it and would
also give the dated-futures basis and roll that `docs/EXPOSURE_ENGINE.md` needs
(layer D). Not done here because it changes the archive format
(`ARCHIVE_VERSION`, `docs/ARCHIVE_SCHEMA.md`) and the collector is the one thing
that must not be touched casually. Asked about before it is built (D-101).

## B-019 — Perpetual funding ingest, minimal (2026-09-16)
The exposure-design branch (D-091, Layer B) cannot compute a perpetual's carry
without a funding stream, and V1 of the product (D-099) cannot show a
perpetual column without it. What is needed is small: the funding rate per
period for the BTC and ETH perpetuals on one venue, timestamped, alongside the
existing snapshots. Which venue, which endpoint, and its terms: `UNKNOWN` until
read. A collector change, so it is planned, its terms are quoted in
`docs/DATA_SOURCES.md` first, and it is asked about before it is built. Gate G6
in `docs/DECISION_GATES.md` depends on it.

## B-020 — A volatility surface for the year-end gap — REJECTED (2026-09-16)
Recorded as rejected rather than as an idea. An SVI or any other fitted surface
would let the year-end digital be read at the settlement date instead of at the
two bracketing expiries. It is not built (D-094, D-101): it replaces a stated
uncertainty with a model whose error is not stated; the nearer expiries that
close the gap arrive in December without any work; and a measurement that has
avoided a model since D-025 does not adopt one to rescue a 0.4-cent margin. If a
surface is ever built, it is for a different question and under a new decision.

## B-021 — Three competitors named in the review could not be found (2026-09-16)
`docs/COMPETITORS.md` entries 1–3: "Fabi et al. / Fair Odds" and "PolyGap"
returned no page under those names; "FairOdds" exists and is a sports odds
converter. Either the names are wrong, or the work is private or unindexed. The
owner is asked for URLs; until then no document cites them. Logged so the search
is not repeated from scratch.

## B-022 — The open pass truncates intraday events; a full ladder needs more than one page (2026-09-16)
The collector's open-market pass asks Kalshi for one page of 200 open markets per
series. For KXBTC / KXETH (and their cumulative twins) that page spans two events
and cuts the first one's middle out — the archive holds `less` to 68,200 and
`between` from 75,000, nothing in between (D-105). The measurement now names such
a ladder `incomplete` and does not sum it; curing it means paging the open pass
(or filtering by event) in `collector/collect.py`, which changes what the archive
holds and widens the sync window by a call or two. Collector change: the owner
decides. Not started.

---

# REMOVED IN THE CORRECTNESS SPRINT — recoverable on purpose

Everything below was WORKING and was taken out between 2026-09-14 and
2026-09-15 while the measurement was being made defensible (D-073 to D-078).
None of it was wrong to remove on methodological grounds. Several were good on
grounds the methodology does not measure: how quickly a stranger understands
the screen, how a recruiter reads the repository, whether the number is
quotable.

Those are real criteria for this project, not a distraction from it. The rule
here is the same as the rest of the backlog — recorded, not built — but the
review date is fixed: **when the 4-6 week programme ends, every item below is
reopened and judged again, on readability and impact as well as on rigour.**

Nothing here should be deleted without that review happening first.

## B-011 — The "x band" grammar
Removed by D-076, which replaced `threshold` with an executable envelope.

What it was: every rung carried `gap / threshold`, rendered as "gap 1.6x band"
with a bar showing the gap against the band. One glance told you whether a rung
was marginal or emphatic, on a scale where 1.0 was the line.

What replaced it: an edge in cents. Honest, and much harder to feel. "edge
0.52c" does not tell a reader whether that is a lot.

How to get it back without lying: `edge / envelope` is a dimensionless ratio
with the same shape, and the envelope is a real cost rather than a confidence
interval. Display only; it must not re-enter the verdict.

## B-012 — The statistical framing (1.96 * SE)
Removed by D-076. `se` is still computed on every rung and still stored — only
the verdict stopped reading it.

Why it mattered: "95%" is a phrase every reader already understands, and the
project now reports no uncertainty measure at all. Two rungs with identical
edges, one quoted by a deep book and one by a single lot, look the same.

How to get it back: show `1.96 * se` beside the envelope as a diagnostic, clearly
labelled as not deciding anything. The data is there; the line was deleted from
the page, not from the computation.

## B-013 — Saying "probability" on screen
D-073 established that the option side is a discounted state price, `D*Q(S>K)`,
and the documents now say so.

The cost: "the options imply a 0.4% chance, the prediction market says 1.2%" is
a sentence anyone can read. "discounted state price 0.0037 against 0.0120" is
not, and that sentence is how this project would be explained to anyone who is
not a derivatives person.

The defensible middle: divide by `D` and label the result
**options-implied risk-neutral probability**, which is what it is, and which
the terminology rules in METHODOLOGY.md already permit. `D` is now carried
explicitly (D-074), so this costs nothing but a display decision.

## B-014 — A headline that sums to 1
Before D-073 the exhaustive ladder summed to 1.0000 and the page could show it
raw: a reader could see the bucket prices add up, with no explanation needed.
It now sums to `D` (0.9881), which is correct and needs a paragraph.

How to get it back: display `total / D`, which lands on 1.0000 when the ladder is
consistent. Same check, same rigour, and the reader's intuition survives.
`measure_exhaustive.py` already pools this ratio internally.

## B-015 — The single headline percentage
"7% of rungs clear the band" was one number, on one line, and it was the
project's headline for weeks.

The honest headline after D-078 is "three rungs, worth $4.69 between them",
which is smaller and stranger. It may also be the better story: a persistent,
reproducible cross-venue price difference that survives every cost we can
measure and that nobody arbitrages because it is not worth the trouble. That is
a finding about market structure, and the fact that we went looking for a trade
and published the disappointment is itself the most credible thing here.

Recorded not because it needs recovering but because the framing decision is
worth making deliberately rather than by default.

## B-016 — The "Methodology under revision" banner that was never added
The strategic response called for freezing the UI behind a banner saying the
methodology was being revised. It was never added, and the page was instead
kept in step with the code at every commit (D-074, D-076, D-077, D-078).

That turned out better than the plan. A banner would have been honest and would
have made the site unusable as a portfolio piece for two weeks, while the actual
outcome is a site whose every number matches the record it cites.

Kept here so the decision is visible as a decision. If the methodology is ever
revised again without the screen following in the same commit, the banner is the
correct answer and this entry says why.
