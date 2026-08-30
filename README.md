# Divergence

Prediction market'lerin ima ettiği olasılıklarla, listelenmiş türev piyasalarının
ima ettiği olasılıkları karşılaştıran bir finansal araştırma altyapısı.

Bahis uygulaması değil, otomatik trading botu değil, sinyal servisi değil.

---

## Soru

Aynı gelecekteki olaya iki ayrı piyasa farklı olasılık veriyor. Neden?

Polymarket'te "BTC eylül sonunda 80.000'in üstünde kapanır mı?" kontratı 44 sente
işlem görüyor. Aynı olayın Deribit opsiyon zincirinden çıkan risk-nötr olasılığı
%36. Aradaki 8 puan bir fırsat mı, yoksa teminat maliyeti, komisyon, volatilite
risk primi ve çözünürlük kuralı farkının toplamı mı?

Bu depo o farkı **ölçmeye** çalışıyor. Cevaplamaya değil.

---

## Neden zor

Naif bir karşılaştırma üç yerde sessizce çöker. Üçünü de bu projede ölçtük.

**1. Kontrat tipi karıştırılırsa hesap sistematik olarak bozulur.**
"Vade içinde 80.000'e değer mi" (*touch*) ile "vadede 80.000'in üstünde kapanır mı"
(*terminal*) aynı şey değildir. Touch olasılığı her zaman terminalden büyük veya ona
eşittir. Bu ayrım projenin en hassas noktası ve sınıflandırma yalnızca kural
metninden yapılıyor, başlıktan değil.

**2. Yanlış enstrümandan olasılık türetilirse sonuç tamamen ters dönebilir.**
Aşağı yön olasılığını derin ITM call'dan hesaplamak, küçük bir farkı iki büyük
sayının farkından okumaktır. Ölçtük — hata, zaman değeri payının monoton
fonksiyonu:

| zaman değeri / fiyat | %86 | %35 | %12 | %4,8 | %1,2 | %0,4 |
|---|---|---|---|---|---|---|
| yanlış yol / doğru yol | 1,01 | 1,01 | 1,02 | 1,04 | 1,28 | **2,09** |

Kural: aşağı yön için put zinciri şart. Put yoksa sayı üretilmez.

**3. Skew yok sayılırsa dijital olasılık yanlış çıkar.**
`P(S_T > K) = −dC/dK` ve `C`, `K`'ya iki yoldan bağlıdır — doğrudan ve IV eğrisi
üzerinden. `N(d2)` ikinci terimi (`vega · ∂σ/∂K`) atar. BTC aylık zincirinde
ölçülen bedel: modelsiz hakeme göre ortalama **%54,8** sapma, kanatlarda **%334**.
Skew terimi eklendiğinde sapma **%1,9**'a düşüyor.

---

## Yöntem

Dört katman. İlk üçü opsiyon verisi gerektirmez — bu, projenin lisans ve maliyet
kırılganlığını azaltan ana tasarım kararı.

| | Katman | Durum |
|---|---|---|
| 1 | Merdiven → ayrık yoğunluk | doğrulandı (ETH ort. hata 0,0014) |
| 2 | Vadeli tutarlılık | doğrulandı (put-call paritesinden F, 21 strike'ta %0,146 dağılım) |
| 3 | Touch primi alt sınırı | doğrulandı (sert alt sınır 19/19) |
| 4 | Breeden–Litzenberger | veri hazır |

---

## Bu depoda ne var

```
collector/    eşzamanlı toplayıcı — Polymarket merdivenleri + akış, Deribit call/put
raw/          ham API yanıtları, tarih damgalı, sonradan değiştirilmez
state/        su işareti — hangi işlemi gördüğümüzün kaydı
docs/         METHODOLOGY · DATA_SOURCES · DECISIONS · BACKLOG
scripts/      ölçüm ve doğrulama betikleri
```

Toplayıcı günde üç kez çalışır ve ham JSON'u olduğu gibi işler.
Anahtar gerekmez: Deribit, Polymarket Gamma ve Polymarket data-api'nin
kullandığımız uçları anahtarsızdır.

**Neden arşiv:** Deribit yalnızca anlık durumu verir. Bir günü kaçırırsak o günün
opsiyon zinciri kalıcı olarak kaybolur. 5 Ağustos'un put zincirini geri
getiremediğimiz için o tarihli bir ölçümü düzeltemedik — arşiv bu yüzden ürünün
yanında değil, altında duruyor.

İşlemler `transactionHash` ile tekillenir; her çekim hangi zaman aralığını
gördüğünü ayrıca kaydeder. Bu olmadan "işlem yok" ile "biz bakmıyorduk"
ayırt edilemez.

---

## Çalışma kuralları

Bu kurallar rahatlık için değil, hepsi bir hatadan sonra yazıldı.

1. **Uydurma yok.** Endpoint, fiyat, kural metni tahmin edilmez. Bilinmiyorsa `UNKNOWN`.
2. **Ham veri değiştirilmeden saklanır.** Metodoloji değişecek; yeniden hesaplayabilmeliyiz.
3. **Kural metni birebir alıntılanır**, özetlenmez.
4. **Kapsam sessizce genişletilmez.** Yeni fikir `docs/BACKLOG.md`'ye yazılır.
5. **Emin olmadığın sayıyı üretme, uyarı üret.** Ekrandaki her sayı birinin
   finansal kararını etkileyebilir.
6. **Belirsizlik çözülmez, yüzeye çıkarılır.**

### Terminoloji

Kullanılmaz: "gerçek olasılık", "doğru olasılık", "AI olasılığı", "insider",
"akıllı para".

Kullanılır: prediction-market-implied probability, options-implied risk-neutral
probability, terminal probability, touch probability, cross-market probability gap,
büyük işlem, yoğunlaşmış pozisyon, geçmiş çözünürlük performansı.

**Olasılık farkı otomatik olarak arbitraj fırsatı değildir.** Fark; teminat
maliyeti, komisyon, makas, volatilite risk primi, çözünürlük kaynağı farkı ve
model hatasından oluşabilir.

---

## Durum

Faz 0 — doğrulama. Uygulama kodu henüz yazılmıyor; amaç karşılaştırılabilir
kontratların gerçekten var olup olmadığını ölçmek.

Karar geçmişi `docs/DECISIONS.md` içinde, geri çektiğim sonuçlar dahil.
