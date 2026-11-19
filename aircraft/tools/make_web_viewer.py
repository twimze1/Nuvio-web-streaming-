"""Build the browser viewer in ../web from the animated GLBs.

    python3 tools/make_web_viewer.py            (run from the aircraft folder)

For each FA-18?_Hornet_animated.glb it writes web/FA-18?.json: a glTF (JSON,
with its small geometry and animation buffer embedded as base64) holding the
same nodes, meshes, materials, cameras and animation clips.  The textures are
moved out to web/tex/ (shared between the variants where they are the same
image) and scaled to at most MAX_SIZE pixels, so the page loads about a
quarter of the data.  (JSON rather than .glb because some static hosts,
including claude.ai artifacts, only serve web file types.)  It then writes web/index.html from tools/web_viewer.html.
Serve the folder over HTTP to view it, e.g.  python3 -m http.server -d web
"""
import base64
import io
import json
import os
import struct

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEB = os.path.join(ROOT, "web")
TEX = os.path.join(WEB, "tex")
MAX_SIZE = 2048


def read_glb(path):
    with open(path, "rb") as f:
        magic, version, length = struct.unpack("<III", f.read(12))
        assert magic == 0x46546C67, "not a GLB"
        n, kind = struct.unpack("<II", f.read(8))
        doc = json.loads(f.read(n))
        n, kind = struct.unpack("<II", f.read(8))
        binary = f.read(n)
    return doc, binary


def write_glb(path, doc, binary):
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    binary += b"\0" * (-len(binary) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binary)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(binary), 0x004E4942) + binary)


def externalise(src, dst):
    doc, binary = read_glb(src)
    views = doc["bufferViews"]
    image_views = set()
    for img in doc.get("images", []):
        if "bufferView" not in img:
            continue
        v = views[img["bufferView"]]
        data = binary[v.get("byteOffset", 0): v.get("byteOffset", 0) + v["byteLength"]]
        im = Image.open(io.BytesIO(data))
        im.load()
        if max(im.size) > MAX_SIZE:
            s = MAX_SIZE / max(im.size)
            im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        keep_png = img.get("mimeType") == "image/png" and (im.mode in ("RGBA", "LA") or max(im.size) <= 1024)
        name = img.get("name") or "image%d" % len(image_views)
        fname = name + (".png" if keep_png else ".jpg")
        out = os.path.join(TEX, fname)
        if keep_png:
            im.save(out, optimize=True)
        else:
            im.convert("RGB").save(out, quality=86, optimize=True, progressive=True)
        image_views.add(img.pop("bufferView"))
        img.pop("mimeType", None)
        img["uri"] = "tex/" + fname
    # rebuild the binary chunk without the image data
    remap, keep, chunks, offset = {}, [], [], 0
    for i, v in enumerate(views):
        if i in image_views:
            continue
        data = binary[v.get("byteOffset", 0): v.get("byteOffset", 0) + v["byteLength"]]
        pad = -offset % 4
        chunks.append(b"\0" * pad)
        offset += pad
        nv = dict(v)
        nv["byteOffset"] = offset
        chunks.append(data)
        offset += len(data)
        remap[i] = len(keep)
        keep.append(nv)
    doc["bufferViews"] = keep
    for acc in doc.get("accessors", []):
        if "bufferView" in acc:
            acc["bufferView"] = remap[acc["bufferView"]]
        sp = acc.get("sparse")
        if sp:
            sp["indices"]["bufferView"] = remap[sp["indices"]["bufferView"]]
            sp["values"]["bufferView"] = remap[sp["values"]["bufferView"]]
    newbin = b"".join(chunks)
    doc["buffers"] = [{"byteLength": len(newbin),
                       "uri": "data:application/octet-stream;base64," + base64.b64encode(newbin).decode()}]
    with open(dst, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
    return len(newbin), len(doc.get("animations", []))


def main():
    os.makedirs(TEX, exist_ok=True)
    for v in "AB":
        src = os.path.join(ROOT, "FA-18%s_Hornet_animated.glb" % v)
        dst = os.path.join(WEB, "FA-18%s.json" % v)
        size, clips = externalise(src, dst)
        print("%s: %.1f MB of geometry and animation, %d clips" % (os.path.basename(dst), size / 1e6, clips))
    page = open(os.path.join(HERE, "web_viewer.html")).read()
    with open(os.path.join(WEB, "index.html"), "w") as f:
        f.write('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                '</head>\n<body>\n' + page + '\n</body>\n</html>\n')
    total = sum(os.path.getsize(os.path.join(TEX, f)) for f in os.listdir(TEX))
    print("textures: %d files, %.1f MB" % (len(os.listdir(TEX)), total / 1e6))


if __name__ == "__main__":
    main()
