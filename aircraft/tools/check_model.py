"""Sanity checks for a generated Hornet .blend.

    blender -b -P check_model.py -- ../FA-18A_Hornet.blend

1. Every hinged part rests at zero rotation (its "_Hinge" parent holds the
   hinge orientation), and port/starboard pairs move the same way for the
   same positive rotation.
2. No two airframe meshes intersect, apart from joints that are meant to
   touch or sit inside the fuselage (fin and wing roots inside the nacelles,
   canopy frames on their transparencies).
3. Cockpit parts stay inside the closed canopy, windscreen and their frames.
4. In every loadout, no store intersects the airframe, the gear or another
   station's store (a store touching its own rack, launcher or pylon at the
   lugs is expected).

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
def coll_of(o):
    return o.users_collection[0].name if o.users_collection else ""


all_meshes = [o for o in objs if o.type == "MESH"]
library = [o for o in all_meshes if coll_of(o) == "Stores Library"]
loadout_objs = [o for o in all_meshes if "Loadout" in coll_of(o)]
cockpit = [o for o in all_meshes if coll_of(o).endswith(" Cockpit")]
base_meshes = [o for o in all_meshes if o not in library and o not in loadout_objs and o not in cockpit]
meshes = base_meshes
cache = {}


def tree(o):
    if o.name not in cache:
        cache[o.name] = BVHTree.FromPolygons(verts(o), [list(p.vertices) for p in o.data.polygons])
    return cache[o.name]


def part(name):
    return name.split("_", 1)[1] if "_" in name else name


ATTACHED_TO_FUSELAGE = ("Wing_Inner", "Fin_", "Stabilator", "Canopy", "Seats", "Antennae",
                        "GunPort", "MainGear", "NoseGear", "Nozzle", "ArrestingHook",
                        "SpeedBrake", "RefuelProbe", "Windscreen", "Pylon_STA5")
EXPECTED = [
    ("Fin_", "Wing_Inner"),          # both roots buried inside the nacelle
    ("Canopy", "CanopyFrames"), ("Windscreen", "WindscreenFrame"),
    ("NoseGearBrace", "NoseGear"),   # the braces pin to their legs
    ("MainGearBrace", "MainGear"),
]
clashes = []


def check(a, b, label=""):
    n = len(tree(a).overlap(tree(b)))
    if n:
        clashes.append("%s%s x %s (%d triangle pairs)" % (label, a.name, b.name, n))


for a, b in itertools.combinations(sorted(base_meshes, key=lambda o: o.name), 2):
    pa, pb = part(a.name), part(b.name)
    if pa == "Fuselage" and pb.startswith(ATTACHED_TO_FUSELAGE):
        continue
    if pb == "Fuselage" and pa.startswith(ATTACHED_TO_FUSELAGE):
        continue
    if any((pa.startswith(x) and pb.startswith(y)) or (pa.startswith(y) and pb.startswith(x))
           for x, y in EXPECTED):
        continue
    check(a, b)
# cockpit interior against the transparencies and their frames (canopy closed)
glass = [o for o in base_meshes if part(o.name).startswith(("Canopy", "Windscreen"))]
for c in cockpit:
    if c.parent and part(c.parent.name).startswith("Canopy"):
        continue                      # mirrors ride on the canopy bow
    for g in glass:
        check(c, g, "cockpit: ")
# every loadout: its stores against the airframe and against each other
by_load = {}
for o in loadout_objs:
    by_load.setdefault(coll_of(o), []).append(o)
for lname, items in sorted(by_load.items()):
    for o in items:
        for b in base_meshes:
            pb = part(b.name)
            if pb.startswith("Pylon_STA") or pb == "Fuselage" and "STA4" in o.name or \
                    pb == "Fuselage" and "STA6" in o.name:
                continue                  # lugs sit in the rack; LAU-116 stores are semi-recessed
            check(o, b, lname + ": ")
    for a, b in itertools.combinations(items, 2):
        sa = a.name.split("_STA")[1].split("_")[0]
        sb_ = b.name.split("_STA")[1].split("_")[0]
        if sa == sb_:
            continue                      # store and its own rack / launcher
        check(a, b, lname + ": ")
for c in clashes:
    print("CLASH", c)
failures += ["clash: " + c for c in clashes]

print("\n%d meshes (%d cockpit, %d in loadouts), %d hinged parts checked" % (len(base_meshes), len(cockpit), len(loadout_objs), len(hinged)))
if failures:
    print("FAILED:\n  " + "\n  ".join(failures))
    sys.exit(1)
print("all checks passed")
