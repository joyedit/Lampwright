"""Builds assets/lampwright/shapes/lampbelt.json from vanilla's merchant-belt.

The belt itself is vanilla, untouched: the band, the buckle and the belt loop keep
their geometry and their uvs. Only three things change.

  1. The texture code is renamed to #lampbelt and points at our own png. Vanilla's
     merchant-belt.png is pasted into the top-left quadrant of that png at 1:1, under a
     16x16 uv space, so every vanilla uv still lands on the pixels it always did -
     see tools/gen_textures.py for the layout.
  2. Vanilla's two hip pouches are dropped.
  3. A hip lamp and four gear studs are added, in the free uv quadrants.

The merchant belt was picked over the other forty waist shapes because it is a plain
band with one buckle and a pouch hanging at the right hip - the pouch is already where
the lamp wants to be, and a plain band is what survives being shrunk to a 48-pixel
inventory icon. The first build used the clockmaker toolbelt, which carries a saw,
hammer, chisel, abacus and pouch, and read as a cluttered garment rather than a belt.
"""
import collections, json, re

VANILLA = ("/home/deftones/Apps/vintagestory/assets/survival/shapes"
           "/entity/humanoid/seraph/clothing/waist/merchant-belt.json")
DST = "/home/deftones/Dev/Lampwright/assets/lampwright/shapes/lampbelt.json"

raw = re.sub(r',(\s*[}\]])', r'\1', open(VANILLA).read())   # vanilla uses trailing commas
raw = raw.replace("#merchant-belt", "#lampbelt")
shape = json.loads(raw, object_pairs_hook=collections.OrderedDict)

# One texture code, one png, in our own domain and therefore in the item atlas the
# inventory icon is tesselated against. The itemtype overrides this per colour variant;
# the value here is the fallback and keeps the shape openable in VS Model Creator.
shape["textures"] = collections.OrderedDict([
    ("lampbelt", "lampwright:entity/lampbelt-temporal"),
])
# uv numbers are in the coordinate space textureSizes declares, not in texels: the image
# is stretched onto it. Vanilla declares 8x8 for its 16x16 png; our png is 32x32 and
# declares 16x16, which is the same two-pixels-per-unit scale with three more quadrants
# of room. Vanilla's uvs, all of which fall inside 0..8, are unaffected.
shape["textureWidth"] = 16
shape["textureHeight"] = 16
shape["textureSizes"] = collections.OrderedDict([("lampbelt", [16, 16])])

waist = shape["elements"][0]
assert waist["name"] == "Waist", waist["name"]
waist["children"] = [c for c in waist["children"]
                     if not c["name"].startswith("pouch")]

# uv rects in the three added quadrants. The gear maps its whole tile: the sprite is
# drawn with alpha, so cropping it would cut the silhouette rather than zoom it.
BRASS_UV = (10, 2, 14, 6)
LENS_UV = (1, 9, 7, 15)
GEAR_UV = (8, 8, 16, 16)


def faces(uv, glow=None):
    f = collections.OrderedDict()
    for side in ("north", "east", "south", "west", "up", "down"):
        d = collections.OrderedDict([("texture", "#lampbelt"), ("uv", list(uv))])
        if glow:
            d["glow"] = glow
        f[side] = d
    return f


def elem(name, frm, to, uv, glow=None):
    # Flat top-level siblings of Waist, each with its own stepParentName. Child
    # coordinates in a VS shape are relative to the parent element, so keeping these
    # unparented puts the numbers below in the same LowerTorso bone space as the band:
    # the band runs x -0.2..5.2, y 0..1, z -0.4..6.4.
    return collections.OrderedDict([
        ("name", name),
        ("stepParentName", "LowerTorso"),
        ("from", frm),
        ("to", to),
        ("faces", faces(uv, glow)),
    ])


# Four gear studs, 0.9 of the band's 1.0 height and standing 0.2 proud of it, one on
# each outer face. The east one sits directly above the lamp so it reads as driving it.
GEARS = [
    ("gear-north", [2.05, 0.05, -0.60], [2.95, 0.95, -0.40]),
    ("gear-south", [2.05, 0.05,  6.40], [2.95, 0.95,  6.60]),
    ("gear-west",  [-0.40, 0.05, 3.05], [-0.20, 0.95, 3.95]),
    ("gear-east",  [5.20, 0.05,  2.55], [5.40, 0.95,  3.45]),
]

added = [elem(n, f, t, GEAR_UV, 255) for n, f, t in GEARS] + [
    # The hip lamp, where vanilla's right-hip pouch was. A narrow glowing body between a
    # brass cap and base that both overhang it, on a short bail tucked under the band:
    # that is the lantern silhouette, and it is the one thing here that has to survive
    # being shrunk to 48 pixels, which is the size most people ever see this at.
    elem("lamp-bail",  [4.90, -0.50, 2.80], [5.35,  0.00, 3.20], BRASS_UV),
    elem("lamp-cap",   [4.65, -0.85, 2.45], [5.85, -0.50, 3.65], BRASS_UV),
    elem("lamp-glass", [4.75, -2.35, 2.55], [5.75, -0.85, 3.55], LENS_UV, 255),
    elem("lamp-base",  [4.65, -2.75, 2.45], [5.85, -2.35, 3.65], BRASS_UV),
]

shape["elements"].extend(added)
open(DST, "w").write(json.dumps(shape, indent="\t") + "\n")
print("wrote", DST)
print("top level:", [e["name"] for e in shape["elements"]])
print("band kids:", [c["name"] for c in waist["children"]])
