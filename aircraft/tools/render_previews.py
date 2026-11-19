"""Preview renders of a generated Hornet .blend.

    blender -b -P render_previews.py -- ../FA-18A_Hornet.blend OUT_PREFIX MODE

MODE  views   Workbench: two 3/4 views, a low view, top/side/front orthographic
              views and a cockpit close-up            -> OUT_PREFIX_<view>.png
      stores  the 3/4 and low views with the AIM-9 / AIM-7 loadout shown
      hero    one EEVEE render                         -> OUT_PREFIX_hero.png
"""
import bpy, sys, math
from mathutils import Vector
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
blend, out, mode = argv[0], argv[1], argv[2]
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
if mode == 'stores':
    for c in bpy.data.collections:
        if 'Stores' in c.name:
            c.hide_render = False
            for o in c.objects: o.hide_render = False
sc.render.engine = 'BLENDER_WORKBENCH' if mode != 'hero' else 'BLENDER_EEVEE'
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'MATERIAL'
sc.display.shading.show_cavity = True
sc.display.shading.show_object_outline = True
sc.render.film_transparent = False
w = bpy.data.worlds.new('w'); sc.world = w
w.color = (0.9, 0.92, 0.95)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
sc.collection.objects.link(cam); sc.camera = cam
if mode == 'hero':
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.30, 0.34, 0.40, 1)
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 2.2
    sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(30))
    sc.collection.objects.link(sun)
def shoot(loc, target, path, ortho=None, res=(1400, 900)):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'; cam.data.lens = 50
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
if mode in ('views', 'stores'):
    shoot((-16, -18, 9), (0, 0.4, 0), out + '_q1.png')
    shoot((14, 20, 7), (0, 0.6, 0), out + '_q2.png')
    shoot((-9, -9, -5), (0, -1, -0.5), out + '_low.png')
    if mode == 'views':
        shoot((0, 0, 40), (0, 0, 0), out + '_top.png', ortho=18.5, res=(1300, 1300))
        cam.rotation_euler = (0, 0, 0)
        shoot((40, 0, 0.3), (0, 0, 0.3), out + '_side.png', ortho=18.5, res=(1400, 600))
        shoot((0, -40, 0.3), (0, 0, 0.3), out + '_front.png', ortho=12.5, res=(1300, 600))
        shoot((-5, -6.5, 3.2), (0, -5.5, 1.0), out + '_cockpit.png', res=(1000, 700))
else:
    shoot((-15, -17, 6), (0, 0.4, 0), out + '_hero.png', res=(1200, 760))
