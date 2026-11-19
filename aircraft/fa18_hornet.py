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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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
TIP_RAIL_Y = 5.94                    # wingtip LAU-7 launcher axis = station 1/9 (NATOPS)
FIN_CANT = math.radians(20.0)
FIN_TIP_Y = 1.80
FIN_TOP_Z = 2.96
STAB_SEMI_SPAN = 3.29                # 6.58 m tailplane span
STAB_ANHEDRAL = math.radians(2.0)
GROUND_Z = FIN_TOP_Z - 4.66          # overall height 4.66 m
WHEEL_TRACK = 3.11
MAIN_GEAR_X = 11.02
NOSE_GEAR_X = MAIN_GEAR_X - 5.42     # wheelbase 5.42 m
# landing-gear bays (see Hornet.cut_bays)
LAUNCH_BAR_STOW = -50.0              # deg the launch bar folds up against the strut as the gear retracts
NOSE_BAY = [(3.60, 3.95, 0.10), (3.95, 4.48, 0.18), (4.48, 4.95, 0.08), (4.95, 5.67, 0.02)]  # x0, x1, ceiling
BRACE_SLOT = (5.66, 6.42, 0.025, 0.15, -0.22)  # x0, x1, |y| inner, |y| outer, ceiling of the drag-brace slots
MAIN_BAY_X = (MAIN_GEAR_X - 1.02, MAIN_GEAR_X + 0.98)   # main bay openings, 10.00 .. 12.00 m
MAIN_BAY_Y_IN = 0.72                 # inboard edge of each main bay opening on the underside
MAIN_BAY_HINGE_Z = 0.12              # main bay door hinge line, up the nacelle side

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


def door_paint(b, n_outer, n_rings):
    """Material per face of a door lofted from rings of (outer skin points +
    inner points reversed): the outer skin and the edges take the airframe
    paint (index 0), the inside the gear-bay white (index 1)."""
    nring = 2 * n_outer
    for k in range(n_rings - 1):
        for j in range(nring):
            b.mats[k * nring + j] = 1 if n_outer <= j <= 2 * n_outer - 2 else 0


def to_blender(p):
    """Design (x aft, y starboard, z up) -> Blender (X port, Y aft, Z up)."""
    return Vector((-p[1], p[0] - X_REF, p[2] - Z_REF))


# ----------------------------------------------------------------------------
# Mesh assembly
# ----------------------------------------------------------------------------
class Builder:
    """Collects closed shells (in design coordinates) for one object.

    Faces may carry UVs: `uvs[i]` is None (auto-unwrapped later), a single
    (u, v) pair (whole face samples one texel, e.g. a colour swatch), or one
    (u, v) per corner.  `paint(uv)` applies a pair to every face added since
    `mark()`.
    """

    def __init__(self):
        self.verts = []
        self.faces = []
        self.mats = []
        self.uvs = []

    def mark(self):
        return len(self.faces)

    def paint(self, since, uv):
        """uv: a (u, v) pair, or a callable(face points) -> per-corner UVs."""
        self.uvs.extend([None] * (len(self.faces) - len(self.uvs)))
        for i in range(since, len(self.faces)):
            self.uvs[i] = uv([self.verts[j] for j in self.faces[i]]) if callable(uv) else uv

    def face(self, idx, mat=0, uv=None):
        """Add one face from vertex indices, with optional per-corner UVs."""
        self.uvs.extend([None] * (len(self.faces) - len(self.uvs)))
        self.faces.append(tuple(idx))
        self.mats.append(mat)
        self.uvs.append(uv([self.verts[j] for j in idx]) if callable(uv) else uv)

    def poly(self, pts, mat=0, uv=None):
        """Add one face from points."""
        self.face(self.ring(pts), mat, uv)

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

    def revolve(self, p0, p1, profile, n=12, mat=0, cap_mats=None, caps=(True, True)):
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
        if caps[0]:
            self.cap(rings[0], cm[0])
        if caps[1]:
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
    "Frame":         ((0.035, 0.036, 0.04), 0.20, 0.55, 1.0),
    "Cockpit":       ((0.05, 0.05, 0.055), 0.00, 0.70, 1.0),
    "CockpitWall":   ((0.04, 0.04, 0.045), 0.00, 0.75, 1.0),
    "Mirror":        ((0.80, 0.80, 0.80), 1.00, 0.04, 1.0),
}


def material(name):
    full = "F18_" + name
    mat = bpy.data.materials.get(full)
    if mat:
        return mat
    if name.startswith("Display_"):                 # placeholder until textured
        color, metal, rough, alpha = (0.0, 0.05, 0.0), 0.0, 0.2, 1.0
    else:
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
            # crew stations: design eye point (x, z) and instrument-panel face x
            self.crew = [dict(name="Front", eye=(5.30, 1.34), panel_x=4.50, hud=True),
                         dict(name="Rear", eye=(7.00, 1.41), panel_x=6.20, hud=False)]
            self.cockpit_x = (4.42, 7.72)      # extent of the cockpit opening
        else:
            self.canopy = Table([
                (3.22, 0.03, 0.94), (3.50, 0.24, 1.08), (3.90, 0.355, 1.26),
                (4.45, 0.425, 1.47), (5.07, 0.42, 1.61), (5.70, 0.41, 1.57),
                (6.30, 0.36, 1.47), (6.84, 0.27, 1.36), (7.15, 0.12, 1.305),
            ])
            self.bows = [4.45, 6.84]
            self.crew = [dict(name="Front", eye=(5.30, 1.34), panel_x=4.50, hud=True)]
            self.cockpit_x = (4.42, 6.05)

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
        self.col_cockpit = bpy.data.collections.new(name + " Cockpit")
        self.col.children.link(self.col_cockpit)
        self.root = bpy.data.objects.new("FA-18%s_Hornet" % self.v, None)
        self.root.empty_display_type = "PLAIN_AXES"
        self.root.empty_display_size = 1.0
        self.col.objects.link(self.root)
        self.root["variant"] = "F/A-18%s" % self.v
        self.root["seats"] = len(self.crew)
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
        uvs = b.uvs + [None] * (len(b.faces) - len(b.uvs))
        explicit = any(u is not None for u in uvs)
        if explicit:
            # set before the normal recalculation so flipped faces keep
            # their UVs attached to the right corners
            layer = mesh.uv_layers.new(name="UVMap")
            data = np.zeros((len(mesh.loops), 2))
            for poly, uv in zip(mesh.polygons, uvs):
                if uv is None:
                    continue
                s0, n = poly.loop_start, poly.loop_total
                data[s0:s0 + n] = uv if isinstance(uv[0], (int, float)) else uv[:n]
            layer.data.foreach_set("uv", data.ravel())
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
        if explicit:
            obj["uv_explicit"] = True
        if hinge:
            obj["hinge"] = "rotate about local X from rest (0); positive = " + hinge
        self.objects[name] = obj
        return obj

    # -- body -----------------------------------------------------------------
    def core_ring(self, x, n=40):
        a, zt, zb, zc, nt, nb = self.core(x)
        return superellipse(x, 0.0, a, zt, zb, zc, nt, nb, n)

    def floor_z(self, x):
        """Cockpit floor height (the rear cockpit of the B sits higher)."""
        return 0.22 if (len(self.crew) > 1 and x > 5.95) else 0.15

    def arch_halfwidth(self, x, z, grow=-0.05):
        """Half-width of the canopy arch (offset by grow) at height z, or 0 above it."""
        pts = self.canopy_arch(x, grow)
        half = pts[: len(pts) // 2 + 1]                # right sill .. top
        for (y0, z0), (y1, z1) in zip([(p[1], p[2]) for p in half], [(p[1], p[2]) for p in half[1:]]):
            if min(z0, z1) <= z <= max(z0, z1) and z1 != z0:
                return y0 + (y1 - y0) * (z - z0) / (z1 - z0)
        return 0.0 if z > half[-1][2] else half[0][1]

    def cockpit_halfwidth(self, x):
        w, _ = self.canopy(min(max(x, self.canopy.x[0]), self.canopy.x[-1]))
        return min(w - 0.016, 0.40)

    def sill_z(self, x):
        w, _ = self.canopy(min(max(x, self.canopy.x[0]), self.canopy.x[-1]))
        return self.core_top_z(x, w) - 0.03

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

    def canopy_arch(self, x, grow=0.0, n=24, sink=0.03):
        """Canopy cross-section at station x, sill to sill.

        The arch ends sit on the fuselage surface at the canopy's half-width;
        grow offsets it outward (+) or inward (-).
        """
        w, zt = self.canopy(x)
        zb = self.core_top_z(x, w + max(grow, 0.0)) - sink
        pts = []
        for i in range(n + 1):
            th = math.pi * i / n
            c, s = math.cos(th), math.sin(th)
            pts.append((x, (w + grow) * spow(c, 2 / 2.3),
                        zb + (zt + grow - zb) * spow(s, 2 / 2.3)))
        return pts

    def build_canopy(self):
        """Windscreen (fixed) and canopy (hinged at its aft end), both thin
        glass shells so the cockpit can be seen and sat in, plus frames."""
        T = 0.014                                   # transparency thickness
        x_split = self.bows[0]                      # windscreen / canopy joint
        xs = self.canopy.stations(0.1)

        def shell(x0, x1):
            b = Builder()
            sx = [x0] + [x for x in xs if x0 + 0.02 < x < x1 - 0.02] + [x1]
            rings = []
            for x in sx:
                out = self.canopy_arch(x)
                inn = self.canopy_arch(x, -T)
                rings.append(out + inn[::-1])
            b.loft(rings)
            return b

        def frame(b, x0, x1, grow_out=0.012, grow_in=-0.025):
            """Arch-shaped frame band between stations x0 and x1."""
            band = []
            for x in (x0, x1):
                band.append((b.ring(self.canopy_arch(x, grow_out)),
                             b.ring(self.canopy_arch(x, grow_in))))
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

        def sill(b, x0, x1, step=0.1):
            """Frame rails along both lower edges of a transparency."""
            sx = list(np.arange(x0, x1, step)) + [x1]
            for side in (+1, -1):
                rings = []
                for x in sx:
                    w, _ = self.canopy(x)
                    y0 = side * (w - 0.010)        # outboard of the cockpit tub wall (w - 0.016)
                    y1 = side * (w + 0.014)
                    zb = self.core_top_z(x, w) - 0.03
                    rings.append([(x, y0, zb), (x, y1, zb), (x, y1, zb + 0.06), (x, y0, zb + 0.07)])
                b.loft(rings)

        x_end = self.canopy.x[-1]
        self.add("Windscreen", shell(self.canopy.x[0], x_split - 0.03), mats=("Glass",), smooth=60.0)
        b = Builder()
        frame(b, x_split - 0.06, x_split - 0.005)
        sill(b, self.canopy.x[0] + 0.25, x_split - 0.03)
        self.add("WindscreenFrame", b, mats=("Frame",), smooth=50.0)

        # canopy: hinged near its aft end on the sill line
        xh = x_end - 0.30
        hinge = (xh, 0.0, self.core_top_z(xh, 0.0) - 0.06)
        canopy = self.add("Canopy", shell(x_split + 0.005, x_end), mats=("Glass",), smooth=60.0,
                          origin=hinge, axis=(0, 1, 0), hinge="canopy opens (front edge up)")
        b = Builder()
        frame(b, x_split + 0.005, x_split + 0.07)          # canopy front bow
        for xb in self.bows[1:]:
            frame(b, xb - 0.03, xb + 0.03)
        frame(b, x_end - 0.45, x_end - 0.02, grow_in=-0.02)  # aft canopy fairing frame
        sill(b, x_split + 0.005, x_end - 0.05)
        self.add("CanopyFrames", b, mats=("Frame",), parent=canopy, smooth=50.0)

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
            # wingtip LAU-7 launcher: station 1/9 lies 5.94 m from the centreline
            # (NATOPS), outboard of the structural tip, so the launcher sits on
            # a tip adapter and the missile hangs beneath it
            zt = self.wing_z(y_tip)
            xt = WING_APEX_X + WING_LE_TAN * y_tip
            yr = TIP_RAIL_Y
            b.revolve((xt - 0.42, side * yr, zt), (xt + 2.00, side * yr, zt),
                      [(0.0, 0.012), (0.05, 0.042), (0.12, 0.052), (0.93, 0.052), (1.0, 0.03)], n=12)
            # adapter between tip and launcher, kept between the AIM-9's canards
            # and tail fins (which straddle the launcher in their X pattern)
            ya, yb = y_tip + 0.001, yr - 0.03
            xa, xb = xt + 0.05, 11.95
            b.box([(xa, side * ya, zt - 0.02), (xb, side * ya, zt - 0.02),
                   (xb, side * yb, zt - 0.02), (xa, side * yb, zt - 0.02),
                   (xa + 0.10, side * ya, zt + 0.02), (xb - 0.05, side * ya, zt + 0.02),
                   (xb - 0.05, side * yb, zt + 0.02), (xa + 0.10, side * yb, zt + 0.02)])
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

    # -- landing gear ---------------------------------------------------------
    def wheel(self, b, centre, radius, width):
        x, y, z = centre
        h = width / 2
        b.revolve((x, y - h, z), (x, y + h, z),
                  [(0.0, radius * 0.55), (0.0, radius * 0.80), (0.22, radius),
                   (0.78, radius), (1.0, radius * 0.80), (1.0, radius * 0.55)],
                  n=20, mat=1, cap_mats=(0, 0))

    def skin_bottom(self, x, y):
        """Design z of the fuselage's lower skin at (x, y), by a ray cast up from
        below the finished fuselage mesh (None if (x, y) is outside it)."""
        if getattr(self, "_skin_tree", None) is None:
            from mathutils.bvhtree import BVHTree
            fus = self.objects[self.prefix + "Fuselage"]
            m = self.world.get(fus.name, Matrix.Identity(4))
            self._skin_tree = BVHTree.FromPolygons([m @ v.co for v in fus.data.vertices],
                                                   [list(p.vertices) for p in fus.data.polygons])
        p = to_blender((x, y, -20.0))
        hit = self._skin_tree.ray_cast(p, Vector((0, 0, 1)))
        return None if hit[0] is None else hit[0].z + Z_REF

    def skin_door(self, name, x0, x1, y_hinge, y_free, side, closes, flare=0.0, n_x=9, n_y=6):
        """A bay door modelled closed along the lower skin (outer face 3 mm proud
        of it, 8 mm thick) between y_hinge and y_free, then swung open about
        its hinge line by 90 deg plus `flare` (the open door splays outward by
        that much), so closing it by that angle (its "travel" property) brings
        it back flush."""
        xs = list(np.linspace(x0, x1, n_x))
        ys = [y_hinge + (y_free - y_hinge) * k / n_y for k in range(n_y + 1)]
        rings = []
        for x in xs:
            outer = [(x, y, self.skin_bottom(x, y) - 0.003) for y in ys]
            inner = [(x, y, z + 0.008) for x, y, z in outer]
            rings.append(outer + inner[::-1])
        A = Vector(rings[0][0])
        B = Vector(rings[-1][0])
        # positive rotation about the hinge axis swings the free edge from
        # hanging straight down to its closed place (inboard or outboard)
        inboard = abs(y_free) < abs(y_hinge)
        axis = (B - A).normalized() * (-side if inboard else side)
        travel = 90.0 + flare
        R = Matrix.Rotation(math.radians(-travel), 3, axis)
        b = Builder()
        b.loft([[tuple(A + R @ (Vector(p) - A)) for p in r] for r in rings])
        door_paint(b, len(ys), len(rings))
        door = self.add(name, b, mats=("Airframe", "Gear"), collection=self.col_gear, smooth=None,
                        origin=tuple(A), axis=tuple(axis), hinge=closes)
        door["travel"] = travel
        return door

    def tag_wheel(self, leg, centre, radius):
        """Record the wheel centre and axle (object-local) for the animation
        script, which cannot rely on material names once textures are applied."""
        inv = self.world[leg.name].inverted()
        leg["wheel_centre"] = tuple(inv @ to_blender(centre))
        leg["wheel_axle"] = tuple((inv.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized())
        leg["wheel_radius"] = radius

    def build_gear(self):
        gz = GROUND_Z
        # -- nose gear ------------------------------------------------------
        # Side view of the F/A-18B drawing: strut raked slightly forward at the
        # top, twin 22 in wheels, a drag brace from aft running down to the
        # strut, the launch bar pivoted at the front of the strut 0.27 m above
        # the axle and resting about 31 deg nose-up, and two pairs of doors
        # hanging below the bay.  The legacy Hornet's nose gear retracts forward.
        # The strut top sits 0.11 m inside the skin so the leg stays inside
        # when it lies forward in the bay.
        b = Builder()
        rn = 0.28
        ax = (NOSE_GEAR_X, 0, gz + rn)
        top = (NOSE_GEAR_X - 0.27, 0, -0.30)
        b.revolve(top, ax, [(0, 0.06), (0.55, 0.06), (0.55, 0.045), (1, 0.045)], n=10)
        b.revolve((ax[0], -0.21, ax[2]), (ax[0], 0.21, ax[2]), [(0, 0.035), (1, 0.035)], n=8)
        lb = (ax[0] - 0.24, 0, ax[2] + 0.27)                       # launch-bar pivot
        b.revolve((ax[0] - 0.05, 0, lb[2]), (lb[0] + 0.02, 0, lb[2]), [(0, 0.03), (1, 0.03)], n=8)  # yoke
        b.revolve((lb[0], -0.05, lb[2]), (lb[0], 0.05, lb[2]), [(0, 0.022), (1, 0.022)], n=8)       # pin
        for side in (+1, -1):
            self.wheel(b, (ax[0], side * 0.15, ax[2]), rn, 0.16)
        leg = self.add("NoseGear", b, mats=("Gear", "Tire"), collection=self.col_gear, smooth=45.0)
        self.tag_wheel(leg, ax, rn)

        b = Builder()
        tip = (ax[0] - 0.81, 0, ax[2] + 0.62)
        b.revolve(lb, tip, [(0, 0.03), (0.85, 0.024), (1, 0.03)], n=8)
        b.revolve((tip[0] - 0.02, -0.035, tip[2]), (tip[0] - 0.02, 0.035, tip[2]), [(0, 0.03), (1, 0.03)], n=8)
        self.add("LaunchBar", b, mats=("Gear",), collection=self.col_gear, smooth=45.0, parent=leg,
                 origin=lb, axis=(0, -1, 0), hinge="bar lowers (tip down to the deck)")

        # drag brace: an A-frame hinged at its aft (upper) end, folding up into
        # the fuselage; its two arms straddle the blade antenna under the nose
        brace_top = (NOSE_GEAR_X + 0.90, 0, -0.30)
        b = Builder()
        for s_ in (+1, -1):
            b.revolve((brace_top[0], s_ * 0.12, brace_top[2]), (NOSE_GEAR_X - 0.05, s_ * 0.03, ax[2] + 0.40),
                      [(0, 0.025), (1, 0.025)], n=8)
        self.add("NoseGearBrace", b, mats=("Gear",), collection=self.col_gear, smooth=45.0,
                 origin=brace_top, axis=(0, 1, 0), hinge="brace folds up into the bay")

        # bay doors (drawing): a forward pair over the stowed wheels, 3.60-4.37 m,
        # and an aft pair flanking the strut, 4.38-5.67 m, hinged on their outer
        # edges just outboard of the tyres (0.26 m) and closing inboard.  Open,
        # they splay outward (head-on photo) by the angle that gives the
        # drawing's hanging depths: 0.23 m forward, 0.18 m aft.
        for side, tag in ((+1, "R"), (-1, "L")):
            self.skin_door("NoseGearDoorFwd_" + tag, 3.60, 4.37, side * 0.26, side * 0.003, side,
                           "door closes (swings inboard)", flare=math.degrees(math.acos(0.23 / 0.26)))
            self.skin_door("NoseGearDoorAft_" + tag, 4.38, 5.67, side * 0.26, side * 0.003, side,
                           "door closes (swings inboard)", flare=math.degrees(math.acos(0.18 / 0.26)))

        # -- main gear --------------------------------------------------------
        # Side view of the drawing: a near-vertical post leaves the nacelle
        # ahead of the wheel, a trailing arm runs aft from its foot to the axle
        # (30 in tyre, 0.38 m radius), and a shock absorber runs diagonally from
        # the nacelle down to the arm.  Across the aircraft the legs splay
        # outboard from the nacelle bottom to the 3.11 m track (photos).  The
        # bay doors are built later (build_bay_doors), fitted to the motion.
        rm = 0.38
        yw = WHEEL_TRACK / 2
        for side, tag in ((+1, "R"), (-1, "L")):
            b = Builder()
            axle = (MAIN_GEAR_X, side * (yw - 0.17), gz + rm)
            foot = (MAIN_GEAR_X - 0.82, side * (yw - 0.20), gz + rm + 0.02)
            post_top = (MAIN_GEAR_X - 0.89, side * 0.80, -0.45)
            b.revolve(post_top, foot, [(0, 0.08), (0.55, 0.08), (0.55, 0.065), (1, 0.065)], n=12)
            b.revolve((foot[0] - 0.06, foot[1], foot[2]), axle, [(0, 0.07), (0.2, 0.06), (1, 0.05)], n=10)
            sa_top = (MAIN_GEAR_X - 0.56, side * 0.88, -0.48)
            sa_bot = (MAIN_GEAR_X - 0.40, side * (yw - 0.20), axle[2] + 0.21)
            b.revolve(sa_top, sa_bot, [(0, 0.065), (0.6, 0.065), (0.6, 0.045), (1, 0.045)], n=10)
            b.revolve(sa_bot, (sa_bot[0] + 0.01, sa_bot[1], axle[2] + 0.02), [(0, 0.04), (1, 0.04)], n=8)
            b.revolve(axle, (MAIN_GEAR_X, side * (yw + 0.02), gz + rm), [(0, 0.045), (1, 0.045)], n=8)
            self.wheel(b, (MAIN_GEAR_X, side * yw, gz + rm), rm, 0.26)
            leg = self.add("MainGear_" + tag, b, mats=("Gear", "Tire"), collection=self.col_gear, smooth=45.0)
            self.tag_wheel(leg, (MAIN_GEAR_X, side * yw, gz + rm), rm)
            inv = self.world[leg.name].inverted()
            leg["post_top"] = tuple(inv @ to_blender(post_top))
            leg["post_axis"] = tuple((inv.to_3x3() @ (to_blender(foot) - to_blender(post_top))).normalized())

    # -- landing-gear retraction and bays -----------------------------------
    def gear_kinematics(self):
        """Work out each leg's retraction on the closed skin, before the bays
        are cut, and record it on the parts (object-local), so that
        tools/setup_animations.py plays exactly the motion the bays and doors
        were made for.  Uses that script's fitting functions."""
        bpy.context.view_layer.update()
        tools = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)
        import setup_animations as SA
        SA._skin.clear()
        self.SA = SA
        pre = self.prefix
        nose, bar, brace = (self.objects[pre + n] for n in ("NoseGear", "LaunchBar", "NoseGearBrace"))
        # the launch bar folds up against the strut as the leg swings forward
        bar["stow_fold"] = LAUNCH_BAR_STOW
        bar.rotation_euler.x = math.radians(LAUNCH_BAR_STOW)
        bpy.context.view_layer.update()
        P, axis, _ = SA.gear_pivot(nose, "nose_gear")
        ang = SA.fold_into_skin(nose, P, axis, 60.0, 150.0, 0.012)
        bar.rotation_euler.x = 0.0
        bpy.context.view_layer.update()
        self.store_stow(nose, P, axis, ang)
        M = brace.matrix_world
        fit = SA.fold_into_skin(brace, M.translation.copy(), M.col[0].xyz, 0.0, 120.0, 0.008)
        brace["stow_fold"] = (fit if fit is not None else 32.0) + 1.0
        for tag in "LR":
            leg = self.objects[pre + "MainGear_" + tag]
            P0, _, _ = SA.gear_pivot(leg, "main_gear")
            W = SA.tyre_frame(leg)[0]
            P, ax1, ang, post, tw, flat, fits = SA.main_stow(leg, P0, W)
            self.store_stow(leg, P, ax1, ang, post, tw)
            leg["stow_flat_error_deg"] = round(math.degrees(math.acos(min(1.0, flat))), 1)

    def store_stow(self, leg, P, axis, ang, twist_axis=None, twist=None):
        Mi = leg.matrix_world.inverted()
        R3 = Mi.to_3x3()
        leg["stow_pivot"] = tuple(Mi @ P)
        leg["stow_axis"] = tuple((R3 @ axis).normalized())
        leg["stow_angle"] = float(ang)
        if twist_axis is not None:
            leg["stow_twist_axis"] = tuple((R3 @ twist_axis).normalized())
            leg["stow_twist"] = float(twist)

    def stow_pose(self, leg, s=1.0):
        """(pivot, rotation) in Blender world space for a leg at retraction
        progress s (0 = down, 1 = stowed); swing and twist run together."""
        M = leg.matrix_world
        P = M @ Vector(leg["stow_pivot"])
        R = Matrix.Rotation(math.radians(s * leg["stow_angle"]), 3, (M.to_3x3() @ Vector(leg["stow_axis"])).normalized())
        if "stow_twist" in leg.keys():
            R = R @ Matrix.Rotation(math.radians(s * leg["stow_twist"]), 3,
                                    (M.to_3x3() @ Vector(leg["stow_twist_axis"])).normalized())
        return P, R

    def side_contour(self, x, side, n=14):
        """Design-coordinate points on the skin at station x, from the hinge line
        up the nacelle side, round its lower outboard corner, to the main bay's
        inboard edge on the underside: rays fanned from inside the nacelle."""
        zb = self.skin_bottom(x, side * MAIN_BAY_Y_IN)        # also builds the skin tree
        tree = self._skin_tree
        c = Vector((x, side * 0.80, -0.20))

        def hit(dy, dz):
            h = tree.ray_cast(to_blender(tuple(c)), Vector((-dy, 0.0, dz)).normalized())
            return Vector((h[0].y + X_REF, -h[0].x, h[0].z + Z_REF))

        p_free = Vector((x, side * MAIN_BAY_Y_IN, zb))
        h = tree.ray_cast(to_blender((x, side * 0.80, MAIN_BAY_HINGE_Z)), Vector((-side, 0.0, 0.0)))
        p_hinge = Vector((h[0].y + X_REF, -h[0].x, h[0].z + Z_REF))
        a0 = math.atan2(p_hinge.z - c.z, (p_hinge.y - c.y) * side)
        a1 = math.atan2(p_free.z - c.z, (p_free.y - c.y) * side)
        mid = [hit(side * math.cos(a0 + (a1 - a0) * k / n), math.sin(a0 + (a1 - a0) * k / n)) for k in range(1, n)]
        return [p_hinge] + mid + [p_free], c

    def build_bay_doors(self):
        """Drag-brace doors under the nose, and two doors per main bay: a main
        door hinged on the inboard edge of the nacelle's underside, hanging
        below it when open (as drawn), and a side door hinged up the nacelle
        side over the lower outboard corner, which the leg's path crosses.
        Each opens just far enough to clear its leg all through the retraction
        and while stowed, the stores on its side's stations at rest, and the
        other door."""
        from mathutils.bvhtree import BVHTree
        x0, x1, yi, yo, _ = BRACE_SLOT
        for side, tag in ((+1, "R"), (-1, "L")):
            self.skin_door("NoseGearDoorBrace_" + tag, x0 + 0.015, x1, side * yo, side * yi, side,
                           "door closes (swings inboard)", flare=35.0, n_y=4)
        bx0, bx1 = MAIN_BAY_X
        xs = list(np.linspace(bx0, bx1, 11))
        self.main_contours = {}
        for side, tag in ((+1, "R"), (-1, "L")):
            leg = self.objects[self.prefix + "MainGear_" + tag]
            contours = [self.side_contour(x, side) for x in xs]
            self.main_contours[side] = contours
            # split where the skin turns from the underside to the side (45 deg)
            pts0, c0 = contours[len(contours) // 2]
            k = min(range(1, len(pts0) - 1), key=lambda i: abs(math.degrees(math.atan2(pts0[i].z - c0.z, (pts0[i].y - c0.y) * side)) + 45.0))
            lverts = [leg.matrix_world @ v.co for v in leg.data.vertices]
            lpolys = [list(p.vertices) for p in leg.data.polygons]
            poses = []
            for n in range(13):
                P, Rl = self.stow_pose(leg, n / 12)
                poses.append(BVHTree.FromPolygons([P + Rl @ (v - P) for v in lverts], lpolys))
            stowed = poses[-1]
            stations = (2, 3, 4) if side < 0 else (6, 7, 8)
            rest = []
            for o in bpy.data.objects:
                if o.type != "MESH" or not any("_STA%d_" % st in o.name for st in stations):
                    continue
                m = o.matrix_basis.copy()
                p_ = o.parent
                while p_ is not None:
                    m = p_.matrix_basis @ m
                    p_ = p_.parent
                rest.append(BVHTree.FromPolygons([m @ v.co for v in o.data.vertices], [list(q.vertices) for q in o.data.polygons]))
            for pyl in ("Pylon_STA%d" % st for st in stations):
                o = self.objects.get(self.prefix + pyl)
                if o is not None:
                    rest.append(BVHTree.FromPolygons([o.matrix_world @ v.co for v in o.data.vertices], [list(q.vertices) for q in o.data.polygons]))
            side_door = self.fit_door("MainGearDoorSide_" + tag, [(p[:k + 1], c) for p, c in contours], poses, stowed,
                                      rest, "door closes (swings in and down)")
            rest.append(side_door[1])
            self.fit_door("MainGearDoor_" + tag, [(p[k:][::-1], c) for p, c in contours], poses, stowed, rest,
                          "door closes (swings outboard and up)")

    def fit_door(self, name, contours, poses, stowed, rest, closes):
        """Build a bay door over the given skin contours (each list starts at
        the hinge), opened by the smallest angle that keeps it clear of the leg
        (all poses open, and stowed while it swings), the rest-pose obstacles
        and the airframe.  Returns (door, BVH of the door as built)."""
        from mathutils.bvhtree import BVHTree
        T = 0.008
        rings = []
        for pts, c in contours:
            pts = list(pts)
            pts[-1] = pts[-1] + (pts[-2] - pts[-1]).normalized() * 0.006    # 6 mm seam at the free edge
            outer = [p + (p - c).normalized() * 0.003 for p in pts]
            inner = [p - (p - c).normalized() * (T - 0.003) for p in pts]
            rings.append([tuple(p) for p in outer] + [tuple(p) for p in inner[::-1]])
        A, B = Vector(rings[0][0]), Vector(rings[-1][0])
        axis = (B - A).normalized()
        free = Vector(rings[len(rings) // 2][len(contours[0][0]) - 1])
        Rt = Matrix.Rotation(math.radians(-20.0), 3, axis)
        if self.inside_fuselage(to_blender(tuple(A + Rt @ (free - A))), 0.0):
            axis = -axis                                        # "-angle" must swing it out
        nring = len(rings[0])
        faces = [[i * nring + j, i * nring + (j + 1) % nring, (i + 1) * nring + (j + 1) % nring, (i + 1) * nring + j]
                 for i in range(len(rings) - 1) for j in range(nring)]
        closed = [to_blender(p) for r in rings for p in r]
        Ab = to_blender(tuple(A))
        axb = Vector((-axis.y, axis.x, axis.z)).normalized()
        far = [i for i, p in enumerate(Vector(p) for r in rings for p in r) if (p - A).cross(axis).length > 0.08]

        def opened(t):
            Rb = Matrix.Rotation(math.radians(-t), 3, axb)
            return [Ab + Rb @ (v - Ab) for v in closed]

        def clear_of(t, trees):
            dt = BVHTree.FromPolygons(opened(t), faces)
            return not any(dt.overlap(tr) for tr in trees)

        travel = None
        for t in range(40, 181, 5):
            ov = opened(t)
            if any(self.inside_fuselage(ov[i]) for i in far):
                continue
            if not clear_of(t, poses + rest):
                continue
            if not all(clear_of(a, [stowed]) for a in range(5, t + 1, 5)):
                continue
            travel = t + 5
            break
        if travel is None:
            travel = 90.0
            print("WARNING: no clear opening angle for " + name)
        R = Matrix.Rotation(math.radians(-travel), 3, axis)
        b = Builder()
        b.loft([[tuple(A + R @ (Vector(p) - A)) for p in r] for r in rings])
        door_paint(b, len(contours[0][0]), len(rings))
        door = self.add(name, b, mats=("Airframe", "Gear"), collection=self.col_gear, smooth=None,
                        origin=tuple(A), axis=tuple(axis), hinge=closes)
        door["travel"] = float(travel)
        return door, BVHTree.FromPolygons(opened(travel), faces)

    def inside_fuselage(self, pb, margin=0.0):
        """Is Blender-space point pb inside the (uncut) fuselage, by vertical rays?"""
        tree = self._skin_tree
        lo = tree.ray_cast(Vector((pb.x, pb.y, -50.0)), Vector((0, 0, 1)))
        hi = tree.ray_cast(Vector((pb.x, pb.y, 50.0)), Vector((0, 0, -1)))
        return lo[0] is not None and hi[0] is not None and lo[0].z + margin < pb.z < hi[0].z - margin

    def cut_bays(self):
        """Cut the wheel wells: the nose bay under its two pairs of doors (its
        ceiling stepped under the cockpit floor, stick and seat), the drag-brace
        slots, and a main bay per side: the skin under the curved door, plus a
        well inside the nacelle that holds the stowed leg.  The well walls take
        the gear-bay paint (material "Gear")."""
        fus = self.objects[self.prefix + "Fuselage"]
        b = Builder()
        rings = []
        for x0, x1, top in NOSE_BAY:
            for x in (x0 + 0.0005, x1 - 0.0005):
                rings.append([(x, -0.26, -0.80), (x, 0.26, -0.80), (x, 0.26, top), (x, -0.26, top)])
        b.loft(rings)
        x0, x1, yi, yo, top = BRACE_SLOT
        for s_ in (1, -1):
            ya, yb = s_ * yi, s_ * yo
            b.box([(x0, ya, -0.80), (x1, ya, -0.80), (x1, yb, -0.80), (x0, yb, -0.80),
                   (x0, ya, top), (x1, ya, top), (x1, yb, top), (x0, yb, top)])
            zi = max(self.skin_bottom(x, y) for x in (x1, NOSE_GEAR_X + 1.0) for y in (ya, yb)) + 0.02
            b.box([(x1 - 0.02, ya, zi), (NOSE_GEAR_X + 1.0, ya, zi), (NOSE_GEAR_X + 1.0, yb, zi), (x1 - 0.02, yb, zi),
                   (x1 - 0.02, ya, top), (NOSE_GEAR_X + 1.0, ya, top), (NOSE_GEAR_X + 1.0, yb, top), (x1 - 0.02, yb, top)])
        for side in (1, -1):
            # skin under the door: the door contour pushed 6 cm out and 5 cm in
            band = []
            for pts, c in self.main_contours[side]:
                out = [p + (p - c).normalized() * 0.06 for p in pts]
                inn = [p - (p - c).normalized() * 0.05 for p in pts]
                band.append([tuple(p) for p in out] + [tuple(p) for p in inn[::-1]])
            b.loft(band)
            # the well: a height field inside the nacelle over the stowed leg
            self.well(b, side)
        mesh = bpy.data.meshes.new("bay_cutter")
        inv = self.world[fus.name].inverted()
        mesh.from_pydata([tuple(inv @ to_blender(p)) for p in b.verts], [], b.faces)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(material("Gear"))
        cutter = bpy.data.objects.new("bay_cutter", mesh)
        bpy.context.scene.collection.objects.link(cutter)
        cutter.matrix_world = fus.matrix_world.copy()
        if material("Gear").name not in [m.name for m in fus.data.materials]:
            fus.data.materials.append(material("Gear"))
        mod = fus.modifiers.new("bays", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.use_self = True
        mod.material_mode = "TRANSFER"
        mod.object = cutter
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        new = bpy.data.meshes.new_from_object(fus.evaluated_get(dg))
        fus.modifiers.remove(mod)
        old = fus.data
        fus.data = new
        new.name = old.name
        bpy.data.meshes.remove(old)
        bpy.data.objects.remove(cutter)
        bpy.data.meshes.remove(mesh)
        self._skin_tree = None

    def well(self, b, side):
        """Height-field volume inside the nacelle: over each (x, y) node between
        the bay's ends and 0.12 m from the centreline out to the side, from 6 mm
        above the lower skin up to 0.40 m (under the buried wing root) or 4 cm
        under the upper skin.  Fully inside the uncut fuselage, so it only opens
        to the outside through the cut under the door."""
        bx0, bx1 = MAIN_BAY_X
        xs = list(np.linspace(bx0, bx1, 41))
        ys = [0.12 + 0.03 * k for k in range(44)]
        node = {}
        for i, x in enumerate(xs):
            for j, y in enumerate(ys):
                pb = to_blender((x, side * y, 0.0))
                lo = self._skin_tree.ray_cast(Vector((pb.x, pb.y, -50.0)), Vector((0, 0, 1)))
                hi = self._skin_tree.ray_cast(Vector((pb.x, pb.y, 50.0)), Vector((0, 0, -1)))
                if lo[0] is None or hi[0] is None:
                    continue
                zb = lo[0].z + Z_REF + 0.006
                zt = min(0.40, hi[0].z + Z_REF - 0.04)
                if zt > zb + 0.05:
                    node[i, j] = (zb, zt)
        idx = {}
        def v(i, j, top):
            k = (i, j, top)
            if k not in idx:
                zb, zt = node[i, j]
                idx[k] = len(b.verts)
                b.verts.append((xs[i], side * ys[j], zt if top else zb))
            return idx[k]
        cells = {(i, j) for i in range(len(xs) - 1) for j in range(len(ys) - 1)
                 if all((i + a, j + c) in node for a in (0, 1) for c in (0, 1))}
        for (i, j) in cells:
            b.faces.append((v(i, j, 1), v(i + 1, j, 1), v(i + 1, j + 1, 1), v(i, j + 1, 1)))
            b.mats.append(0)
            b.faces.append((v(i, j, 0), v(i, j + 1, 0), v(i + 1, j + 1, 0), v(i + 1, j, 0)))
            b.mats.append(0)
            for (p0, p1, nb) in (((0, 0), (1, 0), (0, -1)), ((1, 0), (1, 1), (1, 0)),
                                 ((1, 1), (0, 1), (0, 1)), ((0, 1), (0, 0), (-1, 0))):
                if (i + nb[0], j + nb[1]) in cells:
                    continue
                a0, a1 = (i + p0[0], j + p0[1]), (i + p1[0], j + p1[1])
                b.faces.append((v(*a0, 1), v(*a0, 0), v(*a1, 0), v(*a1, 1)))
                b.mats.append(0)

    def build(self):
        self.setup_collections()
        self.build_fuselage()
        self.build_canopy()
        import fa18_cockpit
        fa18_cockpit.Cockpit(self).build(self.objects[self.prefix + "Fuselage"],
                                          self.objects[self.prefix + "Canopy"])
        self.build_nozzles()
        self.build_wings()
        self.build_tail()
        self.build_details()
        self.build_gear()
        import fa18_stores
        self.stores = fa18_stores.build_all(self, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                "textures"))
        self.gear_kinematics()
        self.build_bay_doors()
        self.cut_bays()
        self.root["length_m"] = LENGTH
        self.root["span_m"] = 2 * SEMI_SPAN
        self.root["ground_z"] = GROUND_Z - Z_REF
        return self.root


# ----------------------------------------------------------------------------
# Entry points
# ----------------------------------------------------------------------------
def build(variant, uv=True):
    h = Hornet(variant)
    h.build()
    if uv:
        unwrap(h)
    return h


def unwrap(h):
    """Smart-UV each texture group (fa18_materials.GROUPS) into its own 0..1
    space; anything else that has no explicit UVs shares one more space."""
    import fa18_materials as M
    root = h.root
    meshes = [o for o in root.children_recursive if o.type == "MESH" and not o.get("uv_explicit")
              and not o.data.get("uv_explicit")]
    sets = []
    taken = set()
    for g in M.GROUPS:
        objs = [o for o in M.group_objects(h, g) if o in meshes]
        taken.update(objs)
        sets.append(objs)
    sets.append([o for o in meshes if o not in taken])
    view_layer = bpy.context.view_layer
    state = M._show_all(meshes)
    for objs in sets:
        if not objs:
            continue
        for o in view_layer.objects:
            o.select_set(False)
        for o in objs:
            o.select_set(True)
        view_layer.objects.active = objs[0]
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004)
        # repack tighter (islands rotated freely, concave shapes nested): about
        # 1.5-2x the texture resolution of smart_project's own packing
        try:
            bpy.ops.uv.pack_islands(rotate=True, rotate_method="ANY", scale=True, margin_method="ADD",
                                    margin=0.0015, shape_method="CONCAVE")
        except TypeError:
            bpy.ops.uv.pack_islands(rotate=True, margin=0.0015)
        bpy.ops.object.mode_set(mode="OBJECT")
        for o in objs:
            o.select_set(False)
    M._restore(state)


def texture(h, args=None):
    """Apply cockpit and exterior textures from ./textures (baking first if asked)."""
    import json
    import fa18_materials as M
    tex = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textures")
    if os.path.exists(os.path.join(tex, "cockpit_basecolor.png")):
        M.apply_cockpit(tex)
    if args is not None and args.bake is not None:
        refs = json.load(open(args.refs)) if args.refs else None
        M.bake_exterior(h, tex, refs, samples=args.samples, groups=args.bake or None)
    missing = M.apply_exterior(h, tex)
    if missing:
        print("no baked textures for:", ", ".join(missing))


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
    ap.add_argument("--bake", nargs="*", default=None, metavar="GROUP",
                    help="bake exterior textures (all groups, or the ones named)")
    ap.add_argument("--refs", default=None, help="refs.json from tools/prepare_reference_lines.py")
    ap.add_argument("--samples", type=int, default=12)
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    for v in (("A", "B") if args.variant == "both" else (args.variant,)):
        _reset_scene()
        h = build(v, uv=not args.no_uv)
        texture(h, args)
        path = os.path.join(args.out, "FA-18%s_Hornet.blend" % v)
        if os.path.exists(path):
            os.remove(path)          # regenerate cleanly, no .blend1 backup
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        print("saved", path)
        import fa18_stores
        fa18_stores.manifest(h, h.stores[2], os.path.join(args.out, "FA-18%s_stations.json" % v))
        if args.glb:
            glb = os.path.join(args.out, "FA-18%s_Hornet.glb" % v)
            # visible objects only: clean airframe, gear down, probe stowed.
            # Unhide the Stores / Optional collections first to include them.
            bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_apply=True,
                                      use_visible=True, export_extras=True, export_cameras=True)
            print("saved", glb)
            if v == "A":
                lib_glb = os.path.join(args.out, "FA-18_Stores.glb")
                fa18_stores.export_library_glb(lib_glb)
                print("saved", lib_glb)


if __name__ == "__main__":
    if "--" in sys.argv:
        main(sys.argv[sys.argv.index("--") + 1:])
    elif bpy.app.background:
        main([])
    else:
        texture(build(VARIANT))
