"""Open cockpit of the He 51 A-1, laid out from the owner's cockpit
screenshots: a grey upper panel with the magneto switch, altimeter (Hoehe),
airspeed (Fahrt), turn-and-bank and tachometer; a lower panel with the small
engine gauges and the compass; the two red-knobbed gun charging handles; a
brown padded roll above the panel and tan leather round the opening; a stick
with a ring grip; two yellow-knobbed levers on the right wall and the
throttle on the left; the sight mount on the cowl ahead of the roll.  PANEL
lists the instruments; the panel texture is painted from the same list
(he51_materials.paint_panel).
"""
import math

import bpy
from mathutils import Matrix, Vector

import he51 as H
from p26a import Builder

PANEL_X = 3.24
PANEL_Y, PANEL_Z = (-0.45, 0.45), (-0.05, 0.75)      # texture window in the panel plane
LOWER = (0.27, 0.15, 0.42)                            # lower panel: half-width, bottom, top
# name, y (starboard +), z, radius, face
PANEL = [
    ("magneto switch", -0.285, 0.545, 0.038, "magneto"), ("altimeter", -0.165, 0.575, 0.045, "alt"),
    ("airspeed", -0.045, 0.595, 0.050, "asi"), ("turn and bank", 0.105, 0.575, 0.047, "turn"),
    ("tachometer", 0.225, 0.550, 0.045, "tach"), ("clock", 0.315, 0.495, 0.028, "clock"),
    ("coolant temperature", -0.19, 0.325, 0.030, "temp"), ("oil temperature", -0.095, 0.335, 0.030, "temp"),
    ("oil pressure", 0.0, 0.335, 0.030, "press"), ("fuel pressure", 0.095, 0.335, 0.030, "press"),
    ("fuel quantity", 0.19, 0.325, 0.030, "fuel"), ("compass", 0.0, 0.225, 0.036, "compass"),
]
EYE = (3.72, 0.0, 0.93)


def panel_uv(y, z):
    return ((y - PANEL_Y[0]) / (PANEL_Y[1] - PANEL_Y[0]), (z - PANEL_Z[0]) / (PANEL_Z[1] - PANEL_Z[0]))


def inner(x, ang, inset=0.027):
    p = H.fus_point(x, ang)
    a, zt, zb, e = H.FUS(x)
    zc = 0.5 * (zt + zb)
    d = math.hypot(p[1], p[2] - zc)
    s = (d - inset) / d
    return Vector((x, p[1] * s, max(zc + (p[2] - zc) * s, H.FLOOR_Z)))


def build(h):
    col = h.col_cockpit
    X = PANEL_X
    lw, lz0, lz1 = LOWER
    b = Builder()
    arc = [inner(X, math.radians(a), 0.03) for a in range(6, 175, 4)]
    arc = [p for p in arc if p.z >= lz1 + 0.01]
    out = [(p.y, p.z) for p in arc] + [(arc[-1].y, lz1), (-lw, lz1), (-lw, lz0), (lw, lz0), (lw, lz1), (arc[0].y, lz1)]
    front = [(X, y, z) for y, z in out]
    back = [(X - 0.012, y, z) for y, z in out]
    b.face(b.ring(front), 0, [panel_uv(y, z) for y, z in out])
    b.face(b.ring(list(reversed(back))), 1)
    for i in range(len(out)):
        j = (i + 1) % len(out)
        b.poly([front[i], back[i], back[j], front[j]], 1)
    for name, y, z, r, face in PANEL:
        m = 22
        circ = lambda rr, dx: [(X + dx, y + rr * math.cos(2 * math.pi * k / m), z + rr * math.sin(2 * math.pi * k / m)) for k in range(m)]
        idx = [b.ring(q) for q in (circ(r + 0.006, 0.0), circ(r + 0.004, 0.008), circ(r, 0.008), circ(r, 0.003))]
        for a_, c_ in zip(idx, idx[1:]):
            b.bridge(a_, c_, 1)
        b.face(idx[3], 0, [panel_uv(q[1], q[2]) for q in circ(r, 0.003)])
    # the two red-knobbed gun charging handles, left of centre under the upper panel
    for y in (-0.115, -0.055):
        p0, p1 = Vector((X + 0.005, y, 0.435)), Vector((X + 0.06, y, 0.445))
        b.tube(p0, p1, 0.005, n=6, mat=1)
        b.revolve(p1, p1 + Vector((0.03, 0, 0.004)), [(0, 0.008), (0.5, 0.016), (1, 0.008)], n=10, mat=2)
    # sight mount on the cowl ahead of the padded roll
    zt = H.fus_top(3.15, 0.0)
    b.box([(3.08, -0.06, zt - 0.01), (3.21, -0.06, zt - 0.01), (3.21, 0.06, zt - 0.01), (3.08, 0.06, zt - 0.01),
           (3.10, -0.045, zt + 0.045), (3.21, -0.045, zt + 0.06), (3.21, 0.045, zt + 0.06), (3.10, 0.045, zt + 0.045)], mat=1)
    h.add("InstrumentPanel", b, mats=("Panel", "Bezel", "KnobRed"), collection=col, smooth=30.0)

    # padded roll above the panel (brown) and leather round the opening (tan)
    b = Builder()
    rings = []
    for k in range(13):
        y = -0.17 + 0.34 * k / 12.0
        sc = 0.55 + 0.45 * math.sin(math.pi * k / 12.0) ** 0.5
        zc = H.fus_top(3.275, y) + 0.012
        rings.append([(3.275 + 0.05 * sc * math.cos(a), y, zc + 0.042 * sc * math.sin(a)) for a in (2 * math.pi * i / 12 for i in range(12))])
    b.loft(rings)
    out_ = h.cockpit_outline
    rim = [Vector((x, y, H.fus_top(x, y) + 0.004)) for x, y in out_]
    keep = [i for i in range(len(rim)) if rim[i].x > 3.31 or abs(rim[i].y) > 0.15]
    start = next(i for i in keep if (i - 1) % len(rim) not in keep)              # the run starts just past the padded roll
    run = [rim[(start + k) % len(rim)] for k in range(len(keep))]
    H.sweep(b, run, 0.024, n=10, mat=1)
    h.add("CockpitPadding", b, mats=("LeatherBrown", "LeatherTan"), collection=col, smooth=60.0)

    # welded steel-tube structure on the walls
    b = Builder()
    for s in (1, -1):
        for a in (30, 75, 118):
            b.tube(inner(3.0, math.radians(90 - s * a), 0.03), inner(3.98, math.radians(90 - s * a), 0.03), 0.011, n=6)
        for x0, x1 in ((3.0, 3.35), (3.35, 3.7), (3.7, 3.98)):
            b.tube(inner(x0, math.radians(90 - s * 30), 0.03), inner(x1, math.radians(90 - s * 75), 0.03), 0.009, n=6)
            b.tube(inner(x1, math.radians(90 - s * 75), 0.03), inner(x1, math.radians(90 - s * 118), 0.03), 0.009, n=6)
    h.add("CockpitStructure", b, mats=("Interior",), collection=col, smooth=None)

    # seat with belts
    b = Builder()
    sx0, sx1, sw, zp = 3.52, 3.90, 0.20, -0.14
    b.box([(sx0, -sw, zp), (sx1, -sw, zp), (sx1, sw, zp), (sx0, sw, zp),
           (sx0, -sw, zp + 0.012), (sx1, -sw, zp + 0.012), (sx1, sw, zp + 0.012), (sx0, sw, zp + 0.012)])
    b.box([(sx1 - 0.012, -sw, zp), (sx1, -sw, zp), (sx1 + 0.07, -sw, 0.50), (sx1 + 0.058, -sw, 0.50),
           (sx1 - 0.012, sw, zp), (sx1, sw, zp), (sx1 + 0.07, sw, 0.50), (sx1 + 0.058, sw, 0.50)])
    for s in (-1, 1):
        b.box([(sx0, s * sw, zp), (sx1, s * sw, zp), (sx1, s * sw, zp + 0.16), (sx0, s * sw, zp + 0.07),
               (sx0, s * (sw - 0.01), zp), (sx1, s * (sw - 0.01), zp), (sx1, s * (sw - 0.01), zp + 0.16), (sx0, s * (sw - 0.01), zp + 0.07)])
        b.tube((sx0 + 0.05, s * 0.16, H.FLOOR_Z), (sx0 + 0.05, s * 0.16, zp), 0.011, n=6)
        b.bar((sx0 + 0.10, s * 0.19, zp + 0.016), (sx0 + 0.24, s * 0.05, zp + 0.016), 0.045, 0.004, mat=1)
        b.bar((sx1 + 0.062, s * 0.07, 0.48), (sx1 + 0.012, s * 0.08, 0.0), 0.045, 0.004, up=(1, 0, 0), mat=1)
    h.add("Seat", b, mats=("Interior", "Belt"), collection=col, smooth=None)

    # stick with a ring grip; rudder pedals; throttle (left); two yellow-knobbed levers (right)
    b = Builder()
    base = (3.46, 0, H.FLOOR_Z)
    b.revolve(base, (3.46, 0, H.FLOOR_Z + 0.06), [(0, 0.045), (1, 0.028)], n=12, mat=1)
    b.revolve((3.46, 0, H.FLOOR_Z + 0.05), (3.41, 0, 0.27), [(0, 0.012), (1, 0.011)], n=8, mat=0)
    c = Vector((3.40, 0, 0.335))
    for k in range(14):
        a0, a1 = 2 * math.pi * k / 14, 2 * math.pi * (k + 1) / 14
        b.tube(c + Vector((0, 0.06 * math.sin(a0), 0.06 * math.cos(a0))), c + Vector((0, 0.06 * math.sin(a1), 0.06 * math.cos(a1))), 0.011, n=6, mat=1)
    h.add("Stick", b, mats=("Interior", "Black"), collection=col, origin=(3.46, 0, H.FLOOR_Z + 0.03), axis=(0, 1, 0),
          hinge="stick forward (nose down)")
    b = Builder()
    b.tube((3.02, -0.22, 0.02), (3.02, 0.22, 0.02), 0.011, n=8)
    for s in (-1, 1):
        b.tube((3.02, s * 0.15, 0.02), (3.05, s * 0.15, -0.16), 0.009, n=6)
        b.bar((3.05, s * 0.09, -0.15), (3.05, s * 0.21, -0.15), 0.10, 0.012, up=(1, 0, 0.25))
    h.add("RudderPedals", b, mats=("Interior",), collection=col)
    b = Builder()
    yl = -(H.fus_side(3.35, 0.30) - 0.05)
    p0, p1 = Vector((3.36, yl, 0.26)), Vector((3.30, yl + 0.01, 0.40))
    b.tube(p0, p1, 0.006, n=6)
    b.revolve(p1, p1 + (p1 - p0).normalized() * 0.03, [(0, 0.008), (0.5, 0.017), (1, 0.008)], n=10, mat=1)
    yr = H.fus_side(3.45, 0.30) - 0.05
    for k, dx in enumerate((0.0, 0.07)):
        p0, p1 = Vector((3.47 + dx, yr, 0.18)), Vector((3.41 + dx, yr - 0.015, 0.36 + 0.03 * k))
        b.tube(p0, p1, 0.006, n=6)
        b.revolve(p1, p1 + (p1 - p0).normalized() * 0.04, [(0, 0.010), (0.5, 0.022 + 0.006 * k), (1, 0.010)], n=10, mat=2)
    h.add("Levers", b, mats=("Interior", "Black", "KnobYellow"), collection=col)

    eye = bpy.data.objects.new(h.prefix + "Eye", None)
    eye.empty_display_size = 0.1
    col.objects.link(eye)
    eye.parent = h.root
    eye.matrix_basis = Matrix.Translation(h.tb(EYE)) @ Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Rotation(math.radians(70), 4, "X")
    h.world[eye.name] = eye.matrix_basis.copy()
    cam = bpy.data.objects.new(h.prefix + "Cam", bpy.data.cameras.new(h.prefix + "Cam"))
    cam.data.lens_unit = "FOV"
    cam.data.angle = math.radians(80)
    cam.data.clip_start = 0.02
    col.objects.link(cam)
    cam.parent = eye
    h.objects[eye.name] = eye
