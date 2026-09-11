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

---

## Data rights — what we checked and where we stand

Checked 2026-09-11 by reading the current terms of all three venues. Not legal advice;
this is a record of what the documents say and what we decided.

### What the terms say

**Kalshi** — [Data Terms of Use](https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf)

> "You may access content only for your personal use for non-commercial purposes.
> Non-commercial use does not include the use of Kalshi Data without prior written
> consent from Kalshi in connection with: (1) the development of any software program...
> or (2) providing archived or cached data sets containing Kalshi Data to another
> person or entity."

That document governs the **website**. The API has a separate Developer Agreement at
kalshi.com/developer-agreement which we have not been able to read — the domain blocks
automated access. It may be more permissive. **Unread, therefore unresolved.**

**Polymarket** — [Terms of Use](https://polymarket.com/tos), effective 2026-08-11

Prohibits accessing Data "directly or through an API... whether in raw, derived,
aggregated, or anonymized form" **if you are** a Capital Market Client (broker, market
maker, prop trader, index calculator, fund) **or a market data distributor**, and
prohibits redistributing Data **to** those parties. The restriction is aimed at
institutional data resale, not at analytics tools.

Against that, Polymarket runs a [Builders Program](https://builders.polymarket.com/)
which says the protocol is "free and permissionless to use and access — just start
building", explicitly invites projects that "empower users with new analytics", and
lists 50+ third-party tools including data products.

**Deribit** — [Terms of Service](https://support.deribit.com/hc/en-us/articles/25944471089437-Terms-of-Service-DRB-Panama-Inc)

> "The use of market data and/or derived data is for personal use only. You are not
> allowed to aggregate, resell, publish, forward or in any other way process market
> data and/or derived data (except for personal use) without prior written approval."

Broadest wording of the three, and it reaches derived data. It also carves out personal
use explicitly. Deribit's public market-data endpoints need no key and allow
cross-origin requests from a browser, and a commercial analytics ecosystem exists on
top of them (Laevitas, Amberdata, Block Scholes).

### What we concluded

Building a tool on this data is normal and, on two of three venues, actively
encouraged. The thing that made us different from every other tool in the ecosystem
was not the analysis — it was that we published a continuously growing archive of raw
vendor payloads. Other tools display data; none redistribute it in bulk.

That is the specific practice the Kalshi clause names, and it is the one we changed.

### What we changed

`raw/` is now a **rolling 14-day window** (`ARSIV_GUN` in `collector/collect.py`).
What remains is a research sample large enough to reproduce the published findings —
about 42 snapshots — rather than an indefinite feed. The same change caps repository
growth, which was measured at 4.03 MB/day and would have reached roughly 1.44 GB in a
year against GitHub's 1 GB guidance.

### Still open

- Kalshi's API Developer Agreement is unread. Until it is, the Kalshi position rests on
  website terms that may not be the governing document.
- No written permission has been requested from any venue. All three have a
  "unless agreed in writing" carve-out; none has been exercised.
- Deribit's "derived data" wording arguably reaches `findings/latest.json`. We publish
  it because it is a research result rather than a data feed, but that is our reading,
  not their ruling.
- The current position suits a research and portfolio project. A commercial product or
  an investment round changes the analysis and would need proper legal review.
