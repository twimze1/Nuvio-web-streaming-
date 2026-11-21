"""Boeing P-26A "Peashooter" for Blender: geometry generator.

    blender -b -P p26a.py -- [--out DIR] [--glb] [--bake [ext] [parts]] [--samples N]

Design coordinates (metres): x aft from the front of the propeller hub,
y to starboard, z up from the thrust line.  Blender: nose along -Y, +Z up,
port wing on +X (to_blender).

Shape sources:
  * the three-view of the Boeing 281 (the export P-26) in L'Aerophile,
    March 1935 (public domain), measured at 138.3 px/m along the fuselage
    and 136.7 px/m across the span;
  * published dimensions: span 27 ft 11.5 in (8.52 m), length 23 ft 10 in
    (7.26 m) (National Museum of the USAF), Pratt & Whitney R-1340 Wasp of
    51.75 in (1.31 m) diameter.
"""
import math
import os
import sys

import bpy
import bmesh  # noqa: E402  (must follow bpy)
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
X_REF = 1.87                      # model origin: about 28 % of the root chord
SPAN = 8.52
LENGTH = 7.26
PROP_DIAMETER = 2.74              # 9 ft; the drawing's front view gives 2.76 m
ENGINE_DIAMETER = 1.314           # R-1340, 51.75 in
DIHEDRAL = math.radians(3.0)
WING_SLOPE = -0.0467              # chord line drops aft: 2.7 deg incidence
GROUND_Z = -1.54                  # under the main wheels, fuselage level
WHEEL = (1.45, 0.78, -1.25, 0.29)     # main wheel centre x, |y|, z and tyre radius
TAILWHEEL = (6.38, 0.0, -0.355, 0.11)
FLOOR_Z = -0.12                   # cockpit floor, just above the wing centre section
COCKPIT = (2.14, 2.72, 0.29)      # opening: front, rear, half-width
GUN = dict(y=0.49, z=-0.16, muzzle=1.42, tube=0.90)   # bore line each side; gun muzzle x; blast tube mouth x
HINGE_AIL = ((1.51, 3.00), (3.62, 2.745))     # aileron hinge line (|y|, x) at each end
GAP = 0.008


def to_blender(p):
    return Vector((-p[1], p[0] - X_REF, p[2]))


# ----------------------------------------------------------------------------
# interpolation
# ----------------------------------------------------------------------------
def pchip(xk, yk, x):
    """Monotone cubic interpolation (Fritsch-Carlson)."""
    xk, yk = np.asarray(xk, float), np.asarray(yk, float)
    h = np.diff(xk)
    d = np.diff(yk) / h
    m = np.zeros_like(yk)
    m[1:-1] = np.where(d[:-1] * d[1:] > 0, 2 * d[:-1] * d[1:] / (d[:-1] + d[1:] + 1e-30), 0.0)
    m[0], m[-1] = d[0], d[-1]
    x = min(max(x, xk[0]), xk[-1])
    i = min(int(np.searchsorted(xk, x, side="right")) - 1, len(xk) - 2)
    t = (x - xk[i]) / h[i]
    return float((2 * t ** 3 - 3 * t ** 2 + 1) * yk[i] + (t ** 3 - 2 * t ** 2 + t) * h[i] * m[i]
                 + (-2 * t ** 3 + 3 * t ** 2) * yk[i + 1] + (t ** 3 - t ** 2) * h[i] * m[i + 1])


def table(rows):
    cols = list(zip(*rows))
    return lambda x: tuple(pchip(cols[0], c, x) for c in cols[1:])


def lin(xk, yk):
    return lambda x: float(np.interp(x, xk, yk))


# fuselage: x, half-width, z top, z bottom, section exponent
FUSELAGE = table([
    (0.78, 0.400, 0.40, -0.40, 2.0), (0.90, 0.455, 0.44, -0.43, 2.0), (1.28, 0.510, 0.54, -0.54, 2.1),
    (1.76, 0.545, 0.66, -0.61, 2.2), (2.22, 0.560, 0.66, -0.64, 2.3), (2.60, 0.560, 0.65, -0.65, 2.3),
    (3.20, 0.550, 0.65, -0.59, 2.3), (3.75, 0.475, 0.59, -0.54, 2.2), (4.17, 0.420, 0.54, -0.51, 2.2),
    (4.90, 0.335, 0.41, -0.45, 2.1), (5.56, 0.255, 0.30, -0.375, 2.0), (5.92, 0.200, 0.24, -0.33, 2.0),
    (6.38, 0.140, 0.20, -0.27, 2.0), (6.70, 0.035, 0.17, -0.24, 2.0),
])
# wing planform: |y|, leading edge x, trailing edge x
_WY = [0.0, 1.0, 2.0, 2.6, 3.13, 3.5, 3.86, 4.10, 4.22, 4.26]
WING_LE = lin(_WY, [1.355, 1.375, 1.395, 1.405, 1.42, 1.50, 1.65, 1.83, 1.96, 2.03])
WING_TE = lin(_WY, [3.175, 3.185, 3.195, 3.155, 3.04, 2.84, 2.60, 2.33, 2.14, 2.05])
# tailplane: |y|, leading edge x, trailing edge x; hinge line at x = 6.30
_TY = [0.0, 0.2, 0.6, 1.0, 1.25, 1.38, 1.45]
TAIL_LE = lin(_TY, [5.50, 5.57, 5.84, 6.10, 6.26, 6.37, 6.47])
TAIL_TE = lin([0.0, 0.15, 0.4, 0.8, 1.1, 1.3, 1.42, 1.45], [6.72, 6.72, 6.82, 6.84, 6.80, 6.70, 6.58, 6.50])
TAIL_HINGE = 6.30
TAIL_Z = 0.03
# fin and rudder: z, fin leading edge x / z, rudder trailing edge x; hinge at x = 6.70
FIN_LE = lin([0.15, 0.31, 0.70, 1.00, 1.10, 1.16, 1.18], [5.87, 5.96, 6.26, 6.49, 6.58, 6.655, 6.69])
RUD_TE = lin([-0.24, -0.22, -0.17, -0.02, 0.17, 0.41, 0.795, 1.03, 1.15, 1.18],
             [6.80, 6.92, 7.06, 7.21, 7.26, 7.23, 7.115, 6.97, 6.82, 6.72])
RUD_HINGE = 6.70


def fus_point(x, ang):
    """Point on the fuselage skin at station x; ang from +y through +z."""
    a, zt, zb, e = FUSELAGE(x)
    zc = 0.5 * (zt + zb) + 0.08 * (zt - zb) * 0.0
    c, s = math.cos(ang), math.sin(ang)
    y = a * math.copysign(abs(c) ** (2 / e), c)
    z = zc + (zt - zc if s >= 0 else zc - zb) * math.copysign(abs(s) ** (2 / e), s)
    return (x, y, z)


def fus_top(x, y=0.0):
    a, zt, zb, e = FUSELAGE(x)
    zc = 0.5 * (zt + zb)
    r = min(abs(y) / a, 0.999)
    return zc + (zt - zc) * (1 - r ** e) ** (1 / e)


def fus_side(x, z):
    """Half-width of the fuselage at height z."""
    a, zt, zb, e = FUSELAGE(x)
    zc = 0.5 * (zt + zb)
    r = min(abs(z - zc) / ((zt - zc) if z >= zc else (zc - zb)), 0.999)
    return a * (1 - r ** e) ** (1 / e)


# ----------------------------------------------------------------------------
# mesh builder
# ----------------------------------------------------------------------------
class Builder:
    def __init__(self):
        self.verts, self.faces, self.mats, self.uvs = [], [], [], []

    def ring(self, pts):
        i0 = len(self.verts)
        self.verts.extend(tuple(p) for p in pts)
        return list(range(i0, i0 + len(pts)))

    def face(self, idx, mat=0, uv=None):
        self.uvs.extend([None] * (len(self.faces) - len(self.uvs)))
        self.faces.append(tuple(idx))
        self.mats.append(mat)
        self.uvs.append(uv)

    def poly(self, pts, mat=0, uv=None):
        self.face(self.ring(pts), mat, uv)

    def bridge(self, r0, r1, mat=0):
        n = len(r0)
        for i in range(n):
            j = (i + 1) % n
            self.face((r0[i], r0[j], r1[j], r1[i]), mat)

    def loft(self, rings, mat=0, caps=(True, True), cap_mats=None):
        idx = [self.ring(r) for r in rings]
        for a, b in zip(idx, idx[1:]):
            self.bridge(a, b, mat)
        cm = cap_mats or (mat, mat)
        if caps[0]:
            self.face(idx[0], cm[0])
        if caps[1]:
            self.face(idx[-1], cm[1])
        return idx

    def box(self, corners, mat=0):
        self.loft([corners[:4], corners[4:]], mat)

    def block(self, x0, x1, y0, y1, z0, z1, mat=0):
        """Axis-aligned box."""
        self.box([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], mat)

    def revolve(self, p0, p1, profile, n=12, mat=0, caps=(True, True), cap_mats=None):
        """Body of revolution about p0->p1; profile = [(t along the axis, radius)]."""
        p0, p1 = Vector(p0), Vector(p1)
        ax = p1 - p0
        length = ax.length
        ax.normalize()
        ref = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
        u = ax.cross(ref).normalized()
        v = ax.cross(u)
        rings = [[tuple(p0 + ax * (t * length) + (u * math.cos(2 * math.pi * k / n) + v * math.sin(2 * math.pi * k / n)) * r)
                  for k in range(n)] for t, r in profile]
        self.loft(rings, mat, caps, cap_mats)

    def tube(self, p0, p1, r, n=6, mat=0):
        self.revolve(p0, p1, [(0, r), (1, r)], n=n, mat=mat)

    def bar(self, p0, p1, w, t, up=(0, 0, 1), mat=0):
        """Rectangular bar from p0 to p1: w across (perpendicular to `up`), t along `up`."""
        p0, p1 = Vector(p0), Vector(p1)
        ax = (p1 - p0).normalized()
        a = ax.cross(Vector(up))
        if a.length < 1e-6:
            a = ax.cross(Vector((1, 0, 0)))
        a.normalize()
        b = ax.cross(a)
        loop = lambda c: [tuple(c + a * (sa * w / 2) + b * (sb * t / 2)) for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        self.box(loop(p0) + loop(p1), mat)


# ----------------------------------------------------------------------------
# aerofoils
# ----------------------------------------------------------------------------
def naca_t(f):
    return 5 * (0.2969 * math.sqrt(max(f, 0)) - 0.1260 * f - 0.3516 * f ** 2 + 0.2843 * f ** 3 - 0.1036 * f ** 4)


def camber(f, m=0.025, p=0.4):
    return m / p ** 2 * (2 * p * f - f * f) if f < p else m / (1 - p) ** 2 * (1 - 2 * p + 2 * p * f - f * f)


def wing_z0(y):
    """Height of the wing leading edge at span station y."""
    return -0.24 + abs(y) * math.tan(DIHEDRAL)


def wing_section(y, f0=0.0, f1=1.0, n=14):
    """Closed section ring at span y between chord fractions f0..f1
    (upper surface aft to forward, then lower surface forward to aft)."""
    le, te = WING_LE(abs(y)), WING_TE(abs(y))
    c = te - le
    t = 0.10 - 0.02 * abs(y) / (SPAN / 2)
    us = [0.5 * (1 - math.cos(math.pi * k / n)) for k in range(n + 1)]
    fs = [f0 + (f1 - f0) * u for u in us]

    def pt(f, side):
        return (le + f * c, y, wing_z0(y) + WING_SLOPE * f * c + (camber(f) + side * t * naca_t(f)) * c)
    up = [pt(f, +1) for f in reversed(fs)]
    lo = [pt(f, -1) for f in fs]
    if f0 <= 1e-6:
        lo = lo[1:]
    return up + lo


def wing_surface(x, y, side):
    """z of the wing's upper (+1) or lower (-1) surface at (x, y)."""
    le, te = WING_LE(abs(y)), WING_TE(abs(y))
    c = te - le
    f = min(max((x - le) / c, 0.0), 1.0)
    t = 0.10 - 0.02 * abs(y) / (SPAN / 2)
    return wing_z0(y) + WING_SLOPE * f * c + (camber(f) + side * t * naca_t(f)) * c


def sym_ring(le, te, f0, f1, tc, place, n=8):
    """Symmetric section between chord fractions f0..f1; place(x, h) -> point,
    h the half-thickness offset."""
    c = te - le
    us = [0.5 * (1 - math.cos(math.pi * k / n)) for k in range(n + 1)]
    fs = [f0 + (f1 - f0) * u for u in us]
    up = [place(le + f * c, tc * naca_t(f) * c) for f in reversed(fs)]
    lo = [place(le + f * c, -tc * naca_t(f) * c) for f in fs]
    if f0 <= 1e-6:
        lo = lo[1:]
    return up + lo


# ----------------------------------------------------------------------------
# materials (flat; the weathered paint is p26a_materials.py)
# ----------------------------------------------------------------------------
MATERIALS = {
    #  name          base colour (linear)        metal  rough  alpha
    "Skin":        ((0.105, 0.105, 0.060), 0.0, 0.55, 1.0),     # dark olive drab 41 / neutral gray 43
    "Metal":       ((0.72, 0.72, 0.72), 1.0, 0.30, 1.0),        # polished aluminium (propeller)
    "PropBack":    ((0.02, 0.02, 0.02), 0.0, 0.6, 1.0),
    "Steel":       ((0.30, 0.30, 0.31), 1.0, 0.40, 1.0),        # wires, fittings
    "EngineGrey":  ((0.23, 0.25, 0.27), 0.3, 0.45, 1.0),        # crankcase enamel
    "Cylinder":    ((0.05, 0.05, 0.05), 0.6, 0.50, 1.0),
    "Exhaust":     ((0.16, 0.09, 0.06), 0.7, 0.75, 1.0),
    "Tyre":        ((0.02, 0.02, 0.02), 0.0, 0.85, 1.0),
    "Glass":       ((0.6, 0.7, 0.7), 0.0, 0.03, 0.25),
    "Leather":     ((0.17, 0.08, 0.04), 0.0, 0.6, 1.0),
    "Interior":    ((0.55, 0.56, 0.57), 0.9, 0.42, 1.0),        # aluminium lacquer
    "Panel":       ((0.02, 0.02, 0.02), 0.0, 0.5, 1.0),
    "Black":       ((0.015, 0.015, 0.015), 0.0, 0.5, 1.0),
    "GunMetal":    ((0.035, 0.037, 0.042), 0.85, 0.42, 1.0),    # blued steel
    "Belt":        ((0.42, 0.38, 0.27), 0.0, 0.8, 1.0),
    "LensRed":     ((0.5, 0.02, 0.02), 0.0, 0.1, 1.0),
    "LensGreen":   ((0.02, 0.4, 0.1), 0.0, 0.1, 1.0),
    "LensWhite":   ((0.8, 0.8, 0.75), 0.0, 0.1, 1.0),
}


def browning(b, x0, y, z, s):
    """Browning .30 calibre M2 aircraft gun, about 1.0 m long with a 0.61 m barrel in a
    perforated jacket.  x0 = muzzle, (y, z) = bore line, s = +1 starboard / -1 port.
    Materials: 0 gun metal, 1 steel."""
    b.revolve((x0, y, z), (x0 + 0.61, y, z), [(0, 0.0105), (0.03, 0.0145), (1, 0.0145)], n=12, mat=0)       # barrel jacket
    for k in range(8):                                                                                   # bands between the cooling holes
        xa = x0 + 0.05 + 0.068 * k
        b.revolve((xa, y, z), (xa + 0.010, y, z), [(0, 0.0158), (1, 0.0158)], n=12, mat=0)
    r0, r1 = x0 + 0.61, x0 + 0.955                                                                       # receiver
    b.block(r0, r1, y - 0.0225, y + 0.0225, z - 0.060, z + 0.038, 0)
    b.block(r0 + 0.02, r1 - 0.015, y - 0.020, y + 0.020, z + 0.038, z + 0.047, 0)                         # top cover
    b.block(r0 + 0.015, r0 + 0.04, y - 0.012, y + 0.012, z + 0.047, z + 0.058, 1)                         # cover latch
    b.block(r0 + 0.05, r0 + 0.13, y - s * 0.0225, y - s * 0.050, z - 0.004, z + 0.030, 1)                 # belt feedway, inboard
    b.block(r1, r1 + 0.012, y - 0.026, y + 0.026, z - 0.064, z + 0.042, 0)                                # back plate
    b.revolve((r1 + 0.012, y, z - 0.012), (x0 + 1.0, y, z - 0.012), [(0, 0.016), (1, 0.014)], n=10, mat=0)   # buffer
    # charging handle: the bolt handle on the inboard side and a lever up to the pilot's hand
    p0 = (r0 + 0.20, y - s * 0.0225, z + 0.012)
    p1 = (r0 + 0.20, y - s * 0.050, z + 0.012)
    b.tube(p0, p1, 0.006, n=8, mat=1)
    b.tube(p1, (r0 + 0.17, y - s * 0.056, z + 0.14), 0.005, n=8, mat=1)
    b.revolve((r0 + 0.17, y - s * 0.056, z + 0.14), (r0 + 0.163, y - s * 0.057, z + 0.175), [(0, 0.007), (0.5, 0.013), (1, 0.007)], n=10, mat=0)
    for xmnt in (r0 + 0.03, r1 - 0.07):                                                                  # mounting lugs
        b.block(xmnt, xmnt + 0.03, y - 0.028, y + 0.028, z - 0.074, z - 0.060, 1)


def material(name):
    full = "P26_" + name
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


# ----------------------------------------------------------------------------
class Peashooter:
    prefix = "P26_"
    x_ref = X_REF

    def tb(self, p):
        """Design coordinates -> Blender (other models built on this class set x_ref)."""
        return Vector((-p[1], p[0] - self.x_ref, p[2]))

    def material(self, name):
        return material(name)

    def __init__(self):
        self.objects, self.world = {}, {}
        sc = bpy.context.scene
        self.col = bpy.data.collections.new("P-26A Peashooter")
        sc.collection.children.link(self.col)
        self.col_cockpit = bpy.data.collections.new("P-26A Cockpit")
        self.col.children.link(self.col_cockpit)
        self.root = bpy.data.objects.new("P-26A_Peashooter", None)
        self.root.empty_display_size = 1.0
        self.col.objects.link(self.root)
        self.world[self.root.name] = Matrix.Identity(4)

    def add(self, name, b, mats=("Skin",), origin=None, axis=None, up=(0, 0, 1), parent=None,
            collection=None, smooth=40.0, hinge=None):
        """Builder -> object.  origin/axis put the object's origin on a hinge
        with its local X axis along it, under a "<name>_Hinge" empty, so a
        deflection is a rotation about local X from zero."""
        name = self.prefix + name
        if origin is None:
            frame = Matrix.Identity(4)
        else:
            o = self.tb(origin)
            if axis is None:
                frame = Matrix.Translation(o)
            else:
                ax = Vector((-axis[1], axis[0], axis[2])).normalized()
                upv = Vector((-up[1], up[0], up[2])).normalized()
                yv = upv.cross(ax).normalized()
                zv = ax.cross(yv).normalized()
                frame = Matrix(((ax.x, yv.x, zv.x, o.x), (ax.y, yv.y, zv.y, o.y), (ax.z, yv.z, zv.z, o.z), (0, 0, 0, 1)))
        inv = frame.inverted()
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([tuple(inv @ self.tb(p)) for p in b.verts], [], b.faces)
        for m in mats:
            mesh.materials.append(self.material(m))
        mesh.polygons.foreach_set("material_index", b.mats)
        uvs = b.uvs + [None] * (len(b.faces) - len(b.uvs))
        if any(u is not None for u in uvs):
            layer = mesh.uv_layers.new(name="UVMap")
            for poly, uv in zip(mesh.polygons, uvs):
                if uv is not None:
                    for k, li in enumerate(poly.loop_indices):
                        layer.data[li].uv = uv[k]
            mesh["uv_explicit"] = True
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
        if smooth is not None:
            mesh.set_sharp_from_angle(angle=math.radians(smooth))
        obj = bpy.data.objects.new(name, mesh)
        col = collection or self.col
        col.objects.link(obj)
        parent = parent or self.root
        if axis is not None:
            pivot = bpy.data.objects.new(name + "_Hinge", None)
            pivot.empty_display_type = "SINGLE_ARROW"
            pivot.empty_display_size = 0.25
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

    # -- fuselage ---------------------------------------------------------------
    def build_fuselage(self):
        b = Builder()
        n = 48
        xs = list(np.arange(0.78, 6.70, 0.11)) + [6.70]
        rings = [[fus_point(x, 2 * math.pi * k / n) for k in range(n)] for x in xs]
        b.loft(rings)
        fus = self.add("Fuselage", b, mats=("Skin", "Interior", "Leather"))
        self.cut_cockpit(fus)

        # headrest / turnover fairing: padded front face, tapering into the spine
        b = Builder()
        hx = [2.745, 2.80, 3.0, 3.3, 3.6, 3.85, 4.02]
        top = lin([2.745, 2.80, 3.98, 4.02], [1.00, 1.06, 0.585, 0.56])
        rings = []
        for x in hx:
            w = 0.205 * (1 - (x - 2.745) / (4.04 - 2.745)) ** 0.8 + 0.012
            zb = fus_top(x, w) - 0.03
            zt = max(top(x), zb + 0.02)
            m = 9
            rings.append([(x, w * math.copysign(abs(math.cos(math.pi * k / m)) ** (2 / 2.4), math.cos(math.pi * k / m)),
                           zb + (zt - zb) * math.sin(math.pi * k / m) ** (2 / 2.4)) for k in range(m + 1)])
        b.loft(rings, caps=(True, True), cap_mats=(1, 0))
        self.add("Headrest", b, mats=("Skin", "Leather"))

    def cut_cockpit(self, fus):
        """Hollow the cockpit: a cavity inside the skin with a flat floor, and
        the opening through the top."""
        def boolean(b, mat):
            me = bpy.data.meshes.new("cutter")
            inv = self.world[fus.name].inverted()
            me.from_pydata([tuple(inv @ to_blender(p)) for p in b.verts], [], b.faces)
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(me)
            bm.free()
            me.materials.append(material(mat))
            ob = bpy.data.objects.new("cutter", me)
            bpy.context.scene.collection.objects.link(ob)
            mod = fus.modifiers.new("cut", "BOOLEAN")
            mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", ob
            mod.material_mode = "TRANSFER"
            dg = bpy.context.evaluated_depsgraph_get()
            new = bpy.data.meshes.new_from_object(fus.evaluated_get(dg))
            fus.modifiers.remove(mod)
            old = fus.data
            fus.data = new
            new.name = old.name
            bpy.data.meshes.remove(old)
            bpy.data.objects.remove(ob)
            bpy.data.meshes.remove(me)

        b = Builder()
        n = 40
        rings = []
        for x in np.linspace(1.74, 2.98, 14):
            ring = []
            for k in range(n):
                p = fus_point(x, 2 * math.pi * k / n)
                a, zt, zb, e = FUSELAGE(x)
                zc = 0.5 * (zt + zb)
                d = math.hypot(p[1], p[2] - zc)
                s = (d - 0.028) / d                         # inset 28 mm
                ring.append((x, p[1] * s, max(zc + (p[2] - zc) * s, FLOOR_Z)))
            rings.append(ring)
        b.loft(rings)
        boolean(b, "Interior")
        x0, x1, hw = COCKPIT
        b = Builder()
        m = 28
        xc, hl = (x0 + x1) / 2, (x1 - x0) / 2
        out = [(xc + hl * math.copysign(abs(math.cos(2 * math.pi * k / m)) ** (2 / 3.2), math.cos(2 * math.pi * k / m)),
                hw * math.copysign(abs(math.sin(2 * math.pi * k / m)) ** (2 / 3.2), math.sin(2 * math.pi * k / m)))
               for k in range(m)]
        self.cockpit_outline = out
        b.loft([[(x, y, 0.30) for x, y in out], [(x, y, 1.2) for x, y in out]])
        boolean(b, "Leather")
        for s in (1, -1):                                   # a well in the floor each side for the gun breech
            b = Builder()
            b.block(1.98, 2.47, s * 0.452, s * 0.520, -0.228, -0.10)
            boolean(b, "Interior")

    # -- windscreen, sight, mast ------------------------------------------------
    def build_windscreen(self):
        A = lambda s: (1.83, s * 0.15, fus_top(1.83, 0.15) - 0.005)
        Bp = lambda s: (2.165, s * 0.155, 0.885)
        D = lambda s: (2.00, s * 0.27, fus_top(2.00, 0.27) - 0.005)
        C = lambda s: (2.20, s * 0.305, fus_top(2.20, 0.305) - 0.005)
        g = Builder()
        g.poly([A(-1), A(1), Bp(1), Bp(-1)])
        for s in (-1, 1):
            g.poly([A(s), D(s), C(s), Bp(s)])
        self.add("Windscreen", g, mats=("Glass",), smooth=None)
        f = Builder()
        edges = [(A(-1), A(1)), (Bp(-1), Bp(1))]
        for s in (-1, 1):
            edges += [(A(s), Bp(s)), (A(s), D(s)), (D(s), C(s)), (C(s), Bp(s))]
        for p0, p1 in edges:
            f.tube(p0, p1, 0.009, n=6)
        # gun sight, all outside and ahead of the windscreen (from the owner's
        # reference picture): a long thin tube on the cowl, tapered to a point
        # at its front end just behind the engine ring, carried on two studs
        # (the front one on a small block) and ending at the windscreen glass.
        s0 = Vector((0.98, 0, fus_top(0.98) + 0.085))
        s1 = Vector((1.875, 0, fus_top(1.83) + 0.045))
        on = lambda x: s0 + (s1 - s0) * ((x - s0.x) / (s1.x - s0.x))
        tt = lambda x: (x - s0.x) / (s1.x - s0.x)
        f.revolve(s0, s1, [(0, 0.003), (tt(1.04), 0.008), (tt(1.13), 0.013), (1, 0.013)], n=12, mat=1)
        xf, xr = 1.25, 1.75
        zb = fus_top(xf)
        f.box([(xf - 0.03, -0.022, zb - 0.01), (xf + 0.03, -0.022, zb - 0.01), (xf + 0.03, 0.022, zb - 0.01), (xf - 0.03, 0.022, zb - 0.01),
               (xf - 0.025, -0.018, zb + 0.035), (xf + 0.025, -0.018, zb + 0.035), (xf + 0.025, 0.018, zb + 0.035), (xf - 0.025, 0.018, zb + 0.035)])
        f.tube((xf, 0, zb + 0.03), (xf, 0, on(xf).z - 0.008), 0.005, n=6, mat=1)
        f.tube((xr, 0, fus_top(xr) - 0.01), (xr, 0, on(xr).z - 0.008), 0.005, n=6, mat=1)
        self.add("WindscreenFrame", f, mats=("Skin", "Black"))
        # radio mast behind the engine, raked forward, with the aerial wire to the fin
        m = Builder()
        base, tip = (1.20, 0, fus_top(1.20) - 0.02), (1.06, 0, fus_top(1.20) + 0.60)
        m.revolve(base, tip, [(0, 0.022), (1, 0.010)], n=8)
        m.tube(tip, (6.62, 0, 1.15), 0.0025, n=4, mat=1)
        # stub mast and pitot head on the starboard wing
        y = 3.05
        zt = wing_surface(1.75, y, +1)
        m.revolve((1.75, y, zt - 0.01), (1.72, y, zt + 0.30), [(0, 0.012), (1, 0.006)], n=6)
        m.tube((1.72, y, zt + 0.30), (6.60, 0.02, 1.12), 0.0025, n=4, mat=1)
        zl = wing_surface(1.50, 3.35, -1)
        m.tube((1.50, 3.35, zl + 0.01), (1.46, 3.35, zl - 0.10), 0.008, n=6, mat=1)
        m.revolve((1.50, 3.35, zl - 0.10), (1.05, 3.35, zl - 0.10), [(0, 0.008), (0.9, 0.008), (1, 0.004)], n=6, mat=1)
        self.add("Masts", m, mats=("Skin", "Steel"))

    # -- wing --------------------------------------------------------------------
    def build_wing(self):
        (y0, xh0), (y1, xh1) = HINGE_AIL
        hinge_x = lambda y: xh0 + (xh1 - xh0) * (abs(y) - y0) / (y1 - y0)
        fh = lambda y: (hinge_x(y) - WING_LE(abs(y))) / (WING_TE(abs(y)) - WING_LE(abs(y)))
        b = Builder()
        centre = [0.0, 0.3, 0.56, 0.8, 1.1, 1.3, y0]
        ys = [-y for y in reversed(centre[1:])] + centre
        b.loft([wing_section(y) for y in ys])
        ya, yb = y0 + 0.0, 3.58
        mid = list(np.linspace(ya, yb, 8))
        tip = [yb, 3.70, 3.86, 3.98, 4.08, 4.16, 4.21, 4.245, 4.258]
        for s in (1, -1):
            b.loft([wing_section(s * y, 0.0, min(fh(y) - GAP / 1.5, 0.995)) for y in mid])
            b.loft([wing_section(s * y) for y in tip])
        self.add("Wing", b)
        for s, tag in ((1, "R"), (-1, "L")):
            # aileron: aft of the hinge line
            a = Builder()
            a.loft([wing_section(s * y, min(fh(y) + GAP / 1.5, 0.997), 1.0, n=5) for y in np.linspace(ya + GAP, yb - GAP, 8)])
            p0 = Vector((hinge_x(ya), s * ya, wing_surface(hinge_x(ya), s * ya, 0)))
            p1 = Vector((hinge_x(yb), s * yb, wing_surface(hinge_x(yb), s * yb, 0)))
            self.add("Aileron_" + tag, a, origin=p0, axis=(p1 - p0) * s, hinge="trailing edge down")
            # split flap under the centre section, between the fuselage and the aileron
            f = Builder()
            yi, yo = 0.60, y0 - 0.02
            pts = []
            for y in (yi, yo):
                te = WING_TE(y)
                for x in (te - 0.30, te - 0.004):
                    pts.append((x, s * y, wing_surface(x, s * y, -1)))
            lo = [tuple(Vector(p) - Vector((0, 0, 0.007))) for p in pts]
            f.box([pts[0], pts[1], pts[3], pts[2], lo[0], lo[1], lo[3], lo[2]])
            h0, h1 = Vector(pts[0]), Vector(pts[2])
            self.add("Flap_" + tag, f, origin=h0, axis=(h1 - h0) * s, hinge="trailing edge down", smooth=None)
        # navigation lights on the tips, and the tail light
        for s, tag, mat in ((1, "R", "LensGreen"), (-1, "L", "LensRed")):
            l = Builder()
            y = 4.20
            c = Vector(((WING_LE(y) + WING_TE(y)) / 2 - 0.05, s * 4.235, wing_surface((WING_LE(y) + WING_TE(y)) / 2, s * y, 0)))
            l.revolve(c, c + Vector((0, s * 0.035, 0)), [(0, 0.022), (0.5, 0.020), (0.85, 0.012), (1, 0.003)], n=10)
            self.add("NavLight_" + tag, l, mats=(mat,))

    # -- tail --------------------------------------------------------------------
    def build_tail(self):
        hz = lambda x, h, y: (x, y, TAIL_Z + h)
        b = Builder()
        ys = [0.0, 0.2, 0.45, 0.7, 0.95, 1.15, 1.26]
        full = [-y for y in reversed(ys[1:])] + ys
        b.loft([sym_ring(TAIL_LE(abs(y)), TAIL_TE(abs(y)), 0.0,
                         min((TAIL_HINGE - GAP - TAIL_LE(abs(y))) / (TAIL_TE(abs(y)) - TAIL_LE(abs(y))), 0.999), 0.035,
                         lambda x, h, y=y: hz(x, h, y)) for y in full])
        self.add("Tailplane", b)
        for s, tag in ((1, "R"), (-1, "L")):
            e = Builder()
            st = [0.13, 0.3, 0.6, 0.9, 1.15, 1.27]
            rings = []
            for y in st:
                le, te = TAIL_LE(y), TAIL_TE(y)
                rings.append(sym_ring(le, te, (TAIL_HINGE + GAP - le) / (te - le), 1.0, 0.035,
                                      lambda x, h, y=y: hz(x, h, s * y), n=5))
            for y in (1.30, 1.36, 1.41, 1.44):                  # the tip wraps round ahead of the hinge
                le, te = TAIL_LE(y), TAIL_TE(y)
                f0 = max((TAIL_HINGE + GAP - le) / (te - le), 0.02)
                rings.append(sym_ring(le, te, f0, 1.0, 0.035, lambda x, h, y=y: hz(x, h, s * y), n=5))
            e.loft(rings)
            self.add("Elevator_" + tag, e, origin=(TAIL_HINGE, s * 0.13, TAIL_Z), axis=(0, s, 0), hinge="trailing edge down")
        # fin and rudder
        vy = lambda x, h, z: (x, h, z)
        b = Builder()
        b.loft([sym_ring(FIN_LE(z), RUD_TE(z), 0.0, min((RUD_HINGE - GAP - FIN_LE(z)) / (RUD_TE(z) - FIN_LE(z)), 0.999), 0.03,
                         lambda x, h, z=z: vy(x, h, z)) for z in (0.12, 0.31, 0.5, 0.7, 0.9, 1.03, 1.11, 1.16, 1.177)])
        self.add("Fin", b)
        r = Builder()
        zs = [-0.238, -0.22, -0.17, -0.08, 0.05, 0.2, 0.4, 0.6, 0.8, 0.95, 1.05, 1.12, 1.165, 1.178]
        rings = []
        for z in zs:
            le = FIN_LE(max(z, 0.15)) if z > 0.15 else 5.87
            te = RUD_TE(z)
            f0 = (RUD_HINGE + GAP - le) / (te - le)
            rings.append(sym_ring(le, te, f0, 1.0, 0.03 if z > 0.2 else 0.03 + 0.05 * (0.2 - z), lambda x, h, z=z: vy(x, h, z), n=6))
        r.loft(rings)
        l = Builder()
        c = Vector((RUD_TE(0.30) - 0.01, 0, 0.30))
        l.revolve(c, c + Vector((0.035, 0, 0)), [(0, 0.018), (0.6, 0.015), (1, 0.003)], n=10)
        rud = self.add("Rudder", r, origin=(RUD_HINGE, 0, -0.24), axis=(0, 0, 1), up=(0, 1, 0),
                       hinge="trailing edge to starboard (nose-right yaw)")
        self.add("TailLight", l, mats=("LensWhite",), parent=rud)

    # -- engine, ring, propeller -------------------------------------------------
    def build_engine(self):
        R = ENGINE_DIAMETER / 2
        xe = 0.66                                             # cylinder plane
        b = Builder()
        # crankcase and nose case
        b.revolve((0.40, 0, 0), (0.80, 0, 0), [(0, 0.07), (0.1, 0.105), (0.25, 0.15), (0.42, 0.215), (0.52, 0.275),
                                               (0.86, 0.275), (0.94, 0.25), (1.0, 0.25)], n=36, mat=0)
        b.revolve((0.30, 0, 0), (0.42, 0, 0), [(0, 0.035), (1, 0.035)], n=12, mat=3)           # propeller shaft
        b.revolve((0.50, 0, 0), (0.515, 0, 0), [(0, 0.30), (1, 0.30)], n=36, mat=3, caps=(False, False))   # ignition ring
        for k in range(9):
            a = 2 * math.pi * k / 9
            d = Vector((0, math.sin(a), math.cos(a)))
            tng = Vector((0, math.cos(a), -math.sin(a)))
            base = Vector((xe, 0, 0))
            # finned barrel, then the head with deeper fins
            prof, r0, r1 = [], 0.25, 0.655
            t = lambda r: (r - r0) / (r1 - r0)
            rr = 0.26
            while rr < 0.475:
                prof += [(t(rr), 0.064), (t(rr + 0.002), 0.079), (t(rr + 0.007), 0.079), (t(rr + 0.009), 0.064)]
                rr += 0.0125
            while rr < 0.60:
                w = 0.088 - 0.02 * (rr - 0.475) / 0.125
                prof += [(t(rr), w - 0.02), (t(rr + 0.003), w), (t(rr + 0.010), w), (t(rr + 0.013), w - 0.02)]
                rr += 0.018
            prof += [(t(0.605), 0.05), (t(0.625), 0.04)]
            b.revolve(base + d * r0, base + d * r1, [(0, 0.064)] + prof, n=14, mat=1)
            # rocker boxes fore and aft, pushrod tubes from the front of the crankcase
            for dx in (-0.055, 0.055):
                c = base + d * 0.615 + Vector((dx, 0, 0))
                b.bar(c - d * 0.03, c + d * 0.04, 0.05, 0.06, up=(1, 0, 0), mat=1)
            for sg in (-1, 1):
                b.tube(Vector((0.545, 0, 0)) + d * 0.265 + tng * (sg * 0.03),
                       base + d * 0.60 + Vector((-0.055, 0, 0)) + tng * (sg * 0.016), 0.008, n=6, mat=3)
            # exhaust stub from the rear of the head, sweeping aft outside the fuselage
            p0 = base + d * 0.52 + Vector((0.07, 0, 0))
            p1 = base + d * 0.575 + Vector((0.22, 0, 0)) + tng * 0.03
            p2 = base + d * 0.56 + Vector((0.42, 0, 0)) + tng * 0.05
            b.tube(p0, p1, 0.030, n=10, mat=2)
            b.revolve(p1, p2, [(0, 0.030), (1, 0.028)], n=10, mat=2, caps=(True, False))
            b.revolve(p2, p1, [(0, 0.024), (1, 0.026)], n=10, mat=4, caps=(False, True))       # dark bore
        self.add("Engine", b, mats=("EngineGrey", "Cylinder", "Exhaust", "Steel", "Black"), smooth=30.0)
        # Townend ring: clears the rocker boxes, outside diameter 1.41 m
        b = Builder()
        prof = [(0.46, 0.648), (0.475, 0.672), (0.52, 0.692), (0.62, 0.705), (0.75, 0.702), (0.87, 0.682),
                (0.865, 0.674), (0.75, 0.682), (0.62, 0.680), (0.52, 0.668), (0.48, 0.650)]
        n = 72
        rings = [[(x, r * math.sin(2 * math.pi * k / n), r * math.cos(2 * math.pi * k / n)) for k in range(n)] for x, r in prof]
        idx = [b.ring(r) for r in rings]
        for i in range(len(idx)):
            b.bridge(idx[i], idx[(i + 1) % len(idx)])
        self.add("TownendRing", b)
        # propeller: Hamilton Standard two-blade, ground-adjustable hub
        b = Builder()
        Rp = PROP_DIAMETER / 2
        xp = 0.32
        b.revolve((xp, 0, -0.13), (xp, 0, 0.13), [(0, 0.05), (0.08, 0.062), (0.92, 0.062), (1, 0.05)], n=14, mat=2)   # barrel
        b.revolve((0.22, 0, 0), (0.40, 0, 0), [(0, 0.03), (0.15, 0.058), (0.85, 0.058), (1, 0.045)], n=16, mat=2)
        for sg in (-1, 1):
            for zc in (0.075, 0.115):                         # blade clamp rings
                b.revolve((xp, 0, sg * zc), (xp, 0, sg * (zc + 0.018)), [(0, 0.07), (1, 0.07)], n=14, mat=2)
            rings = []
            for i in range(15):
                rf = 0.085 + (1 - 0.085) * i / 14.0
                r = rf * Rp
                chord = 0.215 * (math.sin(math.pi * min(rf * 0.98 + 0.04, 1.0)) ** 0.75) * (1.0 if rf < 0.9 else math.sqrt(max(1 - ((rf - 0.9) / 0.1) ** 2, 0.02)))
                chord = max(chord, 0.09 if rf < 0.2 else 0.012)
                thick = max(0.09 * (1 - rf) ** 2.2 + 0.006, 0.006) if rf > 0.2 else 0.088
                pitch = math.radians(58 - 42 * rf ** 0.7)
                m = 10
                sec = []
                for k in range(m):
                    a = 2 * math.pi * k / m
                    u, v = 0.5 * chord * math.cos(a), 0.5 * thick * math.sin(a) * (1.0 if math.sin(a) > 0 else 0.55)
                    if rf <= 0.2:
                        u, v = 0.044 * math.cos(a), 0.044 * math.sin(a)       # round shank
                    # chordwise u turns from the plane of rotation towards the flight direction by the pitch
                    sec.append((xp - u * math.sin(pitch) * sg - v * math.cos(pitch), u * math.cos(pitch) - v * math.sin(pitch) * sg, sg * r))
                rings.append(sec)
            mats_before = len(b.faces)
            b.loft(rings, mat=0)
            for fi in range(mats_before, len(b.faces)):       # rear (pilot's) faces painted matt black
                f = b.faces[fi]
                cx = sum(b.verts[i][0] for i in f) / len(f)
                cz = abs(sum(b.verts[i][2] for i in f) / len(f))
                if cx > xp + 0.002 and cz > 0.2 * Rp:
                    b.mats[fi] = 1
        self.add("Propeller", b, mats=("Metal", "PropBack", "Steel"), origin=(xp, 0, 0), axis=(-1, 0, 0),
                 hinge="propeller turns (clockwise seen from the cockpit)", smooth=35.0)

    # -- landing gear ------------------------------------------------------------
    def build_gear(self):
        wx, wy, wz, wr = WHEEL
        for s, tag in ((1, "R"), (-1, "L")):
            b = Builder()
            y = s * wy
            # tyre and hub
            hw = 0.065
            b.revolve((wx, y - hw, wz), (wx, y + hw, wz), [(0, wr * 0.50), (0.02, wr * 0.80), (0.12, wr * 0.95), (0.3, wr),
                                                           (0.7, wr), (0.88, wr * 0.95), (0.98, wr * 0.80), (1, wr * 0.50)],
                      n=32, mat=1, cap_mats=(2, 2))
            # spat: teardrop around the wheel, open below
            xs = np.linspace(1.01, 1.81, 15)
            rings = []
            for x in xs:
                u = (x - 1.01) / 0.80
                shape = (math.sin(math.pi * u ** 0.62)) ** 0.75 if 0 < u < 1 else 0.0
                w = max(0.145 * shape, 0.004)
                zt = wz + max(0.335 * shape, 0.01)
                zb = wz - max(0.21 * shape, 0.01)
                m = 14
                rings.append([(x, y + w * math.cos(2 * math.pi * k / m), (zt + zb) / 2 + (zt - zb) / 2 * math.sin(2 * math.pi * k / m))
                              for k in range(m)])
            b.loft(rings, mat=0)
            # leg fairing from the wing down into the spat
            zs = np.linspace(wing_surface(1.45, y, -1) + 0.03, wz + 0.22, 6)
            ztop, zbot = zs[0], zs[-1]
            rings = []
            for z in zs:
                u = (ztop - z) / (ztop - zbot)
                xf, xr = 1.27 - 0.05 * u, 1.69 + 0.05 * u
                th = 0.17 + 0.07 * u                          # the "trouser" is thick, widening into the spat
                rings.append(sym_ring(xf, xr, 0.0, 1.0, th / (xr - xf),
                                      lambda x, h, z=z: (x, y + h, z), n=7))
            b.loft(rings, mat=0)
            self.add("MainGear_" + tag, b, mats=("Skin", "Tyre", "Skin"))
        # tailwheel in a small fairing
        tx, _, tz, tr = TAILWHEEL
        b = Builder()
        b.revolve((tx, -0.035, tz), (tx, 0.035, tz), [(0, tr * 0.5), (0.1, tr * 0.9), (0.3, tr), (0.7, tr), (0.9, tr * 0.9), (1, tr * 0.5)],
                  n=20, mat=1, cap_mats=(0, 0))
        rings = []
        for x in np.linspace(tx - 0.24, tx + 0.16, 7):
            u = (x - (tx - 0.24)) / 0.40
            sh = math.sin(math.pi * u ** 0.7) ** 0.8 if 0 < u < 1 else 0.0
            w = max(0.055 * sh, 0.004)
            z1 = -0.22 - 0.03 * u
            z0 = z1 - max(0.17 * sh, 0.01)
            rings.append([(x, w * math.cos(2 * math.pi * k / 10), (z0 + z1) / 2 + (z1 - z0) / 2 * math.sin(2 * math.pi * k / 10)) for k in range(10)])
        b.loft(rings, mat=0)
        self.add("Tailwheel", b, mats=("Skin", "Tyre"))

    # -- bracing wires -------------------------------------------------------------
    def build_wires(self):
        b = Builder()
        wx, wy, wz, wr = WHEEL

        def wire(p0, p1, r=0.0035):
            p0, p1 = Vector(p0), Vector(p1)
            b.tube(p0, p1, r, n=5)
            d = (p1 - p0).normalized()
            for q, sg in ((p0, 1), (p1, -1)):                 # end fittings
                b.tube(q, q + d * (sg * 0.07), 0.007, n=6)
        for s in (1, -1):
            up = (1.60, s * 0.47, 0.50)                       # anchor on the upper longeron
            lo = (1.52, s * (wy + 0.02), wz + 0.26)           # anchor on the gear leg
            for x, dx in ((1.58, 0.03), (1.58, -0.03)):       # doubled front wires
                yw = 2.42
                wire((up[0] + dx, up[1], up[2]), (x + dx, s * yw, wing_surface(x + dx, s * yw, +1)))
                wire((lo[0] + dx, lo[1], lo[2]), (x + dx, s * 2.46, wing_surface(x + dx, s * 2.46, -1)))
            wire(up, (2.53, s * 2.42, wing_surface(2.53, s * 2.42, +1)))
            wire((lo[0] + 0.25, lo[1], lo[2]), (2.50, s * 2.46, wing_surface(2.50, s * 2.46, -1)))
            # jury strut steadying the upper front wires
            ys = 1.66
            zw = wing_surface(1.58, s * ys, +1)
            t = (ys - 0.47) / (2.42 - 0.47)
            zwire = up[2] + (wing_surface(1.58, s * 2.42, +1) - up[2]) * t
            b.bar((1.58, s * ys, zw - 0.005), (1.58, s * ys, zwire + 0.01), 0.012, 0.07, up=(1, 0, 0))
            # cross wires between the gear legs and the fuselage, and a drag wire aft
            wire(lo, (1.52, -s * fus_side(1.52, -0.50) * 0.96, -0.50))
            wire(lo, (2.62, s * fus_side(2.62, -0.56) * 0.96, -0.56))
        self.add("Wires", b, mats=("Steel",), smooth=None)

    # -- guns ------------------------------------------------------------------------
    def marker(self, name, pos, **props):
        """An empty at a point of interest (a gun muzzle), for the game to read."""
        e = bpy.data.objects.new(self.prefix + name, None)
        e.empty_display_type, e.empty_display_size = "PLAIN_AXES", 0.08
        self.col.objects.link(e)
        e.parent = self.root
        e.matrix_basis = Matrix.Translation(self.tb(pos))
        self.world[e.name] = e.matrix_basis.copy()
        for k, v in props.items():
            e[k] = v
        self.objects[e.name] = e
        return e

    def build_guns(self):
        """Two Browning .30 calibre M2 aircraft guns low in the fuselage sides.  Each fires
        through a blast tube that runs forward between the cylinders; the breech sits in a
        well in the cockpit floor beside the pilot's leg."""
        gy, z, xm, xt = GUN["y"], GUN["z"], GUN["muzzle"], GUN["tube"]
        b = Builder()
        g = Builder()
        for s in (1, -1):
            y = s * gy
            # one connected shell (outside, lip, bore) so the bore faces inwards
            circ = lambda x, r: [(x, y + r * math.cos(2 * math.pi * k / 12), z + r * math.sin(2 * math.pi * k / 12)) for k in range(12)]
            idx = [b.ring(q) for q in (circ(1.62, 0.021), circ(xt, 0.021), circ(xt, 0.016), circ(xm + 0.02, 0.016))]
            b.bridge(idx[0], idx[1], 0)
            b.bridge(idx[1], idx[2], 0)
            b.bridge(idx[2], idx[3], 1)
            browning(g, xm, y, z, s)
        self.add("BlastTubes", b, mats=("Skin", "Black"))
        self.add("Guns", g, mats=("GunMetal", "Steel"), smooth=40.0)
        for s, tag in ((1, "R"), (-1, "L")):
            self.marker("Muzzle_" + tag, (xt, s * gy, z), gun="Browning .30 M2", bore_axis="-Y (forward)")

    def build(self):
        self.build_fuselage()
        self.build_windscreen()
        self.build_wing()
        self.build_tail()
        self.build_engine()
        self.build_gear()
        self.build_wires()
        self.build_guns()
        import p26a_cockpit
        p26a_cockpit.build(self)
        tx, _, tz, tr = TAILWHEEL
        self.root["span_m"] = SPAN
        self.root["length_m"] = LENGTH
        self.root["ground_z"] = GROUND_Z
        # nose-up angle with the tailwheel on the ground, about the main-wheel contact point
        self.root["ground_pitch_deg"] = math.degrees(math.atan2((tz - tr) - GROUND_Z, tx - WHEEL[0]))
        self.root["main_wheel_x"] = WHEEL[0] - X_REF
        return self.root


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=HERE)
    ap.add_argument("--glb", action="store_true")
    ap.add_argument("--bake", nargs="*", default=None, help="bake the textures: all groups, or those named (ext, parts)")
    ap.add_argument("--samples", type=int, default=8)
    args = ap.parse_args(argv)
    sys.path.insert(0, HERE)
    reset_scene()
    h = Peashooter()
    h.build()
    import p26a_materials
    bake = False if args.bake is None else (args.bake or True)
    p26a_materials.texture(h, os.path.join(HERE, "textures"), bake=bake, samples=args.samples)
    path = os.path.join(args.out, "P-26A_Peashooter.blend")
    if os.path.exists(path):
        os.remove(path)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print("saved", path)
    if args.glb:
        glb = os.path.join(args.out, "P-26A_Peashooter.glb")
        bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_apply=True, use_visible=True,
                                  export_extras=True, export_cameras=True)
        print("saved", glb)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
