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
     Like the hinges, each pivot sits under a static "<name>_Pivot_Frame" empty
     that holds its orientation, so the pivot itself rests at zero and only
     its local X rotation is keyed.
     Main legs also get a "<name>_Twist" empty that turns the post about its
     own axis as it swings aft, so the wheel ends up lying flat (as on the
     Hornet).
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
    # the outer panels fold to vertical (NATOPS 2.11): 90 deg past the panel's
    # own plane plus the wing's 3 deg anhedral
    "wing_fold": 93.0,
    "hook": 30.0,
}
# Flaps_Down is the NATOPS ground setting with the flap switch in FULL
# (2.8.4): leading-edge flaps 12 deg, trailing-edge flaps 45 deg (43-45),
# ailerons drooped 42 deg, and both rudders toed in 30 deg (maximum toe-in
# with weight on wheels).
FLAPS_FULL = {"le_flap": 12.0, "te_flap": 45.0, "aileron": 42.0, "rudder_toe_in": 30.0}

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
    ("launch_bar", r"launch_?bar"),
    ("gear_door", r"door"),
    ("gear_brace", r"brace"),
    ("nose_gear", r"nose_?gear"),
    ("main_gear", r"main_?gear"),
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
                    "hook", "gear_door", "gear_brace", "launch_bar"):
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


def make_pivot(obj, location, axis, up=Vector((0, 0, 1)), suffix="_Pivot"):
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
    # a static empty holds the hinge orientation; its child does the rotating
    # and rests at zero, so a clip only ever keys its local X rotation
    base = bpy.data.objects.new(obj.name + suffix + "_Frame", None)
    base.empty_display_type = "PLAIN_AXES"
    base.empty_display_size = 0.15
    base.rotation_mode = "QUATERNION"
    piv = bpy.data.objects.new(obj.name + suffix, None)
    piv.empty_display_type = "SINGLE_ARROW"
    piv.empty_display_size = 0.3
    for c in obj.users_collection:
        c.objects.link(base)
        c.objects.link(piv)
    base.parent = obj.parent
    base.matrix_world = frame
    bpy.context.view_layer.update()
    piv.parent = base
    piv.matrix_parent_inverse = Matrix.Identity(4)
    piv.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = piv
    obj.matrix_world = world                    # keep the leg exactly where it is
    piv["pivot"] = "added by setup_animations.py; rotate about local X"
    return piv


def tyre_frame(obj):
    """Centre and axle direction of the wheel: from the leg's "wheel_centre" /
    "wheel_axle" properties (object-local) if present, else from the faces
    using a tyre material, else None."""
    import numpy as np
    if "wheel_centre" in obj.keys() and "wheel_axle" in obj.keys():
        M = obj.matrix_world
        return (M @ Vector(obj["wheel_centre"]),
                (M.to_3x3() @ Vector(obj["wheel_axle"])).normalized())
    mats = [i for i, m in enumerate(obj.data.materials) if m and re.search("tire|tyre", m.name.lower())]
    idx = {v for p in obj.data.polygons if p.material_index in mats for v in p.vertices}
    if not idx:
        return None
    M = obj.matrix_world
    V = [M @ obj.data.vertices[i].co for i in idx]
    lo = Vector([min(v[k] for v in V) for k in range(3)])
    hi = Vector([max(v[k] for v in V) for k in range(3)])
    c = (lo + hi) / 2
    A = np.array([list(v - c) for v in V])
    w, U = np.linalg.eigh(A.T @ A)
    return c, Vector(U[:, 0]).normalized()        # the tyre is thinnest along its axle


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
    low = [v for v in V if v.z < zlow + 0.80 * (P.z - zlow) * 0.5]
    W = sum(low, Vector()) / len(low)              # centre of the wheel(s): roughly the axle
    tf = tyre_frame(obj)
    if tf is not None:
        W = tf[0]                                  # exact, from the tyre faces
    a = W - P
    side = 1.0 if P.x > 0 else -1.0
    if kind == "nose_gear":
        b = Vector((0.0, -1.0, 0.215)).normalized() * a.length       # Blender -Y is forward
    else:
        b = Vector((-side * 0.30, 1.0, 0.30)).normalized() * a.length  # aft, inboard, up
    axis = a.cross(b)
    angle = a.angle(b)
    return P, axis, math.degrees(angle)


# ----------------------------------------------------------------------------
# stowed positions: fold a part until it is inside the lower skin
# ----------------------------------------------------------------------------
_skin = {}


def lower_skin():
    """BVH trees of the airframe skin: visible meshes whose name contains 'fuselage'."""
    if "trees" not in _skin:
        from mathutils.bvhtree import BVHTree
        fus = [o for o in bpy.context.scene.objects if o.type == "MESH" and "fuselage" in o.name.lower()
               and not any(("Library" in c.name or "Loadout" in c.name) for c in o.users_collection)]
        _skin["trees"] = [BVHTree.FromPolygons(world_verts(o), [list(p.vertices) for p in o.data.polygons])
                          for o in fus]
    return _skin["trees"]


def skin_z(p):
    """Height of the lowest skin surface above or below world point p (None outside it)."""
    zs = []
    for t in lower_skin():
        hit = t.ray_cast(Vector((p.x, p.y, -100.0)), Vector((0, 0, 1)))
        if hit[0] is not None:
            zs.append(hit[0].z)
    return min(zs) if zs else None


def mesh_verts(obj):
    """World vertices of obj and of every mesh carried below it."""
    V = world_verts(obj) if obj.type == "MESH" else []
    for c in obj.children_recursive:
        if c.type == "MESH":
            V += world_verts(c)
    return V


def top_z(p):
    """Height of the highest skin surface above or below world point p (None outside it)."""
    zs = []
    for t in lower_skin():
        hit = t.ray_cast(Vector((p.x, p.y, 100.0)), Vector((0, 0, -1)))
        if hit[0] is not None:
            zs.append(hit[0].z)
    return max(zs) if zs else None


def inside_skin(V, P, R, clearance):
    """Every transformed vertex between the lower and upper skin, and at least
    `clearance` from the skin in any direction (the nacelle sides are steep)."""
    trees = lower_skin()
    for v in V:
        w = P + R @ (v - P)
        s = skin_z(w)
        if s is None or w.z < s + clearance:
            return False
        t = top_z(w)
        if t is None or w.z > t - clearance:
            return False
        if any(tr.find_nearest(w, clearance)[0] is not None for tr in trees):
            return False
    return True


def main_stow(obj, P, W, clearance=0.01):
    """Aft retraction with the wheel turned flat, as on the Hornet: the post
    turns about its own axis (carrying the trailing arm and wheel round) while
    it swings aft about its top.  Searches swing directions around straight
    aft and twist angles, and returns (pivot, axis, angle, twist axis, twist,
    flatness, fits) for the pose closest to "post aft, wheel flat under the
    nacelle, just aft of the pivot" that keeps the whole leg inside the skin
    and on its own side of the centreline.  The post comes from the leg's
    "post_top" / "post_axis" properties if present (else the pivot-to-wheel
    line)."""
    M = obj.matrix_world
    if "post_top" in obj.keys() and "post_axis" in obj.keys():
        P = M @ Vector(obj["post_top"])
        p = (M.to_3x3() @ Vector(obj["post_axis"])).normalized()
    else:
        p = (W - P).normalized()
    tf = tyre_frame(obj)
    axle = tf[1] if tf else Vector((1, 0, 0))
    side = 1.0 if P.x > 0 else -1.0                 # Blender +X is port
    V = mesh_verts(obj)
    w = W - P
    ideal = P + Vector((0.0, w.length, 0.10))        # wheel just aft of the pivot, under the nacelle
    cands = []
    for e in range(-10, 41, 2):
        for az in range(-30, 31, 3):
            el, a_ = math.radians(e), math.radians(az)
            d = Vector((side * math.sin(a_) * math.cos(el), math.cos(a_) * math.cos(el), math.sin(el)))
            ax1 = p.cross(d)
            if ax1.length < 1e-9:
                continue
            ax1.normalize()
            ang = p.angle(d)
            R1 = Matrix.Rotation(ang, 3, ax1)
            for t in range(-180, 180, 3):
                R = R1 @ Matrix.Rotation(math.radians(t), 3, p)
                flat = abs((R @ axle).z)
                if flat < 0.7:
                    continue
                wc = P + R @ w
                cost = 6.0 * (1.0 - flat) + (wc - ideal).length
                cands.append((cost, ax1, math.degrees(ang), float(t), flat, R))
    cands.sort(key=lambda c: c[0])
    for cost, ax1, ang, t, flat, R in cands:
        if not lower_skin():
            break
        if not inside_skin(V, P, R, clearance):
            continue
        if any(side * (P + R @ (v - P)).x < 0.03 for v in V):
            continue                                  # stays on its own side of the centreline
        return P, ax1, ang, p, t, flat, True
    c = cands[0]
    return P, c[1], c[2], p, c[3], c[4], False


def fold_into_skin(obj, P, axis, lo, hi, clearance, step=0.5):
    """Smallest rotation (deg, lo..hi) of obj (and the meshes it carries) about
    `axis` through P that leaves every vertex at least `clearance` above the
    lower skin, or None."""
    if not lower_skin():
        return None
    V = mesh_verts(obj)
    axis = axis.normalized()

    def inside(deg):
        R = Matrix.Rotation(math.radians(deg), 3, axis)
        for v in V:
            w = P + R @ (v - P)
            s = skin_z(w)
            if s is None or w.z < s + clearance:
                return False
        return True

    d = lo
    while d <= hi:
        if inside(d):
            a, c = d - step, d                       # a fails (or is lo), c passes
            for _ in range(8):
                m = (a + c) / 2
                a, c = (a, m) if inside(m) else (m, c)
            return c
        d += step
    return None


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
    twists = []
    for kind in ("nose_gear", "main_gear"):
        for o in by(kind):
            if "stow_angle" in o.keys():
                # the model carries its own retraction (worked out when its bays were cut)
                M = o.matrix_world
                P = M @ Vector(o["stow_pivot"])
                axis = (M.to_3x3() @ Vector(o["stow_axis"])).normalized()
                ang = float(o["stow_angle"])
                piv = make_pivot(o, P, axis)
                how = "from the model's stow data"
                if "stow_twist" in o.keys():
                    tw = float(o["stow_twist"])
                    post = (M.to_3x3() @ Vector(o["stow_twist_axis"])).normalized()
                    twi = make_pivot(o, P, post, suffix="_Twist")
                    twists.append((twi, tw))
                    how += ", post turned %.0f deg about its axis" % tw
                gear.append((kind, piv, ang))
                say("  pivot  %-28s at (%.2f, %.2f, %.2f), retract %.1f deg (%s)"
                    % (piv.name, P.x, P.y, P.z, ang, how))
                continue
            P, axis, ang = gear_pivot(o, kind)
            how = "stow direction"
            if kind == "nose_gear":
                # swing forward just far enough that the wheels sit inside the
                # lower skin, clear of the closed doors (as low in the bay as possible)
                fit = fold_into_skin(o, P, axis, 60.0, 150.0, 0.012)
                if fit is not None:
                    ang, how = fit, "fitted inside the lower skin"
                piv = make_pivot(o, P, axis)
            else:
                # aft, turning the wheel flat: pivot, then a twist about the leg
                tf = tyre_frame(o)
                W = tf[0] if tf else P + Vector((0, 0, -1))
                P, axis, ang, post, tw, flat, fits = main_stow(o, P, W)
                how = ("post turned %.0f deg about its axis, wheel within %.0f deg of flat, %s"
                       % (tw, math.degrees(math.acos(min(1.0, flat))),
                          "inside the skin" if fits else "NOT fully inside the skin"))
                piv = make_pivot(o, P, axis)
                twi = make_pivot(o, P, post, suffix="_Twist")
                twists.append((twi, tw))
            gear.append((kind, piv, ang))
            say("  pivot  %-28s at (%.2f, %.2f, %.2f), retract %.1f deg (%s)"
                % (piv.name, P.x, P.y, P.z, ang, how))
    doors = by("gear_door")
    braces = []
    for o in by("gear_brace"):
        if "stow_fold" in o.keys():
            fold, fit = float(o["stow_fold"]), True
            braces.append((o, fold))
            say("  brace  %-28s folds %.1f deg" % (o.name, fold))
            continue
        M = o.matrix_world
        fit = fold_into_skin(o, M.translation.copy(), M.col[0].xyz, 0.0, 120.0, 0.008)
        fold = 32.0 if fit is None else fit + 1.0
        braces.append((o, fold))
        say("  brace  %-28s folds %.1f deg%s" % (o.name, fold, "" if fit is not None else " (default)"))
    if gear:
        # retract: legs swing up, the nose-gear brace folds with them, then the
        # bay doors close; extend is the reverse (doors open first)
        ret = Clip("Gear_Retract", 132)
        ext = Clip("Gear_Extend", 132)
        for kind, piv, ang in gear:
            t0, t1 = (10, 96) if kind == "nose_gear" else (16, 104)
            ret.key(piv, [(1, 0.0), (t0, 0.0), (t1, ang), (132, ang)])
            ext.key(piv, [(1, ang), (30, ang), (116, 0.0), (132, 0.0)])
        for twi, tw in twists:
            ret.key(twi, [(1, 0.0), (16, 0.0), (104, tw), (132, tw)])
            ext.key(twi, [(1, tw), (30, tw), (116, 0.0), (132, 0.0)])
        for o, fold in braces:
            t0, t1 = (10, 90) if "nose" in o.name.lower() else (16, 100)
            ret.key(o, [(1, 0.0), (t0, 0.0), (t1, fold), (132, fold)])
            ext.key(o, [(1, fold), (36, fold), (116, 0.0), (132, 0.0)])
        for o in doors:
            tr = float(o.get("travel", 90.0))      # closing angle (doors that splay open travel further)
            ret.key(o, [(1, 0.0), (106, 0.0), (128, tr), (132, tr)])
            ext.key(o, [(1, tr), (4, tr), (28, 0.0), (132, 0.0)])
        # a launch bar that folds against its strut for stowage
        for o in by("launch_bar"):
            if "stow_fold" in o.keys():
                f = float(o["stow_fold"])
                ret.key(o, [(1, 0.0), (10, 0.0), (96, f), (132, f)])
                ext.key(o, [(1, f), (30, f), (116, 0.0), (132, 0.0)])
                say("  bar    %-28s folds %.0f deg against the strut as the gear retracts" % (o.name, f))
        made += [ret, ext]
    if not doors:
        say("  NOTE   no separate gear-door objects found. Separate door faces into objects whose names")
        say("         contain 'door' (with a 'hinge' property, or use the nose-gear doors as a pattern)")
        say("         and re-run to animate them.")
    else:
        say("  doors  %s close after retraction and open first on extension"
            % ", ".join(o.name for o in doors))
    # launch bar: lowered for a catapult hook-up until its tip is just above the deck
    if by("launch_bar"):
        o = by("launch_bar")[0]
        tyre_z = [v.z for g in by("nose_gear") + by("main_gear") for v in world_verts(g)]
        M = o.matrix_world
        P, axis = M.translation.copy(), M.col[0].xyz.normalized()
        V = world_verts(o)
        down = None
        if tyre_z:
            deck = min(tyre_z)
            for k in range(1, 1201):
                R = Matrix.Rotation(math.radians(k / 10), 3, axis)
                if min((P + R @ (v - P)).z for v in V) <= deck + 0.03:
                    down = k / 10
                    break
        if down is None:
            down = 45.0
        say("  bar    %-28s lowers %.1f deg for a catapult hook-up (tip 3 cm above the deck)" % (o.name, down))
        lo = Clip("LaunchBar_Down", 48)
        lo.key(o, [(1, 0.0), (40, down), (48, down)])
        up = Clip("LaunchBar_Up", 48)
        up.key(o, [(1, down), (40, 0.0), (48, 0.0)])
        made += [lo, up]
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
        drooped = [(o, FLAPS_FULL["le_flap"]) for o in lef] + [(o, FLAPS_FULL["te_flap"]) for o in tef] + \
                  [(o, FLAPS_FULL["aileron"]) for o in ail.values()]
        # toe-in: both rudder trailing edges swing inboard (port rudder to
        # starboard, the positive sense of the rudder hinges, and vice versa)
        drooped += [(o, FLAPS_FULL["rudder_toe_in"] * (1.0 if side == "L" else -1.0)) for side, o in rud.items()]
        for o, a in drooped:
            fd.key(o, [(1, 0), (64, a), (72, a)])
            fu.key(o, [(1, a), (64, 0), (72, 0)])
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
