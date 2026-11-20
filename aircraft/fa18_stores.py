"""
External stores, suspension equipment, station sockets and loadouts for the
F/A-18A/B generator.  Data: stores_data.py.

Every store is an object in the "Stores Library" collection with its origin
at its suspension point (top of the body, midway between the lugs or rail
hangers) and its nose toward -Y (the aircraft's forward axis), so attaching a
store is: put its origin on a station socket.  Socket empties STA_1..STA_9
sit where the store's suspension point goes for that station's usual
equipment; racks and launchers carry their own child sockets.
"""
import json
import math
import os

import bpy
from mathutils import Matrix, Vector

import stores_data as SD

TEX = None    # set by build_all


# ----------------------------------------------------------------------------
# mesh assembly in a store's own frame (x aft from nose, y starboard, z up)
# ----------------------------------------------------------------------------
class SB:
    def __init__(self):
        self.v, self.f, self.uv = [], [], []

    def ring(self, pts):
        i = len(self.v)
        self.v += [tuple(p) for p in pts]
        return list(range(i, i + len(pts)))

    def face(self, idx, uvs):
        self.f.append(tuple(idx))
        self.uv.append(uvs)

    def quad_strip(self, a, b, ua, ub, closed=True):
        n = len(a)
        for i in range(n if closed else n - 1):
            j = (i + 1) % n
            self.face((a[i], a[j], b[j], b[i]), [ua[i], ua[j] if j else ua[n], ub[j] if j else ub[n], ub[i]])


def to_bl(p):
    return (-p[1], p[0], p[2])


def make_object(name, sb, origin, collection, mat):
    """origin: store-frame point that becomes the object origin."""
    mesh = bpy.data.meshes.new(name)
    o = Vector(origin)
    mesh.from_pydata([to_bl(Vector(p) - o) for p in sb.v], [], sb.f)
    layer = mesh.uv_layers.new(name="UVMap")
    k = 0
    for poly, uvs in zip(mesh.polygons, sb.uv):
        for li, uv in zip(poly.loop_indices, uvs):
            layer.data[li].uv = uv
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    if hasattr(mesh, "set_sharp_from_angle"):
        mesh.set_sharp_from_angle(angle=math.radians(40))
    mesh.materials.append(mat)
    ob = bpy.data.objects.new(name, mesh)
    collection.objects.link(ob)
    ob["uv_explicit"] = True
    mesh["uv_explicit"] = True          # linked duplicates (loadouts) share this mesh
    return ob


# ----------------------------------------------------------------------------
# UV helpers into an item's atlas rect
# ----------------------------------------------------------------------------
class Skin:
    def __init__(self, item):
        self.x0, self.y0, self.x1, self.y1, self.bw = SD.pack()[item["id"]]

    def uv(self, px, py):
        return (px / SD.ATLAS, 1.0 - py / SD.ATLAS)

    def body(self, frac_around, x_m):
        return self.uv(self.x0 + 4 + frac_around * (self.bw - 8), self.y0 + 4 + x_m * SD.PPM)

    def fin(self, chord_m, span_m):
        return self.uv(self.x0 + self.bw + 4 + chord_m * SD.PPM, self.y0 + 4 + span_m * SD.PPM)


# ----------------------------------------------------------------------------
# geometry primitives
# ----------------------------------------------------------------------------
N_RING = 20


def body_of_revolution(sb, sk, L, R, profile, n=N_RING, x_from=None, x_to=None, close=True):
    """Revolve profile (t, r/R) about the store axis; UV wraps around the
    skin's body area (seam on the underside)."""
    rings, uvs = [], []
    for t, rf in profile:
        x = t * L
        if x_from is not None and x < x_from - 1e-6:
            continue
        if x_to is not None and x > x_to + 1e-6:
            continue
        r = max(rf * R, 0.0005)
        pts = []
        for k in range(n):
            a = -math.pi / 2 + 2 * math.pi * k / n
            pts.append((x, r * math.cos(a), r * math.sin(a)))
        rings.append(sb.ring(pts))
        uvs.append([sk.body(k / n, x) for k in range(n + 1)])
    for i in range(len(rings) - 1):
        sb.quad_strip(rings[i], rings[i + 1], uvs[i], uvs[i + 1])
    if close:
        sb.face(rings[0][::-1], [uvs[0][k] for k in range(n)][::-1])
        sb.face(rings[-1], [uvs[-1][k] for k in range(n)])
    return rings


def box_body(sb, sk, L, w, h, nose=0.08, tail=0.92):
    """Faceted box body (JSOW, TALD): chamfered square section, tapered ends."""
    def sec(x, s):
        c = 0.18
        hw, hh = w / 2 * s, h / 2 * s
        return [(x, -hw + c * hw, -hh), (x, hw - c * hw, -hh), (x, hw, -hh + c * hh), (x, hw, hh - c * hh),
                (x, hw - c * hw, hh), (x, -hw + c * hw, hh), (x, -hw, hh - c * hh), (x, -hw, -hh + c * hh)]
    stations = [(0.0, 0.25), (nose * L, 1.0), (tail * L, 1.0), (L, 0.6)]
    rings, uvs = [], []
    for x, s in stations:
        rings.append(sb.ring(sec(x, s)))
        uvs.append([sk.body(k / 8, x) for k in range(9)])
    for i in range(len(rings) - 1):
        sb.quad_strip(rings[i], rings[i + 1], uvs[i], uvs[i + 1])
    sb.face(rings[0][::-1], [uvs[0][k] for k in range(8)][::-1])
    sb.face(rings[-1], [uvs[-1][k] for k in range(8)])


def fin_set(sb, sk, R, f, root_r=None):
    """n thin trapezoidal fins about the axis.  Fin planform UV-maps into the
    skin's fin strip (chord across, span down)."""
    t = f.get("t", 0.006)
    r0 = (root_r if root_r is not None else R) * 0.95
    half = f["span"] / 2
    for k in range(f["n"]):
        a = math.radians(f["roll"] + 360.0 * k / f["n"])
        d = Vector((0, math.cos(a), math.sin(a)))
        nrm = Vector((0, -math.sin(a), math.cos(a))) * (t / 2)
        P = [Vector((f["x0"], 0, 0)) + d * r0, Vector((f["x0"] + f["c0"], 0, 0)) + d * r0,
             Vector((f["x1"] + f["c1"], 0, 0)) + d * half, Vector((f["x1"], 0, 0)) + d * half]
        uv = [sk.fin(0, 0), sk.fin(f["c0"], 0), sk.fin(f["x1"] + f["c1"] - f["x0"], half - r0),
              sk.fin(f["x1"] - f["x0"], half - r0)]
        a_ = sb.ring([p + nrm for p in P])
        b_ = sb.ring([p - nrm for p in P])
        sb.face(a_, uv)
        sb.face(b_[::-1], uv[::-1])
        for i in range(4):
            j = (i + 1) % 4
            sb.face((a_[i], b_[i], b_[j], a_[j]), [uv[i], uv[i], uv[j], uv[j]])


def lugs(sb, sk, L, R, x_mid, spacing):
    """Two suspension lugs on top of the body."""
    if not spacing:
        return
    for dx in (-spacing / 2, spacing / 2):
        x = x_mid + dx
        P = [(x - 0.02, -0.012, R - 0.004), (x + 0.02, -0.012, R - 0.004), (x + 0.02, 0.012, R - 0.004),
             (x - 0.02, 0.012, R - 0.004), (x - 0.015, -0.012, R + 0.03), (x + 0.015, -0.012, R + 0.03),
             (x + 0.015, 0.012, R + 0.03), (x - 0.015, 0.012, R + 0.03)]
        _box(sb, P, sk.body(0.5, x))


def _box(sb, P, uv):
    a = sb.ring(P[:4])
    b = sb.ring(P[4:])
    for i in range(4):
        j = (i + 1) % 4
        sb.face((a[i], a[j], b[j], b[i]), [uv] * 4)
    sb.face(a[::-1], [uv] * 4)
    sb.face(b, [uv] * 4)


# ----------------------------------------------------------------------------
# guidance kits and special features
# ----------------------------------------------------------------------------
def kit_parts(sb, sk, s, R):
    L = s["L"]
    kit = s["kit"]
    span = s["kit_span"]
    tail_x = s["profile"][-1][0] * L          # end of the bomb body
    if kit == "conical":
        # conical fin: cone from the body end to the fin box, four fins
        cone = [(tail_x / L, 0.50), (0.90, 0.42), (0.995, 0.36), (1.0, 0.30)]
        body_of_revolution(sb, sk, L, R, cone)
        fin_set(sb, sk, R * 0.42, dict(x0=tail_x + 0.02, c0=(L - tail_x) - 0.04, x1=tail_x + 0.12 * (L - tail_x),
                                      c1=(L - tail_x) * 0.82, span=span, n=4, roll=45, t=0.004))
    elif kit == "snakeye":
        # Mk 15 Snakeye: support tube and four closed drag plates forming an X
        tube = [(tail_x / L, 0.45), (0.86, 0.40), (1.0, 0.36)]
        body_of_revolution(sb, sk, L, R, tube)
        fin_set(sb, sk, R * 0.4, dict(x0=tail_x + 0.01, c0=L - tail_x - 0.02, x1=tail_x + 0.02,
                                      c1=L - tail_x - 0.03, span=span, n=4, roll=45, t=0.012))
    elif kit == "jdam":
        tailcone = [(tail_x / L, 0.62), (0.93, 0.45), (1.0, 0.30)]
        body_of_revolution(sb, sk, L, R, tailcone)
        c = (L - tail_x) * 0.55
        fin_set(sb, sk, R * 0.5, dict(x0=L - c - 0.02, c0=c, x1=L - c * 0.7, c1=c * 0.65, span=span, n=4,
                                      roll=45, t=0.008))
        xs = 0.10 * L if s.get("strakes") == "nose" else 0.42 * L
        fin_set(sb, sk, R, dict(x0=xs, c0=0.32, x1=xs + 0.04, c1=0.26, span=2 * R + 0.10, n=4, roll=45,
                                t=0.010))
    elif kit in ("paveway", "paveway3"):
        # nose: computer-control group with canards, seeker on its gimbal, ring "birdie"
        big = kit == "paveway3"
        cg_r = R * (0.62 if not big else 0.70)
        cg_len = 0.75 if not big else 0.95
        x_seek = 0.0
        ccg = [(0.0, 0.10), (0.03, 0.55), (0.10 / L, 0.70), (cg_len / L, 1.0)]
        body_of_revolution(sb, sk, L, cg_r, [(t, r) for t, r in ccg])
        fin_set(sb, sk, cg_r, dict(x0=0.28, c0=0.26 if not big else 0.34, x1=0.38, c1=0.10,
                                   span=span if not big else 0.997, n=4, roll=45, t=0.006))
        # ring tail of the seeker birdie
        ring = [(0.02, 0.0), (0.021, 1.0), (0.10, 1.0), (0.101, 0.0)]
        body_of_revolution(sb, sk, 1.0, cg_r * 1.25, ring, n=16)
        # airfoil group: folded wings along the tail (carriage position)
        tailcone = [(tail_x / L, 0.62), (0.95, 0.50), (1.0, 0.45)]
        body_of_revolution(sb, sk, L, R, tailcone)
        c = (L - tail_x) * 0.95
        fin_set(sb, sk, R * 0.5, dict(x0=tail_x + 0.02, c0=c, x1=tail_x + 0.04, c1=c - 0.02,
                                      span=2 * R * 0.62 + 0.10 if not big else s["kit_span"], n=4, roll=45,
                                      t=0.010))


def features(sb, sk, s, R):
    L = s["L"]
    for ft in s.get("features", []):
        if ft == "rat":                                   # Walleye ram-air turbine
            hub = [(0.0, 0.3), (0.5, 0.35), (1.0, 0.1)]
            body_of_revolution(sb, sk, 0.12, R * 0.6, [(t, r) for t, r in hub], n=12)
            for v in sb.v[-12 * 3:]:
                pass
            fin_set(sb, sk, R * 0.18, dict(x0=L + 0.01, c0=0.05, x1=L + 0.015, c1=0.04, span=R * 1.3, n=4,
                                           roll=0, t=0.01))
        elif ft == "intake":                              # Harpoon/SLAM ventral intake
            x0 = 0.70 * L
            P = [(x0, -0.06, -R + 0.01), (x0 + 0.45, -0.06, -R + 0.01), (x0 + 0.45, 0.06, -R + 0.01),
                 (x0, 0.06, -R + 0.01), (x0 + 0.05, -0.065, -R - 0.07), (x0 + 0.45, -0.065, -R - 0.05),
                 (x0 + 0.45, 0.065, -R - 0.05), (x0 + 0.05, 0.065, -R - 0.07)]
            _box(sb, P, sk.body(0.0, x0))
        elif ft == "jsow_wings":
            hw = s["box"][0] / 2
            hh = s["box"][1] / 2
            P = [(1.0, -hw * 0.9, hh), (3.2, -hw * 0.9, hh), (3.2, hw * 0.9, hh), (1.0, hw * 0.9, hh),
                 (1.0, -hw * 0.9, hh + 0.04), (3.2, -hw * 0.9, hh + 0.04), (3.2, hw * 0.9, hh + 0.04),
                 (1.0, hw * 0.9, hh + 0.04)]
            _box(sb, P, sk.body(0.5, 2.0))
        elif ft == "tald_wings":
            hw = s["box"][0] / 2
            hh = s["box"][1] / 2
            P = [(0.7, -hw, hh), (1.6, -hw, hh), (1.6, hw, hh), (0.7, hw, hh),
                 (0.7, -hw, hh + 0.025), (1.6, -hw, hh + 0.025), (1.6, hw, hh + 0.025), (0.7, hw, hh + 0.025)]
            _box(sb, P, sk.body(0.5, 1.1))
        elif ft == "harm_bulge":
            bulge = [(0.04, 1.0), (0.07, 1.06), (0.10, 1.0)]
            body_of_revolution(sb, sk, L, R, bulge, close=True)
        elif ft in ("tubes19", "tubes7", "tubes4"):
            n = {"tubes19": 19, "tubes7": 7, "tubes4": 4}[ft]
            # tube mouths on the aft face (dark discs, a touch proud)
            if n == 4:
                pos = [(dy, dz) for dy in (-0.45, 0.45) for dz in (-0.45, 0.45)]
            elif n == 7:
                pos = [(0, 0)] + [(0.62 * math.cos(math.radians(60 * k)), 0.62 * math.sin(math.radians(60 * k)))
                                  for k in range(6)]
            else:
                pos = [(0, 0)] + [(0.36 * math.cos(math.radians(60 * k)), 0.36 * math.sin(math.radians(60 * k)))
                                  for k in range(6)] + \
                      [(0.72 * math.cos(math.radians(30 * k)), 0.72 * math.sin(math.radians(30 * k)))
                       for k in range(12)]
            rt = R * (0.22 if n == 19 else 0.30 if n == 7 else 0.38)
            for dy, dz in pos:
                pts = [(L + 0.002, dy * R + rt * math.cos(2 * math.pi * k / 10),
                        dz * R + rt * math.sin(2 * math.pi * k / 10)) for k in range(10)]
                sb.face(sb.ring(pts), [sk.body(0.0, L)] * 10)
        elif ft == "sensor_head":
            # rotating sensor head with a flat window at the nose
            head = [(0.0, 0.02), (0.005, 0.8), (0.03, 0.97), (0.16, 0.97), (0.165, 0.9)]
            body_of_revolution(sb, sk, L, R * 1.02, head)
        elif ft == "window":
            pass
        elif ft == "datalink":
            # antenna fairing on the underside
            P = [(0.9, -0.08, -R + 0.01), (2.2, -0.08, -R + 0.01), (2.2, 0.08, -R + 0.01), (0.9, 0.08, -R + 0.01),
                 (1.0, -0.06, -R - 0.06), (2.1, -0.06, -R - 0.06), (2.1, 0.06, -R - 0.06), (1.0, 0.06, -R - 0.06)]
            _box(sb, P, sk.body(0.0, 1.5))


# ----------------------------------------------------------------------------
# items
# ----------------------------------------------------------------------------
def attach_x(s):
    cat = s["cat"]
    if cat in ("bomb", "guided_bomb", "cluster", "nuclear"):
        return 0.42 * s["L"]
    if cat in ("fuel_tank",):
        return 0.45 * s["L"]
    return 0.48 * s["L"]


def build_store(s, col, mat):
    sk = Skin(s)
    sb = SB()
    L = s["L"]
    R = s["D"] / 2
    if s.get("box"):
        box_body(sb, sk, L, s["box"][0], s["box"][1])
        top = s["box"][1] / 2
    else:
        prof = s["profile"]
        body_of_revolution(sb, sk, L, R, prof)
        top = R
    for f in s.get("fins", []):
        fin_set(sb, sk, R, f)
    if s.get("kit"):
        kit_parts(sb, sk, s, R)
    features(sb, sk, s, R)
    xa = attach_x(s)
    lugs(sb, sk, L, top, xa, s.get("lugs"))
    ob = make_object("Store_" + s["id"], sb, (xa, 0.0, top), col, mat)
    ob["store_id"] = s["id"]
    ob["name_full"] = s["name"]
    ob["category"] = s["cat"]
    ob["era"] = s["era"]
    ob["mass_kg"] = s["mass"] if s["mass"] is not None else -1
    ob["stations"] = ",".join(str(x) for x in s["stations"]) or "not documented for A/B"
    ob["mount"] = s["mount"]
    ob["confidence"] = s["conf"]
    ob["note"] = s.get("note", "")
    return ob


def equipment_section(kind, L, H, W):
    """Cross-section stations (x, half-width, depth below top) along the part."""
    if kind == "pylon":
        # dense stations so the top edge can follow the wing's curved underside
        out = []
        n = 24
        for i in range(n + 1):
            t = i / n
            hw = W / 2 * (0.25 + 0.75 * min(t / 0.25, 1.0) ** 0.5) * (1.0 if t < 0.85 else 1 - (t - 0.85) / 0.15 * 0.7)
            d = H * (0.55 + 0.45 * min(t / 0.25, 1.0)) * (1.0 if t < 0.85 else 1 - (t - 0.85) / 0.15 * 0.45)
            out.append((t * L, hw, d))
        return out
    return [(0.0, W * 0.35, H * 0.7), (0.08 * L, W / 2, H), (0.92 * L, W / 2, H), (L, W * 0.35, H * 0.7)]


def build_equipment(e, col, mat, top_profile=None):
    """Pylons, racks and launchers: rounded-box sections lofted along x.
    top_profile(x) -> z of the top edge (pylons follow the wing underside)."""
    sk = Skin(e)
    sb = SB()
    L, H, W = e["L"], e["H"], e["W"]
    secs = equipment_section("pylon" if e["cat"] == "pylon" else "box", L, H, W)
    rings, uvs = [], []
    for x, hw, d in secs:
        zt = top_profile(x) if top_profile else 0.0
        zb = zt - d
        pts = [(x, -hw, zt), (x, hw, zt), (x, hw, zb + 0.02), (x, hw * 0.6, zb), (x, -hw * 0.6, zb),
               (x, -hw, zb + 0.02)]
        rings.append(sb.ring(pts))
        per = [0.0, 0.15, 0.40, 0.50, 0.60, 0.85, 1.0]
        uvs.append([sk.body(p, x) for p in per])
    for i in range(len(rings) - 1):
        sb.quad_strip(rings[i], rings[i + 1], uvs[i], uvs[i + 1])
    sb.face(rings[0][::-1], uvs[0][:6][::-1])
    sb.face(rings[-1], uvs[-1][:6])
    if e["id"] == "BRU-33":
        # two ejector units, canted 5 deg outboard (CVER)
        for side in (-1, 1):
            c = math.radians(5) * side
            y0 = side * 0.13
            P = []
            for x in (0.15, 0.95):
                for (yy, zz) in ((-0.05, -H), (0.05, -H), (0.05, -H - 0.12), (-0.05, -H - 0.12)):
                    yr = y0 + yy * math.cos(c) - (zz + H) * math.sin(c)
                    zr = -H + yy * math.sin(c) + (zz + H) * math.cos(c)
                    P.append((x * L, yr, zr))
            _box(sb, P, sk.body(0.5, 0.5))
    ob = make_object("Equip_" + e["id"], sb, (0.0, 0.0, 0.0), col, mat)
    ob["equipment_id"] = e["id"]
    ob["confidence"] = e["conf"]
    ob["note"] = e.get("note", "")
    return ob


# ----------------------------------------------------------------------------
# aircraft side: pylons and sockets
# ----------------------------------------------------------------------------
def pylon_geometry(h, station):
    """Front x, length and a top-profile function (z of the wing underside
    along the pylon) for a wing pylon at a station."""
    from fa18_hornet import SEMI_SPAN, TIP_RAIL_REF_Y
    y = SD.STATION_Y[station]
    side = 1 if y > 0 else -1
    w = h.wing[side]
    s = abs(y) / SEMI_SPAN
    le = w.le(s).x
    x0 = le - 0.35
    L = SD.by_id("SUU-63")["L"]

    def top(xl):
        x = x0 + xl
        f = min(max(w.frac(s, x), 0.0), 1.0)
        return w.point(s, f, -1).z - 0.008
    return x0, L, top, w


def build_pylons_and_sockets(h, mat, library):
    """Pylons on stations 2/3/7/8 and 5, socket empties for all nine."""
    from fa18_hornet import to_blender
    col = h.col_pylons
    sockets = {}

    def socket(name, design_pt, parent=None, kind=""):
        e = bpy.data.objects.new(h.prefix + name, None)
        e.empty_display_type = "ARROWS"
        e.empty_display_size = 0.15
        h.col_sockets.objects.link(e)
        e.parent = parent or h.root
        if parent is None:
            e.location = to_blender(design_pt)
        else:
            e.location = Vector(design_pt)
        e["socket"] = kind
        return e

    for st in (2, 3, 7, 8):
        x0, L, top, w = pylon_geometry(h, st)
        y = SD.STATION_Y[st]
        e = SD.by_id("SUU-63")
        ob = build_equipment(e, col, mat, top_profile=lambda xl: top(xl))
        ob.name = h.prefix + "Pylon_STA%d" % st
        ob.parent = h.root
        ob.location = to_blender((x0, y, 0.0))
        z_hook = min(top(L * 0.48), top(L * 0.30)) - e["H"]
        sockets[st] = socket("STA_%d" % st, (x0 + 0.48 * L, y, z_hook), kind="BRU-32 hooks (SUU-63)")
    # centreline pylon
    e = SD.by_id("SUU-62")
    zc = h.core(10.6)[2] + 0.005
    ob = build_equipment(e, col, mat, top_profile=lambda xl: h.core(9.65 + xl)[2] + 0.004)
    ob.name = h.prefix + "Pylon_STA5"
    ob.parent = h.root
    ob.location = to_blender((9.65, 0.0, 0.0))
    sockets[5] = socket("STA_5", (9.65 + 0.48 * e["L"], 0.0, zc - e["H"]), kind="BRU-32 hooks (SUU-62)")
    # wingtip rails (station 1/9): store suspension point on top of the missile body
    from fa18_hornet import SEMI_SPAN, TIP_RAIL_REF_Y
    aim9 = SD.by_id("AIM-9L")
    for st in (1, 9):
        y = SD.STATION_Y[st]
        side = 1 if y > 0 else -1
        zt = h.wing_z(TIP_RAIL_REF_Y) - 0.054          # 2 mm under the LAU-7 launcher
        outer = h.objects[h.prefix + "Wing_Outer_" + ("R" if side > 0 else "L")]
        sockets[st] = socket("STA_%d" % st, (9.62 + attach_x(aim9), y, zt), kind="LAU-7 wingtip rail")
        sockets[st]["follows"] = outer.name
    # fuselage stations 4/6 (LAU-116 semi-recessed; pods use the same station)
    aim7 = SD.by_id("AIM-7M")
    for st in (4, 6):
        y = SD.STATION_Y[st]
        sockets[st] = socket("STA_%d" % st, (9.20 + attach_x(aim7), y, -0.46 + aim7["D"] / 2),
                             kind="LAU-116 (semi-recessed)")
    for st, e in sockets.items():
        e["station"] = st
        e["y_from_centreline_m"] = SD.STATION_Y[st]
    return sockets


# ----------------------------------------------------------------------------
# loadouts
# ----------------------------------------------------------------------------
def place(h, lib, store_id, socket, col, name, offset=(0, 0, 0), cant=0.0, roll=0.0):
    src = lib[store_id]
    ob = bpy.data.objects.new(name, src.data)
    col.objects.link(ob)
    ob.parent = socket
    ob.location = Vector(offset)
    ob["store_id"] = store_id
    return ob


def build_loadouts(h, lib, equip, sockets):
    """One hidden collection per typical load; stores are linked duplicates
    of the library meshes, parented to the station sockets."""
    parent = bpy.data.collections.new(h.col.name + " Loadouts")
    h.col.children.link(parent)
    for lname, load in SD.LOADOUTS.items():
        col = bpy.data.collections.new("%s Loadout %s" % (h.v, lname))
        parent.children.link(col)
        for st, item in load.items():
            sid, count = (item if isinstance(item, tuple) else (item, 1))
            s = SD.by_id(sid)
            sock = sockets[st]
            base = "%sLO_%s_STA%d_" % (h.prefix, lname, st)
            mount = s["mount"]
            if st in (2, 8) and sid.startswith("AIM-7"):
                mount = "LAU-115"
            if mount in ("LAU-117", "LAU-118", "LAU-115"):
                e = SD.by_id(mount)
                lau = bpy.data.objects.new(base + mount, equip[mount].data)
                col.objects.link(lau)
                lau.parent = sock
                lau.location = Vector((0, -e["L"] * 0.5, 0))
                place(h, lib, sid, sock, col, base + sid, offset=(0, 0, -e["H"]))
            elif count == 2 or mount == "BRU-33" and count > 1:
                e = SD.by_id("BRU-33")
                rack = bpy.data.objects.new(base + "BRU-33", equip["BRU-33"].data)
                col.objects.link(rack)
                rack.parent = sock
                rack.location = Vector((0, -e["L"] * 0.5, 0))
                for side in (-1, 1):
                    # CVER: units 0.13 m either side, canted 5 deg outboard (Blender X is port)
                    ob = place(h, lib, sid, sock, col, base + sid + ("_L" if side < 0 else "_R"),
                               offset=(-side * 0.13, 0.0, -e["H"] - 0.12))
                    ob.rotation_euler = (0.0, math.radians(5.0) * side, 0.0)
            elif st in (4, 6) and s["cat"] == "pod":
                place(h, lib, sid, sock, col, base + sid, offset=(0, -2.15, -0.02))
            else:
                place(h, lib, sid, sock, col, base + sid)
        col.hide_viewport = True
        col.hide_render = True
    return parent


# ----------------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------------
def store_material(tex):
    m = bpy.data.materials.get("F18_Stores")
    if m is None:
        m = bpy.data.materials.new("F18_Stores")
    base = os.path.join(tex, "stores_basecolor.jpg")
    if os.path.exists(base):
        import fa18_materials as M
        M.image_material(m, M.image(base), M.image(os.path.join(tex, "stores_orm.png"), "Non-Color"),
                         M.image(os.path.join(tex, "stores_normal.jpg"), "Non-Color"))
    else:
        m.diffuse_color = (0.5, 0.5, 0.48, 1)
    return m


def build_all(h, tex):
    mat = store_material(tex)
    h.col_pylons = bpy.data.collections.new(h.col.name + " Pylons")
    h.col.children.link(h.col_pylons)
    h.col_sockets = bpy.data.collections.new(h.col.name + " Station Sockets")
    h.col.children.link(h.col_sockets)
    libcol = bpy.data.collections.new("Stores Library")
    bpy.context.scene.collection.children.link(libcol)
    libcol.hide_render = True
    libcol.hide_viewport = True
    lib, equip = {}, {}
    for i, s in enumerate(SD.STORES):
        ob = build_store(s, libcol, mat)
        ob.location = (i % 8 * 1.2 - 4.2, 30 + i // 8 * 6.0, 0)        # laid out away from the aircraft
        lib[s["id"]] = ob
    for i, e in enumerate(SD.EQUIPMENT):
        ob = build_equipment(e, libcol, mat)
        ob.location = (i * 1.2 - 4.2, 64, 0)
        equip[e["id"]] = ob
    sockets = build_pylons_and_sockets(h, mat, lib)
    build_loadouts(h, lib, equip, sockets)
    return lib, equip, sockets


def manifest(h, sockets, path):
    """stations.json: sockets (Blender/glTF and design coordinates), what each
    station carries, and every store's data and sources."""
    from fa18_hornet import X_REF, Z_REF
    st_out = {}
    for st, e in sorted(sockets.items()):
        bl = e.matrix_world.translation if e.parent is None else (e.parent.matrix_world @ e.matrix_basis).translation
        loc = Vector(e.location)
        st_out[st] = dict(
            socket=e.name, kind=e["socket"],
            position_blender=[round(v, 4) for v in loc],
            position_design=[round(loc.y + X_REF, 4), round(-loc.x, 4), round(loc.z + Z_REF, 4)],
            equipment=[k for k, v in SD.CARRIAGE.items() if st in v["stations"]],
            stores=[s["id"] for s in SD.STORES if st in s["stations"]],
        )
    data = dict(
        aircraft="F/A-18%s" % h.v,
        coordinates="Blender/glTF: metres, +Y aft (nose toward -Y), +Z up, +X port. "
                    "Design: x aft from nose tip, y starboard, z up from the nose-tip waterline.",
        attach_rule="Put a store's origin on the socket; racks/launchers hang their store "
                    "H metres lower (see equipment).",
        stations=st_out,
        stores=[{k: v for k, v in s.items() if k not in ("profile", "fins", "body", "nose", "bands")}
                for s in SD.STORES],
        equipment=SD.EQUIPMENT and [{k: v for k, v in e.items() if k != "body"} for e in SD.EQUIPMENT],
        loadouts={k: {str(st): (v if isinstance(v, str) else list(v)) for st, v in ld.items()}
                  for k, ld in SD.LOADOUTS.items()},
    )
    with open(path, "w") as f:
        json.dump(data, f, indent=1, default=str)


def export_library_glb(path):
    """All stores and suspension equipment in one GLB; every node sits at the
    origin so its mesh origin (the suspension point) is the attach point."""
    lib = bpy.data.collections.get("Stores Library")
    if lib is None:
        return
    lib.hide_viewport = False
    lib.hide_render = False
    saved = {o.name: o.location.copy() for o in lib.objects}
    for o in lib.objects:
        o.location = (0, 0, 0)
    bpy.ops.object.select_all(action="DESELECT")
    for o in lib.objects:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_extras=True,
                              export_apply=True)
    for o in lib.objects:
        o.location = saved[o.name]
    lib.hide_viewport = True
    lib.hide_render = True
