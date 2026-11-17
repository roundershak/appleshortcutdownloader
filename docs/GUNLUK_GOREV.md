# Günlük klip görevi (Claude için talimat)

Bu dosya, her gün otomatik çalışan Claude oturumunun yapacağı işi tarif eder.
Amaç: Eray'ın (ve izinli yayıncıların) yeni Kick yayınlarından viral klip adaylarını bulmak, kesmek,
kadrajını doğrulamak ve `hazir/` kuyruğuna eklemek. Yüklemeyi `.github/workflows/scheduler.yml` gün içine yayarak yapar.

## 0. Hazırlık
```bash
pip install -q "yt-dlp[default,curl-cffi]" curl_cffi "opencv-python-headless>=4.9,<5" numpy requests faster-whisper
git fetch origin && git checkout claude/apple-extension-video-download-milmr6 && git pull
```
Çalışma dosyaları için scratchpad kullan, videoları repoya koyma, iş bitince sil.

## 1. Yeni yayın var mı?
- `state/islenen.json` dosyasında işlenmiş VOD id'leri var.
- `https://kick.com/api/v2/channels/eray/videos` adresinden son yayınları al. Listede olmayan **ve bitmiş** yayınları işle.
  Canlı yayın sürüyorsa (`/api/v2/channels/eray` içinde `livestream` doluysa) en son yayını atla, yarın işlenir.
- Yeni yayın yoksa işlem yapma ve kısa bir not bırakarak bitir.

## 2. Analiz (her yeni yayın için)
1. `python tools/kick_chat.py eray <index> chat.jsonl`: chat tekrarını indirir. Düşük hızda çalışır,
   paralel birden fazla indirme başlatma.
2. Yayının hangi bölümünde ne var, görmek için her 30 dakikadan bir kare alıp ızgara yap (`docs/ANALIZ.md`'deki yöntem).
3. `python tools/chat_peaks.py chat.jsonl --top 25 --json peaks.json`
4. GTA, face to face, parkur ya da ekipli oyun bölümleri varsa o aralığı yazıya dök:
   `python tools/transcribe_range.py <uuid> <bas> <bit> tr.jsonl`, ardından
   `python tools/moments.py chat.jsonl tr.jsonl --top 15`.
   Diğer bölümler için: `python tools/inspect_many.py peaks.json out 12`.
5. Konuşma metnini oku ve gerçekten komik, kavgalı, sinirli ya da bağırmalı anları seç.
   **Bağlam bilmeden anlaşılmayan anları ve uzun hikayeleri ele.** Çocuk istismarı belgeseli, üçüncü kişilerin özel
   bilgileri, nefret söylemi ve +18 içerik gibi hassas konulara girme.

## 3. Klip seçimi ve kesim
- Günde **4–6 klip**. Süre 20–50 sn. Chat zirvesinden ~30 sn önce başlat, olay bitince ~5–10 sn sonra kes.
- Kamera konumu yayın içinde değişiyor. Her klip için kaynaktan kare alıp kameranın piksel kutusunu ölç
  (`[x, y, w, h]`, 1920x1080). Sonra `clipbot.edit.plan_layout` + `preview` ile önizleme kar ve **mutlaka gözle kontrol et**:
  üstte yüz, altta oyun ya da ekran olmalı.
- Kamera tam ekransa (IRL, stüdyo) `"layout": "full"` kullan.

## 4. Başlık ve etiket stili
- Küçük harf, kısa anlatım: "eray ... yapıyor". Sonuna ünlem, "..." ya da chat'teki gibi klavye-basma gülme
  (ASDKJASLD) ekle.
- **Emoji az kullan:** her 4 başlıktan en fazla 1'inde, o da tek emoji olsun.
- Etiketler `config/streamers.json` dosyasından otomatik gelir. Klibe özel olarak 1–2 etiket ekle (örn. `gta5`).
- Örnekler: "eray mapi yapana sövüyor ASDKJSADLKJASD", "eray: vur vur öldür onu!!", "eray gta 5'e veda ediyor... 😭"

## 5. Kuyruğa ekle
`hazir/` klasörüne iş dosyası yaz. Dosya adı `YYYYMMDD-NN-kisa-ad.json` olsun, sıralama yükleme sırasını belirler.
Format:
```json
{"vod": "<uuid>", "streamer": "eray", "start": 12345, "end": 12380, "cam": [0,256,450,252],
 "title": "...", "hashtags": ["gta5"], "tags": ["gta 5"], "platforms": ["youtube","tiktok"],
 "tiktok_mode": "draft", "youtube_privacy": "public"}
```
Sonra işlenen VOD id'sini `state/islenen.json` dosyasına ekle, commit et ve `claude/apple-extension-video-download-milmr6` dalına
push et. Aynı commit'i `claude/gracious-faraday-a8x570` dalına da gönder.

## 6. Kontrol
- `hata/` klasöründe dosya varsa `.sonuc.txt` dosyasına bak. Kadraj ya da kesim hatasıysa düzeltip `hazir/` klasörüne geri koy.
  Token hatasıysa bunu not et.
- `hazir/` klasöründe 15'ten fazla klip birikmişse o gün yeni klip ekleme.
