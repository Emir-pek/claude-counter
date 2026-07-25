"""32x32 pixel-art yengec spritesheet ureticisi.
Ust acidan, saga (yuruyus yonune) bakan. 8 kare yuruyus dongusu.
Cikti: crab_walk.png (256x32 RGBA) + preview.png
"""
from PIL import Image
import math

S, FRAMES = 32, 8

BODY  = (217, 119,  87, 255)   # #D97757  Claude turuncusu
LIGHT = (235, 163, 134, 255)
SHADE = (191,  77,  59, 255)   # #BF4D3B
OUTL  = ( 94,  40,  30, 255)
EYEW  = (250, 249, 245, 255)
EYEB  = ( 20,  20,  19, 255)
CLEAR = (0, 0, 0, 0)

# Kabuk: her satir icin (x_bas, x_son). Onu (sag) hafif genis.
SHELL = {
     8: (12, 16),  9: (10, 18), 10: ( 9, 19), 11: ( 9, 19),
    12: ( 8, 20), 13: ( 8, 20), 14: ( 8, 20), 15: ( 8, 20),
    16: ( 8, 20), 17: ( 8, 20), 18: ( 8, 20), 19: ( 8, 20),
    20: ( 9, 19), 21: ( 9, 19), 22: (10, 18), 23: (12, 16),
}

# Kiskac 9x8, saga bakan, ust taraf icin. Alt taraf icin y-flip edilir.
CLAW_OPEN = [
    "..OOOO...",
    ".OLLBBO..",
    "OLLBBBBO.",
    "OLBBBBBBO",
    "OLBBBOO..",
    "OBBBBBBBO",
    ".OBBBBOO.",
    "..OOOO...",
]
CLAW_SHUT = [
    "..OOOO...",
    ".OLLBBO..",
    "OLLBBBBO.",
    "OLBBBBBBO",
    "OLBBBBBBO",
    "OBBBBBBBO",
    ".OBBBBOO.",
    "..OOOO...",
]
PAL = {"O": OUTL, "B": BODY, "L": LIGHT, "S": SHADE}


def px(img, x, y, c):
    if 0 <= x < S and 0 <= y < S and c is not None:
        img.putpixel((x, y), c)


def line(img, x0, y0, x1, y1, c):
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx - dy
    while True:
        px(img, x0, y0, c)
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 > -dy:
            err -= dy; x0 += sx
        if e2 < dx:
            err += dx; y0 += sy


def stamp(img, art, ox, oy, flip_y=False):
    rows = art[::-1] if flip_y else art
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch != ".":
                px(img, ox + i, oy + j, PAL[ch])


def draw_shell(img):
    for y, (x0, x1) in SHELL.items():
        for x in range(x0, x1 + 1):
            img.putpixel((x, y), BODY)
    # hacim: sol-ust isik, sag-alt golge
    for y, (x0, x1) in SHELL.items():
        for x in range(x0, x1 + 1):
            d = (x - 12) * 0.6 + (y - 15) * 0.8
            if d < -4.5:
                img.putpixel((x, y), LIGHT)
            elif d > 5.0:
                img.putpixel((x, y), SHADE)
    # kontur
    for y, (x0, x1) in SHELL.items():
        px(img, x0, y, OUTL); px(img, x1, y, OUTL)
    for x in range(*(SHELL[8][0], SHELL[8][1] + 1)):
        px(img, x, 7, OUTL)
    for x in range(*(SHELL[23][0], SHELL[23][1] + 1)):
        px(img, x, 24, OUTL)
    # kabuk deseni: iki kucuk cukur
    for p in ((13, 13), (13, 18)):
        px(img, p[0], p[1], SHADE)


def draw_eyes(img, blink):
    for ey in (12, 19):
        px(img, 17, ey, EYEW); px(img, 18, ey, EYEW)
        px(img, 17, ey + 1, EYEW); px(img, 18, ey + 1, EYEW)
        if blink:
            for dx in (0, 1):
                px(img, 17 + dx, ey, OUTL); px(img, 17 + dx, ey + 1, OUTL)
        else:
            px(img, 18, ey, EYEB); px(img, 18, ey + 1, EYEB)


def draw_claws(img, phase):
    """Omuz -> kalin kol -> kiskac. Kiskac kolun ucuyla 1px bindirilir,
    boylece hicbir karede kopuk gorunmez."""
    for top in (True, False):
        sgn = -1 if top else 1
        p = phase if top else phase + math.pi
        lift = int(round(math.sin(p) * 1.2))
        sx, sy = 19, (12 if top else 19)
        ex, ey = 20, sy + sgn * (2 + lift)
        # kol 2px kalinlikta
        line(img, sx, sy, ex, ey, SHADE)
        line(img, sx, sy + sgn, ex, ey + sgn, SHADE)
        line(img, sx, sy + sgn * 2, ex, ey + sgn * 2, OUTL)
        art = CLAW_OPEN if math.sin(p) > 0 else CLAW_SHUT
        # 8 satirlik kiskac: baglanti noktasi ust icin r3, alt icin r4
        stamp(img, art, ex, ey - (3 if top else 4), flip_y=not top)


def draw_legs(img, phase):
    for top in (True, False):
        sgn = -1 if top else 1
        root_y = 9 if top else 22
        for i, ax in enumerate((11, 14, 17)):
            p = phase + i * (2 * math.pi / 3) + (0 if top else math.pi)
            swing = int(round(math.sin(p) * 2.0))
            reach = 5 if math.cos(p) > 0 else 6      # adim kalkis/basma
            kx, ky = ax - 1 + swing, root_y + sgn * 3
            tx, ty = ax - 2 + swing * 2, root_y + sgn * reach
            # ust segment 2px (govdeye saglam baglansin), alt segment ince
            line(img, ax, root_y, kx, ky, SHADE)
            line(img, ax + 1, root_y, kx + 1, ky, SHADE)
            line(img, kx, ky, tx, ty, OUTL)
            px(img, tx, ty + sgn, OUTL)          # ayak ucu


def frame(i):
    img = Image.new("RGBA", (S, S), CLEAR)
    ph = (i / FRAMES) * 2 * math.pi
    draw_legs(img, ph)
    draw_claws(img, ph)
    draw_shell(img)
    draw_eyes(img, blink=(i == 6))
    if i in (2, 6):   # yuruyus zipl@masi
        img = img.transform((S, S), Image.AFFINE, (1, 0, 0, 0, 1, 1),
                            resample=Image.NEAREST)
    return img


sheet = Image.new("RGBA", (S * FRAMES, S), CLEAR)
for i in range(FRAMES):
    sheet.paste(frame(i), (i * S, 0))
sheet.save("/sessions/friendly-wizardly-pasteur/mnt/outputs/crab/crab_walk.png")

prev = Image.new("RGBA", (S * FRAMES * 6, S * 6), (31, 30, 29, 255))
prev.alpha_composite(sheet.resize((S * FRAMES * 6, S * 6), Image.NEAREST))
prev.save("/sessions/friendly-wizardly-pasteur/mnt/outputs/crab/preview.png")
print("ok", sheet.size)

# hareketli onizleme (8 fps)
gif = [frame(i).resize((S * 5, S * 5), Image.NEAREST) for i in range(FRAMES)]
bg = [Image.new("RGBA", g.size, (31, 30, 29, 255)) for g in gif]
for b, g in zip(bg, gif):
    b.alpha_composite(g)
bg[0].save("/sessions/friendly-wizardly-pasteur/mnt/outputs/crab/crab_walk.gif",
           save_all=True, append_images=bg[1:], duration=125, loop=0)
print("gif ok")
