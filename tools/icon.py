"""Renders the inventory icon the way the client builds it, to tools/icon.png.

preview.py answers "is the geometry right". This answers "what does the slot show",
and it needs the extra machinery because the icon for a *wearable* is not the item's
shape on its own. Three things decide the picture, all read out of the 1.22.7
assemblies rather than guessed:

  * The mesh is the whole seraph. CollectibleBehaviorWearableAttachment.OnBeforeRender
    (VSSurvivalMod; CollectibleBehaviorWearable extends it) throws away the plain item
    mesh and calls genFullBodyMesh: it clones the player entity's shape, step-parents
    the clothing shape onto it by stepParentName, and tesselates that. The body is
    invisible only because the itemtype maps the "seraph" texture to block/transparent
    and renderAlphaTest cuts it. So the belt sits at the LowerTorso bone - y=15 in
    shape units - not near the origin, which is why the guiTransform's origin is
    y=1.1 and not y=0.

  * The framing is fixed and the slot clips. InventoryItemRenderer.RenderItemstackToGui
    builds the matrix as, applied to a vertex: translate by -origin, rotate Z then Y
    then X, scale by size*transform.scale, then translate to the slot centre. An
    inventory slot is 48 unscaled px and passes size = 25.6, and it pushes a scissor at
    the slot bounds, so a vertex shows only while scale * R*(v - origin) stays inside
    +-24/25.6 = +-0.9375. That is HALF_SLOT, drawn as the box in each panel.

  * textureSizes is a uv coordinate space, not the png's pixel size. The vanilla belt
    declares 8x8 for a 16x16 png, so its uvs cover the whole image at half the numbers.
    Sampling uv as texels lands on the wrong stripe.

GUI space has y pointing down, which is what the 174-degree X rotation in the vanilla
waist transform is there to undo. Anything that hangs off the belt hangs the other way
in the icon unless the transform accounts for it.

Usage:
    python3 tools/icon.py                      # lampbelt-temporal, as the slot shows it
    python3 tools/icon.py --color orange
    python3 tools/icon.py --compare            # beside the vanilla messenger belt
    python3 tools/icon.py --rotation 174,-45,23 --origin 0.4,1.1,0.4 --scale 2.85
"""
import argparse, collections, json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pnglib

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VS = "/home/deftones/Apps/vintagestory/assets"
SERAPH = f"{VS}/game/shapes/entity/humanoid/seraph.json"
OUT = os.path.join(HERE, "tools/icon.png")

# 24 px of visible slot either side of centre, against the 25.6 px the slot passes as
# `size`. A vertex beyond this is scissored away in game.
HALF_SLOT = 24.0 / 25.6

CELL = 240         # rendered pixels across the panel
SS = 3             # supersampling
MARGIN = 0.30      # view beyond the slot, so clipped geometry is visible
PAD = 12
BG = (38, 30, 24)
EDGE = (150, 120, 92)
FACE_GEOM = {   # axis, at the high end, u axis, v axis
    "north": (2, False, 0, 1), "south": (2, True, 0, 1),
    "west": (0, False, 2, 1), "east": (0, True, 2, 1),
    "up": (1, True, 0, 2), "down": (1, False, 0, 2),
}
NORMALS = {"north": (0, 0, -1), "south": (0, 0, 1), "west": (-1, 0, 0),
           "east": (1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0)}


# ---------------------------------------------------------------- json + textures

def load_json(path):
    """Vanilla json is JSON5-ish: comments, unquoted keys, trailing commas."""
    s = open(path).read()
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    s = re.sub(r"//.*", "", s)
    s = re.sub(r"([{,]\s*)([A-Za-z_][\w-]*)(\s*:)", r'\1"\2"\3', s)
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    return json.loads(s, object_pairs_hook=collections.OrderedDict)


def resolve_texture(path):
    domain, rel = path.split(":", 1) if ":" in path else ("game", path)
    if domain == "lampwright":
        p = os.path.join(HERE, "assets/lampwright/textures", rel + ".png")
        return p if os.path.exists(p) else None
    for root in ("survival", "game", "creative"):
        p = f"{VS}/{root}/textures/{rel}.png"
        if os.path.exists(p):
            return p
    return None


# ---------------------------------------------------------------- 4x4 matrices

def ident():
    return [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]


def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def translate(m, x, y, z):
    t = ident()
    t[0][3], t[1][3], t[2][3] = x, y, z
    return mul(m, t)


def rotate(m, deg, axis):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    r = ident()
    if axis == "x":
        r[1][1], r[1][2], r[2][1], r[2][2] = c, -s, s, c
    elif axis == "y":
        r[0][0], r[0][2], r[2][0], r[2][2] = c, s, -s, c
    else:
        r[0][0], r[0][1], r[1][0], r[1][1] = c, -s, s, c
    return mul(m, r)


def scale(m, x, y, z):
    s = ident()
    s[0][0], s[1][1], s[2][2] = x, y, z
    return mul(m, s)


def apply(m, p):
    return [sum(m[i][k] * p[k] for k in range(3)) + m[i][3] for i in range(3)]


# ---------------------------------------------------------------- shape -> boxes

def mark(e):
    """Tag the garment's own elements, so the bounds report can ignore the body."""
    e["_garment"] = True
    for c in e.get("children", []):
        mark(c)


def step_parent(parent_elements, child_elements):
    """Shape.StepParentShape: a child element naming a parent through stepParentName is
    appended to that element's children, so its coordinates become parent-relative."""
    by_name = {}

    def index(els):
        for e in els:
            by_name[e["name"].lower()] = e
            index(e.get("children", []))

    index(parent_elements)
    orphans = []
    for e in child_elements:
        target = by_name.get((e.get("stepParentName") or "").lower())
        if target is None:
            orphans.append(e.get("name"))
        else:
            mark(e)
            target.setdefault("children", []).append(e)
    if orphans:
        print(f"  no step parent for: {', '.join(orphans)} - invisible in game")


def collect(elements, m, out):
    """ShapeTesselator.TesselateShapeElements: per element translate to the rotation
    origin, rotate X/Y/Z, scale, translate to `from`; children inherit that matrix."""
    for e in elements:
        ro = e.get("rotationOrigin") or [0, 0, 0]
        me = translate(m, ro[0] / 16, ro[1] / 16, ro[2] / 16)
        for axis in ("x", "y", "z"):
            deg = e.get("rotation" + axis.upper())
            if deg:
                me = rotate(me, deg, axis)
        sxyz = (e.get("scaleX", 1), e.get("scaleY", 1), e.get("scaleZ", 1))
        if sxyz != (1, 1, 1):
            me = scale(me, *sxyz)
        f, t = e["from"], e["to"]
        me = translate(me, (f[0] - ro[0]) / 16, (f[1] - ro[1]) / 16, (f[2] - ro[2]) / 16)
        if e.get("faces"):
            out.append((e["name"], me, [(t[i] - f[i]) / 16 for i in range(3)], e["faces"],
                        bool(e.get("_garment"))))
        collect(e.get("children", []), me, out)
    return out


class Model:
    """The mesh the client uploads for this itemstack, with its textures."""

    def __init__(self, shape_path, itemtype, tex_overrides=None, on_body=True):
        shape = load_json(shape_path)
        elements = shape["elements"]
        tw, th = shape.get("textureWidth", 16), shape.get("textureHeight", 16)
        sizes = dict(shape.get("textureSizes", {}))
        paths = dict(shape.get("textures", {}))

        if on_body:
            body = load_json(SERAPH)
            step_parent(body["elements"], elements)
            elements = body["elements"]
            for name, p in body.get("textures", {}).items():
                paths.setdefault(name, p)
            for name, s in body.get("textureSizes", {}).items():
                sizes.setdefault(name, s)
        else:
            for e in elements:      # not body-mounted: every element is the item
                mark(e)

        # The itemtype's own texture dict wins, as ITexPositionSource resolves it:
        # "seraph" -> block/transparent is what makes the body invisible.
        for name, tex in (itemtype.get("textures") or {}).items():
            paths[name] = tex["base"] if isinstance(tex, dict) else tex
        paths.update(tex_overrides or {})

        self.boxes = collect(elements, ident(), [])
        self.tex, self.size = {}, {}
        for name, path in paths.items():
            file = resolve_texture(path)
            self.tex[name] = pnglib.read_png(file) if file else None
            if file is None:
                print(f"  MISSING texture {path} (code '{name}')")
            self.size[name] = tuple(sizes.get(name, (tw, th)))


# ---------------------------------------------------------------- rendering

def gui_matrix(tr):
    """InventoryItemRenderer.RenderItemstackToGui without the slot translation: the
    result is in units of the 25.6 px the slot passes as `size`, y pointing down."""
    k = tr.get("scale", 1.0)
    m = scale(ident(), k, k, k)
    for axis in ("x", "y", "z"):
        m = rotate(m, tr["rotation"][axis], axis)
    o = tr["origin"]
    return translate(m, -o["x"], -o["y"], -o["z"])


def render(model, tr, cell=CELL, ss=SS, alpha_test=0.25):
    gui = gui_matrix(tr)
    half = HALF_SLOT * (1 + MARGIN)
    n = cell * ss
    buf = bytearray(BG + (0,)) * (n * n)
    zbuf = [-1e9] * (n * n)
    seen = [1e9, -1e9, 1e9, -1e9]

    def project(m, p):
        q = apply(mul(gui, m), p)
        return ((q[0] + half) / (2 * half) * n, (q[1] + half) / (2 * half) * n, q[2])

    for name, m, size, faces, garment in model.boxes:
        if not garment:
            continue        # the seraph body: block/transparent, cut by the alpha test
        mm = mul(gui, m)
        for fname, (axis, high, ua, va) in FACE_GEOM.items():
            face = faces.get(fname)
            if face is None or face.get("enabled") is False:
                continue
            code = face["texture"].lstrip("#")
            tex = model.tex.get(code)
            if tex is None:
                continue
            tsize = model.size.get(code, (16, 16))

            def corner(fu, fv):
                p = [0.0, 0.0, 0.0]
                p[axis] = size[axis] if high else 0.0
                p[ua] = size[ua] * fu
                p[va] = size[va] * fv
                return p

            # v runs down the texture; for side faces that is the -y end of the box.
            flip = 0 if va == 2 else 1
            pts = [corner(0, flip), corner(1, flip), corner(1, 1 - flip), corner(0, 1 - flip)]
            if garment:
                for p in pts:
                    q = apply(mm, p)
                    seen[0] = min(seen[0], q[0]); seen[1] = max(seen[1], q[0])
                    seen[2] = min(seen[2], q[1]); seen[3] = max(seen[3], q[1])
            quad = [project(m, p) for p in pts]

            nz = NORMALS[fname]
            lit = max(0.0, nz[0] * 0.40 + nz[1] * -0.55 + nz[2] * 0.70)   # gui y is down
            u0, v0, u1, v1 = face.get("uv", [0, 0, 16, 16])
            rasterize(buf, zbuf, n, quad, (u0, v0, u1, v1), tsize, tex,
                      0.60 + 0.40 * lit, face.get("glow", 0) / 255 * 0.45, alpha_test)

    img = downsample(buf, n, cell, ss)
    draw_slot_edge(img, cell)
    return img, seen


def rasterize(buf, zbuf, n, quad, uv, tsize, tex, shade, glow, alpha_test):
    u0, v0, u1, v1 = uv
    tsw, tsh = tsize
    tw, th, px = tex
    corners_uv = [(u0, v1), (u1, v1), (u1, v0), (u0, v0)]
    for a, b, c in ((0, 1, 2), (0, 2, 3)):
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = quad[a], quad[b], quad[c]
        tuv = [corners_uv[a], corners_uv[b], corners_uv[c]]
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-9:
            continue
        ylo = max(0, int(min(y0, y1, y2)))
        yhi = min(n - 1, int(max(y0, y1, y2)) + 1)
        xlo = max(0, int(min(x0, x1, x2)))
        xhi = min(n - 1, int(max(x0, x1, x2)) + 1)
        for y in range(ylo, yhi + 1):
            py = y + 0.5
            for x in range(xlo, xhi + 1):
                pxx = x + 0.5
                w0 = ((x1 - pxx) * (y2 - py) - (x2 - pxx) * (y1 - py)) / area
                w1 = ((x2 - pxx) * (y0 - py) - (x0 - pxx) * (y2 - py)) / area
                w2 = 1 - w0 - w1
                if w0 < -1e-6 or w1 < -1e-6 or w2 < -1e-6:
                    continue
                z = w0 * z0 + w1 * z1 + w2 * z2
                idx = y * n + x
                if z <= zbuf[idx]:              # the gui ortho draws larger z on top
                    continue
                u = w0 * tuv[0][0] + w1 * tuv[1][0] + w2 * tuv[2][0]
                v = w0 * tuv[0][1] + w1 * tuv[1][1] + w2 * tuv[2][1]
                tx = min(tw - 1, max(0, int(u / tsw * tw)))
                ty = min(th - 1, max(0, int(v / tsh * th)))
                o = (ty * tw + tx) * 4
                r, g, b, al = px[o], px[o + 1], px[o + 2], px[o + 3]
                if al / 255 < alpha_test:       # renderAlphaTest discards these
                    continue
                r, g, b = (min(255, int(ch * shade)) for ch in (r, g, b))
                if glow:
                    r, g, b = (min(255, int(ch + (255 - ch) * glow)) for ch in (r, g, b))
                zbuf[idx] = z
                buf[idx * 4:idx * 4 + 4] = bytes((r, g, b, 255))


def downsample(buf, n, cell, ss):
    out = bytearray(cell * cell * 4)
    for y in range(cell):
        for x in range(cell):
            r = g = b = a = 0
            for dy in range(ss):
                for dx in range(ss):
                    o = ((y * ss + dy) * n + x * ss + dx) * 4
                    af = buf[o + 3]
                    r += buf[o] * af; g += buf[o + 1] * af; b += buf[o + 2] * af; a += af
            if a:
                r, g, b = r // a, g // a, b // a
            cov = a / (255 * ss * ss)
            o = (y * cell + x) * 4
            out[o:o + 4] = bytes((int(r * cov + BG[0] * (1 - cov)),
                                  int(g * cov + BG[1] * (1 - cov)),
                                  int(b * cov + BG[2] * (1 - cov)), 255))
    return out


def draw_slot_edge(img, cell):
    """The slot boundary. In game the scissor cuts everything outside this box."""
    lo = int(cell * (MARGIN / (1 + MARGIN)) / 2)
    hi = cell - lo - 1
    for i in range(lo, hi + 1):
        for (x, y) in ((i, lo), (i, hi), (lo, i), (hi, i)):
            o = (y * cell + x) * 4
            img[o:o + 4] = bytes(EDGE + (255,))


def tile(panels, cell=CELL):
    w = len(panels) * (cell + PAD) + PAD
    h = cell + 2 * PAD
    out = bytearray(BG + (255,)) * (w * h)
    for i, (_, img, _) in enumerate(panels):
        x_at = PAD + i * (cell + PAD)
        for y in range(cell):
            d = ((y + PAD) * w + x_at) * 4
            out[d:d + cell * 4] = img[y * cell * 4:(y + 1) * cell * 4]
    return w, h, out


def report(label, seen):
    x0, x1, y0, y1 = seen
    cut = (min(x0, y0) < -HALF_SLOT - 1e-6) or (max(x1, y1) > HALF_SLOT + 1e-6)
    print(f"  {label}: x {x0:+.2f}..{x1:+.2f}  y {y0:+.2f}..{y1:+.2f}"
          f"   (slot is +-{HALF_SLOT:.3f}){'  CLIPPED' if cut else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--color", default="temporal")
    ap.add_argument("--compare", action="store_true",
                    help="render the vanilla merchant belt beside it")
    ap.add_argument("--rotation", help="override, as x,y,z degrees")
    ap.add_argument("--origin", help="override, as x,y,z")
    ap.add_argument("--scale", type=float)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    item = load_json(os.path.join(HERE, "assets/lampwright/itemtypes/lampbelt.json"))
    tr = json.loads(json.dumps(item["guiTransform"]))
    if args.rotation:
        x, y, z = (float(v) for v in args.rotation.split(","))
        tr["rotation"] = {"x": x, "y": y, "z": z}
    if args.origin:
        x, y, z = (float(v) for v in args.origin.split(","))
        tr["origin"] = {"x": x, "y": y, "z": z}
    if args.scale:
        tr["scale"] = args.scale
    print(f"rotation {tr['rotation']}  origin {tr['origin']}  scale {tr['scale']}")

    label = f"lampbelt-{args.color}"
    img, seen = render(Model(os.path.join(HERE, "assets/lampwright/shapes/lampbelt.json"),
                             item, {"lampbelt": f"lampwright:entity/lampbelt-{args.color}"}), tr)
    panels = [(label, img, seen)]
    report(label, seen)

    if args.compare:
        vanilla = {"textures": {"seraph": {"base": "block/transparent"}}}
        img, seen = render(Model(f"{VS}/survival/shapes/entity/humanoid/seraph"
                                 f"/clothing/waist/merchant-belt.json", vanilla),
                           item["guiTransform"])
        panels.append(("vanilla merchant-belt", img, seen))
        report("vanilla merchant-belt", seen)

    w, h, out = tile(panels)
    pnglib.write_png(args.out, w, h, out)
    print("wrote", args.out, f"{w}x{h}")
    print("panels left to right:", ", ".join(p[0] for p in panels))


if __name__ == "__main__":
    main()
