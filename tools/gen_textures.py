"""Generates assets/lampwright/textures/entity/lampbelt-<colour>.png, one per variant,
plus the fully transparent texture the itemtype maps the seraph body to.

One texture, in our own domain, for the whole belt. That is deliberate. An item's
inventory icon is tesselated through the ITEM texture atlas
(CollectibleBehaviorWearableAttachment.OnBeforeRender -> Tesselator.GetTextureSource
(item)), and a texture code that does not resolve there comes back pointing at some
other atlas entry - which draws as a slab of unrelated blocks rather than as a missing
texture. The first version of this belt referenced game:entity/.../messenger-belt,
game:block/metal/plate/brass and game:block/transparent from the shape file and all
three came out as garbage, so everything the shape needs now lives in one png we ship.

Layout. The shape declares a 16x16 uv space over this 32x32 png, so one uv unit is two
pixels and the four 8x8 uv quadrants are four 16x16 pixel tiles:

      uv x 0..8            uv x 8..16
    +--------------------+--------------------+
    | vanilla merchant   | brass              |  uv y 0..8
    | belt, recoloured   |                    |
    +--------------------+--------------------+
    | lens (glowing)     | gear (alpha)       |  uv y 8..16
    +--------------------+--------------------+

Vanilla's merchant-belt.png is 16x16 and its uvs run 0..8, so pasting it at the origin
leaves every vanilla uv in the shape pointing at exactly the pixels it always did. The
belt geometry and its uvs are therefore untouched vanilla; the other three tiles are
new uv space for the parts we add.
"""
import math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pnglib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets/lampwright/textures/entity")
BELT = ("/home/deftones/Apps/vintagestory/assets/survival/textures"
        "/entity/humanoid/seraphclothes/waist/merchant-belt.png")

SIZE = 32          # png pixels
TILE = 16          # one uv quadrant, in png pixels

# variant -> the visible colour of its lens and gears
COLORS = {
    "temporal": (70, 230, 215),
    "orange":   (255, 150, 70),
    "red":      (255, 80, 70),
    "yellow":   (255, 235, 110),
    "blue":     (120, 165, 255),
    "white":    (240, 245, 255),
}

# The merchant belt is olive green with a steel buckle. A lampwright's belt wants to be
# leather and brass, and since we own the copy it is cheaper to recolour the palette
# than to hand-paint a new band. Four greens -> four leathers, four greys -> four
# brasses; everything else (the red stitch, the pouch browns) is left alone.
RECOLOR = {
    (0x8c, 0xa0, 0x76): (0xa8, 0x80, 0x4e),
    (0x80, 0x93, 0x6c): (0x95, 0x6f, 0x42),
    (0x74, 0x87, 0x5f): (0x82, 0x5f, 0x38),
    (0x5e, 0x76, 0x54): (0x68, 0x49, 0x2c),
    (0xcc, 0xd7, 0xdb): (0xe8, 0xc8, 0x78),
    (0xb2, 0xbb, 0xbf): (0xcd, 0xaa, 0x58),
    (0x97, 0xa0, 0xa2): (0xa9, 0x89, 0x40),
    (0x85, 0x8d, 0x8f): (0x8b, 0x6e, 0x31),
}

TEETH = 8
R_TIP = 7.4         # outer radius at a tooth, in tile pixels
R_ROOT = 5.6        # outer radius between teeth
R_HOLE = 1.6        # the axle hole
DUTY = 0.46         # fraction of each tooth pitch that is tooth rather than gap


def blank():
    return bytearray(SIZE * SIZE * 4)


def put(px, x, y, rgba):
    n = (y * SIZE + x) * 4
    px[n:n + 4] = bytes(rgba)


def paste_belt(px):
    """Vanilla's band at the origin, recoloured, so its uvs keep pointing at it."""
    w, h, src = pnglib.read_png(BELT)
    for y in range(h):
        for x in range(w):
            n = (y * w + x) * 4
            r, g, b, a = src[n], src[n + 1], src[n + 2], src[n + 3]
            r, g, b = RECOLOR.get((r, g, b), (r, g, b))
            put(px, x, y, (r, g, b, a))


def paste_brass(px, ox, oy):
    """Hammered brass: a flat plate is fine at this size, a little grain keeps it from
    looking like a solid fill when it is stretched over a 1.4-unit lamp cap."""
    for y in range(TILE):
        for x in range(TILE):
            k = 0.86 + 0.14 * (((x * 7 + y * 13) % 5) / 4.0)
            if x in (0, TILE - 1) or y in (0, TILE - 1):
                k *= 0.78                      # a darker rim reads as an edge
            put(px, ox + x, oy + y,
                tuple(min(255, int(v * k)) for v in (214, 170, 84)) + (255,))


def paste_lens(px, ox, oy, rgb):
    """The lamp glass: a lit pane, brightest through the middle, in a dark frame."""
    for y in range(TILE):
        for x in range(TILE):
            band = 1.0 - abs(y - (TILE - 1) / 2.0) / ((TILE - 1) / 2.0)
            k = 0.62 + 0.38 * band
            if x in (0, TILE - 1) or y in (0, TILE - 1):
                k = 0.42
            put(px, ox + x, oy + y,
                tuple(min(255, int(v * k)) for v in rgb) + (255,))


def paste_gear(px, ox, oy, rgb):
    """A gear silhouette on transparency. The vanilla temporal gear texture cannot be
    reused here: it is an atlas wrapped onto the gear's 3D model and fully opaque, so a
    flat face mapped with it shows a solid square. With real alpha the game's
    renderAlphaTest cuts the teeth out of the plate."""
    c = (TILE - 1) / 2.0
    pitch = 2 * math.pi / TEETH
    for y in range(TILE):
        for x in range(TILE):
            dx, dy = x - c, y - c
            r = math.hypot(dx, dy)
            phase = (math.atan2(dy, dx) % pitch) / pitch
            r_max = R_TIP if phase < DUTY else R_ROOT
            if r > r_max or r < R_HOLE:
                continue                       # transparent: outside the gear, or the hole
            # Lift the rim and the hole's lip so the silhouette survives being drawn at
            # glow 255, where everything otherwise flattens toward white.
            edge = min(r_max - r, r - R_HOLE)
            k = 0.85 + 0.15 * (r / R_TIP) + (0.25 if edge < 0.9 else 0.0)
            put(px, ox + x, oy + y,
                tuple(min(255, int(v * k)) for v in rgb) + (255,))


os.makedirs(OUT, exist_ok=True)
for variant, rgb in COLORS.items():
    px = blank()
    paste_belt(px)
    paste_brass(px, TILE, 0)
    paste_lens(px, 0, TILE, rgb)
    paste_gear(px, TILE, TILE, rgb)
    pnglib.write_png(os.path.join(OUT, f"lampbelt-{variant}.png"), SIZE, SIZE, px)
    print(f"  lampbelt-{variant}.png")

# The itemtype maps the seraph body to this so the body half of the inventory mesh is
# cut away by renderAlphaTest. Vanilla points at game:block/transparent; shipping our
# own keeps every texture this item names inside our domain and the item atlas.
pnglib.write_png(os.path.join(OUT, "invisible.png"), 2, 2, bytearray(2 * 2 * 4))
print("  invisible.png")
print("wrote", OUT)
