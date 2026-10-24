#!/usr/bin/env python3
"""Oblique view looking north that colours every exposed south-facing block by its own block, so cliff strata show.

Usage: face_view.py <world_dir> <out.png> <center_x> <center_z> <size> [--scale 2] [--tilt 0.5] [--exaggeration 1]

Unlike render_view.py (which paints a whole column in its top block's map colour) each pixel row of a face is the
block at that height. Colours approximate the block textures for common terrain blocks and fall back to the map
colours from the pack's reports.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import anvil  # noqa: E402
import colors  # noqa: E402
import dims  # noqa: E402
from render_map import section_lookup, state  # noqa: E402

TEX = {
    "stone": (125, 125, 125), "andesite": (136, 136, 137), "granite": (154, 106, 89), "diorite": (189, 188, 189),
    "tuff": (108, 109, 102), "calcite": (223, 224, 220), "deepslate": (80, 80, 83), "cobbled_deepslate": (77, 77, 80),
    "dripstone_block": (134, 107, 92), "moss_block": (89, 109, 45), "packed_mud": (142, 106, 79),
    "sandstone": (216, 203, 155), "smooth_sandstone": (223, 214, 170), "red_sandstone": (186, 99, 29),
    "terracotta": (152, 94, 67), "orange_terracotta": (161, 83, 37), "white_terracotta": (209, 178, 161),
    "brown_terracotta": (77, 51, 35), "light_gray_terracotta": (135, 107, 98), "red_terracotta": (143, 61, 46),
    "yellow_terracotta": (186, 133, 35), "snow_block": (249, 254, 254), "snow": (249, 254, 254),
    "powder_snow": (248, 253, 253), "packed_ice": (178, 214, 255), "ice": (190, 222, 255), "blue_ice": (120, 190, 255),
    "dirt": (134, 96, 67), "coarse_dirt": (119, 85, 59), "grass_block": (98, 150, 60), "podzol": (91, 63, 24),
    "gravel": (131, 127, 126), "cobblestone": (127, 127, 127), "mossy_cobblestone": (110, 118, 94),
    "sand": (219, 207, 163), "red_sand": (190, 102, 33), "clay": (160, 166, 179), "mud": (60, 57, 61),
    "water": (38, 82, 205), "lava": (225, 95, 15), "smooth_basalt": (72, 72, 78), "basalt": (80, 81, 86),
    "blackstone": (42, 36, 41), "obsidian": (15, 10, 24), "bedrock": (85, 85, 85),
}
SKY = (160, 195, 235)
THIN = {"snow", "short_grass", "tall_grass", "fern", "large_fern", "moss_carpet", "pale_moss_carpet", "leaf_litter",
        "pink_petals", "wildflowers", "dead_bush", "short_dry_grass", "tall_dry_grass", "bush", "firefly_bush"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("world", type=Path)
    ap.add_argument("out")
    ap.add_argument("cx", type=int)
    ap.add_argument("cz", type=int)
    ap.add_argument("size", type=int)
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--tilt", type=float, default=0.5)
    ap.add_argument("--exaggeration", type=float, default=1.0)
    ap.add_argument("--facing", choices=["north", "south", "east", "west"], default="north",
                    help="direction the viewer looks in; the faces shown are the ones turned the other way")
    args = ap.parse_args()
    min_y, height, _ = dims.dimension_info("minecraft:overworld", dims.DEFAULT_GENERATED)
    pal = colors.palette(dims.DEFAULT_GENERATED)
    n = args.size
    x0, z0 = args.cx - n // 2, args.cz - n // 2
    region_dir = dims.region_dir(args.world, "minecraft:overworld")
    chunks = {}
    for rx in range(x0 >> 9, ((x0 + n) >> 9) + 1):
        for rz in range(z0 >> 9, ((z0 + n) >> 9) + 1):
            p = region_dir / f"r.{rx}.{rz}.mca"
            if not p.exists():
                continue
            for lx, lz, c in anvil.read_region(str(p)):
                if c.get("Status") == "minecraft:full":
                    chunks[(rx * 32 + lx, rz * 32 + lz)] = c
    bits = height.bit_length()
    cache = {}

    def column(x, z):
        key = (x, z)
        if key in cache:
            return cache[key]
        c = chunks.get((x >> 4, z >> 4))
        if c is None:
            cache[key] = None
            return None
        if "_sec" not in c:
            c["_sec"] = {s["Y"]: s for s in c.get("sections", [])}
            c["_ws"] = anvil.unpack_longs(c["Heightmaps"]["WORLD_SURFACE"], bits, 256)
        lx, lz = x & 15, z & 15
        top = c["_ws"][lz * 16 + lx] - 1 + min_y
        cache[key] = (c, lx, lz, top)
        return cache[key]

    def block(col, y):
        c, lx, lz, _ = col
        sec = c["_sec"].get(y >> 4)
        if sec is None:
            return "minecraft:air", None
        return state(section_lookup(sec, "block_states", ((y & 15) * 16 + lz) * 16 + lx, 4))

    def colour(name, props):
        short = name.split(":", 1)[-1]
        if short in TEX:
            return TEX[short]
        mc = pal.block(name, props)
        return mc if mc else None

    # screen column i (left to right), row j (back to front) -> world x, z; and the step toward the viewer
    def world(i, j):
        return {"north": (x0 + i, z0 + j), "south": (x0 + n - 1 - i, z0 + n - 1 - j),
                "east": (x0 + n - 1 - j, z0 + i), "west": (x0 + j, z0 + n - 1 - i)}[args.facing]
    step = {"north": (0, 1), "south": (0, -1), "east": (-1, 0), "west": (1, 0)}[args.facing]

    tops = []
    for j in range(n):
        for i in range(n):
            col = column(*world(i, j))
            if col:
                tops.append(col[3])
    if not tops:
        raise SystemExit("nothing generated there")
    lo, hi = min(tops), max(tops)
    s, ex, tilt = args.scale, args.exaggeration, args.tilt
    w = n * s
    h = int((n * tilt + (hi - lo) * ex) * s) + 40
    img = Image.new("RGB", (w, h), SKY)
    px = img.load()
    base = h - 10
    for z in range(n):
        fog = 0.35 * (1 - z / n)
        for x in range(n):
            wx, wz = world(x, z)
            col = column(wx, wz)
            if not col:
                continue
            top = col[3]
            front = column(wx + step[0], wz + step[1])
            front_top = front[3] if front else top - 1
            name, props = block(col, top)
            c = colour(name, props) or (0, 0, 0)
            face_top = top
            if name.split(":")[-1] in THIN:
                face_top = top - 1  # snow layers, carpets, plants: part of the top face, not a block of the cliff
            # top face
            ys = base - (n - 1 - z) * tilt * s - (top - lo) * ex * s
            for yy in range(int(ys), int(ys + tilt * s + 1)):
                for xx in range(x * s, x * s + s):
                    if 0 <= yy < h:
                        px[xx, yy] = tuple(int(v * (1 - fog) + k * fog) for v, k in zip(c, SKY))
            # south face, block by block, down to the top of the column in front
            for y in range(face_top, front_top, -1):
                bn, bp = block(col, y)
                if bn in ("minecraft:air", "minecraft:cave_air"):
                    continue
                bc = colour(bn, bp)
                if bc is None:
                    continue
                bc = tuple(int(v * 0.8) for v in bc)
                bc = tuple(int(v * (1 - fog) + k * fog) for v, k in zip(bc, SKY))
                y_top = base - (n - 1 - z) * tilt * s - (y - lo) * ex * s + tilt * s
                for yy in range(int(y_top), int(y_top + ex * s + 1)):
                    if 0 <= yy < h:
                        for xx in range(x * s, x * s + s):
                            px[xx, yy] = bc
    img.save(args.out)
    print(f"{args.out}: {w}x{h}, heights {lo}..{hi}")


if __name__ == "__main__":
    main()
