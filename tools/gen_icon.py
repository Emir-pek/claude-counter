"""Pencere simgesini üretir: ışın çüveni, `.ico` olarak.

Yalnızca standart kütüphane. Pillow'u tek bir simge için runtime bağımlılığı
yapmak bu widget'a orantısız olurdu, o yüzden PNG'yi elle yazıp ICO kabına
gömüyoruz (Vista ve sonrası ICO içinde PNG'yi destekler).

Çıktı commit edilen bir binary olduğu için üretim deterministik: aynı kaynak
her zaman aynı byte'ları verir, yeniden üretim gürültülü diff yaratmaz.

Kullanım:  python -m tools.gen_icon
"""
from __future__ import annotations

import math
import os
import struct
import zlib

# Simge krem, turuncu değil: başlık çubuğu Claude turuncusuna boyandığı için
# turuncu bir simge orada turuncu üstüne turuncu kalıp seçilmiyordu. Krem,
# başlık yazısıyla aynı renk — simge ve başlık tek bir bütün gibi duruyor.
ICON_COLOR = (0xFA, 0xF9, 0xF5)
SUPERSAMPLE = 4  # kenar yumuşatma için piksel başına örnek (SS x SS)
SIZES = (16, 32, 48, 256)

# (ışın sayısı, açısal yarım genişlik, sivrilme üssü, çekirdek yarıçapı).
# Boyuta göre değişiyor: 12 ince ışın 256 pikselde zarif ama 16 pikselde
# kenar yumuşatma rengi yıkayıp soluk bir bulanıklığa çeviriyor. Küçük
# boyutlarda daha az ve daha kalın ışın okunaklı kalıyor.
_TIERS = (
    (20, (8, 0.32, 0.50, 0.20)),
    (40, (10, 0.24, 0.65, 0.14)),
)
_LARGE = (12, 0.17, 0.80, 0.09)


def params_for(size: int):
    for limit, params in _TIERS:
        if size <= limit:
            return params
    return _LARGE


DEFAULT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "assets", "claude_counter.ico")


def render_burst(size: int, color=ICON_COLOR) -> bytes:
    """RGBA piksel dizisi döndürür (satır sıralı, üstten alta)."""
    r, g, b = color
    rays, half, taper, core = params_for(size)
    sector = 2 * math.pi / rays
    out = bytearray(size * size * 4)
    step = 1.0 / (SUPERSAMPLE + 1)
    samples = SUPERSAMPLE * SUPERSAMPLE
    for y in range(size):
        for x in range(size):
            hits = 0
            for sy in range(1, SUPERSAMPLE + 1):
                # Piksel içindeki örnek noktalarını -1..1 aralığına taşı.
                py = ((y + sy * step) / size) * 2 - 1
                for sx in range(1, SUPERSAMPLE + 1):
                    px = ((x + sx * step) / size) * 2 - 1
                    radius = math.hypot(px, py)
                    if radius > 1.0:
                        continue
                    if radius <= core:
                        hits += 1
                        continue
                    # En yakın ışın eksenine açısal uzaklık.
                    theta = math.atan2(py, px)
                    offset = abs(((theta + sector / 2) % sector) - sector / 2)
                    # Yarım genişlik uca doğru daralıyor: sivri uç, geniş taban.
                    t = (radius - core) / (1.0 - core)
                    if offset <= half * (1.0 - t) ** taper:
                        hits += 1
            i = (y * size + x) * 4
            out[i] = r
            out[i + 1] = g
            out[i + 2] = b
            out[i + 3] = int(round(255 * hits / samples))
    return bytes(out)


def _chunk(tag: bytes, data: bytes) -> bytes:
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def write_png(width: int, height: int, pixels: bytes) -> bytes:
    """RGBA piksellerden sıkıştırılmış PNG üretir (color type 6)."""
    stride = width * 4
    # Her satırın başına filtre baytı (0 = filtre yok).
    raw = b"".join(b"\x00" + pixels[y * stride:(y + 1) * stride] for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(raw, 9))
            + _chunk(b"IEND", b""))


def build_ico(sizes=SIZES, color=ICON_COLOR) -> bytes:
    pngs = [(s, write_png(s, s, render_burst(s, color))) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(pngs))  # reserved, type=icon, adet
    offset = 6 + 16 * len(pngs)
    entries = b""
    for size, png in pngs:
        # Dizin girdisinde boyut tek bayt; 256 sıfır olarak kodlanır.
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
    return header + entries + b"".join(png for _, png in pngs)


def main(path: str = DEFAULT_PATH) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(build_ico())
    return path


if __name__ == "__main__":
    print(main())
