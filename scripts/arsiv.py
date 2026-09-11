#!/usr/bin/env python3
"""Arsiv okuyucu — butun olcum betiklerinin ortak tabani.

Neden var: eski olcum betikleri `raw/_store.json` ve `inventory/*.csv`
okuyordu. Ikisi de repoda YOK (404). Yani betikler duruyordu ama hicbiri
calismiyordu; ekrandaki "0/44" ve "%13" gibi kayitli sayilarin repoda
yeniden uretilebilir bir yolu kalmamisti. Denetimde yakalandi.

Bu modul tek bir soruyu cozer: bir anlik goruntuyu diskten nasil okuruz.
Betikler artik veri toplamaz, yalnizca hesaplar. Ham veri degismez
(kural 2), dolayisiyla ayni anlik goruntu her zaman ayni sayiyi verir.

Kullanim:
    from arsiv import anlik_goruntu, gunler, anlar
    g = anlik_goruntu()                       # en yenisi
    g = anlik_goruntu('2026-09-10T1312Z')     # belirli bir an
    g.kalshi, g.deribit, g.polymarket         # cozulmus JSON
    g.damga, g.gun, g.meta                    # kimlik ve kosu bilgisi
"""
import gzip
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'raw')

AKISLAR = {
    'kalshi': 'kalshi',
    'deribit': 'deribit',
    'polymarket': 'polymarket_events',
}


class Eksik(Exception):
    """Istenen anlik goruntu ya da akis arsivde yok."""


def _gz(yol):
    with gzip.open(yol, 'rt', encoding='utf-8') as f:
        return json.load(f)


def gunler(akis='_meta'):
    """Arsivdeki gunler, eskiden yeniye."""
    p = os.path.join(RAW, AKISLAR.get(akis, akis))
    if not os.path.isdir(p):
        return []
    return sorted(d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d)))


def anlar(akis='_meta'):
    """Arsivdeki butun damgalar (kosu anlari), eskiden yeniye."""
    kok = os.path.join(RAW, AKISLAR.get(akis, akis))
    out = []
    for g in gunler(akis):
        for ad in sorted(os.listdir(os.path.join(kok, g))):
            # meta_2026-09-10T1312Z.json / kalshi_2026-09-10T1312Z.json.gz
            damga = ad.split('_', 1)[-1].split('.')[0]
            if damga:
                out.append(damga)
    return sorted(set(out))


class AnlikGoruntu(object):
    """Tek bir kosunun uc kaynagi. Alanlar ilk erisimde acilir."""

    def __init__(self, damga, gun):
        self.damga = damga
        self.gun = gun
        self._onbellek = {}

    def _oku(self, akis):
        if akis in self._onbellek:
            return self._onbellek[akis]
        klasor = AKISLAR[akis]
        yol = os.path.join(RAW, klasor, self.gun,
                           '%s_%s.json.gz' % (klasor, self.damga))
        if not os.path.isfile(yol):
            raise Eksik('%s akisi %s aninda yok: %s'
                        % (akis, self.damga, os.path.relpath(yol, ROOT)))
        self._onbellek[akis] = _gz(yol)
        return self._onbellek[akis]

    @property
    def kalshi(self):
        return self._oku('kalshi')

    @property
    def deribit(self):
        return self._oku('deribit')

    @property
    def polymarket(self):
        return self._oku('polymarket')

    @property
    def meta(self):
        if 'meta' not in self._onbellek:
            yol = os.path.join(RAW, '_meta', self.gun, 'meta_%s.json' % self.damga)
            if not os.path.isfile(yol):
                raise Eksik('meta yok: %s' % self.damga)
            with open(yol, encoding='utf-8') as f:
                self._onbellek['meta'] = json.load(f)
        return self._onbellek['meta']

    @property
    def pencere(self):
        """Kaynaklar arasi okuma kaymasi (saniye). Bu sayiden buyuk farklar
        piyasa gorusu degil olcum hatasi olabilir (D-015)."""
        return self.meta.get('fiyat_penceresi_saniye')

    def __repr__(self):
        return '<AnlikGoruntu %s>' % self.damga


def anlik_goruntu(damga=None):
    """Damga verilmezse en yeni kosu. Eksikse Eksik firlatir, tahmin etmez."""
    hepsi = anlar('_meta')
    if not hepsi:
        raise Eksik('arsiv bos: %s' % RAW)
    if damga is None:
        damga = hepsi[-1]
    elif damga not in hepsi:
        raise Eksik('%s arsivde yok. En yenisi: %s' % (damga, hepsi[-1]))
    gun = damga.split('T')[0]
    return AnlikGoruntu(damga, gun)


def ozet():
    """Arsivin durumu — betikler bunu basligina yazsin ki hangi veriyle
    olctugu ciktiyla birlikte gorunsun."""
    a = anlar('_meta')
    return {
        'gun_sayisi': len(gunler('_meta')),
        'anlik_goruntu_sayisi': len(a),
        'ilk': a[0] if a else None,
        'son': a[-1] if a else None,
    }


if __name__ == '__main__':
    # Duman testi: arsiv okunuyor mu, uc akis da aciliyor mu?
    o = ozet()
    print('arsiv: %(anlik_goruntu_sayisi)d anlik goruntu / %(gun_sayisi)d gun'
          '  (%(ilk)s .. %(son)s)' % o)
    g = anlik_goruntu()
    print('en yeni: %s' % g.damga)
    for ad in ('kalshi', 'deribit', 'polymarket'):
        try:
            v = getattr(g, ad)
            if isinstance(v, dict):
                bilgi = '%d ust alan: %s' % (len(v), ', '.join(list(v)[:5]))
            else:
                bilgi = '%d kayit' % len(v)
            print('  %-12s OK   %s' % (ad, bilgi))
        except Exception as e:
            print('  %-12s HATA %s' % (ad, e))
            raise
    print('  pencere      %.2f sn' % (g.pencere or -1))
    print('\narsiv okuma yolu calisiyor.')
