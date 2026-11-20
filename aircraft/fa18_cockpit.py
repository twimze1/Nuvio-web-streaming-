"""
Cockpit interior for the F/A-18A / F/A-18B generator (fa18_hornet.py).

Built from:
  * NASA Ames ARC-1993-A83-0499-34, "F/A-18 Hornet cockpit" layout drawing
    (front instrument panel, glareshield lights, HUD, canopy bow mirrors);
  * NASA Dryden ED08-0252-06 (F/A-18B NASA 845 rear instrument panel),
    ED06-0075-11 (HUD combiner and canopy bow), EC02-0102-1, AFRC2018-0104-04,
    ED08-0252-26 and AFRC2026-0188-01 (SJU-5/6 seats, sidewalls, sill
    longerons, canopy interior).
Panel element positions live in cockpit_layout.py and are shared with the
texture painter, so painted legends and modelled parts line up.

Everything is in the generator's design coordinates (x aft from the nose
tip, y starboard, z up, metres).
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

import cockpit_layout as L

NOSE_BAY_ROOF_Z = 0.21          # top of the raised front foot-well floor (m, design z)


def SW(name):
    """Map faces into a worn-material tile of the cockpit atlas."""
    return lambda pts: L.cell_uvs(name, pts)


# ----------------------------------------------------------------------------
# panel space
# ----------------------------------------------------------------------------
class PanelSpace:
    """Panel face coordinates (u right, v down, mm; d toward the pilot, m)."""

    def __init__(self, x_top, z_top, tilt_deg=10.0, y0=0.0):
        t = math.radians(tilt_deg)
        self.o = Vector((x_top, y0, z_top))
        self.D = Vector((math.sin(t), 0.0, -math.cos(t)))     # down the face
        self.N = Vector((math.cos(t), 0.0, math.sin(t)))      # toward the pilot
        self.U = Vector((0.0, 1.0, 0.0))

    def p(self, u, v, d=0.0):
        return tuple(self.o + self.U * (u / 1000.0) + self.D * (v / 1000.0) + self.N * d)


def pbox(b, ps, rect, d0, d1, region=None, front="black", side="black", mat=0, uvf=None):
    """Box on the panel: rect (u0, v0, u1, v1) mm, depth d0..d1 m.

    The front face is mapped planar into the MIP texture region (so painted
    legends land on it) or gets a swatch; the sides get a swatch.
    """
    u0, v0, u1, v1 = rect
    q = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    back = [ps.p(u, v, d0) for u, v in q]
    fr = [ps.p(u, v, d1) for u, v in q]
    r0 = b.ring(back)
    r1 = b.ring(fr)
    m = b.mark()
    b.bridge(r0, r1, mat)
    b.cap(r0[::-1], mat)
    b.paint(m, SW(side))
    if uvf is not None:
        uv = [uvf(u, v) for u, v in q]
    else:
        uv = [L.mip_uv(region, u, v) for u, v in q] if region else SW(front)
    b.face(r1, mat, uv)


def pcyl(b, ps, c, r, d0, d1, uv, n=14, mat=0, taper=1.0):
    """Cylinder (knob, gauge case) along the panel normal."""
    m = b.mark()
    b.revolve(ps.p(c[0], c[1], d0), ps.p(c[0], c[1], d1), [(0, r / 1000.0), (1, r * taper / 1000.0)],
              n=n, mat=mat)
    b.paint(m, uv)


def pdisc(b, ps, c, r, d, uv_centre, uv_radius, n=32, mat=0):
    """Flat disc facing the pilot, UV mapped as a circle (gauge faces)."""
    pts, uvs = [], []
    for k in range(n):
        a = 2 * math.pi * k / n
        pts.append(ps.p(c[0] + r * math.cos(a), c[1] - r * math.sin(a), d))
        uvs.append((uv_centre[0] + uv_radius * math.cos(a), uv_centre[1] + uv_radius * math.sin(a)))
    b.face(b.ring(pts), mat, uvs)


def gauge_uv(face):
    """Centre and radius (UV units) of a gauge face in the atlas."""
    cx, cy = L.gauge_centre_px(face)
    return (cx / L.ATLAS, 1 - cy / L.ATLAS), 96 / L.ATLAS


# ----------------------------------------------------------------------------
# cockpit opening
# ----------------------------------------------------------------------------
def cut_cockpit(h, fus):
    """Boolean the cockpit tub (and the foot well under the panel) out of the
    fuselage.  The cutter's faces become the tub walls and floor."""
    x0, x1 = h.cockpit_x
    xs = [x0 - 0.50, x0 - 0.021, x0 - 0.02] + list(np.arange(x0, x1, 0.05)) + [x1]
    rings = []
    for x in xs:
        if x < x0 - 0.02:                       # foot well below the panel
            hw, top = 0.30, 0.56
        else:
            w, _ = h.canopy(min(max(x, h.canopy.x[0]), h.canopy.x[-1]))
            hw, top = min(w - 0.016, 0.40), 3.0
        fl = h.floor_z(x)
        r = 0.05
        ring = [(x, -hw, top), (x, hw, top)]
        for k in range(5):                       # rounded floor corners
            a = math.pi / 2 * k / 4
            ring.append((x, hw - r + r * math.cos(a), fl + r - r * math.sin(a)))
        for k in range(5):
            a = math.pi / 2 + math.pi / 2 * k / 4
            ring.append((x, -hw + r + r * math.cos(a), fl + r - r * math.sin(a)))
        rings.append(ring)
    from fa18_hornet import Builder
    b = Builder()
    b.loft(rings)
    mesh = bpy.data.meshes.new("cockpit_cutter")
    from fa18_hornet import to_blender
    inv = h.world[fus.name].inverted()
    mesh.from_pydata([tuple(inv @ to_blender(p)) for p in b.verts], [], b.faces)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)      # outward, or the cut inverts
    bm.to_mesh(mesh)
    bm.free()
    from fa18_hornet import material
    mesh.materials.append(material("CockpitWall"))
    cutter = bpy.data.objects.new("cockpit_cutter", mesh)
    bpy.context.scene.collection.objects.link(cutter)
    cutter.matrix_world = fus.matrix_world.copy()
    if material("CockpitWall").name not in [m.name for m in fus.data.materials]:
        fus.data.materials.append(material("CockpitWall"))
    mod = fus.modifiers.new("cockpit", "BOOLEAN")
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


# ----------------------------------------------------------------------------
# builder
# ----------------------------------------------------------------------------
class Cockpit:
    def __init__(self, h):
        self.h = h
        from fa18_hornet import Builder
        self.Builder = Builder

    def add(self, name, b, **kw):
        kw.setdefault("mats", ("Cockpit",))
        kw.setdefault("collection", self.h.col_cockpit)
        kw.setdefault("smooth", 35.0)
        return self.h.add(name, b, **kw)

    # -- instrument panel ------------------------------------------------------
    def panel(self, st):
        h = self.h
        tag = st["name"]
        region = "front_mip" if tag == "Front" else "rear_mip"
        layout = L.FRONT_MIP if tag == "Front" else L.REAR_MIP
        ps = st["ps"]
        b = self.Builder()

        # panel plate: outline polygon, 15 mm thick, upper corners clipped
        # so they stay inside the canopy bow
        outline = self.clipped_outline(st)
        front = [ps.p(u, v, 0.0) for u, v in outline]
        back = [ps.p(u, v, -0.015) for u, v in outline]
        rf, rb = b.ring(front), b.ring(back)
        m = b.mark()
        b.bridge(rb, rf)
        b.paint(m, SW("black"))
        b.face(rf, 0, [L.mip_uv(region, u, v) for u, v in outline])
        b.face(rb[::-1], 0, SW("black"))

        displays = []
        self.items(b, ps, layout, lambda u, v: L.mip_uv(region, u, v), displays)
        self.add("Panel_" + tag, b)
        self.displays(st, displays)

    def items(self, b, ps, layout, uvf, displays):
        """Panel items on the face of PanelSpace ps; uvf maps (u, v) mm to the
        atlas for faces that carry painted legends."""
        for e in layout:
            k = e["kind"]
            if k == "plate":
                pbox(b, ps, e["rect"], -0.005, 0.004, uvf=uvf)
            elif k == "placard":
                pbox(b, ps, e["rect"], -0.003, 0.003, uvf=uvf)
            elif k == "caution":
                pbox(b, ps, e["rect"], -0.003, 0.008, uvf=uvf)
            elif k == "button":
                u0, v0, u1, v1 = e["rect"]
                pbox(b, ps, (u0 + 1, v0 + 1, u1 - 1, v1 - 1), 0.0, 0.010, uvf=uvf)
            elif k == "toggle":
                u, v = e["c"]
                pcyl(b, ps, (u, v), 6, 0.0, 0.006, SW("metal"), n=10)
                m = b.mark()
                b.revolve(ps.p(u, v, 0.004), ps.p(u, v - 6, 0.028), [(0, 0.0022), (1, 0.0018)], n=8)
                b.paint(m, SW("metal"))
            elif k == "knob":
                u, v = e["c"]
                r = e["r"]
                pcyl(b, ps, (u, v), r, 0.0, 0.012, SW("black"), n=16, taper=0.85)
                pbox(b, ps, (u - 1, v - r * 0.8, u + 1, v - r * 0.2), 0.012, 0.0125, front="white")
            elif k == "lcd":
                pbox(b, ps, e["rect"], -0.004, 0.001, uvf=uvf)
            elif k == "gauge":
                u, v = e["c"]
                r = e["r"]
                # case rim proud of the sub-panel plate (front at d = 4 mm), face 4 mm inside the rim
                m = b.mark()
                b.revolve(ps.p(u, v, 0.0), ps.p(u, v, 0.014),
                          [(0, (r + 4) / 1000), (0.6, (r + 4) / 1000), (1, (r + 1) / 1000)], n=32,
                          caps=(True, False))                  # open at the front: the dial shows
                b.paint(m, SW("black"))
                uc, ur = gauge_uv(e["face"])
                pdisc(b, ps, (u, v), r, 0.0095, uc, ur)
            elif k == "wheel":                                   # landing-gear handle, down
                u, v = e["c"]
                m = b.mark()
                b.revolve(ps.p(u, v, 0.002), ps.p(u, v, 0.075), [(0, 0.007), (1, 0.006)], n=10)
                b.paint(m, SW("metal"))
                m = b.mark()
                b.revolve(ps.p(u - 10, v, 0.082), ps.p(u + 10, v, 0.082),
                          [(0, 0.012), (0.2, 0.022), (0.8, 0.022), (1, 0.012)], n=18)
                b.paint(m, SW("white"))
            elif k in ("tee", "fold"):                           # pull handles: stem and a T bar
                u, v = e["c"]
                w = 18 if (k == "fold" or e.get("small")) else 30
                L_ = 0.045 if k == "tee" else 0.06
                m = b.mark()
                b.revolve(ps.p(u, v, 0.002), ps.p(u, v, L_), [(0, 0.005), (1, 0.0045)], n=8)
                b.paint(m, SW("metal"))
                m = b.mark()
                b.revolve(ps.p(u - w, v, L_ + 0.008), ps.p(u + w, v, L_ + 0.008),
                          [(0, 0.006), (0.12, 0.009), (0.88, 0.009), (1, 0.006)], n=10)
                b.paint(m, SW("stripe" if k == "tee" else "black"))
            elif k == "hook":                                    # arresting-hook handle, up
                u, v = e["c"]
                m = b.mark()
                b.revolve(ps.p(u, v, 0.002), ps.p(u, v, 0.05), [(0, 0.006), (1, 0.005)], n=8)
                b.paint(m, SW("metal"))
                m = b.mark()
                b.revolve(ps.p(u, v - 6, 0.056), ps.p(u, v + 34, 0.056), [(0, 0.010), (0.7, 0.011), (1, 0.006)], n=10)
                b.paint(m, SW("yellow"))
            elif k == "lever":                                   # command selector valve
                u, v = e["c"]
                pcyl(b, ps, (u, v), 16, 0.0, 0.008, SW("black"), n=16)
                m = b.mark()
                b.revolve(ps.p(u, v, 0.008), ps.p(u, v - 34, 0.018), [(0, 0.006), (1, 0.005)], n=8)
                b.paint(m, SW("yellow"))
            elif k == "ddi":
                self.bezel(b, ps, e, uvf, depth=0.032)
                displays.append((e["name"], e["screen"], 0.022))
            elif k == "hsd":
                self.bezel(b, ps, e, uvf, depth=0.030)
                displays.append((e["name"], e["screen"], 0.020))
            elif k == "ufc":
                self.ufc(b, ps, e, uvf)
                displays.append(("UFC", None, 0.0))

    def subpanels(self, st):
        """Knee panels and the centre pedestal below the instrument panel."""
        ps = st["ps"]
        b = self.Builder()
        for sp in L.SUBPANELS[st["name"]]:
            region, rect = sp["region"], sp["rect"]
            uvf = (lambda rg, rc: (lambda u, v: L.sub_uv(rg, rc, u, v)))(region, rect)
            pbox(b, ps, rect, -0.015, 0.0, uvf=uvf)
            self.items(b, ps, sp["items"], uvf, [])
        self.add("LowerPanels_" + st["name"], b)

    def clipped_outline(self, st):
        """MIP outline with any point outside the canopy's inner arch (bow
        frame included) moved down the panel until it is inside."""
        h, ps = self.h, st["ps"]
        out = []
        for u, v in L.MIP_OUTLINE:
            for _ in range(60):
                p = Vector(ps.p(u, v, 0.05))
                xs = [p.x]
                if st["name"] == "Front":
                    xs += [h.bows[0] + 0.01, h.bows[0] + 0.07]
                lim = min([h.arch_halfwidth(x, p.z + 0.01, -0.032) for x in xs] +
                          [h.cockpit_halfwidth(p.x) - 0.004])
                if abs(p.y) <= lim:
                    break
                u -= 2 if u > 0 else -2          # pull inboard only; the top edge stays put
            out.append((u, v))
        return out

    def bezel(self, b, ps, e, uvf, depth):
        """Display bezel with a recessed screen opening and push buttons."""
        u0, v0, u1, v1 = e["rect"]
        s0, t0, s1, t1 = e["screen"]
        d = depth
        # outer box sides
        q = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        r0 = b.ring([ps.p(u, v, 0.0) for u, v in q])
        r1 = b.ring([ps.p(u, v, d) for u, v in q])
        m = b.mark()
        b.bridge(r0, r1)
        b.paint(m, SW("black"))
        # front frame around the screen (4 quads), planar-mapped
        inner = [(s0, t0), (s1, t0), (s1, t1), (s0, t1)]
        for i in range(4):
            j = (i + 1) % 4
            pts = [q[i], q[j], inner[j], inner[i]]
            b.poly([ps.p(u, v, d) for u, v in pts], 0, [uvf(u, v) for u, v in pts])
        # screen well
        wi = b.ring([ps.p(u, v, d) for u, v in inner])
        wo = b.ring([ps.p(u, v, d - 0.012) for u, v in inner])
        m = b.mark()
        b.bridge(wi, wo)
        b.paint(m, SW("black"))
        pos = L.bezel_buttons(e)
        for u, v in pos:
            pbox(b, ps, (u - 7, v - 7, u + 7, v + 7), d, d + 0.007, side="darkgrey", uvf=uvf)
        for u, v, r, _ in e.get("knobs", []):
            pcyl(b, ps, (u, v), r, d, d + 0.012, SW("black"), n=14, taper=0.85)
            pbox(b, ps, (u - 1, v - r * 0.8, u + 1, v - r * 0.2), d + 0.012, d + 0.0125, front="white")

    def ufc(self, b, ps, e, uvf):
        """Up-front control panel: raised box, keypad, option buttons, knobs."""
        D = 0.045
        pbox(b, ps, e["rect"], 0.0, D, uvf=uvf)
        o = e["keypad"]["origin"]
        pu, pv = e["keypad"]["pitch"]
        for r, row in enumerate(e["keypad"]["rows"]):
            for c, _ in enumerate(row):
                u = o[0] + c * pu + 9
                v = o[1] + r * pv + 9
                pbox(b, ps, (u - 9, v - 9, u + 9, v + 9), D, D + 0.008, side="darkgrey", uvf=uvf)
        for u, v in e["option_buttons"]:
            pcyl(b, ps, (u, v), 6, D, D + 0.006, SW("darkgrey"), n=12)
        fu0, fv0, fu1, fv1 = e["function_row"]
        n = len(e["functions"])
        w = (fu1 - fu0) / n
        for i in range(n):
            pbox(b, ps, (fu0 + i * w + 2, fv0, fu0 + (i + 1) * w - 2, fv1), D, D + 0.006,
                 side="darkgrey", uvf=uvf)
        for u, v, r, _ in e["knobs"]:
            pcyl(b, ps, (u, v), r, D, D + 0.012, SW("black"), n=14, taper=0.85)

    def displays(self, st, displays):
        """Screens as separate objects with 0..1 UVs, one material each, so a
        game can swap in live render textures."""
        ps = st["ps"]
        tag = st["name"]
        layout = L.FRONT_MIP if tag == "Front" else L.REAR_MIP
        for name, rect, d in displays:
            b = self.Builder()
            if name == "UFC":
                e = next(x for x in layout if x["kind"] == "ufc")
                D = 0.045 + 0.0006
                rects = [e["scratchpad"]] + e["options"]
                # the UFC display texture holds the scratchpad on top and the
                # five option windows below it
                for i, (u0, v0, u1, v1) in enumerate(rects):
                    ty0, ty1 = (0.0, 0.2) if i == 0 else (0.2 + 0.16 * (i - 1), 0.2 + 0.16 * i)
                    pts = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
                    b.poly([ps.p(u, v, D) for u, v in pts], 0,
                           [(0, 1 - ty0), (1, 1 - ty0), (1, 1 - ty1), (0, 1 - ty1)])
                mat = "Display_UFC"
            else:
                u0, v0, u1, v1 = rect
                pts = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
                b.poly([ps.p(u, v, d - 0.011) for u, v in pts], 0, [(0, 1), (1, 1), (1, 0), (0, 0)])
                mat = "Display_" + name
            o = self.add("%s_%s" % (name, tag), b, mats=(mat,), smooth=None)
            o["display"] = name

    # -- glareshield and HUD -----------------------------------------------------
    def glareshield(self, st):
        """Flat-black coaming over the panel, running forward under the
        windscreen; the HUD sits on it for the front cockpit."""
        h, ps = self.h, st["ps"]
        tag = st["name"]
        b = self.Builder()
        outline = self.clipped_outline(st)[:15]            # upper arch
        x_fwd = st["coaming_fwd"]
        rings = []
        lip = []
        hud_ref = [Vector(ps.p(u, v - 4, 0.045)) for u, v in outline]   # HUD and indexer placement
        for u, v in outline:
            p = Vector(ps.p(u, v - 4, 0.028))              # lip overhangs the panel, clear of the top light rows
            lip.append(p)
        top, bot = [], []
        for p in lip:
            f = Vector((x_fwd, p.y * 0.72, p.z - 0.01))
            top.append([p + Vector((0, 0, 0.012)), f + Vector((0, 0, 0.012))])
            # the underside drops to the nose skin so the coaming reads as a
            # solid hump through the windscreen
            fb = Vector((f.x, f.y, min(f.z, h.core_top_z(f.x, f.y) - 0.02)))
            bot.append([p - Vector((0, 0, 0.008)), fb])
        # top surface and underside as two strips joined at the edges
        n = len(lip)
        rt = b.ring([t[0] for t in top] + [t[1] for t in top][::-1])
        rb = b.ring([t[0] for t in bot] + [t[1] for t in bot][::-1])
        m = b.mark()
        b.bridge(rt, rb)
        b.cap(rt)
        b.cap(rb[::-1])
        b.paint(m, SW("black"))
        self.add("Glareshield_" + tag, b)

        # standby magnetic compass at the right end of the coaming (FO-1 item 19,
        # FO-2 item 7): a small case with its card window facing aft
        b = self.Builder()
        q = lip[9] + Vector((-0.06, 0.0, 0.012))
        m = b.mark()
        b.box([tuple(q + Vector(v)) for v in ((-0.03, -0.025, 0), (0.0, -0.025, 0), (0.0, 0.025, 0), (-0.03, 0.025, 0),
                                              (-0.03, -0.025, 0.05), (0.0, -0.025, 0.05), (0.0, 0.025, 0.05),
                                              (-0.03, 0.025, 0.05))])
        b.paint(m, SW("black"))
        m = b.mark()
        b.revolve(tuple(q + Vector((0.0, 0, 0.026))), tuple(q + Vector((0.006, 0, 0.026))), [(0, 0.017), (1, 0.017)], n=16)
        b.paint(m, SW("glass"))
        self.add("StandbyCompass_" + tag, b)

        if not st["hud"]:
            return
        # HUD: body on the coaming, two side posts, tilted combiner glass
        b = self.Builder()
        zc = hud_ref[7].z + 0.012
        xl = hud_ref[7].x
        m = b.mark()
        b.box([(xl - 0.30, -0.085, zc - 0.02), (xl - 0.02, -0.085, zc - 0.02),
               (xl - 0.02, 0.085, zc - 0.02), (xl - 0.30, 0.085, zc - 0.02),
               (xl - 0.30, -0.085, zc + 0.055), (xl - 0.06, -0.085, zc + 0.055),
               (xl - 0.06, 0.085, zc + 0.055), (xl - 0.30, 0.085, zc + 0.055)])
        # exit lens
        b.revolve((xl - 0.17, 0.0, zc + 0.055), (xl - 0.17, 0.0, zc + 0.07), [(0, 0.06), (1, 0.055)], n=20)
        b.paint(m, SW("black"))
        tilt = math.radians(15)
        gb = Vector((xl - 0.10, 0.0, zc + 0.065))           # combiner bottom centre
        up = Vector((math.sin(tilt), 0.0, math.cos(tilt)))  # leans aft at the top
        hgt = 0.165
        for side in (-1, 1):                                # side posts
            m = b.mark()
            a = gb + Vector((0, side * 0.098, -0.04))
            c = gb + up * hgt + Vector((0, side * 0.108, 0))
            b.revolve(tuple(a), tuple(c), [(0, 0.009), (1, 0.007)], n=6)
            b.paint(m, SW("black"))
        m = b.mark()                                        # top cross bar
        b.revolve(tuple(gb + up * (hgt + 0.006) + Vector((0, -0.11, 0))),
                  tuple(gb + up * (hgt + 0.006) + Vector((0, 0.11, 0))), [(0, 0.004), (1, 0.004)], n=6)
        b.paint(m, SW("darkgrey"))
        self.add("HUD_" + tag, b)
        st["hud_glass"] = (gb, up, hgt)

        b = self.Builder()
        g0, g1 = gb + Vector((0, -0.085, 0)), gb + Vector((0, 0.085, 0))
        g3, g2 = gb + up * hgt + Vector((0, -0.10, 0)), gb + up * hgt + Vector((0, 0.10, 0))
        b.poly([tuple(g0), tuple(g1), tuple(g2), tuple(g3)], 0, [(0.075, 0), (0.925, 0), (1, 1), (0, 1)])
        o = self.add("HUD_Combiner_" + tag, b, mats=("Display_HUD",), smooth=None)
        o["display"] = "HUD"

        # angle-of-attack indexer left of the HUD (FO-1 item 3: green high AOA,
        # amber on speed, red low AOA); the lock / shoot lights are on the canopy bow
        b = self.Builder()
        for yc, lights in ((-0.118, ("green", "amber", "red")),):
            n = len(lights)
            hgt = 0.019 * n + 0.008
            z0 = zc - 0.02
            m = b.mark()
            b.box([(xl - 0.05, yc - 0.018, z0), (xl - 0.012, yc - 0.018, z0), (xl - 0.012, yc + 0.018, z0),
                   (xl - 0.05, yc + 0.018, z0), (xl - 0.05, yc - 0.018, z0 + hgt), (xl - 0.012, yc - 0.018, z0 + hgt),
                   (xl - 0.012, yc + 0.018, z0 + hgt), (xl - 0.05, yc + 0.018, z0 + hgt)])
            b.paint(m, SW("black"))
            for k, col in enumerate(lights):
                zl = z0 + hgt - 0.006 - 0.019 * (k + 1)
                xf = xl - 0.0115
                b.poly([(xf, yc - 0.012, zl), (xf, yc + 0.012, zl), (xf, yc + 0.012, zl + 0.014), (xf, yc - 0.012, zl + 0.014)],
                       0, SW(col))
        self.add("AOAIndexer_" + tag, b)

    # -- consoles and controls ---------------------------------------------------
    def consoles(self, st):
        """Left and right consoles, panel by panel from cockpit_layout.CONSOLES
        (NATOPS FO-1 / FO-2 sheet 2), with the throttles on the left."""
        h = self.h
        tag = st["name"]
        x0, x1 = st["console_x"]
        zt = st["console_z"]
        L_ = x1 - x0
        b = self.Builder()
        wall = h.cockpit_halfwidth(x0 + 0.05)
        regions = L.CONSOLE_REGIONS[tag]
        for side, region, panels in ((-1, regions[0], L.CONSOLES[tag]["L"]), (1, regions[1], L.CONSOLES[tag]["R"])):
            yo, yi = side * (wall + 0.01), side * (wall - L.CONSOLE_WIDTH / 1000)
            fl = h.floor_z(x0)
            # body (top face mapped to the console texture)
            pts_top = [(x0, yo, zt), (x1, yo, zt + 0.02), (x1, yi, zt + 0.02), (x0, yi, zt)]
            uv_top = [L.region_uv(region, 0 if side < 0 else 1, 0), L.region_uv(region, 0 if side < 0 else 1, L_ / 1.1),
                      L.region_uv(region, 1 if side < 0 else 0, L_ / 1.1), L.region_uv(region, 1 if side < 0 else 0, 0)]
            b.poly(pts_top, 0, uv_top)
            for a, c in ((pts_top[3], pts_top[2]), (pts_top[0], pts_top[3]), (pts_top[2], pts_top[1])):
                b.poly([a, c, (c[0], c[1], fl), (a[0], a[1], fl)], 0, SW("darkgrey"))

            def at(s_mm, t_mm):
                return Vector((x0 + s_mm / 1000, yo - side * t_mm / 1000, zt + 0.02 * s_mm / 1000 / L_))

            for pnl in panels:
                s0, s1 = pnl["s"]
                t0, t1 = pnl.get("t", (0, L.CONSOLE_WIDTH))
                for c in pnl.get("controls", []):
                    kind, fs, ft = c[:3]
                    ft = ft if side < 0 else 1.0 - ft          # across: from the pilot's left on both consoles
                    p = at(s0 + fs * (s1 - s0), t0 + ft * (t1 - t0))
                    up = Vector((0, 0, 1))
                    if kind == "toggle":
                        m = b.mark()
                        b.revolve(tuple(p), tuple(p + up * 0.006), [(0, 0.006), (1, 0.0055)], n=10)
                        b.paint(m, SW("metal"))
                        m = b.mark()
                        b.revolve(tuple(p + up * 0.004), tuple(p + Vector((0.006, 0, 0.026))), [(0, 0.0022), (1, 0.0018)], n=8)
                        b.paint(m, SW("metal"))
                    elif kind == "knob":
                        m = b.mark()
                        b.revolve(tuple(p), tuple(p + up * 0.014), [(0, 0.009), (1, 0.0075)], n=12)
                        b.paint(m, SW("black"))
                        m = b.mark()                                   # pointer line
                        b.box([tuple(p + Vector(v)) for v in ((-0.007, -0.001, 0.014), (-0.002, -0.001, 0.014),
                                                              (-0.002, 0.001, 0.014), (-0.007, 0.001, 0.014),
                                                              (-0.007, -0.001, 0.0145), (-0.002, -0.001, 0.0145),
                                                              (-0.002, 0.001, 0.0145), (-0.007, 0.001, 0.0145))])
                        b.paint(m, SW("white"))
                    elif kind == "button":
                        m = b.mark()
                        b.box([tuple(p + Vector(v)) for v in ((-0.007, -0.007, 0), (0.007, -0.007, 0), (0.007, 0.007, 0),
                                                              (-0.007, 0.007, 0), (-0.006, -0.006, 0.007), (0.006, -0.006, 0.007),
                                                              (0.006, 0.006, 0.007), (-0.006, 0.006, 0.007))])
                        b.paint(m, SW("darkgrey"))
                    elif kind == "gauge":
                        r = 0.024
                        m = b.mark()
                        b.revolve(tuple(p), tuple(p + up * 0.012), [(0, r + 0.004), (0.6, r + 0.004), (1, r + 0.001)],
                                  n=28, caps=(True, False))
                        b.paint(m, SW("black"))
                        uc, ur = gauge_uv(c[4])
                        pts, uvs = [], []
                        for k in range(28):
                            a = 2 * math.pi * k / 28
                            pts.append(tuple(p + Vector((-r * math.sin(a), r * math.cos(a), 0.008))))
                            uvs.append((uc[0] + ur * math.cos(a), uc[1] + ur * math.sin(a)))
                        b.face(b.ring(pts), 0, uvs)
                    elif kind == "handle":                              # striped pull handle on two posts
                        m = b.mark()
                        for ds in (-0.04, 0.04):
                            q = p + Vector((ds, 0, 0))
                            b.revolve(tuple(q), tuple(q + up * 0.03), [(0, 0.005), (1, 0.005)], n=8)
                        b.paint(m, SW("metal"))
                        m = b.mark()
                        b.revolve(tuple(p + Vector((-0.055, 0, 0.034))), tuple(p + Vector((0.055, 0, 0.034))),
                                  [(0, 0.008), (0.1, 0.011), (0.9, 0.011), (1, 0.008)], n=10)
                        b.paint(m, SW("stripe"))
        self.add("Consoles_" + tag, b)

        # throttle quadrant (left console): two grips on short levers
        thr = next(p for p in L.CONSOLES[tag]["L"] if p.get("throttle"))
        s0, s1 = thr["s"]
        t0, t1 = thr["t"]
        yo = -(wall + 0.01)
        b = self.Builder()
        ys = [yo + (t0 + 0.28 * (t1 - t0)) / 1000, yo + (t0 + 0.74 * (t1 - t0)) / 1000]
        for i, y in enumerate(ys):
            xb = x0 + (s0 + s1) / 2000
            m = b.mark()
            b.box([(xb - 0.03, y - 0.012, zt), (xb + 0.03, y - 0.012, zt), (xb + 0.03, y + 0.012, zt),
                   (xb - 0.03, y + 0.012, zt), (xb - 0.05, y - 0.010, zt + 0.10), (xb - 0.01, y - 0.010, zt + 0.10),
                   (xb - 0.01, y + 0.010, zt + 0.10), (xb - 0.05, y + 0.010, zt + 0.10)])
            b.paint(m, SW("darkgrey"))
            m = b.mark()                                # grip
            gw = 0.022 if i == 0 else 0.019
            b.box([(xb - 0.075, y - gw, zt + 0.095), (xb + 0.005, y - gw, zt + 0.095),
                   (xb + 0.005, y + gw, zt + 0.095), (xb - 0.075, y + gw, zt + 0.095),
                   (xb - 0.07, y - gw, zt + 0.15), (xb - 0.005, y - gw, zt + 0.16),
                   (xb - 0.005, y + gw, zt + 0.16), (xb - 0.07, y + gw, zt + 0.15)])
            b.paint(m, SW("rubber"))
            for k in range(3):                           # HOTAS switches
                m = b.mark()
                b.revolve((xb - 0.06 + 0.02 * k, y, zt + 0.152), (xb - 0.06 + 0.02 * k, y, zt + 0.165),
                          [(0, 0.005), (1, 0.004)], n=8)
                b.paint(m, SW("black"))
        # quadrant slot plate
        m = b.mark()
        xb0, xb1 = x0 + s0 / 1000, x0 + s1 / 1000
        ya, yb = yo + t0 / 1000 + 0.004, yo + t1 / 1000 - 0.004
        b.box([(xb0, ya, zt + 0.003), (xb1, ya, zt + 0.003), (xb1, yb, zt + 0.003), (xb0, yb, zt + 0.003),
               (xb0, ya, zt + 0.012), (xb1, ya, zt + 0.012), (xb1, yb, zt + 0.012), (xb0, yb, zt + 0.012)])
        b.paint(m, SW("black"))
        self.add("Throttles_" + tag, b)

        # control stick: boot, column, Hornet grip with trigger guard and hat
        sx, sz = st["stick"]
        fl = h.floor_z(sx)
        b = self.Builder()
        m = b.mark()
        b.revolve((sx + 0.02, 0, fl), (sx + 0.01, 0, fl + 0.10), [(0, 0.075), (0.5, 0.055), (1, 0.03)], n=16)
        b.paint(m, SW("rubber"))
        m = b.mark()
        b.revolve((sx + 0.01, 0, fl + 0.09), (sx - 0.02, 0, sz - 0.11), [(0, 0.016), (1, 0.014)], n=12)
        b.paint(m, SW("metal"))
        m = b.mark()
        b.revolve((sx - 0.02, 0, sz - 0.12), (sx - 0.05, 0, sz), [(0, 0.020), (0.4, 0.024), (0.85, 0.022), (1, 0.017)],
                  n=14)
        b.paint(m, SW("rubber"))
        m = b.mark()                                       # trigger and guard
        b.box([(sx - 0.075, -0.006, sz - 0.08), (sx - 0.045, -0.006, sz - 0.08),
               (sx - 0.045, 0.006, sz - 0.08), (sx - 0.075, 0.006, sz - 0.08),
               (sx - 0.08, -0.006, sz - 0.05), (sx - 0.05, -0.006, sz - 0.05),
               (sx - 0.05, 0.006, sz - 0.05), (sx - 0.08, 0.006, sz - 0.05)])
        b.revolve((sx - 0.055, -0.02, sz + 0.002), (sx - 0.055, 0.02, sz + 0.002), [(0, 0.008), (1, 0.008)], n=8)
        b.paint(m, SW("black"))
        self.add("Stick_" + tag, b)

        # rudder pedals
        px = st["pedal_x"]
        b = self.Builder()
        for side in (-1, 1):
            y = side * 0.13
            pz = h.floor_z(px) + 0.17
            m = b.mark()
            b.box([(px, y - 0.05, pz - 0.09), (px, y + 0.05, pz - 0.09), (px - 0.03, y + 0.05, pz + 0.09),
                   (px - 0.03, y - 0.05, pz + 0.09), (px + 0.015, y - 0.05, pz - 0.09),
                   (px + 0.015, y + 0.05, pz - 0.09), (px - 0.015, y + 0.05, pz + 0.09),
                   (px - 0.015, y - 0.05, pz + 0.09)])
            b.paint(m, SW("darkgrey"))
            m = b.mark()
            b.revolve((px - 0.12, y, pz - 0.05), (px - 0.005, y, pz - 0.02), [(0, 0.015), (1, 0.012)], n=8)
            b.paint(m, SW("metal"))
        self.add("RudderPedals_" + tag, b)

    # -- ejection seat ---------------------------------------------------------
    def seat(self, st):
        """Martin-Baker SJU-5/A (front) / SJU-6/A (rear) seat, simplified to
        the shapes visible from the cockpit and outside."""
        srp = Vector(st["srp"])
        back_ang = math.radians(18.0)
        up = Vector((math.sin(back_ang), 0, math.cos(back_ang)))       # along the seat back
        fwd = Vector((-math.cos(back_ang), 0, math.sin(back_ang)))     # out of the seat back
        Y = Vector((0, 1, 0))

        def P(a, s, f):
            """a along the back (m), s sideways, f forward of the back line."""
            return tuple(srp + up * a + Y * s + fwd * f)

        def blk(b, a0, a1, s0, s1, f0, f1, uv="black", taper=0.0):
            m = b.mark()
            b.box([P(a0, s0, f0), P(a0, s1, f0), P(a0, s1, f1), P(a0, s0, f1),
                   P(a1, s0 + taper, f0), P(a1, s1 - taper, f0), P(a1, s1 - taper, f1), P(a1, s0 + taper, f1)])
            b.paint(m, SW(uv))

        b = self.Builder()
        # back: parachute container and back pad
        blk(b, 0.02, 0.70, -0.20, 0.20, -0.20, -0.02, "darkgrey")
        blk(b, 0.04, 0.66, -0.18, 0.18, -0.02, 0.035, "cushion")
        # headbox with headrest pad
        blk(b, 0.70, 0.93, -0.17, 0.17, -0.24, 0.03, "black", taper=0.05)
        blk(b, 0.72, 0.88, -0.11, 0.11, 0.03, 0.08, "leather")
        # side frames / main beams
        for s in (-1, 1):
            blk(b, -0.45, 0.99, s * 0.20 - 0.02, s * 0.20 + 0.02, -0.26, -0.05, "darkgrey")
            # gas-generator / drogue-gun cylinders beside the headbox
            m = b.mark()
            b.revolve(P(0.55, s * 0.195, -0.12), P(0.94, s * 0.195, -0.12), [(0, 0.026), (1, 0.026)], n=12)
            b.paint(m, SW("black"))
        # seat bucket and survival-kit cushion (pan rises 6 deg toward the knees)
        pan_up = math.radians(6.0)
        pf = Vector((-math.cos(pan_up), 0, math.sin(pan_up)))

        def Q(f, s, z):
            return tuple(srp + pf * f + Y * s + Vector((0, 0, z)))

        m = b.mark()
        b.box([Q(-0.05, -0.23, -0.20), Q(0.44, -0.23, -0.20), Q(0.44, 0.23, -0.20), Q(-0.05, 0.23, -0.20),
               Q(-0.05, -0.23, -0.01), Q(0.44, -0.23, -0.02), Q(0.44, 0.23, -0.02), Q(-0.05, 0.23, -0.01)])
        b.paint(m, SW("darkgrey"))
        m = b.mark()
        b.box([Q(0.0, -0.19, -0.02), Q(0.42, -0.19, -0.03), Q(0.42, 0.19, -0.03), Q(0.0, 0.19, -0.02),
               Q(0.0, -0.19, 0.035), Q(0.42, -0.19, 0.03), Q(0.42, 0.19, 0.03), Q(0.0, 0.19, 0.035)])
        b.paint(m, SW("cushion"))
        for s in (-1, 1):                                  # bucket sides
            m = b.mark()
            b.box([Q(-0.05, s * 0.23, -0.02), Q(0.40, s * 0.23, -0.02), Q(0.40, s * 0.20, -0.02),
                   Q(-0.05, s * 0.20, -0.02), Q(-0.05, s * 0.23, 0.12), Q(0.30, s * 0.23, 0.07),
                   Q(0.30, s * 0.20, 0.07), Q(-0.05, s * 0.20, 0.12)])
            b.paint(m, SW("darkgrey"))
        # canopy breakers on top of the headbox (NATOPS FO-9)
        for s in (-1, 1):
            m = b.mark()
            b.revolve(P(0.925, s * 0.07, -0.10), P(0.985, s * 0.07, -0.10), [(0, 0.012), (0.6, 0.008), (1, 0.003)], n=8)
            b.paint(m, SW("metal"))
        # SAFE / ARMED handle at the front left of the seat bucket (FO-9)
        m = b.mark()
        b.revolve(Q(0.30, -0.24, 0.07), Q(0.37, -0.255, 0.115), [(0, 0.009), (1, 0.009)], n=8)
        b.paint(m, SW("stripe"))
        self.add("Seat_" + st["name"], b)

        # harness (lies on the empty seat) and the firing handle
        b = self.Builder()
        for s in (-1, 1):
            m = b.mark()
            pts = [P(0.66, s * 0.10, 0.04), P(0.40, s * 0.11, 0.045), P(0.12, s * 0.12, 0.05)]
            for a, c in zip(pts, pts[1:]):
                a, c = Vector(a), Vector(c)
                w = Vector((0, 0.022, 0))
                n = fwd * 0.004
                b.box([tuple(a - w), tuple(a + w), tuple(c + w), tuple(c - w),
                       tuple(a - w + n), tuple(a + w + n), tuple(c + w + n), tuple(c - w + n)])
            # lap belt
            a, c = Vector(Q(0.05, s * 0.21, 0.04)), Vector(Q(0.20, s * 0.05, 0.04))
            b.box([tuple(a), tuple(a + Vector((0.04, 0, 0))), tuple(c + Vector((0.04, 0, 0))), tuple(c),
                   tuple(a + Vector((0, 0, 0.005))), tuple(a + Vector((0.04, 0, 0.005))),
                   tuple(c + Vector((0.04, 0, 0.005))), tuple(c + Vector((0, 0, 0.005)))])
            b.paint(m, SW("strap"))
        m = b.mark()
        hc = Vector(Q(0.455, 0, 0.0))                      # seat firing handle (front of the bucket)
        prev = None
        for k in range(9):
            a = math.pi * k / 8
            p = hc + Vector((0, 0.07 * math.cos(a), 0.05 * math.sin(a)))
            if prev is not None:
                b.revolve(tuple(prev), tuple(p), [(0, 0.008), (1, 0.008)], n=8)
            prev = p
        b.paint(m, SW("yellow"))
        self.add("SeatHarness_" + st["name"], b)

    # -- sidewalls, mirrors, eye points -----------------------------------------------
    def sills(self):
        """Perforated canopy-sill longerons along both sides of the opening."""
        h = self.h
        x0, x1 = h.cockpit_x
        b = self.Builder()
        xs = list(np.arange(x0, x1, 0.1)) + [x1]
        for side in (-1, 1):
            for xa, xb in zip(xs, xs[1:]):
                wa, wb = h.cockpit_halfwidth(xa), h.cockpit_halfwidth(xb)
                za, zb = h.sill_z(xa), h.sill_z(xb)
                ua = (xa - x0) / 1.6
                ub = (xb - x0) / 1.6
                pts = [(xa, side * (wa - 0.002), za - 0.14), (xb, side * (wb - 0.002), zb - 0.14),
                       (xb, side * (wb - 0.002), zb - 0.016), (xa, side * (wa - 0.002), za - 0.016)]
                uvs = [L.region_uv("rail", ua % 1.0 if ua < 1 else ua - 1, 1), L.region_uv("rail", ub % 1.0 if ub < 1 else ub - 1, 1),
                       L.region_uv("rail", ub % 1.0 if ub < 1 else ub - 1, 0), L.region_uv("rail", ua % 1.0 if ua < 1 else ua - 1, 0)]
                if (ua < 1) != (ub < 1):
                    uvs = SW("black")
                if callable(uvs):
                    b.poly(pts if side > 0 else pts[::-1], 0, uvs)
                else:
                    b.poly(pts if side > 0 else pts[::-1], 0, uvs if side > 0 else uvs[::-1])
        self.add("SillLongerons", b, smooth=None)

    def mirrors(self, canopy):
        """Three rear-view mirrors on the canopy front bow and the AIM-7
        LOCK / SHOOT lights, per the NASA layout drawing."""
        h = self.h
        xb = h.bows[0] + 0.07
        pts = h.canopy_arch(xb, -0.036)
        centre = Vector((xb, 0.0, h.core_top_z(xb) - 0.03))
        b = self.Builder()
        mir = self.Builder()

        def at(frac):
            """Point on the inner bow, frac 0 = right sill .. 1 = left sill."""
            i = frac * (len(pts) - 1)
            i0 = int(i)
            i1 = min(i0 + 1, len(pts) - 1)
            p = Vector(pts[i0]).lerp(Vector(pts[i1]), i - i0)
            t = (Vector(pts[i1]) - Vector(pts[max(i0 - 1, 0)])).normalized()
            inward = (centre - p)
            inward.x = 0
            return p, t, inward.normalized()

        for frac, wid in ((0.5, 0.13), (0.80, 0.08), (0.20, 0.08)):
            p, t, inn = at(frac)
            p0 = p + Vector((0.02, 0, 0)) + inn * 0.008
            hw = t * (wid / 2)
            hh = inn * 0.034
            dx = Vector((0.015, 0, 0))
            m = b.mark()
            b.box([tuple(p0 - hw), tuple(p0 + hw), tuple(p0 + hw + hh), tuple(p0 - hw + hh),
                   tuple(p0 - hw + dx), tuple(p0 + hw + dx), tuple(p0 + hw + hh + dx), tuple(p0 - hw + hh + dx)])
            b.paint(m, SW("black"))
            q = dx * 1.02
            mir.poly([tuple(p0 - hw + q), tuple(p0 + hw + q), tuple(p0 + hw + hh + q), tuple(p0 - hw + hh + q)],
                     0, [(0, 0), (1, 0), (1, 1), (0, 1)])
        # LOCK / SHOOT lights, right side of the bow
        p, t, inn = at(0.30)
        p0 = p + Vector((0.02, 0, 0)) + inn * 0.012
        hw, hh, dx = t * 0.012, inn * 0.05, Vector((0.025, 0, 0))
        m = b.mark()
        b.box([tuple(p0 - hw), tuple(p0 + hw), tuple(p0 + hw + hh), tuple(p0 - hw + hh),
               tuple(p0 - hw + dx), tuple(p0 + hw + dx), tuple(p0 + hw + hh + dx), tuple(p0 - hw + hh + dx)])
        b.paint(m, SW("black"))
        self.add("CanopyMirrorMounts", b, parent=canopy)
        self.add("CanopyMirrors", mir, mats=("Mirror",), parent=canopy, smooth=None)

    def eye_points(self, st):
        """Empty + camera at the design eye, looking forward along the
        aircraft axis (camera -Z = nose direction, +Y = up)."""
        from fa18_hornet import to_blender
        h = self.h
        ex, ez = st["eye"]
        loc = to_blender((ex, 0.0, ez))
        e = bpy.data.objects.new(h.prefix + "Eye_" + st["name"], None)
        e.empty_display_type = "SPHERE"
        e.empty_display_size = 0.05
        h.col_cockpit.objects.link(e)
        e.parent = h.root
        e.location = loc
        e.rotation_euler = (math.radians(90), 0, math.radians(180))
        e["purpose"] = "first-person eye point (-Z forward, +Y up)"
        cam_data = bpy.data.cameras.new(h.prefix + "Cam_" + st["name"])
        cam_data.lens_unit = "FOV"
        cam_data.angle = math.radians(80)
        cam_data.clip_start = 0.02
        cam = bpy.data.objects.new(h.prefix + "Cam_" + st["name"], cam_data)
        h.col_cockpit.objects.link(cam)
        cam.parent = e
        h.world[e.name] = Matrix.Identity(4)

    def enclosure(self, st):
        """Instrument box behind the rear panel, down to the floor: the
        bulkhead seen from the front seat."""
        h, ps = self.h, st["ps"]
        px = st["panel_x"]
        x0 = px - 0.25
        fl = h.floor_z(px)
        w, _ = h.canopy(px)
        hw = w - 0.045                                  # inside the canopy sill rails
        top = h.sill_z(px) - 0.012
        b = self.Builder()
        m = b.mark()
        b.box([(x0, -hw, fl), (px, -hw, fl), (px, hw, fl), (x0, hw, fl),
               (x0, -hw, top), (px - 0.02, -hw, top), (px - 0.02, hw, top), (x0, hw, top)])
        b.paint(m, SW("darkgrey"))
        self.add("PanelEnclosure_" + st["name"], b)

    def floor_plate(self, st):
        """Raised floor in the front foot well.  It roofs the nose-wheel bay:
        the retracted nose wheels (see build_gear and tools/setup_animations.py)
        reach 0.19 m, above the tub floor."""
        h = self.h
        x0, x1 = h.cockpit_x[0] - 0.49, h.cockpit_x[0] + 0.08
        z0, z1 = h.floor_z(x0) + 0.002, NOSE_BAY_ROOF_Z
        hw = 0.29
        b = self.Builder()
        m = b.mark()
        b.box([(x0, -hw, z0), (x1, -hw, z0), (x1, hw, z0), (x0, hw, z0),
               (x0, -hw, z1), (x1, -hw, z1), (x1, hw, z1), (x0, hw, z1)])
        b.paint(m, SW("darkgrey"))
        self.add("FloorPlate_" + st["name"], b)

    # -- entry point -------------------------------------------------------------
    def build(self, fus, canopy):
        h = self.h
        cut_cockpit(h, fus)
        for st in h.crew:
            ex, ez = st["eye"]
            px = st["panel_x"]
            st["panel_top"] = ez - 0.19              # glareshield just under the over-nose sight line
            st["ps"] = PanelSpace(px, st["panel_top"], 10.0)
            # seat reference point from the eye with an 18 deg seat back
            st["srp"] = (ex - 0.127, 0.0, ez - 0.779)
            sx, sz = st["srp"][0], st["srp"][2]
            st["coaming_fwd"] = 3.95 if st["name"] == "Front" else px - 0.25
            st["console_x"] = (px + L.CONSOLE_START, px + L.CONSOLE_START + L.CONSOLE_LEN / 1000)
            st["console_z"] = sz + 0.16          # low enough that the knee panels show over the console fronts
            st["stick"] = (sx - 0.30, sz + 0.24)
            st["pedal_x"] = sx - 0.72
            if st["name"] != "Front":
                self.enclosure(st)
            else:
                self.floor_plate(st)
            self.panel(st)
            self.subpanels(st)
            self.glareshield(st)
            self.consoles(st)
            self.seat(st)
            self.eye_points(st)
        self.sills()
        self.mirrors(canopy)
