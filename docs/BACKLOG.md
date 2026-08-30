# BACKLOG — uygulanmayan, kaydedilen fikirler

Kapsam genişletme kuralı gereği bunlar uygulanmadı, buraya yazıldı.

## B-001 — Varlık evrenini hisse senetlerine genişletmek
Gerekçe: ücretsiz opsiyon verisinin en bol olduğu yer ABD hisseleri; emtia en zor yer.
Polymarket'te hazır merdivenler var (hepsi aylık, hepsi touch, Pyth/normal seans):
TSLA 14, NVDA 14, META 14, SPY 14, AAPL 10, MSFT 7, AMZN 7, GOOGL 6 basamak.
Uyarı: MSFT/AMZN/GOOGL hacimleri çok ince (827 / 1.185 / 2.740 USD toplam).
Bu hacimlerde makas, ölçülen farktan büyük olabilir.

## B-002 — Emtia için ETF vekilleri (GLD / SLV / USO)
CME opsiyon verisi lisanslı. ETF opsiyonları ücretsiz kanaldan gelir.
Bedeli: taşıma maliyeti farkı, gider oranı, ve USO'da rulo aşınması.
**USO uzun vadeli WTI vekili DEĞİLDİR** — contango'da sistematik sapar.

## B-003 — Geçmiş biriktirme boru hattı
D-009'daki referans metriği için gerekli. Günlük/haftalık marketler doğup ölüyor;
sonradan geri dönüp çekilemiyor. Her snapshot saklanmalı. Ücretsiz, ama tasarım ister.
**TAMAMLANDI 2026-08-30** — bkz. D-034, D-040. Toplayıcı GitHub Actions'ta çalışıyor.

## B-004 — Kalshi envanteri (ikinci platform)
Amaç: SPX/NDX boşluğu ve aynı vadede touch+terminal çifti bulmak.
Kapsamı bilinmiyor, API anahtar isteyebilir.

## B-005 — Touch primi için model katmanı
Yansıma ilkesi ve varyantları. Katman 3'ü açar ama model riski getirir.
Katman 4 çalışmadan başlanmamalı.
**Kısmen ele alındı D-031** — "2" sabiti lognormal tam formülle değiştirildi.

## B-006 — Alış-satış makası eşiği
Hangi makasın üstünde "gösterme" denecek? Ölçülen fark makastan küçükse sayı yanıltır.
**Karar verildi D-021** — makas ≤ 0,02 ve mid < 0,99. Ayrıca D-033: tick tabanı.

## B-007 — Anlık izleyici ve bildirim (2026-08-30)
Büyük işlem ve yoğunlaşmış pozisyon hareketlerinde bildirim. Ayrı bir süreç olacak;
arşivle AYNI olay formatına yazacak (D-039, D-040). Actions cron 5 dakikadan sık
olamaz ve gecikebilir, o yüzden gerçek anlık izleme için sürekli çalışan bir süreç
gerekir. Ölçüm: en yoğun market 156 işlem/saat, geri kalanı çok yavaş — acele yok.

## B-008 — clob/prices-history ile Polymarket fiyat geçmişi
İlk denemede 200 döndü ama boş (`{"history": []}`). Parametreler yeniden denenmeli.
Çalışırsa aylarca birikim beklemeden geçmiş seri elde ederiz; bu, zaman serisi
grafiğini ve "tipik fark" referansını çok öne çeker.
