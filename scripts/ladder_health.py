#!/usr/bin/env python3
"""
ladder_health.py — MERDIVEN SAGLIK KONTROLU (dis veri gerektirmez)

Opsiyon verisine gecmeden ONCE calistirilmasi gereken kontrol. Uc soru sorar:

1) MAKAS / OLCUM ORANI
   Olcecegimiz fark birkac puan. Alis-satis makasi ondan buyukse, uretilen sayi
   piyasa gorusu degil makasin kendisidir. Esik: makas > 0.02 ise "olculemez".

2) MONOTONLUK  (model icermeyen veri kalitesi testi)
   Ayni merdivende esik yukseldikce touch olasiligi DUSMELI (yukari yon),
   esik dustukce DUSMELI (asagi yon). Ihlal varsa ya kotasyon bozuk ya kayit yanlis.

3) COZULMUS OLABILIR
   mid >= 0.99 olan touch kontrati muhtemelen zaten gerceklesmis; `closed` bayragi
   donmemis olabilir. Bunlar merdivenden cikarilmali, yoksa basamak bozuk kalir.
   (Kullanicinin BTC 62.500 hipotezi — D-020.)
"""
import json, os, re, statistics

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
store = json.load(open(os.path.join(BASE, 'raw', '_store.json'), encoding='utf-8'))

MAKAS_ESIK = 0.02      # bunun ustu: fark olculemez
COZULMUS_ESIK = 0.99   # bunun ustu: muhtemelen gerceklesmis

TICK = {'tsla': 'TSLA', 'nvda': 'NVDA', 'meta': 'META', 'spy': 'SPY',
        'aapl': 'AAPL', 'bitcoin': 'BTC'}


def ladders():
    out = {}
    for ev in store['events'].values():
        m = re.match(r'what-price-will-(\w+)-hit-in-august-2026', ev.get('slug') or '')
        if not m:
            continue
        t = TICK.get(m.group(1), m.group(1).upper())
        rungs = []
        for x in (ev.get('markets') or []):
            gt = x.get('groupItemTitle') or ''
            n = re.findall(r'([\d,\.]+)', gt.replace('$', ''))
            if not n:
                continue
            bb, ba = x.get('bestBid'), x.get('bestAsk')
            if not (isinstance(bb, (int, float)) and isinstance(ba, (int, float))):
                continue
            rungs.append({'K': float(n[0].replace(',', '')),
                          'dir': 'up' if '↑' in gt else 'down',
                          'mid': (bb + ba) / 2, 'spread': ba - bb,
                          'vol': x.get('volumeNum') or 0})
        if rungs:
            out[t] = rungs
    return out


print('=' * 94)
print('MERDIVEN SAGLIK KONTROLU — opsiyon verisine gecmeden once')
print('=' * 94)
print('%-6s %5s %9s %9s %9s %8s %9s %s'
      % ('VARLIK', 'basam', 'medyan', 'ortalama', 'en genis', 'olcule', 'cozulmus', 'monoton'))
print('%-6s %5s %9s %9s %9s %8s %9s %s'
      % ('', '', 'makas', 'makas', 'makas', 'bilir', 'olabilir', 'ihlali'))
print('-' * 94)

report = {}
for t, R in sorted(ladders().items()):
    sp = [r['spread'] for r in R]
    usable = [r for r in R if r['spread'] <= MAKAS_ESIK and r['mid'] < COZULMUS_ESIK]
    resolved = [r for r in R if r['mid'] >= COZULMUS_ESIK]

    # monotonluk: yukari yonde K artarken mid azalmali; asagi yonde K azalirken mid azalmali
    viol = []
    for d, keyf in (('up', lambda r: r['K']), ('down', lambda r: -r['K'])):
        seq = sorted([r for r in R if r['dir'] == d and r['mid'] < COZULMUS_ESIK], key=keyf)
        for a, b in zip(seq, seq[1:]):
            if b['mid'] > a['mid'] + 1e-9:
                viol.append((d, a['K'], a['mid'], b['K'], b['mid']))

    print('%-6s %5d %9.3f %9.3f %9.3f %8d %9d %s'
          % (t, len(R), statistics.median(sp), statistics.mean(sp), max(sp),
             len(usable), len(resolved), len(viol) if viol else '-'))
    report[t] = {'basamak': len(R), 'medyan_makas': round(statistics.median(sp), 4),
                 'en_genis_makas': round(max(sp), 4), 'olculebilir': len(usable),
                 'cozulmus_olabilir': len(resolved),
                 'monotonluk_ihlali': [{'yon': v[0], 'K1': v[1], 'mid1': v[2],
                                        'K2': v[3], 'mid2': v[4]} for v in viol]}

print('-' * 94)
print('"olculebilir" = makas <= %.2f VE mid < %.2f olan basamak sayisi'
      % (MAKAS_ESIK, COZULMUS_ESIK))
print()

for t, r in sorted(report.items()):
    if r['monotonluk_ihlali']:
        print('MONOTONLUK IHLALI — %s:' % t)
        for v in r['monotonluk_ihlali']:
            print('   %s yonu: K=%g mid=%.4f  ->  K=%g mid=%.4f  (olasilik ARTMIS, olamaz)'
                  % (v['yon'], v['K1'], v['mid1'], v['K2'], v['mid2']))

print('\nCOZULMUS OLABILIR (mid >= %.2f) — merdivenden cikarilmali:' % COZULMUS_ESIK)
for t, R in sorted(ladders().items()):
    res = [r for r in R if r['mid'] >= COZULMUS_ESIK]
    if res:
        print('   %-6s %s' % (t, ', '.join('%s%g' % ('↑' if r['dir'] == 'up' else '↓', r['K'])
                                           for r in sorted(res, key=lambda x: x['K']))))

json.dump(report, open(os.path.join(BASE, 'inventory', 'ladder_health.json'), 'w',
                       encoding='utf-8'), ensure_ascii=False, indent=1)
print('\nYazildi: inventory/ladder_health.json')
