"""
PBR materials for the Hornet generator.

Cockpit: painted atlas (tools/make_cockpit_textures.py) -> image materials.
Exterior: a procedural "worn fleet Hornet" shader, baked in Cycles into
per-part atlases (base colour, ORM = occlusion/roughness/metallic, normal),
then replaced by plain image materials that export to glTF / any engine.

Exterior paint is the US Navy tactical paint scheme (TPS) of the legacy
Hornet: FS 36320 dark ghost grey on upper surfaces and FS 36375 light ghost
grey underneath (sRGB values approximate).  Weathering: mismatched
touch-up patches, grime in recesses, flow streaks running aft, chipped
leading edges, exhaust soot aft, gun-gas soot behind the M61 muzzle.
Panel lines come from the general-arrangement drawings (projected from the
top and side views), so they follow the real airframe.
"""
import math
import os

import bpy
from mathutils import Matrix

TPS_DARK = (0.105, 0.125, 0.140)      # FS 36320, linear
TPS_LIGHT = (0.250, 0.268, 0.285)     # FS 36375, linear

# atlas groups: object-name suffixes -> atlas
GROUPS = {
    "fuselage": ["Fuselage", "WindscreenFrame", "CanopyFrames", "Antennae", "GunPort_Vents", "SpeedBrake"],
    "wings": ["Wing_Inner_L", "Wing_Inner_R", "Wing_Outer_L", "Wing_Outer_R", "LEFlap_Inner_L", "LEFlap_Inner_R",
              "LEFlap_Outer_L", "LEFlap_Outer_R", "Flap_L", "Flap_R", "Aileron_L", "Aileron_R",
              "WingtipLauncher_L", "WingtipLauncher_R"],
    "tail": ["Fin_L", "Fin_R", "Rudder_L", "Rudder_R", "Stabilator_L", "Stabilator_R"],
    "gear": ["NoseGear", "LaunchBar", "NoseGearBrace", "NoseGearDoorFwd_L", "NoseGearDoorFwd_R", "NoseGearDoorAft_L",
             "NoseGearDoorAft_R", "NoseGearDoorBrace_L", "NoseGearDoorBrace_R", "MainGear_L", "MainGear_R", "MainGearDoor_L", "MainGearDoor_R", "MainGearDoorSide_L", "MainGearDoorSide_R",
             "ArrestingHook", "Nozzle_L", "Nozzle_R", "RefuelProbe_Extended"],
}
SIZES = {"fuselage": 8192, "wings": 4096, "tail": 4096, "gear": 2048}
# largest image one bake call writes; bigger atlases bake in tiles (bake_exterior)
BAKE_TILE = 4096
SHARED = {"wings", "tail", "gear"}       # identical geometry in both variants


# ----------------------------------------------------------------------------
# small node helpers
# ----------------------------------------------------------------------------
class NT:
    def __init__(self, mat):
        mat.use_nodes = True
        self.t = mat.node_tree
        self.n = self.t.nodes
        self.l = self.t.links
        for node in list(self.n):
            self.n.remove(node)
        self.x = 0

    def node(self, kind, **props):
        nd = self.n.new(kind)
        nd.location = (self.x, 0)
        self.x += 180
        for k, v in props.items():
            if k.startswith("in_"):
                key = k[3:]
                key = int(key) if key.isdigit() else key.replace("__", " ")
                nd.inputs[key].default_value = v
            else:
                setattr(nd, k, v)
        return nd

    def link(self, a, b):
        self.l.new(a, b)

    def math(self, op, a, b=None, clamp=False):
        nd = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                nd.inputs[i].default_value = v
            else:
                self.link(v, nd.inputs[i])
        return nd.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        nd = self.node("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        for sock, v in ((nd.inputs[0], fac), (nd.inputs[6], a), (nd.inputs[7], b)):
            if isinstance(v, (int, float)):
                sock.default_value = v
            elif isinstance(v, tuple):
                sock.default_value = v + (1.0,) if len(v) == 3 else v
            else:
                self.link(v, sock)
        return nd.outputs[2]

    def ramp(self, inp, a, b):
        """Smoothstep-ish map of inp from [a, b] to [0, 1]."""
        nd = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        nd.inputs[1].default_value = a
        nd.inputs[2].default_value = b
        self.link(inp, nd.inputs[0])
        return nd.outputs[0]


def image(path, colorspace="sRGB"):
    name = os.path.basename(path)
    img = bpy.data.images.get(name)
    if img is None:
        img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = colorspace
    return img


def image_material(mat, base, orm=None, normal=None, emission=None, emission_strength=1.0, alpha=False,
                   uv="UVMap"):
    """Plain glTF-friendly PBR material from image maps."""
    nt = NT(mat)
    out = nt.node("ShaderNodeOutputMaterial")
    bsdf = nt.node("ShaderNodeBsdfPrincipled")
    nt.link(bsdf.outputs[0], out.inputs[0])
    tc = nt.node("ShaderNodeUVMap", uv_map=uv)
    tb = nt.node("ShaderNodeTexImage", image=base)
    nt.link(tc.outputs[0], tb.inputs[0])
    nt.link(tb.outputs[0], bsdf.inputs["Base Color"])
    if alpha:
        nt.link(tb.outputs[1], bsdf.inputs["Alpha"])
        for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED")):
            try:
                setattr(mat, attr, val)
            except (AttributeError, TypeError):
                pass
    if orm is not None:
        to = nt.node("ShaderNodeTexImage", image=orm)
        nt.link(tc.outputs[0], to.inputs[0])
        sep = nt.node("ShaderNodeSeparateColor")
        nt.link(to.outputs[0], sep.inputs[0])
        nt.link(sep.outputs[1], bsdf.inputs["Roughness"])
        nt.link(sep.outputs[2], bsdf.inputs["Metallic"])
    if normal is not None:
        tn = nt.node("ShaderNodeTexImage", image=normal)
        nt.link(tc.outputs[0], tn.inputs[0])
        nm = nt.node("ShaderNodeNormalMap", uv_map=uv)
        nt.link(tn.outputs[0], nm.inputs["Color"])
        nt.link(nm.outputs[0], bsdf.inputs["Normal"])
    if emission is not None:
        te = tb if emission is base else nt.node("ShaderNodeTexImage", image=emission)
        if te is not tb:
            nt.link(tc.outputs[0], te.inputs[0])
        nt.link(te.outputs[0], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


# ----------------------------------------------------------------------------
# cockpit
# ----------------------------------------------------------------------------
def apply_cockpit(tex):
    from fa18_hornet import material
    base = image(os.path.join(tex, "cockpit_basecolor.png"))
    orm = image(os.path.join(tex, "cockpit_orm.png"), "Non-Color")
    nrm = image(os.path.join(tex, "cockpit_normal.png"), "Non-Color")
    image_material(material("Cockpit"), base, orm, nrm)
    for name in ("DDI_L", "DDI_R", "DDI_C", "HSD", "UFC"):
        img = image(os.path.join(tex, "display_%s.png" % name))
        m = image_material(material("Display_" + name), img, emission=img, emission_strength=1.6)
        m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.15
    hud = image(os.path.join(tex, "display_HUD.png"))
    m = image_material(material("Display_HUD"), hud, emission=hud, emission_strength=2.5, alpha=True)
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.05


# ----------------------------------------------------------------------------
# exterior procedural shader (bake source)
# ----------------------------------------------------------------------------
def exterior_shader(mat, kind, ref):
    """kind: airframe | frame | dark | wall | nozzle | gear.
    ref: dict with drawing image paths and registrations (see bake())."""
    nt = NT(mat)
    out = nt.node("ShaderNodeOutputMaterial")
    bsdf = nt.node("ShaderNodeBsdfPrincipled")
    nt.link(bsdf.outputs[0], out.inputs[0])
    geo = nt.node("ShaderNodeNewGeometry")
    sep = nt.node("ShaderNodeSeparateXYZ")
    nt.link(geo.outputs["Position"], sep.inputs[0])
    nsep = nt.node("ShaderNodeSeparateXYZ")
    nt.link(geo.outputs["Normal"], nsep.inputs[0])
    X, Y, Z = sep.outputs[0], sep.outputs[1], sep.outputs[2]      # Blender world: X port, Y aft, Z up
    NX, NY, NZ = nsep.outputs[0], nsep.outputs[1], nsep.outputs[2]
    xref, zref = ref["x_ref"], ref["z_ref"]
    xd = nt.math("ADD", Y, xref)                                   # design x (aft from nose tip)
    zd = nt.math("ADD", Z, zref)
    yd = nt.math("MULTIPLY", X, -1.0)                              # design y (starboard)

    def noise(scale, detail=4.0, rough=0.55, vec=None, w=0.0):
        nd = nt.node("ShaderNodeTexNoise", noise_dimensions="4D")
        nd.inputs["Scale"].default_value = scale
        nd.inputs["Detail"].default_value = detail
        nd.inputs["Roughness"].default_value = rough
        nd.inputs["W"].default_value = w
        if vec is not None:
            nt.link(vec, nd.inputs["Vector"])
        else:
            nt.link(geo.outputs["Position"], nd.inputs["Vector"])
        return nd.outputs[0]

    def stretched(sx, sy, sz):
        """Position scaled per axis (for streaks along the flow)."""
        mp = nt.node("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (sx, sy, sz)
        nt.link(geo.outputs["Position"], mp.inputs[0])
        return mp.outputs[0]

    ao = nt.node("ShaderNodeAmbientOcclusion", samples=8)
    ao.inputs["Distance"].default_value = 0.35
    crev = nt.math("SUBTRACT", 1.0, ao.outputs["AO"], clamp=True)            # 1 in recesses

    if kind in ("dark", "wall"):
        col = (0.012, 0.012, 0.013) if kind == "dark" else (0.022, 0.023, 0.025)
        g = noise(9.0)
        c = nt.mix(nt.math("MULTIPLY", g, 0.5), col, (0.006, 0.006, 0.005))
        c = nt.mix(nt.math("MULTIPLY", crev, 0.8, clamp=True), c, (0.003, 0.003, 0.003))
        nt.link(c, bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.8 if kind == "dark" else 0.7
        return mat

    if kind == "nozzle":
        # burnt titanium / Inconel petals: straw-blue heat tint, soot inside
        g = noise(6.0, 6.0)
        heat = nt.ramp(xd, 15.9, 16.6)
        c = nt.mix(heat, (0.30, 0.28, 0.26), (0.10, 0.09, 0.10))
        c = nt.mix(nt.math("MULTIPLY", g, 0.6), c, (0.22, 0.16, 0.10))
        c = nt.mix(nt.math("MULTIPLY", crev, 0.9, clamp=True), c, (0.01, 0.01, 0.01))
        nt.link(c, bsdf.inputs["Base Color"])
        bsdf.inputs["Metallic"].default_value = 0.85
        r = nt.math("ADD", 0.38, nt.math("MULTIPLY", g, 0.3))
        nt.link(r, bsdf.inputs["Roughness"])
        return mat

    if kind == "gear":
        # gloss-white struts and wheels gone grey with brake dust and hydraulic fluid
        g = noise(8.0)
        c = nt.mix(nt.math("MULTIPLY", g, 0.5), (0.62, 0.62, 0.60), (0.30, 0.28, 0.24))
        c = nt.mix(nt.math("MULTIPLY", crev, 1.0, clamp=True), c, (0.04, 0.035, 0.03))
        nt.link(c, bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.45
        return mat

    # --- airframe / frame -----------------------------------------------------
    # TPS: dark ghost grey up, light ghost grey down, soft demarcation on the sides
    up = nt.ramp(NZ, -0.55, 0.15)
    c = nt.mix(up, TPS_LIGHT, TPS_DARK)
    # radome is a slightly different, flatter grey (x < 2.5 m)
    rad = nt.math("SUBTRACT", 1.0, nt.ramp(xd, 2.35, 2.45))
    c = nt.mix(nt.math("MULTIPLY", rad, 0.6), c, (0.13, 0.145, 0.16))
    # touch-up patches: blocky world-space cells, a few repainted in a fresher shade
    vor = nt.node("ShaderNodeTexVoronoi", distance="MANHATTAN", feature="F1")
    vor.inputs["Scale"].default_value = 0.9
    nt.link(geo.outputs["Position"], vor.inputs["Vector"])
    sepc = nt.node("ShaderNodeSeparateColor")
    nt.link(vor.outputs["Color"], sepc.inputs[0])
    patch = nt.math("GREATER_THAN", sepc.outputs[0], 0.72)
    edge_n = noise(6.0, 3.0)
    patch = nt.math("MULTIPLY", patch, nt.ramp(edge_n, 0.25, 0.4))
    tone = nt.math("SUBTRACT", sepc.outputs[1], 0.5)                   # darker or lighter touch-up
    shade = nt.mix(nt.math("GREATER_THAN", tone, 0.0), (0.82, 0.86, 0.92), (1.10, 1.08, 1.06))
    c = nt.mix(patch, c, nt.mix(1.0, c, shade, "MULTIPLY"))
    # large-scale fading / mottling
    mott = noise(0.8, 3.0)
    c = nt.mix(nt.math("MULTIPLY", mott, 0.25), c, (0.30, 0.31, 0.30))
    # grime in recesses and along hinge gaps
    c = nt.mix(nt.math("MULTIPLY", crev, 1.7, clamp=True), c, (0.03, 0.029, 0.025))
    # flow streaks: stretched noise along the airflow (Blender +Y aft), heavier underneath and aft
    st = noise(1.0, 6.0, 0.6, stretched(14.0, 0.18, 14.0))
    streak = nt.ramp(st, 0.55, 0.75)
    under = nt.math("SUBTRACT", 1.0, up)
    aft = nt.ramp(xd, 9.0, 16.0)
    sw = nt.math("ADD", nt.math("ADD", nt.math("MULTIPLY", under, 0.6), nt.math("MULTIPLY", aft, 0.35)), 0.12)
    c = nt.mix(nt.math("MULTIPLY", streak, sw, clamp=True), c, (0.04, 0.038, 0.032))
    # general dirt film, heavier on the underside
    film = noise(2.5, 5.0, 0.6)
    c = nt.mix(nt.math("MULTIPLY", nt.ramp(film, 0.45, 0.8), nt.math("ADD", 0.15, nt.math("MULTIPLY", under, 0.3))),
               c, (0.06, 0.057, 0.05))
    # exhaust soot round and ahead of the nozzles, between the engines
    soot = nt.math("MULTIPLY", nt.ramp(xd, 14.2, 16.4),
                   nt.math("SUBTRACT", 1.0, nt.ramp(nt.math("ABSOLUTE", yd), 0.9, 1.4)))
    soot = nt.math("MULTIPLY", soot, nt.math("SUBTRACT", 1.0, nt.ramp(zd, 0.55, 0.95)))
    sootn = noise(3.0, 5.0)
    soot = nt.math("MULTIPLY", soot, nt.ramp(sootn, 0.2, 0.6), clamp=True)
    c = nt.mix(nt.math("MULTIPLY", soot, 0.9), c, (0.012, 0.011, 0.010))
    # gun gas soot streaming aft from the M61 muzzle on top of the nose
    gx = nt.ramp(xd, 1.35, 1.55)
    gx2 = nt.math("SUBTRACT", 1.0, nt.ramp(xd, 1.6, 3.4))
    gy = nt.math("SUBTRACT", 1.0, nt.ramp(nt.math("ABSOLUTE", yd), 0.03, 0.22))
    gz = nt.ramp(NZ, 0.2, 0.6)
    gun = nt.math("MULTIPLY", nt.math("MULTIPLY", gx, gx2), nt.math("MULTIPLY", gy, gz))
    gun = nt.math("MULTIPLY", gun, nt.ramp(noise(8.0, 4.0, 0.6, stretched(3.0, 0.4, 8.0)), 0.3, 0.6), clamp=True)
    c = nt.mix(nt.math("MULTIPLY", gun, 0.95), c, (0.010, 0.009, 0.008))
    # leading-edge chipping: faces turned into the airflow
    fwd = nt.ramp(nt.math("MULTIPLY", NY, -1.0), 0.55, 0.9)
    chipn = noise(28.0, 4.0, 0.7)
    chips = nt.math("MULTIPLY", fwd, nt.ramp(chipn, 0.55, 0.62), clamp=True)
    c = nt.mix(chips, c, (0.30, 0.31, 0.31))
    # panel lines projected from the drawings (top view on upper faces, side view on sides),
    # with rows of flush rivets on both sides of every line: heads 5.6 mm across on a
    # 25 mm pitch (typical for AN426 1/8 in rivets in fighter skins)
    def rivet_heads(a, b, pitch=0.025, radius=0.0028):
        fa = nt.math("SUBTRACT", nt.math("FRACT", nt.math("DIVIDE", a, pitch)), 0.5)
        fb = nt.math("SUBTRACT", nt.math("FRACT", nt.math("DIVIDE", b, pitch)), 0.5)
        d = nt.math("MULTIPLY", nt.math("SQRT", nt.math("ADD", nt.math("MULTIPLY", fa, fa),
                                                         nt.math("MULTIPLY", fb, fb))), pitch)
        return nt.math("SUBTRACT", 1.0, nt.ramp(d, radius * 0.7, radius))

    lines = None
    rivets = None
    hd = False
    # top view only on upward faces (the underside has no drawing), side view on both sides
    for key, wsock, a, b in (("top", NZ, xd, yd), ("side", nt.math("ABSOLUTE", NX), xd, zd)):
        info = ref.get(key)
        if not info:
            continue
        img = image(info["path"], "Non-Color")
        s, ox, oy, W, H = info["s"], info["ox"], info["oy"], img.size[0], img.size[1]
        u = nt.math("DIVIDE", nt.math("ADD", nt.math("MULTIPLY", a, s), ox), W)
        v = nt.math("SUBTRACT", 1.0, nt.math("DIVIDE", nt.math("SUBTRACT", oy, nt.math("MULTIPLY", b, s)), H))
        comb = nt.node("ShaderNodeCombineXYZ")
        nt.link(u, comb.inputs[0])
        nt.link(v, comb.inputs[1])
        tex = nt.node("ShaderNodeTexImage", image=img, extension="CLIP", interpolation="Linear")
        nt.link(comb.outputs[0], tex.inputs[0])
        weight = nt.ramp(wsock, 0.35, 0.7)
        if info.get("hd"):
            # vectorised maps (tools/vectorize_reference_lines.py): red = 3 mm seams, green = rivet heads
            sepc = nt.node("ShaderNodeSeparateColor")
            nt.link(tex.outputs[0], sepc.inputs[0])
            ink = nt.math("MULTIPLY", sepc.outputs[0], weight)
            heads = nt.math("MULTIPLY", sepc.outputs[1], weight)
        else:
            ink = nt.math("SUBTRACT", 1.0, tex.outputs[0])
            ink = nt.math("MULTIPLY", ink, weight)
            heads = None
        if key == "top" and ref.get("mask_spine"):
            box = nt.math("MULTIPLY", nt.ramp(xd, 6.9, 7.0), nt.math("SUBTRACT", 1.0, nt.ramp(xd, 8.8, 8.9)))
            box = nt.math("MULTIPLY", box, nt.math("SUBTRACT", 1.0, nt.ramp(nt.math("ABSOLUTE", yd), 0.5, 0.6)))
            ink = nt.math("MULTIPLY", ink, nt.math("SUBTRACT", 1.0, box))
            if heads is not None:
                heads = nt.math("MULTIPLY", heads, nt.math("SUBTRACT", 1.0, box))
        lines = ink if lines is None else nt.math("MAXIMUM", lines, ink)
        if heads is None:
            # low-resolution line art: rows in the fringe beside each line on a 25 mm grid
            band = nt.math("MULTIPLY", nt.ramp(ink, 0.05, 0.2), nt.math("SUBTRACT", 1.0, nt.ramp(ink, 0.45, 0.7)))
            heads = nt.math("MULTIPLY", band, rivet_heads(a, b), clamp=True)
        rivets = heads if rivets is None else nt.math("MAXIMUM", rivets, heads)
        hd = info.get("hd", False)
    if rivets is not None:
        # paint over flush heads: a faint grime ring makes them read as slightly darker dots
        c = nt.mix(nt.math("MULTIPLY", rivets, 0.22), c, (0.05, 0.05, 0.05))
    if lines is not None:
        lines = nt.ramp(lines, 0.08, 0.6) if hd else nt.ramp(lines, 0.25, 0.75)
        c = nt.mix(nt.math("MULTIPLY", lines, 0.7 if hd else 0.55), c, (0.03, 0.03, 0.03))
    # national insignia, low-visibility, upper port and lower starboard wing
    ins = ref.get("insignia")
    if ins:
        img = image(ins["path"], "sRGB")
        mark = None
        for cy, cx, face in ((ins["y_up"], ins["x"], 1.0), (ins["y_dn"], ins["x"], -1.0)):
            u = nt.math("ADD", nt.math("DIVIDE", nt.math("SUBTRACT", yd, cy), ins["size"] * face), 0.5)
            v = nt.math("ADD", nt.math("DIVIDE", nt.math("SUBTRACT", xd, cx), -ins["size"]), 0.5)
            comb = nt.node("ShaderNodeCombineXYZ")
            nt.link(u, comb.inputs[0])
            nt.link(v, comb.inputs[1])
            tex = nt.node("ShaderNodeTexImage", image=img, extension="CLIP")
            nt.link(comb.outputs[0], tex.inputs[0])
            side = nt.ramp(nt.math("MULTIPLY", NZ, face), 0.5, 0.8)
            m = nt.math("MULTIPLY", tex.outputs[1], side)
            mark = m if mark is None else nt.math("MAXIMUM", mark, m)
        c = nt.mix(nt.math("MULTIPLY", mark, 0.85), c, (0.055, 0.065, 0.075))
    if kind == "frame":
        # canopy frames: TPS grey outside, flat black on the faces turned into the cockpit
        inner = nt.ramp(nt.math("MULTIPLY", nt.math("ADD", nt.math("MULTIPLY", NZ, 1.0),
                                                     nt.math("MULTIPLY", nt.math("MULTIPLY", NX, X), 4.0)), -1.0),
                        0.05, 0.3)
        c = nt.mix(inner, c, (0.02, 0.02, 0.022))
    nt.link(c, bsdf.inputs["Base Color"])
    # roughness: semi-matte TPS, rougher where sooted, smoother on chips and fresh patches
    r = nt.math("ADD", 0.52, nt.math("MULTIPLY", mott, 0.12))
    r = nt.math("ADD", r, nt.math("MULTIPLY", soot, 0.25))
    r = nt.math("SUBTRACT", r, nt.math("MULTIPLY", patch, 0.08))
    r = nt.math("SUBTRACT", r, nt.math("MULTIPLY", chips, 0.2), clamp=True)
    if rivets is not None:
        r = nt.math("SUBTRACT", r, nt.math("MULTIPLY", rivets, 0.07), clamp=True)
    nt.link(r, bsdf.inputs["Roughness"])
    nt.link(nt.math("MULTIPLY", chips, 0.6), bsdf.inputs["Metallic"])
    # normal: engraved panel lines, chips and fine orange-peel
    if lines is not None or True:
        hgt = nt.math("MULTIPLY", noise(180.0, 2.0), 0.15)
        if lines is not None:
            hgt = nt.math("SUBTRACT", hgt, nt.math("MULTIPLY", lines, 0.8))
        if rivets is not None:
            hgt = nt.math("SUBTRACT", hgt, nt.math("MULTIPLY", rivets, 0.35))    # shallow dimple per head
        hgt = nt.math("SUBTRACT", hgt, nt.math("MULTIPLY", chips, 0.4))
        bump = nt.node("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.9
        bump.inputs["Distance"].default_value = 0.003
        nt.link(hgt, bump.inputs["Height"])
        nt.link(bump.outputs[0], bsdf.inputs["Normal"])
    return mat


# ----------------------------------------------------------------------------
# insignia image
# ----------------------------------------------------------------------------
def insignia_png(path):
    """Low-visibility US star-and-bar: solid shapes on a transparent field,
    star pointing to the top of the image (the nose)."""
    if os.path.exists(path):
        return path
    from PIL import Image, ImageDraw
    n = 1024
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = n / 2
    r = n * 0.20                                   # roundel radius; bars make up the rest
    fill = (255, 255, 255, 255)
    d.rectangle((c - 2 * r, c - r * 0.5, c + 2 * r, c + r * 0.5), fill=fill)       # bars (span 4r)
    d.ellipse((c - r, c - r, c + r, c + r), fill=fill)
    # cut the star out of the roundel so it shows the base paint
    pts = []
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        rr = r * (0.95 if k % 2 == 0 else 0.38)
        pts.append((c + rr * math.cos(a), c - rr * math.sin(a)))
    d.polygon(pts, fill=(0, 0, 0, 0))
    # rotate so the bars run spanwise (image x = span, image y = chord)
    im.save(path)
    return path


# ----------------------------------------------------------------------------
# baking
# ----------------------------------------------------------------------------
PROC_KIND = {"Airframe": "airframe", "Frame": "frame", "Dark": "dark", "CockpitWall": "wall",
             "Nozzle": "nozzle", "Gear": "gear", "Tire": "dark", "Glass": None}


def group_objects(h, group):
    names = [h.prefix + n for n in GROUPS[group]]
    return [bpy.data.objects[n] for n in names if n in bpy.data.objects]


def atlas_name(h, group, channel):
    tag = "" if group in SHARED else h.v
    return "ext_%s%s_%s" % (group, ("_" + tag) if tag else "", channel)


def _show_all(objs):
    state = []
    for c in bpy.data.collections:
        state.append((c, c.hide_viewport, c.hide_render))
        c.hide_viewport = False
        c.hide_render = False
    for o in objs:
        state.append((o, o.hide_viewport, o.hide_render))
        o.hide_viewport = False
        o.hide_render = False
    return state


def _restore(state):
    for o, hv, hr in state:
        o.hide_viewport = hv
        o.hide_render = hr


def bake_exterior(h, tex, refs, samples=12, groups=None):
    """Bake the procedural exterior into per-group atlases in `tex`."""
    import numpy as np
    from fa18_hornet import X_REF, Z_REF
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.render.bake.margin = 16
    sc.render.bake.use_selected_to_active = False
    ref = dict(refs or {})
    ref["x_ref"], ref["z_ref"] = X_REF, Z_REF
    ref["insignia"] = {"path": insignia_png(os.path.join(tex, "insignia_lowvis.png")),
                       "x": 11.4, "y_up": -4.85, "y_dn": 4.85, "size": 1.2}
    if h.v == "A":
        # the B sheet's longer canopy would draw a frame line on the A's spine
        ref["mask_spine"] = True
    procs = {}
    for name, kind in PROC_KIND.items():
        if kind is None:
            continue
        m = bpy.data.materials.new("PROC_" + name)
        exterior_shader(m, kind, ref)
        procs["F18_" + name] = m

    groups = groups or list(GROUPS)
    for group in groups:
        objs = group_objects(h, group)
        if not objs:
            continue
        size = SIZES[group]
        state = _show_all(objs)
        # the airframe is painted as it flies: legs, braces and bay doors cast no
        # shadow onto it (their own group bakes them in the flight pose)
        movers = [o for o in bpy.data.objects if o.type == "MESH" and o not in objs
                  and any(k in o.keys() for k in ("stow_angle", "travel", "stow_fold"))]
        hidden = [(o, o.hide_render) for o in movers]
        for o in movers:
            o.hide_render = True
        # swap in procedural materials
        saved = {}
        for o in objs:
            saved[o.name] = [s.material for s in o.material_slots]
            for s in o.material_slots:
                if s.material and s.material.name in procs:
                    s.material = procs[s.material.name]
        used = {s.material for o in objs for s in o.material_slots if s.material}
        # bay doors are painted as they sit in flight: closed, with the gear stowed
        doors = [o for o in objs if "travel" in o.keys()]
        rest = [o for o in objs if o not in doors]
        # Atlases above BAKE_TILE are baked as n x n tiles: every UV is mapped
        # to uv * n - (i, j), so tile (i, j) holds exactly that part of the atlas
        # (the bake clips triangles at the image edge and skips ones outside it).
        # One bake call needs several full-size float buffers, about 9 GB at 8192 px.
        # Every pass bakes without a margin; the image alpha records which pixels
        # were baked, and the 16 px margin is grown once, after all passes and
        # tiles (_dilate).  A margin per pass would paint the second pass's
        # margin over the doors baked in the first.
        n = max(1, -(-size // BAKE_TILE))
        tile = size // n
        uv_saved = {}
        if n > 1:
            for o in objs:
                lay = o.data.uv_layers.active
                arr = np.empty(len(lay.data) * 2, np.float32)
                lay.data.foreach_get("uv", arr)
                uv_saved[o.name] = (lay, arr)
        results, cover = {}, None
        try:
            for channel in ("basecolor", "roughness", "metallic", "normal", "ao"):
                kind = {"normal": "NORMAL", "ao": "AO"}.get(channel, "EMIT")
                if channel == "ao":
                    sc.cycles.samples = max(samples, 32)
                rgb = channel in ("basecolor", "normal")
                full = np.zeros((size, size, 3) if rgb else (size, size), np.uint8)   # rows bottom-up
                cov = np.zeros((size, size), bool)
                for ti in range(n):
                    for tj in range(n):
                        for lay, arr in uv_saved.values():
                            uv = arr.reshape(-1, 2) * n - np.array([ti, tj], np.float32)
                            lay.data.foreach_set("uv", uv.ravel())
                        img = bpy.data.images.new("bake_%s_%s" % (group, channel), tile, tile, alpha=True,
                                                  float_buffer=(channel == "normal"))
                        img.generated_color = (0, 0, 0, 0)         # alpha marks the baked pixels
                        img.colorspace_settings.name = "sRGB" if channel == "basecolor" else "Non-Color"
                        for m in used:
                            nodes = m.node_tree.nodes
                            tgt = nodes.get("BAKE_TARGET") or nodes.new("ShaderNodeTexImage")
                            tgt.name = "BAKE_TARGET"
                            tgt.image = img
                            nodes.active = tgt
                            _route(m, channel)
                        passes = [(doors, True), (rest, False)] if doors else [(objs, False)]
                        for k, (sel, flight) in enumerate(passes):
                            if not sel:
                                continue
                            saved_pose = _flight_pose(h) if flight else None
                            bpy.ops.object.select_all(action="DESELECT")
                            for o in sel:
                                o.select_set(True)
                            bpy.context.view_layer.objects.active = sel[0]
                            sc.render.bake.use_clear = (k == 0)
                            bpy.ops.object.bake(type=kind, margin=0, normal_space="TANGENT")
                            if saved_pose is not None:
                                _restore_pose(saved_pose)
                        # foreach_get into one float32 buffer: img.pixels[:] would build
                        # a Python float per channel value (about 8.6 GB for an 8K atlas)
                        buf = np.empty(tile * tile * 4, np.float32)
                        img.pixels.foreach_get(buf)
                        buf = buf.reshape(tile, tile, 4)
                        r0, c0 = tj * tile, ti * tile
                        # keep only what the maps use, as 8-bit
                        full[r0:r0 + tile, c0:c0 + tile] = _to8(buf[..., :3] if rgb else buf[..., 0], flip=False)
                        cov[r0:r0 + tile, c0:c0 + tile] = buf[..., 3] > 0.5
                        del buf
                        bpy.data.images.remove(img)
                sc.render.bake.use_clear = True
                sc.cycles.samples = samples
                for m in used:
                    _route(m, None)
                results[channel] = full
                if cover is None:
                    cover = cov
        finally:
            for lay, arr in uv_saved.values():
                lay.data.foreach_set("uv", arr)
        _dilate(list(results.values()), cover, 16)
        del cover
        for channel in results:
            results[channel] = results[channel][::-1]                # top row first
        _write_maps(h, group, tex, results)
        for o in objs:
            for s, m in zip(o.material_slots, saved[o.name]):
                s.material = m
        for o, was in hidden:
            o.hide_render = was
        _restore(state)
    for m in procs.values():
        bpy.data.materials.remove(m)


def _flight_pose(h):
    """Stow the gear and close every bay door (for baking the doors); returns
    what _restore_pose needs."""
    saved = []
    legs = [o for o in bpy.data.objects if o.type == "MESH" and "stow_angle" in o.keys()]
    for leg in legs:
        if not hasattr(h, "stow_pose"):
            break
        P, R = h.stow_pose(leg, 1.0)
        saved.append((leg, leg.matrix_basis.copy(), None))
        M = Matrix.Translation(P) @ R.to_4x4() @ Matrix.Translation(-P)
        leg.matrix_world = M @ leg.matrix_world
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        ang = o.get("travel", o.get("stow_fold"))
        if ang is not None:
            saved.append((o, None, o.rotation_euler.x))
            o.rotation_euler.x = math.radians(float(ang))
    bpy.context.view_layer.update()
    return saved


def _restore_pose(saved):
    for o, basis, rx in reversed(saved):
        if basis is not None:
            o.matrix_basis = basis
        else:
            o.rotation_euler.x = rx
    bpy.context.view_layer.update()


def _route(mat, channel):
    """Send one BSDF input to the output through an emission shader (or
    restore the BSDF when channel is None / normal / ao)."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    out = next(n for n in nodes if n.type == "OUTPUT_MATERIAL")
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    em = nodes.get("BAKE_EMIT") or nodes.new("ShaderNodeEmission")
    em.name = "BAKE_EMIT"
    for l in list(out.inputs[0].links):
        links.remove(l)
    src_name = {"basecolor": "Base Color", "roughness": "Roughness", "metallic": "Metallic"}.get(channel)
    if src_name is None:
        links.new(bsdf.outputs[0], out.inputs[0])
        return
    for l in list(em.inputs[0].links):
        links.remove(l)
    inp = bsdf.inputs[src_name]
    if inp.links:
        links.new(inp.links[0].from_socket, em.inputs[0])
    else:
        v = inp.default_value
        em.inputs[0].default_value = tuple(v) if hasattr(v, "__len__") else (v, v, v, 1.0)
    links.new(em.outputs[0], out.inputs[0])


def _to8(a, flip=True):
    """Float bake pixels -> uint8; flip=True puts the top row first (Blender
    rows run bottom-up).  The EMIT bake of the sRGB base colour is already
    display-encoded."""
    import numpy as np
    out = np.empty(a.shape, np.uint8)
    rows = 1024                                   # in strips, so the temporaries stay small
    for r in range(0, a.shape[0], rows):
        s = np.clip(a[r:r + rows], 0, 1) * 255 + 0.5
        out[r:r + rows] = s.astype(np.uint8)
    return out[::-1] if flip else out


def _dilate(maps, cover, px):
    """Grow the baked islands by px pixels in every map: each empty pixel within
    px (8-neighbour steps) of the islands takes the nearest baked pixel's value,
    like Blender's Extend margin.  `cover` marks the baked pixels; the maps
    are changed in place."""
    import numpy as np
    H, W = cover.shape
    src = np.full((H, W), -1, np.int32)                  # flat index of the pixel to copy
    src[cover] = np.flatnonzero(cover).astype(np.int32)
    steps = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    for _ in range(px):
        prev = src.copy()
        for dy, dx in steps:
            # target (y, x) looks at its neighbour (y - dy, x - dx)
            t = src[max(dy, 0):H + min(dy, 0), max(dx, 0):W + min(dx, 0)]
            s = prev[max(-dy, 0):H + min(-dy, 0), max(-dx, 0):W + min(-dx, 0)]
            take = (t < 0) & (s >= 0)
            t[take] = s[take]
        del prev
    grow = ((src >= 0) & ~cover).ravel()
    pick = src.ravel()[grow]
    del src
    for m in maps:
        flat = m.reshape(H * W, -1)
        flat[grow] = flat[pick]


def _write_maps(h, group, tex, res):
    """res: 8-bit maps from bake_exterior (basecolor/normal RGB; ao, roughness,
    metallic single channel)."""
    import numpy as np
    from PIL import Image

    Image.fromarray(res["basecolor"]).save(os.path.join(tex, atlas_name(h, group, "basecolor") + ".jpg"),
                                           quality=92, subsampling=0)
    orm = np.stack([res["ao"], res["roughness"], res["metallic"]], -1)
    # high-quality JPEG without chroma subsampling: channels stay independent enough
    # for ORM / normal use and the files stay a fraction of PNG size
    Image.fromarray(orm).save(os.path.join(tex, atlas_name(h, group, "orm") + ".jpg"), quality=95,
                              subsampling=0)
    Image.fromarray(res["normal"]).save(os.path.join(tex, atlas_name(h, group, "normal") + ".jpg"),
                                        quality=95, subsampling=0)


def apply_exterior(h, tex):
    """Give every baked group one image material.  Returns the groups that
    had no baked textures."""
    from fa18_hornet import material  # noqa: F401
    missing = []
    for group in GROUPS:
        objs = group_objects(h, group)
        if not objs:
            continue
        files = []
        for c in ("basecolor", "orm", "normal"):
            stem = os.path.join(tex, atlas_name(h, group, c))
            files.append(stem + ".jpg" if os.path.exists(stem + ".jpg") else stem + ".png")
        if not all(os.path.exists(f) for f in files):
            missing.append(group)
            continue
        name = "F18_Ext_%s" % atlas_name(h, group, "")[4:].rstrip("_")
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        image_material(mat, image(files[0]), image(files[1], "Non-Color"), image(files[2], "Non-Color"))
        for o in objs:
            for s in o.material_slots:
                s.material = mat
    return missing
