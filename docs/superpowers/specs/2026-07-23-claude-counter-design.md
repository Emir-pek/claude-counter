# claude-counter — Tasarım Dokümanı

**Tarih:** 2026-07-23
**Durum:** Onaylandı, uygulamaya hazır

## 1. Amaç

Claude aboneliğinin **5 saatlik** ve **haftalık** kullanım limitlerini, her zaman
ekranın üstünde duran küçük bir masaüstü widget'ında gösteren bir uygulama.
Her limit için:

- Harcanan yüzde (renkli ilerleme çubuğu)
- Limitin ne kadar sürede yenileneceği (canlı geri sayım)

Bu, Claude Code'un `/usage` komutunun gösterdiği bilginin bağımsız, sürekli
görünür bir penceredeki karşılığıdır.

## 2. Veri Kaynağı (doğrulandı)

Veri, Claude Code'un kendi kullandığı özel OAuth endpoint'inden gelir:

```
GET https://api.anthropic.com/api/oauth/usage
Authorization: Bearer <accessToken>
Content-Type: application/json
timeout: 5000 ms
```

Access token, `~/.claude/.credentials.json` içindeki
`claudeAiOauth.accessToken` alanından okunur (Windows'ta:
`C:\Users\<kullanıcı>\.claude\.credentials.json`).

### Örnek yanıt (gerçek çağrıdan, kısaltılmış)

```json
{
  "five_hour":  { "utilization": 30.0, "resets_at": "2026-07-23T21:09:59.349625+00:00" },
  "seven_day":  { "utilization": 71.0, "resets_at": "2026-07-25T10:00:00.349653+00:00" },
  "limits": [
    { "kind": "session",     "group": "session", "percent": 30, "severity": "normal",
      "resets_at": "2026-07-23T21:09:59.349625+00:00", "is_active": false },
    { "kind": "weekly_all",  "group": "weekly",  "percent": 71, "severity": "normal",
      "resets_at": "2026-07-25T10:00:00.349653+00:00", "is_active": true }
  ]
}
```

İhtiyacımız olan alanlar: `five_hour.utilization`, `five_hour.resets_at`,
`seven_day.utilization`, `seven_day.resets_at`. (`limits` dizisi de aynı bilgiyi
yapısal olarak taşır; birincil kaynak `five_hour` / `seven_day` nesneleridir,
`limits` yedek olarak kullanılabilir.)

### Bilinen riskler

- **Özel/dokümante edilmemiş endpoint.** Abonelik 5s/haftalık limitleri public
  API'de yok; tek kaynak `/usage`'ın kullandığı bu özel endpoint. Bir Claude Code
  güncellemesiyle değişebilir/bozulabilir.
- **Token yaşam döngüsü bize ait değil.** Token'ı biz yenilemiyoruz. Her istekte
  `.credentials.json` yeniden okunur; token'ı taze tutan Claude Code'un kendi
  mekanizmasıdır. Bu yalnızca Claude Code token'ı yenilerken geçerlidir.

## 3. Teknoloji

- **Dil/Runtime:** Python 3.11 (sistemde kurulu).
- **GUI:** CustomTkinter (koyu tema, yuvarlatılmış köşeler, şık ilerleme çubukları).
  Tek dış bağımlılık: `pip install customtkinter`.
- **Ağ:** Python standart kütüphanesi (`urllib.request`) — ekstra bağımlılık yok.

## 4. Mimari

Sorumluluğu ayrılmış üç küçük modül:

```
claude-counter/
├── usage_client.py   # Veri katmanı: token oku + API çağrısı + parse
├── app.py            # UI katmanı: CustomTkinter penceresi
├── main.py           # Başlangıç noktası
└── requirements.txt  # customtkinter
```

### 4.1 `usage_client.py` (veri katmanı, UI'dan bağımsız)

Sorumluluk: kimlik + ağ + parse. Tkinter'a hiçbir bağımlılığı yok, tek başına
test edilebilir.

- `read_token() -> str` — `.credentials.json`'dan access token'ı okur.
- `fetch_usage() -> UsageData` — endpoint'e GET atar, yanıtı parse eder.
- Dönen veri sade bir yapıdır:

  ```python
  @dataclass
  class Window:
      utilization: float          # 0..100
      resets_at: datetime         # timezone-aware (UTC)

  @dataclass
  class UsageData:
      five_hour: Window | None
      seven_day: Window | None
      fetched_at: datetime        # yerel saat

  @dataclass
  class UsageError:
      kind: str                   # "no_credentials" | "unauthorized" | "network" | "bad_response"
      message: str                # kullanıcıya gösterilecek kısa mesaj
  ```

- `fetch_usage()` başarısız olursa exception fırlatmak yerine `UsageError` döner
  (ya da açık bir Result tipi); UI bunu ekrana durum mesajı olarak yansıtır.

### 4.2 `app.py` (UI katmanı)

Sorumluluk: pencereyi çizmek ve durumu göstermek.

- ~260×150 px, her zaman üstte (`-topmost`), sade/çerçevesiz, başlığından
  sürüklenebilir küçük pencere.
- İki bölüm (5 saatlik, haftalık); her biri: etiket + renkli ilerleme çubuğu +
  yüzde + yenilenme geri sayımı.
- Sağ üstte ↻ elle yenileme butonu; en altta "güncellendi: HH:MM".
- `render(UsageData)` ve `render_error(UsageError)` gibi net giriş noktaları.

### 4.3 `main.py` (başlangıç noktası)

Sorumluluk: modülleri birbirine bağlamak, zamanlayıcıları kurmak, uygulamayı
başlatmak.

## 5. Veri Akışı ve Zamanlama

- **Token:** Her istekte `.credentials.json` yeniden okunur (bkz. §2 riskler).
- **Ağ döngüsü:** 60 saniyede bir arka planda `fetch_usage()` çağrılır.
- **Elle yenileme:** ↻ butonu anında `fetch_usage()` tetikler ve 60 sn'lik
  zamanlayıcıyı sıfırlar.
- **Geri sayım:** "kalan süre", `resets_at` ile "şimdi" arasından her saniye
  **yerelde** hesaplanır — ağa gidilmez. Sayaçlar akıcı ilerler, trafik azdır.
- **Thread güvenliği:** Ağ isteği UI thread'ini kilitlememek için ayrı bir
  thread'de yapılır; sonuç Tkinter'ın thread-güvenli mekanizmasıyla
  (`after()` ile ana thread'e sıralama) UI'a aktarılır.

## 6. Hata Yönetimi

Uygulama hiçbir durumda çökmez; sorun olursa durumu gösterir:

| Durum | Davranış |
|---|---|
| `.credentials.json` yok / token okunamıyor | "Claude oturumu bulunamadı", çubuklar gri |
| 401 (token süresi dolmuş) | "Oturum süresi dolmuş — Claude Code'da giriş yapın" |
| Ağ hatası / timeout (5 sn) | Son başarılı veri ekranda kalır; "güncellendi" solar, "bağlantı yok" eklenir; 60 sn sonra tekrar denenir |
| Beklenmedik yanıt yapısı | Eksik alanı olan limit "—" gösterir; diğer limit etkilenmez |

Genel ilke: bir istek başarısız olsa bile uygulama ayakta kalır ve bir sonraki
döngüde kendini toparlar.

## 7. Görünüm

Koyu tema, ~260×150 px:

```
┌ Claude Kullanımı        ↻ ┐
│                            │
│ 5 saatlik                  │
│ ▓▓▓░░░░░░░  30%   ⟳ 1s 12dk│
│                            │
│ Haftalık                   │
│ ▓▓▓▓▓▓▓░░░  71%   ⟳ 1g 12s │
│                            │
│ güncellendi: 21:42         │
└────────────────────────────┘
```

- **Çubuk rengi eşiği:** yeşil (<%60), sarı (%60–85), kırmızı (>%85).
- **Geri sayım biçimi:** kalan süreye göre "1g 12s", "1s 12dk", "12dk", "yenilendi".
- Pencere her zaman üstte, başlığından tutup sürüklenebilir.

## 8. Test

`usage_client.py` UI'dan bağımsız olduğu için asıl mantık kolayca test edilir:

- **Parse testi:** örnek JSON (§2) → doğru `utilization` ve `resets_at`.
- **Geri sayım biçimlendirme testi:** verilen `resets_at` + "şimdi" için
  "1s 12dk", "1g 12s" doğru mu; süre geçtiyse "yenilendi" mi.
- **Renk eşiği testi:** %30→yeşil, %71→sarı, %90→kırmızı.
- **Hata yolları:** token yok / 401 / bozuk JSON → doğru `UsageError`
  (ağ mock'lanarak).

UI otomatik test edilmez; çalıştırılıp gözle doğrulanır.

## 9. Kapsam Dışı (YAGNI)

- Ekstra kredi / spend gösterimi (şimdilik dahil değil).
- Opus/Sonnet ayrı kırılımı.
- Sistem tepsisi ikonu, bildirimler, geçmiş grafiği.
- Token yenileme mantığı (Claude Code'a bırakılıyor).
