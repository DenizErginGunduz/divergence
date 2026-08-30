#!/usr/bin/env python3
"""
layer1_consistency.py — KATMAN 1 IC TUTARLILIK TESTI

Soru: Kova (range) merdiveninden cikardigimiz ayrik yogunlugun kumulatifi,
AYNI VADEDEKI terminal esik merdiveninin fiyatlarini veriyor mu?

Iki merdiven ayni olayi iki farkli sekilde fiyatliyor:
  - range   : P(K_i < S_T <= K_{i+1})     -> yogunluk, dogrudan
  - terminal: P(S_T > K)                  -> kumulatif hayatta kalma fonksiyonu
Ozdeslik:  P(S_T > K_j) = toplam_{i >= j} P(kova_i)

Tutuyorsa: merdiven->yogunluk motoru calisiyor, siniflandirmam dogru.
Tutmuyorsa: ya siniflandirma yanlis, ya piyasada tutarsizlik var, ya veri bayat.
Ucunu ayirt etmek icin sapmanin BUYUKLUGU ve ISARETI okunur.

Dis veri kaynagi GEREKTIRMEZ. Yalnizca raw/_store.json kullanir.
"""
import json, os, sys, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(BASE, 'raw', '_store.json')


def mid(m):
    """Orta fiyat. Tek tarafli kitapta karsi taraf yoksa outcomePrices'a duser."""
    bb, ba = m.get('bestBid'), m.get('bestAsk')
    if isinstance(bb, (int, float)) and isinstance(ba, (int, float)):
        return (bb + ba) / 2.0, 'bid/ask ortasi'
    try:
        return float(json.loads(m['outcomePrices'])[0]), 'outcomePrices (tek tarafli kitap)'
    except Exception:
        return None, 'YOK'


def num(s):
    return float(str(s).replace(',', '').replace('$', '').strip())


def collect(store, above_pat, range_pat, expiry):
    above, rng = {}, []
    for m in store['markets'].values():
        sl = m.get('slug') or ''
        if m.get('endDateIso') != expiry:
            continue
        gt = (m.get('groupItemTitle') or '').strip()
        p, src = mid(m)
        if p is None:
            continue
        if above_pat in sl:
            above[num(gt)] = (p, src, (m.get('updatedAt') or '')[11:19])
        elif range_pat in sl:
            if gt.startswith('>'):
                lo, hi = num(gt[1:]), float('inf')
            elif gt.startswith('<'):
                lo, hi = 0.0, num(gt[1:])
            elif '-' in gt:
                a, b = gt.split('-'); lo, hi = num(a), num(b)
            else:
                continue
            rng.append({'lo': lo, 'hi': hi, 'p': p, 'src': src,
                        'upd': (m.get('updatedAt') or '')[11:19], 'label': gt})
    rng.sort(key=lambda x: x['lo'])
    return above, rng


def run(asset, above_pat, range_pat, expiry):
    store = json.load(open(STORE, encoding='utf-8'))
    above, rng = collect(store, above_pat, range_pat, expiry)
    if not above or not rng:
        print('%s: veri yok (above=%d, range=%d)' % (asset, len(above), len(rng)))
        return None

    print('\n' + '=' * 76)
    print('KATMAN 1 — %s, vade %s' % (asset, expiry))
    print('=' * 76)

    ts = sorted({v[2] for v in above.values()} | {r['upd'] for r in rng})
    print('Snapshot damgalari: %s  (yayilma bu testin hata payinin bir parcasi)'
          % ', '.join(ts))

    tot = sum(r['p'] for r in rng)
    print('\nKova toplami = %.4f   (arbitrajsizlik: 1.0 olmali; fazlasi makas/yuvarlama)'
          % tot)
    covered_lo = min(r['lo'] for r in rng)
    has_low_tail = any(r['lo'] == 0.0 for r in rng)
    if not has_low_tail:
        print('UYARI: alt kuyruk kovasi (<%g) yok. Merdiven TUKENMIS DEGIL.' % covered_lo)
        print('       Kumulatif bu seviyenin altinda anlamsizdir.')

    # Kumulatif: P(S_T > K) = K ve ustundeki kovalarin toplami
    print('\n%-9s %-12s %-12s %-10s %-10s %s' %
          ('ESIK', 'KOVA->KUM.', 'TERMINAL', 'FARK', 'NORM.FARK', 'YORUM'))
    print('-' * 76)
    rows = []
    for K in sorted(above.keys(), reverse=True):
        cum = sum(r['p'] for r in rng if r['lo'] >= K - 1e-9)
        term, src, _ = above[K]
        d = cum - term
        dn = (cum / tot) - term          # kova seti 1'e normalize edilirse
        flag = ''
        if abs(d) > 0.05:
            flag = 'BUYUK SAPMA'
        elif abs(d) > 0.02:
            flag = 'dikkat'
        if not has_low_tail and K <= covered_lo:
            flag = (flag + ' | alt kuyruk eksik').strip(' |')
        print('%-9g %-12.4f %-12.4f %-+10.4f %-+10.4f %s' % (K, cum, term, d, dn, flag))
        rows.append({'strike': K, 'kova_kumulatif': round(cum, 6),
                     'terminal': round(term, 6), 'fark': round(d, 6),
                     'normalize_fark': round(dn, 6), 'terminal_kaynak': src})

    va = [abs(r['fark']) for r in rows]
    vn = [abs(r['normalize_fark']) for r in rows]
    print('-' * 76)
    print('Ortalama |fark| = %.4f   |  normalize sonrasi = %.4f' %
          (sum(va) / len(va), sum(vn) / len(vn)))
    print('En buyuk |fark| = %.4f  |  normalize sonrasi = %.4f' % (max(va), max(vn)))
    return {'asset': asset, 'expiry': expiry, 'kova_toplami': round(tot, 6),
            'alt_kuyruk_var': has_low_tail, 'snapshot_damgalari': ts,
            'ortalama_mutlak_fark': round(sum(va) / len(va), 6),
            'normalize_ortalama_mutlak_fark': round(sum(vn) / len(vn), 6),
            'satirlar': rows}


if __name__ == '__main__':
    out = []
    for args in [('ETH', 'ethereum-above-', 'the-price-of-ethereum-be', '2026-08-06'),
                 ('BTC', 'bitcoin-above-', 'the-price-of-bitcoin-be', '2026-08-06')]:
        r = run(*args)
        if r:
            out.append(r)
    p = os.path.join(BASE, 'inventory', 'layer1_results.json')
    json.dump({'uretim_zamani_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'sonuclar': out}, open(p, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\nYazildi: %s' % p)
    print("""
NASIL OKUNUR
  fark ~ 0            -> motor calisiyor, siniflandirma dogru.
  fark hep POZITIF    -> kova seti 1'in ustunde toplaniyor; makas/yuvarlama.
                         "normalize fark" sutunu bunu duzeltir.
  tek bir esikte buyuk sapma -> once o kontratin kural metnini oku,
                         siniflandirma hatasi ihtimali piyasa tutarsizligindan yuksek.
  alt kuyruk eksikse  -> o seviyenin altindaki kumulatif ANLAMSIZDIR, okuma.
""")
