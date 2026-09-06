# PRODUCT.md — ekran neden böyle görünüyor

Bu belge `DECISIONS.md` ile arayüz arasındaki köprü. Orada **ne ölçtüğümüz**
yazıyor; burada o ölçümlerin ekranda **ne anlama geldiği**.

**Ne değil:** özellik listesi. Öyle olsaydı `BACKLOG.md`'yi tekrarlar ve ilk
tasarım değişikliğinde çürürdü. Yerleşim, renk, bileşen kütüphanesi, framework
burada yok — onlar ucuz değiştirilir, şimdi karar vermek bilmediğimizi biliyormuş
gibi yapmak olur.

**İlke:** sonradan değiştirmesi pahalı olanı sabitle, gerisini aç bırak.
Veri modelinde yaptığımızın aynısı (D-040).

---

## 1. Ürün ne yapıyor

Aynı gelecekteki olaya iki piyasa farklı olasılık veriyor. Bu ürün o farkı
**ölçüyor** ve **ne kadar güvenilebileceğini** söylüyor.

Söylemediği şey: ne yapman gerektiği. Ölçtük — fark yön olarak gerçek ama
neredeyse hiçbir yerde işlenebilir değil (D-049, D-054). Fırsat etiketi
basmak 44 satırın 44'ünde yanlış olurdu.

## 2. Hedef kitle — ve çelişkinin çözümü

Öncelik **kişisel işlem aracı**; site ayrıca portfolyo ve marka değeri taşıyacak.

Bu ikisi ters yöne çekiyor gibi görünür: portfolyo parçası tamamlanmış görünmek
ister, kişisel araç ise yalan söylememek. **Çelişki yok.** Türevden anlayan bir
okuyucuya göre, makası 0,099 olan bir merdivende "44%" basan araç amatör görünür;
"bu satırda makas ölçtüğümüz farktan büyük, sayı üretmiyorum" diyen araç konuya
hakim görünür. **Susmak kusur değil, portfolyo değerinin kendisi.**

Politika: sessizlik gizlenmez, iyi sunulur.

---

## 3. Ölçümden gelen sabitler

Bunlar tasarım tercihi değil, **bulgu**. Değiştirmek için yeni ölçüm gerekir.

### 3.1 Manşet sayı çoğu satırda YOK
TSLA'da 14 basamağın 7'si, SPY aşağı kanadında 7'nin 7'si sayı üretmiyor (D-021).
→ **Liste sütunları her zaman hesaplanabilen şeylerden seçilir.** Fiyatlama sayısı
listenin taşıyıcı sütunu olamaz.

### 3.2 Kanıt gücü ufka göre değişir
Kısa vadede modelsiz dijital; uzun vadede touch sınırı model varsayıyor (D-046).
Kalshi'nin yıllık terminal kovaları bu kısıtı kriptoda kaldırdı (D-064, D-066)
ama emtia/endekste vekil hatası duruyor.
→ **Her satır kendi kanıt seviyesini taşır.** Aynı sayıymış gibi göstermek yanlış.

### 3.3 Hiçbir şey işlenebilir çıkmadı
Dar spread'le 0/44, geniş spread'le 0/25 gerçek hayatta kalan, delta hedge zaten
dijitali replike etmiyor (D-053, D-054). Kalshi yıllık kovalarında ilk kez 2/26
bandı aştı (D-066) — ve o bile vade boşluğu çekincesi taşıyor.
→ **"Alınabilir / satılabilir" etiketi yok.** Bandın kendisi gösterilir: fark,
belirsizlik, sürtünme, ve neden dokunulmaz olduğu.

### 3.4 Referans sıfır değil, farkın kendi tarihi
Opsiyon-implied olasılık varyans risk primi taşır; ham farkı sıfıra göre okumak
kullanıcıyı sürekli aynı yapısal yöne iter (D-009).
→ **"Tipik fark" alanı zorunlu.** Henüz yok — arşiv 2026-08-30'da başladı.

### 3.5 Her sayının yanında onu çürütebilecek bir kısıt bulunur
Bugüne kadar dört hata yakalandı ve **dördünü de sayı değil kısıt yakaladı**:
kıvrık tırnak, metrik oyunlama, put tarafında yanlış eğri, kova sınırında bir
kuruş (D-055, D-067). Sonuncusunda dijitaller tek tek kusursuz görünüyordu;
yalnızca "tüketici kümenin toplamı 1 olmalı" kısıtı hatayı görünür kıldı.
→ **Bu ürünün tasarım ilkesi.** Ekrandaki her sayının yanında onu yanlışlayabilecek
bir kontrol durur: toplam, monotonluk, iki yöntemin uyuşması, makas, eşzamanlılık.

---

## 4. Ekran mimarisi

### 4.1 Manşet: fiyatlama tezi
Ekranın söylediği şey tez. Üstte tek bir ölçüm öne çıkar — o an en güçlü kanıt
seviyesine sahip olan karşılaştırma.

### 4.2 Liste: akış dolgusu + her zaman hesaplanabilen sütunlar
Akış verisi her markette dolu (D-038); fiyatlama sayısı seyrek. Bu yüzden
**tez manşet mesaj, akış liste dolgusu.** İkisi çelişmiyor, farklı iş yapıyor.

Liste sütunları — hepsi her satırda hesaplanabilir:

| sütun | neden burada |
|---|---|
| varlık / merdiven | kimlik |
| basamak sayısı | merdivenin derinliği |
| **ölçülebilir oran** (örn. `20/22`) | tek bakışta güvenilirlik |
| kanıt seviyesi | modelsiz / model varsayımlı |
| hacim · açık pozisyon | likidite |
| tazelik | son güncelleme, ve iki tarafın kayması |
| vade | ufuk |

Fiyatlama sayısı listede **taşıyıcı sütun değil**; hak edildiği satırda görünür.

### 4.3 Sıralama: ölçülebilirliğe göre
Alfabetik veya hacme göre değil. Ölçülen varlıklar üstte (BTC/ETH: 20/22),
ölçülemeyenler altta. Böylece ekranın üstü dolu ve canlı; solukluk beklenen
yerde başlıyor ve "veri gelmemiş" değil "burası zaten ölçülemeyen bölge"
diye okunuyor.

### 4.4 Detay: satıra tıklayınca
Basamak tablosu, iki tarafın fiyatı, fark, belirsizlik, sürtünme kırılımı,
ve geçerli kontroller. Sekmeler: **Pricing** ve **Hedge** aktif; diğerleri
`DATA_SOURCES.md`'de doğrulanmadan açılmaz.

---

## 5. Sessiz satır politikası

Ölçülemeyen satır **soluk gösterilir**, gerekçe üstüne gelince görünür.
Filtrelenmez, gizlenmez.

Gerekçe her zaman somut ve sayısal olur:
- `spread 0.099 — wider than the gap we measure`
- `time value 1.2% of price — deep ITM, unusable`
- `PM price at tick floor`
- `no put chain — downside not measurable`
- `bucket sum 1.13 — set fails exhaustiveness check`

**Neden soluk, neden gizli değil:** ölçemediğimiz yeri göstermek, ölçtüğümüz
yerin değerini artırıyor. Gizlersek ürün her şeyi bilir görünür, ki bilmiyoruz.

---

## 6. Arşiv eksikliği gizlenmez

"Tipik fark" alanı haftalarca boş kalacak. Yerine sayaç yazar:
`reference: collecting — 3 days`.

Eksikliği saklamak yerine sayacı göstermek arşivi **kusur değil özellik**
yapıyor: kullanıcı neyin biriktiğini görüyor, ve o birikimin sonunda ne
geleceğini biliyor.

Arşiv yeterli uzunluğa gelene kadar hiçbir yerde **"istatistiksel olarak
anlamlı"** denmez (D-051). Betimleyici dil kullanılır.

---

## 7. Dil

- **Arayüz: İngilizce.** Türev terminolojisi zaten İngilizce yerleşik
  ("terminal probability", "touch probability", "implied"), ve portfolyo
  okuyucusu İngilizce okuyor.
- **Belgeler: Türkçe.** `DECISIONS.md`, `METHODOLOGY.md`, `DATA_SOURCES.md`
  ve bu belge Türkçe kalır. Çalışma dili bozulmaz, 68 kararın çevirisinde
  nokta kaybetme riski alınmaz.
- **README: Türkçe**, çünkü metodolojiyi anlatıyor. Gerekirse sonradan
  İngilizce bir özet eklenir.

---

## 8. Terminoloji (arayüzde de geçerli)

Kullanılmaz: *fair value, true probability, AI probability, edge, signal,
arbitrage, insider, smart money.*

Kullanılır: *prediction-market-implied probability, options-implied risk-neutral
probability, cross-market probability gap, terminal / touch probability,
measurable / not measurable, large trade, concentrated position,
historical resolution record.*

Gerekçe: iddia edemediğimiz şeyi isimlendirmeyiz. "Edge" ve "signal" işlenebilir
bir şey vaat ediyor; ölçtüğümüz kadarıyla öyle bir şey yok.

---

## 9. Bilerek açık bırakılanlar

Bunlar karara bağlanmadı çünkü **ucuz değiştirilir** ve şimdi karar vermek
bilgi taklidi olur:

- yerleşim, tipografi, renk paleti
- framework ve bileşen kütüphanesi (fork edilmeyecek, kütüphane kullanılacak)
- grafik türleri
- mobil davranış
- bildirim kanalı (B-007)

---

## 10. Bu belgeyi ne değiştirir

Bölüm 3'teki sabitler yalnızca **yeni bir ölçümle** değişir; tartışmayla değil.
Bir sabiti değiştiren ölçüm `DECISIONS.md`'ye karar olarak girer, sonra bu belge
güncellenir. Ters sıra değil.

Bölüm 4–7 kullanıcı tercihidir; değişebilir, gerekçesi buraya yazılır.
