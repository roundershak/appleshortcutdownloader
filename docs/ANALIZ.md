# Eray – Yayın ve Klip Analizi (17 Kasım 2026)

## Kaynaklar
- **Kick:** son 4 yayının (13–15 Kasım, yaklaşık 30 saat) **chat tekrarının tamamı**, 5 saniyelik dilimler halinde indirildi
  (yaklaşık 21.000 pencere). Ses seviyesi ölçüldü ve Whisper ile konuşma metni çıkarıldı.
- **YouTube GTA V playlist'i (60 video):** en çok izlenen 10 videonun "en çok tekrar izlenen"
  grafikleri ve zaman damgalı yorumları incelendi.

## İzleyicinin sevdiği şey (YouTube'dan)
Playlist başlıklarının neredeyse hepsi aynı kalıpta: **KAVGA, SİNİR, KAOS, ALT F4, KÜFÜR, DOSTLUK BOZAN.**
En çok beğeni alan zaman damgalı yorumlar şu anlara ait:
- **Taklitler ve sataşmalar:** "çok iyi taklit 😂" (17👍), "erayın zorbalık yapması daha eğlenceli" (53👍)
- **Ekip içi hakaret ve sinir anları:** "AYBOYA AĞIZA ALINMAYACAK HAKARET", "Eray abi Tolunay abiye azıcık kızdı"
- **Aynı yerde art arda düşme / parkurda sinir krizi:** "BİR insan nasıl aynı yerde art arda 4 kere düşebilir"
- **Herkesin aynı anda bağırdığı kaos:** "hepsi aynı anda konuşuyor ... gülmekten çalışamadım"
- **Hikayeler** (Apo'nun hikayeleri). Bunlar uzun içerik, Shorts için zayıf.

Tekrar izleme grafiğinin zirveleri ile yorumlardaki zaman damgaları aynı anlara denk geliyor.

## Kick chat'i ne söylüyor
- Chat'in normalde yaklaşık %5–20'si gülme emote'u atıyor (KEKW, GoldenKEKW, wideKEKW, LULW, ICANT ya da klavyeye
  rastgele basma: "ASDJKASJD"). **Viral anlarda bu oran %60–90'a çıkıyor.**
- GTA bölümünde gülme oranı zaten sürekli yüksek, ortalama %48.
- Klip adayı için en iyi sinyal üçünün birlikte görülmesi:
  **chat gülmesinin ani yükselmesi + Eray'ın sesinin ortalamanın 8–15 dB üstüne çıkması + küfür/"lan/oğlum" yoğunluğu.**
- Chat olaya 5–15 saniye geç tepki veriyor. Bu yüzden klipler, chat'in patladığı andan yaklaşık 30 saniye önce başlatılıyor.

## Yayınların içeriği
| Yayın | İçerik |
|---|---|
| 15 Kas – "GTA 5 ELVEDA" (11,5 saat) | Sohbet, belgesel, **3:15–6:00 arası GTA 5 (parkur ve face to face)**, CS2, bir temizlik oyunu |
| 13 Kas (9,6 saat) | Sohbet, simülasyon oyunları, CS2 |
| 12 Kas gece (2,6 saat) | Sohbet |
| 12 Kas (6,2 saat) | Sohbet, **stüdyoda arkadaşlarla direksiyon/ETS (IRL)**, platform oyunu |

## Hazır klipler (`hazir/` klasörü)
| # | Yayın anı | Ne oluyor | Chat |
|---|---|---|---|
| 1 | 5:04:50 | Parkuru yapana sövüyor: "Senin kurduğun mapin a.k." | %69 gülme, "ROLLENME YA" |
| 2 | 5:16:58 | "6 yıldır küfürüyorsun lan bunlara". Hobbit'in parkurlarına isyan | %70 gülme |
| 3 | 5:07:58 | Geçemiyor: "aptalın oğlu, gerizekalısın, cüce" | "NİYE GEÇEMİYON BURAYI" |
| 4 | 3:16:52 | GTA 6 tartışması kavgaya dönüyor: "Ben sana hakaret ettim mi?" | "Kavga çıktı" |
| 5 | 4:00:40 | Face to face'te çığlık ve kaos: "ne oluyor ya bana" | +11 dB, %82 gülme |
| 6 | 4:02:55 | "Aptal!", "Öl!" | "BARON KIZDI", "VUR VUR ÖLDÜR ONU" |
| 7 | 3:37:33 | Roleplay "Alo bebeğim…" bölümü "Kaç kere yapacağım bunu!" diye bitiyor | %77 gülme |
| 8 | 3:53:38 | Yayının en yüksek sesli anı | "İŞTE BUUU", "gururlu göz yaşı" |

## İkinci sıradaki adaylar (henüz kesilmedi)
- 12 Kas 3:00:30 (stüdyoda IRL): "Salan sordu… Gerizekalı." Chat'in %88'i gülüyor.
- 12 Kas 5:21:50: "Lan öldürürüm lan!" Ekip birlikte zıplarken düşürüyorlar.
- 15 Kas 9:54:15: Apo'ya "kral olsan" muhabbeti. Chat'in %79'u gülüyor (taban %11).

## Araçlar
- `tools/kick_chat.py`: Kick yayın tekrarı chat'ini indirir.
- `tools/chat_peaks.py`: Chat'teki gülme, hype ve sinir zirvelerini bulur.
- `tools/transcribe_range.py`: Yayından bir aralığı yazıya döker ve ses seviyesini ölçer.
- `tools/moments.py`: Chat, ses ve konuşmayı birleştirip anları sıralar.
- `tools/inspect_peak.py` / `inspect_many.py`: Seçilen zirvenin metnini ve karelerini çıkarır.
- `tools/yt_analyze.py` + `.github/workflows/analyze.yml`: YouTube tekrar izlenme grafiğini ve yorumları analiz eder (GitHub üzerinde çalışır).
