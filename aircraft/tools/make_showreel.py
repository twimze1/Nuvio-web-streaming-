"""Label the frames from render_showreel.py and encode them as an MP4.

    python3 make_showreel.py FRAMES_DIR OUT.mp4

Needs Pillow and ffmpeg (libx264) on the PATH.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

src, out = sys.argv[1], sys.argv[2]
info = json.load(open(os.path.join(src, "shots.json")))
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
big = ImageFont.truetype(BOLD if os.path.exists(BOLD) else FONT, 30)
small = ImageFont.truetype(FONT, 21)
tag = ImageFont.truetype(FONT, 18)

tmp = tempfile.mkdtemp(prefix="reel_")
n = 0
for shot in info["shots"]:
    for k, u in enumerate(shot["frames"]):
        im = Image.open(os.path.join(src, "u%05d.png" % u)).convert("RGB")
        ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        W, H = im.size
        d.rectangle((0, H - 92, W, H), fill=(12, 16, 22, 150))
        d.text((28, H - 84), shot["label"].replace("_", " "), font=big, fill=(255, 255, 255, 255))
        d.text((28, H - 42), shot["caption"], font=small, fill=(220, 226, 235, 255))
        d.text((W - 210, 18), "F/A-18A Hornet", font=tag, fill=(255, 255, 255, 220))
        im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
        im.save(os.path.join(tmp, "f%05d.png" % n))
        n += 1
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(info["fps"]), "-i",
                os.path.join(tmp, "f%05d.png"), "-c:v", "libx264", "-preset", "slow", "-crf", "20",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], check=True)
shutil.rmtree(tmp)
print("wrote %s: %d frames, %.1f s" % (out, n, n / info["fps"]))
