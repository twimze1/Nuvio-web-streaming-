"""
Paint the cockpit texture atlas and display images (PIL + numpy, no Blender).

    python tools/make_cockpit_textures.py            # writes aircraft/textures/

Outputs (all from the layout in cockpit_layout.py, so legends sit on the
modelled parts):
    cockpit_basecolor.png   sRGB albedo, 4096^2
    cockpit_orm.png         R = ambient occlusion, G = roughness, B = metallic
    cockpit_normal.png      OpenGL-style tangent-space normal (+Y up)
    display_DDI_L.png, display_DDI_R.png, display_HSD.png,
    display_UFC.png, display_HUD.png (RGBA)
The finish is deliberately worn: scuffed black paint, edge wear to primer
and metal, grime in corners, polished patches where hands and boots rub.
Display images are representative formats in Hornet style; a game would
normally render these live onto the separate display meshes.
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import cockpit_layout as L  # noqa: E402

OUT = os.path.join(HERE, "..", "textures")
A = L.ATLAS
rng = np.random.default_rng(1818)

FONT_B = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_R = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
FONT_M = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
_fonts = {}


def font(size, kind="b"):
    key = (size, kind)
    if key not in _fonts:
        path = {"b": FONT_B, "r": FONT_R, "m": FONT_M}[kind]
        _fonts[key] = ImageFont.truetype(path, size)
    return _fonts[key]


# FS 595 colours (approximate sRGB)
BLACK = (27, 27, 29)            # FS 37038 instrument black
GULL = (93, 96, 97)             # FS 36231 dark gull grey, cockpit interior
LEGEND = (226, 226, 218)
PRIMER = (120, 128, 108)        # zinc-chromate-ish primer showing through

base = Image.new("RGB", (A, A), BLACK)
height = Image.new("L", (A, A), 128)
rough = Image.new("L", (A, A), 170)
metal = Image.new("L", (A, A), 0)
db, dh, dr, dm = (ImageDraw.Draw(i) for i in (base, height, rough, metal))


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def text_c(draw, xy, s, size, fill, kind="b", spacing=1):
    """Centred multi-line text."""
    f = font(size, kind)
    lines = s.split("\n")
    hgt = size * len(lines) + spacing * (len(lines) - 1)
    y = xy[1] - hgt / 2
    for line in lines:
        w = draw.textlength(line, font=f)
        draw.text((xy[0] - w / 2, y), line, font=f, fill=fill)
        y += size + spacing


def P(region, u, v):
    """Panel mm -> atlas pixel (x, y)."""
    x0, y0, x1, y1 = L.REGION[region]
    return ((x0 + x1) / 2 + u * L.PX_PER_MM, y0 + 10 + v * L.PX_PER_MM)


def R(region, rect):
    a = P(region, rect[0], rect[1])
    b = P(region, rect[2], rect[3])
    return (a[0], a[1], b[0], b[1])


def dzus(x, y, r=5):
    """Quarter-turn fastener: bright rim, dark slot, slight dome."""
    db.ellipse((x - r, y - r, x + r, y + r), fill=(70, 70, 70), outline=(110, 110, 108))
    db.line((x - r + 1, y, x + r - 1, y), fill=(20, 20, 20), width=2)
    dh.ellipse((x - r, y - r, x + r, y + r), fill=168)
    dh.line((x - r + 1, y, x + r - 1, y), fill=110, width=2)
    dm.ellipse((x - r, y - r, x + r, y + r), fill=200)
    dr.ellipse((x - r, y - r, x + r, y + r), fill=110)


def hatch(rect, period=14, width=7, c0=(205, 165, 30), c1=(20, 20, 20)):
    """Yellow / black hazard stripes clipped to rect."""
    x0, y0, x1, y1 = [int(round(v)) for v in rect]
    w, hh = max(1, x1 - x0), max(1, y1 - y0)
    tile = Image.new("RGB", (w, hh), c0)
    d = ImageDraw.Draw(tile)
    for t in range(-hh, w + hh, max(2, int(period))):
        d.polygon([(t, hh), (t + width, hh), (t + width + hh, 0), (t + hh, 0)], fill=c1)
    base.paste(tile, (x0, y0))


def bevel_rect(rect, fill, edge_hi=(70, 70, 72), h_in=150, h_edge=175):
    x0, y0, x1, y1 = rect
    db.rectangle(rect, fill=fill)
    db.rectangle(rect, outline=edge_hi)
    dh.rectangle(rect, fill=h_in)
    dh.rectangle(rect, outline=h_edge, width=2)


def noise(w, h, scale, octaves=4, seed=None):
    """Value noise (0..1) by summing upsampled random grids."""
    r = np.random.default_rng(seed) if seed is not None else rng
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        cells = max(2, int(scale * 2 ** o))
        g = r.random((cells, cells)).astype(np.float32)
        img = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        out += amp * np.asarray(img, np.float32) / 255
        tot += amp
        amp *= 0.5
    return out / tot


def scratches(rect, count, colour, length=(4, 26), width=1, alpha=60, bias_bottom=0.0):
    """Thin random scratches (lighter paint wear) inside rect."""
    x0, y0, x1, y1 = [int(v) for v in rect]
    layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    hl = ImageDraw.Draw(height)
    for _ in range(count):
        fy = rng.random() ** (1.0 / (1.0 + bias_bottom * 3))
        x = rng.uniform(0, x1 - x0)
        y = fy * (y1 - y0)
        a = rng.uniform(0, math.pi)
        ln = rng.uniform(*length)
        x2, y2 = x + ln * math.cos(a), y + ln * math.sin(a)
        d.line((x, y, x2, y2), fill=colour + (int(alpha * rng.uniform(0.4, 1.0)),), width=width)
        hl.line((x0 + x, y0 + y, x0 + x2, y0 + y2), fill=118, width=width)
    base.paste(layer, (x0, y0), layer)


def grime(rect, strength=0.35, scale=6, dark=(10, 10, 8), mask_edges=True, seed=None):
    """Multiply-darken with noise, heavier toward the edges of rect."""
    x0, y0, x1, y1 = [int(v) for v in rect]
    w, h = x1 - x0, y1 - y0
    if w < 4 or h < 4:
        return
    n = noise(w, h, scale, seed=seed)
    if mask_edges:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        e = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy))
        edge = np.clip(1 - e / max(6.0, min(w, h) * 0.12), 0, 1)
        n = np.clip(n * 0.6 + edge * 0.7, 0, 1)
    region = np.asarray(base.crop((x0, y0, x1, y1)), np.float32)
    k = (n ** 1.6 * strength)[..., None]
    region = region * (1 - k) + np.array(dark, np.float32) * k
    base.paste(Image.fromarray(np.clip(region, 0, 255).astype(np.uint8)), (x0, y0))


def edge_wear(rect, width=3, prob=0.35, colour=(118, 118, 112), primer=False):
    """Paint rubbed off along the edges of a raised part (to primer / metal)."""
    x0, y0, x1, y1 = [int(v) for v in rect]
    pts = []
    for x in range(x0, x1, 3):
        pts += [(x, y0), (x, y1)]
    for y in range(y0, y1, 3):
        pts += [(x0, y), (x1, y)]
    for x, y in pts:
        if rng.random() < prob:
            r = rng.uniform(1, width)
            c = PRIMER if (primer and rng.random() < 0.3) else colour
            db.ellipse((x - r, y - r, x + r, y + r), fill=c)
            dm.ellipse((x - r, y - r, x + r, y + r), fill=0 if c == PRIMER else 160)
            dr.ellipse((x - r, y - r, x + r, y + r), fill=120)


# ----------------------------------------------------------------------------
# main instrument panels
# ----------------------------------------------------------------------------
LIGHT = {"red": (150, 30, 25), "amber": (170, 120, 20), "green": (40, 130, 60)}
DDI_LEGENDS_L = ["STRS", "RDR", "HSI", "FLIR", "BIT", "SMS", "", "", "", "MENU",
                 "CHKLST", "FCS", "ENG", "FUEL", "ADI", "", "", "", "", ""]
DDI_LEGENDS_R = ["RWS", "TWS", "VS", "ACM", "BIT", "", "", "", "", "MENU",
                 "PRF", "SCAN", "BARS", "AZ", "DCLTR", "", "", "", "", "SIL"]


def paint_items(items, Pf, Rf):
    """Paint panel items; Pf maps (u, v) mm to a pixel, Rf a rect."""
    for e in items:
        k = e["kind"]
        if k in ("plate", "placard"):
            r = Rf(e["rect"])
            bevel_rect(r, BLACK)
            if k == "plate":
                for fx, fy in ((r[0] + 9, r[1] + 9), (r[2] - 9, r[1] + 9), (r[0] + 9, r[3] - 9), (r[2] - 9, r[3] - 9)):
                    dzus(fx, fy)
            else:
                db.rectangle((r[0] + 3, r[1] + 3, r[2] - 3, r[3] - 3), outline=(150, 150, 140), width=1)
                text_c(db, ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2), e["text"], 11, LEGEND, spacing=3)
            edge_wear(r, width=2.5, prob=0.18)
            scratches(r, 8, (150, 150, 145), (3, 14))
        elif k == "button":
            r = Rf(e["rect"])
            col = e.get("colour", "green")
            if col == "stripe":
                hatch(r)
                db.rectangle((r[0] + 6, r[1] + 6, r[2] - 6, r[3] - 6), fill=(25, 25, 25))
                text_c(db, ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2), e["legend"], 13, LEGEND)
            else:
                db.rectangle(r, fill=(16, 16, 17), outline=(60, 60, 60))
                lc = tuple(int(c * 0.75) for c in LIGHT[col])
                size = 10 if (r[3] - r[1]) < 34 else 12 if (r[3] - r[1]) < 40 else 15
                text_c(db, ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2), e["legend"], size, lc)
            dh.rectangle(r, outline=176, width=2)
            dr.rectangle(r, fill=90)                         # lens faces are glossy
        elif k == "caution":
            r = Rf(e["rect"])
            db.rectangle(r, fill=(20, 20, 21), outline=(80, 80, 80), width=2)
            cols = e["cols"]
            rows = (len(e["legends"]) + cols - 1) // cols
            w, hgt = (r[2] - r[0] - 8) / cols, (r[3] - r[1] - 8) / rows
            for n, lg in enumerate(e["legends"]):
                cx0 = r[0] + 4 + (n % cols) * w
                cy0 = r[1] + 4 + (n // cols) * hgt
                cell = (cx0 + 2, cy0 + 2, cx0 + w - 2, cy0 + hgt - 2)
                db.rectangle(cell, fill=(12, 12, 12), outline=(55, 55, 55))
                if lg:
                    text_c(db, ((cell[0] + cell[2]) / 2, (cell[1] + cell[3]) / 2), lg, 10,
                           tuple(int(c * 0.75) for c in LIGHT["amber"]))
            dr.rectangle(r, fill=90)
        elif k == "toggle":
            x, y = Pf(*e["c"])
            db.ellipse((x - 13, y - 13, x + 13, y + 13), fill=(48, 48, 48), outline=(95, 95, 92))
            dm.ellipse((x - 13, y - 13, x + 13, y + 13), fill=170)
            text_c(db, (x, y - 34), e["legend"], 13 if "\n" not in e["legend"] else 11, LEGEND)
        elif k == "knob":
            x, y = Pf(*e["c"])
            r = e["r"] * 2
            for a in range(-135, 136, 45):                    # detent marks
                t = math.radians(a - 90)
                db.line((x + (r + 4) * math.cos(t), y + (r + 4) * math.sin(t),
                         x + (r + 11) * math.cos(t), y + (r + 11) * math.sin(t)), fill=LEGEND, width=2)
            text_c(db, (x, y + r + 20), e["legend"], 12, LEGEND)
        elif k == "lcd":
            r = Rf(e["rect"])
            db.rectangle(r, fill=(96, 104, 86), outline=(30, 30, 30), width=3)
            text_c(db, ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2), e["text"], 26, (28, 32, 24), "m")
            dr.rectangle(r, fill=60)
        elif k == "gauge":
            x, y = Pf(*e["c"])
            r = e["r"] * 2 + 8
            db.ellipse((x - r, y - r, x + r, y + r), fill=(14, 14, 14))
        elif k == "wheel":                                     # gear handle slot, UP above, DN below
            x, y = Pf(*e["c"])
            db.rounded_rectangle((x - 12, y - 140, x + 12, y + 22), 10, fill=(8, 8, 8), outline=(90, 90, 88))
            dh.rounded_rectangle((x - 12, y - 140, x + 12, y + 22), 10, fill=60)
            text_c(db, (x + 34, y - 125), "UP", 13, LEGEND)
            text_c(db, (x + 34, y + 2), "DN", 13, LEGEND)
            text_c(db, (x - 46, y + 30), e["legend"], 11, LEGEND)
        elif k == "tee":                                       # yellow/black striped plate behind a pull handle
            x, y = Pf(*e["c"])
            w = 34 if e.get("small") else 54
            rr = (x - w, y - 22, x + w, y + 22)
            hatch(rr)
            text_c(db, (x, y - 46), e["legend"], 11, LEGEND)
        elif k == "hook":
            x, y = Pf(*e["c"])
            db.rounded_rectangle((x - 10, y - 18, x + 10, y + 180), 9, fill=(8, 8, 8), outline=(90, 90, 88))
            text_c(db, (x - 34, y - 6), "UP", 12, LEGEND)
            text_c(db, (x - 34, y + 160), "DN", 12, LEGEND)
            text_c(db, (x, y - 40), e["legend"], 13, LEGEND)
        elif k == "fold":
            x, y = Pf(*e["c"])
            for lab, dy in (("SPREAD", -60), ("HOLD", 0), ("FOLD", 60)):
                text_c(db, (x + 68, y + dy), lab, 11, LEGEND)
                db.line((x + 30, y + dy, x + 42, y + dy), fill=LEGEND, width=2)
            text_c(db, (x, y - 92), e["legend"] + "\nPULL TO UNLOCK", 11, LEGEND)
        elif k == "lever":
            x, y = Pf(*e["c"])
            for lab, a in (("NORM", -40), ("SOLO", 0), ("AFT\nINITIATE", 40)):
                t = math.radians(a - 90)
                text_c(db, (x + 70 * math.cos(t), y + 70 * math.sin(t)), lab, 10, LEGEND)
            rr = (x - 30, y + 26, x + 30, y + 44)
            db.rectangle(rr, fill=(205, 165, 30))
            text_c(db, (x, y + 64), e["legend"], 11, LEGEND)
        elif k in ("ddi", "hsd"):
            r = Rf(e["rect"])
            bevel_rect(r, BLACK)
            sc = Rf(e["screen"])
            db.rectangle(sc, fill=(6, 8, 6))
            for fx, fy in ((r[0] + 12, r[1] + 12), (r[2] - 12, r[1] + 12), (r[0] + 12, r[3] - 12), (r[2] - 12, r[3] - 12)):
                dzus(fx, fy, 6)
            cu = (e["rect"][0] + e["rect"][2]) / 2
            legends = (DDI_LEGENDS_L if cu < 0 else DDI_LEGENDS_R) if k == "ddi" else [""] * 20
            for (u, v), lg in zip(L.bezel_buttons(e), legends):
                x, y = Pf(u, v)
                db.rectangle((x - 14, y - 14, x + 14, y + 14), fill=(58, 60, 60), outline=(90, 90, 90))
                db.rectangle((x - 9, y - 2, x + 9, y + 2), fill=(150, 150, 140))      # finger groove
                dh.rectangle((x - 9, y - 2, x + 9, y + 2), fill=112)
                # hands polish the most-used buttons
                if rng.random() < 0.5:
                    db.ellipse((x - 8, y - 8, x + 8, y + 8), outline=(95, 97, 96))
            for u, v, rr, lg in e.get("knobs", []):
                x, y = Pf(u, v)
                text_c(db, (x, y - rr * 2 - 14), lg, 11, LEGEND)
            edge_wear(r, width=3, prob=0.22, primer=True)
            scratches(r, 14, (140, 140, 136), (3, 16))
        elif k == "ufc":
            r = Rf(e["rect"])
            bevel_rect(r, BLACK)
            o = e["keypad"]["origin"]
            pu, pv = e["keypad"]["pitch"]
            letters = {"2": "N", "4": "W", "6": "E", "8": "S"}
            for ri, row in enumerate(e["keypad"]["rows"]):
                for ci, ch in enumerate(row):
                    u = o[0] + ci * pu + 9
                    v = o[1] + ri * pv + 9
                    x, y = Pf(u, v)
                    db.rectangle((x - 18, y - 18, x + 18, y + 18), fill=(40, 41, 41), outline=(100, 100, 98))
                    lbl = {"C": "CLR", "E": "ENT"}.get(ch, ch)
                    if ch in letters:
                        text_c(db, (x, y - 7), letters[ch], 11, LEGEND)
                        text_c(db, (x, y + 7), lbl, 16, LEGEND)
                    else:
                        text_c(db, (x, y), lbl, 16 if len(lbl) == 1 else 12, LEGEND)
                    db.ellipse((x - 10, y - 10, x + 10, y + 10), outline=(70, 72, 72))   # finger wear
            for u0, v0, u1, v1 in [e["scratchpad"]] + e["options"]:
                rr = Rf((u0, v0, u1, v1))
                db.rectangle(rr, fill=(5, 7, 5), outline=(70, 70, 70))
            for u, v in e["option_buttons"]:
                x, y = Pf(u, v)
                db.ellipse((x - 12, y - 12, x + 12, y + 12), fill=(45, 45, 45), outline=(110, 110, 105))
            fu0, fv0, fu1, fv1 = e["function_row"]
            n = len(e["functions"])
            w = (fu1 - fu0) / n
            for i, lg in enumerate(e["functions"]):
                rr = Rf((fu0 + i * w + 2, fv0, fu0 + (i + 1) * w - 2, fv1))
                db.rectangle(rr, fill=(40, 41, 41), outline=(100, 100, 98))
                text_c(db, ((rr[0] + rr[2]) / 2, (rr[1] + rr[3]) / 2), lg, 11, LEGEND)
            for u, v, rr, lg in e["knobs"]:
                x, y = Pf(u, v)
                text_c(db, (x, y + rr * 2 + 12), lg, 11, LEGEND)
            x, y = Pf(98, 135 + e.get("dv", 0))
            text_c(db, (x, y), "EMCON", 11, LEGEND)
            edge_wear(r, width=3, prob=0.25, primer=True)
            scratches(r, 16, (140, 140, 136), (3, 14))


def paint_mip(region, layout):
    outline = [P(region, u, v) for u, v in L.MIP_OUTLINE]
    db.polygon(outline, fill=GULL)
    dh.polygon(outline, fill=128)
    dr.polygon(outline, fill=175)
    x0, y0, x1, y1 = L.REGION[region]
    grime((x0, y0, x1, y1), strength=0.18, scale=5)
    paint_items(layout, lambda u, v: P(region, u, v), lambda r: R(region, r))
    # boots and knees scuff the lower edge, gloves the area round the UFC
    lo = (x0, y0 + 900, x1, y0 + 1200)
    scratches(lo, 90, (150, 150, 146), (4, 28), width=1, alpha=55)
    grime((x0, y0, x1, y1), strength=0.12, scale=12, mask_edges=False)


def paint_sub(sp):
    """A knee panel or pedestal: its backing plate and items."""
    region, rect = sp["region"], sp["rect"]
    Pf = lambda u, v: L.sub_px(region, rect, u, v)
    Rf = lambda r: Pf(r[0], r[1]) + Pf(r[2], r[3])
    x0, y0, x1, y1 = L.REGION[region]
    db.rectangle((x0, y0, x1, y1), fill=GULL)
    dh.rectangle((x0, y0, x1, y1), fill=128)
    dr.rectangle((x0, y0, x1, y1), fill=175)
    grime((x0, y0, x1, y1), strength=0.18, scale=5)
    paint_items(sp["items"], Pf, Rf)
    scratches((x0, y0, x1, y1), 50, (150, 150, 146), (4, 24), width=1, alpha=55)   # knees and boots
    grime((x0, y0, x1, y1), strength=0.14, scale=10, mask_edges=False)


# ----------------------------------------------------------------------------
# gauges
# ----------------------------------------------------------------------------
def gauge_centre(face):
    return L.gauge_centre_px(face)


def dial(cx, cy, r, a0, a1, majors, minors, labels=None, lsize=14):
    for i in range(minors + 1):
        a = math.radians(a0 + (a1 - a0) * i / minors - 90)
        big = (i % (minors // majors) == 0) if majors else False
        r0 = r - (14 if big else 7)
        db.line((cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + (r - 2) * math.cos(a), cy + (r - 2) * math.sin(a)),
                fill=LEGEND, width=3 if big else 1)
    if labels:
        for i, lab in enumerate(labels):
            a = math.radians(a0 + (a1 - a0) * i / (len(labels) - 1) - 90)
            text_c(db, (cx + (r - 28) * math.cos(a), cy + (r - 28) * math.sin(a)), lab, lsize, LEGEND)


def needle(cx, cy, length, ang, colour=LEGEND, w=5):
    a = math.radians(ang - 90)
    db.line((cx - 12 * math.cos(a), cy - 12 * math.sin(a), cx + length * math.cos(a), cy + length * math.sin(a)),
            fill=colour, width=w)
    db.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=(60, 60, 60))


def paint_gauges():
    x0, y0, x1, y1 = L.REGION["gauges"]
    db.rectangle((x0, y0, x1, y1), fill=(12, 12, 12))
    R_ = 96
    # ADI: grey sky over black ground, pitch lines, bank scale, orange aircraft symbol
    cx, cy = gauge_centre("adi")
    db.pieslice((cx - R_, cy - R_, cx + R_, cy + R_), 180, 360, fill=(165, 165, 160))
    db.pieslice((cx - R_, cy - R_, cx + R_, cy + R_), 0, 180, fill=(30, 30, 30))
    db.line((cx - R_, cy, cx + R_, cy), fill=(240, 240, 235), width=3)
    for p in (-20, -10, 10, 20):
        y = cy - p * 2.2
        w = 26 if abs(p) == 10 else 40
        db.line((cx - w, y, cx + w, y), fill=(20, 20, 20) if p > 0 else (230, 230, 225), width=2)
    for a in (-60, -30, -20, -10, 0, 10, 20, 30, 60):
        t = math.radians(a - 90)
        db.line((cx + 78 * math.cos(t), cy + 78 * math.sin(t), cx + 94 * math.cos(t), cy + 94 * math.sin(t)),
                fill=(240, 240, 235), width=3)
    db.line((cx - 50, cy + 4, cx - 18, cy + 4), fill=(235, 120, 20), width=6)
    db.line((cx + 18, cy + 4, cx + 50, cy + 4), fill=(235, 120, 20), width=6)
    db.ellipse((cx - 5, cy - 1, cx + 5, cy + 9), fill=(235, 120, 20))
    # RWR azimuth indicator
    cx, cy = gauge_centre("rwr")
    db.ellipse((cx - R_, cy - R_, cx + R_, cy + R_), fill=(8, 12, 8))
    for rr in (32, 62, 92):
        db.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(50, 110, 55), width=2)
    for a in range(0, 360, 30):
        t = math.radians(a)
        db.line((cx + 20 * math.cos(t), cy + 20 * math.sin(t), cx + 92 * math.cos(t), cy + 92 * math.sin(t)),
                fill=(35, 80, 40), width=1)
    # airspeed
    cx, cy = gauge_centre("asi")
    db.ellipse((cx - R_, cy - R_, cx + R_, cy + R_), fill=(16, 16, 16))
    dial(cx, cy, R_, 0, 340, 9, 45, ["0", "1", "2", "3", "4", "5", "6", "7", "8"], 15)
    text_c(db, (cx, cy + 34), "KNOTS\nx100", 11, LEGEND)
    needle(cx, cy, 80, 70)
    # altimeter
    cx, cy = gauge_centre("alt")
    db.ellipse((cx - R_, cy - R_, cx + R_, cy + R_), fill=(16, 16, 16))
    dial(cx, cy, R_, 0, 324, 9, 50, [str(i) for i in range(10)], 15)
    db.rectangle((cx - 34, cy - 14, cx + 34, cy + 14), fill=(4, 4, 4), outline=(90, 90, 90))
    text_c(db, (cx, cy), "15 0", 20, LEGEND, "m")
    text_c(db, (cx, cy + 40), "ALT", 12, LEGEND)
    needle(cx, cy, 82, 0)
    # vertical speed
    cx, cy = gauge_centre("vsi")
    db.ellipse((cx - R_, cy - R_, cx + R_, cy + R_), fill=(16, 16, 16))
    dial(cx, cy, R_, 100, 440, 6, 36, ["6", "4", "2", "0", "2", "4", "6"], 15)
    text_c(db, (cx + 30, cy - 30), "UP", 12, LEGEND)
    text_c(db, (cx + 30, cy + 30), "DOWN", 12, LEGEND)
    text_c(db, (cx - 10, cy + 50), "x1000 FT/MIN", 10, LEGEND)
    needle(cx, cy, 80, 270)
    # fuel quantity
    cx, cy = gauge_centre("fuel")
    db.ellipse((cx - R_, cy - R_, cx + R_, cy + R_), fill=(16, 16, 16))
    dial(cx, cy, R_, -135, 135, 6, 24, ["0", "2", "4", "6", "8", "10", "12"], 14)
    text_c(db, (cx, cy - 30), "FUEL QTY", 11, LEGEND)
    for sx in (-28, 28):
        db.rectangle((cx + sx - 20, cy + 30, cx + sx + 20, cy + 46), fill=(4, 4, 4), outline=(90, 90, 90))
    text_c(db, (cx - 28, cy + 58), "LEFT", 10, LEGEND)
    text_c(db, (cx + 28, cy + 58), "RIGHT", 10, LEGEND)
    needle(cx, cy, 78, 40)
    # nozzle position (small dials, labels kept large to read at size)
    cx, cy = gauge_centre("noz")
    db.ellipse((cx - R_, cy - R_, cx + R_, cy + R_), fill=(16, 16, 16))
    dial(cx, cy, R_, -120, 120, 4, 20, ["0", "", "50", "", "100"], 22)
    needle(cx, cy, 80, -90, w=8)
    # clock
    cx, cy = gauge_centre("clock")
    db.ellipse((cx - R_, cy - R_, cx + R_, cy + R_), fill=(16, 16, 16))
    dial(cx, cy, R_, 0, 330, 12, 60, ["12", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"], 14)
    needle(cx, cy, 55, 300)
    needle(cx, cy, 80, 60, w=3)
    # second row (gauges2): knee-panel and console gauges
    x0b, y0b, x1b, y1b = L.REGION["gauges2"]
    db.rectangle((x0b, y0b, x1b, y1b), fill=(12, 12, 12))
    cx, cy = gauge_centre("brake")                      # brake accumulator pressure
    db.ellipse((cx - R_, cy - R_, cx + R_, cy + R_), fill=(16, 16, 16))
    dial(cx, cy, R_, -120, 120, 4, 20, ["0", "1", "2", "3", "4"], 16)
    text_c(db, (cx, cy + 40), "BRAKE\nPSI x1000", 11, LEGEND)
    needle(cx, cy, 78, 55)
    cx, cy = gauge_centre("hyd")                        # HYD 1 and 2 pressure, two needles
    db.ellipse((cx - R_, cy - R_, cx + R_, cy + R_), fill=(16, 16, 16))
    dial(cx, cy, R_, -130, 130, 5, 25, ["0", "1", "2", "3", "4", "5"], 15)
    text_c(db, (cx, cy + 42), "HYD\nPSI x1000", 11, LEGEND)
    needle(cx, cy, 76, 78)
    needle(cx, cy, 64, 82, colour=(230, 230, 120), w=4)
    text_c(db, (cx - 22, cy - 26), "1", 14, LEGEND)
    text_c(db, (cx + 22, cy - 26), "2", 14, (230, 230, 120))
    cx, cy = gauge_centre("radalt")                     # radar altimeter
    db.ellipse((cx - R_, cy - R_, cx + R_, cy + R_), fill=(16, 16, 16))
    dial(cx, cy, R_, 0, 330, 6, 30, ["0", "1", "2", "3", "4", "5"], 15)
    db.ellipse((cx - 70, cy - 82, cx - 54, cy - 66), fill=(150, 30, 25))      # low-altitude warning light
    text_c(db, (cx, cy + 40), "RADAR\nALT x1000", 11, LEGEND)
    needle(cx, cy, 78, 20)
    cx, cy = gauge_centre("cabalt")                     # cockpit altimeter
    db.ellipse((cx - R_, cy - R_, cx + R_, cy + R_), fill=(16, 16, 16))
    dial(cx, cy, R_, 0, 300, 5, 25, ["0", "10", "20", "30", "40", "50"], 14)
    text_c(db, (cx, cy + 40), "CABIN ALT\nx1000 FT", 11, LEGEND)
    needle(cx, cy, 78, 40)
    cx, cy = gauge_centre("lox")                        # liquid oxygen quantity
    db.ellipse((cx - R_, cy - R_, cx + R_, cy + R_), fill=(16, 16, 16))
    dial(cx, cy, R_, -135, 135, 5, 20, ["0", "2", "4", "6", "8", "10"], 15)
    text_c(db, (cx, cy + 40), "LIQUID OXYGEN\nLITERS", 10, LEGEND)
    needle(cx, cy, 78, 70)
    cx, cy = gauge_centre("volt")                       # DC voltmeter
    db.ellipse((cx - R_, cy - R_, cx + R_, cy + R_), fill=(16, 16, 16))
    dial(cx, cy, R_, -120, 120, 4, 16, ["16", "20", "24", "28", "32"], 15)
    text_c(db, (cx, cy + 40), "VOLTS", 12, LEGEND)
    needle(cx, cy, 78, 70)
    # glass sheen and dust
    for face in L.GAUGE_ORDER:
        cx, cy = gauge_centre(face)
        dr.ellipse((cx - R_, cy - R_, cx + R_, cy + R_), fill=40)
    grime((x0, y0, x1, y1), strength=0.15, scale=20, mask_edges=False)
    grime((x0b, y0b, x1b, y1b), strength=0.15, scale=20, mask_edges=False)


# ----------------------------------------------------------------------------
# consoles, rails, labels, material tiles
# ----------------------------------------------------------------------------
def paint_console(region, panels, side):
    """One side console: panels from cockpit_layout.CONSOLES, controls at the
    same places the model puts them.  t runs from the cockpit wall."""
    x0, y0, x1, y1 = L.REGION[region]
    k = L.REGION_PPM.get(region, L.PX_PER_MM)
    f = k / L.PX_PER_MM                                   # text and mark scale
    sz = lambda n: max(6, int(round(n * f)))
    db.rectangle((x0, y0, x1, y1), fill=GULL)
    X = lambda t: (x0 + t * k) if side < 0 else (x1 - t * k)
    for p in panels:
        s0, s1 = p["s"]
        t0, t1 = p.get("t", (0, L.CONSOLE_WIDTH))
        xa, xb = sorted((X(t0), X(t1)))
        r = (xa + 2, y0 + s0 * k + 2, xb - 2, y0 + s1 * k - 2)
        bevel_rect(r, BLACK)
        m = 10 * f
        for fx, fy in ((r[0] + m, r[1] + m), (r[2] - m, r[1] + m), (r[0] + m, r[3] - m), (r[2] - m, r[3] - m)):
            dzus(fx, fy, max(3, 5 * f))
        if p.get("name"):
            text_c(db, ((r[0] + r[2]) / 2, r[1] + 22 * f), p["name"], sz(13), LEGEND)
        if p.get("throttle"):
            db.rectangle((r[0] + 14 * f, r[1] + 50 * f, r[2] - 14 * f, r[3] - 40 * f), fill=(10, 10, 10))
            for n in range(9):
                yy = r[1] + 60 * f + n * (r[3] - r[1] - 110 * f) / 8
                db.line((r[0] + 4 * f, yy, r[0] + 12 * f, yy), fill=LEGEND, width=2)
            for lab, fy in (("MAX", 0.12), ("MIL", 0.35), ("IDLE", 0.72), ("OFF", 0.9)):
                text_c(db, (r[2] - 2 * f, r[1] + fy * (r[3] - r[1])), "", sz(10), LEGEND)
                text_c(db, (r[0] + 30 * f, r[1] + fy * (r[3] - r[1])), lab, sz(10), LEGEND)
            continue
        for c in p.get("controls", []):
            kind, fs, ft, lg = c[:4]
            ft = ft if side < 0 else 1.0 - ft                # across: from the pilot's left on both consoles
            px, py = X(t0 + ft * (t1 - t0)), y0 + (s0 + fs * (s1 - s0)) * k
            if kind == "toggle":
                rr = 11 * f
                db.ellipse((px - rr, py - rr, px + rr, py + rr), fill=(48, 48, 48), outline=(95, 95, 92))
                text_c(db, (px, py - 25 * f), lg, sz(10), LEGEND)
            elif kind == "knob":
                for a in range(-120, 121, 40):
                    tt = math.radians(a - 90)
                    db.line((px + 22 * f * math.cos(tt), py + 22 * f * math.sin(tt), px + 30 * f * math.cos(tt),
                             py + 30 * f * math.sin(tt)), fill=LEGEND, width=2)
                text_c(db, (px, py + 40 * f), lg, sz(10), LEGEND)
            elif kind == "button":
                rr = 9 * f
                db.rectangle((px - rr, py - rr, px + rr, py + rr), fill=(40, 41, 41), outline=(100, 100, 98))
                text_c(db, (px, py + 22 * f), lg, sz(9), LEGEND)
            elif kind == "gauge":
                rr = 50 * f
                db.ellipse((px - rr, py - rr, px + rr, py + rr), fill=(14, 14, 14))
            elif kind == "handle":
                rr = (px - 40 * f, py - 70 * f, px + 40 * f, py + 70 * f)
                hatch(rr, period=16 * f, width=8 * f)
                db.rectangle(rr, outline=(20, 20, 20), width=2)
                text_c(db, (px, rr[1] - 14 * f), lg, sz(10), LEGEND)
        edge_wear(r, 3, 0.25, primer=True)
        scratches(r, 10, (150, 150, 145), (3, 18))
    # arm and elbow wear along the outboard edge
    scratches((x0, y0, x1, y1), int(110 * f), (150, 150, 146), (4, 30), width=1, alpha=55)
    grime((x0, y0, x1, y1), strength=0.25, scale=8)


def paint_rail():
    """Sill longeron: black, a row of lightening holes, two rivet lines."""
    x0, y0, x1, y1 = L.REGION["rail"]
    db.rectangle((x0, y0, x1, y1), fill=(32, 33, 34))
    dh.rectangle((x0, y0, x1, y1), fill=128)
    for x in range(x0 + 40, x1, 80):
        r = 26
        cy = y0 + 110
        db.ellipse((x - r, cy - r, x + r, cy + r), fill=(6, 6, 6), outline=(70, 70, 68), width=3)
        dh.ellipse((x - r, cy - r, x + r, cy + r), fill=40)
        dh.ellipse((x - r, cy - r, x + r, cy + r), outline=170, width=4)
    for x in range(x0 + 10, x1, 26):
        for cy in (y0 + 30, y0 + 182):
            db.ellipse((x - 3, cy - 3, x + 3, cy + 3), fill=(80, 80, 78))
            dh.ellipse((x - 3, cy - 3, x + 3, cy + 3), fill=160)
            dm.ellipse((x - 3, cy - 3, x + 3, cy + 3), fill=180)
    scratches((x0, y0, x1, y0 + 60), 120, (150, 150, 145), (6, 40), width=1, alpha=80)   # top edge: helmets, sleeves
    edge_wear((x0, y0, x1, y0 + 4), 4, 0.6, colour=(130, 130, 126))
    grime((x0, y0, x1, y1), 0.3, 10)


def paint_labels():
    """Seat and canopy placards (not yet mapped; kept for future use)."""
    x0, y0, x1, y1 = L.REGION["labels"]
    db.rectangle((x0, y0, x1, y1), fill=BLACK)


TILE = {
    #  name        colour            rough  metal  scuff  grime  weave
    "black":     (BLACK,            0.62,  0.0,   1.0,   0.30,  0),
    "panel":     (GULL,             0.66,  0.0,   0.8,   0.35,  0),
    "darkgrey":  ((55, 57, 58),     0.64,  0.0,   0.9,   0.35,  0),
    "midgrey":   ((110, 112, 112),  0.62,  0.0,   0.7,   0.35,  0),
    "lightgrey": ((160, 162, 160),  0.60,  0.0,   0.5,   0.40,  0),
    "metal":     ((165, 165, 160),  0.38,  1.0,   0.6,   0.20,  0),
    "rubber":    ((24, 24, 24),     0.90,  0.0,   0.2,   0.25,  1),
    "cushion":   ((66, 68, 63),     0.88,  0.0,   0.2,   0.40,  2),
    "leather":   ((36, 36, 37),     0.55,  0.0,   0.5,   0.25,  0),
    "strap":     ((96, 101, 88),    0.85,  0.0,   0.2,   0.40,  3),
    "yellow":    ((212, 170, 32),   0.55,  0.0,   0.8,   0.30,  0),
    "red":       ((160, 32, 28),    0.55,  0.0,   0.6,   0.30,  0),
    "white":     ((225, 225, 218),  0.50,  0.0,   0.5,   0.35,  0),
    "green":     ((40, 120, 55),    0.55,  0.0,   0.5,   0.30,  0),
    "amber":     ((180, 120, 25),   0.55,  0.0,   0.5,   0.30,  0),
    "glow":      ((30, 70, 35),     0.30,  0.0,   0.0,   0.10,  0),
    "floor":     ((50, 51, 51),     0.80,  0.0,   1.0,   0.60,  4),
    "wall":      ((38, 39, 40),     0.70,  0.0,   0.6,   0.45,  0),
    "stripe":    ((212, 170, 32),   0.55,  0.0,   0.8,   0.30,  5),
    "olive":     ((78, 84, 60),     0.70,  0.0,   0.8,   0.40,  0),
    "canvas":    ((120, 116, 96),   0.90,  0.0,   0.2,   0.40,  2),
    "steel":     ((120, 122, 124),  0.45,  1.0,   0.6,   0.30,  0),
    "brass":     ((170, 140, 70),   0.40,  1.0,   0.3,   0.30,  0),
    "glass":     ((20, 24, 24),     0.08,  0.0,   0.2,   0.20,  0),
}


def paint_tiles():
    for name in L.CELLS:
        colour, rgh, mtl, scuff, grm, weave = TILE[name]
        x0, y0, x1, y1 = L.cell_rect(name)
        w = x1 - x0
        n = noise(w, w, 6, seed=L.CELLS.index(name) * 31 + 5)
        img = np.ones((w, w, 3), np.float32) * np.array(colour, np.float32)
        img *= (0.95 + 0.1 * n)[..., None]
        hgt = np.full((w, w), 128, np.float32)
        yy, xx = np.mgrid[0:w, 0:w]
        if weave == 1:          # rubber grain
            hgt += (noise(w, w, 60, 2, seed=7) - 0.5) * 30
        elif weave == 2:        # fabric weave
            hgt += 10 * np.sin(xx * 0.9) * np.sin(yy * 0.9)
        elif weave == 3:        # webbing: ribs along one direction
            hgt += 14 * np.sin(yy * 1.3)
            img *= (0.94 + 0.06 * np.sin(yy * 1.3))[..., None]
        elif weave == 4:        # non-skid grit
            g = rng.random((w, w)) > 0.82
            hgt += g * 26
            img *= (1 - 0.15 * g)[..., None]
        elif weave == 5:        # yellow / black handle stripes
            band = (((xx + yy) // 28) % 2) == 0
            img[band] = np.array((22, 22, 22), np.float32)
        tile = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
        base.paste(tile, (x0, y0))
        height.paste(Image.fromarray(np.clip(hgt, 0, 255).astype(np.uint8)), (x0, y0))
        dr.rectangle((x0, y0, x1, y1), fill=int(rgh * 255))
        dm.rectangle((x0, y0, x1, y1), fill=int(mtl * 255))
        if scuff:
            scratches((x0, y0, x1, y1), int(110 * scuff), (165, 165, 160) if name != "metal" else (210, 210, 205),
                      (4, 30), width=1, alpha=int(40 + 50 * scuff))
            # chips through to primer on painted tiles
            if mtl == 0 and name not in ("rubber", "cushion", "strap", "canvas", "glass"):
                for _ in range(int(60 * scuff)):
                    cx, cy = rng.uniform(x0, x1), rng.uniform(y0, y1)
                    r = rng.uniform(1.5, 6)
                    c = PRIMER if rng.random() < 0.4 else (140, 142, 140)
                    db.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c)
                    dh.ellipse((cx - r, cy - r, cx + r, cy + r), fill=112)
                    if c != PRIMER:
                        dm.ellipse((cx - r, cy - r, cx + r, cy + r), fill=180)
                        dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=100)
        grime((x0, y0, x1, y1), strength=grm * 0.5, scale=5, mask_edges=False, seed=L.CELLS.index(name) * 17 + 3)


# ----------------------------------------------------------------------------
# displays
# ----------------------------------------------------------------------------
G = (90, 255, 120)


def phosphor(img):
    """Green CRT glow: blur halo under crisp lines, faint raster."""
    glow = img.filter(ImageFilter.GaussianBlur(4))
    arr = np.maximum(np.asarray(img, np.float32), np.asarray(glow, np.float32) * 0.8)
    arr[::3] *= 0.92
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def disp_stores():
    im = Image.new("RGB", (1024, 1024), (2, 6, 3))
    d = ImageDraw.Draw(im)
    f = font(30, "m")
    # planform outline (simplified legacy Hornet) with the nine stations
    c = 512
    pts = [(c, 170), (c + 40, 320), (c + 60, 430), (c + 330, 560), (c + 330, 610), (c + 70, 600), (c + 60, 700),
           (c + 170, 790), (c + 170, 830), (c + 40, 810), (c, 860), (c - 40, 810), (c - 170, 830),
           (c - 170, 790), (c - 60, 700), (c - 70, 600), (c - 330, 610), (c - 330, 560), (c - 60, 430),
           (c - 40, 320)]
    d.line(pts + [pts[0]], fill=G, width=3)
    for x, lab in ((c - 330, "9L"), (c - 230, "7F"), (c - 130, "TANK"), (c, "TANK"), (c + 130, "TANK"),
                   (c + 230, "7F"), (c + 330, "9L")):
        w = d.textlength(lab, font=f)
        d.text((x - w / 2, 650), lab, font=f, fill=G)
    for x, y, lab in ((c - 110, 470, "7M"), (c + 110, 470, "7M")):
        d.text((x - 25, y), lab, font=f, fill=G)
    d.text((40, 40), "STORES", font=font(34, "m"), fill=G)
    d.text((720, 40), "SAFE", font=font(34, "m"), fill=G)
    d.text((40, 950), "GUN 578", font=f, fill=G)
    d.text((700, 950), "JETT", font=f, fill=G)
    return phosphor(im)


def disp_radar():
    im = Image.new("RGB", (1024, 1024), (2, 6, 3))
    d = ImageDraw.Draw(im)
    f = font(30, "m")
    d.rectangle((140, 140, 884, 884), outline=G, width=2)
    for i in range(1, 4):
        y = 140 + i * 744 / 4
        d.line((140, y, 160, y), fill=G, width=2)
    for i in range(1, 6):
        x = 140 + i * 744 / 6
        d.line((x, 884, x, 864), fill=G, width=2)
    d.text((60, 140), "80", font=f, fill=G)
    d.text((40, 40), "RWS", font=font(34, "m"), fill=G)
    d.text((440, 40), "MRM", font=f, fill=G)
    d.text((800, 40), "A 4", font=f, fill=G)
    for x, y in ((430, 360), (560, 410), (610, 300)):
        d.rectangle((x - 14, y - 6, x + 14, y + 6), fill=G)
    d.line((512, 884, 512, 860), fill=G, width=3)
    d.line((120, 512, 140, 512), fill=G, width=3)
    d.text((40, 950), "PRF MED", font=f, fill=G)
    d.text((760, 950), "SCAN", font=f, fill=G)
    return phosphor(im)


def disp_hsd():
    im = Image.new("RGB", (1024, 1024), (2, 6, 3))
    d = ImageDraw.Draw(im)
    c = 512
    # moving-map backdrop (subdued) under a compass rose
    n = noise(1024, 1024, 5, seed=3)
    arr = np.zeros((1024, 1024, 3), np.float32)
    arr[..., 1] = n * 50
    arr[..., 0] = n * 30
    arr[..., 2] = n * 20
    yy, xx = np.mgrid[0:1024, 0:1024]
    arr[(xx - c) ** 2 + (yy - c) ** 2 > 470 ** 2] = 4
    im = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(im)
    for k in range(0, 360, 10):
        a = math.radians(k - 90)
        r0 = 440 if k % 30 else 410
        d.line((c + r0 * math.cos(a), c + r0 * math.sin(a), c + 470 * math.cos(a), c + 470 * math.sin(a)),
               fill=G, width=3)
        if k % 30 == 0:
            lab = {0: "N", 90: "E", 180: "S", 270: "W"}.get(k, str(k // 10))
            w = d.textlength(lab, font=font(32, "m"))
            d.text((c + 370 * math.cos(a) - w / 2, c + 370 * math.sin(a) - 16), lab, font=font(32, "m"), fill=G)
    d.line((c, c - 30, c, c + 40), fill=G, width=4)
    d.line((c - 30, c + 5, c + 30, c + 5), fill=G, width=4)
    d.line((c, c, c + 160, c - 300), fill=G, width=2)
    d.ellipse((c + 150, c - 310, c + 170, c - 290), outline=G, width=3)
    return phosphor(im)


def disp_ufc():
    """Scratchpad (top fifth) and five option windows below it."""
    im = Image.new("RGB", (512, 1024), (2, 5, 2))
    d = ImageDraw.Draw(im)
    f = font(80, "m")
    d.text((40, 50), "1  300", font=f, fill=G)
    for i, lab in enumerate([":TCN", " T/R", " A/A", " X", " Y"]):
        y = 205 + 164 * i
        d.text((30, y + 30), lab, font=font(76, "m"), fill=G)
    return phosphor(im)


def disp_hud():
    im = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    g = (90, 255, 120, 255)
    f = font(34, "m")
    c = 512
    for p in (-10, -5, 5, 10):                         # pitch ladder
        y = c - p * 34
        dash = p < 0
        for sx in (-1, 1):
            x0, x1 = c + sx * 60, c + sx * 200
            if dash:
                for t in range(0, 140, 30):
                    d.line((c + sx * (60 + t), y, c + sx * (75 + t), y), fill=g, width=4)
            else:
                d.line((x0, y, x1, y), fill=g, width=4)
            d.line((x1, y, x1, y + (16 if p > 0 else -16)), fill=g, width=4)
            lab = str(abs(p))
            d.text((c + sx * 240 - 18, y - 18), lab, font=f, fill=g)
    d.line((c - 300, c, c - 80, c), fill=g, width=4)  # horizon
    d.line((c + 80, c, c + 300, c), fill=g, width=4)
    d.ellipse((c - 18, c + 22, c + 18, c + 58), outline=g, width=4)      # velocity vector
    d.line((c - 46, c + 40, c - 18, c + 40), fill=g, width=4)
    d.line((c + 18, c + 40, c + 46, c + 40), fill=g, width=4)
    d.line((c, c + 22, c, c + 6), fill=g, width=4)
    d.line((c - 40, c - 60, c - 14, c - 60), fill=g, width=4)            # waterline
    d.line((c + 14, c - 60, c + 40, c - 60), fill=g, width=4)
    d.rectangle((120, 470, 250, 520), outline=g, width=4)
    d.text((140, 474), "350", font=f, fill=g)
    d.rectangle((770, 470, 930, 520), outline=g, width=4)
    d.text((782, 474), "15000", font=f, fill=g)
    for i in range(-4, 5):                              # heading tape
        x = c + i * 70
        d.line((x, 80, x, 100 if i % 2 else 112), fill=g, width=4)
        if i % 2 == 0:
            d.text((x - 28, 120), "%03d" % ((360 + i * 5) % 360 // 10 * 10 // 10), font=f, fill=g)
    d.text((140, 560), "M 0.82", font=f, fill=g)
    d.text((140, 610), "G 1.0", font=f, fill=g)
    d.text((140, 830), "ARM", font=f, fill=g)
    d.text((780, 830), "9L 2", font=f, fill=g)
    glow = im.filter(ImageFilter.GaussianBlur(3))
    out = Image.alpha_composite(Image.new("RGBA", im.size, (0, 0, 0, 0)), glow)
    return Image.alpha_composite(out, im)


# ----------------------------------------------------------------------------
def normal_from_height(h, strength=3.0):
    a = np.asarray(h, np.float32) / 255.0
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, 1:-1] = (a[:, 2:] - a[:, :-2]) * 0.5
    gy[1:-1, :] = (a[2:, :] - a[:-2, :]) * 0.5
    nx, ny, nz = -gx * strength * 10, gy * strength * 10, np.ones_like(a)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.stack([nx / ln, ny / ln, nz / ln], -1) * 0.5 + 0.5
    return Image.fromarray((rgb * 255).astype(np.uint8))


def main():
    os.makedirs(OUT, exist_ok=True)
    paint_tiles()
    paint_mip("front_mip", L.FRONT_MIP)
    paint_mip("rear_mip", L.REAR_MIP)
    for st in ("Front", "Rear"):
        for sp in L.SUBPANELS[st]:
            paint_sub(sp)
        rl, rr = L.CONSOLE_REGIONS[st]
        paint_console(rl, L.CONSOLES[st]["L"], -1)
        paint_console(rr, L.CONSOLES[st]["R"], 1)
    paint_gauges()
    paint_rail()
    paint_labels()
    base.save(os.path.join(OUT, "cockpit_basecolor.png"), optimize=True)
    ao = Image.new("L", (A, A), 255)
    Image.merge("RGB", (ao, rough, metal)).save(os.path.join(OUT, "cockpit_orm.png"), optimize=True)
    normal_from_height(height.filter(ImageFilter.GaussianBlur(0.8))).save(
        os.path.join(OUT, "cockpit_normal.png"), optimize=True)
    disp_stores().save(os.path.join(OUT, "display_DDI_L.png"))
    disp_radar().save(os.path.join(OUT, "display_DDI_R.png"))
    disp_hsd().save(os.path.join(OUT, "display_HSD.png"))
    disp_hsd().save(os.path.join(OUT, "display_DDI_C.png"))         # rear centre DDI, HSI format
    disp_ufc().save(os.path.join(OUT, "display_UFC.png"))
    disp_hud().save(os.path.join(OUT, "display_HUD.png"))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
