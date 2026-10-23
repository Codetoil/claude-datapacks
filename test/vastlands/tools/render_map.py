#!/usr/bin/env python3
"""Render top-down maps of a generated world straight from its region files.

Usage: render_map.py <world_dir> <out_prefix> [--min-y -64] [--height 512] [--dimension minecraft/overworld]

Writes <out_prefix>-terrain.png (surface blocks + hillshade), -height.png (elevation tint with
contours every 32 blocks) and -biomes.png, and prints terrain statistics. Only fully generated
chunks are drawn; everything else stays black. Needs Pillow for PNG output.
"""
import argparse
import math
import os
import sys
from multiprocessing import Pool
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anvil  # noqa: E402

SEA_LEVEL = 63

BLOCK_COLORS = {
    "water": (52, 96, 196), "bubble_column": (52, 96, 196), "kelp_plant": (52, 96, 196), "kelp": (52, 96, 196),
    "seagrass": (52, 96, 196), "tall_seagrass": (52, 96, 196), "lily_pad": (40, 120, 40),
    "lava": (230, 100, 20), "magma_block": (140, 60, 20),
    "grass_block": (98, 150, 60), "short_grass": (98, 150, 60), "tall_grass": (98, 150, 60), "fern": (80, 135, 55),
    "large_fern": (80, 135, 55), "dirt": (134, 96, 67), "coarse_dirt": (119, 85, 59), "rooted_dirt": (134, 96, 67),
    "podzol": (106, 76, 44), "mycelium": (111, 99, 105), "mud": (60, 57, 60), "muddy_mangrove_roots": (70, 60, 50),
    "moss_block": (89, 110, 44), "moss_carpet": (89, 110, 44), "pale_moss_block": (110, 116, 104), "pale_moss_carpet": (110, 116, 104),
    "sand": (219, 207, 163), "sandstone": (216, 203, 155), "red_sand": (190, 102, 33), "red_sandstone": (186, 99, 29),
    "gravel": (131, 127, 126), "clay": (160, 166, 179), "suspicious_sand": (219, 207, 163), "suspicious_gravel": (131, 127, 126),
    "stone": (125, 125, 125), "andesite": (136, 136, 137), "diorite": (188, 188, 189), "granite": (149, 103, 85),
    "deepslate": (80, 80, 82), "tuff": (108, 109, 102), "calcite": (223, 224, 220), "dripstone_block": (134, 107, 92),
    "pointed_dripstone": (134, 107, 92), "cobblestone": (127, 127, 127), "mossy_cobblestone": (110, 118, 94),
    "snow": (240, 245, 250), "snow_block": (240, 245, 250), "powder_snow": (245, 248, 252),
    "ice": (145, 183, 253), "packed_ice": (141, 180, 250), "blue_ice": (116, 167, 253),
    "terracotta": (152, 94, 67), "white_terracotta": (209, 178, 161), "orange_terracotta": (161, 83, 37),
    "yellow_terracotta": (186, 133, 35), "brown_terracotta": (77, 51, 35), "red_terracotta": (143, 61, 46),
    "light_gray_terracotta": (135, 106, 97), "obsidian": (20, 18, 30), "bedrock": (85, 85, 85),
    "cactus": (85, 127, 43), "dead_bush": (148, 109, 52), "sugar_cane": (148, 192, 101), "bamboo": (93, 144, 19),
    "pumpkin": (198, 118, 24), "melon": (111, 145, 30), "sweet_berry_bush": (60, 100, 50),
}
LEAF_COLORS = {
    "oak": (60, 110, 40), "dark_oak": (45, 85, 30), "birch": (110, 150, 70), "spruce": (50, 85, 55),
    "jungle": (45, 125, 30), "acacia": (95, 130, 40), "mangrove": (70, 120, 40), "cherry": (230, 170, 200),
    "azalea": (90, 120, 40), "flowering_azalea": (130, 120, 90), "pale_oak": (150, 155, 145),
}
BIOME_COLORS = {
    "ocean": (0, 0, 112), "deep_ocean": (0, 0, 48), "warm_ocean": (0, 0, 172), "lukewarm_ocean": (0, 0, 144),
    "deep_lukewarm_ocean": (0, 0, 64), "cold_ocean": (32, 32, 112), "deep_cold_ocean": (32, 32, 56),
    "frozen_ocean": (112, 112, 214), "deep_frozen_ocean": (64, 64, 144), "river": (0, 0, 255), "frozen_river": (160, 160, 255),
    "beach": (250, 222, 85), "snowy_beach": (250, 240, 192), "stony_shore": (162, 162, 132),
    "plains": (141, 179, 96), "sunflower_plains": (181, 219, 136), "snowy_plains": (255, 255, 255), "ice_spikes": (180, 220, 220),
    "desert": (250, 148, 24), "swamp": (7, 249, 178), "mangrove_swamp": (44, 204, 142),
    "forest": (5, 102, 33), "flower_forest": (45, 142, 73), "birch_forest": (48, 116, 68), "dark_forest": (64, 81, 26),
    "old_growth_birch_forest": (88, 156, 108), "pale_garden": (160, 168, 150), "dappled_forest": (70, 130, 50),
    "taiga": (11, 102, 89), "snowy_taiga": (49, 85, 74), "old_growth_pine_taiga": (89, 102, 81), "old_growth_spruce_taiga": (129, 142, 121),
    "savanna": (189, 178, 95), "savanna_plateau": (167, 157, 100), "windswept_savanna": (229, 218, 135),
    "jungle": (83, 123, 9), "sparse_jungle": (98, 139, 23), "bamboo_jungle": (118, 142, 20),
    "badlands": (217, 69, 21), "eroded_badlands": (255, 109, 61), "wooded_badlands": (176, 151, 101),
    "meadow": (131, 187, 109), "cherry_grove": (255, 160, 220), "grove": (160, 210, 190), "snowy_slopes": (210, 225, 240),
    "frozen_peaks": (160, 190, 255), "jagged_peaks": (220, 220, 230), "stony_peaks": (123, 143, 116),
    "windswept_hills": (96, 96, 96), "windswept_gravelly_hills": (136, 136, 136), "windswept_forest": (88, 106, 88),
    "mushroom_fields": (255, 0, 255), "dripstone_caves": (130, 90, 60), "lush_caves": (40, 200, 40),
    "deep_dark": (10, 30, 40), "sulfur_caves": (200, 200, 40),
}


def short(name):
    if isinstance(name, dict):
        # 26.x states are {"id", "properties"}; mixed palettes wrap plain strings as {"": "..."}.
        name = name.get("id", name.get("Name", name.get("", "")))
    name = name.split("[", 1)[0]
    return name.split(":", 1)[-1]


def block_color(name):
    if name in BLOCK_COLORS:
        return BLOCK_COLORS[name]
    if name.endswith("_leaves"):
        return LEAF_COLORS.get(name[:-7], (60, 110, 40))
    if name.endswith(("_log", "_wood", "_stem")):
        return (100, 80, 50)
    if name.endswith("_terracotta"):
        return (150, 95, 70)
    if any(k in name for k in ("flower", "tulip", "poppy", "dandelion", "orchid", "allium", "bluet", "daisy", "cornflower", "lily", "rose", "petals")):
        return (98, 150, 60)
    h = hash(name) & 0xFFFFFF
    return (96 + (h & 63), 96 + ((h >> 6) & 63), 96 + ((h >> 12) & 63))


def biome_color(name):
    return BIOME_COLORS.get(name, (128, 128, 128))


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
    path, min_y, height = args
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
            sec = sections.get(top >> 4)
            blk = bio = ""
            if sec is not None:
                ly = top & 15
                blk = short(section_lookup(sec, "block_states", (ly * 16 + lz) * 16 + lx, 4) or "")
                bio = short(section_lookup(sec, "biomes", (ly >> 2) * 16 + (lz >> 2) * 4 + (lx >> 2), 1) or "")
            cols.append((ground[i] - 1 + min_y, flo, blk, bio))
        out.append((rx * 32 + lx_c, rz * 32 + lz_c, cols))
    return out


def height_tint(y, water_depth):
    if water_depth > 0:
        t = min(water_depth / 60.0, 1.0)
        return (int(90 - 70 * t), int(150 - 115 * t), int(230 - 120 * t))
    stops = [(SEA_LEVEL, (70, 140, 60)), (100, (120, 170, 80)), (140, (200, 190, 110)),
             (190, (165, 120, 75)), (250, (130, 110, 100)), (320, (190, 190, 195)), (380, (250, 250, 255))]
    if y <= stops[0][0]:
        return stops[0][1]
    for (y0, c0), (y1, c1) in zip(stops, stops[1:]):
        if y <= y1:
            t = (y - y0) / (y1 - y0)
            return tuple(int(a + (b - a) * t) for a, b in zip(c0, c1))
    return stops[-1][1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("world", type=Path)
    ap.add_argument("out_prefix")
    ap.add_argument("--min-y", type=int, default=-64)
    ap.add_argument("--height", type=int, default=512)
    ap.add_argument("--dimension", default="minecraft/overworld")
    ap.add_argument("--bounds", type=int, nargs=4, metavar=("X0", "Z0", "X1", "Z1"),
                    help="only draw this block rectangle")
    args = ap.parse_args()

    region_dir = args.world / "dimensions" / args.dimension / "region"
    if not region_dir.is_dir():
        region_dir = args.world / "region"
    jobs = [(str(p), args.min_y, args.height) for p in sorted(region_dir.glob("r.*.mca"))]
    if args.bounds:
        bx0, bz0, bx1, bz1 = args.bounds
        def overlaps(path):
            rx, rz = map(int, Path(path).name.split(".")[1:3])
            return rx * 512 < bx1 and rx * 512 + 512 > bx0 and rz * 512 < bz1 and rz * 512 + 512 > bz0
        jobs = [j for j in jobs if overlaps(j[0])]
    with Pool(min(len(jobs), os.cpu_count() or 4) or 1) as pool:
        chunks = [ch for res in pool.map(process_region, jobs) for ch in res]
    if args.bounds:
        chunks = [ch for ch in chunks if bx0 <= ch[0] * 16 < bx1 and bz0 <= ch[1] * 16 < bz1]
    if not chunks:
        raise SystemExit("no fully generated chunks found")

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
            top, flo, blk, bio = col
            tops[z][x] = top
            info[z][x] = (flo, blk, bio)

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
            flo, blk, bio = irow[x]
            is_water = blk in ("water", "bubble_column", "kelp", "kelp_plant", "seagrass", "tall_seagrass", "ice")
            depth = top - flo if is_water else 0
            surface = top
            if not is_water or blk == "ice":
                if top > best[0]:
                    best = (top, x, z)
            if is_water and top >= SEA_LEVEL - 1 and top <= SEA_LEVEL:
                ocean_depths.append(depth)
            else:
                land_heights.append(top)
                if is_water and top > 100:
                    high_water += 1

            def hgt(xx, zz):
                if 0 <= xx < w and 0 <= zz < h and tops[zz][xx] is not None:
                    return tops[zz][xx]
                return surface
            slope = (hgt(x - 1, z) - hgt(x + 1, z)) + (hgt(x, z - 1) - hgt(x, z + 1))
            shade = max(0.55, min(1.4, 1.0 + 0.045 * slope)) if not (is_water and depth > 0) else 1.0
            base = block_color(blk)
            if is_water:
                t = min(depth / 50.0, 1.0)
                base = (int(base[0] * (1 - 0.6 * t)), int(base[1] * (1 - 0.55 * t)), int(base[2] * (1 - 0.35 * t)))
            tp[x, z] = tuple(min(255, int(c * shade)) for c in base)
            ht = height_tint(top, depth if is_water and top <= SEA_LEVEL else 0)
            contour = not is_water and (top // 32) != (hgt(x + 1, z) // 32) or (top // 32) != (hgt(x, z + 1) // 32)
            ht = tuple(min(255, int(c * shade * (0.75 if contour and not is_water else 1.0))) for c in ht)
            hp[x, z] = ht
            bp[x, z] = biome_color(bio)

    terrain.save(f"{args.out_prefix}-terrain.png")
    tint.save(f"{args.out_prefix}-height.png")
    biomes.save(f"{args.out_prefix}-biomes.png")

    def pct(vals, p):
        vals = sorted(vals)
        return vals[min(len(vals) - 1, int(p / 100 * len(vals)))] if vals else None
    total = len(land_heights) + len(ocean_depths)
    print(f"area: {w}x{h} blocks, origin block x={cx0 * 16} z={cz0 * 16}, {len(chunks)} chunks")
    print(f"ocean/sea-level water: {100 * len(ocean_depths) / total:.1f}% of columns; depth p50={pct(ocean_depths, 50)} p90={pct(ocean_depths, 90)} max={max(ocean_depths) if ocean_depths else None}")
    print(f"land surface y: p10={pct(land_heights, 10)} p50={pct(land_heights, 50)} p90={pct(land_heights, 90)} p99={pct(land_heights, 99)} max={best[0]} at x={cx0 * 16 + best[1]} z={cz0 * 16 + best[2]}")
    print(f"water columns above y=100 (lakes, waterfalls): {high_water}")
    hist = {}
    for v in land_heights:
        hist[v // 32 * 32] = hist.get(v // 32 * 32, 0) + 1
    print("land height histogram (32-block bins):", ", ".join(f"{k}:{100 * n / total:.1f}%" for k, n in sorted(hist.items())))


if __name__ == "__main__":
    main()
