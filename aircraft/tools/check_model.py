"""Sanity checks for a generated Hornet .blend.

    blender -b -P check_model.py -- ../FA-18A_Hornet.blend

1. Every hinged part rests at zero rotation (its "_Hinge" parent holds the
   hinge orientation), and port/starboard pairs move the same way for the
   same positive rotation.
2. No two meshes intersect, apart from joints that are meant to touch or
   that sit inside the fuselage (fin and wing roots inside the nacelles,
   stores on their stations, canopy parts).  Hidden objects (stores, the
   extended refuelling probe) are checked too.

Exits non-zero if a check fails.
"""
import itertools
import math
import sys

import bpy
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
bpy.ops.wm.open_mainfile(filepath=argv[0])
objs = bpy.data.objects
failures = []


def world(o):
    """World matrix from the parent chain (valid for hidden objects too)."""
    m = o.matrix_basis.copy()
    p = o.parent
    while p is not None:
        m = p.matrix_basis @ m
        p = p.parent
    return m


def verts(o):
    m = world(o)
    return [m @ v.co for v in o.data.vertices]


# -- 1. hinges ----------------------------------------------------------------
hinged = [o for o in objs if o.type == "MESH" and "hinge" in o.keys()]
for o in hinged:
    if any(abs(a) > 1e-6 for a in o.rotation_euler):
        failures.append("%s does not rest at zero rotation" % o.name)

moves = {}
for o in hinged:
    before = verts(o)
    o.rotation_euler.x = math.radians(20)
    after = verts(o)
    o.rotation_euler.x = 0.0
    # mean displacement in design axes: x aft (Blender +Y), y starboard (-X), z up
    n = len(before)
    d = [sum((a - b)[i] for a, b in zip(after, before)) / n for i in range(3)]
    moves[o.name] = (d[1], -d[0], d[2])
    print("%-28s +20 deg -> mean move aft %+.3f stbd %+.3f up %+.3f   [%s]"
          % (o.name, d[1], -d[0], d[2], o["hinge"].split("positive = ")[-1]))

for name, (dx, dy, dz) in moves.items():
    if name.endswith("_R"):
        other = moves.get(name[:-2] + "_L")
        if other is None:
            continue
        # mirror pair: aft and vertical motion should agree; for rudders the
        # sideways motion must agree too (both trailing edges to starboard)
        if "Rudder" in name:
            same = dy * other[1] > 0
        else:
            same = abs(dz - other[2]) < 0.02 and abs(dx - other[0]) < 0.02
        if not same:
            failures.append("%s and its port twin move differently" % name)

# -- 2. clashes ---------------------------------------------------------------
meshes = [o for o in objs if o.type == "MESH"]
trees = {o.name: BVHTree.FromPolygons(verts(o), [list(p.vertices) for p in o.data.polygons])
         for o in meshes}


def part(name):
    return name.split("_", 1)[1]


ATTACHED_TO_FUSELAGE = ("Wing_Inner", "Fin_", "Stabilator", "Canopy", "Seats", "Antennae",
                        "GunPort", "AIM7", "MainGear", "NoseGear", "Nozzle", "ArrestingHook",
                        "SpeedBrake", "RefuelProbe", "CockpitInterior")
EXPECTED = [
    ("Fin_", "Wing_Inner"),          # both roots buried inside the nacelle
    ("AIM9", "Wing_Outer"),          # launcher on the tip rail
    ("Canopy", "CanopyFrames"), ("Canopy", "Seats"), ("Canopy", "CockpitInterior"),
    ("CanopyFrames", "CockpitInterior"), ("Seats", "CockpitInterior"),
    ("CanopyFrames", "Seats"),
]
clashes = []
for a, b in itertools.combinations(sorted(trees), 2):
    pa, pb = part(a), part(b)
    if pa == "Fuselage" and pb.startswith(ATTACHED_TO_FUSELAGE):
        continue
    if pb == "Fuselage" and pa.startswith(ATTACHED_TO_FUSELAGE):
        continue
    if any((pa.startswith(x) and pb.startswith(y)) or (pa.startswith(y) and pb.startswith(x))
           for x, y in EXPECTED):
        continue
    n = len(trees[a].overlap(trees[b]))
    if n:
        clashes.append("%s x %s (%d triangle pairs)" % (a, b, n))
for c in clashes:
    print("CLASH", c)
failures += ["clash: " + c for c in clashes]

print("\n%d meshes, %d hinged parts checked" % (len(meshes), len(hinged)))
if failures:
    print("FAILED:\n  " + "\n  ".join(failures))
    sys.exit(1)
print("all checks passed")
