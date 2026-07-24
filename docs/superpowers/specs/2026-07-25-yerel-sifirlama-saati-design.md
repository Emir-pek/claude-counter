# Yerel sıfırlanma saati — Tasarım Dokümanı

**Tarih:** 2026-07-25
**Durum:** Onaylandı, uygulamaya hazır
**Temel:** v1 (`main`, `3eaaa78`)

## 1. Amaç

Her limit satırı şu an yalnızca **ne kadar kaldığını** gösteriyor (`⟳ 4s 39dk`).
Buna ek olarak limitin **yerel saatle ne zaman** sıfırlanacağı da yazılacak:

```
%5   ⟳ 4s 39dk · 05:12
```

İkinci amaç: bu saat metni her saniye yeniden hesaplanmayacak. Değeri yalnızca
gerçekten değiştiğinde üretilecek — pratikte 5 saatlik dilim için döngü başına
bir kez, haftalık dilim için haftada bir kez.

## 2. Görünüm

Kural her iki satırda da aynıdır: **sıfırlanma bugüne düşüyorsa yalnızca saat,
başka bir güne düşüyorsa gün adı da** yazılır.

```
Claude Kullanımı                    ↻

5 saatlik
██░░░░░░░░░░░░░░░░░░░░░░░░░░░░
%5   ⟳ 4s 39dk · 05:12

Haftalık
██████████████████████████░░░░
%86   ⟳ 6g 12s · Cum 12:58

güncellendi: 23:59
```

| Durum | Sonuç |
|---|---|
| Saat 09:00, sıfırlanma bugün 14:00 | `%40   ⟳ 5s · 14:00` |
| Saat 23:00, sıfırlanma yarın 02:00 | `%40   ⟳ 3s · Cmt 02:00` |
| Haftalık, 6 gün sonra | `%86   ⟳ 6g 12s · Cum 12:58` |
| Süre dolmuş (`secs <= 0`) | `%86   ⟳ yenilendi` — saat yazılmaz |
| Limit verisi yok (`window is None`) | `—` (mevcut davranış korunur) |

Gün adı kuralının kalan süreye değil takvim gününe bağlanmasının sebebi: gece
yarısını aşan 5 saatlik dilimde çıplak `02:00` yazısı bugünü mü yarını mı
gösterdiğini belli etmez.

**Genişlik:** ölçüldü, sorun yok. Kullanılabilir alan 240 px (260 px pencere,
iki yanda 10 px padx); gün adlı en uzun hal (`%86   ⟳ 12s 59dk · Cum 12:58`)
150 px. Pencere boyutu değişmiyor.

## 3. Biçimlendirme — `formatting.py`

Tüm mantık `formatting.py`'de durur. Sebep: `app.py`'nin otomatik testi yok,
`formatting.py`'nin var; ve asıl doğrulama burada yapılacak.

```python
DAY_NAMES = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")

def format_reset_time(resets_at: datetime, now: datetime, tz=None) -> str
```

Davranış:

1. `secs = int((resets_at - now).total_seconds())`; `secs <= 0` ise `""` döner.
   Geçmiş bir saati göstermenin anlamı yok — satırda yalnızca `yenilendi` kalır.
2. `tz` verilmemişse sistem yerel saat dilimi kullanılır (`tz=None` →
   `astimezone()` varsayılanı).
3. **Her iki zaman da yerel saate çevrilir**, sonra tarihleri karşılaştırılır.
4. Yerel tarihler aynıysa `"%H:%M"` → `05:12`.
   Farklıysa `"{gün} %H:%M"` → `Cmt 02:00`.

### 3.1 Karşılaştırma yerelde yapılmak zorunda

Bu, uygulamada gözden kaçması en olası hata. `resets_at` sunucudan `+00:00`
gelir ve `refresh_countdown` `now`'u UTC olarak alır. Tarihler doğrudan
karşılaştırılırsa UTC tarihleri karşılaştırılmış olur ve Türkiye'de (UTC+3)
şu yanlış sonuç çıkar:

| | Yerel (UTC+3) | UTC |
|---|---|---|
| şimdi | 25 Tem 22:00 | 25 Tem 19:00 |
| sıfırlanma | 26 Tem 01:00 | 25 Tem 22:00 |
| tarihler | **farklı** → gün adı gerekli | **aynı** → gün adı çıkmaz |

Yani kuralın var olma sebebi olan durumda tam olarak çalışmaz, üstelik bu her
akşam tekrarlanır. Önce `.astimezone(tz)`, sonra `.date()` karşılaştırması.

### 3.2 Gün adları elle yazılır

`strftime("%a")` sistem diline bağlıdır ve bu makinede `Fri` döndürür.
`DAY_NAMES` sabiti `weekday()` ile indekslenir (0 = Pazartesi).

### 3.3 `tz` parametresi

Test süsü değil, `format_countdown`'ın `now` parametresiyle aynı türden bir
dikiş. §3.1'deki hatayı teste sabitlemenin tek yolu UTC+3'ü dışarıdan
verebilmektir. Ekran görüntüsü bu hatayı ancak 21:00 ile gece yarısı arasında
alınırsa yakalar.

## 4. Önbellek ve yazma — `app.py` / `_Row`

Önbellek satırın kendi durumudur, `_Row` içinde yaşar. Alternatifler
değerlendirildi ve elendi: `UsageApp.render` içinde tutmak satır başına iki
yerde durum gerektirir; `Window` dataclass'ında precompute etmek sunum
mantığını veri katmanına sızdırır.

`_Row` iki yeni alan tutar:

```
_reset_key   = (resets_at, yerel_bugün, süresi_doldu)   →   _reset_text
_last_info   = etikete en son yazılan metin
```

`yerel_bugün` = `now.astimezone(tz).date()`,
`süresi_doldu` = `int((resets_at - now).total_seconds()) <= 0`.

Satır metni şöyle kurulur — saat metni boşsa ayraç da yazılmaz:

```python
text = f"%{util:.0f}   ⟳ {countdown}"
if reset_text:
    text += f" · {reset_text}"
```

### 4.1 Saat metni: anahtar değişince hesapla

`refresh_countdown` her çağrıldığında anahtarı üretir ve önbellektekiyle
karşılaştırır; eşitse `_reset_text` yeniden kullanılır, değilse
`format_reset_time` çağrılıp önbellek tazelenir.

Anahtara `yerel_bugün`'ün de girmesinin sebebi: gün adının **varlığı** gece
yarısı bayatlar. 23:50'de doğru biçimde `Cum 12:58` yazılır, ama gece
yarısından sonra aynı sıfırlanma artık "bugün"dür ve çıplak `12:58` olmalıdır.
`resets_at` değişmediği için anahtar tek başına bunu yakalayamaz.

Anahtardaki üçüncü alanın (`süresi_doldu`) sebebi benzer: süre dolduğunda
`format_reset_time` boş string döndürmelidir (§2), ama o anda ne `resets_at`
ne de yerel gün değişir. Bu alan olmasaydı önbellekteki eski saat yerinde
kalır ve satır `⟳ yenilendi · 12:58` olurdu.

Bu iki alan, döngü başına bir hesaplamaya en fazla gece yarısında bir ve süre
dolduğunda bir tane daha ekler — istenen "döngü başına bir kez" hedefiyle
uyumludur.

### 4.2 Etikete yazma: yalnızca metin değiştiyse

Geri sayım dakika hassasiyetindedir ama `tick()` saniyede bir çalışır, yani
`configure()` şu an dakikada 59 kez gereksiz çağrılır. Bundan sonra satır
metni kurulur, `_last_info` ile karşılaştırılır ve **yalnızca farklıysa**
`configure()` çağrılır. `tick()` döngüsü ve 1 sn'lik aralık aynı kalır;
dakika dönüşümü yine anında ekrana yansır.

### 4.3 `set(None)` dalında önbellek temizlenir

`_Row.set(None)` etikete `"—"` yazıp döner. `_last_info` eski metni tutmaya
devam ederse şu hata oluşur: `resets_at` değişmeden gelen sonraki geçerli veri
aynı metni üretir, karşılaştırma eşit çıkar, `configure()` atlanır ve satır
bir dakikaya kadar `"—"` takılı kalır.

Bu erişilebilir bir durumdur — bozuk bir alan `_parse_window`'dan `None`
döndürdüğünde gerçekleşir. Bu yüzden `set(None)` dalı hem `_last_info` hem
`_reset_key` alanlarını temizler.

## 5. Test

`formatting.py` testleri asıl doğrulamadır; hepsi `tz` sabitlenerek (UTC+3)
yazılır:

- Sıfırlanma bugün → `"14:00"`, gün adı yok
- Sıfırlanma ertesi gün → `"Cmt 02:00"`
- **Gece yarısını aşan 5 saatlik dilim** (yerel 22:00 → yerel 01:00): UTC
  tarihleri aynı olmasına rağmen gün adı çıkmalı — §3.1'i kilitleyen test
- Günler sonrası (haftalık) → doğru gün adı
- `secs <= 0` → `""`
- Gün adları Türkçe ve sistem dilinden bağımsız

Mevcut 21 testin hepsi geçmeye devam etmelidir.

UI otomatik test edilmez; çalıştırılıp gözle doğrulanır (pencere boyutu
değişmediği için taşma beklenmiyor, yine de bakılacak).

## 6. Kapsam Dışı (YAGNI)

- `tick()` aralığını değiştirmek (1 sn kalır).
- Saat biçimi tercihi (12/24 saat) — sistem her zaman 24 saat.
- Uygulama açıkken saat diliminin elle değiştirilmesini algılamak. DST
  geçişleri bu kapsamın dışında değil, zaten sorun çıkarmıyor: `astimezone()`
  hedef anın UTC ofsetini çözer, dolayısıyla sabit bir `resets_at` her
  hesaplandığında aynı yerel değere döner. DST'nin oynatabileceği tek alan
  `local_now.date()`'dir ve o zaten anahtardadır. Asıl kapsam dışı bırakılan
  durum, kullanıcının işletim sistemi saat dilimi ayarını uygulama açıkken
  elle değiştirmesidir: bu durumda bir sonraki 60 sn'lik fetch aynı
  `resets_at`'ı döndürür, `yerel_bugün` ve `süresi_doldu` de değişmeyebilir,
  anahtar eşit çıkar ve metin bir sonraki fetch'e kadar değil, döngünün
  kendisi bitene kadar bayat kalabilir — 5 saatlik satır için en fazla 5
  saat, haftalık satır için en fazla 7 gün. Kişisel bir araç için kabul
  edilmiştir.
