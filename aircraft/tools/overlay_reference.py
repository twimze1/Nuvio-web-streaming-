"""Check a generated Hornet against a scanned general-arrangement drawing.

Projects every visible mesh orthographically and draws the model's outline
(red) and footprint (tint) over the drawing, so shape and proportion errors
show up directly.  Runs with Blender's Python (or the `bpy` pip module).

usage:
  blender -b -P overlay_reference.py -- model.blend VIEW out.png REF.png PX_PER_M OX OY [X0 Y0 X1 Y1]
  blender -b -P overlay_reference.py -- model.blend VIEW out.png          (plain render, no reference)

VIEW is top | side | front.  The drawing is registered by its scale (pixels
per metre) and the pixel position of the nose tip (top/side) or of the nose
tip on the centreline (front):
  top   col = OX + x*s, row = OY - y*s     (x aft from nose tip, y starboard)
  side  col = OX + x*s, row = OY - z*s     (z up from the nose-tip waterline)
  front col = OX - y*s, row = OY - z*s
X0..Y1 optionally crops the result.

Registrations used for the supplied sheets (README lists them in full):
  F/A-18B sheet (1200x1015):  s=57.1, top 182.5 453, side 233 907, front 373 192
  F/A-18A sheet (2471x1649):  s=82.0, top 1057 526, side 1037 1501, front 1301 857
"""
import sys, math
import bpy, numpy as np
from PIL import Image, ImageDraw, ImageFilter
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import fa18_hornet as F

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
blend, view, out = argv[0:3]
bpy.ops.wm.open_mainfile(filepath=blend)
dg = bpy.context.evaluated_depsgraph_get()
tris = []  # (pts design coords Nx3, colour)
for ob in bpy.context.scene.objects:
    if ob.type != 'MESH' or ob.hide_render or ob.hide_get():
        continue
    if any(c.hide_render for c in ob.users_collection):
        continue
    me = ob.evaluated_get(dg).to_mesh()
    M = ob.matrix_world
    V = np.array([tuple(M @ v.co) for v in me.vertices])
    D = np.stack([V[:, 1] + F.X_REF, -V[:, 0], V[:, 2] + F.Z_REF], 1)
    for p in me.polygons:
        mat = ob.material_slots[p.material_index].material if ob.material_slots else None
        col = tuple(mat.diffuse_color[:3]) if mat else (0.5, 0.5, 0.5)
        idx = list(p.vertices)
        for k in range(1, len(idx) - 1):
            tris.append((D[[idx[0], idx[k], idx[k + 1]]], col, ob.name))
    ob.evaluated_get(dg).to_mesh_clear()

def proj(P, view):
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    if view == 'top':   return np.stack([x, -y], -1), z          # depth: larger z nearer
    if view == 'side':  return np.stack([x, -z], -1), -y         # seen from port (y<0 nearer)
    if view == 'front': return np.stack([-y, -z], -1), -x
light = np.array([0.35, -0.45, 0.82]); light /= np.linalg.norm(light)
ref = argv[3] if len(argv) > 3 else None
if ref:
    s, ox, oy = map(float, argv[4:7])
    R = Image.open(ref).convert('RGB')
    W, H = R.size
else:
    s = 60.0
items = []
for P, col, name in tris:
    q, dep = proj(P, view)
    n = np.cross(P[1] - P[0], P[2] - P[0]); nn = np.linalg.norm(n)
    if nn < 1e-12: continue
    n /= nn
    sh = 0.35 + 0.65 * abs(float(n @ light))
    items.append((float(dep.mean()), q, tuple(int(255 * min(1, (c ** (1/2.2)) * sh * 1.1)) for c in col)))
items.sort(key=lambda t: t[0])
allq = np.concatenate([q for _, q, _ in items])
if ref:
    off = np.array([ox, oy])
else:
    mn, mx = allq.min(0), allq.max(0)
    W, H = int((mx[0] - mn[0]) * s) + 40, int((mx[1] - mn[1]) * s) + 40
    off = -mn * s + 20
img = Image.new('RGB', (W, H), (255, 255, 255))
mask = Image.new('L', (W, H), 0)
d, dm = ImageDraw.Draw(img), ImageDraw.Draw(mask)
for dep, q, c in items:
    pts = [tuple(p) for p in (q * s + off)]
    d.polygon(pts, fill=c)
    dm.polygon(pts, fill=255)
if ref:
    edge = mask.filter(ImageFilter.MaxFilter(3))
    er = mask.filter(ImageFilter.MinFilter(3))
    e = np.array(edge).astype(int) - np.array(er).astype(int)
    Ra = np.array(R).astype(float)
    m = np.array(mask)[..., None] / 255.0
    comp = Ra * (1 - 0.18 * m) + np.array([255, 120, 0]) * 0.18 * m
    comp[e > 0] = [230, 0, 0]
    out_img = Image.fromarray(comp.clip(0, 255).astype(np.uint8))
    if len(argv) > 7:
        x0, y0, x1, y1 = map(int, argv[7:11])
        out_img = out_img.crop((x0, y0, x1, y1))
    out_img.save(out)
else:
    img.save(out)
print('ok', out)
