"""
Paint the external-stores atlas (PIL + numpy, no Blender).

    python tools/make_store_textures.py        # writes aircraft/textures/stores_*.{jpg,png}

Each store / pylon / launcher owns a rectangle (stores_data.pack()): the body
wrap (around x along) and a strip for its fins.  Paint follows US Navy
ordnance practice (NAVEDTRA 12308): olive-drab Mk 80 bodies with a rough
thermally-protective coating on shipboard bombs, yellow band(s) for high
explosive, brown band for rocket motors, light blue for practice stores;
white missile bodies; grey pods, tanks and suspension equipment.  Stencils
are representative nomenclature, not copies of real lot markings.
Wear: grime streaking aft, handling scuffs around the lugs, chipped noses and
fin edges.
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import stores_data as SD  # noqa: E402

OUT = os.path.join(HERE, "..", "textures")
A = SD.ATLAS
PPM = SD.PPM
rng = np.random.default_rng(84)
FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

base = Image.new("RGB", (A, A), (80, 80, 80))
rough = Image.new("L", (A, A), 160)
metal = Image.new("L", (A, A), 0)
height = Image.new("L", (A, A), 128)
db, dr, dm, dh = (ImageDraw.Draw(i) for i in (base, rough, metal, height))

STENCIL = {
    "AIM-9L": "GUIDED MISSILE AIR INTERCEPT AIM-9M", "AIM-9X": "AIM-9X  GUIDED MISSILE",
    "AIM-7M": "GUIDED MISSILE AIR INTERCEPT AIM-7M", "AIM-120A": "AIM-120B  AMRAAM",
    "AIM-120C": "AIM-120C  AMRAAM", "AGM-65E": "GUIDED MISSILE AGM-65E", "AGM-88": "AGM-88C  HARM",
    "AGM-84D": "AGM-84D HARPOON", "AGM-84E": "AGM-84E SLAM", "AGM-62": "GUIDED WEAPON MK 21 WALLEYE",
    "AGM-62II": "GUIDED WEAPON MK 23 WALLEYE II", "AGM-154A": "AGM-154A JSOW", "ADM-141": "ADM-141A TALD",
    "GBU-12": "BOMB GP 500 LB BLU-111A/B  THERMALLY PROTECTED", "GBU-16": "BOMB GP 1000 LB BLU-110  THERMALLY PROTECTED",
    "GBU-10": "BOMB GP 2000 LB BLU-117  THERMALLY PROTECTED", "GBU-24": "BOMB GP 2000 LB BLU-109",
    "GBU-38": "BOMB GP 500 LB BLU-111A/B", "GBU-32": "BOMB GP 1000 LB BLU-110", "GBU-31": "BOMB GP 2000 LB BLU-117",
    "MK-82": "BOMB GP 500 LB BLU-111A/B  THERMALLY PROTECTED", "MK-82SE": "BOMB GP 500 LB MK 82 MOD 6",
    "MK-83": "BOMB GP 1000 LB BLU-110A/B  THERMALLY PROTECTED", "MK-84": "BOMB GP 2000 LB BLU-117/B  THERMALLY PROTECTED",
    "MK-20": "DISPENSER MK 7 MOD 6  MK 20 ROCKEYE II", "MK-77": "FIRE BOMB MK 77 MOD 5",
    "LAU-61": "LAUNCHER ROCKET 2.75 IN LAU-61C/A", "LAU-68": "LAUNCHER ROCKET 2.75 IN LAU-68D/A",
    "LAU-10": "LAUNCHER ROCKET 5.0 IN LAU-10D/A", "B61": "TRAINING SHAPE", "B57": "TRAINING SHAPE",
    "MK-76": "MK 76 PRACTICE", "TANK-330": "FUEL ONLY  JP-5  330 GAL", "AAS-38": "AN/AAS-38",
    "LITENING": "AN/AAQ-28(V)", "ASQ-173": "AN/ASQ-173", "AWW-13": "AN/AWW-13", "ACMI": "TACTS / ACMI",
    "SUU-63": "NO STEP", "SUU-62": "NO STEP", "BRU-33": "BRU-33A/A", "LAU-115": "LAU-115", "LAU-7": "LAU-7",
    "LAU-117": "LAU-117", "LAU-118": "LAU-118",
}


def noise(w, h, scale, octaves=4, seed=0):
    r = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp = tot = 0.0
    amp = 1.0
    for o in range(octaves):
        cx = max(2, int(scale * 2 ** o * w / max(w, h)) + 1)
        cy = max(2, int(scale * 2 ** o * h / max(w, h)) + 1)
        g = r.random((cy, cx)).astype(np.float32)
        out += amp * np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC),
                                np.float32) / 255
        tot += amp
        amp *= 0.5
    return out / tot


def nose_end(s):
    """Fraction of the length where the nose reaches full diameter."""
    if not s.get("profile"):
        return 0.08
    for t, r in s["profile"]:
        if r >= 0.97:
            return t
    return 0.1


def text_along(rect_xy, s, size, fill, angle=90):
    """Text running along the store's length (rotated 90 deg)."""
    f = ImageFont.truetype(FONT, size)
    w = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(s, font=f)) + 4
    im = Image.new("RGBA", (w, size + 6), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2, 1), s, font=f, fill=fill + (235,))
    im = im.rotate(-angle, expand=True)
    base.paste(im, (int(rect_xy[0] - im.width / 2), int(rect_xy[1])), im)


def paint_item(s, rect):
    x0, y0, x1, y1, bw = rect
    is_equip = s in SD.EQUIPMENT
    col = np.array(s["body"], np.float32)
    w, h = x1 - x0, y1 - y0
    finish = s.get("finish", "paint")
    # base colour with mottling
    n = noise(w, h, 3, seed=sum(map(ord, s["id"])) * 7)
    img = np.ones((h, w, 3), np.float32) * col * (0.93 + 0.12 * n)[..., None]
    hgt = np.full((h, w), 128, np.float32)
    rg = np.full((h, w), 165 if finish == "thermal" else 120 if not is_equip else 140, np.float32)
    if finish == "thermal":
        # ablative coating: bumpy, matte, slightly lighter on the high points
        bumps = noise(w, h, 40, 3, seed=7) - 0.5
        hgt += bumps * 70
        img *= (1 + bumps * 0.10)[..., None]
        rg = np.full((h, w), 215, np.float32)
    lay = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    base.paste(lay, (x0, y0))
    rough.paste(Image.fromarray(np.clip(rg, 0, 255).astype(np.uint8)), (x0, y0))
    height.paste(Image.fromarray(np.clip(hgt, 0, 255).astype(np.uint8)), (x0, y0))
    by = y0 + 4                                   # body v origin (nose)
    if not is_equip:
        L = s["L"]
        # nose / seeker / guidance-kit colour
        nose = s.get("nose", s["body"])
        if nose != s["body"]:
            if s.get("kit") in ("paveway", "paveway3"):
                ne = (0.75 if s["kit"] == "paveway" else 0.95) / L
            else:
                ne = nose_end(s)
            db.rectangle((x0, by, x0 + bw, by + ne * L * PPM), fill=tuple(nose))
            if nose == SD.GLASS:
                dr.rectangle((x0, by, x0 + bw, by + ne * L * PPM), fill=20)
        if s.get("kit") in ("jdam", "paveway", "paveway3"):
            t0 = s["profile"][-1][0]
            db.rectangle((x0, by + t0 * L * PPM, x0 + bw, y1), fill=SD.KIT)
            dr.rectangle((x0, by + t0 * L * PPM, x0 + bw, y1), fill=140)
        if s.get("kit") == "conical" or s.get("kit") == "snakeye":
            t0 = s["profile"][-1][0]
            db.rectangle((x0, by + t0 * L * PPM, x0 + bw, y1), fill=tuple(int(c * 0.92) for c in s["body"]))
        # colour bands
        for t, wid, c in s.get("bands", []):
            ya = by + t * L * PPM
            db.rectangle((x0, ya, x0 + bw, ya + wid * PPM), fill=c)
            dh.rectangle((x0, ya, x0 + bw, ya + wid * PPM), fill=140)
        # stencils on both sides (u = 0.25 and 0.75: right and left)
        txt = STENCIL.get(s["id"], s["id"])
        fill = (225, 190, 40) if s["body"] in (SD.OD, SD.OD_THERMAL) else (25, 25, 25)
        size = max(9, min(13, int(0.045 * PPM)))
        for fu in (0.25, 0.75):
            text_along((x0 + 4 + fu * (bw - 8), by + 0.30 * L * PPM), txt, size, fill)
        # lug area: handling scuffs and bare-metal sway-brace marks on top (u = 0.5)
        xa = 0.42 if s["cat"] in ("bomb", "guided_bomb", "cluster", "nuclear") else 0.48
        cx, cy = x0 + 4 + 0.5 * (bw - 8), by + xa * L * PPM
        for _ in range(int(25 + bw * 0.1)):
            sx = cx + rng.normal(0, bw * 0.08)
            sy = cy + rng.normal(0, 0.25 * PPM)
            ln = rng.uniform(3, 14)
            a = rng.uniform(0, math.pi)
            db.line((sx, sy, sx + ln * math.cos(a), sy + ln * math.sin(a)), fill=(150, 150, 140), width=1)
        # chips on the nose
        for _ in range(int(bw * 0.25)):
            px = rng.uniform(x0, x0 + bw)
            py = by + abs(rng.normal(0, 0.12 * PPM))
            r = rng.uniform(0.7, 2.2)
            db.ellipse((px - r, py - r, px + r, py + r), fill=(150, 150, 145))
            dm.ellipse((px - r, py - r, px + r, py + r), fill=170)
        # fin strip: body colour, worn leading edges
        if x1 - (x0 + bw) > 4:
            fx0 = x0 + bw
            fc = SD.KIT if s.get("kit") in ("jdam", "paveway", "paveway3") else s["body"]
            db.rectangle((fx0, y0, x1, y1), fill=tuple(int(c * 0.97) for c in fc))
            for _ in range(int(h * 0.05)):
                py = rng.uniform(y0, y1)
                db.line((fx0 + 4, py, fx0 + 4 + rng.uniform(2, 10), py), fill=(160, 160, 150), width=1)
    else:
        # suspension equipment: panel lines, fasteners, sway-brace wear underneath (u 0.4..0.6)
        Lp = s["L"] * PPM
        for k in range(1, int(s["L"] / 0.4)):
            yy = by + k * 0.4 * PPM
            db.line((x0, yy, x0 + bw, yy), fill=tuple(int(c * 0.7) for c in s["body"]), width=1)
            dh.line((x0, yy, x0 + bw, yy), fill=100, width=1)
        for yy in np.arange(by + 6, by + Lp, 9):
            for fu in (0.05, 0.95):
                px = x0 + fu * bw
                db.ellipse((px - 1.2, yy - 1.2, px + 1.2, yy + 1.2), fill=tuple(int(c * 0.8) for c in s["body"]))
        db.rectangle((x0 + 0.42 * bw, by + 0.3 * Lp, x0 + 0.58 * bw, by + 0.7 * Lp), fill=(70, 72, 72))
        for _ in range(60):
            px = rng.uniform(x0 + 0.40 * bw, x0 + 0.60 * bw)
            py = rng.uniform(by + 0.25 * Lp, by + 0.75 * Lp)
            db.line((px, py, px + rng.uniform(-4, 4), py + rng.uniform(4, 16)), fill=(150, 150, 146))
            dm.point((px, py), fill=200)
        text_along((x0 + 0.15 * bw, by + 0.2 * Lp), STENCIL.get(s["id"], s["id"]), 10, (40, 40, 40))
    # grime streaking aft and general dirt
    region = np.asarray(base.crop((x0, y0, x1, y1)), np.float32)
    st = noise(w, h, 2, 3, seed=sum(map(ord, s["id"])) * 3)
    streak = np.asarray(Image.fromarray((st * 255).astype(np.uint8)).resize((w, max(2, h // 12))).resize(
        (w, h), Image.BICUBIC), np.float32) / 255
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    k = np.clip((streak - 0.45) * 1.6, 0, 1) * (0.25 + 0.5 * yy) * (0.6 if not is_equip else 0.9)
    region = region * (1 - k[..., None] * 0.55) + np.array((30, 28, 22), np.float32) * (k[..., None] * 0.55)
    base.paste(Image.fromarray(np.clip(region, 0, 255).astype(np.uint8)), (x0, y0))


def normal_from_height(h, strength=2.5):
    a = np.asarray(h.filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 255.0
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, 1:-1] = (a[:, 2:] - a[:, :-2]) * 0.5
    gy[1:-1, :] = (a[2:, :] - a[:-2, :]) * 0.5
    nx, ny, nz = -gx * strength * 10, gy * strength * 10, np.ones_like(a)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    return Image.fromarray(((np.stack([nx / ln, ny / ln, nz / ln], -1) * 0.5 + 0.5) * 255).astype(np.uint8))


def main():
    os.makedirs(OUT, exist_ok=True)
    rects = SD.pack()
    for s in SD.all_items():
        paint_item(s, rects[s["id"]])
    base.save(os.path.join(OUT, "stores_basecolor.jpg"), quality=92, subsampling=0)
    Image.merge("RGB", (Image.new("L", (A, A), 255), rough, metal)).save(os.path.join(OUT, "stores_orm.png"),
                                                                          optimize=True)
    normal_from_height(height).save(os.path.join(OUT, "stores_normal.jpg"), quality=95, subsampling=0)
    print("wrote stores textures")


if __name__ == "__main__":
    main()
