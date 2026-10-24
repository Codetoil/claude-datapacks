#!/usr/bin/env python3
"""Diagnose cliff springs: count positions where Stratafall's water-fall rules would allow a spring, and the water
sources actually embedded in cliff faces (water source with exactly one open side, rock above and below).

Usage: spring_sites.py <world> <x0> <z0> <x1> <z1> [--depth 2 12] [--drop 3]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import anvil  # noqa: E402
import dims  # noqa: E402
from render_map import section_lookup, state  # noqa: E402

PACK = Path(__file__).resolve().parents[1] / "pack/data/stratafall"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("world")
    ap.add_argument("bounds", type=int, nargs=4)
    ap.add_argument("--depth", type=int, nargs=2, default=(2, 12))
    ap.add_argument("--drop", type=int, default=3)
    args = ap.parse_args()
    x0, z0, x1, z1 = args.bounds
    valid = set(json.loads((PACK / "worldgen/configured_feature/water_fall.json").read_text())["config"]["valid_blocks"])
    water_biomes = set()
    for k in ("water_high", "water_low"):
        for v in json.loads((PACK / f"tags/worldgen/biome/falls/{k}.json").read_text())["values"]:
            water_biomes.add(v if isinstance(v, str) else v["id"])
    min_y, height, _ = dims.dimension_info("minecraft:overworld", dims.DEFAULT_GENERATED)
    rd = dims.region_dir(Path(args.world), "minecraft:overworld")
    chunks = {}
    for rx in range(x0 >> 9, ((x1 - 1) >> 9) + 1):
        for rz in range(z0 >> 9, ((z1 - 1) >> 9) + 1):
            p = rd / f"r.{rx}.{rz}.mca"
            if p.exists():
                for lx, lz, c in anvil.read_region(str(p)):
                    if c.get("Status") == "minecraft:full":
                        c["_s"] = {s["Y"]: s for s in c.get("sections", [])}
                        chunks[(rx * 32 + lx, rz * 32 + lz)] = c

    def blk(x, y, z):
        c = chunks.get((x >> 4, z >> 4))
        if c is None:
            return None, None
        s = c["_s"].get(y >> 4)
        if s is None:
            return "minecraft:air", None
        return state(section_lookup(s, "block_states", ((y & 15) * 16 + (z & 15)) * 16 + (x & 15), 4))

    def biome(x, y, z):
        c = chunks.get((x >> 4, z >> 4))
        s = c["_s"].get(y >> 4) if c else None
        if s is None:
            return ""
        return state(section_lookup(s, "biomes", ((y & 15) >> 2) * 16 + ((z & 15) >> 2) * 4 + ((x & 15) >> 2), 1))[0]

    # WORLD_SURFACE_WG is gone after generation; WORLD_SURFACE (incl. vegetation) is the closest proxy.
    def top(x, z):
        c = chunks.get((x >> 4, z >> 4))
        if c is None:
            return None
        if "_h" not in c:
            c["_h"] = anvil.unpack_longs(c["Heightmaps"]["WORLD_SURFACE"], height.bit_length(), 256)
        return c["_h"][(z & 15) * 16 + (x & 15)] + min_y  # first air above the surface, like the heightmap placement

    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    sites = Counter()
    embedded = 0
    columns = 0
    for x in range(x0 + 1, x1 - 1):
        for z in range(z0 + 1, z1 - 1):
            h = top(x, z)
            if h is None:
                continue
            columns += 1
            for k in range(args.depth[0], args.depth[1] + 1):
                y = h - k
                if y < 72:
                    continue
                n_here, _ = blk(x, y, z)
                above, _ = blk(x, y + 1, z)
                below, _ = blk(x, y - 1, z)
                if above not in valid or below not in valid or not (n_here == "minecraft:air" or n_here in valid):
                    continue
                rocks = holes = 0
                open_dir = None
                for dx, dz in dirs:
                    nb, _ = blk(x + dx, y, z + dz)
                    if nb in valid:
                        rocks += 1
                    elif nb == "minecraft:air":
                        holes += 1
                        open_dir = (dx, dz)
                if rocks != 3 or holes != 1:
                    continue
                dx, dz = open_dir
                if all(blk(x + dx, y - d, z + dz)[0] == "minecraft:air" for d in sorted({0, args.drop // 2, args.drop})):
                    sites["ok_" + ("water_biome" if biome(x, y, z) in water_biomes else "other_biome")] += 1
            # embedded water sources in this column's faces
            for y in range(max(72, h - 30), h):
                n, props = blk(x, y, z)
                if n == "minecraft:water" and (props or {}).get("level", "0") == "0":
                    side = [blk(x + dx, y, z + dz)[0] for dx, dz in dirs]
                    if sum(1 for s in side if s in valid) == 3 and blk(x, y + 1, z)[0] in valid:
                        embedded += 1
    n_chunks = len({(x >> 4, z >> 4) for x in range(x0, x1, 16) for z in range(z0, z1, 16)})
    print(f"columns {columns}, chunks ~{n_chunks}")
    print(f"valid spring positions (column, depth): {dict(sites)}")
    print(f"water sources embedded in faces (3 rock sides + rock above): {embedded}")


if __name__ == "__main__":
    main()
