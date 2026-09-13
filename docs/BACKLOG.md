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
