#!/usr/bin/env python3
"""
put_vs_itmcall_test.py — D-032'nin BEDELINI OLC (Polymarket verisi GEREKTIRMEZ)

D-032'de iddia ettim: asagi yon terminali derin ITM call'dan cikarilamaz.
O iddia dun teshis seviyesindeydi. Bugun elimizde ayni vadenin HEM call HEM put
zinciri var; iddia artik dogrudan olculebilir. Ayni buyuklugu iki yoldan hesapla:

    A) PUT yolu  (dogru)   : P(S_T < K) = +dP/dK, OTM put fiyatlarindan
    B) CALL yolu (D-032)   : P(S_T < K) = 1 - (-dC/dK), ITM call fiyatlarindan

Ikisi teorik olarak AYNI sayidir (put-call paritesi). Ayrilma miktari,
dogrudan olcum hatasidir. Uydurma yok, varsayim yok, hakem yok — ozdeslik.

BONUS — KATMAN 2 BEDAVA GELIYOR:
Put-call paritesi C - P = F - K, her strike icin bir F tahmini verir.
Strike'lar arasinda tutarliysa zincir ic tutarli demektir ve forward'i
vadeli veri cekmeden elde etmis oluruz.
"""
import csv, os, statistics

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(BASE, 'raw', 'deribit_btc_putcall_2026-08-28T1858Z.csv')
INDEX = 77478.56
ZAMAN_DEGERI_ESIK = 0.05

ch = {'C': {}, 'P': {}}
for r in csv.DictReader(open(CSV, encoding='utf-8')):
    if r['expiry'] != '25SEP26':
        continue
    ch[r['type']][int(r['strike'])] = {'mark': float(r['mark']),
                                       'iv': float(r['iv']) / 100.0}

# ---------- KATMAN 2: put-call paritesinden forward ----------
print('=' * 92)
print('KATMAN 2 (bedava) — put-call paritesinden ileri fiyat:  F = K + C - P')
print('=' * 92)
Fs = []
ortak = sorted(set(ch['C']) & set(ch['P']))
for K in ortak:
    if not (0.75 * INDEX <= K <= 1.30 * INDEX):      # parite basaba yakininda saglam
        continue
    F = K + ch['C'][K]['mark'] - ch['P'][K]['mark']
    Fs.append((K, F))
for K, F in Fs:
    print('   K=%-8d F=%.2f' % (K, F))
F_MED = statistics.median([f for _, f in Fs])
sp = max(f for _, f in Fs) - min(f for _, f in Fs)
print('-' * 92)
print('Medyan F = %.2f   |   dagilim = %.2f USD (%.3f%%)   |   index = %.2f'
      % (F_MED, sp, 100 * sp / F_MED, INDEX))
print('Bazis (F/index - 1) = %+.3f%%  -> 28 gunde yillik %+.1f%% tasima'
      % (100 * (F_MED / INDEX - 1), 100 * ((F_MED / INDEX) ** (365 / 28) - 1)))
print('YORUM: dagilim dar ise zincir IC TUTARLI. Vadeli veri cekmeden forward elde.')

# ---------- D-032: put yolu vs ITM call yolu ----------
def dig_put(K):
    """P(S_T < K) = +dP/dK  (OTM put tarafi, iyi kosullu)."""
    ks = sorted(ch['P'])
    lo = [k for k in ks if k < K]
    hi = [k for k in ks if k > K]
    if not lo or not hi:
        return None
    a, b = lo[-1], hi[0]
    return max(0.0, min(1.0, (ch['P'][b]['mark'] - ch['P'][a]['mark']) / (b - a)))


def dig_call(K):
    """P(S_T < K) = 1 - (-dC/dK)  (K < F ise ITM call tarafi, KOTU kosullu)."""
    ks = sorted(ch['C'])
    lo = [k for k in ks if k < K]
    hi = [k for k in ks if k > K]
    if not lo or not hi:
        return None
    a, b = lo[-1], hi[0]
    return max(0.0, min(1.0, 1.0 - (ch['C'][a]['mark'] - ch['C'][b]['mark']) / (b - a)))


def zaman_degeri(K):
    """ITM call'da zaman degerinin fiyata orani. D-032 dedektoru."""
    c = ch['C'].get(K)
    if not c or c['mark'] <= 0:
        return None
    return (c['mark'] - max(0.0, INDEX - K)) / c['mark']


print('\n' + '=' * 92)
print('D-032 TESTI — ayni sayi, iki yol.  P(S_T < K), 25SEP26')
print('=' * 92)
print('%-9s %-11s %-13s %-13s %-11s %s'
      % ('ESIK', 'zam.deg.', 'A: PUT yolu', 'B: CALL yolu', 'B/A', 'DEGERLENDIRME'))
print('-' * 92)
rows = []
for K in sorted(ch['P']):
    if K > F_MED or K < 40000:
        continue
    a, b = dig_put(K), dig_call(K)
    zd = zaman_degeri(K)
    if a is None or b is None or a < 1e-5:
        continue
    r = b / a
    kotu = (zd is not None and zd < ZAMAN_DEGERI_ESIK)
    st = ('CALL YOLU COKTU' if (r > 2 or r < 0.5) else
          'call yolu sapiyor' if (r > 1.25 or r < 0.8) else 'iki yol uyumlu')
    print('%-9d %-11s %-13.4f %-13.4f %-11.2fx %s'
          % (K, ('%.1f%%' % (100 * zd)) if zd is not None else '-', a, b, r,
             st + (' (derin ITM)' if kotu else '')))
    rows.append((K, zd, a, b, r, kotu))
print('-' * 92)
derin = [x for x in rows if x[5]]
sig = [x for x in rows if not x[5]]
if derin:
    rr = [x[4] for x in derin]
    print('DERIN ITM bolgesi (zaman degeri < %.0f%%): %d basamak, B/A orani %.2f–%.2f'
          % (100 * ZAMAN_DEGERI_ESIK, len(derin), min(rr), max(rr)))
if sig:
    rr = [x[4] for x in sig]
    print('SAGLAM bolge                            : %d basamak, B/A orani %.2f–%.2f'
          % (len(sig), min(rr), max(rr)))
print()
print('SONUC — D-032 artik teshis degil, OLCUM.')
print(' * Iki yol ayni sayiyi vermek ZORUNDA (put-call paritesi). Ayrilma = hata.')
print(' * Hata derin ITM bolgesinde patliyor, saglam bolgede kayboluyor.')
print(' * Kural: asagi yon icin PUT zinciri sart. Put yoksa sayi uretilmez.')
