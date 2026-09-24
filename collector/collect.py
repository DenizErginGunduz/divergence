#!/usr/bin/env python3
"""
collect.py v3 — DIVERGENCE COLLECTOR, EVENT-BASED

v1 re-stored the last 100 trades of every market on every run. Measured: 106
markets, ~10,600 trades, 7.3 MB — while the median market sees only ~3 new
trades in 8 hours. Almost the whole file was a copy.

v2 changed three things. All three because they are expensive to add later:

  1) EVENT-BASED STORAGE
     Trades are de-duplicated by transactionHash; only NEW ones are appended.
     So we write to the same store no matter how fast we poll. A live watcher
     added later will not force a format change.

  2) COVERAGE RECORD
     Every fetch writes down "over which time range did I see this market".
     Without it, "no trades" and "we were not looking" cannot be told apart.
     In an alerting product that distinction is everything: silence gets
     mistaken for information.

  3) GAP DETECTION + PAGINATION
     79 markets hit the limit of 100; there may be trades before that we never
     saw. If we cannot reach back to the previous watermark, a GAP flag is set
     and pagination tries to close it.
     NOTE: offset support on data-api is NOT VERIFIED. So the script does not
     assume — it makes the attempt and writes the result into pagination_worked.
     The first run tells us.

The schema our own files use is versioned (ARCHIVE_VERSION below), so a reader can
tell which shape a snapshot is in without guessing. Vendor payloads are stored
exactly as returned and are never renamed.

Unchanged rules: simultaneity comes first (D-015), vendor fields are never
modified (rule 2), a failed stage is never hidden (rule 6).
"""
import json, gzip, os, re, sys, time, datetime, urllib.request

UA = {'User-Agent': 'divergence-research/0.3 (+github)'}
GAMMA = 'https://gamma-api.polymarket.com'
DATA = 'https://data-api.polymarket.com'
DERIBIT = 'https://www.deribit.com/api/v2/public'
KALSHI = 'https://external-api.kalshi.com/trade-api/v2'
HYPERLIQUID = 'https://api.hyperliquid.xyz/info'
POLY_PERPS = 'https://api.perpetuals.polymarket.com/v1/info'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ARCHIVE_VERSION = 7                          # schema version of the files we write (6: raw/funding, D-111; 7: raw/carry, D-119)

# Trade fields dropped before writing. Two kinds, neither of them market data:
#
#   PROFILE — name, pseudonym, bio, profileImage. Who the trader says they
#   are. Measured 2026-09-16: present on 6,568 of 7,081 trades in one run.
#   Nothing in this project reads them, and publishing a rolling archive of
#   which named person bought which contract is a different category of thing
#   from publishing prices (D-087). proxyWallet is KEPT: concentration work
#   (B-007) needs an actor key, and the wallet is already on-chain public.
#
#   REDUNDANT — icon, title, slug, eventSlug. Repeated on every trade row and
#   already archived once per run in raw/polymarket_events/. conditionId
#   resolves them.
#
# Together they were 47.5% of the bytes.
TRADE_DROP = ('name', 'pseudonym', 'bio', 'profileImage',
              'profileImageOptimized', 'icon', 'title', 'slug', 'eventSlug')

# Holder fields dropped before writing, on the same two grounds as TRADE_DROP
# and with the same distinction between them (D-088):
#
#   PROFILE, not recoverable and not wanted — name, pseudonym, bio,
#   profileImage, profileImageOptimized, displayUsernamePublic, verified.
#   Measured on the 2026-09-15T0505Z file: name populated on 9,622 of 10,409
#   holder rows. This stream is worse than the trade stream in one respect:
#   a trade is a past act, a holding is a CURRENT position, so the row said
#   which named account is holding which side right now.
#
#   REDUNDANT, exactly recoverable — asset. It equals the enclosing token on
#   all 10,409 rows checked, 0 mismatches, so removing it loses nothing at
#   all: any reader can put it back from the key it sits under.
#
# KEPT: proxyWallet (actor key, already on-chain, B-007 needs it), amount,
# outcomeIndex. Together the dropped fields were 73.5% of the field bytes.
HOLDER_DROP = ('name', 'pseudonym', 'bio', 'profileImage',
               'profileImageOptimized', 'displayUsernamePublic', 'verified',
               'asset')

ASSETS = ['bitcoin', 'ethereum']             # D-034: the V1 measured universe
DERIBIT_CURRENCIES = ['BTC', 'ETH']

# Perpetual funding (D-111). The HISTORY endpoint, not the ticker's instantaneous
# value: three samples a day are not a history. Each run re-asks for the last 48
# hours, so a run every eight hours sees every hour about six times and up to five
# consecutive missed runs leave no hole. Readers de-duplicate on timestamp; the
# archive stores what came back.
FUNDING_INSTRUMENTS = ['BTC-PERPETUAL', 'ETH-PERPETUAL']
FUNDING_LOOKBACK_MS = 48 * 3600 * 1000
# Carry (D-119): the perpetuals a buyer would use for a linear position, and
# Deribit's dated futures. Hyperliquid is the base, Polymarket's perpetuals second.
# Coins are ASKED FOR only if the dex's own universe lists them; an absent one is
# recorded as absent. Eight days back, so a weekly mean exists from the first run.
CARRY_LOOKBACK_MS = 8 * 24 * 3600 * 1000
HL_COINS = {'': ['BTC', 'ETH'],
            'xyz': ['CL', 'BRENTOIL', 'GOLD', 'SILVER', 'SP500', 'XYZ100']}
POLY_PERP_SYMBOLS = ['BTC-USD', 'ETH-USD', 'WTIOIL-USD', 'BRENTOIL-USD',
                     'GOLD-USD', 'SILVER-USD', 'SP500-USD']
POLY_PERP_MAX_PAGES = 4                      # "at most 100 funding-rate entries per request"
PAGE = 100                                   # data-api limit
MAX_PAGES = 6                                # cap on gap-closing attempts
HOLDERS_HOUR = 5                             # holders fetched ONCE a day (05 UTC)

# The Kalshi series list is NOT hardcoded. The first attempt derived it from a
# truncated catalogue response and missed 42 of 62 BTC/ETH series — including the
# annual TERMINAL contracts we were actually after. It is now DERIVED from the
# catalogue on every run; if the source changes, we change with it.
# Word boundaries are REQUIRED: in the first version the 'Dow' pattern matched
# 'downloads' and the observation bucket filled with Netflix/Disney+ app-install
# markets.
KALSHI_OBSERVED_PATTERN = (r'S&P 500|SPX|Nasdaq|NDX|DJIA|Dow Jones'
                           r'|\bgold\b|\bsilver\b|\boil\b|\bcrude\b|\bWTI\b|\bBrent\b')
KALSHI_SERIES_CAP = 90            # bound the run time


def get(url, timeout=30, attempts=3):
    last = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError('%s -> %s' % (url[:90], str(last)[:120]))


def post(url, body, timeout=30, attempts=3):
    """Hyperliquid's info endpoint takes a JSON body. Same retry shape as get()."""
    last = None
    data = json.dumps(body).encode('utf-8')
    hdr = dict(UA); hdr['Content-Type'] = 'application/json'
    for i in range(attempts):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, data=data, headers=hdr), timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError('%s %s -> %s' % (url[:60], json.dumps(body)[:60], str(last)[:120]))


def write_gz(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    return os.path.getsize(path)


t0_all = time.time()
now = datetime.datetime.now(datetime.timezone.utc)
STAMP = now.strftime('%Y-%m-%dT%H%MZ')
DAY = now.strftime('%Y-%m-%d')

bucket, errors, durations = {}, {}, {}


def stage(name, fn):
    t = time.time()
    try:
        bucket[name] = fn()
    except Exception as e:
        errors[name] = str(e)[:300]
        print('  ! %s FAILED: %s' % (name, str(e)[:140]), file=sys.stderr)
    durations[name] = round(time.time() - t, 2)


# ---------------- watermark ----------------
# For each market: the newest trade instant we have seen, plus the hashes at that
# instant. Only boundary hashes are kept, so the state file does not grow.
WM_PATH = os.path.join(ROOT, 'state', 'watermark.json')
try:
    with open(WM_PATH, encoding='utf-8') as f:
        WM = json.load(f)
except Exception:
    WM = {}


# ---------------- 1. Deribit: calls + puts, both currencies ----------------
def deribit():
    out = {}
    for c in DERIBIT_CURRENCIES:
        out[c] = {
            'book_summary': get('%s/get_book_summary_by_currency?currency=%s&kind=option'
                                % (DERIBIT, c), timeout=60),
            'index': get('%s/get_index_price?index_name=%s_usd' % (DERIBIT, c.lower())),
        }
    return out


# ---------------- 2. Polymarket ladders ----------------
def polymarket_events():
    return {a: get('%s/events?tag_slug=%s&closed=false&limit=200' % (GAMMA, a),
                   timeout=60) for a in ASSETS}


# ---------------- 3. Kalshi ----------------
def kalshi():
    """Catalogue -> series to track -> ALL markets of those series.

    NO status filter: resolved markets come too. Resolution outcomes are the
    calibration / Brier data set itself and cannot be recovered afterwards.

    The series list is derived from the catalogue:
      markets  = every series tagged BTC or ETH
      observed = series under Financials matching the index/commodity pattern
                 (no number is produced from these until scope is decided)
    """
    out = {'catalogue': {}, 'markets': {}, 'observed': {}, 'selection': {}}
    for cat in ('Crypto', 'Financials'):
        try:
            out['catalogue'][cat] = get('%s/series?category=%s' % (KALSHI, cat), timeout=45)
        except Exception as e:
            out['catalogue'][cat] = {'_error': str(e)[:150]}

    def series(cat, pick):
        d = out['catalogue'].get(cat) or {}
        return [x.get('ticker') for x in (d.get('series') or []) if x.get('ticker') and pick(x)]

    crypto = series('Crypto', lambda x: bool({'BTC', 'ETH'} & set(x.get('tags') or [])))
    observed = series('Financials', lambda x: bool(re.search(
        KALSHI_OBSERVED_PATTERN, (x.get('title') or '') + ' ' + ' '.join(x.get('tags') or []), re.I)))
    crypto = crypto[:KALSHI_SERIES_CAP]
    observed = observed[:KALSHI_SERIES_CAP // 3]
    out['selection'] = {'crypto': crypto, 'observed': observed,
                        'truncated': [], 'open_pass_errors': {}}

    PAGES, PER_PAGE = 5, 200
    CAP = PAGES * PER_PAGE

    def markets(t):
        """Every market of one series.

        NO status filter on the main pass: resolved markets come too, and the
        resolution outcomes ARE the calibration data set.

        But the main pass stops at 5 x 200 = 1,000 rows, and for a busy series
        Kalshi fills those rows with markets that are not tradable now.
        Measured 2026-09-15: KXBTCD returned 1,000 of 1,000 'initialized', so
        not one live daily quote had ever been archived, and KXBTC15M returned
        946 finalized against 1 active. That is why the validation inventory
        found 88 usable pairs out of 4,657 resolved markets (D-080).

        So when the cap is hit — and only then — one more call asks for the
        OPEN markets explicitly. Truncated series pay for it and the rest do
        not, which keeps the sync window, itself a measured quality number,
        from widening for nothing.
        """
        page, cursor, all_rows = 0, '', []
        while page < PAGES:
            u = '%s/markets?series_ticker=%s&limit=%d' % (KALSHI, t, PER_PAGE)
            if cursor:
                u += '&cursor=%s' % cursor
            d = get(u, timeout=30)
            m = d.get('markets') or []
            all_rows += m
            cursor = d.get('cursor') or ''
            if not cursor or not m:
                break
            page += 1
        if len(all_rows) < CAP:
            return all_rows
        out['selection']['truncated'].append(t)
        try:
            d = get('%s/markets?series_ticker=%s&status=open&limit=%d'
                    % (KALSHI, t, PER_PAGE), timeout=30)
        except Exception as e:
            # Recorded, not swallowed: the main pass still stands, but a run
            # where this failed has no live quotes for a truncated series and
            # must not be mistaken for one where none existed.
            out['selection']['open_pass_errors'][t] = str(e)[:150]
            return all_rows
        seen = set(r.get('ticker') for r in all_rows)
        for r in (d.get('markets') or []):
            if r.get('ticker') not in seen:
                all_rows.append(r)
        return all_rows

    for key, tickers in (('markets', crypto), ('observed', observed)):
        for t in tickers:
            try:
                out[key][t] = markets(t)
            except Exception as e:
                out[key][t] = {'_error': str(e)[:150]}
            time.sleep(0.08)
    return out


# ---- SIMULTANEITY: each source's own instant is recorded separately (D-015) ----
# Kalshi takes ~20 calls and widens the window. Rather than hide that, we MEASURE
# it, so the drift between any pair can be computed afterwards.
MARKS = {}
MARKS['start'] = 0.0
stage('deribit', deribit);            MARKS['deribit_end'] = round(time.time()-t0_all, 2)
stage('polymarket_events', polymarket_events); MARKS['polymarket_end'] = round(time.time()-t0_all, 2)
WINDOW = MARKS['polymarket_end']                # Deribit <-> Polymarket drift
stage('kalshi', kalshi);              MARKS['kalshi_end'] = round(time.time()-t0_all, 2)


# ---------------- 3b. Funding: the perpetuals' hourly history (D-111) ----------------
# AFTER the synchronous reads on purpose: WINDOW above is the Deribit <-> Polymarket
# drift the whole comparison depends on, and nothing may sit between those two
# stages. This stage gets its own mark so its latency is visible, not hidden.
def funding(end_ms=None):
    """One call per perpetual: the last FUNDING_LOOKBACK_MS of hourly funding
    points, ending at the run's instant. The JSON-RPC envelope is stored whole; the
    'request' block is ours, so a reader can tell "no points" from "not asked"."""
    end = int(time.time() * 1000) if end_ms is None else int(end_ms)
    start = end - FUNDING_LOOKBACK_MS
    out = {}
    for name in FUNDING_INSTRUMENTS:
        out[name] = {
            'request': {'method': 'public/get_funding_rate_history',
                        'instrument_name': name,
                        'start_timestamp': start, 'end_timestamp': end},
            'response': get('%s/get_funding_rate_history?instrument_name=%s'
                            '&start_timestamp=%d&end_timestamp=%d'
                            % (DERIBIT, name, start, end), timeout=30),
        }
    return out


stage('funding', funding);            MARKS['funding_end'] = round(time.time()-t0_all, 2)


# ---------------- 3c. Carry: other venues' perpetuals and Deribit's dated futures (D-119) ----------------
# After funding, for the same reason funding sits after the synchronous reads. Each
# venue is its own try: one venue failing records its error inside the file and
# leaves the other two intact. Payloads are stored as returned, beside our request.
def _try(fn):
    try:
        return {'ok': True, 'value': fn()}
    except Exception as e:
        return {'ok': False, 'error': str(e)[:300]}


def _hyperliquid(start, end):
    out = {'perpDexs': _try(lambda: post(HYPERLIQUID, {'type': 'perpDexs'})),
           'ctx': {}, 'funding': {}, 'absent': []}
    for dex, coins in HL_COINS.items():
        body = {'type': 'metaAndAssetCtxs'}
        if dex:
            body['dex'] = dex
        ctx = _try(lambda: post(HYPERLIQUID, body))
        out['ctx'][dex or 'main'] = {'request': body, 'response': ctx}
        listed = set()
        if ctx['ok'] and isinstance(ctx['value'], list) and ctx['value']:
            listed = set(u.get('name') for u in (ctx['value'][0] or {}).get('universe') or [])
        for c in coins:
            name = '%s:%s' % (dex, c) if dex else c
            if listed and name not in listed:
                out['absent'].append(name)
                continue
            req = {'type': 'fundingHistory', 'coin': name, 'startTime': start, 'endTime': end}
            out['funding'][name] = {'request': req,
                                    'response': _try(lambda: post(HYPERLIQUID, req))}
    return out


def _poly_perps(start, end):
    out = {'tickers': _try(lambda: get('%s/tickers' % POLY_PERPS)), 'funding': {}, 'absent': []}
    if not os.path.isdir(os.path.join(ROOT, 'raw', 'carry', DAY)) or now.hour == HOLDERS_HOUR:
        out['instruments'] = _try(lambda: get('%s/instruments' % POLY_PERPS))
    ids = {}
    if out['tickers']['ok'] and isinstance(out['tickers']['value'], list):
        ids = dict((t.get('symbol'), t.get('instrument_id')) for t in out['tickers']['value'])
    for sym in POLY_PERP_SYMBOLS:
        if sym not in ids:
            out['absent'].append(sym)
            continue
        pages, lo, hi = [], start, end
        for _ in range(POLY_PERP_MAX_PAGES):
            req = {'instrument_id': ids[sym], 'start_timestamp': lo, 'end_timestamp': hi}
            r = _try(lambda: get('%s/funding?instrument_id=%s&start_timestamp=%d&end_timestamp=%d'
                                 % (POLY_PERPS, ids[sym], lo, hi)))
            pages.append({'request': req, 'response': r})
            v = r.get('value') if r['ok'] else None
            rows = (v or {}).get('data') if isinstance(v, dict) else None
            if not (isinstance(v, dict) and v.get('more') and rows):
                break
            ts = [int(x.get('timestamp') or 0) for x in rows]
            # Page toward whichever end the venue has not returned yet; the order of
            # the rows is not documented, so it is read from the rows themselves.
            if ts[0] <= ts[-1]:
                lo = max(ts) + 1
            else:
                hi = min(ts) - 1
            if lo > hi:
                break
        out['funding'][sym] = pages
    return out


def _deribit_futures():
    out = {}
    for cur in DERIBIT_CURRENCIES:
        out[cur] = {
            'book_summary': _try(lambda: get('%s/get_book_summary_by_currency?currency=%s&kind=future'
                                             % (DERIBIT, cur))),
            'instruments': _try(lambda: get('%s/get_instruments?currency=%s&kind=future&expired=false'
                                            % (DERIBIT, cur))),
            'index': _try(lambda: get('%s/get_index_price?index_name=%s_usd' % (DERIBIT, cur.lower()))),
        }
    return out


def carry(end_ms=None):
    end = int(time.time() * 1000) if end_ms is None else int(end_ms)
    start = end - CARRY_LOOKBACK_MS
    return {'window': {'start_ms': start, 'end_ms': end},
            'hyperliquid': _hyperliquid(start, end),
            'polymarket_perps': _poly_perps(start, end),
            'deribit_futures': _deribit_futures()}


stage('carry', carry);                MARKS['carry_end'] = round(time.time()-t0_all, 2)


# ---------------- 3. Flow: event-based, with gaps ----------------
def _is_new(t, wm):
    """Is this trade after the watermark? Ties at the boundary split by hash."""
    ts = int(t.get('timestamp') or 0)
    if ts > wm['ts']:
        return True
    return ts == wm['ts'] and t.get('transactionHash') not in wm['hashes']


def flow(cids):
    new, coverage = [], []
    for cid in cids:
        wm = WM.get(cid) or {'ts': 0, 'hashes': []}
        first_time = wm['ts'] == 0
        collected, page_no, pagination_worked, seen = [], 0, None, set()
        try:
            while page_no < MAX_PAGES:
                url = '%s/trades?market=%s&limit=%d' % (DATA, cid, PAGE)
                if page_no:
                    url += '&offset=%d' % (page_no * PAGE)
                s = get(url, timeout=25)
                if not isinstance(s, list) or not s:
                    break
                h = {x.get('transactionHash') for x in s}
                if page_no:
                    # Does pagination actually return new records? MEASURE, do not assume.
                    pagination_worked = len(h - seen) > 0
                    if not pagination_worked:
                        break
                seen |= h
                collected += s
                if len(s) < PAGE:
                    break
                # On the first run do not dig backwards: this is our starting point.
                if first_time:
                    break
                # Once we reach the watermark, that is enough.
                if min(int(x.get('timestamp') or 0) for x in s) <= wm['ts']:
                    break
                page_no += 1
            time.sleep(0.12)
        except Exception as e:
            coverage.append({'market': cid, 'error': str(e)[:150]})
            continue

        n = [t for t in collected if _is_new(t, wm)]
        new += n
        all_ts = [int(t.get('timestamp') or 0) for t in collected if t.get('timestamp')]
        oldest = min(all_ts) if all_ts else None
        newest = max(all_ts) if all_ts else None
        limit_hit = len(collected) >= PAGE
        # GAP: we hit the limit AND could not reach back to the previous watermark.
        gap = bool(limit_hit and not first_time and oldest is not None
                   and oldest > wm['ts'])
        coverage.append({
            'market': cid, 'fetched_utc': now.isoformat(),
            'returned': len(collected), 'new': len(n), 'pages': page_no + 1,
            'oldest_ts': oldest, 'newest_ts': newest,
            'previous_watermark': wm['ts'], 'limit_hit': limit_hit,
            'pagination_worked': pagination_worked,
            'first_time': first_time,
            # on the first run "gap" is meaningless: this is the starting point.
            'GAP': gap,
        })
        if newest is not None:
            WM[cid] = {'ts': newest,
                       'hashes': [t.get('transactionHash') for t in collected
                                  if int(t.get('timestamp') or 0) == newest]}
    return {'new_trades': new, 'coverage': coverage}


# ---------------- Scope filter: PRICE LADDERS only ----------------
# The first v2 run fetched 770 markets; those are ALL markets tagged
# 'bitcoin'/'ethereum'. The scope we declared (D-034) is BTC/ETH price ladders.
# This is a COLLECTION filter, NOT a classification: contract type (terminal /
# touch / range) is still decided from the rule text. The only question here is
# "does this market carry a price threshold".
THRESHOLD_RE = re.compile(r'\$\s?\d[\d.,]{2,}')


def is_ladder(m):
    text = '%s %s' % (m.get('question') or '', m.get('groupItemTitle') or '')
    return bool(THRESHOLD_RE.search(text))


cids, out_of_scope = [], 0
for _a, evs in (bucket.get('polymarket_events') or {}).items():
    for e in (evs or []):
        for m in (e.get('markets') or []):
            if not m.get('conditionId'):
                continue
            if is_ladder(m):
                cids.append(m['conditionId'])
            else:
                out_of_scope += 1
cids = list(dict.fromkeys(cids))
stage('flow', lambda: flow(cids))


# ---------------- 4. Holders: once a day ----------------
# Anything that is not a list of token groups is counted here rather than
# passed over. One condition in the 2026-09-15T0505Z file had a JSON null
# body: not an exception, so the try/except below never saw it, and null and
# 'nobody holds this' were stored identically. The payload is still written
# exactly as it arrived -- only the count is new, so the hole is visible in
# _meta instead of being invisible everywhere.
HOLDERS_UNEXPECTED = []


def strip_holders(payload):
    """Remove HOLDER_DROP from every holder row, in place. Non-list payloads
    are returned untouched and counted."""
    if not isinstance(payload, list):
        HOLDERS_UNEXPECTED.append(type(payload).__name__)
        return payload
    for group in payload:
        if not isinstance(group, dict):
            continue
        group['holders'] = [
            dict((k, v) for k, v in h.items() if k not in HOLDER_DROP)
            for h in (group.get('holders') or []) if isinstance(h, dict)]
    return payload


def holders():
    out = {}
    for c in cids[:80]:
        try:
            out[c] = strip_holders(
                get('%s/holders?market=%s&limit=100' % (DATA, c), timeout=25))
        except Exception as e:
            out[c] = {'_error': str(e)[:150]}
        time.sleep(0.12)
    return out


holders_day_path = os.path.join(ROOT, 'raw', 'holders', DAY)
if not os.path.isdir(holders_day_path) or now.hour == HOLDERS_HOUR:
    stage('holders', holders)
else:
    durations['holders'] = 'skipped (once a day)'


# ---------------- WRITING ----------------
written = []


def save(name, data):
    p = os.path.join(ROOT, 'raw', name, DAY, '%s_%s.json.gz' % (name, STAMP))
    written.append({'file': os.path.relpath(p, ROOT), 'bytes': write_gz(p, data)})


if 'deribit' in bucket:
    save('deribit', bucket['deribit'])
if 'polymarket_events' in bucket:
    save('polymarket_events', bucket['polymarket_events'])
if 'holders' in bucket:
    save('holders', bucket['holders'])
if 'kalshi' in bucket:
    save('kalshi', bucket['kalshi'])
if 'funding' in bucket:
    save('funding', bucket['funding'])
if 'carry' in bucket:
    save('carry', bucket['carry'])

flow_result = bucket.get('flow') or {'new_trades': [], 'coverage': []}

# New trades: a separate gz file PER RUN. Why not append to one file: git stores
# files as whole blobs, so appending to a growing NDJSON three times a day
# re-stores the entire file as a new object each time. A file per run removes
# that growth. De-duplication is already done by watermark, so append semantics
# are not needed.
#
# Vendor fields are preserved as-is EXCEPT TRADE_DROP. Rule 2 says raw data is
# stored as it arrives, and this is the one deliberate exception: its purpose
# is that a changed methodology can be recomputed from the archive, and none of
# the dropped fields can affect any recomputation of a price. The reason for
# dropping them is that four of them are somebody's profile (D-087).
nd = os.path.join(ROOT, 'raw', 'events', 'trades', DAY, 'trades_%s.ndjson.gz' % STAMP)
os.makedirs(os.path.dirname(nd), exist_ok=True)
with gzip.open(nd, 'wt', encoding='utf-8') as f:
    for t in flow_result['new_trades']:
        row = dict((k, v) for k, v in t.items() if k not in TRADE_DROP)
        f.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
written.append({'file': os.path.relpath(nd, ROOT), 'bytes': os.path.getsize(nd)})

cp = os.path.join(ROOT, 'raw', 'coverage', DAY, 'coverage_%s.json' % STAMP)
os.makedirs(os.path.dirname(cp), exist_ok=True)
with open(cp, 'w', encoding='utf-8') as f:
    json.dump(flow_result['coverage'], f, ensure_ascii=False, indent=1)
written.append({'file': os.path.relpath(cp, ROOT), 'bytes': os.path.getsize(cp)})

os.makedirs(os.path.dirname(WM_PATH), exist_ok=True)
with open(WM_PATH, 'w', encoding='utf-8') as f:
    json.dump(WM, f, ensure_ascii=False, separators=(',', ':'))

C = flow_result['coverage']
pagination = [c.get('pagination_worked') for c in C if c.get('pagination_worked') is not None]
summary = {
    'markets': len(C),
    'out_of_scope_markets': out_of_scope,   # no price threshold, so not fetched
    'new_trades': len(flow_result['new_trades']),
    'limit_hit': sum(1 for c in C if c.get('limit_hit')),
    'WITH_GAP': sum(1 for c in C if c.get('GAP')),
    'first_time': sum(1 for c in C if c.get('first_time')),
    'pagination_tried': len(pagination),
    'pagination_worked': sum(1 for x in pagination if x),
}
meta = {'snapshot_utc': now.isoformat(),
        'total_seconds': round(time.time() - t0_all, 2),
        'sync_window_seconds': WINDOW,          # Deribit <-> Polymarket
        'source_marks_seconds': MARKS,          # the third source's drift is visible too
        'stage_seconds': durations, 'errors': errors,
        'complete': len(errors) == 0, 'flow_summary': summary,
        'kalshi_summary': (lambda k: None if not k else {
            'catalogue': {a: len((b or {}).get('series') or []) for a, b in k['catalogue'].items()},
            'crypto_series_tracked': len(k['selection']['crypto']),
            'observed_series_tracked': len(k['selection']['observed']),
            'series_returning_markets': sum(1 for v in k['markets'].values() if isinstance(v, list) and v),
            'total_markets': sum(len(v) for v in k['markets'].values() if isinstance(v, list)),
            'observed_markets': sum(len(v) for v in k['observed'].values() if isinstance(v, list)),
        })(bucket.get('kalshi')),
        'holders_unexpected': (len(HOLDERS_UNEXPECTED)
                               if 'holders' in bucket else None),
        # Points returned per perpetual and the window asked for (D-111): a run
        # that came back empty is visible here without opening the file.
        'funding_summary': (lambda f: None if not f else {
            'lookback_hours': FUNDING_LOOKBACK_MS // 3600000,
            'points': {k: len(((v.get('response') or {}).get('result') or []))
                       if isinstance((v.get('response') or {}).get('result'), list) else None
                       for k, v in f.items()},
        })(bucket.get('funding')),
        # Which carry blocks came back and how many rows each (D-119).
        'carry_summary': (lambda c: None if not c else {
            'lookback_hours': CARRY_LOOKBACK_MS // 3600000,
            'hyperliquid_rows': {k: (len(v['response']['value']) if v['response']['ok']
                                     and isinstance(v['response']['value'], list) else None)
                                 for k, v in c['hyperliquid']['funding'].items()},
            'hyperliquid_absent': c['hyperliquid']['absent'],
            'polymarket_rows': {k: sum(len(((p['response'].get('value') or {}).get('data') or []))
                                       if p['response']['ok'] and isinstance(p['response'].get('value'), dict) else 0
                                       for p in v)
                                for k, v in c['polymarket_perps']['funding'].items()},
            'polymarket_absent': c['polymarket_perps']['absent'],
            'deribit_futures_ok': {k: v['book_summary']['ok'] for k, v in c['deribit_futures'].items()},
        })(bucket.get('carry')),
        'files': written, 'assets': ASSETS, 'version': ARCHIVE_VERSION}
mp = os.path.join(ROOT, 'raw', '_meta', DAY, 'meta_%s.json' % STAMP)
os.makedirs(os.path.dirname(mp), exist_ok=True)
with open(mp, 'w', encoding='utf-8') as f:
    json.dump(meta, f, ensure_ascii=False, indent=1)

# ---------------- pointer (state/latest.json) ----------------
# The page used to list the GitHub contents API to find the newest snapshot. The
# unauthenticated limit is 60 per hour. The counter also listed EVERY archive day
# separately, so the cost grew by one call a day: at 12 days that was ~18 calls
# per page load, i.e. ~3 page opens per visitor per hour, after which the site
# showed "archive unavailable". This file replaces those listings; the page reads
# one raw file and the API cost drops to zero. raw.githubusercontent.com has no
# such limit (only a ~5 minute CDN cache, which is irrelevant when the collector
# runs three times a day -- 05:00/13:00/21:00 UTC, eight hours apart).
# Decision: D-070.
def _rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, '/')


paths = {}
for w in written:
    d = w['file'].replace(os.sep, '/')
    # 'funding' and 'carry' are listed here (the block's purpose is the newest file
    # of each stream) but are NOT in the required-streams check below: the page does
    # not read them, and their failure must not mark the pointer broken (D-111, D-119).
    for name in ('kalshi', 'deribit', 'polymarket_events', 'funding', 'carry'):
        if d.startswith('raw/%s/' % name):
            paths[name] = d

# The archive counter is counted from disk. That was the only reason the page
# made one API listing per day.
meta_root = os.path.join(ROOT, 'raw', '_meta')
per_day = {}
if os.path.isdir(meta_root):
    for d in sorted(os.listdir(meta_root)):
        dp = os.path.join(meta_root, d)
        if os.path.isdir(dp):
            per_day[d] = len([x for x in os.listdir(dp) if x.endswith('.json')])

day_list = sorted(per_day)
pointer = {
    'version': 2,
    'snapshot_utc': now.isoformat(),
    'day': DAY,
    'stamp': STAMP,
    'sync_window_seconds': WINDOW,
    'complete': len(errors) == 0,
    'paths': paths,
    'meta_path': _rel(mp),
    'archive': {
        'day_count': len(per_day),
        'snapshot_count': sum(per_day.values()),
        'first_day': day_list[0] if day_list else None,
        'last_day': day_list[-1] if day_list else None,
        'per_day': per_day,
    },
}
ip = os.path.join(ROOT, 'state', 'latest.json')
os.makedirs(os.path.dirname(ip), exist_ok=True)
with open(ip, 'w', encoding='utf-8') as f:
    json.dump(pointer, f, ensure_ascii=False, indent=1)
written.append({'file': _rel(ip), 'bytes': os.path.getsize(ip)})

# A pointer with a missing stream must not pass quietly: the page cannot read it.
for _name in ('kalshi', 'deribit'):
    if _name not in paths:
        errors['pointer_missing_%s' % _name] = 'stream absent from pointer'

# The archive window is NOT here: pruning lives in scripts/prune_archive.py and
# runs in the workflow AFTER the private mirror has been updated successfully.
# The order matters — if the mirror is skipped the pruning must be skipped too,
# otherwise data is lost silently.
print('DIVERGENCE v3 — %s' % now.isoformat())
print('  sync window : %.2f s' % WINDOW)
print('  total time  : %.2f s' % meta['total_seconds'])
print('  flow: %(markets)d ladder markets (out of scope %(out_of_scope_markets)d)'
      ' | %(new_trades)d NEW trades | limit hit %(limit_hit)d'
      ' | WITH GAP %(WITH_GAP)d | first time %(first_time)d' % summary)
print('  pagination: %d tried, %d worked  <- data-api offset support is read from THIS line'
      % (summary['pagination_tried'], summary['pagination_worked']))
for w in written:
    print('    %-52s %8.1f KB' % (w['file'], w['bytes'] / 1024))
if errors:
    print('  FAILED STAGES : %s' % ', '.join(errors))
sys.exit(0)
