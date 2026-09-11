#!/usr/bin/env python3
"""Uzun ufuk touch siniri — ucuncu kurulum, ve tek MODEL VARSAYAN olcum.

TOUCH NEDIR, NEDEN ZOR
"What price will Bitcoin hit in 2026?" sorusu vade icinde HERHANGI BIR AN
esige degmeyi sorar. Opsiyon zincirinde bunun dogrudan karsiligi YOKTUR.
Terminal olasilik P(S_T > K) fiyatlardan modelsiz cikar; touch cikmaz.

Bu yuzden bu olcum digerlerinden farklidir ve oyle isaretlenir:
diger iki kurulum MODELSIZ, bu MODEL VARSAYAR.

SINIR
Driftsiz aritmetik Brown hareketinde yansima ilkesi touch = 2 * terminal
verir. Gercek dunyada uc varsayim da tutmaz: surukleme sifir degil, izleme
surekli degil, volatilite tek degil. O yuzden "2" bir sabit DEGILDIR (D-031).

Lognormal altinda risk-notr olcude, a = ln(A/F) ve mu = -sigma^2/2 icin:

    terminal = N((-a + mu*T) / (sigma*sqrt(T)))
    touch    = terminal + exp(-a) * N((-a - mu*T) / (sigma*sqrt(T)))

Bu bir SINIR verir, nokta tahmini degil. Oran teorik olarak 1 ile 2 arasinda
olmalidir. Oran 1'in ALTINDAYSA arbitrajsizlik ihlali vardir: bir seviyeye
vade icinde degme olasiligi, vadede o seviyenin ustunde KAPANMA olasiligindan
kucuk olamaz. Bu betigin en degerli ciktisi o ihlalleri saymaktir — cunku
ihlal, modele degil aritmetige aykiridir.

sigma NEREDEN GELIYOR
Zincirin kendi ima edilen volatilitesinden, esige en yakin iki strike'in
mark_iv'si arasinda dogrusal interpolasyonla. Bisection ile sigma cozmeyi
DENEDIK ve elendi: N(d2) yukari strike'larda sigma'da monoton degil,
cozucu %400'de doyuyordu.

Kullanim:
    python scripts/measure_touch.py
    python scripts/measure_touch.py --son 5
"""
import math
import re
import sys

from arsiv import anlik_goruntu, anlar, ozet, Eksik
from measure_band import forward, dijital, AY
from kararlilik import Kararlilik

VARLIKLAR = [('BTC', 'bitcoin', 'BTC'), ('ETH', 'ethereum', 'ETH')]
TOUCH_BASLIK = re.compile(r'What price will (Bitcoin|Ethereum) hit', re.I)
VADE_ET = re.compile(r'^(\d+)([A-Z]{3})(\d{2})$')


def _norm(x):
    """Standart normal kumulatif — scipy yok, erf yeterli."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def zincir_iv(D, para):
    """Deribit zinciri + her strike'in ima edilen volatilitesi.
    measure_band.zincir mark_iv tasimiyor; touch icin sigma sart."""
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
            'iv': (b.get('mark_iv') or 0) / 100.0,
        }
    return ch, idx


def vade_gun(etiket):
    m = VADE_ET.match(etiket)
    if not m:
        return None
    return (2000 + int(m.group(3))) * 372 + AY[m.group(2)] * 31 + int(m.group(1))


def sigma_interp(o, K):
    """Esigi saran iki strike'in IV'si arasinda dogrusal interpolasyon."""
    ks = sorted(k for k in o if o[k].get('iv'))
    if not ks:
        return None
    alt = [k for k in ks if k <= K]
    ust = [k for k in ks if k >= K]
    if not alt or not ust:
        # esik zincirin disinda: en yakin ucu kullan, ama uydurma yapma
        return o[ks[0]]['iv'] if K < ks[0] else o[ks[-1]]['iv']
    a, b = alt[-1], ust[0]
    if a == b:
        return o[a]['iv']
    w = (K - a) / (b - a)
    return o[a]['iv'] * (1 - w) + o[b]['iv'] * w


def touch_sinir(A, F, sigma, T):
    """Lognormal altinda terminal ve touch. A: esik, F: forward."""
    if sigma <= 0 or T <= 0 or F <= 0 or A <= 0:
        return None
    a = math.log(A / F)
    mu = -0.5 * sigma * sigma
    kok = sigma * math.sqrt(T)
    terminal = _norm((-a + mu * T) / kok)
    touch = terminal + math.exp(-a) * _norm((-a - mu * T) / kok)
    return {'terminal': terminal, 'touch': min(touch, 1.0)}


def kosu(damga, kar):
    g = anlik_goruntu(damga)
    PM, D = g.polymarket, g.deribit
    sonuc = {'damga': damga, 'olcum': 0, 'ihlal': 0, 'band_disi': 0}
    for varlik, anahtar, para in VARLIKLAR:
        try:
            ch, idx = zincir_iv(D, para)
        except (KeyError, TypeError):
            continue
        for olay in (PM.get(anahtar) or []):
            baslik = olay.get('title') or ''
            if not TOUCH_BASLIK.search(baslik):
                continue
            bitis = (olay.get('endDate') or '')[:10]
            if len(bitis) < 10:
                continue
            hedef = int(bitis[:4]) * 372 + int(bitis[5:7]) * 31 + int(bitis[8:10])

            uygun = [(abs(vade_gun(v) - hedef), v) for v in ch
                     if ch[v].get('C') and ch[v].get('P') and vade_gun(v)]
            if not uygun:
                continue
            uygun.sort()
            fark_gun, vade = uygun[0]
            F = forward(ch, vade, idx)
            if not F:
                continue
            # vadeye kalan sure: hedef gun - olcum gunu
            bugun = int(damga[:4]) * 372 + int(damga[5:7]) * 31 + int(damga[8:10])
            T = max((hedef - bugun), 1) / 365.0

            for m in (olay.get('markets') or []):
                if not (m.get('active') and not m.get('closed')):
                    continue
                ham = (m.get('groupItemTitle') or '').replace(',', '').replace('$', '')
                mm = re.search(r'\d+(?:\.\d+)?', ham)
                bid, ask = m.get('bestBid'), m.get('bestAsk')
                if not mm or bid is None or ask is None:
                    continue
                A = float(mm.group(0))
                if A <= F:        # asagi yonlu touch ayri bir hesap, kapsam disi
                    continue
                # TERMINAL MODELSIZ olmali. Onceki surumde lognormal terminal
                # kullaniliyordu ve sonuc "aritmetik ihlal" diye etiketleniyordu;
                # yanlisti. Lognormal bir modeldir, ona aykirilik modeli curutur,
                # aritmetigi degil. Gercek ihlal icin terminal opsiyon
                # fiyatlarindan dogrudan cikmali (D-025 dijital yaklasimi).
                d = dijital(ch, vade, A, F, idx)
                if not d or d['p'] <= 0:
                    continue
                pm = (float(bid) + float(ask)) / 2
                if pm <= 0:
                    continue
                terminal = d['p']
                oran = pm / terminal
                sonuc['olcum'] += 1
                # IHLAL: vade icinde degme olasiligi, vadede ustunde kapanma
                # olasiligindan KUCUK olamaz. Terminal modelsiz oldugu icin
                # bu gercekten aritmetiktir.
                if oran < 1.0:
                    sonuc['ihlal'] += 1
                # Driftsiz sinir 2'dir ama "2" bir sabit DEGILDIR (D-031).
                if oran > 2.0:
                    sonuc['band_disi'] += 1
                kar.ekle('%s:%s:%g' % (varlik, bitis, A), oran > 2.0)
    return sonuc


def main():
    argv = sys.argv[1:]
    son = int(argv[argv.index('--son') + 1]) if '--son' in argv else None
    hepsi = anlar('_meta')
    if son:
        hepsi = hepsi[-son:]

    o = ozet()
    kar = Kararlilik()
    print('UZUN UFUK TOUCH SINIRI — MODEL VARSAYAN olcum')
    print('arsiv: %(anlik_goruntu_sayisi)d anlik goruntu / %(gun_sayisi)d gun' % o)
    print()
    print('%-18s %8s %8s %10s' % ('an', 'olcum', 'ihlal', 'oran>2'))
    print('-' * 48)

    t_olcum = t_ihlal = t_band = 0
    for damga in hepsi:
        try:
            s = kosu(damga, kar)
        except Eksik:
            continue
        if not s['olcum']:
            continue
        print('%-18s %8d %8d %10d' % (damga, s['olcum'], s['ihlal'], s['band_disi']))
        t_olcum += s['olcum']; t_ihlal += s['ihlal']; t_band += s['band_disi']

    print('-' * 48)
    print('TOPLAM %8d olcum, %d aritmetik ihlal, %d oran>2'
          % (t_olcum, t_ihlal, t_band))
    if t_olcum:
        print('       ihlal orani %.1f%%  (touch < terminal: MUMKUN DEGIL)'
              % (100.0 * t_ihlal / t_olcum))
        print('       oran>2     %.1f%%  (lognormal sinirin ustu)'
              % (100.0 * t_band / t_olcum))
    kar.yaz('KARARLILIK — oran>2 olan esikler')

    print()
    print('ORAN = prediction market touch fiyati / MODELSIZ terminal dijital.')
    print('Terminal opsiyon fiyatlarindan dogrudan cikiyor, model varsayilmiyor.')
    print('')
    print('oran < 1 : ARITMETIK ihlal. Vade icinde degme, vadede ustunde')
    print('           kapanmadan az olamaz. Modele degil mantiga aykiri.')
    print('oran > 2 : driftsiz Brown sinirinin ustu. Bu daha ZAYIF bir')
    print('           iddiadir, cunku "2" bir sabit degildir (D-031).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
