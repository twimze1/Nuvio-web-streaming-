"""Render a showreel of every animation clip in an *_animated.blend.

    blender -b -P render_showreel.py -- FA-18A_Hornet_animated.blend OUT_DIR WORKER WORKERS [SAMPLES]

Each clip on the NLA gets its own camera, aimed at the parts it moves, with
a slow eased orbit; a short orbit of the neutral pose opens the reel.  The
unique frames are split between WORKERS processes (this one renders those
whose index % WORKERS == WORKER) and written as OUT_DIR/u00000.png ...; the
shot list (which unique frame shows when, and the label for each shot) is
written to OUT_DIR/shots.json by worker 0.  tools/make_showreel.py then adds
the labels and encodes the MP4.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
blend, out, worker, workers = argv[0], argv[1], int(argv[2]), int(argv[3])
samples = int(argv[4]) if len(argv) > 4 else 3
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
sc = bpy.context.scene
os.makedirs(out, exist_ok=True)

# -- look ----------------------------------------------------------------------
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = samples
for k, v in (("use_raytracing", False), ("shadow_ray_count", 1), ("shadow_step_count", 4)):
    if hasattr(sc.eevee, k):
        setattr(sc.eevee, k, v)
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.render.resolution_percentage = 100
w = bpy.data.worlds.new("reel")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.50, 0.62, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sun = bpy.data.objects.new("reel_sun", bpy.data.lights.new("reel_sun", "SUN"))
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(38), math.radians(-15), math.radians(150))
sc.collection.objects.link(sun)
cam = bpy.data.objects.new("reel_cam", bpy.data.cameras.new("reel_cam"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.clip_start = 0.05

# -- clips and what they move ---------------------------------------------------
ranges, movers = {}, {}
for o in bpy.data.objects:
    if o.animation_data:
        for t in o.animation_data.nla_tracks:
            for s in t.strips:
                ranges[t.name] = (int(s.frame_start), int(s.frame_end))
                movers.setdefault(t.name, []).append(o)


def centre(objs):
    pts = []
    for o in objs:
        for m in [o] + list(o.children_recursive):
            if m.type == "MESH":
                pts += [m.matrix_world @ Vector(c) for c in m.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return (lo + hi) / 2


sc.frame_set(0)
# camera offset from the moving parts' centre (Blender axes: +X port, +Y aft,
# +Z up), lens, orbit half-angle, and the caption for each clip
VIEWS = {
    "Gear_Retract": ((-8.5, -9.5, -4.5), 27, 8, "Landing gear retract: the nose leg swings forward, the main posts swing aft and turn the wheels flat, then the doors close"),
    "Gear_Extend": ((8.5, -9.5, -4.5), 27, 8, "Landing gear extend: the doors open first, then the legs come down"),
    "LaunchBar_Down": ((4.2, -3.2, 0.1), 45, 6, "Launch bar down to the deck for a catapult hook-up"),
    "LaunchBar_Up": ((4.2, -3.2, 0.1), 45, 6, "Launch bar back up"),
    "Canopy_Open": ((-5.2, -4.2, 2.4), 30, 8, "Canopy open, about its aft hinge"),
    "Canopy_Close": ((-5.2, -4.2, 2.4), 30, 8, "Canopy close"),
    "Airbrake_Extend": ((-6.5, 7.0, 4.5), 28, 8, "Speed brake extend"),
    "Airbrake_Retract": ((-6.5, 7.0, 4.5), 28, 8, "Speed brake retract"),
    "Controls_Roll": ((5.5, 10.0, 3.6), 36, 6, "Roll: ailerons and differential stabilators"),
    "Controls_Pitch": ((5.5, 10.0, 3.6), 36, 6, "Pitch: stabilators"),
    "Controls_Yaw": ((5.5, 10.0, 3.6), 36, 6, "Yaw: rudders"),
    "Flaps_Down": ((-10.0, -11.0, 6.0), 34, 6, "Leading- and trailing-edge flaps down"),
    "Flaps_Up": ((-10.0, -11.0, 6.0), 34, 6, "Flaps up"),
    "WingFold_Fold": ((-6.0, -17.0, 5.0), 38, 6, "Wing fold"),
    "WingFold_Unfold": ((-6.0, -17.0, 5.0), 38, 6, "Wing unfold"),
    "Hook_Down": ((5.0, 6.5, -1.2), 32, 6, "Arresting hook down"),
    "Hook_Up": ((5.0, 6.5, -1.2), 32, 6, "Arresting hook up"),
}
HOLD_IN, HOLD_OUT = 8, 16


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def place(target, offset, lens, ang):
    off = Matrix.Rotation(math.radians(ang), 3, "Z") @ Vector(offset)
    cam.location = target + off
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens


# unique renders: (source frame, target, offset, lens, orbit angle)
renders, shots = [], []
whole = centre([o for o in bpy.data.objects if o.type == "MESH" and o.visible_get()])
intro = []
for i in range(72):
    intro.append(len(renders))
    renders.append((0, tuple(whole), (-12.5, -14.5, 4.5), 35, -25 + 50 * smooth(i / 71)))
shots.append({"label": "F/A-18A Hornet", "caption": "Animation clips: neutral pose", "frames": intro})
for name in sorted(ranges, key=lambda n: ranges[n][0]):
    if name not in VIEWS:
        continue
    a, b = ranges[name]
    offset, lens, orbit, caption = VIEWS[name]
    tgt = centre(movers[name])
    seq = []
    first = len(renders)
    for f in range(a, b + 1):
        u = (f - a) / max(1, b - a)
        renders.append((f, tuple(tgt), offset, lens, -orbit + 2 * orbit * smooth(u)))
    last = len(renders) - 1
    seq = [first] * HOLD_IN + list(range(first, last + 1)) + [last] * HOLD_OUT
    shots.append({"label": name, "caption": caption, "frames": seq})

if worker == 0:
    with open(os.path.join(out, "shots.json"), "w") as f:
        json.dump({"fps": sc.render.fps, "shots": shots, "count": len(renders)}, f)

for i, (f, tgt, offset, lens, ang) in enumerate(renders):
    if i % workers != worker:
        continue
    path = os.path.join(out, "u%05d.png" % i)
    if os.path.exists(path):
        continue                          # resume after an interruption
    sc.frame_set(f)
    place(Vector(tgt), offset, lens, ang)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("rendered %d / %d" % (i, len(renders)), flush=True)
