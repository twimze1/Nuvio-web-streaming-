"""PBR materials and textures for the He 51 A-1.

Scheme (from the owner's screenshots): overall light grey (RLM 63), black
crosses with white edging on the fuselage sides, on top of the upper wing
and under the lower wing, two narrow black bands round the rear fuselage,
black-white-red stripes across the starboard side of the fin and rudder,
and a red band with a white disc on the port side.  The disc is left blank:
the swastika of the period is not drawn.

Fabric areas (wings, tail, rear fuselage) show rib tapes and stringers;
the metal nose shows panel seams and fasteners.  Weathering: exhaust soot
behind the stubs, oil along the belly, grime along ribs and seams, chipped
paint on the metal panels.  The node helper, the worn-finish material and
the bake are shared with ../p26a/p26a_materials.py.
"""
import math
import os

import bpy
import numpy as np

import he51 as H
import he51_cockpit as C
from p26a_materials import NT, worn, unwrap, bake_group, image_material

GREY = (0.325, 0.385, 0.375)             # RLM 63 light grey
RED = (0.58, 0.03, 0.014)
WHITE = (0.80, 0.80, 0.77)
BLACK = (0.012, 0.012, 0.012)
SOOT = (0.012, 0.011, 0.010)
ALUMINIUM = (0.60, 0.60, 0.61)
CROSS = dict(fuselage=(5.0, 0.10, 0.95), upper=(2.58, 4.30, 1.42), lower=(2.89, 3.20, 0.95))
BANDS = (5.895, 6.035, 0.035)          # two fuselage bands: centres, half-width
TAIL_BAND = (0.57, 1.17)               # z range of the tail markings
TAIL_DISC = (7.74, 0.23)               # white disc on the port side: centre x, radius
GROUPS = {
    "ext": (4096, ["Fuselage", "UpperWing", "Aileron_L", "Aileron_R", "LowerWing", "Tailplane", "Elevator_L", "Elevator_R",
                   "Fin", "Rudder", "MainGear_L", "MainGear_R", "Radiator"]),
    "parts": (2048, ["Propeller", "Exhausts", "WindscreenFrame", "Mast", "Struts", "Wires", "TailSkid", "CockpitPadding",
                     "CockpitStructure", "Seat", "Stick", "RudderPedals", "Levers"]),
}


def paint_cross(path):
    """Balkenkreuz: black cross, white edging along the arms, thin black outline."""
    from PIL import Image, ImageDraw
    n = 1024
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c, a, wb, ln, L = n / 2, 0.14 * n, 0.032 * n, 0.010 * n, n / 2 - 4
    for half, col in ((a + wb + ln, (14, 14, 14, 255)), (a + wb, (228, 226, 218, 255)), (a, (14, 14, 14, 255))):
        d.rectangle((c - half, c - L, c + half, c + L), fill=col)
        d.rectangle((c - L, c - half, c + L, c + half), fill=col)
    im.save(path)


def paint_panel(path):
    from PIL import Image, ImageDraw, ImageFont
    W, H_ = 1152, 1024
    rng = np.random.default_rng(51)
    base = np.zeros((H_, W, 3), np.float32) + np.array([150, 160, 156], np.float32)        # grey upper panel
    px = lambda y, z: (C.panel_uv(y, z)[0] * W, (1 - C.panel_uv(y, z)[1]) * H_)
    lw, lz0, lz1 = C.LOWER
    x0, y1 = px(-lw, lz0)
    x1, y0 = px(lw, lz1)
    base[int(y0):int(y1), int(x0):int(x1)] = (132, 142, 138)                                # lower panel, set forward in the shadow
    base[int(y0):int(y0) + 40, int(x0):int(x1)] *= np.linspace(0.55, 1.0, 40, dtype=np.float32)[:, None, None]
    base += (rng.random((H_, W, 1)) * 12 - 6)
    im = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    font = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", s)
    k = W / (C.PANEL_Y[1] - C.PANEL_Y[0])
    white = (225, 224, 214)

    def text(xy, s, size, fill=white):
        f = font(size)
        d.text((xy[0] - d.textlength(s, font=f) / 2, xy[1] - size / 2), s, font=f, fill=fill)

    def dial(cx, cy, r, a0, a1, labels, minor, title, needle, sub=""):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(8, 8, 8))
        n = (len(labels) - 1) * minor
        for i in range(n + 1):
            a = math.radians(a0 + (a1 - a0) * i / n - 90)
            big = i % minor == 0
            r0 = r * (0.80 if big else 0.88)
            d.line((cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + r * 0.96 * math.cos(a), cy + r * 0.96 * math.sin(a)), fill=white, width=3 if big else 1)
            if big and labels[i // minor]:
                text((cx + r * 0.63 * math.cos(a), cy + r * 0.63 * math.sin(a)), labels[i // minor], max(9, int(r * 0.2)))
        if title:
            text((cx, cy + r * 0.34), title, max(8, int(r * 0.14)))
        if sub:
            text((cx, cy - r * 0.32), sub, max(8, int(r * 0.13)))
        a = math.radians(a0 + (a1 - a0) * needle - 90)
        d.line((cx - r * 0.15 * math.cos(a), cy - r * 0.15 * math.sin(a), cx + r * 0.78 * math.cos(a), cy + r * 0.78 * math.sin(a)), fill=white, width=max(3, int(r * 0.05)))
        d.ellipse((cx - r * 0.07, cy - r * 0.07, cx + r * 0.07, cy + r * 0.07), fill=(70, 70, 70))

    for name, y, z, r, face in C.PANEL:
        cx, cy = px(y, z)
        R = r * k
        if face == "asi":
            dial(cx, cy, R, 215, 530, ["100", "150", "200", "250", "300", "350", "400", "450"], 5, "km/h", 0.0, "Fahrt")
        elif face == "alt":
            dial(cx, cy, R, 180, 495, [str(i) for i in range(8)], 5, "km", 0.0, "Höhe")
        elif face == "tach":
            dial(cx, cy, R, -140, 140, ["6", "8", "10", "12", "14", "16", "18", "20", "22", "24"], 2, "U/min x100", 0.05)
        elif face == "clock":
            dial(cx, cy, R, 0, 330, ["12", "", "", "3", "", "", "6", "", "", "9", "", ""], 1, "", 0.82)
        elif face in ("temp", "press", "fuel"):
            lab = {"temp": ["0", "50", "100"], "press": ["0", "2", "4"], "fuel": ["0", "1/2", "1"]}[face]
            dial(cx, cy, R, -120, 120, lab, 4, {"temp": "°C", "press": "kg/cm²", "fuel": "Kraftstoff"}[face], 0.45)
        elif face == "turn":
            d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(8, 8, 8))
            text((cx, cy - R * 0.55), "DREHT", int(R * 0.2))
            text((cx, cy + R * 0.62), "HÄNGT", int(R * 0.2))
            d.line((cx, cy - R * 0.35, cx, cy + R * 0.15), fill=white, width=int(R * 0.1))
            d.arc((cx - R * 0.6, cy - R * 0.25, cx + R * 0.6, cy + R * 0.55), 20, 160, fill=white, width=int(R * 0.14))
            d.ellipse((cx - R * 0.08, cy + R * 0.40, cx + R * 0.08, cy + R * 0.56), fill=(8, 8, 8))
        elif face == "compass":
            d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(14, 14, 14))
            d.rounded_rectangle((cx - R * 0.78, cy - R * 0.36, cx + R * 0.78, cy + R * 0.30), int(R * 0.12), fill=(36, 34, 26), outline=(120, 118, 110), width=3)
            for i, lab in enumerate(("33", "N", "3")):
                text((cx - R * 0.5 + i * R * 0.5, cy - R * 0.05), lab, int(R * 0.3))
        elif face == "magneto":
            d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(20, 20, 20), outline=(90, 90, 90), width=3)
            text((cx, cy + R * 0.55), "BOSCH", int(R * 0.22))
            for i, lab in enumerate(("0", "M1", "M2", "M1+2")):
                a = math.radians(-150 + 40 * i)
                text((cx + R * 0.68 * math.cos(a), cy + R * 0.68 * math.sin(a)), lab, int(R * 0.17))
            d.line((cx, cy, cx - R * 0.45, cy - R * 0.35), fill=(200, 200, 195), width=int(R * 0.16))
        for a in (45, 135, 225, 315):
            sx, sy = cx + (R + 8) * math.cos(math.radians(a)), cy + (R + 8) * math.sin(math.radians(a))
            d.ellipse((sx - 3, sy - 3, sx + 3, sy + 3), fill=(60, 60, 60), outline=(110, 110, 105))
    cx, cy = px(-0.105, 0.225)                                                              # red switch box
    d.rounded_rectangle((cx - 26, cy - 34, cx + 26, cy + 34), 4, fill=(22, 22, 22))
    d.rectangle((cx - 16, cy - 16, cx + 16, cy + 14), fill=(190, 70, 80))
    cx, cy = px(0.105, 0.225)                                                               # orange push button
    d.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), fill=(18, 18, 18))
    d.ellipse((cx - 13, cy - 13, cx + 13, cy + 13), fill=(215, 110, 40))
    for yy, zz, lab in ((-0.215, 0.395, "Brandhahn"), (0.0, 0.395, "Kraftstoff"), (0.215, 0.395, "Kühlstoff")):
        cx, cy = px(yy, zz)
        d.rectangle((cx - 44, cy - 9, cx + 44, cy + 9), fill=(16, 16, 16), outline=(150, 150, 140))
        text((cx, cy), lab, 12)
    im.save(path)


def skin(mat, mode, tex):
    """mode: fuselage | upper | lower | tail | fin."""
    nt = NT(mat)
    out = nt.node("ShaderNodeOutputMaterial")
    bsdf = nt.node("ShaderNodeBsdfPrincipled")
    nt.t.links.new(bsdf.outputs[0], out.inputs[0])
    geo = nt.node("ShaderNodeNewGeometry")
    sp = nt.node("ShaderNodeSeparateXYZ")
    nt.t.links.new(geo.outputs["Position"], sp.inputs[0])
    sn = nt.node("ShaderNodeSeparateXYZ")
    nt.t.links.new(geo.outputs["Normal"], sn.inputs[0])
    xd = nt.math("ADD", sp.outputs[1], H.X_REF)
    yd = nt.math("MULTIPLY", sp.outputs[0], -1.0)
    zd = sp.outputs[2]
    nz = sn.outputs[2]
    nyd = nt.math("MULTIPLY", sn.outputs[0], -1.0)             # faces starboard when positive
    fwd = nt.math("MULTIPLY", sn.outputs[1], -1.0)
    pos = geo.outputs["Position"]
    dist = lambda coord, spacing: nt.math("PINGPONG", coord, spacing / 2)
    absd = lambda coord, centre: nt.math("ABSOLUTE", nt.math("SUBTRACT", coord, centre))
    band = lambda coord, centre, half: nt.ss(absd(coord, centre), half, half - 0.004)

    big = nt.noise(pos, 1.1, 5.0, 0.6)
    fine = nt.noise(pos, 36.0, 4.0, 0.6)
    paint = nt.mix(nt.ss(big, 0.35, 0.75, 0.0, 0.35), GREY, tuple(c * 0.86 for c in GREY))
    metal_zone = None
    # ---- structure showing through: rib tapes / stringers on fabric, seams and fasteners on metal
    if mode == "fuselage":
        girth = nt.math("MULTIPLY", nt.math("ARCTAN2", zd, yd), 0.42)
        metal_zone = nt.ss(xd, 2.80, 2.72)                        # 1 on the metal nose, 0 on the fabric rear
        fabric = nt.math("SUBTRACT", 1.0, metal_zone)
        rd = dist(girth, 0.11)
        rib = nt.mul(nt.ss(rd, 0.014, 0.006), fabric)
        ridge = nt.mul(nt.ss(rd, 0.055, 0.0), fabric)
        seams = nt.math("MINIMUM", dist(nt.math("SUBTRACT", xd, 0.22), 0.62), dist(girth, 0.33))
        seam = nt.mul(nt.ss(seams, 0.0032, 0.0014), metal_zone)
        near_seam = nt.mul(nt.ss(seams, 0.035, 0.003), metal_zone)
        r2 = nt.math("ADD", nt.math("POWER", nt.math("SUBTRACT", seams, 0.014), 2.0), nt.math("POWER", dist(nt.math("ADD", xd, girth), 0.05), 2.0))
        rivet = nt.mul(nt.ss(nt.math("SQRT", r2), 0.0045, 0.0025), metal_zone)
    else:
        across = {"upper": yd, "lower": yd, "tail": yd, "fin": zd}[mode]
        spacing = {"upper": 0.29, "lower": 0.29, "tail": 0.24, "fin": 0.22}[mode]
        rd = dist(across, spacing)
        fabric = 1.0
        if mode in ("upper", "lower"):                            # plywood leading edge: no ribs show
            w = H.UPPER if mode == "upper" else H.LOWER
            fabric = nt.ss(xd, w["le"] + 0.13 * w["chord"], w["le"] + 0.19 * w["chord"])
        rib = nt.mul(nt.ss(rd, 0.018, 0.007), fabric)
        ridge = nt.mul(nt.ss(rd, spacing / 2, 0.0), fabric)
        seam = near_seam = rivet = None

    # ---- markings
    cross = bpy.data.images.load(os.path.join(tex, "balkenkreuz.png"), check_existing=True)

    def decal(u, v, mask):
        t = nt.node("ShaderNodeTexImage", image=cross, extension="CLIP")
        nt.t.links.new(nt.vec(u, v, 0.0), t.inputs["Vector"])
        return t.outputs["Color"], nt.math("MULTIPLY", t.outputs["Alpha"], mask)

    uv = lambda coord, centre, D: nt.math("ADD", nt.math("DIVIDE", nt.math("SUBTRACT", coord, centre), D), 0.5)
    if mode == "fuselage":
        x0, z0, D = CROSS["fuselage"]
        col, a = decal(uv(xd, x0, D), uv(zd, z0, D), nt.ss(nt.math("ABSOLUTE", nz), 0.9, 0.75))
        paint = nt.mix(a, paint, col)
        b1, b2, hw = BANDS
        paint = nt.mix(nt.mx(band(xd, b1, hw), band(xd, b2, hw)), paint, BLACK)
    elif mode in ("upper", "lower"):
        x0, y0, D = CROSS[mode]
        face = 1.0 if mode == "upper" else -1.0
        for sgn in (-1.0, 1.0):
            col, a = decal(uv(yd, sgn * y0, D), uv(xd, x0, D), nt.ss(nt.math("MULTIPLY", nz, face), 0.2, 0.5))
            paint = nt.mix(a, paint, col)
    elif mode == "fin":
        z0, z1 = TAIL_BAND
        inband = nt.mul(nt.ss(zd, z0 - 0.004, z0), nt.ss(zd, z1, z1 - 0.004))
        stbd = nt.ss(nyd, -0.05, 0.05)
        third = (z1 - z0) / 3
        stripes = nt.mix(nt.ss(zd, z0 + third - 0.003, z0 + third), RED, nt.mix(nt.ss(zd, z0 + 2 * third - 0.003, z0 + 2 * third), WHITE, BLACK))
        r2 = nt.math("ADD", nt.math("POWER", nt.math("SUBTRACT", xd, TAIL_DISC[0]), 2.0), nt.math("POWER", nt.math("SUBTRACT", zd, (z0 + z1) / 2), 2.0))
        port = nt.mix(nt.ss(nt.math("SQRT", r2), TAIL_DISC[1] + 0.002, TAIL_DISC[1] - 0.002), RED, WHITE)
        paint = nt.mix(inband, paint, nt.mix(stbd, port, stripes))

    # ---- weathering
    streak_v = nt.vec(nt.math("MULTIPLY", xd, 2.2), nt.math("MULTIPLY", yd, 11.0), nt.math("MULTIPLY", zd, 11.0))
    streak = nt.noise(streak_v, 1.0, 4.0, 0.6)
    grime = nt.ss(streak, 0.55, 0.85, 0.0, 0.10)
    tape_edge = nt.math("SUBTRACT", nt.mul(nt.ss(rd, 0.032, 0.016), fabric), rib)       # dirt beside the rib tapes
    grime = nt.math("ADD", grime, nt.math("MULTIPLY", tape_edge, 0.13))
    if near_seam is not None:
        grime = nt.math("ADD", grime, nt.math("MULTIPLY", near_seam, 0.30))
    if mode == "fuselage":
        zone = nt.mul(nt.ss(xd, 0.85, 1.05), nt.ss(xd, 5.2, 2.0), nt.ss(zd, -0.30, -0.05), nt.ss(zd, 0.62, 0.40))
        soot = nt.mul(zone, nt.ss(streak, 0.3, 0.8, 0.14, 0.52))
        belly = nt.mul(nt.ss(nz, -0.5, -0.85), nt.ss(xd, 1.6, 2.2), nt.ss(streak, 0.4, 0.75), 0.8)
        grime = nt.math("ADD", grime, nt.mx(soot, belly))
    grime = nt.math("MINIMUM", nt.math("MULTIPLY", grime, nt.ss(fine, 0.2, 0.8, 0.6, 1.0)), 1.0)
    color = nt.mix(grime, paint, SOOT)
    color = nt.mix(nt.math("MULTIPLY", rib, 0.6), color, nt.mix(1.0, color, (0.045, 0.045, 0.045), blend="ADD"))   # tapes catch the light
    color = nt.mix(nt.math("MULTIPLY", nt.math("SUBTRACT", fabric, ridge) if fabric != 1.0 else nt.math("SUBTRACT", 1.0, ridge), 0.07),
                   color, (0.05, 0.055, 0.05))                                         # fabric sags between the ribs
    height = nt.math("ADD", nt.math("MULTIPLY", ridge, 3.0), nt.math("MULTIPLY", rib, 0.5))
    chip = None
    if seam is not None:
        color = nt.mix(nt.math("MULTIPLY", seam, 0.85), color, (0.01, 0.01, 0.01))
        chipn = nt.noise(pos, 70.0, 7.0, 0.68)
        thr = nt.math("SUBTRACT", 0.77, nt.math("ADD", nt.math("MULTIPLY", near_seam, 0.06), nt.math("MULTIPLY", nt.ss(fwd, 0.8, 0.99), 0.10)))
        chip = nt.mul(nt.ss(chipn, thr, nt.math("ADD", thr, 0.015)), metal_zone)
        chip = nt.mx(chip, nt.mul(rivet, nt.ss(big, 0.5, 0.65)))
        color = nt.mix(chip, color, ALUMINIUM)
        height = nt.math("ADD", height, nt.math("ADD", nt.math("MULTIPLY", rivet, 0.7), nt.math("MULTIPLY", seam, -0.8)))
        nt.set(bsdf.inputs["Metallic"], nt.math("MULTIPLY", chip, 0.95))
    nt.set(bsdf.inputs["Base Color"], color)
    rough = nt.math("ADD", nt.ss(fine, 0.2, 0.8, 0.40, 0.52), nt.math("MULTIPLY", grime, 0.25))
    if chip is not None:
        rough = nt.math("SUBTRACT", rough, nt.math("MULTIPLY", chip, 0.15))
    nt.set(bsdf.inputs["Roughness"], rough)
    bump = nt.node("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 1.0
    bump.inputs["Distance"].default_value = 0.0015
    nt.t.links.new(height, bump.inputs["Height"])
    nt.t.links.new(bump.outputs[0], bsdf.inputs["Normal"])
    return mat


def procedural(h, tex):
    paint_cross(os.path.join(tex, "balkenkreuz.png"))
    paint_panel(os.path.join(tex, "he51_panel.png"))
    skins = {m: skin(bpy.data.materials.new("He51_Skin_" + m), m, tex) for m in ("fuselage", "upper", "lower", "tail", "fin")}
    base = H.material("Skin")
    for o in h.objects.values():
        if o.type != "MESH":
            continue
        part = o.name[len(h.prefix):]
        mode = ("upper" if part.startswith(("UpperWing", "Aileron")) else "lower" if part.startswith("LowerWing") else
                "tail" if part.startswith(("Tailplane", "Elevator")) else "fin" if part.startswith(("Fin", "Rudder")) else "fuselage")
        for s in o.material_slots:
            if s.material == base:
                s.material = skins[mode]
    worn(H.material("Wood"), (0.072, 0.023, 0.013), 0.0, 0.28, grime=0.15, scale=18.0, dark=(0.03, 0.012, 0.008))
    worn(H.material("Steel"), (0.32, 0.32, 0.33), 1.0, 0.42, grime=0.2)
    worn(H.material("Strut"), (0.09, 0.10, 0.115), 0.2, 0.42, grime=0.15, dark=(0.25, 0.25, 0.24))
    worn(H.material("Black"), (0.015, 0.015, 0.015), 0.0, 0.5, grime=0.15, dark=(0.10, 0.10, 0.10))
    worn(H.material("Exhaust"), (0.065, 0.045, 0.035), 0.6, 0.75, grime=0.6, bump=0.002, scale=140.0)
    worn(H.material("Tyre"), (0.02, 0.02, 0.02), 0.0, 0.85, grime=0.5, dark=(0.10, 0.09, 0.07), bump=0.001)
    worn(H.material("LeatherBrown"), (0.10, 0.04, 0.02), 0.0, 0.5, grime=0.3, bump=0.0015, scale=160.0)
    worn(H.material("LeatherTan"), (0.30, 0.22, 0.13), 0.0, 0.6, grime=0.3, bump=0.0012, scale=200.0)
    worn(H.material("Interior"), (0.20, 0.22, 0.19), 0.0, 0.5, grime=0.3, scale=90.0)
    worn(H.material("Belt"), (0.40, 0.36, 0.25), 0.0, 0.85, grime=0.3, bump=0.0008, scale=300.0)
    worn(H.material("KnobYellow"), (0.75, 0.55, 0.04), 0.0, 0.35, grime=0.15)
    panel = H.material("Panel")
    nt = NT(panel)
    out = nt.node("ShaderNodeOutputMaterial")
    bsdf = nt.node("ShaderNodeBsdfPrincipled")
    nt.t.links.new(bsdf.outputs[0], out.inputs[0])
    t = nt.node("ShaderNodeTexImage", image=bpy.data.images.load(os.path.join(tex, "he51_panel.png"), check_existing=True))
    nt.t.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.45


def texture(h, tex, bake=False, samples=8):
    os.makedirs(tex, exist_ok=True)
    procedural(h, tex)
    groups = {g: (size, [h.objects[h.prefix + n] for n in names]) for g, (size, names) in GROUPS.items()}
    for g, (size, objs) in groups.items():
        unwrap(objs)
    stems = {g: os.path.join(tex, "he51_%s_" % g) for g in groups}
    if bake:
        for g, (size, objs) in groups.items():
            if bake is True or g in bake:
                bake_group(g, objs, size, tex, samples, prefix="he51")
    if all(os.path.exists(stems[g] + "basecolor.jpg") for g in groups) and (bake or os.environ.get("HE51_PROCEDURAL") != "1"):
        for g, (size, objs) in groups.items():
            m = image_material("He51_" + g.capitalize(), stems[g])
            for o in objs:
                for s in o.material_slots:
                    s.material = m
        for m in list(bpy.data.materials):
            if m.users == 0 and m.name.startswith("He51_"):
                bpy.data.materials.remove(m)
