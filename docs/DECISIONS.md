# DECISIONS — Faz 0, Gün 1

Bu dosya, envanteri üretirken verdiğim ve sonucu etkileyen kararları kaydeder.
Hiçbiri sessizce verilmedi; her biri gerekçesiyle burada duruyor ve geri alınabilir.

## D-001 — Veri kaynağı: Gamma API, ezberden değil şemadan
Endpoint ve alan adları `https://docs.polymarket.com/api-reference/markets/list-markets`
adresindeki resmî OpenAPI şemasından teyit edildi. Kullanılan uçlar:
`GET /markets`, `GET /events`, `GET /tags/slug/{slug}`. Anahtar gerekmiyor.

## D-002 — Ağ erişimi kısıtı (uygulama detayı, metodolojiyi etkiler)
Kod çalıştırdığım kum havuzunun ağı beyaz listeyle kısıtlı; `polymarket.com` alan adlarına
doğrudan `curl`/Python ile erişilemiyor. Tüm çağrılar izinli getirme aracıyla yapıldı.
Bu aracın yanıt başına ~82 KB sınırı var. Sonuç: her sayfa küçük tutuldu ve
**yanıtın JSON olarak eksiksiz kapanıp kapanmadığı her seferinde programatik olarak
doğrulandı**; kesilen sayfalarda yalnızca tam ayrıştırılabilen nesneler alındı,
sayfalar 10'luk örtüşmeli ofsetlerle çekilerek boşluk oluşması engellendi.
`raw/_store.json` içindeki `fetches` bölümü her çağrının kaç nesne verdiğini ve
eksiksiz olup olmadığını tutar.

## D-003 — Süresi geçmiş marketler dışarıda
Filtre: `closed=false` **ve** `end_date_min = bugün`.
Gerekçe: Polymarket'te `closed=false` olduğu hâlde vadesi aylar önce dolmuş kayıtlar var
(örnek: Aralık 2025 tarihli 5 dakikalık "Up or Down" marketleri, hacim ve likidite sıfır).
Bunlar canlı fiyat taşımıyor ve envanteri şişiriyor.
**Risk:** bu filtre, vadesi bugün dolan bir marketi kaçırabilir. Faz 0 için kabul edildi.

## D-004 — Sınıflandırma yalnızca kural metninden
`contract_type`, başlıktan değil `description` alanından türetildi. Başlık ile kural metni
çelişirse ikisi de kaydedilir ve `ambiguity_flags` işaretlenir. Bu taramada çelişki bulunmadı.
Tanınmayan kural metni **zorlama sınıflandırılmadı**, `other` bırakıldı.

## D-005 — Kapsam kolonu: hiçbir satır silinmedi
Yedi varlıkla ilgili olup fiyat/seviye eşiği taşımayan marketler (ör. "ABD ulusal Bitcoin
rezervi", "NYSE devre kesici", "Venezuela ham petrol üretimi") envanterden atılmadı;
`scope = KAPSAM_DISI_fiyat_disi_veya_cozulemedi` olarak işaretlendi.
Gerekçe: sayım kaybı olmasın, kararı sen ver.

## D-006 — Event grubu gelmeyen kayıtlara sentetik merdiven etiketi
Bazı marketler API yanıtında `events` nesnesi olmadan geldi. Bunlara
`SENTETIK::varlık|vade|tip|yön` biçiminde bir `ladder_group` türetildi ve ilgili satırlar
`ambiguity_flags` ile işaretlendi. **Bu bir varsayımdır**, API'den gelen bir grup değil.

## D-007 — İki BTC merdiveni elle enjekte edildi
`bitcoin-above-on-august-6-2026` (11 basamak) ve `bitcoin-price-on-august-6-2026`
(11 kova) etiket sorgusuyla gelmiyordu; `GET /events?slug=...` ile ayrıca çekildi ve
API yanıtındaki değerlerle deponun içine yazıldı. Uydurma değer yok, ama bu iki grubun
`conditionId` alanı `"see_raw"` olarak duruyor — tam kimlik gerekiyorsa yeniden çekilmeli.
**Ayrıca:** bu iki grubun anlık görüntü zamanı farklı (`above` 17:11 UTC, `price` 06:19 UTC).
İkisini aynı anda karşılaştırmadan önce eşzamanlı yeniden çekim yapılmalı.

## D-008 — Fiyat alanları
`yes_bid`/`yes_ask` Gamma'nın `bestBid`/`bestAsk` alanları; `yes_mid` bunların ortalaması.
Tek taraflı kitapta karşı taraf yoksa `UNKNOWN` yazıldı, sıfır varsayılmadı.
`snapshot_timestamp_utc` çekim anını, `market_updated_at` Gamma'nın kaydı en son
güncelleme anını verir. İkisi ayrı tutuldu çünkü bazı marketler saatlerdir güncellenmemiş.

## D-009 — Ürünün amacı genişletildi (kullanıcı onaylı, 2026-08-05)
Proje bağlamındaki "sinyal servisi değil" kuralı korunuyor ama ürün artık sadece
farkı göstermekle kalmayacak, **farkın kendi tarihine göre konumunu** da gösterecek.
Yani "fark %8" değil, "fark %8, tipik %6, alışılmışın 1,2 sigma üstünde".

Neden gerekli: opsiyon-implied olasılık varyans risk primi taşır. Ham farkı sıfıra
göre göstermek, kullanıcıyı sürekli aynı yapısal yöne iter ve o yön fırsat değildir.

Sınır: tek bir yeşil/kırmızı skora indirgenmeyecek. Ekranda dört şey ayrı ayrı
durur — prediction fiyatı, türev karşılığı, fark, farkın tipik seviyesi.
İndirgenirse çizgi geçilmiş olur.

Bedeli: referans birikmeden gösterge üretilemez. İlk haftalar yalnızca veri toplar.

## D-010 — Kısa vade üründe değil, kalibrasyonda
Günlük/haftalık merdivenler ürün kapsamı dışında (kullanıcı kararı) ama
**motor doğrulaması için kullanılıyor.** Katman 1 testi bu sayede dış veri
olmadan yapılabildi. Kalibrasyon amaçlı kullanım kapsam genişletmesi sayılmaz.

## D-011 — Altın: CME GC seçildi, XAUUSD beklemede
Hacim ve likidite GC vadelisini gösteriyor (toplam 1.158.013 vs 184.006;
likidite 400.962 vs 55.869). 24 saatlik hacim ters yönü gösteriyor (80.784 vs 12.539)
ama bu vade yakınlığından kaynaklanıyor (XAUUSD 27 gün, GC 148 gün).
İkinci gerekçe: GC, CME'de listelenmiş türevle doğrudan karşılaştırılabilen tek dayanak.
Geri alınabilir.

## D-012 — SPY, SPX endeksi olarak sayılmıyor
Polymarket marketi SPY ETF'i üzerine yazılıyor (kural metni: Pyth, normal seans,
bölünme düzeltmeli). Karşısına SPY opsiyonu konacak, endeks opsiyonu değil.
Böylece temettü ve ölçek düzeltmesi gerekmiyor. `asset=SPX` kalıyor ama
`underlying_reference` alanı "ETF: SPY (S&P 500 ENDEKSI DEGIL)" ve çelişki bayraklı.

## D-013 — CBOE programatik olarak kullanılmayacak
CBOE gecikmeli kotasyon tablolarının otomatik çekimini açıkça yasaklıyor ve
IP engellediğini belirtiyor. Boru hattına konmayacak. Elle bakmak serbest.

## D-014 — ATH kontratları beklemede
Petrol ATH kontratının eşiği kural metninde birebir yazılı ($147,27), yani
147,27 seviyeli normal bir touch gibi işlenebilir. Kullanıcı kararı: şimdilik beklet.

## D-015 — Ölçülen fark, zamanlamaya karşı aşırı duyarlı (2026-08-05, kanıtlı)
İki Deribit snapshot'ı arasında **8 dakika** var (21:14 ve 21:22). Polymarket tarafı
hiç değişmedi (17:11'de donmuş). Buna rağmen ölçülen fark:

| | ortalama \|fark\| | en büyük |
|---|---|---|
| Deribit 21:14 | 0,0094 | 0,0424 |
| Deribit 21:22 | 0,0063 | 0,0264 |

BTC endeksi bu 8 dakikada 64.728 → 64.665 (−64 USD) hareket etti ve ölçülen fark
**%33 küçüldü.** Yani gördüğümüz "fark"ın büyük kısmı piyasa görüşü değil, zamanlama.

**Kural:** eşzamanlılık penceresi dakikalar mertebesinde olmadan bu tabloda sayı
gösterilmeyecek. Ekranda her iki tarafın snapshot zamanı ve aradaki fark zorunlu alan.

## D-016 — Gamma'da sorgu yolu veri tazeliğini değiştiriyor
Aynı market için `/events?slug=...` ile `/events?tag_slug=...&end_date_min=...`
farklı `updatedAt` ve farklı fiyat döndürdü (62.000–64.000 kovası: doğrudan sorguda
0,13/0,14 @20:50, etiketli sorguda 0,23/0,24 @17:14). Muhtemelen önbellek katmanı.

**Sonuç:** üretimde marketler **doğrudan slug/id ile** çekilecek, etiketli liste
sorgusu yalnızca keşif için kullanılacak. Bu doğrulanmadan boru hattı yazılmamalı.

## D-017 — `bitcoin-above-on-august-6-2026` merdiveni durgun
Üç ayrı sorgu yolundan da `updatedAt = 17:11:01` döndü. Yani merdiven 4+ saattir
güncellenmiyor. Karşılaştırma için daha likit bir merdivene geçilmeli, ya da
ölçüm bu merdivende yapılmayacaksa "durgun" etiketiyle gösterilmeli.
Bu, ekranda "son güncelleme" alanının neden zorunlu olduğunun somut gerekçesi.

## D-018 — Katman 3 ENGELLI DEGIL: önceki değerlendirmemi düzeltiyorum
"Aynı vadede touch+terminal çifti yok, Katman 3 ölçülemez" demiştim. Yanlıştı.
Terminal tarafı **Polymarket'ten gelmek zorunda değil** — opsiyon zincirinden gelebilir.
Kullanılan ilişki varsayım değil, tanım gereği doğru:
`P(vade içinde K'ya değme) ≥ P(vadede K'nın ötesinde kapanma)`.

**Ölçüm (2026-08-05, aylık BTC touch merdiveni, 20 basamak):**
20/20 basamak teorik [1, 2] bandında. Sert ihlal yok. Oran başa baş bölgede
zirve yapıp (1,93–1,97) kanatlara doğru 1,0'a iniyor — yansıma ilkesinin
öngördüğü şeklin ta kendisi, ben dayatmadan veriden çıktı.

Bu aynı zamanda touch/terminal **sınıflandırmamın doğru olduğunun bağımsız kanıtı**:
etiketleri karıştırsaydım oranlar anlamsız çıkardı.

## D-019 — Uzun ufuk, eşzamanlılık sorununa dayanıklı
Günlük merdivende 8 dakikalık kayma ölçümü %33 oynatmıştı (D-015).
Aylık merdivende **4,4 saatlik** kaymaya rağmen 20/20 basamak bantta kaldı.
Sebep: oran göreli bir büyüklük ve 26 günlük ufukta 4 saat ihmal edilebilir.

**Sonuç:** orta/uzun vade önceliği yalnızca ürün tercihi değil, **ölçüm dayanıklılığı
gerekçesi.** Kısa vade eşzamanlılık altyapısı olmadan çalışmaz; orta vade bugün çalışır.

## D-020 — Yinelenen market kaydı bulundu
"Will Bitcoin dip to $62,500 in August?" üç kez geçiyor; ikisi mid=0,9995
(BTC 64.639'ken imkansız), biri 0,695. Envanterde (eşik, yön) anahtarına göre
tekilleştirme yapılıyor, en yüksek hacimli tutuluyor, diğerleri raporlanıyor.
Bu adım boru hattında zorunlu — atlanırsa merdivenin o basamağı bozuk çıkar.

## D-021 — Hisse merdivenleri LIKIDITE nedeniyle ölçülemiyor (2026-08-06)
Dün "hisseler en kolay taraf" demiştim. Eksik değerlendirmeydi: yalnızca **veri
erişimine** bakmıştım, **likiditeye** bakmamıştım. Ölçüm:

| Varlık | Basamak | Medyan makas | Ölçülebilir basamak |
|---|---|---|---|
| BTC | 22 | 0,002 | **20** |
| SPY | 14 | 0,024 | 2 |
| NVDA | 14 | 0,074 | **0** |
| META | 14 | 0,090 | 1 |
| TSLA | 14 | 0,099 | 1 |

Ölçülebilir = makas ≤ 0,02 **ve** mid < 0,99.
Eşik gerekçesi: BTC'de ölçtüğümüz farklar 0,006–0,026 aralığındaydı. Makas bundan
büyükse üretilen sayı piyasa görüşü değil makasın kendisidir.

**Sonuç:** hisse opsiyon zinciri çekmenin şu an anlamı yok. Darboğaz opsiyon
tarafında değil, Polymarket tarafında. Task #11 (yfinance/Finnhub) **askıya alındı**.

**Hisseler üründen çıkarılmıyor:** listede görünürler, yanlarında sayı yerine
"makas çok geniş — ölçülemez" etiketi durur. METHODOLOGY'deki "emin olmadığın
sayıyı üretme, uyarı üret" kuralının ilk gerçek uygulaması.

## D-022 — Çözülmüş market tespiti: kullanıcı hipotezi doğrulandı
D-020'deki hipotez beş varlıkta birden doğrulandı. mid ≥ 0,99 olan 13 basamak:
- SPY ↑740 ↑750 ↑760 ↑770 · META ↓560 ↓580 ↑600 · NVDA ↓200 ↑208 ↑216
- TSLA ↑315 · BTC ↓62.500 (iki yinelenen kayıt)

Hepsi tutarlı: NVDA'da hem ↓200 hem ↑216 dolu, yani ağustosta o bandın içinde
dolaşmış. `closed` bayrağı dönmemiş ama market fiilen bitmiş.
Kural `ladder_health.py` içinde, her çalıştırmada otomatik ayıklıyor.

## D-023 — Monotonluk kontrolü boru hattına eklendi
Aynı merdivende eşik uzaklaştıkça touch olasılığı düşmek **zorunda**. Model gerektirmez.
TSLA'da bir ihlal: `↓240 = 0,020` ama `↓225 = 0,105`. O basamağın hacmi sıfır,
makası 0,190 — gerçek arbitraj değil, işlem görmemiş geniş kotasyon.
Bedava ve etkili bir bozuk-kotasyon dedektörü. `ladder_health.py` içinde.

## D-024 — Makul değer bandı tasarımı (kullanıcı fikri, benimsendi)
Polymarket orta fiyatını ölçüm girdisi yapmak yerine **opsiyonu çıpa yapıp
prediction tarafına makul fiyat bandı yayınlamak.** İlikit markette zaten
ihtiyaç duyulan şey referans fiyattır.

Eklediğim incelik: geniş makasta **orta fiyatla değil, alış ve satışla ayrı ayrı**
karşılaştırmak. Orta fiyat kimsenin işlem yapmadığı hayali bir sayıdır.
- `satış < bant_alt` → alınabilir
- `alış > bant_üst` → satılabilir
- diğer → bant makasın içinde, söylenecek bir şey yok

Bandın kaynağı: opsiyondan terminal olasılık, touch/terminal oranı [1, 2].
Model uydurmuyor; oran bandı dün BTC'de 20/20 doğrulandı.

## D-025 — İLK ÖLÇÜM GEÇERSİZ: derin ITM call IV tuzağı
`fair_band_equity.py` ilk çalıştırmada 34 basamağın 11'ini "işlem yapılabilir"
işaretledi. **Dokuzu sahte.** Sebep: aşağı yönlü basamaklar için derin ITM
call'ların implied volatilitesini kullandım.

Derin ITM call fiyatı neredeyse tamamen içkin değerdir; IV kalan kırıntıdan çıkar:

| SPY strike | mid | içkin | zaman değeri | pay | IV |
|---|---|---|---|---|---|
| 670 | 101,83 | 98,93 | 2,90 | **%2,8** | 0,4034 |
| 700 | 72,32 | 68,93 | 3,39 | %4,7 | 0,3168 |
| 730 | 43,17 | 38,93 | 4,24 | %9,8 | 0,2234 |
| 770 (ATM) | 10,47 | 0 | 10,47 | %100 | 0,1347 |

Sonuç IV seçimine göre **tamamen ters dönüyor**. SPY ↓670, PM satış 0,029:

| IV varsayımı | terminal | bant | 0,029 nerede |
|---|---|---|---|
| derin ITM call (0,4034) | 0,1063 | 0,106–0,213 | ALINABILIR |
| makul skew (0,26) | 0,0238 | 0,024–0,048 | bant içinde |
| makul skew (0,22) | 0,0093 | 0,009–0,019 | PAHALI |
| ATM (0,1347) | 0,0001 | ~0 | ÇOK PAHALI |

**Kural:** zaman değeri payı %20'nin altındaki opsiyondan IV türetilmeyecek.

**Düzeltme:** aşağı yön için PUT çekilecek. Derin OTM put'un fiyatı %100 zaman
değeridir. Dahası put'lardan dijital yaklaşımı doğrudan kurulabilir
(`P(S_T<K) ≈ ∂P/∂K`) — bu hiç IV kullanmaz, model taşımaz.

**Ayakta kalan:** TSLA ↑345 ve ↑375 (OTM call, IV güvenilir). ↑345'teki fark
0,003 — yuvarlama içinde, anlamsız. ↑375'teki fark 0,031 — tek ciddi aday,
ama bant üstü (2×) yumuşak sınır olduğu için **bayrak, kanıt değil**.

## D-026 — yfinance çalışıyor (D-021'in bir kısmı düzeltildi)
Colab'dan `yfinance` kütüphanesiyle 5/5 sembol başarılı, gerçek alış/satış geldi.
Doğrudan HTTP bloklu ama kütüphane çalışıyor. Hisse opsiyon zinciri **erişilebilir**.
Likidite sorunu (D-021) ayrı ve hâlâ geçerli — ama D-024 tasarımı onu aşıyor.

## D-027 — Naif N(d2) yöntemi skew varken YANLIŞ; modelsiz dijital birincil olacak
D-025'i düzelttikten sonra (yukarı OTM call / aşağı OTM put) iki bağımsız yöntem
32 basamağın 17'sinde birbirini tutmadı. Sebebi araştırdım: hata veride değil,
**benim analitik yöntemimde**.

Naif yöntem `N(d2)`'yi strike'ın kendi IV'siyle hesaplıyor. Ama call fiyatı
`C(K, σ(K))` biçimindedir ve doğru türev:

    dC/dK = (∂C/∂K)|σ sabit  +  vega · (∂σ/∂K)

İkinci terim skew varken büyüktür. SPY put eğrisinde ölçülen eğim
`∂σ/∂K = −0,0015` (K düştükçe IV yükseliyor). Bu terimi atlayınca:

| strike | naif N(−d2) | modelsiz dijital | oran |
|---|---|---|---|
| 670 | 0,0193 | 0,0091 | **2,12×** |
| 700 | 0,0428 | 0,0229 | 1,87× |
| 720 | 0,0804 | 0,0488 | 1,65× |

Naif yöntem sol kuyruğu sistematik olarak **şişiriyor** — tam da ölçülen yönde.

**Karar:** modelsiz dijital **birincil** yöntem. Analitik yöntem yalnızca vade
uyuşmazlığını düzeltmek için, ve **skew düzeltme terimi eklenerek** kullanılacak.
Düzeltilmeden karşılaştırma yapılmayacak.

Not: BTC/ETH ölçümlerinde (`bridge_btc.py`, `touch_premium_btc.py`) aynı naif
yöntem kullanıldı. Deribit'te ATM civarında skew daha yatık olduğu için etki
daha küçük, ama **sıfır değil**. Bu iki betik skew terimiyle yeniden çalıştırılmalı.

## D-028 — Uyuşmazlık kontrolü ürünün kalıcı parçası
İki bağımsız yöntem birbirini tutmuyorsa **sayı üretilmiyor**. Bu kontrol
D-025'teki 9 sahte sinyalin dokuzunu da yakaladı ve ayrıca yukarıdaki
metodoloji hatasını ortaya çıkardı. `fair_band_v2.py` içinde, eşik %35.

**v2 sonucu:** 32 basamak, 17'si uyuşmazlık nedeniyle reddedildi,
14'ü "bant makasın içinde", **1 tanesi bant dışı**: TSLA ↑375, PM alış 0,200,
modelsiz bant üstü 0,141. Hacim 2.189 USD.
Bu hâlâ **bayrak**, kanıt değil — bant üstü (2×) sıfır sürüklenme varsayımı.

## D-029 — Skew düzeltmesinin BTC'deki ölçülen etkisi (2026-08-28)
`skew_correction_btc.py`, aynı merdiveni üç yöntemle hesaplayıp modelsiz dijitali
hakem alarak D-027'nin BTC tarafındaki bedelini ölçtü:

| Zincir | naif N(d2) sapması | skew'li sapma |
|---|---|---|
| aylık 28AUG26 | ort. **%54,8**, en büyük **%334** | ort. **%1,9**, en büyük %9,3 |
| günlük 6AUG26 | ort. %10,5 | ort. %10,3 |

Aylık zincirde düzeltme belirleyici. Günlükte neredeyse hiç etki yok — çünkü
vade 0,4 gün, vega ≈ 0, skew terimi çarpacak bir şey bulamıyor. Günlükteki
artık %10,5'lik sapma skew'den değil, **kanat veri kalitesinden** geliyor
(66.000 ve 67.000 mark fiyatları 12,49 ve 0,58; fiilen tick kotasyonu).

**Sonuç:** skew terimi orta/uzun vadede zorunlu, kısa vadede ihmal edilebilir.
Bu, orta vade önceliğimizin (D-019) ikinci bağımsız gerekçesi.

## D-030 — D-018'in "20/20 bantta" sonucu GERİ ÇEKİLDİ
Dünkü sonuç naif paydayla hesaplanmıştı. Modelsiz paydayla yeniden çalıştırıldı
(`touch_premium_v2.py`): **19 basamağın 6'sı [1,2] bandında**, 13'ü 2'yi aşıyor.

**Ama D-018'in ÇEKİRDEK iddiası ayakta:** sert alt sınır (oran ≥ 1) 19/19 sağlanıyor,
hatta düzeltme oranları büyüttüğü için daha güvenli hale geldi. Yani
touch/terminal sınıflandırmasının doğru olduğu kanıtı bozulmadı.
Bozulan şey "rahatça bandın içinde" çerçevesiydi. İkisi ayrı iddia; ayrı tutulmalı.

## D-031 — "2" bir sabit değil; lognormal tam sınırla değiştirildi
Üst sınır 2, **sürüklenmesiz aritmetik** Brownian hareket için türetilmiştir.
Fiyat lognormaldir ve ileri ölçüde martingal olsa bile log-fiyatın sürüklenmesi
−σ²/2'dir. Tam formül (`touch_bound_lognormal.py`) her basamağa **kendi** üst
sınırını verir; ölçülen aralık 1,94–2,07.

Sabit kullanmak yukarı yönde fazla gevşek, aşağı yönde fazla sıkı bir sınırdı.
Boru hattında sabit yerine tam formül kullanılacak.

## D-032 — D-025 TEKRAR ETTİ: aşağı yön terminali derin ITM call'dan çıkıyor
Elimizdeki Deribit aylık dosyası **yalnızca call içeriyor**. Aşağı yön terminali
`1 − P(S>K)` olarak hesaplanınca kaynak derin ITM call oluyor. Zaman değeri payı:

| Eşik | 42.500 | 45.000 | 47.500 | 50.000 | 52.500 | 55.000 | 57.500 | 60.000 | 62.500 |
|---|---|---|---|---|---|---|---|---|---|
| zaman değeri / fiyat | %0,8 | %0,9 | %1,1 | %1,5 | %2,1 | %3,4 | %6,3 | %14,0 | %37,8 |

İlk altı basamakta fiyatın %99'u iç değer. Oradan türev almak, küçük bir farkı
iki büyük sayının farkından okumaktır. **D-025 ile birebir aynı tuzak.**

**Kural (kalıcı):** aşağı yön için PUT zinciri şart. Put yoksa aşağı yön için
sayı üretilmez. Eşik: zaman değeri payı < %5 → `ÖLÇÜLEMEZ`.
Otomatik dedektör `touch_bound_lognormal.py` içinde, her çalıştırmada işaretliyor.

**Yapılacak:** Deribit put zinciri çekilecek (aynı uç nokta, `kind=option`
zaten put'ları da döndürür — dünkü çekimde filtrelenmiş).

## D-033 — Tick çözünürlüğü tabanı eklenecek
`up 100.000` basamağında PM fiyatı 0,0025, terminal 0,0004, oran 6,42.
Her iki sayı da kotasyon tick'i mertebesinde; oran piyasa görüşü değil yuvarlama
gürültüsü. Makas kuralının (D-021) küçük fiyat tarafındaki karşılığı:
**PM fiyatı tick'in birkaç katından küçükse oran üretilmez.**

## D-034 — Ürün kararları (kullanıcı onaylı, 2026-08-28)
- **Hedef kitle:** öncelik kişisel işlem aracı; site ayrıca portfolyo/marka değeri
  taşıyacak. Çelişki yok — ölçemediğinde susan bir araç, türevden anlayan bir
  okuyucuya karşı sayı uyduran bir araçtan **daha** yetkin görünür.
  Sessizlik gizlenmeyecek, iyi tasarlanacak.
- **Toplayıcı:** GitHub Actions. Ücretsiz cron, Deribit + Polymarket'e erişir,
  snapshot'ları repoya işler. Açık repo aynı zamanda metodolojiyi görünür kılar.
- **Bant:** modelsiz geniş bant. Aktarılmış kalibrasyon şimdilik kullanılmayacak.
- **V1 kapsamı:** BTC+ETH ölçülü; hisse ve emtia listede görünür, sayı yerine
  gerekçeli "ölçülemez" etiketi taşır.
- **Ekran mimarisi:** GPT önerisinin 4 ekranlı yapısı (Overview / Event detail /
  Scanner / Research) kabuk olarak alınır; motor ve ölçüm disiplini bizden kalır.
- **Arşiv V2'den V1'e alındı.** Zaman serisi, "tipik fark" referansı ve Brier
  skoru üçü de arşive bağlı; bugün başlamazsa hiç başlamaz.
- **Lead/lag analizi V3'e ertelendi.** Dakika çözünürlüğü gerektiriyor; 8 dakikalık
  kayma ölçümü %33 oynatıyordu (D-015).

## D-035 — D-032 artık teşhis değil, ÖLÇÜM (2026-08-28)
Aynı vadenin hem call hem put zinciri elde. Aynı büyüklük iki yoldan hesaplandı;
put-call paritesi gereği **aynı sayı olmak zorunda**, ayrılma doğrudan hatadır.

| zaman değeri payı | %86 | %35 | %12 | %4,8 | %1,2 | %0,4 |
|---|---|---|---|---|---|---|
| call yolu / put yolu | 1,01 | 1,01 | 1,02 | 1,04 | 1,28 | **2,09** |

Hata, zaman değeri payının **monoton** fonksiyonu. Sağlam bölgede 1,01–1,03;
derin ITM'de 2,09'a kadar patlıyor. %5 eşiği veriden doğrulandı, uydurma değil.

**Kural kesinleşti:** aşağı yön için PUT zinciri şart. Put yoksa sayı üretilmez.

## D-036 — KATMAN 2 bedava geldi: forward, put-call paritesinden
`F = K + C − P` her strike için bir forward tahmini verir. 25SEP26 zincirinde
21 strike boyunca dağılım **113,75 USD (%0,146)** — zincir iç tutarlı.
Medyan F = 77.704,64, index 77.478,56, bazis **+%0,292** (yıllık +%3,9 taşıma).

**Sonuç:** vadeli veri çekmeye gerek yok, opsiyon zinciri forward'ı kendi içinde
taşıyor. Bir veri bağımlılığı ortadan kalktı. Katman 2 doğrulandı.

## D-037 — ÖLÇÜM TABANIMIZ BAYAT; geriye dönüş YOK
5 Ağustos snapshot'ı ile bugün arasında BTC **64.638,85 → 77.478,56 (+%19,9)**.
Ayrıca 28AUG26 vadesi bugün expire oldu ve listeden düştü.

**Kritik sonuç:** Deribit `get_book_summary` yalnızca ANLIK durumu verir.
5 Ağustos'un put zinciri **geri getirilemez.** Yani D-032 düzeltmesi eski ölçüme
uygulanamıyor; ölçüm sıfırdan, **eşzamanlı** çekimle tekrarlanmalı.

Bu, arşiv kararının (D-034) en sert gerekçesi: kaçırdığımız gün kalıcı olarak kayıp.
Toplayıcı yan iş değil, doğru ölçümün ÖN KOŞULU.

## D-038 — Akış/balina verisi CANLI-DOĞRULANDI, terminoloji sabitlendi
`data-api.polymarket.com` anahtarsız çalışıyor:
- `/trades` → `proxyWallet, size, price, side, outcome, timestamp, transactionHash,
  conditionId, pseudonym, name, bio` — cüzdan bazında, işlem bazında akış. **200 OK**
- `/holders?market=<conditionId>` → pozisyon sahipleri. **200 OK**
- `clob/prices-history` → **200 ama boş** (`{"history": []}`). Parametreler yeniden
  denenmeli; çalışırsa Polymarket geçmişi hazır gelir ve aylarca birikim beklemeyiz.
- `clob/book` 404, `clob/trades` 401 (kimlik ister) — ikisi de gerekli değil.

**Terminoloji (kalıcı, D-034 ile aynı disiplin):**
Kullanılmaz: "insider", "insider wallet", "akıllı para", "balina sinyali".
Kullanılır: **büyük işlem**, **yoğunlaşmış pozisyon**, **geçmiş çözünürlük
performansı**, **cüzdan akışı**. İddia edemediğimiz şeyi isimlendirmeyiz.

## D-039 — Akış katmanı listenin ÜSTÜNDE, fiyatlama tezi DERİNLİKTE
Önceki tavsiyemi tersine çeviriyorum. Fiyatlama sayısı satırların çoğunda yok
(TSLA'da 14'ün 7'si); akış verisi ise her markette var. Bu yüzden:
- **liste katmanı** = akış (her zaman dolu, her gün değişir)
- **derinlik katmanı** = fiyatlama tezi (hak edildiği yerde çıkar)

Ayrıca ikisi birbirinin çapraz kontrolü: model "türevlere göre pahalı" derken
büyük bir adres o tarafı alıyorsa, o adres türevlerle aynı fikirde değildir.
Uyuşma gözlemi güçlendirir, çelişki araştırma sorusu doğurur.

**Not:** likidite kapısı akışa da uygulanır. 10,7 bin USD'lik merdivende "büyük
işlem" 500 USD'dir; eşik hacme göre ölçeklenmeli, sabit olmamalı.

## D-040 — Toplayıcı v2: olay bazlı depolama (2026-08-30)
v1 her koşuda her marketin son 100 işlemini yeniden saklıyordu; dosyanın neredeyse
tamamı kopyaydı. v2 üç şeyi değiştirdi ve üçü de "sonradan eklemesi pahalı"
olduğu için şimdi yapıldı:

1. **`transactionHash` ile tekilleme + su işareti.** Hangi hızda çekersek çekelim
   aynı depoya yazıyoruz. Anlık izleyici sonradan devreye girdiğinde format
   değişmeyecek.
2. **Kapsam kaydı.** Her çekim "bu marketi hangi aralıkta gördüm" yazar.
   Bu olmadan "işlem yok" ile "biz bakmıyorduk" ayırt edilemez — bildirim
   ürününde bu ayrım her şeydir.
3. **Boşluk bayrağı + sayfalama.** Su işaretine geri ulaşılamazsa `BOSLUK` konur.

**Ölçülen kazanç:** koşu başına işlem dosyası **24,9 MB → 94 KB**.
gzip ayrıca: Deribit 816→69 KB (11,8×), merdivenler 3.251→350 KB (9,3×).
Koşu süresi 4dk05 → 2dk36. Fiyat penceresi 1,28 sn.

## D-041 — Kapsam hatam ve düzeltmesi
v2'nin ilk koşusu **770 market** çekti. v1'de `[:120]` sınırı vardı, v2'yi
yazarken düşünmeden kaldırdım — proje kuralı 5'in (kapsam sessizce
genişletilmez) ihlaliydi ve fark eder etmez bildirdim.

Düzeltme: fiyat eşiği taşıyan marketler (`\$\s?\d[\d.,]{2,}`) süzülüyor.
Sonuç: **524 merdiven marketi, 248 kapsam dışı.**

**Önemli sınır:** bu bir TOPLAMA filtresidir, sınıflandırma değildir.
Kontrat tipi (terminal/touch/range) hâlâ yalnızca kural metninden belirlenir.

## D-042 — Sayfalama sorusu hâlâ AÇIK, ve bu doğru davranış
`data-api`'nin `offset` desteğini doğrulayamadık: iki koşu arasında 1 saat
geçtiği için hiçbir markette boşluk oluşmadı (`BOSLUKLU: 0`), dolayısıyla
sayfalama hiç tetiklenmedi (`sayfalama_denendi: 0`).

Bu bir eksiklik değil: mekanizma yerinde ve gereksiz yere çalışmadı.
Cevap, 8 saat aralıklı zamanlanmış koşularda en yoğun markette boşluk
oluştuğunda kendiliğinden gelecek ve `sayfalama_calisti` alanına yazılacak.

## D-043 — Repo canlı, ama yalnızca boru hattı yüklü
`github.com/DenizErginGunduz/divergence` — public, üç koşu başarılı.
Yüklü: `.github/`, `collector/`, `raw/`, `state/`.
**Eksik: `README.md`, `docs/`, `scripts/`, `.gitignore`.**
İlk yükleme denemesinde dosyalar düz geldiği için commit edilmemişti.
Portfolyo değeri README ve docs'ta olduğu için bu eksik kapatılmalı.
