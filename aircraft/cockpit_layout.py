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


def ddi(name, cu, v0=65):
    """Digital display indicator centred at u=cu, top at v0 (bezel 210 x 237 mm)."""
    return dict(kind="ddi", name=name,
                rect=(cu - 105, v0, cu + 105, v0 + 237),
                screen=(cu - 70, v0 + 45, cu + 70, v0 + 185),
                knobs=[(cu - 10, v0 + 17, 9, "NIGHT/DAY"), (cu - 88, v0 + 219, 9, "BRT"),
                       (cu + 88, v0 + 219, 9, "CONT")])


def bezel_buttons(e):
    """Push-button centres (u, v) around a DDI or HSD bezel: 5 top, 5 bottom,
    5 left, 5 right (shared by the model and the texture painter)."""
    u0, v0, u1, v1 = e["rect"]
    cu = (u0 + u1) / 2
    t0, t1 = e["screen"][1], e["screen"][3]
    if e["kind"] == "ddi":
        return ([(cu - 56 + 28 * i, v0 + 23) for i in range(5)] + [(cu - 56 + 28 * i, v0 + 205) for i in range(5)] +
                [(u0 + 17, v0 + 60 + 27.5 * i) for i in range(5)] + [(u1 - 17, v0 + 60 + 27.5 * i) for i in range(5)])
    return ([(cu - 56 + 28 * i, (t0 + v0) / 2 + 4) for i in range(5)] +
            [(cu - 56 + 28 * i, (t1 + v1) / 2) for i in range(5)] +
            [(u0 + 17, t0 + 18 + 32 * i) for i in range(5)] + [(u1 - 17, t0 + 18 + 32 * i) for i in range(5)])


def ufc(dv=0):
    """Up-front control, shifted dv mm down the panel."""
    return dict(kind="ufc", name="UFC", rect=(-110, 22 + dv, 110, 220 + dv), dv=dv,
                scratchpad=(-82, 34 + dv, -12, 54 + dv),
                keypad=dict(origin=(-80, 62 + dv), pitch=(25, 26), rows=["123", "456", "789", "C0E"]),
                options=[(22, 62 + dv + 22 * i, 92, 80 + dv + 22 * i) for i in range(5)],
                option_buttons=[(12, 71 + dv + 22 * i) for i in range(5)],
                functions=["A/P", "IFF", "TCN", "ILS", "D/L", "BCN", "ON/OFF"],
                function_row=(-88, 196 + dv, 88, 212 + dv),
                knobs=[(-98, 70 + dv, 8, "ADF"), (-98, 110 + dv, 9, "VOL 1"), (98, 70 + dv, 8, "BRT"),
                       (98, 110 + dv, 9, "VOL 2"), (-98, 160 + dv, 7, "COMM 1"), (98, 160 + dv, 7, "COMM 2")])


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
    ufc(0),
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

# The F/A-18B rear cockpit, NATOPS figure FO-2: DDIs either side of the UFC
# (moved 40 mm down), the warning / caution lights above the UFC with the
# emergency jettison button to their left and the master mode lights to
# their right, a third DDI in the centre where the front seat has the HSD,
# gear and flap position lights and a display select switch at lower left,
# the engine monitor, fuel quantity and clock, and the standby instruments.
REAR_MIP = [
    ddi("DDI_L", -220), ufc(40), ddi("DDI_R", 220),
    dict(kind="plate", name="RearWarn", rect=(-110, 16, 110, 58)),
    dict(kind="button", rect=(-105, 21, -78, 53), legend="FIRE", colour="red"),
    dict(kind="button", rect=(-75, 21, -45, 53), legend="MASTER\nCAUTION", colour="amber"),
    dict(kind="button", rect=(-42, 21, -14, 36), legend="L BLEED", colour="red"),
    dict(kind="button", rect=(-42, 38, -14, 53), legend="R BLEED", colour="red"),
    dict(kind="button", rect=(-11, 21, 17, 36), legend="SPD BRK", colour="green"),
    dict(kind="button", rect=(-11, 38, 17, 53), legend="L BAR", colour="green"),
    dict(kind="button", rect=(20, 21, 48, 53), legend="", colour="amber"),
    dict(kind="button", rect=(51, 21, 77, 53), legend="APU\nFIRE", colour="red"),
    dict(kind="button", rect=(80, 21, 105, 53), legend="FIRE", colour="red"),
    dict(kind="button", rect=(-165, 12, -120, 58), legend="EMERG\nJETT", colour="stripe"),
    dict(kind="plate", name="MasterMode", rect=(118, 10, 162, 62)),
    dict(kind="button", rect=(122, 14, 158, 36), legend="A/A", colour="green"),
    dict(kind="button", rect=(122, 38, 158, 58), legend="A/G", colour="green"),
    # gear / flap position lights, display select
    dict(kind="plate", name="GearFlaps", rect=(-390, 318, -334, 440)),
    dict(kind="button", rect=(-380, 326, -344, 344), legend="NOSE", colour="green"),
    dict(kind="button", rect=(-384, 348, -364, 366), legend="LEFT", colour="green"),
    dict(kind="button", rect=(-361, 348, -341, 366), legend="RIGHT", colour="green"),
    dict(kind="button", rect=(-384, 372, -364, 390), legend="HALF", colour="green"),
    dict(kind="button", rect=(-361, 372, -341, 390), legend="FULL", colour="green"),
    dict(kind="button", rect=(-380, 396, -344, 414), legend="FLAPS", colour="amber"),
    dict(kind="plate", name="DisplaySel", rect=(-390, 448, -334, 508)),
    dict(kind="toggle", c=(-362, 484), legend="DISPLAY"),
] + [e for e in LOWER_PANEL
     if e.get("name") not in ("JettSel", "HSD", "HdgCrs")
     and e.get("legend") not in ("CTR", "LI", "RI", "LO", "RO", "NOSE\nLEFT RIGHT\nHALF FULL\nFLAPS", "HDG", "CRS")] + [
    dict(kind="plate", name="Clock", rect=(-212, 466, -124, 540)),
    dict(kind="gauge", c=(-168, 503), r=30, face="clock"),
    ddi("DDI_C", 0, 330),
]

# --- side consoles -----------------------------------------------------------
# Panel order from the NATOPS foldouts: FO-1 sheet 2 (front cockpit, A/B) and
# FO-2 sheet 2 (rear cockpit of the B).  Coordinates: s along the console
# from its forward end (mm, aft positive), t across it from the cockpit wall
# (mm, inboard positive).  Controls are (kind, fs, ft, legend[, extra]) with
# fs / ft the fractions along the panel / across it from the pilot's left; kinds: toggle, knob, button,
# gauge (extra = face), handle (striped pull handle).  Switch positions within a
# panel follow the drawings' arrangement, not measured spacing.
CONSOLE_LEN = 1080
CONSOLE_WIDTH = 150
CONSOLE_START = 0.30          # m aft of the instrument panel face: room for the knee panels


def row(kind, legends, fs, t0=0.2, t1=0.8):
    """Controls of one kind spread across a panel at fraction fs along it."""
    n = len(legends)
    return [(kind, fs, t0 + (t1 - t0) * (i / (n - 1) if n > 1 else 0.5), lg) for i, lg in enumerate(legends)]


def blank(s, t=(0, CONSOLE_WIDTH), name=""):
    return dict(name=name, s=s, t=t, blank=True, controls=[])


CONSOLES = {
    "Front": {
        "L": [
            dict(name="GND PWR", s=(0, 150), t=(0, 52),
                 controls=row("toggle", ["1", "2"], 0.33, 0.25, 0.75) + row("toggle", ["3", "4"], 0.6, 0.25, 0.75)
                 + row("toggle", ["EXT PWR"], 0.86)),
            dict(name="FIRE TEST", s=(0, 60), t=(55, 150), controls=row("toggle", ["TEST"], 0.55)),
            dict(name="THROTTLES", s=(60, 380), t=(55, 150), throttle=True, controls=[]),
            dict(name="EXT LT", s=(150, 380), t=(0, 52),
                 controls=row("knob", ["FORMATION"], 0.2) + row("knob", ["POSITION"], 0.47)
                 + row("toggle", ["STROBE", "INTR WING"], 0.8, 0.25, 0.75)),
            dict(name="FUEL", s=(380, 520),
                 controls=row("toggle", ["PROBE"], 0.55, 0.15, 0.15) + row("knob", ["WING", "CTR"], 0.55, 0.42, 0.66)
                 + row("toggle", ["DUMP"], 0.55, 0.88, 0.88)),
            dict(name="APU", s=(520, 610), t=(0, 70), controls=row("toggle", ["APU", "ENG CRANK"], 0.55)),
            dict(name="FCS", s=(520, 620), t=(72, 150),
                 controls=row("knob", ["RUD TRIM"], 0.38, 0.3, 0.3) + row("button", ["T/O TRIM"], 0.38, 0.75, 0.75)
                 + row("button", ["GAIN ORIDE", "RESET"], 0.8)),
            dict(name="COMM", s=(620, 800),
                 controls=row("knob", ["ICS", "RWR", "WPN", "AUX"], 0.3, 0.12, 0.88)
                 + row("toggle", ["IFF", "ILS", "CRYPTO", "MODE 4"], 0.75, 0.12, 0.88)),
            dict(name="OXY / ANTI-G", s=(800, 950),
                 controls=[("gauge", 0.45, 0.62, "LOX", "lox")] + row("toggle", ["OXYGEN"], 0.3, 0.18, 0.18)
                 + row("button", ["OXY TEST"], 0.78, 0.2, 0.2)),
            dict(name="MC / HYD ISOL", s=(950, 1010), controls=row("toggle", ["MC", "HYD ISOL"], 0.55)),
            dict(name="ANT SEL", s=(1010, 1080), controls=row("toggle", ["COMM 1", "IFF"], 0.55)),
        ],
        "R": [
            dict(name="ELEC", s=(0, 125),
                 controls=[("gauge", 0.3, 0.5, "VOLTS", "volt")] + row("toggle", ["L GEN", "BATT", "R GEN"], 0.78)),
            dict(name="ECS", s=(125, 265),
                 controls=row("knob", ["MODE", "TEMP"], 0.25, 0.25, 0.6) + row("toggle", ["CABIN PRESS"], 0.25, 0.88, 0.88)
                 + row("toggle", ["PITOT", "ENG"], 0.72, 0.15, 0.45) + row("knob", ["BLEED AIR"], 0.72, 0.8, 0.8)),
            dict(name="INTR LT", s=(265, 405),
                 controls=row("knob", ["CONSOLES", "INST PNL", "FLOOD"], 0.28)
                 + row("toggle", ["LT TEST"], 0.75, 0.2, 0.2) + row("knob", ["WARN/CAUTION", "CHART"], 0.75, 0.52, 0.85)),
            dict(name="SNSR", s=(405, 535),
                 controls=row("toggle", ["FLIR", "LTD/R", "LST/NFLR"], 0.28) + row("knob", ["RADAR", "INS"], 0.75, 0.3, 0.72)),
            dict(name="KY-58", s=(535, 645),
                 controls=row("knob", ["MODE", "FILL", "POWER"], 0.35) + row("knob", ["VOLUME"], 0.8, 0.25, 0.25)),
            blank((645, 765)), blank((765, 885)),
            dict(name="FAN TEST", s=(885, 950), controls=row("toggle", ["FAN TEST"], 0.55)),
            dict(name="MAP & DATA CASE", s=(950, 1080), blank=True, controls=[]),
        ],
    },
    "Rear": {
        "L": [
            blank((0, 150), (0, 52)),
            blank((0, 60), (55, 150)),
            dict(name="THROTTLES", s=(60, 380), t=(55, 150), throttle=True, controls=[]),
            dict(name="VOL", s=(150, 380), t=(0, 52),
                 controls=row("knob", ["TCN", "ICS"], 0.2, 0.25, 0.75) + row("knob", ["WPN", "AUX"], 0.45, 0.25, 0.75)
                 + row("knob", ["RWR", "ECM"], 0.7, 0.25, 0.75) + row("toggle", ["RADIO ORIDE"], 0.9)),
            blank((380, 420), (0, 52)),
            dict(name="CANOPY JETT", s=(420, 620), t=(0, 70), controls=[("handle", 0.5, 0.5, "CANOPY JETT")]),
            dict(name="AN/ARC-182 DATA LINK", s=(380, 620), t=(70, 150), blank=True, controls=[]),
            dict(name="ALE-39", s=(620, 900), t=(0, 60), controls=[("button", f, 0.5, "") for f in (0.3, 0.42, 0.54, 0.66, 0.78)]),
            dict(name="OXY / ANTI-G", s=(620, 900), t=(60, 150),
                 controls=row("toggle", ["OXYGEN"], 0.2, 0.2, 0.2) + [("gauge", 0.25, 0.68, "LOX", "lox")]
                 + row("button", ["OXY TEST"], 0.55, 0.3, 0.3) + row("button", ["ANTI-G"], 0.82, 0.5, 0.5)),
            blank((900, 1080)),
        ],
        "R": [
            blank((0, 100)),
            dict(name="INTR LT", s=(100, 260),
                 controls=row("knob", ["CONSOLES", "INST PNL", "FLOOD"], 0.3)
                 + row("toggle", ["LT TEST"], 0.75, 0.2, 0.2) + row("knob", ["WARN/CAUTION"], 0.75, 0.6, 0.6)),
            blank((260, 420)), blank((420, 560)),
            blank((560, 820), (0, 105)), blank((820, 1080), (0, 105)),
            dict(name="FAN TEST", s=(560, 660), t=(105, 150), controls=row("toggle", ["FAN TEST"], 0.55)),
            dict(name="UTILITY LT", s=(660, 760), t=(105, 150), controls=[("knob", 0.5, 0.5, "")]),
            dict(name="MAP CASE", s=(760, 1080), t=(105, 150), blank=True, controls=[]),
        ],
    },
}
CONSOLE_REGIONS = {"Front": ("console_l", "console_r"), "Rear": ("console_rl", "console_rr")}

# --- knee panels and centre pedestal ---------------------------------------------
# Below the main panel, in its plane (u, v in panel mm, as the MIP): the left
# and right vertical panels and the pedestal under the HSD, from FO-1 / FO-2.
# Kinds as the MIP, plus: wheel (landing-gear handle, wheel knob on a stem),
# tee (striped T pull handle), hook (arresting-hook handle), fold (wing-fold
# handle), lever (command selector), caution (grid of caution lights), placard
# (flat plate with text).
CAUTION_FRONT = ["CK SEAT", "APU ACC", "BATT SW", "", "GEN TIE", "", "", "FCES", "FCS HOT", "FUEL LO", "L GEN", "R GEN"]
SUBPANELS = {
    "Front": [
        dict(name="KneeL", region="vpanel_fl", rect=(-393, 516, -150, 690), items=[
            dict(kind="plate", name="LdgGear", rect=(-390, 520, -300, 686)),
            dict(kind="wheel", c=(-345, 610), legend="LDG GEAR"),
            dict(kind="button", rect=(-385, 530, -355, 546), legend="DN LOCK\nORIDE", colour="amber"),
            dict(kind="button", rect=(-335, 530, -305, 546), legend="WARN\nTONE SIL", colour="amber"),
            dict(kind="plate", name="LdgControls", rect=(-296, 520, -153, 600)),
            dict(kind="toggle", c=(-276, 560), legend="LAUNCH\nBAR"),
            dict(kind="toggle", c=(-238, 560), legend="FLAP"),
            dict(kind="knob", c=(-185, 558), r=14, legend="SELECT JETT"),
            dict(kind="plate", name="LdgLights", rect=(-296, 604, -153, 686)),
            dict(kind="toggle", c=(-276, 640), legend="LDG/\nTAXI"),
            dict(kind="toggle", c=(-238, 640), legend="ANTI\nSKID"),
            dict(kind="toggle", c=(-200, 640), legend="HOOK\nBYPASS"),
            dict(kind="tee", c=(-170, 664), legend="EMERG BRK"),
        ]),
        dict(name="KneeR", region="vpanel_fr", rect=(150, 516, 393, 690), items=[
            dict(kind="plate", name="Gauges", rect=(153, 520, 300, 596)),
            dict(kind="gauge", c=(190, 558), r=30, face="brake"),
            dict(kind="gauge", c=(262, 558), r=30, face="hyd"),
            dict(kind="caution", rect=(153, 600, 260, 686), legends=CAUTION_FRONT, cols=3),
            dict(kind="plate", name="HookFold", rect=(264, 520, 390, 686)),
            dict(kind="hook", c=(360, 548), legend="HOOK"),
            dict(kind="button", rect=(326, 528, 344, 542), legend="HOOK", colour="red"),
            dict(kind="fold", c=(330, 640), legend="WING FOLD"),
            dict(kind="toggle", c=(284, 560), legend="FCS\nCOOL"),
            dict(kind="placard", rect=(268, 600, 300, 682), text="LANDING\nWHEELS\nFLAPS\nHOOK\nANTISKID\nHARNESS"),
        ]),
        dict(name="Pedestal", region="pedestal_f", rect=(-85, 596, 85, 800), items=[
            dict(kind="plate", name="Dispenser", rect=(-82, 600, 82, 690)),
            dict(kind="knob", c=(-50, 635), r=14, legend="DISPENSER"),
            dict(kind="toggle", c=(-5, 625), legend="CHAFF"),
            dict(kind="toggle", c=(25, 625), legend="FLARE"),
            dict(kind="knob", c=(58, 635), r=11, legend="ECM"),
            dict(kind="button", rect=(-20, 660, 20, 680), legend="AUX REL", colour="amber"),
            dict(kind="plate", name="Clock", rect=(-60, 696, 60, 768)),
            dict(kind="gauge", c=(0, 732), r=32, face="clock"),
            dict(kind="tee", c=(-45, 786), legend="RUD PED ADJ", small=True),
        ]),
    ],
    "Rear": [
        dict(name="KneeL", region="vpanel_rl", rect=(-393, 516, -150, 680), items=[
            dict(kind="plate", name="Emerg", rect=(-390, 520, -153, 676)),
            dict(kind="tee", c=(-330, 580), legend="EMERG\nLDG GEAR"),
            dict(kind="tee", c=(-230, 640), legend="EMERG BRK"),
        ]),
        dict(name="KneeR", region="vpanel_rr", rect=(150, 516, 393, 680), items=[
            dict(kind="plate", name="Command", rect=(153, 520, 300, 596)),
            dict(kind="lever", c=(225, 560), legend="COMMAND\nSELECTOR"),
            dict(kind="caution", rect=(153, 600, 260, 676), legends=CAUTION_FRONT, cols=3),
            dict(kind="plate", name="Gauges", rect=(304, 520, 390, 676)),
            dict(kind="gauge", c=(347, 560), r=30, face="hyd"),
            dict(kind="gauge", c=(347, 636), r=30, face="cabalt"),
        ]),
        dict(name="Pedestal", region="pedestal_r", rect=(-85, 596, 85, 780), items=[
            dict(kind="plate", name="PedAdj", rect=(-82, 600, 82, 690)),
            dict(kind="tee", c=(-40, 645), legend="RUD PED ADJ", small=True),
            dict(kind="placard", rect=(10, 620, 76, 650), text="BUNO"),
            dict(kind="plate", name="Louver", rect=(-70, 700, 70, 770)),
        ]),
    ],
}

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
    "gauges2": (0, 1620, 1600, 1820),         # 8 more faces
    "pedestal_f": (0, 1820, 400, 2280),       # 200 x 230 mm
    "pedestal_r": (400, 1820, 800, 2280),
    "labels": (800, 1820, 1600, 2560),        # seat and canopy placards
    "vpanel_fl": (1600, 1220, 2100, 1620),    # knee panels, 250 x 200 mm
    "vpanel_fr": (2100, 1220, 2600, 1620),
    "vpanel_rl": (2600, 1220, 3100, 1620),
    "vpanel_rr": (1600, 1620, 2100, 2020),
    "console_rl": (3840, 0, 4000, 1100),      # rear consoles, 1 px per mm
    "console_rr": (3840, 1100, 4000, 2200),
    "cells": (0, 2560, 4096, 4096),           # 8 x 3 material tiles, 512 px = 1 m
}
REGION_PPM = {"console_rl": 1.0, "console_rr": 1.0}      # px per mm where not PX_PER_MM
GAUGE_ORDER = ["adi", "rwr", "asi", "alt", "vsi", "fuel", "noz", "clock",
               "brake", "hyd", "radalt", "cabalt", "lox", "volt"]
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


def gauge_centre_px(face):
    """Pixel centre of a gauge face: the first 8 in "gauges", the rest in "gauges2"."""
    i = GAUGE_ORDER.index(face)
    x0, y0, _, _ = REGION["gauges" if i < 8 else "gauges2"]
    return x0 + 100 + 200 * (i % 8), y0 + 100


def sub_px(region, rect, u, v):
    """Pixel of panel point (u, v) mm in a sub-panel region whose top-left is rect[:2]."""
    x0, y0, _, _ = REGION[region]
    return x0 + 4 + (u - rect[0]) * PX_PER_MM, y0 + 4 + (v - rect[1]) * PX_PER_MM


def sub_uv(region, rect, u, v):
    px, py = sub_px(region, rect, u, v)
    return (px / ATLAS, 1.0 - py / ATLAS)
