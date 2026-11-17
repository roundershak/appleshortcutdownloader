# Klip Botu – Kurulum (bir kerelik)

Bu kurulumdan sonra sohbete Kick klip linkini atman yeterli. Claude klibi
inceler, kadrajı ayarlar ve `queue/` klasörüne bir iş dosyası ekler.
GitHub Actions da klibi **indirir, dikey edit yapar (üstte kamera, altta ekran),
YouTube Shorts ve TikTok'a başlık ve etiketlerle yükler, sonra videoyu siler.**
Videolar ne telefonuna ne de başka bir yere kaydedilir.

Şifreler ve token'lar sohbete **yazılmaz**. Hepsi şuraya girilir:
**GitHub → bu repo → Settings → Secrets and variables → Actions → New repository secret**

---

## 1. YouTube (kalıcı erişim)

### 1.1 Google Cloud projesi
1. https://console.cloud.google.com adresine **kanalın bağlı olduğu Google hesabıyla** gir.
2. Üstten **Yeni proje** oluştur (adı örneğin `klip-bot`).
3. **APIs & Services → Library** bölümünde **YouTube Data API v3**'ü bul ve **Enable** de.

### 1.2 OAuth izin ekranı ⚠️ (token'ın süresiz olması için en önemli adım)
1. **APIs & Services → OAuth consent screen** (veya **Google Auth Platform**) bölümüne gir.
2. User type olarak **External** seç. Uygulama adı ve e-posta alanlarını doldur.
3. **Audience / Test users** kısmına kendi Gmail adresini ekle.
4. **Publishing status** ayarını **"In production"** yap (**Publish app** butonu).
   - Bu ayar **"Testing"** olarak kalırsa token **7 günde bir ölür**. Asıl sebep bu.
   - "Production" modunda doğrulama gerekmez. Giriş yaparken bir "Google bu uygulamayı
     doğrulamadı" uyarısı çıkar, **Gelişmiş → klip-bot'a git** demen yeterli.

### 1.3 OAuth istemcisi
1. **Credentials → Create credentials → OAuth client ID** yolunu izle.
2. Tür olarak **Web application** seç.
3. **Authorized redirect URIs** alanına şunu ekle: `https://developers.google.com/oauthplayground`
4. Çıkan **Client ID** ve **Client secret** değerlerini GitHub secret olarak kaydet:
   - `YT_CLIENT_ID`
   - `YT_CLIENT_SECRET`

### 1.4 Refresh token (bir kere alınır, bir daha yenilenmez)
1. https://developers.google.com/oauthplayground adresini aç.
2. Sağ üstteki ⚙️ simgesine bas, **Use your own OAuth credentials** seçeneğini işaretle
   ve Client ID ile secret'ı yapıştır.
3. Soldaki kutuya `https://www.googleapis.com/auth/youtube.upload` yaz ve **Authorize APIs** de.
4. **Kanalın hesabını** seç ve izin ver. Hesabın birden fazla kanalı varsa doğru kanalı seç.
5. **Exchange authorization code for tokens** butonuna bas.
6. Çıkan **Refresh token** değerini `YT_REFRESH_TOKEN` secret'ı olarak kaydet.

Bu token, şifreni değiştirmediğin ve izni kaldırmadığın sürece kalıcıdır.
Tek koşul: 6 ay hiç kullanılmazsa geçersiz olur.

### 1.5 Videoların "Özel" kalmaması için: API denetimi
Google, denetlenmemiş projelerden yüklenen videoları **Özel** olarak kilitler.
Daha önce yaşadığın sorun büyük ihtimalle buydu.
- Formun adresi: https://support.google.com/youtube/contact/yt_api_form
  (seçenek: *"I would like to request an API audit"*). Ücretsizdir.
- Kullanım amacı olarak şunu yazabilirsin: *"İzinli yayıncıların klip kanalımı yöneten kişisel
  yükleme aracı; yalnızca kendi kanalıma video yüklüyor."*
- Denetim bitene kadar bot yine çalışır, sadece videolar "Özel" kalır.

**Kota:** Günde varsayılan 10.000 birim var, bir yükleme yaklaşık 1.600 birim tutuyor.
Yani günde **6 civarı Shorts** atılabilir. Denetim formunda kota artışı da isteyebilirsin.

---

## 2. TikTok

1. https://developers.tiktok.com adresinde TikTok hesabınla geliştirici hesabı aç ve **Create app** de.
2. **Products** kısmına **Login Kit** ve **Content Posting API** ekle.
   Content Posting içinde **Direct Post** seçeneğini aç.
3. Scope olarak `user.info.basic`, `video.publish` ve `video.upload` seç.
4. **Redirect URI** olarak https ile başlayan bir adres gir. Bu adresi GitHub'a
   `TIKTOK_REDIRECT_URI` secret'ı olarak kaydet.
5. `TIKTOK_CLIENT_KEY` ve `TIKTOK_CLIENT_SECRET` değerlerini kaydet.
6. Yetki kodunu almak için Claude'un vereceği yetki linkini aç ve onayla. Açılan sayfanın
   adres çubuğundaki `code=` değerini `TIKTOK_AUTH_CODE` secret'ı olarak kaydet.
   İlk çalışmada bot bu kodu kalıcı token'a çevirir.
7. **GH_PAT**: Bot, TikTok token'ı yenilendiğinde secret'ı kendisi güncellesin diye gerekli.
   GitHub → Settings → Developer settings → **Fine-grained token** yolunu izle.
   Sadece bu repo için **Secrets: Read and write** iznini ver ve süreyi **No expiration** seç.
   Bu token'ı `GH_PAT` secret'ı olarak kaydet. Böylece TikTok tarafında da elle token yenilemen gerekmez.

**Denetim:** TikTok, uygulama denetlenene kadar API ile atılan videoları
**"Sadece ben"** olarak yayınlar. **Submit for review** ile denetime gönder.
Onaylanınca videolar herkese açık gider.
O zamana kadar iş dosyasında `"tiktok_mode": "draft"` kullanılabilir. Bu modda video,
başlıkla birlikte TikTok uygulamana taslak bildirimi olarak düşer ve tek dokunuşla paylaşırsın.

---

## 3. Secret listesi (özet)

| Secret | Nereden |
|---|---|
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET` | Google Cloud → Credentials |
| `YT_REFRESH_TOKEN` | OAuth Playground |
| `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` | TikTok Developers → App |
| `TIKTOK_REDIRECT_URI` | Uygulamaya girdiğin redirect adresi |
| `TIKTOK_AUTH_CODE` | Tek seferlik yetki kodu |
| `GH_PAT` | GitHub fine-grained token |

---

## 4. İş dosyası formatı (`queue/*.json`)

```json
{
  "url": "https://kick.com/eray/clips/clip_XXXX",
  "title": "Eray kasadan bıçak çıkardı",
  "hashtags": ["csgo"],
  "tags": ["cs2 kasa açılımı"],
  "platforms": ["youtube", "tiktok"],
  "tiktok_mode": "direct",
  "youtube_privacy": "public",
  "cam": [0.0, 0.0, 0.222, 0.219],
  "game": null,
  "start": null,
  "end": null
}
```

- `cam` / `game`: kaynak videodaki bölge, `[x, y, genişlik, yükseklik]` olarak 0–1 arası oranlar.
  Boş bırakılırsa `config/streamers.json` ayarları ya da otomatik yüz algılama kullanılır.
- `layout: "full"`: Kamera yoksa video ortaya, arkasına bulanık arka plan konur.
- `start` / `end`: Saniye cinsinden kırpma.
