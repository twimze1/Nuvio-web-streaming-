"""
External stores of the US Navy / USMC F/A-18A/B: dimensions, carriage and
station compatibility, shared by the Blender builder (fa18_stores.py) and the
texture painter (tools/make_store_textures.py).  Pure Python, no bpy.

Sources (full list and disagreements in README "Weapons"):
  * NAVEDTRA 12308 Aviation Ordnanceman 3 & 2 (1990, approved for public
    release), Fig. 14-21 F/A-18 station chart -- launchers/racks per station.
  * A1-F18AC-NFM-000 NATOPS (2008), Fig. 4-4 -- station distances from the
    centreline: 1/9 5.94 m, 2/8 3.41 m, 3/7 2.23 m, 4/6 1.13 m; tanks on 3/5/7.
  * USAF Weapons File 2003-04, designation-systems.net, FAS, NWC TP 7033 --
    store dimensions and weights.
`conf` is the confidence in the *shape and size*: "high" = published
length, diameter and span; "medium" = published length/diameter, fin
sizes scaled from photos/drawings; "est" = no published dimensions found,
estimated (stated in `note`).
`stations` lists only stations documented for the A/B; an empty list means
the store was carried by Hornets but its A/B stations are not documented.
`era`: "baseline" (A/B as built) or "A+" (later upgrade, mostly C-equivalent).
"""
import math

IN = 0.0254

# --- body profiles: (t along length 0 nose .. 1 tail, radius as fraction of D/2)
def ogive(nose=0.18, tail=0.97, tail_r=0.92, tip=0.02):
    """Missile body: tangent-ogive radome, cylinder, slight boat tail."""
    pts = [(0.0, tip)]
    for i in range(1, 9):
        f = i / 8
        pts.append((nose * f, tip + (1 - tip) * math.sqrt(1 - (1 - f) ** 2)))
    pts += [(tail, 1.0), (1.0, tail_r)]
    return pts


def dome(nose=0.06, tail=0.98, tail_r=0.9):
    """Hemispherical seeker dome (AIM-9, Maverick, SLAM, Walleye)."""
    pts = [(0.0, 0.0)]
    for i in range(1, 7):
        a = math.pi / 2 * i / 6
        pts.append((nose * (1 - math.cos(a)), math.sin(a) * 0.96))
    pts += [(nose + 0.01, 1.0), (tail, 1.0), (1.0, tail_r)]
    return pts


def mk80(body_end=0.80, fuze=0.16):
    """Low-drag general-purpose bomb (Mk 80 series), body only; the tail
    (conical fin, Snakeye, JDAM or Paveway airfoil group) is added aft."""
    pts = [(0.0, fuze), (0.01, fuze + 0.05)]
    for i in range(1, 10):
        f = i / 9
        pts.append((0.01 + 0.37 * f, fuze + (1 - fuze) * math.sqrt(1 - (1 - f) ** 2.2)))
    pts += [(0.55, 1.0), (body_end, 0.62), (body_end + 0.004, 0.50)]
    return pts


def can(nose=0.10, tail=0.92, tail_r=0.7):
    """Pods, tanks, dispensers: rounded nose, cylinder, tapered tail."""
    pts = [(0.0, 0.05)]
    for i in range(1, 7):
        f = i / 6
        pts.append((nose * f, 0.05 + 0.95 * math.sqrt(1 - (1 - f) ** 2)))
    pts += [(tail, 1.0), (1.0, tail_r)]
    return pts


def tank(nose=0.27, tail=0.70):
    """Drop tank: long ogive nose, cylinder, long tail cone to a point."""
    pts = [(0.0, 0.03)]
    for i in range(1, 10):
        f = i / 9
        pts.append((nose * f, 0.03 + 0.97 * math.sqrt(1 - (1 - f) ** 2)))
    for i in range(0, 9):
        f = i / 8
        pts.append((tail + (1 - tail) * f, 1.0 - 0.94 * f ** 1.6))
    return pts


def fins(x0, c0, x1, c1, span, n=4, roll=45.0, t=0.006, name="fin"):
    """Fin set: root LE x0 and chord c0, tip LE x1 and chord c1 (m from the
    nose), total span tip-to-tip (m), n fins, roll angle of the first fin."""
    return dict(x0=x0, c0=c0, x1=x1, c1=c1, span=span, n=n, roll=roll, t=t, name=name)


# --- colours (sRGB) --------------------------------------------------------------
OD = (88, 92, 64)            # olive drab, Mk 80 bodies
OD_THERMAL = (96, 98, 74)    # thermally protected (ablative) coating, lighter and rough
WHITE = (214, 214, 206)      # missile bodies
LGREY = (168, 172, 170)
GREY = (120, 126, 130)       # pods, tanks (airframe-ish grey)
TPS = (110, 118, 124)        # pylons
DGREY = (70, 74, 76)
KIT = (150, 152, 140)        # guidance kits
YELLOW = (224, 180, 30)
BROWN = (120, 72, 36)
BLUE = (90, 140, 200)
BLACK = (30, 30, 30)
GLASS = (40, 50, 60)

# --- the stores -------------------------------------------------------------------
# geometry: L length, D body diameter, profile, fin sets, extra features
# carriage: mount = launcher/rack id ("" for pylons/launchers themselves);
#           lugs = suspension lug spacing (m) for rack-carried stores
# paint: body colour, nose colour, bands [(t, width m, colour)], finish
STORES = [
    # ---------------- air-to-air ----------------
    dict(id="AIM-9L", name="AIM-9L/M Sidewinder", cat="aa_missile", era="baseline", conf="medium",
         L=2.85, D=0.127, mass=86.6, profile=dome(0.035), mount="LAU-7", stations=[1, 2, 8, 9],
         fins=[fins(0.30, 0.28, 0.46, 0.06, 0.56, roll=45, name="canard"),
               fins(2.42, 0.40, 2.62, 0.20, 0.63, roll=45, name="wing")],
         features=["rollerons"], body=WHITE, nose=GLASS,
         bands=[(0.22, 0.05, YELLOW), (0.45, 0.05, BROWN)],
         note="Rear wing span 0.63 m published; canard span (0.56 m) and planforms scaled from photos. "
              "2/8 via LAU-115 with two LAU-7 side rails."),
    dict(id="AIM-9X", name="AIM-9X Sidewinder", cat="aa_missile", era="A+", conf="medium",
         L=3.02, D=0.127, mass=85.3, profile=dome(0.035), mount="LAU-7", stations=[],
         fins=[fins(1.05, 0.40, 1.15, 0.25, 0.353, roll=45, name="wing"),
               fins(2.72, 0.24, 2.80, 0.13, 0.445, roll=45, name="tail")],
         body=WHITE, nose=GLASS, bands=[(0.20, 0.05, YELLOW), (0.55, 0.05, BROWN)],
         note="Sources disagree on spans (0.28 vs 0.35/0.44 m); USAF WF values used. A/B stations not documented."),
    dict(id="AIM-7M", name="AIM-7F/M Sparrow", cat="aa_missile", era="baseline", conf="high",
         L=3.66, D=0.203, mass=231.3, profile=ogive(0.16), mount="LAU-116", stations=[2, 4, 6, 8],
         fins=[fins(1.45, 0.62, 1.82, 0.22, 1.016, roll=0, name="wing"),
               fins(3.18, 0.44, 3.40, 0.22, 0.81, roll=0, name="tail")],
         body=WHITE, nose=(200, 200, 192), bands=[(0.36, 0.06, YELLOW), (0.62, 0.06, BROWN)],
         note="LAU-116 semi-recessed on 4/6, LAU-115 on 2/8. Fins carried in + on the fuselage stations."),
    dict(id="AIM-120A", name="AIM-120A/B AMRAAM", cat="aa_missile", era="A+", conf="high",
         L=3.66, D=0.178, mass=156.5, profile=ogive(0.15), mount="LAU-116", stations=[2, 4, 6, 8],
         fins=[fins(1.30, 0.30, 1.50, 0.08, 0.533, roll=45, name="wing"),
               fins(3.30, 0.30, 3.42, 0.16, 0.635, roll=45, name="tail")],
         body=WHITE, nose=(200, 200, 192), bands=[(0.32, 0.06, YELLOW), (0.58, 0.06, BROWN)],
         note="A+ (APG-73) aircraft. Same stations as AIM-7 (LAU-116 on 4/6, LAU-115 + LAU-127 on 2/8)."),
    dict(id="AIM-120C", name="AIM-120C AMRAAM", cat="aa_missile", era="A+", conf="high",
         L=3.66, D=0.178, mass=156.5, profile=ogive(0.15), mount="LAU-116", stations=[2, 4, 6, 8],
         fins=[fins(1.30, 0.28, 1.45, 0.12, 0.447, roll=45, name="wing"),
               fins(3.32, 0.28, 3.42, 0.18, 0.447, roll=45, name="tail")],
         body=WHITE, nose=(200, 200, 192), bands=[(0.32, 0.06, YELLOW), (0.58, 0.06, BROWN)],
         note="Clipped wings and fins (0.447 m)."),
    # ---------------- air-to-ground missiles ----------------
    dict(id="AGM-65E", name="AGM-65E/F Maverick", cat="ag_missile", era="baseline", conf="high",
         L=2.49, D=0.305, mass=285.8, profile=dome(0.09), mount="LAU-117", stations=[2, 3, 7, 8],
         fins=[fins(1.05, 1.10, 1.75, 0.40, 0.719, roll=45, name="wing"),
               fins(2.30, 0.16, 2.34, 0.10, 0.50, roll=45, name="control")],
         body=WHITE, nose=GLASS, bands=[(0.35, 0.06, YELLOW), (0.72, 0.06, BROWN)],
         note="Laser (E) seeker shown as a dome; IR (F, A+) uses a glass dome of the same size."),
    dict(id="AGM-88", name="AGM-88 HARM", cat="ag_missile", era="baseline", conf="high",
         L=4.17, D=0.254, mass=362.9, profile=ogive(0.12), mount="LAU-118", stations=[2, 3, 7, 8],
         fins=[fins(1.55, 0.78, 1.95, 0.20, 1.118, roll=45, name="wing"),
               fins(3.86, 0.30, 3.98, 0.15, 0.61, roll=45, name="tail")],
         features=["harm_bulge"], body=WHITE, nose=(190, 190, 182),
         bands=[(0.28, 0.06, YELLOW), (0.62, 0.06, BROWN)],
         note="Wing span 1.118 m (designation-systems; FAS figure inconsistent)."),
    dict(id="AGM-84D", name="AGM-84D Harpoon", cat="ag_missile", era="baseline", conf="medium",
         L=3.85, D=0.343, mass=544, profile=ogive(0.08, tip=0.30), mount="BRU-32", lugs=30 * IN, stations=[],
         fins=[fins(1.60, 0.55, 1.80, 0.25, 0.914, roll=45, name="wing"),
               fins(3.45, 0.32, 3.55, 0.20, 0.70, roll=45, name="tail")],
         features=["intake"], body=WHITE, nose=(200, 200, 192),
         bands=[(0.30, 0.06, YELLOW), (0.50, 0.04, BROWN)],
         note="Air-launched, no booster; carried directly on BRU-32 (30 in lugs). A/B stations not documented."),
    dict(id="AGM-84E", name="AGM-84E SLAM", cat="ag_missile", era="A+", conf="medium",
         L=4.50, D=0.343, mass=628, profile=dome(0.05), mount="BRU-32", lugs=30 * IN, stations=[],
         fins=[fins(2.25, 0.55, 2.45, 0.25, 0.914, roll=45, name="wing"),
               fins(4.10, 0.32, 4.20, 0.20, 0.70, roll=45, name="tail")],
         features=["intake"], body=WHITE, nose=GLASS, bands=[(0.25, 0.06, YELLOW)],
         note="Harpoon airframe with IIR seeker and data link."),
    dict(id="AGM-62", name="AGM-62 Walleye I ER/DL", cat="guided_bomb", era="baseline", conf="medium",
         L=3.45, D=0.318, mass=510, profile=dome(0.07), mount="BRU-32", lugs=14 * IN, stations=[2, 8],
         fins=[fins(2.20, 1.00, 3.00, 0.25, 1.156, roll=45, name="wing")],
         features=["rat"], body=WHITE, nose=GLASS, bands=[(0.30, 0.06, YELLOW)],
         note="Stations 2/8 per Desert Storm F/A-18A loads (VFA-195); ER/DL wings slightly larger than Mk 1 span used."),
    dict(id="AGM-62II", name="AGM-62 Walleye II ER/DL", cat="guided_bomb", era="baseline", conf="medium",
         L=4.04, D=0.457, mass=1061, profile=dome(0.08), mount="BRU-32", lugs=30 * IN, stations=[],
         fins=[fins(2.60, 1.20, 3.55, 0.30, 1.295, roll=45, name="wing")],
         features=["rat"], body=WHITE, nose=GLASS, bands=[(0.30, 0.07, YELLOW)],
         note="Used by an F/A-18A in 1991; station not documented."),
    dict(id="AGM-154A", name="AGM-154A JSOW", cat="guided_bomb", era="A+", conf="medium",
         L=4.06, D=0.34, mass=483, profile=None, box=(0.34, 0.41), mount="BRU-32", lugs=14 * IN, stations=[],
         fins=[fins(3.55, 0.36, 3.75, 0.18, 0.70, n=6, roll=0, name="tail")],
         features=["jsow_wings"], body=(150, 156, 150), nose=(150, 156, 150), bands=[(0.25, 0.05, YELLOW)],
         note="Faceted box body (designation-systems width 0.338 m; height estimated); wings folded on top."),
    dict(id="ADM-141", name="ADM-141 TALD", cat="ag_missile", era="baseline", conf="est",
         L=2.34, D=0.28, mass=181, profile=None, box=(0.28, 0.28), mount="TER", lugs=14 * IN, stations=[],
         fins=[fins(2.00, 0.30, 2.15, 0.15, 0.55, n=3, roll=0, name="tail")],
         features=["tald_wings"], body=(190, 190, 186), nose=(190, 190, 186), bands=[],
         note="Length 2.34 m and deployed span 1.55 m published; body section estimated. Carried on TERs."),
    # ---------------- laser-guided and GPS bombs ----------------
    dict(id="GBU-12", name="GBU-12 Paveway II (500 lb)", cat="guided_bomb", era="baseline", conf="high",
         L=3.33, D=0.273, mass=275, profile=mk80(0.80), mount="BRU-32", lugs=14 * IN, stations=[],
         kit="paveway", kit_span=0.30, body=OD_THERMAL, nose=KIT, finish="thermal",
         bands=[(0.36, 0.05, YELLOW), (0.39, 0.05, YELLOW)],
         note="Mk 82 / BLU-111 body. A/B relied on off-board lasing; stations not documented."),
    dict(id="GBU-16", name="GBU-16 Paveway II (1,000 lb)", cat="guided_bomb", era="baseline", conf="high",
         L=3.68, D=0.356, mass=495, profile=mk80(0.80), mount="BRU-32", lugs=14 * IN, stations=[],
         kit="paveway", kit_span=0.38, body=OD_THERMAL, nose=KIT, finish="thermal",
         bands=[(0.36, 0.05, YELLOW), (0.39, 0.05, YELLOW)], note="Mk 83 / BLU-110 body."),
    dict(id="GBU-10", name="GBU-10 Paveway II (2,000 lb)", cat="guided_bomb", era="baseline", conf="high",
         L=4.32, D=0.457, mass=957, profile=mk80(0.80), mount="BRU-32", lugs=30 * IN, stations=[],
         kit="paveway", kit_span=0.48, body=OD_THERMAL, nose=KIT, finish="thermal",
         bands=[(0.36, 0.06, YELLOW), (0.39, 0.06, YELLOW)], note="Mk 84 / BLU-117 body."),
    dict(id="GBU-24", name="GBU-24 Paveway III", cat="guided_bomb", era="A+", conf="medium",
         L=4.39, D=0.457, mass=1050, profile=mk80(0.78), mount="BRU-32", lugs=30 * IN, stations=[],
         kit="paveway3", kit_span=0.914, body=OD_THERMAL, nose=KIT, finish="thermal",
         bands=[(0.38, 0.06, YELLOW)], note="Canard span 0.997 m; wings stowed 0.914 m."),
    dict(id="GBU-38", name="GBU-38 JDAM (500 lb)", cat="guided_bomb", era="A+", conf="high",
         L=2.35, D=0.273, mass=253, profile=mk80(0.84), mount="BRU-32", lugs=14 * IN, stations=[],
         kit="jdam", kit_span=0.432, strakes="nose", body=OD_THERMAL, nose=OD_THERMAL, finish="thermal",
         bands=[(0.08, 0.04, YELLOW), (0.11, 0.04, YELLOW)], note="Strakes at the nose on the 500 lb size."),
    dict(id="GBU-32", name="GBU-32 JDAM (1,000 lb)", cat="guided_bomb", era="A+", conf="high",
         L=3.04, D=0.356, mass=468, profile=mk80(0.84), mount="BRU-32", lugs=14 * IN, stations=[],
         kit="jdam", kit_span=0.498, strakes="mid", body=OD_THERMAL, nose=OD_THERMAL, finish="thermal",
         bands=[(0.08, 0.05, YELLOW), (0.11, 0.05, YELLOW)], note=""),
    dict(id="GBU-31", name="GBU-31 JDAM (2,000 lb)", cat="guided_bomb", era="A+", conf="high",
         L=3.88, D=0.457, mass=946, profile=mk80(0.84), mount="BRU-32", lugs=30 * IN, stations=[],
         kit="jdam", kit_span=0.643, strakes="mid", body=OD_THERMAL, nose=OD_THERMAL, finish="thermal",
         bands=[(0.08, 0.05, YELLOW), (0.11, 0.05, YELLOW)], note=""),
    # ---------------- general purpose bombs ----------------
    dict(id="MK-82", name="Mk 82 LDGP / BLU-111 (500 lb)", cat="bomb", era="baseline", conf="medium",
         L=2.21, D=0.273, mass=241, profile=mk80(0.78), mount="BRU-33", lugs=14 * IN, stations=[2, 3, 5, 7, 8],
         kit="conical", kit_span=0.38, body=OD_THERMAL, nose=OD_THERMAL, finish="thermal",
         bands=[(0.10, 0.04, YELLOW), (0.13, 0.04, YELLOW)],
         note="Conical fin span estimated (1.4 D). Two on each BRU-33 VER. Thermal coating = Navy BLU-111."),
    dict(id="MK-82SE", name="Mk 82 Snakeye (Mk 15 fin)", cat="bomb", era="baseline", conf="medium",
         L=2.17, D=0.274, mass=250, profile=mk80(0.72), mount="BRU-33", lugs=14 * IN, stations=[],
         kit="snakeye", kit_span=0.40, body=OD_THERMAL, nose=OD_THERMAL, finish="thermal",
         bands=[(0.10, 0.04, YELLOW), (0.13, 0.04, YELLOW)], note="Drag plates shown closed (carriage)."),
    dict(id="MK-83", name="Mk 83 LDGP / BLU-110 (1,000 lb)", cat="bomb", era="baseline", conf="medium",
         L=3.01, D=0.356, mass=447, profile=mk80(0.80), mount="BRU-33", lugs=14 * IN, stations=[2, 3, 5, 7, 8],
         kit="conical", kit_span=0.50, body=OD_THERMAL, nose=OD_THERMAL, finish="thermal",
         bands=[(0.10, 0.05, YELLOW), (0.13, 0.05, YELLOW)], note="Conical fin span estimated."),
    dict(id="MK-84", name="Mk 84 LDGP / BLU-117 (2,000 lb)", cat="bomb", era="baseline", conf="medium",
         L=3.85, D=0.457, mass=894, profile=mk80(0.80), mount="BRU-32", lugs=30 * IN, stations=[2, 3, 7, 8],
         kit="conical", kit_span=0.64, body=OD_THERMAL, nose=OD_THERMAL, finish="thermal",
         bands=[(0.10, 0.06, YELLOW), (0.13, 0.06, YELLOW)],
         note="Too heavy for the BRU-33 (1,000 lb per unit); single carriage only."),
    dict(id="MK-20", name="Mk 20 Rockeye II / CBU-59 / CBU-78", cat="cluster", era="baseline", conf="high",
         L=2.34, D=0.337, mass=222, profile=can(0.14, 0.80, 0.55), mount="BRU-33", lugs=14 * IN,
         stations=[2, 3, 5, 7, 8],
         fins=[fins(1.95, 0.38, 2.10, 0.20, 0.437, roll=45, name="tail")], body=OD, nose=OD,
         bands=[(0.18, 0.05, YELLOW)],
         note="Mk 7 dispenser; fins closed (0.437 m) in carriage, 0.876 m open. CBU-59/78 share the shape."),
    dict(id="MK-77", name="Mk 77 fire bomb", cat="bomb", era="baseline", conf="est", L=3.30, D=0.53, mass=230,
         profile=can(0.25, 0.70, 0.15), mount="BRU-32", lugs=14 * IN, stations=[5], body=(150, 150, 146),
         nose=(150, 150, 146), bands=[(0.30, 0.04, (190, 70, 60))],
         note="Unfinned aluminium case; length and diameter estimated (no published figure found). "
              "Centreline per Desert Storm loads."),
    # ---------------- rockets ----------------
    dict(id="LAU-61", name="LAU-61 (19 x 2.75 in)", cat="rocket_pod", era="baseline", conf="medium",
         L=1.52, D=0.406, mass=70, profile=can(0.12, 0.97, 0.97), mount="BRU-33", lugs=14 * IN, stations=[],
         features=["tubes19"], body=OD_THERMAL, nose=(210, 210, 200), bands=[], finish="thermal",
         note="Thermally coated Navy pod; stations not documented for the A/B."),
    dict(id="LAU-68", name="LAU-68 (7 x 2.75 in)", cat="rocket_pod", era="baseline", conf="medium",
         L=1.56, D=0.249, mass=39, profile=can(0.12, 0.97, 0.97), mount="BRU-33", lugs=14 * IN, stations=[2, 8],
         features=["tubes7"], body=OD_THERMAL, nose=(210, 210, 200), bands=[], finish="thermal", note=""),
    dict(id="LAU-10", name="LAU-10 (4 x 5 in Zuni)", cat="rocket_pod", era="baseline", conf="est",
         L=2.50, D=0.40, mass=None, profile=can(0.12, 0.97, 0.97), mount="BRU-33", lugs=14 * IN, stations=[2, 8],
         features=["tubes4"], body=OD_THERMAL, nose=(210, 210, 200), bands=[], finish="thermal",
         note="Dimensions estimated (none published in the sources found)."),
    # ---------------- nuclear (shape only) ----------------
    dict(id="B61", name="B61", cat="nuclear", era="baseline", conf="medium", L=3.60, D=0.338, mass=341,
         profile=ogive(0.25, 0.86, 0.75), mount="BRU-32", lugs=14 * IN, stations=[],
         fins=[fins(3.10, 0.48, 3.30, 0.28, 0.57, roll=45, name="tail")], body=(170, 172, 170),
         nose=(170, 172, 170), bands=[], note="Fin span estimated. A/B carriage station not documented."),
    dict(id="B57", name="B57", cat="nuclear", era="baseline", conf="medium", L=3.00, D=0.375, mass=227,
         profile=ogive(0.22, 0.86, 0.75), mount="BRU-32", lugs=14 * IN, stations=[],
         fins=[fins(2.55, 0.42, 2.75, 0.25, 0.60, roll=45, name="tail")], body=(170, 172, 170),
         nose=(170, 172, 170), bands=[], note="Fin span estimated. Retired 1993."),
    # ---------------- practice ----------------
    dict(id="MK-76", name="Mk 76 practice bomb", cat="bomb", era="baseline", conf="medium", L=0.58, D=0.102,
         mass=11.3, profile=can(0.35, 0.55, 0.35), mount="PRACTICE", lugs=None, stations=[],
         fins=[fins(0.42, 0.14, 0.45, 0.11, 0.17, roll=45, name="tail")], body=BLUE, nose=BLUE, bands=[],
         note="Practice racks not documented for the A/B."),
    # ---------------- fuel and pods ----------------
    dict(id="TANK-330", name="330 US gal fuel tank (FPU-8/A)", cat="fuel_tank", era="baseline", conf="est",
         L=3.90, D=0.76, mass=195, profile=tank(0.27, 0.70), mount="BRU-32", lugs=30 * IN, stations=[3, 5, 7],
         body=GREY, nose=GREY, bands=[],
         note="No published drawing: diameter from the front-view drawing (~0.76 m), length sized for 330 gal. "
              "Empty mass 195 kg (NATOPS chart reading)."),
    dict(id="AAS-38", name="AN/AAS-38 NITE Hawk FLIR pod", cat="pod", era="baseline", conf="medium",
         L=1.83, D=0.33, mass=154, profile=can(0.02, 0.95, 0.80), mount="POD-4", lugs=None, stations=[4],
         features=["sensor_head"], body=GREY, nose=GREY, bands=[], note="Port fuselage station only."),
    dict(id="LITENING", name="AN/AAQ-28 LITENING (USMC)", cat="pod", era="A+", conf="medium",
         L=2.20, D=0.406, mass=208, profile=can(0.02, 0.95, 0.80), mount="POD-4", lugs=None, stations=[4, 5],
         features=["sensor_head"], body=GREY, nose=GREY, bands=[], note="USMC legacy Hornets from 2005-06."),
    dict(id="ASQ-173", name="AN/ASQ-173 LST/SCAM pod", cat="pod", era="baseline", conf="est",
         L=2.20, D=0.22, mass=None, profile=can(0.08, 0.95, 0.85), mount="POD-6", lugs=None, stations=[6],
         features=["window"], body=GREY, nose=GLASS, bands=[],
         note="Starboard fuselage station; dimensions estimated (none published in the sources found)."),
    dict(id="AWW-13", name="AN/AWW-13 data-link pod", cat="pod", era="baseline", conf="est",
         L=3.40, D=0.38, mass=None, profile=can(0.15, 0.90, 0.6), mount="BRU-32", lugs=14 * IN,
         stations=[2, 3, 5, 7, 8], features=["datalink"], body=GREY, nose=(200, 200, 194), bands=[],
         note="Walleye/SLAM data link (AWW-9 similar); dimensions estimated."),
    dict(id="ACMI", name="ACMI / TACTS pod", cat="pod", era="baseline", conf="est", L=2.85, D=0.127, mass=None,
         profile=dome(0.05), mount="LAU-7", stations=[1, 9],
         fins=[fins(0.30, 0.28, 0.46, 0.06, 0.56, roll=45, name="canard"),
               fins(2.42, 0.40, 2.62, 0.20, 0.63, roll=45, name="wing")],
         body=(200, 200, 196), nose=(60, 60, 60), bands=[], note="Sidewinder-shaped training pod; dims estimated."),
]

# --- suspension equipment (modelled as separate parts) ---------------------------------
EQUIPMENT = [
    dict(id="SUU-63", name="SUU-63 wing pylon (with BRU-32)", cat="pylon", conf="est", L=2.40, H=0.36, W=0.11,
         stations=[2, 3, 7, 8], body=TPS,
         note="No published dimensions; length and depth from the drawings (nose about 0.35 m ahead of the "
              "wing leading edge in the F/A-18B top view)."),
    dict(id="SUU-62", name="SUU-62 centreline pylon (with BRU-32)", cat="pylon", conf="est", L=1.90, H=0.22,
         W=0.11, stations=[5], body=TPS, note="Dimensions estimated."),
    dict(id="BRU-33", name="BRU-33 VER / CVER (twin)", cat="rack", conf="est", L=1.10, H=0.16, W=0.50,
         stations=[2, 3, 5, 7, 8], body=DGREY,
         note="Two ejector units, canted 5 deg outboard on the CVER; 1,000 lb per unit. Dimensions estimated."),
    dict(id="LAU-115", name="LAU-115 wing missile launcher", cat="launcher", conf="medium", L=2.083, H=0.17,
         W=0.12, stations=[2, 8], body=TPS, note="Length published (2.083 m); section estimated."),
    dict(id="LAU-7", name="LAU-7 Sidewinder rail (pylon side mount)", cat="launcher", conf="est", L=1.90,
         H=0.09, W=0.09, stations=[2, 8], body=TPS, note="Side rails on the LAU-115 for twin AIM-9."),
    dict(id="LAU-117", name="LAU-117 Maverick launcher", cat="launcher", conf="medium", L=2.388, H=0.279,
         W=0.279, stations=[2, 3, 7, 8], body=TPS, note="11 x 11 in section (USAF (V)3/A)."),
    dict(id="LAU-118", name="LAU-118 HARM launcher", cat="launcher", conf="medium", L=2.007, H=0.203,
         W=0.296, stations=[2, 3, 7, 8], body=TPS, note="11.65 x 8 in section (USAF (V)4/A)."),
]

# --- station geometry (design coordinates: x aft of nose tip, y starboard, z up) ------------
# Spanwise distances: NATOPS Fig. 4-4.  Longitudinal positions: estimated from the drawings.
STATION_Y = {1: -5.94, 2: -3.41, 3: -2.23, 4: -1.13, 5: 0.0, 6: 1.13, 7: 2.23, 8: 3.41, 9: 5.94}
CARRIAGE = {
    # mount -> how it attaches; stations it is allowed on (AO 3&2 Fig. 14-21)
    "LAU-7": dict(stations=[1, 9], via=None),
    "LAU-115+LAU-7": dict(stations=[2, 8], via=["SUU-63", "LAU-115", "LAU-7"]),
    "LAU-115": dict(stations=[2, 8], via=["SUU-63", "LAU-115"]),
    "LAU-116": dict(stations=[4, 6], via=None),
    "LAU-117": dict(stations=[2, 3, 7, 8], via=["SUU-63", "LAU-117"]),
    "LAU-118": dict(stations=[2, 3, 7, 8], via=["SUU-63", "LAU-118"]),
    "BRU-32": dict(stations=[2, 3, 5, 7, 8], via=["SUU-63|SUU-62"]),
    "BRU-33": dict(stations=[2, 3, 5, 7, 8], via=["SUU-63|SUU-62", "BRU-33"]),
    "POD-4": dict(stations=[4], via=None),
    "POD-6": dict(stations=[6], via=None),
    "TER": dict(stations=[], via=None),
    "PRACTICE": dict(stations=[], via=None),
}

# typical loads actually flown by A/B (and Desert Storm Hornets), stations 1..9
LOADOUTS = {
    "CAP": {1: "AIM-9L", 9: "AIM-9L", 4: "AIM-7M", 6: "AIM-7M", 3: "TANK-330", 5: "TANK-330", 7: "TANK-330"},
    "Fleet_air_defence": {1: "AIM-9L", 9: "AIM-9L", 2: "AIM-7M", 8: "AIM-7M", 4: "AIM-7M", 6: "AIM-7M",
                          3: "TANK-330", 5: "TANK-330", 7: "TANK-330"},
    "Strike_Mk83": {1: "AIM-9L", 9: "AIM-9L", 4: "AAS-38", 6: "ASQ-173", 3: "TANK-330", 7: "TANK-330",
                    2: ("MK-83", 2), 8: ("MK-83", 2), 5: "MK-83"},
    "Heavy_strike_Mk84": {1: "AIM-9L", 9: "AIM-9L", 4: "AIM-7M", 6: "AIM-7M", 2: "MK-84", 3: "MK-84",
                          7: "MK-84", 8: "MK-84", 5: "TANK-330"},
    "SEAD_HARM": {1: "AIM-9L", 9: "AIM-9L", 2: "AGM-88", 8: "AGM-88", 4: "AIM-7M", 6: "AIM-7M",
                  3: "TANK-330", 5: "TANK-330", 7: "TANK-330"},
    "Walleye_1991": {1: "AIM-9L", 9: "AIM-9L", 2: "AGM-62", 8: "AGM-62", 3: "TANK-330", 7: "TANK-330",
                     4: "AAS-38", 5: "AWW-13"},
    "Rockeye_CAS": {1: "AIM-9L", 9: "AIM-9L", 2: ("MK-20", 2), 8: ("MK-20", 2), 3: ("MK-20", 2),
                    7: ("MK-20", 2), 4: "AIM-7M", 6: "AIM-7M", 5: "TANK-330"},
}


def all_items():
    return STORES + EQUIPMENT


def by_id(i):
    for s in all_items():
        if s["id"] == i:
            return s
    raise KeyError(i)


# --- texture atlas allocation --------------------------------------------------------
ATLAS = 4096
PPM = 260               # pixels per metre on the store skins


def skin_size(s):
    """(width, height) in px of an item's skin: body wrap + a strip for fins."""
    if s in EQUIPMENT:
        w = int(2 * (s["H"] + s["W"]) * PPM) + 8
        return max(w, 64), int(s["L"] * PPM) + 8
    if s.get("box"):
        bw, bh = s["box"]
        circ = 2 * (bw + bh)
    else:
        circ = math.pi * s["D"]
    w = max(int(circ * PPM) + 8, 48)
    h = int(s["L"] * PPM) + 8
    fin_w = 0
    for f in s.get("fins", []) + ([dict(span=s.get("kit_span", 0.3), c0=0.4)] if s.get("kit") else []):
        fin_w = max(fin_w, int(max(f["c0"], 0.2) * PPM) + 8)
    if s.get("features") and any(k in s["features"] for k in ("jsow_wings", "tald_wings")):
        fin_w = max(fin_w, int(0.5 * PPM))
    return w + fin_w, h


def pack():
    """Shelf-pack every item's skin into one atlas.  Returns {id: (x0, y0, x1, y1, body_w)}."""
    items = sorted(all_items(), key=lambda s: -skin_size(s)[1])
    x = y = 0
    shelf = 0
    out = {}
    for s in items:
        w, h = skin_size(s)
        if x + w > ATLAS:
            x = 0
            y += shelf
            shelf = 0
        if y + h > ATLAS:
            raise RuntimeError("store atlas overflow at " + s["id"])
        if s in EQUIPMENT:
            body_w = w
        else:
            body_w = (int(2 * sum(s["box"]) * PPM) if s.get("box") else int(math.pi * s["D"] * PPM)) + 8
            body_w = max(body_w, 48)
        out[s["id"]] = (x, y, x + w, y + h, body_w)
        x += w
        shelf = max(shelf, h)
    return out
