"""
McDonnell Douglas F/A-18A (single-seat) and F/A-18B (two-seat) legacy Hornet
-- procedural Blender model generator.

Run headless (writes one .blend per variant next to this script):

    blender --background --python fa18_hornet.py -- --variant both

or open it in Blender's Text Editor, set VARIANT below and press Run Script
(the aircraft is added to the current scene).

Options after the "--":
    --variant A|B|both     which airframe to build        (default: both)
    --out DIR              where to save .blend files     (default: script dir)
    --glb                  also export a .glb per variant
    --no-uv                skip the automatic Smart UV unwrap

Conventions
    * Units are metres, real-world scale.
    * Nose points along -Y, +Z is up, port wing is +X (Blender "front" view
      looks at the nose).
    * Everything hangs off one Empty per aircraft.  Its origin is on the
      centreline at 25 % of the mean aerodynamic chord.
    * Moving parts are separate objects, each under a "<name>_Hinge" empty
      that sits on the hinge line.  The part rests at zero rotation and a
      rotation about its local X axis deflects it; the sign is stored in
      its "hinge" custom property (exported to glTF as extras):
        flaps, ailerons, stabilators: + = trailing edge down
        leading-edge flaps: + = leading edge down
        rudders: + = trailing edge to starboard
        outer wing panels: + = fold up (90 deg folded)
        speed brake: + = open; arresting hook: + = down
      Outer leading-edge flaps and ailerons ride on the outer wing panels.
    * Collections: landing gear; "Optional" (refuelling probe, extended,
      hidden); "Stores" (AIM-9 wingtip / AIM-7 fuselage loadout, hidden).

Geometry is laid out in "design" coordinates: x aft from the nose tip,
y to starboard, z up from the nose-tip waterline.

Dimensional anchors
    From the reference sheet and published specifications:
        overall length 17.07 m (56 ft), span 11.43 m (37 ft 6 in),
        height 4.66 m (15 ft 3.5 in), wing area 37.16 m2 (400 ft2),
        wing section 5 % thick at the root and 3.5 % at the tip
        (NACA 65A005 / 65A003.5 mod), tailplane span 6.58 m,
        wheel track 3.11 m, wheelbase 5.42 m.
    Used, then checked against the drawings:
        taper 0.35 with 20 deg quarter-chord sweep (gives 26.6 deg at the
        leading edge, against the 26.7 deg usually quoted; the planform
        overlays the top views), fold line at 4.19 m (8.38 m folded width;
        the drawing's fold line measures 4.12 m), fins canted 20 deg,
        wing anhedral 3 deg and tailplane anhedral 2 deg (front views).
Everything else (stations, cross-sections, canopy lines, gear and store
positions) was scaled off the general-arrangement drawings of the F/A-18A
and F/A-18B.  Nothing here comes from the F/A-18E/F Super Hornet.
"""

import math
import os
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

VARIANT = "A"            # used when run from Blender's Text Editor

# ----------------------------------------------------------------------------
# Published / derived dimensions
# ----------------------------------------------------------------------------
LENGTH = 17.07
SEMI_SPAN = 5.715                    # 11.43 m span
WING_AREA = 37.16
TAPER = 0.35
C_ROOT = 2 * WING_AREA / (2 * SEMI_SPAN * (1 + TAPER))   # centreline chord, 4.82 m
C_TIP = C_ROOT * TAPER                                    # 1.69 m
SWEEP_QC = math.radians(20.0)        # quarter-chord sweep
WING_LE_TAN = math.tan(SWEEP_QC) + (C_ROOT - C_TIP) / 4 / SEMI_SPAN   # LE sweep 26.6 deg
WING_APEX_X = 7.90                   # wing leading edge projected to the centreline
WING_Z_AT_ROOT = 0.50                # wing mid-plane at y = 1.42 (LEX junction), from the front views
WING_ANHEDRAL = math.radians(3.0)
FOLD_Y = 4.19                        # half the 8.38 m folded width
FIN_CANT = math.radians(20.0)
FIN_TIP_Y = 1.80
FIN_TOP_Z = 2.96
STAB_SEMI_SPAN = 3.29                # 6.58 m tailplane span
STAB_ANHEDRAL = math.radians(2.0)
GROUND_Z = FIN_TOP_Z - 4.66          # overall height 4.66 m
WHEEL_TRACK = 3.11
MAIN_GEAR_X = 11.02
NOSE_GEAR_X = MAIN_GEAR_X - 5.42     # wheelbase 5.42 m

MAC = 2 / 3 * C_ROOT * (1 + TAPER + TAPER ** 2) / (1 + TAPER)
Y_MAC = SEMI_SPAN / 3 * (1 + 2 * TAPER) / (1 + TAPER)
X_REF = WING_APEX_X + WING_LE_TAN * Y_MAC + 0.25 * MAC    # model origin (25 % MAC)
Z_REF = 0.25

GAP = 0.012                          # visible joint width between moving parts


# ----------------------------------------------------------------------------
# Small maths helpers
# ----------------------------------------------------------------------------
def pchip(xk, yk, x):
    """Shape-preserving cubic interpolation (no overshoot between keys)."""
    xk = np.asarray(xk, float)
    yk = np.asarray(yk, float)
    x = np.atleast_1d(np.asarray(x, float))
    h = np.diff(xk)
    delta = np.diff(yk) / h
    d = np.zeros_like(yk)
    for i in range(1, len(xk) - 1):
        if delta[i - 1] * delta[i] > 0:
            w1 = 2 * h[i] + h[i - 1]
            w2 = h[i] + 2 * h[i - 1]
            d[i] = (w1 + w2) / (w1 / delta[i - 1] + w2 / delta[i])
    d[0], d[-1] = delta[0], delta[-1]
    i = np.clip(np.searchsorted(xk, x) - 1, 0, len(xk) - 2)
    t = np.clip((x - xk[i]) / h[i], 0.0, 1.0)
    h00 = 2 * t ** 3 - 3 * t ** 2 + 1
    h10 = t ** 3 - 2 * t ** 2 + t
    h01 = -2 * t ** 3 + 3 * t ** 2
    h11 = t ** 3 - t ** 2
    return h00 * yk[i] + h10 * h[i] * d[i] + h01 * yk[i + 1] + h11 * h[i] * d[i + 1]


class Table:
    """Keyed stations -> smooth per-column lookup."""

    def __init__(self, rows):
        a = np.array(rows, float)
        self.x = a[:, 0]
        self.cols = a[:, 1:].T

    def __call__(self, x):
        return [float(pchip(self.x, c, x)[0]) for c in self.cols]

    def stations(self, step, x0=None, x1=None):
        x0 = self.x[0] if x0 is None else x0
        x1 = self.x[-1] if x1 is None else x1
        xs = set(np.round(np.arange(x0, x1 + 1e-6, step), 4))
        xs |= {round(float(v), 4) for v in self.x if x0 <= v <= x1}
        xs |= {round(x0, 4), round(x1, 4)}
        return sorted(xs)


def spow(v, e):
    return math.copysign(abs(v) ** e, v)


def superellipse(x, yc, a, zt, zb, zc, nt, nb, n=40):
    """Closed section in the plane x = const, starting at the top centre."""
    pts = []
    for k in range(n):
        th = math.pi / 2 - 2 * math.pi * k / n
        c, s = math.cos(th), math.sin(th)
        e = nt if s >= 0 else nb
        b = (zt - zc) if s >= 0 else (zc - zb)
        pts.append((x, yc + a * spow(c, 2 / e), zc + b * spow(s, 2 / e)))
    return pts


def naca_half_thickness(f):
    """NACA symmetric thickness form, per unit chord and unit thickness ratio."""
    f = min(max(f, 0.0), 1.0)
    return 5 * (0.2969 * math.sqrt(f) - 0.1260 * f - 0.3516 * f ** 2
                + 0.2843 * f ** 3 - 0.1036 * f ** 4)


def lerp(a, b, t):
    return a + (b - a) * t


def to_blender(p):
    """Design (x aft, y starboard, z up) -> Blender (X port, Y aft, Z up)."""
    return Vector((-p[1], p[0] - X_REF, p[2] - Z_REF))


# ----------------------------------------------------------------------------
# Mesh assembly
# ----------------------------------------------------------------------------
class Builder:
    """Collects closed shells (in design coordinates) for one object."""

    def __init__(self):
        self.verts = []
        self.faces = []
        self.mats = []

    def ring(self, pts):
        i0 = len(self.verts)
        self.verts.extend(tuple(p) for p in pts)
        return list(range(i0, i0 + len(pts)))

    def bridge(self, r0, r1, mat=0):
        n = len(r0)
        for i in range(n):
            j = (i + 1) % n
            self.faces.append((r0[i], r0[j], r1[j], r1[i]))
            self.mats.append(mat)

    def cap(self, r, mat=0):
        self.faces.append(tuple(r))
        self.mats.append(mat)

    def fan(self, r, apex, mat=0):
        a = len(self.verts)
        self.verts.append(tuple(apex))
        n = len(r)
        for i in range(n):
            self.faces.append((r[i], r[(i + 1) % n], a))
            self.mats.append(mat)

    def loft(self, rings, mat=0, cap_start=True, cap_end=True):
        idx = [self.ring(r) for r in rings]
        for a, b in zip(idx, idx[1:]):
            self.bridge(a, b, mat)
        if cap_start:
            self.cap(idx[0], mat)
        if cap_end:
            self.cap(idx[-1], mat)
        return idx

    def box(self, corners, mat=0):
        """corners: 4 points of one face followed by the 4 of the opposite face."""
        r0 = self.ring(corners[:4])
        r1 = self.ring(corners[4:])
        self.bridge(r0, r1, mat)
        self.cap(r0, mat)
        self.cap(r1, mat)

    def revolve(self, p0, p1, profile, n=12, mat=0, cap_mats=None):
        """Body of revolution about the axis p0->p1.

        profile: list of (t, radius) with t the fraction along the axis.
        """
        p0, p1 = Vector(p0), Vector(p1)
        ax = (p1 - p0)
        length = ax.length
        ax.normalize()
        ref = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
        u = ax.cross(ref).normalized()
        v = ax.cross(u)
        rings = []
        for t, r in profile:
            c = p0 + ax * (t * length)
            rings.append(self.ring([c + (u * math.cos(2 * math.pi * k / n)
                                         + v * math.sin(2 * math.pi * k / n)) * r
                                    for k in range(n)]))
        for a, b in zip(rings, rings[1:]):
            self.bridge(a, b, mat)
        cm = cap_mats or (mat, mat)
        self.cap(rings[0], cm[0])
        self.cap(rings[-1], cm[1])


class Foil:
    """Straight-tapered lifting surface with a thin symmetric section.

    The chord always runs along +x; `normal` is the thickness direction.
    s is the span fraction between the two defining stations (it may run
    slightly below 0 to bury a root in the fuselage); f is chord fraction.
    """

    def __init__(self, le0, c0, t0, le1, c1, t1, normal=(0, 0, 1)):
        self.le0, self.le1 = Vector(le0), Vector(le1)
        self.c0, self.c1, self.t0, self.t1 = c0, c1, t0, t1
        self.n = Vector(normal).normalized()

    def le(self, s):
        return self.le0.lerp(self.le1, s)

    def chord(self, s):
        return lerp(self.c0, self.c1, s)

    def frac(self, s, x):
        return (x - self.le(s).x) / self.chord(s)

    def point(self, s, f, side=0):
        c = self.chord(s)
        h = naca_half_thickness(f) * lerp(self.t0, self.t1, s) * c * side
        return self.le(s) + Vector((f * c, 0, 0)) + self.n * h

    def shell(self, b, s0, s1, fa=0.0, fb=1.0, nch=7, mat=0):
        """Closed piece between span fractions s0..s1 and chord bounds fa..fb.

        fa / fb may be numbers or callables of s (for straight hinge lines).
        """
        rings = []
        for s in (s0, s1):
            f0 = fa(s) if callable(fa) else fa
            f1 = fb(s) if callable(fb) else fb
            lead = f0 <= 1e-6
            trail = f1 >= 1 - 1e-6
            us = [(k / nch) ** (1.7 if lead else 1.0) for k in range(nch + 1)]
            fs = [f0 + (f1 - f0) * u for u in us]
            up = [self.point(s, f, +1) for f in fs]
            lo = [self.point(s, f, -1) for f in reversed(fs)]
            if trail:
                lo = lo[1:]
            if lead:
                lo = lo[:-1]
            rings.append(b.ring(up + lo))
        b.bridge(rings[0], rings[1], mat)
        b.cap(rings[0], mat)
        b.cap(rings[1], mat)


# ----------------------------------------------------------------------------
# Materials
# ----------------------------------------------------------------------------
MATERIALS = {
    #  name            base colour (linear RGB)   metal  rough  alpha
    "Airframe":      ((0.33, 0.36, 0.39), 0.10, 0.55, 1.0),
    "Glass":         ((0.02, 0.035, 0.05), 0.00, 0.05, 0.55),
    "Dark":          ((0.015, 0.015, 0.018), 0.00, 0.80, 1.0),
    "Nozzle":        ((0.10, 0.095, 0.09), 0.85, 0.45, 1.0),
    "Gear":          ((0.75, 0.75, 0.74), 0.10, 0.45, 1.0),
    "Tire":          ((0.02, 0.02, 0.02), 0.00, 0.90, 1.0),
    "Seat":          ((0.05, 0.055, 0.05), 0.00, 0.80, 1.0),
}


def material(name):
    full = "F18_" + name
    mat = bpy.data.materials.get(full)
    if mat:
        return mat
    color, metal, rough, alpha = MATERIALS[name]
    mat = bpy.data.materials.new(full)
    mat.diffuse_color = (*color, alpha)
    mat.metallic = metal
    mat.roughness = rough
    if mat.node_tree is None:
        mat.use_nodes = True
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Alpha"].default_value = alpha
    if alpha < 1.0:
        for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED")):
            try:
                setattr(mat, attr, val)
            except (AttributeError, TypeError):
                pass
    return mat


# ----------------------------------------------------------------------------
# Aircraft
# ----------------------------------------------------------------------------
class Hornet:
    def __init__(self, variant):
        self.v = variant.upper()
        assert self.v in ("A", "B")
        self.prefix = "F18%s_" % self.v
        two_seat = self.v == "B"

        # ---- fuselage core: x, half-width, z top, z bottom, z of max width,
        #      top exponent, bottom exponent.  Only the cockpit/spine top line
        #      differs between the variants.
        top = {  # x: (A, B)
            3.20: (0.92, 0.90), 4.40: (1.04, 1.02), 5.60: (1.16, 1.14),
            6.85: (1.28, 1.25), 8.00: (1.30, 1.36), 8.60: (1.30, 1.34),
            9.50: (1.27, 1.28),
        }
        k = 1 if two_seat else 0
        self.core = Table([
            (0.00, 0.000, 0.000, 0.000, 0.00, 2.0, 2.0),
            (0.15, 0.085, 0.095, -0.075, 0.01, 2.0, 2.0),
            (0.50, 0.200, 0.235, -0.170, 0.03, 2.0, 2.0),
            (1.00, 0.315, 0.385, -0.260, 0.06, 2.0, 2.0),
            (1.75, 0.430, 0.540, -0.320, 0.10, 2.0, 2.0),
            (2.50, 0.475, 0.720, -0.355, 0.15, 2.1, 2.2),
            (3.20, 0.500, top[3.20][k], -0.380, 0.22, 2.3, 2.4),
            (4.40, 0.550, top[4.40][k], -0.400, 0.30, 2.6, 2.6),
            (5.60, 0.580, top[5.60][k], -0.420, 0.35, 2.6, 2.6),
            (6.85, 0.580, top[6.85][k], -0.440, 0.38, 2.4, 2.6),
            (8.00, 0.540, top[8.00][k], -0.460, 0.40, 2.2, 2.6),
            (8.60, 0.550, top[8.60][k], -0.465, 0.40, 2.2, 2.6),
            (9.50, 0.600, top[9.50][k], -0.480, 0.42, 2.1, 2.6),
            (10.20, 0.650, 1.22, -0.500, 0.45, 2.1, 2.6),
            (12.00, 0.750, 1.04, -0.520, 0.45, 2.8, 2.6),
            (13.50, 0.740, 0.84, -0.500, 0.35, 3.4, 2.5),
            (14.60, 0.640, 0.69, -0.440, 0.25, 3.2, 2.4),
            (15.60, 0.450, 0.58, -0.320, 0.15, 2.6, 2.2),
            (16.00, 0.250, 0.45, -0.150, 0.12, 2.2, 2.0),
        ])

        # ---- engine nacelle (starboard): x, y centre, half-width, z top,
        #      z bottom, z of max width, exponent
        self.nacelle = Table([
            (8.20, 0.94, 0.34, 0.56, -0.46, 0.08, 2.7),
            (8.60, 0.94, 0.37, 0.60, -0.50, 0.08, 2.8),
            (9.20, 0.92, 0.41, 0.68, -0.54, 0.10, 2.9),
            (10.00, 0.88, 0.46, 0.80, -0.57, 0.12, 3.0),
            (11.00, 0.80, 0.50, 0.86, -0.57, 0.15, 2.8),
            (12.00, 0.70, 0.49, 0.86, -0.56, 0.15, 2.6),
            (12.70, 0.64, 0.47, 0.82, -0.54, 0.14, 2.5),
            (13.50, 0.57, 0.47, 0.74, -0.50, 0.12, 2.3),
            (14.50, 0.51, 0.47, 0.63, -0.45, 0.10, 2.1),
            (15.80, 0.48, 0.46, 0.54, -0.38, 0.08, 2.0),
        ])

        # ---- leading-edge extension: x, half-span, z
        self.lex = Table([
            (3.40, 0.34, 0.84), (3.80, 0.50, 0.82), (4.20, 0.62, 0.80),
            (4.80, 0.82, 0.765), (5.30, 0.98, 0.735), (6.10, 1.15, 0.69),
            (7.20, 1.31, 0.62), (8.20, 1.39, 0.54), (8.70, 1.42, 0.51),
            (9.30, 1.42, 0.50),
        ])

        # ---- canopy: x, half-width, z top
        if two_seat:
            self.canopy = Table([
                (3.18, 0.03, 0.92), (3.50, 0.25, 1.07), (3.90, 0.36, 1.26),
                (4.36, 0.42, 1.47), (5.20, 0.44, 1.72), (5.91, 0.44, 1.80),
                (7.05, 0.42, 1.68), (7.99, 0.33, 1.47), (8.40, 0.22, 1.39),
                (8.70, 0.10, 1.345),
            ])
            self.bows = [4.36, 6.00, 7.99]
            self.seats = [5.20, 7.05]
        else:
            self.canopy = Table([
                (3.22, 0.03, 0.94), (3.50, 0.24, 1.08), (3.90, 0.35, 1.26),
                (4.45, 0.41, 1.47), (5.07, 0.42, 1.61), (5.70, 0.41, 1.57),
                (6.30, 0.36, 1.47), (6.84, 0.27, 1.36), (7.15, 0.12, 1.305),
            ])
            self.bows = [4.45, 6.84]
            self.seats = [5.30]

        # ---- lifting surfaces
        z_wing = lambda y: WING_Z_AT_ROOT - (y - 1.42) * math.tan(WING_ANHEDRAL)
        self.wing_z = z_wing
        self.wing = {}
        self.fin = {}
        self.stab = {}
        for side in (+1, -1):
            self.wing[side] = Foil(
                (WING_APEX_X, 0, z_wing(0)), C_ROOT, 0.05,
                (WING_APEX_X + WING_LE_TAN * SEMI_SPAN, side * SEMI_SPAN, z_wing(SEMI_SPAN)),
                C_TIP, 0.035)
            # fin: defined at the fuselage shoulder (z = 0.66) and the tip
            dz = FIN_TOP_Z - 0.66
            y_base = FIN_TIP_Y - dz * math.tan(FIN_CANT)
            self.fin[side] = Foil(
                (11.86, side * y_base, 0.66), 14.73 - 11.86, 0.045,
                (13.95, side * FIN_TIP_Y, FIN_TOP_Z), 15.12 - 13.95, 0.035,
                normal=(0, side * math.cos(FIN_CANT), -math.sin(FIN_CANT)))
            # stabilator: defined at the fuselage side (y = 0.95) and the tip
            self.stab[side] = Foil(
                (13.67, side * 0.95, 0.15), 15.95 - 13.67, 0.045,
                (16.00, side * STAB_SEMI_SPAN,
                 0.15 - (STAB_SEMI_SPAN - 0.95) * math.tan(STAB_ANHEDRAL)),
                LENGTH - 16.00, 0.03)

        self.objects = {}
        self.world = {}

    # -- scene plumbing -------------------------------------------------------
    def setup_collections(self):
        scene = bpy.context.scene
        name = "FA-18%s Hornet" % self.v
        self.col = bpy.data.collections.new(name)
        scene.collection.children.link(self.col)
        self.col_gear = bpy.data.collections.new(name + " Landing Gear")
        self.col.children.link(self.col_gear)
        self.col_opt = bpy.data.collections.new(name + " Optional")
        self.col.children.link(self.col_opt)
        self.col_stores = bpy.data.collections.new(name + " Stores (AIM-9 / AIM-7)")
        self.col.children.link(self.col_stores)
        self.root = bpy.data.objects.new("FA-18%s_Hornet" % self.v, None)
        self.root.empty_display_type = "PLAIN_AXES"
        self.root.empty_display_size = 1.0
        self.col.objects.link(self.root)
        self.root["variant"] = "F/A-18%s" % self.v
        self.root["seats"] = len(self.seats)
        self.world[self.root.name] = Matrix.Identity(4)

    def add(self, name, b, mats=("Airframe",), origin=None, axis=None, up=(0, 0, 1),
            parent=None, collection=None, smooth=40.0, hinge=None):
        """Turn a Builder into an object.

        origin/axis (design coords) place the object's origin on a hinge and
        point its local X axis along it.
        """
        name = self.prefix + name
        if origin is None:
            frame = Matrix.Identity(4)
        else:
            o = to_blender(origin)
            if axis is None:
                frame = Matrix.Translation(o)
            else:
                ax = Vector((-axis[1], axis[0], axis[2])).normalized()
                upv = Vector((-up[1], up[0], up[2])).normalized()
                yv = upv.cross(ax).normalized()
                zv = ax.cross(yv).normalized()
                frame = Matrix((
                    (ax.x, yv.x, zv.x, o.x),
                    (ax.y, yv.y, zv.y, o.y),
                    (ax.z, yv.z, zv.z, o.z),
                    (0, 0, 0, 1)))
        inv = frame.inverted()
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([tuple(inv @ to_blender(p)) for p in b.verts], [], b.faces)
        for m in mats:
            mesh.materials.append(material(m))
        mesh.polygons.foreach_set("material_index", b.mats)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
        if smooth is not None and hasattr(mesh, "set_sharp_from_angle"):
            mesh.set_sharp_from_angle(angle=math.radians(smooth))
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        col = collection or self.col
        col.objects.link(obj)
        parent = parent or self.root
        if axis is not None:
            # A "_Hinge" empty carries the hinge position and orientation, so
            # the mesh itself rests at zero rotation and a deflection is just
            # its local X rotation (rotation_euler.x, or a glTF node rotation).
            pivot = bpy.data.objects.new(name + "_Hinge", None)
            pivot.empty_display_type = "SINGLE_ARROW"
            pivot.empty_display_size = 0.3
            col.objects.link(pivot)
            pivot.parent = parent
            pivot.matrix_parent_inverse = Matrix.Identity(4)
            pivot.matrix_basis = self.world[parent.name].inverted() @ frame
            pivot.rotation_mode = "QUATERNION"
            self.world[pivot.name] = frame
            parent = pivot
        obj.parent = parent
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_basis = self.world[parent.name].inverted() @ frame
        self.world[obj.name] = frame
        if hinge:
            obj["hinge"] = "rotate about local X from rest (0); positive = " + hinge
        self.objects[name] = obj
        return obj

    # -- body -----------------------------------------------------------------
    def core_ring(self, x, n=40):
        a, zt, zb, zc, nt, nb = self.core(x)
        return superellipse(x, 0.0, a, zt, zb, zc, nt, nb, n)

    def core_top_z(self, x, y=0.0):
        a, zt, zb, zc, nt, nb = self.core(x)
        r = min(abs(y) / a, 1.0)
        return zc + (zt - zc) * (1 - r ** nt) ** (1 / nt)

    def core_side_y(self, x, z):
        a, zt, zb, zc, nt, nb = self.core(x)
        if z >= zc:
            r, e = (z - zc) / (zt - zc), nt
        else:
            r, e = (zc - z) / (zc - zb), nb
        return a * (1 - min(r, 1.0) ** e) ** (1 / e)

    def build_fuselage(self):
        b = Builder()
        # nose-to-tail core (forward fuselage, spine, keel)
        xs = [x for x in self.core.stations(0.25) if x >= 0.05]
        xs = [0.05, 0.10] + [x for x in xs if x > 0.10]
        idx = [b.ring(self.core_ring(x)) for x in xs]
        for r0, r1 in zip(idx, idx[1:]):
            b.bridge(r0, r1)
        b.fan(idx[0], (0.0, 0.0, 0.0))
        b.cap(idx[-1])

        # engine nacelles with recessed intake ducts
        for side in (+1, -1):
            rings = []
            for x in self.nacelle.stations(0.4):
                yc, a, zt, zb, zc, n = self.nacelle(x)
                rings.append(superellipse(x, side * yc, a, zt, zb, zc, n, n, 32))
            yc, a, zt, zb, zc, n = self.nacelle(8.2)

            def duct(x, k):
                return superellipse(x, side * yc, a * k, zc + (zt - zc) * k,
                                    zc + (zb - zc) * k, zc, n, n, 32)
            inner = [b.ring(duct(9.3, 0.78)), b.ring(duct(8.2, 0.93))]
            b.cap(inner[0], 1)
            b.bridge(inner[0], inner[1], 1)
            outer = [b.ring(r) for r in rings]
            b.bridge(inner[1], outer[0], 0)
            for r0, r1 in zip(outer, outer[1:]):
                b.bridge(r0, r1)
            b.cap(outer[-1])

            # boundary-layer splitter plate between intake and fuselage
            y0, y1 = side * 0.575, side * 0.595
            b.box([(7.78, y0, 0.50), (8.45, y0, 0.50), (8.45, y0, -0.44), (8.02, y0, -0.44),
                   (7.78, y1, 0.50), (8.45, y1, 0.50), (8.45, y1, -0.44), (8.02, y1, -0.44)])

        # leading-edge extensions (one plate through the fuselage)
        rings = []
        m = 14
        for x in self.lex.stations(0.3):
            w, z = self.lex(x)
            t = 0.13 if x < 8.7 else lerp(0.13, 0.04, (x - 8.7) / 0.6)
            ys = [-w * math.cos(math.pi * i / m) for i in range(m + 1)]
            prof = lambda y: (1 - (y / w) ** 2) ** 0.75
            up = [(x, y, z + 0.6 * t * prof(y)) for y in ys]
            lo = [(x, y, z - 0.4 * t * prof(y)) for y in reversed(ys)]
            rings.append(up + lo[1:-1])
        b.loft(rings)
        self.add("Fuselage", b, mats=("Airframe", "Dark"))

    def build_canopy(self):
        def arch(x, grow=0.0, n=18, sink=0.03):
            # glass runs from sill to sill: the arch ends sit on the fuselage
            # surface at the canopy's half-width, not at the centreline height
            w, zt = self.canopy(x)
            zb = self.core_top_z(x, w + max(grow, 0.0)) - sink
            pts = []
            for i in range(n + 1):
                th = math.pi * i / n
                c, s = math.cos(th), math.sin(th)
                pts.append((x, (w + grow) * spow(c, 2 / 2.3),
                            zb + (zt + grow - zb) * spow(s, 2 / 2.3)))
            return pts

        b = Builder()
        xs = self.canopy.stations(0.2)
        b.loft([arch(x) for x in xs])
        self.add("Canopy", b, mats=("Glass",), smooth=60.0)

        # windscreen bow and canopy frames
        b = Builder()
        for xb in self.bows:
            band = []
            for x in (xb - 0.03, xb + 0.03):
                outer = arch(x, 0.012)
                inner = arch(x, -0.03)
                band.append((b.ring(outer), b.ring(inner)))
            (o0, i0), (o1, i1) = band
            n = len(o0)
            for i in range(n - 1):
                for quad in ((o0[i], o0[i + 1], o1[i + 1], o1[i]),
                             (i0[i], i0[i + 1], i1[i + 1], i1[i]),
                             (o0[i], o0[i + 1], i0[i + 1], i0[i]),
                             (o1[i], o1[i + 1], i1[i + 1], i1[i])):
                    b.faces.append(quad)
                    b.mats.append(0)
            for e in (0, n - 1):
                b.faces.append((o0[e], o1[e], i1[e], i0[e]))
                b.mats.append(0)
        self.add("CanopyFrames", b)

        # cockpit interior: a dark skin over the fuselage top inside the
        # canopy footprint, so the glazing reads as an open cockpit
        b = Builder()
        rings = []
        for x in self.canopy.stations(0.2):
            w, _ = self.canopy(x)
            ys = np.linspace(-0.97 * w, 0.97 * w, 13)
            up = [(x, y, self.core_top_z(x, y) + 0.012) for y in ys]
            lo = [(x, y, self.core_top_z(x, y) - 0.010) for y in ys[::-1]]
            rings.append(up + lo)
        b.loft(rings)
        self.add("CockpitInterior", b, mats=("Dark",), smooth=None)

        # ejection seats (one per crew station)
        b = Builder()
        for xs_ in self.seats:
            w, zt = self.canopy(xs_)
            z0 = self.core_top_z(xs_) - 0.12
            z1 = zt - 0.20
            b.box([(xs_, -0.20, z0), (xs_, 0.20, z0), (xs_, 0.16, z1), (xs_, -0.16, z1),
                   (xs_ + 0.22, -0.20, z0), (xs_ + 0.22, 0.20, z0),
                   (xs_ + 0.20, 0.16, z1), (xs_ + 0.20, -0.16, z1)])
        self.add("Seats", b, mats=("Seat",), smooth=None)

    def build_nozzles(self):
        for side, tag in ((+1, "R"), (-1, "L")):
            b = Builder()
            b.revolve((15.75, side * 0.48, 0.08), (16.65, side * 0.48, 0.12),
                      [(0.0, 0.46), (0.28, 0.455), (0.62, 0.41), (1.0, 0.30),
                       (1.0, 0.27), (0.45, 0.37)], n=24, mat=0, cap_mats=(0, 1))
            self.add("Nozzle_" + tag, b, mats=("Nozzle", "Dark"), smooth=50.0)

    # -- wings ----------------------------------------------------------------
    def build_wings(self):
        y_tip = SEMI_SPAN - 0.10          # structural tip; the launcher rail takes the rest
        for side, tag in ((+1, "R"), (-1, "L")):
            w = self.wing[side]
            s = lambda y: y / SEMI_SPAN
            y_flap = 1.20                  # flap root just clear of the nacelle side
            te_hinge_x = lambda y: 11.76 + 0.041 * (y - 1.08)
            le_hinge_x = lambda y: WING_APEX_X + WING_LE_TAN * y + 0.60 - 0.055 * y
            f_te = lambda sv: w.frac(sv, te_hinge_x(sv * SEMI_SPAN))
            f_le = lambda sv: w.frac(sv, le_hinge_x(sv * SEMI_SPAN))
            gc = lambda sv: GAP / w.chord(sv)
            f_te_aft = lambda sv: f_te(sv) + gc(sv)
            f_le_fwd = lambda sv: f_le(sv) - gc(sv)

            def hinge(fn_x, y0, y1):
                p0 = Vector((fn_x(y0), side * y0, self.wing_z(y0)))
                p1 = Vector((fn_x(y1), side * y1, self.wing_z(y1)))
                return p0, (p1 - p0) * side

            # fixed inner panel
            b = Builder()
            w.shell(b, s(0.80), s(y_flap), 0.0, 1.0)
            w.shell(b, s(y_flap), s(1.45), 0.0, f_te)
            w.shell(b, s(1.45), s(FOLD_Y - GAP / 2), f_le, f_te)
            self.add("Wing_Inner_" + tag, b)

            # inboard leading-edge flap
            b = Builder()
            w.shell(b, s(1.45 + GAP), s(FOLD_Y - GAP / 2), 0.0, f_le_fwd)
            o, ax = hinge(le_hinge_x, 1.45, FOLD_Y)
            self.add("LEFlap_Inner_" + tag, b, origin=o, axis=-ax, hinge="leading edge down")

            # trailing-edge flap
            b = Builder()
            w.shell(b, s(y_flap + GAP), s(FOLD_Y - GAP / 2), f_te_aft, 1.0, nch=5)
            o, ax = hinge(te_hinge_x, y_flap, FOLD_Y)
            self.add("Flap_" + tag, b, origin=o, axis=ax, hinge="trailing edge down")

            # outer panel, hinged at the wing fold
            b = Builder()
            w.shell(b, s(FOLD_Y + GAP / 2), s(y_tip), f_le, f_te)
            zt = self.wing_z(y_tip + 0.05)
            xt = WING_APEX_X + WING_LE_TAN * y_tip
            b.revolve((xt - 0.42, side * (y_tip + 0.05), zt), (xt + 2.00, side * (y_tip + 0.05), zt),
                      [(0.0, 0.012), (0.05, 0.04), (0.12, 0.05), (0.93, 0.05), (1.0, 0.03)], n=10)
            fold_o = (w.point(s(FOLD_Y), 0.45).x, side * FOLD_Y, self.wing_z(FOLD_Y))
            outer = self.add("Wing_Outer_" + tag, b, origin=fold_o, axis=(side, 0, 0),
                             hinge="wing folds up (90 deg = folded)")

            b = Builder()
            w.shell(b, s(FOLD_Y + GAP / 2), s(y_tip - GAP), 0.0, f_le_fwd)
            o, ax = hinge(le_hinge_x, FOLD_Y, y_tip)
            self.add("LEFlap_Outer_" + tag, b, origin=o, axis=-ax, parent=outer, hinge="leading edge down")

            b = Builder()
            w.shell(b, s(FOLD_Y + GAP / 2), s(y_tip - GAP), f_te_aft, 1.0, nch=5)
            o, ax = hinge(te_hinge_x, FOLD_Y, y_tip)
            self.add("Aileron_" + tag, b, origin=o, axis=ax, parent=outer, hinge="trailing edge down")

    # -- tail -----------------------------------------------------------------
    def build_tail(self):
        for side, tag in ((+1, "R"), (-1, "L")):
            f = self.fin[side]
            s_root = -0.09                       # bury the root in the nacelle shoulder
            r0, r1, fh = 0.10, 0.64, 0.72        # rudder span fractions / hinge chord fraction
            b = Builder()
            f.shell(b, s_root, r0, 0.0, 1.0)
            f.shell(b, r0, r1, 0.0, fh)
            f.shell(b, r1, 1.0, 0.0, 1.0)
            self.add("Fin_" + tag, b)

            b = Builder()
            gs = GAP / 2.4
            f.shell(b, r0 + gs, r1 - gs, lambda sv: fh + GAP / f.chord(sv), 1.0, nch=5)
            p0, p1 = f.point(r0, fh), f.point(r1, fh)
            self.add("Rudder_" + tag, b, origin=p0, axis=(p1 - p0),
                     up=(0, side * math.cos(FIN_CANT), -math.sin(FIN_CANT)),
                     hinge="trailing edge to starboard (nose-right yaw)")

            st = self.stab[side]
            b = Builder()
            st.shell(b, 0.0, 1.0, 0.0, 1.0, nch=9)     # root sits at the nacelle side, clear of the nozzle
            pivot = (15.00, side * 0.95, 0.15)
            self.add("Stabilator_" + tag, b, origin=pivot, axis=(0, 1, 0), hinge="trailing edge down")

        # dorsal speed brake between the fins
        b = Builder()
        rings = []
        for x in np.linspace(12.75, 14.35, 6):
            ys = np.linspace(-0.36, 0.36, 7)
            up = [(x, y, self.core_top_z(x, y) + 0.008) for y in ys]
            lo = [(x, y, self.core_top_z(x, y) - 0.03) for y in ys[::-1]]
            rings.append(up + lo)
        b.loft(rings)
        self.add("SpeedBrake", b, origin=(12.75, 0, self.core_top_z(12.75)), axis=(0, -1, 0),
                 hinge="opens (trailing edge up)")

    # -- details --------------------------------------------------------------
    def blade(self, b, x, z, height, chord_root, chord_tip, sweep, thick=0.02):
        """Blade antenna on the centreline; height < 0 points down."""
        h = height
        t = thick / 2
        x1 = x + sweep
        b.box([(x, -t, z), (x + chord_root, -t, z), (x1 + chord_tip, -t / 2, z + h), (x1, -t / 2, z + h),
               (x, t, z), (x + chord_root, t, z), (x1 + chord_tip, t / 2, z + h), (x1, t / 2, z + h)])

    def build_details(self):
        # blade antennae: two on the spine, two under the forward fuselage
        b = Builder()
        self.blade(b, 8.86, self.core_top_z(8.94) - 0.02, 0.15, 0.22, 0.09, 0.10)
        self.blade(b, 9.74, self.core_top_z(9.83) - 0.02, 0.24, 0.20, 0.12, 0.05)
        zb = lambda x: self.core(x)[2]
        self.blade(b, 2.72, zb(2.82) + 0.02, -0.21, 0.22, 0.12, 0.07)
        self.blade(b, 5.90, zb(5.98) + 0.02, -0.18, 0.20, 0.11, 0.06)
        self.add("Antennae", b, smooth=None)

        # cannon port (nose top) and gun-bay gas vents (nose sides)
        b = Builder()
        b.revolve((1.38, 0, self.core_top_z(1.38) - 0.012), (1.68, 0, self.core_top_z(1.68) - 0.012),
                  [(0.0, 0.012), (0.15, 0.034), (0.85, 0.034), (1.0, 0.012)], n=10)
        for side in (+1, -1):
            for x0, x1 in ((1.88, 2.25), (2.32, 2.70)):
                z0, z1 = 0.315, 0.345
                ya = self.core_side_y(x0, 0.33)
                yb = self.core_side_y(x1, 0.33)
                b.box([(x0, side * (ya - 0.03), z0), (x1, side * (yb - 0.03), z0),
                       (x1, side * (yb - 0.03), z1), (x0, side * (ya - 0.03), z1),
                       (x0, side * (ya + 0.004), z0), (x1, side * (yb + 0.004), z0),
                       (x1, side * (yb + 0.004), z1), (x0, side * (ya + 0.004), z1)])
        self.add("GunPort_Vents", b, mats=("Dark",), smooth=None)

        # arresting hook, stowed between the nacelles
        b = Builder()
        zh = lambda x: self.core(x)[2] - 0.045
        b.revolve((13.20, 0, zh(13.20)), (15.62, 0, zh(15.62)),
                  [(0.0, 0.05), (0.06, 0.038), (0.94, 0.038), (1.0, 0.03)], n=8)
        z = zh(15.62)
        b.box([(15.56, -0.05, z + 0.03), (15.80, -0.035, z + 0.02), (15.80, -0.035, z - 0.07), (15.56, -0.05, z - 0.05),
               (15.56, 0.05, z + 0.03), (15.80, 0.035, z + 0.02), (15.80, 0.035, z - 0.07), (15.56, 0.05, z - 0.05)])
        self.add("ArrestingHook", b, mats=("Gear",), origin=(13.20, 0, zh(13.20)), axis=(0, 1, 0),
                 hinge="hook down")

        # in-flight refuelling probe (starboard nose), modelled extended and
        # hidden by default -- un-hide it to show the probe out.
        b = Builder()
        base = (3.05, 0.30, 0.86)
        tip = (2.05, 0.60, 1.22)
        b.revolve(base, tip, [(0.0, 0.045), (0.82, 0.04), (0.86, 0.055), (0.95, 0.055), (1.0, 0.03)], n=10)
        probe = self.add("RefuelProbe_Extended", b, origin=base, collection=self.col_opt)
        probe.hide_viewport = True
        probe.hide_render = True

    # -- optional stores ------------------------------------------------------
    def missile(self, b, nose, length, dia, fin_sets, roll=45.0):
        """Body of revolution along +x plus cruciform fin sets (roll 45 = x, 0 = +).

        fin_sets: (root LE from nose, root chord, tip LE from nose, tip chord, span)
        """
        x, y, z = nose
        r = dia / 2
        b.revolve((x, y, z), (x + length, y, z),
                  [(0.0, 0.004), (0.03, r * 0.55), (0.09, r * 0.92), (0.14, r),
                   (0.985, r), (1.0, r * 0.8)], n=14, mat=0, cap_mats=(0, 2))
        for le0, c0, le1, c1, span in fin_sets:
            for k in range(4):
                a = math.radians(roll + 90 * k)
                d = Vector((0, math.cos(a), math.sin(a)))
                n = Vector((0, -math.sin(a), math.cos(a))) * 0.004
                c = Vector(nose)
                r0, r1 = c + d * (r * 0.9), c + d * (span / 2)
                p = [r0 + Vector((le0, 0, 0)), r0 + Vector((le0 + c0, 0, 0)),
                     r1 + Vector((le1 + c1, 0, 0)), r1 + Vector((le1, 0, 0))]
                b.box([tuple(q - n) for q in p] + [tuple(q + n) for q in p], mat=1)

    def build_stores(self):
        """Air-to-air loadout drawn on the reference sheets: AIM-9 on each
        wingtip launcher, AIM-7 on each nacelle-corner fuselage station.
        Hidden by default; the clean airframe is the default configuration.
        Positions are scaled off the side and front views (the front view
        shows the AIM-7s at about y = +/-1.04 m, z = -0.52 m).
        AIM-9L: 2.87 m long, 127 mm diameter.  AIM-7F: 3.66 m long, 203 mm.
        """
        for side, tag in ((+1, "R"), (-1, "L")):
            b = Builder()
            # The front views put the missile axis just outboard of and below
            # the tip rail (span over missiles is published as 12.31 m); the
            # x-pattern fins then clear the aileron.  A launcher body joins
            # missile and rail.
            yt = SEMI_SPAN + 0.165
            zt = self.wing_z(SEMI_SPAN) - 0.06
            self.missile(b, (9.62, side * yt, zt), 2.87, 0.127,
                         [(0.38, 0.20, 0.50, 0.08, 0.56), (2.40, 0.42, 2.66, 0.18, 0.64)])
            yr = SEMI_SPAN + 0.05
            zr = self.wing_z(SEMI_SPAN - 0.05) - 0.005
            b.revolve((10.30, side * yr, zr), (11.95, side * yr, zr),
                      [(0.0, 0.02), (0.06, 0.06), (0.94, 0.06), (1.0, 0.03)], n=10)
            outer = self.objects[self.prefix + "Wing_Outer_" + tag]
            self.add("AIM9_" + tag, b, mats=("Gear", "Dark", "Dark"), origin=(9.62, side * yt, zt),
                     parent=outer, collection=self.col_stores, smooth=45.0)
            b = Builder()
            # semi-recessed in the nacelle corner, fins in + so the lower fin
            # clears the main-gear leg and brace
            self.missile(b, (9.20, side * 1.06, -0.50), 3.66, 0.203,
                         [(1.45, 0.62, 1.82, 0.22, 1.02), (3.18, 0.44, 3.40, 0.22, 0.81)], roll=0.0)
            self.add("AIM7_" + tag, b, mats=("Gear", "Dark", "Dark"), origin=(9.20, side * 1.06, -0.50),
                     collection=self.col_stores, smooth=45.0)
        self.col_stores.hide_render = True
        self.col_stores.hide_viewport = True

    # -- landing gear ---------------------------------------------------------
    def wheel(self, b, centre, radius, width):
        x, y, z = centre
        h = width / 2
        b.revolve((x, y - h, z), (x, y + h, z),
                  [(0.0, radius * 0.55), (0.0, radius * 0.80), (0.22, radius),
                   (0.78, radius), (1.0, radius * 0.80), (1.0, radius * 0.55)],
                  n=20, mat=1, cap_mats=(0, 0))

    def build_gear(self):
        gz = GROUND_Z
        # nose gear: twin wheels, drag brace, launch bar, doors
        b = Builder()
        rn = 0.28
        ax = (NOSE_GEAR_X, 0, gz + rn)
        top = (NOSE_GEAR_X - 0.27, 0, -0.36)
        b.revolve(top, ax, [(0, 0.06), (0.55, 0.06), (0.55, 0.045), (1, 0.045)], n=10)
        b.revolve((ax[0], -0.21, ax[2]), (ax[0], 0.21, ax[2]), [(0, 0.035), (1, 0.035)], n=8)
        b.revolve((NOSE_GEAR_X + 0.90, 0, -0.40), (NOSE_GEAR_X - 0.05, 0, ax[2] + 0.40),
                  [(0, 0.03), (1, 0.03)], n=8)
        b.revolve((ax[0] - 0.04, 0, ax[2] + 0.06), (ax[0] - 0.60, 0, ax[2] + 0.20),
                  [(0, 0.028), (1, 0.022)], n=8)
        for side in (+1, -1):
            self.wheel(b, (ax[0], side * 0.15, ax[2]), rn, 0.16)
            y = side * 0.25
            x0, x1 = NOSE_GEAR_X - 0.95, NOSE_GEAR_X - 0.10
            b.box([(x0, y, -0.38), (x1, y, -0.40), (x1, y, -0.72), (x0, y, -0.66),
                   (x0, y + side * 0.015, -0.38), (x1, y + side * 0.015, -0.40),
                   (x1, y + side * 0.015, -0.72), (x0, y + side * 0.015, -0.66)])
        self.add("NoseGear", b, mats=("Gear", "Tire"), collection=self.col_gear, smooth=45.0)

        # main gear: per the side and front views the leg leaves the nacelle
        # bottom inboard of the AIM-7 station, splays outboard and down, and
        # the wheel trails aft on a short arm (30 in tyre, 0.38 m radius).
        rm = 0.38
        yw = WHEEL_TRACK / 2
        for side, tag in ((+1, "R"), (-1, "L")):
            b = Builder()
            top = (MAIN_GEAR_X - 0.67, side * 0.80, -0.50)
            axle = (MAIN_GEAR_X, side * (yw - 0.17), gz + rm)
            knee = (MAIN_GEAR_X - 0.47, side * (yw - 0.19), gz + rm + 0.32)
            mid = tuple((a + c) / 2 for a, c in zip(top, knee))
            b.revolve(top, knee, [(0, 0.065), (1, 0.055)], n=10)
            b.revolve(knee, axle, [(0, 0.055), (1, 0.05)], n=10)
            b.revolve((MAIN_GEAR_X - 0.97, side * 0.70, -0.52), mid, [(0, 0.03), (1, 0.03)], n=8)
            b.revolve(axle, (MAIN_GEAR_X, side * (yw + 0.02), gz + rm), [(0, 0.045), (1, 0.045)], n=8)
            self.wheel(b, (MAIN_GEAR_X, side * yw, gz + rm), rm, 0.26)
            self.add("MainGear_" + tag, b, mats=("Gear", "Tire"), collection=self.col_gear, smooth=45.0)

    def build(self):
        self.setup_collections()
        self.build_fuselage()
        self.build_canopy()
        self.build_nozzles()
        self.build_wings()
        self.build_tail()
        self.build_details()
        self.build_gear()
        self.build_stores()
        self.root["length_m"] = LENGTH
        self.root["span_m"] = 2 * SEMI_SPAN
        self.root["ground_z"] = GROUND_Z - Z_REF
        return self.root


# ----------------------------------------------------------------------------
# Entry points
# ----------------------------------------------------------------------------
def build(variant, uv=True):
    root = Hornet(variant).build()
    if uv:
        unwrap(root)
    return root


def unwrap(root):
    """Automatic UVs (Smart UV Project) so the meshes can take textures."""
    meshes = [o for o in root.children_recursive if o.type == "MESH"]
    if not meshes:
        return
    view_layer = bpy.context.view_layer
    hidden = []
    for o in meshes:                       # stores / probe are hidden: show them briefly
        if not o.visible_get():
            hidden.append((o, o.hide_viewport))
            o.hide_viewport = False
    cols = [c for c in bpy.data.collections if c.hide_viewport]
    for c in cols:
        c.hide_viewport = False
    for o in view_layer.objects:
        o.select_set(False)
    for o in meshes:
        o.select_set(True)
    view_layer.objects.active = meshes[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.003)
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in meshes:
        o.select_set(False)
    for c in cols:
        c.hide_viewport = True
    for o, h in hidden:
        o.hide_viewport = h


def _reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def main(argv):
    import argparse
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--variant", default="both", choices=["A", "B", "both"])
    ap.add_argument("--out", default=here)
    ap.add_argument("--glb", action="store_true")
    ap.add_argument("--no-uv", action="store_true", help="skip the automatic UV unwrap")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    for v in (("A", "B") if args.variant == "both" else (args.variant,)):
        _reset_scene()
        build(v, uv=not args.no_uv)
        path = os.path.join(args.out, "FA-18%s_Hornet.blend" % v)
        if os.path.exists(path):
            os.remove(path)          # regenerate cleanly, no .blend1 backup
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        print("saved", path)
        if args.glb:
            glb = os.path.join(args.out, "FA-18%s_Hornet.glb" % v)
            # visible objects only: clean airframe, gear down, probe stowed.
            # Unhide the Stores / Optional collections first to include them.
            bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_apply=True,
                                      use_visible=True, export_extras=True)
            print("saved", glb)


if __name__ == "__main__":
    if "--" in sys.argv:
        main(sys.argv[sys.argv.index("--") + 1:])
    elif bpy.app.background:
        main([])
    else:
        build(VARIANT)
