"""
Set up reusable animations for the moving parts of a Hornet .blend, without
changing the model, and save the result as a NEW file.

Run headless (the source file is never overwritten):

    blender -b FA-18A_Hornet.blend -P tools/setup_animations.py -- [--out FILE] [--glb]

or open the .blend in Blender, load this script in the Text Editor and press
Run Script: it does the same and saves "<name>_animated.blend" beside the file.

What it does
  1. Inspects the scene and reports every object it could animate, every
     moving part that is NOT a separate object (so you can separate or name it
     yourself), and anything missing (gear doors, pilots, second crew member).
  2. Pivots: parts that carry a "hinge" custom property already have a hinge
     empty and rest at zero rotation; they are animated about their local X
     axis using the sign stated in that property.  Landing-gear legs get a new
     "<name>_Pivot" empty at the top of the leg (found from the mesh), and the
     leg is re-parented to it with its world position kept: no mesh is edited.
  3. Actions: one Action per clip (Blender 4.4+ slotted actions: one slot per
     animated object), Bezier keys with eased in/out, fake user set.  Every
     clip is laid out on an NLA "showreel" (a track per clip on each object,
     strips that extrapolate to nothing), with a timeline marker per clip, so
     the aircraft sits in its neutral pose whenever no clip is playing.
  4. Saves a copy as a new .blend (and, with --glb, a GLB whose animations are
     the clips, one glTF animation per NLA track).

Angles are visual: they make the motion readable and are not flight-control
data.  Change them in ANGLES below.
"""
import math
import os
import re
import sys

import bpy
from mathutils import Matrix, Vector

FPS = 24
ANGLES = {                      # degrees, visual only
    "canopy": 45.0,
    "airbrake": 45.0,
    "aileron": 20.0,
    "stab_roll": 6.0,
    "stab_pitch": 12.0,
    "rudder": 20.0,
    "le_flap": 20.0,
    "te_flap": 30.0,
    "wing_fold": 90.0,
    "hook": 30.0,
}

# role keywords (lower-case, matched against object names)
ROLE_WORDS = [
    ("canopy", r"(^|_)canopy$"),
    ("airbrake", r"speed_?brake|air_?brake"),
    ("rudder", r"rudder"),
    ("aileron", r"aileron"),
    ("le_flap", r"le_?flap|slat|leading"),
    ("te_flap", r"(^|_)flap(_|$)|te_?flap"),
    ("stabilator", r"stabilator|elevator|(^|_)stab(_|$)"),
    ("wing_fold", r"wing_outer|wingfold|wing_fold"),
    ("hook", r"hook"),
    ("nose_gear", r"nose_?gear"),
    ("main_gear", r"main_?gear"),
    ("gear_door", r"door"),
    ("pilot", r"pilot|crew|wso|helmet|(^|_)head(_|$)"),
]

report = []


def say(msg=""):
    print(msg)
    report.append(msg)


# ----------------------------------------------------------------------------
# inspection
# ----------------------------------------------------------------------------
def role_of(obj):
    n = obj.name.lower()
    for role, pat in ROLE_WORDS:
        if re.search(pat, n):
            return role
    return None


def side_of(obj):
    n = obj.name.lower()
    if re.search(r"(_l$|_left|left_|_l_)", n):
        return "L"
    if re.search(r"(_r$|_right|right_|_r_)", n):
        return "R"
    x = obj.matrix_world.translation.x          # +X is port in these models
    return "L" if x > 0.05 else "R" if x < -0.05 else "C"


def hinge_sign(obj):
    """Return (+1) when a positive local-X rotation does what the role needs
    (deflect down / open / fold up / extend), from the 'hinge' property."""
    txt = obj.get("hinge", "")
    if not txt:
        return None
    m = re.search(r"positive\s*=\s*(.*)", txt)
    return m.group(1).strip() if m else txt


def inspect(scene):
    """Collect animatable parts.  Hidden library / loadout copies are ignored."""
    parts = {}
    skipped = []
    say("== Scene inspection ==")
    for obj in sorted(scene.objects, key=lambda o: o.name):
        cols = [c.name for c in obj.users_collection]
        if any(("Library" in c or "Loadout" in c) for c in cols):
            continue
        role = role_of(obj)
        if role is None or obj.type not in ("MESH", "EMPTY"):
            continue
        if role != "pilot" and any(c.endswith("Cockpit") for c in cols):
            continue                                 # cockpit items (e.g. rudder pedals) are not flight controls
        if obj.type == "EMPTY":
            continue                                 # hinge empties are found through their mesh child
        if role in ("canopy", "airbrake", "rudder", "aileron", "le_flap", "te_flap", "stabilator", "wing_fold",
                    "hook"):
            if "hinge" not in obj.keys():
                skipped.append((obj.name, role, "no 'hinge' property / pivot: rotation axis unknown"))
                continue
        parts.setdefault(role, []).append(obj)
    for role in sorted(parts):
        for o in parts[role]:
            say("  %-12s %-34s side %s  %s" % (role, o.name, side_of(o),
                                                ("[" + hinge_sign(o) + "]") if o.get("hinge") else "[needs pivot]"))
    for name, role, why in skipped:
        say("  SKIPPED %-34s (%s): %s" % (name, role, why))
    return parts


# ----------------------------------------------------------------------------
# pivots for parts without hinges (landing gear)
# ----------------------------------------------------------------------------
def world_verts(obj):
    M = obj.matrix_world
    return [M @ v.co for v in obj.data.vertices]


def make_pivot(obj, location, axis, up=Vector((0, 0, 1))):
    """Empty at `location` whose local X is `axis`; obj re-parented to it with
    its world transform unchanged."""
    ax = axis.normalized()
    yv = up.cross(ax)
    if yv.length < 1e-6:
        yv = Vector((0, 1, 0)).cross(ax)
    yv.normalize()
    zv = ax.cross(yv).normalized()
    frame = Matrix(((ax.x, yv.x, zv.x, location.x), (ax.y, yv.y, zv.y, location.y),
                    (ax.z, yv.z, zv.z, location.z), (0, 0, 0, 1)))
    piv = bpy.data.objects.new(obj.name + "_Pivot", None)
    piv.empty_display_type = "SINGLE_ARROW"
    piv.empty_display_size = 0.3
    for c in obj.users_collection:
        c.objects.link(piv)
    parent = obj.parent
    piv.parent = parent
    piv.matrix_world = frame
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = piv
    obj.matrix_world = world                    # keep the leg exactly where it is
    piv["pivot"] = "added by setup_animations.py; rotate about local X"
    return piv


def gear_pivot(obj, kind):
    """Top of the leg = mean of the highest vertices near the centre of the
    top; retraction rotation carries the wheel (lowest point) to a stowed
    direction: nose gear forward-up, main gear aft, inboard and up (the legacy
    Hornet's nose gear retracts forward, its main gears aft with the wheels
    turning to lie flat under the intake ducts)."""
    V = world_verts(obj)
    ztop = max(v.z for v in V)
    top = [v for v in V if v.z > ztop - 0.04]
    P = sum(top, Vector()) / len(top)
    zlow = min(v.z for v in V)
    low = [v for v in V if v.z < zlow + 0.10]
    W = sum(low, Vector()) / len(low)              # wheel(s)
    a = W - P
    side = 1.0 if P.x > 0 else -1.0
    if kind == "nose_gear":
        b = Vector((0.0, -1.0, 0.21)).normalized() * a.length        # Blender -Y is forward
    else:
        b = Vector((-side * 0.30, 1.0, 0.30)).normalized() * a.length  # aft, inboard, up
    axis = a.cross(b)
    angle = a.angle(b)
    return P, axis, math.degrees(angle)


# ----------------------------------------------------------------------------
# actions
# ----------------------------------------------------------------------------
SLOTTED = bpy.app.version >= (4, 4, 0)
clips = []          # (name, start, length)


class Clip:
    def __init__(self, name, length):
        self.name = name
        self.length = length
        self.tracks = {}                            # obj -> list of (frame, value)
        self.action = bpy.data.actions.get(name) or bpy.data.actions.new(name)
        self.action.use_fake_user = True

    def key(self, obj, frames_values):
        self.tracks.setdefault(obj, []).extend(frames_values)

    def build(self):
        for obj, keys in self.tracks.items():
            obj.animation_data_create()
            if SLOTTED:
                obj.animation_data.action = self.action
            else:                                   # Blender < 4.4: one action per object
                act = bpy.data.actions.new("%s|%s" % (self.name, obj.name))
                act.use_fake_user = True
                obj.animation_data.action = act
            rest = obj.rotation_euler.x
            for f, v in sorted(keys):
                obj.rotation_euler.x = math.radians(v)
                obj.keyframe_insert("rotation_euler", index=0, frame=f)
            obj.rotation_euler.x = rest
            for fc in fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.easing = "AUTO"
                    kp.handle_left_type = "AUTO_CLAMPED"
                    kp.handle_right_type = "AUTO_CLAMPED"
                fc.update()


def fcurves(obj):
    ad = obj.animation_data
    if SLOTTED:
        cb = ad.action.layers[0].strips[0].channelbag(ad.action_slot)
        return list(cb.fcurves) if cb else []
    return list(ad.action.fcurves)


def push_to_nla(clip, start):
    """One NLA track per clip on each object, strip at `start`, nothing held
    outside it; the object is left with no active action (neutral pose)."""
    for obj in clip.tracks:
        ad = obj.animation_data
        act = ad.action
        slot = ad.action_slot if SLOTTED else None
        tr = ad.nla_tracks.new()
        tr.name = clip.name
        st = tr.strips.new(clip.name, int(start), act)
        if SLOTTED:
            st.action_slot = slot
        st.extrapolation = "NOTHING"
        st.blend_type = "REPLACE"
        ad.action = None
        obj.rotation_euler.x = 0.0


# ----------------------------------------------------------------------------
# clip definitions
# ----------------------------------------------------------------------------
def ease_pair(t0, t1, v):
    return [(t0, 0.0), (t1, v)]


def build_clips(parts):
    made = []
    by = lambda role: parts.get(role, [])

    def sided(role):
        return {side_of(o): o for o in by(role)}

    # landing gear (pivots added); doors only if they exist as separate objects
    gear = []
    for kind in ("nose_gear", "main_gear"):
        for o in by(kind):
            P, axis, ang = gear_pivot(o, kind)
            piv = make_pivot(o, P, axis)
            gear.append((kind, piv, ang))
            say("  pivot  %-28s at (%.2f, %.2f, %.2f), retract %.0f deg" % (piv.name, P.x, P.y, P.z, ang))
    doors = by("gear_door")
    if gear:
        ret = Clip("Gear_Retract", 120)
        ext = Clip("Gear_Extend", 120)
        for kind, piv, ang in gear:
            t0, t1 = (12, 100) if kind == "nose_gear" else (18, 108)
            ret.key(piv, [(1, 0.0), (t0, 0.0), (t1, ang), (120, ang)])
            ext.key(piv, [(1, ang), (120 - t1 + 1, ang), (120 - t0 + 1, 0.0), (120, 0.0)])
        made += [ret, ext]
    if not doors:
        say("  NOTE   no separate gear-door objects found: the nose-gear doors are part of the nose-gear")
        say("         mesh and the main-gear bays have no doors. Separate the door faces into objects whose")
        say("         names contain 'door' and re-run to animate them.")
    for kind, piv, ang in gear:
        leg = piv.children[0]
        V = world_verts(leg)
        P = piv.matrix_world.translation
        reach = max((v - P).length for v in V if v.z > P.z - 0.15)
        if kind == "nose_gear" and reach > 0.6:
            say("  NOTE   %s: parts that hang from the top of the bay well away from the pivot (the drag" % leg.name)
            say("         brace and doors) are fused into the leg mesh, so they swing with the leg and show")
            say("         below the nose while the gear retracts. Separate them (names containing 'brace' or")
            say("         'door') to give them their own motion.")
    # canopy
    if by("canopy"):
        o = by("canopy")[0]
        op = Clip("Canopy_Open", 96)
        op.key(o, [(1, 0.0), (8, 0.0), (90, ANGLES["canopy"]), (96, ANGLES["canopy"])])
        cl = Clip("Canopy_Close", 96)
        cl.key(o, [(1, ANGLES["canopy"]), (8, ANGLES["canopy"]), (90, 0.0), (96, 0.0)])
        made += [op, cl]
    # airbrake
    if by("airbrake"):
        o = by("airbrake")[0]
        ex = Clip("Airbrake_Extend", 48)
        ex.key(o, [(1, 0.0), (40, ANGLES["airbrake"]), (48, ANGLES["airbrake"])])
        rt = Clip("Airbrake_Retract", 48)
        rt.key(o, [(1, ANGLES["airbrake"]), (40, 0.0), (48, 0.0)])
        made += [ex, rt]
    # control surfaces: a pre-flight style control check, plus single-axis clips
    ail, stab, rud = sided("aileron"), sided("stabilator"), sided("rudder")
    lef, tef = by("le_flap"), by("te_flap")           # several per side (inner and outer)
    if ail or stab:
        roll = Clip("Controls_Roll", 96)               # roll right, roll left, centre
        a, s_ = ANGLES["aileron"], ANGLES["stab_roll"]
        for side, o in ail.items():
            k = 1.0 if side == "L" else -1.0         # right roll: left aileron trailing edge down
            roll.key(o, [(1, 0), (24, k * a), (48, 0), (72, -k * a), (96, 0)])
        for side, o in stab.items():
            k = 1.0 if side == "L" else -1.0
            roll.key(o, [(1, 0), (24, k * s_), (48, 0), (72, -k * s_), (96, 0)])
        made.append(roll)
    if stab:
        pitch = Clip("Controls_Pitch", 72)             # nose up (trailing edges up), nose down, centre
        p = ANGLES["stab_pitch"]
        for o in stab.values():
            pitch.key(o, [(1, 0), (24, -p), (48, p * 0.6), (72, 0)])
        made.append(pitch)
    if rud:
        yaw = Clip("Controls_Yaw", 72)                 # right rudder, left rudder, centre
        r = ANGLES["rudder"]
        for o in rud.values():
            yaw.key(o, [(1, 0), (24, r), (48, -r), (72, 0)])
        made.append(yaw)
    if lef or tef:
        fd = Clip("Flaps_Down", 72)
        fu = Clip("Flaps_Up", 72)
        for o in lef:
            fd.key(o, [(1, 0), (64, ANGLES["le_flap"]), (72, ANGLES["le_flap"])])
            fu.key(o, [(1, ANGLES["le_flap"]), (64, 0), (72, 0)])
        for o in tef:
            fd.key(o, [(1, 0), (64, ANGLES["te_flap"]), (72, ANGLES["te_flap"])])
            fu.key(o, [(1, ANGLES["te_flap"]), (64, 0), (72, 0)])
        made += [fd, fu]
    # extras that exist on these models
    if by("wing_fold"):
        fo = Clip("WingFold_Fold", 120)
        un = Clip("WingFold_Unfold", 120)
        for o in by("wing_fold"):
            fo.key(o, [(1, 0), (110, ANGLES["wing_fold"]), (120, ANGLES["wing_fold"])])
            un.key(o, [(1, ANGLES["wing_fold"]), (110, 0), (120, 0)])
        made += [fo, un]
    if by("hook"):
        o = by("hook")[0]
        hd = Clip("Hook_Down", 36)
        hd.key(o, [(1, 0), (30, ANGLES["hook"]), (36, ANGLES["hook"])])
        hu = Clip("Hook_Up", 48)
        hu.key(o, [(1, ANGLES["hook"]), (40, 0), (48, 0)])
        made += [hd, hu]
    return made


# ----------------------------------------------------------------------------
def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--glb", action="store_true")
    args = ap.parse_args(argv)
    src = bpy.data.filepath
    if not src:
        raise SystemExit("save the .blend first: the result is written beside it as a new file")
    out = args.out or os.path.splitext(src)[0] + "_animated.blend"
    if os.path.abspath(out) == os.path.abspath(src):
        raise SystemExit("refusing to overwrite the source file")
    sc = bpy.context.scene
    sc.render.fps = FPS
    say("Source: %s" % src)
    if any(a.name.startswith(("Gear_", "Canopy_", "Controls_")) for a in bpy.data.actions):
        raise SystemExit("this file already has the animation clips; run on the original model")
    parts = inspect(sc)
    say("")
    say("== Set-up ==")
    made = build_clips(parts)
    # build each clip and lay it straight onto the NLA showreel (clips share
    # objects, so each must be pushed before the next one is keyed)
    frame = 1
    for c in made:
        c.build()
        push_to_nla(c, frame)
        sc.timeline_markers.new(c.name, frame=frame)
        say("  clip   %-18s frames %4d-%4d  (%d objects)" % (c.name, frame, frame + c.length - 1, len(c.tracks)))
        frame += c.length + 12
    sc.frame_start, sc.frame_end = 1, frame
    sc.frame_set(0)
    # crew
    say("")
    say("== Crew ==")
    eyes = [o.name for o in sc.objects if o.name.endswith(("Eye_Front", "Eye_Rear"))]
    if not parts.get("pilot"):
        say("  No pilot or crew mesh is modelled (eye points only: %s), so no head animation was" % ", ".join(eyes))
        say("  set up. Nothing was added.")
        if any(e.endswith("Eye_Rear") for e in eyes):
            say("  This is the two-seat F/A-18B: the second crew member is also missing. Say if you want")
            say("  pilot figures added before any geometry is created.")
    txt = bpy.data.texts.get("Animation_Report") or bpy.data.texts.new("Animation_Report")
    txt.from_string("\n".join(report))
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True)
    say("")
    say("Saved %s (source left unchanged)" % out)
    with open(os.path.splitext(out)[0] + "_report.txt", "w") as f:
        f.write("\n".join(report) + "\n")
    if args.glb:
        glb = os.path.splitext(out)[0] + ".glb"
        bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_visible=True, export_extras=True,
                                  export_cameras=True, export_animations=True,
                                  export_animation_mode="NLA_TRACKS", export_anim_slide_to_zero=True,
                                  export_force_sampling=True)
        print("Saved", glb)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
