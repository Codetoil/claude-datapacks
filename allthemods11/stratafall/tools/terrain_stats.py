#!/usr/bin/env python3
"""Terrain statistics for comparing worldgen iterations, straight from region files.

Usage: terrain_stats.py <world_dir> [--bounds X0 Z0 X1 Z1] [--json OUT] [--cliff-png OUT]

Per surface column it takes the top solid, non-leaf block (MOTION_BLOCKING_NO_LEAVES heightmap) and the
slope = max - min of the ground heights of the 4 neighbours (x+-1, z+-1), the same measure as the
lithostitched:slope surface condition but without its chunk-edge clamping. Prints:
- slope distribution, and for slope classes the share of each surface material group (soil, snow, rock, ...)
- water above sea level (lakes, springs, waterfalls) and lava above sea level
- block counts of selected decoration blocks found on the surface
--cliff-png draws steep columns (slope >= 5) coloured by material group over a grey hillshade.
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import anvil  # noqa: E402
import dims  # noqa: E402
from render_map import section_lookup, state  # noqa: E402

GROUPS = [
    ("water", ("water", "bubble_column", "kelp", "seagrass")),
    ("ice", ("ice", "packed_ice", "blue_ice")),
    ("lava", ("lava", "magma")),
    ("snow", ("snow", "powder_snow")),
    ("soil", ("grass_block", "dirt", "podzol", "mycelium", "rooted_dirt", "mud", "moss_block", "coarse_dirt",
              "farmland", "dirt_path", "clay", "pale_moss_block", "_grass_block", "_dirt", "_soil", "_podzol")),
    ("sand", ("sand", "sandstone", "suspicious_sand")),
    ("gravel", ("gravel",)),
    ("terracotta", ("terracotta",)),
    ("rock", ("stone", "andesite", "diorite", "granite", "tuff", "calcite", "deepslate", "basalt", "blackstone",
              "cobblestone", "dripstone", "obsidian", "chalk", "marble", "limestone", "slate", "shale", "argillite",
              "bedrock", "smooth_basalt", "mossy_cobblestone", "prismarine", "quartz")),
]


def group(block):
    name = block.split(":", 1)[-1]
    for g, keys in GROUPS:
        for k in keys:
            if (k.startswith("_") and name.endswith(k)) or name == k or (not k.startswith("_") and k in name):
                return g
    return "other"


def process_region(args):
    path, min_y, height, bounds = args
    rx, rz = map(int, Path(path).name.split(".")[1:3])
    out = []
    bits = height.bit_length()
    for lx_c, lz_c, c in anvil.read_region(path):
        if c.get("Status") != "minecraft:full":
            continue
        cx, cz = rx * 32 + lx_c, rz * 32 + lz_c
        if bounds and not (bounds[0] <= cx * 16 < bounds[2] and bounds[1] <= cz * 16 < bounds[3]):
            continue
        hms = c.get("Heightmaps", {})
        if "MOTION_BLOCKING_NO_LEAVES" not in hms:
            continue
        ground = anvil.unpack_longs(hms["MOTION_BLOCKING_NO_LEAVES"], bits, 256)
        sections = {s["Y"]: s for s in c.get("sections", [])}
        cols = []
        def block_at(lx, y, lz):
            sec = sections.get(y >> 4)
            if sec is None:
                return ""
            return state(section_lookup(sec, "block_states", ((y & 15) * 16 + lz) * 16 + lx, 4))[0]
        for i in range(256):
            lx, lz = i & 15, i >> 4
            y = ground[i] - 1 + min_y
            blk = block_at(lx, y, lz)
            # Step down past trees, plants, structures' wood etc. to the terrain block (at most 48 blocks).
            for _ in range(48):
                if group(blk) != "other" or y <= min_y:
                    break
                y -= 1
                blk = block_at(lx, y, lz)
            above = block_at(lx, y + 1, lz)
            sec = sections.get(y >> 4)
            bio = ""
            if sec is not None:
                bio = state(section_lookup(sec, "biomes", ((y & 15) >> 2) * 16 + (lz >> 2) * 4 + (lx >> 2), 1))[0]
            cols.append((y, blk, above, bio))
        # Fluids and ice high up anywhere in the chunk (springs and their falls, lakes, aquifers, glaciers).
        src = flow = 0
        extra = Counter()
        targets = {"minecraft:water", "minecraft:lava", "minecraft:packed_ice", "minecraft:blue_ice"}
        for sy, sec in sections.items():
            if sy * 16 + 15 < 64:
                continue
            st = sec.get("block_states")
            if not st:
                continue
            pal = st["palette"]
            if not any(state(e)[0] in targets for e in pal):
                continue
            for idx in range(4096):
                yy = sy * 16 + (idx >> 8)
                if yy < 64:
                    continue
                n, props = state(section_lookup(sec, "block_states", idx, 4))
                if n == "minecraft:water" and yy >= 72:
                    if (props or {}).get("level", "0") == "0":
                        src += 1
                    else:
                        flow += 1
                elif n == "minecraft:lava":
                    extra["lava_y64"] += 1
                elif n in ("minecraft:packed_ice", "minecraft:blue_ice") and yy >= 80:
                    extra[n.split(":")[1] + "_y80"] += 1
        out.append((cx, cz, cols, src, flow, extra))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("world", type=Path)
    ap.add_argument("--bounds", type=int, nargs=4)
    ap.add_argument("--json")
    ap.add_argument("--cliff-png")
    ap.add_argument("--sea-level", type=int, default=63)
    args = ap.parse_args()
    min_y, height, _ = dims.dimension_info("minecraft:overworld", dims.DEFAULT_GENERATED)
    region_dir = dims.region_dir(args.world, "minecraft:overworld")
    jobs = []
    for p in sorted(region_dir.glob("r.*.mca")):
        rx, rz = map(int, p.name.split(".")[1:3])
        if args.bounds:
            b = args.bounds
            if not (rx * 512 < b[2] and rx * 512 + 512 > b[0] and rz * 512 < b[3] and rz * 512 + 512 > b[1]):
                continue
        jobs.append((str(p), min_y, height, args.bounds))
    with Pool(min(len(jobs), os.cpu_count() or 4)) as pool:
        chunks = [ch for res in pool.map(process_region, jobs) for ch in res]
    if not chunks:
        raise SystemExit("no chunks")
    w_src = sum(c[3] for c in chunks)
    w_flow = sum(c[4] for c in chunks)
    cols = {}
    extras = Counter()
    for ch in chunks:
        extras.update(ch[5])
    for cx, cz, cl, *_ in chunks:
        for i, col in enumerate(cl):
            cols[(cx * 16 + (i & 15), cz * 16 + (i >> 4))] = col
    slope_hist = Counter()
    by_class = defaultdict(Counter)
    by_class_biome = defaultdict(Counter)
    high_water = high_lava = 0
    surface_blocks = Counter()
    land = 0
    for (x, z), (y, blk, above, bio) in cols.items():
        hs = [cols[n][0] for n in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)) if n in cols]
        if len(hs) < 4:
            continue
        s = max(hs) - min(hs)
        g = group(blk)
        if g in ("water", "ice") and y <= args.sea_level:
            continue  # sea / ocean surface (frozen or not)
        if "ocean" in bio:
            continue  # icebergs and sea stacks are not land terrain
        land += 1
        capped = above.endswith(":snow")  # snow layer on top: counted separately, the terrain block decides the group
        surface_blocks[blk] += 1
        if g == "water":
            high_water += 1
        if g == "lava" and y > args.sea_level:
            high_lava += 1
        slope_hist[min(s, 30)] += 1
        cls = "flat(0-1)" if s <= 1 else "gentle(2-3)" if s <= 3 else "steep(4-6)" if s <= 6 else "cliff(7-12)" if s <= 12 else "sheer(13+)"
        by_class[cls][g] += 1
        if capped:
            by_class[cls]["(snow-capped)"] += 1
        if s >= 7:
            by_class_biome[bio][g] += 1
    res = {"chunks": len(chunks), "land_columns": land, "high_water_columns": high_water, "high_lava_columns": high_lava,
           "water_sources_y72": w_src, "water_flowing_y72": w_flow, **dict(extras)}
    print(f"water blocks at y>=72: {w_src} sources, {w_flow} flowing ({w_src / len(chunks):.2f} sources per chunk); "
          f"lava y>=64: {extras['lava_y64']}; packed ice y>=80: {extras['packed_ice_y80']}, blue ice y>=80: {extras['blue_ice_y80']}")
    print(f"chunks {len(chunks)}, land/above-sea columns {land}, water above sea level {high_water} ({1e4 * high_water / max(land, 1):.1f} per 10k), lava above sea level {high_lava}")
    tot = sum(slope_hist.values())
    cum = 0
    line = []
    for k in (2, 4, 5, 7, 10, 13, 20):
        n = sum(v for s, v in slope_hist.items() if s >= k)
        line.append(f">={k}: {100 * n / tot:.1f}%")
    print("slope share:", ", ".join(line))
    res["slope_ge"] = {k: sum(v for s, v in slope_hist.items() if s >= k) / tot for k in (2, 4, 5, 7, 10, 13, 20)}
    res["classes"] = {}
    for cls in ("flat(0-1)", "gentle(2-3)", "steep(4-6)", "cliff(7-12)", "sheer(13+)"):
        c = by_class[cls]
        n = sum(v for g, v in c.items() if not g.startswith("("))
        if not n:
            continue
        parts = ", ".join(f"{g} {100 * v / n:.0f}%" for g, v in c.most_common(8))
        print(f"  {cls:12s} n={n:7d}: {parts}")
        res["classes"][cls] = {g: v / n for g, v in c.items()} | {"n": n}
    worst = sorted(((sum(c.values()), b, c) for b, c in by_class_biome.items()), reverse=True)[:12]
    print("cliff columns (slope>=7) by biome, top 12:")
    for n, b, c in worst:
        soil = (c["soil"] + c["snow"] + c["sand"]) / n
        print(f"  {b:40s} n={n:6d} soil/snow/sand {100 * soil:4.0f}% rock {100 * c['rock'] / n:4.0f}% other {100 * (c['other'] + c['terracotta'] + c['gravel'] + c['ice']) / n:4.0f}%")
    res["cliff_biomes"] = {b: dict(c) for n, b, c in worst}
    print("top surface blocks:", ", ".join(f"{b.split(':')[-1]} {100 * v / land:.1f}%" for b, v in surface_blocks.most_common(14)))
    res["surface_blocks"] = dict(surface_blocks.most_common(60))
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=1))
    if args.cliff_png:
        from PIL import Image
        xs = [k[0] for k in cols]
        zs = [k[1] for k in cols]
        x0, z0 = min(xs), min(zs)
        w, h = max(xs) - x0 + 1, max(zs) - z0 + 1
        img = Image.new("RGB", (w, h))
        px = img.load()
        colmap = {"soil": (60, 170, 60), "snow": (250, 250, 255), "sand": (230, 210, 140), "rock": (150, 120, 220),
                  "gravel": (120, 120, 120), "terracotta": (200, 110, 70), "ice": (140, 200, 255), "water": (40, 90, 230),
                  "lava": (255, 90, 0), "other": (255, 0, 200)}
        for (x, z), (y, blk, above, bio) in cols.items():
            hs = [cols[n][0] for n in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)) if n in cols]
            if len(hs) < 4:
                continue
            s = max(hs) - min(hs)
            shade = max(40, min(200, 110 + 3 * ((cols.get((x - 1, z), (y,))[0]) - y)))
            g = group(blk)
            if g in ("water", "ice") and y <= args.sea_level:
                px[x - x0, z - z0] = (20, 40, 90)
            elif s >= 5:
                px[x - x0, z - z0] = colmap[g]
            else:
                px[x - x0, z - z0] = (shade, shade, shade)
        img.save(args.cliff_png)


if __name__ == "__main__":
    main()
