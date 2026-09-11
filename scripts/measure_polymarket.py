#!/usr/bin/env python3
"""Polymarket kisa vadeli terminal merdivenleri — ucuncu bagimsiz kurulum.

NEDEN AYRI BIR OLCUM
Ayni sekli (prediction market'in olasi olmayan sonucu opsiyondan zengin
fiyatlamasi) uc farkli kurulumda gormek, tek kurulumda gormekten cok daha
guclu. Kalshi yil sonu kovalari ve uzun ufuk touch siniri olculdu; bu betik
ucuncusunu, Polymarket gunluk esik merdivenlerini olcuyor.

TOUCH / TERMINAL AYRIMI — BU BETIGIN EN HASSAS NOKTASI
Polymarket'te iki farkli soru tipi ic ice duruyor:

  "What price will Bitcoin hit in September?"     -> TOUCH  (yol bagimli)
  "Bitcoin above ___ on September 11?"            -> TERMINAL
  "Bitcoin price on September 11?"                -> TERMINAL (kova)

"hit" kelimesi vade icinde HERHANGI BIR AN degmeyi sorar. Touch olasiligi
ayni seviyedeki terminal olasiligindan her zaman buyuk veya ona esittir.
Ikisini karistirmak butun hesabi sistematik olarak bozar. Bu betik touch
merdivenlerini ACIKCA disarida birakir ve kac tanesini eledigini raporlar.

VADE VE COZUNURLUK BOSLUGU — GIZLENMIYOR
Polymarket gunluk merdivenler 16:00 UTC'de, Binance BTC/USDT 1 dakikalik
mum kapanisiyla cozuluyor. Deribit opsiyonlari 08:00 UTC'de, Deribit
endeksiyle. Yani:

  - zaman boslugu : opsiyon vadesi tipik olarak 8 saat ONCE
  - kaynak farki  : Binance spot vs Deribit endeksi

Opsiyon vadesi daha erken oldugu icin opsiyonun ima ettigi dagilim daha
DAR olur; dijitaller 0 ve 1'e olduklarindan daha yakin cikar. Bu, farki
bizim lehimize sisirebilecek bir sapmadir. O yuzden her satirda boslugun
kac saat oldugu yaziliyor ve ozet, boslugun buyuklugune gore ayriliyor.

Kullanim:
    python scripts/measure_polymarket.py
    python scripts/measure_polymarket.py --son 5
"""
import re
import sys

from arsiv import anlik_goruntu, anlar, ozet, Eksik
from measure_band import zincir, forward, dijital, AY
from kararlilik import Kararlilik

VARLIKLAR = [('BTC', 'bitcoin', 'BTC'), ('ETH', 'ethereum', 'ETH')]

# "Bitcoin above ___ on September 11?" -> terminal esik merdiveni
TERMINAL = re.compile(r'^(Bitcoin|Ethereum) above ___ on ', re.I)
# "What price will Bitcoin hit in 2026?" -> TOUCH, karsilastirilmaz
TOUCH = re.compile(r'\bhit\b', re.I)

VADE_ET = re.compile(r'^(\d+)([A-Z]{3})(\d{2})$')


def vade_saat(etiket):
    """Deribit vade etiketi -> (yil, ay, gun). Vadeler 08:00 UTC'de kapanir."""
    m = VADE_ET.match(etiket)
    if not m:
        return None
    return (2000 + int(m.group(3)), AY[m.group(2)], int(m.group(1)))


def _gun_sayisi(y, ay, g):
    """Kaba gun sayaci — yalnizca FARK almak icin, takvim dogrulugu gerekmez."""
    return y * 372 + ay * 31 + g


def esik_coz(market):
    """groupItemTitle'dan sayisal esik. '70,000' -> 70000.0"""
    ham = (market.get('groupItemTitle') or '').replace(',', '').replace('$', '').strip()
    m = re.search(r'\d+(?:\.\d+)?', ham)
    if not m:
        return None
    return float(m.group(0))


def merdiven(olay, ch, idx):
    """Bir Polymarket terminal merdiveninin butun basamaklari."""
    M = [m for m in (olay.get('markets') or []) if m.get('active') and not m.get('closed')]
    if len(M) < 3:
        return None

    bitis = (olay.get('endDate') or '')[:10]
    if len(bitis) < 10:
        return None
    hy, hay, hg = int(bitis[:4]), int(bitis[5:7]), int(bitis[8:10])
    hedef = _gun_sayisi(hy, hay, hg)

    # Boslugu EN KUCUK olan vade secilir; yonu ve buyuklugu raporlanir.
    uygun = []
    for v in ch:
        if not (ch[v].get('C') and ch[v].get('P')):
            continue
        vs = vade_saat(v)
        if not vs:
            continue
        uygun.append((abs(_gun_sayisi(*vs) - hedef), _gun_sayisi(*vs) - hedef, v))
    if not uygun:
        return None
    uygun.sort()
    _, gun_farki, vade = uygun[0]
    # Polymarket 16:00 UTC, Deribit 08:00 UTC -> ayni gun ise opsiyon 8 saat once
    saat_boslugu = gun_farki * 24 - 8

    F = forward(ch, vade, idx)
    if not F:
        return None

    satirlar = []
    for m in M:
        K = esik_coz(m)
        if K is None:
            continue
        bid, ask = m.get('bestBid'), m.get('bestAsk')
        if bid is None or ask is None:
            continue
        d = dijital(ch, vade, K, F, idx)
        if not d:
            satirlar.append({'K': K, 'sessiz': 'strike araligi disinda'})
            continue
        pm = (float(bid) + float(ask)) / 2
        mk = float(ask) - float(bid)
        # Polymarket maker ucreti 0 kabul ediliyor (kullanici karari).
        surt = d['fee'] + mk / 2
        esik = (0 if d['se'] is None else 1.96 * d['se']) + surt
        satirlar.append({'K': K, 'pm': pm, 'opt': d['p'], 'fark': pm - d['p'],
                         'esik': esik, 'mk': mk,
                         'asiyor': abs(pm - d['p']) > esik})
    if not satirlar:
        return None
    return {'satirlar': satirlar, 'vade': vade, 'bosluk_saat': saat_boslugu,
            'baslik': olay.get('title'), 'bitis': bitis}


def kosu(damga):
    g = anlik_goruntu(damga)
    PM, D = g.polymarket, g.deribit
    cikti = {'damga': damga, 'merdivenler': [], 'elenen_touch': 0}
    for varlik, anahtar, para in VARLIKLAR:
        try:
            ch, idx = zincir(D, para)
        except (KeyError, TypeError):
            continue
        for olay in (PM.get(anahtar) or []):
            baslik = olay.get('title') or ''
            if TOUCH.search(baslik):
                cikti['elenen_touch'] += 1
                continue
            if not TERMINAL.match(baslik):
                continue
            try:
                h = merdiven(olay, ch, idx)
            except (KeyError, TypeError, ValueError):
                continue
            if h:
                h['varlik'] = varlik
                cikti['merdivenler'].append(h)
    return cikti


def main():
    argv = sys.argv[1:]
    son = int(argv[argv.index('--son') + 1]) if '--son' in argv else None
    hepsi = anlar('_meta')
    if son:
        hepsi = hepsi[-son:]

    o = ozet()
    kar = Kararlilik()
    print('POLYMARKET TERMINAL MERDIVENLERI — ucuncu bagimsiz kurulum')
    print('arsiv: %(anlik_goruntu_sayisi)d anlik goruntu / %(gun_sayisi)d gun' % o)
    print()
    print('%-18s %-4s %-30s %5s %6s %s' %
          ('an', 'var', 'merdiven', 'bosl', 'asan', '(asan/olculen)'))
    print('-' * 86)

    top_asan = top_olculen = 0
    dar_asan = dar_olculen = 0      # bosluk <= 12 saat olanlar
    touch_elenen = 0
    gosterilen = 0

    for damga in hepsi:
        try:
            s = kosu(damga)
        except Eksik:
            continue
        touch_elenen += s['elenen_touch']
        for h in s['merdivenler']:
            olculen = [r for r in h['satirlar'] if 'opt' in r]
            if not olculen:
                continue
            asan = sum(1 for r in olculen if r['asiyor'])
            for r in olculen:
                # kimlik: varlik + merdivenin vadesi + esik. Gunluk merdivenler
                # her gun yenilendigi icin cogu basamak az sayida gozlenir;
                # kararlilik ozeti bunu oldugu gibi gosterir.
                kar.ekle('%s:%s:%g' % (h['varlik'], h['bitis'], r['K']), r['asiyor'])
            top_asan += asan
            top_olculen += len(olculen)
            if abs(h['bosluk_saat']) <= 12:
                dar_asan += asan
                dar_olculen += len(olculen)
            if gosterilen < 24:      # log'u bogmadan ornek goster
                print('%-18s %-4s %-30s %+5dh %6s %d/%d' %
                      (damga, h['varlik'], (h['baslik'] or '')[:30],
                       h['bosluk_saat'], '', asan, len(olculen)))
                gosterilen += 1

    print('-' * 86)
    print()
    print('TOPLAM     : %d / %d basamak-gozlemi bandi asti' % (top_asan, top_olculen))
    if top_olculen:
        print('             %.1f%%' % (100.0 * top_asan / top_olculen))
    print('BOSLUK<=12h: %d / %d' % (dar_asan, dar_olculen))
    if dar_olculen:
        print('             %.1f%%  <- vade boslugu kucukken de ayni mi?'
              % (100.0 * dar_asan / dar_olculen))
    kar.yaz('KARARLILIK — Polymarket gunluk esikleri')
    print()
    print('elenen touch merdiveni: %d  ("hit" sorulari terminal DEGILDIR)' % touch_elenen)
    print()
    print('CEKINCE: Polymarket 16:00 UTC / Binance BTC-USDT kapanisi ile,')
    print('Deribit 08:00 UTC / Deribit endeksi ile cozuluyor. Hem zaman hem')
    print('kaynak farki var. Opsiyon vadesi daha erken oldugundan dagilim')
    print('daha dar cikar ve fark BIZIM LEHIMIZE sisebilir. Bu sayi bir')
    print('firsat sayisi degil, bir karsilastirilabilirlik olcusudur.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
