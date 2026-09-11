#!/usr/bin/env python3
"""Kararlilik sayaci — tekrarlanan gozlemden sahte N uretmeyi engeller.

SORUN
"1030 / 3795 basamak bandi asti" cumlesi 3795 BAGIMSIZ gozlem varmis gibi
okunuyor. Yok. Ayni merdivenler 40 anlik goruntude tekrar tekrar olculuyor;
Kalshi tarafinda gercekte ~44 farkli basamak var, her biri ~35 kez gozlendi.
Oranin paydasini sismis bir N ile buyutmek, guveni hak edilmemis bicimde
artirir. Bu, D-051'in ("tek anlik goruntuden anlamlilik cikmaz") diger yuzu:
tekrarlanan anlik goruntuden de bagimsiz orneklem cikmaz.

DOGRU SORU
"Yuzde kaci asti" degil, "HANGI basamaklar, KAC gozlemin kacinda asti".
Bir basamak 35 gozlemin 35'inde bandi asiyorsa bu yapisal bir seydir.
18'inde asip 17'sinde asmiyorsa bu gurultudur. Ikisi ayni orana katkida
bulunur ama ayni sey degildir.

Bu modul her basamagi kimligiyle izler ve dagilimi raporlar.
"""
from collections import OrderedDict


class Kararlilik(object):
    def __init__(self):
        # anahtar -> [gozlem_sayisi, asan_sayi]
        self._g = OrderedDict()

    def ekle(self, anahtar, asiyor):
        s = self._g.setdefault(anahtar, [0, 0])
        s[0] += 1
        if asiyor:
            s[1] += 1

    def __len__(self):
        return len(self._g)

    def ozet(self, hep_esigi=0.9, hic_esigi=0.0):
        """Basamaklari davranislarina gore ayirir."""
        hep, bazen, hic = [], [], []
        for anahtar, (n, a) in self._g.items():
            oran = a / float(n) if n else 0.0
            if oran > hep_esigi:
                hep.append((anahtar, n, a))
            elif oran <= hic_esigi:
                hic.append((anahtar, n, a))
            else:
                bazen.append((anahtar, n, a))
        toplam_gozlem = sum(n for n, _ in self._g.values())
        toplam_asan = sum(a for _, a in self._g.values())
        return {
            'farkli_basamak': len(self._g),
            'toplam_gozlem': toplam_gozlem,
            'toplam_asan': toplam_asan,
            'hep': hep, 'bazen': bazen, 'hic': hic,
            'ort_gozlem': (toplam_gozlem / float(len(self._g))) if self._g else 0,
        }

    def yaz(self, baslik='KARARLILIK'):
        o = self.ozet()
        print()
        print(baslik)
        print('  farkli basamak     : %d' % o['farkli_basamak'])
        print('  toplam gozlem      : %d  (basamak basina ort. %.1f kez)'
              % (o['toplam_gozlem'], o['ort_gozlem']))
        print('  ---')
        print('  HER ZAMAN asan     : %d basamak' % len(o['hep']))
        print('  BAZEN asan         : %d basamak  <- gurultu suphesi' % len(o['bazen']))
        print('  HIC asmayan        : %d basamak' % len(o['hic']))
        if o['hep']:
            print('  ---')
            print('  her zaman asanlar (ilk 12):')
            for anahtar, n, a in o['hep'][:12]:
                print('    %-42s %d/%d gozlem' % (str(anahtar)[:42], a, n))
        print()
        print('  Okuma notu: oran degil, KARARLILIK anlamlidir. Ayni basamak her')
        print('  gozlemde bandi asiyorsa yapisal; gozlemlerin yarisinda asiyorsa')
        print('  gurultu. Ikisi ayni yuzdeye katkida bulunur ama ayni sey degildir.')
        return o
