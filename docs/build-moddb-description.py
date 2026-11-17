#!/usr/bin/env python3
"""Builds the paste-ready ModDB description for Lampwright.

mods.vintagestory.at strips <style> blocks and ignores class= in a mod description, but it
keeps inline style="..." attributes. So a page that keeps its design in a stylesheet arrives
on the ModDB as a wall of unstyled text. This script emits the content with every rule
inlined, and wraps the same fragment in a standalone document for checking it in a browser.

    python3 docs/build-moddb-description.py

Writes:
    docs/lampwright-moddb.html   the fragment to paste into the ModDB description field
    docs/lampwright.html         the same fragment in a full page, for local preview

Size is the binding constraint. The site&#39;s editor re-serialises whatever you paste before
it measures it, and that rewrite inflates inline CSS by roughly 60%: every shorthand expands,
every #hex becomes rgb(r, g, b), and every declaration gains its spaces back. The ModDB
refused a 53KB file as "85KB". So the budget is this file&#39;s weight times about 1.6, and
the target is 32KB generated, which lands near 50KB stored.

What that buys: no tables except the figure strip under the masthead - a cell carries its own
padding and border and both treble in the rewrite, so feature lists, recipes and colours are
plain <ul>. Styling sits on the parent wherever colour, line-height and font-size can
inherit. <code> is monospace in every browser without being told.

Other house rules:
  - Content lives here and nowhere else; both files are generated, so they cannot drift.
  - No backtick characters anywhere in the text, apostrophes are written &#39; as you go
    (never regex-swept - a sweep eats the f' that opens every f-string), and the AI
    disclosure stays last, verbatim.
  - No author byline and no source link: Jay links the source elsewhere on each mod page.

Derived from ~/Dev/Quartermaster/docs/build-moddb-description.py - the fleet template.
Structure and typography are the fleet&#39;s; only the accent shifts, here to the temporal
teal of the belt&#39;s default lens.
"""
import os
import re

PAPER   = "#F2EEE5"
SURFACE = "#FAF7F0"
INK     = "#1B1915"
INK2    = "#4A4539"
INK3    = "#7A746A"
RULE    = "#DCD5C6"
RULES   = "#BEB5A3"
TEAL    = "#1C6B70"

# Short on purpose: a font stack is stamped into every element that names it.
BODY = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
DISP = "Georgia,'Times New Roman',serif"
MONO = "ui-monospace,Menlo,Consolas,monospace"

VERSION = "0.2.0"
GAME    = "1.22"

BUDGET = 32 * 1024


def p(text, mt="0", mb="14px", color=None, size=None):
    extra = f" font-size:{size};" if size else ""
    extra += f" color:{color};" if color else ""
    return f'<p style="margin:{mt} 0 {mb};{extra}">{text}</p>'


def h2(text):
    return (f'<h2 style="font-family:{DISP}; font-size:1.6em; line-height:1.15; margin:36px 0 14px;'
            f' padding-top:24px; border-top:1px solid {RULE};">{text}</h2>')


def code(t):
    """Monospace comes from the browser; only the colour is worth a declaration."""
    return f'<code style="color:{TEAL};">{t}</code>'


def key(t):
    """A click or a keystroke, set in bold monospace - a bordered box costs three
    declarations that treble in the editor&#39;s rewrite."""
    return f'<code style="font-weight:700;">{t}</code>'


def term(t):
    return f"<em>{t}</em>"


def note(label, text):
    return (f'<div style="background:{SURFACE}; border-left:4px solid {TEAL}; padding:12px 16px;'
            f' margin:20px 0;">'
            f'<div style="font-family:{MONO}; font-size:0.68em; font-weight:700; letter-spacing:0.14em;'
            f' text-transform:uppercase; color:{TEAL}; margin-bottom:6px;">{label}</div>'
            f'<div>{text}</div></div>')


def bullets(items, mb="14px"):
    lis = "".join(f"<li>{i}</li>" for i in items)
    return (f'<ul style="margin:10px 0 {mb}; padding-left:22px; color:{INK2}; line-height:1.65;">'
            f"{lis}</ul>")


def recipe(rows):
    """The crafting grid, as the game lays it out. One box, monospace, no table."""
    inner = "<br>".join(rows)
    return (f'<div style="font-family:{MONO}; font-size:0.85em; color:{INK2}; background:{SURFACE};'
            f' border-left:3px solid {RULES}; padding:11px 14px; margin:14px 0; line-height:1.9;'
            f' white-space:pre;">{inner}</div>')


def specs(items):
    cells = []
    for n, unit, label in items:
        u = (f' <span style="font-size:0.5em; color:{INK3}; font-style:italic;">{unit}</span>'
             if unit else "")
        cells.append(
            f'<td style="padding:15px 14px; vertical-align:top; width:25%;">'
            f'<div style="font-family:{MONO}; font-size:1.8em; font-weight:600; line-height:1;">{n}{u}</div>'
            f'<div style="font-size:0.78em; color:{INK3}; margin-top:6px; line-height:1.4;">{label}</div></td>')
    return (f'<table style="width:100%; border-top:1px solid {RULES}; border-bottom:1px solid {RULES};'
            f' background:{SURFACE}; margin:0 0 28px; text-align:left;" cellspacing="0" cellpadding="0">'
            f'<tr>{"".join(cells)}</tr></table>')


def chips(words):
    return (f'<div style="font-family:{MONO}; font-size:0.78em; color:{INK3}; margin:14px 0 4px;">'
            + " &nbsp;&middot;&nbsp; ".join(words) + "</div>")


H = []
a = H.append

a(f'<div style="font-family:{BODY}; font-size:16px; line-height:1.75; color:{INK};'
  f' background:{PAPER}; max-width:860px; margin:0 auto; padding:30px 26px 34px;">')

# ---- masthead ----
a(f'<div style="font-family:{MONO}; font-size:0.68em; font-weight:600; letter-spacing:0.16em;'
  f' text-transform:uppercase; color:{TEAL}; margin-bottom:10px;">Vintage Story &middot; mod guide</div>')
a(f'<h1 style="font-family:{DISP}; font-size:2.9em; line-height:1; margin:0 0 12px;">Lampwright</h1>')
a(f'<p style="font-size:1.1em; line-height:1.6; color:{INK2}; max-width:34em; margin:0 0 18px;">'
  f'A belt that lights your way while you wear it &mdash; so both hands and the offhand slot '
  f'stay free for the axe, the bow, or the shield you actually came down here with.</p>')
a(f'<div style="font-family:{MONO}; font-size:0.76em; color:{INK3}; margin:0 0 26px;">v{VERSION} '
  f'&nbsp;&middot;&nbsp; built for Vintage Story {GAME} &nbsp;&middot;&nbsp; client and server</div>')

a(specs([("17", "light", "brighter than a torch, just under a lantern"),
         ("6", "colours", "dyed in a barrel, any colour to any other"),
         ("0", "fuel", "never burns down, never needs filling"),
         ("0", "dependencies", "nothing else to install")]))

a(p('Vintage Story only lights you from what you are holding. Carry a torch and you give up a '
    'hand; carry a lantern and you give up the offhand. Pick up a two-handed weapon, a bow or a '
    'shield and you walk blind.'))

a(p('Lampwright&#39;s Belt is a tinker&#39;s belt with four temporal gears set into the leather, '
    'feeding a small brass lamp at the hip. Wear it and it lights the ground around you from the '
    'waist slot &mdash; which costs you nothing you were using &mdash; at light level 17, brighter '
    'than a torch and a shade under a lantern. It never burns down and never needs filling.'))

a(p('It was built for playing with heavy lighting or path-tracing shaders, where the world is '
    'genuinely dark and a free hand matters. It is just as useful in a vanilla cave.'))

a(note("Before you install",
       f'<b>Dynamic lights have to be switched on.</b> If your client has Max Dynamic Lights set '
       f'to 0, you will see no glow at all &mdash; from this belt or from a held torch. That is a '
       f'client graphics setting no mod can override; the game&#39;s default is 10, and anything '
       f'above 0 is enough.'))

# ---- crafting ----
a(h2("Crafting"))
a(p('A ring in the 3x3 grid, around any waist belt you already own:'))
a(recipe(["gear   twine  gear",
          "twine  belt   twine",
          "gear   twine  gear"]))
a(bullets([
    '<b>4x</b> temporal gear, in the corners',
    '<b>4x</b> flax twine, on the edges',
    '<b>1x</b> any waist belt, in the centre']))
a(p('The gears go in four separate cells because a temporal gear stacks to one, so a recipe '
    'asking for a stack of four could never be satisfied. Any vanilla belt works as the base '
    '&mdash; the plain leather one is the cheapest.'))
a(p('That gives you the <b>temporal</b> belt, which glows cyan. The other five colours come out '
    'of a barrel.'))

# ---- colours ----
a(h2("Six colours"))
a(p('Seal the belt in a barrel with <b>dye</b> for <b>4 hours</b>, the same way you dye cloth '
    'and daub. Pour the dye in by holding the bucket and right-clicking the barrel &mdash; '
    'liquid does not go in through the barrel window &mdash; then open the barrel and drop the '
    'belt into its item slot. Any amount from <b>1 litre</b> up works, and only 1 litre is '
    'spent, so a single bucket does the whole set:'))
a(bullets([
    '<b>Temporal</b> &mdash; cyan, the colour it is crafted at',
    '<b>Orange</b> &mdash; the exact colour of a lit torch',
    '<b>Red</b>',
    '<b>Yellow</b> &mdash; warm, close to a gas lamp',
    '<b>Blue</b> &mdash; a cool sky blue',
    '<b>White</b> &mdash; neutral; the one colour made from borax rather than a plant']))
a(p('Any colour re-dyes straight to any other, so you never have to pass back through temporal. '
    'Putting a <b>temporal gear</b> in the barrel in place of the dye fits the original lens back '
    'and returns it to cyan.'))
a(p('The light the belt casts always matches the lens you can see on the model, and the glow '
    'lands on you as well as on the ground around you.'))

# ---- wear ----
a(h2("Wear and repair"))
a(p('The belt is ordinary clothing. It wears down as you use it, gives 0.3&deg;C of warmth, and '
    'is mended the way any garment is &mdash; pick the material up on your cursor and click it '
    'onto the belt:'))
a(bullets([
    f'<b>Sewing kit</b> &mdash; {key("+75%")} condition',
    f'<b>Cloth or linen</b> &mdash; {key("+50%")}',
    f'<b>Flax twine</b> &mdash; {key("+10%")}']))
a(p('A trip through the dye barrel also mends it. Barrel crafting hands back a fresh item '
    'rather than carrying the old one across, so a belt comes out of a re-dye at full '
    'condition whatever state it went in at.'))
a(p('Condition only scales the warmth. A belt worn down to its last threads still lights at full '
    'strength.'))

# ---- how the light works ----
a(h2("How the light works"))
a(p('The belt is a moving point light, the same kind the game already gives a held torch. Nothing '
    'is baked into chunk lighting, so there is no relight cost as you walk and no bright patches '
    'left behind you.'))
a(p('It does not replace what is in your hands. A torch and the belt stack rather than cancelling '
    'each other, so you can throw light down a tunnel ahead while the belt covers your feet.'))
a(p('<b>Other players see it too</b>, provided the server has the mod. The light is published by '
    'the server and drawn by every client in range, so a lit belt reads across a multiplayer world '
    'rather than only to the person wearing it.'))

# ---- compatibility ----
a(h2("Compatibility"))
a(note("Needed on the server as well",
       f'This is <b>not a client-side mod</b>. It adds an item, and the server is what tells every '
       f'client that a belt is lit &mdash; so installing it only on your client will not work when '
       f'you join a multiplayer server. It has to be on the server too. In singleplayer, installing '
       f'it covers both.'))
a(p('No dependencies. Built and tested against Vintage Story 1.22.7. The belt is an ordinary item '
    'in an ordinary clothing slot, so adding or removing the mod disturbs nothing in a world beyond '
    'the belts themselves.'))
a(chips(["no dependencies", "client and server", "six colours",
         f"built for Vintage Story {GAME}"]))

# ---- footer + disclosure ----
a(f'<div style="margin-top:32px; padding-top:16px; border-top:1px solid {RULES};">')
a(f'<p style="font-family:{MONO}; font-size:0.74em; color:{INK3}; margin:0 0 12px;">'
  f'Lampwright v{VERSION} &middot; built for Vintage Story {GAME}</p>')
a(f'<p style="font-size:0.88em; line-height:1.7; color:{INK3}; margin:0;">'
  f'AI Disclosure: This mod was developed with the assistance of AI tools, and its full source code is '
  f'linked on this page for anyone who wants to review it. If AI-assisted content isn&#39;t for you, please '
  f'filter or skip this mod. The comment section is reserved for bug reports, compatibility questions, and '
  f'gameplay feedback.</p>')
a("</div>")
a("</div>")

fragment = "\n".join(H)

# Whitespace inside a style attribute is only there for the reader of this script, and it is
# counted twice over once the site's editor rewrites the page. Nothing outside style="..." is
# touched, so the prose keeps its own semicolons and colons.
fragment = re.sub(r'style="([^"]*)"',
                  lambda m: 'style="' + re.sub(r"\s*([:;])\s*", r"\1", m.group(1)).rstrip(";") + '"',
                  fragment)

here = os.path.dirname(os.path.abspath(__file__))

moddb = os.path.join(here, "lampwright-moddb.html")
with open(moddb, "w") as f:
    f.write(fragment)

page = os.path.join(here, "lampwright.html")
with open(page, "w") as f:
    f.write("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "<title>Lampwright</title>\n<!-- Generated by docs/build-moddb-description.py "
            "- do not edit; edit the script. -->\n</head>\n"
            f'<body style="margin:0; background:{PAPER};">\n' + fragment + "\n</body>\n</html>\n")

# What the site measures is this file after its editor has expanded every shorthand and turned
# every #hex into rgb(r, g, b). Estimate that here rather than finding out on upload.
decls = sum(len([d for d in s.split(";") if d.strip()])
            for s in re.findall(r'style="([^"]*)"', fragment))
hexes = len(re.findall(r"#[0-9A-Fa-f]{6}", fragment))
borders = len(re.findall(r"border[a-z-]*:[^;\"]+", fragment))
pasted = len(fragment) + decls * 3 + hexes * 11 + borders * 60

print(f"written {moddb} {len(fragment)} bytes ({len(fragment) / 1024:.1f}KB)")
print(f"written {page}")
print(f"estimated once pasted: ~{pasted / 1000:.0f}KB - the ModDB counts that, not the file")
if len(fragment) > BUDGET:
    print(f"WARNING: over the {BUDGET // 1024}KB budget by {(len(fragment) - BUDGET) / 1024:.1f}KB. "
          f"Drop a whole aside, never add a table.")
