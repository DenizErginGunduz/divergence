#!/usr/bin/env python3
"""
collect.py — DIVERGENCE ESZAMANLI TOPLAYICI

Neden var: D-037. Deribit `get_book_summary` yalnizca ANLIK durumu verir;
5 Agustos'un put zinciri geri getirilemedi. Kacirilan gun kalici olarak kayiptir.
Bu betik her calistiginda uc tarafi da ayni pencerede yakalar ve HAM haliyle saklar.

Tasarim kararlari (gerekcesiyle):

1) ESZAMANLILIK ONCE GELIR. D-015'te 8 dakikalik kayma olculen farki %33 oynatmisti.
   Bu yuzden once TUM cagrilar yapilir, sonra diske yazilir. Yazma islemi
   cagrilarin arasina girmez. Her dosyaya kendi cekim ani damgalanir.

2) HAM VERI DEGISTIRILMEDEN SAKLANIR (proje kurali 2). Hicbir alan silinmez,
   yeniden adlandirilmaz, yuvarlanmaz. Metodoloji degisecek; ham veriden
   yeniden hesaplayabilmeliyiz.

3) KISMI YAZMA YOK. Bir taraf duserse o kosu ISARETLENIR ama digerleri yine de
   yazilir — cunku eksik gun, hic gun olmamasindan iyidir. Eksiklik _meta.json
   icinde acikca durur, sessizce gizlenmez.

4) SIR YOK. Deribit, Polymarket gamma ve data-api anahtarsiz calisir
   (D-038 ve DATA_SOURCES'ta CANLI-DOGRULANDI). GitHub Actions kendi reposuna
   yazmak icin hazir GITHUB_TOKEN kullanir. Kurulmasi gereken hicbir gizli deger yok.
"""
import json, os, sys, time, datetime, urllib.request, urllib.error

UA = {'User-Agent': 'divergence-research/0.1 (+github)'}
GAMMA = 'https://gamma-api.polymarket.com'
DATA = 'https://data-api.polymarket.com'
DERIBIT = 'https://www.deribit.com/api/v2/public'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# D-034: V1 olculen evren BTC + ETH. Digerleri urunde gorunur ama sayi uretmez,
# o yuzden burada da toplanmaz — kapsam genisletmesi olmasin (proje kurali 5).
VARLIKLAR = ['bitcoin', 'ethereum']
DERIBIT_PARA = ['BTC', 'ETH']


def get(url, timeout=30, deneme=3):
    """Tek GET + geri cekilmeli yeniden deneme. Hata yutulmaz, yukari tasinir."""
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


# ============================ CEKIM ============================
# Bu blok bittikten SONRA diske yazilir. Arada I/O yok ki pencere dar kalsin.
t_basla = time.time()
zaman = datetime.datetime.now(datetime.timezone.utc)
DAMGA = zaman.strftime('%Y-%m-%dT%H%MZ')
GUN = zaman.strftime('%Y-%m-%d')

kova = {}
hatalar = {}
zamanlar = {}


def asama(ad, fn):
    """Bir asamayi calistir, suresini ve hatasini kaydet. Cokme, isaretle."""
    t0 = time.time()
    try:
        kova[ad] = fn()
        zamanlar[ad] = round(time.time() - t0, 2)
    except Exception as e:
        hatalar[ad] = str(e)[:300]
        zamanlar[ad] = round(time.time() - t0, 2)
        print('  ! %s BASARISIZ: %s' % (ad, str(e)[:140]), file=sys.stderr)


# --- 1. Deribit opsiyon zinciri: call VE put (D-032/D-035: put sart) ---
def deribit():
    out = {}
    for para in DERIBIT_PARA:
        out[para] = {
            'book_summary': get('%s/get_book_summary_by_currency?currency=%s&kind=option'
                                % (DERIBIT, para), timeout=60),
            'index': get('%s/get_index_price?index_name=%s_usd'
                         % (DERIBIT, para.lower())),
        }
    return out


# --- 2. Polymarket merdivenleri (kesif: etiketli liste) ---
def polymarket_events():
    out = {}
    for v in VARLIKLAR:
        out[v] = get('%s/events?tag_slug=%s&closed=false&limit=200'
                     % (GAMMA, v), timeout=60)
    return out


# --- 3. Polymarket akisi: cuzdan bazinda islemler (D-038) ---
def polymarket_akis():
    """Merdiven marketlerinin conditionId'leri uzerinden islem akisi.
    D-016: etiketli sorgu onbellekli olabilir; akis icin dogrudan market bazli
    sorgu kullaniliyor, o yuzden burada conditionId'ler event'lerden aliniyor."""
    cids, out = [], {}
    for v, evs in (kova.get('polymarket_events') or {}).items():
        for e in (evs or []):
            for m in (e.get('markets') or []):
                if m.get('conditionId'):
                    cids.append(m['conditionId'])
    cids = list(dict.fromkeys(cids))[:120]        # tekille, makul sinirla
    out['_condition_ids'] = cids
    out['trades'] = {}
    for c in cids:
        try:
            out['trades'][c] = get('%s/trades?market=%s&limit=100' % (DATA, c), timeout=25)
        except Exception as e:
            out['trades'][c] = {'_hata': str(e)[:150]}
        time.sleep(0.12)                          # nazik ol, rate limit yeme
    return out


# --- 4. Pozisyon sahipleri: yogunlasma olcumu icin ---
def polymarket_holders():
    out = {}
    for c in ((kova.get('polymarket_flow') or {}).get('_condition_ids') or [])[:60]:
        try:
            out[c] = get('%s/holders?market=%s&limit=100' % (DATA, c), timeout=25)
        except Exception as e:
            out[c] = {'_hata': str(e)[:150]}
        time.sleep(0.12)
    return out


print('DIVERGENCE toplayici — %s' % zaman.isoformat())
asama('deribit', deribit)                      # once turev: en hizli degisen taraf
asama('polymarket_events', polymarket_events)
t_fiyat_penceresi = round(time.time() - t_basla, 2)   # fiyat taraflari arasi kayma
asama('polymarket_flow', polymarket_akis)      # akis daha yavas, fiyattan SONRA
asama('polymarket_holders', polymarket_holders)

# ============================ YAZMA ============================
yazildi = []
for ad, veri in kova.items():
    d = os.path.join(ROOT, 'raw', ad, GUN)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, '%s_%s.json' % (ad, DAMGA))
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(veri, f, ensure_ascii=False, separators=(',', ':'))
    yazildi.append({'dosya': os.path.relpath(p, ROOT),
                    'bayt': os.path.getsize(p), 'asama': ad})

meta = {
    'snapshot_utc': zaman.isoformat(),
    'toplam_saniye': round(time.time() - t_basla, 2),
    # KRITIK ALAN: iki fiyat tarafi arasindaki kayma. D-015 geregi ekranda
    # gosterilecek; bu deger buyukse o kosunun farklari guvenilmez.
    'fiyat_penceresi_saniye': t_fiyat_penceresi,
    'asama_sureleri': zamanlar,
    'hatalar': hatalar,
    'tam_mi': len(hatalar) == 0,
    'dosyalar': yazildi,
    'varliklar': VARLIKLAR,
    'not': 'Ham yanitlar degistirilmeden saklandi (proje kurali 2).',
}
md = os.path.join(ROOT, 'raw', '_meta', GUN)
os.makedirs(md, exist_ok=True)
with open(os.path.join(md, 'meta_%s.json' % DAMGA), 'w', encoding='utf-8') as f:
    json.dump(meta, f, ensure_ascii=False, indent=1)

print('  fiyat penceresi : %.2f sn   (D-015: dar olmali)' % t_fiyat_penceresi)
print('  toplam sure     : %.2f sn' % meta['toplam_saniye'])
print('  yazilan dosya   : %d' % len(yazildi))
for y in yazildi:
    print('    %-58s %8.1f KB' % (y['dosya'], y['bayt'] / 1024))
if hatalar:
    print('  EKSIK ASAMALAR  : %s' % ', '.join(hatalar))
    print('  (kosu yine de kaydedildi — eksik gun, hic gun olmamasindan iyidir)')
sys.exit(0)
