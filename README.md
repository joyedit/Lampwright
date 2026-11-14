# Lampwright

A waist-slot belt for Vintage Story that lights your way while worn, leaving both hands
and the offhand slot free. Built for playing with heavy lighting or path-tracing shaders,
where carrying a two-handed weapon otherwise means walking blind.

## Craft

3x3 grid:

```
gear   twine  gear
twine  belt   twine
gear   twine  gear
```

- 4x temporal gear (`game:gear-temporal`)
- 4x flax twine (`game:flaxtwine`)
- 1x any belt (`game:clothes-waist-*`)

That produces the temporal (cyan) belt. The other colours come from sealing the belt in
a barrel with 1 litre of dye for 4 hours, the same way vanilla dyes cloth and daub; a
temporal gear in the barrel puts the original lens back.

Temporal gears have a max stack size of 1, so the four gears must occupy four separate
cells - a `quantity: 4` ingredient could never be satisfied.

## How the light works

Vintage Story does not light the player from clothing slots. `EntityPlayer.LightHsv`
reads exactly two slots, `RightHandItemSlot` and `LeftHandItemSlot`; that is why the
vanilla temporal gear amulet (`clothes-neck-gear-amulet-temporal`) ships a `lightHsv`
that does nothing while worn.

That same property has a public setter writing a private `baseLightHsv` field, and the
getter merges that field with hand light through `ColorUtil.MergeLightHSV`. Assigning to
it is therefore enough - no Harmony patch, no reflection - and a torch in hand still
stacks with the belt instead of cancelling it.

`SystemRenderPlayerEffects` then collects every entity within 120 blocks whose
`LightHsv[2] > 0` and hands it to the shaders as a moving point light, capped by the
client's `maxDynamicLights` setting (default 10). Nothing is baked into chunk lighting,
so there is no relight cost, and the glow lands on the wearer's own model as well as the
terrain around them.

`LightHsv` is never synced, so the server publishes a `lampwrightLit` watched attribute
and each client applies the light locally. The local player is read straight from their
own character inventory so equipping has no visible delay.

## Colours

`lightHsv` is `[hue 0-63, saturation 0-7, brightness 0-31]`; the client expands it as
`hue * 4` and `sat * 32` onto a 0-255 wheel (`ClientSystemStartup`), then runs
`ColorUtil.Hsv2RgbInts`. Running that maths over the variants and the vanilla sources
they were matched against:

| source | lightHsv | emitted light | |
| --- | --- | --- | --- |
| vanilla lit torch | `[4, 4, 14]` | `#ffaf7e` | warm orange |
| vanilla lantern | `[7, 3, 18]` | `#ffde9e` | soft amber |
| vanilla gas lamp | `[8, 4, 22]` | `#ffdf7e` | amber |
| vanilla temporal gear | `[32, 5, 2]` | `#5efffd` | cyan |
| **belt, temporal** | `[32, 5, 17]` | `#5efffd` | cyan |
| **belt, orange** | `[4, 4, 17]` | `#ffaf7e` | torch, exactly |
| **belt, red** | `[0, 6, 17]` | `#ff3f3e` | red |
| **belt, yellow** | `[9, 4, 17]` | `#ffeb7e` | warm yellow |
| **belt, blue** | `[40, 4, 17]` | `#7ea1ff` | sky blue |
| **belt, white** | `[0, 0, 17]` | `#ffffff` | neutral white |

Saturation 0 is the special case that makes white: the conversion short-circuits and
returns `(v, v, v)` whatever the hue is.

Brightness 17 sits between a lit torch (14) and a lantern (18-20); the engine caps it
at 31. Nothing in C# hardcodes a colour - `LampwrightModSystem` reads `lightHsv` back
off the collectible, so `lightHsvByType` in the itemtype is the only place to change it
and new variants need no code change.

A client with dynamic lights set to 0 will see no glow at all; that is a client setting
the mod cannot override.

## Dyeing and condition

A barrel, one litre of vanilla liquid dye and the belt, sealed four hours, gives
orange, red, yellow, blue or white; a temporal gear in place of the dye puts the
original cyan lens back. The ingredient matches `lampbelt-*`, so any colour goes
straight to any other.

The belt declares `warmth: 0.25`, which puts it inside vanilla's clothing wear system:
condition ticks down as it is worn and goes back up by handing it a sewing kit (+75%),
cloth or linen (+50%) or flax twine (+10%). Condition scales warmth only - a belt at
16% still lights at full strength.

`CollectibleBehaviorWearable.ensureConditionExists` rolls a random 0-40% condition for
any clothing stack that has no `condition` attribute yet, and only `OnCreatedByCrafting`
sets it to 1. `BarrelRecipe.TryCraftNow` clones its output and writes it straight into
the slot without going through that, so a dyed belt arrives with no condition and gets
the random roll - a belt that went in at 100% could come out Heavily Tattered. The same
roll is why a belt from `/giveitem` or the creative inventory is born worn.

`src/LampbeltWearable.cs` subclasses the behaviour and replaces that roll with a flat
1. Fixing it there costs a ten-line override; carrying the old condition across the
barrel instead would mean Harmony patching `TryCraftNow`, which has no hook and
overwrites its own input slots. The trade-off is that re-dyeing refurbishes the belt.

## Model

`assets/lampwright/shapes/lampbelt.json` is *generated*, not hand-authored:
`tools/gen_shape.py` copies vanilla's **merchant-belt** - a plain band with one buckle,
a belt loop and a pouch hanging at the right hip - keeps the band, buckle and loop
exactly as they are, drops the two pouches, and adds four gear studs and a four-piece
hip lamp (brass bail, cap, glowing glass, base) where the right-hip pouch was. Re-run it
if a VS update changes the vanilla belt.

It was picked over the other forty waist shapes because a plain band is what survives
being shrunk to a 48-pixel inventory icon, and because its pouch already hangs where the
lamp wants to be. The first build used the clockmaker toolbelt, which carries a saw,
hammer, chisel, abacus and pouch; at icon size that reads as a cluttered garment rather
than a belt.

`tools/gen_textures.py` draws one 32x32 texture per colour variant,
`assets/lampwright/textures/entity/lampbelt-<colour>.png`, holding everything the shape
needs in four 16x16 tiles: vanilla's merchant-belt recoloured from olive to leather and
brass, a brass plate, the glowing lens, and a gear sprite. The vanilla temporal gear
texture cannot be reused for that last one: it is fully opaque, an atlas wrapped onto
the gear's 3D model, so a face mapped with it shows a solid square. The generated sprite
carries real alpha, so `renderAlphaTest` cuts the gear silhouette out of the plate.

`uv` numbers are in the coordinate space `textureSizes` declares for that texture, not
in texels: the image is stretched onto it. Vanilla declares `8x8` for its `16x16` png,
and ours declares `16x16` for a `32x32` png - the same two-pixels-per-unit scale with
three more quadrants of room. Vanilla's uvs all fall inside `0..8`, so pasting its image
at the origin leaves every one of them pointing at the pixels it always did, and the
belt's geometry and uvs stay untouched vanilla.

`tools/preview.py` renders the shape to `tools/preview.png` - three orthographic views,
faces sampled from the real textures through their uv rects with the same alpha cutout
the game applies - so geometry can be checked without launching the client. The lens
faces carry `"glow": 255` so they read as lit on the character model independently of
the point light.

## Icon

`tools/icon.py` renders the inventory slot to `tools/icon.png`: same mesh, same matrix,
same scissor as the client, so the icon can be judged - and the `guiTransform` tuned -
without launching the game. `--compare` puts the vanilla merchant belt beside it,
`--rotation/--origin/--scale` try a transform without editing the itemtype. It is
validated against a vanilla backpack, which it reproduces.

Three things decide that picture, all read out of the 1.22.7 assemblies:

- **A wearable's icon is not its own shape.**
  `CollectibleBehaviorWearableAttachment.OnBeforeRender` throws the plain item mesh away
  and calls `genFullBodyMesh`: it clones the player entity's shape, step-parents the
  clothing shape onto it by `stepParentName`, and tesselates *that*. The body is
  invisible only because the itemtype maps the `seraph` texture to `block/transparent`
  and `renderAlphaTest` cuts it. So the belt sits at the `LowerTorso` bone, around y=15
  in shape units, which is why the `guiTransform` origin is `y: 1.1` and not `y: 0`.
- **The matrix.** `InventoryItemRenderer.RenderItemstackToGui`, applied to a vertex:
  translate by `-origin`, rotate Z then Y then X, scale by `size * scale`, translate to
  the slot centre. GUI space has y pointing *down*, which is what the 174-degree X
  rotation in the vanilla waist transform is there to undo.
- **The slot clips.** A slot is 48 unscaled px and passes `size = 25.6`, then pushes a
  scissor at its own bounds, so a vertex shows only while `scale * R*(v - origin)` stays
  inside `+-24/25.6 = +-0.9375`.

- **Every texture code the shape uses must resolve against the ITEM atlas.** The icon is
  tesselated through `capi.Tesselator.GetTextureSource(item)`, and the cloned body shape
  is built with `Textures = null`, so the shape file's own `textures` block is not what
  decides this - the itemtype's is. A code that does not resolve there does not draw as
  a missing texture; it comes back pointing into some other atlas and draws as a slab of
  unrelated blocks. The first build named `game:...messenger-belt`,
  `game:block/metal/plate/brass` and `game:block/transparent` from the shape, and all
  three came out as garbage while the two `lampwright:` textures rendered correctly.
  Everything the belt needs is one png in our own domain now, including the transparent
  one the itemtype maps the seraph body to.

The belt therefore does *not* use vanilla's waist transform. Vanilla's numbers frame a
flat band; against a belt with a lamp hanging off it they put the lamp behind the band,
nearly edge on, seen from underneath.

## Build

```
./deploy.sh
```

Builds, packages `Lampwright_<version>.zip` from `modinfo.json`, removes older copies and
drops it in the Mods folder. Close the game first; the script refuses to deploy over a
running client unless `FORCE=1`.
