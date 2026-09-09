# DESIGN.md — tasarım dili

`PRODUCT.md` ekranın **ne söylediğini** yazıyor; bu belge **nasıl göründüğünü**.

Temel kural: **yarın bir tema geldiğinde değişmesi gereken tek şey token dosyası
olmalı.** Bunun için üç katman ayrıldı ve karışmaları yasak.

| katman | içerik | değişebilir mi |
|---|---|---|
| **token** | palet, yazı tipi, köşe, boşluk, gölge | **evet** — tema dosyası değişir, başka hiçbir şey |
| **işlevsel** | yoğunluk, hizalama, tabular rakam, renk anlamları, sessizlik dili | **hayır** — ancak yeni bir ölçümle |
| **içerik** | kart alanları, sütunlar, ikon eşlemesi | **evet** — veri, kod değil |

---

## 1. Token katmanı

Hepsi CSS değişkeni. Tema değişimi = bu bloğun değişmesi.

```
--bg            arka plan            #090b0c
--surface       yüzey (kart, satır)  #131516
--border        ayırıcı              #1f2223
--text          birincil metin       #e8e8e8
--text-2        ikincil              #c6c6c6
--text-3        soluk / etiket       #878787
--text-4        sessiz satır         #4a5052
--accent        tek vurgu rengi      (tema belirler)
--font          gövde yazı tipi      Inter var
--radius        köşe                 6px
--gap           temel boşluk         8px
```

**Vurgu rengi tektir.** DefiLlama tek mavi (202 kullanım), Laevitas tek teal
(117 kullanım) kullanıyor. Renk dekorasyon için harcanmaz.

---

## 2. İşlevsel katman — tema bunlara dokunmaz

Bunlar süs değil, okunabilirlik ve dürüstlük taşıyor. Değiştirmek için gerekçe
`DECISIONS.md`'ye karar olarak girmeli.

### 2.1 Sayılar
- **Sağa hizalı.** İsimler sola, sayılar sağa. (DefiLlama'da hücrelerin %89'u sağa hizalı.)
- **`font-variant-numeric: tabular-nums` zorunlu.** İncelediğimiz iki referansta da
  yoktu; sütun sütun sayı karşılaştıran bir üründe en ucuz okunabilirlik kazancı bu.
- Aynı sütunda **aynı ondalık basamak sayısı**. 0.0255 ve 0.005 değil, 0.0255 ve 0.0050.

### 2.2 Renk anlamları
Tema paleti değiştirir, **anlamı değiştiremez**:

| rol | anlam | nerede |
|---|---|---|
| `--ok` | kontrol geçti | toplam, monotonluk, eşzamanlılık |
| `--warn` | çekince var, sayı yine de gösterilir | vade boşluğu, endeks uyuşmazlığı |
| `--muted` | henüz hesaplanamıyor | arşiv bekleyen alanlar |
| `--accent` | ölçülen büyüklük | fark çubuğu |

Yeşil "al" demez, kırmızı "sat" demez. **Yön için renk kullanılmaz** — yön işaretle
yazılır (`+0.0206`). Bu, D-009'daki "tek bir yeşil/kırmızı skora indirgenmeyecek"
kuralının görsel karşılığı.

### 2.3 Yoğunluk
- Tablo satırı **36–40px**. (DefiLlama 50px kullanıyor ama bizim sütunumuz daha fazla.)
- İki punto: **12px** ve **14px**. İki ağırlık: **400** ve **500**.
  600 ve üstü yalnızca kart başlığında.
  Referansta arayüzün ~%95'ini bu dört kombinasyon taşıyordu.
- Kart içi dikey ritim `--gap` katları.

### 2.4 Sessiz satır
Silik (`--text-4`), **yerinde durur**, filtrelenmez. Gerekçe her zaman somut ve
sayısal (bkz. `PRODUCT.md` §5). Gerekçe metni İngilizce ve şablonludur:
`not measurable · <ölçüt> <değer>`

---

## 3. İçerik katmanı — veri, kod değil

Kart alanları ve sütunlar **yapılandırma** olarak durur; değiştirmek için bileşen
açılmaz. Şema:

```json
{
  "asset": "BTC",
  "label": "Bitcoin",
  "icon": "btc",
  "spot": 78483.28,
  "ladders": 6, "expiries": 8,
  "analyses": [
    {"id":"pricing","label":"Pricing","state":"live","detail":"26/28 buckets · model-free"},
    {"id":"flow","label":"Flow","state":"live","detail":"data-api live"},
    {"id":"cross","label":"Cross-platform","state":"live","detail":"Kalshi + Polymarket"}
  ],
  "note": "tails 4–8× richer on prediction"
}
```

`state` üç değer alır: `live` · `partial` · `none`. Yeni bir analiz eklemek
diziye bir eleman eklemek demek; kart bileşeni değişmez.

**Kural:** kartta **skor, rozet, sıralama veya tek sayılık güven yüzdesi yok.**
Kart durum söyler, hüküm vermez.

---

## 4. Varlık simgeleri

Her varlığın bir simgesi olur (Polymarket'teki gibi). Üç kaynak sırayla denenir:

1. **Yerel simge haritası** — kendi kontrolümüzde, `icon` alanındaki anahtarla eşlenir
2. **Polymarket `icon` alanı** — arşivde zaten var (`polymarket_events`), kaynak kayıtlı
3. **Geri düşüş** — dairenin içinde ticker, `--surface` zemin, `--text-2` metin

**Simge asla zorunlu değildir.** Eksikse arayüz bozulmaz, geri düşüş devreye girer.
Üçüncü taraf CDN'e doğrudan bağlanılmaz; dış görsel kullanılacaksa kaynağı ve
lisansı `DATA_SOURCES.md`'ye yazılır.

---

## 5. Sayfa sırası ve açılma

### 5.0 Üstteki iki şerit — gezinme değil, cevap

**[0] Bulgu şeridi (findings strip).** Sayfanın en üstünde, "bu araç ne buldu"
sorusunun cevabı. Yatay, **elle kaydırılan**, dönmeyen.

- **Dönmez.** Otomatik karusel bir kalıp hatasıdır: kullanıcıların çoğu ikinci
  kartı hiç görmez. En iyi bulgumuzu zamanlayıcının arkasına koyamayız.
- **İçeriği daima hesaplanır**, elle yazılmaz. Her kart bir ölçümden türer ve
  veri değişince kart da değişir. Elle yazılmış bir cümle buraya sızarsa
  şerit slogan panosuna döner.
- Her kart **bağımsız anlamlı** olmak zorunda; sıralamaya bağımlı olamaz.

**[0.5] Notable right now.** Varlık kartlarının hemen üstünde üç-dört satırlık
vitrin. Gezinme değil, somut örnek.

- Adı **"notable"**, "opportunities" veya "signals" DEĞİL. Vitrin mantığı
  zamanla fırsat listesine kayar; isim bunu engelleyen ilk settir.
- **Seçim kuralı yazılıdır ve hesaplanır:** farkı sürtünme+belirsizlik bandını
  aşan satırlar; hiçbiri aşmıyorsa en yüksek orana sahip olanlar, ve o durumda
  satırın yanına "within trading costs" etiketi konur.
- Boşsa gizlenir; doldurmak için eşik gevşetilmez.

### 5.1 Açılma



```
[1] Varlık kartları        ızgara · filtre çipleri kalıcı
      ↓ tıkla
[2] Merdiven listesi       satır = merdiven · her zaman hesaplanabilen sütunlar
      ↓ tıkla (YERİNDE açılır)
[3] Basamak tablosu        satır = basamak · fark/band çubuğu
      ↓ tıkla (YERİNDE açılır)
[4] Detay kartı            tek ölçüm · tam gerekçe · kısıt şeridi
```

**Yerinde açılma şart.** Sayfa değiştirmek komşu satırlarla karşılaştırmayı
imkânsız kılar, ki asıl iş odur. Gezinme yorar, açılma yormaz.

---

## 6. İkon aileleri — ikiye ayrılır

Bir ikon "buraya bak" demektir, yani bir iddiadır. Her ikonun **hesaplanabilir
tanımı ve eşiği** olmak zorunda.

**Yapısal — bugün yanar**, tek anlık görüntüden hesaplanır:
- merdiven içinde açık pozisyon sıralaması
- makas durumu (ölçülebilir / değil)
- kanıt seviyesi (modelsiz / model varsayımlı)
- fark bandı aşıyor mu
- tazelik ve eşzamanlılık

**Zamansal — arşiv birikene kadar `--muted` ve "collecting"**:
- hacim, kendi 30 günlük medyanına göre
- olağandışı cüzdan hareketi
- farkın kendi tarihine göre konumu

"Yüksek hacim" gibi eşiksiz etiket kullanılmaz. `volume 4.2× 30d median` kullanılır.

---

## 7. Tema değiştirme kontrol listesi

Yeni tema geldiğinde sırayla:

1. Token bloğu değişir — başka hiçbir dosya açılmaz
2. Kontrast kontrolü: `--text-4` sessiz satırda hâlâ **okunabilir** mi?
   Sessiz satır silik olmalı ama görünmez değil.
3. `--ok` / `--warn` / `--muted` birbirinden ayırt edilebiliyor mu?
   Renk körlüğü altında da ayırt edilmeli — bu yüzden ikon şekli renkle
   birlikte taşınır, renge tek başına güvenilmez.
4. Tabular rakam korunuyor mu? Yeni yazı tipi `tnum` desteklemiyorsa kullanılmaz.
5. Satır yüksekliği 36–40px bandında mı?

Bu beş madde geçmeden tema kabul edilmez.

---

## 8. Bilerek kararsız bırakılanlar

Vurgu renginin kendisi, tipografi ailesi (Inter varsayılan ama bağlayıcı değil),
grafik türleri, mobil kırılma noktaları, animasyon. Bunlar tema geldiğinde
belirlenir; iskelet bunlardan bağımsız çalışır.
