"""Exterior details from the F/A-18A/B NATOPS flight manual (A1-F18AC-NFM-000):
exterior lights, air-data probes, the boarding ladder, the fuel dump masts and
the afterburner section behind the nozzles.

Called by Hornet.build() once the fuselage, wings, tail and gear exist (after
the bays are cut), so lenses and probes can be placed on the finished skin by
ray casts.  Everything here uses plain materials outside the baked atlases.

Where the manual says only roughly where a part is, the README lists it as
an approximate position.

Lights: each lens is geometry with an emissive material, and each light also
has a marker empty named "<prefix>Light_<kind>_<where>[_L|_R]" whose +Z axis
points where the light shines, with custom properties (light, colour, rgb,
source) for an engine to attach a light component to.
"""
import math

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from fa18_hornet import (Builder, to_blender, X_REF, Z_REF, GROUND_Z, NOSE_GEAR_X,
                         SEMI_SPAN, WING_APEX_X, WING_LE_TAN, FOLD_Y,
                         TIP_RAIL_Y, TIP_RAIL_REF_Y)

# light colours for the marker properties (linear RGB)
RGB = {"red": (1.0, 0.04, 0.02), "green": (0.05, 1.0, 0.2), "white": (1.0, 1.0, 0.95),
       "amber": (1.0, 0.5, 0.05), "formation": (0.55, 1.0, 0.25)}
LADDER_TILT = 10.0          # extended ladder leans this far forward of vertical (deg)
LADDER_WIDTH = 0.30


def from_blender(v):
    return Vector((v.y + X_REF, -v.x, v.z + Z_REF))


def normal_from_blender(n):
    return Vector((n.y, -n.x, n.z)).normalized()


class Exterior:
    def __init__(self, h):
        self.h = h
        self.trees = {}

    # -- skin queries -----------------------------------------------------------
    def tree(self, name):
        if name not in self.trees:
            o = self.h.objects[self.h.prefix + name]
            m = self.h.world[o.name]
            self.trees[name] = BVHTree.FromPolygons([m @ v.co for v in o.data.vertices],
                                                    [list(p.vertices) for p in o.data.polygons])
        return self.trees[name]

    def hit(self, name, origin, direction):
        """First point where a ray (design coords) meets object `name`, with the
        outward surface normal facing back along the ray."""
        o = to_blender(origin)
        d = Vector((-direction[1], direction[0], direction[2])).normalized()
        loc, nrm, _, _ = self.tree(name).ray_cast(o, d)
        if loc is None:
            raise RuntimeError("no skin hit on %s from %s along %s" % (name, origin, direction))
        n = normal_from_blender(nrm)
        dd = Vector(direction).normalized()
        if n.dot(dd) > 0:
            n = -n
        return from_blender(loc), n

    # -- small shapes -------------------------------------------------------------
    @staticmethod
    def dome(b, c, n, r, h, mat):
        """Lens dome standing on the skin at c, bulging along n."""
        c, n = Vector(c), Vector(n).normalized()
        b.revolve(c - n * 0.004, c + n * h, [(0.0, r), (0.4, r * 0.93), (0.75, r * 0.65), (1.0, r * 0.12)],
                  n=14, mat=mat)

    @staticmethod
    def strip(b, c, t, n, length, width, thick, mat):
        """Flat strip (formation light) lying on the skin: centre c, long
        direction t, outward normal n."""
        c, t, n = Vector(c), Vector(t).normalized(), Vector(n).normalized()
        w = n.cross(t).normalized()
        lo, hi = c - n * 0.003, c + n * thick
        loop = lambda base: [tuple(base + t * (sl * length / 2) + w * (sw * width / 2))
                             for sl, sw in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        b.box(loop(lo) + loop(hi), mat=mat)

    def marker(self, name, pos, aim, parent, light, colour, source, note=""):
        h = self.h
        e = bpy.data.objects.new(h.prefix + "Light_" + name, None)
        e.empty_display_type = "SINGLE_ARROW"
        e.empty_display_size = 0.25
        h.col.objects.link(e)
        z = Vector((-aim[1], aim[0], aim[2])).normalized()       # +Z: where it shines
        ref = Vector((0, 0, 1)) if abs(z.z) < 0.9 else Vector((1, 0, 0))
        x = ref.cross(z).normalized()
        y = z.cross(x)
        p = to_blender(pos)
        frame = Matrix(((x.x, y.x, z.x, p.x), (x.y, y.y, z.y, p.y), (x.z, y.z, z.z, p.z), (0, 0, 0, 1)))
        e.parent = parent
        e.matrix_parent_inverse = Matrix.Identity(4)
        e.matrix_basis = h.world[parent.name].inverted() @ frame
        h.world[e.name] = frame
        e["light"] = light
        e["colour"] = colour
        e["rgb"] = RGB[colour]
        e["source"] = source
        if note:
            e["note"] = note
        return e

    # -- lights -------------------------------------------------------------------
    def build_lights(self):
        h = self.h
        P = h.prefix
        root = h.root
        src_pos = "NATOPS 2.6.1.2 position lights"
        src_frm = "NATOPS 2.6.1.3 formation lights"
        src_stb = "NATOPS 2.6.1.4 strobe lights"
        te_hinge_x = lambda y: 11.76 + 0.041 * (y - 1.08)          # as in build_wings

        # fuselage: LEX position lights, forward and aft formation strips
        b = Builder()
        mats = ("LensRed", "LensGreen", "Formation")
        for side in (+1, -1):
            tag = "R" if side > 0 else "L"
            red = side < 0
            # position light on the LEX edge, forward of the wing root
            x = 7.55
            half, _z = h.lex(x)
            c, n = self.hit("Fuselage", (x, side * (half - 0.04), 2.0), (0, 0, -1))
            out = Vector((0, side * 0.75, 0.66)).normalized()
            self.dome(b, c, out, 0.022, 0.024, 0 if red else 1)
            self.marker("Position_LEX_" + tag, c + out * 0.02, out, root, "position",
                        "red" if red else "green", src_pos, "on the LEX edge forward of the wing root")
            # formation strip on the forward fuselage, just forward of the LEX
            c0, n0 = self.hit("Fuselage", (2.92, side * 2.0, 0.36), (0, -side, 0))
            c1, n1 = self.hit("Fuselage", (3.28, side * 2.0, 0.36), (0, -side, 0))
            c, nn = (c0 + c1) / 2, (n0 + n1).normalized()
            self.strip(b, c, c1 - c0, nn, (c1 - c0).length, 0.05, 0.003, 2)
            self.marker("Formation_FwdFuselage_" + tag, c + nn * 0.004, nn, root, "formation", "formation",
                        src_frm)
            # formation strip on the aft fuselage below the fin
            c0, n0 = self.hit("Fuselage", (12.55, side * 3.0, 0.38), (0, -side, 0))
            c1, n1 = self.hit("Fuselage", (13.25, side * 3.0, 0.38), (0, -side, 0))
            c, nn = (c0 + c1) / 2, (n0 + n1).normalized()
            self.strip(b, c, c1 - c0, nn, (c1 - c0).length, 0.05, 0.003, 2)
            self.marker("Formation_AftFuselage_" + tag, c + nn * 0.004, nn, root, "formation", "formation",
                        src_frm)
        h.add("ExtLights_Fuselage", b, mats=mats, smooth=None)

        # wings (ride on the outer panels, so they fold with them)
        for side in (+1, -1):
            tag = "R" if side > 0 else "L"
            red = side < 0
            outer = h.objects[P + "Wing_Outer_" + tag]
            b = Builder()
            # wingtip position light on the front corner of the tip launcher
            # adapter (the leading-edge flap runs out to the tip)
            xa = WING_APEX_X + WING_LE_TAN * TIP_RAIL_REF_Y + 0.05
            c = Vector((xa + 0.012, side * (TIP_RAIL_Y - 0.05), h.wing_z(TIP_RAIL_REF_Y) - 0.004))
            out = Vector((-0.72, side * 0.69, 0.0)).normalized()
            self.dome(b, c, out, 0.014, 0.016, 0)
            self.marker("Position_Wingtip_" + tag, c + out * 0.016, out, outer, "position",
                        "red" if red else "green", src_pos, "wingtip, front of the launcher adapter")
            # position light under the wing at the aileron hinge
            y = 4.90
            c, n = self.hit("Wing_Outer_" + tag, (te_hinge_x(y) - 0.07, side * y, -2.0), (0, 0, 1))
            self.dome(b, c, n, 0.024, 0.02, 0)
            self.marker("Position_UnderWing_" + tag, c + n * 0.02, n, outer, "position",
                        "red" if red else "green", src_pos, "under the wing at the aileron hinge")
            # formation strip along the wingtip, aft of the launcher adapter
            x0, x1 = 11.98, 12.30
            yt = SEMI_SPAN + 0.0015
            c = Vector(((x0 + x1) / 2, side * yt, h.wing_z(SEMI_SPAN)))
            nn = Vector((0, side, 0))
            self.strip(b, c, (1, 0, 0), nn, x1 - x0, 0.022, 0.003, 1)
            self.marker("Formation_Wingtip_" + tag, c + nn * 0.004, nn, outer, "formation", "formation", src_frm,
                        "on the wingtip, seen above and below a tip missile")
            h.add("ExtLights_Wing_" + tag, b, mats=("LensRed" if red else "LensGreen", "Formation"),
                  parent=outer, smooth=None)

        # fins: formation strip and red strobe on the outboard face of each fin,
        # white position light just below the tip of the right fin
        for side in (+1, -1):
            tag = "R" if side > 0 else "L"
            f = h.fin[side]
            fin = h.objects[P + "Fin_" + tag]
            b = Builder()
            n = f.n.copy()
            p0, p1 = f.point(0.32, 0.30, +1), f.point(0.62, 0.30, +1)
            c = (p0 + p1) / 2 + n * 0.001
            self.strip(b, c, p1 - p0, n, (p1 - p0).length, 0.045, 0.003, 1)
            self.marker("Formation_Fin_" + tag, c + n * 0.004, n, fin, "formation", "formation", src_frm)
            c = f.point(0.86, 0.22, +1)
            self.dome(b, c, n, 0.028, 0.022, 0)
            self.marker("Strobe_Fin_" + tag, c + n * 0.02, n, fin, "anti-collision strobe", "red", src_stb,
                        "outboard face of the fin")
            mats = ["Strobe", "Formation"]
            if side > 0:
                c = f.point(0.94, 0.995, 0)
                aft = Vector((1, 0, 0))
                self.dome(b, c, aft, 0.02, 0.026, 2)
                self.marker("Position_Tail", c + aft * 0.025, aft, fin, "position", "white", src_pos,
                            "just below the tip of the right fin")
                mats.append("LensWhite")
            h.add("ExtLights_Fin_" + tag, b, mats=tuple(mats), parent=fin, smooth=None)

        # nose strut: landing/taxi light and the three approach lights.  The
        # launch bar folds up against the front of the strut, so both sit on
        # the sides of the strut, facing forward.
        leg = h.objects[P + "NoseGear"]
        rn = 0.28
        top = Vector((NOSE_GEAR_X - 0.27, 0, -0.30))
        axle = Vector((NOSE_GEAR_X, 0, GROUND_Z + rn))
        along = lambda t: top + (axle - top) * t
        fwd = Vector((-1, 0, 0))
        b = Builder()
        c = along(0.33) + Vector((0, -0.085, 0))                   # landing/taxi light, port side
        b.revolve(c + Vector((0.035, 0, 0)), c + Vector((-0.045, 0, 0)), [(0, 0.028), (0.15, 0.040), (1.0, 0.040)],
                  n=14, mat=0, cap_mats=(0, 1))
        self.marker("LandingTaxi_Strut", c + fwd * 0.05, Vector((-1, 0, -0.08)), leg, "landing/taxi", "white",
                    "NATOPS 2.6.1.5 landing/taxi light")
        cc = along(0.36) + Vector((0, 0.080, 0))                   # approach lights, starboard side
        b.box([tuple(cc + Vector(v)) for v in ((0.025, -0.025, -0.065), (0.025, 0.025, -0.065), (0.025, 0.025, 0.065),
                                               (0.025, -0.025, 0.065), (-0.03, -0.025, -0.065), (-0.03, 0.025, -0.065),
                                               (-0.03, 0.025, 0.065), (-0.03, -0.025, 0.065))], mat=0)
        for k, (col, mat) in enumerate((("green", 2), ("amber", 3), ("red", 4))):
            p = cc + Vector((-0.03, 0, 0.04 - 0.04 * k))
            self.dome(b, p, fwd, 0.013, 0.012, mat)
            self.marker("Approach_%s_Strut" % col.capitalize(), p + fwd * 0.012, fwd, leg, "approach", col,
                        "NATOPS 2.6.1.6 approach lights (green high AOA, amber on speed, red low AOA)")
        h.add("ExtLights_Strut", b, mats=("Gear", "LensWhite", "LensGreen", "LensAmber", "LensRed"), parent=leg,
              collection=h.col_gear, smooth=None)

        # refuelling probe light: the manual names it but does not place it, so
        # this is a marker only, at the probe well, aimed at the probe tip
        base, tip = Vector((3.05, 0.30, 0.86)), Vector((2.05, 0.60, 1.22))
        self.marker("ProbeLight", base + Vector((0.10, -0.02, 0.02)), tip - base, root, "refuelling probe",
                    "white", "NATOPS 2.6.1.1 (refueling probe light)", "position not given in the manual")

    # -- probes -----------------------------------------------------------------
    def build_probes(self):
        h = self.h
        for side in (+1, -1):
            tag = "R" if side > 0 else "L"
            # pitot-static tube: under the nose, forward of the nosewheel well
            x = 3.05
            zc = h.core(x)[3]
            out = Vector((0, side * 0.72, -0.70)).normalized()
            c, n = self.hit("Fuselage", Vector((x, 0, zc)) + out * 2.0, -out)
            b = Builder()
            knee = c + n * 0.10
            b.revolve(c - n * 0.01, knee, [(0, 0.016), (1, 0.011)], n=10)
            b.revolve(knee + Vector((0.035, 0, 0)), knee + Vector((-0.30, 0, 0)),
                      [(0, 0.011), (0.85, 0.011), (0.97, 0.007), (1.0, 0.004)], n=10)
            h.add("Probe_Pitot_" + tag, b, mats=("Metal",), smooth=40.0)
            # angle-of-attack probe: conical sensor on the nose side
            x = 3.40
            zc = h.core(x)[3]
            c, n = self.hit("Fuselage", (x, side * 2.0, zc - 0.05), (0, -side, 0))
            b = Builder()
            b.revolve(c - n * 0.004, c + n * 0.075, [(0, 0.03), (0.15, 0.027), (1.0, 0.004)], n=14)
            h.add("Probe_AOA_" + tag, b, mats=("Metal",), smooth=40.0)
        # total temperature probe: lower left fuselage, aft of the nosewheel
        x = 6.05
        zc = h.core(x)[3]
        out = Vector((0, -0.55, -0.83)).normalized()
        c, n = self.hit("Fuselage", Vector((x, 0, zc)) + out * 2.0, -out)
        b = Builder()
        t = n.cross(Vector((1, 0, 0))).normalized() * 0.006
        a0, a1 = c - n * 0.01, c + n * 0.065
        b.box([tuple(a0 + Vector((-0.03, 0, 0)) - t), tuple(a0 + Vector((0.05, 0, 0)) - t),
               tuple(a1 + Vector((0.03, 0, 0)) - t), tuple(a1 + Vector((-0.02, 0, 0)) - t),
               tuple(a0 + Vector((-0.03, 0, 0)) + t), tuple(a0 + Vector((0.05, 0, 0)) + t),
               tuple(a1 + Vector((0.03, 0, 0)) + t), tuple(a1 + Vector((-0.02, 0, 0)) + t)])
        b.revolve(a1 + Vector((0.04, 0, 0)), a1 + Vector((-0.05, 0, 0)), [(0, 0.012), (0.8, 0.014), (1, 0.010)], n=10)
        h.add("Probe_TotalTemp", b, mats=("Metal",), smooth=40.0)

    # -- fuel vent / dump masts ---------------------------------------------------
    def build_dump_masts(self):
        h = self.h
        for side in (+1, -1):
            tag = "R" if side > 0 else "L"
            f = h.fin[side]
            p = f.point(0.975, 1.0, 0)
            b = Builder()
            b.revolve(p + Vector((-0.06, 0, 0)), p + Vector((0.07, 0, 0)), [(0, 0.009), (0.9, 0.009), (1, 0.006)], n=8)
            h.add("FuelDumpMast_" + tag, b, mats=("Metal",), parent=h.objects[h.prefix + "Fin_" + tag], smooth=40.0)

    # -- boarding ladder ----------------------------------------------------------
    def build_ladder(self):
        """Stowed flat under the left LEX (the manual: it rotates down from the
        forward beam under the LEX, and up and aft to stow).  Rest pose is
        stowed; rotating by its 'extend' angle stands it on the ground,
        leaning LADDER_TILT forward of vertical."""
        h = self.h
        y = -0.80
        x0 = 5.65
        under = lambda x: self.hit("Fuselage", (x, y, -1.0), (0, 0, 1))[0].z
        zp = under(x0) - 0.045
        foot_z = GROUND_Z + 0.02
        tilt = math.radians(LADDER_TILT)
        length = (zp - foot_z) / math.cos(tilt)
        # stowed slope: follow the LEX underside aft of the pivot
        x1 = x0 + length
        slope = math.atan2(zp - (under(x1 - 0.05) - 0.045), length)
        if x1 > 8.15:
            raise RuntimeError("ladder (%.2f m) does not fit under the LEX ahead of the intake" % length)
        extend = 90.0 + LADDER_TILT - math.degrees(slope)
        pivot = Vector((x0, y, zp))
        d_e = Vector((-math.sin(tilt), 0, -math.cos(tilt)))      # extended: down, leaning forward
        e_w = Vector((0, 1, 0))
        e_t = d_e.cross(e_w)
        b = Builder()

        def bar(p0, p1, w, t):
            p0, p1 = Vector(p0), Vector(p1)
            ax = (p1 - p0).normalized()
            u = ax.cross(Vector((0, 1, 0)))
            if u.length < 1e-6:
                u = ax.cross(Vector((1, 0, 0)))
            u.normalize()
            v = ax.cross(u)
            loop = lambda c: [tuple(c + u * su * t / 2 + v * sv * w / 2) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            b.box(loop(p0) + loop(p1))

        hw = LADDER_WIDTH / 2
        for s in (-1, 1):
            a = pivot + e_w * (s * hw)
            bar(a + d_e * 0.02, a + d_e * length, 0.028, 0.04)
            bar(a + d_e * (length - 0.01) + e_t * 0.03, a + d_e * (length - 0.01) - e_t * 0.06, 0.05, 0.02)   # foot
        k = 0.30
        while k < length - 0.12:
            c = pivot + d_e * k
            bar(c - e_w * hw, c + e_w * hw, 0.03, 0.022)
            k += 0.30
        bar(pivot - e_w * (hw + 0.02), pivot + e_w * (hw + 0.02), 0.05, 0.05)    # hinge beam
        # rotate the extended ladder up to its stowed rest pose about the hinge
        R = Matrix.Rotation(math.radians(-extend), 3, Vector((0, 1, 0)))
        b.verts = [tuple(pivot + R @ (Vector(v) - pivot)) for v in b.verts]
        lad = h.add("BoardingLadder", b, mats=("Airframe",), origin=tuple(pivot), axis=(0, 1, 0), smooth=None,
                    hinge="ladder swings down to the ground (extends)")
        lad["extend"] = extend
        return lad

    # -- afterburner and turbine face ----------------------------------------------
    def build_afterburners(self):
        """Liner, flame holder and turbine face, seen through the nozzles."""
        h = self.h
        for side in (+1, -1):
            tag = "R" if side > 0 else "L"
            A = Vector((15.75, side * 0.48, 0.08))
            B = Vector((16.65, side * 0.48, 0.12))
            u = (B - A)
            at = lambda t: A + u * t
            b = Builder()
            # liner from the nozzle's inner end (t = 0.45) forward to the turbine face
            t0, t1 = -1.0, 0.45
            b.revolve(at(t0), at(t1), [(0.0, 0.355), (0.0, 0.372), (1.0, 0.372), (1.0, 0.355), (0.02, 0.355)],
                      n=28, mat=0, cap_mats=(1, 1))
            # turbine face: hub and blades just aft of the liner's front wall
            tf = t0 + 0.02 * (t1 - t0)
            ax = u.normalized()
            b.revolve(at(tf), at(tf) + ax * 0.10, [(0, 0.12), (0.6, 0.09), (1.0, 0.03)], n=16, mat=1)
            ref = Vector((0, 0, 1))
            e1 = ax.cross(ref).normalized()
            e2 = ax.cross(e1)
            nb = 28
            for k in range(nb):
                a = 2 * math.pi * k / nb
                r_dir = e1 * math.cos(a) + e2 * math.sin(a)
                tan = ax.cross(r_dir)
                tw = tan * math.cos(math.radians(35)) + ax * math.sin(math.radians(35))
                c0 = at(tf) + ax * 0.02
                p0, p1 = c0 + r_dir * 0.11, c0 + r_dir * 0.35
                cw = tw * 0.025
                th = ax.cross(tw).normalized() * 0.003
                b.box([tuple(p0 - cw - th), tuple(p1 - cw - th), tuple(p1 + cw - th), tuple(p0 + cw - th),
                       tuple(p0 - cw + th), tuple(p1 - cw + th), tuple(p1 + cw + th), tuple(p0 + cw + th)], mat=1)
            # flame holder: two V-gutter rings joined by radial gutters
            tfh = t0 + 0.62 * (t1 - t0)
            for r0, r1 in ((0.20, 0.225), (0.29, 0.312)):
                b.revolve(at(tfh), at(tfh) + ax * 0.04, [(0, r0), (0, r1), (1, r1), (1, r0)], n=28, mat=2,
                          caps=(False, False))
            for k in range(6):
                a = 2 * math.pi * k / 6 + 0.26
                r_dir = e1 * math.cos(a) + e2 * math.sin(a)
                tan = ax.cross(r_dir)
                c0 = at(tfh)
                p0, p1 = c0 + r_dir * 0.08, c0 + r_dir * 0.34
                cw, th = tan * 0.012, ax * 0.04
                b.box([tuple(p0 - cw), tuple(p1 - cw), tuple(p1 + cw), tuple(p0 + cw),
                       tuple(p0 - cw + th), tuple(p1 - cw + th), tuple(p1 + cw + th), tuple(p0 + cw + th)], mat=2)
            h.add("Afterburner_" + tag, b, mats=("Liner", "Turbine", "Turbine"), smooth=35.0)

    def build(self):
        self.build_lights()
        self.build_probes()
        self.build_dump_masts()
        self.build_ladder()
        self.build_afterburners()


def build(h):
    Exterior(h).build()
