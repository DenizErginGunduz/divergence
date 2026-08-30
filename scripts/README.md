# scripts/ — ölçüm ve doğrulama betikleri

Bunlar ürün kodu değil. Her biri **tek bir iddiayı sınamak** için yazıldı ve
sonucu `../docs/DECISIONS.md` içinde bir karar numarasına bağlı.

## Dizin

| Betik | Ne yapar | Dış veri | Karar |
|---|---|---|---|
| `layer1_consistency.py` | Kova merdiveni ile eşik merdivenini birbirine karşı test eder: `P(S_T > K_j) = Σ P(kova_i)` | **gerekmez** | Katman 1 |
| `ladder_health.py` | Opsiyona geçmeden önceki ön kontrol: makas/ölçüm oranı, monotonluk, çözülmüş market tespiti | **gerekmez** | D-021, D-022, D-023 |
| `skew_correction_btc.py` | Aynı merdiveni üç yöntemle hesaplar (naif N(d2) / skew düzeltmeli / modelsiz dijital) ve sapmayı ölçer | Deribit | D-027, D-029 |
| `touch_premium_v2.py` | Katman 3'ü düzeltilmiş paydayla yeniden hesaplar; sert alt sınır ve üst sınır ayrı sayılır | Deribit + Polymarket | D-030 |
| `touch_bound_lognormal.py` | Üst sınır "2" sabitini lognormal tam formülle değiştirir; ölçülemeyen basamakları eler | Deribit | D-031, D-032 |
| `put_vs_itmcall_test.py` | Aynı olasılığı put ve derin ITM call yollarından hesaplayıp farkı ölçer; ayrıca paritedan forward çıkarır | Deribit | D-035, D-036 |

## Üç uyarı

**1. Bu betikler tarih damgalı yerel dosyalara bakıyor.**
Yazıldıkları sırada toplayıcı yoktu; `raw/` altındaki elle çekilmiş CSV'leri
okuyorlar. Depodaki güncel `raw/` yapısı (toplayıcının ürettiği `.json.gz`)
farklıdır. Olduğu gibi çalıştırılamazlar; **kanıt kaydı olarak duruyorlar.**

**2. Bazı betikler bilerek burada değil.**
`bridge_btc.py` ve `touch_premium_btc.py` naif `N(d2)` kullanıyordu ve
sonuçları D-027 ile geçersiz kılındı. `fair_band_equity.py` derin ITM call'dan
IV türetiyordu (D-025). Yerlerine geçen sürümler yukarıdaki tabloda.

**3. Ölçüm tabanı bayat (D-037).**
Bu betiklerin dayandığı 5 Ağustos verisinden bu yana BTC %19,9 hareket etti ve
o günün put zinciri geri getirilemiyor. Sonuçlar yöntemin doğruluğunu gösterir,
güncel piyasa durumunu göstermez. Eşzamanlı yeniden ölçüm bekliyor.

## Neden hepsi duruyor

Yanlış çıkan sonuçları silmiyoruz. Bir yöntemin nerede ve neden çöktüğünü
gösteren ölçüm, çalışan yöntemin kendisi kadar değerli — `DECISIONS.md` de
aynı mantıkla geri çekilen sonuçları içeriyor.
