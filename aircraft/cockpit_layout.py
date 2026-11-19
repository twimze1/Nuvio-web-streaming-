"""
Cockpit layout shared by the Blender builder (fa18_cockpit.py) and the
texture painter (tools/make_cockpit_textures.py).  Pure Python, no bpy.

Main instrument panel (MIP) coordinates are millimetres on the panel face:
    u  to the right as the pilot sees it (aircraft starboard), 0 on the centreline
    v  downward from the top of the panel at the centreline
Layout and sizes were measured from NASA Ames photo ARC-1993-A83-0499-34
("F/A-18 Hornet cockpit", the front-cockpit layout of the F/A-18A/B), whose
DDI bezels confirm its scale (about 1 mm per drawing pixel).  The rear
cockpit of the F/A-18B follows NASA Dryden photo ED08-0252-06 (NASA 845):
the same display layout without the HUD and its control panel.
"""

# --- outline of the main instrument panel (u, v) mm, clockwise from top-left
MIP_OUTLINE = [
    (-393, 128), (-385, 98), (-365, 68), (-330, 40), (-285, 20), (-220, 6), (-140, 0),
    (0, -2), (140, 0), (220, 6), (285, 20), (330, 40), (365, 68), (385, 98), (393, 128),
    (393, 512), (120, 512), (120, 592), (-120, 592), (-120, 512), (-393, 512),
]

# --- elements --------------------------------------------------------------
# kinds:
#   ddi      bezel rect, screen rect, 5 buttons per side, 3 knobs
#   ufc      up-front control: keypad, option windows, scratchpad, function row
#   hsd      horizontal situation display: bezel, round map screen, buttons
#   gauge    round instrument: centre, radius, face id
#   lcd      recessed numeric display window
#   knob     rotary knob: centre, radius
#   toggle   toggle switch: centre
#   button   push button / indicator light: rect, legend, colour
#   plate    raised sub-panel: rect
DDI_BUTTON_PITCH = 28


def ddi(name, cu):
    """Digital display indicator centred at u=cu (bezel 210 x 237 mm)."""
    return dict(kind="ddi", name=name,
                rect=(cu - 105, 65, cu + 105, 302),
                screen=(cu - 70, 110, cu + 70, 250),
                knobs=[(cu - 10, 82, 9, "NIGHT/DAY"), (cu - 88, 284, 9, "BRT"), (cu + 88, 284, 9, "CONT")])


WARNING_LIGHTS = [
    dict(kind="plate", name="WarnL", rect=(-238, 8, -122, 54)),
    dict(kind="button", rect=(-232, 14, -198, 48), legend="FIRE", colour="red"),
    dict(kind="button", rect=(-194, 14, -160, 48), legend="MASTER\nCAUTION", colour="amber"),
    dict(kind="button", rect=(-155, 13, -127, 24), legend="SPN RCVY", colour="amber"),
    dict(kind="button", rect=(-155, 26, -127, 37), legend="L BLEED", colour="red"),
    dict(kind="button", rect=(-155, 39, -127, 50), legend="R BLEED", colour="red"),
    dict(kind="plate", name="WarnR", rect=(122, 8, 248, 54)),
    dict(kind="button", rect=(127, 13, 160, 24), legend="CK SEAT", colour="amber"),
    dict(kind="button", rect=(127, 26, 160, 37), legend="APU ACC", colour="green"),
    dict(kind="button", rect=(127, 39, 160, 50), legend="BATT SW", colour="amber"),
    dict(kind="button", rect=(165, 14, 202, 48), legend="APU\nFIRE", colour="red"),
    dict(kind="button", rect=(206, 14, 242, 48), legend="FIRE", colour="red"),
]
MASTER_ARM = [
    dict(kind="plate", name="MasterArm", rect=(-390, 135, -330, 268)),
    dict(kind="button", rect=(-383, 142, -337, 160), legend="READY\nDISCH", colour="green"),
    dict(kind="button", rect=(-383, 166, -360, 186), legend="A/A", colour="green"),
    dict(kind="button", rect=(-358, 166, -337, 186), legend="A/G", colour="green"),
    dict(kind="toggle", c=(-360, 212), legend="MASTER ARM"),
    dict(kind="button", rect=(-385, 236, -335, 262), legend="EMERG\nJETT", colour="stripe"),
    dict(kind="knob", c=(-358, 290), r=19, legend="SEL JETT"),
]
HUD_CONTROLS = [
    dict(kind="plate", name="HUDCtl", rect=(-108, 226, 108, 290)),
    dict(kind="toggle", c=(-84, 262), legend="HUD SYM\nREJ"),
    dict(kind="knob", c=(-50, 262), r=10, legend="BRT"),
    dict(kind="knob", c=(-17, 262), r=10, legend="DAY/NIGHT"),
    dict(kind="knob", c=(17, 262), r=10, legend="AOA INDXR"),
    dict(kind="toggle", c=(50, 262), legend="ALT\nBARO RDR"),
    dict(kind="toggle", c=(84, 262), legend="ATT\nINS STBY"),
]
DISPLAYS = [
    ddi("DDI_L", -220),
    dict(kind="ufc", name="UFC", rect=(-110, 22, 110, 220),
         scratchpad=(-82, 34, -12, 54),
         keypad=dict(origin=(-80, 62), pitch=(25, 26), rows=["123", "456", "789", "C0E"]),
         options=[(22, 62 + 22 * i, 92, 80 + 22 * i) for i in range(5)],
         option_buttons=[(12, 71 + 22 * i) for i in range(5)],
         functions=["A/P", "IFF", "TCN", "ILS", "D/L", "BCN", "ON/OFF"],
         function_row=(-88, 196, 88, 212),
         knobs=[(-98, 70, 8, "ADF"), (-98, 110, 9, "VOL 1"), (98, 70, 8, "BRT"),
                (98, 110, 9, "VOL 2"), (-98, 160, 7, "COMM 1"), (98, 160, 7, "COMM 2")]),
    ddi("DDI_R", 220),
    dict(kind="plate", name="RightCol", rect=(332, 150, 390, 312)),
    dict(kind="toggle", c=(361, 180), legend="IR COOL"),
    dict(kind="knob", c=(361, 232), r=12, legend="MAP GAIN"),
    dict(kind="toggle", c=(361, 286), legend="STBY ADI\nILS"),
]
LOWER_PANEL = [
    # jettison station select / flap and gear position lights
    dict(kind="plate", name="JettSel", rect=(-390, 318, -334, 508)),
    dict(kind="button", rect=(-380, 346, -344, 366), legend="CTR", colour="green"),
    dict(kind="button", rect=(-382, 374, -364, 394), legend="LI", colour="green"),
    dict(kind="button", rect=(-360, 374, -342, 394), legend="RI", colour="green"),
    dict(kind="button", rect=(-382, 400, -364, 420), legend="LO", colour="green"),
    dict(kind="button", rect=(-360, 400, -342, 420), legend="RO", colour="green"),
    dict(kind="button", rect=(-384, 432, -340, 498), legend="NOSE\nLEFT RIGHT\nHALF FULL\nFLAPS", colour="green"),
    # engine monitor display
    dict(kind="plate", name="EngineDisp", rect=(-330, 318, -216, 460)),
    dict(kind="lcd", rect=(-322, 340, -276, 358), text="98"),
    dict(kind="lcd", rect=(-268, 340, -222, 358), text="103"),
    dict(kind="lcd", rect=(-322, 372, -276, 390), text="854"),
    dict(kind="lcd", rect=(-268, 372, -222, 390), text="876"),
    dict(kind="lcd", rect=(-322, 404, -276, 422), text="10200"),
    dict(kind="lcd", rect=(-268, 404, -222, 422), text="10400"),
    dict(kind="gauge", c=(-296, 444), r=13, face="noz"),
    dict(kind="gauge", c=(-250, 444), r=13, face="noz"),
    # fuel quantity, bingo, HDG / CRS
    dict(kind="plate", name="FuelQty", rect=(-212, 318, -124, 462)),
    dict(kind="gauge", c=(-168, 372), r=36, face="fuel"),
    dict(kind="knob", c=(-200, 436), r=8, legend="BINGO"),
    dict(kind="knob", c=(-150, 440), r=12, legend="FUEL SEL"),
    dict(kind="plate", name="HdgCrs", rect=(-212, 466, -124, 508)),
    dict(kind="knob", c=(-190, 488), r=11, legend="HDG"),
    dict(kind="knob", c=(-146, 488), r=11, legend="CRS"),
    # horizontal situation display
    dict(kind="hsd", name="HSD", rect=(-117, 306, 117, 590), screen=(-82, 352, 82, 516),
         knobs=[(-98, 330, 9, "MODE"), (98, 330, 9, "BRT")]),
    # standby instruments and RWR azimuth indicator
    dict(kind="plate", name="Standby", rect=(124, 318, 392, 510)),
    dict(kind="gauge", c=(182, 378), r=48, face="adi"),
    dict(kind="gauge", c=(298, 378), r=50, face="rwr"),
    dict(kind="gauge", c=(162, 464), r=36, face="asi"),
    dict(kind="gauge", c=(250, 464), r=36, face="alt"),
    dict(kind="gauge", c=(338, 464), r=36, face="vsi"),
]
FRONT_MIP = WARNING_LIGHTS + MASTER_ARM + DISPLAYS + HUD_CONTROLS + LOWER_PANEL

# The F/A-18B rear cockpit (NASA 845, photo ED08-0252-06): the same DDIs,
# UFC and lower panel; no HUD or HUD control panel, and a row of caution /
# A/A / A/G lights under the UFC instead of the master arm panel.
REAR_MIP = DISPLAYS + LOWER_PANEL + [
    dict(kind="plate", name="RearLights", rect=(-80, 226, 80, 262)),
    dict(kind="button", rect=(-74, 230, -40, 258), legend="MASTER\nCAUTION", colour="amber"),
    dict(kind="button", rect=(-34, 230, 0, 258), legend="FIRE", colour="red"),
    dict(kind="button", rect=(6, 230, 40, 258), legend="A/A", colour="green"),
    dict(kind="button", rect=(46, 230, 74, 258), legend="A/G", colour="green"),
    dict(kind="plate", name="Placard", rect=(-390, 140, -334, 300)),
]

# --- side consoles -----------------------------------------------------------
# No direct photo of the A/B side consoles was available, so these follow the
# general Hornet arrangement (throttle quadrant forward on the left console,
# rows of 146 mm (5.75 in) DZUS-fastened panels) without claiming exact
# switch positions.  Coordinates: s along the console from its forward end
# (mm, aft positive), t across it from the cockpit wall (mm, inboard positive).
CONSOLE_LEN = 1080
CONSOLE_WIDTH = 150
LEFT_CONSOLE = [
    dict(name="FUEL", s=(0, 120), switches=4, knobs=1),
    dict(name="THROTTLE QUADRANT", s=(120, 400), throttle=True),
    dict(name="EXT LT", s=(400, 520), switches=3, knobs=3),
    dict(name="COMM", s=(520, 680), switches=2, knobs=4),
    dict(name="OBOGS / ANTI-G", s=(680, 820), switches=3, knobs=1),
    dict(name="GND PWR", s=(820, 940), switches=4, knobs=0),
    dict(name="SEAT", s=(940, 1080), switches=1, knobs=1),
]
RIGHT_CONSOLE = [
    dict(name="ELEC", s=(0, 140), switches=4, knobs=0),
    dict(name="ECS", s=(140, 300), switches=3, knobs=3),
    dict(name="INTR LT", s=(300, 440), switches=1, knobs=5),
    dict(name="SNSR", s=(440, 600), switches=3, knobs=2),
    dict(name="KY-58", s=(600, 740), switches=2, knobs=2),
    dict(name="DEFOG", s=(740, 860), switches=2, knobs=1),
    dict(name="AVIONICS", s=(860, 1080), switches=4, knobs=0),
]

# --- texture atlas regions (pixels in a 4096 x 4096 atlas) ---------------------
ATLAS = 4096
PX_PER_MM = 2.0
REGION = {
    "front_mip": (0, 0, 1600, 1220),          # 800 x 610 mm at 2 px/mm
    "rear_mip": (1600, 0, 3200, 1220),
    "console_l": (3200, 0, 3520, 2200),       # 160 x 1100 mm
    "console_r": (3520, 0, 3840, 2200),
    "gauges": (0, 1220, 1600, 1420),          # 8 faces, 200 px each
    "rail": (0, 1420, 1600, 1620),            # perforated sill longeron strip
    "labels": (0, 1620, 1600, 2560),          # seat and canopy placards
    "cells": (0, 2560, 4096, 4096),           # 8 x 3 material tiles, 512 px = 1 m
}
GAUGE_ORDER = ["adi", "rwr", "asi", "alt", "vsi", "fuel", "noz", "clock"]
# material tiles: worn finishes that any part can map onto (planar, 1 m per tile)
CELLS = ["black", "panel", "darkgrey", "midgrey", "lightgrey", "metal", "rubber", "cushion",
         "leather", "strap", "yellow", "red", "white", "green", "amber", "glow",
         "floor", "wall", "stripe", "olive", "canvas", "steel", "brass", "glass"]
CELL_PX = 512
CELL_M = 1.0


def cell_rect(name):
    """Pixel rect of a material tile."""
    x0, y0, _, _ = REGION["cells"]
    i = CELLS.index(name)
    cx = x0 + CELL_PX * (i % 8)
    cy = y0 + CELL_PX * (i // 8)
    return (cx, cy, cx + CELL_PX, cy + CELL_PX)


def swatch_uv(name):
    """UV (Blender convention, origin bottom-left) at the centre of a tile."""
    x0, y0, x1, y1 = cell_rect(name)
    return (((x0 + x1) / 2) / ATLAS, 1.0 - ((y0 + y1) / 2) / ATLAS)


def cell_uvs(name, pts):
    """Planar UVs for one face inside a material tile: project on the face's
    dominant axis, metres -> tile pixels, inset 8 px from the tile edges."""
    x0, y0, x1, y1 = cell_rect(name)
    n = [0.0, 0.0, 0.0]
    m = len(pts)
    for i in range(m):                                   # Newell normal
        a, b = pts[i], pts[(i + 1) % m]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    k = max(range(3), key=lambda i: abs(n[i]))
    ax = [i for i in range(3) if i != k]
    pa = [p[ax[0]] for p in pts]
    pb = [p[ax[1]] for p in pts]
    ext = max(max(pa) - min(pa), max(pb) - min(pb), 1e-6)
    scale = min(1.0, CELL_M / ext * 0.97)
    inset = 8
    span = CELL_PX - 2 * inset
    out = []
    for a, b in zip(pa, pb):
        fu = (a - min(pa)) * scale / CELL_M
        fv = (b - min(pb)) * scale / CELL_M
        out.append(((x0 + inset + fu * span) / ATLAS, 1.0 - (y0 + inset + fv * span) / ATLAS))
    return out


def region_uv(region, fx, fy):
    """UV for fractional position (fx right, fy down) inside a named region."""
    x0, y0, x1, y1 = REGION[region]
    return ((x0 + fx * (x1 - x0)) / ATLAS, 1.0 - (y0 + fy * (y1 - y0)) / ATLAS)


def mip_uv(region, u, v):
    """UV for panel coordinates (mm) inside a MIP region (panel centred)."""
    x0, y0, x1, y1 = REGION[region]
    px = (x0 + x1) / 2 + u * PX_PER_MM
    py = y0 + 10 + v * PX_PER_MM
    return (px / ATLAS, 1.0 - py / ATLAS)
