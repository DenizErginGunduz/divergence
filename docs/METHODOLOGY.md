# METHODOLOGY.md

Güncelleme: 2026-08-30. Bu belgenin önceki sürümü üç yerde yanlıştı; düzeltmeler
gerekçesiyle birlikte aşağıda ve `DECISIONS.md`'de duruyor.

| Katman | Durum | Kanıt |
|---|---|---|
| 1 — merdiven → yoğunluk | **doğrulandı** | ETH ort. mutlak hata 0,0014 |
| 2 — vadeli tutarlılık | **doğrulandı** | put-call paritesi, 21 strike, %0,146 dağılım (D-036) |
| 3 — touch primi alt sınırı | **doğrulandı** | sert alt sınır 19/19 (D-018, D-030) |
| 4 — Breeden–Litzenberger | veri hazır | strike ızgarası kanatlarda seyrek |

---

## 0. Köprü — iki aracı aynı birime çevirmek

**Adım 1 — Prediction tarafını olasılığa çevir.**
Binary kontratın fiyatı zaten olasılık birimindedir. Ama **orta fiyat kullanılmaz**:
ince merdivende orta fiyat kimsenin işlem yapmadığı hayali bir sayıdır. Alış ve
satış ayrı ayrı karşılaştırılır (D-024). Tek taraflı kitapta `UNKNOWN`, sıfır değil.

**Adım 2 — Opsiyon tarafını olasılığa çevir.**
Call fiyatı olasılık değildir. Terminal olasılık dijital yaklaşımıyla çıkarılır:

    P(S_T > K) ≈ −∂C/∂K ≈ [C(K₁) − C(K₂)] / (K₂ − K₁)

Bu bir model değil, türevin sayısal yaklaşımıdır. **Birincil yöntem budur** (D-027).

**Adım 3 — Kontrat tipini eşleştir.** Atlanamaz, bkz. bölüm 2.

---

## 0a. İki tuzak — ikisi de bu projede ölçüldü

### Tuzak 1: yanlış enstrüman (D-025, D-035)
Aşağı yön olasılığını derin ITM call'dan türetmek, küçük bir farkı iki büyük
sayının farkından okumaktır. Put-call paritesi gereği iki yol **aynı sayıyı
vermek zorundadır**; ayrılma doğrudan ölçüm hatasıdır:

| zaman değeri / fiyat | %86 | %35 | %12 | %4,8 | %1,2 | %0,4 |
|---|---|---|---|---|---|---|
| call yolu / put yolu | 1,01 | 1,01 | 1,02 | 1,04 | 1,28 | **2,09** |

**Kural:** yukarı yön OTM call, aşağı yön OTM put. Zaman değeri payı < %5 ise
o basamak `ÖLÇÜLEMEZ`. Put zinciri yoksa aşağı yön için sayı üretilmez.

### Tuzak 2: skew'i yok saymak (D-027, D-029)
`C`, `K`'ya iki yoldan bağlıdır — doğrudan ve IV eğrisi üzerinden:

    dC/dK = (∂C/∂K)|σ + vega · (∂σ/∂K)

Naif `N(d2)` ikinci terimi atar. BTC aylık zincirinde ölçülen bedel: modelsiz
hakeme göre ortalama **%54,8**, kanatlarda **%334** sapma. Skew terimi eklenince
sapma **%1,9**'a düşüyor. Günlük zincirde etki yok — vade 0,4 gün, vega ≈ 0.

**Sonuç:** skew düzeltmesi orta/uzun vadede zorunlu; bu, orta vade önceliğinin
ikinci bağımsız gerekçesi.

---

## 1. Katman 1 — merdiven → ayrık yoğunluk

    P(S_T > K_j) = Σ_{i ≥ j} P(kova_i)

| Varlık | Snapshot yayılması | Ort. mutlak fark | Maks. |
|---|---|---|---|
| **ETH** | ~2 dakika | **0,0014** | 0,0040 |
| **BTC** | ~3,5 saat | 0,0123 | 0,0899 |

Eşzamanlı iki bağımsız merdiven birbirini 0,14 puan hatayla doğruluyor — hem
dönüşümün hem sınıflandırmanın kanıtı. 3,5 saatlik kayma hatayı 9 kat büyütüyor;
bu piyasa tutarsızlığı değil **ölçüm hatasıdır**.

**Tükenmişlik şartı:** kümülatif yalnızca kova seti tüm sonuç uzayını kapsıyorsa
geçerlidir. Alt kuyruk kovası yoksa o bölge okunmaz. Betik otomatik uyarır.

---

## 2. Kontrat tipi eşleştirmesi

| Tip | Sorduğu soru | Opsiyon karşılığı |
|---|---|---|
| `terminal` | `P(S_T > K)` | dijital yaklaşımı, model yok |
| `range` | `P(K₁ < S_T ≤ K₂)` | iki dijitalin farkı, model yok |
| `touch` | `P(max S_t ≥ K)` | doğrudan karşılığı yok — alt sınır ilişkisi var |

**Önceki sürümdeki hata:** "touch opsiyonla karşılaştırılmayacak" demiştim.
Yanlıştı. Terminal taraf opsiyondan gelebilir ve şu ilişki **tanım gereği** doğrudur:

    P(vade içinde K'ya değme) ≥ P(vadede K'nın ötesinde kapanma)

Bu sert alt sınır 19/19 basamakta sağlandı — sınıflandırmanın bağımsız kanıtı.

**Üst sınır "2" ise bir sabit DEĞİLDİR (D-031).** O sayı sürüklenmesiz aritmetik
Brownian hareketten gelir. Fiyat lognormaldir; ileri ölçüde martingal olsa bile
log-fiyatın sürüklenmesi −σ²/2'dir. Tam formül her basamağa kendi üst sınırını
verir (ölçülen aralık 1,94–2,07). Sabit kullanmak yukarı yönde fazla gevşek,
aşağı yönde fazla sıkı bir sınır üretiyordu.

---

## 3. Fark neyin karşısında ölçülür — sıfır değil, kendi tarihi

Mükemmel veriyle bile opsiyon-implied olasılık gerçek frekansa eşit olmaz:
**varyans risk primi** vardır. "Prediction market opsiyona göre ucuz" satırları
çoğunlukla yapısaldır, fırsat değil.

    fark_t   = P_prediction − P_türev
    referans = aynı varlık + benzer vade için farkın geçmiş medyanı
    konum    = (fark_t − referans) / farkın geçmiş standart sapması

Ekranda "fark %8" değil, "fark %8, tipik %6, alışılmışın 1,2 sigma üstünde".
Referans birikmeden gösterge **üretilmez**.

---

## 4. İki görünüm

**Hedge görünümü** — touch merdiveni + vadeli/spot. Opsiyon gerekmez. Kontratı
olasılık tahmini olarak değil koşullu emir maliyeti olarak okur. Bugün çalışır.

**Fiyatlama görünümü** — terminal/range merdiveni + opsiyon zinciri.
Katman 1, 2 ve 4 burada. Model içermeyen tek karşılaştırma. Önce BTC/ETH.

---

## 5. Ekranda zorunlu alanlar

`kontrat_tipi`, `dayanak_referansı`, `çözünürlük_kaynağı`, `vade`,
`snapshot_zamanı` (her iki taraf için ayrı), `alış-satış makası`, `hacim`.

Bunlardan biri eksikken gösterilen fark yorumlanamaz. Özellikle makas: ince
merdivenlerde makas, ölçtüğümüz farkın kendisinden büyük olabilir.

Toplayıcı her koşuda `fiyat_penceresi_saniye` yazar — iki fiyat tarafı arasındaki
kayma. Ölçülen değer 0,75–1,97 sn aralığında; D-015'teki 8 dakikalık kayma farkı
%33 oynatıyordu.

---

## 6. Terminoloji

Kullanılmaz: "gerçek olasılık", "doğru olasılık", "AI olasılığı",
"arbitraj fırsatı", "insider", "akıllı para".

Kullanılır: prediction-market-implied probability, options-implied risk-neutral
probability, cross-market probability gap, terminal probability, touch probability,
büyük işlem, yoğunlaşmış pozisyon, geçmiş çözünürlük performansı.

---

## 7. Açık kalanlar

- Katman 4 (Breeden–Litzenberger) hesabı kurulmadı; veri hazır.
- Referans birikimi başladı (2026-08-30) ama henüz istatistik üretecek uzunlukta değil.
- `data-api` `offset` desteği doğrulanmadı — boşluk oluşmadığı için tetiklenmedi (D-042).
- 5 Ağustos ölçümü bayat: BTC o tarihten beri %19,9 hareket etti ve o günün put
  zinciri geri getirilemez. Ölçüm eşzamanlı veriyle sıfırdan tekrarlanmalı (D-037).
