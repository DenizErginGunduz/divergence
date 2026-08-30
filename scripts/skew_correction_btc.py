#!/usr/bin/env python3
"""
skew_correction_btc.py — D-027 BORCU: BTC olcumlerini skew terimiyle yeniden hesapla

SORUN (D-027'de SPY'da yakalandi):
Dijital olasilik, call fiyatinin strike'a gore turevidir:
        P(S_T > K) = -dC/dK
Ama C, K'ya IKI yoldan bagli: dogrudan, ve IV egrisi uzerinden.
        C = C_BS(K, sigma(K))
        dC/dK = (dC_BS/dK)|sigma  +  vega * (dsigma/dK)
                 \_____________/     \________________/
                   -N(d2)              SKEW TERIMI

Naif N(d2), ikinci terimi TAMAMEN atiyor. Skew varken (BTC'de her zaman var)
bu sistematik bir hatadir; SPY'da sol kanatta 2,12x sapma olcmustuk.

Bu betik ayni merdivenleri UC yontemle hesaplar ve yan yana koyar:
   A) naif      : N(d2)                        <- dunku hatali yontem
   B) skew'li   : N(d2) - vega * dsigma/dK     <- duzeltilmis analitik
   C) modelsiz  : [C(a) - C(b)] / (b - a)      <- hicbir varsayim tasimaz, HAKEM

C hakemdir. B, C'ye A'dan daha yakinsa duzeltme dogru yonde calisiyor demektir.

Black-76 (ileri fiyat uzerinde, iskonto ihmal — vadeler <=51 gun):
   d1 = (ln(F/K) + v/2) / sqrt(v),  d2 = d1 - sqrt(v),   v = sigma^2 * T
   dC/dK|sigma = -N(d2)
   vega        = F * phi(d1) * sqrt(T)
"""
import csv, os, math, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = lambda x: 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
PHI = lambda x: math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
YEAR = 365.0


def load(path):
    """CSV'yi vade -> strike -> {mark, iv} sozlugune cevirir. IV yuzdeden ondaliga."""
    ch = {}
    for r in csv.DictReader(open(path, encoding='utf-8')):
        ch.setdefault(r['expiry'], {})[int(r['strike'])] = {
            'mark': float(r['mark']), 'iv': float(r['iv']) / 100.0}
    return ch


def iv_at(c, K):
    """Strike bazinda IV; tam strike yoksa komsulardan dogrusal ara deger."""
    if K in c:
        return c[K]['iv']
    ks = sorted(c)
    lo = [k for k in ks if k < K]
    hi = [k for k in ks if k > K]
    if not lo or not hi:
        return None
    a, b = lo[-1], hi[0]
    return c[a]['iv'] + (c[b]['iv'] - c[a]['iv']) * (K - a) / (b - a)


def dsigma_dK(c, K):
    """IV egiminin merkezi farkla olcumu. Bu, D-027'de eksik olan buyukluk."""
    ks = sorted(c)
    lo = [k for k in ks if k < K]
    hi = [k for k in ks if k > K]
    if not lo or not hi:
        return None
    a, b = lo[-1], hi[0]
    return (c[b]['iv'] - c[a]['iv']) / (b - a)


def probs(c, K, F, T):
    """Ayni strike icin naif ve skew duzeltmeli olasilik + ara buyuklukler."""
    s = iv_at(c, K)
    sk = dsigma_dK(c, K)
    if s is None or s <= 0 or T <= 0:
        return None
    v = s * s * T
    d1 = (math.log(F / K) + 0.5 * v) / math.sqrt(v)
    d2 = d1 - math.sqrt(v)
    naive = N(d2)
    vega = F * PHI(d1) * math.sqrt(T)          # birim vol basina USD
    corr = vega * sk if sk is not None else 0.0
    return {'naive': naive, 'skew_adj': max(0.0, min(1.0, naive - corr)),
            'vega': vega, 'dsig': sk, 'corr': corr, 'iv': s}


def digital(c, K):
    """Modelsiz hakem: K'yi kusatan iki strike'in call fiyat farki."""
    ks = sorted(c)
    lo = [k for k in ks if k < K]
    hi = [k for k in ks if k > K]
    if not lo or not hi:
        return None
    a, b = lo[-1], hi[0]
    return max(0.0, min(1.0, (c[a]['mark'] - c[b]['mark']) / (b - a)))


def rapor(baslik, c, F, T, strikes):
    print('\n' + '=' * 96)
    print(baslik)
    print('=' * 96)
    print('Forward %.2f   |   T = %.5f yil (%.1f gun)' % (F, T, T * YEAR))
    print('%-8s %-7s %-11s %-9s %-10s %-10s %-10s %s'
          % ('K', 'IV', 'dsig/dK', 'vega', 'A naif', 'B skewli', 'C modelsiz',
             'naif/modelsiz'))
    print('-' * 96)
    sa, sb = [], []
    for K in strikes:
        p = probs(c, K, F, T)
        d = digital(c, K)
        if p is None or d is None or d < 1e-4:
            continue
        ra, rb = p['naive'] / d, p['skew_adj'] / d
        sa.append(abs(ra - 1)); sb.append(abs(rb - 1))
        print('%-8d %-7.1f %-11.2e %-9.0f %-10.4f %-10.4f %-10.4f %.2fx'
              % (K, p['iv'] * 100, p['dsig'], p['vega'],
                 p['naive'], p['skew_adj'], d, ra))
    print('-' * 96)
    if sa:
        print('Hakemden ortalama sapma:  A naif = %.1f%%   ->   B skewli = %.1f%%'
              % (100 * sum(sa) / len(sa), 100 * sum(sb) / len(sb)))
        print('En buyuk sapma         :  A naif = %.1f%%   ->   B skewli = %.1f%%'
              % (100 * max(sa), 100 * max(sb)))
    return sa, sb


# ---------------- 1) GUNLUK zincir: bridge_btc.py'nin dayandigi veri ----------------
g = load(os.path.join(BASE, 'raw', 'deribit_btc_2026-08-05T2123Z.csv'))
SNAP_G = datetime.datetime(2026, 8, 5, 21, 22, 55, tzinfo=datetime.timezone.utc)
T_6AUG = (datetime.datetime(2026, 8, 6, 8, 0, tzinfo=datetime.timezone.utc)
          - SNAP_G).total_seconds() / 86400.0 / YEAR
ks_g = [k for k in sorted(g['6AUG26']) if 60000 <= k <= 67000]
a1, b1 = rapor('GUNLUK ZINCIR — 6AUG26 (bridge_btc.py bu veriyi kullaniyor)',
               g['6AUG26'], 64673.90, T_6AUG, ks_g)

# ---------------- 2) AYLIK zincir: touch_premium_btc.py'nin dayandigi veri ----------
m = load(os.path.join(BASE, 'raw', 'deribit_btc_monthly_2026-08-05T2135Z.csv'))
SNAP_M = datetime.datetime(2026, 8, 5, 21, 35, 12, tzinfo=datetime.timezone.utc)
T_28AUG = (datetime.datetime(2026, 8, 28, 8, 0, tzinfo=datetime.timezone.utc)
           - SNAP_M).total_seconds() / 86400.0 / YEAR
ks_m = [k for k in sorted(m['28AUG26']) if 52000 <= k <= 85000]
a2, b2 = rapor('AYLIK ZINCIR — 28AUG26 (touch_premium_btc.py bu veriyi kullaniyor)',
               m['28AUG26'], 64794.96, T_28AUG, ks_m)

print('\n' + '=' * 96)
print('SONUC — D-027 duzeltmesinin BTC tarafindaki etkisi')
print('=' * 96)
for ad, A, B in (('gunluk 6AUG26', a1, b1), ('aylik 28AUG26', a2, b2)):
    if not A:
        continue
    ia, ib = sum(A) / len(A), sum(B) / len(B)
    print('%-16s ortalama sapma %.1f%% -> %.1f%%   (%s)'
          % (ad, 100 * ia, 100 * ib,
             'DUZELDI' if ib < ia else 'DUZELMEDI — incelenmeli'))
