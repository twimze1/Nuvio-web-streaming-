"""Animation clips for the He 51 A-1, saved to a new file beside the model.

    blender -b -P tools/animate.py -- [He-51A-1.blend] [--glb]

Writes He-51A-1_animated.blend (the source file is not changed) and, with
--glb, He-51A-1_animated.glb.  Every moving part rests at zero under its
"<name>_Hinge" empty and turns about its local X axis, so the clips are
plain rotation keys.  Each clip is an NLA track of the same name on every
object it moves; the glTF exporter merges them into one animation per clip.

Clips (24 fps):
  Prop_Spin        one turn of the propeller, linear, loops
  Controls_Roll    ailerons (upper wing only), opposite ways
  Controls_Pitch   elevators (nose up, nose down, centre), with the stick
  Controls_Yaw     rudder (right, left, centre)
The He 51 has no flaps.  The deflection angles are for show; they are not
the type's rigging limits.
"""
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ANGLES = {"aileron": 20.0, "elevator": 22.0, "rudder": 25.0, "stick": 12.0}


def main(argv):
    glb = "--glb" in argv
    files = [a for a in argv if not a.startswith("--")]
    src = files[0] if files else os.path.join(os.path.dirname(HERE), "He-51A-1.blend")
    bpy.ops.wm.open_mainfile(filepath=src)
    sc = bpy.context.scene
    sc.render.fps = 24
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    O = bpy.data.objects
    start = [1]
    report = []

    def clip(name, length, parts):
        """parts: [(object, [(frame, degrees), ...])]"""
        for obj, keys in parts:
            ad = obj.animation_data or obj.animation_data_create()
            act = bpy.data.actions.new("%s_%s" % (name, obj.name))
            ad.action = act
            for f, deg in keys:
                obj.rotation_euler.x = math.radians(deg)
                obj.keyframe_insert("rotation_euler", index=0, frame=f)
            obj.rotation_euler.x = 0.0
            ad.action = None
            track = ad.nla_tracks.new()
            track.name = name
            track.strips.new(name, start[0], act)
        report.append("%-16s frames %4d-%4d  (%d objects)" % (name, start[0], start[0] + length - 1, len(parts)))
        start[0] += length + 12

    a, e, r, s = (ANGLES[k] for k in ("aileron", "elevator", "rudder", "stick"))
    clip("Prop_Spin", 24, [(O["He51_Propeller"], [(1, 0), (25, 360)])])
    clip("Controls_Roll", 96, [(O["He51_Aileron_L"], [(1, 0), (24, a), (48, 0), (72, -a), (96, 0)]),
                               (O["He51_Aileron_R"], [(1, 0), (24, -a), (48, 0), (72, a), (96, 0)])])
    clip("Controls_Pitch", 72, [(O["He51_Elevator_" + side], [(1, 0), (24, -e), (48, e * 0.7), (72, 0)]) for side in "LR"]
         + [(O["He51_Stick"], [(1, 0), (24, -s), (48, s * 0.7), (72, 0)])])
    clip("Controls_Yaw", 72, [(O["He51_Rudder"], [(1, 0), (24, r), (48, -r), (72, 0)])])
    sc.frame_start, sc.frame_end = 1, start[0]
    sc.frame_set(0)
    out = os.path.splitext(src)[0] + "_animated.blend"
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
    print("\n".join(report))
    print("saved", out)
    if glb:
        path = os.path.splitext(out)[0] + ".glb"
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_visible=True, export_extras=True,
                                  export_cameras=True, export_animations=True, export_animation_mode="NLA_TRACKS",
                                  export_anim_slide_to_zero=True, export_force_sampling=True)
        print("saved", path)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
