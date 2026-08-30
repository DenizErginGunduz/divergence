# DATA_SOURCES.md — veri erişilebilirliği

Kısıt: **ücretsiz**, lisans alınmayacak. Güncelleme: 2026-08-30.

## Kanıt seviyesi — bunu önce oku

| Seviye | Anlamı |
|---|---|
| `CANLI-DOĞRULANDI` | Gerçek çağrı yapıldı, veri döndü. |
| `DOKÜMAN` | Sağlayıcının dokümanı okundu, çağrı yapılamadı. |
| `ERİŞİLEMEDİ` | Çağrı denendi, o ortamdan ulaşılamadı. Kaynak hakkında hüküm değil. |
| `YASAK` | Sağlayıcı otomatik çekimi açıkça yasaklıyor. |

Bu ayrım önemli: bir kaynağa ulaşamamak, o kaynağın kapalı olduğu anlamına gelmez.
Geliştirme kum havuzumuzun ağı beyaz listeli olduğu için birçok uç oradan
erişilemedi; aynı uçlar GitHub Actions koşucusundan ve Colab'dan sorunsuz çalıştı.

---

## 1. BTC / ETH — Deribit · `CANLI-DOĞRULANDI`

| Ne | Durum |
|---|---|
| Opsiyon zinciri — **call ve put** (strike, mark, bid/ask, IV, OI, hacim) | anahtarsız |
| Index (spot referans) | anahtarsız |
| Vadeli + perpetual | anahtarsız |

Uç noktalar: `https://www.deribit.com/api/v2/public`
- `get_book_summary_by_currency?currency=BTC&kind=option` — tüm zincir tek çağrıda
- `get_index_price?index_name=btc_usd`

**Put zinciri kritik (D-032, D-035).** İlk çekimimiz yalnızca call içeriyordu ve
aşağı yön olasılığı derin ITM call'dan türetiliyordu — sonuçlar 2,09 kata kadar
saptı. Toplayıcı artık `kind=option` ile ikisini de çekiyor.

**Vadeli veriye gerek kalmadı (D-036).** Put-call paritesi `F = K + C − P`
forward'ı zincirin kendi içinden veriyor. 25SEP26 zincirinde 21 strike boyunca
dağılım 113,75 USD (%0,146) — zincir iç tutarlı. Bir veri bağımlılığı düştü.

**Deribit opsiyonları ters (inverse) tiptir:** USD fiyat = BTC prim × index.

**Geri dönüş yok:** `get_book_summary` yalnızca anlık durumu verir. Kaçırılan
günün zinciri kalıcı olarak kaybolur. Arşivin gerekçesi budur (D-037).

---

## 2. Polymarket · `CANLI-DOĞRULANDI`

| Uç | Durum | Ne veriyor |
|---|---|---|
| `gamma-api` `/events?tag_slug=...` | 200 | merdivenler, kural metni, bestBid/bestAsk |
| `data-api` `/trades?market=<conditionId>` | 200 | `proxyWallet, size, price, side, outcome, timestamp, transactionHash` |
| `data-api` `/holders?market=<conditionId>` | 200 | pozisyon sahipleri |
| `clob` `/prices-history` | 200 ama **boş** | parametreler yeniden denenmeli (B-008) |
| `clob` `/book` | 404 | yol yanlış; gerekli değil |
| `clob` `/trades` | 401 | kimlik ister; `data-api` karşılıyor |

**Akış verisi ürünün ikinci ayağı (D-038, D-039).** Opsiyon piyasasında karşı
tarafta kimin olduğunu göremezsin; prediction market zincir üstü olduğu için
görebilirsin. Bu, prediction market'lerin yapısal üstünlüğü.

**Ölçülen işlem hızı (2026-08-30, 106 market):**

| | en hızlı | p10 | medyan | p90 |
|---|---|---|---|---|
| 100 işlemin kapsadığı süre | 0,64 sa | 34 sa | **248 sa** | 3.040 sa |

Marketlerin yarısı 24 saattir sessiz; en yoğunu saatte 156 işlem yapıyor.
`limit=100` ile hiçbir işlemi kaçırmamak için çekim aralığı en yoğun marketin
100-işlem penceresinden (38 dk) kısa olmalı. Günde üç koşu medyan markette
hiçbir şey kaybettirmiyor, en yoğununda kaybettirebilir — bu yüzden toplayıcı
boşluğu tespit edip bayrak koyuyor.

**`offset` sayfalama desteği doğrulanmadı (D-042).** Betik varsaymıyor: deniyor
ve sonucu `sayfalama_calisti` alanına yazıyor. Boşluk oluşmadığı için henüz
tetiklenmedi.

**Not — coğrafi engel:** Polymarket Türkiye'den erişime kapalı. Bu boru hattını
etkilemiyor; toplayıcı GitHub Actions üzerinde (ABD) çalışıyor ve tüm uçlara
erişiyor. Actions mimarisinin ikinci faydası.

---

## 3. Emtia (altın, gümüş, petrol)

**Fiyat ile opsiyon zincirini ayırmak şart.** İkisi çok farklı zorlukta.

### 3a. Vadeli/spot FİYAT — kolay
API Ninjas Commodity, CommodityPriceAPI, OilPriceAPI — hepsi `DOKÜMAN`.
15 dakika gecikme bizim için sorun değil.

### 3b. Opsiyon ZİNCİRİ — asıl darboğaz
CME opsiyon verisi lisanslı. Ücretsiz emtia API'lerinin hiçbiri zincir vermiyor.

**Çıkış yolu: ETF vekilleri (GLD, SLV, USO).** Bedeli sessizce geçilmemeli:
- **Taşıma maliyeti farkı** — GLD fiziki altın tutar, GC vadelisi taşıma içerir.
- **USO'da rulo aşınması** — ön ay CL tutup rulo yapar; contango'da uzun vadede
  spot petrolden sistematik sapar. **USO uzun vadeli WTI vekili DEĞİLDİR.**
- **Gider oranı** — fon ücreti yavaş bir kayma yaratır.

### 3c. Polymarket tarafındaki uyumsuzluk
Altın merdivenimiz `Gold (GC)` CME vadelisi üzerinden çözülüyor. GLD opsiyonuyla
karşılaştırmak iki dönüşümü üst üste bindirir: GC→GLD ve touch→terminal.
Her dönüşüm bir hata kaynağı.

---

## 4. S&P 500

| Ne | Durum |
|---|---|
| SPY opsiyon zinciri | `DOKÜMAN` — hisse opsiyonu kanalından ücretsiz |
| CBOE gecikmeli kotasyon sayfaları | **`YASAK`** |
| ES vadelisi | `UNKNOWN` |

**CBOE uyarısı:** otomatik çekimi açıkça yasaklıyor ve IP engellediğini belirtiyor.
Boru hattına konmayacak. Elle bakmak serbest.

**İyi haber:** Polymarket marketi zaten SPY üzerine yazılıyor (kural metni: Pyth,
normal seans, bölünme düzeltmeli). Yani SPY opsiyonuyla karşılaştırmak daha doğru;
endeks/ETF sorusu kendiliğinden çözülüyor (D-012).

---

## 5. Hisse senetleri (Mag7)

| Kaynak | Ücretsiz koşulu | Not |
|---|---|---|
| yfinance (Yahoo) | anahtarsız | Resmî API değil. Doğrudan HTTP veri merkezi IP'lerinden engelli; kütüphane Colab'dan çalıştı. |
| Finnhub | 60 çağrı/dk, 20 dk gecikme | Ücretsiz katmanların en cömerti |
| Polygon.io | 5 çağrı/dk | Yavaş ama çalışır |
| Alpha Vantage | **25 çağrı/gün** | Pratikte kullanılamaz |

### Ama darboğaz opsiyon tarafında değil (D-021)

Önce "hisseler en kolay taraf" demiştim; yalnızca **veri erişimine** bakmıştım,
**likiditeye** bakmamıştım. Ölçüm:

| Varlık | Basamak | Medyan makas | Ölçülebilir |
|---|---|---|---|
| BTC | 22 | 0,002 | **20** |
| SPY | 14 | 0,024 | 2 |
| NVDA | 14 | 0,074 | **0** |
| META | 14 | 0,090 | 1 |
| TSLA | 14 | 0,099 | 1 |

Ölçülebilir = makas ≤ 0,02 **ve** mid < 0,99. Eşiğin gerekçesi: BTC'de ölçtüğümüz
farklar 0,006–0,026 aralığındaydı; makas bundan büyükse üretilen sayı piyasa
görüşü değil makasın kendisidir.

**Hisseler üründen çıkarılmıyor:** listede görünürler, sayı yerine gerekçeli
"ölçülemez" etiketi taşırlar.

---

## 6. Özet

| Varlık | Prediction market | Opsiyon zinciri | Durum |
|---|---|---|---|
| BTC | çok derin | Deribit call+put | **çalışıyor** |
| ETH | derin | Deribit call+put | **çalışıyor** |
| SPY | 14 touch aylık | ücretsiz kanal | merdiven likiditesi zayıf |
| TSLA/NVDA/META | 14'er touch | ücretsiz kanal | **ölçülemiyor** — makas |
| Altın/Gümüş/Petrol | var | yalnızca ETF vekili | vekil hatası taşır |
