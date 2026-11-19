"""Turn the low-resolution line art from prepare_reference_lines.py into crisp,
high-resolution panel-line and rivet maps for the exterior bake.

    python tools/vectorize_reference_lines.py REFS.json OUT_DIR [PX_PER_M]

The general-arrangement sheet resolves about 17 mm per pixel, so drawn
straight onto the skin its lines are 2-4 cm bands with stair-stepped edges.
This tool thins each view's ink to one-pixel centre lines, traces them into
polylines, simplifies them (Douglas-Peucker, 1.6 px, which straightens the sheet's one-pixel steps) and redraws them at
PX_PER_M (default 500, i.e. 2 mm per pixel):

  red   panel seams, 3 mm wide, anti-aliased;
  green flush rivet heads, 5.6 mm across, in a row 12 mm either side of every
        seam at 25 mm pitch (AN426 1/8 in rivets, typical fighter spacing),
        stopping short of line ends and junctions.

Writes OUT_DIR/ref_<view>_hd.png and OUT_DIR/refs_hd.json, which has the
same layout as refs.json (path, px per metre, nose-tip registration) so the
bake reads either.  Needs numpy, Pillow and scikit-image.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from skimage.morphology import skeletonize

SEAM_MM = 3.0
RIVET_D_MM = 5.6
RIVET_PITCH_MM = 25.0
RIVET_OFFSET_MM = 12.0
END_GAP_MM = 18.0
SUPER = 2                       # draw at 2x and downsample for anti-aliasing


def trace(skel):
    """Skeleton pixels -> list of polylines [(x, y), ...] between end points and junctions."""
    ys, xs = np.nonzero(skel)
    on = set(zip(xs.tolist(), ys.tolist()))
    nbr = {}
    for p in on:
        x, y = p
        nbr[p] = [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                  if (dx or dy) and (x + dx, y + dy) in on]
    nodes = {p for p, n in nbr.items() if len(n) != 2}
    seen = set()
    paths = []

    def walk(a, b):
        path = [a, b]
        prev, cur = a, b
        while cur not in nodes:
            nxt = [q for q in nbr[cur] if q != prev and (cur, q) not in seen]
            if not nxt:
                break
            seen.add((cur, nxt[0]))
            seen.add((nxt[0], cur))
            prev, cur = cur, nxt[0]
            path.append(cur)
            if cur == a:
                break
        return path

    for a in nodes:
        for b in nbr[a]:
            if (a, b) in seen:
                continue
            seen.add((a, b))
            seen.add((b, a))
            paths.append(walk(a, b))
    # closed loops with no node
    for p in on:
        if p in nodes or all((p, q) in seen for q in nbr[p]):
            continue
        q = nbr[p][0]
        seen.add((p, q))
        seen.add((q, p))
        paths.append(walk(p, q))
    return [pth for pth in paths if len(pth) >= 3]


def simplify(pts, eps):
    """Douglas-Peucker."""
    if len(pts) < 3:
        return pts
    a, b = np.array(pts[0], float), np.array(pts[-1], float)
    ab = b - a
    L = np.hypot(*ab)
    best, idx = -1.0, 0
    for i in range(1, len(pts) - 1):
        p = np.array(pts[i], float)
        d = abs(ab[0] * (p - a)[1] - ab[1] * (p - a)[0]) / L if L > 1e-9 else np.hypot(*(p - a))
        if d > best:
            best, idx = d, i
    if best <= eps:
        return [pts[0], pts[-1]]
    return simplify(pts[:idx + 1], eps)[:-1] + simplify(pts[idx:], eps)


def main(refs_path, out, ppm=500.0):
    refs = json.load(open(refs_path))
    os.makedirs(out, exist_ok=True)
    result = {}
    for view, info in refs.items():
        if not isinstance(info, dict) or "path" not in info:
            continue
        src = np.array(Image.open(info["path"]).convert("L"))
        ink = src < 128
        skel = skeletonize(ink)
        paths = [simplify(p, 1.6) for p in trace(skel)]
        s0, ox0, oy0 = info["s"], info["ox"], info["oy"]
        ys, xs = np.nonzero(ink)
        pad = 4
        x0, x1 = max(0, xs.min() - pad), min(src.shape[1], xs.max() + pad)
        y0, y1 = max(0, ys.min() - pad), min(src.shape[0], ys.max() + pad)
        k = ppm / s0                                  # source px -> output px
        W, H = int(round((x1 - x0) * k)), int(round((y1 - y0) * k))
        ks = k * SUPER
        mm = ppm * SUPER / 1000.0                     # supersampled px per mm
        seams = Image.new("L", (W * SUPER, H * SUPER), 0)
        rivets = Image.new("L", (W * SUPER, H * SUPER), 0)
        ds, dr = ImageDraw.Draw(seams), ImageDraw.Draw(rivets)
        r_px = RIVET_D_MM * mm / 2
        n_rivets = 0
        for pth in paths:
            P = [((x - x0 + 0.5) * ks, (y - y0 + 0.5) * ks) for x, y in pth]
            ds.line(P, fill=255, width=max(1, int(round(SEAM_MM * mm))), joint="curve")
            # rivet rows along the polyline, either side, clear of its ends
            seg = [(np.array(P[i], float), np.array(P[i + 1], float)) for i in range(len(P) - 1)]
            total = sum(np.hypot(*(b - a)) for a, b in seg)
            gap, pitch, off = END_GAP_MM * mm, RIVET_PITCH_MM * mm, RIVET_OFFSET_MM * mm
            if total < 2 * gap + pitch:
                continue
            t = gap
            acc = 0.0
            for a, b in seg:
                L = np.hypot(*(b - a))
                if L < 1e-6:
                    continue
                d = (b - a) / L
                n = np.array([-d[1], d[0]])
                while t <= acc + L and t <= total - gap:
                    c = a + d * (t - acc)
                    for sgn in (1, -1):
                        q = c + n * off * sgn
                        dr.ellipse((q[0] - r_px, q[1] - r_px, q[0] + r_px, q[1] + r_px), fill=255)
                        n_rivets += 1
                    t += pitch
                acc += L
        seams = seams.resize((W, H), Image.LANCZOS)
        rivets = rivets.resize((W, H), Image.LANCZOS)
        rgb = Image.merge("RGB", (seams, rivets, Image.new("L", (W, H), 0)))
        path = os.path.join(out, "ref_%s_hd.png" % view)
        rgb.save(path, optimize=True)
        result[view] = {"path": path, "s": ppm, "ox": (ox0 - x0) * k, "oy": (oy0 - y0) * k, "hd": True}
        print("%s: %d polylines, %d rivets, %d x %d px at %.0f px/m" % (view, len(paths), n_rivets, W, H, ppm))
    with open(os.path.join(out, "refs_hd.json"), "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 500.0)
