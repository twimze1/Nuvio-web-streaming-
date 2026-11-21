"""Open cockpit of the P-26A: instrument panel, seat, stick, rudder pedals,
throttle, padded rim, structure on the bare-metal walls, and the pilot's
eye point with a camera.

The layout follows the general arrangement of the type (curved black panel
with the flight instruments in two rows, engine instruments to the right, a
small electrical panel at lower left, fuel and oil gauges on a centre
pedestal).  PANEL lists every instrument; the panel texture is painted from
the same list (p26a_materials.paint_panel), so faces and bezels line up.
"""
import math

import bpy
from mathutils import Matrix, Vector

import p26a as P

PANEL_X = 1.935
# panel texture window in the panel plane: y from -0.5 to 0.5, z from -0.15 to 0.65
PANEL_Y, PANEL_Z = (-0.5, 0.5), (-0.15, 0.65)
# instruments: name, y (starboard +), z, radius, face
PANEL = [
    ("airspeed", -0.175, 0.455, 0.050, "asi"), ("compass", 0.0, 0.480, 0.043, "compass"),
    ("tachometer", 0.175, 0.455, 0.050, "tach"), ("clock", 0.305, 0.395, 0.031, "clock"),
    ("altimeter", -0.170, 0.320, 0.044, "alt"), ("turn and bank", 0.0, 0.335, 0.044, "turn"),
    ("engine gauge unit", 0.150, 0.305, 0.044, "engine"), ("manifold pressure", 0.280, 0.270, 0.038, "map"),
    ("ammeter", -0.300, 0.330, 0.028, "amp"),
    ("fuel quantity", -0.048, 0.025, 0.034, "fuel"), ("oil temperature", 0.048, 0.025, 0.034, "oil"),
]
EYE = (2.52, 0.0, 0.84)


def panel_uv(y, z):
    return ((y - PANEL_Y[0]) / (PANEL_Y[1] - PANEL_Y[0]), (z - PANEL_Z[0]) / (PANEL_Z[1] - PANEL_Z[0]))


def inner(x, ang, inset=0.03):
    """Point on the cockpit wall (the skin inset) at station x."""
    p = P.fus_point(x, ang)
    a, zt, zb, e = P.FUSELAGE(x)
    zc = 0.5 * (zt + zb)
    d = math.hypot(p[1], p[2] - zc)
    s = (d - inset) / d
    return Vector((x, p[1] * s, max(zc + (p[2] - zc) * s, P.FLOOR_Z)))


def build(h):
    B = P.Builder
    col = h.col_cockpit
    x0, x1, hw = P.COCKPIT

    # ---- instrument panel: follows the wall above z = 0.14, with a centre pedestal
    b = B()
    X = PANEL_X
    arc = [inner(X, math.radians(a), 0.034) for a in range(8, 173, 6)]
    arc = [p for p in arc if p.z >= 0.14]
    out = [(arc[0].y, 0.14)] + [(p.y, p.z) for p in arc] + [(arc[-1].y, 0.14), (-0.105, 0.14), (-0.105, -0.085),
                                                             (0.105, -0.085), (0.105, 0.14)]
    b.face(b.ring([(X, y, z) for y, z in out]), 0, [panel_uv(y, z) for y, z in out])
    b.face(b.ring([(X - 0.012, y, z) for y, z in reversed(out)]), 1)
    n = len(out)
    front = [(X, y, z) for y, z in out]
    back = [(X - 0.012, y, z) for y, z in out]
    for i in range(n):
        j = (i + 1) % n
        b.poly([front[i], back[i], back[j], front[j]], 1)
    for name, y, z, r, face in PANEL:                        # bezels, with the dial 4 mm inside
        m = 24
        ring0 = [(X, y + (r + 0.006) * math.cos(2 * math.pi * k / m), z + (r + 0.006) * math.sin(2 * math.pi * k / m)) for k in range(m)]
        ring1 = [(X + 0.008, y + (r + 0.004) * math.cos(2 * math.pi * k / m), z + (r + 0.004) * math.sin(2 * math.pi * k / m)) for k in range(m)]
        ring2 = [(X + 0.008, y + r * math.cos(2 * math.pi * k / m), z + r * math.sin(2 * math.pi * k / m)) for k in range(m)]
        ring3 = [(X + 0.003, y + r * math.cos(2 * math.pi * k / m), z + r * math.sin(2 * math.pi * k / m)) for k in range(m)]
        idx = [b.ring(q) for q in (ring0, ring1, ring2, ring3)]
        for a_, c_ in zip(idx, idx[1:]):
            b.bridge(a_, c_, 1)
        b.face(idx[3], 0, [panel_uv(q[1], q[2]) for q in ring3])
    h.add("InstrumentPanel", b, mats=("Panel", "Black"), collection=col, smooth=30.0)

    # ---- structure on the walls: frames and stringers (bare aluminium)
    b = B()
    for x in (2.02, 2.34, 2.66, 2.94):
        for s in (1, -1):
            pts = [inner(x, math.radians(90 - s * a), 0.029) for a in range(22, 121, 9)]
            pts = [p for p in pts if p.z > P.FLOOR_Z + 0.01]
            for p0, p1 in zip(pts, pts[1:]):
                nrm = Vector((0, -p0.y, -(p0.z - 0.0))).normalized()
                b.bar(p0, p1, 0.022, 0.022, up=tuple(nrm))
    for a in (38, 62, 86, 112):
        for s in (1, -1):
            p0, p1 = inner(1.96, math.radians(90 - s * a), 0.03), inner(2.94, math.radians(90 - s * a), 0.03)
            if p0.z > P.FLOOR_Z + 0.02:
                b.bar(p0, p1, 0.016, 0.014, up=(0, -s, 0))
    h.add("CockpitStructure", b, mats=("Interior",), collection=col, smooth=None)

    # ---- seat: aluminium bucket on a tube frame, lap and shoulder belts
    b = B()
    sx0, sx1, sw = 2.50, 2.90, 0.21
    zp = 0.02
    b.box([(sx0, -sw, zp), (sx1, -sw, zp), (sx1, sw, zp), (sx0, sw, zp),
           (sx0, -sw, zp + 0.012), (sx1, -sw, zp + 0.012), (sx1, sw, zp + 0.012), (sx0, sw, zp + 0.012)])
    b.box([(sx1 - 0.012, -sw, zp), (sx1, -sw, zp), (sx1 + 0.07, -sw, 0.58), (sx1 + 0.058, -sw, 0.58),
           (sx1 - 0.012, sw, zp), (sx1, sw, zp), (sx1 + 0.07, sw, 0.58), (sx1 + 0.058, sw, 0.58)])
    for s in (-1, 1):
        b.box([(sx0, s * sw, zp), (sx1, s * sw, zp), (sx1, s * sw, zp + 0.16), (sx0, s * sw, zp + 0.07),
               (sx0, s * (sw - 0.01), zp), (sx1, s * (sw - 0.01), zp), (sx1, s * (sw - 0.01), zp + 0.16), (sx0, s * (sw - 0.01), zp + 0.07)])
        b.tube((sx0 + 0.05, s * 0.17, P.FLOOR_Z), (sx0 + 0.05, s * 0.17, zp), 0.012, n=6)
        b.tube((sx1 - 0.05, s * 0.17, P.FLOOR_Z), (sx1 - 0.05, s * 0.17, zp), 0.012, n=6)
        b.bar((sx0 + 0.10, s * 0.20, zp + 0.016), (sx0 + 0.24, s * 0.05, zp + 0.016), 0.045, 0.004, mat=1)      # lap belt
        b.bar((sx1 + 0.062, s * 0.07, 0.56), (sx1 + 0.012, s * 0.08, 0.12), 0.045, 0.004, up=(1, 0, 0), mat=1)   # shoulder strap
    b.box([(sx0 + 0.02, -sw + 0.02, zp + 0.012), (sx1 - 0.02, -sw + 0.02, zp + 0.012), (sx1 - 0.02, sw - 0.02, zp + 0.012),
           (sx0 + 0.02, sw - 0.02, zp + 0.012), (sx0 + 0.02, -sw + 0.02, zp + 0.05), (sx1 - 0.02, -sw + 0.02, zp + 0.05),
           (sx1 - 0.02, sw - 0.02, zp + 0.05), (sx0 + 0.02, sw - 0.02, zp + 0.05)], mat=2)                       # cushion
    h.add("Seat", b, mats=("Interior", "Belt", "Leather"), collection=col, smooth=None)

    # ---- control stick, rudder pedals, throttle quadrant
    b = B()
    b.revolve((2.25, 0, P.FLOOR_Z), (2.25, 0, P.FLOOR_Z + 0.06), [(0, 0.05), (1, 0.03)], n=12, mat=1)
    b.revolve((2.25, 0, P.FLOOR_Z + 0.05), (2.20, 0, 0.26), [(0, 0.012), (1, 0.011)], n=8, mat=0)
    b.revolve((2.20, 0, 0.25), (2.185, 0, 0.375), [(0, 0.016), (0.2, 0.019), (0.85, 0.019), (1, 0.014)], n=10, mat=1)
    b.tube((2.185, -0.02, 0.365), (2.165, -0.02, 0.385), 0.006, n=6, mat=1)                                       # trigger
    h.add("Stick", b, mats=("Interior", "Black"), collection=col, origin=(2.25, 0, P.FLOOR_Z + 0.03), axis=(0, 1, 0),
          hinge="stick forward (nose down)")
    b = B()
    b.tube((1.80, -0.24, 0.20), (1.80, 0.24, 0.20), 0.012, n=8)
    for s in (-1, 1):
        b.tube((1.80, s * 0.16, 0.20), (1.83, s * 0.16, 0.02), 0.009, n=6)
        b.bar((1.83, s * 0.10, 0.03), (1.83, s * 0.22, 0.03), 0.10, 0.012, up=(1, 0, 0.25))
    h.add("RudderPedals", b, mats=("Interior",), collection=col)
    b = B()
    yw = -(P.fus_side(2.26, 0.28) - 0.05)
    b.box([(2.16, yw, 0.22), (2.36, yw, 0.22), (2.36, yw + 0.035, 0.22), (2.16, yw + 0.035, 0.22),
           (2.16, yw, 0.31), (2.36, yw, 0.31), (2.36, yw + 0.035, 0.31), (2.16, yw + 0.035, 0.31)])
    for k, (dx, mat) in enumerate(((0.0, 1), (0.06, 2))):
        p0, p1 = Vector((2.27 + dx, yw + 0.02 + 0.012 * k, 0.30)), Vector((2.22 + dx, yw + 0.02 + 0.012 * k, 0.41))
        b.tube(p0, p1, 0.005, n=6)
        b.revolve(p1, p1 + (p1 - p0).normalized() * 0.03, [(0, 0.008), (0.5, 0.016), (1, 0.008)], n=10, mat=mat)
    h.add("Throttle", b, mats=("Interior", "Black", "LensRed"), collection=col)

    # ---- padded leather roll round the cockpit opening
    b = B()
    out = h.cockpit_outline
    pts = [Vector((x, y, P.fus_top(x, y) + 0.004)) for x, y in out]
    m = len(pts)
    for i in range(m):
        b.tube(pts[i], pts[(i + 1) % m], 0.026, n=8)
    h.add("CockpitRim", b, mats=("Leather",), collection=col, smooth=60.0)

    # ---- pilot's eye point and camera
    eye = bpy.data.objects.new(h.prefix + "Eye", None)
    eye.empty_display_size = 0.1
    col.objects.link(eye)
    eye.parent = h.root
    eye.matrix_basis = Matrix.Translation(P.to_blender(EYE)) @ Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Rotation(math.radians(84), 4, "X")
    h.world[eye.name] = eye.matrix_basis.copy()
    cam = bpy.data.objects.new(h.prefix + "Cam", bpy.data.cameras.new(h.prefix + "Cam"))
    cam.data.lens_unit = "FOV"
    cam.data.angle = math.radians(80)
    cam.data.clip_start = 0.02
    col.objects.link(cam)
    cam.parent = eye
    h.objects[eye.name] = eye
