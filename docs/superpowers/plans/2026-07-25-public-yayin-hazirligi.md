# Public Yayın Hazırlığı Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `claude-counter` deposunu, yabancı bir Windows kullanıcısının tek bir dosyaya çift tıklayarak çalıştırabileceği ve güvenle inceleyebileceği public bir repo hâline getirmek.

**Architecture:** Uygulama kodu hiç değişmiyor. Depoya dört yeni parça giriyor: kendi venv'ini kuran `baslat.bat` başlatıcısı, MIT `LICENSE`, iki dilli README ve sentetik veriyle üretilmiş bir ekran görüntüsü. Bunun yanında `requirements.txt` sürümü sabitleniyor ve süreç dokümanları takipten çıkarılıyor.

**Tech Stack:** Windows `cmd` batch, Python 3.10+ / `venv`, customtkinter 6.x, git.

Spec: `docs/superpowers/specs/2026-07-25-public-yayin-hazirligi-design.md`

## Global Constraints

- **Uygulama kodu değişmez.** `app.py`, `main.py`, `usage_client.py`, `formatting.py`, `tests/**` ve `requirements-dev.txt` bu planın hiçbir görevinde düzenlenmez.
- **`baslat.bat` ASCII-only ve BOM'suz olmalı.** UTF-8 BOM `cmd.exe`'nin ilk satırını bozar; Türkçe karakterler varsayılan OEM kod sayfasında mojibake olur. `.bat` içindeki tüm kullanıcı mesajları İngilizce.
- **`baslat.bat` satır sonları CRLF olmalı** ve `.gitattributes` bunu klonlarda garanti etmeli.
- Telif satırı birebir: `Copyright (c) 2026 Emir-swe`.
- Python taban sürümü metinlerde birebir: `Python 3.10+` (test edilen: 3.11.9).
- customtkinter sabiti birebir: `customtkinter>=6.0,<7`.
- Ekran görüntüsü **sentetik veriyle** üretilir; sahibinin gerçek kullanım yüzdeleri repoya girmez.
- Git geçmişi yeniden yazılmaz. Remote eklenmez, push edilmez.
- Yol: proje kökü `C:\Users\emire\Desktop\projeler\claude-counter`. Geçici dosyalar scratchpad'e yazılır, repoya değil.

---

### Task 1: `baslat.bat` başlatıcısı + bağımlılık sabitleme

Deposu klonlayan bir yabancının tek yapması gereken şey bu dosyaya çift tıklamak olacak. `requirements.txt` sabitlemesi bu göreve ait, çünkü `.bat`'in ilk çalıştırmada kurduğu şey tam olarak o dosya.

**Files:**
- Create: `baslat.bat`
- Create: `.gitattributes`
- Modify: `requirements.txt` (tek satır)
- Test: otomatik test yok — cmd script'i izole edilebilir bir birim değil; doğrulama Step 4-6'daki elle reçete.

**Interfaces:**
- Consumes: `requirements.txt`, `main.py` (kökte, çalışma dizini repo kökü olarak varsayılır).
- Produces: `.venv\Scripts\pythonw.exe` (kurulum tamamlanma göstergesi). Task 3 ekran görüntüsü alırken bu yorumlayıcıyı kullanır.

- [ ] **Step 1: `requirements.txt`'i sabitle**

Dosyanın tamamı tek satır olacak:

```
customtkinter>=6.0,<7
```

- [ ] **Step 2: `.gitattributes` oluştur**

`.bat` LF satır sonlarıyla klonlanırsa `goto` etiketleri bozulabilir; bu dosya klonlarda CRLF'i garanti eder.

```
* text=auto
*.bat text eol=crlf
```

- [ ] **Step 3: `baslat.bat`'i yaz**

Yapı bilinçli olarak `goto` tabanlı: parantezli bloklar içinde değişken okumak `cmd`'de gecikmeli genişletme tuzağına düşürür.

```bat
@echo off
setlocal
cd /d "%~dp0"

REM --- Find a working Python. Existence is not enough: on Windows the
REM --- "python" command is often the Microsoft Store stub, which opens the
REM --- Store instead of running anything. Executing a no-op filters it out.
set "PY="
py -3 -c "pass" >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if defined PY goto have_python

python -c "pass" >nul 2>&1
if not errorlevel 1 set "PY=python"
if defined PY goto have_python

echo.
echo Python was not found on this computer.
echo.
echo Install Python 3.10 or newer from:
echo     https://www.python.org/downloads/
echo During setup, tick "Add python.exe to PATH".
echo Then run this file again.
echo.
pause
exit /b 1

:have_python
REM --- The completion marker is pythonw.exe, not the .venv folder: a setup
REM --- interrupted halfway leaves the folder behind and would otherwise
REM --- wedge every future launch.
if exist ".venv\Scripts\pythonw.exe" goto run

echo.
echo First run: setting up a local Python environment.
echo This takes a few seconds and happens only once.
echo.
%PY% -m venv .venv
if errorlevel 1 goto setup_failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto setup_failed
if not exist ".venv\Scripts\pythonw.exe" goto setup_failed
echo.
echo Setup complete. Starting Claude Counter...

:run
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

:setup_failed
echo.
echo Setup failed.
echo Check your internet connection, delete the .venv folder,
echo and run this file again.
echo.
pause
exit /b 1
```

- [ ] **Step 4: Kodlamayı ve satır sonlarını doğrula**

`baslat.bat` ASCII, BOM'suz ve CRLF olmalı. PowerShell'de:

```powershell
$p = "C:\Users\emire\Desktop\projeler\claude-counter\baslat.bat"
$b = [IO.File]::ReadAllBytes($p)
"BOM: " + ($b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF)
"NonAscii: " + (($b | Where-Object { $_ -gt 127 }).Count)
"CR count: " + (($b | Where-Object { $_ -eq 13 }).Count)
"LF count: " + (($b | Where-Object { $_ -eq 10 }).Count)
```

Beklenen: `BOM: False`, `NonAscii: 0`, CR sayısı = LF sayısı (hepsi CRLF).

Değilse dönüştür:

```powershell
$p = "C:\Users\emire\Desktop\projeler\claude-counter\baslat.bat"
$t = (Get-Content $p -Raw) -replace "`r`n","`n" -replace "`n","`r`n"
[IO.File]::WriteAllText($p, $t, (New-Object Text.UTF8Encoding $false))
```

- [ ] **Step 5: Temiz kurulum testi — ÇİFT TIKLAMA**

Bu görevdeki asıl test budur. Terminalden çalıştırmak farklı bir bağlamdır ve gerçek hatayı gizler.

```powershell
Get-Process pythonw* -ErrorAction SilentlyContinue | Stop-Process -Force
$root = "C:\Users\emire\Desktop\projeler\claude-counter"
if (Test-Path "$root\.venv") { Rename-Item "$root\.venv" ".venv_yedek" }
explorer $root
```

Açılan Gezgin penceresinde `baslat.bat`'a **çift tıkla**. Beklenen sırayla:
1. Konsol açılır, "First run: setting up a local Python environment." yazar.
2. pip çıktısı akar (birkaç saniye).
3. Widget penceresi ("Claude Kullanımı") açılır, konsol kapanır.

Doğrula:

```powershell
Test-Path "C:\Users\emire\Desktop\projeler\claude-counter\.venv\Scripts\pythonw.exe"
Get-Process pythonw -ErrorAction SilentlyContinue | Select-Object Id,MainWindowTitle
```

Beklenen: `True` ve çalışan bir `pythonw` süreci.

- [ ] **Step 6: İkinci çalıştırma testi**

Widget'ı ✕ ile kapat, `baslat.bat`'a tekrar **çift tıkla**. Beklenen: kurulum çıktısı yok, pencere neredeyse anında açılır. Sonra kapat ve yedeği geri al:

```powershell
Get-Process pythonw* -ErrorAction SilentlyContinue | Stop-Process -Force
$root = "C:\Users\emire\Desktop\projeler\claude-counter"
if (Test-Path "$root\.venv_yedek") { Remove-Item "$root\.venv" -Recurse -Force; Rename-Item "$root\.venv_yedek" ".venv" }
```

- [ ] **Step 7: Testlerin hâlâ yeşil olduğunu doğrula**

```powershell
python -m pytest -q
```

Beklenen: 35 passed. (Bu görev uygulama kodunu değiştirmiyor; kırmızı gelirse durup nedenini bul.)

- [ ] **Step 8: Commit**

```bash
git add baslat.bat .gitattributes requirements.txt
git commit -m "feat: cift tiklanan baslat.bat launcher ve surum sabitleme"
```

---

### Task 2: Depo temizliği — süreç dokümanlarını takipten çıkar

Süreç artıkları (spec/plan dokümanları, sdd defterleri) yabancıya hitap etmiyor ve tek kişisel yol sızıntısı da orada. Dosyalar diskte kalır, yalnızca takipten çıkar.

**Files:**
- Modify: `.gitignore`
- Untrack: `docs/superpowers/**` (dosyalar silinmez)

**Interfaces:**
- Consumes: yok.
- Produces: `docs/` dizini takipli kalır ama içinde yalnızca Task 3'ün ekleyeceği `docs/screenshot.png` bulunur. `docs/superpowers/` ignore edilir, `docs/*.png` edilmez.

- [ ] **Step 1: `.gitignore`'u genişlet**

Dosyanın tamamı şu hâle gelecek:

```
__pycache__/
*.pyc
.venv/
venv/
.pytest_cache/
.claude/
.superpowers/
docs/superpowers/
assets/
tools/
```

- [ ] **Step 2: `docs/superpowers/`'ı takipten çıkar**

`--cached` diskteki dosyalara dokunmaz, yalnızca indeksten düşürür:

```bash
git rm -r --cached docs/superpowers
```

- [ ] **Step 3: Sonucu doğrula**

```powershell
git ls-files | Select-String "superpowers"
Test-Path "C:\Users\emire\Desktop\projeler\claude-counter\docs\superpowers\specs\2026-07-25-public-yayin-hazirligi-design.md"
git status --short
```

Beklenen: ilk komut **hiçbir şey** döndürmez (takipli süreç dosyası kalmadı), ikinci komut `True` (dosyalar diskte duruyor), `git status` çıktısında takipsiz `assets/`, `tools/`, `docs/` görünmez (hepsi ignore).

- [ ] **Step 4: Kişisel yolun kalmadığını doğrula**

```powershell
git grep -n -I "emire"
```

Beklenen: çıktı boş. (Sızıntı `docs/superpowers/plans/2026-07-25-yerel-sifirlama-saati.md:378` içindeydi ve takipten çıktı.)

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore: surec dokumanlarini takipten cikar, gitignore'u genislet"
```

---

### Task 3: Sentetik veriyle ekran görüntüsü

README'nin en etkili parçası. Gerçek veri kullanılmaz: sahibinin kullanım yüzdeleri repoya girmemeli.

**Files:**
- Create: `docs/screenshot.png`
- Create (geçici, repoya girmez): `<scratchpad>\shot_app.py`, `<scratchpad>\capture.ps1`

`<scratchpad>` = `C:\Users\emire\AppData\Local\Temp\claude\C--Users-emire-Desktop-projeler-claude-counter\<session>\scratchpad`

**Interfaces:**
- Consumes: `UsageApp.render(UsageData)` (`app.py:194`), `UsageData(five_hour, seven_day, fetched_at)` ve `Window(utilization, resets_at)` (`usage_client.py:30-40`), Task 1'in kurduğu `.venv\Scripts\pythonw.exe`.
- Produces: `docs/screenshot.png`, Task 4'ün README'lerinden referans verilecek.

- [ ] **Step 1: Ekran görüntüsü script'ini yaz**

Değerler bilinçli seçildi: `color_for` eşiklerine göre (`formatting.py:30-35`) 42 yeşil, 78 sarı — iki farklı bar rengi tek karede görünür. Haftalık sıfırlanma 2 gün sonra: `format_reset_time` başka bir yerel güne düştüğü için gün adını da gösterir (`· Paz 14:30` gibi), yani her iki biçim de kareye girer.

`<scratchpad>\shot_app.py`:

```python
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, r"C:\Users\emire\Desktop\projeler\claude-counter")

from app import UsageApp
from usage_client import UsageData, Window

now = datetime.now(timezone.utc)
data = UsageData(
    five_hour=Window(utilization=42.0, resets_at=now + timedelta(hours=2, minutes=39)),
    seven_day=Window(utilization=78.0, resets_at=now + timedelta(days=2, hours=5)),
    fetched_at=now,
)

app = UsageApp()
app.render(data)
app.after(20000, app.destroy)  # ekran görüntüsü alınacak kadar açık kalsın
app.mainloop()
```

- [ ] **Step 2: Yakalama script'ini yaz**

`<scratchpad>\capture.ps1`:

Pencereyi **başlıkla aramıyoruz**: "Claude Kullanımı" içindeki Türkçe karakterler,
BOM'suz UTF-8 kaydedilmiş bir `.ps1`'i PowerShell 5.1 okuduğunda bozulur ve `FindWindow`
boş döner. Bunun yerine `pythonw` sürecinin `MainWindowHandle`'ı kullanılıyor — ASCII-güvenli.

```powershell
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class W {
  [DllImport("user32.dll")]
  public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
Add-Type -AssemblyName System.Drawing

$proc = Get-Process pythonw -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $proc) { throw "Pencere bulunamadi (pythonw sureci yok ya da penceresi acilmadi)" }
$h = $proc.MainWindowHandle
"Baslik: $($proc.MainWindowTitle)"
$r = New-Object W+RECT
[void][W]::GetWindowRect($h, [ref]$r)
$w = $r.Right - $r.Left
$ht = $r.Bottom - $r.Top
"Rect: $($r.Left),$($r.Top) ${w}x${ht}"
$bmp = New-Object System.Drawing.Bitmap $w, $ht
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
$out = "C:\Users\emire\Desktop\projeler\claude-counter\docs\screenshot.png"
$bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
"Kaydedildi: $out"
```

- [ ] **Step 3: Pencereyi aç ve yakala**

```powershell
$root = "C:\Users\emire\Desktop\projeler\claude-counter"
$scratch = "<scratchpad>"
Start-Process "$root\.venv\Scripts\pythonw.exe" -ArgumentList "$scratch\shot_app.py" -WorkingDirectory $root
Start-Sleep -Seconds 3
powershell -ExecutionPolicy Bypass -File "$scratch\capture.ps1"
```

Pencere `-topmost` olduğu için başka bir pencerenin altında kalmaz. "Pencere bulunamadi" hatası gelirse `shot_app.py`'yi `python.exe` ile çalıştırıp konsol hatasını oku.

- [ ] **Step 4: Görüntüyü gözle doğrula**

`docs/screenshot.png` dosyasını Read aracıyla aç ve şunları teyit et:
- Pencerenin tamamı görünüyor, kırpılmamış (~260x310 civarı, DPI ölçeklemesiyle daha büyük olabilir).
- "5 saatlik" satırı `%42` ve yeşilimsi bar; "Haftalık" satırı `%78` ve turuncumsu/sarımsı bar.
- Haftalık satırın geri sayımında gün adı var (`· Paz 14:30` biçimi).
- **Gerçek kullanım verisi yok** — değerler tam olarak 42 ve 78.

Kırpılma veya yanlış pencere varsa Step 3'ü tekrarla.

- [ ] **Step 5: Süreci kapat ve commit**

```powershell
Get-Process pythonw* -ErrorAction SilentlyContinue | Stop-Process -Force
```

```bash
git add docs/screenshot.png
git commit -m "docs: README icin sentetik veriyle ekran goruntusu"
```

---

### Task 4: README (EN + TR) ve LICENSE

Deponun yabancıya bakan yüzü. İki README aynı bölümleri aynı sırada taşır ve birbirine link verir.

**Files:**
- Create: `README.md` (İngilizce, ana)
- Create: `README.tr.md` (Türkçe)
- Create: `LICENSE`

**Interfaces:**
- Consumes: Task 1'in `baslat.bat`'i, Task 3'ün `docs/screenshot.png`'si.
- Produces: yok (son görev).

- [ ] **Step 1: `LICENSE` dosyasını yaz**

MIT tam metni, telif satırı birebir:

```
MIT License

Copyright (c) 2026 Emir-swe

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: `README.md` (İngilizce) yaz**

````markdown
# Claude Counter

A small always-on-top desktop widget for Windows that shows how much of your
Claude subscription you have used: the 5-hour window and the weekly window,
each with a colored bar, a live countdown, and the local clock time when it
resets.

*Türkçe: [README.tr.md](README.tr.md)*

![Claude Counter](docs/screenshot.png)

> **Note:** the widget's interface is currently in Turkish
> (`5 saatlik` = 5-hour, `Haftalık` = weekly, `güncellendi` = updated).

## Requirements

- Windows
- [Python 3.10+](https://www.python.org/downloads/) (tested on 3.11.9) — during
  setup, tick **"Add python.exe to PATH"**
- [Claude Code](https://claude.com/claude-code) installed and logged in — the
  widget reads its session

## Install and run

1. Download the code: **Code → Download ZIP**, then extract it (or
   `git clone` the repository).
2. Double-click **`baslat.bat`** (Turkish for "start").
3. The first run creates a local `.venv` and installs customtkinter. It takes a
   few seconds and happens only once — later runs open instantly.

The widget refreshes every 60 seconds; the **↻** button refreshes it manually.
Close it with the **✕** button.

To start it automatically with Windows, press `Win+R`, run `shell:startup`, and
put a shortcut to `baslat.bat` in the folder that opens.

## What it does with your data

This program reads your Claude session token, so you should know exactly what
it does before you run it:

- It reads the token from `claudeAiOauth.accessToken` in
  `~/.claude/.credentials.json` **fresh on every request**. It never copies,
  stores, or logs it.
- The only network call it makes is
  `GET https://api.anthropic.com/api/oauth/usage`. It connects to no other
  server and sends no telemetry. See [`usage_client.py`](usage_client.py) — it
  is under 100 lines.
- **That endpoint is undocumented.** It is a private endpoint that Claude Code
  uses for itself. Anthropic may change or remove it without notice, and the
  widget would then stop showing data.
- **It is not the paid API.** The request runs no model and consumes no tokens,
  so it costs nothing and does not appear on any bill. It does not consume your
  5-hour or weekly limit either — it only reports it.
- It polls once every 60 seconds. If you restart it many times in a row, the
  endpoint may answer with HTTP 429; the rows then keep showing the last good
  data.

## Development

```
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
```

Run from source without the launcher: `pythonw main.py`

Layout: `main.py` is the refresh loop, `app.py` the CustomTkinter window,
`usage_client.py` the fetch and parse layer, `formatting.py` the countdown and
color rules.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| "Python was not found" | Install Python 3.10+ and tick "Add python.exe to PATH" |
| Widget says `Claude oturumu bulunamadı` | Log in with Claude Code first |
| Widget says `Oturum süresi dolmuş` | Your session expired — log in with Claude Code again |
| Widget says `Bağlantı yok` | No internet connection |
| Something broke after an update | Delete the `.venv` folder, then double-click `baslat.bat` again |

## License

MIT — see [LICENSE](LICENSE).
````

- [ ] **Step 3: `README.tr.md` (Türkçe) yaz**

````markdown
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
````

- [ ] **Step 4: Bağlantıları ve iddiaları doğrula**

```powershell
$root = "C:\Users\emire\Desktop\projeler\claude-counter"
foreach ($f in "docs\screenshot.png","LICENSE","usage_client.py","README.md","README.tr.md","baslat.bat","requirements-dev.txt") {
  "{0,-24} {1}" -f $f, (Test-Path "$root\$f")
}
```

Beklenen: hepsi `True` (README'lerdeki her göreli link bir dosyaya karşılık geliyor).

README'lerdeki hata mesajlarının gerçek metinlerle eşleştiğini teyit et — `usage_client.py:75,86,89`: `Claude oturumu bulunamadı`, `Oturum süresi dolmuş — Claude Code'da giriş yapın`, `Bağlantı yok`.

- [ ] **Step 5: Son bütünlük kontrolü**

```powershell
python -m pytest -q
git status --short
git ls-files
```

Beklenen: 35 passed; `git status` yalnızca bu görevin yeni dosyalarını gösterir; `git ls-files` çıktısında `docs/superpowers/` **yok**, `baslat.bat`, `.gitattributes`, `LICENSE`, `README.md`, `README.tr.md`, `docs/screenshot.png` **var**.

- [ ] **Step 6: Commit**

```bash
git add README.md README.tr.md LICENSE
git commit -m "docs: iki dilli README ve MIT lisansi"
```

---

## Uygulama sonrası

Plan bittiğinde depo yayına hazırdır ama **hiçbir şey push edilmez** — remote ekleme ve GitHub'da repo oluşturma sahibinin kendi işidir (spec'te kapsam dışı).

Son adım olarak `superpowers:finishing-a-development-branch` çalıştırılabilir; iş doğrudan `main` üzerinde ilerlediği için muhtemelen yalnızca doğrulama turu olacaktır.
