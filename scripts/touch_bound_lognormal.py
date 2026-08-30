#!/usr/bin/env python3
"""
touch_bound_lognormal.py — "2" ust siniri dogru mu, ve asagi yon olculebilir mi?

IKI SORU BIRDEN. Ilk surumde sigma'yi terminal olasiliktan geri cikarmaya
calistim; cozucu doydu (hepsi %400). Sebep: N(d2) sigma'da MONOTON DEGIL,
yukari strike'larda iki cozum var. Duzeltme: sigma'yi uydurmak yerine
zincirin KENDI IV'sini kullan, vadeye toplam varyansla tasi.

SORU 1 — Ust sinir "2" hatali mi?
  Lognormal, ileri olcude martingal: X_t = mu*t + sigma*W_t, mu = -sigma^2/2
    asagi b = ln(B/F) < 0:
       terminal = N((b-mu*T)/rT)
       touch    = terminal + exp(-b) * N((b+mu*T)/rT)
    yukari a = ln(A/F) > 0:
       terminal = N((-a+mu*T)/rT)
       touch    = terminal + exp(-a) * N((-a-mu*T)/rT)
  "2" sabiti yalnizca suruklenmesiz aritmetik BM'de tamdir. Tam formul her
  basamak icin KENDI ust sinirini verir; sabit bir sayi degildir.

SORU 2 — Asagi yon terminali guvenilir mi?  (D-025'in tekrari olabilir)
  Elimizdeki Deribit dosyasi YALNIZCA CALL iceriyor. Asagi yon terminali
  1 - P(S>K) olarak, yani DERIN ITM call'lardan cikiyor.
  Derin ITM call fiyati neredeyse tamamen ic degerdir; zaman degeri fiyatin
  yuzde birkacidir. Boyle bir fiyattan turev almak, kucuk bir farki buyuk iki
  sayinin farkindan okumaktir. D-025 tam olarak bu tuzakti.
  Bu betik her basamak icin ZAMAN DEGERI PAYINI olcup rapor eder.
  Pay kucukse o satirin sayisi UYDURMADIR; teorik tartismaya girmeden elenir.
"""
import json, csv, os, math

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = lambda x: 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
ZAMAN_DEGERI_ESIK = 0.05      # ic degerin %5'inden az zaman degeri -> olculemez

d = json.load(open(os.path.join(BASE, 'inventory', 'touch_premium_v2.json'),
                   encoding='utf-8'))
F, TP, w = d['F'], d['TP'], d['w']

chain = {}
for r in csv.DictReader(open(os.path.join(
        BASE, 'raw', 'deribit_btc_monthly_2026-08-05T2135Z.csv'), encoding='utf-8')):
    chain.setdefault(r['expiry'], {})[int(r['strike'])] = {
        'mark': float(r['mark']), 'iv': float(r['iv']) / 100.0}
E1, E2 = '28AUG26', '25SEP26'
T1, T2 = 0.06146, 0.13804      # skew_correction_btc.py ile ayni vade tanimlari
INDEX = 64638.85


def interp(c, K, alan):
    ks = sorted(c)
    if K in c:
        return c[K][alan]
    lo = [k for k in ks if k < K]
    hi = [k for k in ks if k > K]
    if not lo or not hi:
        return None
    a, b = lo[-1], hi[0]
    return c[a][alan] + (c[b][alan] - c[a][alan]) * (K - a) / (b - a)


def sigma_TP(K):
    """Toplam varyans interpolasyonuyla Polymarket vadesindeki sigma."""
    i1, i2 = interp(chain[E1], K, 'iv'), interp(chain[E2], K, 'iv')
    if i1 is None or i2 is None:
        return None
    v = (i1 * i1 * T1) * (1 - w) + (i2 * i2 * T2) * w
    return math.sqrt(v / TP) if v > 0 else None


def zaman_degeri_payi(K):
    """Derin ITM call teshisi: zaman degeri / opsiyon fiyati. D-025 dedektoru."""
    mk = interp(chain[E1], K, 'mark')
    if mk is None or mk <= 0:
        return None
    ic = max(0.0, INDEX - K)
    return (mk - ic) / mk


def teorik(K, direction, sigma):
    mu = -0.5 * sigma * sigma
    rT = sigma * math.sqrt(TP)
    x = math.log(K / F)
    if direction == 'down':
        term = N((x - mu * TP) / rT)
        touch = term + math.exp(-x) * N((x + mu * TP) / rT)
    else:
        term = N((-x + mu * TP) / rT)
        touch = term + math.exp(-x) * N((-x - mu * TP) / rT)
    return (touch / term) if term > 1e-12 else None


print('=' * 104)
print('UST SINIR + OLCULEBILIRLIK TESTI')
print('=' * 104)
print('%-5s %-8s %-9s %-9s %-11s %-11s %-9s %s'
      % ('YON', 'ESIK', 'sigma', 'zam.deg.', 'GOZLENEN', 'TEORIK ust', 'gozl/teo', 'DURUM'))
print('-' * 104)
res = []
for r in d['rows']:
    K, dr = r['strike'], r['dir']
    s = sigma_TP(K)
    if s is None:
        continue
    zd = zaman_degeri_payi(K)
    to = teorik(K, dr, s)
    obs = r['ratio_digital']
    if to is None:
        continue
    if dr == 'down' and zd is not None and zd < ZAMAN_DEGERI_ESIK:
        st = 'OLCULEMEZ — derin ITM call (D-025)'
        rel = None
    elif obs > to:
        st = 'teorik ustu asiyor'
        rel = obs / to
    else:
        st = 'teorik ustun altinda'
        rel = obs / to
    print('%-5s %-8d %-9.1f %-9s %-11.2f %-11.2f %-9s %s'
          % (dr, K, s * 100, ('%.1f%%' % (100 * zd)) if zd is not None else '-',
             obs, to, ('%.2f' % rel) if rel else '-', st))
    res.append({'dir': dr, 'strike': K, 'sigma': s, 'zaman_degeri_payi': zd,
                'observed': obs, 'theoretical_max': to, 'rel': rel, 'status': st})
print('-' * 104)
olc = [x for x in res if not x['status'].startswith('OLCULEMEZ')]
elen = [x for x in res if x['status'].startswith('OLCULEMEZ')]
alt = [x for x in olc if x['observed'] <= x['theoretical_max']]
print('Olculebilir basamak : %d / %d   (elenen: %d, hepsi asagi yon derin ITM)'
      % (len(olc), len(res), len(elen)))
print('Teorik ustun altinda: %d / %d' % (len(alt), len(olc)))
if olc:
    rr = [x['rel'] for x in olc]
    print('gozlenen/teorik ortalamasi = %.2f  (1,00 = sinira tam yapisik)'
          % (sum(rr) / len(rr)))
print()
print('KARSILASTIRMA')
print('  eski sabit "2" ile           : bantta 6 / 19')
print('  lognormal tam sinir + eleme  : teorik altinda %d / %d olculebilir'
      % (len(alt), len(olc)))
print()
print('SONUC')
print(' * "2" bir SABIT DEGIL. Her basamagin kendi ust siniri var; sabiti kullanmak')
print('   yukari yonde fazla gevsek, asagi yonde fazla siki bir sinir uretiyordu.')
print(' * Asagi yon basamaklari CALL zincirinden olculemiyor. Cozum PUT verisi cekmek;')
print('   put yoksa asagi yon icin sayi uretilmemeli. Bu D-025 kuralinin aynen tekrari.')
json.dump(res, open(os.path.join(BASE, 'inventory', 'touch_bound_lognormal.json'), 'w',
                    encoding='utf-8'), ensure_ascii=False, indent=1)
