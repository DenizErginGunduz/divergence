# raw/ — third-party market data. Not ours, not licensed by us.

Everything under this directory is market data retrieved from Kalshi, Polymarket
and Deribit. **It is not covered by the repository's MIT licence.** That licence
applies to the software in `collector/`, `scripts/` and `web/`. We hold no rights
in the data and grant none.

| venue | terms |
|---|---|
| Kalshi | [Data Terms of Use](https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf) |
| Polymarket | [Terms of Use](https://polymarket.com/tos) |
| Deribit | [Terms of Service](https://support.deribit.com/hc/en-us/articles/25944471089437-Terms-of-Service-DRB-Panama-Inc) |

All three restrict bulk redistribution of market data. If you intend to use what is
here for anything beyond reading this repository, their terms govern — not ours.
`docs/DATA_SOURCES.md` records what those terms say and the position we took.

---

## Why this directory is small

A **rolling 14-day window**, roughly 42 snapshots. Enough to reproduce the published
findings, and deliberately not an indefinite feed.

Two reasons, one of them legal and one of them practical:

1. Tools in this ecosystem display market data; they do not redistribute archives of
   it. A continuously growing store made this repository look like a data service,
   which is the specific thing the venue terms name.
2. Growth was measured at 4.03 MB/day — about 1.44 GB in a year, against GitHub's
   1 GB guidance. The window holds it near 56 MB.

Older snapshots are not destroyed. They are kept in a private archive and remain
available to the maintainer for work that needs a long series — how a gap behaves as
expiry approaches, where it sits against its own history, regime changes.

## Structure

See `docs/ARCHIVE_SCHEMA.md` for the shape of each stream, which fields matter, and
the one mistake that will silently corrupt your numbers (Deribit option prices are
quoted in the underlying, not in dollars).

Files here are written once and never modified. If a file looks wrong, write a new
measurement — do not edit the archive.
