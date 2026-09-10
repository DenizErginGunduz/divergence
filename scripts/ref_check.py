#!/usr/bin/env python3
"""Karar referansi denetleyicisi.

Neden var: arayuzdeki bulgu kartlari "D-049", "D-045 · D-046 · D-066" gibi
karar numaralari basiyordu, ama o kararlar DECISIONS.md'ye hic yazilmamisti.
Yani ekran, var olmayan kayitlara atif yapiyordu. Bunu bir insan fark etti,
kod degil. Olcum titizligi iddia eden bir projede en kotu turden acik.

Ne yapar:
  1. Repodaki metin dosyalarini tarar, D-\\d{3} bicimindeki her atifi toplar.
  2. DECISIONS.md'deki "## D-XXX" basliklarini tanimli kabul eder.
  3. Tanimi olmayan atif varsa HATA verir (cikis 1).
  4. Tanimli ama "KAYIT KAYIP" isaretli olanlari ayrica sayar ve listeler;
     bunlar hata degil, kapatilmayi bekleyen borctur.

Kullanim:
    python scripts/ref_check.py            # denetle
    python scripts/ref_check.py --liste    # her atifin nerede gectigini de yaz
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KARAR_DOSYASI = os.path.join('docs', 'DECISIONS.md')

# Ham arsiv taranmaz: orada karar atifi olmaz, dosyalar buyuk ve degismezdir.
ATLA_KLASOR = {'.git', 'raw', 'state', '__pycache__', 'node_modules'}
TARA_UZANTI = {'.md', '.py', '.html', '.yml', '.yaml', '.json', '.txt', '.js', '.css'}

ATIF = re.compile(r'\bD-(\d{3})\b')
TANIM = re.compile(r'^##\s+(D-\d{3})', re.MULTILINE)
KAYIP = re.compile(r'^##\s+(D-\d{3})\s+—\s+KAYIT KAYIP', re.MULTILINE)


def dosyalar():
    for kok, klasorler, adlar in os.walk(ROOT):
        klasorler[:] = [k for k in klasorler if k not in ATLA_KLASOR]
        for ad in adlar:
            if os.path.splitext(ad)[1].lower() in TARA_UZANTI:
                tam = os.path.join(kok, ad)
                yield tam, os.path.relpath(tam, ROOT).replace(os.sep, '/')


def kendi_testi():
    """Denetleyicinin gercekten HATA verebildigini kanitlar.

    Yesil kalan ama hicbir seyi yakalamayan bir denetleyici, denetleyici degildir.
    CI'da once bu kosar: yakalama yetenegi kanitlanmadan asil denetim anlamsiz.
    """
    # Ornek numaralar PARCALI kuruluyor: kaynakta duz bir numara yazsaydi
    # denetleyici kendi test verisini gercek bir atif sanip kendini kirardi.
    # Tam olarak bu oldu — ilk surum CI'da patladi. Aracin calistiginin kaniti,
    # ama test verisi uretim verisine benzememeli.
    P = 'D-'
    ornek_karar = ('## %s001 — gercek karar\n'
                   '## %s002 — KAYIT KAYIP\n'
                   'govde metni\n') % (P, P)
    ornek_metin = 'burada %s001, %s002 ve tanimsiz %s999 aniliyor\n' % (P, P, P)

    tanimli = set(TANIM.findall(ornek_karar))
    kayip = set(KAYIP.findall(ornek_karar))
    atif = {P + m.group(1) for m in ATIF.finditer(ornek_metin)}
    asili = sorted(a for a in atif if a not in tanimli)

    sorun = []
    if tanimli != {P + '001', P + '002'}:
        sorun.append('tanim taninmadi: %s' % sorted(tanimli))
    if kayip != {P + '002'}:
        sorun.append('KAYIT KAYIP taninmadi: %s' % sorted(kayip))
    if atif != {P + '001', P + '002', P + '999'}:
        sorun.append('atif taranmadi: %s' % sorted(atif))
    if asili != [P + '999']:
        sorun.append('asili referans YAKALANMADI: %s' % asili)

    if sorun:
        print('KENDI TESTI BASARISIZ:')
        for s in sorun:
            print('  - %s' % s)
        return 1
    print('kendi testi: gecti (asili referans yakalaniyor, KAYIT KAYIP ayirt ediliyor)')
    return 0


def main():
    ayrinti = '--liste' in sys.argv
    if '--kendi-testi' in sys.argv:
        return kendi_testi()

    kp = os.path.join(ROOT, KARAR_DOSYASI)
    if not os.path.isfile(kp):
        print('HATA: %s bulunamadi' % KARAR_DOSYASI)
        return 1
    kararlar = open(kp, encoding='utf-8').read()
    tanimli = set(TANIM.findall(kararlar))
    kayip = set(KAYIP.findall(kararlar))

    nerede = {}
    for tam, rel in dosyalar():
        try:
            metin = open(tam, encoding='utf-8').read()
        except (UnicodeDecodeError, OSError):
            continue
        for m in ATIF.finditer(metin):
            no = 'D-' + m.group(1)
            nerede.setdefault(no, set()).add(rel)

    asili = sorted(n for n in nerede if n not in tanimli)
    kullanilan_kayip = sorted(n for n in nerede if n in kayip)

    taranan = sum(1 for _ in dosyalar())
    print('taranan dosya   : %d' % taranan)
    print('tanimli karar   : %d' % len(tanimli))
    print('atif yapilan    : %d' % len(nerede))

    # Bos tarama sessizce yesil kalmasin: yol yanlissa denetim hicbir sey demiyordur.
    if taranan < 5 or not tanimli:
        print('\nHATA: tarama bos dondu (dosya=%d, tanim=%d). ROOT yanlis olabilir: %s'
              % (taranan, len(tanimli), ROOT))
        return 1

    if ayrinti:
        for no in sorted(nerede):
            im = ' [KAYIT KAYIP]' if no in kayip else ''
            print('  %s%s  <- %s' % (no, im, ', '.join(sorted(nerede[no]))))

    if kullanilan_kayip:
        print('\nKAYIT KAYIP ama anilan (%d) — borc, hata degil:' % len(kullanilan_kayip))
        for no in kullanilan_kayip:
            print('  %-7s <- %s' % (no, ', '.join(sorted(nerede[no]))))

    if asili:
        print('\nASILI REFERANS (%d) — tanimi yok:' % len(asili))
        for no in asili:
            print('  %-7s <- %s' % (no, ', '.join(sorted(nerede[no]))))
        print('\nKarar yazilmadan numara anilmaz. DECISIONS.md\'ye ya gercek kayit')
        print('ya da "## %s — KAYIT KAYIP" yer tutucusu eklenmeli.' % asili[0])
        return 1

    print('\nasili referans yok.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
