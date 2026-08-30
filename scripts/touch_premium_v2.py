#!/usr/bin/env python3
"""
touch_premium_v2.py — KATMAN 3, D-027 DUZELTMESIYLE

Dunku `touch_premium_btc.py` terminal olasiligi naif N(d2) ile uretiyordu.
`skew_correction_btc.py` o yontemin aylik zincirde hakemden ortalama %54,8,
kanatlarda %334 saptigini olctu. Yani dunku "20/20 bantta" sonucu, YANLIS bir
paydayla hesaplanmisti.

Bu betik ayni merdiveni uc paydayla yeniden hesaplar:
   A) naif       : N(d2)                         <- dunku payda
   B) skew'li    : N(d2) - vega * dsigma/dK      <- duzeltilmis analitik
   C) modelsiz   : -dC/dK, komsu strike farki    <- BIRINCIL (D-027 karari)

Onemli olan yon: naif payda kanatlarda TERMINALI SISIRIYOR. Sisik payda orani
KUCULTUR. Yani duzeltme oranlari BUYUTUR.
  -> Sert alt sinir (oran >= 1) ihlal edilemez hale gelir; D-018 sonucu ayakta kalir.
  -> Ust sinir (oran <= 2) YUMUSAKTIR ve asilabilir; asan basamak ihlal degil BAYRAKTIR.
Bu ayrimi kaybetmemek icin ikisi ayri sayiliyor.
"""
import json, csv, os, math, datetime, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DER = os.path.join(BASE, 'raw', 'deribit_btc_monthly_2026-08-05T2135Z.csv')
STORE = os.path.join(BASE, 'raw', '_store.json')

SNAP = datetime.datetime(2026, 8, 5, 21, 35, 12, tzinfo=datetime.timezone.utc)
PM_EXPIRY = datetime.datetime(2026, 9, 1, 3, 59, tzinfo=datetime.timezone.utc)
EXP = {'28AUG26': datetime.datetime(2026, 8, 28, 8, 0, tzinfo=datetime.timezone.utc),
       '25SEP26': datetime.datetime(2026, 9, 25, 8, 0, tzinfo=datetime.timezone.utc)}
FUT = {'28AUG26': 64794.96, '25SEP26': 65024.68}
YEAR = 365.0
N = lambda x: 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
PHI = lambda x: math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
yrs = lambda t: (t - SNAP).total_seconds() / 86400.0 / YEAR

chain = {}
for r in csv.DictReader(open(DER, encoding='utf-8')):
    chain.setdefault(r['expiry'], {})[int(r['strike'])] = {
        'mark': float(r['mark']), 'iv': float(r['iv']) / 100.0}

E1, E2 = '28AUG26', '25SEP26'
T1, T2, TP = yrs(EXP[E1]), yrs(EXP[E2]), yrs(PM_EXPIRY)
w = (TP - T1) / (T2 - T1)
F = FUT[E1] + (FUT[E2] - FUT[E1]) * (TP - T1) / (T2 - T1)


def _br(c, K):
    """K'yi kusatan iki strike."""
    ks = sorted(c)
    lo = [k for k in ks if k < K]
    hi = [k for k in ks if k > K]
    return (lo[-1], hi[0]) if (lo and hi) else (None, None)


def iv_at(e, K):
    c = chain[e]
    if K in c:
        return c[K]['iv']
    a, b = _br(c, K)
    if a is None:
        return None
    return c[a]['iv'] + (c[b]['iv'] - c[a]['iv']) * (K - a) / (b - a)


def dsig_at(e, K):
    c = chain[e]
    a, b = _br(c, K)
    if a is None:
        return None
    return (c[b]['iv'] - c[a]['iv']) / (b - a)


def dig_at(e, K):
    c = chain[e]
    a, b = _br(c, K)
    if a is None:
        return None
    return max(0.0, min(1.0, (c[a]['mark'] - c[b]['mark']) / (b - a)))


def terminals(K):
    """Uc yontemle P(S_T > K), Polymarket vadesine tasinmis."""
    i1, i2 = iv_at(E1, K), iv_at(E2, K)
    if i1 is None or i2 is None:
        return None
    v = (i1 * i1 * T1) * (1 - w) + (i2 * i2 * T2) * w      # toplam varyans interp.
    if v <= 0:
        return None
    d1 = (math.log(F / K) + 0.5 * v) / math.sqrt(v)
    d2 = d1 - math.sqrt(v)
    naive = N(d2)
    s1, s2 = dsig_at(E1, K), dsig_at(E2, K)
    skew = None
    if s1 is not None and s2 is not None:
        ds = s1 * (1 - w) + s2 * w                          # skew de interpole edilir
        skew = max(0.0, min(1.0, naive - F * PHI(d1) * math.sqrt(TP) * ds))
    g1, g2 = dig_at(E1, K), dig_at(E2, K)
    digi = None if (g1 is None or g2 is None) else g1 * (1 - w) + g2 * w
    return {'naive': naive, 'skew': skew, 'dig': digi}


# ---------- Polymarket aylik touch merdiveni (dunku cikarma mantiginin aynisi) ----------
store = json.load(open(STORE, encoding='utf-8'))
raw = []
for m in store['markets'].values():
    ql = (m.get('question') or '').lower()
    if 'bitcoin' not in ql or m.get('endDateIso') != '2026-09-01':
        continue
    if 'reach' not in ql and 'dip to' not in ql:
        continue
    n = re.findall(r'\$([\d,]+)', m.get('question') or '')
    bb, ba = m.get('bestBid'), m.get('bestAsk')
    if not n or not (isinstance(bb, (int, float)) and isinstance(ba, (int, float))):
        continue
    raw.append({'K': int(n[0].replace(',', '')), 'dir': 'up' if 'reach' in ql else 'down',
                'mid': (bb + ba) / 2, 'spread': ba - bb, 'vol': m.get('volumeNum') or 0})

seen, rows = {}, []
for r in sorted(raw, key=lambda x: -x['vol']):
    if (r['K'], r['dir']) not in seen:
        seen[(r['K'], r['dir'])] = r
        rows.append(r)

print('=' * 100)
print('KATMAN 3 v2 — TOUCH PRIMI, SKEW DUZELTMESIYLE (D-027 borcu kapatiliyor)')
print('=' * 100)
print('Forward %.2f   |   PM vadesi T=%.4f yil   |   interp w=%.4f' % (F, TP, w))
print('%-5s %-8s %-9s %-9s %-9s %-9s %-7s %-7s %-7s %s'
      % ('YON', 'ESIK', 'PM_touch', 'A naif', 'B skew', 'C modelsz',
         'orA', 'orB', 'orC', 'DURUM (C birincil)'))
print('-' * 100)
out = []
cnt = {'ihlal': 0, 'bant': 0, 'bayrak': 0}
degisen = []
for r in sorted(rows, key=lambda x: (x['dir'], x['K'])):
    t = terminals(r['K'])
    if t is None or t['dig'] is None or t['skew'] is None:
        continue
    fix = lambda p: p if r['dir'] == 'up' else 1 - p
    tA, tB, tC = fix(t['naive']), fix(t['skew']), fix(t['dig'])
    if min(tA, tB, tC) <= 1e-6:
        continue
    oA, oB, oC = r['mid'] / tA, r['mid'] / tB, r['mid'] / tC
    if oC < 1:
        st = 'SERT IHLAL'; cnt['ihlal'] += 1
    elif oC <= 2:
        st = 'bantta'; cnt['bant'] += 1
    else:
        st = 'bayrak (>2)'; cnt['bayrak'] += 1
    dA = 'bantta' if 1 <= oA <= 2 else ('SERT IHLAL' if oA < 1 else 'bayrak (>2)')
    if dA != st:
        degisen.append((r['dir'], r['K'], dA, st, oA, oC))
    print('%-5s %-8d %-9.4f %-9.4f %-9.4f %-9.4f %-7.2f %-7.2f %-7.2f %s'
          % (r['dir'], r['K'], r['mid'], tA, tB, tC, oA, oB, oC, st))
    out.append({'dir': r['dir'], 'strike': r['K'], 'pm_touch': r['mid'],
                'pm_spread': r['spread'], 'term_naive': tA, 'term_skew': tB,
                'term_digital': tC, 'ratio_naive': oA, 'ratio_skew': oB,
                'ratio_digital': oC, 'status': st, 'volume': r['vol']})
print('-' * 100)
print('MODELSIZ PAYDAYLA (birincil): bantta %d  |  SERT IHLAL %d  |  bayrak(>2) %d   [toplam %d]'
      % (cnt['bant'], cnt['ihlal'], cnt['bayrak'], len(out)))
print()
if degisen:
    print('DUNKU SONUCA GORE DEGISEN BASAMAKLAR (naif payda -> modelsiz payda):')
    for d in degisen:
        print('   %-5s %-7d  %-12s -> %-12s   (oran %.2f -> %.2f)'
              % (d[0], d[1], d[2], d[3], d[4], d[5]))
else:
    print('Hicbir basamagin durumu degismedi — dunku sonuc paydaya karsi dayanikli cikti.')
print()
print('YORUM')
print(' * Sert alt sinir (oran >= 1) TANIM GEREGI dogrudur, model tartismasi yoktur.')
print(' * Ust sinir (oran <= 2) sifir suruklenme varsayimindan gelir; asmak IHLAL DEGIL.')
print(' * Naif payda kanatlarda terminali sisiriyordu; duzeltme oranlari BUYUTUR,')
print('   yani alt siniri daha da guvenli hale getirir, ust sinirda bayrak uretebilir.')
json.dump({'snapshot': SNAP.isoformat(), 'w': w, 'F': F, 'TP': TP,
           'counts': cnt, 'rows': out},
          open(os.path.join(BASE, 'inventory', 'touch_premium_v2.json'), 'w',
               encoding='utf-8'), ensure_ascii=False, indent=1)
