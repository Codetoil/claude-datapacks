#!/usr/bin/env python3
"""Render top-down maps of a generated world straight from its region files.

Usage: render_map.py <world_dir> <out_prefix> [--dimension minecraft:overworld] [--bounds X0 Z0 X1 Z1]
       [--min-y Y] [--height H] [--sea-level Y] [--generated DIR]

Writes <out_prefix>-terrain.png (surface blocks in their in-game map colors + hillshade),
-height.png (elevation tint with contours every 32 blocks) and -biomes.png, and prints terrain
statistics. Only fully generated chunks are drawn; everything else stays black. Needs Pillow.
The dimension's build height and sea level, the block map colors and the biome colors come from
the pack's generated reports (--generated, default ../datagen/generated; see dims.py, colors.py).
"""
import argparse
import os
import sys
from multiprocessing import Pool
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anvil  # noqa: E402
import colors  # noqa: E402
import dims  # noqa: E402

SEA_LEVEL = 63
WATERY = {"minecraft:water", "minecraft:bubble_column", "minecraft:kelp", "minecraft:kelp_plant",
          "minecraft:seagrass", "minecraft:tall_seagrass", "minecraft:ice"}
SEE_THROUGH_DEPTH = 64  # how far down to look past blocks without a map color


def state(entry):
    """(id, properties) of a palette entry. 26.1.2 states are {"Name", "Properties"}; 26.3 uses
    {"id", "properties"} and wraps plain strings in mixed palettes as {"": "..."}."""
    if isinstance(entry, dict):
        return entry.get("Name", entry.get("id", entry.get(""))) or "", entry.get("Properties", entry.get("properties"))
    return entry or "", None


def section_lookup(sec, key, idx, min_bits):
    st = sec.get(key)
    if not st:
        return None
    pal = st["palette"]
    data = st.get("data")
    if not data or len(pal) == 1:
        return pal[0]
    bits = max(min_bits, (len(pal) - 1).bit_length())
    per = 64 // bits
    word = data[idx // per] & 0xFFFFFFFFFFFFFFFF
    return pal[(word >> ((idx % per) * bits)) & ((1 << bits) - 1)]


def process_region(args):
    """Per column: (ground y, ocean-floor y, surface block id, biome id, map color or None)."""
    path, min_y, height, generated = args
    pal = colors.palette(generated)
    rx, rz = map(int, Path(path).name.split(".")[1:3])
    out = []
    hm_bits = height.bit_length()
    for lx_c, lz_c, c in anvil.read_region(path):
        if c.get("Status") != "minecraft:full":
            continue
        hms = c.get("Heightmaps", {})
        if "WORLD_SURFACE" not in hms or "OCEAN_FLOOR" not in hms:
            continue
        surf = anvil.unpack_longs(hms["WORLD_SURFACE"], hm_bits, 256)
        ground = anvil.unpack_longs(hms.get("MOTION_BLOCKING_NO_LEAVES", hms["WORLD_SURFACE"]), hm_bits, 256)
        floor = anvil.unpack_longs(hms["OCEAN_FLOOR"], hm_bits, 256)
        sections = {s["Y"]: s for s in c.get("sections", [])}
        cols = []
        for i in range(256):
            lx, lz = i & 15, i >> 4
            top = surf[i] - 1 + min_y
            flo = floor[i] - 1 + min_y
            blk = bio = ""
            color = None
            sec = sections.get(top >> 4)
            if sec is not None:
                ly = top & 15
                bio = state(section_lookup(sec, "biomes", (ly >> 2) * 16 + (lz >> 2) * 4 + (lx >> 2), 1))[0]
            # Like an in-game map, look down past blocks without a map color (glass, torches, air).
            for y in range(top, max(min_y, top - SEE_THROUGH_DEPTH) - 1, -1):
                sec = sections.get(y >> 4)
                if sec is None:
                    continue
                name, props = state(section_lookup(sec, "block_states", ((y & 15) * 16 + lz) * 16 + lx, 4))
                if not name:
                    continue
                if not blk:
                    blk = name
                color = pal.block(name, props)
                if color is not None:
                    blk = name
                    break
            cols.append((ground[i] - 1 + min_y, flo, blk, bio, color))
        out.append((rx * 32 + lx_c, rz * 32 + lz_c, cols))
    return out


def height_tint(y, water_depth):
    if water_depth > 0:
        t = min(water_depth / 60.0, 1.0)
        return (int(90 - 70 * t), int(150 - 115 * t), int(230 - 120 * t))
    s = SEA_LEVEL
    stops = [(s, (70, 140, 60)), (s + 37, (120, 170, 80)), (s + 77, (200, 190, 110)),
             (s + 127, (165, 120, 75)), (s + 187, (130, 110, 100)), (s + 257, (190, 190, 195)), (s + 317, (250, 250, 255))]
    if y <= stops[0][0]:
        return stops[0][1]
    for (y0, c0), (y1, c1) in zip(stops, stops[1:]):
        if y <= y1:
            t = (y - y0) / (y1 - y0)
            return tuple(int(a + (b - a) * t) for a, b in zip(c0, c1))
    return stops[-1][1]


def load_chunks(world, dimension, generated, min_y=None, height=None, sea_level=None, bounds=None):
    """Read every fully generated chunk (in bounds) of a dimension; sets SEA_LEVEL. Returns (chunks, min_y)."""
    global SEA_LEVEL
    info = dims.dimension_info(dimension, generated) if None in (min_y, height) else (min_y, height, sea_level)
    min_y = info[0] if min_y is None else min_y
    height = info[1] if height is None else height
    SEA_LEVEL = sea_level if sea_level is not None else (info[2] if info[2] is not None else 63)
    region_dir = dims.region_dir(world, dimension)
    jobs = [(str(p), min_y, height, generated) for p in sorted(region_dir.glob("r.*.mca"))]
    if bounds:
        bx0, bz0, bx1, bz1 = bounds

        def overlaps(path):
            rx, rz = map(int, Path(path).name.split(".")[1:3])
            return rx * 512 < bx1 and rx * 512 + 512 > bx0 and rz * 512 < bz1 and rz * 512 + 512 > bz0
        jobs = [j for j in jobs if overlaps(j[0])]
    if not jobs:
        raise SystemExit(f"no region files in {region_dir}")
    with Pool(min(len(jobs), os.cpu_count() or 4)) as pool:
        chunks = [ch for res in pool.map(process_region, jobs) for ch in res]
    if bounds:
        chunks = [ch for ch in chunks if bx0 <= ch[0] * 16 < bx1 and bz0 <= ch[1] * 16 < bz1]
    return chunks, min_y


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("world", type=Path)
    ap.add_argument("out_prefix")
    ap.add_argument("--dimension", default="minecraft:overworld")
    ap.add_argument("--min-y", type=int, help="default: from the dimension type")
    ap.add_argument("--height", type=int, help="default: from the dimension type")
    ap.add_argument("--sea-level", type=int, help="default: from the noise settings, else 63")
    ap.add_argument("--generated", type=Path, default=dims.DEFAULT_GENERATED)
    ap.add_argument("--bounds", type=int, nargs=4, metavar=("X0", "Z0", "X1", "Z1"),
                    help="only draw this block rectangle")
    args = ap.parse_args()

    chunks, _ = load_chunks(args.world, args.dimension, args.generated, args.min_y, args.height,
                            args.sea_level, args.bounds)
    if not chunks:
        raise SystemExit("no fully generated chunks found")
    pal = colors.palette(args.generated)

    cxs = [c[0] for c in chunks]
    czs = [c[1] for c in chunks]
    cx0, cz0 = min(cxs), min(czs)
    w, h = (max(cxs) - cx0 + 1) * 16, (max(czs) - cz0 + 1) * 16
    tops = [[None] * w for _ in range(h)]
    info = [[None] * w for _ in range(h)]
    for cx, cz, cols in chunks:
        bx, bz = (cx - cx0) * 16, (cz - cz0) * 16
        for i, col in enumerate(cols):
            x, z = bx + (i & 15), bz + (i >> 4)
            tops[z][x] = col[0]
            info[z][x] = col[1:]

    terrain = Image.new("RGB", (w, h))
    tint = Image.new("RGB", (w, h))
    biomes = Image.new("RGB", (w, h))
    tp, hp, bp = terrain.load(), tint.load(), biomes.load()
    land_heights = []
    ocean_depths = []
    high_water = 0
    best = (-10**9, 0, 0)
    for z in range(h):
        row, irow = tops[z], info[z]
        for x in range(w):
            top = row[x]
            if top is None:
                continue
            flo, blk, bio, color = irow[x]
            is_water = blk in WATERY
            depth = top - flo if is_water else 0
            surface = top
            if not is_water or blk == "minecraft:ice":
                if top > best[0]:
                    best = (top, x, z)
            if is_water and SEA_LEVEL - 1 <= top <= SEA_LEVEL:
                ocean_depths.append(depth)
            else:
                land_heights.append(top)
                if is_water and top > SEA_LEVEL + 37:
                    high_water += 1

            def hgt(xx, zz):
                if 0 <= xx < w and 0 <= zz < h and tops[zz][xx] is not None:
                    return tops[zz][xx]
                return surface
            slope = (hgt(x - 1, z) - hgt(x + 1, z)) + (hgt(x, z - 1) - hgt(x, z + 1))
            shade = max(0.55, min(1.4, 1.0 + 0.045 * slope)) if not (is_water and depth > 0) else 1.0
            base = color or (0, 0, 0)
            if is_water:
                t = min(depth / 50.0, 1.0)
                base = (int(base[0] * (1 - 0.6 * t)), int(base[1] * (1 - 0.55 * t)), int(base[2] * (1 - 0.35 * t)))
            tp[x, z] = tuple(min(255, int(c * shade)) for c in base)
            ht = height_tint(top, depth if is_water and top <= SEA_LEVEL else 0)
            contour = not is_water and (top // 32) != (hgt(x + 1, z) // 32) or (top // 32) != (hgt(x, z + 1) // 32)
            ht = tuple(min(255, int(c * shade * (0.75 if contour and not is_water else 1.0))) for c in ht)
            hp[x, z] = ht
            bp[x, z] = pal.biome(bio)

    terrain.save(f"{args.out_prefix}-terrain.png")
    tint.save(f"{args.out_prefix}-height.png")
    biomes.save(f"{args.out_prefix}-biomes.png")

    def pct(vals, p):
        vals = sorted(vals)
        return vals[min(len(vals) - 1, int(p / 100 * len(vals)))] if vals else None
    total = len(land_heights) + len(ocean_depths)
    print(f"area: {w}x{h} blocks, origin block x={cx0 * 16} z={cz0 * 16}, {len(chunks)} chunks, sea level {SEA_LEVEL}")
    print(f"ocean/sea-level water: {100 * len(ocean_depths) / total:.1f}% of columns; depth p50={pct(ocean_depths, 50)} p90={pct(ocean_depths, 90)} max={max(ocean_depths) if ocean_depths else None}")
    print(f"land surface y: p10={pct(land_heights, 10)} p50={pct(land_heights, 50)} p90={pct(land_heights, 90)} p99={pct(land_heights, 99)} max={best[0]} at x={cx0 * 16 + best[1]} z={cz0 * 16 + best[2]}")
    print(f"water columns more than 37 blocks above sea level (lakes, waterfalls): {high_water}")
    hist = {}
    for v in land_heights:
        hist[v // 32 * 32] = hist.get(v // 32 * 32, 0) + 1
    print("land height histogram (32-block bins):", ", ".join(f"{k}:{100 * n / total:.1f}%" for k, n in sorted(hist.items())))


if __name__ == "__main__":
    main()
