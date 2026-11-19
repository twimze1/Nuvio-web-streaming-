"""Preview renders of a generated Hornet .blend.

    blender -b -P render_previews.py -- ../FA-18A_Hornet.blend OUT_PREFIX MODE [ARG]

MODE  views     Workbench: 3/4 views, low view, top/side/front orthographic
                                                        -> OUT_PREFIX_<view>.png
      hero      EEVEE 3/4 view                          -> OUT_PREFIX_hero.png
      cockpit   EEVEE from every eye-point camera, looking 16 deg down
                                                        -> OUT_PREFIX_cockpit_<seat>.png
      loadout   EEVEE low 3/4 and front views with the named loadout shown
                (ARG = loadout name, e.g. Strike_Mk83)  -> OUT_PREFIX_<name>_low.png / _front.png
      library   EEVEE line-up of every store             -> OUT_PREFIX_library.png
"""
import math
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
blend, out, mode = argv[0], argv[1], argv[2]
arg = argv[3] if len(argv) > 3 else None
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene


def eevee(sky=(0.42, 0.50, 0.62, 1), strength=1.0, sun=3.0):
    sc.render.engine = "BLENDER_EEVEE"
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = sky
    w.node_tree.nodes["Background"].inputs[1].default_value = strength
    s = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    s.data.energy = sun
    s.rotation_euler = (math.radians(38), math.radians(-15), math.radians(150))
    sc.collection.objects.link(s)


def workbench():
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_cavity = True
    sh.show_object_outline = True
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.color = (0.9, 0.92, 0.95)


cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)


def shoot(loc, target, path, ortho=None, res=(1400, 900), lens=50):
    sc.camera = cam
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = "PERSP"
        cam.data.lens = lens
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def show_loadout(name):
    for c in bpy.data.collections:
        if " Loadout " in c.name:
            vis = c.name.endswith(" " + name)
            c.hide_viewport = not vis
            c.hide_render = not vis


if mode == "views":
    workbench()
    shoot((-16, -18, 9), (0, 0.4, 0), out + "_q1.png")
    shoot((14, 20, 7), (0, 0.6, 0), out + "_q2.png")
    shoot((-9, -9, -5), (0, -1, -0.5), out + "_low.png")
    shoot((0, 0, 40), (0, 0, 0), out + "_top.png", ortho=18.5, res=(1300, 1300))
    shoot((40, 0, 0.3), (0, 0, 0.3), out + "_side.png", ortho=18.5, res=(1400, 600))
    shoot((0, -40, 0.3), (0, 0, 0.3), out + "_front.png", ortho=12.5, res=(1300, 600))
elif mode == "hero":
    eevee()
    shoot((-15, -17, 6), (0, 0.4, 0), out + "_hero.png", res=(1400, 880))
elif mode == "cockpit":
    eevee((0.55, 0.65, 0.80, 1), 1.2, 3.5)
    for c in [o for o in sc.objects if o.type == "CAMERA" and o is not cam]:
        sc.camera = c
        c.rotation_euler.x = math.radians(-16)
        sc.render.resolution_x, sc.render.resolution_y = 1400, 900
        sc.render.filepath = out + "_cockpit_" + c.name.split("_")[-1] + ".png"
        bpy.ops.render.render(write_still=True)
elif mode == "loadout":
    eevee()
    show_loadout(arg)
    shoot((-12, -16, -5.5), (0, 0.5, -0.8), out + "_" + arg + "_low.png", lens=32)
    shoot((0, -40, -0.5), (0, 0, -0.5), out + "_" + arg + "_front.png", ortho=13.5, res=(1500, 700))
elif mode == "library":
    eevee((0.6, 0.62, 0.66, 1), 1.0, 3.0)
    lib = bpy.data.collections["Stores Library"]
    lib.hide_viewport = False
    lib.hide_render = False
    for c in bpy.data.collections:
        if c.name.startswith("FA-18"):
            c.hide_render = True
    shoot((-3, 38, 7), (-1, 46, 0), out + "_library.png", lens=30, res=(1500, 1000))
