"""PBR materials and textures for the P-26A.

texture(h, tex, bake, samples):
  1. paints the instrument panel and the national insignia (Pillow);
  2. builds the procedural paint: dark olive drab 41 over neutral gray 43
     with the star-in-circle insignia of 1941, round-head rivet rows, panel
     seams, sun fading, chipped leading edges and walkways, exhaust soot
     and oil streaks;
  3. with bake=True, unwraps the model into two atlases and bakes the
     procedural materials to base colour / ORM / normal maps, then swaps in
     plain image materials (what a game engine needs).

The paint is laid out in world coordinates, with the model at rest.
"""
import math
import os

import bpy
import numpy as np

import p26a as P
import p26a_cockpit as C

# colours, linear RGB
OLIVE = (0.058, 0.061, 0.029)          # dark olive drab 41
OLIVE_FADED = (0.105, 0.100, 0.056)
GRAY = (0.185, 0.195, 0.20)            # neutral gray 43
ALUMINIUM = (0.60, 0.60, 0.61)
SOOT = (0.012, 0.011, 0.010)
INSIGNIA = dict(fuselage=(4.30, 0.02, 0.78), wing=(2.26, 3.12, 1.22))     # centre (x, z | x, |y|), diameter

GROUPS = {
    "ext": (4096, ["Fuselage", "Headrest", "Wing", "Aileron_L", "Aileron_R", "Flap_L", "Flap_R", "Tailplane",
                   "Elevator_L", "Elevator_R", "Fin", "Rudder", "TownendRing", "MainGear_L", "MainGear_R", "Tailwheel"]),
    "parts": (2048, ["Engine", "Propeller", "Wires", "Masts", "WindscreenFrame", "BlastTubes", "CockpitStructure",
                     "Seat", "Stick", "RudderPedals", "Throttle", "CockpitRim", "Guns"]),
}
WING_PARTS = ("Wing", "Aileron", "Flap", "Tailplane", "Elevator")
FIN_PARTS = ("Fin", "Rudder")
BAKE_TILE = 4096


# ----------------------------------------------------------------------------
# painted images
# ----------------------------------------------------------------------------
def paint_insignia(path):
    """Type 1 national insignia (1921-42): white star on a blue disc, red centre."""
    from PIL import Image, ImageDraw
    n = 1024
    im = Image.new("RGBA", (n * 2, n * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c, R = n, n - 8
    d.ellipse((c - R, c - R, c + R, c + R), fill=(22, 38, 78, 255))
    r_in = R * math.sin(math.radians(18)) / math.sin(math.radians(126))
    pts = []
    for k in range(10):
        a = math.radians(-90 + 36 * k)
        r = R if k % 2 == 0 else r_in
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    d.polygon(pts, fill=(232, 230, 222, 255))
    rr = r_in * math.cos(math.radians(36))                       # tangent to the inner pentagon
    d.ellipse((c - rr, c - rr, c + rr, c + rr), fill=(168, 30, 28, 255))
    im.resize((n, n), Image.LANCZOS).save(path)


def paint_panel(path):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1280, 1024
    im = Image.new("RGB", (W, H), (17, 17, 18))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(26)
    # black crackle finish
    noise = (rng.random((H, W)) * 14).astype(np.uint8)
    im = Image.fromarray(np.clip(np.asarray(im).astype(int) + noise[..., None] - 5, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    try:
        font = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", s)
        font(10)
    except OSError:
        font = lambda s: ImageFont.load_default()
    px = lambda y, z: (C.panel_uv(y, z)[0] * W, (1 - C.panel_uv(y, z)[1]) * H)
    k = W / (C.PANEL_Y[1] - C.PANEL_Y[0])                         # px per metre
    white = (225, 224, 214)

    def text(xy, s, size, fill=white):
        f = font(size)
        w = d.textlength(s, font=f)
        d.text((xy[0] - w / 2, xy[1] - size / 2), s, font=f, fill=fill)

    def dial(cx, cy, r, a0, a1, labels, minor, title, needle, sub=""):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(8, 8, 8))
        n = (len(labels) - 1) * minor
        for i in range(n + 1):
            a = math.radians(a0 + (a1 - a0) * i / n - 90)
            big = i % minor == 0
            r0 = r * (0.80 if big else 0.88)
            d.line((cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + r * 0.96 * math.cos(a), cy + r * 0.96 * math.sin(a)),
                   fill=white, width=3 if big else 1)
            if big:
                text((cx + r * 0.64 * math.cos(a), cy + r * 0.64 * math.sin(a)), labels[i // minor], max(9, int(r * 0.2)))
        text((cx, cy + r * 0.34), title, max(8, int(r * 0.13)))
        if sub:
            text((cx, cy - r * 0.32), sub, max(8, int(r * 0.12)))
        a = math.radians(a0 + (a1 - a0) * needle - 90)
        d.line((cx - r * 0.15 * math.cos(a), cy - r * 0.15 * math.sin(a), cx + r * 0.78 * math.cos(a), cy + r * 0.78 * math.sin(a)),
               fill=white, width=max(3, int(r * 0.05)))
        d.ellipse((cx - r * 0.07, cy - r * 0.07, cx + r * 0.07, cy + r * 0.07), fill=(70, 70, 70))

    for name, y, z, r, face in C.PANEL:
        cx, cy = px(y, z)
        R = r * k
        if face == "asi":
            dial(cx, cy, R, 20, 340, ["40", "60", "80", "100", "120", "140", "160", "180", "200", "250"], 2, "AIRSPEED", 0.0, "M.P.H.")
        elif face == "tach":
            dial(cx, cy, R, 0, 330, ["0", "5", "10", "15", "20", "25"], 5, "R.P.M.", 0.02, "HUNDREDS")
        elif face == "alt":
            dial(cx, cy, R, 0, 324, [str(i) for i in range(10)], 5, "ALTITUDE", 0.0, "1000 FT")
        elif face == "clock":
            dial(cx, cy, R, 0, 330, ["12", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"], 1, "", 0.82)
        elif face == "map":
            dial(cx, cy, R, -140, 140, ["10", "20", "30", "40", "50"], 5, "MANIFOLD", 0.48, "PRESS.")
        elif face in ("amp", "fuel", "oil"):
            lab = {"amp": ["-", "0", "+"], "fuel": ["0", "1/2", "F"], "oil": ["0", "50", "100"]}[face]
            dial(cx, cy, R, -60, 60, lab, 4, {"amp": "AMP", "fuel": "FUEL", "oil": "OIL C"}[face], 0.55 if face != "fuel" else 0.8)
        elif face == "engine":                                   # three-in-one engine gauge unit
            d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(8, 8, 8))
            for lab, a0 in (("OIL TEMP", -90), ("OIL LBS", 150), ("FUEL LBS", 30)):
                for i in range(7):
                    a = math.radians(a0 - 40 + 80 * i / 6)
                    d.line((cx + R * 0.82 * math.cos(a), cy + R * 0.82 * math.sin(a), cx + R * 0.95 * math.cos(a), cy + R * 0.95 * math.sin(a)),
                           fill=white, width=2)
                a = math.radians(a0)
                text((cx + R * 0.5 * math.cos(a), cy + R * 0.5 * math.sin(a)), lab, max(8, int(R * 0.11)))
                a = math.radians(a0 + 12)
                d.line((cx + R * 0.2 * math.cos(a), cy + R * 0.2 * math.sin(a), cx + R * 0.8 * math.cos(a), cy + R * 0.8 * math.sin(a)), fill=white, width=3)
        elif face == "compass":                                  # window-type magnetic compass
            d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(14, 14, 14))
            d.rounded_rectangle((cx - R * 0.78, cy - R * 0.42, cx + R * 0.78, cy + R * 0.30), int(R * 0.12), fill=(36, 34, 26), outline=(120, 118, 110), width=3)
            for i, lab in enumerate(("33", "N", "3")):
                text((cx - R * 0.5 + i * R * 0.5, cy - R * 0.12), lab, int(R * 0.30))
            for i in range(9):
                x = cx - R * 0.7 + i * R * 0.175
                d.line((x, cy + R * 0.12, x, cy + R * 0.26), fill=white, width=2)
            d.line((cx, cy - R * 0.42, cx, cy + R * 0.30), fill=(230, 200, 120), width=2)
        elif face == "selector":                                 # fuel selector: red plate, white pointer
            d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(150, 26, 22), outline=white, width=3)
            d.polygon([(cx - R * 0.16, cy + R * 0.3), (cx + R * 0.16, cy + R * 0.3), (cx, cy - R * 0.8)], fill=white)
            d.ellipse((cx - R * 0.28, cy - R * 0.28, cx + R * 0.28, cy + R * 0.28), fill=(20, 20, 20))
            text((cx, cy + R * 1.45), "FUEL", 12)
        elif face == "turn":
            d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(8, 8, 8))
            d.line((cx, cy - R * 0.75, cx, cy - R * 0.2), fill=white, width=int(R * 0.09))
            d.arc((cx - R * 0.6, cy - R * 0.1, cx + R * 0.6, cy + R * 0.9), 200, 340, fill=white, width=int(R * 0.16))
            d.ellipse((cx - R * 0.09, cy + R * 0.02, cx + R * 0.09, cy + R * 0.2), fill=(8, 8, 8))
            text((cx, cy + R * 0.55), "TURN & BANK", max(8, int(R * 0.12)))
        # mounting screws
        for a in (45, 135, 225, 315):
            sx, sy = cx + (R + 9) * math.cos(math.radians(a)), cy + (R + 9) * math.sin(math.radians(a))
            d.ellipse((sx - 4, sy - 4, sx + 4, sy + 4), fill=(60, 60, 60), outline=(110, 110, 105))
    # switches and placards at lower left; data plate at lower right
    cx, cy = px(-0.300, 0.272)                                   # ignition switch under the small gauge
    d.rounded_rectangle((cx - 22, cy - 13, cx + 22, cy + 13), 4, fill=(120, 24, 20), outline=white, width=2)
    d.line((cx, cy, cx + 12, cy - 9), fill=white, width=4)
    for dy, lab in ((-0.060, "PRIMER"), (0.005, "OFF  L  R  BOTH")):
        cx, cy = px(dy, 0.158 if lab == "PRIMER" else -0.035)
        text((cx, cy), lab, 10)
    # wear: scratches round the lower edge
    for _ in range(220):
        x, y = rng.integers(0, W), rng.integers(int(H * 0.2), H)
        L = rng.integers(3, 16)
        a = rng.random() * math.pi
        d.line((x, y, x + L * math.cos(a), y + L * math.sin(a)), fill=(70, 70, 68), width=1)
    im.save(path)


# ----------------------------------------------------------------------------
# node helper
# ----------------------------------------------------------------------------
class NT:
    def __init__(self, mat):
        mat.use_nodes = True
        self.t = mat.node_tree
        self.t.nodes.clear()

    def node(self, kind, **props):
        n = self.t.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def set(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.t.links.new(v, sock)
        elif isinstance(v, (int, float)):
            sock.default_value = v if sock.type == "VALUE" else (v, v, v, 1.0) if sock.type == "RGBA" else (v, v, v)
        else:
            sock.default_value = (*v, 1.0) if (sock.type == "RGBA" and len(v) == 3) else v

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.set(n.inputs[0], a)
        if b is not None:
            self.set(n.inputs[1], b)
        if c is not None:
            self.set(n.inputs[2], c)
        return n.outputs[0]

    def ss(self, v, lo, hi, out0=0.0, out1=1.0):
        """smoothstep(v; lo..hi) mapped to out0..out1."""
        n = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        for i, x in enumerate((v, lo, hi, out0, out1)):
            self.set(n.inputs[i], x)
        return n.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        n = self.node("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        self.set(n.inputs[0], fac)
        self.set(n.inputs[6], a)
        self.set(n.inputs[7], b)
        return n.outputs[2]

    def vec(self, x, y, z):
        n = self.node("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            self.set(n.inputs[i], v)
        return n.outputs[0]

    def noise(self, vector, scale, detail=4.0, rough=0.55):
        n = self.node("ShaderNodeTexNoise")
        self.t.links.new(vector, n.inputs["Vector"])
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        return n.outputs[0]

    def mul(self, *xs):
        out = xs[0]
        for x in xs[1:]:
            out = self.math("MULTIPLY", out, x)
        return out

    def mx(self, a, b):
        return self.math("MAXIMUM", a, b)


def skin_shader(mat, mode, tex):
    """mode: 'fuselage' (frames round the body), 'wing' (ribs across the
    span) or 'fin' (ribs up the fin)."""
    nt = NT(mat)
    out = nt.node("ShaderNodeOutputMaterial")
    bsdf = nt.node("ShaderNodeBsdfPrincipled")
    nt.t.links.new(bsdf.outputs[0], out.inputs[0])
    geo = nt.node("ShaderNodeNewGeometry")
    sp = nt.node("ShaderNodeSeparateXYZ")
    nt.t.links.new(geo.outputs["Position"], sp.inputs[0])
    sn = nt.node("ShaderNodeSeparateXYZ")
    nt.t.links.new(geo.outputs["Normal"], sn.inputs[0])
    xd = nt.math("ADD", sp.outputs[1], P.X_REF)                 # design x, aft
    yd = nt.math("MULTIPLY", sp.outputs[0], -1.0)               # design y, starboard
    zd = sp.outputs[2]
    nz = sn.outputs[2]
    fwd = nt.math("MULTIPLY", sn.outputs[1], -1.0)              # how far the surface faces forward
    pos = geo.outputs["Position"]
    dist = lambda coord, spacing: nt.math("PINGPONG", coord, spacing / 2)      # distance to the nearest multiple

    # ---- rivet rows and seams: (distance across the row, coordinate along it)
    if mode == "fuselage":
        ang = nt.math("ARCTAN2", zd, yd)
        girth = nt.math("MULTIPLY", ang, 0.50)                   # arc length round a 0.5 m radius
        rows = [(dist(xd, 0.305), girth), (dist(girth, 0.131), xd)]             # frames; stringers every 15 deg
        seams = nt.math("MINIMUM", dist(xd, 0.915), dist(girth, 0.5236))
    elif mode == "wing":
        rows = [(dist(yd, 0.26), xd), (dist(nt.math("SUBTRACT", xd, 0.30), 0.44), yd)]    # ribs; spar lines
        seams = nt.math("MINIMUM", dist(yd, 0.78), dist(nt.math("SUBTRACT", xd, 0.30), 0.88))
    else:
        rows = [(dist(zd, 0.20), xd), (dist(nt.math("SUBTRACT", xd, 0.10), 0.30), zd)]
        seams = nt.math("MINIMUM", dist(zd, 0.60), dist(nt.math("SUBTRACT", xd, 0.10), 0.60))
    rivet = None
    near_row = None
    for across, along in rows:
        r2 = nt.math("ADD", nt.math("POWER", across, 2.0), nt.math("POWER", dist(along, 0.036), 2.0))
        head = nt.ss(nt.math("SQRT", r2), 0.0025, 0.0048, 1.0, 0.0)
        rivet = head if rivet is None else nt.mx(rivet, head)
        nr = nt.ss(across, 0.004, 0.03, 1.0, 0.0)
        near_row = nr if near_row is None else nt.mx(near_row, nr)
    seam = nt.ss(seams, 0.0012, 0.0030, 1.0, 0.0)
    near_seam = nt.ss(seams, 0.003, 0.035, 1.0, 0.0)

    # ---- paint: olive drab above, neutral gray below, faded by the sun on top
    big = nt.noise(pos, 1.3, 5.0, 0.6)
    fine = nt.noise(pos, 38.0, 4.0, 0.6)
    under = nt.ss(nz, -0.42, -0.24, 1.0, 0.0)
    fade = nt.mul(nt.ss(big, 0.40, 0.80), nt.ss(nz, -0.2, 0.8, 0.25, 1.0))
    olive = nt.mix(fade, OLIVE, OLIVE_FADED)
    paint = nt.mix(under, olive, GRAY)
    paint = nt.mix(nt.ss(fine, 0.3, 0.7, 0.0, 0.16), paint, nt.mix(0.5, paint, (0.0, 0.0, 0.0)))

    # ---- national insignia
    img = bpy.data.images.load(os.path.join(tex, "insignia.png"), check_existing=True)

    def decal(u, v, mask):
        t = nt.node("ShaderNodeTexImage", image=img, extension="CLIP")
        nt.t.links.new(nt.vec(u, v, 0.0), t.inputs["Vector"])
        return t.outputs["Color"], nt.math("MULTIPLY", t.outputs["Alpha"], mask)

    if mode == "fuselage":
        x0, z0, D = INSIGNIA["fuselage"]
        side = nt.math("SIGN", yd)
        uu = nt.math("ADD", nt.math("DIVIDE", nt.math("MULTIPLY", nt.math("SUBTRACT", xd, x0), side), -D), 0.5)
        vv = nt.math("ADD", nt.math("DIVIDE", nt.math("SUBTRACT", zd, z0), D), 0.5)
        col, a = decal(uu, vv, nt.ss(nt.math("ABSOLUTE", nz), 0.75, 0.9, 1.0, 0.0))
        paint = nt.mix(a, paint, col)
    elif mode == "wing":
        x0, y0, D = INSIGNIA["wing"]
        for sgn, face in ((-1.0, 1.0), (1.0, -1.0)):              # upper left, lower right
            uu = nt.math("ADD", nt.math("DIVIDE", nt.math("SUBTRACT", yd, sgn * y0), D * face), 0.5)
            vv = nt.math("ADD", nt.math("DIVIDE", nt.math("SUBTRACT", xd, x0), -D), 0.5)
            col, a = decal(uu, vv, nt.ss(nt.math("MULTIPLY", nz, face), 0.2, 0.5))
            paint = nt.mix(a, paint, col)

    # ---- grime in seams and round rivet rows, rain streaks down the chord
    streak_v = nt.vec(nt.math("MULTIPLY", xd, 1.6), nt.math("MULTIPLY", yd, 26.0), nt.math("MULTIPLY", zd, 26.0))
    streak = nt.noise(streak_v, 1.0, 4.0, 0.6)
    grime = nt.mx(nt.math("MULTIPLY", near_seam, 0.36), nt.math("MULTIPLY", near_row, 0.18))
    grime = nt.math("ADD", grime, nt.ss(streak, 0.55, 0.85, 0.0, 0.12))
    grime = nt.math("MULTIPLY", grime, nt.ss(fine, 0.2, 0.8, 0.5, 1.0))
    soot = None
    if mode == "fuselage":
        # exhaust soot behind the stubs, oil along the belly, dust thrown up behind the wheels
        zone = nt.mul(nt.ss(xd, 0.95, 1.15), nt.ss(xd, 1.4, 3.2, 1.0, 0.0))
        soot = nt.mul(zone, nt.ss(streak, 0.3, 0.75, 0.2, 0.75))
        belly = nt.mul(nt.ss(nz, -0.5, -0.85), nt.ss(xd, 0.9, 1.3), nt.ss(streak, 0.4, 0.75))
        soot = nt.mx(soot, nt.math("MULTIPLY", belly, 0.8))
    dirt = nt.math("MINIMUM", nt.math("ADD", grime, soot) if soot is not None else grime, 1.0)
    color = nt.mix(dirt, paint, SOOT)
    color = nt.mix(nt.math("MULTIPLY", seam, 0.85), color, (0.01, 0.01, 0.01))

    # ---- chipped paint: leading edges, the port wing-root walkway, the cockpit rim, rivet heads
    chipn = nt.noise(pos, 70.0, 7.0, 0.68)
    thr = nt.math("SUBTRACT", 0.75, nt.math("MULTIPLY", nt.ss(fwd, 0.78, 0.99), 0.15))
    thr = nt.math("SUBTRACT", thr, nt.math("MULTIPLY", near_seam, 0.035))
    if mode == "wing":
        # walkway: a strip on the port wing beside the fuselage only (y from -0.9 to -0.56)
        walk = nt.mul(nt.ss(yd, -1.0, -0.9), nt.ss(yd, -0.56, -0.50, 1.0, 0.0), nt.ss(xd, 1.9, 2.1), nt.ss(xd, 3.15, 3.0), nt.ss(nz, 0.4, 0.7))
        thr = nt.math("SUBTRACT", thr, nt.math("MULTIPLY", walk, 0.10))
    else:
        rim = nt.mul(nt.ss(zd, 0.5, 0.62), nt.ss(xd, 2.05, 2.15), nt.ss(xd, 2.85, 2.75), nt.ss(nt.math("ABSOLUTE", yd), 0.45, 0.35))
        thr = nt.math("SUBTRACT", thr, nt.math("MULTIPLY", rim, 0.12))
    chip = nt.ss(chipn, thr, nt.math("ADD", thr, 0.015))
    chip = nt.mx(chip, nt.mul(rivet, nt.ss(big, 0.45, 0.6), nt.ss(fine, 0.45, 0.6)))
    worn_metal = nt.mix(nt.ss(fine, 0.3, 0.7, 0.0, 0.35), ALUMINIUM, (0.30, 0.30, 0.31))
    color = nt.mix(chip, color, worn_metal)
    nt.set(bsdf.inputs["Base Color"], color)
    nt.set(bsdf.inputs["Metallic"], nt.math("MULTIPLY", chip, 0.95))
    rough = nt.ss(fine, 0.2, 0.8, 0.56, 0.72)
    rough = nt.math("ADD", rough, nt.math("MULTIPLY", dirt, 0.12))
    rough = nt.math("SUBTRACT", rough, nt.math("MULTIPLY", chip, 0.36))
    nt.set(bsdf.inputs["Roughness"], rough)
    height = nt.math("ADD", nt.math("MULTIPLY", rivet, 1.0), nt.math("MULTIPLY", seam, -0.8))
    height = nt.math("ADD", height, nt.math("MULTIPLY", chip, -0.25))
    bump = nt.node("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 1.0
    bump.inputs["Distance"].default_value = 0.0012
    nt.t.links.new(height, bump.inputs["Height"])
    nt.t.links.new(bump.outputs[0], bsdf.inputs["Normal"])
    return mat


def worn(mat, color, metal, rough, grime=0.25, bump=0.0, scale=45.0, dark=(0.02, 0.018, 0.015)):
    """Simple worn finish: colour and roughness varied by noise, dirt in the hollows."""
    nt = NT(mat)
    out = nt.node("ShaderNodeOutputMaterial")
    bsdf = nt.node("ShaderNodeBsdfPrincipled")
    nt.t.links.new(bsdf.outputs[0], out.inputs[0])
    geo = nt.node("ShaderNodeNewGeometry")
    n1 = nt.noise(geo.outputs["Position"], scale, 6.0, 0.65)
    n2 = nt.noise(geo.outputs["Position"], scale * 0.12, 4.0, 0.6)
    ao = nt.node("ShaderNodeAmbientOcclusion", samples=4)
    ao.inputs["Distance"].default_value = 0.05
    hollow = nt.ss(ao.outputs["AO"], 0.55, 0.95, 1.0, 0.0)
    d = nt.math("MINIMUM", nt.math("ADD", nt.math("MULTIPLY", hollow, 0.7), nt.ss(n2, 0.45, 0.75, 0.0, grime)), 1.0)
    col = nt.mix(nt.ss(n1, 0.3, 0.7, 0.0, 0.3), color, tuple(c * 0.55 for c in color))
    nt.set(bsdf.inputs["Base Color"], nt.mix(d, col, dark))
    nt.set(bsdf.inputs["Metallic"], nt.math("MULTIPLY", nt.math("SUBTRACT", 1.0, d), metal))
    nt.set(bsdf.inputs["Roughness"], nt.math("ADD", nt.ss(n1, 0.2, 0.8, rough - 0.08, rough + 0.10), nt.math("MULTIPLY", d, 0.2)))
    if bump:
        bn = nt.node("ShaderNodeBump")
        bn.inputs["Strength"].default_value = 1.0
        bn.inputs["Distance"].default_value = bump
        nt.t.links.new(n1, bn.inputs["Height"])
        nt.t.links.new(bn.outputs[0], bsdf.inputs["Normal"])
    return mat


def procedural(h, tex):
    """Put the procedural materials on the model."""
    paint_insignia(os.path.join(tex, "insignia.png"))
    paint_panel(os.path.join(tex, "p26a_panel.png"))
    skins = {m: skin_shader(bpy.data.materials.new("P26_Skin_" + m), m, tex) for m in ("fuselage", "wing", "fin")}
    base = P.material("Skin")
    for o in h.objects.values():
        if o.type != "MESH":
            continue
        part = o.name[len(h.prefix):]
        mode = "wing" if part.startswith(WING_PARTS) else "fin" if part.startswith(FIN_PARTS) else "fuselage"
        for s in o.material_slots:
            if s.material == base:
                s.material = skins[mode]
    worn(P.material("Metal"), (0.78, 0.78, 0.78), 1.0, 0.28, grime=0.08, scale=120.0)
    worn(P.material("PropBack"), (0.02, 0.02, 0.02), 0.0, 0.6, grime=0.1, dark=(0.12, 0.11, 0.1))
    worn(P.material("Steel"), (0.32, 0.32, 0.33), 1.0, 0.42, grime=0.2)
    worn(P.material("EngineGrey"), (0.20, 0.22, 0.24), 0.2, 0.45, grime=0.5)
    worn(P.material("Cylinder"), (0.06, 0.06, 0.06), 0.7, 0.5, grime=0.4, dark=(0.03, 0.02, 0.012))
    worn(P.material("Exhaust"), (0.20, 0.10, 0.055), 0.6, 0.78, grime=0.6, bump=0.002, scale=140.0)
    worn(P.material("Tyre"), (0.02, 0.02, 0.02), 0.0, 0.85, grime=0.5, dark=(0.10, 0.09, 0.07), bump=0.001)
    worn(P.material("Leather"), (0.085, 0.042, 0.022), 0.0, 0.5, grime=0.3, bump=0.0015, scale=160.0)
    worn(P.material("Interior"), (0.56, 0.57, 0.58), 0.9, 0.42, grime=0.3, scale=90.0)
    worn(P.material("Belt"), (0.40, 0.36, 0.25), 0.0, 0.85, grime=0.3, bump=0.0008, scale=300.0)
    worn(P.material("Black"), (0.015, 0.015, 0.015), 0.0, 0.5, grime=0.15, dark=(0.10, 0.10, 0.10))
    worn(P.material("GunMetal"), (0.035, 0.037, 0.042), 0.85, 0.40, grime=0.2, dark=(0.02, 0.018, 0.015))
    panel = P.material("Panel")
    nt = NT(panel)
    out = nt.node("ShaderNodeOutputMaterial")
    bsdf = nt.node("ShaderNodeBsdfPrincipled")
    nt.t.links.new(bsdf.outputs[0], out.inputs[0])
    t = nt.node("ShaderNodeTexImage", image=bpy.data.images.load(os.path.join(tex, "p26a_panel.png"), check_existing=True))
    nt.t.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.45


# ----------------------------------------------------------------------------
# bake
# ----------------------------------------------------------------------------
def _route(mat, channel):
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    out = next(n for n in nodes if n.type == "OUTPUT_MATERIAL")
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    em = nodes.get("BAKE_EMIT") or nodes.new("ShaderNodeEmission")
    em.name = "BAKE_EMIT"
    for l in list(out.inputs[0].links):
        links.remove(l)
    name = {"basecolor": "Base Color", "roughness": "Roughness", "metallic": "Metallic"}.get(channel)
    if name is None:
        links.new(bsdf.outputs[0], out.inputs[0])
        return
    for l in list(em.inputs[0].links):
        links.remove(l)
    inp = bsdf.inputs[name]
    if inp.links:
        links.new(inp.links[0].from_socket, em.inputs[0])
    else:
        v = inp.default_value
        em.inputs[0].default_value = tuple(v) if hasattr(v, "__len__") else (v, v, v, 1.0)
    links.new(em.outputs[0], out.inputs[0])


def _dilate(maps, cover, px):
    H, W = cover.shape
    src = np.full((H, W), -1, np.int32)
    src[cover] = np.flatnonzero(cover).astype(np.int32)
    steps = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    for _ in range(px):
        prev = src.copy()
        for dy, dx in steps:
            t = src[max(dy, 0):H + min(dy, 0), max(dx, 0):W + min(dx, 0)]
            s = prev[max(-dy, 0):H + min(-dy, 0), max(-dx, 0):W + min(-dx, 0)]
            take = (t < 0) & (s >= 0)
            t[take] = s[take]
    grow = ((src >= 0) & ~cover).ravel()
    pick = src.ravel()[grow]
    for m in maps:
        flat = m.reshape(H * W, -1)
        flat[grow] = flat[pick]


def unwrap(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.0015, area_weight=0.0)
    try:
        bpy.ops.uv.pack_islands(rotate=True, rotate_method="ANY", margin_method="ADD", margin=0.0015, shape_method="CONCAVE")
    except TypeError:
        bpy.ops.uv.pack_islands(rotate=True, margin=0.0015)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_group(group, objs, size, tex, samples, prefix="p26a"):
    """Bake one atlas.  With P26_KEEP_AO=1 and an existing ORM map, the
    occlusion channel (geometry only, the slowest pass) is reused."""
    from PIL import Image
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = False
    sc.render.bake.use_selected_to_active = False
    mats = {s.material for o in objs for s in o.material_slots if s.material}
    n = max(1, -(-size // BAKE_TILE))
    tile = size // n
    uv0 = {}
    for o in objs:
        lay = o.data.uv_layers.active
        arr = np.empty(len(lay.data) * 2, np.float32)
        lay.data.foreach_get("uv", arr)
        uv0[o.name] = (lay, arr)
    res, cover = {}, None
    try:
        old_orm = os.path.join(tex, "%s_%s_orm.jpg" % (prefix, group))
        keep_ao = os.environ.get("P26_KEEP_AO") == "1" and os.path.exists(old_orm)
        for channel in ("basecolor", "roughness", "metallic", "normal", "ao"):
            if channel == "ao" and keep_ao:
                res["ao"] = np.ascontiguousarray(np.asarray(Image.open(old_orm).convert("RGB"))[::-1, :, 0])
                print("kept", group, "ao", flush=True)
                continue
            kind = {"normal": "NORMAL", "ao": "AO"}.get(channel, "EMIT")
            sc.cycles.samples = max(samples, 32) if channel == "ao" else samples
            rgb = channel in ("basecolor", "normal")
            full = np.zeros((size, size, 3) if rgb else (size, size), np.uint8)
            cov = np.zeros((size, size), bool)
            for ti in range(n):
                for tj in range(n):
                    if n > 1:
                        for lay, arr in uv0.values():
                            lay.data.foreach_set("uv", (arr.reshape(-1, 2) * n - np.array([ti, tj], np.float32)).ravel())
                    img = bpy.data.images.new("bake", tile, tile, alpha=True, float_buffer=(channel == "normal"))
                    img.generated_color = (0, 0, 0, 0)
                    img.colorspace_settings.name = "sRGB" if channel == "basecolor" else "Non-Color"
                    for m in mats:
                        nodes = m.node_tree.nodes
                        tgt = nodes.get("BAKE_TARGET") or nodes.new("ShaderNodeTexImage")
                        tgt.name = "BAKE_TARGET"
                        tgt.image = img
                        nodes.active = tgt
                        _route(m, channel)
                    bpy.ops.object.select_all(action="DESELECT")
                    for o in objs:
                        o.select_set(True)
                    bpy.context.view_layer.objects.active = objs[0]
                    bpy.ops.object.bake(type=kind, margin=0, normal_space="TANGENT")
                    buf = np.empty(tile * tile * 4, np.float32)
                    img.pixels.foreach_get(buf)
                    buf = buf.reshape(tile, tile, 4)
                    r0, c0 = tj * tile, ti * tile
                    part = buf[..., :3] if rgb else buf[..., 0]
                    full[r0:r0 + tile, c0:c0 + tile] = (np.clip(part, 0, 1) * 255 + 0.5).astype(np.uint8)
                    cov[r0:r0 + tile, c0:c0 + tile] = buf[..., 3] > 0.5
                    bpy.data.images.remove(img)
            for m in mats:
                _route(m, None)
            res[channel] = full
            cover = cov if cover is None else cover
            print("baked", group, channel, flush=True)
    finally:
        for lay, arr in uv0.values():
            lay.data.foreach_set("uv", arr)
    _dilate(list(res.values()), cover, 12)
    stem = os.path.join(tex, "%s_%s_" % (prefix, group))
    Image.fromarray(res["basecolor"][::-1]).save(stem + "basecolor.jpg", quality=93, subsampling=0)
    Image.fromarray(np.stack([res["ao"], res["roughness"], res["metallic"]], -1)[::-1]).save(stem + "orm.jpg", quality=94, subsampling=0)
    Image.fromarray(res["normal"][::-1]).save(stem + "normal.jpg", quality=95, subsampling=0)


def image_material(name, stem):
    m = bpy.data.materials.new(name)
    nt = NT(m)
    out = nt.node("ShaderNodeOutputMaterial")
    bsdf = nt.node("ShaderNodeBsdfPrincipled")
    nt.t.links.new(bsdf.outputs[0], out.inputs[0])

    def tex_node(suffix, cs):
        img = bpy.data.images.load(stem + suffix, check_existing=True)
        img.colorspace_settings.name = cs
        return nt.node("ShaderNodeTexImage", image=img)
    nt.t.links.new(tex_node("basecolor.jpg", "sRGB").outputs["Color"], bsdf.inputs["Base Color"])
    sep = nt.node("ShaderNodeSeparateColor")
    nt.t.links.new(tex_node("orm.jpg", "Non-Color").outputs["Color"], sep.inputs[0])
    nt.t.links.new(sep.outputs[1], bsdf.inputs["Roughness"])
    nt.t.links.new(sep.outputs[2], bsdf.inputs["Metallic"])
    nm = nt.node("ShaderNodeNormalMap")
    nt.t.links.new(tex_node("normal.jpg", "Non-Color").outputs["Color"], nm.inputs["Color"])
    nt.t.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    return m


def texture(h, tex, bake=False, samples=8):
    os.makedirs(tex, exist_ok=True)
    procedural(h, tex)
    groups = {g: (size, [h.objects[h.prefix + n] for n in names]) for g, (size, names) in GROUPS.items()}
    for g, (size, objs) in groups.items():
        unwrap(objs)
    stems = {g: os.path.join(tex, "p26a_%s_" % g) for g in groups}
    if bake:
        for g, (size, objs) in groups.items():
            if bake is True or g in bake:
                bake_group(g, objs, size, tex, samples)
    if all(os.path.exists(stems[g] + "basecolor.jpg") for g in groups) and (bake or os.environ.get("P26_PROCEDURAL") != "1"):
        for g, (size, objs) in groups.items():
            m = image_material("P26_" + g.capitalize(), stems[g])
            for o in objs:
                for s in o.material_slots:
                    s.material = m
        for m in list(bpy.data.materials):
            if m.users == 0 and m.name.startswith("P26_"):
                bpy.data.materials.remove(m)
