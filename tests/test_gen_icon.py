import struct

from tools.gen_icon import build_ico, params_for, render_burst, write_png

PNG_SIG = b"\x89PNG\r\n\x1a\n"
ICO_SIG = b"\x00\x00\x01\x00"


def test_render_burst_produces_rgba_bytes():
    pixels = render_burst(8)
    assert len(pixels) == 8 * 8 * 4


def test_burst_has_opaque_centre_and_clear_corners():
    size = 32
    pixels = render_burst(size)

    def alpha(x, y):
        return pixels[(y * size + x) * 4 + 3]

    assert alpha(size // 2, size // 2) == 255, "merkez dolu olmalı"
    assert alpha(0, 0) == 0, "köşeler şeffaf olmalı"


def test_burst_defaults_to_the_titlebar_foreground():
    # Krem, turuncu değil: başlık çubuğu Claude turuncusuna boyandığı için
    # turuncu bir simge orada turuncu üstüne turuncu kalıp seçilmiyordu.
    size = 16
    pixels = render_burst(size)
    i = ((size // 2) * size + size // 2) * 4
    assert tuple(pixels[i:i + 3]) == (0xFA, 0xF9, 0xF5)


def test_burst_colour_is_overridable():
    size = 16
    pixels = render_burst(size, color=(0xD9, 0x77, 0x57))
    i = ((size // 2) * size + size // 2) * 4
    assert tuple(pixels[i:i + 3]) == (0xD9, 0x77, 0x57)


def test_burst_has_rays_not_a_plain_disc():
    # Işınlar arasında boşluk yoksa elimizdeki şey bir daire olurdu.
    size = 64
    pixels = render_burst(size)
    ring = [pixels[(y * size + x) * 4 + 3]
            for x, y in _ring_coords(size, radius=size * 0.42)]
    assert max(ring) > 200, "ışın uçları dolu olmalı"
    assert min(ring) < 40, "ışınlar arası boşluk olmalı"


def _ring_coords(size, radius, count=180):
    import math
    cx = cy = size / 2
    out = []
    for i in range(count):
        a = 2 * math.pi * i / count
        out.append((int(cx + radius * math.cos(a)), int(cy + radius * math.sin(a))))
    return out


def test_small_sizes_get_fewer_and_thicker_rays():
    # 12 ince ışın 256'da zarif, 16'da kenar yumuşatma turuncuyu yıkayıp
    # soluk bir bulanıklık bırakıyordu.
    small_rays, small_half, _, _ = params_for(16)
    big_rays, big_half, _, _ = params_for(256)
    assert small_rays < big_rays
    assert small_half > big_half


def test_sixteen_pixel_icon_stays_saturated():
    # Asıl başarısızlık modu buydu: ışınlar var ama hepsi yarı saydam.
    pixels = render_burst(16)
    assert max(pixels[3::4]) == 255, "16px'te tam opak piksel kalmalı"
    opaque = sum(1 for a in pixels[3::4] if a > 200)
    assert opaque >= 20, f"16px'te yeterli dolu piksel yok: {opaque}"


def test_write_png_has_signature_and_ends_with_iend():
    data = write_png(4, 4, bytes(4 * 4 * 4))
    assert data.startswith(PNG_SIG)
    assert data.endswith(b"IEND\xae\x42\x60\x82")


def test_ico_starts_with_signature_and_counts_images():
    ico = build_ico([16, 32])
    assert ico.startswith(ICO_SIG)
    assert struct.unpack("<H", ico[4:6])[0] == 2


def test_ico_embeds_png_payloads():
    ico = build_ico([16])
    offset = struct.unpack("<I", ico[6 + 12:6 + 16])[0]
    assert ico[offset:offset + 8] == PNG_SIG


def test_ico_encodes_256_as_zero():
    # ICO dizin girdisinde boyut tek bayt; 256 sıfır olarak yazılır.
    ico = build_ico([256])
    assert ico[6] == 0 and ico[7] == 0


def test_ico_records_each_declared_size():
    ico = build_ico([16, 48])
    assert ico[6] == 16
    assert ico[6 + 16] == 48


def test_build_is_deterministic():
    # İkon commit edilen bir binary; aynı kaynaktan aynı byte'lar çıkmazsa
    # her yeniden üretim gürültülü bir diff olur.
    assert build_ico([16, 32]) == build_ico([16, 32])
