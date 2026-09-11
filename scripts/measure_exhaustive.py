#!/usr/bin/env python3
"""Tuketicilik kisiti — kova sinirini yanlis kurarsan ne oluyor?

KISIT
Bir kova merdiveni tum sonuc uzayini bolusuyorsa, kovalarin olasiliklari
toplami 1 olmak ZORUNDADIR. Bu bir tercih degil, aritmetik. Dolayisiyla
toplam 1'den sapiyorsa hesapta hata var — hangi kovanin yanlis oldugunu
soylemese bile, yanlis oldugunu soyler.

NEDEN ONEMLI
Bu projede yakalanan hatalarin cogunu sayilar degil KISITLAR yakaladi.
Kova siniri hatasinda dijitallerin her biri tek tek makul gorunuyordu;
yalnizca toplamin 1 olmasi gerektigi kurali hatayi gorunur kildi.

BU BETIK NE YAPAR
Ayni veriyi uc farkli sinir kuraliyla hesaplar ve her birinin toplamini
raporlar. Hangi kuralin dogru oldugunu iddia etmez — toplamlar soyler.

  duzeltilmis : hi = round(cap + 0.01)     <- bugun kullanilan
  naif_a      : hi = round(cap)            <- epsilon hic yok
  naif_b      : hi = round(cap) + 0.01     <- epsilon yuvarlamanin DISINDA

Fark neden onemli: cap 24999.99 ise round(24999.99 + 0.01) = 25000, ama
round(24999.99) + 0.01 = 25000.01. Bir sonraki kovanin tabani 25000.
Dijital, K'yi saran strike'lari KESIN esitsizlikle sectigi icin 25000.01
ile 25000 ayni sinir icin FARKLI strike ciftleri secebiliyor. O zaman bir
bolge iki kez sayiliyor ve toplam 1'i asiyor.

DURUSTLUK NOTU
Hatanin tarihsel bicimi bir ozetten yeniden kuruldu. Bu betik "toplam
su kadardi" diye iddia etmiyor; uc kurali da olcup sonucu gosteriyor.
Olcum neyi soyluyorsa o yazilir.

Kullanim:
    python scripts/measure_exhaustive.py
    python scripts/measure_exhaustive.py --son 5
"""
import sys

from arsiv import anlik_goruntu, anlar, ozet, Eksik
from measure_band import SERILER, zincir, forward, dijital, van

KURALLAR = ('duzeltilmis', 'naif_a', 'naif_b')


def sinirlar(m, kural):
    """Bir Kalshi kovasinin alt/ust esigi, secilen sinir kuralina gore."""
    tip = m.get('strike_type')
    if tip == 'less':
        cap = m['cap_strike']
        if kural == 'duzeltilmis':
            return None, round(cap)
        if kural == 'naif_a':
            return None, round(cap)
        return None, round(cap)
    if tip == 'greater':
        fl = m['floor_strike']
        if kural == 'duzeltilmis':
            return round(fl + .01), None
        if kural == 'naif_a':
            return round(fl), None
        return round(fl) + .01, None
    fl, cap = m['floor_strike'], m['cap_strike']
    if kural == 'duzeltilmis':
        return round(fl), round(cap + .01)
    if kural == 'naif_a':
        return round(fl), round(cap)
    return round(fl), round(cap) + .01


def toplam(KA, D, seri, para, kural):
    """Bir merdivenin kova olasiliklari toplami, verilen sinir kuraliyla."""
    M = [m for m in (KA.get('marketler', {}).get(seri) or [])
         if m.get('status') == 'active']
    if not M:
        return None
    ch, idx = zincir(D, para)
    kapanis = M[0].get('close_time', '')
    uygun = [v for v in ch if ch[v].get('C') and ch[v].get('P') and van(v)]
    if not uygun:
        return None
    uygun.sort(key=van)
    hedef = int(kapanis[:4] + kapanis[5:7] + kapanis[8:10]) if len(kapanis) >= 10 else None
    alt = [v for v in uygun if hedef is None or van(v) <= hedef]
    if not alt:
        return None
    vade = alt[-1]
    F = forward(ch, vade, idx)
    if not F:
        return None

    t = 0.0
    sayi = 0
    for m in M:
        lo, hi = sinirlar(m, kural)
        dL = dijital(ch, vade, lo, F, idx) if lo is not None else {'p': 1}
        dH = dijital(ch, vade, hi, F, idx) if hi is not None else {'p': 0}
        if not dL or not dH:
            continue
        t += dL['p'] - dH['p']
        sayi += 1
    return {'toplam': t, 'kova': sayi}


def main():
    argv = sys.argv[1:]
    son = int(argv[argv.index('--son') + 1]) if '--son' in argv else None
    hepsi = anlar('_meta')
    if son:
        hepsi = hepsi[-son:]

    o = ozet()
    print('TUKETICILIK KISITI — kova siniri kurali ve toplamin 1\'den sapmasi')
    print('arsiv: %(anlik_goruntu_sayisi)d anlik goruntu / %(gun_sayisi)d gun' % o)
    print()
    print('%-18s %-5s %10s %10s %10s' % ('an', 'seri', 'duzeltilmis', 'naif_a', 'naif_b'))
    print('-' * 60)

    birikim = {k: [] for k in KURALLAR}
    for damga in hepsi:
        try:
            g = anlik_goruntu(damga)
            KA, D = g.kalshi, g.deribit
        except Eksik:
            continue
        for varlik, seri, para in SERILER:
            satir = []
            for kural in KURALLAR:
                try:
                    r = toplam(KA, D, seri, para, kural)
                except (KeyError, TypeError, ValueError):
                    r = None
                if r:
                    satir.append(r['toplam'])
                    birikim[kural].append(r['toplam'])
                else:
                    satir.append(None)
            if any(x is not None for x in satir):
                print('%-18s %-5s %10s %10s %10s' % (
                    damga, varlik,
                    *['%.4f' % x if x is not None else '—' for x in satir]))

    print('-' * 60)
    print()
    print('%-14s %8s %10s %10s %10s' % ('kural', 'olcum', 'ortalama', 'en dusuk', 'en yuksek'))
    for kural in KURALLAR:
        v = birikim[kural]
        if not v:
            print('%-14s %8s' % (kural, 'yok'))
            continue
        ort = sum(v) / len(v)
        print('%-14s %8d %10.4f %10.4f %10.4f'
              % (kural, len(v), ort, min(v), max(v)))
        sapma = 100.0 * (ort - 1.0)
        print('%-14s %8s 1\'den sapma: %+.1f%%' % ('', '', sapma))

    print()
    print('Okuma notu: toplam 1\'den ne kadar saparsa, o sinir kurali o kadar')
    print('yanlis. Hangi kovanin bozuk oldugunu bu kisit soylemez — yalnizca')
    print('bir yerde bozukluk OLDUGUNU soyler. Hatayi yakalayan da tam olarak')
    print('buydu: dijitaller tek tek kusursuz gorunuyordu.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
