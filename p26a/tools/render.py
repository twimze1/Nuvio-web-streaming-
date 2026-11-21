"""Cycles renders of the P-26A under a physical sky, standing on its wheels.

    blender -b -P tools/render.py -- P-26A_Peashooter.blend OUT_PREFIX [VIEW ...]
        [--size W H] [--samples N] [--clay] [--level] [--sun ELEV AZIMUTH]

--level keeps the fuselage level with no ground (flight attitude).
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import p26a as P  # noqa: E402

# azimuth from the nose towards port (deg), elevation, distance (m), lens (mm), target (design x, y, z)
VIEWS = {
    "hero": (38, 7, 14.5, 50, (2.9, 0, -0.3)),
    "side": (90, 2, 21, 85, (3.5, 0, -0.2)),
    "front": (0, 3, 17, 70, (1.0, 0, -0.2)),
    "rear": (148, 12, 14.5, 50, (3.2, 0, -0.2)),
    "top": (90, 86, 21, 50, (3.4, 0, 0)),
    "engine": (28, 4, 3.6, 45, (0.7, 0, -0.1)),
    "cockpit": (158, 38, 3.0, 40, (2.3, 0, 0.5)),
    "gear": (62, -3, 4.2, 50, (1.5, -0.5, -0.9)),
    "tail": (130, 8, 4.5, 50, (6.3, 0, 0.3)),
    "starboard": (-55, 10, 10.5, 50, (2.9, 0, -0.3)),
    "sight": (58, 27, 2.3, 50, (1.45, 0, 0.55)),
}


def sky(sc, elev, azim, pose):
    w = bpy.data.worlds.new("Sky")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    tex = nt.nodes.new("ShaderNodeTexSky")
    for kind in ("MULTIPLE_SCATTERING", "NISHITA", "SINGLE_SCATTERING", "HOSEK_WILKIE"):
        try:
            tex.sky_type = kind
            break
        except TypeError:
            continue
    for attr, val in (("sun_elevation", math.radians(elev)), ("sun_rotation", math.radians(azim))):
        if hasattr(tex, attr):
            setattr(tex, attr, val)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.vector_type = "NORMAL"
    mp.inputs["Rotation"].default_value = pose.to_euler()
    nt.links.new(tc.outputs["Generated"], mp.inputs[0])
    nt.links.new(mp.outputs[0], tex.inputs[0])
    nt.links.new(tex.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = 0.10


def ground(sc, z):
    me = bpy.data.meshes.new("Ground")
    s = 300.0
    me.from_pydata([(-s, -s, z), (s, -s, z), (s, s, z), (-s, s, z)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new("Ground", me)
    sc.collection.objects.link(ob)
    m = bpy.data.materials.new("Ground")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.6
    noise.inputs["Detail"].default_value = 10.0
    noise.inputs["Roughness"].default_value = 0.7
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.3, 0.75
    ramp.color_ramp.elements[0].color = (0.055, 0.053, 0.048, 1)
    ramp.color_ramp.elements[1].color = (0.125, 0.12, 0.11, 1)
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(noise.outputs[0], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.9
    me.materials.append(m)
    return ob


def main(argv):
    opts = {"size": (1600, 900), "samples": 48, "clay": False, "level": False, "sun": (40.0, 150.0), "scale": 1.0, "exposure": 0.0, "hide": []}
    pos, i = [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--size":
            opts["size"] = (int(argv[i + 1]), int(argv[i + 2])); i += 3
        elif a == "--samples":
            opts["samples"] = int(argv[i + 1]); i += 2
        elif a == "--sun":
            opts["sun"] = (float(argv[i + 1]), float(argv[i + 2])); i += 3
        elif a == "--scale":                     # camera distances, for a larger or smaller aircraft
            opts["scale"] = float(argv[i + 1]); i += 2
        elif a == "--view":                      # a one-off view: name, azimuth, elevation, distance, lens, target x y z
            VIEWS[argv[i + 1]] = (float(argv[i + 2]), float(argv[i + 3]), float(argv[i + 4]), float(argv[i + 5]),
                                  tuple(float(v) for v in argv[i + 6:i + 9])); i += 9
        elif a == "--hide":                      # leave out objects whose name contains this (to look inside)
            opts["hide"].append(argv[i + 1]); i += 2
        elif a == "--exposure":                  # stops; negative for a pale aircraft
            opts["exposure"] = float(argv[i + 1]); i += 2
        elif a in ("--clay", "--level"):
            opts[a[2:]] = True; i += 1
        else:
            pos.append(a); i += 1
    bpy.ops.wm.open_mainfile(filepath=pos[0])
    prefix, views = pos[1], pos[2:] or ["hero"]
    sc = bpy.context.scene
    for o in bpy.data.objects:
        if any(h in o.name for h in opts["hide"]):
            o.hide_render = True
    root = next(o for o in bpy.data.objects if o.type == "EMPTY" and "ground_pitch_deg" in o.keys())
    x_ref = root.get("x_ref", P.X_REF)
    tb = lambda p: Vector((-p[1], p[0] - x_ref, p[2]))
    # The aircraft stays level at the origin (the procedural paint is laid
    # out in world coordinates); the ground, cameras and sky are tilted
    # round it instead, which gives the same picture as a tail-down aircraft.
    pose = Matrix.Identity(4)
    if not opts["level"]:
        pivot = Vector((0, root["main_wheel_x"], root["ground_z"]))
        pose = Matrix.Translation(pivot) @ Matrix.Rotation(-math.radians(root["ground_pitch_deg"]), 4, "X") @ Matrix.Translation(-pivot)
        ground(sc, root["ground_z"] - 0.003).matrix_world = pose.inverted()
    unpose = pose.inverted()
    if opts["clay"]:
        clay = bpy.data.materials.new("Clay")
        clay.use_nodes = True
        b = next(n for n in clay.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        b.inputs["Base Color"].default_value = (0.55, 0.55, 0.55, 1)
        b.inputs["Roughness"].default_value = 0.6
        for o in bpy.data.objects:
            if o.type == "MESH" and o.name != "Ground":
                for s in o.material_slots:
                    if s.material and not s.material.name.endswith("_Glass"):
                        s.material = clay
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = opts["samples"]
    try:
        sc.cycles.use_denoising = True
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except (TypeError, AttributeError):
        sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y = opts["size"]
    sc.render.resolution_percentage = 100
    try:
        sc.view_settings.view_transform = "AgX"
    except TypeError:
        pass
    sc.view_settings.exposure = opts["exposure"]
    sky(sc, opts["sun"][0], opts["sun"][1], pose)
    cam = bpy.data.objects.new("RenderCam", bpy.data.cameras.new("RenderCam"))
    sc.collection.objects.link(cam)
    cam.data.clip_start = 0.02
    for v in views:
        if v == "pilot":
            sc.camera = next(o for o in bpy.data.objects if o.type == "CAMERA" and o.name.endswith("_Cam"))
        else:
            az, el, d, lens, tgt = VIEWS[v]
            t = pose @ tb(tuple(c * (opts["scale"] if k == 0 else 1.0) for k, c in enumerate(tgt)))
            d *= opts["scale"]
            az, el = math.radians(az), math.radians(el)
            loc = t + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * d
            m = Matrix.Translation(loc) @ (t - loc).to_track_quat("-Z", "Y").to_matrix().to_4x4()
            cam.matrix_world = unpose @ m
            cam.data.lens = lens
            sc.camera = cam
        sc.render.filepath = "%s%s.png" % (prefix, v)
        bpy.ops.render.render(write_still=True)
        print("rendered", sc.render.filepath)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
