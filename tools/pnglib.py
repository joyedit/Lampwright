"""Minimal pure-Python PNG read/write - no Pillow on this box.

Handles 8-bit non-interlaced PNGs in greyscale / RGB / palette / greyscale+alpha /
RGBA, which covers every texture Vintage Story ships. Returns and accepts flat
RGBA byte lists.
"""
import struct, zlib


def read_png(path):
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")

    idat, plte, trns, hdr = b"", None, None, None
    i = 8
    while i < len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        body = data[i + 8:i + 8 + ln]
        if typ == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", body)
        elif typ == b"IDAT":
            idat += body
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        i += 12 + ln

    w, h, bitdepth, colortype, _, _, interlace = hdr
    if bitdepth != 8 or interlace != 0:
        raise ValueError(f"{path}: only 8-bit non-interlaced PNGs supported")

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colortype]
    raw = zlib.decompress(idat)
    stride = w * channels

    # Undo the per-scanline filters (PNG spec 9.2).
    out = bytearray()
    prev = bytearray(stride)
    pos = 0
    for _ in range(h):
        ftype = raw[pos]; pos += 1
        line = bytearray(raw[pos:pos + stride]); pos += stride
        for x in range(stride):
            a = line[x - channels] if x >= channels else 0
            b = prev[x]
            c = prev[x - channels] if x >= channels else 0
            if ftype == 1:   line[x] = (line[x] + a) & 255
            elif ftype == 2: line[x] = (line[x] + b) & 255
            elif ftype == 3: line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out += line
        prev = line

    # Normalise everything to RGBA.
    px = bytearray(w * h * 4)
    for n in range(w * h):
        s = out[n * channels:(n + 1) * channels]
        if colortype == 0:   r = g = b = s[0]; a = 255
        elif colortype == 2: r, g, b = s; a = 255
        elif colortype == 3:
            r, g, b = plte[s[0] * 3:s[0] * 3 + 3]
            a = trns[s[0]] if trns and s[0] < len(trns) else 255
        elif colortype == 4: r = g = b = s[0]; a = s[1]
        else:                r, g, b, a = s
        px[n * 4:n * 4 + 4] = bytes((r, g, b, a))

    return w, h, px


def write_png(path, w, h, px):
    """px is a flat RGBA bytearray of w*h*4. Written unfiltered."""
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += px[y * w * 4:(y + 1) * w * 4]

    def chunk(typ, body):
        return (struct.pack(">I", len(body)) + typ + body
                + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF))

    open(path, "wb").write(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b""))


def average_rgb(path):
    """Alpha-weighted mean colour, for flat-shading a face in a preview."""
    w, h, px = read_png(path)
    tr = tg = tb = ta = 0
    for n in range(w * h):
        r, g, b, a = px[n * 4:n * 4 + 4]
        tr += r * a; tg += g * a; tb += b * a; ta += a
    if ta == 0:
        return (0, 0, 0)
    return (tr // ta, tg // ta, tb // ta)
