# Public yayın hazırlığı — tasarım dokümanı

Tarih: 2026-07-25
Durum: onaylandı

## Amaç

`claude-counter`'ı, sahibinin GitHub hesabında **public** bir repo olarak yayınlanabilir hâle
getirmek. Yayın hedefi iki şey istiyor:

1. Yabancı bir kullanıcı **hiç terminal komutu yazmadan**, tek bir dosyaya çift tıklayarak
   widget'ı çalıştırabilsin.
2. Repo bir yabancının güvenle bakabileceği hâlde olsun: ne işe yaradığı, neyi okuduğu ve
   nereye bağlandığı açıkça yazılı; kişisel iz ve süreç artığı temizlenmiş; lisansı belli.

Bu iş **yalnızca localde** yapılır. Push etme, remote ekleme ve repo oluşturma bu spec'in
kapsamı dışındadır; sahibi kendisi yapacak.

## Kapsam dışı (bilinçli)

- Uygulama davranışında hiçbir değişiklik yok. `app.py`, `main.py`, `usage_client.py`,
  `formatting.py` ve testler bu iş kapsamında **değişmez**.
- Tek başına `.exe` (PyInstaller) üretilmez. Karar gerekçesiyle birlikte aşağıda.
- Git geçmişi yeniden yazılmaz.
- Windows dışı platform desteği eklenmez.

## Dağıtım kararı: `.exe` değil, `baslat.bat`

Değerlendirilen üç seçenek: (a) tek başına `.exe`, (b) repoda venv kuran çift tıklanan
başlatıcı, (c) ikisi birden. Seçilen: **(b)**.

Gerekçe: bu program kullanıcının Claude OAuth token'ını okuyup ağa çıkıyor. İmzasız bir
PyInstaller `.exe`, SmartScreen'de "bilinmeyen yayıncı" uyarısı verir ve antivirüs yazılımlarında
sık sık yanlış pozitife takılır — "token okuyan imzasız exe" tarifi, benimsenmenin önündeki en
büyük güven engelidir. Kaynak kodun görünür kalması, tam da bu tür bir araç için en ikna edici
dağıtım biçimidir. Bedeli: kullanıcıda Python kurulu olması gerekir.

## Bileşen 1 — `baslat.bat`

Repo kökünde tek dosya. Çift tıklanır. Akış:

1. `@echo off`, ardından `cd /d "%~dp0"` — script hangi dizinden çağrılırsa çağrılsın çalışma
   dizinini proje köküne alır.
2. **Python bulma.** Sırasıyla `py -3 -c "pass"` ve `python -c "pass"` denenir; ilk başarılı olan
   kullanılır. Varlık değil **çalıştırılabilirlik** test edilir: Windows'ta `python`, çoğu makinede
   Microsoft Store'un stub'ına gider; stub programı çalıştırmak yerine Store'u açar ve bu testi
   geçemez.
3. **Python yoksa:** python.org indirme adresi ekrana yazılır, `pause` ile beklenir, hata koduyla
   çıkılır. `pause` olmadan başarısız bir çift tıklama kullanıcıya tamamen görünmezdir.
4. **İlk çalıştırma (kurulum).** `.venv\Scripts\pythonw.exe` **yoksa**: `.venv` oluşturulur ve
   `pip install -r requirements.txt` çalıştırılır. Bu adım konsol görünürken yapılır; kurulum
   çıktısının akması istenen davranıştır (birkaç saniye sürer, kullanıcı ne olduğunu görür).
   venv kurulumu veya pip başarısız olursa mesaj yazılır, `pause`, çıkılır.
5. **Her çalıştırma.** `start "" ".venv\Scripts\pythonw.exe" main.py` ile widget konsolsuz açılır,
   ardından `.bat` `exit` eder.

Bilinçli detaylar:

- **Kontrol dosyası `.venv` klasörü değil, `.venv\Scripts\pythonw.exe`.** Yarıda kesilmiş bir
  kurulum klasörü bırakır; klasör varlığına bakan bir kontrol, sonraki her açılışı kalıcı olarak
  kilitler.
- **Dosya ASCII ve BOM'suz olmalı.** UTF-8 BOM `cmd.exe`'nin ilk satırını bozar. Ayrıca `echo`
  ile yazılan Türkçe karakterler varsayılan OEM kod sayfasında mojibake olur; `chcp 65001` ile
  uğraşmak yerine kullanıcıya görünen tüm `.bat` mesajları **İngilizce ve ASCII** yazılır.
- **Her açılışta konsol kısa bir an yanıp söner.** Bu kabul edilmiştir: istenen şey "kullanıcı
  komut yazmasın"dı, "hiç pencere görünmesin" değil. Sıfır-flash için `.vbs` sarmalayıcı veya
  `.lnk` peşine düşülmez — antivirüs şüphesi çeker, kazancı yoktur.
- Bağımlılık **güncelleme** mantığı yok. `requirements.txt` değişirse kullanıcı `.venv` klasörünü
  siler; README bunu yazar.

**Test edilebilirlik.** `.bat` için otomatik test yazılmaz — cmd script'i anlamlı biçimde izole
edilebilir bir birim değil ve gerçek risk (Store stub'ı, venv, çift tıklama bağlamı) ancak gerçek
ortamda ortaya çıkar. Doğrulama elle yapılır; reçete aşağıda.

## Bileşen 2 — Repoyu yayına hazırlama

- **`requirements.txt` sabitlenir:** `customtkinter` → `customtkinter>=6.0,<7`. Yabancı bir
  makinede pip çalıştıran bir başlatıcıda sabitlenmemiş sürüm, gelecekteki kırıcı bir sürümde
  herkesin ilk açılışını bozar.
- **`docs/superpowers/` takipten çıkarılır:** `git rm -r --cached docs/superpowers` (dosyalar
  diskte kalır) ve `.gitignore`'a eklenir. Bunlar yabancıya hitap etmeyen süreç artıkları; tek
  kişisel yol sızıntısı da (`docs/superpowers/plans/2026-07-25-yerel-sifirlama-saati.md:378`,
  `C:\Users\emire\...`) burada yaşıyor ve onlarla birlikte gider.
- **`.gitignore` genişletilir:** `docs/superpowers/`, `.superpowers/`, `.claude/`,
  `.pytest_cache/`, `assets/`, `tools/`.
- `assets/` ve `tools/` (yengeç maskotu görselleri ve üretici script'ler) takipsiz kalır: uygulama
  bunları kullanmıyor, yayına kullanılmayan varlık sokulmaz. Diskte dururlar.

**Güvenlik ön kontrolü yapıldı ve temiz çıktı:** `git log -p -S "sk-ant"` ve takipli dosyalarda
`sk-ant` araması boş; `.claude/settings.local.json` ve `.superpowers/` zaten takipsiz. Geçmişte
sızmış bir kimlik bilgisi yok, dolayısıyla **geçmiş yeniden yazılmaz**. Bir yerel dosya yolu sır
değildir; `filter-branch` burada bedava risktir.

## Bileşen 3 — README (EN + TR)

`README.md` İngilizce ana dosya, `README.tr.md` Türkçe; ikisi birbirine tek satırlık bir dil
bağlantısıyla gönderme yapar. Aynı bölümler, aynı sıra:

1. Ne işe yarar — bir cümle + ekran görüntüsü.
2. Gereksinimler — Windows, Python 3.10+ (3.11.9 ile test edildi), makinede kurulu ve giriş
   yapılmış Claude Code.
3. Kurulum ve çalıştırma — repoyu indir (ZIP veya clone), `baslat.bat`'a çift tıkla. İlk açılış
   venv kurar ve birkaç saniye sürer, sonrakiler anında. Kapatmak için pencerenin ✕'i.
4. **Verilerinizle ne yapıyor** (aşağıda ayrı başlık).
5. Geliştirme — venv, `pip install -r requirements-dev.txt`, `python -m pytest`.
6. Lisans — MIT.

### "Verilerinizle ne yapıyor" bölümü

Bu bölüm gizlenmez, önden ve açıkça yazılır; token okuyan bir araçta şeffaflık benimsemeyi
artırır. İçeriği:

- Token'ı `~/.claude/.credentials.json` içindeki `claudeAiOauth.accessToken` alanından **her
  sorguda yeniden okur**; hiçbir yere kopyalamaz, saklamaz, loglamaz.
- Tek yaptığı ağ çağrısı `GET https://api.anthropic.com/api/oauth/usage`. Başka hiçbir sunucuya
  bağlanmaz; telemetri yoktur.
- Bu endpoint **dokümante değildir** — Claude Code'un kendi kullandığı özel bir uçtur. Anthropic
  haber vermeden değiştirebilir veya kaldırabilir; o zaman widget veri gösteremez.
- Ücretli API değildir: model çalıştırmaz, token tüketmez, faturaya yansımaz. Kullanıcının
  5 saatlik/haftalık limitini tüketmez, yalnızca raporlar.
- 60 saniyede bir sorgular. Çok sık yeniden başlatılırsa endpoint 429 döndürebilir; bu durumda
  satırlar son geçerli veriyi göstermeye devam eder.

### Ekran görüntüsü

`docs/screenshot.png`. **Sentetik veriyle** üretilir: `UsageApp.render(UsageData(...))` elle
kurulmuş değerlerle çağrılır, pencere ekran görüntüsü alınır. Sahibinin gerçek kullanım
yüzdeleri repoya girmez. Seçilen değerler her iki satırı da anlamlı gösterecek şekilde olmalı
(ör. biri güvenli aralıkta, biri uyarı renginde) ve haftalık satırda gün adı görünsün diye
sıfırlanma zamanı başka bir yerel güne düşmeli.

## Bileşen 4 — LICENSE

Kök dizinde `LICENSE`, MIT tam metni, `Copyright (c) 2026 Emir-swe`.

MIT seçildi: izin verici, kısa, kişisel araçlarda standart ve garanti/sorumluluk reddi sahibini
korur. Telif satırında GitHub kullanıcı adı kullanılır; geçerli bir telif sahibi tanımıdır ve
gerçek adı public repoda görünür yapmaz. Lisans dosyası olmayan bir repo yasal olarak "tüm
hakları saklıdır" sayılır ve yayın amacıyla çelişirdi.

## Nihai dosya listesi

Yeni: `baslat.bat`, `README.md`, `README.tr.md`, `LICENSE`, `docs/screenshot.png`.
Değişen: `requirements.txt` (sürüm sabitleme), `.gitignore` (yeni girdiler).
Takipten çıkan: `docs/superpowers/**`.
Dokunulmayan: `app.py`, `main.py`, `usage_client.py`, `formatting.py`, `tests/**`,
`requirements-dev.txt`.

## Doğrulama

1. **Çift tıklama testi (asıl test).** Mevcut `.venv` başka bir ada taşınır. `baslat.bat`
   Gezgin'den **çift tıklanarak** açılır (terminalden değil — çalıştırma bağlamı farklıdır):
   venv kurulur, widget açılır, konsol kapanır. İkinci çift tıklama anında açar.
2. **Python yok senaryosu** elle gözden geçirilir: `py` ve `python` başarısızken mesaj + `pause`
   davranışı okunarak doğrulanır.
3. `python -m pytest` — 35 test yeşil kalmalı (bu iş uygulama kodunu değiştirmiyor).
4. `git status` temiz; `git ls-files` çıktısında `docs/superpowers/` yok, yeni dosyalar var.
5. `docs/screenshot.png` açılıp gerçek veri içermediği gözle doğrulanır.

## Kabul edilen sınırlar

- Yalnızca Windows. `.bat` ve `pythonw.exe` platforma bağlı; README bunu açıkça yazar.
- Kullanıcıda Python gerekir — dağıtım kararının bilinçli bedeli.
- Her açılışta kısa konsol flash'ı.
- `.bat` bağımlılıkları güncellemez; çözüm `.venv`'i silmek, README'de yazılı.
