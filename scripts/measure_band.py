#!/usr/bin/env python3
"""Surtunme bandi olcumu — kac basamak islem maliyetini asiyor?

SORU
Prediction market fiyati ile opsiyon zincirinden cikan dijital olasilik
arasindaki fark, o farki islemek icin odenecek bedelden BUYUK mu?

Bedel uc parcadan olusuyor:
  1. Opsiyon ucreti      — Deribit: dayanak basina %0.03, opsiyon fiyatinin
                           %12.5'iyle sinirli. Iki bacak icin de odenir.
  2. Prediction makasi   — alis-satis farkinin yarisi.
  3. Olcum belirsizligi  — dijital, iki komsu strike'in fiyat farkindan
                           cikiyor; her iki bacagin makasi sonuca hata
                           tasiyor. 1.96 * standart hata (yaklasik %95).

Esik = 1.96*SE + surtunme.  |PM - opsiyon| > esik ise "bandi asiyor".

NEDEN BU BETIK VAR
Ekranda "0/44" yaziyordu ama onu ureten hicbir sey repoda yoktu; eski
betikler artik var olmayan bir dosya duzenini okuyordu (denetim, 2026-09-11).
Bu betik hesabi ham arsivden yapar, dolayisiyla sonucu kontrol edilebilir.

TEK ANLIK GORUNTU YETMEZ
Tek bir anlik goruntuden istatistiksel anlamlilik iddia edilemez.
O yuzden butun arsiv taranir ve dagilim raporlanir. Bir basamagin bandi
astigi an, ertesi kosuda asmayabilir; onemli olan oran degil, kararlilik.

Mantik web/index.html'deki `kovalar()` fonksiyonundan BIREBIR tasindi.
Ikisi ayrilirsa ekran ile kayit celisir; o yuzden degistiren ikisini de
degistirmeli.

Kullanim:
    python scripts/measure_band.py             # butun arsiv
    python scripts/measure_band.py --son 5     # yalnizca son 5 kosu
    python scripts/measure_band.py --json      # makine okunur cikti
"""
import json
import math
import re
import sys

from arsiv import anlik_goruntu, anlar, ozet, Eksik
from kararlilik import Kararlilik

SERILER = [('BTC', 'KXBTCY', 'BTC'), ('ETH', 'KXETHY', 'ETH')]

AY = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
      'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
VADE = re.compile(r'^(\d+)([A-Z]{3})(\d{2})$')


def van(etiket):
    """Deribit vade etiketi -> siralanabilir sayi. '26DEC25' -> 20251226"""
    m = VADE.match(etiket)
    if not m:
        return None
    return (2000 + int(m.group(3))) * 10000 + AY[m.group(2)] * 100 + int(m.group(1))


def zincir(D, para):
    """Deribit book_summary -> ch[vade]['C'/'P'][strike] = {mark,bid,ask}
    Fiyatlar ters (inverse) kontratta dayanak cinsinden gelir; endeksle
    carpip dolara ceviriyoruz."""
    idx = D[para]['index']['result']['index_price']
    bs = D[para]['book_summary']
    bs = bs['result'] if isinstance(bs, dict) else bs
    ch = {}
    for b in bs:
        q = b['instrument_name'].split('-')
        if len(q) != 4:
            continue
        vade, strike, tur = q[1], float(q[2]), q[3]
        ch.setdefault(vade, {}).setdefault(tur, {})[strike] = {
            'mark': (b.get('mark_price') or 0) * idx,
            'bid': b['bid_price'] * idx if b.get('bid_price') else None,
            'ask': b['ask_price'] * idx if b.get('ask_price') else None,
        }
    return ch, idx


def forward(ch, vade, idx):
    """Put-call paritesinden ileri fiyat: F = K + C - P. Medyan alinir ki
    tek bir bozuk kotasyon sonucu suruklemesin. Vadeli veri gerekmez."""
    C, P = ch[vade].get('C'), ch[vade].get('P')
    if not C or not P:
        return None
    v = [k + C[k]['mark'] - P[k]['mark']
         for k in C if k in P and 0.85 * idx < k < 1.2 * idx]
    if not v:
        return None
    v.sort()
    return v[len(v) // 2]


def kusatan(o, K):
    """K'yi saran iki komsu strike."""
    ks = sorted(o)
    alt = [k for k in ks if k < K]
    ust = [k for k in ks if k > K]
    return (alt[-1], ust[0]) if alt and ust else None


def dijital(ch, vade, K, F, idx):
    """P(S_T > K) = -dC/dK, iki komsu strike'in fark bolumuyle.

    Model YOK: lognormal varsayilmaz, IV kullanilmaz. Yalnizca fiyat farki.
    Yon secimi onemli: K forward'in altindaysa PUT tarafi kullanilir, cunku
    derin ITM call'da zaman degeri fiyatin cok kucuk bir parcasidir ve
    fark bolumu gurultuye bogulur (D-025 / D-032).
    """
    tur = 'P' if K < F else 'C'
    o = ch[vade].get(tur)
    if not o:
        return None
    br = kusatan(o, K)
    if not br:
        return None
    a, b = br
    g = b - a
    A, B = o[a], o[b]
    p = (A['mark'] - B['mark']) / g if tur == 'C' else 1 - (B['mark'] - A['mark']) / g
    if None in (A['bid'], A['ask'], B['bid'], B['ask']):
        se = None
    else:
        se = math.sqrt(((A['ask'] - A['bid']) / 2) ** 2 +
                       ((B['ask'] - B['bid']) / 2) ** 2) / g
    # Deribit: dayanak basina %0.03, opsiyon fiyatinin %12.5'iyle sinirli
    ucret = lambda x: min(0.0003 * idx, 0.125 * x)
    return {'p': p, 'se': se, 'fee': (ucret(A['mark']) + ucret(B['mark'])) / g}


def basamaklar(KA, D, seri, para):
    """Bir Kalshi kova merdiveninin butun basamaklari icin band hesabi."""
    M = [m for m in (KA.get('marketler', {}).get(seri) or [])
         if m.get('status') == 'active']
    if not M:
        return None
    ch, idx = zincir(D, para)
    kapanis = M[0].get('close_time', '')

    uygun = sorted((v for v in ch if ch[v].get('C') and ch[v].get('P')), key=van)
    uygun = [v for v in uygun if van(v)]
    if not uygun:
        return None
    # Kalshi vadesini GECMEYEN en yakin opsiyon vadesi. Esit degil: vade
    # boslugu kalirsa sonuc bizim lehimize sapar, bu cekince raporlanir.
    hedef = int(kapanis[:4] + kapanis[5:7] + kapanis[8:10]) if len(kapanis) >= 10 else None
    alt = [v for v in uygun if hedef is None or van(v) <= hedef]
    if not alt:
        return None
    vade = alt[-1]

    F = forward(ch, vade, idx)
    if not F:
        return None

    S = sorted(M, key=lambda m: (m.get('floor_strike') if m.get('floor_strike')
                                 is not None else m.get('cap_strike')) or 0)
    satirlar = []
    for m in S:
        tip = m.get('strike_type')
        lo = hi = None
        if tip == 'less':
            hi = round(m['cap_strike'])
        elif tip == 'greater':
            lo = round(m['floor_strike'] + .01)
        else:
            lo = round(m['floor_strike'])
            hi = round(m['cap_strike'] + .01)   # kova siniri: D-067 duzeltmesi

        etiket = m.get('ticker') or ('%s-%s' % (lo, hi))
        dL = dijital(ch, vade, lo, F, idx) if lo is not None else {'p': 1, 'se': 0, 'fee': 0}
        dH = dijital(ch, vade, hi, F, idx) if hi is not None else {'p': 0, 'se': 0, 'fee': 0}
        pm = (float(m['yes_bid_dollars']) + float(m['yes_ask_dollars'])) / 2
        mk = float(m['yes_ask_dollars']) - float(m['yes_bid_dollars'])
        if not dL or not dH:
            satirlar.append({'etiket': etiket, 'sessiz': 'strike araligi disinda',
                             'pm': pm, 'mk': mk})
            continue
        opt = dL['p'] - dH['p']
        se = None if (dL['se'] is None or dH['se'] is None) else \
            math.sqrt(dL['se'] ** 2 + dH['se'] ** 2)
        surt = dL['fee'] + dH['fee'] + mk / 2
        esik = (0 if se is None else 1.96 * se) + surt
        satirlar.append({'etiket': etiket, 'pm': pm, 'opt': opt, 'fark': pm - opt,
                         'se': se, 'surt': surt, 'esik': esik, 'mk': mk,
                         'asiyor': abs(pm - opt) > esik})
    return {'satirlar': satirlar, 'vade': vade, 'F': F, 'idx': idx,
            'toplam': sum(r['opt'] for r in satirlar if 'opt' in r)}


def kosu(damga, kar=None):
    """Tek anlik goruntu icin iki serinin band sonucu.
    kar: Kararlilik sayaci — ayni basamagin kosular boyunca davranisini izler."""
    g = anlik_goruntu(damga)
    cikti = {'damga': damga, 'pencere': g.pencere, 'seriler': {}}
    for varlik, seri, para in SERILER:
        try:
            h = basamaklar(g.kalshi, g.deribit, seri, para)
        except (KeyError, TypeError, ValueError) as e:
            cikti['seriler'][varlik] = {'hata': '%s: %s' % (type(e).__name__, e)}
            continue
        if not h:
            cikti['seriler'][varlik] = {'hata': 'merdiven yok'}
            continue
        olculen = [r for r in h['satirlar'] if 'opt' in r]
        if kar is not None:
            for r in olculen:
                kar.ekle('%s:%s' % (varlik, r.get('etiket')), r['asiyor'])
        cikti['seriler'][varlik] = {
            'basamak': len(h['satirlar']),
            'olculen': len(olculen),
            'asan': sum(1 for r in olculen if r['asiyor']),
            'vade': h['vade'],
            'yogunluk_toplami': round(h['toplam'], 4),
            'ort_esik': round(sum(r['esik'] for r in olculen) / len(olculen), 4)
            if olculen else None,
        }
    return cikti


def main():
    argv = sys.argv[1:]
    son = None
    if '--son' in argv:
        son = int(argv[argv.index('--son') + 1])
    makine = '--json' in argv

    hepsi = anlar('_meta')
    if son:
        hepsi = hepsi[-son:]

    o = ozet()
    kar = Kararlilik()
    sonuclar = []
    for d in hepsi:
        try:
            sonuclar.append(kosu(d, kar))
        except Eksik as e:
            sonuclar.append({'damga': d, 'hata': str(e)})

    if makine:
        print(json.dumps({'arsiv': o, 'kosular': sonuclar},
                         ensure_ascii=False, indent=1))
        return 0

    print('SURTUNME BANDI OLCUMU')
    print('arsiv: %(anlik_goruntu_sayisi)d anlik goruntu / %(gun_sayisi)d gun' % o)
    print('taranan: %d kosu' % len(sonuclar))
    print()
    print('%-18s %6s  %-22s %-22s' % ('an', 'pencere', 'BTC (asan/olculen)', 'ETH (asan/olculen)'))
    print('-' * 74)

    top_asan = top_olculen = 0
    for s in sonuclar:
        if 'hata' in s:
            print('%-18s  %s' % (s['damga'], s['hata']))
            continue
        hucre = []
        for v in ('BTC', 'ETH'):
            d = s['seriler'].get(v, {})
            if 'hata' in d:
                hucre.append('%-22s' % d['hata'][:22])
            else:
                hucre.append('%-22s' % ('%d/%d   (yogunluk %.3f)'
                                        % (d['asan'], d['olculen'], d['yogunluk_toplami'])))
                top_asan += d['asan']
                top_olculen += d['olculen']
        print('%-18s %6s  %s %s' % (s['damga'], s['pencere'], hucre[0], hucre[1]))

    print('-' * 74)
    print('TOPLAM: %d / %d basamak-gozlemi bandi asti' % (top_asan, top_olculen))
    if top_olculen:
        print('        %.1f%% — bu bir oran, firsat sayisi DEGIL.' %
              (100.0 * top_asan / top_olculen))
    kar.yaz('KARARLILIK — Kalshi kova basamaklari')
    print()
    print('Okuma notu: "asan" = fark, surtunme + 1.96*SE toplamindan buyuk.')
    print('Bandi asmak islenebilir demek degildir; teminat maliyeti, vade')
    print('boslugu ve cozunurluk kaynagi farki bu hesaba GIRMIYOR.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
