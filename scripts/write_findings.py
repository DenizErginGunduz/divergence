#!/usr/bin/env python3
"""Olcum sonuclarini findings/latest.json'a yazar.

NEDEN DOSYAYA YAZIYORUZ
1. Log okunmuyor. GitHub is akisi loglarini API'den cekmek yonetici yetkisi
   istiyor, arayuzdeki log gorunumu sanallastirilmis. Sonuc ortada duruyor
   ama erisilemiyor — yani pratikte yok.
2. Ekran buradan beslenecek. Sitedeki "kayitli olcum" kartlari bugune kadar
   elle yazilmisti ve hicbiri yeniden uretilemiyordu. Bundan sonra ayni
   dosyayi hem kayit hem ekran okuyacak; ikisi yapisal olarak ayrilamaz.
3. Tarih birikir. Her kosu bir onceki sonucu degistirirse, sayinin ne zaman
   ve hangi arsiv uzerinde uretildigi kaybolur. Dosya bunu tasiyor.

ONEMLI: bu betik OLCMUYOR, olcum modullerini CAGIRIYOR. Hesap tek yerde
durur; burada yalnizca toplama ve yazma vardir.
"""
import json
import os
import sys

from arsiv import anlar, ozet, Eksik
import measure_band
import measure_polymarket
import measure_touch
from kararlilik import Kararlilik

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def kararlilik_ozet(kar):
    o = kar.ozet()
    return {
        'farkli_basamak': o['farkli_basamak'],
        'toplam_gozlem': o['toplam_gozlem'],
        'basamak_basina_gozlem': round(o['ort_gozlem'], 1),
        'her_zaman_asan': len(o['hep']),
        'bazen_asan': len(o['bazen']),
        'hic_asmayan': len(o['hic']),
        'her_zaman_asanlar': [{'basamak': str(a), 'gozlem': n, 'asan': x}
                              for a, n, x in o['hep'][:20]],
    }


def band_olc(anlar_listesi):
    kar = Kararlilik()
    asan = olculen = 0
    yogunluk = []
    for d in anlar_listesi:
        try:
            s = measure_band.kosu(d, kar)
        except Eksik:
            continue
        for v in s['seriler'].values():
            if 'hata' in v:
                continue
            asan += v['asan']; olculen += v['olculen']
            yogunluk.append(v['yogunluk_toplami'])
    return {
        'asan': asan, 'olculen': olculen,
        'oran': round(100.0 * asan / olculen, 1) if olculen else None,
        'yogunluk_ort': round(sum(yogunluk) / len(yogunluk), 4) if yogunluk else None,
        'kararlilik': kararlilik_ozet(kar),
    }


def polymarket_olc(anlar_listesi):
    kar = Kararlilik()
    asan = olculen = 0
    dar_asan = dar_olculen = 0
    touch_elenen = 0
    for d in anlar_listesi:
        try:
            s = measure_polymarket.kosu(d)
        except Eksik:
            continue
        touch_elenen += s['elenen_touch']
        for h in s['merdivenler']:
            ol = [r for r in h['satirlar'] if 'opt' in r]
            if not ol:
                continue
            a = sum(1 for r in ol if r['asiyor'])
            asan += a; olculen += len(ol)
            if abs(h['bosluk_saat']) <= 12:
                dar_asan += a; dar_olculen += len(ol)
            for r in ol:
                kar.ekle('%s:%s:%g' % (h['varlik'], h['bitis'], r['K']), r['asiyor'])
    return {
        'asan': asan, 'olculen': olculen,
        'oran': round(100.0 * asan / olculen, 1) if olculen else None,
        'bosluk_12h_asan': dar_asan, 'bosluk_12h_olculen': dar_olculen,
        'bosluk_12h_oran': round(100.0 * dar_asan / dar_olculen, 1) if dar_olculen else None,
        'elenen_touch_merdiveni': touch_elenen,
        'kararlilik': kararlilik_ozet(kar),
    }


def touch_olc(anlar_listesi):
    kar = Kararlilik()
    olcum = ihlal = band_disi = 0
    for d in anlar_listesi:
        try:
            s = measure_touch.kosu(d, kar)
        except Eksik:
            continue
        olcum += s['olcum']; ihlal += s['ihlal']; band_disi += s['band_disi']
    return {
        'olcum': olcum, 'aritmetik_ihlal': ihlal, 'oran_2_ustu': band_disi,
        'ihlal_orani': round(100.0 * ihlal / olcum, 1) if olcum else None,
        'oran_2_ustu_orani': round(100.0 * band_disi / olcum, 1) if olcum else None,
        'kararlilik': kararlilik_ozet(kar),
        'not': ('Terminal MODELSIZ dijitalden geliyor. "oran>2" driftsiz Brown '
                'sinirinin ustu demek; "2" bir sabit degildir (D-031), bu yuzden '
                'zayif bir iddiadir. "oran<1" ise aritmetik ihlaldir.'),
    }


def main():
    hepsi = anlar('_meta')
    o = ozet()
    print('olcum basliyor: %d anlik goruntu' % len(hepsi))

    sonuc = {
        'arsiv': o,
        'uretildi': 'scripts/write_findings.py',
        'olcumler': {
            'surtunme_bandi_kalshi': band_olc(hepsi),
            'polymarket_terminal': polymarket_olc(hepsi),
            'uzun_ufuk_touch': touch_olc(hepsi),
        },
    }

    hedef = os.path.join(ROOT, 'findings')
    os.makedirs(hedef, exist_ok=True)
    yol = os.path.join(hedef, 'latest.json')
    with open(yol, 'w', encoding='utf-8') as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=1)

    print('yazildi: findings/latest.json')
    for ad, m in sonuc['olcumler'].items():
        k = m.get('kararlilik', {})
        print('  %-26s farkli basamak %-4s her zaman asan %-4s'
              % (ad, k.get('farkli_basamak'), k.get('her_zaman_asan')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
