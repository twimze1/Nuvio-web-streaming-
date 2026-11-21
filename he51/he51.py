"""Heinkel He 51 A-1 for Blender: geometry generator.

    blender -b -P he51.py -- [--out DIR] [--glb] [--bake [ext] [parts]] [--samples N]

Design coordinates (metres): x aft from the spinner tip, y to starboard,
z up from the thrust line.  Blender: nose along -Y, +Z up, port wing on +X.

Shape sources:
  * a side profile of an He 51 A-1 of I./JG 132 (Wikimedia Commons),
    measured at 144 px/m, which matches the published length and height;
  * the owner's top and front screenshots, for spans and strut positions;
  * published dimensions: span 11.0 m, length 8.4 m, height 3.2 m, wing
    area 27.2 m2 ("Warplanes of the Luftwaffe", via Wikipedia).
The mesh builder, the bake and the node helper are shared with ../p26a.
"""
import math
import os
import sys

import bpy
import bmesh  # noqa: E402  (must follow bpy)
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "p26a"))
import p26a as P  # noqa: E402
from p26a import Builder, table, lin, naca_t, camber, sym_ring  # noqa: E402

X_REF = 2.55                       # model origin: about 30 % of the mean chord
LENGTH = 8.4
PROP_DIAMETER = 3.10               # estimated from photographs (ground clearance)
GROUND_Z = -1.88
WHEEL = (1.83, 1.10, -1.60, 0.28)  # main wheel centre x, |y|, z, tyre radius
SKID = (7.35, -0.70)               # tail skid shoe x, z
FLOOR_Z = -0.30
COCKPIT = (3.28, 3.89, 0.30)       # opening: front, rear, half-width
GAP = 0.008
# wings: leading edge x, chord, z of the chord line at the centre, dihedral, span, thickness ratio, tip radius
UPPER = dict(le=1.74, chord=1.68, z=1.18, dih=math.radians(1.5), span=11.0, tc=0.11, tip=0.75)
LOWER = dict(le=2.30, chord=1.18, z=-0.375, dih=math.radians(3.0), span=8.2, tc=0.11, tip=0.60)
AILERON = (2.16, 4.86, 0.80)       # upper wing only: inboard, outboard |y|, hinge chord fraction
CUTOUT = (0.44, 0.833)             # upper centre-section trailing-edge cut-out: half-width, chord fraction
EXHAUST = (0.86, 1.76, 0.16, 0.45)  # exhaust trough on each side of the nose: x front, x rear, z bottom, z top

# fuselage: x, half-width, z top, z bottom, section exponent
FUS = table([
    (0.52, 0.30, 0.47, -0.27, 2.2), (0.70, 0.40, 0.56, -0.33, 2.6), (1.11, 0.45, 0.64, -0.40, 3.0),
    (1.86, 0.45, 0.69, -0.40, 3.0), (2.86, 0.44, 0.74, -0.44, 2.6), (3.30, 0.43, 0.74, -0.46, 2.4),
    (3.89, 0.42, 0.74, -0.46, 2.3), (4.92, 0.34, 0.625, -0.42, 2.2), (6.03, 0.24, 0.555, -0.36, 2.1),
    (6.69, 0.17, 0.55, -0.32, 2.0), (7.64, 0.03, 0.50, -0.24, 2.0),
])
TAIL_LE = lin([0.0, 0.6, 1.2, 1.6, 1.8], [6.61, 6.68, 6.90, 7.20, 7.44])
TAIL_TE = lin([0.0, 0.12, 0.6, 1.2, 1.6, 1.8], [7.86, 7.90, 7.94, 7.88, 7.70, 7.46])
TAIL_HINGE, TAIL_Z = 7.38, 0.25
FIN_LE = lin([0.45, 0.55, 0.9, 1.2, 1.34, 1.375], [6.55, 6.64, 7.02, 7.34, 7.50, 7.60])
RUD_TE = lin([-0.24, -0.04, 0.35, 0.8, 1.125, 1.3, 1.375], [7.72, 8.25, 8.39, 8.33, 8.14, 7.90, 7.68])
RUD_HINGE = 7.64


def fus_point(x, ang):
    a, zt, zb, e = FUS(x)
    zc = 0.5 * (zt + zb)
    c, s = math.cos(ang), math.sin(ang)
    return (x, a * math.copysign(abs(c) ** (2 / e), c), zc + (zt - zc if s >= 0 else zc - zb) * math.copysign(abs(s) ** (2 / e), s))


def fus_top(x, y=0.0):
    a, zt, zb, e = FUS(x)
    zc = 0.5 * (zt + zb)
    return zc + (zt - zc) * (1 - min(abs(y) / a, 0.999) ** e) ** (1 / e)


def fus_side(x, z):
    a, zt, zb, e = FUS(x)
    zc = 0.5 * (zt + zb)
    r = min(abs(z - zc) / ((zt - zc) if z >= zc else (zc - zb)), 0.999)
    return a * (1 - r ** e) ** (1 / e)


def sweep(b, pts, r, n=8, mat=0, closed=False):
    """A round bar along a polyline, with one ring at each point (smooth joints)."""
    pts = [Vector(p) for p in pts]
    m = len(pts)
    rings = []
    for i, p in enumerate(pts):
        a = pts[(i - 1) % m] if (closed or i > 0) else p
        c = pts[(i + 1) % m] if (closed or i < m - 1) else p
        t = (c - a).normalized()
        u = t.cross(Vector((0, 0, 1)))
        u = u.normalized() if u.length > 1e-6 else Vector((1, 0, 0))
        v = u.cross(t)
        rings.append([tuple(p + r * (math.cos(2 * math.pi * k / n) * u + math.sin(2 * math.pi * k / n) * v)) for k in range(n)])
    if closed:
        rings.append(rings[0])
    b.loft(rings, mat=mat, caps=(not closed, not closed))


def wing_geo(w, y):
    """Leading edge x, chord and z of the chord line at span station y (rounded tips)."""
    hs, rt = w["span"] / 2, w["tip"]
    t = max(0.0, (abs(y) - (hs - rt)) / rt)
    c = w["chord"] * math.sqrt(max(1 - min(t, 0.9995) ** 2, 0.001))
    return w["le"] + (w["chord"] - c) * 0.45, c, w["z"] + abs(y) * math.tan(w["dih"])


def wing_ring(w, y, f0=0.0, f1=1.0, n=10):
    le, c, z = wing_geo(w, y)
    us = [0.5 * (1 - math.cos(math.pi * k / n)) for k in range(n + 1)]
    fs = [f0 + (f1 - f0) * u for u in us]
    pt = lambda f, side: (le + f * c, y, z + (camber(f, 0.03) + side * w["tc"] * naca_t(f)) * c)
    up = [pt(f, +1) for f in reversed(fs)]
    lo = [pt(f, -1) for f in fs]
    return up + (lo[1:] if f0 <= 1e-6 else lo)


def wing_surf(w, x, y, side):
    le, c, z = wing_geo(w, y)
    f = min(max((x - le) / c, 0.0), 1.0)
    return z + (camber(f, 0.03) + side * w["tc"] * naca_t(f)) * c


MATERIALS = {
    #  name          base colour (linear)        metal  rough  alpha
    "Skin":        ((0.325, 0.385, 0.375), 0.0, 0.42, 1.0),      # RLM 63 light grey
    "Wood":        ((0.16, 0.055, 0.03), 0.0, 0.30, 1.0),     # varnished laminated propeller
    "Steel":       ((0.30, 0.30, 0.31), 1.0, 0.40, 1.0),
    "Strut":       ((0.10, 0.11, 0.12), 0.3, 0.45, 1.0),      # dark blue-grey struts
    "Black":       ((0.015, 0.015, 0.015), 0.0, 0.5, 1.0),
    "Bezel":       ((0.012, 0.012, 0.012), 0.0, 0.45, 1.0),   # instrument rims (plain, not baked)
    "Exhaust":     ((0.10, 0.07, 0.05), 0.7, 0.7, 1.0),
    "Tyre":        ((0.02, 0.02, 0.02), 0.0, 0.85, 1.0),
    "Glass":       ((0.6, 0.7, 0.7), 0.0, 0.03, 0.25),
    "LeatherBrown": ((0.11, 0.045, 0.022), 0.0, 0.5, 1.0),
    "LeatherTan":  ((0.33, 0.25, 0.15), 0.0, 0.6, 1.0),
    "Interior":    ((0.20, 0.22, 0.19), 0.0, 0.5, 1.0),       # grey-green
    "Panel":       ((0.2, 0.22, 0.2), 0.0, 0.5, 1.0),
    "Belt":        ((0.42, 0.38, 0.27), 0.0, 0.8, 1.0),
    "KnobYellow":  ((0.75, 0.55, 0.04), 0.0, 0.35, 1.0),
    "KnobRed":     ((0.5, 0.03, 0.02), 0.0, 0.35, 1.0),
}


def material(name):
    full = "He51_" + name
    m = bpy.data.materials.get(full)
    if m:
        return m
    color, metal, rough, alpha = MATERIALS[name]
    m = bpy.data.materials.new(full)
    m.use_nodes = True
    m.diffuse_color = (*color, alpha)
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Alpha"].default_value = alpha
    if alpha < 1.0:
        for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED")):
            try:
                setattr(m, attr, val)
            except (AttributeError, TypeError):
                pass
    return m


class He51(P.Peashooter):
    prefix = "He51_"
    x_ref = X_REF

    def __init__(self):
        self.objects, self.world = {}, {}
        sc = bpy.context.scene
        self.col = bpy.data.collections.new("He 51 A-1")
        sc.collection.children.link(self.col)
        self.col_cockpit = bpy.data.collections.new("He 51 Cockpit")
        self.col.children.link(self.col_cockpit)
        self.root = bpy.data.objects.new("He-51A-1", None)
        self.root.empty_display_size = 1.0
        self.col.objects.link(self.root)
        self.world[self.root.name] = Matrix.Identity(4)

    def material(self, name):
        return material(name)

    def boolean(self, obj, b, mat):
        me = bpy.data.meshes.new("cutter")
        inv = self.world[obj.name].inverted()
        me.from_pydata([tuple(inv @ self.tb(p)) for p in b.verts], [], b.faces)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(material(mat))
        ob = bpy.data.objects.new("cutter", me)
        bpy.context.scene.collection.objects.link(ob)
        mod = obj.modifiers.new("cut", "BOOLEAN")
        mod.operation, mod.solver, mod.object, mod.material_mode = "DIFFERENCE", "EXACT", ob, "TRANSFER"
        new = bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        obj.modifiers.remove(mod)
        old = obj.data
        obj.data = new
        new.name = old.name
        bpy.data.meshes.remove(old)
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)

    # -- fuselage, nose ----------------------------------------------------------
    def build_fuselage(self):
        b = Builder()
        n = 44
        xs = list(np.arange(0.52, 7.64, 0.12)) + [7.64]
        b.loft([[fus_point(x, 2 * math.pi * k / n) for k in range(n)] for x in xs])
        fus = self.add("Fuselage", b, mats=("Skin", "Interior", "LeatherTan"))
        c = Builder()                                           # cockpit cavity inside the skin
        rings = []
        for x in np.linspace(2.86, 4.02, 12):
            a, zt, zb, e = FUS(x)
            zc = 0.5 * (zt + zb)
            ring = []
            for k in range(36):
                p = fus_point(x, 2 * math.pi * k / 36)
                d = math.hypot(p[1], p[2] - zc)
                s = (d - 0.025) / d
                ring.append((x, p[1] * s, max(zc + (p[2] - zc) * s, FLOOR_Z)))
            rings.append(ring)
        c.loft(rings)
        self.boolean(fus, c, "Interior")
        x0, x1, hw = COCKPIT
        c = Builder()
        xc, hl, m = (x0 + x1) / 2, (x1 - x0) / 2, 28
        sq = lambda v: math.copysign(abs(v) ** (2 / 3.0), v)
        self.cockpit_outline = [(xc + hl * sq(math.cos(2 * math.pi * k / m)), hw * sq(math.sin(2 * math.pi * k / m))) for k in range(m)]
        c.loft([[(x, y, 0.2) for x, y in self.cockpit_outline], [(x, y, 1.3) for x, y in self.cockpit_outline]])
        self.boolean(fus, c, "LeatherTan")

        # spinner and the two-blade wooden propeller
        b = Builder()
        b.revolve((0.0, 0, 0), (0.515, 0, 0), [(0, 0.004), (0.06, 0.06), (0.2, 0.13), (0.45, 0.20), (0.75, 0.245), (1, 0.262)], n=28, mat=0)
        Rp, xp = PROP_DIAMETER / 2, 0.34
        for sg in (-1, 1):
            rings = []
            for i in range(15):
                rf = 0.13 + 0.87 * i / 14.0
                chord = 0.25 * (math.sin(math.pi * min(rf * 0.95 + 0.06, 1.0)) ** 0.7) * (1.0 if rf < 0.9 else math.sqrt(max(1 - ((rf - 0.9) / 0.1) ** 2, 0.02)))
                chord = max(chord, 0.014)
                thick = max(0.13 * (1 - rf) ** 1.8 + 0.008, 0.008)
                pitch = math.radians(56 - 40 * rf ** 0.7)
                sec = []
                for k in range(10):
                    a = 2 * math.pi * k / 10
                    u, v = 0.5 * chord * math.cos(a), 0.5 * thick * math.sin(a) * (1.0 if math.sin(a) > 0 else 0.55)
                    sec.append((xp - u * math.sin(pitch) * sg - v * math.cos(pitch), u * math.cos(pitch) - v * math.sin(pitch) * sg, sg * rf * Rp))
                rings.append(sec)
            b.loft(rings, mat=1)
        self.add("Propeller", b, mats=("Skin", "Wood"), origin=(xp, 0, 0), axis=(-1, 0, 0),
                 hinge="propeller turns (clockwise seen from the cockpit)", smooth=35.0)

        # exhaust: a recessed trough high on each side of the nose with six upright stubs; gun troughs on the cowl
        ex0, ex1, ez0, ez1 = EXHAUST
        zs = np.linspace(ez0, ez1, 7)
        for s in (1, -1):
            c = Builder()
            c.loft([[(x, s * (fus_side(x, z) - 0.03), z) for z in zs] + [(x, s * 0.7, z) for z in reversed(zs)] for x in np.linspace(ex0, ex1, 9)])
            self.boolean(fus, c, "Black")
        b = Builder()
        m = 14
        for s in (1, -1):
            for k in range(6):
                x, zc = ex0 + 0.085 + (ex1 - ex0 - 0.17) * k / 5.0, 0.5 * (ez0 + ez1)
                def oval(scale, out, lean):
                    pts = []
                    for i in range(m):
                        a = 2 * math.pi * i / m * s
                        dx, dz = 0.036 * scale * math.cos(a), 0.105 * scale * math.sin(a)
                        px = x + dx - 0.10 * dz + lean
                        pts.append((px, s * (fus_side(px, zc + dz) + out), zc + dz))
                    return pts
                b.loft([oval(1.0, -0.032, 0.0), oval(1.0, 0.014, 0.012)], mat=0, caps=(False, False))
                b.loft([oval(1.0, 0.014, 0.012), oval(0.78, 0.014, 0.012), oval(0.78, -0.02, 0.0)], mat=1, caps=(False, True))
            ya = s * 0.15
            b.revolve((0.66, ya, fus_top(0.66, 0.15) - 0.005), (2.80, ya, fus_top(2.80, 0.15) + 0.012), [(0, 0.012), (0.02, 0.02), (1, 0.02)], n=8, mat=2)
        self.add("Exhausts", b, mats=("Exhaust", "Black", "Skin"), smooth=35.0)
        b = Builder()
        r0, r1 = 1.80, 2.52
        zt = lambda x: -0.36
        pts = [(r0 + 0.10, -0.33, -0.40), (r1, -0.33, -0.42), (r1, 0.33, -0.42), (r0 + 0.10, 0.33, -0.40),
               (r0, -0.36, -0.70), (r1 - 0.05, -0.36, -0.70), (r1 - 0.05, 0.36, -0.70), (r0, 0.36, -0.70)]
        b.box(pts, mat=0)
        b.poly([(r0 + 0.094, -0.30, -0.42), (r0 + 0.094, 0.30, -0.42), (r0 - 0.004, 0.33, -0.68), (r0 - 0.004, -0.33, -0.68)], mat=1)
        b.poly([(r1 + 0.003, -0.30, -0.44), (r1 - 0.047, -0.33, -0.68), (r1 - 0.047, 0.33, -0.68), (r1 + 0.003, 0.30, -0.44)], mat=1)
        self.add("Radiator", b, mats=("Skin", "Black"), smooth=None)

    def build_windscreen(self):
        # a small frameless curved screen raked back from a black base strip on the cockpit rim
        m = 24
        base, top = [], []
        for i in range(m + 1):
            t = -1 + 2.0 * i / m
            c, sn = math.cos(t * math.pi / 2), math.sin(t * math.pi / 2)
            x, y = 3.30 - 0.28 * c, 0.31 * sn
            z = fus_top(x, y) - 0.004
            hgt = 0.215 * max(c, 0.0) ** 0.6
            base.append((x, y, z))
            top.append((x + 1.02 * hgt, y * (1.0 + 0.06 * c), z + hgt))
        g = Builder()
        for i in range(m):
            g.poly([base[i], base[i + 1], top[i + 1], top[i]])
        self.add("Windscreen", g, mats=("Glass",), smooth=60.0)
        f = Builder()
        sweep(f, base, 0.008, n=6, mat=1)
        sweep(f, top, 0.0035, n=6, mat=1)
        # ring-and-bead sight on the cowl
        zr = fus_top(2.86) + 0.10
        f.tube((2.86, 0, fus_top(2.86) - 0.01), (2.86, 0, zr - 0.035), 0.005, n=6, mat=1)
        for k in range(12):
            a0, a1 = 2 * math.pi * k / 12, 2 * math.pi * (k + 1) / 12
            f.tube((2.86, 0.035 * math.sin(a0), zr + 0.035 * math.cos(a0)), (2.86, 0.035 * math.sin(a1), zr + 0.035 * math.cos(a1)), 0.003, n=4, mat=1)
        f.revolve((2.05, 0, fus_top(2.05) - 0.01), (2.05, 0, zr + 0.004), [(0, 0.005), (0.9, 0.004), (1, 0.008)], n=6, mat=1)
        self.add("WindscreenFrame", f, mats=("Strut", "Black"))

    # -- wings, struts, wires ------------------------------------------------------
    def build_wings(self):
        y0, y1, fh = AILERON
        cw, cf = CUTOUT
        hs = UPPER["span"] / 2
        b = Builder()
        b.loft([wing_ring(UPPER, y, 0.0, cf) for y in (-cw, 0.0, cw)])
        tip = [y1, 4.95, 5.05, 5.15, 5.25, 5.33, 5.40, 5.45, 5.485, 5.498]
        for s in (1, -1):
            b.loft([wing_ring(UPPER, s * y) for y in (cw, 0.9, 1.5, y0)])
            b.loft([wing_ring(UPPER, s * y, 0.0, fh - GAP / 1.2) for y in np.linspace(y0, y1, 6)])
            b.loft([wing_ring(UPPER, s * y) for y in tip])
        up = self.add("UpperWing", b)
        for s, tag in ((1, "R"), (-1, "L")):
            a = Builder()
            a.loft([wing_ring(UPPER, s * y, fh + GAP / 1.2, 1.0, n=5) for y in np.linspace(y0 + GAP, y1 - GAP, 6)])
            hx = UPPER["le"] + fh * UPPER["chord"]
            p0 = Vector((hx, s * y0, wing_surf(UPPER, hx, s * y0, 0)))
            p1 = Vector((hx, s * y1, wing_surf(UPPER, hx, s * y1, 0)))
            self.add("Aileron_" + tag, a, origin=p0, axis=(p1 - p0) * s, hinge="trailing edge down")
        b = Builder()
        hl = LOWER["span"] / 2
        ys = [0.0, 0.5, 1.2, 2.0, 2.8, hl - 0.6, hl - 0.48, hl - 0.36, hl - 0.25, hl - 0.15, hl - 0.07, hl - 0.02, hl - 0.002]
        b.loft([wing_ring(LOWER, y) for y in [-v for v in reversed(ys[1:])] + ys])
        self.add("LowerWing", b)
        # radio mast on the upper wing, with the aerial to the fin
        m = Builder()
        zt = wing_surf(UPPER, 2.67, 0, +1)
        m.revolve((2.67, 0, zt - 0.01), (2.67, 0, zt + 0.30), [(0, 0.014), (1, 0.008)], n=8)
        m.tube((2.67, 0, zt + 0.30), (7.55, 0, 1.36), 0.0025, n=4, mat=1)
        self.add("Mast", m, mats=("Strut", "Steel"), parent=up)

    def build_struts(self):
        b = Builder()
        w = Builder()

        def strut(p0, p1, chord=0.075, thick=0.028):
            b.bar(p0, p1, chord, thick, up=(0, 1, 0))

        def wire(p0, p1):
            p0, p1 = Vector(p0), Vector(p1)
            w.tube(p0, p1, 0.0035, n=5)
            d = (p1 - p0).normalized()
            for q, sg in ((p0, 1), (p1, -1)):
                w.tube(q, q + d * (sg * 0.07), 0.007, n=6)
        for s in (1, -1):
            # cabane: an N each side, from the upper longeron to the centre section
            f1, f2 = (1.95, s * 0.40, fus_top(1.95, 0.40) - 0.02), (2.95, s * 0.40, fus_top(2.95, 0.40) - 0.02)
            w1 = (2.00, s * 0.52, wing_surf(UPPER, 2.00, 0.52, -1) + 0.01)
            w2 = (3.00, s * 0.52, wing_surf(UPPER, 3.00, 0.52, -1) + 0.01)
            strut(f1, w1, 0.06, 0.025)
            strut(f2, w2, 0.06, 0.025)
            strut(f1, w2, 0.05, 0.022)
            # interplane N struts, leaning outwards towards the upper wing
            l1 = (2.45, s * 2.72, wing_surf(LOWER, 2.45, 2.72, +1) - 0.01)
            l2 = (3.20, s * 2.72, wing_surf(LOWER, 3.20, 2.72, +1) - 0.01)
            u1 = (1.95, s * 3.62, wing_surf(UPPER, 1.95, 3.62, -1) + 0.01)
            u2 = (2.95, s * 3.62, wing_surf(UPPER, 2.95, 3.62, -1) + 0.01)
            strut(l1, u1)
            strut(l2, u2)
            strut(l1, u2, 0.06, 0.025)
            # flying wires (root of the lower wing to the top of the struts), landing wires (cabane to strut feet)
            for xr, u in ((2.45, u1), (3.20, u2)):
                wire((xr, s * (fus_side(xr, -0.30) + 0.01), wing_surf(LOWER, xr, 0.5, +1)), u)
            wire(w1, l1)
            wire(w2, l2)
            # tail bracing
            wire((7.30, 0.0, 1.05), (7.20, s * 1.25, TAIL_Z + 0.03))
            wire((7.20, s * 1.25, TAIL_Z - 0.03), (7.20, s * 0.10, -0.26))
        self.add("Struts", b, mats=("Strut",), smooth=None)
        self.add("Wires", w, mats=("Steel",), smooth=None)

    # -- tail ------------------------------------------------------------------------
    def build_tail(self):
        hz = lambda x, h, y: (x, y, TAIL_Z + h)
        frac = lambda le, te, x: (x - le) / (te - le)
        b = Builder()
        ys = [0.0, 0.3, 0.7, 1.1, 1.4, 1.6]
        b.loft([sym_ring(TAIL_LE(abs(y)), TAIL_TE(abs(y)), 0.0, min(frac(TAIL_LE(abs(y)), TAIL_TE(abs(y)), TAIL_HINGE - GAP), 0.999), 0.04,
                         lambda x, h, y=y: hz(x, h, y)) for y in [-v for v in reversed(ys[1:])] + ys])
        self.add("Tailplane", b)
        for s, tag in ((1, "R"), (-1, "L")):
            e = Builder()
            rings = []
            for y in (0.12, 0.4, 0.8, 1.2, 1.5, 1.62, 1.70, 1.76, 1.79):
                le, te = TAIL_LE(y), TAIL_TE(y)
                rings.append(sym_ring(le, te, max(frac(le, te, TAIL_HINGE + GAP), 0.03), 1.0, 0.04, lambda x, h, y=y: hz(x, h, s * y), n=5))
            e.loft(rings)
            self.add("Elevator_" + tag, e, origin=(TAIL_HINGE, s * 0.12, TAIL_Z), axis=(0, s, 0), hinge="trailing edge down")
        vy = lambda x, h, z: (x, h, z)
        b = Builder()
        b.loft([sym_ring(FIN_LE(z), RUD_TE(z), 0.0, min(frac(FIN_LE(z), RUD_TE(z), RUD_HINGE - GAP), 0.999), 0.035,
                         lambda x, h, z=z: vy(x, h, z)) for z in (0.42, 0.55, 0.75, 0.95, 1.15, 1.28, 1.35, 1.372)])
        self.add("Fin", b)
        r = Builder()
        rings = []
        for z in (-0.238, -0.2, -0.1, 0.05, 0.2, 0.4, 0.6, 0.8, 1.0, 1.15, 1.27, 1.34, 1.372):
            le = FIN_LE(max(z, 0.45)) if z > 0.45 else 6.55
            te = RUD_TE(z)
            rings.append(sym_ring(le, te, max(frac(le, te, RUD_HINGE + GAP), 0.03), 1.0, 0.035 if z > 0.4 else 0.035 + 0.06 * (0.4 - z),
                                  lambda x, h, z=z: vy(x, h, z), n=6))
        r.loft(rings)
        self.add("Rudder", r, origin=(RUD_HINGE, 0, -0.24), axis=(0, 0, 1), up=(0, 1, 0),
                 hinge="trailing edge to starboard (nose-right yaw)")

    # -- landing gear ------------------------------------------------------------------
    def build_gear(self):
        wx, wy, wz, wr = WHEEL
        for s, tag in ((1, "R"), (-1, "L")):
            b = Builder()
            y = s * wy
            b.revolve((wx, y - 0.07, wz), (wx, y + 0.07, wz), [(0, wr * 0.5), (0.02, wr * 0.8), (0.12, wr * 0.95), (0.3, wr), (0.7, wr),
                                                                (0.88, wr * 0.95), (0.98, wr * 0.8), (1, wr * 0.5)], n=30, mat=1, cap_mats=(0, 0))
            rings = []
            for x in np.linspace(1.39, 2.56, 16):                 # spat
                u = (x - 1.39) / 1.17
                sh = (math.sin(math.pi * u ** 0.6)) ** 0.75 if 0 < u < 1 else 0.0
                hw, zt, zb = max(0.15 * sh, 0.004), wz + max(0.37 * sh, 0.01), wz - max(0.13 * sh, 0.01)
                rings.append([(x, y + hw * math.cos(2 * math.pi * k / 14), (zt + zb) / 2 + (zt - zb) / 2 * math.sin(2 * math.pi * k / 14)) for k in range(14)])
            b.loft(rings, mat=0)
            rings = []
            for u in np.linspace(0, 1, 6):                        # cantilever leg from the fuselage to the spat
                z = -0.36 + (wz + 0.30 + 0.36) * u
                yy = s * (0.38 + (wy - 0.02 - 0.38) * u)
                xf = 1.88 - 0.16 * u
                rings.append(sym_ring(xf, xf + 0.34, 0.0, 1.0, 0.30, lambda x, h, z=z, yy=yy: (x, yy + h, z), n=7))
            b.loft(rings, mat=0)
            self.add("MainGear_" + tag, b, mats=("Skin", "Tyre"))
        b = Builder()
        sx, sz = SKID
        b.revolve((6.85, 0, -0.30), (sx, 0, sz + 0.03), [(0, 0.03), (1, 0.02)], n=8)
        b.box([(sx - 0.10, -0.03, sz + 0.02), (sx + 0.08, -0.03, sz + 0.05), (sx + 0.08, 0.03, sz + 0.05), (sx - 0.10, 0.03, sz + 0.02),
               (sx - 0.10, -0.03, sz), (sx + 0.08, -0.03, sz + 0.03), (sx + 0.08, 0.03, sz + 0.03), (sx - 0.10, 0.03, sz)])
        self.add("TailSkid", b, mats=("Steel",))

    def build(self):
        self.build_fuselage()
        self.build_windscreen()
        self.build_wings()
        self.build_struts()
        self.build_tail()
        self.build_gear()
        import he51_cockpit
        he51_cockpit.build(self)
        sx, sz = SKID
        self.root["span_m"] = UPPER["span"]
        self.root["length_m"] = LENGTH
        self.root["x_ref"] = X_REF
        self.root["ground_z"] = GROUND_Z
        self.root["ground_pitch_deg"] = math.degrees(math.atan2(sz - GROUND_Z, sx - WHEEL[0]))
        self.root["main_wheel_x"] = WHEEL[0] - X_REF
        return self.root


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=HERE)
    ap.add_argument("--glb", action="store_true")
    ap.add_argument("--bake", nargs="*", default=None)
    ap.add_argument("--samples", type=int, default=8)
    args = ap.parse_args(argv)
    sys.path.insert(0, HERE)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    h = He51()
    h.build()
    import he51_materials
    he51_materials.texture(h, os.path.join(HERE, "textures"), bake=False if args.bake is None else (args.bake or True), samples=args.samples)
    path = os.path.join(args.out, "He-51A-1.blend")
    if os.path.exists(path):
        os.remove(path)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print("saved", path)
    if args.glb:
        glb = os.path.join(args.out, "He-51A-1.glb")
        bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_apply=True, use_visible=True,
                                  export_extras=True, export_cameras=True)
        print("saved", glb)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
