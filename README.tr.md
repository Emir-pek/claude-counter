# Claude Counter

Claude aboneliğinizin ne kadarını kullandığınızı gösteren, her zaman üstte
duran küçük bir Windows masaüstü widget'ı: 5 saatlik ve haftalık dilim, her
biri için renkli bir çubuk, canlı geri sayım ve sıfırlanmanın yerel saati.

*English: [README.md](README.md)*

![Claude Counter](docs/screenshot.png)

## Gereksinimler

- Windows
- [Python 3.10+](https://www.python.org/downloads/) (3.11.9 ile test edildi) —
  kurulumda **"Add python.exe to PATH"** kutusunu işaretleyin
- Kurulu ve giriş yapılmış [Claude Code](https://claude.com/claude-code) —
  widget onun oturumunu okur

## Kurulum ve çalıştırma

1. Kodu indirin: **Code → Download ZIP**, sonra arşivi çıkarın (ya da
   `git clone` yapın).
2. **`baslat.bat`** dosyasına çift tıklayın.
3. İlk çalıştırma yerel bir `.venv` kurup customtkinter'ı indirir. Birkaç
   saniye sürer ve yalnızca bir kez olur — sonraki açılışlar anında.

Widget 60 saniyede bir kendini yeniler; **↻** düğmesi elle yeniler. Kapatmak
için **✕** düğmesini kullanın.

Windows açılışında kendiliğinden başlaması için `Win+R` → `shell:startup`
yazın ve açılan klasöre `baslat.bat` kısayolunu koyun.

## Verilerinizle ne yapıyor

Bu program Claude oturum token'ınızı okuyor; çalıştırmadan önce ne yaptığını
tam olarak bilmelisiniz:

- Token'ı `~/.claude/.credentials.json` içindeki `claudeAiOauth.accessToken`
  alanından **her sorguda yeniden** okur. Hiçbir yere kopyalamaz, saklamaz,
  loglamaz.
- Yaptığı tek ağ çağrısı `GET https://api.anthropic.com/api/oauth/usage`.
  Başka hiçbir sunucuya bağlanmaz, telemetri göndermez. Kodu görün:
  [`usage_client.py`](usage_client.py) — 100 satırdan kısa.
- **Bu endpoint dokümante değildir.** Claude Code'un kendi kullandığı özel bir
  uçtur. Anthropic haber vermeden değiştirebilir veya kaldırabilir; o zaman
  widget veri gösteremez.
- **Ücretli API değildir.** İstek model çalıştırmaz, token tüketmez; hiçbir
  ücrete tabi değildir ve faturaya yansımaz. 5 saatlik veya haftalık limitinizi
  de tüketmez, yalnızca raporlar.
- 60 saniyede bir sorgular. Arka arkaya çok kez yeniden başlatılırsa endpoint
  HTTP 429 dönebilir; bu durumda satırlar son geçerli veriyi göstermeye devam
  eder.

## Geliştirme

```
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
```

Başlatıcı olmadan kaynaktan çalıştırma: `pythonw main.py`

Dosya düzeni: `main.py` yenileme döngüsü, `app.py` CustomTkinter penceresi,
`usage_client.py` veri çekme ve ayrıştırma, `formatting.py` geri sayım ve renk
kuralları.

## Sorun giderme

| Sorun | Çözüm |
| --- | --- |
| "Python was not found" | Python 3.10+ kurun, "Add python.exe to PATH" işaretli olsun |
| `Claude oturumu bulunamadı` | Önce Claude Code ile giriş yapın |
| `Oturum süresi dolmuş` | Oturumunuz bitmiş — Claude Code ile tekrar giriş yapın |
| `Bağlantı yok` | İnternet bağlantısı yok |
| Güncellemeden sonra bozuldu | `.venv` klasörünü silin, `baslat.bat`'a tekrar çift tıklayın |

## Lisans

MIT — bkz. [LICENSE](LICENSE).
