"""
Turn the F/A-18B general-arrangement sheet into clean line art for the
panel-line projection used by the exterior bake.

    python tools/prepare_reference_lines.py SHEET.gif OUT_DIR

Writes OUT_DIR/ref_top.png, OUT_DIR/ref_side.png and OUT_DIR/refs.json
(scale and nose-tip registration, same numbers tools/overlay_reference.py
uses for that sheet).  Parts of the sheet that would project onto the
airframe as false lines are erased: the front view's wing tip overlapping
the top view, the wing-tip missile drawn across the fin in the side view,
and the missiles drawn under the fuselage in the side view.

The sheet itself is not stored in this repository; only the baked textures
derived from it are.
"""
import json
import os
import sys

from PIL import Image, ImageDraw

S = 57.1                      # px per metre on the F/A-18B sheet (1200 x 1015 px)
TOP_NOSE = (182.5, 453.0)     # nose tip, top view
SIDE_NOSE = (233.0, 907.0)    # nose tip, side view (z = 0 at the nose tip)


def main(sheet, out):
    os.makedirs(out, exist_ok=True)
    im = Image.open(sheet).convert("L")
    # lines: dark ink -> keep, everything else white
    ink = im.point(lambda v: 0 if v < 150 else 255)

    top = ink.copy()
    d = ImageDraw.Draw(top)
    # the front view sits top-left; keep only the starboard wing behind its leading edge
    for y in range(0, 336):
        x_le = 689 + (317 - y) * (61 / 217)
        d.line((0, y, x_le - 6, y), fill=255)
    d.rectangle((0, 700, 1200, 1015), fill=255)        # side view below
    d.rectangle((0, 520, 660, 700), fill=255)          # title text
    top.save(os.path.join(out, "ref_top.png"))

    side = ink.copy()
    d = ImageDraw.Draw(side)
    d.rectangle((0, 0, 1200, 712), fill=255)           # everything above the side view
    d.rectangle((840, 712, 1192, 812), fill=255)       # top view's wing tip and missile over the fin
    d.rectangle((728, 893, 1012, 1015), fill=255)      # AIM-9 / AIM-7 drawn under the fuselage
    d.rectangle((0, 960, 1200, 1015), fill=255)        # landing gear and ground line
    side.save(os.path.join(out, "ref_side.png"))

    refs = {
        "top": {"path": os.path.abspath(os.path.join(out, "ref_top.png")), "s": S,
                "ox": TOP_NOSE[0], "oy": TOP_NOSE[1]},
        "side": {"path": os.path.abspath(os.path.join(out, "ref_side.png")), "s": S,
                 "ox": SIDE_NOSE[0], "oy": SIDE_NOSE[1]},
    }
    with open(os.path.join(out, "refs.json"), "w") as f:
        json.dump(refs, f, indent=2)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
