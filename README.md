# Video İndirici – iPhone Kestirmesi (TikTok · YouTube Shorts · Instagram)

Bu kestirme, TikTok, YouTube (Shorts dahil) veya Instagram'da bir videoda
**Paylaş → Video İndir** dediğinde videoyu doğrudan **Fotoğraflar (galeri)**
uygulamana kaydeder. Paylaş menüsü yerine linki kopyalayıp kestirmeyi
çalıştırırsan panodaki linki de kullanır.

Nasıl çalışıyor:

| Platform | Kullanılan servis |
|---|---|
| TikTok | `tikwm.com` API (filigransız) |
| YouTube / Shorts | `cobalt` API |
| Instagram (Reels, gönderi, karusel) | `cobalt` API |

> Sadece kendi kişisel kullanımın için ve paylaşma hakkın olan videoları indir.

---

## 1. Hazırlık (bir kere)

1. iPhone'da **Kestirmeler (Shortcuts)** uygulamasını aç (yoksa App Store'dan indir).
2. **Ayarlar → Kestirmeler → Gelişmiş** bölümüne gir ve
   **"Paylaşmaya İzin Ver / Allow Sharing Large Amounts of Data"** seçeneğini aç.

## 2. Kestirmeyi oluştur

Kestirmeler → sağ üstteki **+** → en üstteki ismi **Video İndir** yap.
Sonra aşağıdaki eylemleri **sırayla** ekle (alttaki arama kutusuna eylem adını
yazıp dokunarak eklersin). Türkçe adı yanında İngilizcesi parantez içinde.

### A) Girdi ayarı
1. Kestirmenin ayarlarından (alttaki **ⓘ** simgesi) **"Paylaşım Sayfasında Göster"**
   (*Show in Share Sheet*) seçeneğini aç.
2. En üstte çıkan **"… girdi olarak al"** satırında türleri **URL** ve **Metin** yap.
3. **"Girdi yoksa"** kısmını **"Panoyu Al"** (*Get Clipboard*) olarak ayarla.

### B) Eylemler

```
1.  Girdideki URL'leri Al            (Get URLs from Input)
       Girdi: Kestirme Girdisi
2.  Listeden Öğe Al → İlk Öğe        (Get Item from List → First Item)
       → bunu "Değişken Ata" ile  link  adlı değişkene ata
3.  Metin                              (Text)
       https://COBALT-SUNUCUSU/        ← bkz. Bölüm 4
       → "Değişken Ata" ile  cobalt  adlı değişkene ata

4.  Eğer  link  "tiktok" içeriyorsa   (If … contains "tiktok")

    5.  URL                            (URL)
           https://www.tikwm.com/api/?hd=1&url=[link]
    6.  URL'nin İçeriğini Al           (Get Contents of URL)   – Yöntem: GET
    7.  Sözlük Değerini Al             (Get Dictionary Value)
           Anahtar: data.hdplay
    8.  Eğer  Sözlük Değeri  "değeri yok" ise  (If … does not have any value)
            9.  Sözlük Değerini Al  – Anahtar: data.play   (6. adımın çıktısından)
           10.  Değişken Ata → video_url
        Değilse (Otherwise)
           11.  Değişken Ata → video_url   (7. adımın çıktısı)
        Eğer Sonu
   12.  URL'nin İçeriğini Al  → video_url
   13.  Fotoğraf Albümüne Kaydet       (Save to Photo Album) – Albüm: Son Öğeler

    Değilse (Otherwise)                ← YouTube & Instagram

   14.  URL'nin İçeriğini Al           (Get Contents of URL)
           URL:    cobalt
           Yöntem: POST
           Başlıklar (Headers):
              Accept        → application/json
              Content-Type  → application/json
           İstek Gövdesi: JSON
              url           (Metin)  → link
              videoQuality  (Metin)  → 1080
   15.  Değişken Ata → cevap
   16.  Sözlük Değerini Al – Anahtar: status   (cevap'tan)

   17.  Eğer  status  "picker" ise     ← Instagram karusel (birden çok medya)
           18. Sözlük Değerini Al – Anahtar: picker  (cevap'tan)
           19. Her Biri İçin Tekrarla  (Repeat with Each)
                  20. Sözlük Değerini Al – Anahtar: url  (Tekrarlanan Öğe)
                  21. URL'nin İçeriğini Al
                  22. Fotoğraf Albümüne Kaydet
               Tekrar Sonu
       Değilse (Otherwise)
           23. Eğer  status  "error" ise
                  24. Uyarı Göster: "İndirilemedi: " + cevap   (Show Alert)
                  25. Kestirmeyi Durdur (Stop This Shortcut)
               Eğer Sonu
           26. Sözlük Değerini Al – Anahtar: url  (cevap'tan)
           27. URL'nin İçeriğini Al
           28. Fotoğraf Albümüne Kaydet
       Eğer Sonu

    Eğer Sonu

29. Bildirim Göster: "Video galeriye kaydedildi ✅"   (Show Notification)
```

> İpucu: `[link]` gibi köşeli parantezli yerlerde metnin içine dokunup klavyenin
> üstündeki değişken çubuğundan ilgili değişkeni seçiyorsun.

## 3. Kullanım

- **TikTok:** videoda **Paylaş → Diğer (…)/Paylaş** → **Video İndir**.
  (TikTok'ta paylaş menüsünde göremezsen **Bağlantıyı Kopyala** de ve kestirmeyi
  Kestirmeler uygulamasından ya da ana ekrandan çalıştır – panodaki linki alır.)
- **YouTube / Shorts:** **Paylaş → Diğer → Video İndir**.
- **Instagram:** **Paylaş (uçak simgesi) → Paylaş… / Bağlantıyı Kopyala** → **Video İndir**.

İlk çalıştırmada iPhone "tikwm.com'a / sunucuya bağlanmaya izin ver" ve
"Fotoğraflara eriş" diye soracak → **Her Zaman İzin Ver** de.

**Kolaylık:** Ayarlar → Erişilebilirlik → Dokunma → **Arkaya Dokunma** →
İki Kez Dokunma → **Video İndir**. Linki kopyala, telefonun arkasına iki kere vur, bitti.

## 4. Cobalt sunucusu (YouTube + Instagram için)

YouTube ve Instagram için ücretsiz, açık kaynaklı **cobalt** API'si kullanılıyor.
Resmî `api.cobalt.tools` artık doğrulama istiyor, bu yüzden 3. adımdaki metne
**herkese açık bir cobalt sunucusu** adresi yazman gerekiyor:

1. Tarayıcıda **https://instances.cobalt.best** sayfasını aç.
2. Listede YouTube ve Instagram sütunları ✅ olan, *"auth"* gerektirmeyen bir
   sunucunun **API adresini** kopyala (örn. `https://xxxx.example.com/`).
3. Kestirmedeki 3. adımın metnine yapıştır (sonunda `/` olsun).

Bir gün YouTube/Instagram indirmesi "error" verirse sadece bu adresi başka bir
sunucuyla değiştirmen yeterli. TikTok kısmı bundan etkilenmez.

## Sorun giderme

| Sorun | Çözüm |
|---|---|
| Paylaş menüsünde "Video İndir" yok | ⓘ → *Paylaşım Sayfasında Göster* açık mı? Paylaş menüsünün en altında **Eylemleri Düzenle**'den ekle. |
| "error.api.auth…" hatası | Seçtiğin cobalt sunucusu anahtar istiyor → listeden başka sunucu seç. |
| Video yerine dosya/yazı kaydediliyor | 12/21/27. adımlarda doğru değişkene (`video_url` / `url`) bağlandığından emin ol. |
| Gizli hesap / yaş kısıtlı video | Bu servisler giriş gerektiren içerikleri indiremez. |

---

# Klip Botu (Kick → YouTube Shorts + TikTok)

`clipbot/` klasörü Kick kliplerini indirir, dikey formatta edit eder (üstte kamera, altta ekran),
YouTube Shorts ve TikTok'a aynı anda yükler, sonra videoyu siler.
GitHub Actions üzerinde `queue/` klasörüne eklenen her iş dosyası için çalışır.
Kurulum için bkz. [docs/KURULUM.md](docs/KURULUM.md).
