#!/usr/bin/env python3
"""
collect.py v2 — DIVERGENCE TOPLAYICI, OLAY BAZLI

v1 her kosuda her marketin son 100 islemini yeniden sakliyordu. Olcum:
106 market, ~10.600 islem, 7,3 MB — ve medyan markette 8 saatte yalnizca ~3 yeni
islem oluyor. Yani dosyanin neredeyse tamami kopyaydi.

v2 uc seyi degistiriyor. Ucu de "sonradan eklemesi pahali" oldugu icin simdi:

  1) OLAY BAZLI DEPOLAMA
     Islemler transactionHash ile tekillenir; yalnizca YENI olanlar eklenir.
     Boylece hangi hizda cekersek cekelim ayni depoya yaziyoruz. Anlik izleyici
     sonradan devreye girdiginde format degistirmeye gerek kalmaz.

  2) KAPSAM KAYDI
     Her cekim "bu marketi hangi zaman araliginda gordum" bilgisini yazar.
     Bu olmadan sonra "islem yok" ile "biz bakmiyorduk" ayirt edilemez.
     Bildirim urununde bu ayrim her seydir: sessizlik bilgi sanilir.

  3) BOSLUK TESPITI + SAYFALAMA
     79 market 100 sinirina dayanmisti; oncesinde gormedigimiz islemler olabilir.
     Bir onceki su isaretinden geriye ulasamazsak BOSLUK bayragi konur ve
     sayfalama ile kapatilmaya calisilir.
     NOT: data-api'nin offset destegi DOGRULANMADI. Bu yuzden betik varsaymaz —
     denemeyi yapar, sonucu `sayfalama_calisti` alanina yazar. Ilk kosu bize soyler.

Degismeyen kurallar: eszamanlilik once gelir (D-015), ham veri alanlari
degistirilmez (kural 2), eksik asama gizlenmez (kural 6).
"""
import json, gzip, os, re, sys, time, datetime, urllib.request

UA = {'User-Agent': 'divergence-research/0.2 (+github)'}
GAMMA = 'https://gamma-api.polymarket.com'
DATA = 'https://data-api.polymarket.com'
DERIBIT = 'https://www.deribit.com/api/v2/public'
KALSHI = 'https://external-api.kalshi.com/trade-api/v2'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VARLIKLAR = ['bitcoin', 'ethereum']          # D-034: V1 olculen evren
DERIBIT_PARA = ['BTC', 'ETH']
SAYFA = 100                                  # data-api limit
MAX_SAYFA = 6                                # bosluk kapatma denemesi ust siniri
HOLDERS_SAATI = 5                            # pozisyon sahipleri gunde BIR kez (05 UTC)

# Kalshi seri listesi ELLE SABITLENMEZ (D-063). Ilk denemede listeyi kesik bir
# katalog yanitindan cikardim ve 62 BTC/ETH serisinin 42'sini kacirdim -- aralarinda
# tam aradigimiz yillik TERMINAL kontratlar da vardi. Artik her kosuda katalogdan
# TURETILIYOR; kaynak degisirse biz de degisiriz.
KALSHI_GOZLEM_DESEN = r'S&P|SPX|Nasdaq|NDX|Dow|DJIA|gold|silver|oil|crude|WTI|Brent'
KALSHI_SERI_UST_SINIR = 90        # kosu suresini sinirla


def get(url, timeout=30, deneme=3):
    son = None
    for i in range(deneme):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            son = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError('%s -> %s' % (url[:90], str(son)[:120]))


def yaz_gz(yol, veri):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with gzip.open(yol, 'wt', encoding='utf-8') as f:
        json.dump(veri, f, ensure_ascii=False, separators=(',', ':'))
    return os.path.getsize(yol)


t0_hepsi = time.time()
zaman = datetime.datetime.now(datetime.timezone.utc)
DAMGA = zaman.strftime('%Y-%m-%dT%H%MZ')
GUN = zaman.strftime('%Y-%m-%d')

kova, hatalar, sureler = {}, {}, {}


def asama(ad, fn):
    t = time.time()
    try:
        kova[ad] = fn()
    except Exception as e:
        hatalar[ad] = str(e)[:300]
        print('  ! %s BASARISIZ: %s' % (ad, str(e)[:140]), file=sys.stderr)
    sureler[ad] = round(time.time() - t, 2)


# ---------------- su isareti (watermark) ----------------
# Her market icin en son gordugumuz islem ani + o andaki hash'ler.
# Hash listesi yalnizca SINIR anindakileri tutar; durum dosyasi boyle sisimez.
WM_YOL = os.path.join(ROOT, 'state', 'watermark.json')
try:
    with open(WM_YOL, encoding='utf-8') as f:
        WM = json.load(f)
except Exception:
    WM = {}


# ---------------- 1. Deribit: call + put, iki para ----------------
def deribit():
    out = {}
    for p in DERIBIT_PARA:
        out[p] = {
            'book_summary': get('%s/get_book_summary_by_currency?currency=%s&kind=option'
                                % (DERIBIT, p), timeout=60),
            'index': get('%s/get_index_price?index_name=%s_usd' % (DERIBIT, p.lower())),
        }
    return out


# ---------------- 2. Polymarket merdivenleri ----------------
def polymarket_events():
    return {v: get('%s/events?tag_slug=%s&closed=false&limit=200' % (GAMMA, v),
                   timeout=60) for v in VARLIKLAR}


# ---------------- 3. Kalshi (D-056) ----------------
def kalshi():
    """Katalog -> izlenecek seriler -> o serilerin TUM marketleri.

    status filtresi YOK: cozulmus marketler de gelsin. Cozulme sonucu
    kalibrasyon/Brier veri setinin ta kendisi ve sonradan geri alinamaz.

    Seri listesi katalogdan turetilir (D-063):
      olculen  = BTC veya ETH etiketli her seri
      gozlem   = Financials icinde endeks/emtia deseni tutan seriler
                 (kapsam karari verilene kadar sayi uretilmez)
    """
    out = {'katalog': {}, 'marketler': {}, 'gozlem': {}, 'secim': {}}
    for kat in ('Crypto', 'Financials'):
        try:
            out['katalog'][kat] = get('%s/series?category=%s' % (KALSHI, kat), timeout=45)
        except Exception as e:
            out['katalog'][kat] = {'_hata': str(e)[:150]}

    def seriler(kat, sec):
        d = out['katalog'].get(kat) or {}
        return [x.get('ticker') for x in (d.get('series') or []) if x.get('ticker') and sec(x)]

    kripto = seriler('Crypto', lambda x: bool({'BTC', 'ETH'} & set(x.get('tags') or [])))
    gozlem = seriler('Financials', lambda x: bool(re.search(
        KALSHI_GOZLEM_DESEN, (x.get('title') or '') + ' ' + ' '.join(x.get('tags') or []), re.I)))
    kripto = kripto[:KALSHI_SERI_UST_SINIR]
    gozlem = gozlem[:KALSHI_SERI_UST_SINIR // 3]
    out['secim'] = {'kripto': kripto, 'gozlem': gozlem}

    def markets(t):
        sayfa, imlec, hepsi = 0, '', []
        while sayfa < 5:
            u = '%s/markets?series_ticker=%s&limit=200' % (KALSHI, t)
            if imlec:
                u += '&cursor=%s' % imlec
            d = get(u, timeout=30)
            m = d.get('markets') or []
            hepsi += m
            imlec = d.get('cursor') or ''
            if not imlec or not m:
                break
            sayfa += 1
        return hepsi

    for kova_ad, liste in (('marketler', kripto), ('gozlem', gozlem)):
        for t in liste:
            try:
                out[kova_ad][t] = markets(t)
            except Exception as e:
                out[kova_ad][t] = {'_hata': str(e)[:150]}
            time.sleep(0.08)
    return out


# ---- ESZAMANLILIK: uc kaynagin da kendi ani ayri kaydediliyor (D-015) ----
# Kalshi ~20 cagri suruyor; pencereyi buyutuyor. Gizlemek yerine OLCUYORUZ:
# hangi ikili arasindaki kaymanin ne oldugu sonradan hesaplanabilsin.
ANLAR = {}
ANLAR['baslangic'] = 0.0
asama('deribit', deribit);            ANLAR['deribit_bitis'] = round(time.time()-t0_hepsi, 2)
asama('polymarket_events', polymarket_events); ANLAR['polymarket_bitis'] = round(time.time()-t0_hepsi, 2)
PENCERE = ANLAR['polymarket_bitis']             # Deribit <-> Polymarket kaymasi
asama('kalshi', kalshi);              ANLAR['kalshi_bitis'] = round(time.time()-t0_hepsi, 2)


# ---------------- 3. Akis: olay bazli, boslukla birlikte ----------------
def _yeni_mi(t, wm):
    """Bu islem su isaretinden sonra mi? Sinir anindaki beraberlikler hash ile ayrilir."""
    ts = int(t.get('timestamp') or 0)
    if ts > wm['ts']:
        return True
    return ts == wm['ts'] and t.get('transactionHash') not in wm['hashes']


def akis(cids):
    yeni, kapsam = [], []
    for cid in cids:
        wm = WM.get(cid) or {'ts': 0, 'hashes': []}
        ilk_kez = wm['ts'] == 0
        toplandi, sayfa_no, sayfalama_calisti, gorulen = [], 0, None, set()
        try:
            while sayfa_no < MAX_SAYFA:
                url = '%s/trades?market=%s&limit=%d' % (DATA, cid, SAYFA)
                if sayfa_no:
                    url += '&offset=%d' % (sayfa_no * SAYFA)
                s = get(url, timeout=25)
                if not isinstance(s, list) or not s:
                    break
                h = {x.get('transactionHash') for x in s}
                if sayfa_no:
                    # Sayfalama gercekten yeni kayit getiriyor mu? OLC, varsayma.
                    sayfalama_calisti = len(h - gorulen) > 0
                    if not sayfalama_calisti:
                        break
                gorulen |= h
                toplandi += s
                if len(s) < SAYFA:
                    break
                # Ilk kosuda geriye kazmaya calisma: baslangic noktamiz burasi.
                if ilk_kez:
                    break
                # Su isaretine ulastiysak yeter.
                if min(int(x.get('timestamp') or 0) for x in s) <= wm['ts']:
                    break
                sayfa_no += 1
            time.sleep(0.12)
        except Exception as e:
            kapsam.append({'market': cid, 'hata': str(e)[:150]})
            continue

        n = [t for t in toplandi if _yeni_mi(t, wm)]
        yeni += n
        ts_hepsi = [int(t.get('timestamp') or 0) for t in toplandi if t.get('timestamp')]
        en_eski = min(ts_hepsi) if ts_hepsi else None
        en_yeni = max(ts_hepsi) if ts_hepsi else None
        limit_doldu = len(toplandi) >= SAYFA
        # BOSLUK: sinira dayandik AMA onceki su isaretine geri ulasamadik.
        bosluk = bool(limit_doldu and not ilk_kez and en_eski is not None
                      and en_eski > wm['ts'])
        kapsam.append({
            'market': cid, 'cekim_utc': zaman.isoformat(),
            'donen': len(toplandi), 'yeni': len(n), 'sayfa': sayfa_no + 1,
            'en_eski_ts': en_eski, 'en_yeni_ts': en_yeni,
            'onceki_su_isareti': wm['ts'], 'limit_doldu': limit_doldu,
            'sayfalama_calisti': sayfalama_calisti,
            'ilk_kez': ilk_kez,
            # ilk kosuda "bosluk" kavrami anlamsiz: baslangic noktasi burasi.
            'BOSLUK': bosluk,
        })
        if en_yeni is not None:
            WM[cid] = {'ts': en_yeni,
                       'hashes': [t.get('transactionHash') for t in toplandi
                                  if int(t.get('timestamp') or 0) == en_yeni]}
    return {'yeni_islemler': yeni, 'kapsam': kapsam}


# ---------------- Kapsam filtresi: yalnizca FIYAT MERDIVENLERI ----------------
# v2'nin ilk kosusu 770 market cekti; bunlar 'bitcoin'/'ethereum' etiketli TUM
# marketler. Ilan ettigimiz kapsam (D-034) ise BTC/ETH fiyat merdivenleri.
# Bu bir TOPLAMA filtresidir, siniflandirma DEGILDIR: kontrat tipi (terminal/
# touch/range) hala kural metninden belirlenir. Burada yalnizca "bu market bir
# fiyat esigi tasiyor mu" sorusu soruluyor.
ESIK = re.compile(r'\$\s?\d[\d.,]{2,}')


def merdiven_mi(m):
    metin = '%s %s' % (m.get('question') or '', m.get('groupItemTitle') or '')
    return bool(ESIK.search(metin))


cids, kapsam_disi = [], 0
for _v, evs in (kova.get('polymarket_events') or {}).items():
    for e in (evs or []):
        for m in (e.get('markets') or []):
            if not m.get('conditionId'):
                continue
            if merdiven_mi(m):
                cids.append(m['conditionId'])
            else:
                kapsam_disi += 1
cids = list(dict.fromkeys(cids))
asama('akis', lambda: akis(cids))


# ---------------- 4. Pozisyon sahipleri: gunde bir kez ----------------
def holders():
    out = {}
    for c in cids[:80]:
        try:
            out[c] = get('%s/holders?market=%s&limit=100' % (DATA, c), timeout=25)
        except Exception as e:
            out[c] = {'_hata': str(e)[:150]}
        time.sleep(0.12)
    return out


holders_gun_yolu = os.path.join(ROOT, 'raw', 'holders', GUN)
if not os.path.isdir(holders_gun_yolu) or zaman.hour == HOLDERS_SAATI:
    asama('holders', holders)
else:
    sureler['holders'] = 'atlandi (gunde bir kez)'


# ---------------- YAZMA ----------------
yazildi = []


def kaydet(ad, veri):
    p = os.path.join(ROOT, 'raw', ad, GUN, '%s_%s.json.gz' % (ad, DAMGA))
    yazildi.append({'dosya': os.path.relpath(p, ROOT), 'bayt': yaz_gz(p, veri)})


if 'deribit' in kova:
    kaydet('deribit', kova['deribit'])
if 'polymarket_events' in kova:
    kaydet('polymarket_events', kova['polymarket_events'])
if 'holders' in kova:
    kaydet('holders', kova['holders'])
if 'kalshi' in kova:
    kaydet('kalshi', kova['kalshi'])

akis_sonuc = kova.get('akis') or {'yeni_islemler': [], 'kapsam': []}

# Yeni islemler: KOSU BASINA ayri gz dosyasi. Ham alanlar aynen korunur (kural 2).
# Neden tek dosyaya eklemiyoruz: git dosyalari tam blob olarak saklar. Buyuyen
# tek bir NDJSON'a gunde uc kez eklemek, her seferinde dosyanin tamamini yeni
# bir nesne olarak yazdirir. Kosu basina dosya bu buyumeyi ortadan kaldirir.
# Tekilleme zaten su isaretiyle yapildigi icin ekleme semantigine ihtiyac yok.
nd = os.path.join(ROOT, 'raw', 'events', 'trades', GUN, 'trades_%s.ndjson.gz' % DAMGA)
os.makedirs(os.path.dirname(nd), exist_ok=True)
with gzip.open(nd, 'wt', encoding='utf-8') as f:
    for t in akis_sonuc['yeni_islemler']:
        f.write(json.dumps(t, ensure_ascii=False, separators=(',', ':')) + '\n')
yazildi.append({'dosya': os.path.relpath(nd, ROOT), 'bayt': os.path.getsize(nd)})

kp = os.path.join(ROOT, 'raw', 'coverage', GUN, 'coverage_%s.json' % DAMGA)
os.makedirs(os.path.dirname(kp), exist_ok=True)
with open(kp, 'w', encoding='utf-8') as f:
    json.dump(akis_sonuc['kapsam'], f, ensure_ascii=False, indent=1)
yazildi.append({'dosya': os.path.relpath(kp, ROOT), 'bayt': os.path.getsize(kp)})

os.makedirs(os.path.dirname(WM_YOL), exist_ok=True)
with open(WM_YOL, 'w', encoding='utf-8') as f:
    json.dump(WM, f, ensure_ascii=False, separators=(',', ':'))

K = akis_sonuc['kapsam']
sayfalama = [k.get('sayfalama_calisti') for k in K if k.get('sayfalama_calisti') is not None]
ozet = {
    'market': len(K),
    'kapsam_disi_market': kapsam_disi,   # fiyat esigi tasimadigi icin cekilmedi
    'yeni_islem': len(akis_sonuc['yeni_islemler']),
    'limit_dolan': sum(1 for k in K if k.get('limit_doldu')),
    'BOSLUKLU': sum(1 for k in K if k.get('BOSLUK')),
    'ilk_kez': sum(1 for k in K if k.get('ilk_kez')),
    'sayfalama_denendi': len(sayfalama),
    'sayfalama_calisti': sum(1 for x in sayfalama if x),
}
meta = {'snapshot_utc': zaman.isoformat(),
        'toplam_saniye': round(time.time() - t0_hepsi, 2),
        'fiyat_penceresi_saniye': PENCERE,      # Deribit <-> Polymarket
        'kaynak_anlari_saniye': ANLAR,          # ucuncu kaynagin kaymasi da gorunur
        'asama_sureleri': sureler, 'hatalar': hatalar,
        'tam_mi': len(hatalar) == 0, 'akis_ozeti': ozet,
        'kalshi_ozeti': (lambda k: None if not k else {
            'katalog': {a: len((b or {}).get('series') or []) for a, b in k['katalog'].items()},
            'izlenen_kripto_seri': len(k['secim']['kripto']),
            'izlenen_gozlem_seri': len(k['secim']['gozlem']),
            'market_donen_seri': sum(1 for v in k['marketler'].values() if isinstance(v, list) and v),
            'toplam_market': sum(len(v) for v in k['marketler'].values() if isinstance(v, list)),
            'gozlem_market': sum(len(v) for v in k['gozlem'].values() if isinstance(v, list)),
        })(kova.get('kalshi')),
        'dosyalar': yazildi, 'varliklar': VARLIKLAR, 'surum': 2}
mp = os.path.join(ROOT, 'raw', '_meta', GUN, 'meta_%s.json' % DAMGA)
os.makedirs(os.path.dirname(mp), exist_ok=True)
with open(mp, 'w', encoding='utf-8') as f:
    json.dump(meta, f, ensure_ascii=False, indent=1)

print('DIVERGENCE v2 — %s' % zaman.isoformat())
print('  fiyat penceresi : %.2f sn' % PENCERE)
print('  toplam sure     : %.2f sn' % meta['toplam_saniye'])
print('  akis: %(market)d merdiven marketi (kapsam disi %(kapsam_disi_market)d) | %(yeni_islem)d YENI islem | limit dolan %(limit_dolan)d'
      ' | BOSLUKLU %(BOSLUKLU)d | ilk kez %(ilk_kez)d' % ozet)
print('  sayfalama: %d denendi, %d calisti  <- data-api offset destegi BU SATIRDAN okunur'
      % (ozet['sayfalama_denendi'], ozet['sayfalama_calisti']))
for y in yazildi:
    print('    %-52s %8.1f KB' % (y['dosya'], y['bayt'] / 1024))
if hatalar:
    print('  EKSIK ASAMALAR : %s' % ', '.join(hatalar))
sys.exit(0)
