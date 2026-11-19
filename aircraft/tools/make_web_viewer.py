"""Build the browser viewer from the animated GLBs as ONE self-contained page.

    python3 tools/make_web_viewer.py [--fragment PATH] [--src DIR]     (run from the aircraft folder)

For each FA-18?_Hornet_animated.glb the page carries a gzipped GLB with the
same nodes, meshes, materials, cameras and animation clips, and every
texture once (shared between the variants where they are the same image),
scaled to web sizes.  All of it is embedded as base64, so the page needs no
other files: it works from any host, including ones that only serve the page
itself, and opens straight from disk.

Writes web/index.html, the page ready to open or serve, from the template
tools/web_viewer.html.  --fragment PATH also writes the same page without the
<html>/<head> shell, for hosts that add their own (claude.ai artifacts).
--src DIR reads the animated GLBs from DIR instead of the aircraft folder.
"""
import base64
import gzip
import io
import json
import os
import struct
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEB = os.path.join(ROOT, "web")
# longest side in pixels by texture family; the page must stay well under 16 MB
SIZES = {"ext_": 1536, "stores_": 1024, "cockpit_": 2048, "display_": 1024}


def read_glb(path):
    with open(path, "rb") as f:
        magic, version, length = struct.unpack("<III", f.read(12))
        assert magic == 0x46546C67, "not a GLB"
        n, kind = struct.unpack("<II", f.read(8))
        doc = json.loads(f.read(n))
        n, kind = struct.unpack("<II", f.read(8))
        binary = f.read(n)
    return doc, binary


def glb_bytes(doc, binary):
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    binary += b"\0" * (-len(binary) % 4)
    out = io.BytesIO()
    out.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binary)))
    out.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
    out.write(struct.pack("<II", len(binary), 0x004E4942) + binary)
    return out.getvalue()


def web_image(name, data, mime):
    im = Image.open(io.BytesIO(data))
    im.load()
    limit = next((v for k, v in SIZES.items() if name.startswith(k)), 1024)
    if max(im.size) > limit:
        s = limit / max(im.size)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    out = io.BytesIO()
    if mime == "image/png" and (im.mode in ("RGBA", "LA") or name.startswith("display_")):
        im.save(out, "PNG", optimize=True)
        return name + ".png", out.getvalue()
    im.convert("RGB").save(out, "JPEG", quality=84, optimize=True, progressive=True)
    return name + ".jpg", out.getvalue()


def split(src, textures):
    """GLB with its images moved out (uri tex/<file>) and the image files added to `textures`."""
    doc, binary = read_glb(src)
    views = doc["bufferViews"]
    image_views = set()
    for k, img in enumerate(doc.get("images", [])):
        if "bufferView" not in img:
            continue
        v = views[img["bufferView"]]
        data = binary[v.get("byteOffset", 0): v.get("byteOffset", 0) + v["byteLength"]]
        fname, payload = web_image(img.get("name") or "image%d" % k, data, img.get("mimeType"))
        textures.setdefault(fname, payload)
        image_views.add(img.pop("bufferView"))
        img.pop("mimeType", None)
        img["uri"] = "tex/" + fname
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
    doc["buffers"] = [{"byteLength": len(newbin)}]
    return glb_bytes(doc, newbin), len(doc.get("animations", []))


def block(attrs, payload):
    return '<script type="text/plain" %s>%s</script>\n' % (attrs, base64.b64encode(payload).decode())


def main():
    os.makedirs(WEB, exist_ok=True)
    textures, blocks = {}, []
    for v in "AB":
        src = sys.argv[sys.argv.index("--src") + 1] if "--src" in sys.argv else ROOT
        glb, clips = split(os.path.join(src, "FA-18%s_Hornet_animated.glb" % v), textures)
        packed = gzip.compress(glb, 9)
        blocks.append(block('id="glb-%s"' % v, packed))
        print("FA-18%s: model %.1f MB, gzipped %.1f MB, %d clips" % (v, len(glb) / 1e6, len(packed) / 1e6, clips))
    for name in sorted(textures):
        blocks.append(block('data-tex="%s"' % name, textures[name]))
    print("textures: %d files, %.1f MB" % (len(textures), sum(map(len, textures.values())) / 1e6))
    template = open(os.path.join(HERE, "web_viewer.html")).read()
    assert "<!--EMBEDDED-DATA-->" in template
    page = template.replace("<!--EMBEDDED-DATA-->", "".join(blocks))
    if "--fragment" in sys.argv:
        with open(sys.argv[sys.argv.index("--fragment") + 1], "w") as f:
            f.write(page)
    with open(os.path.join(WEB, "index.html"), "w") as f:
        f.write('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                '</head>\n<body>\n' + page + '\n</body>\n</html>\n')
    print("page: %.1f MB" % (os.path.getsize(os.path.join(WEB, "index.html")) / 1e6))


if __name__ == "__main__":
    main()
