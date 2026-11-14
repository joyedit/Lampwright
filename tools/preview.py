"""Renders assets/lampwright/shapes/lampbelt.json to a PNG so geometry can be checked
without launching the game.

Orthographic, three views. Every element in this shape is axis-aligned, so each face
projects to a plain rectangle and a painter's-algorithm fill is exact rather than an
approximation. Faces are sampled from the real texture through their uv rect, with the
same alpha cutout the game applies via renderAlphaTest - which matters here because the
temporal gear texture is a gear silhouette on transparency, so a flat fill would show a
solid square and hide whether the gears read as gears. Faces carrying "glow" are
brightened toward white.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pnglib

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHAPE = os.path.join(HERE, "assets/lampwright/shapes/lampbelt.json")
OUT = os.path.join(HERE, "tools/preview.png")
VANILLA_TEX = "/home/deftones/Apps/vintagestory/assets/survival/textures/"

PPU = 34            # pixels per model unit
PAD = 16
BG = (28, 28, 32)
LABEL = (90, 90, 100)

shape = json.load(open(SHAPE))

# Textures are loaded whole so faces can be sampled rather than averaged. A mod-domain
# texture resolves against this repo's assets, anything else against the vanilla folder.
textures = {}
for name, path in shape["textures"].items():
    domain, rel = path.split(":", 1)
    full = (os.path.join(HERE, "assets/lampwright/textures", rel + ".png")
            if domain == "lampwright" else VANILLA_TEX + rel + ".png")
    textures[name] = pnglib.read_png(full) if os.path.exists(full) else None
    if textures[name] is None:
        print(f"  MISSING texture {path} -> {full}")

# uv numbers are in the coordinate space `textureSizes` declares for that texture, not
# in texels - the image is stretched onto it. The vanilla band declares 8x8 for a 16x16
# png, so reading its uv as texels samples the wrong half.
TEX_SIZES = {name: tuple(s) for name, s in shape.get("textureSizes", {}).items()}
DEFAULT_SIZE = (shape.get("textureWidth", 16), shape.get("textureHeight", 16))


def flatten(elements, off=(0.0, 0.0, 0.0), out=None):
    """VS child elements are positioned relative to the parent's `from` corner."""
    if out is None:
        out = []
    for e in elements:
        f = [e["from"][i] + off[i] for i in range(3)]
        t = [e["to"][i] + off[i] for i in range(3)]
        for key in ("rotationX", "rotationY", "rotationZ"):
            if e.get(key):
                print(f"  note: {e['name']} has {key}={e[key]}, preview ignores rotation")
        out.append((e["name"], f, t, e.get("faces", {})))
        if e.get("children"):
            flatten(e["children"], tuple(f), out)
    return out


boxes = flatten(shape["elements"])
xs = [v for _, f, t, _ in boxes for v in (f[0], t[0])]
ys = [v for _, f, t, _ in boxes for v in (f[1], t[1])]
zs = [v for _, f, t, _ in boxes for v in (f[2], t[2])]
print(f"bounds x {min(xs):.2f}..{max(xs):.2f}  y {min(ys):.2f}..{max(ys):.2f}  z {min(zs):.2f}..{max(zs):.2f}")

# view -> (horizontal axis, vertical axis, depth axis, flip-v, face drawn, label)
VIEWS = [
    ("front (-Z)", 0, 1, 2, True, "north"),
    ("side  (+X)", 2, 1, 0, True, "east"),
    ("top   (-Y)", 0, 2, 1, False, "up"),
]

panels = []
for label, ha, va, da, flipv, facename in VIEWS:
    lo = [min(xs), min(ys), min(zs)][ha], [min(xs), min(ys), min(zs)][va]
    hi = [max(xs), max(ys), max(zs)][ha], [max(xs), max(ys), max(zs)][va]
    w = int((hi[0] - lo[0]) * PPU) + 2 * PAD
    h = int((hi[1] - lo[1]) * PPU) + 2 * PAD
    buf = bytearray()
    for _ in range(w * h):
        buf += bytes(BG + (255,))

    # Nearest last. For -Z and -Y views the viewer is at the low end of the depth axis.
    near_is_low = facename in ("north", "up")
    order = sorted(boxes, key=lambda b: b[1][da], reverse=near_is_low)

    for name, f, t, faces in order:
        face = faces.get(facename) or next(iter(faces.values()), None)
        if face is None:
            continue
        code = face["texture"].lstrip("#")
        tex = textures.get(code)
        uv = face.get("uv", [0, 0, 16, 16])
        usw, ush = TEX_SIZES.get(code, DEFAULT_SIZE)
        glow = face.get("glow", 0)
        k = glow / 255 * 0.5
        x0 = int((f[ha] - lo[0]) * PPU) + PAD
        x1 = int((t[ha] - lo[0]) * PPU) + PAD
        y0 = int((f[va] - lo[1]) * PPU) + PAD
        y1 = int((t[va] - lo[1]) * PPU) + PAD
        if flipv:
            y0, y1 = h - y1 - PAD + PAD, h - y0 - PAD + PAD
        ylo, yhi = max(0, min(y0, y1)), min(h, max(y0, y1))
        xlo, xhi = max(0, min(x0, x1)), min(w, max(x0, x1))
        if tex is None or yhi <= ylo or xhi <= xlo:
            continue
        tw, th, px = tex
        u0, v0, u1, v1 = uv
        for y in range(ylo, yhi):
            fy = (y - ylo) / max(1, yhi - ylo)
            ty = min(th - 1, max(0, int((v0 + (v1 - v0) * fy) / ush * th)))
            for x in range(xlo, xhi):
                fx = (x - xlo) / max(1, xhi - xlo)
                tx = min(tw - 1, max(0, int((u0 + (u1 - u0) * fx) / usw * tw)))
                n = (ty * tw + tx) * 4
                r, g, b, a = px[n], px[n + 1], px[n + 2], px[n + 3]
                if a < 64:        # renderAlphaTest: the game discards these too
                    continue
                if k:
                    r, g, b = (int(c + (255 - c) * k) for c in (r, g, b))
                m = (y * w + x) * 4
                buf[m:m + 4] = bytes((r, g, b, 255))
    panels.append((label, w, h, buf))
    print(f"  {label}: {w}x{h}")

TW = sum(p[1] for p in panels) + PAD * (len(panels) + 1)
TH = max(p[2] for p in panels) + PAD * 2
out = bytearray()
for _ in range(TW * TH):
    out += bytes(BG + (255,))

x_at = PAD
for label, w, h, buf in panels:
    for y in range(h):
        dst = ((y + PAD) * TW + x_at) * 4
        out[dst:dst + w * 4] = buf[y * w * 4:(y + 1) * w * 4]
    for i in range(w):                       # a rule under each panel as a divider
        n = ((PAD + h + 3) * TW + x_at + i) * 4
        out[n:n + 4] = bytes(LABEL + (255,))
    x_at += w + PAD

pnglib.write_png(OUT, TW, TH, out)
print("wrote", OUT, f"{TW}x{TH}")
print("panels left to right:", ", ".join(p[0] for p in panels))
